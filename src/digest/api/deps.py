"""FastAPI dependencies."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator

from ..config import get_settings
from ..store.db import connect


def get_db() -> Iterator[sqlite3.Connection]:
    """One SQLite connection per request (read-mostly; WAL handles concurrency)."""
    settings = get_settings()
    conn = connect(settings.resolved_db_path)
    try:
        yield conn
    finally:
        conn.close()
