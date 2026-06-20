"""FastAPI application factory."""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from moves import __version__
from moves.store import init_db

from .routers import market


def create_app() -> FastAPI:
    # Ensure the store + schema exist so read-only request connections succeed.
    init_db()

    app = FastAPI(title="market-moves API", version=__version__)

    origins = os.environ.get(
        "MOVES_CORS_ORIGINS",
        "http://localhost:3001,http://127.0.0.1:3001",
    ).split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in origins if o.strip()],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(market.router, prefix="/api")

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    return app


app = create_app()
