"""Text documents as corpus episodes: SEC filings (shared, "print") and users'
own research uploads (private, "inside view").

A document becomes an episode whose transcript is its paragraphs, so the
standard pipeline (nugget extraction → thesis matching) runs on it unchanged.
Private documents carry episodes.owner_user_id: they are matched only against
their owner's questions and excluded from every shared listing.
"""

from __future__ import annotations

import io
import re
import sqlite3
from datetime import datetime, timezone

from .acquire.base import ParsedTranscript, TranscriptSegment
from .config import Settings, get_settings
from .pipeline import persist_parsed_transcript, process_episode_pipeline
from .registry import Show
from .store import repo
from .store.models import Episode, EpisodeStatus, TranscriptSource

# Extraction cost scales with length; long filings are trimmed to their core.
MAX_CHARS = 60_000

SEC_SHOW = Show(
    slug="sec-filings", name="SEC filings", tier="B",
    transcript_source="sec_edgar", format="filing", active=True,
)
RESEARCH_SHOW = Show(
    slug="research", name="Private research", tier="B",
    transcript_source="upload", format="research", active=True,
)


def paragraphs_from_text(text: str) -> list[str]:
    """Split plain text into paragraph-sized segments (blank-line separated;
    over-long blocks are split on sentence boundaries)."""
    text = text[:MAX_CHARS]
    blocks = [re.sub(r"\s+", " ", b).strip() for b in re.split(r"\n\s*\n", text)]
    out: list[str] = []
    for b in blocks:
        if len(b) < 2:
            continue
        while len(b) > 1500:
            cut = b.rfind(". ", 0, 1500)
            cut = cut + 1 if cut > 400 else 1500
            out.append(b[:cut].strip())
            b = b[cut:].strip()
        if b:
            out.append(b)
    return out


def text_from_pdf(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    return "\n\n".join((page.extract_text() or "") for page in reader.pages)


def create_document(
    conn: sqlite3.Connection,
    *,
    show: Show,
    guid: str,
    title: str,
    paragraphs: list[str],
    url: str | None = None,
    published_at: datetime | None = None,
    owner_user_id: int | None = None,
    settings: Settings | None = None,
) -> tuple[int, bool]:
    """Store a text document as a transcribed episode. Idempotent on (show, guid).

    Returns (episode_id, created)."""
    settings = settings or get_settings()
    if not conn.execute("SELECT 1 FROM shows WHERE slug = ?", (show.slug,)).fetchone():
        repo.sync_shows(conn, [show])
    existing = repo.get_episode_by_guid(conn, show.slug, guid)
    if existing is not None:
        return existing.id, False
    episode_id, _ = repo.upsert_episode(
        conn,
        Episode(
            show_slug=show.slug,
            guid=guid,
            title=title,
            episode_url=url,
            published_at=published_at or datetime.now(timezone.utc),
        ),
    )
    if owner_user_id is not None:
        conn.execute(
            "UPDATE episodes SET owner_user_id = ? WHERE id = ?", (owner_user_id, episode_id)
        )
        conn.commit()
    episode = repo.get_episode(conn, episode_id)
    parsed = ParsedTranscript(
        provider=show.transcript_source,
        segments=[TranscriptSegment(speaker_name=None, text=p) for p in paragraphs],
        has_diarization=False,
        source_url=url,
    )
    persist_parsed_transcript(conn, episode, parsed, TranscriptSource.OFFICIAL, settings)
    repo.set_status(conn, episode_id, EpisodeStatus.TRANSCRIBED)
    return episode_id, True


def process_document(conn: sqlite3.Connection, episode_id: int, settings: Settings | None = None) -> None:
    """Extract nuggets and match them (the standard pipeline from TRANSCRIBED on)."""
    process_episode_pipeline(conn, episode_id, settings or get_settings())
