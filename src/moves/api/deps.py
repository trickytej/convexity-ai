"""FastAPI dependencies."""

from __future__ import annotations

from collections.abc import Iterator

import duckdb
from fastapi import HTTPException

from moves.store.db import connect


def get_db() -> Iterator[duckdb.DuckDBPyConnection]:
    """One read-only DuckDB connection per request.

    DuckDB permits many concurrent read-only connections to a file. If a
    read-write process (e.g. ``moves ingest``) holds the file, opening fails and
    we surface a clear 503 rather than a raw error.
    """
    try:
        con = connect(read_only=True)
    except duckdb.Error as exc:  # store missing or locked by a writer
        raise HTTPException(
            status_code=503,
            detail="store unavailable (run `moves ingest` first, or stop a running ingest)",
        ) from exc
    try:
        yield con
    finally:
        con.close()
