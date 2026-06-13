"""Load and validate the curated show registry and domain glossary."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

from .config import Settings, get_settings

Tier = Literal["A", "B"]


class Show(BaseModel):
    slug: str
    name: str
    network: str = ""
    rss_url: str = ""
    homepage: str = ""
    tier: Tier
    transcript_source: str  # parser key (tier A) or "asr" (tier B)
    hosts: list[str] = Field(default_factory=list)
    format: str = "interview"
    active: bool = True

    @property
    def uses_official_transcript(self) -> bool:
        return self.tier == "A" and self.transcript_source != "asr"


class Glossary(BaseModel):
    companies: list[str] = Field(default_factory=list)
    people: list[str] = Field(default_factory=list)
    technical_terms: list[str] = Field(default_factory=list)
    finance_terms: list[str] = Field(default_factory=list)
    aliases: dict[str, str] = Field(default_factory=dict)

    def all_terms(self) -> list[str]:
        """Deduplicated, order-preserving list for ASR word boosting."""
        seen: set[str] = set()
        out: list[str] = []
        for group in (
            self.companies,
            self.people,
            self.technical_terms,
            self.finance_terms,
        ):
            for term in group:
                key = term.lower()
                if key not in seen:
                    seen.add(key)
                    out.append(term)
        return out

    def correction_context(self) -> str:
        """Compact glossary rendering for the LLM correction prompt."""
        lines: list[str] = []
        if self.companies:
            lines.append("Companies: " + ", ".join(self.companies))
        if self.people:
            lines.append("People: " + ", ".join(self.people))
        if self.technical_terms:
            lines.append("Technical terms: " + ", ".join(self.technical_terms))
        if self.finance_terms:
            lines.append("Finance terms: " + ", ".join(self.finance_terms))
        if self.aliases:
            pairs = "; ".join(f"'{k}' -> '{v}'" for k, v in self.aliases.items())
            lines.append("Common mistranscriptions to fix in context: " + pairs)
        return "\n".join(lines)


class Registry(BaseModel):
    shows: list[Show]
    glossary: Glossary

    def get(self, slug: str) -> Show:
        for show in self.shows:
            if show.slug == slug:
                return show
        raise KeyError(f"Unknown show slug: {slug!r}")

    def active(self) -> list[Show]:
        return [s for s in self.shows if s.active]

    def by_tier(self, tier: Tier) -> list[Show]:
        return [s for s in self.active() if s.tier == tier]


def _load_yaml(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"Config file not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected a mapping at top level of {path}")
    return data


def load_registry(settings: Settings | None = None) -> Registry:
    settings = settings or get_settings()
    shows_raw = _load_yaml(settings.shows_file)
    glossary_raw = _load_yaml(settings.glossary_file)

    shows = [Show.model_validate(s) for s in shows_raw.get("shows", [])]
    slugs = [s.slug for s in shows]
    dupes = {x for x in slugs if slugs.count(x) > 1}
    if dupes:
        raise ValueError(f"Duplicate show slugs in registry: {sorted(dupes)}")

    glossary = Glossary.model_validate(glossary_raw)
    return Registry(shows=shows, glossary=glossary)
