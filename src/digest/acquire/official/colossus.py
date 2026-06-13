"""Official transcript fetcher for Invest Like the Best (colossus.com).

Colossus server-renders the transcript inside ``<main>`` with each paragraph
prefixed by the speaker's first name (e.g. "Patrick ...", "Alex ..."). The page
is occasionally returned without the transcript body; in that case we raise
``TranscriptUnavailable`` so the pipeline falls back to ASR rather than storing a
partial transcript.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ...net import fetch_text
from ...registry import Show
from ...store.models import Episode
from ..base import ParsedTranscript, TranscriptSegment, TranscriptUnavailable, merge_consecutive

_MIN_PARAGRAPHS = 10
_MIN_CHARS = 2000


class ColossusFetcher:
    source_key = "colossus"

    def fetch(self, episode: Episode, show: Show) -> ParsedTranscript:
        if not episode.episode_url:
            raise TranscriptUnavailable("episode has no source URL")
        html = fetch_text(episode.episode_url)
        return self.parse(html, episode, show)

    def parse(self, html: str, episode: Episode, show: Show) -> ParsedTranscript:
        soup = BeautifulSoup(html, "lxml")
        main = soup.select_one("main") or soup.select_one("article")
        if main is None:
            raise TranscriptUnavailable("no main/article container")

        paragraphs = [p.get_text(" ", strip=True) for p in main.find_all("p")]
        paragraphs = [p for p in paragraphs if p]
        if len(paragraphs) < _MIN_PARAGRAPHS or sum(len(p) for p in paragraphs) < _MIN_CHARS:
            raise TranscriptUnavailable("transcript body not present in server HTML")

        names = self._name_pool(show, episode)
        segments: list[TranscriptSegment] = []
        current: str | None = None
        for para in paragraphs:
            speaker, rest = self._split_speaker(para, names)
            if speaker is not None:
                current = speaker
                if rest:
                    segments.append(TranscriptSegment(speaker_name=current, text=rest))
            elif current is not None:
                segments.append(TranscriptSegment(speaker_name=current, text=para))
            # else: pre-dialogue boilerplate; skip until first attributable speaker

        segments = merge_consecutive(segments)
        if len(segments) < 3:
            raise TranscriptUnavailable("could not attribute speakers in transcript")

        return ParsedTranscript(
            provider="colossus",
            segments=segments,
            language="en",
            has_diarization=True,
            source_url=episode.episode_url,
            meta={"speakers": sorted({s.speaker_name for s in segments if s.speaker_name})},
        )

    @staticmethod
    def _name_pool(show: Show, episode: Episode) -> dict[str, str]:
        """Map a recognised leading first-name (lowercased) -> display name."""
        pool: dict[str, str] = {}
        for host in show.hosts:
            first = host.split()[0]
            pool[first.lower()] = first
        # Guest name is typically the leading token(s) of the episode title.
        head = re.split(r"\s[-–—]\s", episode.title)[0].strip()
        head = re.sub(r"\[.*?\]|\(.*?\)", "", head).strip()
        if head and len(head.split()) <= 4:
            guest_first = head.split()[0]
            if guest_first[:1].isupper():
                pool.setdefault(guest_first.lower(), guest_first)
                pool[head.lower()] = head  # also allow full guest name as prefix
        return pool

    @staticmethod
    def _split_speaker(para: str, names: dict[str, str]) -> tuple[str | None, str | None]:
        # Try a full-name prefix first, then a single leading token.
        lowered = para.lower()
        for key, display in sorted(names.items(), key=lambda kv: -len(kv[0])):
            if lowered.startswith(key):
                after = para[len(key):]
                # Must be a prefix label, not "Name, ..." address mid-sentence.
                if after[:1] in {" ", ""} and not after.lstrip().startswith(","):
                    return display, after.strip() or None
        return None, None
