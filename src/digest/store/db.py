"""Database connection + schema.

Local dev uses a libSQL file on disk; production points at Turso (hosted libSQL)
via TURSO_DATABASE_URL / TURSO_AUTH_TOKEN. A thin wrapper restores sqlite3.Row-style
access (``row["col"]``, ``row.keys()``) on top of libsql's positional-tuple rows, so
the rest of the codebase keeps working unchanged.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import libsql

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

CREATE TABLE IF NOT EXISTS nuggets (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    episode_id    INTEGER NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
    type          TEXT NOT NULL,
    claim         TEXT NOT NULL,
    quote         TEXT,
    speaker_name  TEXT,
    start_ms      INTEGER,
    end_ms        INTEGER,
    entities      TEXT,                  -- json {companies, people, tickers}
    sectors       TEXT,                  -- json array of cross-cutting tags (incl. AI)
    primary_sector TEXT,                 -- controlled vertical for grouping
    scores        TEXT,                  -- json {specificity, novelty, ...}
    signal_score  REAL NOT NULL DEFAULT 0,
    quote_verified INTEGER NOT NULL DEFAULT 0,
    triage        TEXT NOT NULL DEFAULT 'pending',  -- pending | relevant | not_relevant
    model         TEXT,
    created_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_nuggets_episode ON nuggets(episode_id);
CREATE INDEX IF NOT EXISTS idx_nuggets_signal ON nuggets(signal_score);
CREATE INDEX IF NOT EXISTS idx_nuggets_type ON nuggets(type);
CREATE INDEX IF NOT EXISTS idx_nuggets_triage ON nuggets(triage);

CREATE TABLE IF NOT EXISTS reports (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    week_key     TEXT NOT NULL UNIQUE,   -- e.g. 2026-W24
    since        TEXT,
    until        TEXT,
    days         INTEGER,
    source_mode  TEXT,                   -- relevant | top_signal
    model        TEXT,
    payload      TEXT NOT NULL,          -- json: exec_summary, sections, top_entities, stats
    generated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_reports_week ON reports(week_key);

CREATE TABLE IF NOT EXISTS episode_digests (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    episode_id   INTEGER NOT NULL UNIQUE REFERENCES episodes(id) ON DELETE CASCADE,
    model        TEXT,
    payload      TEXT NOT NULL,          -- json: themes, stocks
    generated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS nugget_curation (
    nugget_id             INTEGER PRIMARY KEY,
    -- Intentionally NO "REFERENCES nuggets(id) ON DELETE CASCADE": curator decisions
    -- must survive nugget re-extraction (which deletes + reinserts with new ids).
    -- Rows whose nugget_id no longer exists in nuggets are orphans; queries exclude
    -- them via INNER JOIN.  See replace_nuggets() in repo.py.
    decision              TEXT NOT NULL DEFAULT 'unreviewed',  -- unreviewed | kept | killed
    curator_rank          INTEGER,                             -- 1 | 2 | 3
    contradicts_consensus INTEGER NOT NULL DEFAULT 0,
    note                  TEXT,
    updated_at            TEXT NOT NULL
);
"""


# --- sqlite3.Row compatibility shim over libsql ---------------------------------
#
# libsql (0.1.x) returns positional tuples and exposes no row_factory. This codebase
# relies on sqlite3.Row semantics (row["col"], row[idx], row.keys()). We rebuild that
# from the cursor's ``description`` so no query code has to change.


class Row:
    """Mapping/sequence hybrid mirroring the bits of sqlite3.Row we use."""

    __slots__ = ("_keys", "_vals", "_index")

    def __init__(self, keys: tuple[str, ...], vals: tuple[Any, ...]) -> None:
        self._keys = keys
        self._vals = vals
        self._index: dict[str, int] | None = None

    def _idx(self) -> dict[str, int]:
        if self._index is None:
            self._index = {k: i for i, k in enumerate(self._keys)}
        return self._index

    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, str):
            return self._vals[self._idx()[key]]
        return self._vals[key]

    def keys(self) -> list[str]:
        return list(self._keys)

    def get(self, key: str, default: Any = None) -> Any:
        i = self._idx().get(key)
        return self._vals[i] if i is not None else default

    def __contains__(self, key: str) -> bool:
        return key in self._idx()

    def __iter__(self) -> Iterator[Any]:
        return iter(self._vals)

    def __len__(self) -> int:
        return len(self._vals)

    def __repr__(self) -> str:
        body = ", ".join(f"{k}={v!r}" for k, v in zip(self._keys, self._vals))
        return f"Row({body})"


class _Cursor:
    def __init__(self, conn: "_Conn", raw: Any) -> None:
        self._conn = conn
        self._raw = raw

    def _colkeys(self) -> tuple[str, ...]:
        desc = self._raw.description if self._raw is not None else None
        return tuple(c[0] for c in desc) if desc else ()

    def execute(self, sql: str, params: Any = None) -> "_Cursor":
        self._raw = self._conn._exec_raw(sql, params)
        return self

    def executemany(self, sql: str, seq: Any) -> "_Cursor":
        self._conn._raw.executemany(sql, list(seq))
        self._raw = None
        return self

    def fetchone(self) -> Row | None:
        if self._raw is None:
            return None
        v = self._raw.fetchone()
        return None if v is None else Row(self._colkeys(), tuple(v))

    def fetchall(self) -> list[Row]:
        if self._raw is None:
            return []
        keys = self._colkeys()
        return [Row(keys, tuple(v)) for v in self._raw.fetchall()]

    def fetchmany(self, size: int | None = None) -> list[Row]:
        if self._raw is None:
            return []
        keys = self._colkeys()
        rows = self._raw.fetchmany(size) if size is not None else self._raw.fetchmany()
        return [Row(keys, tuple(v)) for v in rows]

    def __iter__(self) -> Iterator[Row]:
        return iter(self.fetchall())

    @property
    def description(self) -> Any:
        return self._raw.description if self._raw is not None else None

    @property
    def lastrowid(self) -> Any:
        return getattr(self._raw, "lastrowid", None)

    @property
    def rowcount(self) -> int:
        return getattr(self._raw, "rowcount", -1)


class _Conn:
    """sqlite3.Connection-shaped wrapper around a libsql connection."""

    def __init__(self, raw: Any) -> None:
        self._raw = raw
        self.row_factory: Any = None  # accepted but ignored — rows are always Row

    def _exec_raw(self, sql: str, params: Any) -> Any:
        if params is None:
            return self._raw.execute(sql)
        return self._raw.execute(sql, params)

    def execute(self, sql: str, params: Any = None) -> _Cursor:
        return _Cursor(self, self._exec_raw(sql, params))

    def executemany(self, sql: str, seq: Any) -> _Cursor:
        self._raw.executemany(sql, list(seq))
        return _Cursor(self, None)

    def executescript(self, script: str) -> _Cursor:
        self._raw.executescript(script)
        return _Cursor(self, None)

    def cursor(self) -> _Cursor:
        return _Cursor(self, None)

    def commit(self) -> None:
        self._raw.commit()

    def rollback(self) -> None:
        try:
            self._raw.rollback()
        except Exception:
            pass

    def close(self) -> None:
        try:
            self._raw.close()
        except Exception:
            pass

    def __enter__(self) -> "_Conn":
        return self

    def __exit__(self, exc_type: Any, *_: Any) -> bool:
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        return False


def _turso_target() -> tuple[str | None, str | None]:
    url = os.environ.get("TURSO_DATABASE_URL") or os.environ.get("LIBSQL_URL")
    token = os.environ.get("TURSO_AUTH_TOKEN") or os.environ.get("LIBSQL_AUTH_TOKEN")
    return (url or None), (token or None)


def connect(db_path: Path) -> _Conn:
    """Open a connection. Remote (Turso) when env is set, else a local libSQL file."""
    url, token = _turso_target()
    if url:
        raw = libsql.connect(database=url, auth_token=token)
        conn = _Conn(raw)
    else:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        raw = libsql.connect(str(db_path))
        conn = _Conn(raw)
        # Local-file pragmas (no-ops / unsupported on remote, so only set here).
        for pragma in ("PRAGMA journal_mode = WAL;", "PRAGMA busy_timeout = 5000;"):
            try:
                conn.execute(pragma)
            except Exception:
                pass
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
    except Exception:
        pass
    return conn


def _migrate(conn: _Conn) -> None:
    """Idempotent column additions for existing databases."""
    nugget_cols = {row[1] for row in conn.execute("PRAGMA table_info(nuggets)").fetchall()}
    if "primary_sector" not in nugget_cols:
        conn.execute("ALTER TABLE nuggets ADD COLUMN primary_sector TEXT")

    show_cols = {row[1] for row in conn.execute("PRAGMA table_info(shows)").fetchall()}
    if "format" not in show_cols:
        conn.execute("ALTER TABLE shows ADD COLUMN format TEXT")

    conn.commit()


def init_db(conn: _Conn) -> None:
    conn.executescript(SCHEMA)
    _migrate(conn)
    conn.commit()


@contextmanager
def get_conn(db_path: Path) -> Iterator[_Conn]:
    conn = connect(db_path)
    try:
        yield conn
    finally:
        conn.close()
