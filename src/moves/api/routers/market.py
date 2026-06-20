"""Market endpoints: instruments, per-symbol series + moves, and baskets."""

from __future__ import annotations

import time
from datetime import date, datetime, timedelta

import duckdb
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query

from moves.config import load_watchlist
from moves.engine import build_basket, detect_moves, detect_spikes, volatility_threshold
from moves.ingest import backfill
from moves.insights import attribute_move, investigate_move
from moves.insights.llm import LLMError
from moves.models import Move
from moves.providers import PolygonClient
from moves.store import bar_counts, get_bars
from moves.store.cache import cache_connect, get_cached, insight_key, put_cached
from moves.store.db import connect as store_connect

from ..deps import get_db
from ..schemas import (
    BarOut,
    BasketOut,
    BasketPoint,
    BasketRequest,
    IngestRequest,
    IngestResult,
    InsightOut,
    InsightRequest,
    InstrumentOut,
    MoveOut,
    ScanOut,
    SeriesOut,
)

router = APIRouter(tags=["market"])


def _bar_times(df: pd.DataFrame) -> list[int]:
    """UNIX seconds (UTC) for each row, derived from the stored naive-UTC ts.

    Cast to second precision first so the result is correct regardless of the
    source datetime64 unit (DuckDB hands back microseconds).
    """
    return df["ts"].astype("datetime64[s]").astype("int64").tolist()


def _parse_date(value: str | None) -> datetime | None:
    """Parse an ISO date/datetime window bound, or None."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"invalid date: {value!r}") from exc


# Minutes per bar, for converting a spike's max DURATION into a bar count. A spike is
# a fast move (minutes to a couple of hours), not a multi-day swing.
_TF_MINUTES = {"minute": 1, "5min": 5, "15min": 15, "hour": 60, "day": 390, "week": 1950}


def _spike_max_bars(timeframe: str, spike_minutes: int) -> int:
    return max(1, round(spike_minutes / _TF_MINUTES.get(timeframe, 15)))


def _detect(
    prices, *, mode: str, timeframe: str, threshold: float, vol_normalize: bool,
    min_move: float | None, symbol: str, spike_minutes: int = 60,
) -> list[Move]:
    """Dispatch to spike (discrete fast moves) or swing (Directional Change) detection."""
    if mode == "spikes":
        return detect_spikes(
            prices,
            threshold=threshold,
            max_bars=_spike_max_bars(timeframe, spike_minutes),
            symbol=symbol,
        )
    thr = volatility_threshold(prices) if vol_normalize else threshold
    return detect_moves(prices, threshold=thr, min_move=min_move, symbol=symbol)


def _moves_out(moves: list[Move], times: list[int]) -> list[MoveOut]:
    return [
        MoveOut(
            direction=m.direction.value,
            start_time=times[m.start_index],
            end_time=times[m.end_index],
            start_price=m.start_price,
            end_price=m.end_price,
            pct_change=m.pct_change,
            n_bars=m.n_bars,
            confirmed=m.confirmed,
            max_adverse_pct=m.max_adverse_pct,
        )
        for m in moves
    ]


@router.get("/instruments", response_model=list[InstrumentOut])
def instruments(db: duckdb.DuckDBPyConnection = Depends(get_db)) -> list[InstrumentOut]:
    counts = bar_counts(db)
    tf_map: dict[str, list[str]] = {}
    for _, row in counts.iterrows():
        tf_map.setdefault(row["symbol"], []).append(row["timeframe"])

    out: list[InstrumentOut] = []
    seen: set[str] = set()
    for inst in load_watchlist():
        seen.add(inst.ticker)
        tfs = tf_map.get(inst.ticker, [])
        out.append(
            InstrumentOut(
                ticker=inst.ticker,
                name=inst.name,
                group=inst.group,
                has_data=bool(tfs),
                timeframes=sorted(tfs),
            )
        )
    for sym, tfs in tf_map.items():
        if sym not in seen:
            out.append(InstrumentOut(ticker=sym, has_data=True, timeframes=sorted(tfs)))
    return out


# Sensible default history per timeframe; intraday is bounded so we never try to
# pull years of minute bars on demand.
_DEFAULT_LOOKBACK_DAYS = {
    "minute": 45,
    "5min": 120,
    "15min": 240,
    "hour": 730,
    "day": 1825,
    "week": 3650,
}
_LOOKBACK_CAP_DAYS = {"minute": 60, "5min": 180, "15min": 365, "hour": 1095}


def _ingest_lookback_days(timeframe: str, requested: int | None) -> int:
    base = requested if requested else _DEFAULT_LOOKBACK_DAYS.get(timeframe, 365)
    cap = _LOOKBACK_CAP_DAYS.get(timeframe)
    return min(base, cap) if cap else base


@router.post("/ingest", response_model=IngestResult)
def ingest_symbol(req: IngestRequest) -> IngestResult:
    """On-demand backfill of any ticker from Polygon into the store.

    Uses its own read-write DuckDB connection (with a short retry, since the API
    otherwise opens read-only connections and DuckDB allows a single writer).
    Intraday timeframes use a bounded lookback to keep ingests fast.
    """
    symbol = req.symbol.upper().strip()
    if not symbol:
        raise HTTPException(status_code=400, detail="symbol required")
    lookback = _ingest_lookback_days(req.timeframe, req.days)
    start = (date.today() - timedelta(days=lookback)).isoformat()
    end = date.today().isoformat()

    con = None
    for _ in range(6):
        try:
            con = store_connect(read_only=False)
            break
        except duckdb.Error:
            time.sleep(0.3)
    if con is None:
        raise HTTPException(status_code=503, detail="store busy; try again")

    try:
        try:
            client = PolygonClient()
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        written = backfill(con, client, [symbol], req.timeframe, start, end)
    finally:
        con.close()

    bars = written.get(symbol, 0)
    if bars == 0:
        raise HTTPException(
            status_code=404, detail=f"no {req.timeframe} data for {symbol} from Polygon"
        )
    return IngestResult(symbol=symbol, timeframe=req.timeframe, bars=bars)


@router.get("/series", response_model=SeriesOut)
def series(
    symbol: str,
    timeframe: str = "day",
    threshold: float = Query(0.05, gt=0, le=1),
    vol_normalize: bool = False,
    min_move: float | None = Query(None, gt=0, le=1),
    mode: str = "swings",
    spike_minutes: int = Query(60, ge=5, le=480),
    start: str | None = None,
    end: str | None = None,
    db: duckdb.DuckDBPyConnection = Depends(get_db),
) -> SeriesOut:
    df = get_bars(db, symbol.upper(), timeframe, _parse_date(start), _parse_date(end))
    if df.empty:
        raise HTTPException(status_code=404, detail=f"no {timeframe} bars for {symbol.upper()}")

    times = _bar_times(df)
    bars = [
        BarOut(
            time=t,
            open=row.open,
            high=row.high,
            low=row.low,
            close=row.close,
            volume=None if pd.isna(row.volume) else float(row.volume),
        )
        for t, row in zip(times, df.itertuples(index=False), strict=True)
    ]

    moves = _detect(
        df["close"].to_numpy(),
        mode=mode,
        timeframe=timeframe,
        threshold=threshold,
        vol_normalize=vol_normalize,
        min_move=min_move,
        symbol=symbol.upper(),
        spike_minutes=spike_minutes,
    )
    return SeriesOut(
        symbol=symbol.upper(), timeframe=timeframe, bars=bars, moves=_moves_out(moves, times)
    )


@router.get("/scan", response_model=ScanOut)
def scan(
    symbol: str,
    timeframe: str = "hour",
    threshold: float = Query(0.03, gt=0, le=1),
    spike_minutes: int = Query(60, ge=5, le=480),
    start: str | None = None,
    end: str | None = None,
    db: duckdb.DuckDBPyConnection = Depends(get_db),
) -> ScanOut:
    """List every fast move >= threshold completing within spike_minutes over the
    whole window. Returns moves only (no bars), so it has no chart-render limit and
    can scan the full available history for a timeframe."""
    df = get_bars(db, symbol.upper(), timeframe, _parse_date(start), _parse_date(end))
    if df.empty:
        raise HTTPException(status_code=404, detail=f"no {timeframe} bars for {symbol.upper()}")
    times = _bar_times(df)
    spikes = detect_spikes(
        df["close"].to_numpy(),
        threshold=threshold,
        max_bars=_spike_max_bars(timeframe, spike_minutes),
        symbol=symbol.upper(),
    )
    out = _moves_out(spikes, times)
    out.sort(key=lambda m: abs(m.pct_change), reverse=True)
    return ScanOut(
        symbol=symbol.upper(),
        timeframe=timeframe,
        threshold=threshold,
        spike_minutes=spike_minutes,
        bars_scanned=len(times),
        first_time=times[0] if times else None,
        last_time=times[-1] if times else None,
        moves=out,
    )


@router.post("/basket", response_model=BasketOut)
def basket(
    req: BasketRequest, db: duckdb.DuckDBPyConnection = Depends(get_db)
) -> BasketOut:
    symbols = [s.upper() for s in req.symbols]
    if not symbols:
        raise HTTPException(status_code=400, detail="provide at least one symbol")

    prices_map: dict[str, pd.Series] = {}
    used: list[str] = []
    start_dt, end_dt = _parse_date(req.start), _parse_date(req.end)
    for sym in symbols:
        df = get_bars(db, sym, req.timeframe, start_dt, end_dt)
        if df.empty:
            continue
        prices_map[sym] = pd.Series(df["close"].to_numpy(), index=pd.DatetimeIndex(df["ts"]))
        used.append(sym)

    if not prices_map:
        raise HTTPException(status_code=404, detail="no bars for any requested symbol")

    try:
        result = build_basket(
            prices_map,
            weighting=req.weighting,
            weights=req.weights,
            rebalance=req.rebalance,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    level = result.index
    times = level.index.astype("datetime64[s]").astype("int64").tolist()
    values = level.to_numpy()
    points = [BasketPoint(time=t, value=float(v)) for t, v in zip(times, values, strict=True)]

    moves = _detect(
        values,
        mode=req.mode,
        timeframe=req.timeframe,
        threshold=req.threshold,
        vol_normalize=req.vol_normalize,
        min_move=None,
        symbol="BASKET",
        spike_minutes=req.spike_minutes,
    )
    return BasketOut(
        symbols=symbols,
        used_symbols=used,
        timeframe=req.timeframe,
        weighting=req.weighting.value,
        rebalance=req.rebalance.value,
        initial_weights=result.initial_weights,
        points=points,
        moves=_moves_out(moves, times),
    )


@router.post("/insight", response_model=InsightOut)
def insight(
    req: InsightRequest, db: duckdb.DuckDBPyConnection = Depends(get_db)
) -> InsightOut:
    """Grounded AI attribution for a single move (cached; pass regenerate to refresh)."""
    try:
        symbol = req.symbol.upper()
        key = insight_key(symbol, req.timeframe, req.start_time, req.end_time)
        cache = cache_connect()
        try:
            if not req.regenerate:
                cached = get_cached(cache, key)
                if cached:
                    cached["cached"] = True
                    return InsightOut(**cached)
            payload = attribute_move(
                db,
                symbol=symbol,
                timeframe=req.timeframe,
                start_time=req.start_time,
                end_time=req.end_time,
                direction=req.direction,
                pct_change=req.pct_change,
            )
            put_cached(cache, key, payload)
            payload["cached"] = False
            return InsightOut(**payload)
        finally:
            cache.close()
    except HTTPException:
        raise
    except LLMError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        import logging
        import traceback

        logging.getLogger("moves.api").warning("insight failed: %s\n%s", exc, traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}") from exc


@router.post("/investigate", response_model=InsightOut)
def investigate(req: InsightRequest) -> InsightOut:
    """Agentic Opus deep-dive (tool-using). Slower; cached separately from /insight."""
    symbol = req.symbol.upper()
    key = "deep:" + insight_key(symbol, req.timeframe, req.start_time, req.end_time)
    cache = cache_connect()
    try:
        if not req.regenerate:
            cached = get_cached(cache, key)
            if cached:
                cached["cached"] = True
                return InsightOut(**cached)
        # Read-write connection: the agent may ingest peers/suppliers on demand.
        con = None
        for _ in range(6):
            try:
                con = store_connect(read_only=False)
                break
            except duckdb.Error:
                time.sleep(0.3)
        if con is None:
            raise HTTPException(status_code=503, detail="store busy; try again")
        try:
            payload = investigate_move(
                con,
                symbol=symbol,
                timeframe=req.timeframe,
                start_time=req.start_time,
                end_time=req.end_time,
                direction=req.direction,
                pct_change=req.pct_change,
            )
        except LLMError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        finally:
            con.close()
        put_cached(cache, key, payload)
        payload["cached"] = False
        return InsightOut(**payload)
    finally:
        cache.close()
