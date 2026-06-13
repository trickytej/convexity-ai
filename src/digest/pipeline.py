"""Orchestration across the Step 1-2 stages (discovery for now)."""

from __future__ import annotations

import json
import logging
import sqlite3
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from pathlib import Path

from .acquire.audio import download_audio
from .acquire.base import ParsedTranscript, TranscriptSegment, TranscriptUnavailable
from .acquire.official import get_official_fetcher
from .config import Settings, get_settings
from .feeds import fetch_feed
from .registry import Registry, Show
from .store import repo
from .store.models import Episode, EpisodeStatus, Segment, Transcript, TranscriptSource

log = logging.getLogger(__name__)


@dataclass
class ShowDiscovery:
    slug: str
    new: int = 0
    seen: int = 0
    total_in_feed: int = 0
    error: str | None = None


def discover_show(
    conn: sqlite3.Connection, show: Show, settings: Settings | None = None
) -> ShowDiscovery:
    settings = settings or get_settings()
    result = ShowDiscovery(slug=show.slug)
    try:
        episodes = fetch_feed(show, settings)
    except Exception as exc:  # network/parse failures shouldn't abort the whole poll
        result.error = f"{type(exc).__name__}: {exc}"
        log.warning("discovery failed for %s: %s", show.slug, result.error)
        return result

    result.total_in_feed = len(episodes)
    for ep in episodes:
        _episode_id, created = repo.upsert_episode(conn, ep)
        if created:
            result.new += 1
        else:
            result.seen += 1
    return result


def discover_all(
    conn: sqlite3.Connection,
    registry: Registry,
    settings: Settings | None = None,
    only: Iterable[str] | None = None,
) -> list[ShowDiscovery]:
    settings = settings or get_settings()
    shows = registry.active()
    if only:
        only_set = set(only)
        shows = [s for s in shows if s.slug in only_set]
    return [discover_show(conn, show, settings) for show in shows]


# --- acquisition (Step 2a: get the transcript or the audio) --------------


@dataclass
class AcquireResult:
    episode_id: int
    action: str  # "official" | "audio" | "failed"
    detail: str = ""
    error: str | None = None


def persist_parsed_transcript(
    conn: sqlite3.Connection,
    episode: Episode,
    parsed: ParsedTranscript,
    source: TranscriptSource,
    settings: Settings,
    *,
    corrected: bool = False,
) -> int:
    """Write the normalized transcript JSON to disk and upsert it into the DB."""
    assert episode.id is not None
    out_dir = settings.transcripts_dir / episode.show_slug
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{episode.id}.json"

    segments = [
        Segment(
            idx=i,
            text=s.text,
            speaker_name=s.speaker_name,
            speaker_label=s.speaker_label,
            start_ms=s.start_ms,
            end_ms=s.end_ms,
        )
        for i, s in enumerate(parsed.segments)
    ]

    payload = {
        "episode_id": episode.id,
        "show_slug": episode.show_slug,
        "title": episode.title,
        "published_at": episode.published_at.isoformat() if episode.published_at else None,
        "source": source.value,
        "provider": parsed.provider,
        "language": parsed.language,
        "has_diarization": parsed.has_diarization,
        "corrected": corrected,
        "source_url": parsed.source_url,
        "word_count": parsed.word_count(),
        "meta": parsed.meta,
        "segments": [
            {
                "idx": s.idx,
                "speaker_name": s.speaker_name,
                "speaker_label": s.speaker_label,
                "start_ms": s.start_ms,
                "end_ms": s.end_ms,
                "text": s.text,
            }
            for s in segments
        ],
    }
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    transcript = Transcript(
        episode_id=episode.id,
        source=source,
        provider=parsed.provider,
        language=parsed.language,
        has_diarization=parsed.has_diarization,
        corrected=corrected,
        word_count=parsed.word_count(),
        normalized_path=str(out_path),
        meta=parsed.meta,
        segments=segments,
    )
    return repo.insert_transcript(conn, transcript)


def acquire_episode(
    conn: sqlite3.Connection,
    episode: Episode,
    show: Show,
    settings: Settings | None = None,
) -> AcquireResult:
    """Tier A: fetch the official transcript (fall back to audio if unavailable).
    Tier B: download the audio enclosure for later ASR.
    """
    settings = settings or get_settings()
    assert episode.id is not None

    if show.uses_official_transcript:
        fetcher = get_official_fetcher(show.transcript_source)
        if fetcher is not None:
            try:
                parsed = fetcher.fetch(episode, show)
                if not parsed.non_empty():
                    raise TranscriptUnavailable("empty transcript")
                persist_parsed_transcript(
                    conn, episode, parsed, TranscriptSource.OFFICIAL, settings
                )
                repo.set_status(conn, episode.id, EpisodeStatus.TRANSCRIBED)
                return AcquireResult(
                    episode.id,
                    "official",
                    f"{len(parsed.segments)} segs, {parsed.word_count()} words",
                )
            except TranscriptUnavailable as exc:
                log.info(
                    "official transcript unavailable for ep %s (%s); falling back to audio",
                    episode.id,
                    exc,
                )
            except Exception as exc:  # parser bug shouldn't strand the episode
                log.warning("official fetch error for ep %s: %s", episode.id, exc)

    try:
        dest = download_audio(episode, settings)
        repo.set_audio_path(conn, episode.id, str(dest))
        repo.set_status(conn, episode.id, EpisodeStatus.ACQUIRED)
        size_mb = dest.stat().st_size / (1024 * 1024)
        return AcquireResult(episode.id, "audio", f"{size_mb:.1f} MB")
    except Exception as exc:
        msg = f"{type(exc).__name__}: {exc}"
        repo.set_status(conn, episode.id, EpisodeStatus.FAILED, error=msg)
        return AcquireResult(episode.id, "failed", error=msg)


# --- transcription (Step 2b: ASR -> speaker names -> correction) ---------


@dataclass
class TranscribeResult:
    episode_id: int
    ok: bool
    detail: str = ""
    error: str | None = None


def transcribe_episode(
    conn: sqlite3.Connection,
    episode: Episode,
    show: Show,
    glossary,
    settings: Settings | None = None,
    *,
    correct: bool = True,
    identify: bool = True,
) -> TranscribeResult:
    """Transcribe a downloaded episode: ASR + diarization, map speaker names,
    run the proper-noun correction pass, and store the normalized transcript.
    """
    settings = settings or get_settings()
    assert episode.id is not None
    if not episode.audio_path:
        return TranscribeResult(episode.id, False, error="no audio (run `acquire` first)")

    # Imported lazily so `poll`/`acquire` don't pay the SDK import cost.
    from .transcribe.assemblyai_client import TranscriptionError, transcribe_audio
    from .transcribe.correct import correct_transcript
    from .transcribe.llm import LLMError
    from .transcribe.speakers import apply_speaker_names, identify_speakers

    try:
        parsed = transcribe_audio(episode.audio_path, show, glossary, settings)
    except TranscriptionError as exc:
        msg = f"{type(exc).__name__}: {exc}"
        repo.set_status(conn, episode.id, EpisodeStatus.FAILED, error=msg)
        return TranscribeResult(episode.id, False, error=msg)

    if identify and parsed.has_diarization:
        try:
            mapping = identify_speakers(parsed, show, episode, settings)
        except LLMError as exc:
            log.warning("speaker id skipped (%s)", exc)
            mapping = {}
        apply_speaker_names(parsed, mapping)
    else:
        apply_speaker_names(parsed, {})

    corrected = False
    if correct:
        try:
            n = correct_transcript(
                parsed, glossary, settings, context=f"{show.name}: {episode.title}"
            )
            corrected = True
            log.info("correction changed %d segment(s)", n)
        except LLMError as exc:
            log.warning("correction skipped (%s)", exc)

    persist_parsed_transcript(
        conn, episode, parsed, TranscriptSource.ASR, settings, corrected=corrected
    )
    repo.set_status(conn, episode.id, EpisodeStatus.TRANSCRIBED)
    speakers = sorted({s.speaker_name for s in parsed.segments if s.speaker_name})
    detail = f"{len(parsed.segments)} segs, {parsed.word_count()} words, {len(speakers)} speakers"
    if corrected:
        detail += ", corrected"
    return TranscribeResult(episode.id, True, detail=detail)


# --- weekly ingest: discover -> acquire -> transcribe a date window ------


@dataclass
class IngestOutcome:
    episode_id: int
    show_slug: str
    title: str
    stage: str  # "official" | "transcribed" | "failed"
    detail: str = ""
    error: str | None = None


def ingest_window(
    conn: sqlite3.Connection,
    registry: Registry,
    settings: Settings | None = None,
    *,
    days: int = 7,
    only: Iterable[str] | None = None,
    correct: bool = True,
    identify: bool = True,
    skip_poll: bool = False,
    progress: Callable[[str], None] | None = None,
) -> list[IngestOutcome]:
    """Run the full pipeline for every episode published in the last ``days``:
    discover (unless skipped) -> acquire -> transcribe Tier B.
    """
    settings = settings or get_settings()
    emit = progress or (lambda _msg: None)

    if not skip_poll:
        emit("polling feeds")
        discover_all(conn, registry, settings, only)

    since = datetime.now(timezone.utc) - timedelta(days=days)
    shows = registry.active()
    if only:
        only_set = set(only)
        shows = [s for s in shows if s.slug in only_set]

    outcomes: list[IngestOutcome] = []
    for show in shows:
        episodes = repo.list_episodes(conn, show_slug=show.slug, published_since=since)
        for ep in episodes:
            if ep.status == EpisodeStatus.TRANSCRIBED:
                continue
            assert ep.id is not None

            if ep.status in (EpisodeStatus.DISCOVERED, EpisodeStatus.FAILED):
                emit(f"acquiring {show.slug} ep {ep.id}")
                acquire_episode(conn, ep, show, settings)

            current = repo.get_episode(conn, ep.id)
            if current is None:
                continue

            if current.status == EpisodeStatus.TRANSCRIBED:
                outcomes.append(
                    IngestOutcome(ep.id, show.slug, ep.title, "official", "official transcript")
                )
            elif current.status == EpisodeStatus.ACQUIRED:
                emit(f"transcribing {show.slug} ep {ep.id}")
                result = transcribe_episode(
                    conn,
                    current,
                    show,
                    registry.glossary,
                    settings,
                    correct=correct,
                    identify=identify,
                )
                if result.ok:
                    outcomes.append(
                        IngestOutcome(ep.id, show.slug, ep.title, "transcribed", result.detail)
                    )
                else:
                    outcomes.append(
                        IngestOutcome(ep.id, show.slug, ep.title, "failed", error=result.error)
                    )
            else:
                outcomes.append(
                    IngestOutcome(
                        ep.id, show.slug, ep.title, "failed", error=current.error or "not acquired"
                    )
                )
    return outcomes


@dataclass
class RemapOutcome:
    episode_id: int
    show_slug: str
    speakers: list[str]


def remap_speakers(
    conn: sqlite3.Connection,
    registry: Registry,
    settings: Settings | None = None,
    *,
    only: Iterable[str] | None = None,
    only_placeholder: bool = True,
    limit: int | None = None,
    progress: Callable[[str], None] | None = None,
) -> list[RemapOutcome]:
    """Re-run speaker identification on stored ASR transcripts, reusing the saved
    diarization labels (no re-transcription). By default only re-maps episodes that
    still carry placeholder "Speaker X" names.
    """
    settings = settings or get_settings()
    emit = progress or (lambda _msg: None)
    from .transcribe.speakers import apply_speaker_names, identify_speakers

    show_by_slug = {s.slug: s for s in registry.shows}
    only_set = set(only) if only else None

    rows = conn.execute(
        """
        SELECT t.episode_id, t.normalized_path, t.corrected, e.show_slug
        FROM transcripts t JOIN episodes e ON e.id = t.episode_id
        WHERE t.source = 'asr' AND t.normalized_path IS NOT NULL
        ORDER BY t.episode_id DESC
        """
    ).fetchall()

    outcomes: list[RemapOutcome] = []
    for row in rows:
        if only_set and row["show_slug"] not in only_set:
            continue
        path = Path(row["normalized_path"])
        if not path.is_file():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        seg_data = data.get("segments", [])
        if not any(s.get("speaker_label") for s in seg_data):
            continue  # no diarization labels to re-map
        if only_placeholder and not any(
            (s.get("speaker_name") or "").startswith("Speaker ") for s in seg_data
        ):
            continue

        show = show_by_slug.get(row["show_slug"])
        episode = repo.get_episode(conn, row["episode_id"])
        if show is None or episode is None:
            continue

        parsed = ParsedTranscript(
            provider=data.get("provider", "assemblyai"),
            segments=[
                TranscriptSegment(
                    speaker_name=None,
                    speaker_label=s.get("speaker_label"),
                    text=s["text"],
                    start_ms=s.get("start_ms"),
                    end_ms=s.get("end_ms"),
                )
                for s in seg_data
            ],
            language=data.get("language", "en"),
            has_diarization=True,
            meta=data.get("meta"),
        )
        emit(f"remapping {show.slug} ep {episode.id}")
        mapping = identify_speakers(parsed, show, episode, settings)
        apply_speaker_names(parsed, mapping)
        persist_parsed_transcript(
            conn, episode, parsed, TranscriptSource.ASR, settings, corrected=bool(row["corrected"])
        )
        outcomes.append(
            RemapOutcome(
                episode.id,
                show.slug,
                sorted({s.speaker_name for s in parsed.segments if s.speaker_name}),
            )
        )
        if limit and len(outcomes) >= limit:
            break
    return outcomes
