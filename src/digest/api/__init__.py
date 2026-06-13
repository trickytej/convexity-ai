"""FastAPI web API exposing the digest data (transcripts, episodes, nuggets)."""

from .app import app, create_app

__all__ = ["app", "create_app"]
