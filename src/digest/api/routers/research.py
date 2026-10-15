"""Private research ("inside view"): a user's own notes, PDFs and links.

Documents are stored as episodes owned by the user (episodes.owner_user_id),
run through nugget extraction, and matched only against that user's questions.
"""

from __future__ import annotations

import sqlite3
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from ...acquire.article import fetch_article
from ...acquire.base import TranscriptUnavailable
from ...config import get_settings
from ...documents import RESEARCH_SHOW, create_document, paragraphs_from_text, process_document, text_from_pdf
from ...store import repo
from ...store.db import connect
from ..deps import current_user_id, get_db

router = APIRouter(tags=["research"])

_MAX_UPLOAD_BYTES = 20 * 1024 * 1024


class ResearchIn(BaseModel):
    title: str = ""
    text: str | None = None
    url: str | None = None


def _process_in_background(background_tasks: BackgroundTasks, episode_id: int) -> None:
    def _run() -> None:
        settings = get_settings()
        conn = connect(settings.resolved_db_path)
        try:
            process_document(conn, episode_id, settings)
        finally:
            conn.close()

    background_tasks.add_task(_run)


def _store(
    db: sqlite3.Connection,
    background_tasks: BackgroundTasks,
    user_id: int,
    title: str,
    paragraphs: list[str],
    url: str | None,
) -> dict:
    if not paragraphs:
        raise HTTPException(status_code=422, detail="no readable text found")
    episode_id, _ = create_document(
        db,
        show=RESEARCH_SHOW,
        guid=f"u{user_id}-{uuid.uuid4().hex}",
        title=title or paragraphs[0][:80],
        paragraphs=paragraphs,
        url=url,
        owner_user_id=user_id,
    )
    _process_in_background(background_tasks, episode_id)
    return {"id": episode_id, "status": "processing", "paragraphs": len(paragraphs)}


@router.post("/research")
def add_research(
    body: ResearchIn,
    background_tasks: BackgroundTasks,
    user_id: int = Depends(current_user_id),
    db: sqlite3.Connection = Depends(get_db),
) -> dict:
    """Add pasted text, or a link to fetch. Processed in the background."""
    url = (body.url or "").strip() or None
    if body.text and body.text.strip():
        paragraphs = paragraphs_from_text(body.text)
    elif url:
        try:
            paragraphs = [s.text for s in fetch_article(url).segments]
        except TranscriptUnavailable as exc:
            raise HTTPException(status_code=422, detail=f"could not read that link: {exc}")
    else:
        raise HTTPException(status_code=422, detail="provide text or a url")
    return _store(db, background_tasks, user_id, body.title.strip(), paragraphs, url)


@router.post("/research/upload")
async def upload_research(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str = Form(""),
    user_id: int = Depends(current_user_id),
    db: sqlite3.Connection = Depends(get_db),
) -> dict:
    """Upload a PDF, text or Markdown file."""
    data = await file.read()
    if len(data) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="file too large (20 MB max)")
    name = (file.filename or "").lower()
    if name.endswith(".pdf") or file.content_type == "application/pdf":
        try:
            text = text_from_pdf(data)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"could not read PDF: {exc}")
    elif name.endswith((".txt", ".md", ".markdown")) or (file.content_type or "").startswith("text/"):
        text = data.decode("utf-8", errors="replace")
    else:
        raise HTTPException(status_code=415, detail="upload a PDF, .txt or .md file")
    default_title = (file.filename or "").rsplit(".", 1)[0]
    return _store(
        db, background_tasks, user_id, title.strip() or default_title, paragraphs_from_text(text), None
    )


@router.get("/research")
def list_research(
    user_id: int = Depends(current_user_id), db: sqlite3.Connection = Depends(get_db)
) -> dict:
    return {"documents": [dict(r) for r in repo.list_research(db, user_id)]}


@router.delete("/research/{episode_id}")
def delete_research(
    episode_id: int, user_id: int = Depends(current_user_id), db: sqlite3.Connection = Depends(get_db)
) -> dict:
    if not repo.delete_research(db, user_id, episode_id):
        raise HTTPException(status_code=404, detail="document not found")
    return {"deleted": episode_id}
