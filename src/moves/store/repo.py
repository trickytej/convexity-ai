"""Read/write helpers over the DuckDB store.

Writes are idempotent upserts keyed on natural keys, so re-ingesting an
overlapping window never duplicates rows.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import duckdb
import pandas as pd

_BAR_COLS = [
    "symbol",
    "timeframe",
    "ts",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "vwap",
    "transactions",
]


def upsert_bars(
    con: duckdb.DuckDBPyConnection, symbol: str, timeframe: str, df: pd.DataFrame
) -> int:
    """Insert/update OHLCV bars for one symbol/timeframe. Returns rows written."""
    if df is None or df.empty:
        return 0
    frame = df.copy()
    frame["symbol"] = symbol
    frame["timeframe"] = timeframe
    frame = frame[_BAR_COLS]
    cols = ", ".join(_BAR_COLS)
    con.register("_incoming_bars", frame)
    try:
        con.execute(
            f"""
            INSERT INTO bars ({cols})
            SELECT {cols} FROM _incoming_bars
            ON CONFLICT (symbol, timeframe, ts) DO UPDATE SET
                open = excluded.open, high = excluded.high, low = excluded.low,
                close = excluded.close, volume = excluded.volume,
                vwap = excluded.vwap, transactions = excluded.transactions
            """
        )
    finally:
        con.unregister("_incoming_bars")
    return len(frame)


def get_bars(
    con: duckdb.DuckDBPyConnection,
    symbol: str,
    timeframe: str,
    start: datetime | None = None,
    end: datetime | None = None,
) -> pd.DataFrame:
    """Return ordered OHLCV bars for one symbol/timeframe as a DataFrame."""
    query = (
        "SELECT ts, open, high, low, close, volume, vwap, transactions "
        "FROM bars WHERE symbol = ? AND timeframe = ?"
    )
    params: list[Any] = [symbol, timeframe]
    if start is not None:
        query += " AND ts >= ?"
        params.append(start)
    if end is not None:
        query += " AND ts <= ?"
        params.append(end)
    query += " ORDER BY ts"
    return con.execute(query, params).df()


def latest_bar_ts(
    con: duckdb.DuckDBPyConnection, symbol: str, timeframe: str
) -> datetime | None:
    """Most recent stored bar timestamp for a symbol/timeframe, or None."""
    row = con.execute(
        "SELECT max(ts) FROM bars WHERE symbol = ? AND timeframe = ?", [symbol, timeframe]
    ).fetchone()
    return row[0] if row and row[0] is not None else None


def list_symbols(con: duckdb.DuckDBPyConnection, timeframe: str | None = None) -> list[str]:
    """Distinct symbols present in the store, optionally filtered by timeframe."""
    if timeframe:
        rows = con.execute(
            "SELECT DISTINCT symbol FROM bars WHERE timeframe = ? ORDER BY symbol", [timeframe]
        ).fetchall()
    else:
        rows = con.execute("SELECT DISTINCT symbol FROM bars ORDER BY symbol").fetchall()
    return [r[0] for r in rows]


def bar_counts(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Per symbol/timeframe coverage: row count and first/last timestamp."""
    return con.execute(
        """
        SELECT symbol, timeframe, count(*) AS n_bars, min(ts) AS first_ts, max(ts) AS last_ts
        FROM bars GROUP BY symbol, timeframe ORDER BY symbol, timeframe
        """
    ).df()


def upsert_splits(con: duckdb.DuckDBPyConnection, symbol: str, df: pd.DataFrame) -> int:
    if df is None or df.empty:
        return 0
    frame = df.copy()
    frame["symbol"] = symbol
    frame = frame[["symbol", "ex_date", "split_from", "split_to"]]
    con.register("_incoming_splits", frame)
    try:
        con.execute(
            """
            INSERT INTO splits (symbol, ex_date, split_from, split_to)
            SELECT symbol, ex_date, split_from, split_to FROM _incoming_splits
            ON CONFLICT (symbol, ex_date) DO UPDATE SET
                split_from = excluded.split_from, split_to = excluded.split_to
            """
        )
    finally:
        con.unregister("_incoming_splits")
    return len(frame)


def upsert_dividends(con: duckdb.DuckDBPyConnection, symbol: str, df: pd.DataFrame) -> int:
    if df is None or df.empty:
        return 0
    frame = df.copy()
    frame["symbol"] = symbol
    frame = frame[["symbol", "ex_date", "cash_amount", "frequency"]]
    con.register("_incoming_divs", frame)
    try:
        con.execute(
            """
            INSERT INTO dividends (symbol, ex_date, cash_amount, frequency)
            SELECT symbol, ex_date, cash_amount, frequency FROM _incoming_divs
            ON CONFLICT (symbol, ex_date) DO UPDATE SET
                cash_amount = excluded.cash_amount, frequency = excluded.frequency
            """
        )
    finally:
        con.unregister("_incoming_divs")
    return len(frame)


def upsert_news(con: duckdb.DuckDBPyConnection, items: list[dict[str, Any]]) -> int:
    """Insert news items (dedup on id). Each item carries a list of tickers."""
    if not items:
        return 0
    rows = [
        (
            it["id"],
            it.get("published_utc"),
            it.get("title"),
            it.get("article_url"),
            it.get("publisher"),
            it.get("tickers", []),
            it.get("description"),
        )
        for it in items
    ]
    con.executemany(
        """
        INSERT INTO news (id, published_utc, title, article_url, publisher, tickers, description)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (id) DO NOTHING
        """,
        rows,
    )
    return len(rows)
