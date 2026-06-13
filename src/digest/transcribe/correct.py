"""LLM proper-noun / technical-term correction for ASR transcripts.

Processes the transcript in batches and asks the model to fix only clearly
mistranscribed proper nouns and domain terms (using the glossary), preserving
everything else verbatim. Any batch that fails to parse keeps its original text,
so the pass can never lose or corrupt content.
"""

from __future__ import annotations

import json
import logging

from ..acquire.base import ParsedTranscript
from ..config import Settings, get_settings
from ..registry import Glossary
from . import llm

log = logging.getLogger(__name__)

_MAX_BATCH_SEGMENTS = 24
_MAX_BATCH_WORDS = 3000

_SYSTEM = (
    "You correct speech-to-text transcripts of technical AI, semiconductor, and "
    "investing podcasts. Fix ONLY clear mistranscriptions of proper nouns (company "
    "and people names) and domain/technical/finance terms, guided by the supplied "
    "glossary and context. Do NOT paraphrase, summarize, translate, reorder, change "
    "meaning, alter punctuation/casing, or remove filler words. Return text verbatim "
    "except for corrected terms. Output strict JSON: an array of objects "
    '{"idx": <int>, "text": "<corrected text>"} with exactly the same idx values you '
    "were given. No commentary."
)


def _batches(segments, max_segments: int, max_words: int):
    batch: list = []
    words = 0
    for seg in segments:
        seg_words = len(seg.text.split())
        if batch and (len(batch) >= max_segments or words + seg_words > max_words):
            yield batch
            batch, words = [], 0
        batch.append(seg)
        words += seg_words
    if batch:
        yield batch


def correct_transcript(
    parsed: ParsedTranscript,
    glossary: Glossary,
    settings: Settings | None = None,
    *,
    context: str = "",
) -> int:
    """Mutate ``parsed`` segments in place. Returns the number of segments changed."""
    settings = settings or get_settings()
    client = llm.get_client(settings)  # raises LLMError if no key

    indexed = list(enumerate(parsed.segments))
    glossary_ctx = glossary.correction_context()
    changed = 0

    for batch in _batches([s for _, s in indexed], _MAX_BATCH_SEGMENTS, _MAX_BATCH_WORDS):
        # Map back to global indices for this batch.
        idx_lookup = {id(seg): i for i, seg in indexed}
        payload = [{"idx": idx_lookup[id(seg)], "text": seg.text} for seg in batch]
        user = (
            f"Glossary and context:\n{glossary_ctx}\n"
            + (f"\nEpisode context: {context}\n" if context else "")
            + "\nCorrect the following transcript segments. Return JSON only.\n"
            + json.dumps(payload, ensure_ascii=False)
        )
        try:
            raw = llm.complete(
                client,
                system=_SYSTEM,
                user=user,
                model=settings.anthropic_model,
                max_tokens=8192,
            )
            data = llm.extract_json(raw)
        except llm.LLMError as exc:
            log.warning("correction batch failed (%s); keeping original text", exc)
            continue

        if not isinstance(data, list):
            continue
        corrections = {
            item["idx"]: item["text"]
            for item in data
            if isinstance(item, dict) and "idx" in item and isinstance(item.get("text"), str)
        }
        for global_idx, seg in indexed:
            new_text = corrections.get(global_idx)
            if new_text is not None and new_text.strip() and new_text != seg.text:
                seg.text = new_text
                changed += 1

    return changed
