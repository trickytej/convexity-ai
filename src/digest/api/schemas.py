"""Pydantic response models for the web API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


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


# --- Layer 2: weekly report (built from dataclasses via from_attributes) ---


class ReportNuggetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    episode_id: int
    show_slug: str
    episode_title: str
    published_at: str | None = None
    type: str
    claim: str
    quote: str | None = None
    speaker_name: str | None = None
    start_ms: int | None = None
    signal_score: float
    quote_verified: bool
    triage: str = "pending"
    sectors: list[str] = []
    companies: list[str] = []
    corroboration_shows: int = 1


class ReportSectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    sector: str
    count: int
    nuggets: list[ReportNuggetOut]


class EntityBuzzOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str
    shows: list[str]
    nugget_count: int


class WeeklyReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    since: str | None = None
    until: str
    days: int
    stats: dict
    sections: list[ReportSectionOut]
    top_entities: list[EntityBuzzOut]
