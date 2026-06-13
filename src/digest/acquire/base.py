"""Shared types for transcript acquisition.

A fetched/parsed transcript is represented uniformly as a list of
``TranscriptSegment`` regardless of whether it came from an official source or
from ASR, so downstream stages don't care about provenance.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from ..registry import Show
from ..store.models import Episode


class TranscriptUnavailable(Exception):
    """Raised when an official transcript cannot be retrieved.

    Signals the pipeline to fall back to the audio + ASR path.
    """


@dataclass
class TranscriptSegment:
    speaker_name: str | None
    text: str
    speaker_label: str | None = None
    start_ms: int | None = None
    end_ms: int | None = None


@dataclass
class ParsedTranscript:
    provider: str
    segments: list[TranscriptSegment] = field(default_factory=list)
    language: str | None = "en"
    has_diarization: bool = True
    source_url: str | None = None
    raw_text: str | None = None
    meta: dict | None = None

    def word_count(self) -> int:
        return sum(len(re.findall(r"\w+", s.text)) for s in self.segments)

    def non_empty(self) -> bool:
        return any(s.text.strip() for s in self.segments)


@runtime_checkable
class OfficialFetcher(Protocol):
    source_key: str

    def fetch(self, episode: Episode, show: Show) -> ParsedTranscript: ...


def merge_consecutive(segments: list[TranscriptSegment]) -> list[TranscriptSegment]:
    """Collapse adjacent segments from the same speaker into one block."""
    merged: list[TranscriptSegment] = []
    for seg in segments:
        text = seg.text.strip()
        if not text:
            continue
        if merged and merged[-1].speaker_name == seg.speaker_name and seg.start_ms is None:
            merged[-1].text = f"{merged[-1].text}\n\n{text}"
            if seg.end_ms is not None:
                merged[-1].end_ms = seg.end_ms
        else:
            merged.append(
                TranscriptSegment(
                    speaker_name=seg.speaker_name,
                    text=text,
                    speaker_label=seg.speaker_label,
                    start_ms=seg.start_ms,
                    end_ms=seg.end_ms,
                )
            )
    return merged
