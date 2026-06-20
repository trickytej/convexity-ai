"""SQLite cache for generated move insights.

Kept separate from the DuckDB bars store: insights are written on demand while
the API holds read-only DuckDB connections, and DuckDB allows only one writer.
SQLite (WAL) handles concurrent readers + a writer cleanly.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from typing import Any

from moves.config import get_settings


def cache_connect() -> sqlite3.Connection:
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(settings.insights_cache_path))
    con.execute("PRAGMA journal_mode=WAL")
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS insights (
            key        TEXT PRIMARY KEY,
            payload    TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    return con


def insight_key(symbol: str, timeframe: str, start_time: int, end_time: int) -> str:
    return f"{symbol.upper()}:{timeframe}:{start_time}:{end_time}"


def get_cached(con: sqlite3.Connection, key: str) -> dict[str, Any] | None:
    row = con.execute("SELECT payload FROM insights WHERE key = ?", [key]).fetchone()
    return json.loads(row[0]) if row else None


def put_cached(con: sqlite3.Connection, key: str, payload: dict[str, Any]) -> None:
    con.execute(
        "INSERT OR REPLACE INTO insights (key, payload, created_at) VALUES (?, ?, ?)",
        [key, json.dumps(payload), datetime.now(UTC).isoformat()],
    )
    con.commit()
