"""Backfill orchestration: pull bars (and optionally corporate actions / news)
from Polygon into the DuckDB store. Idempotent and resumable."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import date, datetime

import duckdb

from moves.providers import PolygonClient
from moves.store import (
    upsert_bars,
    upsert_dividends,
    upsert_news,
    upsert_splits,
)


def backfill(
    con: duckdb.DuckDBPyConnection,
    client: PolygonClient,
    symbols: Iterable[str],
    timeframe: str,
    start: str | date | datetime,
    end: str | date | datetime,
    *,
    corporate_actions: bool = False,
    news: bool = False,
    progress: Callable[[str, int], None] | None = None,
) -> dict[str, int]:
    """Backfill ``timeframe`` bars for each symbol over [start, end].

    Returns a {symbol: bars_written} map. When ``corporate_actions`` is set,
    splits + dividends are refreshed; when ``news`` is set, recent ticker news is
    pulled. ``progress`` is called with (symbol, bars_written) after each symbol.
    """
    written: dict[str, int] = {}
    for symbol in symbols:
        df = client.get_aggs_df(symbol, timeframe, start, end)
        n = upsert_bars(con, symbol, timeframe, df)
        written[symbol] = n

        if corporate_actions:
            upsert_splits(con, symbol, client.get_splits(symbol))
            upsert_dividends(con, symbol, client.get_dividends(symbol))
        if news:
            upsert_news(con, client.get_news(symbol, since=start))

        if progress is not None:
            progress(symbol, n)
    return written
