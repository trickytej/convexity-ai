"""Listen Notes API client for Scout episode search."""

from __future__ import annotations

import logging

import httpx

from ..config import get_settings

log = logging.getLogger(__name__)

_BASE = "https://listen-api.listennotes.com/api/v2"

# date_filter values accepted by Listen Notes search endpoint
DATE_FILTERS = {
    7:   "week_1",
    30:  "month_1",
    90:  "month_3",
    180: "month_6",
    365: "year_1",
}

def _date_filter(days: int) -> str:
    for threshold, label in sorted(DATE_FILTERS.items()):
        if days <= threshold:
            return label
    return "year_1"


def search_episodes(query: str, *, days: int = 30, max_results: int = 10) -> list[dict]:
    """Search Listen Notes for episodes with query in the title.

    Returns raw result dicts from the API.  Returns [] if the key is missing
    or the request fails (so the caller can continue with other queries).
    """
    settings = get_settings()
    if not settings.listennotes_api_key:
        log.warning("LISTENNOTES_API_KEY not set — skipping search for %r", query)
        return []

    try:
        with httpx.Client(timeout=20) as client:
            resp = client.get(
                f"{_BASE}/search",
                params={
                    "q":            query,
                    "type":         "episode",
                    "only_in":      "title",   # title-only = featured appearances, not mere mentions
                    "sort_by_date": 1,
                    "date_filter":  _date_filter(days),
                    "language":     "English",
                    "len_min":      5,
                    "offset":       0,
                },
                headers={"X-ListenAPI-Key": settings.listennotes_api_key},
            )
            resp.raise_for_status()
            return resp.json().get("results", [])[:max_results]
    except Exception as exc:
        log.warning("Listen Notes search failed for %r: %s", query, exc)
        return []
