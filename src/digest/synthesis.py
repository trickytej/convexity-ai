"""Step 6: generate a synthesized, sector-by-sector weekly report from the insights.

Distinct from report.py (which aggregates raw nuggets for the "insights" view):
this condenses those nuggets into a tight narrative digest via the LLM, keeping a
source citation (nugget -> transcript) behind every bullet so it stays auditable.
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from datetime import datetime, timezone

from .config import Settings, get_settings
from .report import ReportNugget, ReportSection, build_weekly_report
from .store import repo
from .transcribe import llm

# Opus 4.8 + 1M context can take far more context than Sonnet, so feed generously.
_MAX_NUGGETS_PER_SECTION = 150
CONTEXT_1M_BETA = "context-1m-2025-08-07"


def _synth_complete(client, settings: Settings, system: str, user: str, max_tokens: int) -> str:
    """Run a synthesis completion on the configured synthesis model (Opus 4.8 by
    default) with adaptive ("max") thinking + the 1M-context beta when enabled."""
    return llm.complete(
        client,
        system=system,
        user=user,
        model=settings.synthesis_model,
        max_tokens=max_tokens,
        thinking=settings.synthesis_thinking,
        betas=[CONTEXT_1M_BETA] if settings.synthesis_context_1m else None,
        stream=True,
    )


_REPORT_SYSTEM = """\
You write a weekly investment research digest from extracted podcast insights \
("nuggets"), already grouped by sector. In a SINGLE pass over the whole week, produce:
1. "exec_summary": 2-4 specific, high-signal sentences on what mattered most this \
week ACROSS sectors (draw cross-sector connections).
2. "sections": for EACH sector provided, an object with a short "headline", 3-6 \
synthesized "bullets", and optional "watch_items".

Merge repetition, lead with the most important, weave in specific numbers and named \
companies/people, attribute to speakers, and flag disagreements/contrarian takes. \
Use ONLY the provided nuggets - do not invent facts. For each bullet, cite the nugget \
id(s) it draws from. Cover every sector you are given.

Output STRICT JSON only:
{"exec_summary": "...", "sections": [{"sector": "<exact sector name>", "headline": "...", "bullets": [{"text": "...", "nugget_ids": [1, 2]}], "watch_items": ["..."]}]}
No prose outside the JSON."""


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


def _synthesize_report(client, settings: Settings, agg) -> tuple[str, list[dict]]:
    """Single whole-week pass: feed every sector's nuggets in one Opus-1M call and
    return (exec_summary, sections). Globally coherent + far fewer calls than per-sector.
    """
    lookup: dict[int, ReportNugget] = {}
    counts: dict[str, int] = {}
    blocks: list[str] = []
    for sec in agg.sections:
        if not sec.nuggets:
            continue
        counts[sec.sector] = sec.count
        blocks.append(f"### {sec.sector} ({sec.count} insights)")
        for n in sec.nuggets[:_MAX_NUGGETS_PER_SECTION]:
            lookup[n.id] = n
            blocks.append(_nugget_line(n))
    if not blocks:
        return "", []

    user = "Sectors and their insights:\n\n" + "\n".join(blocks)
    try:
        raw = _synth_complete(client, settings, _REPORT_SYSTEM, user, max_tokens=32000)
        data = llm.extract_json(raw)
    except llm.LLMError:
        return "", []
    if not isinstance(data, dict):
        return "", []

    exec_summary = (data.get("exec_summary") or "").strip()
    sections_out: list[dict] = []
    for s in data.get("sections") or []:
        if not isinstance(s, dict):
            continue
        sector = (s.get("sector") or "").strip()
        headline = (s.get("headline") or "").strip()
        if not sector or not headline:
            continue
        bullets = []
        for b in s.get("bullets") or []:
            if not isinstance(b, dict):
                continue
            text = (b.get("text") or "").strip()
            if not text:
                continue
            bullets.append({"text": text, "sources": _sources_for(b.get("nugget_ids", []), lookup)})
        watch_items = (
            [str(w).strip() for w in s["watch_items"] if str(w).strip()]
            if isinstance(s.get("watch_items"), list)
            else []
        )
        sections_out.append(
            {
                "sector": sector,
                "count": counts.get(sector, len(bullets)),
                "headline": headline,
                "bullets": bullets,
                "watch_items": watch_items,
            }
        )
    return exec_summary, sections_out


def generate_report(
    conn: sqlite3.Connection,
    days: int = 7,
    *,
    per_section_limit: int = 60,
    settings: Settings | None = None,
) -> dict:
    """Generate, store, and return the synthesized weekly report.

    Hybrid feed: synthesize triaged-relevant nuggets if any exist this week,
    otherwise the top-N by signal per sector.
    """
    settings = settings or get_settings()
    client = llm.get_client(settings)  # raises LLMError if no key
    base = build_weekly_report(conn, days=days)
    relevant_n = int((base.stats.get("triage") or {}).get("relevant", 0) or 0)
    if relevant_n > 0:
        agg = build_weekly_report(conn, days=days, triage="relevant")
        source_mode = "relevant"
    else:
        agg = build_weekly_report(conn, days=days, per_section_limit=per_section_limit)
        source_mode = "top_signal"

    exec_summary, sections_out = _synthesize_report(client, settings, agg)

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
    repo.upsert_report(
        conn, week_key, agg.since, agg.until, days, source_mode, settings.synthesis_model, payload
    )

    return {
        "week_key": week_key,
        "since": agg.since,
        "until": agg.until,
        "days": days,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        **payload,
    }


# --- per-episode digest (TMTB-style: themes + quotes + stock read-through) ---

_EPISODE_THEME_SYSTEM = """\
You create a per-episode research digest from extracted insights ("nuggets") of ONE \
podcast episode. Cluster the nuggets into 4-8 THEMES capturing the episode's key \
ideas. For each theme provide: a short "headline"; a one-line "takeaway" (your sharp \
editorial read of why it matters); and 3-6 synthesized "points". Merge repetition, \
lead with the most important, weave in specific numbers and named entities, and \
attribute to the speaker. Use ONLY the provided nuggets - do not invent. For each \
point, cite the nugget id(s) it draws from.

Output STRICT JSON only:
{"themes": [{"headline": "...", "takeaway": "...", "points": [{"text": "...", "nugget_ids": [1, 2]}]}]}
No prose outside the JSON."""

_EPISODE_STOCKS_SYSTEM = """\
You write the "stock read-through" of a per-episode podcast digest for investors. \
For each notable company discussed, output: "company" (name); "stance" - STRICTLY \
one of "owned" (the speaker explicitly states they or their fund own/invested in it), \
"bullish", "bearish", or "mentioned" (neutral/just discussed); a one-line "summary" \
of what was said; and the supporting "nugget_ids". Base stance ONLY on what the text \
supports - if ownership is not explicitly stated, do not use "owned". Include only \
companies with substantive discussion.

Output STRICT JSON only:
{"stocks": [{"company": "...", "stance": "owned|bullish|bearish|mentioned", "summary": "...", "nugget_ids": [1]}]}
No prose outside the JSON."""

_VALID_STANCE = {"owned", "bullish", "bearish", "mentioned"}


def _ep_nugget_line(n) -> str:
    quote = (n.quote or "").strip().replace("\n", " ")
    if len(quote) > 240:
        quote = quote[:240] + "…"
    return f'[{n.id}] ({n.type}, {n.speaker_name or "unknown"}) {n.claim}\n    quote: "{quote}"'


def _resolve_ep_sources(nugget_ids, lookup, fuller) -> tuple[list[dict], str | None]:
    sources: list[dict] = []
    primary_quote: str | None = None
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
                "start_ms": n.start_ms,
                "speaker_name": n.speaker_name,
            }
        )
        if primary_quote is None:
            primary_quote = fuller(n)
    return sources, primary_quote


def _synthesize_themes(client, settings: Settings, episode, nuggets, lookup, fuller) -> list[dict]:
    user = f"Episode: {episode.title}\n\nNuggets:\n" + "\n".join(
        _ep_nugget_line(n) for n in nuggets
    )
    try:
        raw = _synth_complete(client, settings, _EPISODE_THEME_SYSTEM, user, max_tokens=24000)
        data = llm.extract_json(raw)
    except llm.LLMError:
        data = {}

    themes_out: list[dict] = []
    for t in (data.get("themes") if isinstance(data, dict) else None) or []:
        if not isinstance(t, dict):
            continue
        headline = (t.get("headline") or "").strip()
        if not headline:
            continue
        points = []
        for p in t.get("points") or []:
            if not isinstance(p, dict):
                continue
            text = (p.get("text") or "").strip()
            if not text:
                continue
            sources, quote = _resolve_ep_sources(p.get("nugget_ids", []), lookup, fuller)
            points.append({"text": text, "quote": quote, "sources": sources})
        themes_out.append(
            {"headline": headline, "takeaway": (t.get("takeaway") or "").strip(), "points": points}
        )
    return themes_out


def _synthesize_stocks(client, settings: Settings, episode, nuggets, lookup, fuller) -> list[dict]:
    by_company: dict[str, list] = defaultdict(list)
    for n in nuggets:
        for co in (n.entities or {}).get("companies", []) or []:
            if isinstance(co, str) and co.strip():
                by_company[co.strip()].append(n)
    ranked = sorted(by_company.items(), key=lambda kv: -len(kv[1]))[:15]
    if not ranked:
        return []

    lines: list[str] = []
    for company, ns in ranked:
        lines.append(f"## {company}")
        for n in ns[:4]:
            q = (n.quote or "").strip().replace("\n", " ")
            if len(q) > 200:
                q = q[:200] + "…"
            lines.append(f'  [{n.id}] {n.claim}  quote: "{q}"')
    user = f"Episode: {episode.title}\n\nCompanies and related insights:\n" + "\n".join(lines)

    try:
        raw = _synth_complete(client, settings, _EPISODE_STOCKS_SYSTEM, user, max_tokens=16000)
        data = llm.extract_json(raw)
    except llm.LLMError:
        data = {}

    stocks_out: list[dict] = []
    for s in (data.get("stocks") if isinstance(data, dict) else None) or []:
        if not isinstance(s, dict):
            continue
        company = (s.get("company") or "").strip()
        if not company:
            continue
        stance = (s.get("stance") or "mentioned").strip().lower()
        if stance not in _VALID_STANCE:
            stance = "mentioned"
        sources, _ = _resolve_ep_sources(s.get("nugget_ids", []), lookup, fuller)
        stocks_out.append(
            {"company": company, "stance": stance, "summary": (s.get("summary") or "").strip(), "sources": sources}
        )
    return stocks_out


def generate_episode_digest(
    conn: sqlite3.Connection, episode_id: int, *, settings: Settings | None = None
) -> dict:
    """Generate, store, and return a TMTB-style per-episode digest."""
    settings = settings or get_settings()
    client = llm.get_client(settings)  # raises LLMError if no key

    episode = repo.get_episode(conn, episode_id)
    if episode is None:
        raise ValueError("episode not found")
    nuggets = repo.list_nuggets(conn, episode_id=episode_id)
    if not nuggets:
        raise ValueError("no nuggets for this episode (run `digest insights` first)")

    # Fuller quotes: map a nugget's start_ms back to its full transcript segment.
    seg_text: dict[int, str] = {}
    transcript = repo.get_transcript_for_episode(conn, episode_id)
    if transcript is not None:
        for seg in repo.get_segments(conn, transcript["id"]):
            if seg.start_ms is not None:
                seg_text[seg.start_ms] = seg.text

    def fuller(n) -> str | None:
        if n.start_ms is not None and n.start_ms in seg_text:
            return seg_text[n.start_ms]
        return n.quote

    lookup = {n.id: n for n in nuggets}
    themes = _synthesize_themes(client, settings, episode, nuggets[:200], lookup, fuller)
    stocks = _synthesize_stocks(client, settings, episode, nuggets, lookup, fuller)

    payload = {
        "episode_id": episode_id,
        "title": episode.title,
        "show_slug": episode.show_slug,
        "nugget_count": len(nuggets),
        "themes": themes,
        "stocks": stocks,
    }
    repo.upsert_episode_digest(conn, episode_id, settings.synthesis_model, payload)
    return {"generated_at": datetime.now(timezone.utc).isoformat(), **payload}
