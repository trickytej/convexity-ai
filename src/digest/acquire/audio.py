"""Download episode audio enclosures for the ASR path."""

from __future__ import annotations

import os
import re
from pathlib import Path
from urllib.parse import urlparse

from ..config import Settings, get_settings
from ..net import download_file
from ..store.models import Episode

_AUDIO_EXTS = {".mp3", ".m4a", ".mp4", ".aac", ".ogg", ".oga", ".opus", ".wav", ".flac"}
_YT_AUDIO_EXTS = {".m4a", ".webm", ".mp4", ".ogg", ".opus"}

_AUDIO_MAGIC: list[tuple[int, bytes]] = [
    (0,  b'ID3'),           # MP3 with ID3 tag
    (0,  b'\xff\xfb'),      # MP3 frame
    (0,  b'\xff\xf3'),
    (0,  b'\xff\xf2'),
    (4,  b'ftyp'),          # M4A / MP4 / AAC
    (0,  b'\x1a\x45\xdf\xa3'),  # WebM / MKV
    (0,  b'OggS'),          # OGG / Opus
    (0,  b'fLaC'),          # FLAC
    (0,  b'RIFF'),          # WAV
]


def _is_valid_audio_file(path: Path) -> bool:
    """Check magic bytes to confirm path is real audio, not HTML/junk."""
    try:
        with path.open("rb") as f:
            header = f.read(12)
        return any(header[off: off + len(sig)] == sig for off, sig in _AUDIO_MAGIC)
    except OSError:
        return False

_YOUTUBE_RE = re.compile(
    r"(youtube\.com/(watch|shorts|live)|youtu\.be/)", re.IGNORECASE
)


def _is_youtube(url: str) -> bool:
    return bool(_YOUTUBE_RE.search(url))


def _guess_ext(url: str) -> str:
    path = urlparse(url).path
    ext = os.path.splitext(path)[1].lower()
    return ext if ext in _AUDIO_EXTS else ".mp3"


def audio_dest(episode: Episode, settings: Settings) -> Path:
    if episode.id is None:
        raise ValueError("episode must be persisted (have an id) before download")
    ext = _guess_ext(episode.audio_url or "")
    return settings.audio_dir / episode.show_slug / f"{episode.id}{ext}"


def _find_existing_audio(dir: Path, stem: str) -> Path | None:
    """Return an existing audio file for this episode stem if magic bytes confirm it's audio."""
    if not dir.exists():
        return None
    for f in dir.glob(f"{stem}.*"):
        if f.suffix.lower() in (_AUDIO_EXTS | _YT_AUDIO_EXTS) and _is_valid_audio_file(f):
            return f
    return None


def _download_youtube(url: str, dest: Path) -> Path:
    import yt_dlp  # only imported when needed

    dest.parent.mkdir(parents=True, exist_ok=True)

    # Delete any stale non-audio file (e.g. HTML page saved with audio extension)
    for stale in dest.parent.glob(f"{dest.name}.*"):
        if not _is_valid_audio_file(stale):
            stale.unlink(missing_ok=True)

    out_tmpl = str(dest) + ".%(ext)s"
    ydl_opts = {
        "format": "bestaudio[ext=m4a]/bestaudio/best",
        "outtmpl": out_tmpl,
        "quiet": True,
        "no_warnings": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    result = _find_existing_audio(dest.parent, dest.name)
    if result:
        return result
    raise FileNotFoundError(f"yt-dlp finished but no valid audio file found near {dest}")


def download_audio(episode: Episode, settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    if not episode.audio_url:
        raise ValueError("episode has no audio_url")

    if _is_youtube(episode.audio_url):
        audio_dir = settings.audio_dir / episode.show_slug
        stem = str(episode.id)
        existing = _find_existing_audio(audio_dir, stem)
        if existing:
            return existing
        return _download_youtube(episode.audio_url, audio_dir / stem)

    dest = audio_dest(episode, settings)
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    return download_file(episode.audio_url, dest, settings)
