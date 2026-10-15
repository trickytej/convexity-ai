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


def current_user_id(x_user_id: str | None = Header(None)) -> int:
    """The signed-in user, as asserted by the frontend.

    Trusted only because the API-key middleware has already authenticated the
    caller as our frontend, which sets X-User-Id from its own session (and
    strips any browser-supplied value).
    """
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
