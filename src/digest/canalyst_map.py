"""AI-mapped Canalyst import: Claude picks the rows, code builds and verifies.

Canalyst models differ a lot company to company (segment builds, KPI rows,
GAAP vs non-GAAP blocks), so label heuristics alone mis-pick rows. Here Claude
reads a compact listing of the Model sheet and returns a row mapping — revenue
segments (with subtotals), P&L lines, a few operating KPIs, consensus rows —
which `build_mapped` turns into a base model and `validate` checks: segments
must add up to total revenue, and the driver engine must reproduce the
vendor's revenue / operating income / net income / EPS.

Mappings are plain JSON so they can be saved, reviewed, and re-used.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from .finmodel import _add_residual_segment, _balance, _canalyst_frame, _num, run_engine

MAPPING_MODEL = "claude-opus-5-5"
LINES = ("gross_profit", "rd", "sga", "operating_income", "ebt", "tax", "net_income",
         "shares", "eps", "da", "ocf", "capex")

_SYSTEM = """\
You map rows of a Canalyst financial model (one company) into a simplified operating model. \
You get the Model sheet as numbered rows: row index, label, and values for the last \
reported fiscal year and the next two forecast fiscal years. Section headers have no values.

Return STRICT JSON only, exactly this shape (row = the row index number; null when absent):
{
  "total_revenue": <row>,
  "segments": [{"row": <row>, "name": "<short display name>", "children": [<row>, ...] | null}],
  "lines": {"gross_profit": <rows>, "rd": <rows>, "sga": <rows>,
            "operating_income": <rows>, "ebt": <rows>, "tax": <rows>,
            "net_income": <rows>, "shares": <rows>, "eps": <rows>,
            "da": <rows>, "ocf": <rows>, "capex": <rows>},
  "kpis": [{"row": <row>, "name": "<short name>", "unit": "mm" | "%" | "count" | "$"}],
  "consensus": {"revenue": <row|null>, "eps": <row|null>, "operating_income": <row|null>,
                "gross_margin_pct": <row|null>},
  "notes": "<one or two sentences on anything unusual>"
}

Rules:
- total_revenue: the company's total reported revenue row (in $mm), the one the P&L uses.
- segments: the revenue build that ADDS UP to total revenue, in display order, as reported \
revenue lines only — product/business/geographic segments. Never KPIs, bookings, billings, \
GMV/GBV/TPV, deferred/unearned revenue, ASPs, units, growth rates, margins or GAAP-to-non-GAAP \
items. Prefer the most informative breakdown the model actually forecasts (non-empty forecast \
values). If a segment is a subtotal of other listed segments, put it AFTER them and list their \
rows in "children" (subtotals may nest). Leaf segments (no children) must sum to total_revenue. \
Use 2-8 leaves; if the model only forecasts total revenue, return an empty list.
- lines: each value is a row, a LIST of rows to add together when the model has no combined row (e.g. sga = [sales & marketing, general & administrative]; tax = [current, deferred]), or null. Prefer the NON-GAAP / adjusted rows when the model has both (gross profit, R&D, SG&A, \
operating income, pre-tax income, tax provision, net income to common, diluted EPS); shares = \
diluted weighted-average shares; da = depreciation & amortization; ocf = operating cash flow \
(after working capital); capex = capital expenditures. All in $mm except shares (mm) and EPS ($).
- kpis: up to 4 forecast operating metrics investors track for this company (e.g. gross \
bookings, GMV, TPV, nights booked, subscribers, ARR, RPO, units/shipments, ASP, wafer starts). \
Skip if none are meaningful.
- consensus: rows whose label starts with "Consensus Estimates" for total revenue, EPS, \
operating income, and gross margin %, only if they hold numeric values.
- Only use row indices that appear in the listing. No prose outside the JSON."""


def _fmt(v: float | None) -> str:
    if v is None:
        return ""
    if abs(v) >= 100:
        return f"{v:,.0f}"
    return f"{v:.3g}"


def listing(frame: dict) -> tuple[str, list[str]]:
    """Compact row listing for the prompt, plus the fiscal-year ids shown."""
    fys = [c for c in frame["kept"] if c["kind"] == "FY"]
    last_actual = [c for c in fys if frame["is_actual"](c)][-1:]
    fcst = [c for c in fys if not frame["is_actual"](c)][:2]
    cols = last_actual + fcst
    ids = [c["id"] + ("A" if frame["is_actual"](c) else "E") for c in cols]
    lines = [f"columns: {' | '.join(ids)}"]
    for i, lab, r in frame["labelled"]:
        vals = [_num(r[c["ci"]]) if c["ci"] < len(r) else None for c in cols]
        has_any = any(_num(r[c["ci"]]) is not None for c in frame["kept"] if c["ci"] < len(r))
        low = lab.lower()
        if not has_any:
            if len(lab) < 80 and not low.startswith(("q/q", "y/y")):
                lines.append(f"## {lab}")
            continue
        if re.match(r"^(q/q|y/y)\b", low) or "bps" in low:
            continue  # growth/margin deltas are noise for the mapping
        lines.append(f"{i}\t{lab}\t" + " | ".join(_fmt(v) for v in vals))
    return "\n".join(lines), ids


def ask_mapping(frame: dict, client=None) -> dict:
    import anthropic

    from .transcribe.llm import extract_json

    client = client or anthropic.Anthropic()
    text, _ = listing(frame)
    with client.beta.messages.stream(
        model=MAPPING_MODEL,
        max_tokens=32000,
        system=_SYSTEM,
        output_config={"effort": "high"},
        betas=["server-side-fallback-2026-07-01"],
        extra_body={"fallbacks": "default"},
        messages=[{"role": "user", "content": f"Company: {frame['company']} ({frame['ticker']})\n\n{text}"}],
    ) as stream:
        msg = stream.get_final_message()
    if msg.stop_reason == "refusal":
        raise RuntimeError("mapping request was declined")
    raw = "".join(b.text for b in msg.content if b.type == "text")
    data = extract_json(raw)
    if not isinstance(data, dict) or "total_revenue" not in data:
        raise ValueError(f"unparseable mapping: {raw[:300]}")
    return data


def build_mapped(path: str | Path, mapping: dict, frame: dict | None = None) -> dict:
    """Base model document from a Canalyst workbook + row mapping."""
    f = frame or _canalyst_frame(path)
    by_row = {i: r for i, _, r in f["labelled"]}

    def ser(row) -> dict[str, float]:
        return f["series"](by_row[row]) if row in by_row else {}

    def ser_sum(rows) -> dict[str, float]:
        """One row, or several rows added together (only periods all of them have)."""
        rows = [rows] if isinstance(rows, int) else [r for r in (rows or []) if isinstance(r, int)]
        parts = [ser(r) for r in rows]
        parts = [p for p in parts if p]
        if not parts:
            return {}
        common = set.intersection(*(set(p) for p in parts))
        return {pid: sum(p[pid] for p in parts) for pid in common}

    lines: dict[str, dict[str, float]] = {"revenue": ser(mapping["total_revenue"])}
    for key in LINES:
        values = ser_sum((mapping.get("lines") or {}).get(key))
        if values:
            lines[key] = values
    if "capex" in lines:
        lines["capex"] = {k: abs(v) for k, v in lines["capex"].items()}
    if "eps" not in lines and lines.get("net_income") and lines.get("shares"):
        lines["eps"] = {p: v / lines["shares"][p] for p, v in lines["net_income"].items() if lines["shares"].get(p)}

    segs: list[dict] = []
    row_to_id: dict[int, str] = {}
    for s in mapping.get("segments") or []:
        values = ser(s["row"])
        if not values:
            continue
        sid = f"s{len(segs)}"
        row_to_id[s["row"]] = sid
        seg = {"id": sid, "name": (s.get("name") or "Segment").strip(), "revenue": values}
        kids = [row_to_id[c] for c in (s.get("children") or []) if c in row_to_id]
        if kids:
            seg["children"] = kids
        segs.append(seg)
    _add_residual_segment(segs, lines["revenue"])
    if len(segs) == 1 and segs[0]["name"] == "Other":
        segs[0]["name"] = "Revenue"  # forecast only at the total level

    kpis = [
        {"name": k["name"], "unit": k.get("unit") or "", "values": ser(k["row"])}
        for k in (mapping.get("kpis") or [])[:4] if ser(k["row"])
    ]

    cons_map = mapping.get("consensus") or {}
    cons_lines: dict[str, dict[str, float]] = {}
    for key, line in (("revenue", "revenue"), ("eps", "eps"), ("operating_income", "operating_income")):
        if cons_map.get(key) is not None and ser(cons_map[key]):
            cons_lines[line] = ser(cons_map[key])
    if cons_map.get("gross_margin_pct") is not None and cons_lines.get("revenue"):
        gm = ser(cons_map["gross_margin_pct"])
        cons_lines["gross_profit"] = {
            p: (g / 100 if g > 1.5 else g) * cons_lines["revenue"][p]
            for p, g in gm.items() if p in cons_lines["revenue"]
        }

    return {
        "source": "Canalyst",
        "file": Path(path).name,
        "company_name": f["company"],
        "ticker": f["ticker"],
        "periods": f["periods"],
        "segments": segs,
        "lines": lines,
        "kpis": kpis,
        "balance": _balance(f["wb"], f["last_actual"]["id"]),
        "consensus": {"lines": cons_lines, "segments": {}} if cons_lines else None,
        "mapping_notes": mapping.get("notes"),
        "imported_at": datetime.utcnow().isoformat(),
    }


def validate(base: dict) -> dict:
    """Checks a built base: segment sums vs total, and engine reproduction."""
    issues: list[str] = []
    leaves = [s for s in base["segments"] if "children" not in s]
    total = base["lines"].get("revenue", {})
    fc = [p["id"] for p in base["periods"] if not p["actual"]]
    if leaves:
        bad = [p for p in fc if p in total and total[p] and
               abs(sum(s["revenue"].get(p, 0) for s in leaves) - total[p]) > 0.01 * abs(total[p])]
        if bad:
            issues.append(f"segments don't sum to revenue in {len(bad)} forecast periods")
    if len(leaves) > 1 and any(s["name"] == "Other" and "children" not in s for s in base["segments"]):
        other = next(s for s in base["segments"] if s["name"] == "Other")
        share = max((abs(other["revenue"].get(p, 0)) / abs(total[p]) for p in fc if total.get(p)), default=0)
        if share > 0.05:
            issues.append(f"unexplained 'Other' revenue up to {share:.0%} of total")
    V, _, _ = run_engine(base)
    checked = mismatched = 0
    worst = []
    for line in ("revenue", "operating_income", "net_income", "eps"):
        for pid, bv in base["lines"].get(line, {}).items():
            v = V.get(line, {}).get(pid)
            if bv is None or v is None:
                continue
            checked += 1
            if abs(v - bv) > 0.005 * max(1.0, abs(bv)):
                mismatched += 1
                worst.append((line, pid, round(bv, 2), round(v, 2)))
    if mismatched:
        issues.append(f"engine differs from vendor on {mismatched}/{checked} values, e.g. {worst[:3]}")
    missing = [k for k in ("gross_profit", "operating_income", "net_income", "shares") if k not in base["lines"]]
    if missing:
        issues.append(f"missing lines: {', '.join(missing)}")
    return {"issues": issues, "checked": checked, "mismatched": mismatched,
            "leaves": len(leaves), "kpis": len(base.get("kpis") or []),
            "consensus": bool(base.get("consensus"))}
