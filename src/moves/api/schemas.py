"""Request/response models for the web API.

Times are UNIX seconds (UTC) so they drop straight into TradingView Lightweight
Charts on the frontend.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from moves.models import Rebalance, Weighting


class InstrumentOut(BaseModel):
    ticker: str
    name: str = ""
    group: str = ""
    has_data: bool = False
    timeframes: list[str] = Field(default_factory=list)


class BarOut(BaseModel):
    time: int
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None


class MoveOut(BaseModel):
    direction: str
    start_time: int
    end_time: int
    start_price: float
    end_price: float
    pct_change: float
    n_bars: int
    confirmed: bool
    max_adverse_pct: float


class SeriesOut(BaseModel):
    symbol: str
    timeframe: str
    bars: list[BarOut]
    moves: list[MoveOut]


class BasketPoint(BaseModel):
    time: int
    value: float


class BasketRequest(BaseModel):
    symbols: list[str]
    timeframe: str = "day"
    weighting: Weighting = Weighting.EQUAL
    rebalance: Rebalance = Rebalance.MONTHLY
    weights: dict[str, float] | None = None
    threshold: float = 0.05
    vol_normalize: bool = False
    mode: str = "swings"
    spike_minutes: int = 60
    start: str | None = None
    end: str | None = None


class BasketOut(BaseModel):
    symbols: list[str]
    used_symbols: list[str]
    timeframe: str
    weighting: str
    rebalance: str
    initial_weights: dict[str, float]
    points: list[BasketPoint]
    moves: list[MoveOut]


class IngestRequest(BaseModel):
    symbol: str
    timeframe: str = "day"
    days: int | None = None  # lookback; defaults per-timeframe (intraday is capped)


class IngestResult(BaseModel):
    symbol: str
    timeframe: str
    bars: int


class ScanOut(BaseModel):
    symbol: str
    timeframe: str
    threshold: float
    spike_minutes: int
    bars_scanned: int
    first_time: int | None = None
    last_time: int | None = None
    moves: list[MoveOut]


class InsightRequest(BaseModel):
    symbol: str
    timeframe: str = "day"
    start_time: int
    end_time: int
    direction: str
    pct_change: float
    regenerate: bool = False


class EvidenceItem(BaseModel):
    id: str
    kind: str
    point: str
    label: str
    url: str | None = None
    published: str | None = None
    timing: str | None = None


class HeadlineOut(BaseModel):
    published: str | None = None
    publisher: str | None = None
    title: str | None = None
    url: str | None = None
    timing: str | None = None


class InsightOut(BaseModel):
    symbol: str
    timeframe: str
    start_time: int
    end_time: int
    direction: str
    pct_change: float
    horizon: str = ""
    scope: str = ""
    summary: str
    confidence: str
    no_clear_catalyst: bool
    evidence: list[EvidenceItem]
    sources_considered: dict[str, int]
    headlines: list[HeadlineOut] = Field(default_factory=list)
    model: str
    generated_at: str
    cached: bool = False
    deep: bool = False
    trace: list[str] = Field(default_factory=list)
