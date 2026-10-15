"""Admin bulk loads: base models and ConvexityAI's default questions."""

from __future__ import annotations

import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile

from ...config import get_settings
from ...house import import_house_questions, import_models
from ...store import repo
from ...store.db import connect
from ...theses import run_brief_match
from ..deps import get_db, require_admin

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.post("/models/import")
async def bulk_import_models(
    files: list[UploadFile] = File(...), db: sqlite3.Connection = Depends(get_db)
) -> dict:
    """Upload many Canalyst-format .xlsx models; each is matched to its security by ticker."""
    with tempfile.TemporaryDirectory() as tmp:
        paths = []
        for i, f in enumerate(files):
            p = Path(tmp) / f"{i}.xlsx"
            p.write_bytes(await f.read())
            paths.append((f.filename or p.name, p))
        return {"results": import_models(db, paths)}


@router.post("/house-questions/import")
async def bulk_import_questions(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: sqlite3.Connection = Depends(get_db),
) -> dict:
    """Upload a CSV of default questions (see digest.house for the columns)."""
    try:
        results = import_house_questions(db, (await file.read()).decode("utf-8", errors="replace"))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    house = repo.house_user_id(db)
    if house is not None:
        # Score recent evidence against the new defaults so followers inherit it.
        since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        repo.reset_seen_window(db, house, since)

        def _run() -> None:
            settings = get_settings()
            conn = connect(settings.resolved_db_path)
            try:
                run_brief_match(conn, settings, days=30, user_id=house)
            finally:
                conn.close()

        background_tasks.add_task(_run)
    return {"results": results}
