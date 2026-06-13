"""FastAPI application factory."""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .. import __version__
from .routers import digests, insights, library, nuggets, report


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

    app.include_router(library.router, prefix="/api")
    app.include_router(insights.router, prefix="/api")
    app.include_router(report.router, prefix="/api")
    app.include_router(nuggets.router, prefix="/api")
    app.include_router(digests.router, prefix="/api")

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    return app


app = create_app()
