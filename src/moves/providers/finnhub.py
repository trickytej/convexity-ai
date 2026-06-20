"""Finnhub client — earnings calendar (free tier) for deterministic event tagging.

Knowing a move landed on/after an earnings release is a far stronger "short-term
catalyst" signal than scraping headlines, so this feeds the attribution layer.
"""

from __future__ import annotations

from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from moves.config import get_settings

_BASE = "https://finnhub.io/api/v1"

_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
)


def finnhub_available() -> bool:
    return bool(get_settings().finnhub_api_key)


class FinnhubClient:
    """Minimal Finnhub REST wrapper (earnings calendar)."""

    def __init__(self, api_key: str | None = None) -> None:
        key = api_key or get_settings().finnhub_api_key
        if not key:
            raise RuntimeError("MOVES_FINNHUB_API_KEY is not set (free key at finnhub.io)")
        self._key = key

    @_retry
    def earnings_calendar(self, symbol: str, start: str, end: str) -> list[dict[str, Any]]:
        """Reported/expected earnings for a symbol in [start, end] (YYYY-MM-DD).

        Each item: date, hour (bmo/amc/dmh), epsActual, epsEstimate,
        revenueActual, revenueEstimate, quarter, year.
        """
        with httpx.Client(timeout=20) as http:
            resp = http.get(
                f"{_BASE}/calendar/earnings",
                params={"from": start, "to": end, "symbol": symbol.upper(), "token": self._key},
            )
            resp.raise_for_status()
            data = resp.json()
        return data.get("earningsCalendar") or []
