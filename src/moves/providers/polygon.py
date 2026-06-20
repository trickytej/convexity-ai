"""Polygon.io (Massive) client: REST backfill + corporate actions + news, and a
real-time WebSocket aggregate stream.

REST calls are wrapped with exponential-backoff retries. All bar timestamps are
normalized to naive UTC to match the store convention.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Callable
from datetime import date, datetime
from typing import Any

import pandas as pd
from polygon import RESTClient, WebSocketClient
from polygon.websocket.models import Feed, Market
from tenacity import retry, stop_after_attempt, wait_exponential

from moves.config import get_settings

# Supported bar timeframes -> (multiplier, Polygon timespan).
TIMEFRAMES: dict[str, tuple[int, str]] = {
    "minute": (1, "minute"),
    "5min": (5, "minute"),
    "15min": (15, "minute"),
    "hour": (1, "hour"),
    "day": (1, "day"),
    "week": (1, "week"),
}

_BAR_COLUMNS = ["ts", "open", "high", "low", "close", "volume", "vwap", "transactions"]

_retry = retry(
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=1, max=20),
    reraise=True,
)


def _require_key(api_key: str | None) -> str:
    key = api_key or get_settings().polygon_api_key
    if not key:
        raise RuntimeError("MOVES_POLYGON_API_KEY is not set (see .env.example)")
    return key


class PolygonClient:
    """Thin, typed wrapper over Polygon's REST endpoints used by this app."""

    def __init__(self, api_key: str | None = None) -> None:
        self.rest = RESTClient(_require_key(api_key))

    @_retry
    def get_aggs_df(
        self,
        ticker: str,
        timeframe: str,
        start: str | date | datetime,
        end: str | date | datetime,
        *,
        adjusted: bool = True,
    ) -> pd.DataFrame:
        """Fetch OHLCV bars as a DataFrame (split-adjusted by default).

        Uses ``list_aggs`` which transparently paginates beyond the 50k cap.
        """
        if timeframe not in TIMEFRAMES:
            raise ValueError(f"unknown timeframe {timeframe!r}; choices: {list(TIMEFRAMES)}")
        multiplier, timespan = TIMEFRAMES[timeframe]
        rows: list[dict[str, Any]] = []
        for agg in self.rest.list_aggs(
            ticker,
            multiplier,
            timespan,
            start,
            end,
            adjusted=adjusted,
            sort="asc",
            limit=50000,
        ):
            rows.append(
                {
                    "ts_ms": agg.timestamp,
                    "open": agg.open,
                    "high": agg.high,
                    "low": agg.low,
                    "close": agg.close,
                    "volume": agg.volume,
                    "vwap": getattr(agg, "vwap", None),
                    "transactions": getattr(agg, "transactions", None),
                }
            )
        df = pd.DataFrame(rows, columns=["ts_ms", *_BAR_COLUMNS[1:]])
        df["ts"] = pd.to_datetime(df["ts_ms"], unit="ms", utc=True).dt.tz_localize(None)
        df["transactions"] = df["transactions"].astype("Int64")
        return df[_BAR_COLUMNS]

    @_retry
    def get_news(
        self,
        ticker: str,
        *,
        since: str | date | datetime | None = None,
        until: str | date | datetime | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Ticker-tagged news in [since, until]. ``list_ticker_news`` paginates, so we
        cap at ``limit`` and pass an upper bound to keep windowed fetches fast."""
        kwargs: dict[str, Any] = {
            "limit": min(limit, 1000),
            "order": "desc",
            "sort": "published_utc",
        }
        if since is not None:
            kwargs["published_utc_gte"] = str(since)
        if until is not None:
            kwargs["published_utc_lte"] = str(until)
        items: list[dict[str, Any]] = []
        for n in self.rest.list_ticker_news(ticker, **kwargs):
            published = getattr(n, "published_utc", None)
            items.append(
                {
                    "id": n.id,
                    "published_utc": pd.to_datetime(published, utc=True).tz_localize(None)
                    if published
                    else None,
                    "title": getattr(n, "title", None),
                    "article_url": getattr(n, "article_url", None),
                    "publisher": getattr(getattr(n, "publisher", None), "name", None),
                    "tickers": list(getattr(n, "tickers", []) or []),
                    "description": getattr(n, "description", None),
                }
            )
            if len(items) >= limit:
                break
        return items

    @_retry
    def get_splits(self, ticker: str) -> pd.DataFrame:
        """Historical stock splits for a ticker (ex_date, split_from, split_to)."""
        rows = [
            {
                "ex_date": pd.to_datetime(s.execution_date).date(),
                "split_from": float(s.split_from),
                "split_to": float(s.split_to),
            }
            for s in self.rest.list_splits(ticker, limit=1000)
            if getattr(s, "execution_date", None)
        ]
        return pd.DataFrame(rows, columns=["ex_date", "split_from", "split_to"])

    @_retry
    def get_dividends(self, ticker: str) -> pd.DataFrame:
        """Historical cash dividends for a ticker (ex_date, cash_amount, frequency)."""
        rows = []
        for d in self.rest.list_dividends(ticker, limit=1000):
            if not getattr(d, "ex_dividend_date", None):
                continue
            freq = getattr(d, "frequency", None)
            rows.append(
                {
                    "ex_date": pd.to_datetime(d.ex_dividend_date).date(),
                    "cash_amount": float(d.cash_amount) if d.cash_amount is not None else None,
                    "frequency": int(freq) if freq is not None else None,
                }
            )
        return pd.DataFrame(rows, columns=["ex_date", "cash_amount", "frequency"])


def stream_aggregates(
    tickers: list[str],
    on_bar: Callable[[Any], None],
    *,
    api_key: str | None = None,
    feed: Feed = Feed.RealTime,
    max_seconds: float | None = None,
) -> None:
    """Stream minute aggregates (``AM.<ticker>``) over Polygon's WebSocket.

    ``on_bar`` is invoked once per inbound message. ``feed`` defaults to the
    real-time SIP feed (the Advanced plan); pass ``Feed.Delayed`` for delayed
    tiers.     ``max_seconds`` closes the socket after a fixed duration (useful for
    smoke tests / bounded runs). The Polygon WebSocket API is async, so this is
    driven on a dedicated asyncio loop and shut down cleanly on timeout.
    """
    key = _require_key(api_key)
    subscriptions = [f"AM.{t.upper()}" for t in tickers]

    async def _run() -> None:
        client = WebSocketClient(
            api_key=key, feed=feed, market=Market.Stocks, subscriptions=subscriptions
        )

        async def _processor(messages: list[Any]) -> None:
            for message in messages:
                on_bar(message)

        connect_task = asyncio.create_task(client.connect(_processor))
        if max_seconds is None:
            await connect_task
            return
        await asyncio.sleep(max_seconds)
        await client.close()
        connect_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await connect_task

    asyncio.run(_run())
