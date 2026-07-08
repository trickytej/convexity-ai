"""Step 4: aggregate per-episode nuggets into a weekly, classified report.

MVP approach (no extra model calls): pull the week's nuggets, canonicalize their
sector tags, group into sections, rank by signal_score, and surface cross-show
corroboration (a company discussed on several shows is a strong importance cue).
"""

from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from .store import repo

# Canonicalize the free-text sector tags the LLM produces.
_SECTOR_CANON = {
    "ai": "AI",
    "artificial intelligence": "AI",
    "ml": "AI",
    "machine learning": "AI",
    "llm": "AI",
    "semiconductors": "Semiconductors",
    "semis": "Semiconductors",
    "chips": "Semiconductors",
    "hardware": "Semiconductors",
    "infrastructure": "Infrastructure",
    "cloud": "Infrastructure",
    "datacenter": "Infrastructure",
    "data centers": "Infrastructure",
    "data center": "Infrastructure",
    "compute": "Infrastructure",
    "networking": "Infrastructure",
    "software": "Software",
    "saas": "Software",
    "developer tools": "Software",
    "markets": "Markets",
    "public markets": "Markets",
    "macro": "Markets",
    "finance": "Markets",
    "economics": "Markets",
    "venture": "Venture",
    "vc": "Venture",
    "startups": "Venture",
    "private markets": "Venture",
    "energy": "Energy",
    "power": "Energy",
    "nuclear": "Energy",
    "biotech": "Biotech",
    "life sciences": "Biotech",
    "pharmaceuticals": "Biotech",
    "pharma": "Biotech",
    "healthcare": "Biotech",
    "biology": "Biotech",
    "crypto": "Crypto",
    "defense": "Defense",
    "space": "Space",
    "robotics": "Robotics",
    "consumer": "Consumer",
    "technology": "Technology",
    "tech": "Technology",
}


def canon_sector(tag: str) -> str:
    key = (tag or "").strip().lower()
    if not key:
        return "Other"
    return _SECTOR_CANON.get(key, tag.strip().title())


@dataclass
class ReportNugget:
    id: int
    episode_id: int
    show_slug: str
    episode_title: str
    published_at: str | None
    type: str
    claim: str
    quote: str | None
    speaker_name: str | None
    start_ms: int | None
    signal_score: float
    quote_verified: bool
    triage: str
    sectors: list[str]
    primary_sector: str | None
    companies: list[str]
    corroboration_shows: int = 1


@dataclass
class ReportSection:
    sector: str
    count: int
    nuggets: list[ReportNugget]


@dataclass
class EntityBuzz:
    name: str
    shows: list[str]
    nugget_count: int


@dataclass
class WeeklyReport:
    since: str | None
    until: str
    days: int
    stats: dict
    sections: list[ReportSection]
    top_entities: list[EntityBuzz]


def _parse_json(raw, default):
    if not raw:
        return default
    try:
        value = json.loads(raw)
        return value if value is not None else default
    except (json.JSONDecodeError, TypeError):
        return default


def _companies(entities: dict | None) -> list[str]:
    if not isinstance(entities, dict):
        return []
    items = entities.get("companies")
    return [c for c in items if isinstance(c, str) and c.strip()] if isinstance(items, list) else []


def build_weekly_report(
    conn: sqlite3.Connection,
    days: int = 7,
    *,
    since_iso: str | None = None,
    until_iso: str | None = None,
    min_signal: float = 0.0,
    per_section_limit: int | None = None,
    triage: str | None = None,
    include_tweets: bool = False,
) -> WeeklyReport:
    until = datetime.now(timezone.utc)
    since = until - timedelta(days=days) if days else None
    if since_iso:
        since = datetime.fromisoformat(since_iso).replace(tzinfo=timezone.utc)
    if until_iso:
        until = datetime.fromisoformat(until_iso).replace(tzinfo=timezone.utc)
    rows = repo.nuggets_in_window(
        conn, since=since, until=until, min_signal=min_signal, include_tweets=include_tweets
    )

    nuggets: list[ReportNugget] = []
    company_shows: dict[str, set[str]] = defaultdict(set)
    company_display: dict[str, str] = {}
    company_count: dict[str, int] = defaultdict(int)

    for r in rows:
        entities = _parse_json(r["entities"], {})
        raw_sectors = _parse_json(r["sectors"], [])
        sectors: list[str] = []
        for tag in raw_sectors if isinstance(raw_sectors, list) else []:
            c = canon_sector(tag)
            if c not in sectors:
                sectors.append(c)
        companies = _companies(entities)

        nuggets.append(
            ReportNugget(
                id=r["id"],
                episode_id=r["episode_id"],
                show_slug=r["show_slug"],
                episode_title=r["episode_title"],
                published_at=r["episode_published_at"],
                type=r["type"],
                claim=r["claim"],
                quote=r["quote"],
                speaker_name=r["speaker_name"],
                start_ms=r["start_ms"],
                signal_score=r["signal_score"],
                quote_verified=bool(r["quote_verified"]),
                triage=r["triage"],
                sectors=sectors,
                primary_sector=(r["primary_sector"] if "primary_sector" in r.keys() else None),
                companies=companies,
            )
        )
        for company in companies:
            key = company.lower()
            company_shows[key].add(r["show_slug"])
            company_count[key] += 1
            company_display.setdefault(key, company)

    # Cross-show corroboration: how many distinct shows mention a nugget's company.
    for n in nuggets:
        best = 1
        for company in n.companies:
            best = max(best, len(company_shows[company.lower()]))
        n.corroboration_shows = best

    # Triage counts over the whole window; sections over the (optionally) filtered set.
    # Tweets (show "x") bypass the triage filter: nuggets_in_window already
    # restricted them to curator-kept ones, and keep/kill is their triage.
    triage_counts: dict[str, int] = defaultdict(int)
    for n in nuggets:
        triage_counts[n.triage] += 1
    visible = [
        n for n in nuggets
        if triage is None or n.triage == triage or n.show_slug == "x"
    ]

    # Group by the controlled primary_sector; fall back to the legacy first-tag.
    by_sector: dict[str, list[ReportNugget]] = defaultdict(list)
    for n in visible:
        if n.show_slug == "x":
            primary = "From X"  # kept tweets get their own report section
        else:
            primary = n.primary_sector or (n.sectors[0] if n.sectors else "Other")
        by_sector[primary].append(n)

    sections: list[ReportSection] = []
    for sector, items in by_sector.items():
        items.sort(key=lambda x: (-x.signal_score, -x.corroboration_shows))
        capped = items[:per_section_limit] if per_section_limit else items
        sections.append(ReportSection(sector=sector, count=len(items), nuggets=capped))
    sections.sort(key=lambda s: -s.count)

    top_entities = [
        EntityBuzz(name=company_display[k], shows=sorted(v), nugget_count=company_count[k])
        for k, v in company_shows.items()
    ]
    top_entities.sort(key=lambda e: (-len(e.shows), -e.nugget_count))
    top_entities = [e for e in top_entities if len(e.shows) >= 2][:20]

    type_counts: dict[str, int] = defaultdict(int)
    for n in visible:
        type_counts[n.type] += 1

    stats = {
        "nuggets": len(visible),
        "window_nuggets": len(nuggets),
        "episodes": len({n.episode_id for n in visible}),
        "shows": len({n.show_slug for n in visible}),
        "verified": sum(1 for n in visible if n.quote_verified),
        "by_type": dict(type_counts),
        "triage": dict(triage_counts),
    }

    return WeeklyReport(
        since=since.isoformat() if since else None,
        until=until.isoformat(),
        days=days,
        stats=stats,
        sections=sections,
        top_entities=top_entities,
    )
