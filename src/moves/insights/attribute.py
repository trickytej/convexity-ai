"""Grounded LLM attribution of a price move to its likely cause(s).

Retrieves candidate evidence (news, corporate actions, sector/peer behavior,
podcast discussion), gives each a stable id, asks Claude to explain the move
citing ONLY those ids, then resolves the cited ids back to real sources (URLs /
transcript deep links). Nothing the model cites can be ungrounded.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import duckdb

from moves.config import Settings, get_settings
from moves.corpus import deep_link
from moves.insights import llm
from moves.insights.retrieve import Candidates, gather_candidates
from moves.providers import PolygonClient

_SYSTEM = """You explain why a stock made a significant price move, using ONLY the \
supplied evidence (news, earnings, corporate actions, sector-peer and broad-market \
index behavior, and investor-podcast discussion).

First determine SCOPE from the co-movement evidence:
- "market": the broad market/index moved similarly -> likely a MACRO catalyst \
(jobs/CPI/Fed/rates, geopolitics, risk-on/off).
- "sector": peers moved but the broad market did not -> a sector-specific driver.
- "company": mainly this name -> company-specific.

TIMING IS DECISIVE. Each news/earnings item is annotated with its timing vs the move \
window: "[Xm before move start]", "[during move]", or "[Xh after move ended (reaction, \
not cause)]". A genuine CATALYST must occur BEFORE or AT the move's start. An item \
dated AFTER the move ended cannot have caused it — at most it confirms/extends it. If \
your strongest evidence post-dates the move, do NOT claim it as the trigger: lower \
confidence and say the move PRECEDED the news (the real trigger is earlier, or not in \
the evidence).

Explain the move according to its HORIZON (given):
- SHORT-TERM (a day or two): identify the SPECIFIC catalyst and WHEN it hit \
(earnings/guidance, analyst rating/PT change, FDA/regulatory, M&A, lawsuit/short \
report, contract win, macro print) — and verify it precedes/coincides with the start.
- MEDIUM-TERM (weeks to months): explain the CHANGE IN EXPECTATIONS for the company or \
its industry (estimates, demand/pricing, competition, sentiment, sector re-rating).
- LONG-TERM (many months): briefly attribute to the structural/secular driver. Short.

Then fill:
- "summary": 1-3 specific sentences. START with WHEN the move happened (its date + UTC \
time window). Name the catalyst/driver, companies, numbers, AND state the timing \
relationship explicitly (e.g. "the move ran 10:00-14:00 UTC; the Intel earnings hit at \
14:11, after it ended, so it confirmed rather than triggered the move").
- "confidence": "high" | "medium" | "low" (lower it when the catalyst's timing or scope \
does not line up).
- "no_clear_catalyst": true if nothing convincingly explains the move (including when \
the only relevant items post-date it).
- "evidence": ranked supporting items; for each give the candidate "id" exactly as \
shown and a one-line "point" that includes its timing vs the move.

Rules: cite ONLY ids present in the candidate list; never invent facts, sources, or ids.

Output STRICT JSON only:
{"scope":"company","summary":"...","confidence":"medium","no_clear_catalyst":false,"evidence":[{"id":"N1","point":"..."}]}
No prose outside the JSON."""


def _fmt_dt(unix_seconds: int, with_time: bool = False) -> str:
    d = datetime.fromtimestamp(unix_seconds, tz=UTC)
    return d.strftime("%Y-%m-%d %H:%M UTC") if with_time else d.strftime("%Y-%m-%d")


def _naive_utc(unix_seconds: int) -> datetime:
    return datetime.fromtimestamp(unix_seconds, tz=UTC).replace(tzinfo=None)


def _fmt_dur(minutes: float) -> str:
    m = abs(minutes)
    if m < 90:
        return f"{m:.0f}m"
    h = m / 60
    return f"{h:.0f}h" if h < 48 else f"{h / 24:.0f}d"


def _timing_note(ts: datetime | None, start_dt: datetime, end_dt: datetime) -> str:
    """How an evidence timestamp relates to the move window (cause vs reaction)."""
    if ts is None:
        return ""
    if ts < start_dt:
        return f"{_fmt_dur((start_dt - ts).total_seconds() / 60)} before move start"
    if ts <= end_dt:
        return "during move"
    return f"{_fmt_dur((ts - end_dt).total_seconds() / 60)} after move ended (reaction, not cause)"


def headlines_from_news(
    news_items: list, start_dt: datetime, end_dt: datetime
) -> list[dict[str, Any]]:
    """Dedup + timing-tag a set of NewsItem-like objects for the 'headlines' panel."""
    out: list[dict[str, Any]] = []
    seen: set[Any] = set()
    for n in news_items:
        key = n.url or (n.published, n.title)
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "published": n.published,
                "publisher": n.publisher,
                "title": n.title,
                "url": n.url,
                "timing": _timing_note(n.published_ts, start_dt, end_dt),
            }
        )
    out.sort(key=lambda h: h["published"] or "", reverse=True)
    return out[:30]


def _earnings_ts(date_str: str, hour: str) -> datetime | None:
    """Approximate UTC time of an earnings release from its date + bmo/amc/dmh flag."""
    try:
        d = datetime.fromisoformat(date_str)
    except ValueError:
        return None
    h, m = {"bmo": (11, 30), "amc": (20, 30), "dmh": (17, 0)}.get(hour, (12, 0))
    return d.replace(hour=h, minute=m)


def _build_block(
    c: Candidates, start_dt: datetime, end_dt: datetime
) -> tuple[str, dict[str, dict[str, Any]]]:
    """Render candidate evidence with ids; return (prompt_block, id->source registry).

    News and earnings are annotated with their timing relative to the move window so
    the model (and the user) can tell a trigger (before the move) from a reaction
    (after it).
    """
    lines: list[str] = []
    registry: dict[str, dict[str, Any]] = {}

    for i, n in enumerate(c.news, 1):
        cid = f"N{i}"
        timing = _timing_note(n.published_ts, start_dt, end_dt)
        tag = f"  [{timing}]" if timing else ""
        lines.append(f"[{cid}] {n.published or '?'} ({n.publisher or 'news'}) {n.title}{tag}")
        registry[cid] = {
            "kind": "news",
            "label": n.publisher or "News",
            "url": n.url,
            "published": n.published,
            "timing": timing,
        }

    for i, n in enumerate(c.market_news, 1):
        cid = f"MN{i}"
        timing = _timing_note(n.published_ts, start_dt, end_dt)
        tag = f"  [{timing}]" if timing else ""
        lines.append(
            f"[{cid}] {n.published or '?'} MARKET news ({n.publisher or 'news'}) {n.title}{tag}"
        )
        registry[cid] = {
            "kind": "news",
            "label": f"Market: {n.publisher or 'news'}",
            "url": n.url,
            "published": n.published,
            "timing": timing,
        }

    for i, e in enumerate(c.earnings, 1):
        cid = f"E{i}"
        bits: list[str] = []
        if e.eps_actual is not None and e.eps_estimate is not None:
            verdict = "beat" if e.eps_actual >= e.eps_estimate else "miss"
            bits.append(f"EPS {e.eps_actual} vs est {e.eps_estimate} ({verdict})")
        if e.rev_actual is not None and e.rev_estimate is not None:
            verdict = "beat" if e.rev_actual >= e.rev_estimate else "miss"
            bits.append(f"rev {e.rev_actual:.0f} vs est {e.rev_estimate:.0f} ({verdict})")
        hour = f" {e.hour}" if e.hour else ""
        detail = (" — " + "; ".join(bits)) if bits else ""
        timing = _timing_note(_earnings_ts(e.date, e.hour), start_dt, end_dt)
        tag = f"  [{timing}]" if timing else ""
        lines.append(f"[{cid}] {e.date}{hour} EARNINGS RELEASE{detail}{tag}")
        registry[cid] = {
            "kind": "earnings",
            "label": f"Earnings {e.date}",
            "url": None,
            "published": e.date,
            "timing": timing,
        }

    for i, a in enumerate(c.corp_actions, 1):
        cid = f"C{i}"
        lines.append(f"[{cid}] {a.date} {a.detail}")
        registry[cid] = {
            "kind": "corporate_action",
            "label": a.detail,
            "url": None,
            "published": a.date,
        }

    for i, p in enumerate(c.podcast, 1):
        cid = f"P{i}"
        quote = (p.quote or "").strip().replace("\n", " ")
        if len(quote) > 200:
            quote = quote[:200] + "…"
        date = (p.published_at or "")[:10]
        speaker = p.speaker_name or ""
        lines.append(f'[{cid}] {p.show_slug} {date} {speaker}: {p.claim}  quote: "{quote}"')
        registry[cid] = {
            "kind": "podcast",
            "label": f"{p.show_slug} — {p.speaker_name or 'podcast'}",
            "url": deep_link(p),
            "published": date,
        }

    if c.peers:
        same = [p for p in c.peers if p.same_direction]
        detail = ", ".join(
            f"{p.symbol} {p.pct * 100:+.1f}%"
            for p in sorted(c.peers, key=lambda x: -abs(x.pct))[:6]
        )
        cid = "M1"
        lines.append(
            f"[{cid}] Sector ({c.peer_group}): {len(same)} of {len(c.peers)} peers moved "
            f"the same direction over the window — {detail}"
        )
        registry[cid] = {
            "kind": "market",
            "label": f"Sector co-movement ({c.peer_group})",
            "url": None,
            "published": None,
        }

    if c.benchmarks:
        detail = ", ".join(f"{b.symbol} {b.pct * 100:+.1f}%" for b in c.benchmarks)
        cid = "B1"
        lines.append(
            f"[{cid}] Broad market over the same window: {detail} "
            "(use to judge whether the move was market-wide/macro)"
        )
        registry[cid] = {
            "kind": "market",
            "label": "Broad-market index move",
            "url": None,
            "published": None,
        }

    block = "\n".join(lines) if lines else "(no candidate evidence found)"
    return block, registry


def attribute_move(
    con: duckdb.DuckDBPyConnection,
    *,
    symbol: str,
    timeframe: str,
    start_time: int,
    end_time: int,
    direction: str,
    pct_change: float,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Generate a grounded attribution payload for one move (no caching)."""
    settings = settings or get_settings()
    client = llm.get_client(settings)  # raises LLMError if no key

    span_days = (end_time - start_time) / 86400.0
    if span_days <= 3:
        horizon = "short"
    elif span_days <= 120:
        horizon = "medium"
    else:
        horizon = "long"

    if span_days < 2:
        span_label = f"~{(end_time - start_time) / 3600:.0f} hours"
    elif span_days < 90:
        span_label = f"~{span_days:.0f} days"
    else:
        span_label = f"~{span_days / 30:.0f} months"

    try:
        poly: PolygonClient | None = PolygonClient(settings.polygon_api_key)
    except Exception:
        poly = None

    candidates = gather_candidates(
        con,
        poly,
        symbol=symbol,
        timeframe=timeframe,
        start_time=start_time,
        end_time=end_time,
        direction=direction,
        horizon=horizon,
    )
    start_dt = _naive_utc(start_time)
    end_dt = _naive_utc(end_time)
    block, registry = _build_block(candidates, start_dt, end_dt)

    horizon_label = {
        "short": "SHORT-TERM — identify the specific news catalyst and its timing",
        "medium": "MEDIUM-TERM — explain the change in expectations (company/industry)",
        "long": "LONG-TERM — structural/TAM driver (keep brief)",
    }[horizon]
    with_time = horizon == "short"
    user = (
        f"MOVE: {symbol} {direction} {pct_change * 100:+.1f}% over {span_label} "
        f"[{horizon_label}] from {_fmt_dt(start_time, with_time)} to "
        f"{_fmt_dt(end_time, with_time)}.\n\n"
        f"CANDIDATE EVIDENCE:\n{block}"
    )

    # Deterministic anchor: flag earnings near the window, WITH their timing, so the
    # model only treats them as the cause if they actually preceded the move.
    window_lo = (start_dt.date() - timedelta(days=1)).isoformat()
    window_hi = end_dt.date().isoformat()
    earnings_in_window = [e for e in candidates.earnings if window_lo <= e.date <= window_hi]
    if earnings_in_window:
        parts = []
        for e in earnings_in_window:
            timing = _timing_note(_earnings_ts(e.date, e.hour), start_dt, end_dt)
            parts.append(f"{e.date} {e.hour}".strip() + (f" ({timing})" if timing else ""))
        user += (
            f"\n\nNOTE: earnings near this window: {'; '.join(parts)}. Weigh it as the cause "
            "ONLY if it preceded the move; if it followed, treat it as a reaction and explain "
            "the beat/miss/guidance accordingly."
        )

    summary, confidence, no_catalyst, scope = "", "low", True, ""
    evidence: list[dict[str, Any]] = []
    try:
        raw = llm.complete(
            client,
            system=_SYSTEM,
            user=user,
            model=settings.anthropic_model,
            max_tokens=1400,
            thinking=settings.anthropic_thinking,
        )
        data = llm.extract_json(raw)
    except llm.LLMError:
        data = {}

    if isinstance(data, dict):
        summary = (data.get("summary") or "").strip()
        confidence = (data.get("confidence") or "low").strip().lower()
        if confidence not in {"high", "medium", "low"}:
            confidence = "low"
        scope = (data.get("scope") or "").strip().lower()
        if scope not in {"market", "sector", "company", "mixed"}:
            scope = ""
        no_catalyst = bool(data.get("no_clear_catalyst", not summary))
        for item in data.get("evidence") or []:
            if not isinstance(item, dict):
                continue
            cid = str(item.get("id", "")).strip()
            src = registry.get(cid)
            if not src:
                continue  # drop any hallucinated id
            evidence.append(
                {
                    "id": cid,
                    "kind": src["kind"],
                    "point": (item.get("point") or "").strip(),
                    "label": src["label"],
                    "url": src["url"],
                    "published": src["published"],
                    "timing": src.get("timing", ""),
                }
            )

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "start_time": start_time,
        "end_time": end_time,
        "direction": direction,
        "pct_change": pct_change,
        "horizon": horizon,
        "scope": scope,
        "summary": summary,
        "confidence": confidence,
        "no_clear_catalyst": no_catalyst,
        "evidence": evidence,
        "sources_considered": {
            "news": len(candidates.news),
            "earnings": len(candidates.earnings),
            "podcast": len(candidates.podcast),
            "corporate_action": len(candidates.corp_actions),
            "peers": len(candidates.peers),
        },
        "headlines": headlines_from_news(
            candidates.news + candidates.market_news, start_dt, end_dt
        ),
        "model": settings.anthropic_model,
        "generated_at": datetime.now(UTC).isoformat(),
    }
