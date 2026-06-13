"""RSS feed parsing and episode discovery."""

from __future__ import annotations

from datetime import datetime, timezone

import feedparser
from dateutil import parser as dateparser

from .config import Settings, get_settings
from .net import fetch_bytes
from .registry import Show
from .store.models import Episode


def _parse_duration(value: object) -> int | None:
    """itunes:duration may be 'HH:MM:SS', 'MM:SS', or a plain seconds string."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.isdigit():
        return int(text)
    try:
        nums = [int(p) for p in text.split(":")]
    except ValueError:
        return None
    seconds = 0
    for n in nums:
        seconds = seconds * 60 + n
    return seconds


def _parse_date(entry: feedparser.FeedParserDict) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        st = entry.get(key)
        if st:
            return datetime(*st[:6], tzinfo=timezone.utc)
    for key in ("published", "updated", "pubDate"):
        raw = entry.get(key)
        if raw:
            try:
                dt = dateparser.parse(raw)
            except (ValueError, OverflowError, TypeError):
                continue
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
    return None


def _audio_url(entry: feedparser.FeedParserDict) -> str | None:
    for enc in entry.get("enclosures", []) or []:
        href = enc.get("href") or enc.get("url")
        typ = (enc.get("type") or "").lower()
        if href and (typ.startswith("audio") or not typ):
            return href
    for link in entry.get("links", []) or []:
        if link.get("rel") == "enclosure" and link.get("href"):
            typ = (link.get("type") or "").lower()
            if typ.startswith("audio") or not typ:
                return link["href"]
    return None


def _guid(entry: feedparser.FeedParserDict) -> str | None:
    return (
        entry.get("id")
        or entry.get("guid")
        or entry.get("link")
        or entry.get("title")
    )


def parse_feed(show: Show, raw: bytes) -> list[Episode]:
    parsed = feedparser.parse(raw)
    episodes: list[Episode] = []
    for entry in parsed.entries:
        guid = _guid(entry)
        if not guid:
            continue
        title = (entry.get("title") or "(untitled)").strip()
        episodes.append(
            Episode(
                show_slug=show.slug,
                guid=str(guid),
                title=title,
                published_at=_parse_date(entry),
                audio_url=_audio_url(entry),
                episode_url=entry.get("link"),
                duration_seconds=_parse_duration(entry.get("itunes_duration")),
            )
        )
    return episodes


def fetch_feed(show: Show, settings: Settings | None = None) -> list[Episode]:
    settings = settings or get_settings()
    if not show.rss_url:
        return []
    raw = fetch_bytes(show.rss_url, settings)
    return parse_feed(show, raw)
