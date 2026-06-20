"""Gather candidate causes for a detected move from all available sources."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import duckdb
import numpy as np

from moves.config import load_watchlist
from moves.corpus import PodcastMention, find_mentions
from moves.providers import FinnhubClient, PolygonClient, finnhub_available
from moves.store import get_bars


@dataclass
class NewsItem:
    title: str
    url: str | None
    publisher: str | None
    published: str | None
    published_ts: datetime | None = None


@dataclass
class CorpAction:
    kind: str
    date: str
    detail: str


@dataclass
class PeerMove:
    symbol: str
    pct: float
    same_direction: bool


@dataclass
class Earnings:
    date: str
    hour: str
    eps_actual: float | None
    eps_estimate: float | None
    rev_actual: float | None
    rev_estimate: float | None


@dataclass
class Candidates:
    news: list[NewsItem] = field(default_factory=list)
    market_news: list[NewsItem] = field(default_factory=list)
    earnings: list[Earnings] = field(default_factory=list)
    corp_actions: list[CorpAction] = field(default_factory=list)
    peers: list[PeerMove] = field(default_factory=list)
    benchmarks: list[PeerMove] = field(default_factory=list)
    podcast: list[PodcastMention] = field(default_factory=list)
    peer_group: str | None = None


BENCHMARKS = ["SPY", "QQQ"]


def _utc_naive(unix_seconds: int) -> datetime:
    return datetime.fromtimestamp(unix_seconds, tz=UTC).replace(tzinfo=None)


def gather_news(
    client: PolygonClient,
    symbol: str,
    start_dt: datetime,
    end_dt: datetime,
    *,
    horizon: str = "medium",
    limit: int = 15,
) -> list[NewsItem]:
    # Short-term moves (incl. minute/hour spikes) have a precise catalyst right at
    # the move; use a tight window so the news timing actually correlates with the
    # spike. Longer moves use a wider window for the narrative.
    if horizon == "short":
        lower, upper = start_dt - timedelta(hours=6), end_dt + timedelta(hours=2)
        keep_time = True
    else:
        lower, upper = start_dt - timedelta(days=3), end_dt + timedelta(days=1)
        keep_time = False
    try:
        raw = client.get_news(
            symbol,
            since=lower.date().isoformat(),
            until=(upper + timedelta(days=1)).date().isoformat(),
            limit=80,
        )
    except Exception:
        return []
    items: list[NewsItem] = []
    for n in raw:
        published = n.get("published_utc")
        if published is None or published < lower or published > upper:
            continue
        stamp = str(published)[:16] if keep_time else str(published)[:10]
        ts = published.to_pydatetime() if hasattr(published, "to_pydatetime") else published
        items.append(
            NewsItem(
                title=n.get("title") or "",
                url=n.get("article_url"),
                publisher=n.get("publisher"),
                published=stamp,
                published_ts=ts,
            )
        )
    return items[:limit]


def gather_earnings(symbol: str, start_date: str, end_date: str) -> list[Earnings]:
    """Earnings releases for the symbol in [start_date, end_date] (needs Finnhub key)."""
    if not finnhub_available():
        return []
    try:
        raw = FinnhubClient().earnings_calendar(symbol, start_date, end_date)
    except Exception:
        return []
    out: list[Earnings] = []
    for e in raw:
        date = str(e.get("date") or "")
        if not date:
            continue
        out.append(
            Earnings(
                date=date,
                hour=str(e.get("hour") or ""),
                eps_actual=e.get("epsActual"),
                eps_estimate=e.get("epsEstimate"),
                rev_actual=e.get("revenueActual"),
                rev_estimate=e.get("revenueEstimate"),
            )
        )
    return out


def gather_corp_actions(
    con: duckdb.DuckDBPyConnection, symbol: str, start_date: str, end_date: str
) -> list[CorpAction]:
    rows = con.execute(
        "SELECT ex_date, split_from, split_to FROM splits "
        "WHERE symbol = ? AND ex_date BETWEEN ? AND ? ORDER BY ex_date",
        [symbol, start_date, end_date],
    ).fetchall()
    return [
        CorpAction(
            kind="split",
            date=str(r[0]),
            detail=f"{int(r[2])}-for-{int(r[1])} stock split (ex-date)",
        )
        for r in rows
    ]


def _window_return(
    con: duckdb.DuckDBPyConnection, symbol: str, timeframe: str, start_time: int, end_time: int
) -> float | None:
    """Return of ``symbol`` over [start_time, end_time], or None if not covered."""
    df = get_bars(con, symbol, timeframe)
    if df.empty:
        return None
    times = df["ts"].astype("datetime64[s]").astype("int64").to_numpy()
    closes = df["close"].to_numpy()
    idx = np.where((times >= start_time) & (times <= end_time))[0]
    if idx.size < 2:
        return None
    return float(closes[idx[-1]] / closes[idx[0]] - 1.0)


def gather_peers(
    con: duckdb.DuckDBPyConnection,
    symbol: str,
    timeframe: str,
    start_time: int,
    end_time: int,
    direction: str,
) -> tuple[list[PeerMove], str | None]:
    group_map = {inst.ticker: inst.group for inst in load_watchlist()}
    group = group_map.get(symbol)
    if not group:
        return [], None
    out: list[PeerMove] = []
    for peer, g in group_map.items():
        if g != group or peer == symbol:
            continue
        pct = _window_return(con, peer, timeframe, start_time, end_time)
        if pct is None:
            continue
        out.append(PeerMove(symbol=peer, pct=pct, same_direction=(pct > 0) == (direction == "up")))
    return out, group


def gather_benchmarks(
    con: duckdb.DuckDBPyConnection,
    symbol: str,
    timeframe: str,
    start_time: int,
    end_time: int,
    direction: str,
) -> list[PeerMove]:
    """Broad-market index returns over the window (to distinguish macro-wide moves)."""
    out: list[PeerMove] = []
    for bench in BENCHMARKS:
        if bench == symbol:
            continue
        pct = _window_return(con, bench, timeframe, start_time, end_time)
        if pct is None:
            continue
        out.append(PeerMove(symbol=bench, pct=pct, same_direction=(pct > 0) == (direction == "up")))
    return out


def gather_candidates(
    con: duckdb.DuckDBPyConnection,
    client: PolygonClient | None,
    *,
    symbol: str,
    timeframe: str,
    start_time: int,
    end_time: int,
    direction: str,
    horizon: str = "long",
) -> Candidates:
    start_dt = _utc_naive(start_time)
    end_dt = _utc_naive(end_time)
    start_date = start_dt.date().isoformat()
    end_date = end_dt.date().isoformat()

    news = (
        gather_news(client, symbol, start_dt, end_dt, horizon=horizon)
        if client is not None
        else []
    )
    # Broad-market news (SPY) so a MACRO catalyst (Fed/CPI/tariff/geo) can be named,
    # not just "risk-off" — the subject ticker's own news won't contain it.
    market_news = (
        gather_news(client, "SPY", start_dt, end_dt, horizon=horizon, limit=8)
        if client is not None and symbol.upper() not in {"SPY", "QQQ"}
        else []
    )
    # Catch an earnings release at or just before the move start.
    earnings = gather_earnings(
        symbol, (start_dt - timedelta(days=5)).date().isoformat(), end_date
    )
    corp = gather_corp_actions(con, symbol, start_date, end_date)
    # Co-movement is judged on DAILY bars (which we keep for the watchlist + indices)
    # so scope detection works even for intraday moves.
    peers, group = gather_peers(con, symbol, "day", start_time, end_time, direction)
    benchmarks = gather_benchmarks(con, symbol, "day", start_time, end_time, direction)

    # Medium/long moves are explained by the evolving narrative, so pull more
    # podcast discussion over a wider window; short news catalysts need only a little.
    pod_limit = {"short": 3, "medium": 8, "long": 12}.get(horizon, 8)
    pad = {"short": 2, "medium": 4, "long": 5}.get(horizon, 4)
    podcast = find_mentions(
        symbol,
        (start_dt - timedelta(days=pad)).date().isoformat(),
        (end_dt + timedelta(days=pad)).date().isoformat(),
        limit=pod_limit,
    )
    return Candidates(
        news=news,
        market_news=market_news,
        earnings=earnings,
        corp_actions=corp,
        peers=peers,
        benchmarks=benchmarks,
        podcast=podcast,
        peer_group=group,
    )
