"""'What Matters' theses: per-company key questions, matcher, and the daily Brief."""

from __future__ import annotations

import logging
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ...config import get_settings
from ...store import repo
from ...store.db import connect
from ...theses import build_brief, draft_questions, run_brief_match
from ...transcribe.llm import LLMError
from ..deps import get_db

log = logging.getLogger(__name__)
router = APIRouter(tags=["theses"])

# In-process state for the most recent /brief/match background run (single
# uvicorn worker — same pattern as scout's _refresh_state).
_match_state: dict = {
    "status": "idle",  # idle | running | done | error
    "started_at": None,
    "finished_at": None,
    "episodes": 0,
    "nuggets_evaluated": 0,
    "hits": 0,
    "error": None,
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class QuestionIn(BaseModel):
    id: int | None = None
    question: str
    note: str | None = None


class CompanyThesesIn(BaseModel):
    company: str = Field(min_length=1)
    ticker: str | None = None
    questions: list[QuestionIn]


class DraftIn(BaseModel):
    company: str = Field(min_length=1)
    ticker: str | None = None


def _grouped_theses(rows: list[sqlite3.Row]) -> list[dict]:
    by_company: dict[str, dict] = defaultdict(lambda: {"questions": []})
    for r in rows:
        c = by_company[r["company"]]
        c["company"] = r["company"]
        c["ticker"] = r["ticker"]
        c["questions"].append(
            {
                "id": r["id"],
                "question": r["question"],
                "note": r["note"],
                "position": r["position"],
                "active": bool(r["active"]),
            }
        )
    return sorted(by_company.values(), key=lambda c: c["company"].lower())


@router.get("/theses")
def get_theses(db: sqlite3.Connection = Depends(get_db)) -> dict:
    """All active theses grouped by company."""
    return {"companies": _grouped_theses(repo.list_theses(db))}


@router.put("/theses")
def put_theses(body: CompanyThesesIn, db: sqlite3.Connection = Depends(get_db)) -> dict:
    """Save one company's ordered question set (array order = position).

    Questions carrying an id are edited in place (keeping their hit history);
    omitted existing questions are soft-deactivated.
    """
    rows = repo.save_company_theses(
        db, body.company.strip(), (body.ticker or "").strip() or None,
        [q.model_dump() for q in body.questions],
    )
    return {"companies": _grouped_theses(rows)}


@router.post("/theses/draft")
def draft_theses(body: DraftIn, db: sqlite3.Connection = Depends(get_db)) -> dict:
    """Propose 4-6 questions for a company from its recent nugget history."""
    try:
        questions = draft_questions(
            db, body.company.strip(), (body.ticker or "").strip() or None, get_settings()
        )
    except LLMError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return {"questions": questions}


@router.get("/brief")
def get_brief(
    days: int = Query(1, ge=1, le=30),
    since: str | None = Query(None, description="ISO timestamp; overrides days"),
    min_relevance: float = Query(0.5, ge=0.0, le=1.0),
    db: sqlite3.Connection = Depends(get_db),
) -> dict:
    """The morning Brief: thesis hits in the window, grouped company → question."""
    if since is None:
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    return build_brief(db, since, min_relevance=min_relevance)


@router.post("/brief/match")
def trigger_brief_match(
    background_tasks: BackgroundTasks,
    days: int = Query(2, ge=1, le=30),
) -> dict:
    """Run the catch-up matcher sweep in the background (idempotent via the
    seen ledger). Poll GET /brief/match/status for the outcome."""
    if _match_state["status"] == "running":
        return {"status": "already_running"}

    _match_state.update(
        status="running", started_at=_now_iso(), finished_at=None,
        episodes=0, nuggets_evaluated=0, hits=0, error=None,
    )

    def _run() -> None:
        settings = get_settings()
        conn = connect(settings.resolved_db_path)
        try:
            result = run_brief_match(conn, settings, days=days)
            _match_state.update(status="done", finished_at=_now_iso(), **result)
        except Exception as exc:
            _match_state.update(status="error", finished_at=_now_iso(), error=str(exc))
        finally:
            conn.close()

    background_tasks.add_task(_run)
    return {"status": "started"}


@router.get("/brief/match/status")
def brief_match_status() -> dict:
    return _match_state
