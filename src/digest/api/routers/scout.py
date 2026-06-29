"""Scout API — podcast appearance monitoring."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

from ...registry import Show
from ...store import repo
from ...store.models import Episode
from ..deps import get_db

router = APIRouter(tags=["scout"])

_SCOUT_SHOW_SLUG = "scout"
_SCOUT_SHOW = Show(
    slug=_SCOUT_SHOW_SLUG,
    name="Scout",
    tier="B",
    transcript_source="asr",
    active=True,
)


def _row_to_appearance(row: sqlite3.Row) -> dict:
    keys = row.keys()
    return {
        "id":            row["id"],
        "company":       row["company"],
        "person_name":   row["person_name"] if "person_name" in keys else None,
        "person_role":   row["person_role"] if "person_role" in keys else None,
        "episode_id":    row["episode_id"] if "episode_id" in keys else None,
        "episode_title": row["episode_title"],
        "podcast_name":  row["podcast_name"],
        "episode_url":   row["episode_url"],
        "thumbnail":     row["thumbnail"],
        "description":   row["description"],
        "published_at":  row["published_at"],
        "created_at":    row["created_at"],
    }


@router.get("/scout/appearances")
def list_appearances(
    company: str | None = Query(None),
    days:    int        = Query(90),
    limit:   int        = Query(200),
    db: sqlite3.Connection = Depends(get_db),
) -> list[dict]:
    """Return stored Scout appearances, newest first."""
    sql = "SELECT * FROM scout_appearances WHERE 1=1"
    params: list = []

    if company:
        sql += " AND company = ?"
        params.append(company)

    if days:
        sql += " AND (published_at IS NULL OR published_at >= datetime('now', ?))"
        params.append(f"-{days} days")

    sql += " ORDER BY published_at DESC, created_at DESC LIMIT ?"
    params.append(limit)

    rows = db.execute(sql, params).fetchall()
    return [_row_to_appearance(r) for r in rows]


@router.post("/scout/refresh")
def refresh_appearances(
    days: int = Query(30, description="Look-back window in days"),
    db: sqlite3.Connection = Depends(get_db),
) -> dict:
    """Trigger a Listen Notes search for all watchlist people and persist confirmed appearances."""
    from ...scout.pipeline import run_cycle
    result = run_cycle(db, days=days)
    return {
        "new":      result.new,
        "skipped":  result.skipped,
        "filtered": result.filtered,
        "errors":   result.errors,
    }


def _run_process(episode_id: int) -> None:
    """Background task: acquire → transcribe → insights."""
    from ...config import get_settings
    from ...store.db import connect as _db_connect
    from ...pipeline import acquire_episode, generate_insights, transcribe_episode
    from ...store.models import EpisodeStatus
    from ...registry import Glossary, Registry
    import logging
    log = logging.getLogger(__name__)

    settings = get_settings()
    conn = _db_connect(settings.resolved_db_path)
    try:
        ep = repo.get_episode(conn, episode_id)
        if ep is None:
            return
        show_row = conn.execute("SELECT * FROM shows WHERE slug = ?", (ep.show_slug,)).fetchone()
        if show_row is None:
            return
        show = Show(
            slug=show_row["slug"],
            name=show_row["name"],
            rss_url=show_row["rss_url"] or "",
            tier=show_row["tier"],
            transcript_source=show_row["transcript_source"] or "asr",
            hosts=json.loads(show_row["hosts"]) if show_row["hosts"] else [],
            format=show_row["format"] or "interview",
            active=bool(show_row["active"]),
        )
        try:
            glossary = Registry.load(settings.shows_file).glossary
        except Exception:
            glossary = Glossary()

        def _audio_valid(path: str | None) -> bool:
            if not path:
                return False
            from pathlib import Path as _P
            from ...acquire.audio import _is_valid_audio_file
            p = _P(path)
            return p.exists() and _is_valid_audio_file(p)

        needs_acquire = ep.status not in (EpisodeStatus.ACQUIRED, EpisodeStatus.TRANSCRIBED) or (
            ep.status == EpisodeStatus.ACQUIRED and not _audio_valid(ep.audio_path)
        )
        if needs_acquire:
            acquire_episode(conn, ep, show, settings)
            ep = repo.get_episode(conn, episode_id)
            if ep is None:
                return

        if ep.status == EpisodeStatus.ACQUIRED:
            result = transcribe_episode(conn, ep, show, glossary, settings)
            if not result.ok:
                return
            ep = repo.get_episode(conn, episode_id)
            if ep is None:
                return

        if ep.status == EpisodeStatus.TRANSCRIBED:
            generate_insights(conn, ep, show, settings)
    except Exception as exc:
        log.error("scout process error for episode %s: %s", episode_id, exc, exc_info=True)
        try:
            ep = repo.get_episode(conn, episode_id)
            if ep is not None:
                from ...store.models import EpisodeStatus as _S
                if ep.status not in (_S.TRANSCRIBED, _S.FAILED):
                    repo.set_status(conn, episode_id, _S.FAILED, error=f"{type(exc).__name__}: {exc}")
        except Exception:
            pass
    finally:
        conn.close()


@router.post("/scout/appearances/{appearance_id}/ingest")
def ingest_appearance(
    appearance_id: int,
    db: sqlite3.Connection = Depends(get_db),
) -> dict:
    """Create an episode record from a Scout appearance and kick off transcription.

    Idempotent: if the appearance already has an episode_id, returns it immediately.
    """
    row = db.execute(
        "SELECT * FROM scout_appearances WHERE id = ?", (appearance_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="appearance not found")

    # Already ingested — just return the episode id
    if row["episode_id"]:
        return {"episode_id": row["episode_id"], "created": False}

    audio_url   = row["audio_url"]   or row["episode_url"] or ""
    episode_url = row["episode_url"] or ""

    if not audio_url:
        raise HTTPException(status_code=422, detail="No audio URL available for this appearance")

    # Ensure the scout catch-all show exists
    if not db.execute("SELECT slug FROM shows WHERE slug = ?", (_SCOUT_SHOW_SLUG,)).fetchone():
        repo.sync_shows(db, [_SCOUT_SHOW])

    # Idempotent on audio_url
    existing = db.execute(
        "SELECT id FROM episodes WHERE audio_url = ? AND show_slug = ?",
        (audio_url, _SCOUT_SHOW_SLUG),
    ).fetchone()
    if existing:
        episode_id = existing["id"]
        db.execute(
            "UPDATE scout_appearances SET episode_id = ? WHERE id = ?",
            (episode_id, appearance_id),
        )
        db.commit()
        return {"episode_id": episode_id, "created": False}

    pub_at = None
    if row["published_at"]:
        try:
            pub_at = datetime.fromisoformat(row["published_at"])
        except ValueError:
            pass

    ep = Episode(
        show_slug=_SCOUT_SHOW_SLUG,
        guid=audio_url,
        title=row["episode_title"],
        audio_url=audio_url,
        episode_url=episode_url,
        published_at=pub_at,
    )
    episode_id, _ = repo.upsert_episode(db, ep)

    db.execute(
        "UPDATE scout_appearances SET episode_id = ? WHERE id = ?",
        (episode_id, appearance_id),
    )
    db.commit()

    return {"episode_id": episode_id, "created": True}
