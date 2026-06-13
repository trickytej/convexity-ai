"""Per-source fetchers/parsers for shows that publish their own transcripts."""

from __future__ import annotations

from ..base import OfficialFetcher
from .colossus import ColossusFetcher
from .dwarkesh import DwarkeshFetcher

_FETCHERS: dict[str, OfficialFetcher] = {
    f.source_key: f for f in (DwarkeshFetcher(), ColossusFetcher())
}


def get_official_fetcher(source_key: str) -> OfficialFetcher | None:
    return _FETCHERS.get(source_key)


__all__ = ["get_official_fetcher", "DwarkeshFetcher", "ColossusFetcher"]

