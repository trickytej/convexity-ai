"""Scout API — podcast appearance and X (Twitter) account monitoring."""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

from ...config import get_settings
from ...scout import roster
from ...scout import x as x_scout
from ...scout.pipeline import ingest_appearance_row
from ...store import repo
from ...store.db import connect_turso
from ..deps import get_scout_db
from .curation import _nugget_with_curation_out

log = logging.getLogger(__name__)
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
    "roster_size": 0,
    "processing_done": 0,
    "processing_total": 0,
}

# Same idea for the X (tweets) refresh — independent of the podcast scan so the
# two buttons in the UI can run and report separately.
_x_refresh_state: dict = {
    "status": "idle",  # idle | running | done | error
    "started_at": None,
    "finished_at": None,
    "new": 0,
    "skipped": 0,
    "errors": [],
    "handles_synced": 0,
}

# A full scan costs one Podscan request per tracked person against a
# 100-requests/day plan quota, so at most one full scan per day is sustainable.
# Refreshes inside this window return "cooldown" instead of burning the quota.
_REFRESH_COOLDOWN_HOURS = float(os.environ.get("SCOUT_REFRESH_COOLDOWN_HOURS", "20"))


def _meta_datetime(conn, key: str) -> datetime | None:
    raw = repo.meta_get(conn, key)
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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
    db: sqlite3.Connection = Depends(get_scout_db),
) -> list[dict]:
    """Return stored Scout appearances, newest first. Dismissed ones are hidden."""
    sql = "SELECT * FROM scout_appearances WHERE dismissed = 0"
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


@router.get("/scout/watchlist")
def get_watchlist(db: sqlite3.Connection = Depends(get_scout_db)) -> dict:
    """Return the tracked companies/people, seeding defaults on first use."""
    return {"watchlist": roster.load_watchlist(db)}


@router.put("/scout/watchlist")
def put_watchlist(watchlist: list[dict], db: sqlite3.Connection = Depends(get_scout_db)) -> dict:
    """Save the tracked companies/people — the single source of truth the next
    /scout/refresh scan searches against."""
    roster.save_watchlist(db, watchlist)
    return {"watchlist": watchlist}


@router.post("/scout/refresh")
def refresh_appearances(
    background_tasks: BackgroundTasks,
    days: int = Query(30, description="Look-back window in days"),
    force: bool = Query(False, description="Bypass the scan cooldown"),
    db: sqlite3.Connection = Depends(get_scout_db),
) -> dict:
    """Kick off a Podscan scan for the current watchlist in the background, then
    ingest + transcribe + extract insights for everything it finds within the
    *days* window (older pending appearances are left for a manually triggered
    scout-sync run) and return immediately. Poll GET /scout/refresh/status for
    the real outcome.
    """
    from ...scout.pipeline import sync_and_process

    if _refresh_state["status"] == "running":
        return {"status": "already_running"}

    now = datetime.now(timezone.utc)

    if not force:
        # Known quota exhaustion from a previous run — refuse until it resets.
        quota_reset = _meta_datetime(db, "scout_quota_reset_at")
        if quota_reset and quota_reset > now:
            return {
                "status": "cooldown",
                "reason": "quota",
                "retry_at": quota_reset.isoformat(),
            }

        last_scan = _meta_datetime(db, "scout_last_scan_at")
        if last_scan:
            next_allowed = last_scan + timedelta(hours=_REFRESH_COOLDOWN_HOURS)
            if next_allowed > now:
                return {
                    "status": "cooldown",
                    "reason": "recent_scan",
                    "last_scan_at": last_scan.isoformat(),
                    "retry_at": next_allowed.isoformat(),
                }

    flat_roster = roster.flatten_watchlist(roster.load_watchlist(db))

    _refresh_state.update(
        status="running", started_at=_now_iso(), finished_at=None, new=0, skipped=0, errors=[],
        roster_size=len(flat_roster), processing_done=0, processing_total=0,
    )

    def _on_progress(done: int, total: int) -> None:
        _refresh_state.update(processing_done=done, processing_total=total)

    def _run() -> None:
        settings = get_settings()
        conn = connect_turso(settings)
        try:
            result = sync_and_process(
                conn, settings, flat_roster, days=days,
                scope_sweep_to_days=True, on_progress=_on_progress,
            )
            _refresh_state.update(
                status="error" if result.errors and not (result.new or result.skipped) else "done",
                finished_at=_now_iso(),
                new=result.new,
                skipped=result.skipped,
                errors=result.errors[:5],
                processing_done=result.processed,
                processing_total=result.processing_total,
            )
            if result.quota_reset_at:
                repo.meta_set(conn, "scout_quota_reset_at", result.quota_reset_at)
            if not result.aborted:
                # Full pass completed — start the cooldown clock.
                repo.meta_set(conn, "scout_last_scan_at", _now_iso())
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


def _reprocess_one(episode_id: int) -> None:
    from ...pipeline import process_episode_pipeline

    settings = get_settings()
    conn = connect_turso(settings)
    try:
        process_episode_pipeline(conn, episode_id, settings)
    finally:
        conn.close()


@router.post("/scout/reprocess-pending")
def reprocess_pending(background_tasks: BackgroundTasks, db: sqlite3.Connection = Depends(get_scout_db)) -> dict:
    """Retry insight extraction for appearances already ingested but not yet
    insights_extracted (e.g. the nightly scout-sync job's LLM call failed, or
    was interrupted mid-run). Fast: no Podscan/AssemblyAI calls for episodes
    that already have a transcript — just the LLM extraction step.
    """
    try:
        rows = db.execute(
            """
            SELECT sa.episode_id FROM scout_appearances sa
            JOIN episodes e ON e.id = sa.episode_id
            WHERE e.status IN ('transcribed', 'failed') AND sa.dismissed = 0
            """
        ).fetchall()
        for row in rows:
            background_tasks.add_task(_reprocess_one, row["episode_id"])
        return {"queued": len(rows)}
    except Exception as exc:
        log.error("reprocess-pending failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}")


@router.delete("/scout/appearances/{appearance_id}")
def dismiss_appearance(
    appearance_id: int,
    db: sqlite3.Connection = Depends(get_scout_db),
) -> dict:
    """Soft-delete an appearance the user judged irrelevant.

    The row is kept (dismissed = 1) rather than deleted: its unique
    listennotes_id is what makes the next Podscan scan's INSERT OR IGNORE a
    no-op, so the appearance can't come back on refresh. Any episode/nuggets
    already extracted from it are left untouched.
    """
    cur = db.execute(
        "UPDATE scout_appearances SET dismissed = 1 WHERE id = ?", (appearance_id,)
    )
    db.commit()
    if not cur.rowcount:
        raise HTTPException(status_code=404, detail="appearance not found")
    return {"dismissed": True}


@router.post("/scout/appearances/{appearance_id}/ingest")
def ingest_appearance(
    appearance_id: int,
    db: sqlite3.Connection = Depends(get_scout_db),
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

    try:
        episode_id, created = ingest_appearance_row(db, row, get_settings())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return {"episode_id": episode_id, "created": created}


# ── X (Twitter) accounts ──────────────────────────────────────────────────────

@router.get("/scout/x-accounts")
def get_x_accounts(db: sqlite3.Connection = Depends(get_scout_db)) -> dict:
    """Tracked X handles plus whether the X API is usable (bearer token set)."""
    return {
        "handles": x_scout.load_accounts(db),
        "configured": bool(get_settings().x_bearer_token),
    }


@router.put("/scout/x-accounts")
def put_x_accounts(
    handles: list[str], db: sqlite3.Connection = Depends(get_scout_db)
) -> dict:
    """Save the tracked X handles — the list the next /scout/refresh pulls
    timelines for. Accepts @handles, bare handles, or profile URLs."""
    return {
        "handles": x_scout.save_accounts(db, handles),
        "configured": bool(get_settings().x_bearer_token),
    }


@router.post("/scout/refresh-x")
def refresh_x(
    background_tasks: BackgroundTasks,
    days: int = Query(7, description="Look-back window in days"),
) -> dict:
    """Pull tweets for every tracked X handle in the background — independent of
    the podcast scan (own quota, no Podscan cooldown). Poll
    GET /scout/refresh-x/status for the outcome."""
    if _x_refresh_state["status"] == "running":
        return {"status": "already_running"}

    _x_refresh_state.update(
        status="running", started_at=_now_iso(), finished_at=None,
        new=0, skipped=0, errors=[], handles_synced=0,
    )

    def _run_x() -> None:
        settings = get_settings()
        conn = connect_turso(settings)
        try:
            result = x_scout.sync_x_accounts(conn, settings, days=days)
            _x_refresh_state.update(
                status="error" if result.errors and not (result.new or result.skipped) else "done",
                finished_at=_now_iso(),
                new=result.new,
                skipped=result.skipped,
                errors=result.errors[:5],
                handles_synced=result.handles_synced,
            )
            # Freshly minted tweet nuggets should reach the "What Matters"
            # Brief same-day, not at the next nightly sweep. Best-effort.
            if result.new:
                try:
                    from ...theses import run_brief_match
                    run_brief_match(conn, settings, days=1)
                except Exception as exc:
                    log.warning("thesis matching after X sync failed: %s", exc)
        except Exception as exc:
            _x_refresh_state.update(status="error", finished_at=_now_iso(), errors=[str(exc)])
        finally:
            conn.close()

    background_tasks.add_task(_run_x)
    return {"status": "started"}


@router.get("/scout/refresh-x/status")
def refresh_x_status() -> dict:
    """Return the state of the most recent (or in-progress) /scout/refresh-x run."""
    return _x_refresh_state


@router.get("/scout/tweets")
def list_scout_tweets(
    days: int = Query(7, description="Look-back window in days"),
    db: sqlite3.Connection = Depends(get_scout_db),
) -> list[dict]:
    """Synced tweets from the window, bucketed by handle, each tweet carrying
    its keep/kill nugget (with curation) so the frontend renders the same
    review cards used for podcast insights."""
    buckets = x_scout.list_tweet_buckets(db, days=days)
    return [
        {
            "handle": b["handle"],
            "author_name": b["author_name"],
            "episode_id": b["episode_id"],
            "tweets": [
                {
                    "tweet_id": r["tweet_id"],
                    "url": r["url"],
                    "created_at": r["created_at"],
                    "metrics": json.loads(r["metrics"]) if r["metrics"] else None,
                    "nugget": _nugget_with_curation_out(r),
                }
                for r in b["tweets"]
            ],
        }
        for b in buckets
    ]
