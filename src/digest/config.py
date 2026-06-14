"""Runtime configuration.

Settings come from environment variables (prefixed ``DIGEST_``) and an optional
``.env`` file. API keys are read from their conventional unprefixed names
(``ANTHROPIC_API_KEY``, ``ASSEMBLYAI_API_KEY``).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def find_project_root(start: Path | None = None) -> Path:
    """Walk upward from ``start`` (or this file) to the dir holding pyproject.toml."""
    candidates: list[Path] = []
    if start is not None:
        candidates.append(start)
    candidates.append(Path.cwd())
    candidates.append(Path(__file__).resolve())

    for origin in candidates:
        origin = origin.resolve()
        for parent in [origin, *origin.parents]:
            if (parent / "pyproject.toml").is_file():
                return parent
    # Fallback: package is src/digest/, so root is two levels up.
    return Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DIGEST_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    data_dir: Path = Path("data")
    config_dir: Path = Path("config")
    db_path: Path | None = None

    anthropic_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("ANTHROPIC_API_KEY", "DIGEST_ANTHROPIC_API_KEY"),
    )
    assemblyai_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("ASSEMBLYAI_API_KEY", "DIGEST_ASSEMBLYAI_API_KEY"),
    )

    # High-volume / mechanical work: extraction, correction, speaker-id, sectors.
    anthropic_model: str = "claude-sonnet-4-6"
    # Low-volume / high-value synthesis: weekly report + per-episode digest.
    synthesis_model: str = "claude-opus-4-8"
    synthesis_thinking: bool = True       # adaptive (max) reasoning for synthesis
    synthesis_context_1m: bool = True     # enable the 1M-context beta on synthesis
    # Comma-separated AssemblyAI model fallback chain (best accuracy first).
    assemblyai_speech_models: str = "universal-3-pro,universal-2"
    user_agent: str = "research-digest/0.1 (+https://localhost)"
    http_timeout_seconds: float = 60.0

    # Email / SMTP (optional — set to enable Send Email in newsletter UI)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_pass: str = ""
    smtp_from: str = ""

    def _anchor(self, p: Path) -> Path:
        return p if p.is_absolute() else (find_project_root() / p)

    @property
    def resolved_data_dir(self) -> Path:
        return self._anchor(self.data_dir)

    @property
    def resolved_config_dir(self) -> Path:
        return self._anchor(self.config_dir)

    @property
    def resolved_db_path(self) -> Path:
        if self.db_path is not None:
            return self._anchor(self.db_path)
        return self.resolved_data_dir / "digest.db"

    @property
    def audio_dir(self) -> Path:
        return self.resolved_data_dir / "audio"

    @property
    def transcripts_dir(self) -> Path:
        return self.resolved_data_dir / "transcripts"

    @property
    def shows_file(self) -> Path:
        return self.resolved_config_dir / "shows.yaml"

    @property
    def glossary_file(self) -> Path:
        return self.resolved_config_dir / "glossary.yaml"

    def ensure_dirs(self) -> None:
        for d in (self.resolved_data_dir, self.audio_dir, self.transcripts_dir):
            d.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
