"""Layer 2 endpoint: the aggregated, classified weekly report."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Query

from ...report import build_weekly_report
from ..deps import get_db
from ..schemas import WeeklyReportOut

router = APIRouter(tags=["report"])


@router.get("/report", response_model=WeeklyReportOut)
def weekly_report(
    days: int = Query(7, ge=1, le=90),
    min_signal: float = Query(0.0, ge=0.0, le=1.0),
    per_section_limit: int | None = Query(None, ge=1, le=200),
    db: sqlite3.Connection = Depends(get_db),
) -> WeeklyReportOut:
    return build_weekly_report(
        db,
        days=days,
        min_signal=min_signal,
        per_section_limit=per_section_limit,
    )  # type: ignore[return-value]
