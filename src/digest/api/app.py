"""FastAPI application factory."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from .. import __version__
from ..config import get_settings
from ..store import repo
from ..store.db import connect, init_db
from .routers import (
    admin,
    curation,
    digests,
    ingest,
    insights,
    library,
    newsletter,
    nuggets,
    report,
    scout,
    theses,
    research,
    users,
)

log = logging.getLogger(__name__)

# Open paths that never require the API key (health check + CORS preflight).
_OPEN_PATHS = {"/api/health"}
_GUEST_BLOCKED = ("/api/me/tokens", "/api/auth/", "/api/research")


@asynccontextmanager
async def _lifespan(app: FastAPI):
    # Apply idempotent schema migrations on boot so deploys never serve a stale
    # schema (previously only CLI commands ran init_db).
    conn = connect(get_settings().resolved_db_path)
    try:
        init_db(conn)
    finally:
        conn.close()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="research-digest API", version=__version__, lifespan=_lifespan)

    origins = os.environ.get(
        "DIGEST_CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in origins if o.strip()],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Shared-secret gate. When DIGEST_API_KEY is set (production), every /api request
    # must present it via `X-API-Key` (or `Authorization: Bearer`). Unset = open
    # (local dev). Added after CORS so it sits outermost; OPTIONS pass through.
    api_key = os.environ.get("DIGEST_API_KEY")
    if not api_key:
        log.warning(
            "DIGEST_API_KEY is unset: the API is open and X-User-Id is unauthenticated. "
            "Local dev only — never deploy like this."
        )

    def _token_user(token: str) -> int | None:
        conn = connect(get_settings().resolved_db_path)
        try:
            return repo.user_for_token(conn, token)
        finally:
            conn.close()

    @app.middleware("http")
    async def require_api_key(request: Request, call_next):  # type: ignore[no-untyped-def]
        # Signed-out demo visitors (X-Guest, set only by our frontend proxy) may
        # read, nothing else: no writes, no tokens, no model downloads.
        if request.headers.get("x-guest") == "1":
            path = request.url.path
            if request.method not in ("GET", "HEAD", "OPTIONS") or any(
                path.startswith(p) for p in _GUEST_BLOCKED
            ) or path.endswith("/download"):
                return JSONResponse({"detail": "sign in required", "guest": True}, status_code=401)
        # Personal tokens (MCP servers, scripts) authenticate as their user
        # directly: the token's user replaces any client-supplied X-User-Id.
        auth = request.headers.get("authorization", "")
        if auth[:7].lower() == "bearer " and auth[7:].startswith("cvx_"):
            uid = _token_user(auth[7:].strip())
            if uid is None:
                return JSONResponse({"detail": "invalid token"}, status_code=401)
            request.scope["headers"] = [
                (k, v) for k, v in request.scope["headers"] if k not in (b"x-user-id", b"x-guest")
            ] + [(b"x-user-id", str(uid).encode())]
            return await call_next(request)
        if api_key and request.method != "OPTIONS":
            path = request.url.path
            if path.startswith("/api") and path not in _OPEN_PATHS:
                provided = request.headers.get("x-api-key", "")
                if not provided:
                    auth = request.headers.get("authorization", "")
                    if auth.lower().startswith("bearer "):
                        provided = auth[7:]
                if provided != api_key:
                    return JSONResponse({"detail": "unauthorized"}, status_code=401)
        return await call_next(request)

    app.include_router(library.router, prefix="/api")
    app.include_router(insights.router, prefix="/api")
    app.include_router(report.router, prefix="/api")
    app.include_router(nuggets.router, prefix="/api")
    app.include_router(digests.router, prefix="/api")
    app.include_router(curation.router, prefix="/api")
    app.include_router(newsletter.router, prefix="/api")
    app.include_router(ingest.router, prefix="/api")
    app.include_router(scout.router, prefix="/api")
    app.include_router(theses.router, prefix="/api")
    app.include_router(users.router, prefix="/api")
    app.include_router(research.router, prefix="/api")
    app.include_router(admin.router, prefix="/api")

    # market-moves (vendored): price series + move detection + grounded attribution.
    # Guarded so a missing optional dep/data never takes down the core digest API.
    try:
        from moves.api.routers import market as moves_market

        app.include_router(moves_market.router, prefix="/api/moves")
    except Exception as exc:  # pragma: no cover
        import logging

        logging.getLogger(__name__).warning("moves router unavailable: %s", exc)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    return app


app = create_app()
