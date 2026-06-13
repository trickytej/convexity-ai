"""Official transcript fetcher for the Dwarkesh Podcast (Substack).

Transcripts live in the post body (``div.available-content``). Each speaker turn
starts with a paragraph whose entire content is the speaker's name in bold,
followed by that speaker's paragraphs until the next name header.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup, Tag

from ...net import fetch_text
from ...registry import Show
from ...store.models import Episode
from ..base import ParsedTranscript, TranscriptSegment, TranscriptUnavailable, merge_consecutive

_TS_SUFFIX = re.compile(r"\s*[\(\[]?\d{1,2}:\d{2}(?::\d{2})?[\)\]]?\s*$")

# Bold one-word section labels that are not speakers.
_NON_SPEAKER = {
    "sponsors",
    "sponsor",
    "transcript",
    "timestamps",
    "outline",
    "introduction",
    "intro",
    "note",
    "update",
}


class DwarkeshFetcher:
    source_key = "dwarkesh"

    def fetch(self, episode: Episode, show: Show) -> ParsedTranscript:
        if not episode.episode_url:
            raise TranscriptUnavailable("episode has no source URL")
        html = fetch_text(episode.episode_url)
        return self.parse(html, episode)

    def parse(self, html: str, episode: Episode) -> ParsedTranscript:
        soup = BeautifulSoup(html, "lxml")
        container = soup.select_one("div.available-content") or soup.select_one(
            "div.body.markup"
        )
        if container is None:
            raise TranscriptUnavailable("transcript container not found in page")

        segments: list[TranscriptSegment] = []
        current: str | None = None
        started = False

        # Only <p>/<li> carry dialogue; headings (h1-h3) are section markers.
        for block in container.find_all(["p", "li"]):
            text = block.get_text(" ", strip=True)
            if not text:
                continue

            speaker, inline_speech = self._speaker_from_block(block, text)
            if speaker is not None:
                current = speaker
                started = True
                if inline_speech:
                    segments.append(TranscriptSegment(speaker_name=current, text=inline_speech))
                continue

            if not started or current is None:
                # Skip the intro / sponsor blocks that precede the first speaker.
                continue
            segments.append(TranscriptSegment(speaker_name=current, text=text))

        segments = merge_consecutive(segments)
        if len(segments) < 3:
            raise TranscriptUnavailable("parsed too few dialogue segments")

        return ParsedTranscript(
            provider="dwarkesh",
            segments=segments,
            language="en",
            has_diarization=True,
            source_url=episode.episode_url,
            meta={"speakers": sorted({s.speaker_name for s in segments if s.speaker_name})},
        )

    @staticmethod
    def _speaker_from_block(block: Tag, text: str) -> tuple[str | None, str | None]:
        """Return (speaker_name, inline_speech) if the block opens a speaker turn."""
        strong = block.find(["strong", "b"])
        if strong is None:
            return None, None
        name = strong.get_text(" ", strip=True)
        if not name:
            return None, None

        # Case 1: the whole block is just the bold name (optionally + timestamp).
        cleaned = _TS_SUFFIX.sub("", text).strip()
        if cleaned == name and DwarkeshFetcher._looks_like_name(name):
            return name.rstrip(":").strip(), None

        # Case 2: inline "Name: speech" where the name is bold at the start.
        if name.endswith(":") and text.startswith(name):
            speaker = name.rstrip(":").strip()
            if DwarkeshFetcher._looks_like_name(speaker):
                speech = text[len(name):].strip()
                return speaker, (speech or None)

        return None, None

    @staticmethod
    def _looks_like_name(value: str) -> bool:
        value = value.rstrip(":").strip()
        if not value or len(value) > 50:
            return False
        if value.lower() in _NON_SPEAKER:
            return False
        words = value.split()
        if not (1 <= len(words) <= 5):
            return False
        # Reject sentence-like text.
        if re.search(r"[.!?]", value):
            return False
        return value[0].isupper()
