"""'What Matters' theses: per-company key questions, matcher, and the daily Brief.

Everything here is scoped to the signed-in user (X-User-Id, see deps)."""

from __future__ import annotations

import json
import logging
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ...config import get_settings
from ...securities import resolve
from ...store import repo
from ...store.db import connect
from ...theses import build_brief, clean_drivers, draft_questions, run_brief_match
from ...transcribe.llm import LLMError
from ..deps import current_user_id, get_db

log = logging.getLogger(__name__)
router = APIRouter(tags=["theses"])

# In-process state for each user's most recent /brief/match background run
# (single uvicorn worker — same pattern as scout's _refresh_state).
_match_states: dict[int, dict] = {}

# How far back a question edit re-checks the corpus.
_RESEED_DAYS = 2


def _idle_state() -> dict:
    return {
        "status": "idle",  # idle | running | done | error
        "started_at": None,
        "finished_at": None,
        "users": 0,
        "episodes": 0,
        "nuggets_evaluated": 0,
        "hits": 0,
        "error": None,
    }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class DriverIn(BaseModel):
    line: str
    year: int | None = None


class QuestionIn(BaseModel):
    id: int | None = None
    question: str
    note: str | None = None
    drivers: list[DriverIn] = []


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
                "drivers": json.loads(r["drivers"]) if r["drivers"] else [],
                "position": r["position"],
                "active": bool(r["active"]),
            }
        )
    return sorted(by_company.values(), key=lambda c: c["company"].lower())


@router.get("/theses")
def get_theses(
    user_id: int = Depends(current_user_id), db: sqlite3.Connection = Depends(get_db)
) -> dict:
    """The user's active theses grouped by company."""
    return {"companies": _grouped_theses(repo.list_theses(db, user_id))}


@router.put("/theses")
def put_theses(
    body: CompanyThesesIn,
    background_tasks: BackgroundTasks,
    user_id: int = Depends(current_user_id),
    db: sqlite3.Connection = Depends(get_db),
) -> dict:
    """Save one company's ordered question set (array order = position).

    Questions carrying an id are edited in place (keeping their hit history);
    omitted existing questions are soft-deactivated. Saving follows the
    security and re-checks the last few days of nuggets against the new set.
    """
    company = body.company.strip()
    ticker = (body.ticker or "").strip() or None
    questions = [
        {**q.model_dump(), "drivers": clean_drivers([d.model_dump() for d in q.drivers])}
        for q in body.questions
    ]
    rows = repo.save_company_theses(db, user_id, company, ticker, questions)
    sec = resolve(db, company)
    repo.follow_security(db, user_id, company, ticker, sec["category"] if sec else None)
    if rows:
        since = (datetime.now(timezone.utc) - timedelta(days=_RESEED_DAYS)).isoformat()
        repo.reset_seen_window(db, user_id, since)
        _start_match(background_tasks, user_id, _RESEED_DAYS)
    return {"companies": _grouped_theses(rows)}


@router.post("/theses/draft")
def draft_theses(
    body: DraftIn,
    user_id: int = Depends(current_user_id),
    db: sqlite3.Connection = Depends(get_db),
) -> dict:
    """Propose 4-6 questions for a company from its recent nugget history."""
    try:
        questions = draft_questions(
            db, body.company.strip(), (body.ticker or "").strip() or None, get_settings(),
            user_id=user_id,
        )
    except LLMError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return {"questions": questions}


@router.get("/brief")
def get_brief(
    days: int = Query(7, ge=1, le=365),
    since: str | None = Query(None, description="ISO date/timestamp; overrides days"),
    until: str | None = Query(None, description="ISO date (inclusive) or timestamp"),
    min_relevance: float = Query(0.5, ge=0.0, le=1.0),
    status: str = Query("pending", pattern="^(pending|kept|dropped|all)$"),
    user_id: int = Depends(current_user_id),
    db: sqlite3.Connection = Depends(get_db),
) -> dict:
    """The daily Brief: the user's thesis hits in the window, grouped
    company → question. Defaults to undecided (pending) hits."""
    if since is None:
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    if until and len(until) == 10:  # a bare date includes that whole day
        until = (datetime.fromisoformat(until) + timedelta(days=1)).date().isoformat()
    return build_brief(
        db, user_id, since, until=until, min_relevance=min_relevance,
        decision=None if status == "all" else status,
    )


def _start_match(background_tasks: BackgroundTasks, user_id: int, days: int) -> bool:
    state = _match_states.setdefault(user_id, _idle_state())
    if state["status"] == "running":
        return False
    state.update(_idle_state(), status="running", started_at=_now_iso())

    def _run() -> None:
        settings = get_settings()
        conn = connect(settings.resolved_db_path)
        try:
            result = run_brief_match(conn, settings, days=days, user_id=user_id)
            state.update(status="done", finished_at=_now_iso(), **result)
        except Exception as exc:
            state.update(status="error", finished_at=_now_iso(), error=str(exc))
        finally:
            conn.close()

    background_tasks.add_task(_run)
    return True


@router.post("/brief/match")
def trigger_brief_match(
    background_tasks: BackgroundTasks,
    days: int = Query(2, ge=1, le=30),
    user_id: int = Depends(current_user_id),
) -> dict:
    """Run the catch-up matcher sweep for the user's questions in the background
    (idempotent via the seen ledger). Poll GET /brief/match/status for the outcome."""
    if not _start_match(background_tasks, user_id, days):
        return {"status": "already_running"}
    return {"status": "started"}


@router.get("/brief/match/status")
def brief_match_status(user_id: int = Depends(current_user_id)) -> dict:
    return _match_states.get(user_id) or _idle_state()
