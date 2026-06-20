"""DuckDB connection and schema management.

DuckDB is the engine of record for the heavy time-series (bars) plus the
reference data needed to attribute moves (splits, dividends, news). It embeds
like SQLite (single file, no server) but is columnar and built for the
analytical scans the move/basket/event-study layers run. All timestamps are
stored as naive UTC (`TIMESTAMP`) by convention.
"""

from __future__ import annotations

import duckdb

from moves.config import get_settings

_SCHEMA: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS bars (
        symbol       VARCHAR   NOT NULL,
        timeframe    VARCHAR   NOT NULL,
        ts           TIMESTAMP NOT NULL,
        open         DOUBLE,
        high         DOUBLE,
        low          DOUBLE,
        close        DOUBLE,
        volume       DOUBLE,
        vwap         DOUBLE,
        transactions BIGINT,
        PRIMARY KEY (symbol, timeframe, ts)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS splits (
        symbol     VARCHAR NOT NULL,
        ex_date    DATE    NOT NULL,
        split_from DOUBLE,
        split_to   DOUBLE,
        PRIMARY KEY (symbol, ex_date)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS dividends (
        symbol      VARCHAR NOT NULL,
        ex_date     DATE    NOT NULL,
        cash_amount DOUBLE,
        frequency   INTEGER,
        PRIMARY KEY (symbol, ex_date)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS news (
        id            VARCHAR PRIMARY KEY,
        published_utc TIMESTAMP,
        title         VARCHAR,
        article_url   VARCHAR,
        publisher     VARCHAR,
        tickers       VARCHAR[],
        description   VARCHAR
    )
    """,
)


def connect(read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """Open a DuckDB connection to the configured store, creating the dir if needed."""
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(settings.duckdb_path), read_only=read_only)


def init_db(con: duckdb.DuckDBPyConnection | None = None) -> None:
    """Create all tables if they do not exist (idempotent)."""
    owned = con is None
    con = con or connect()
    try:
        for stmt in _SCHEMA:
            con.execute(stmt)
    finally:
        if owned:
            con.close()
