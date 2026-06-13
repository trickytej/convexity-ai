"""AssemblyAI transcription with diarization and domain word-boosting."""

from __future__ import annotations

import logging
from pathlib import Path

import assemblyai as aai

from ..acquire.base import ParsedTranscript, TranscriptSegment
from ..config import Settings, get_settings
from ..registry import Glossary, Show

log = logging.getLogger(__name__)

# AssemblyAI caps word_boost; keep phrases short and the list bounded.
_MAX_BOOST_TERMS = 900
_MAX_BOOST_WORDS_PER_TERM = 6


class TranscriptionError(Exception):
    pass


def _word_boost(glossary: Glossary) -> list[str]:
    terms = [
        t
        for t in glossary.all_terms()
        if 0 < len(t.split()) <= _MAX_BOOST_WORDS_PER_TERM
    ]
    return terms[:_MAX_BOOST_TERMS]


def transcribe_audio(
    audio_path: str | Path,
    show: Show,
    glossary: Glossary,
    settings: Settings | None = None,
) -> ParsedTranscript:
    settings = settings or get_settings()
    if not settings.assemblyai_api_key:
        raise TranscriptionError("ASSEMBLYAI_API_KEY is not set")
    audio_path = Path(audio_path)
    if not audio_path.is_file():
        raise TranscriptionError(f"audio file not found: {audio_path}")

    aai.settings.api_key = settings.assemblyai_api_key
    speech_models = [m.strip() for m in settings.assemblyai_speech_models.split(",") if m.strip()]
    if not speech_models:
        speech_models = ["universal-3-pro", "universal-2"]

    config = aai.TranscriptionConfig(
        speech_models=speech_models,
        speaker_labels=True,
        word_boost=_word_boost(glossary),
        boost_param="high",
        punctuate=True,
        format_text=True,
    )

    log.info("submitting %s to AssemblyAI (models=%s)", audio_path.name, speech_models)
    transcript = aai.Transcriber(config=config).transcribe(str(audio_path))

    if transcript.status == aai.TranscriptStatus.error:
        raise TranscriptionError(transcript.error or "AssemblyAI transcription failed")

    utterances = transcript.utterances or []
    segments: list[TranscriptSegment] = [
        TranscriptSegment(
            speaker_name=None,
            speaker_label=u.speaker,
            text=u.text,
            start_ms=int(u.start) if u.start is not None else None,
            end_ms=int(u.end) if u.end is not None else None,
        )
        for u in utterances
        if (u.text or "").strip()
    ]

    # Fall back to the flat transcript if diarization yielded nothing.
    if not segments and (transcript.text or "").strip():
        segments = [TranscriptSegment(speaker_name=None, text=transcript.text.strip())]

    if not segments:
        raise TranscriptionError("AssemblyAI returned an empty transcript")

    return ParsedTranscript(
        provider="assemblyai",
        segments=segments,
        language=transcript.language_code or "en",
        has_diarization=bool(utterances),
        meta={"assemblyai_id": transcript.id, "speech_models": speech_models},
    )
