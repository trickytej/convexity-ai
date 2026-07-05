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

# Delay between consecutive person searches to stay within Podscan's rate limit.
_REQUEST_DELAY_SECONDS = 1.0
_RETRY_AFTER_SECONDS = 60     # wait after a 429 before retrying once


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


def _cutoff_dt(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


def search_episodes(query: str, *, days: int = 30, max_results: int = 10) -> list[dict]:
    """Search Podscan for recent episodes where *person_name* is a guest.

    Podscan's full-text search returns all mentions, so we apply client-side
    filters: date window, minimum duration, and a guest-appearance heuristic
    on the title + description.

    Results are sorted newest-first so we stop paginating once past the window.
    """
    settings = get_settings()
    if not settings.podscan_api_key:
        log.warning("PODSCAN_API_KEY not set — skipping search for %r", query)
        return []

    cutoff = _cutoff_dt(days)
    collected: list[dict] = []
    page = 1

    try:
        with httpx.Client(timeout=20) as client:
            while len(collected) < max_results:
                params = {
                    "query":    query,
                    "order_by": "posted_at",
                    "order":    "desc",
                    "per_page": 20,
                    "page":     page,
                }
                headers = {"Authorization": f"Bearer {settings.podscan_api_key}"}

                resp = client.get(f"{_BASE}/episodes/search", params=params, headers=headers)

                if resp.status_code == 429:
                    log.warning("Podscan rate limit hit for %r — waiting %ss", query, _RETRY_AFTER_SECONDS)
                    time.sleep(_RETRY_AFTER_SECONDS)
                    resp = client.get(f"{_BASE}/episodes/search", params=params, headers=headers)

                resp.raise_for_status()
                data = resp.json()
                episodes = data.get("episodes", [])
                if not episodes:
                    break

                past_window = False
                for ep in episodes:
                    posted_raw = ep.get("posted_at") or ""
                    if posted_raw:
                        try:
                            posted = datetime.fromisoformat(posted_raw)
                            if posted.tzinfo is None:
                                posted = posted.replace(tzinfo=timezone.utc)
                            if posted < cutoff:
                                past_window = True
                                break
                        except ValueError:
                            pass

                    duration = ep.get("episode_duration") or 0
                    if duration < _MIN_DURATION_SECONDS:
                        continue

                    title = (ep.get("episode_title") or "").strip()
                    desc = ep.get("episode_description") or ""
                    if not _is_guest_appearance(query, title, desc):
                        continue

                    collected.append(_normalise(ep))
                    if len(collected) >= max_results:
                        break

                if past_window or len(collected) >= max_results:
                    break

                pagination = data.get("pagination", {})
                if page >= (pagination.get("last_page") or 1):
                    break
                page += 1

                time.sleep(_REQUEST_DELAY_SECONDS)

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
