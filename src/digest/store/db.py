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

CREATE TABLE IF NOT EXISTS scout_appearances (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    listennotes_id  TEXT UNIQUE NOT NULL,
    company         TEXT NOT NULL,
    episode_title   TEXT NOT NULL,
    podcast_name    TEXT NOT NULL,
    episode_url     TEXT,
    audio_url       TEXT,
    thumbnail       TEXT,
    description     TEXT,
    published_at    TEXT,
    created_at      TEXT NOT NULL,
    -- Soft delete: the row must survive so INSERT OR IGNORE (unique
    -- listennotes_id) keeps the next Podscan scan from resurrecting it.
    dismissed       INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_scout_company   ON scout_appearances(company);
CREATE INDEX IF NOT EXISTS idx_scout_published ON scout_appearances(published_at DESC);

CREATE TABLE IF NOT EXISTS scout_tweets (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    tweet_id    TEXT UNIQUE NOT NULL,
    handle      TEXT NOT NULL,               -- X username, no @
    author_name TEXT,
    text        TEXT NOT NULL,
    url         TEXT,
    created_at  TEXT,                        -- tweet publish time, ISO-8601 UTC
    metrics     TEXT,                        -- json public_metrics
    episode_id  INTEGER,                     -- per-handle episode bucketing the nuggets
    nugget_id   INTEGER,                     -- the keep/kill nugget minted for this tweet
    fetched_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_scout_tweets_handle  ON scout_tweets(handle);
CREATE INDEX IF NOT EXISTS idx_scout_tweets_created ON scout_tweets(created_at DESC);

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


def _is_stale_stream_error(exc: Exception) -> bool:
    """True when the remote (Hrana) stream backing this connection has been
    reaped server-side — Turso closes streams that idle for a few minutes,
    which long pipelines hit whenever they wait on external APIs between
    queries. The connection object is unusable; only a reconnect recovers."""
    msg = str(exc).lower()
    return "stream not found" in msg or "stream expired" in msg


class _Conn:
    """sqlite3.Connection-shaped wrapper around a libsql connection."""

    def __init__(self, raw: Any, reconnect: Any = None) -> None:
        self._raw = raw
        self._reconnect = reconnect  # () -> raw connection, for stale-stream recovery
        self.row_factory: Any = None  # accepted but ignored — rows are always Row

    def _recover(self) -> None:
        try:
            self._raw.close()
        except Exception:
            pass
        self._raw = self._reconnect()
        try:
            self._raw.execute("PRAGMA foreign_keys = ON;")
        except Exception:
            pass

    def _exec_raw(self, sql: str, params: Any) -> Any:
        try:
            if params is None:
                return self._raw.execute(sql)
            return self._raw.execute(sql, params)
        except Exception as exc:
            if self._reconnect is None or not _is_stale_stream_error(exc):
                raise
            self._recover()
            if params is None:
                return self._raw.execute(sql)
            return self._raw.execute(sql, params)

    def execute(self, sql: str, params: Any = None) -> _Cursor:
        return _Cursor(self, self._exec_raw(sql, params))

    def executemany(self, sql: str, seq: Any) -> _Cursor:
        rows = list(seq)
        try:
            self._raw.executemany(sql, rows)
        except Exception as exc:
            if self._reconnect is None or not _is_stale_stream_error(exc):
                raise
            self._recover()
            self._raw.executemany(sql, rows)
        return _Cursor(self, None)

    def executescript(self, script: str) -> _Cursor:
        try:
            self._raw.executescript(script)
        except Exception as exc:
            if self._reconnect is None or not _is_stale_stream_error(exc):
                raise
            self._recover()
            self._raw.executescript(script)
        return _Cursor(self, None)

    def cursor(self) -> _Cursor:
        return _Cursor(self, None)

    def commit(self) -> None:
        try:
            self._raw.commit()
        except Exception as exc:
            if self._reconnect is None or not _is_stale_stream_error(exc):
                raise
            # The stream died with this transaction's statements on it — they
            # are gone server-side and cannot be committed. Recover the
            # connection so subsequent work proceeds, then surface the loss.
            self._recover()
            raise

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


class TursoNotConfiguredError(RuntimeError):
    """Raised when a Turso-only code path runs without Turso credentials."""


def connect_turso(settings) -> _Conn:
    """Open a connection to the hosted (Turso) database, never a local file.

    Scout uses this for every read and write so appearance data always lands in
    the production database, regardless of what the rest of the process is
    pointed at. Credentials come from Settings (env vars or .env).
    """
    url = getattr(settings, "turso_database_url", None)
    token = getattr(settings, "turso_auth_token", None)
    if not url or not token:
        raise TursoNotConfiguredError(
            "Scout requires the hosted database: set TURSO_DATABASE_URL and "
            "TURSO_AUTH_TOKEN (env or .env)."
        )
    def _open():  # fresh raw connection, reused for stale-stream recovery
        return libsql.connect(database=url, auth_token=token)

    conn = _Conn(_open(), reconnect=_open)
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
    except Exception:
        pass
    return conn


def connect(db_path: Path) -> _Conn:
    """Open a connection. Remote (Turso) when env is set, else a local libSQL file."""
    url, token = _turso_target()
    if url:
        def _open():  # fresh raw connection, reused for stale-stream recovery
            return libsql.connect(database=url, auth_token=token)

        conn = _Conn(_open(), reconnect=_open)
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

    scout_cols = {row[1] for row in conn.execute("PRAGMA table_info(scout_appearances)").fetchall()}
    if "person_name" not in scout_cols:
        conn.execute("ALTER TABLE scout_appearances ADD COLUMN person_name TEXT")
    if "person_role" not in scout_cols:
        conn.execute("ALTER TABLE scout_appearances ADD COLUMN person_role TEXT")
    if "episode_id" not in scout_cols:
        conn.execute("ALTER TABLE scout_appearances ADD COLUMN episode_id INTEGER")
    if "duration_seconds" not in scout_cols:
        conn.execute("ALTER TABLE scout_appearances ADD COLUMN duration_seconds INTEGER")
    if "transcript" not in scout_cols:
        conn.execute("ALTER TABLE scout_appearances ADD COLUMN transcript TEXT")
    if "dismissed" not in scout_cols:
        conn.execute("ALTER TABLE scout_appearances ADD COLUMN dismissed INTEGER NOT NULL DEFAULT 0")

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
