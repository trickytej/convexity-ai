"""Step 6: generate a synthesized, sector-by-sector weekly report from the insights.

Distinct from report.py (which aggregates raw nuggets for the "insights" view):
this condenses those nuggets into a tight narrative digest via the LLM, keeping a
source citation (nugget -> transcript) behind every bullet so it stays auditable.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from .config import Settings, get_settings
from .report import ReportNugget, ReportSection, build_weekly_report
from .store import repo
from .transcribe import llm

_MAX_NUGGETS_PER_SECTION = 40

_SECTION_SYSTEM = """\
You write ONE section of a weekly investment research digest, synthesized from \
extracted podcast insights ("nuggets"). Produce a TIGHT section: a short headline \
and 3-5 synthesized bullets. Merge repetitive points, lead with the most important, \
weave in specific numbers and named companies/people, attribute to speakers/shows \
where useful, and explicitly flag disagreements or contrarian takes. Use ONLY the \
provided nuggets - do not invent facts. For each bullet, cite the nugget id(s) it \
draws from.

Output STRICT JSON only:
{"headline": "...", "bullets": [{"text": "...", "nugget_ids": [1, 2]}], "watch_items": ["..."]}
No prose outside the JSON."""

_EXEC_SYSTEM = """\
You write the executive summary of a weekly investment research digest for AI, \
semiconductors, technology, and markets. Given the section headlines and the \
most-discussed companies, write 2-4 specific, high-signal sentences on what mattered \
most this week. Output STRICT JSON only: {"exec_summary": "..."}"""


def _week_key(until_iso: str) -> str:
    dt = datetime.fromisoformat(until_iso)
    year, week, _ = dt.isocalendar()
    return f"{year}-W{week:02d}"


def _nugget_line(n: ReportNugget) -> str:
    quote = (n.quote or "").strip().replace("\n", " ")
    if len(quote) > 280:
        quote = quote[:280] + "…"
    return (
        f"[{n.id}] ({n.type}, signal {n.signal_score:.2f}, "
        f"{n.speaker_name or 'unknown'} on {n.show_slug}) {n.claim}\n"
        f'    quote: "{quote}"'
    )


def _sources_for(nugget_ids: list, lookup: dict[int, ReportNugget]) -> list[dict]:
    sources: list[dict] = []
    seen: set[int] = set()
    for raw in nugget_ids or []:
        try:
            nid = int(raw)
        except (TypeError, ValueError):
            continue
        n = lookup.get(nid)
        if n is None or nid in seen:
            continue
        seen.add(nid)
        sources.append(
            {
                "nugget_id": n.id,
                "episode_id": n.episode_id,
                "show_slug": n.show_slug,
                "start_ms": n.start_ms,
                "speaker_name": n.speaker_name,
            }
        )
    return sources


def _synthesize_section(client, model: str, section: ReportSection) -> dict:
    nuggets = section.nuggets[:_MAX_NUGGETS_PER_SECTION]
    lookup = {n.id: n for n in nuggets}
    user = (
        f"Sector: {section.sector}\n\nNuggets:\n"
        + "\n".join(_nugget_line(n) for n in nuggets)
    )
    try:
        raw = llm.complete(
            client, system=_SECTION_SYSTEM, user=user, model=model, max_tokens=2048
        )
        data = llm.extract_json(raw)
    except llm.LLMError:
        data = {}

    headline = (data.get("headline") if isinstance(data, dict) else None) or section.sector
    bullets_out: list[dict] = []
    raw_bullets = data.get("bullets") if isinstance(data, dict) else None
    for b in raw_bullets or []:
        if not isinstance(b, dict):
            continue
        text = (b.get("text") or "").strip()
        if not text:
            continue
        bullets_out.append({"text": text, "sources": _sources_for(b.get("nugget_ids", []), lookup)})

    watch_items = []
    if isinstance(data, dict) and isinstance(data.get("watch_items"), list):
        watch_items = [str(w).strip() for w in data["watch_items"] if str(w).strip()]

    return {
        "sector": section.sector,
        "count": section.count,
        "headline": headline,
        "bullets": bullets_out,
        "watch_items": watch_items,
    }


def _synthesize_exec(client, model: str, sections: list[dict], top_entities: list) -> str:
    headlines = "\n".join(f"- {s['sector']}: {s['headline']}" for s in sections)
    entities = ", ".join(f"{e.name} ({len(e.shows)} shows)" for e in top_entities[:10])
    user = f"Section headlines:\n{headlines}\n\nMost-discussed companies: {entities}"
    try:
        raw = llm.complete(
            client, system=_EXEC_SYSTEM, user=user, model=model, max_tokens=512
        )
        data = llm.extract_json(raw)
        if isinstance(data, dict) and isinstance(data.get("exec_summary"), str):
            return data["exec_summary"].strip()
    except llm.LLMError:
        pass
    return ""


def generate_report(
    conn: sqlite3.Connection,
    days: int = 7,
    *,
    per_section_limit: int = 15,
    settings: Settings | None = None,
) -> dict:
    """Generate, store, and return the synthesized weekly report.

    Hybrid feed: synthesize triaged-relevant nuggets if any exist this week,
    otherwise the top-N by signal per sector.
    """
    settings = settings or get_settings()
    client = llm.get_client(settings)  # raises LLMError if no key
    model = settings.anthropic_model

    base = build_weekly_report(conn, days=days)
    relevant_n = int((base.stats.get("triage") or {}).get("relevant", 0) or 0)
    if relevant_n > 0:
        agg = build_weekly_report(conn, days=days, triage="relevant")
        source_mode = "relevant"
    else:
        agg = build_weekly_report(conn, days=days, per_section_limit=per_section_limit)
        source_mode = "top_signal"

    sections_out = [
        _synthesize_section(client, model, sec) for sec in agg.sections if sec.nuggets
    ]
    exec_summary = _synthesize_exec(client, model, sections_out, agg.top_entities)

    payload = {
        "exec_summary": exec_summary,
        "sections": sections_out,
        "top_entities": [
            {"name": e.name, "shows": e.shows, "nugget_count": e.nugget_count}
            for e in agg.top_entities
        ],
        "stats": agg.stats,
        "source_mode": source_mode,
    }
    week_key = _week_key(agg.until)
    repo.upsert_report(conn, week_key, agg.since, agg.until, days, source_mode, model, payload)

    return {
        "week_key": week_key,
        "since": agg.since,
        "until": agg.until,
        "days": days,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        **payload,
    }
