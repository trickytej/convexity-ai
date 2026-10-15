"""ConvexityAI MCP server: let Claude (or any MCP client) work with your
What Matters board — read the brief, inspect a security, add questions, keep or
drop developments, and push your own research into the platform.

Runs locally over stdio and talks to the ConvexityAI API with a personal token
(create one on the Settings page):

    CONVEXITY_API_URL=https://<your-api-host>  CONVEXITY_TOKEN=cvx_...  convexity-mcp

Claude Desktop / Claude Code config:

    {"mcpServers": {"convexity": {"command": "convexity-mcp",
      "env": {"CONVEXITY_API_URL": "...", "CONVEXITY_TOKEN": "cvx_..."}}}}
"""

from __future__ import annotations

import os
from typing import Any

import httpx
from mcp.server.mcpserver import MCPServer

mcp = MCPServer(
    name="convexity",
    instructions=(
        "ConvexityAI tracks the 4-5 'What Matters' questions a user holds for each security "
        "they follow, matches new research (podcasts, X, SEC filings, the user's own notes) "
        "against them, and keeps a 3-year model per security. 'Signals' are strong, "
        "high-quality evidence that supports or contradicts a question; everything else is "
        "'reference'. Use add_research to bring the user's own notes or links in."
    ),
)


def _client() -> httpx.Client:
    base = os.environ.get("CONVEXITY_API_URL", "http://127.0.0.1:8000").rstrip("/")
    token = os.environ.get("CONVEXITY_TOKEN")
    if not token:
        raise RuntimeError("Set CONVEXITY_TOKEN (create one on the ConvexityAI Settings page).")
    return httpx.Client(base_url=base, headers={"Authorization": f"Bearer {token}"}, timeout=60)


def _call(method: str, path: str, **kwargs: Any) -> Any:
    with _client() as c:
        resp = c.request(method, path, **kwargs)
    if resp.status_code >= 400:
        try:
            detail = resp.json().get("detail")
        except ValueError:
            detail = resp.text
        raise RuntimeError(f"{resp.status_code}: {detail}")
    return resp.json()


def _hit(h: dict) -> dict:
    return {
        "hit_id": h["hit_id"],
        "tier": h["tier"],
        "direction": h["direction"] if h["tier"] == "signal" else None,
        "impact": h["impact"]["label"] + (" up" if h["impact"]["direction"] == "up" else " down")
        if h.get("impact") else None,
        "source": h["source_class"],
        "claim": h["nugget"]["claim"],
        "why": h["why"],
        "from": h["nugget"]["show_slug"],
    }


@mcp.tool()
def get_board() -> list[dict]:
    """The CIO board: every followed security with its questions, each question's
    green/yellow/red status over the last 30 days, and signal counts by source
    (print = filings/articles, chatter = podcasts/X, inside = the user's own research)."""
    return _call("GET", "/api/board")["securities"]


@mcp.tool()
def get_brief(days: int = 1, include_reference: bool = False) -> list[dict]:
    """Undecided developments from the last `days` days, grouped by security and
    question. By default only signals; set include_reference for everything."""
    brief = _call("GET", "/api/brief", params={"days": days, "status": "pending"})
    out = []
    for c in brief["companies"]:
        for q in c["questions"]:
            hits = [_hit(h) for h in q["hits"] if include_reference or h["tier"] == "signal"]
            if hits:
                out.append({"company": c["company"], "ticker": c["ticker"], "question": q["question"], "hits": hits})
    return out


@mcp.tool()
def get_security(key: str) -> dict:
    """One security (ticker, or name for privates): its questions with status, the
    3-year model (consensus vs the user's numbers, target P/E, implied value) and
    the developments the user has kept."""
    m = _call("GET", f"/api/model/{key}")
    n = m["numbers"]
    return {
        "company": m["company"],
        "ticker": m["ticker"],
        "questions": [
            {"id": q["id"], "question": q["question"], "status": q["status"], "signals_30d": q["signals"]}
            for q in m["questions"]
        ],
        "model": {
            "fiscal_years": n["fiscal_years"],
            **{line: [c["value"] for c in cells] for line, cells in n["grid"].items()},
            "target_pe": n["multiple"]["value"],
            "price": n["price"]["value"],
            "implied_value": [v["value"] for v in n["implied"]],
        },
        "kept": [
            {"question": q["question"], "hits": [_hit(h) for h in q["hits"]]} for q in m["kept"]
        ],
    }


@mcp.tool()
def add_question(company: str, question: str, note: str | None = None) -> list[dict]:
    """Add a What Matters question to a security (follows it if needed). Returns
    the security's full question list."""
    sec = _call("GET", f"/api/model/{company}")
    existing = [{"id": q["id"], "question": q["question"], "note": q["note"], "drivers": q["drivers"]}
                for q in sec["questions"]]
    res = _call("PUT", "/api/theses", json={
        "company": sec["company"], "ticker": sec["ticker"],
        "questions": existing + [{"question": question, "note": note}],
    })
    block = next((c for c in res["companies"] if c["company"] == sec["company"]), {"questions": []})
    return [{"id": q["id"], "question": q["question"]} for q in block["questions"]]


@mcp.tool()
def decide(hit_id: int, decision: str) -> dict:
    """Keep or drop a development: decision is 'kept', 'dropped' or 'pending'."""
    return _call("PATCH", f"/api/hits/{hit_id}", json={"decision": decision})


@mcp.tool()
def add_research(title: str, text: str | None = None, url: str | None = None) -> dict:
    """Bring the user's own research in (their 'inside view'): pasted notes, call
    transcripts, or a link to fetch. It stays private to this user and is matched
    against their questions within a minute or two."""
    return _call("POST", "/api/research", json={"title": title, "text": text, "url": url})


def main() -> None:
    mcp.run("stdio")


if __name__ == "__main__":
    main()
