"""Trigger hosted ingestion (discover + download + transcribe + extract).

The transcription pipeline needs ffmpeg, the AssemblyAI key, and several minutes
per episode -- work the web service can't do inside a request. Instead this
endpoint dispatches the repository's ``ingest`` GitHub Actions workflow, which
already installs ffmpeg, holds the API keys as secrets, and writes results
straight into the (Turso) database the site reads from.

Configuration (API environment):
- ``GITHUB_DISPATCH_TOKEN``  GitHub fine-grained PAT with ``Actions: write`` on the repo.
- ``GITHUB_REPO``           ``owner/name`` (default ``dav-s-git/research-digest``).
- ``INGEST_WORKFLOW``       workflow file name (default ``ingest.yml``).
- ``INGEST_REF``            git ref to run against (default ``main``).
"""

from __future__ import annotations

import os
from datetime import date

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(tags=["ingest"])

_GITHUB_API = "https://api.github.com"


class IngestDispatchIn(BaseModel):
    days: int | None = Field(
        default=None, description="Look-back window in days. Takes precedence over `since`."
    )
    since: str | None = Field(
        default=None, description="Start date YYYY-MM-DD; converted to a look-back window."
    )


class IngestDispatchOut(BaseModel):
    dispatched: bool
    days: int
    repo: str
    workflow: str
    run_url: str


def _days_from_since(since: str) -> int:
    try:
        start = date.fromisoformat(since)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="`since` must be YYYY-MM-DD") from exc
    # Inclusive of the start day; the workflow ingests everything published since.
    return max(1, (date.today() - start).days + 1)


@router.post("/ingest/dispatch", response_model=IngestDispatchOut, status_code=202)
def dispatch_ingest(body: IngestDispatchIn) -> IngestDispatchOut:
    """Kick off the ingest workflow for a date range. Returns immediately; the
    workflow runs on a GitHub runner and episodes/nuggets appear as it completes."""
    token = os.environ.get("GITHUB_DISPATCH_TOKEN")
    repo = os.environ.get("GITHUB_REPO", "dav-s-git/research-digest")
    workflow = os.environ.get("INGEST_WORKFLOW", "ingest.yml")
    ref = os.environ.get("INGEST_REF", "main")

    if not token:
        raise HTTPException(
            status_code=503,
            detail=(
                "Background ingestion is not configured. Set GITHUB_DISPATCH_TOKEN "
                "(a GitHub fine-grained PAT with 'Actions: write') in the API environment."
            ),
        )

    if body.days is not None:
        days = max(1, body.days)
    elif body.since:
        days = _days_from_since(body.since)
    else:
        days = 7

    url = f"{_GITHUB_API}/repos/{repo}/actions/workflows/{workflow}/dispatches"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    payload = {"ref": ref, "inputs": {"days": str(days)}}

    try:
        resp = httpx.post(url, json=payload, headers=headers, timeout=20.0)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"GitHub dispatch failed: {exc}") from exc

    if resp.status_code not in (201, 204):
        detail = resp.text[:300] or f"status {resp.status_code}"
        raise HTTPException(status_code=502, detail=f"GitHub rejected dispatch: {detail}")

    return IngestDispatchOut(
        dispatched=True,
        days=days,
        repo=repo,
        workflow=workflow,
        run_url=f"https://github.com/{repo}/actions/workflows/{workflow}",
    )
