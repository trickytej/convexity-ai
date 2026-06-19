"""Fetch and extract text from a web article (newsletter RSS path).

Returns a ParsedTranscript whose segments are article paragraphs, so the
existing persist_parsed_transcript / insights pipeline works unchanged.
"""

from __future__ import annotations

import logging

import httpx
from bs4 import BeautifulSoup

from .base import ParsedTranscript, TranscriptSegment, TranscriptUnavailable

log = logging.getLogger(__name__)

_STRIP_TAGS = {"script", "style", "nav", "header", "footer", "aside", "noscript", "figure"}
_CONTENT_TAGS = {"article", "main", "[document]"}


def _extract_paragraphs(html: str, url: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")

    # Remove noise elements
    for tag in soup(_STRIP_TAGS):
        tag.decompose()

    # Prefer <article> or <main>; fall back to <body>
    root = soup.find("article") or soup.find("main") or soup.body or soup

    paragraphs: list[str] = []
    for p in root.find_all("p"):
        text = p.get_text(separator=" ", strip=True)
        if len(text) > 40:  # skip tiny captions / nav links
            paragraphs.append(text)

    if not paragraphs:
        # Fallback: grab all block-level text nodes
        for tag in root.find_all(["p", "li", "blockquote", "h2", "h3"]):
            text = tag.get_text(separator=" ", strip=True)
            if len(text) > 40:
                paragraphs.append(text)

    return paragraphs


def fetch_article(url: str) -> ParsedTranscript:
    """Fetch *url* and return its text as a ParsedTranscript."""
    if not url:
        raise TranscriptUnavailable("no article URL")

    # Explicit per-phase timeouts: connect quickly, allow up to 20s to read the body.
    timeout = httpx.Timeout(connect=8.0, read=20.0, write=5.0, pool=5.0)

    try:
        resp = httpx.get(
            url,
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; research-digest/1.0)"},
        )
        resp.raise_for_status()
    except httpx.TimeoutException as exc:
        raise TranscriptUnavailable(f"timed out fetching {url}") from exc
    except httpx.HTTPStatusError as exc:
        raise TranscriptUnavailable(
            f"HTTP {exc.response.status_code} fetching {url}"
        ) from exc
    except httpx.HTTPError as exc:
        raise TranscriptUnavailable(f"HTTP error fetching {url}: {exc}") from exc

    content_type = resp.headers.get("content-type", "")
    if "html" not in content_type and "text" not in content_type:
        raise TranscriptUnavailable(f"unexpected content-type: {content_type}")

    paragraphs = _extract_paragraphs(resp.text, url)
    if not paragraphs:
        raise TranscriptUnavailable(f"no text extracted from {url}")

    log.info("article %s → %d paragraphs", url, len(paragraphs))

    segments = [
        TranscriptSegment(speaker_name=None, text=p)
        for p in paragraphs
    ]

    return ParsedTranscript(
        provider="rss_text",
        segments=segments,
        has_diarization=False,
        source_url=url,
    )
