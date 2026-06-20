"""Core domain models shared across the engine, storage, and API layers."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class MoveDirection(StrEnum):
    UP = "up"
    DOWN = "down"


class Weighting(StrEnum):
    EQUAL = "equal"
    MARKET_CAP = "market_cap"
    PRICE = "price"
    CUSTOM = "custom"


class ReturnType(StrEnum):
    PRICE = "price"
    TOTAL = "total"


class Rebalance(StrEnum):
    NONE = "none"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"


class Bar(BaseModel):
    """A single OHLCV bar (daily or intraday)."""

    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None


class Move(BaseModel):
    """A detected significant price move (a confirmed swing between two pivots).

    A move runs from a pivot extreme to the next pivot extreme, so it can exceed
    the detection threshold arbitrarily (the "even if it goes beyond 5%" case).
    `confirmed=False` marks the final, still-open swing whose reversal has not yet
    been observed.
    """

    symbol: str | None = None
    direction: MoveDirection
    start_index: int
    end_index: int
    start_ts: datetime | None = None
    end_ts: datetime | None = None
    start_price: float
    end_price: float
    pct_change: float = Field(description="Signed fractional return, end/start - 1.")
    n_bars: int
    confirmed: bool = True
    max_adverse_pct: float = Field(
        default=0.0,
        description="Worst intra-move counter-move against the swing direction, as a fraction.",
    )

    @property
    def magnitude(self) -> float:
        """Absolute size of the move as a fraction."""
        return abs(self.pct_change)
