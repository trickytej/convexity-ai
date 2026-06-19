"""Layer 1 endpoints: shows, episodes, and formatted transcripts."""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timedelta, timezone

import feedparser
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel

from ...config import get_settings
from ...feeds import parse_feed
from ...net import fetch_bytes
from ...pipeline import acquire_episode, discover_show, generate_insights, transcribe_episode
from ...registry import Glossary, Registry, Show
from ...store import repo
from ...store.models import Episode, EpisodeStatus
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
    keys = row.keys()
    return EpisodeOut(
        id=row["id"],
        show_slug=row["show_slug"],
        title=row["title"],
        published_at=row["published_at"],
        duration_seconds=row["duration_seconds"],
        guests=_json_list(row["guests"]) or None,
        episode_url=row["episode_url"],
        audio_url=row["audio_url"],
        source=row["transcript_source"] if "transcript_source" in keys else None,
        provider=row["transcript_provider"] if "transcript_provider" in keys else None,
        word_count=row["word_count"] if "word_count" in keys else None,
        nugget_count=row["nugget_count"] or 0 if "nugget_count" in keys else 0,
        status=row["status"] if "status" in keys else None,
        error=row["error"] if "error" in keys else None,
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
def list_shows(
    format: str | None = Query(None),
    db: sqlite3.Connection = Depends(get_db),
) -> list[ShowOut]:
    rows = repo.list_shows_with_counts(db)
    if format:
        rows = [r for r in rows if (r["format"] or "interview") == format]
    return [
        ShowOut(
            slug=r["slug"],
            name=r["name"],
            network=r["network"],
            homepage=r["homepage"],
            hosts=_json_list(r["hosts"]),
            tier=r["tier"],
            format=r["format"] or "interview",
            active=bool(r["active"]),
            total=r["total"] or 0,
            transcribed=r["transcribed"] or 0,
        )
        for r in rows
    ]


@router.get("/episodes", response_model=EpisodeListOut)
def list_episodes(
    show: str | None = None,
    days: int | None = None,
    all: bool = Query(False, alias="all"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: sqlite3.Connection = Depends(get_db),
) -> EpisodeListOut:
    since = datetime.now(timezone.utc) - timedelta(days=days) if days else None
    transcript_only = not all
    rows = repo.browse_episodes(db, show_slug=show, published_since=since, with_transcript_only=transcript_only, limit=limit, offset=offset)
    total = repo.count_episodes(db, show_slug=show, published_since=since, with_transcript_only=transcript_only)
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


@router.delete("/episodes/{episode_id}")
def delete_episode(episode_id: int, db: sqlite3.Connection = Depends(get_db)) -> dict:
    if db.execute("SELECT id FROM episodes WHERE id = ?", (episode_id,)).fetchone() is None:
        raise HTTPException(status_code=404, detail="episode not found")
    db.execute("DELETE FROM nugget_curation WHERE nugget_id IN (SELECT id FROM nuggets WHERE episode_id = ?)", (episode_id,))
    db.execute("DELETE FROM nuggets WHERE episode_id = ?", (episode_id,))
    db.execute("DELETE FROM episode_digests WHERE episode_id = ?", (episode_id,))
    db.execute("DELETE FROM transcripts WHERE episode_id = ?", (episode_id,))
    db.execute("DELETE FROM episodes WHERE id = ?", (episode_id,))
    db.commit()
    return {"deleted": episode_id}


class EpisodePatch(BaseModel):
    title: str


@router.patch("/episodes/{episode_id}", response_model=EpisodeOut)
def patch_episode(
    episode_id: int, body: EpisodePatch, db: sqlite3.Connection = Depends(get_db)
) -> EpisodeOut:
    ep = repo.get_episode(db, episode_id)
    if ep is None:
        raise HTTPException(status_code=404, detail="episode not found")
    title = body.title.strip()
    if not title:
        raise HTTPException(status_code=422, detail="title cannot be empty")
    db.execute(
        "UPDATE episodes SET title = ?, updated_at = ? WHERE id = ?",
        (title, __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(), episode_id),
    )
    db.commit()
    ep = repo.get_episode(db, episode_id)
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


# --- poll / process / status --------------------------------------------


def _show_from_db(db: sqlite3.Connection, slug: str) -> Show:
    row = db.execute("SELECT * FROM shows WHERE slug = ?", (slug,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"show '{slug}' not found")
    return Show(
        slug=row["slug"],
        name=row["name"],
        rss_url=row["rss_url"] or "",
        tier=row["tier"],
        transcript_source=row["transcript_source"] or "asr",
        hosts=_json_list(row["hosts"]),
        format=row["format"] or "interview",
        active=bool(row["active"]),
    )


@router.delete("/shows/{slug}")
def delete_show(slug: str, db: sqlite3.Connection = Depends(get_db)) -> dict:
    """Remove a show and all its associated data."""
    episode_ids = [r["id"] for r in db.execute("SELECT id FROM episodes WHERE show_slug = ?", (slug,)).fetchall()]
    if episode_ids:
        placeholders = ",".join("?" * len(episode_ids))
        db.execute(f"DELETE FROM nugget_curation WHERE nugget_id IN (SELECT id FROM nuggets WHERE episode_id IN ({placeholders}))", episode_ids)
        db.execute(f"DELETE FROM nuggets WHERE episode_id IN ({placeholders})", episode_ids)
        db.execute(f"DELETE FROM episode_digests WHERE episode_id IN ({placeholders})", episode_ids)
        db.execute(f"DELETE FROM episodes WHERE show_slug = ?", (slug,))
    db.execute("DELETE FROM shows WHERE slug = ?", (slug,))
    db.commit()
    return {"deleted": slug}


@router.post("/shows/{slug}/poll")
def poll_show(slug: str, db: sqlite3.Connection = Depends(get_db)) -> dict:
    """Discover new episodes for a show from its RSS feed."""
    show = _show_from_db(db, slug)
    if not show.rss_url:
        raise HTTPException(status_code=400, detail="This show has no RSS URL configured")
    result = discover_show(db, show)
    if result.error:
        raise HTTPException(status_code=502, detail=result.error)
    return {"new": result.new, "seen": result.seen, "total": result.total_in_feed}


def _load_glossary(settings) -> Glossary:
    try:
        return Registry.load(settings.shows_file).glossary
    except Exception:
        return Glossary()


import logging as _logging
_log = _logging.getLogger(__name__)


def _run_process(episode_id: int) -> None:
    """Background: acquire → transcribe → extract insights for one episode."""
    settings = get_settings()
    from ...store.db import connect as _db_connect

    conn = _db_connect(settings.resolved_db_path)
    try:
        ep = repo.get_episode(conn, episode_id)
        if ep is None:
            return
        show_row = conn.execute("SELECT * FROM shows WHERE slug = ?", (ep.show_slug,)).fetchone()
        if show_row is None:
            return
        show = Show(
            slug=show_row["slug"],
            name=show_row["name"],
            rss_url=show_row["rss_url"] or "",
            tier=show_row["tier"],
            transcript_source=show_row["transcript_source"] or "asr",
            hosts=json.loads(show_row["hosts"]) if show_row["hosts"] else [],
            format=show_row["format"] or "interview",
            active=bool(show_row["active"]),
        )
        glossary = _load_glossary(settings)

        # Re-acquire if not yet acquired, or if ACQUIRED but audio file is missing/invalid
        def _audio_is_valid(path: str | None) -> bool:
            if not path:
                return False
            from pathlib import Path as _Path
            from ...acquire.audio import _is_valid_audio_file
            p = _Path(path)
            return p.exists() and _is_valid_audio_file(p)

        is_newsletter = show.format == "newsletter" or show.transcript_source == "rss_text"

        needs_acquire = ep.status not in (EpisodeStatus.ACQUIRED, EpisodeStatus.TRANSCRIBED) or (
            ep.status == EpisodeStatus.ACQUIRED and (
                is_newsletter or not _audio_is_valid(ep.audio_path)
            )
        )
        if needs_acquire:
            acquire_episode(conn, ep, show, settings)
            ep = repo.get_episode(conn, episode_id)
            if ep is None:
                return
        if ep.status == EpisodeStatus.ACQUIRED and not is_newsletter:
            result = transcribe_episode(conn, ep, show, glossary, settings)
            if not result.ok:
                return
            ep = repo.get_episode(conn, episode_id)
            if ep is None:
                return

        if ep.status == EpisodeStatus.TRANSCRIBED:
            generate_insights(conn, ep, show, settings)
    except Exception as exc:
        _log.error("unhandled error processing episode %s: %s", episode_id, exc, exc_info=True)
        try:
            ep = repo.get_episode(conn, episode_id)
            if ep is not None and ep.status not in (EpisodeStatus.TRANSCRIBED, EpisodeStatus.FAILED):
                repo.set_status(conn, episode_id, EpisodeStatus.FAILED,
                                error=f"{type(exc).__name__}: {exc}")
        except Exception:
            pass
    finally:
        conn.close()


@router.post("/episodes/{episode_id}/process")
def process_episode(
    episode_id: int,
    background_tasks: BackgroundTasks,
    db: sqlite3.Connection = Depends(get_db),
) -> dict:
    """Start acquire → transcribe → insights pipeline for an episode in the background."""
    ep = repo.get_episode(db, episode_id)
    if ep is None:
        raise HTTPException(status_code=404, detail="episode not found")
    if ep.status == EpisodeStatus.TRANSCRIBED and repo.has_nuggets(db, episode_id):
        return {"status": "already_done"}
    background_tasks.add_task(_run_process, episode_id)
    return {"status": "started"}


@router.get("/episodes/{episode_id}/status")
def get_episode_status(episode_id: int, db: sqlite3.Connection = Depends(get_db)) -> dict:
    ep = repo.get_episode(db, episode_id)
    if ep is None:
        raise HTTPException(status_code=404, detail="episode not found")
    nugget_count = sum(repo.nugget_type_counts(db, episode_id).values())
    return {"status": ep.status, "error": ep.error, "nugget_count": nugget_count}


# --- podcast URL import --------------------------------------------------


def _slugify(text: str) -> str:
    return re.sub(r"-{2,}", "-", re.sub(r"[^a-z0-9]+", "-", text.lower())).strip("-")[:48]


class ImportPodcastIn(BaseModel):
    url: str


class ImportPodcastOut(BaseModel):
    slug: str
    name: str
    episode_count: int
    created: bool


@router.post("/shows/import", response_model=ImportPodcastOut)
def import_podcast(body: ImportPodcastIn, db: sqlite3.Connection = Depends(get_db)) -> ImportPodcastOut:
    """Accept an RSS feed URL, register the show, and import its episode list."""
    url = body.url.strip()
    if not url:
        raise HTTPException(status_code=422, detail="url is required")

    try:
        raw = fetch_bytes(url, timeout=20)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not fetch URL: {exc}") from exc

    parsed = feedparser.parse(raw)
    feed_title = (parsed.feed.get("title") or "").strip()
    if not feed_title and not parsed.entries:
        raise HTTPException(status_code=400, detail="URL does not appear to be a valid RSS/Atom feed")

    name = feed_title or url
    base_slug = _slugify(name) or "imported"

    # ensure slug is unique
    existing_slugs = {r["slug"] for r in db.execute("SELECT slug FROM shows").fetchall()}
    slug = base_slug
    suffix = 2
    while slug in existing_slugs:
        slug = f"{base_slug}-{suffix}"
        suffix += 1

    show_existed = slug in existing_slugs  # always False after loop, but track via DB
    # Check if this RSS URL is already registered
    existing_by_url = db.execute("SELECT slug FROM shows WHERE rss_url = ?", (url,)).fetchone()
    created = existing_by_url is None
    if existing_by_url:
        slug = existing_by_url["slug"]
        name = db.execute("SELECT name FROM shows WHERE slug = ?", (slug,)).fetchone()["name"]

    if created:
        show = Show(
            slug=slug,
            name=name,
            rss_url=url,
            tier="B",
            transcript_source="asr",
            active=True,
        )
        repo.sync_shows(db, [show])

    # Upsert episodes from the feed
    show_obj = Show(slug=slug, name=name, rss_url=url, tier="B", transcript_source="asr")
    try:
        episodes = parse_feed(show_obj, raw)
    except Exception:
        episodes = []

    for ep in episodes:
        repo.upsert_episode(db, ep)

    return ImportPodcastOut(slug=slug, name=name, episode_count=len(episodes), created=created)


# --- newsletter RSS import -----------------------------------------------


class ImportNewsletterOut(BaseModel):
    slug: str
    name: str
    episode_count: int
    created: bool


@router.post("/newsletters/import", response_model=ImportNewsletterOut)
def import_newsletter(body: ImportPodcastIn, db: sqlite3.Connection = Depends(get_db)) -> ImportNewsletterOut:
    """Register a newsletter RSS feed and import its articles as episodes."""
    url = body.url.strip()
    if not url:
        raise HTTPException(status_code=422, detail="url is required")

    try:
        raw = fetch_bytes(url, timeout=20)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not fetch URL: {exc}") from exc

    parsed = feedparser.parse(raw)
    feed_title = (parsed.feed.get("title") or "").strip()
    if not feed_title and not parsed.entries:
        raise HTTPException(status_code=400, detail="URL does not appear to be a valid RSS/Atom feed")

    name = feed_title or url
    base_slug = _slugify(name) or "newsletter"

    # Check if this RSS URL is already registered
    existing_by_url = db.execute("SELECT slug FROM shows WHERE rss_url = ?", (url,)).fetchone()
    created = existing_by_url is None

    if existing_by_url:
        slug = existing_by_url["slug"]
        name = db.execute("SELECT name FROM shows WHERE slug = ?", (slug,)).fetchone()["name"]
    else:
        existing_slugs = {r["slug"] for r in db.execute("SELECT slug FROM shows").fetchall()}
        slug = base_slug
        suffix = 2
        while slug in existing_slugs:
            slug = f"{base_slug}-{suffix}"
            suffix += 1

        show = Show(
            slug=slug,
            name=name,
            rss_url=url,
            tier="B",
            transcript_source="rss_text",
            format="newsletter",
            active=True,
        )
        repo.sync_shows(db, [show])

    show_obj = Show(slug=slug, name=name, rss_url=url, tier="B", transcript_source="rss_text", format="newsletter")
    try:
        episodes = parse_feed(show_obj, raw)
    except Exception:
        episodes = []

    for ep in episodes:
        repo.upsert_episode(db, ep)

    return ImportNewsletterOut(slug=slug, name=name, episode_count=len(episodes), created=created)


# --- single episode / interview import -----------------------------------

_IMPORTED_SHOW_SLUG = "imported"
_IMPORTED_SHOW = Show(
    slug=_IMPORTED_SHOW_SLUG,
    name="Imported",
    tier="B",
    transcript_source="asr",
    active=True,
)


class ImportEpisodeIn(BaseModel):
    url: str
    title: str = ""


class ImportEpisodeOut(BaseModel):
    episode_id: int
    title: str
    show_slug: str
    created: bool


@router.post("/episodes/import", response_model=ImportEpisodeOut)
def import_episode(body: ImportEpisodeIn, db: sqlite3.Connection = Depends(get_db)) -> ImportEpisodeOut:
    """Add a single interview or audio URL as an importable episode."""
    url = body.url.strip()
    if not url:
        raise HTTPException(status_code=422, detail="url is required")

    title = body.title.strip() or url

    # Ensure the "imported" catch-all show exists
    existing_show = db.execute("SELECT slug FROM shows WHERE slug = ?", (_IMPORTED_SHOW_SLUG,)).fetchone()
    if not existing_show:
        repo.sync_shows(db, [_IMPORTED_SHOW])

    # Check for existing episode with this URL to stay idempotent
    existing_ep = db.execute(
        "SELECT id, title FROM episodes WHERE (audio_url = ? OR episode_url = ?) AND show_slug = ?",
        (url, url, _IMPORTED_SHOW_SLUG),
    ).fetchone()
    if existing_ep:
        return ImportEpisodeOut(
            episode_id=existing_ep["id"],
            title=existing_ep["title"],
            show_slug=_IMPORTED_SHOW_SLUG,
            created=False,
        )

    ep = Episode(
        show_slug=_IMPORTED_SHOW_SLUG,
        guid=url,
        title=title,
        audio_url=url,
        episode_url=url,
        published_at=None,
    )
    episode_id, _ = repo.upsert_episode(db, ep)
    return ImportEpisodeOut(episode_id=episode_id, title=title, show_slug=_IMPORTED_SHOW_SLUG, created=True)
