"""Application settings (env-driven) and watchlist loading."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "config"
DATA_DIR = REPO_ROOT / "data"


class Settings(BaseSettings):
    """Runtime configuration, loaded from environment / .env (prefix MOVES_)."""

    model_config = SettingsConfigDict(
        env_prefix="MOVES_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    polygon_api_key: str = ""
    finnhub_api_key: str = ""
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"
    synthesis_model: str = "claude-opus-4-8"
    anthropic_thinking: bool = False  # fast/default attribution (Sonnet) — keep snappy
    synthesis_thinking: bool = True  # Opus deep-dive agent — adaptive ("max") reasoning

    # research-digest corpus bridge (read-only).
    digest_db_path: str = ""
    digest_web_base: str = "http://localhost:3000"

    # Default detection parameters (overridable per request).
    move_threshold: float = 0.05

    data_dir: Path = DATA_DIR

    @property
    def parquet_dir(self) -> Path:
        return self.data_dir / "parquet"

    @property
    def duckdb_path(self) -> Path:
        return self.data_dir / "moves.duckdb"

    @property
    def insights_cache_path(self) -> Path:
        return self.data_dir / "insights.sqlite"

    @property
    def resolved_digest_db_path(self) -> Path | None:
        """Path to research-digest's digest.db, if available.

        Uses MOVES_DIGEST_DB_PATH when set, else the sibling repo's default
        location. Returns None if neither exists.
        """
        if self.digest_db_path:
            p = Path(self.digest_db_path)
            return p if p.exists() else None
        sibling = REPO_ROOT.parent / "research-digest" / "data" / "digest.db"
        return sibling if sibling.exists() else None


class Instrument(BaseModel):
    ticker: str
    name: str = ""
    group: str = ""


def load_watchlist(path: Path | None = None) -> list[Instrument]:
    """Load the curated instrument watchlist from config/watchlist.yaml."""
    path = path or (CONFIG_DIR / "watchlist.yaml")
    data = yaml.safe_load(path.read_text())
    return [Instrument(**row) for row in data.get("instruments", [])]


def get_settings() -> Settings:
    return Settings()
