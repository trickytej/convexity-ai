"""Map diarization labels (A/B/C) to real speaker names.

Uses the show's host roster plus the episode's likely guest (from the title) and
a sample of each label's speech, and asks the LLM to assign names. Labels it
can't confidently identify keep a readable "Speaker A" fallback.
"""

from __future__ import annotations

import logging
import re

from ..acquire.base import ParsedTranscript
from ..config import Settings, get_settings
from ..registry import Show
from ..store.models import Episode
from . import llm

log = logging.getLogger(__name__)

_SAMPLE_CHARS = 700

_SYSTEM = (
    "You identify speakers in a podcast transcript. You are given the show's recurring "
    "hosts, the full episode title (guests are usually named in it), and a sample of "
    "each anonymous speaker label's words. Map each label to the full real name of the "
    "most likely speaker - a recurring host or a guest named in the title. Use the "
    "samples to decide who is interviewing vs. being interviewed. Return null only when "
    "genuinely unclear. Never invent a name and never use episode numbers, article "
    "titles, or topics as a name. Respond with ONLY a strict JSON object mapping each "
    "label to a name string or null - no preamble, explanation, or markdown fences."
)

# Reject obviously-bad 'names' the model might echo from the title.
_BAD_NAME = re.compile(r"^\s*(ep\.?|episode|part|#)\s*\d|^\d", re.IGNORECASE)


def _valid_name(value: object) -> bool:
    if not isinstance(value, str):
        return False
    value = value.strip()
    if not value or len(value) > 60:
        return False
    if _BAD_NAME.search(value):
        return False
    # Require at least one alphabetic word.
    return any(ch.isalpha() for ch in value)


def _samples(parsed: ParsedTranscript) -> dict[str, str]:
    out: dict[str, str] = {}
    for seg in parsed.segments:
        label = seg.speaker_label
        if not label:
            continue
        if len(out.get(label, "")) < _SAMPLE_CHARS:
            out[label] = (out.get(label, "") + " " + seg.text).strip()[:_SAMPLE_CHARS]
    return out


def identify_speakers(
    parsed: ParsedTranscript,
    show: Show,
    episode: Episode,
    settings: Settings | None = None,
) -> dict[str, str]:
    """Return a mapping of speaker_label -> resolved display name."""
    settings = settings or get_settings()
    samples = _samples(parsed)
    if not samples:
        return {}

    roster = ", ".join(show.hosts) if show.hosts else "(unknown)"
    sample_block = "\n\n".join(f'Label "{lbl}": {txt}' for lbl, txt in samples.items())
    user = (
        f"Show: {show.name}\n"
        f"Episode title: {episode.title}\n"
        f"Recurring hosts: {roster}\n"
        "Guests are usually named in the episode title.\n"
        f"Labels to identify: {', '.join(samples)}\n\n"
        f"Speaker samples:\n{sample_block}\n\n"
        "For each label, return the full name of the most likely speaker, or null. "
        "Return JSON mapping label -> name or null."
    )

    try:
        client = llm.get_client(settings)
        raw = llm.complete(
            client,
            system=_SYSTEM,
            user=user,
            model=settings.anthropic_model,
            max_tokens=512,
        )
        data = llm.extract_json(raw)
    except llm.LLMError as exc:
        log.warning("speaker identification failed (%s); keeping labels", exc)
        data = {}

    # Accept either {"A": "Name"} or [{"label": "A", "name": "Name"}] shapes.
    pairs: dict[str, object] = {}
    if isinstance(data, dict):
        pairs = data
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                label = item.get("label") or item.get("speaker") or item.get("id")
                if label is not None:
                    pairs[str(label)] = item.get("name") or item.get("value")

    mapping: dict[str, str] = {}
    for label in samples:
        name = pairs.get(label)
        if _valid_name(name):
            mapping[label] = name.strip()  # type: ignore[union-attr]
    # Readable fallback for any unmapped/invalid labels.
    for label in samples:
        mapping.setdefault(label, f"Speaker {label}")
    return mapping


def apply_speaker_names(parsed: ParsedTranscript, mapping: dict[str, str]) -> None:
    for seg in parsed.segments:
        if seg.speaker_label and seg.speaker_label in mapping:
            seg.speaker_name = mapping[seg.speaker_label]
        elif seg.speaker_name is None and seg.speaker_label:
            seg.speaker_name = f"Speaker {seg.speaker_label}"
