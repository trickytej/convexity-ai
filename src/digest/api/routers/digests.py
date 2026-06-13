"""Per-episode digest (TMTB-style): generate + fetch."""

from __future__ import annotations

import json
import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from ...store import repo
from ...synthesis import generate_episode_digest
from ...transcribe.llm import LLMError
from ..deps import get_db

router = APIRouter(tags=["digests"])


def _row_to_digest(row: sqlite3.Row) -> dict:
    return {"generated_at": row["generated_at"], **json.loads(row["payload"])}


@router.get("/episodes/{episode_id}/digest")
def get_digest(episode_id: int, db: sqlite3.Connection = Depends(get_db)) -> dict | None:
    row = repo.get_episode_digest(db, episode_id)
    return _row_to_digest(row) if row else None


@router.post("/episodes/{episode_id}/digest")
def make_digest(episode_id: int, db: sqlite3.Connection = Depends(get_db)) -> dict:
    try:
        return generate_episode_digest(db, episode_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except LLMError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
