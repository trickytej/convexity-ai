"""Scout detection cycle: search Podscan by founder/C-suite name."""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone

from typing import Callable

from ..acquire.base import ParsedTranscript, TranscriptSegment
from ..config import Settings
from ..pipeline import persist_parsed_transcript, process_episode_pipeline
from ..registry import Show
from ..store import repo
from ..store.models import Episode, EpisodeStatus, TranscriptSource
from .sources import PodscanAuthError, PodscanRateLimitError, search_episodes

log = logging.getLogger(__name__)

SCOUT_SHOW_SLUG = "scout"
_SCOUT_SHOW = Show(
    slug=SCOUT_SHOW_SLUG,
    name="Scout",
    tier="B",
    transcript_source="asr",
    active=True,
)

# Podscan transcript line format:
# [HH:MM:SS.mmm --> HH:MM:SS.mmm] [SPEAKER_XX] text...
_LINE_RE = re.compile(
    r"^\[(\d{2}:\d{2}:\d{2}\.\d+)\s*-->\s*(\d{2}:\d{2}:\d{2}\.\d+)\]\s*"
    r"(?:\[(\w+)\]\s*)?(.+)$"
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ts_ms(ts: str) -> int:
    h, m, s = ts.split(":")
    return int((int(h) * 3600 + int(m) * 60 + float(s)) * 1000)


def _parse_podscan_transcript(text: str) -> list[TranscriptSegment]:
    segments = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        m = _LINE_RE.match(line)
        if not m:
            continue
        segments.append(
            TranscriptSegment(
                speaker_name=None,
                start_ms=_ts_ms(m.group(1)),
                end_ms=_ts_ms(m.group(2)),
                speaker_label=m.group(3),
                text=m.group(4).strip(),
            )
        )
    return segments


def ingest_appearance_row(
    conn: sqlite3.Connection, row: sqlite3.Row, settings: Settings
) -> tuple[int, bool]:
    """Create (or find) the episode backing a Scout appearance and, if Podscan
    provided a transcript inline, persist it (skipping AssemblyAI entirely).

    Returns (episode_id, created). Idempotent: safe to call again once
    ``row["episode_id"]`` is set — returns it immediately.
    """
    if row["episode_id"]:
        return row["episode_id"], False

    audio_url = row["audio_url"] or row["episode_url"] or ""
    episode_url = row["episode_url"] or ""
    if not audio_url:
        raise ValueError("No audio URL available for this appearance")

    if not conn.execute("SELECT slug FROM shows WHERE slug = ?", (SCOUT_SHOW_SLUG,)).fetchone():
        repo.sync_shows(conn, [_SCOUT_SHOW])

    # Idempotent on audio_url
    existing = conn.execute(
        "SELECT id FROM episodes WHERE audio_url = ? AND show_slug = ?",
        (audio_url, SCOUT_SHOW_SLUG),
    ).fetchone()
    if existing:
        episode_id = existing["id"]
        conn.execute(
            "UPDATE scout_appearances SET episode_id = ? WHERE id = ?",
            (episode_id, row["id"]),
        )
        conn.commit()
        return episode_id, False

    pub_at = None
    if row["published_at"]:
        try:
            pub_at = datetime.fromisoformat(row["published_at"])
        except ValueError:
            pass

    ep = Episode(
        show_slug=SCOUT_SHOW_SLUG,
        guid=audio_url,
        title=row["episode_title"],
        audio_url=audio_url,
        episode_url=episode_url,
        published_at=pub_at,
    )
    episode_id, _ = repo.upsert_episode(conn, ep)

    # Store Podscan transcript directly if available — skips AssemblyAI entirely.
    transcript_text = row["transcript"] if "transcript" in row.keys() else None
    if transcript_text:
        segments = _parse_podscan_transcript(transcript_text)
        ep.id = episode_id
        parsed = ParsedTranscript(
            provider="podscan",
            segments=segments,
            has_diarization=True,
            source_url=episode_url or audio_url,
        )
        persist_parsed_transcript(conn, ep, parsed, TranscriptSource.ASR, settings)
        repo.set_status(conn, episode_id, EpisodeStatus.TRANSCRIBED)

    conn.execute(
        "UPDATE scout_appearances SET episode_id = ? WHERE id = ?",
        (episode_id, row["id"]),
    )
    conn.commit()
    return episode_id, True


@dataclass
class ScoutResult:
    new: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
    aborted: bool = False                # cycle stopped early (auth / quota) — not a full pass
    quota_reset_at: str | None = None    # ISO time the Podscan quota resets, when we hit it
    processed: int = 0                   # appearances that ran through ingest+process
    processing_total: int = 0            # appearances that were pending ingest+process
    rows: list[dict] = field(default_factory=list)  # per-appearance detail: episode_id/title/status


def run_cycle(conn, roster: list[tuple[str, str, str]], *, days: int = 7) -> ScoutResult:
    """Search Podscan for every (company, person_name, person_role) triple in
    *roster* and persist confirmed appearances.

    Podscan's ``has_guests=true`` filter already limits results to actual guest
    appearances, so no additional regex filtering is needed here.
    """
    result = ScoutResult()

    for company_name, person_name, person_role in roster:
        try:
            episodes = search_episodes(person_name, days=days)
        except PodscanAuthError as exc:
            result.errors.append(str(exc))
            result.aborted = True
            log.error("aborting scout cycle: %s", exc)
            conn.commit()  # keep appearances found before the abort
            return result
        except PodscanRateLimitError as exc:
            result.errors.append(str(exc))
            result.aborted = True
            if exc.reset_at is not None:
                result.quota_reset_at = exc.reset_at.isoformat()
            log.error("aborting scout cycle: %s", exc)
            conn.commit()
            return result

        for ep in episodes:
            podscan_id = ep.get("podscan_id") or ""
            if not podscan_id:
                continue

            try:
                cur = conn.execute(
                    """
                    INSERT OR IGNORE INTO scout_appearances
                        (listennotes_id, company, person_name, person_role,
                         episode_title, podcast_name,
                         episode_url, audio_url, thumbnail, description,
                         published_at, duration_seconds, transcript, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        podscan_id,
                        company_name,
                        person_name,
                        person_role,
                        ep["title"],
                        ep["podcast_name"],
                        ep["episode_url"],
                        ep["audio_url"],
                        ep["thumbnail"],
                        ep["description"],
                        ep["published_at"],
                        ep["duration"],
                        ep["transcript"],
                        _now_iso(),
                    ),
                )
                if cur.rowcount and cur.rowcount > 0:
                    result.new += 1
                    log.info(
                        "new appearance: %s — %s (%s)",
                        person_name,
                        ep["title"][:60],
                        ep["podcast_name"],
                    )
                else:
                    result.skipped += 1
            except Exception as exc:
                result.errors.append(f"{person_name}: {exc}")
                log.warning("insert failed for %s: %s", person_name, exc)

    conn.commit()
    return result


def sync_and_process(
    conn,
    settings: Settings,
    roster: list[tuple[str, str, str]],
    *,
    days: int = 7,
    scope_sweep_to_days: bool = False,
    on_progress: Callable[[int, int], None] | None = None,
) -> ScoutResult:
    """Search Podscan (``run_cycle``), then ingest + transcribe + extract
    insights for every appearance still missing an episode — the same loop the
    ``scout-sync`` CLI command runs, shared here so the interactive Refresh
    button gets the identical end-to-end behavior.

    Runs the ingest+process sweep even if the search itself aborted (auth/quota
    exhausted) — there may already be appearances discovered by an earlier run
    that are still waiting to be transcribed, and those shouldn't get stuck
    just because today's search couldn't run.

    By default the sweep covers every pending appearance ever discovered
    (unbounded by *days*), which is what lets the nightly ``scout-sync`` job
    gradually clear the whole backlog. Pass ``scope_sweep_to_days=True`` (used
    by the interactive Refresh button) to limit it to appearances published
    within the *days* window, so a Refresh for "last 7 days" doesn't also kick
    off processing on a large unrelated historical backlog.
    """
    result = run_cycle(conn, roster, days=days)

    if scope_sweep_to_days:
        rows = conn.execute(
            "SELECT * FROM scout_appearances WHERE episode_id IS NULL "
            "AND (published_at IS NULL OR published_at >= datetime('now', ?))",
            (f"-{days} days",),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM scout_appearances WHERE episode_id IS NULL").fetchall()
    result.processing_total = len(rows)

    for i, row in enumerate(rows, start=1):
        try:
            episode_id, _ = ingest_appearance_row(conn, row, settings)
            process_episode_pipeline(conn, episode_id, settings)
            ep = repo.get_episode(conn, episode_id)
            result.rows.append({
                "episode_id": episode_id,
                "title": row["episode_title"],
                "status": ep.status.value if ep else "unknown",
            })
            result.processed += 1
        except Exception as exc:
            result.rows.append({"episode_id": None, "title": row["episode_title"], "status": "failed"})
            result.errors.append(f"{row['episode_title']}: {exc}")
            log.warning("ingest/process failed for appearance %s: %s", row["id"], exc)
        if on_progress:
            on_progress(i, result.processing_total)

    return result
