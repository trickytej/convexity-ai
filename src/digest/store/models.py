"""Dataclass models mirroring the persisted rows."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class EpisodeStatus(str, Enum):
    DISCOVERED = "discovered"   # found in feed, nothing fetched yet
    ACQUIRED = "acquired"       # audio downloaded or official transcript raw fetched
    TRANSCRIBED = "transcribed" # normalized transcript stored
    FAILED = "failed"


class TranscriptSource(str, Enum):
    OFFICIAL = "official"
    ASR = "asr"


@dataclass
class Episode:
    show_slug: str
    guid: str
    title: str
    published_at: datetime | None = None
    audio_url: str | None = None
    episode_url: str | None = None
    duration_seconds: int | None = None
    guests: list[str] | None = None
    audio_path: str | None = None
    status: EpisodeStatus = EpisodeStatus.DISCOVERED
    error: str | None = None
    id: int | None = None


@dataclass
class Segment:
    idx: int
    text: str
    speaker_label: str | None = None
    speaker_name: str | None = None
    start_ms: int | None = None
    end_ms: int | None = None
    id: int | None = None
    transcript_id: int | None = None


@dataclass
class Transcript:
    episode_id: int
    source: TranscriptSource
    provider: str
    language: str | None = None
    has_diarization: bool = False
    corrected: bool = False
    word_count: int | None = None
    raw_path: str | None = None
    normalized_path: str | None = None
    meta: dict | None = None
    id: int | None = None
    segments: list[Segment] = field(default_factory=list)
