"""Accounts, followed securities, the per-security Model payload, and keep/drop."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone

import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from ...finmodel import parse_canalyst
from ...model import build_model, save_base, save_user_model
from ...securities import resolve, security_key, universe
from ...store import repo
from ...theses import build_brief, question_statuses
from ..deps import current_user_id, get_db, require_admin

router = APIRouter(tags=["users"])

_RECENT_HIT_DAYS = 14
_FEED_DAYS = 90


class UpsertUserIn(BaseModel):
    email: str = Field(min_length=3)
    name: str | None = None
    image: str | None = None
    provider: str | None = None
    provider_account_id: str | None = None


class FollowIn(BaseModel):
    company: str = Field(min_length=1)


class ModelNumbersIn(BaseModel):
    overrides: dict[str, float | None] = {}  # "gm@Q3-2027" -> value; null clears
    target_pe: float | None = None
    price: float | None = None  # manual share price override


class DecisionIn(BaseModel):
    decision: str = Field(pattern="^(pending|kept|dropped)$")


def _user_out(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "email": row["email"],
        "name": row["name"],
        "image": row["image"],
        "is_admin": bool(row["is_admin"]),
    }


@router.post("/auth/upsert-user")
def upsert_user(body: UpsertUserIn, db: sqlite3.Connection = Depends(get_db)) -> dict:
    """Called by the frontend's Auth.js callback on sign-in (API key only)."""
    row = repo.upsert_user(
        db, body.email, body.name, body.image, body.provider, body.provider_account_id
    )
    return _user_out(row)


@router.get("/me")
def me(user_id: int = Depends(current_user_id), db: sqlite3.Connection = Depends(get_db)) -> dict:
    row = repo.get_user(db, user_id)
    if not row:
        raise HTTPException(status_code=401, detail="unknown user")
    return _user_out(row)


@router.get("/securities/universe")
def get_universe(
    user_id: int = Depends(current_user_id), db: sqlite3.Connection = Depends(get_db)
) -> dict:
    """Every followable security by category, flagged with the user's follows."""
    followed = {r["company"] for r in repo.list_user_securities(db, user_id)}
    question_counts: dict[str, int] = {}
    for t in repo.list_theses(db, user_id):
        question_counts[t["company"]] = question_counts.get(t["company"], 0) + 1
    categories = universe(db)
    for category in categories:
        for c in category["companies"]:
            c["followed"] = c["company"] in followed
            c["question_count"] = question_counts.get(c["company"], 0)
    return {"categories": categories}


@router.put("/me/securities")
def follow(
    body: FollowIn,
    user_id: int = Depends(current_user_id),
    db: sqlite3.Connection = Depends(get_db),
) -> dict:
    sec = resolve(db, body.company)
    if not sec:
        raise HTTPException(status_code=404, detail="not in the security universe")
    repo.follow_security(db, user_id, sec["company"], sec["ticker"], sec["category"])
    # First follow: start from ConvexityAI's default questions (and their evidence).
    adopted = 0
    if not repo.has_any_theses(db, user_id, sec["company"]):
        adopted = repo.adopt_house_questions(db, user_id, sec["company"])
    return {"followed": True, "adopted_questions": adopted, **sec}


@router.delete("/me/securities/{company}")
def unfollow(
    company: str,
    user_id: int = Depends(current_user_id),
    db: sqlite3.Connection = Depends(get_db),
) -> dict:
    """Unfollow keeps the user's questions and hits (re-following restores them)."""
    repo.unfollow_security(db, user_id, company)
    return {"followed": False, "company": company}


@router.get("/model/{key}")
def get_model(
    key: str,
    user_id: int = Depends(current_user_id),
    db: sqlite3.Connection = Depends(get_db),
) -> dict:
    """One security's page: its What Matters questions, recent undecided hits,
    and the kept-hit tracker."""
    sec = resolve(db, key)
    if not sec:
        raise HTTPException(status_code=404, detail="unknown security")
    company = sec["company"]
    followed = any(r["company"] == company for r in repo.list_user_securities(db, user_id))
    statuses = question_statuses(db, user_id, company=company)
    questions = [
        {
            "id": t["id"],
            "question": t["question"],
            "note": t["note"],
            "drivers": json.loads(t["drivers"]) if t["drivers"] else [],
            "position": t["position"],
            "status": statuses.get(t["id"], {}).get("status", "none"),
            "signals": statuses.get(t["id"], {}).get("signals", 0),
            "references": statuses.get(t["id"], {}).get("references", 0),
        }
        for t in repo.list_theses(db, user_id, company=company)
    ]
    since = (datetime.now(timezone.utc) - timedelta(days=_RECENT_HIT_DAYS)).isoformat()
    pending = build_brief(db, user_id, since, decision="pending", company=company)
    kept = build_brief(db, user_id, None, decision="kept", company=company)

    def _questions(brief: dict) -> list[dict]:
        return brief["companies"][0]["questions"] if brief["companies"] else []

    # The page's nugget feed: every non-dropped development on the user's
    # questions in the window (signals and reference, pending and kept),
    # newest first, each tagged with its question.
    feed_since = (datetime.now(timezone.utc) - timedelta(days=_FEED_DAYS)).isoformat()
    feed = [
        {**h, "question_id": q["question_id"], "question": q["question"]}
        for q in _questions(build_brief(db, user_id, feed_since, decision=None, company=company))
        for h in q["hits"]
        if h["decision"] != "dropped"
    ]
    feed.sort(key=lambda h: h["nugget"]["published_at"] or h["matched_at"], reverse=True)
    house = repo.house_user_id(db)
    house_rows = repo.list_theses(db, house, company=company) if house else []

    return {
        **sec,
        "key": security_key(company, sec["ticker"]),
        "followed": followed,
        "questions": questions,
        "pending": _questions(pending),
        "kept": _questions(kept),
        "feed": feed,
        "house_questions": [
            {"id": t["id"], "question": t["question"], "note": t["note"],
             "drivers": json.loads(t["drivers"]) if t["drivers"] else [], "position": t["position"]}
            for t in house_rows
        ],
        "numbers": build_model(db, user_id, company, sec["ticker"]),
    }


@router.post("/model/{key}/adopt-house")
def adopt_house(
    key: str, user_id: int = Depends(current_user_id), db: sqlite3.Connection = Depends(get_db)
) -> dict:
    """Replace the user's questions for this security with ConvexityAI's defaults
    (and the evidence already matched to them)."""
    sec = resolve(db, key)
    if not sec:
        raise HTTPException(status_code=404, detail="unknown security")
    repo.follow_security(db, user_id, sec["company"], sec["ticker"], sec["category"])
    return {"adopted_questions": repo.adopt_house_questions(db, user_id, sec["company"])}


@router.put("/model/{key}/numbers")
def put_model_numbers(
    key: str,
    body: ModelNumbersIn,
    user_id: int = Depends(current_user_id),
    db: sqlite3.Connection = Depends(get_db),
) -> dict:
    """Save the user's overrides (null = back to consensus) and target multiple."""
    sec = resolve(db, key)
    if not sec:
        raise HTTPException(status_code=404, detail="unknown security")
    save_user_model(db, user_id, sec["company"], body.overrides, body.target_pe, body.price)
    return build_model(db, user_id, sec["company"], sec["ticker"])


@router.post("/model/{key}/import", dependencies=[Depends(require_admin)])
async def import_model(
    key: str, file: UploadFile = File(...), db: sqlite3.Connection = Depends(get_db)
) -> dict:
    """Load a Canalyst-format .xlsx as this security's shared base model."""
    sec = resolve(db, key)
    if not sec:
        raise HTTPException(status_code=404, detail="unknown security")
    with tempfile.NamedTemporaryFile(suffix=".xlsx") as tmp:
        tmp.write(await file.read())
        tmp.flush()
        try:
            base = parse_canalyst(Path(tmp.name))
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"could not read model: {exc}")
    base["file"] = file.filename
    save_base(db, sec["company"], sec["ticker"], base)
    return {"company": sec["company"], "periods": len(base["periods"]), "segments": len(base["segments"])}


@router.get("/board")
def get_board(
    user_id: int = Depends(current_user_id), db: sqlite3.Connection = Depends(get_db)
) -> dict:
    """The CIO Brain board: every followed security → its questions, each with a
    green/yellow/red status and signal counts per source class."""
    statuses = question_statuses(db, user_id)
    by_company: dict[str, list[dict]] = {}
    for t in repo.list_theses(db, user_id):
        st = statuses.get(t["id"], {})
        by_company.setdefault(t["company"], []).append(
            {
                "id": t["id"],
                "question": t["question"],
                "drivers": json.loads(t["drivers"]) if t["drivers"] else [],
                "status": st.get("status", "none"),
                "signals": st.get("signals", 0),
                "references": st.get("references", 0),
                "by_class": st.get("by_class")
                or {k: {"supports": 0, "contradicts": 0} for k in ("print", "chatter", "inside")},
            }
        )
    with_model = {r["company"] for r in db.execute("SELECT company FROM model_bases").fetchall()}
    rows = []
    for sec in repo.list_user_securities(db, user_id):
        rows.append(
            {
                "company": sec["company"],
                "ticker": sec["ticker"],
                "key": security_key(sec["company"], sec["ticker"]),
                "category": sec["category"],
                "has_model": sec["company"] in with_model,
                "questions": by_company.get(sec["company"], []),
            }
        )
    return {"securities": rows}


class TokenIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)


@router.get("/me/tokens")
def list_tokens(user_id: int = Depends(current_user_id), db: sqlite3.Connection = Depends(get_db)) -> dict:
    return {"tokens": [dict(r) for r in repo.list_api_tokens(db, user_id)]}


@router.post("/me/tokens")
def create_token(
    body: TokenIn, user_id: int = Depends(current_user_id), db: sqlite3.Connection = Depends(get_db)
) -> dict:
    """Mint a personal API token (for the MCP server). Shown once."""
    token_id, token = repo.create_api_token(db, user_id, body.name.strip())
    return {"id": token_id, "token": token}


@router.delete("/me/tokens/{token_id}")
def revoke_token(
    token_id: int, user_id: int = Depends(current_user_id), db: sqlite3.Connection = Depends(get_db)
) -> dict:
    if not repo.delete_api_token(db, user_id, token_id):
        raise HTTPException(status_code=404, detail="token not found")
    return {"revoked": token_id}


@router.patch("/hits/{hit_id}")
def decide_hit(
    hit_id: int,
    body: DecisionIn,
    user_id: int = Depends(current_user_id),
    db: sqlite3.Connection = Depends(get_db),
) -> dict:
    """Keep or drop a hit (or reset it to pending)."""
    if not repo.set_hit_decision(db, user_id, hit_id, body.decision):
        raise HTTPException(status_code=404, detail="hit not found")
    return {"hit_id": hit_id, "decision": body.decision}
