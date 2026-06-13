"""Pydantic response models for the web API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ShowOut(BaseModel):
    slug: str
    name: str
    network: str | None = None
    homepage: str | None = None
    hosts: list[str] = []
    tier: str
    active: bool
    total: int
    transcribed: int


class EpisodeOut(BaseModel):
    id: int
    show_slug: str
    title: str
    published_at: datetime | None = None
    duration_seconds: int | None = None
    guests: list[str] | None = None
    episode_url: str | None = None
    audio_url: str | None = None
    source: str | None = None          # official | asr
    provider: str | None = None
    word_count: int | None = None
    nugget_count: int = 0


class EpisodeListOut(BaseModel):
    total: int
    limit: int
    offset: int
    episodes: list[EpisodeOut]


class SegmentOut(BaseModel):
    idx: int
    speaker_name: str | None = None
    speaker_label: str | None = None
    start_ms: int | None = None
    end_ms: int | None = None
    text: str


class TranscriptOut(BaseModel):
    episode: EpisodeOut
    source: str
    provider: str
    has_diarization: bool
    corrected: bool
    word_count: int | None = None
    speakers: list[str] = []
    segments: list[SegmentOut]
