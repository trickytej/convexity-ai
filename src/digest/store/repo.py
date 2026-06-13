"""Repository functions: all SQL lives here."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from ..registry import Show
from .models import Episode, EpisodeStatus, Segment, Transcript


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dt_to_iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _iso_to_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _json_list(value: list[str] | None) -> str | None:
    return json.dumps(value) if value else None


def _parse_json_list(value: str | None) -> list[str] | None:
    if not value:
        return None
    try:
        data = json.loads(value)
        return data if isinstance(data, list) else None
    except json.JSONDecodeError:
        return None


# --- shows ---------------------------------------------------------------


def sync_shows(conn: sqlite3.Connection, shows: list[Show]) -> int:
    now = _now_iso()
    rows = [
        (
            s.slug,
            s.name,
            s.network,
            s.rss_url,
            s.homepage,
            s.tier,
            s.transcript_source,
            json.dumps(s.hosts),
            s.format,
            1 if s.active else 0,
            now,
        )
        for s in shows
    ]
    conn.executemany(
        """
        INSERT INTO shows (slug, name, network, rss_url, homepage, tier,
                           transcript_source, hosts, format, active, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(slug) DO UPDATE SET
            name=excluded.name,
            network=excluded.network,
            rss_url=excluded.rss_url,
            homepage=excluded.homepage,
            tier=excluded.tier,
            transcript_source=excluded.transcript_source,
            hosts=excluded.hosts,
            format=excluded.format,
            active=excluded.active,
            updated_at=excluded.updated_at
        """,
        rows,
    )
    conn.commit()
    return len(rows)


# --- episodes ------------------------------------------------------------


def _row_to_episode(row: sqlite3.Row) -> Episode:
    return Episode(
        id=row["id"],
        show_slug=row["show_slug"],
        guid=row["guid"],
        title=row["title"],
        published_at=_iso_to_dt(row["published_at"]),
        audio_url=row["audio_url"],
        episode_url=row["episode_url"],
        duration_seconds=row["duration_seconds"],
        guests=_parse_json_list(row["guests"]),
        audio_path=row["audio_path"],
        status=EpisodeStatus(row["status"]),
        error=row["error"],
    )


def get_episode_by_guid(
    conn: sqlite3.Connection, show_slug: str, guid: str
) -> Episode | None:
    row = conn.execute(
        "SELECT * FROM episodes WHERE show_slug = ? AND guid = ?",
        (show_slug, guid),
    ).fetchone()
    return _row_to_episode(row) if row else None


def get_episode(conn: sqlite3.Connection, episode_id: int) -> Episode | None:
    row = conn.execute("SELECT * FROM episodes WHERE id = ?", (episode_id,)).fetchone()
    return _row_to_episode(row) if row else None


def upsert_episode(conn: sqlite3.Connection, ep: Episode) -> tuple[int, bool]:
    """Insert a newly discovered episode, or refresh metadata if it exists.

    Returns ``(episode_id, created)``.
    """
    existing = get_episode_by_guid(conn, ep.show_slug, ep.guid)
    now = _now_iso()
    if existing is not None:
        conn.execute(
            """
            UPDATE episodes SET
                title = ?,
                published_at = COALESCE(?, published_at),
                audio_url = COALESCE(?, audio_url),
                episode_url = COALESCE(?, episode_url),
                duration_seconds = COALESCE(?, duration_seconds),
                guests = COALESCE(?, guests),
                updated_at = ?
            WHERE id = ?
            """,
            (
                ep.title,
                _dt_to_iso(ep.published_at),
                ep.audio_url,
                ep.episode_url,
                ep.duration_seconds,
                _json_list(ep.guests),
                now,
                existing.id,
            ),
        )
        conn.commit()
        return int(existing.id), False  # type: ignore[arg-type]

    cur = conn.execute(
        """
        INSERT INTO episodes (show_slug, guid, title, published_at, audio_url,
                              episode_url, duration_seconds, guests, audio_path,
                              status, error, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            ep.show_slug,
            ep.guid,
            ep.title,
            _dt_to_iso(ep.published_at),
            ep.audio_url,
            ep.episode_url,
            ep.duration_seconds,
            _json_list(ep.guests),
            ep.audio_path,
            ep.status.value,
            ep.error,
            now,
            now,
        ),
    )
    conn.commit()
    return int(cur.lastrowid), True  # type: ignore[arg-type]


def set_status(
    conn: sqlite3.Connection,
    episode_id: int,
    status: EpisodeStatus,
    error: str | None = None,
) -> None:
    conn.execute(
        "UPDATE episodes SET status = ?, error = ?, updated_at = ? WHERE id = ?",
        (status.value, error, _now_iso(), episode_id),
    )
    conn.commit()


def set_audio_path(conn: sqlite3.Connection, episode_id: int, audio_path: str) -> None:
    conn.execute(
        "UPDATE episodes SET audio_path = ?, updated_at = ? WHERE id = ?",
        (audio_path, _now_iso(), episode_id),
    )
    conn.commit()


def list_episodes(
    conn: sqlite3.Connection,
    show_slug: str | None = None,
    status: EpisodeStatus | None = None,
    limit: int | None = None,
    published_since: datetime | None = None,
) -> list[Episode]:
    clauses: list[str] = []
    params: list[object] = []
    if show_slug:
        clauses.append("show_slug = ?")
        params.append(show_slug)
    if status:
        clauses.append("status = ?")
        params.append(status.value)
    if published_since is not None:
        clauses.append("published_at >= ?")
        params.append(_dt_to_iso(published_since))
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"SELECT * FROM episodes {where} ORDER BY published_at DESC, id DESC"
    if limit:
        sql += " LIMIT ?"
        params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    return [_row_to_episode(r) for r in rows]


# --- transcripts ---------------------------------------------------------


def insert_transcript(conn: sqlite3.Connection, t: Transcript) -> int:
    cur = conn.execute(
        """
        INSERT INTO transcripts (episode_id, source, provider, language,
                                 has_diarization, corrected, word_count,
                                 raw_path, normalized_path, meta, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(episode_id, source, provider) DO UPDATE SET
            language=excluded.language,
            has_diarization=excluded.has_diarization,
            corrected=excluded.corrected,
            word_count=excluded.word_count,
            raw_path=excluded.raw_path,
            normalized_path=excluded.normalized_path,
            meta=excluded.meta
        RETURNING id
        """,
        (
            t.episode_id,
            t.source.value,
            t.provider,
            t.language,
            1 if t.has_diarization else 0,
            1 if t.corrected else 0,
            t.word_count,
            t.raw_path,
            t.normalized_path,
            json.dumps(t.meta) if t.meta else None,
            _now_iso(),
        ),
    )
    transcript_id = int(cur.fetchone()[0])

    # Replace any existing segments for an idempotent re-run.
    conn.execute("DELETE FROM segments WHERE transcript_id = ?", (transcript_id,))
    if t.segments:
        conn.executemany(
            """
            INSERT INTO segments (transcript_id, idx, speaker_label, speaker_name,
                                  start_ms, end_ms, text)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    transcript_id,
                    seg.idx,
                    seg.speaker_label,
                    seg.speaker_name,
                    seg.start_ms,
                    seg.end_ms,
                    seg.text,
                )
                for seg in t.segments
            ],
        )
    conn.commit()
    return transcript_id


def get_transcript_for_episode(
    conn: sqlite3.Connection, episode_id: int
) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM transcripts WHERE episode_id = ? ORDER BY id DESC LIMIT 1",
        (episode_id,),
    ).fetchone()


# --- reporting -----------------------------------------------------------


def status_matrix(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT s.slug AS slug, s.name AS name, s.tier AS tier, s.active AS active,
               COUNT(e.id) AS total,
               SUM(CASE WHEN e.status = 'discovered'  THEN 1 ELSE 0 END) AS discovered,
               SUM(CASE WHEN e.status = 'acquired'    THEN 1 ELSE 0 END) AS acquired,
               SUM(CASE WHEN e.status = 'transcribed' THEN 1 ELSE 0 END) AS transcribed,
               SUM(CASE WHEN e.status = 'failed'      THEN 1 ELSE 0 END) AS failed
        FROM shows s
        LEFT JOIN episodes e ON e.show_slug = s.slug
        GROUP BY s.slug
        ORDER BY s.active DESC, s.tier, s.slug
        """
    ).fetchall()
