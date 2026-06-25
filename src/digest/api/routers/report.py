"""Step 6: the synthesized weekly report (generate + fetch latest)."""

from __future__ import annotations

import json
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query

from ...store import repo
from ...synthesis import generate_report
from ...transcribe.llm import LLMError
from ..deps import get_db

router = APIRouter(tags=["report"])


def _row_to_report(row: sqlite3.Row) -> dict:
    payload = json.loads(row["payload"])
    return {
        "week_key": row["week_key"],
        "since": row["since"],
        "until": row["until"],
        "days": row["days"],
        "generated_at": row["generated_at"],
        **payload,
    }


@router.post("/report/generate")
def generate(
    days: int = Query(7, ge=1, le=90),
    since: str | None = Query(None),
    until: str | None = Query(None),
    db: sqlite3.Connection = Depends(get_db),
) -> dict:
    try:
        return generate_report(db, days=days, since_iso=since, until_iso=until)
    except LLMError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/report/latest")
def latest(db: sqlite3.Connection = Depends(get_db)) -> dict | None:
    row = repo.get_latest_report(db)
    return _row_to_report(row) if row else None
