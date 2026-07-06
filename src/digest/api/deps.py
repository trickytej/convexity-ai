"""FastAPI dependencies."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator

from fastapi import HTTPException

from ..config import get_settings
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
