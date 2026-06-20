"""Persistence layer: DuckDB store for bars, corporate actions, and news."""

from moves.store.db import connect, init_db
from moves.store.repo import (
    bar_counts,
    get_bars,
    latest_bar_ts,
    list_symbols,
    upsert_bars,
    upsert_dividends,
    upsert_news,
    upsert_splits,
)

__all__ = [
    "bar_counts",
    "connect",
    "get_bars",
    "init_db",
    "latest_bar_ts",
    "list_symbols",
    "upsert_bars",
    "upsert_dividends",
    "upsert_news",
    "upsert_splits",
]
