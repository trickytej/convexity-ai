"""Repository functions: all SQL lives here."""

from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
from datetime import datetime, timezone

from ..registry import Show
from .models import Episode, EpisodeStatus, Nugget, Segment, Transcript


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
    clauses: list[str] = ["owner_user_id IS NULL"]  # private research never lists
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
    # libsql does not allow conn.commit() while any cursor from RETURNING is still
    # alive, so we split into an upsert + a plain SELECT to get the id.
    conn.execute(
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
    row = conn.execute(
        "SELECT id FROM transcripts WHERE episode_id = ? AND source = ? AND provider = ?",
        (t.episode_id, t.source.value, t.provider),
    ).fetchone()
    transcript_id = int(row[0])

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


def get_segments(conn: sqlite3.Connection, transcript_id: int) -> list[Segment]:
    rows = conn.execute(
        "SELECT * FROM segments WHERE transcript_id = ? ORDER BY idx ASC",
        (transcript_id,),
    ).fetchall()
    return [
        Segment(
            id=r["id"],
            transcript_id=r["transcript_id"],
            idx=r["idx"],
            speaker_label=r["speaker_label"],
            speaker_name=r["speaker_name"],
            start_ms=r["start_ms"],
            end_ms=r["end_ms"],
            text=r["text"],
        )
        for r in rows
    ]


# --- read helpers for the web API ----------------------------------------


def list_shows_with_counts(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT s.slug, s.name, s.network, s.homepage, s.hosts, s.tier, s.active,
               s.format,
               COUNT(e.id) AS total,
               SUM(CASE WHEN e.status IN ('transcribed', 'insights_extracted') THEN 1 ELSE 0 END) AS transcribed
        FROM shows s
        LEFT JOIN episodes e ON e.show_slug = s.slug AND e.owner_user_id IS NULL
        WHERE COALESCE(s.format, '') != 'research'
        GROUP BY s.slug
        ORDER BY s.active DESC, transcribed DESC, s.slug
        """
    ).fetchall()


def _browse_where(
    show_slug: str | None,
    published_since: datetime | None,
    with_transcript_only: bool,
    published_until: datetime | None = None,
) -> tuple[str, list[object]]:
    clauses: list[str] = ["e.owner_user_id IS NULL"]  # private research never lists
    params: list[object] = []
    if show_slug:
        clauses.append("e.show_slug = ?")
        params.append(show_slug)
    if published_since is not None:
        clauses.append("e.published_at >= ?")
        params.append(_dt_to_iso(published_since))
    if published_until is not None:
        clauses.append("e.published_at <= ?")
        params.append(_dt_to_iso(published_until))
    if with_transcript_only:
        clauses.append("EXISTS (SELECT 1 FROM transcripts t WHERE t.episode_id = e.id)")
    where = f"WHERE {' AND '.join(clauses)}"
    return where, params


def browse_episodes(
    conn: sqlite3.Connection,
    show_slug: str | None = None,
    published_since: datetime | None = None,
    published_until: datetime | None = None,
    with_transcript_only: bool = True,
    limit: int = 50,
    offset: int = 0,
) -> list[sqlite3.Row]:
    where, params = _browse_where(show_slug, published_since, with_transcript_only, published_until)
    sql = f"""
        SELECT e.*,
            (SELECT source FROM transcripts t WHERE t.episode_id = e.id
                ORDER BY id DESC LIMIT 1) AS transcript_source,
            (SELECT provider FROM transcripts t WHERE t.episode_id = e.id
                ORDER BY id DESC LIMIT 1) AS transcript_provider,
            (SELECT word_count FROM transcripts t WHERE t.episode_id = e.id
                ORDER BY id DESC LIMIT 1) AS word_count,
            (SELECT COUNT(*) FROM nuggets n WHERE n.episode_id = e.id) AS nugget_count
        FROM episodes e
        {where}
        ORDER BY e.published_at DESC, e.id DESC
        LIMIT ? OFFSET ?
    """
    return conn.execute(sql, [*params, limit, offset]).fetchall()


def count_episodes(
    conn: sqlite3.Connection,
    show_slug: str | None = None,
    published_since: datetime | None = None,
    published_until: datetime | None = None,
    with_transcript_only: bool = True,
) -> int:
    where, params = _browse_where(show_slug, published_since, with_transcript_only, published_until)
    row = conn.execute(f"SELECT COUNT(*) AS n FROM episodes e {where}", params).fetchone()
    return int(row["n"]) if row else 0


# --- reporting -----------------------------------------------------------


# --- nuggets -------------------------------------------------------------


def _row_to_nugget(row: sqlite3.Row) -> Nugget:
    return Nugget(
        id=row["id"],
        episode_id=row["episode_id"],
        type=row["type"],
        claim=row["claim"],
        quote=row["quote"],
        speaker_name=row["speaker_name"],
        start_ms=row["start_ms"],
        end_ms=row["end_ms"],
        entities=json.loads(row["entities"]) if row["entities"] else None,
        sectors=json.loads(row["sectors"]) if row["sectors"] else None,
        primary_sector=(row["primary_sector"] if "primary_sector" in row.keys() else None),
        scores=json.loads(row["scores"]) if row["scores"] else None,
        signal_score=row["signal_score"],
        quote_verified=bool(row["quote_verified"]),
        triage=row["triage"],
        model=row["model"],
    )


def get_nugget(conn: sqlite3.Connection, nugget_id: int) -> Nugget | None:
    row = conn.execute("SELECT * FROM nuggets WHERE id = ?", (nugget_id,)).fetchone()
    return _row_to_nugget(row) if row else None


def set_triage(conn: sqlite3.Connection, nugget_id: int, triage: str) -> bool:
    cur = conn.execute(
        "UPDATE nuggets SET triage = ? WHERE id = ?", (triage, nugget_id)
    )
    conn.commit()
    return cur.rowcount > 0


def has_nuggets(conn: sqlite3.Connection, episode_id: int) -> bool:
    row = conn.execute(
        "SELECT 1 FROM nuggets WHERE episode_id = ? LIMIT 1", (episode_id,)
    ).fetchone()
    return row is not None


def replace_nuggets(
    conn: sqlite3.Connection, episode_id: int, nuggets: list[Nugget]
) -> int:
    """Replace all nuggets for an episode (idempotent re-extraction).

    nugget_curation rows are NOT deleted here — they have no ON DELETE CASCADE
    and are intentionally orphaned so curator decisions survive re-extraction.
    Orphaned curation rows are excluded from live queries via INNER JOIN.
    """
    now = _now_iso()
    conn.execute("DELETE FROM nuggets WHERE episode_id = ?", (episode_id,))
    conn.executemany(
        """
        INSERT INTO nuggets (episode_id, type, claim, quote, speaker_name, start_ms,
                             end_ms, entities, sectors, primary_sector, scores,
                             signal_score, quote_verified, triage, model, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                episode_id,
                n.type,
                n.claim,
                n.quote,
                n.speaker_name,
                n.start_ms,
                n.end_ms,
                json.dumps(n.entities) if n.entities else None,
                json.dumps(n.sectors) if n.sectors else None,
                n.primary_sector,
                json.dumps(n.scores) if n.scores else None,
                n.signal_score,
                1 if n.quote_verified else 0,
                n.triage,
                n.model,
                now,
            )
            for n in nuggets
        ],
    )
    conn.commit()
    return len(nuggets)


def add_nugget(conn: sqlite3.Connection, n: Nugget) -> int:
    """Append one nugget without touching the episode's existing ones (unlike
    replace_nuggets). Used by Scout's tweet sync, which mints nuggets
    incrementally as new tweets arrive. Returns the new nugget id."""
    conn.execute(
        """
        INSERT INTO nuggets (episode_id, type, claim, quote, speaker_name, start_ms,
                             end_ms, entities, sectors, primary_sector, scores,
                             signal_score, quote_verified, triage, model, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            n.episode_id,
            n.type,
            n.claim,
            n.quote,
            n.speaker_name,
            n.start_ms,
            n.end_ms,
            json.dumps(n.entities) if n.entities else None,
            json.dumps(n.sectors) if n.sectors else None,
            n.primary_sector,
            json.dumps(n.scores) if n.scores else None,
            n.signal_score,
            1 if n.quote_verified else 0,
            n.triage,
            n.model,
            _now_iso(),
        ),
    )
    # libsql cursors don't expose lastrowid reliably; the sync task is the sole
    # writer for its episode, so the newest row is the one just inserted.
    row = conn.execute(
        "SELECT id FROM nuggets WHERE episode_id = ? ORDER BY id DESC LIMIT 1",
        (n.episode_id,),
    ).fetchone()
    return row["id"]


def nuggets_for_classification(
    conn: sqlite3.Connection, only_missing: bool = True
) -> list[sqlite3.Row]:
    where = "WHERE primary_sector IS NULL" if only_missing else ""
    return conn.execute(
        f"SELECT id, claim, quote FROM nuggets {where} ORDER BY id ASC"
    ).fetchall()


def set_primary_sector(conn: sqlite3.Connection, nugget_id: int, sector: str) -> None:
    conn.execute(
        "UPDATE nuggets SET primary_sector = ? WHERE id = ?", (sector, nugget_id)
    )


def list_nuggets(
    conn: sqlite3.Connection,
    episode_id: int | None = None,
    nugget_type: str | None = None,
    triage: str | None = None,
    min_signal: float | None = None,
    limit: int | None = None,
) -> list[Nugget]:
    clauses: list[str] = []
    params: list[object] = []
    if episode_id is not None:
        clauses.append("episode_id = ?")
        params.append(episode_id)
    if nugget_type:
        clauses.append("type = ?")
        params.append(nugget_type)
    if triage:
        clauses.append("triage = ?")
        params.append(triage)
    if min_signal is not None:
        clauses.append("signal_score >= ?")
        params.append(min_signal)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"SELECT * FROM nuggets {where} ORDER BY signal_score DESC, id ASC"
    if limit:
        sql += " LIMIT ?"
        params.append(limit)
    return [_row_to_nugget(r) for r in conn.execute(sql, params).fetchall()]


def nuggets_in_window(
    conn: sqlite3.Connection,
    since: datetime | None = None,
    until: datetime | None = None,
    min_signal: float = 0.0,
    include_tweets: bool = False,
) -> list[sqlite3.Row]:
    """Nuggets joined to their episode + show, for the weekly report.

    Show ``x`` holds verbatim tweets minted by Scout; they are excluded unless
    ``include_tweets``, and then only curator-kept ones qualify, windowed on
    the tweet's own post time (the per-handle episode's published_at is just
    the first sync date, so it can't be the window basis)."""
    clauses = ["s.active = 1", "e.owner_user_id IS NULL"]
    params: list[object] = []
    if include_tweets:
        joins = (
            "LEFT JOIN scout_tweets st ON st.nugget_id = n.id "
            "LEFT JOIN nugget_curation nc ON nc.nugget_id = n.id"
        )
        window_col = "COALESCE(st.created_at, e.published_at)"
        clauses.append("(e.show_slug != 'x' OR nc.decision = 'kept')")
    else:
        joins = ""
        window_col = "e.published_at"
        clauses.append("e.show_slug != 'x'")
    if since is not None:
        clauses.append(f"{window_col} >= ?")
        params.append(_dt_to_iso(since))
    if until is not None:
        clauses.append(f"{window_col} <= ?")
        params.append(_dt_to_iso(until))
    if min_signal:
        clauses.append("n.signal_score >= ?")
        params.append(min_signal)
    where = "WHERE " + " AND ".join(clauses)
    return conn.execute(
        f"""
        SELECT n.*, e.show_slug AS show_slug, e.title AS episode_title,
               e.published_at AS episode_published_at
        FROM nuggets n
        JOIN episodes e ON e.id = n.episode_id
        JOIN shows s ON s.slug = e.show_slug
        {joins}
        {where}
        ORDER BY n.signal_score DESC, n.id ASC
        """,
        params,
    ).fetchall()


def upsert_report(
    conn: sqlite3.Connection,
    week_key: str,
    since: str | None,
    until: str | None,
    days: int,
    source_mode: str,
    model: str,
    payload: dict,
) -> None:
    conn.execute(
        """
        INSERT INTO reports (week_key, since, until, days, source_mode, model,
                             payload, generated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(week_key) DO UPDATE SET
            since=excluded.since, until=excluded.until, days=excluded.days,
            source_mode=excluded.source_mode, model=excluded.model,
            payload=excluded.payload, generated_at=excluded.generated_at
        """,
        (
            week_key,
            since,
            until,
            days,
            source_mode,
            model,
            json.dumps(payload),
            _now_iso(),
        ),
    )
    conn.commit()


def get_latest_report(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM reports ORDER BY generated_at DESC LIMIT 1"
    ).fetchone()


def get_report_by_week(conn: sqlite3.Connection, week_key: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM reports WHERE week_key = ?", (week_key,)
    ).fetchone()


def upsert_episode_digest(
    conn: sqlite3.Connection, episode_id: int, model: str, payload: dict
) -> None:
    conn.execute(
        """
        INSERT INTO episode_digests (episode_id, model, payload, generated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(episode_id) DO UPDATE SET
            model=excluded.model, payload=excluded.payload, generated_at=excluded.generated_at
        """,
        (episode_id, model, json.dumps(payload), _now_iso()),
    )
    conn.commit()


def get_episode_digest(conn: sqlite3.Connection, episode_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM episode_digests WHERE episode_id = ?", (episode_id,)
    ).fetchone()


def list_digest_stocks_for_episodes(
    conn: sqlite3.Connection, episode_ids: list[int]
) -> list[dict]:
    """Return the LLM-generated stock entries from episode digests for the given episode IDs."""
    if not episode_ids:
        return []
    placeholders = ",".join("?" * len(episode_ids))
    rows = conn.execute(
        f"SELECT episode_id, payload FROM episode_digests WHERE episode_id IN ({placeholders})",
        episode_ids,
    ).fetchall()
    result: list[dict] = []
    for row in rows:
        try:
            payload = json.loads(row["payload"])
            for stock in payload.get("stocks", []):
                result.append(
                    {
                        "episode_id": row["episode_id"],
                        "company": stock.get("company", ""),
                        "stance": stock.get("stance", "mentioned"),
                        "summary": stock.get("summary", ""),
                        "sources": stock.get("sources", []),
                    }
                )
        except (json.JSONDecodeError, KeyError):
            continue
    return result


# --- curation ------------------------------------------------------------


def get_curation(conn: sqlite3.Connection, nugget_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM nugget_curation WHERE nugget_id = ?", (nugget_id,)
    ).fetchone()


def upsert_curation(
    conn: sqlite3.Connection,
    nugget_id: int,
    *,
    decision: str | None = None,
    curator_rank: int | None = None,
    contradicts_consensus: bool | None = None,
    note: str | None = None,
) -> sqlite3.Row:
    """Create or partial-update a curation record. Only supplied fields are written."""
    now = _now_iso()
    existing = get_curation(conn, nugget_id)
    if existing is None:
        conn.execute(
            """
            INSERT INTO nugget_curation
                (nugget_id, decision, curator_rank, contradicts_consensus, note, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                nugget_id,
                decision or "unreviewed",
                curator_rank,
                1 if contradicts_consensus else 0,
                note,
                now,
            ),
        )
    else:
        updates: dict[str, object] = {"updated_at": now}
        if decision is not None:
            updates["decision"] = decision
        if curator_rank is not None:
            updates["curator_rank"] = curator_rank
        if contradicts_consensus is not None:
            updates["contradicts_consensus"] = 1 if contradicts_consensus else 0
        if note is not None:
            updates["note"] = note
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        conn.execute(
            f"UPDATE nugget_curation SET {set_clause} WHERE nugget_id = ?",
            [*updates.values(), nugget_id],
        )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM nugget_curation WHERE nugget_id = ?", (nugget_id,)
    ).fetchone()
    assert row is not None
    return row


def list_nuggets_with_curation(
    conn: sqlite3.Connection, episode_id: int
) -> list[sqlite3.Row]:
    """All nuggets for an episode with their curation record LEFT-JOINed in."""
    return conn.execute(
        """
        SELECT n.*,
               nc.decision,
               nc.curator_rank,
               nc.contradicts_consensus,
               nc.note         AS curation_note,
               nc.updated_at   AS curation_updated_at
        FROM nuggets n
        LEFT JOIN nugget_curation nc ON nc.nugget_id = n.id
        WHERE n.episode_id = ?
        ORDER BY n.signal_score DESC, n.id ASC
        """,
        (episode_id,),
    ).fetchall()


def nugget_curation_stats(conn: sqlite3.Connection, episode_id: int) -> dict[str, int]:
    """Return counts: total, reviewed (not unreviewed), kept, killed."""
    rows = conn.execute(
        """
        SELECT
            COUNT(*)                                                   AS total,
            COUNT(nc.nugget_id)                                        AS has_curation,
            SUM(CASE WHEN nc.decision != 'unreviewed' THEN 1 ELSE 0 END) AS reviewed,
            SUM(CASE WHEN nc.decision = 'kept'        THEN 1 ELSE 0 END) AS kept,
            SUM(CASE WHEN nc.decision = 'killed'      THEN 1 ELSE 0 END) AS killed
        FROM nuggets n
        LEFT JOIN nugget_curation nc ON nc.nugget_id = n.id
        WHERE n.episode_id = ?
        """,
        (episode_id,),
    ).fetchone()
    return {
        "total": rows["total"] or 0,
        "reviewed": rows["reviewed"] or 0,
        "kept": rows["kept"] or 0,
        "killed": rows["killed"] or 0,
    }


# --- newsletter ----------------------------------------------------------


def list_kept_nuggets_for_newsletter(
    conn: sqlite3.Connection,
    from_iso: str | None = None,
    to_iso: str | None = None,
    episode_ids: list[int] | None = None,
    show_slug: str | None = None,
    exclude_show_slugs: list[str] | None = None,
) -> list[sqlite3.Row]:
    """Kept nuggets ordered rank ASC then signal DESC. All filters are optional."""
    clauses = ["nc.decision = 'kept'", "e.owner_user_id IS NULL"]
    params: list[object] = []
    if from_iso:
        clauses.append("e.published_at >= ?")
        params.append(from_iso)
    if to_iso:
        clauses.append("e.published_at <= ?")
        params.append(to_iso)
    if episode_ids:
        placeholders = ",".join("?" * len(episode_ids))
        clauses.append(f"n.episode_id IN ({placeholders})")
        params.extend(episode_ids)
    if show_slug:
        clauses.append("e.show_slug = ?")
        params.append(show_slug)
    if exclude_show_slugs:
        placeholders = ",".join("?" * len(exclude_show_slugs))
        clauses.append(f"e.show_slug NOT IN ({placeholders})")
        params.extend(exclude_show_slugs)
    where = " AND ".join(clauses)
    return conn.execute(
        f"""
        SELECT n.*,
               nc.decision, nc.curator_rank, nc.contradicts_consensus,
               nc.note         AS curation_note,
               e.show_slug     AS show_slug,
               e.title         AS episode_title,
               e.published_at  AS episode_published_at
        FROM nuggets n
        JOIN nugget_curation nc ON nc.nugget_id = n.id
        JOIN episodes e ON e.id = n.episode_id
        WHERE {where}
        ORDER BY nc.curator_rank ASC, n.signal_score DESC, n.id ASC
        """,
        params,
    ).fetchall()


def nugget_type_counts(conn: sqlite3.Connection, episode_id: int) -> dict[str, int]:
    rows = conn.execute(
        "SELECT type, COUNT(*) n FROM nuggets WHERE episode_id = ? GROUP BY type",
        (episode_id,),
    ).fetchall()
    return {r["type"]: r["n"] for r in rows}


_META_TABLE_SQL = "CREATE TABLE IF NOT EXISTS app_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"


def meta_get(conn: sqlite3.Connection, key: str) -> str | None:
    conn.execute(_META_TABLE_SQL)
    row = conn.execute("SELECT value FROM app_meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def meta_set(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(_META_TABLE_SQL)
    conn.execute(
        "INSERT INTO app_meta (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    conn.commit()


def status_matrix(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT s.slug AS slug, s.name AS name, s.tier AS tier, s.active AS active,
               COUNT(e.id) AS total,
               SUM(CASE WHEN e.status = 'discovered'  THEN 1 ELSE 0 END) AS discovered,
               SUM(CASE WHEN e.status = 'acquired'    THEN 1 ELSE 0 END) AS acquired,
               SUM(CASE WHEN e.status = 'transcribed'        THEN 1 ELSE 0 END) AS transcribed,
               SUM(CASE WHEN e.status = 'insights_extracted' THEN 1 ELSE 0 END) AS insights_extracted,
               SUM(CASE WHEN e.status = 'failed'             THEN 1 ELSE 0 END) AS failed
        FROM shows s
        LEFT JOIN episodes e ON e.show_slug = s.slug AND e.owner_user_id IS NULL
        WHERE COALESCE(s.format, '') != 'research'
        GROUP BY s.slug
        ORDER BY s.active DESC, s.tier, s.slug
        """
    ).fetchall()


# --- "What Matters" theses ------------------------------------------------


def list_theses(
    conn: sqlite3.Connection,
    user_id: int | None,
    company: str | None = None,
    include_inactive: bool = False,
) -> list[sqlite3.Row]:
    """user_id=None spans every user — matcher/internal use only, never an API path."""
    sql = "SELECT * FROM theses WHERE 1=1"
    params: list = []
    if user_id is not None:
        sql += " AND user_id = ?"
        params.append(user_id)
    if not include_inactive:
        sql += " AND active = 1"
    if company:
        sql += " AND company = ?"
        params.append(company)
    sql += " ORDER BY company, position, id"
    return conn.execute(sql, params).fetchall()


def save_company_theses(
    conn: sqlite3.Connection,
    user_id: int,
    company: str,
    ticker: str | None,
    questions: list[dict],
) -> list[sqlite3.Row]:
    """Diff-based save of one company's question set.

    *questions* is an ordered list of {"id"?: int, "question": str, "note"?: str,
    "drivers"?: [{"line": str, "year": int | None}]}.
    Rows with an id are updated in place (so editing a question's wording keeps
    its id and therefore its accumulated thesis_hits); rows without are inserted;
    the company's active rows whose ids are absent from the payload are
    soft-deactivated, never deleted. Everything is scoped to *user_id*.
    """
    now = _now_iso()
    keep_ids: set[int] = set()
    for pos, q in enumerate(questions):
        text = (q.get("question") or "").strip()
        if not text:
            continue
        note = (q.get("note") or "").strip() or None
        drivers = json.dumps(q["drivers"]) if q.get("drivers") else None
        qid = q.get("id")
        if qid is not None:
            cur = conn.execute(
                "UPDATE theses SET question = ?, note = ?, drivers = ?, position = ?, ticker = ?, "
                "active = 1, updated_at = ? WHERE id = ? AND company = ? AND user_id = ?",
                (text, note, drivers, pos, ticker, now, qid, company, user_id),
            )
            if cur.rowcount:
                keep_ids.add(int(qid))
                continue
        cur = conn.execute(
            "INSERT INTO theses (user_id, company, ticker, question, note, drivers, position, "
            "active, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)",
            (user_id, company, ticker, text, note, drivers, pos, now, now),
        )
        keep_ids.add(int(cur.lastrowid))
    if keep_ids:
        placeholders = ",".join("?" * len(keep_ids))
        conn.execute(
            f"UPDATE theses SET active = 0, updated_at = ? "
            f"WHERE company = ? AND user_id = ? AND active = 1 AND id NOT IN ({placeholders})",
            (now, company, user_id, *keep_ids),
        )
    else:
        conn.execute(
            "UPDATE theses SET active = 0, updated_at = ? "
            "WHERE company = ? AND user_id = ? AND active = 1",
            (now, company, user_id),
        )
    conn.commit()
    return list_theses(conn, user_id, company=company)


def record_thesis_hits(conn: sqlite3.Connection, hits: list[dict]) -> int:
    """UPSERT matcher hits keyed on (question_id, claim_hash) — re-running the
    matcher after a re-extraction heals the stale nugget_id instead of duplicating."""
    now = _now_iso()
    conn.executemany(
        """
        INSERT INTO thesis_hits (question_id, nugget_id, episode_id, claim_hash,
                                 relevance, direction, why, model, matched_at,
                                 evidence, tier, impact_line, impact_year, impact_dir)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(question_id, claim_hash) DO UPDATE SET
            nugget_id = excluded.nugget_id,
            relevance = excluded.relevance,
            direction = excluded.direction,
            why = excluded.why,
            model = excluded.model,
            matched_at = excluded.matched_at,
            evidence = excluded.evidence,
            tier = excluded.tier,
            impact_line = excluded.impact_line,
            impact_year = excluded.impact_year,
            impact_dir = excluded.impact_dir
        """,
        [
            (
                h["question_id"], h["nugget_id"], h["episode_id"], h["claim_hash"],
                h["relevance"], h["direction"], h.get("why"), h.get("model"), now,
                h.get("evidence"), h.get("tier", "reference"),
                h.get("impact_line"), h.get("impact_year"), h.get("impact_dir"),
            )
            for h in hits
        ],
    )
    conn.commit()
    return len(hits)


def mark_nuggets_seen(
    conn: sqlite3.Connection, user_id: int, pairs: list[tuple[int, int]]
) -> None:
    """pairs = [(nugget_id, episode_id)] — records that the matcher evaluated them
    against *user_id*'s questions."""
    now = _now_iso()
    conn.executemany(
        "INSERT OR IGNORE INTO thesis_match_seen (user_id, nugget_id, episode_id, matched_at) "
        "VALUES (?, ?, ?, ?)",
        [(user_id, nid, eid, now) for nid, eid in pairs],
    )
    conn.commit()


def demote_hits_since(conn: sqlite3.Connection, user_id: int, since: str) -> None:
    """Before a full re-grade: mark the user's hits on recent nuggets as reference,
    so hits the stricter matcher no longer returns don't keep a stale signal tier."""
    conn.execute(
        "UPDATE thesis_hits SET tier = 'reference' WHERE question_id IN "
        "(SELECT id FROM theses WHERE user_id = ?) AND nugget_id IN "
        "(SELECT id FROM nuggets WHERE created_at >= ?)",
        (user_id, since),
    )
    conn.commit()


def reset_seen_window(conn: sqlite3.Connection, user_id: int, since: str) -> None:
    """Forget which recent nuggets were evaluated for *user_id*, so the next sweep
    re-checks them against new/edited questions. Safe: hits UPSERT."""
    conn.execute(
        "DELETE FROM thesis_match_seen WHERE user_id = ? AND nugget_id IN "
        "(SELECT id FROM nuggets WHERE created_at >= ?)",
        (user_id, since),
    )
    conn.commit()


def unseen_nuggets(
    conn: sqlite3.Connection,
    user_id: int,
    episode_id: int | None = None,
    created_since: str | None = None,
) -> list[sqlite3.Row]:
    """Nuggets the thesis matcher has not yet evaluated for *user_id*: the shared
    corpus plus the user's own private research (never anyone else's)."""
    sql = """
        SELECT n.*, e.show_slug, e.title AS episode_title
        FROM nuggets n
        JOIN episodes e ON e.id = n.episode_id
        LEFT JOIN thesis_match_seen s ON s.nugget_id = n.id AND s.user_id = ?
        WHERE s.nugget_id IS NULL
          AND (e.owner_user_id IS NULL OR e.owner_user_id = ?)
    """
    params: list = [user_id, user_id]
    if episode_id is not None:
        sql += " AND n.episode_id = ?"
        params.append(episode_id)
    if created_since is not None:
        sql += " AND n.created_at >= ?"
        params.append(created_since)
    sql += " ORDER BY n.episode_id, n.id"
    return conn.execute(sql, params).fetchall()


# Windows are on when the *source* was published (tweet time for X posts), not
# when the matcher ran — a re-grade must not make old evidence look new.
_PUBLISHED = "COALESCE(st.created_at, e.published_at, h.matched_at)"


def thesis_hits_since(
    conn: sqlite3.Connection,
    user_id: int,
    since: str | None,
    until: str | None = None,
    min_relevance: float = 0.5,
    decision: str | None = None,
    company: str | None = None,
    exclude_dropped: bool = False,
) -> list[sqlite3.Row]:
    """Brief query: hits in the window with question, nugget, episode, and (for
    X posts) tweet context. INNER JOIN on nuggets drops hits orphaned by a
    re-extraction until the matcher re-runs and heals them."""
    sql = """
        SELECT h.id AS hit_id, h.relevance, h.direction, h.why, h.matched_at,
               h.decision, h.decided_at, h.evidence, h.tier,
               h.impact_line, h.impact_year, h.impact_dir,
               s.format AS show_format, e.owner_user_id,
               t.id AS question_id, t.company, t.ticker, t.question,
               t.note AS question_note, t.position,
               n.id AS nugget_id, n.claim, n.quote, n.speaker_name, n.start_ms,
               n.signal_score, n.type AS nugget_type,
               e.id AS episode_id, e.show_slug, e.title AS episode_title,
               e.published_at,
               st.url AS tweet_url, st.created_at AS tweet_created_at
        FROM thesis_hits h
        JOIN theses t   ON t.id = h.question_id
        JOIN nuggets n  ON n.id = h.nugget_id
        JOIN episodes e ON e.id = n.episode_id
        LEFT JOIN shows s ON s.slug = e.show_slug
        LEFT JOIN scout_tweets st ON st.nugget_id = n.id
        WHERE t.user_id = ? AND h.relevance >= ? AND t.active = 1
    """
    params: list = [user_id, min_relevance]
    if since is not None:
        sql += f" AND {_PUBLISHED} >= ?"
        params.append(since)
    if decision is not None:
        sql += " AND h.decision = ?"
        params.append(decision)
    if company is not None:
        sql += " AND t.company = ?"
        params.append(company)
    if exclude_dropped:
        sql += " AND h.decision != 'dropped'"
    if until is not None:
        sql += f" AND {_PUBLISHED} < ?"
        params.append(until)
    sql += " ORDER BY t.company, t.position, h.relevance DESC"
    return conn.execute(sql, params).fetchall()


def set_hit_decision(
    conn: sqlite3.Connection, user_id: int, hit_id: int, decision: str
) -> bool:
    """Keep/drop a hit. Only the owner of the hit's question may decide it."""
    cur = conn.execute(
        "UPDATE thesis_hits SET decision = ?, decided_at = ? WHERE id = ? AND question_id IN "
        "(SELECT id FROM theses WHERE user_id = ?)",
        (decision, _now_iso() if decision != "pending" else None, hit_id, user_id),
    )
    conn.commit()
    return bool(cur.rowcount)


def list_users_with_active_theses(conn: sqlite3.Connection) -> list[int]:
    rows = conn.execute(
        "SELECT DISTINCT user_id FROM theses WHERE active = 1 AND user_id IS NOT NULL"
    ).fetchall()
    return [r["user_id"] for r in rows]


# --- Users ------------------------------------------------------------------


def upsert_user(
    conn: sqlite3.Connection,
    email: str,
    name: str | None = None,
    image: str | None = None,
    provider: str | None = None,
    provider_account_id: str | None = None,
) -> sqlite3.Row:
    """Sign-in upsert keyed by email (the owner row is pre-seeded by the migration).

    UPDATE-then-INSERT rather than INSERT … ON CONFLICT, which would burn an
    AUTOINCREMENT id on every sign-in."""
    now = _now_iso()
    email = email.strip()
    cur = conn.execute(
        """
        UPDATE users SET
            name = COALESCE(?, name),
            image = COALESCE(?, image),
            provider = COALESCE(?, provider),
            provider_account_id = COALESCE(?, provider_account_id),
            last_login_at = ?
        WHERE email = ?
        """,
        (name, image, provider, provider_account_id, now, email),
    )
    if not cur.rowcount:
        conn.execute(
            "INSERT INTO users (email, name, image, provider, provider_account_id, "
            "created_at, last_login_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (email, name, image, provider, provider_account_id, now, now),
        )
    conn.commit()
    return conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()


def get_user(conn: sqlite3.Connection, user_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def list_user_securities(conn: sqlite3.Connection, user_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM user_securities WHERE user_id = ? ORDER BY company", (user_id,)
    ).fetchall()


def follow_security(
    conn: sqlite3.Connection,
    user_id: int,
    company: str,
    ticker: str | None,
    category: str | None,
) -> None:
    conn.execute(
        "INSERT INTO user_securities (user_id, company, ticker, category, added_at) "
        "VALUES (?, ?, ?, ?, ?) ON CONFLICT(user_id, company) DO UPDATE SET "
        "ticker = excluded.ticker, category = COALESCE(excluded.category, user_securities.category)",
        (user_id, company, ticker, category, _now_iso()),
    )
    conn.commit()


def unfollow_security(conn: sqlite3.Connection, user_id: int, company: str) -> None:
    conn.execute(
        "DELETE FROM user_securities WHERE user_id = ? AND company = ?", (user_id, company)
    )
    conn.commit()


# --- Personal API tokens ------------------------------------------------------


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_api_token(conn: sqlite3.Connection, user_id: int, name: str) -> tuple[int, str]:
    """Mint a token; returns (id, plaintext). Only the hash is stored."""
    token = "cvx_" + secrets.token_urlsafe(32)
    cur = conn.execute(
        "INSERT INTO api_tokens (user_id, name, token_hash, prefix, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (user_id, name, _token_hash(token), token[:10], _now_iso()),
    )
    conn.commit()
    return int(cur.lastrowid), token


def user_for_token(conn: sqlite3.Connection, token: str) -> int | None:
    row = conn.execute(
        "SELECT id, user_id FROM api_tokens WHERE token_hash = ?", (_token_hash(token),)
    ).fetchone()
    if not row:
        return None
    conn.execute("UPDATE api_tokens SET last_used_at = ? WHERE id = ?", (_now_iso(), row["id"]))
    conn.commit()
    return int(row["user_id"])


def list_api_tokens(conn: sqlite3.Connection, user_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT id, name, prefix, created_at, last_used_at FROM api_tokens "
        "WHERE user_id = ? ORDER BY id DESC",
        (user_id,),
    ).fetchall()


def delete_api_token(conn: sqlite3.Connection, user_id: int, token_id: int) -> bool:
    cur = conn.execute("DELETE FROM api_tokens WHERE id = ? AND user_id = ?", (token_id, user_id))
    conn.commit()
    return bool(cur.rowcount)


# --- Private research ("inside view") -------------------------------------------


def list_research(conn: sqlite3.Connection, user_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT e.id, e.title, e.episode_url AS url, e.status, e.error, e.created_at,
               (SELECT COUNT(*) FROM nuggets n WHERE n.episode_id = e.id) AS nugget_count,
               (SELECT COUNT(*) FROM thesis_hits h WHERE h.episode_id = e.id AND h.tier = 'signal')
                   AS signal_count,
               (SELECT COUNT(*) FROM thesis_hits h WHERE h.episode_id = e.id) AS hit_count
        FROM episodes e
        WHERE e.owner_user_id = ?
        ORDER BY e.id DESC
        """,
        (user_id,),
    ).fetchall()


def delete_research(conn: sqlite3.Connection, user_id: int, episode_id: int) -> bool:
    """Delete one of the user's documents with its nuggets and thesis hits."""
    if not conn.execute(
        "SELECT 1 FROM episodes WHERE id = ? AND owner_user_id = ?", (episode_id, user_id)
    ).fetchone():
        return False
    conn.execute("DELETE FROM thesis_hits WHERE episode_id = ?", (episode_id,))
    conn.execute("DELETE FROM thesis_match_seen WHERE episode_id = ?", (episode_id,))
    conn.execute("DELETE FROM nuggets WHERE episode_id = ?", (episode_id,))
    conn.execute("DELETE FROM episodes WHERE id = ?", (episode_id,))
    conn.commit()
    return True
