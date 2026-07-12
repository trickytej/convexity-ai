"""Podscan.fm API client for Scout episode search."""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timedelta, timezone

import httpx

from ..config import get_settings

log = logging.getLogger(__name__)

_BASE = "https://podscan.fm/api/v1"
_MIN_DURATION_SECONDS = 300   # ignore sub-5-min clips / news briefs

# Minimum spacing between consecutive Podscan requests (one per person searched).
_REQUEST_DELAY_SECONDS = 1.0
_RETRY_AFTER_SECONDS = 60      # fallback wait after a 429 with no Retry-After header
_RETRY_MAX_WAIT_SECONDS = 120  # a Retry-After beyond this means the daily quota is gone, not a burst limit


class PodscanAuthError(Exception):
    """Raised when PODSCAN_API_KEY is missing or Podscan rejects it (401/403).

    Deliberately not swallowed inside search_episodes: the caller (pipeline.run_cycle)
    catches this once and aborts the whole cycle instead of silently returning zero
    results for every one of the 100+ tracked people.
    """


class PodscanRateLimitError(Exception):
    """Raised when the Podscan request quota is exhausted (HTTP 429 that won't
    clear within _RETRY_MAX_WAIT_SECONDS).

    Like PodscanAuthError, this aborts the whole cycle: the quota is per-key,
    so every remaining person search would also 429. Carries ``reset_at`` so
    callers can tell the user exactly when scanning becomes possible again.
    """

    def __init__(self, message: str, reset_at: datetime | None = None) -> None:
        super().__init__(message)
        self.reset_at = reset_at


def _quota_error(resp: httpx.Response) -> PodscanRateLimitError:
    reset_at = None
    raw = resp.headers.get("x-ratelimit-reset")
    if raw:
        try:
            reset_at = datetime.fromtimestamp(int(raw), tz=timezone.utc)
        except (ValueError, OverflowError, OSError):
            pass
    when = f" — quota resets at {reset_at.strftime('%Y-%m-%d %H:%M UTC')}" if reset_at else ""
    return PodscanRateLimitError(f"Podscan request quota exhausted (HTTP 429){when}", reset_at)


_last_request_at = 0.0


def _throttle() -> None:
    """Keep consecutive Podscan requests ≥ _REQUEST_DELAY_SECONDS apart.

    Module-level so the spacing applies across person searches, plus the rare
    429 retry within one search.
    """
    global _last_request_at
    wait = _last_request_at + _REQUEST_DELAY_SECONDS - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    _last_request_at = time.monotonic()


# ── Guest-appearance filter ───────────────────────────────────────────────────
#
# Podscan's full-text search returns any episode that mentions a person, not
# just those where the person is actually a guest speaker. These patterns
# separate real appearances from editorial coverage.

def _is_guest_appearance(person_name: str, title: str, description: str) -> bool:
    """Return True only when the episode is likely an actual guest appearance."""
    last = re.escape(person_name.split()[-1].lower())
    title_l = title.lower()
    desc_l = description.lower()[:2000]

    # Reject: editorial / analysis titles where person is discussed not speaking
    noise_title = [
        rf"^(why|what|how|is|are|was|can|will|did)\s+{last}",
        rf"^(the|a|an)\s+\w+\s+of\s+{last}",
        rf"\b{last}'s\b",
        rf"\b(story|rise|fall|legacy|impact|future|vision|guide|profile)\s+of\s+{last}",
        rf"\b(about|analyzing|dissecting|breaking\s+down)\s+{last}",
        rf"\beverything\s+{last}\s+(said|told)",
        rf"\bwhat\s+{last}\s+(said|told|revealed|thinks)",
    ]
    for pat in noise_title:
        if re.search(pat, title_l):
            return False

    # Accept: title patterns that are almost always a guest appearance
    guest_title = [
        rf"\b{last}\s*:",
        rf":\s*[^|]{{0,50}}\b{last}\b",
        rf"\bwith\s+{last}\b",
        rf"#\s*\d+[^|]{{0,60}}\b{last}\b",
        rf"\b{last}\b[^|]{{0,60}}#\s*\d+",
        rf"\b(ep|episode)\s*\d+[^|]{{0,60}}\b{last}\b",
        rf"\b{last}\b[^|]{{0,60}}\b(ep|episode)\s*\d+",
        rf"\binterview\b[^|]{{0,60}}\b{last}\b",
        rf"\b{last}\b[^|]{{0,60}}\binterview\b",
        rf"\b{last}\b[^|]{{0,60}}\bon\b\s+\w",
        rf"\b{last},\s",
        rf"\b{last}\b[^|]{{0,10}}\|",
        rf"\|\s*[^|]{{0,30}}\b{last}\b",
        rf"\b{last}\b[^|]{{0,60}}\b(joins?|joined)\b",
        rf"\b(guest|keynote|fireside)\b[^|]{{0,60}}\b{last}\b",
    ]
    for pat in guest_title:
        if re.search(pat, title_l):
            return True

    # Accept: description signals that the person is a guest/speaker
    guest_desc = [
        rf"\b{last}\b[^.{{0,120}}]\b(joins?|joining|joined)\b",
        rf"\b(joins?|joining|joined)\b[^.{{0,120}}]\b{last}\b",
        rf"\b(my|our|today.s|this week.s|special)\s+guest[^.{{0,120}}]\b{last}\b",
        rf"\b{last}\b[^.{{0,120}}]\b(discusses?|shares?|talks?\s+about|explains?)\b",
        rf"\b(welcome|welcoming)\b[^.{{0,120}}]\b{last}\b",
        rf"\binterview(?:ed|ing)?\b[^.{{0,120}}]\b{last}\b",
        rf"\b{last}\b[^.{{0,120}}]\binterview",
        rf"\bsits?\s+down\b[^.{{0,120}}]\b{last}\b",
        rf"\b{last}\b[^.{{0,120}}]\bsits?\s+down",
        rf"\bin\s+this\s+(episode|conversation|interview)[^.{{0,120}}]\b{last}\b",
        rf"\bspeak(?:s|ing)?\s+with\b[^.{{0,120}}]\b{last}\b",
        rf"\bin\s+conversation\s+with\b[^.{{0,120}}]\b{last}\b",
    ]
    for pat in guest_desc:
        if re.search(pat, desc_l):
            return True

    return False


def _mentions(term: str, text: str) -> bool:
    """Word-boundary, case-insensitive match; whitespace in *term* is flexible."""
    pattern = r"\b" + r"\s+".join(re.escape(w) for w in term.split()) + r"\b"
    return re.search(pattern, text, re.IGNORECASE) is not None


def _cutoff_dt(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


def search_episodes(
    query: str, *, days: int = 30, max_results: int = 10, company: str | None = None
) -> list[dict]:
    """Search Podscan for recent episodes where *query* (a person's name) is a guest.

    Exactly ONE Podscan request per call — the daily quota is 100 requests and
    a full watchlist scan runs one search per tracked person, so pagination is
    not affordable. Everything that used to force extra pages is pushed
    server-side instead:

      - the person's name goes in quotes (a bare multi-word query is OR-matched
        word by word, so "Tom Brown" would match every episode saying just
        "Tom" or just "Brown" — that noise is what made paging necessary);
      - ``search_fields=title,description``: _is_guest_appearance can only
        accept an episode whose title/description names the person, so
        transcript hits (news shows quoting them — the bulk of matches for a
        famous name) could never survive the filter and would just crowd the
        page;
      - ``since`` scopes results to the date window;
      - ``min_duration`` drops sub-5-min clips;
      - ``per_page`` is 50, the API maximum.

    *company* is deliberately NOT in the server query: descriptions don't
    always name the guest's company, but transcripts nearly always do, so the
    word-boundary company check below (which sees the transcript) keeps recall
    while still weeding out same-name strangers. The guest-appearance
    heuristic also still runs client-side — Podscan can't tell a guest from a
    mention.
    """
    settings = get_settings()
    if not settings.podscan_api_key:
        raise PodscanAuthError("PODSCAN_API_KEY is not set")

    cutoff = _cutoff_dt(days)
    params = {
        "query":         f'"{query}"',
        "search_fields": "title,description",
        "since":         cutoff.strftime("%Y-%m-%d %H:%M:%S"),
        "order_by":      "posted_at",
        "order_dir":     "desc",
        "per_page":      50,
        "min_duration":  _MIN_DURATION_SECONDS,
    }
    headers = {"Authorization": f"Bearer {settings.podscan_api_key}"}
    collected: list[dict] = []

    try:
        with httpx.Client(timeout=60) as client:
            _throttle()
            resp = client.get(f"{_BASE}/episodes/search", params=params, headers=headers)

            if resp.status_code == 429:
                try:
                    retry_after = int(resp.headers.get("retry-after") or 0)
                except ValueError:
                    retry_after = 0
                if retry_after > _RETRY_MAX_WAIT_SECONDS:
                    raise _quota_error(resp)
                wait = retry_after or _RETRY_AFTER_SECONDS
                log.warning("Podscan rate limit hit for %r — waiting %ss", query, wait)
                time.sleep(wait)
                _throttle()
                resp = client.get(f"{_BASE}/episodes/search", params=params, headers=headers)
                if resp.status_code == 429:
                    raise _quota_error(resp)

            if resp.status_code in (401, 403):
                raise PodscanAuthError(
                    f"Podscan rejected the API key (HTTP {resp.status_code}) — check PODSCAN_API_KEY"
                )

            resp.raise_for_status()
            episodes = resp.json().get("episodes", [])

            for ep in episodes:
                posted_raw = ep.get("posted_at") or ""
                if posted_raw:
                    try:
                        posted = datetime.fromisoformat(posted_raw)
                        if posted.tzinfo is None:
                            posted = posted.replace(tzinfo=timezone.utc)
                        if posted < cutoff:
                            continue
                    except ValueError:
                        pass

                duration = ep.get("episode_duration") or 0
                if duration < _MIN_DURATION_SECONDS:
                    continue

                title = (ep.get("episode_title") or "").strip()
                desc = ep.get("episode_description") or ""
                if not _is_guest_appearance(query, title, desc):
                    continue

                haystack = "\n".join(
                    (title, desc, ep.get("episode_transcript") or "")
                )
                if not _mentions(query, haystack):
                    continue
                if company and not _mentions(company, haystack):
                    continue

                collected.append(_normalise(ep))
                if len(collected) >= max_results:
                    break

    except (PodscanAuthError, PodscanRateLimitError):
        raise
    except Exception as exc:
        log.warning("Podscan search failed for %r: %s", query, exc)

    return collected


def _normalise(ep: dict) -> dict:
    """Flatten a Podscan episode dict into the shape pipeline.run_cycle expects."""
    podcast = ep.get("podcast") or {}
    return {
        "podscan_id":   ep.get("episode_id") or "",
        "title":        (ep.get("episode_title") or "").strip(),
        "podcast_name": (podcast.get("podcast_name") or "").strip(),
        "episode_url":  ep.get("episode_url") or ep.get("episode_permalink") or "",
        "audio_url":    ep.get("episode_audio_url") or "",
        "thumbnail":    ep.get("episode_image_url") or "",
        "description":  (ep.get("episode_description") or "")[:600],
        "published_at": ep.get("posted_at") or "",
        "duration":     ep.get("episode_duration") or 0,
        "transcript":   ep.get("episode_transcript") or "",
    }
