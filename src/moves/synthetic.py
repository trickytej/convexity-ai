"""Deterministic synthetic price series for demos and tests (no market data key).

Generates a geometric Brownian motion path with optional injected jumps so the
move detector has clear, reproducible swings to find.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd


def gbm_series(
    *,
    days: int = 252,
    start_price: float = 100.0,
    mu: float = 0.08,
    sigma: float = 0.25,
    jumps: dict[int, float] | None = None,
    seed: int = 7,
    start: datetime | None = None,
) -> pd.Series:
    """Return a daily close-price Series (business days) via GBM + optional jumps.

    ``jumps`` maps a day index to a one-off fractional return (e.g. {60: -0.12}
    injects a -12% gap on day 60), useful for exercising move detection.
    """
    rng = np.random.default_rng(seed)
    dt = 1.0 / 252.0
    shocks = rng.normal((mu - 0.5 * sigma**2) * dt, sigma * np.sqrt(dt), size=days)
    if jumps:
        for i, j in jumps.items():
            if 0 <= i < days:
                shocks[i] += np.log1p(j)
    log_path = np.log(start_price) + np.cumsum(shocks)
    prices = np.exp(log_path)

    start = start or (datetime.utcnow() - timedelta(days=int(days * 1.5)))
    idx = pd.bdate_range(start=start.date(), periods=days)
    return pd.Series(prices, index=idx, name="close")
