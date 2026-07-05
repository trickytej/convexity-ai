"""Scout API — podcast appearance monitoring."""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

from ...registry import Show
from ...store import repo
from ...store.models import Episode, EpisodeStatus, Segment, Transcript, TranscriptSource
from ..deps import get_db

router = APIRouter(tags=["scout"])

# In-process state for the most recent /scout/refresh background run. Fine as a
# module-level dict since the API runs as a single uvicorn worker (see Dockerfile).
_refresh_state: dict = {
    "status": "idle",  # idle | running | done | error
    "started_at": None,
    "finished_at": None,
    "new": 0,
    "skipped": 0,
    "errors": [],
}

_SCOUT_SHOW_SLUG = "scout"
_SCOUT_SHOW = Show(
    slug=_SCOUT_SHOW_SLUG,
    name="Scout",
    tier="B",
    transcript_source="asr",
    active=True,
)

# Podscan transcript line format:
# [HH:MM:SS.mmm --> HH:MM:SS.mmm] [SPEAKER_XX] text...
_LINE_RE = re.compile(
    r"^\[(\d{2}:\d{2}:\d{2}\.\d+)\s*-->\s*(\d{2}:\d{2}:\d{2}\.\d+)\]\s*"
    r"(?:\[(\w+)\]\s*)?(.+)$"
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ts_ms(ts: str) -> int:
    h, m, s = ts.split(":")
    return int((int(h) * 3600 + int(m) * 60 + float(s)) * 1000)


def _parse_podscan_transcript(text: str) -> list[Segment]:
    segments = []
    for i, line in enumerate(text.splitlines()):
        line = line.strip()
        if not line:
            continue
        m = _LINE_RE.match(line)
        if not m:
            continue
        segments.append(
            Segment(
                idx=i,
                start_ms=_ts_ms(m.group(1)),
                end_ms=_ts_ms(m.group(2)),
                speaker_label=m.group(3),
                text=m.group(4).strip(),
            )
        )
    return segments


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
    background_tasks: BackgroundTasks,
    days: int = Query(30, description="Look-back window in days"),
) -> dict:
    """Kick off a Podscan scan in the background and return immediately.

    The scan queries every tracked person (100+ calls at ~1 s each), so it
    runs in a background thread to avoid blocking the HTTP response. Poll
    GET /scout/refresh/status for the real outcome.
    """
    from ...config import get_settings
    from ...store.db import connect as _db_connect
    from ...scout.pipeline import run_cycle

    _refresh_state.update(
        status="running", started_at=_now_iso(), finished_at=None, new=0, skipped=0, errors=[],
    )

    def _run() -> None:
        settings = get_settings()
        conn = _db_connect(settings.resolved_db_path)
        try:
            result = run_cycle(conn, days=days)
            _refresh_state.update(
                status="error" if result.errors and not (result.new or result.skipped) else "done",
                finished_at=_now_iso(),
                new=result.new,
                skipped=result.skipped,
                errors=result.errors[:5],
            )
        except Exception as exc:
            _refresh_state.update(status="error", finished_at=_now_iso(), errors=[str(exc)])
        finally:
            conn.close()

    background_tasks.add_task(_run)
    return {"status": "started"}


@router.get("/scout/refresh/status")
def refresh_status() -> dict:
    """Return the state of the most recent (or in-progress) /scout/refresh run."""
    return _refresh_state


def _run_process(episode_id: int) -> None:
    """Background task: (acquire →) transcribe → insights.

    If the episode already has a transcript stored (from Podscan), skips straight
    to insights extraction without hitting AssemblyAI.
    """
    from ...config import get_settings
    from ...store.db import connect as _db_connect
    from ...pipeline import acquire_episode, generate_insights, transcribe_episode
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

        # Already transcribed (e.g. transcript came from Podscan) — go straight to insights.
        if ep.status == EpisodeStatus.TRANSCRIBED:
            generate_insights(conn, ep, show, settings)
            return

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

    If the appearance has a Podscan transcript, it is stored directly and the
    episode is marked TRANSCRIBED so the background task skips AssemblyAI.

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

    # Store Podscan transcript directly if available — skips AssemblyAI entirely.
    transcript_text = row["transcript"] if "transcript" in row.keys() else None
    if transcript_text:
        segments = _parse_podscan_transcript(transcript_text)
        t = Transcript(
            episode_id=episode_id,
            source=TranscriptSource.ASR,
            provider="podscan",
            has_diarization=True,
            word_count=len(transcript_text.split()),
            segments=segments,
        )
        repo.insert_transcript(db, t)
        repo.set_status(db, episode_id, EpisodeStatus.TRANSCRIBED)

    db.execute(
        "UPDATE scout_appearances SET episode_id = ? WHERE id = ?",
        (episode_id, appearance_id),
    )
    db.commit()

    return {"episode_id": episode_id, "created": True}
