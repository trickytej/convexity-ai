"""Agentic move attribution (the "Investigate" deep path).

An Opus tool-use loop that forms hypotheses about why a move happened, then pulls
real evidence about ANY entity it deems relevant — the stock itself, a peer whose
earnings dragged the group, a supplier/customer, a sector/index ETF, rates, or the
podcast corpus — verifies timing, and concludes. Every cited item is a real source
returned by a tool, so the conclusion stays auditable (unlike a free-form narrative).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any

import duckdb
import numpy as np

from moves.config import Settings, get_settings
from moves.corpus import deep_link, find_mentions
from moves.ingest import backfill
from moves.insights import llm
from moves.insights.attribute import _earnings_ts, _fmt_dt, _naive_utc, _timing_note
from moves.providers import FinnhubClient, PolygonClient, finnhub_available
from moves.store import get_bars

_AGENT_SYSTEM = """You are a markets analyst investigating WHY a specific stock made a \
significant price move. You have tools to pull real evidence about ANY company or \
index — not just the stock in question. Find the true, grounded cause.

METHOD:
1. Form 2-4 hypotheses for THIS move given its size, direction, timing and sector — \
e.g. the stock's own news/earnings; a PEER's earnings dragging the whole group; a \
supplier (e.g. TSM) or key customer; a macro print (CPI/Fed/jobs); a sector or \
commodity move; broad risk-on/off.
2. TEST them with tools. Don't stop at the stock itself: pull news/earnings for the \
most likely OTHER entities too, and use get_returns on several tickers (peers, \
suppliers, sector ETFs like SMH, indices SPY/QQQ, TLT for rates) to see what actually \
co-moved.
3. TIMING IS DECISIVE: a cause must occur BEFORE or AT the move's start. Items dated \
AFTER the move ended are reactions, not triggers (each news/earnings item is \
timing-tagged). 
4. Iterate until you can name a grounded cause, or are confident none is present.

Then call `conclude`. The summary must START with the move's date + UTC time window, \
name the specific driver/companies/numbers, and state the timing relationship. Cite \
ONLY ids returned by tools. Be rigorous and honest: if the only relevant items \
post-date the move, say the trigger isn't established. Never invent sources or facts."""


def _tool_schemas() -> list[dict[str, Any]]:
    return [
        {
            "name": "get_news",
            "description": (
                "Ticker-tagged news headlines around the move window, each annotated "
                "with its timing vs the move (before/during/after). Use for the stock "
                "AND for peers/suppliers/customers you suspect."
            ),
            "input_schema": {
                "type": "object",
                "properties": {"ticker": {"type": "string"}},
                "required": ["ticker"],
            },
        },
        {
            "name": "get_returns",
            "description": (
                "Percent return of one or more tickers over the exact move window — to "
                "see what co-moved. Pass peers, suppliers (TSM), sector ETFs (SMH), "
                "indices (SPY, QQQ), or rates (TLT)."
            ),
            "input_schema": {
                "type": "object",
                "properties": {"tickers": {"type": "array", "items": {"type": "string"}}},
                "required": ["tickers"],
            },
        },
        {
            "name": "get_earnings",
            "description": (
                "Earnings releases (date, EPS/revenue beat/miss, timing vs the move) for "
                "a ticker near the window. Check the stock AND peers."
            ),
            "input_schema": {
                "type": "object",
                "properties": {"ticker": {"type": "string"}},
                "required": ["ticker"],
            },
        },
        {
            "name": "search_podcasts",
            "description": "Investor-podcast discussion mentioning a ticker near the window.",
            "input_schema": {
                "type": "object",
                "properties": {"ticker": {"type": "string"}},
                "required": ["ticker"],
            },
        },
        {
            "name": "conclude",
            "description": "Submit the final grounded attribution and stop.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "scope": {"type": "string", "enum": ["market", "sector", "company", "mixed"]},
                    "horizon": {"type": "string", "enum": ["short", "medium", "long"]},
                    "summary": {"type": "string"},
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                    "no_clear_catalyst": {"type": "boolean"},
                    "evidence": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "point": {"type": "string"},
                            },
                            "required": ["id", "point"],
                        },
                    },
                },
                "required": ["scope", "summary", "confidence", "no_clear_catalyst", "evidence"],
            },
        },
    ]


@dataclass
class ToolContext:
    con: duckdb.DuckDBPyConnection
    poly: PolygonClient | None
    start_time: int
    end_time: int
    start_dt: datetime
    end_dt: datetime
    registry: dict[str, dict[str, Any]] = field(default_factory=dict)
    trace: list[str] = field(default_factory=list)
    _seq: int = 0

    def _nid(self, prefix: str) -> str:
        self._seq += 1
        return f"{prefix}{self._seq}"

    def _ensure_bars(self, ticker: str):
        df = get_bars(self.con, ticker, "day")
        if df.empty and self.poly is not None:
            start = (date.today() - timedelta(days=420)).isoformat()
            try:
                backfill(self.con, self.poly, [ticker], "day", start, date.today().isoformat())
                df = get_bars(self.con, ticker, "day")
            except Exception:
                pass
        return df

    def get_news(self, ticker: str) -> str:
        ticker = ticker.upper()
        if self.poly is None:
            return json.dumps({"error": "news unavailable"})
        lower = (self.start_dt - timedelta(days=2)).date().isoformat()
        upper = (self.end_dt + timedelta(days=1)).date().isoformat()
        try:
            raw = self.poly.get_news(ticker, since=lower, until=upper, limit=12)
        except Exception:
            raw = []
        items = []
        for n in raw:
            ts = n.get("published_utc")
            tid = self._nid("N")
            timing = _timing_note(ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts,
                                  self.start_dt, self.end_dt)
            self.registry[tid] = {
                "kind": "news",
                "label": n.get("publisher") or "News",
                "title": n.get("title"),
                "url": n.get("article_url"),
                "published": str(ts)[:16] if ts is not None else None,
                "timing": timing,
            }
            items.append(
                {
                    "id": tid,
                    "published": str(ts)[:16] if ts is not None else None,
                    "publisher": n.get("publisher"),
                    "title": n.get("title"),
                    "timing": timing,
                }
            )
        self.trace.append(f"get_news({ticker}) → {len(items)}")
        return json.dumps({"ticker": ticker, "count": len(items), "items": items})

    def get_returns(self, tickers: list[str]) -> str:
        out = []
        for t in tickers[:12]:
            t = t.upper()
            df = self._ensure_bars(t)
            pct: float | None = None
            if not df.empty:
                times = df["ts"].astype("datetime64[s]").astype("int64").to_numpy()
                closes = df["close"].to_numpy()
                idx = np.where((times >= self.start_time) & (times <= self.end_time))[0]
                if idx.size >= 2:
                    pct = float(closes[idx[-1]] / closes[idx[0]] - 1.0)
            tid = self._nid("R")
            self.registry[tid] = {
                "kind": "market",
                "label": f"{t} return over window",
                "url": None,
                "published": None,
                "timing": "",
            }
            out.append({"id": tid, "ticker": t, "pct": round(pct, 4) if pct is not None else None})
        self.trace.append(f"get_returns({', '.join(t.upper() for t in tickers[:12])})")
        return json.dumps({"items": out})

    def get_earnings(self, ticker: str) -> str:
        ticker = ticker.upper()
        if not finnhub_available():
            return json.dumps({"ticker": ticker, "items": [], "note": "no finnhub key"})
        lo = (self.start_dt - timedelta(days=10)).date().isoformat()
        hi = (self.end_dt + timedelta(days=2)).date().isoformat()
        try:
            raw = FinnhubClient().earnings_calendar(ticker, lo, hi)
        except Exception:
            raw = []
        items = []
        for e in raw:
            d = str(e.get("date") or "")
            if not d:
                continue
            tid = self._nid("E")
            timing = _timing_note(
                _earnings_ts(d, str(e.get("hour") or "")), self.start_dt, self.end_dt
            )
            self.registry[tid] = {
                "kind": "earnings",
                "label": f"{ticker} earnings {d}",
                "url": None,
                "published": d,
                "timing": timing,
            }
            items.append(
                {
                    "id": tid,
                    "date": d,
                    "hour": e.get("hour"),
                    "eps_actual": e.get("epsActual"),
                    "eps_estimate": e.get("epsEstimate"),
                    "rev_actual": e.get("revenueActual"),
                    "rev_estimate": e.get("revenueEstimate"),
                    "timing": timing,
                }
            )
        self.trace.append(f"get_earnings({ticker}) → {len(items)}")
        return json.dumps({"ticker": ticker, "count": len(items), "items": items})

    def search_podcasts(self, ticker: str) -> str:
        ticker = ticker.upper()
        lo = (self.start_dt - timedelta(days=5)).date().isoformat()
        hi = (self.end_dt + timedelta(days=5)).date().isoformat()
        mentions = find_mentions(ticker, lo, hi, limit=5)
        items = []
        for m in mentions:
            tid = self._nid("P")
            self.registry[tid] = {
                "kind": "podcast",
                "label": f"{m.show_slug} — {m.speaker_name or 'podcast'}",
                "url": deep_link(m),
                "published": (m.published_at or "")[:10],
                "timing": "",
            }
            items.append({"id": tid, "show": m.show_slug, "date": (m.published_at or "")[:10],
                          "claim": m.claim})
        self.trace.append(f"search_podcasts({ticker}) → {len(items)}")
        return json.dumps({"ticker": ticker, "count": len(items), "items": items})

    def dispatch(self, name: str, args: dict[str, Any]) -> str:
        if name == "get_news":
            return self.get_news(str(args.get("ticker", "")))
        if name == "get_returns":
            return self.get_returns([str(t) for t in (args.get("tickers") or [])])
        if name == "get_earnings":
            return self.get_earnings(str(args.get("ticker", "")))
        if name == "search_podcasts":
            return self.search_podcasts(str(args.get("ticker", "")))
        return json.dumps({"error": f"unknown tool {name}"})


def investigate_move(
    con: duckdb.DuckDBPyConnection,
    *,
    symbol: str,
    timeframe: str,
    start_time: int,
    end_time: int,
    direction: str,
    pct_change: float,
    settings: Settings | None = None,
    max_rounds: int = 7,
) -> dict[str, Any]:
    """Run the agentic Opus investigation and return a grounded attribution payload."""
    settings = settings or get_settings()
    client = llm.get_client(settings)
    model = settings.synthesis_model  # Opus

    start_dt = _naive_utc(start_time)
    end_dt = _naive_utc(end_time)
    span_days = (end_time - start_time) / 86400.0
    horizon = "short" if span_days <= 3 else "medium" if span_days <= 120 else "long"

    try:
        poly: PolygonClient | None = PolygonClient(settings.polygon_api_key)
    except Exception:
        poly = None
    ctx = ToolContext(con, poly, start_time, end_time, start_dt, end_dt)

    user0 = (
        f"MOVE: {symbol} {direction} {pct_change * 100:+.1f}% "
        f"from {_fmt_dt(start_time, True)} to {_fmt_dt(end_time, True)} "
        f"(horizon: {horizon}). Investigate and find the grounded cause."
    )
    messages: list[dict[str, Any]] = [{"role": "user", "content": user0}]
    tools = _tool_schemas()
    final: dict[str, Any] | None = None

    for _ in range(max_rounds):
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": 8000 if settings.synthesis_thinking else 4096,
            "system": _AGENT_SYSTEM,
            "tools": tools,
            "messages": messages,
        }
        if settings.synthesis_thinking:
            # Adaptive ("max") thinking, interleaved with tool calls.
            kwargs["thinking"] = {"type": "adaptive"}
            kwargs["extra_headers"] = {"anthropic-beta": "interleaved-thinking-2025-05-14"}
        resp = client.messages.create(**kwargs)

        if resp.stop_reason != "tool_use":
            break
        messages.append({"role": "assistant", "content": resp.content})
        results = []
        for block in resp.content:
            if getattr(block, "type", None) != "tool_use":
                continue
            if block.name == "conclude":
                final = dict(block.input)
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": "ok"})
            else:
                out = ctx.dispatch(block.name, dict(block.input))
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": out})
        messages.append({"role": "user", "content": results})
        if final is not None:
            break

    return _finalize(
        ctx, final, symbol, timeframe, start_time, end_time, direction, pct_change, horizon, model
    )


def _finalize(
    ctx: ToolContext,
    final: dict[str, Any] | None,
    symbol: str,
    timeframe: str,
    start_time: int,
    end_time: int,
    direction: str,
    pct_change: float,
    horizon: str,
    model: str,
) -> dict[str, Any]:
    summary, confidence, no_catalyst, scope = "", "low", True, ""
    evidence: list[dict[str, Any]] = []
    if isinstance(final, dict):
        summary = (final.get("summary") or "").strip()
        confidence = (final.get("confidence") or "low").strip().lower()
        if confidence not in {"high", "medium", "low"}:
            confidence = "low"
        scope = (final.get("scope") or "").strip().lower()
        if scope not in {"market", "sector", "company", "mixed"}:
            scope = ""
        no_catalyst = bool(final.get("no_clear_catalyst", not summary))
        for item in final.get("evidence") or []:
            if not isinstance(item, dict):
                continue
            cid = str(item.get("id", "")).strip()
            src = ctx.registry.get(cid)
            if not src:
                continue  # ungrounded id -> drop
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
    if not summary:
        summary = "The investigation did not converge on a grounded cause."

    headlines = [
        {
            "published": v.get("published"),
            "publisher": v.get("label"),
            "title": v.get("title"),
            "url": v.get("url"),
            "timing": v.get("timing", ""),
        }
        for v in ctx.registry.values()
        if v.get("kind") == "news" and v.get("title")
    ]
    headlines.sort(key=lambda h: h["published"] or "", reverse=True)

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
            "tools_called": len(ctx.trace),
            "sources_fetched": len(ctx.registry),
        },
        "headlines": headlines[:40],
        "trace": ctx.trace,
        "model": model,
        "deep": True,
        "generated_at": datetime.now(UTC).isoformat(),
    }
