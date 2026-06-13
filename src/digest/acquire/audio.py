"""Download episode audio enclosures for the ASR path."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse

from ..config import Settings, get_settings
from ..net import download_file
from ..store.models import Episode

_AUDIO_EXTS = {".mp3", ".m4a", ".mp4", ".aac", ".ogg", ".oga", ".opus", ".wav", ".flac"}


def _guess_ext(url: str) -> str:
    path = urlparse(url).path
    ext = os.path.splitext(path)[1].lower()
    return ext if ext in _AUDIO_EXTS else ".mp3"


def audio_dest(episode: Episode, settings: Settings) -> Path:
    if episode.id is None:
        raise ValueError("episode must be persisted (have an id) before download")
    ext = _guess_ext(episode.audio_url or "")
    return settings.audio_dir / episode.show_slug / f"{episode.id}{ext}"


def download_audio(episode: Episode, settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    if not episode.audio_url:
        raise ValueError("episode has no audio_url")
    dest = audio_dest(episode, settings)
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    return download_file(episode.audio_url, dest, settings)
