"""Layer 1 endpoints: shows, episodes, and formatted transcripts."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

from ...store import repo
from ...store.models import Episode
from ..deps import get_db
from ..schemas import EpisodeListOut, EpisodeOut, SegmentOut, ShowOut, TranscriptOut

router = APIRouter(tags=["library"])


def _json_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def _episode_out_from_row(row: sqlite3.Row) -> EpisodeOut:
    return EpisodeOut(
        id=row["id"],
        show_slug=row["show_slug"],
        title=row["title"],
        published_at=row["published_at"],
        duration_seconds=row["duration_seconds"],
        guests=_json_list(row["guests"]) or None,
        episode_url=row["episode_url"],
        audio_url=row["audio_url"],
        source=row["transcript_source"],
        provider=row["transcript_provider"],
        word_count=row["word_count"],
        nugget_count=row["nugget_count"] or 0,
    )


def _episode_out(ep: Episode, transcript: sqlite3.Row | None, nugget_count: int) -> EpisodeOut:
    return EpisodeOut(
        id=ep.id,
        show_slug=ep.show_slug,
        title=ep.title,
        published_at=ep.published_at,
        duration_seconds=ep.duration_seconds,
        guests=ep.guests,
        episode_url=ep.episode_url,
        audio_url=ep.audio_url,
        source=transcript["source"] if transcript else None,
        provider=transcript["provider"] if transcript else None,
        word_count=transcript["word_count"] if transcript else None,
        nugget_count=nugget_count,
    )


@router.get("/shows", response_model=list[ShowOut])
def list_shows(db: sqlite3.Connection = Depends(get_db)) -> list[ShowOut]:
    return [
        ShowOut(
            slug=r["slug"],
            name=r["name"],
            network=r["network"],
            homepage=r["homepage"],
            hosts=_json_list(r["hosts"]),
            tier=r["tier"],
            active=bool(r["active"]),
            total=r["total"] or 0,
            transcribed=r["transcribed"] or 0,
        )
        for r in repo.list_shows_with_counts(db)
    ]


@router.get("/episodes", response_model=EpisodeListOut)
def list_episodes(
    show: str | None = None,
    days: int | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: sqlite3.Connection = Depends(get_db),
) -> EpisodeListOut:
    since = datetime.now(timezone.utc) - timedelta(days=days) if days else None
    rows = repo.browse_episodes(db, show_slug=show, published_since=since, limit=limit, offset=offset)
    total = repo.count_episodes(db, show_slug=show, published_since=since)
    return EpisodeListOut(
        total=total,
        limit=limit,
        offset=offset,
        episodes=[_episode_out_from_row(r) for r in rows],
    )


@router.get("/episodes/{episode_id}", response_model=EpisodeOut)
def get_episode(
    episode_id: int, db: sqlite3.Connection = Depends(get_db)
) -> EpisodeOut:
    ep = repo.get_episode(db, episode_id)
    if ep is None:
        raise HTTPException(status_code=404, detail="episode not found")
    transcript = repo.get_transcript_for_episode(db, episode_id)
    nugget_count = sum(repo.nugget_type_counts(db, episode_id).values())
    return _episode_out(ep, transcript, nugget_count)


@router.get("/episodes/{episode_id}/transcript", response_model=TranscriptOut)
def get_transcript(
    episode_id: int, db: sqlite3.Connection = Depends(get_db)
) -> TranscriptOut:
    ep = repo.get_episode(db, episode_id)
    if ep is None:
        raise HTTPException(status_code=404, detail="episode not found")
    transcript = repo.get_transcript_for_episode(db, episode_id)
    if transcript is None:
        raise HTTPException(status_code=404, detail="no transcript for this episode")

    segments = repo.get_segments(db, transcript["id"])
    speakers: list[str] = []
    for seg in segments:
        if seg.speaker_name and seg.speaker_name not in speakers:
            speakers.append(seg.speaker_name)
    nugget_count = sum(repo.nugget_type_counts(db, episode_id).values())

    return TranscriptOut(
        episode=_episode_out(ep, transcript, nugget_count),
        source=transcript["source"],
        provider=transcript["provider"],
        has_diarization=bool(transcript["has_diarization"]),
        corrected=bool(transcript["corrected"]),
        word_count=transcript["word_count"],
        speakers=speakers,
        segments=[
            SegmentOut(
                idx=s.idx,
                speaker_name=s.speaker_name,
                speaker_label=s.speaker_label,
                start_ms=s.start_ms,
                end_ms=s.end_ms,
                text=s.text,
            )
            for s in segments
        ],
    )
