"""FastAPI application factory."""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from .. import __version__
from .routers import (
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
)

# Open paths that never require the API key (health check + CORS preflight).
_OPEN_PATHS = {"/api/health"}


def create_app() -> FastAPI:
    app = FastAPI(title="research-digest API", version=__version__)

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

    @app.middleware("http")
    async def require_api_key(request: Request, call_next):  # type: ignore[no-untyped-def]
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
