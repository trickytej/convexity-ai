"""Basket / index construction.

Turns a set of instrument price series into a single comparable index level. The
construction is a proper drift-and-rebalance portfolio: between rebalances the
constituent weights drift with prices (buy-and-hold), and at each rebalance bar
they reset to the target weighting. This is what makes basket % moves correct
enough to feed the same move detector used for single names.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from moves.models import Rebalance, Weighting

_PERIOD_CODE = {
    Rebalance.WEEKLY: "W",
    Rebalance.MONTHLY: "M",
    Rebalance.QUARTERLY: "Q",
}


@dataclass
class BasketResult:
    index: pd.Series
    weighting: Weighting
    rebalance: Rebalance
    initial_weights: dict[str, float] = field(default_factory=dict)


def align_prices(prices_map: dict[str, pd.Series]) -> pd.DataFrame:
    """Align constituent price series onto a common timeline.

    Uses the union of timestamps, forward-fills internal gaps, then trims leading
    rows until every constituent has data (so weights are well defined from the
    first row). Requires each series to have a sorted DatetimeIndex.
    """
    if not prices_map:
        raise ValueError("prices_map is empty")
    df = pd.DataFrame(prices_map).sort_index()
    df = df.ffill().dropna(how="any")
    if df.empty:
        raise ValueError("no overlapping timestamps across constituents after alignment")
    return df


def rebalance_mask(index: pd.DatetimeIndex, freq: Rebalance) -> np.ndarray:
    """Boolean mask (len == n) marking bars where weights reset to target.

    The initial bar is handled separately by the caller; this governs t >= 1.
    """
    n = len(index)
    mask = np.zeros(n, dtype=bool)
    if freq is Rebalance.NONE:
        return mask
    if freq is Rebalance.DAILY:
        mask[1:] = True
        return mask
    periods = index.to_period(_PERIOD_CODE[freq])
    for i in range(1, n):
        if periods[i] != periods[i - 1]:
            mask[i] = True
    return mask


def _target_weights(
    px_row: pd.Series,
    weighting: Weighting,
    custom: dict[str, float] | None,
    shares: dict[str, float] | None,
) -> np.ndarray:
    symbols = list(px_row.index)
    n = len(symbols)
    if weighting is Weighting.EQUAL:
        return np.full(n, 1.0 / n)
    if weighting is Weighting.PRICE:
        prices = px_row.to_numpy(dtype=float)
        return prices / prices.sum()
    if weighting is Weighting.MARKET_CAP:
        if not shares:
            raise ValueError("MARKET_CAP weighting requires shares_outstanding per symbol")
        missing = [s for s in symbols if s not in shares]
        if missing:
            raise ValueError(f"shares_outstanding missing for: {missing}")
        caps = np.array([shares[s] * float(px_row[s]) for s in symbols])
        return caps / caps.sum()
    if weighting is Weighting.CUSTOM:
        if not custom:
            raise ValueError("CUSTOM weighting requires a weights mapping")
        missing = [s for s in symbols if s not in custom]
        if missing:
            raise ValueError(f"custom weights missing for: {missing}")
        w = np.array([float(custom[s]) for s in symbols])
        total = w.sum()
        if total <= 0:
            raise ValueError("custom weights must sum to a positive number")
        return w / total
    raise ValueError(f"unsupported weighting: {weighting}")


def build_basket(
    prices_map: dict[str, pd.Series],
    *,
    weighting: Weighting = Weighting.EQUAL,
    weights: dict[str, float] | None = None,
    shares_outstanding: dict[str, float] | None = None,
    rebalance: Rebalance = Rebalance.MONTHLY,
    normalize_to: float = 100.0,
) -> BasketResult:
    """Construct a basket index level series from constituent prices.

    The index starts at ``normalize_to`` and evolves by the period portfolio
    return; weights drift between rebalances and reset to the target weighting on
    each rebalance bar.
    """
    px = align_prices(prices_map)
    symbols = list(px.columns)
    index = px.index
    n = len(index)

    rets = px.pct_change().to_numpy()  # row 0 is NaN
    mask = rebalance_mask(index, rebalance)

    w = _target_weights(px.iloc[0], weighting, weights, shares_outstanding)
    initial_weights = dict(zip(symbols, w.tolist(), strict=True))

    level = np.empty(n, dtype=float)
    level[0] = normalize_to
    for t in range(1, n):
        r = rets[t]
        port_ret = float(np.dot(w, r))
        level[t] = level[t - 1] * (1.0 + port_ret)
        # drift weights with realized returns, then renormalize
        w = w * (1.0 + r)
        w = w / w.sum()
        if mask[t]:
            w = _target_weights(px.iloc[t], weighting, weights, shares_outstanding)

    return BasketResult(
        index=pd.Series(level, index=index, name="basket"),
        weighting=weighting,
        rebalance=rebalance,
        initial_weights=initial_weights,
    )
