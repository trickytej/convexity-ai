"""Step 5: triage writes (relevant / not_relevant / pending)."""

from __future__ import annotations

import sqlite3
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ...store import repo
from ..deps import get_db

router = APIRouter(tags=["nuggets"])


class TriageIn(BaseModel):
    triage: Literal["pending", "relevant", "not_relevant"]


class TriageOut(BaseModel):
    id: int
    triage: str


@router.post("/nuggets/{nugget_id}/triage", response_model=TriageOut)
def set_triage(
    nugget_id: int, body: TriageIn, db: sqlite3.Connection = Depends(get_db)
) -> TriageOut:
    if not repo.set_triage(db, nugget_id, body.triage):
        raise HTTPException(status_code=404, detail="nugget not found")
    return TriageOut(id=nugget_id, triage=body.triage)
