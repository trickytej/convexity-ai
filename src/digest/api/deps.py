"""FastAPI dependencies."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator

from fastapi import Depends, Header, HTTPException

from ..config import get_settings
from ..store import repo
from ..store.db import TursoNotConfiguredError, connect, connect_turso


def get_db() -> Iterator[sqlite3.Connection]:
    """One SQLite connection per request (read-mostly; WAL handles concurrency)."""
    settings = get_settings()
    conn = connect(settings.resolved_db_path)
    try:
        yield conn
    finally:
        conn.close()


def get_scout_db() -> Iterator[sqlite3.Connection]:
    """Scout always reads/writes the hosted (Turso) database, never the local
    file — appearance data must land where production serves it from."""
    try:
        conn = connect_turso(get_settings())
    except TursoNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    try:
        yield conn
    finally:
        conn.close()


def is_guest(x_guest: str | None = Header(None)) -> bool:
    """A signed-out visitor browsing the read-only demo (set by the frontend proxy)."""
    return x_guest == "1"


def current_user_id(
    x_user_id: str | None = Header(None),
    guest: bool = Depends(is_guest),
    db: sqlite3.Connection = Depends(get_db),
) -> int:
    """The signed-in user, as asserted by the frontend.

    Trusted only because the API-key middleware has already authenticated the
    caller as our frontend, which sets X-User-Id from its own session (and
    strips any browser-supplied value). Signed-out demo visitors (X-Guest: 1)
    see the house account; the middleware has already limited them to reads.
    """
    if not x_user_id and guest:
        house = repo.house_user_id(db)
        return house if house is not None else _unauthenticated()
    try:
        return int(x_user_id) if x_user_id else _unauthenticated()
    except ValueError:
        return _unauthenticated()


def _unauthenticated() -> int:
    raise HTTPException(status_code=401, detail="sign in required")


def require_admin(
    user_id: int = Depends(current_user_id),
    db: sqlite3.Connection = Depends(get_db),
) -> int:
    """Curator-only endpoints (ingestion, scout, newsletter, curation writes)."""
    user = repo.get_user(db, user_id)
    if not user or not user["is_admin"]:
        raise HTTPException(status_code=403, detail="admin only")
    return user_id


def visible_episode(
    episode_id: int,
    x_user_id: str | None = Header(None),
    db: sqlite3.Connection = Depends(get_db),
) -> None:
    """404 for another user's private research episode — admins included.
    Shared-corpus episodes are visible to everyone signed in."""
    row = db.execute("SELECT owner_user_id FROM episodes WHERE id = ?", (episode_id,)).fetchone()
    if row is None or row["owner_user_id"] is None:
        return
    if not x_user_id or str(row["owner_user_id"]) != x_user_id:
        raise HTTPException(status_code=404, detail="episode not found")
