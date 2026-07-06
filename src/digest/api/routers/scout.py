"""Scout API — podcast appearance monitoring."""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

from ...config import get_settings
from ...scout.pipeline import ingest_appearance_row
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

# A full scan costs one Podscan request per tracked person (~72) against a
# 100-requests/day plan quota, so at most one full scan per day is sustainable.
# Refreshes inside this window return "cooldown" instead of burning the quota.
_REFRESH_COOLDOWN_HOURS = float(os.environ.get("SCOUT_REFRESH_COOLDOWN_HOURS", "20"))

_META_TABLE_SQL = "CREATE TABLE IF NOT EXISTS app_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"


def _meta_get(conn, key: str) -> str | None:
    conn.execute(_META_TABLE_SQL)
    row = conn.execute("SELECT value FROM app_meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def _meta_set(conn, key: str, value: str) -> None:
    conn.execute(_META_TABLE_SQL)
    conn.execute(
        "INSERT INTO app_meta (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    conn.commit()


def _meta_datetime(conn, key: str) -> datetime | None:
    raw = _meta_get(conn, key)
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
    force: bool = Query(False, description="Bypass the scan cooldown"),
    db: sqlite3.Connection = Depends(get_db),
) -> dict:
    """Kick off a Podscan scan in the background and return immediately.

    The scan queries every tracked person (~72 requests, ≥1 s apart) against a
    100-requests/day Podscan quota, so it runs in a background thread and at
    most once per cooldown window. Poll GET /scout/refresh/status for the
    real outcome.
    """
    from ...config import get_settings
    from ...store.db import connect as _db_connect
    from ...scout.pipeline import run_cycle

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
            if result.quota_reset_at:
                _meta_set(conn, "scout_quota_reset_at", result.quota_reset_at)
            if not result.aborted:
                # Full pass completed — start the cooldown clock.
                _meta_set(conn, "scout_last_scan_at", _now_iso())
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
    from ...store.db import connect as _db_connect

    settings = get_settings()
    conn = _db_connect(settings.resolved_db_path)
    try:
        process_episode_pipeline(conn, episode_id, settings)
    finally:
        conn.close()


@router.post("/scout/reprocess-pending")
def reprocess_pending(background_tasks: BackgroundTasks, db: sqlite3.Connection = Depends(get_db)) -> dict:
    """Retry insight extraction for appearances already ingested but not yet
    insights_extracted (e.g. the nightly scout-sync job's LLM call failed, or
    was interrupted mid-run). Fast: no Podscan/AssemblyAI calls for episodes
    that already have a transcript — just the LLM extraction step.
    """
    rows = db.execute(
        """
        SELECT sa.episode_id FROM scout_appearances sa
        JOIN episodes e ON e.id = sa.episode_id
        WHERE e.status IN ('transcribed', 'failed')
        """
    ).fetchall()
    for row in rows:
        background_tasks.add_task(_reprocess_one, row["episode_id"])
    return {"queued": len(rows)}


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

    try:
        episode_id, created = ingest_appearance_row(db, row, get_settings())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return {"episode_id": episode_id, "created": created}
