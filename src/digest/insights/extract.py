"""Extraction pipeline: transcript -> verified, scored, deduped nuggets."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from ..config import Settings, get_settings
from ..registry import Show
from ..store.models import Episode, Nugget
from ..transcribe import llm
from . import taxonomy

log = logging.getLogger(__name__)

_MAX_CHUNK_WORDS = 1800
_CHUNK_OVERLAP = 1
_DEDUP_JACCARD = 0.6


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower()


def _ms_to_mmss(ms: int | None) -> str:
    if ms is None:
        return "?"
    s = ms // 1000
    return f"{s // 60}:{s % 60:02d}"


def _chunk_segments(segments: list[dict]) -> list[list[dict]]:
    chunks: list[list[dict]] = []
    current: list[dict] = []
    words = 0
    for seg in segments:
        w = len((seg.get("text") or "").split())
        if current and words + w > _MAX_CHUNK_WORDS:
            chunks.append(current)
            current = current[-_CHUNK_OVERLAP:] if _CHUNK_OVERLAP else []
            words = sum(len((s.get("text") or "").split()) for s in current)
        current.append(seg)
        words += w
    if current:
        chunks.append(current)
    return chunks


def _render_chunk(chunk: list[dict]) -> str:
    lines = []
    for s in chunk:
        speaker = s.get("speaker_name") or "?"
        lines.append(f"[#{s.get('idx')} {speaker} {_ms_to_mmss(s.get('start_ms'))}] {s.get('text')}")
    return "\n".join(lines)


def _find_segment(quote: str, chunk: list[dict]) -> tuple[dict | None, bool]:
    """Locate the segment a quote came from. Returns (segment, exact_match)."""
    q = _norm(quote)
    if len(q) < 8:
        return None, False
    for seg in chunk:
        if q in _norm(seg.get("text") or ""):
            return seg, True
    # Fall back to best token overlap (for attribution/timestamp only).
    q_tokens = set(q.split())
    best: dict | None = None
    best_overlap = 0.0
    for seg in chunk:
        s_tokens = set(_norm(seg.get("text") or "").split())
        if not s_tokens or not q_tokens:
            continue
        overlap = len(q_tokens & s_tokens) / len(q_tokens)
        if overlap > best_overlap:
            best_overlap, best = overlap, seg
    return (best, False) if best_overlap >= 0.6 else (None, False)


def _parse_item(item: dict, chunk: list[dict], episode_id: int, model: str) -> Nugget | None:
    if not isinstance(item, dict):
        return None
    claim = (item.get("claim") or "").strip()
    if not claim:
        return None

    nugget_type = str(item.get("type") or "").strip().lower()
    if nugget_type not in taxonomy.VALID_TYPES:
        nugget_type = "thesis"

    quote = (item.get("quote") or "").strip()
    seg, exact = _find_segment(quote, chunk) if quote else (None, False)

    speaker = (seg.get("speaker_name") if seg else None) or (item.get("speaker") or None)
    start_ms = seg.get("start_ms") if seg else None
    end_ms = seg.get("end_ms") if seg else None

    scores = item.get("scores") if isinstance(item.get("scores"), dict) else {}
    entities = item.get("entities") if isinstance(item.get("entities"), dict) else None
    sectors = item.get("sectors") if isinstance(item.get("sectors"), list) else None
    primary_sector = item.get("primary_sector")
    if primary_sector not in taxonomy.VERTICALS:
        primary_sector = None

    return Nugget(
        episode_id=episode_id,
        type=nugget_type,
        claim=claim,
        quote=quote or None,
        speaker_name=speaker,
        start_ms=start_ms,
        end_ms=end_ms,
        entities=entities,
        sectors=sectors,
        primary_sector=primary_sector,
        scores=scores or None,
        signal_score=taxonomy.composite_score(scores),
        quote_verified=exact,
        model=model,
    )


def _dedup(nuggets: list[Nugget]) -> list[Nugget]:
    kept: list[Nugget] = []
    for nugget in sorted(nuggets, key=lambda n: -n.signal_score):
        claim_tokens = set(_norm(nugget.claim).split())
        duplicate = False
        for existing in kept:
            other = set(_norm(existing.claim).split())
            if not claim_tokens or not other:
                continue
            jaccard = len(claim_tokens & other) / len(claim_tokens | other)
            if jaccard >= _DEDUP_JACCARD:
                duplicate = True
                break
        if not duplicate:
            kept.append(nugget)
    return kept


def extract_nuggets(
    episode: Episode,
    show: Show,
    transcript_path: str | Path,
    settings: Settings | None = None,
) -> list[Nugget]:
    """Extract verified, scored, deduped nuggets from a normalized transcript."""
    settings = settings or get_settings()
    assert episode.id is not None
    data = json.loads(Path(transcript_path).read_text(encoding="utf-8"))
    segments = data.get("segments", [])
    if not segments:
        return []

    client = llm.get_client(settings)  # raises LLMError if no key
    speakers = sorted({s.get("speaker_name") for s in segments if s.get("speaker_name")})
    model = settings.anthropic_model

    candidates: list[Nugget] = []
    for chunk in _chunk_segments(segments):
        user = taxonomy.build_user_prompt(show.name, episode.title, speakers, _render_chunk(chunk))
        try:
            raw = llm.complete(
                client,
                system=taxonomy.SYSTEM_PROMPT,
                user=user,
                model=model,
                max_tokens=8192,
            )
            parsed = llm.extract_json(raw)
        except llm.LLMError as exc:
            log.warning("nugget extraction failed for a chunk of ep %s: %s", episode.id, exc)
            continue
        if not isinstance(parsed, list):
            continue
        for item in parsed:
            nugget = _parse_item(item, chunk, episode.id, model)
            if nugget is not None:
                candidates.append(nugget)

    return _dedup(candidates)
