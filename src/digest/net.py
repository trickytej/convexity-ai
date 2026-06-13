"""HTTP helpers with a shared user-agent, sane timeouts, and retry/backoff."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from .config import Settings, get_settings


def _headers(settings: Settings) -> dict[str, str]:
    return {"User-Agent": settings.user_agent}


def _should_retry(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.TransportError, httpx.TimeoutException)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        return code == 429 or code >= 500
    return False


_retry = retry(
    reraise=True,
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=1, max=20),
    retry=retry_if_exception(_should_retry),
)


@_retry
def fetch_bytes(url: str, settings: Settings | None = None, *, timeout: float | None = None) -> bytes:
    settings = settings or get_settings()
    timeout = timeout if timeout is not None else settings.http_timeout_seconds
    with httpx.Client(follow_redirects=True, timeout=timeout, headers=_headers(settings)) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.content


@_retry
def fetch_text(url: str, settings: Settings | None = None, *, timeout: float | None = None) -> str:
    settings = settings or get_settings()
    timeout = timeout if timeout is not None else settings.http_timeout_seconds
    with httpx.Client(follow_redirects=True, timeout=timeout, headers=_headers(settings)) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.text


@_retry
def download_file(
    url: str,
    dest: Path,
    settings: Settings | None = None,
    *,
    chunk_size: int = 1 << 16,
    on_progress: Callable[[int, int | None], None] | None = None,
) -> Path:
    """Stream a URL to ``dest`` atomically (via a .part temp file)."""
    settings = settings or get_settings()
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    # Longer read timeout for large media; keep connect timeout short.
    timeout = httpx.Timeout(settings.http_timeout_seconds, read=300.0)
    with httpx.Client(follow_redirects=True, timeout=timeout, headers=_headers(settings)) as client:
        with client.stream("GET", url) as resp:
            resp.raise_for_status()
            total = int(resp.headers.get("Content-Length") or 0) or None
            downloaded = 0
            with tmp.open("wb") as fh:
                for chunk in resp.iter_bytes(chunk_size):
                    fh.write(chunk)
                    downloaded += len(chunk)
                    if on_progress is not None:
                        on_progress(downloaded, total)
    tmp.replace(dest)
    return dest
