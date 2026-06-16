"""Pydantic response models for the web API."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


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
    status: str | None = None          # discovered | acquired | transcribed | failed
    error: str | None = None


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


# --- Layer 2: curation ---------------------------------------------------


class CurationOut(BaseModel):
    decision: str = "unreviewed"
    curator_rank: int | None = None
    contradicts_consensus: bool = False
    note: str | None = None
    updated_at: str | None = None


class NuggetWithCurationOut(BaseModel):
    id: int
    episode_id: int
    type: str
    claim: str
    quote: str | None = None
    speaker_name: str | None = None
    start_ms: int | None = None
    end_ms: int | None = None
    entities: dict | None = None
    sectors: list[str] = []
    primary_sector: str | None = None
    scores: dict | None = None
    signal_score: float
    quote_verified: bool
    triage: str
    suggested_rank: int  # 1/2/3 derived from signal_score at read time
    curation: CurationOut


class CurationPatch(BaseModel):
    decision: Literal["unreviewed", "kept", "killed"] | None = None
    curator_rank: int | None = Field(None, ge=1, le=3)
    contradicts_consensus: bool | None = None
    note: str | None = None


class CurationStatsOut(BaseModel):
    total: int
    reviewed: int
    kept: int
    killed: int


# --- Layer 2: newsletter -------------------------------------------------


class NewsletterNuggetOut(BaseModel):
    id: int
    episode_id: int
    show_slug: str
    episode_title: str
    episode_published_at: str | None = None
    type: str
    claim: str
    quote: str | None = None
    speaker_name: str | None = None
    start_ms: int | None = None
    sectors: list[str] = []
    primary_sector: str | None = None
    companies: list[str] = []
    tickers: list[str] = []
    curator_rank: int | None = None
    contradicts_consensus: bool = False
    curation_note: str | None = None


class StockMentionOut(BaseModel):
    company: str
    tickers: list[str]
    mention_count: int
    nugget_ids: list[int]
    stance: str = "mentioned"
    summary: str = ""
    source_episode_id: int | None = None
    source_start_ms: int | None = None


class NewsletterOut(BaseModel):
    from_date: str | None
    to_date: str | None
    episode_count: int
    kept_count: int
    lead: list[NewsletterNuggetOut]         # curator_rank == 1
    good_to_know: list[NewsletterNuggetOut] # curator_rank 2-3 or unranked
    stock_readthrough: list[StockMentionOut]
    markdown: str
