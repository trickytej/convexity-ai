"""SQLite connection management and schema."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS shows (
    slug              TEXT PRIMARY KEY,
    name              TEXT NOT NULL,
    network           TEXT,
    rss_url           TEXT,
    homepage          TEXT,
    tier              TEXT NOT NULL,
    transcript_source TEXT NOT NULL,
    hosts             TEXT,                 -- json array
    format            TEXT,
    active            INTEGER NOT NULL DEFAULT 1,
    updated_at        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS episodes (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    show_slug        TEXT NOT NULL REFERENCES shows(slug) ON DELETE CASCADE,
    guid             TEXT NOT NULL,
    title            TEXT NOT NULL,
    published_at     TEXT,                  -- ISO-8601 UTC
    audio_url        TEXT,
    episode_url      TEXT,
    duration_seconds INTEGER,
    guests           TEXT,                  -- json array
    audio_path       TEXT,
    status           TEXT NOT NULL DEFAULT 'discovered',
    error            TEXT,
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL,
    UNIQUE(show_slug, guid)
);
CREATE INDEX IF NOT EXISTS idx_episodes_show ON episodes(show_slug);
CREATE INDEX IF NOT EXISTS idx_episodes_status ON episodes(status);
CREATE INDEX IF NOT EXISTS idx_episodes_published ON episodes(published_at);

CREATE TABLE IF NOT EXISTS transcripts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    episode_id      INTEGER NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
    source          TEXT NOT NULL,          -- official | asr
    provider        TEXT NOT NULL,          -- colossus | dwarkesh | assemblyai | ...
    language        TEXT,
    has_diarization INTEGER NOT NULL DEFAULT 0,
    corrected       INTEGER NOT NULL DEFAULT 0,
    word_count      INTEGER,
    raw_path        TEXT,
    normalized_path TEXT,
    meta            TEXT,                    -- json
    created_at      TEXT NOT NULL,
    UNIQUE(episode_id, source, provider)
);
CREATE INDEX IF NOT EXISTS idx_transcripts_episode ON transcripts(episode_id);

CREATE TABLE IF NOT EXISTS segments (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    transcript_id INTEGER NOT NULL REFERENCES transcripts(id) ON DELETE CASCADE,
    idx           INTEGER NOT NULL,
    speaker_label TEXT,
    speaker_name  TEXT,
    start_ms      INTEGER,
    end_ms        INTEGER,
    text          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_segments_transcript ON segments(transcript_id);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


@contextmanager
def get_conn(db_path: Path) -> Iterator[sqlite3.Connection]:
    conn = connect(db_path)
    try:
        yield conn
    finally:
        conn.close()
