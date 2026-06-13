"""Layer 2: per-nugget curation (keep / kill / rank / note)."""

from __future__ import annotations

import json
import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from ...store import repo
from ..deps import get_db
from ..schemas import (
    CurationOut,
    CurationPatch,
    CurationStatsOut,
    NuggetWithCurationOut,
)

router = APIRouter(tags=["curation"])

_RANK_THRESHOLDS = ((0.65, 1), (0.35, 2))  # signal_score → suggested rank


def _suggested_rank(signal_score: float) -> int:
    for threshold, rank in _RANK_THRESHOLDS:
        if signal_score >= threshold:
            return rank
    return 3


def _curation_out(row: sqlite3.Row) -> CurationOut:
    keys = row.keys()
    # JOIN queries alias these columns; direct curation-table queries use bare names.
    note = row["curation_note"] if "curation_note" in keys else row["note"]
    updated_at = row["curation_updated_at"] if "curation_updated_at" in keys else row["updated_at"]
    return CurationOut(
        decision=row["decision"] or "unreviewed",
        curator_rank=row["curator_rank"],
        contradicts_consensus=bool(row["contradicts_consensus"]),
        note=note,
        updated_at=updated_at,
    )


def _nugget_with_curation_out(row: sqlite3.Row) -> NuggetWithCurationOut:
    has_curation = row["decision"] is not None
    entities_raw = json.loads(row["entities"]) if row["entities"] else None
    sectors_raw = json.loads(row["sectors"]) if row["sectors"] else []
    scores_raw = json.loads(row["scores"]) if row["scores"] else None
    return NuggetWithCurationOut(
        id=row["id"],
        episode_id=row["episode_id"],
        type=row["type"],
        claim=row["claim"],
        quote=row["quote"],
        speaker_name=row["speaker_name"],
        start_ms=row["start_ms"],
        end_ms=row["end_ms"],
        entities=entities_raw,
        sectors=sectors_raw if isinstance(sectors_raw, list) else [],
        primary_sector=row["primary_sector"] if "primary_sector" in row.keys() else None,
        scores=scores_raw,
        signal_score=row["signal_score"],
        quote_verified=bool(row["quote_verified"]),
        triage=row["triage"],
        suggested_rank=_suggested_rank(row["signal_score"]),
        curation=CurationOut(
            decision=row["decision"] or "unreviewed",
            curator_rank=row["curator_rank"],
            contradicts_consensus=bool(row["contradicts_consensus"] or 0),
            note=row["curation_note"],
            updated_at=row["curation_updated_at"],
        ) if has_curation else CurationOut(),
    )


@router.get("/episodes/{episode_id}/nuggets", response_model=list[NuggetWithCurationOut])
def list_episode_nuggets(
    episode_id: int, db: sqlite3.Connection = Depends(get_db)
) -> list[NuggetWithCurationOut]:
    if repo.get_episode(db, episode_id) is None:
        raise HTTPException(status_code=404, detail="episode not found")
    rows = repo.list_nuggets_with_curation(db, episode_id)
    return [_nugget_with_curation_out(r) for r in rows]


@router.get("/episodes/{episode_id}/nuggets/stats", response_model=CurationStatsOut)
def nugget_curation_stats(
    episode_id: int, db: sqlite3.Connection = Depends(get_db)
) -> CurationStatsOut:
    if repo.get_episode(db, episode_id) is None:
        raise HTTPException(status_code=404, detail="episode not found")
    return CurationStatsOut(**repo.nugget_curation_stats(db, episode_id))


@router.patch("/nuggets/{nugget_id}/curation", response_model=CurationOut)
def patch_curation(
    nugget_id: int, body: CurationPatch, db: sqlite3.Connection = Depends(get_db)
) -> CurationOut:
    if repo.get_nugget(db, nugget_id) is None:
        raise HTTPException(status_code=404, detail="nugget not found")
    row = repo.upsert_curation(
        db,
        nugget_id,
        decision=body.decision,
        curator_rank=body.curator_rank,
        contradicts_consensus=body.contradicts_consensus,
        note=body.note,
    )
    return _curation_out(row)
