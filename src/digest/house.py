"""Bulk loading of ConvexityAI's house content: base models and default questions.

Questions CSV columns (header row required; extra columns ignored):
    ticker      ticker or company name from the watchlist (e.g. NVDA, Anthropic)
    question    the What Matters question
    note        optional: why it matters
    drivers     optional: model lines it moves, separated by ";" — e.g.
                "Y2 Revenue; Y1 Gross margin; Multiple"
Rows for the same security are kept in file order. Importing a security's
questions replaces its previous house set (hits on unchanged wording are kept).
"""

from __future__ import annotations

import csv
import io
import re
import sqlite3
from collections import OrderedDict
from pathlib import Path

from .finmodel import parse_model
from .model import save_base
from .securities import resolve
from .store import repo

_LINE_NAMES = {
    "revenue": "revenue", "revenues": "revenue", "sales": "revenue",
    "gross margin": "gross_margin", "gm": "gross_margin",
    "op margin": "op_margin", "operating margin": "op_margin", "opm": "op_margin",
    "eps": "eps", "multiple": "multiple", "p/e": "multiple", "valuation": "multiple",
}


def parse_drivers(text: str) -> list[dict]:
    out = []
    for part in re.split(r"[;,]", text or ""):
        m = re.match(r"\s*(?:Y([123])\s+)?(.+?)\s*$", part, re.I)
        if not m or not m.group(2):
            continue
        line = _LINE_NAMES.get(m.group(2).lower())
        if line:
            year = int(m.group(1)) if m.group(1) and line != "multiple" else None
            out.append({"line": line, "year": year})
    return out


def import_models(conn: sqlite3.Connection, files: list[tuple[str, Path]]) -> list[dict]:
    """[(display_name, path)] → one result row per file, matched by the file's ticker."""
    results = []
    for name, path in files:
        try:
            base = parse_model(path)
        except Exception as exc:
            results.append({"file": name, "ok": False, "error": f"could not read: {exc}"})
            continue
        # Canalyst files carry their ticker; ConvexityAI templates are matched by
        # the file name's first word ("NVDA model v3.xlsx" → NVDA).
        guess = base.get("ticker") or re.split(r"[\s_\-.]+", Path(name).stem)[0]
        sec = resolve(conn, guess or "")
        if not sec:
            results.append({"file": name, "ok": False, "error": f"{guess!r} isn't a watchlist ticker — name the file '<TICKER> …xlsx'"})
            continue
        base["file"] = name
        save_base(conn, sec["company"], sec["ticker"], base)
        results.append({"file": name, "ok": True, "company": sec["company"],
                        "periods": len(base["periods"]), "segments": len(base["segments"])})
    return results


def import_house_questions(conn: sqlite3.Connection, csv_text: str) -> list[dict]:
    house = repo.house_user_id(conn)
    if house is None:
        raise RuntimeError("house account missing — run `digest init`")
    reader = csv.DictReader(io.StringIO(csv_text.lstrip("﻿")))
    fields = {f.lower().strip(): f for f in (reader.fieldnames or [])}
    key_col = fields.get("ticker") or fields.get("company")
    q_col = fields.get("question")
    if not key_col or not q_col:
        raise ValueError("CSV needs 'ticker' (or 'company') and 'question' columns")
    by_sec: OrderedDict[str, dict] = OrderedDict()
    unknown: list[str] = []
    for row in reader:
        key, question = (row.get(key_col) or "").strip(), (row.get(q_col) or "").strip()
        if not key or not question:
            continue
        sec = resolve(conn, key)
        if not sec:
            unknown.append(key)
            continue
        entry = by_sec.setdefault(sec["company"], {"sec": sec, "questions": []})
        entry["questions"].append({
            "question": question,
            "note": (row.get(fields.get("note", ""), "") or "").strip() or None,
            "drivers": parse_drivers(row.get(fields.get("drivers", ""), "") or ""),
        })
    results = []
    for company, entry in by_sec.items():
        existing = {t["question"].strip().lower(): t["id"] for t in repo.list_theses(conn, house, company=company)}
        for q in entry["questions"]:
            if q["question"].lower() in existing:
                q["id"] = existing[q["question"].lower()]
        repo.save_company_theses(conn, house, company, entry["sec"]["ticker"], entry["questions"])
        results.append({"company": company, "questions": len(entry["questions"])})
    for key in sorted(set(unknown)):
        results.append({"company": key, "error": "not in watchlist"})
    return results


# --- AI-drafted default questions ------------------------------------------------

DRAFT_MODEL = "claude-opus-5-5"

_DRAFT_SYSTEM = """\
You write the default "What Matters" questions for a stock on an investment research platform: \
the 4 questions that will decide the investment outcome over the next 1-3 years. A portfolio \
manager reads them every morning; new podcast, news, filing and research evidence is matched \
against them and marked as supporting or contradicting.

Good questions are:
- decisive: the answer moves the stock, not trivia;
- falsifiable and trackable from public evidence (earnings, filings, management commentary, \
channel checks, expert interviews), phrased so evidence can clearly support or contradict;
- specific to this company: name the products, segments, customers, competitors and metrics;
- together, the real bull/bear debate — including at least one about durability or competitive \
position (what drives the valuation multiple, not just next year's numbers);
- 8-18 words each, punchy like the Nvidia examples — one question each, no compound lists.

Tie each to the model lines it moves: line is revenue, gross_margin, op_margin, eps or multiple; \
year is 1, 2 or 3 (Y1 = current fiscal year in progress; null for multiple).

Output STRICT JSON only:
{"questions": [{"question": "...", "note": "<one sentence on why it matters>", \
"drivers": [{"line": "...", "year": 1|2|3|null}]}]}
Exactly 4 questions. No prose outside the JSON."""

_STYLE = """Style reference — the house questions for Nvidia:
1. Is hyperscaler + sovereign AI datacenter capex still accelerating, or starting to plateau? (Demand durability is the whole bull case)
2. Is inference (vs training) becoming the dominant workload, and does Nvidia keep share there? (Inference is more competitive: custom silicon, AMD, Groq)
3. Are custom ASICs (TPU, Trainium, MTIA) materially eroding Nvidia allocation at the big buyers?
4. Does supply (CoWoS, HBM) stay the binding constraint or is it easing into oversupply?"""


def _model_brief(base: dict | None) -> str:
    """A few lines describing the company's model: segments, KPIs, key ratios."""
    if not base:
        return "No financial model loaded (private company or not yet modelled)."
    fys = sorted([p for p in base["periods"] if p["kind"] == "FY"], key=lambda p: p["fy"])
    act = [p["id"] for p in fys if p["actual"]][-1:]
    fc = [p["id"] for p in fys if not p["actual"]][:2]
    L = base["lines"]

    def g(line, pid):
        return L.get(line, {}).get(pid)

    out = []
    for pid in act + fc:
        rev, gp, oi, eps = g("revenue", pid), g("gross_profit", pid), g("operating_income", pid), g("eps", pid)
        parts = [f"{pid}: revenue ${rev:,.0f}mm" if rev else pid]
        if rev and gp:
            parts.append(f"GM {gp / rev:.0%}")
        if rev and oi:
            parts.append(f"op margin {oi / rev:.0%}")
        if eps is not None:
            parts.append(f"EPS ${eps:.2f}")
        out.append(", ".join(parts))
    leaves = [s for s in base["segments"] if "children" not in s]
    if act and leaves:
        a = act[0]
        segs = sorted(leaves, key=lambda s: -(s["revenue"].get(a) or 0))
        out.append("Segments (" + a + "): " + "; ".join(
            f"{s['name']} ${s['revenue'].get(a, 0):,.0f}mm" for s in segs[:8]))
    if base.get("kpis"):
        out.append("Tracked KPIs: " + ", ".join(k["name"] for k in base["kpis"]))
    return "\n".join(out)


def _recent_research(conn: sqlite3.Connection, company: str, ticker: str | None, limit: int = 40) -> str:
    pats = [f"%{company}%"] + ([f"%{ticker}%"] if ticker else [])
    likes = " OR ".join("(n.entities LIKE ? OR n.claim LIKE ?)" for _ in pats)
    params = [x for p in pats for x in (p, p)]
    rows = conn.execute(
        f"""SELECT n.claim, e.show_slug FROM nuggets n JOIN episodes e ON e.id = n.episode_id
            WHERE e.owner_user_id IS NULL AND ({likes})
            ORDER BY n.created_at DESC, n.signal_score DESC LIMIT ?""",
        [*params, limit],
    ).fetchall()
    return "\n".join(f"- {r['claim']} ({r['show_slug']})" for r in rows) or "(no recent research on file)"


def draft_house_set(company: str, ticker: str | None, category: str | None, model_brief: str,
                    research: str, client=None) -> list[dict]:
    """Ask Claude for 4 default questions (returns cleaned question dicts)."""
    import anthropic

    from .theses import clean_drivers
    from .transcribe.llm import extract_json

    client = client or anthropic.Anthropic()
    user = (f"Company: {company}" + (f" ({ticker})" if ticker else "") + f"\nSector: {category or 'n/a'}\n\n"
            f"Model:\n{model_brief}\n\nRecent research mentions:\n{research}\n\n{_STYLE}")
    with client.beta.messages.stream(
        model=DRAFT_MODEL,
        max_tokens=16000,
        system=_DRAFT_SYSTEM,
        output_config={"effort": "high"},
        betas=["server-side-fallback-2026-07-01"],
        extra_body={"fallbacks": "default"},
        messages=[{"role": "user", "content": user}],
    ) as stream:
        msg = stream.get_final_message()
    if msg.stop_reason == "refusal":
        raise RuntimeError("draft request was declined")
    data = extract_json("".join(b.text for b in msg.content if b.type == "text"))
    out = []
    for q in (data.get("questions") if isinstance(data, dict) else None) or []:
        if isinstance(q, dict) and (q.get("question") or "").strip():
            out.append({"question": q["question"].strip(), "note": (q.get("note") or "").strip() or None,
                        "drivers": clean_drivers(q.get("drivers"))})
    return out[:4]
