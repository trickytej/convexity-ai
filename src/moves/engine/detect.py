"""Significant-move detection via the Directional Change (DC) framework.

The question "when is a move over?" is answered by a *reversal threshold*: an
up-move keeps extending as long as price makes new highs, and is only declared
over once price retraces `threshold` from that high. The move's end is then the
peak (its true extreme), so a move can run arbitrarily far past the threshold.
Down-moves are symmetric.

This module is pure NumPy and has no I/O or provider dependencies, so it can be
unit-tested deterministically and reused for single instruments or basket index
series alike.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

import numpy as np

from moves.models import Move, MoveDirection


@dataclass(frozen=True)
class Pivot:
    """A confirmed (or provisional) turning point in a price series."""

    index: int
    price: float
    kind: str  # "high" or "low"
    confirmed: bool


def _as_threshold_array(threshold: float | Sequence[float] | np.ndarray, n: int) -> np.ndarray:
    """Normalize a scalar or per-bar threshold into a length-n float array."""
    if np.isscalar(threshold):
        thr = np.full(n, float(threshold), dtype=float)
    else:
        thr = np.asarray(threshold, dtype=float)
        if thr.shape != (n,):
            raise ValueError(f"threshold array must have shape ({n},), got {thr.shape}")
    if np.any(thr <= 0):
        raise ValueError("threshold values must be strictly positive")
    return thr


def find_pivots(
    prices: Sequence[float] | np.ndarray,
    threshold: float | Sequence[float] | np.ndarray = 0.05,
    *,
    include_open: bool = True,
) -> list[Pivot]:
    """Return alternating high/low pivots using the Directional Change algorithm.

    ``threshold`` is a fractional reversal size (0.05 = 5%) and may be a scalar or
    a per-bar array (for volatility-normalized detection). The initial mode is
    "up" but is self-correcting: if price first falls by ``threshold`` the anchor
    is emitted as a high pivot, which is the correct interpretation.
    """
    p = np.asarray(prices, dtype=float)
    n = p.size
    if n == 0:
        return []
    if np.isnan(p).any():
        raise ValueError("prices contain NaN; forward-fill/clean before detection")
    thr = _as_threshold_array(threshold, n)

    pivots: list[Pivot] = []
    mode = "up"  # expecting an up-run -> watching for a downturn
    ext_price = p[0]
    ext_idx = 0

    for i in range(1, n):
        price = p[i]
        if mode == "up":
            if price > ext_price:
                ext_price, ext_idx = price, i
            elif price <= ext_price * (1.0 - thr[i]):
                pivots.append(Pivot(ext_idx, ext_price, "high", confirmed=True))
                mode = "down"
                ext_price, ext_idx = price, i
        else:  # mode == "down"
            if price < ext_price:
                ext_price, ext_idx = price, i
            elif price >= ext_price * (1.0 + thr[i]):
                pivots.append(Pivot(ext_idx, ext_price, "low", confirmed=True))
                mode = "up"
                ext_price, ext_idx = price, i

    if include_open and (not pivots or pivots[-1].index != ext_idx):
        kind = "high" if mode == "up" else "low"
        pivots.append(Pivot(ext_idx, ext_price, kind, confirmed=False))

    # Represent the initial leg: prepend the anchor as the opposite-kind pivot so
    # the move from the series start to the first detected extreme is captured.
    if pivots and pivots[0].index != 0:
        opposite = "low" if pivots[0].kind == "high" else "high"
        pivots.insert(0, Pivot(0, float(p[0]), opposite, confirmed=True))

    return pivots


def _max_adverse(p: np.ndarray, start: int, end: int, direction: MoveDirection) -> float:
    """Worst intra-move counter-excursion, as a positive fraction.

    Up-move -> deepest peak-to-trough drawdown within the swing.
    Down-move -> largest trough-to-peak rally within the swing.
    """
    seg = p[start : end + 1]
    if seg.size < 2:
        return 0.0
    if direction is MoveDirection.UP:
        running = np.maximum.accumulate(seg)
        return float(np.max((running - seg) / running))
    running = np.minimum.accumulate(seg)
    return float(np.max((seg - running) / running))


def detect_moves(
    prices: Sequence[float] | np.ndarray,
    timestamps: Sequence[datetime] | None = None,
    *,
    threshold: float | Sequence[float] | np.ndarray = 0.05,
    min_move: float | None = None,
    symbol: str | None = None,
    include_open: bool = True,
) -> list[Move]:
    """Detect significant moves in a price series.

    Parameters
    ----------
    prices:
        Ordered close prices (oldest first).
    timestamps:
        Optional aligned timestamps; attached to each move for charting.
    threshold:
        Reversal threshold that defines when a move is over (scalar or per-bar).
    min_move:
        Optional minimum |return| to keep a move. Defaults to ``None``; because DC
        swings are already >= ``threshold`` by construction, this only matters when
        you want a higher highlight bar than the reversal sensitivity (e.g. detect
        turns at 2% but only surface >= 5% moves), or with per-bar thresholds.
    symbol:
        Optional instrument symbol stamped on each move.
    include_open:
        Include the final, still-open swing (marked ``confirmed=False``).
    """
    p = np.asarray(prices, dtype=float)
    if timestamps is not None and len(timestamps) != p.size:
        raise ValueError("timestamps must align 1:1 with prices")

    pivots = find_pivots(p, threshold, include_open=include_open)
    if len(pivots) < 2:
        return []

    moves: list[Move] = []
    for a, b in zip(pivots[:-1], pivots[1:], strict=True):
        direction = MoveDirection.UP if b.price >= a.price else MoveDirection.DOWN
        pct = b.price / a.price - 1.0
        if min_move is not None and abs(pct) < min_move:
            continue
        moves.append(
            Move(
                symbol=symbol,
                direction=direction,
                start_index=a.index,
                end_index=b.index,
                start_ts=timestamps[a.index] if timestamps is not None else None,
                end_ts=timestamps[b.index] if timestamps is not None else None,
                start_price=float(a.price),
                end_price=float(b.price),
                pct_change=float(pct),
                n_bars=b.index - a.index,
                confirmed=b.confirmed,
                max_adverse_pct=_max_adverse(p, a.index, b.index, direction),
            )
        )
    return moves


def detect_spikes(
    prices: Sequence[float] | np.ndarray,
    timestamps: Sequence[datetime] | None = None,
    *,
    threshold: float = 0.05,
    max_bars: int = 26,
    symbol: str | None = None,
) -> list[Move]:
    """Detect discrete *fast* moves ("spikes"), not trend swings.

    A spike is a window where price moves at least ``threshold`` within at most
    ``max_bars`` bars. Unlike :func:`detect_moves` (Directional Change), this does
    NOT partition the whole series — normal/slow drift is left unflagged, so large
    fast moves stand out against the background. Greedy: from each position, take
    the largest move within the lookahead window; if it clears the threshold,
    record it and continue after its extreme.
    """
    p = np.asarray(prices, dtype=float)
    n = p.size
    if n < 2:
        return []
    if np.isnan(p).any():
        raise ValueError("prices contain NaN; forward-fill/clean before detection")
    if max_bars < 1:
        raise ValueError("max_bars must be >= 1")

    moves: list[Move] = []
    i = 0
    while i < n - 1:
        hi = min(n - 1, i + max_bars)
        seg = p[i : hi + 1]
        rets = seg / p[i] - 1.0
        k = int(np.argmax(np.abs(rets)))
        if k > 0 and abs(rets[k]) >= threshold:
            j = i + k
            direction = MoveDirection.UP if rets[k] > 0 else MoveDirection.DOWN
            moves.append(
                Move(
                    symbol=symbol,
                    direction=direction,
                    start_index=i,
                    end_index=j,
                    start_ts=timestamps[i] if timestamps is not None else None,
                    end_ts=timestamps[j] if timestamps is not None else None,
                    start_price=float(p[i]),
                    end_price=float(p[j]),
                    pct_change=float(rets[k]),
                    n_bars=j - i,
                    confirmed=True,
                    max_adverse_pct=_max_adverse(p, i, j, direction),
                )
            )
            i = j  # resume after the spike's extreme
        else:
            i += 1
    return moves


def volatility_threshold(
    prices: Sequence[float] | np.ndarray,
    *,
    window: int = 20,
    k: float = 3.0,
    floor: float = 0.02,
) -> np.ndarray:
    """Per-bar reversal threshold scaled to recent volatility.

    Returns ``max(floor, k * rolling_std(log returns))`` per bar, so the same
    detector flags genuine moves on both sleepy and high-beta names instead of a
    one-size-fits-all percentage. Pass the result as ``threshold=`` to
    :func:`detect_moves`.
    """
    p = np.asarray(prices, dtype=float)
    n = p.size
    out = np.full(n, floor, dtype=float)
    if n < 3:
        return out
    logret = np.diff(np.log(p), prepend=np.log(p[0]))
    for i in range(n):
        lo = max(1, i - window + 1)
        sigma = float(np.std(logret[lo : i + 1])) if i >= 1 else 0.0
        out[i] = max(floor, k * sigma)
    return out
