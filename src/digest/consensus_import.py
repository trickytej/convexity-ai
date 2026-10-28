"""Import sell-side consensus from a Bloomberg export (one sheet per ticker,
quarterly columns "2027 Q3 (Fwd)" with period-end dates on the next row, field
codes in column B) into each house model's consensus section.

Columns are matched to model quarters by fiscal period end. For each line the
Bloomberg field whose reported quarters best match the model's actuals is used
(adjusted first, GAAP when a company reports no adjusted figure). FY consensus is
the sum of its quarters, using model actuals for quarters already reported. Every
import is also stored as a dated snapshot, so re-importing tracks revisions."""

from __future__ import annotations

import datetime
import math
import sqlite3
import statistics
from pathlib import Path


def _num(v):
    if v is None or v == "": return None
    try: return float(str(v).replace(",", ""))
    except ValueError: return None

def parse(path):
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    out = {}
    for name in wb.sheetnames:
        rows = list(wb[name].iter_rows(max_row=500, max_col=16, values_only=True))
        labels = rows[2][4:]; ends = rows[3][4:]
        cols = []
        for lab, end in zip(labels, ends):
            if not lab: break
            d = end if isinstance(end, datetime.datetime) else datetime.datetime.fromisoformat(str(end)[:10])
            cols.append((str(lab), d.date(), "(Fwd)" in str(lab)))
        fields = []
        for r in rows[4:]:
            if not r[1]: continue
            fields.append({"label": str(r[0]).strip(), "code": str(r[1]).strip(), "seg": bool(r[3]),
                           "values": [_num(v) for v in r[4:4 + len(cols)]]})
        out[name.strip().upper()] = {"unit": str(rows[2][0]).strip(), "cols": cols, "fields": fields}
    return out

CANDIDATES = {
    "revenue": ["IS_COMP_SALES", "SALES_REV_TURN"],
    "gross_profit": ["IS_ADJ_GROSS_PROFI", "CB_IS_GROSS_PROFIT", "IS_GROSS_PROFIT"],
    "gross_margin": ["IS_COMP_GROSS_MARG", "CB_IS_GROSS_MARGIN", "IS_COMP_GROSS_MARGIN_PERCENTAGE", "GROSS_MARGIN"],
    "operating_income": ["IS_COMPARABLE_EBIT", "CB_IS_ADJ_OPER", "IS_OPER_INC"],
    "eps": ["IS_COMP_EPS_ADJUST", "IS_COMP_EPS_EXCL", "IS_COMP_EPS_GAAP", "IS_DILUTED_EPS", "BEST_EPS"],
}

def _match_periods(cols, periods):
    """col index -> model quarter id, by fiscal period end within 12 days."""
    qs = [p for p in periods if p["id"].startswith("Q") and p.get("end")]
    out = {}
    for i, (_, end, _) in enumerate(cols):
        best = min(qs, key=lambda p: abs((datetime.date.fromisoformat(p["end"][:10]) - end).days), default=None)
        if best and abs((datetime.date.fromisoformat(best["end"][:10]) - end).days) <= 12:
            out[i] = best["id"]
    return out

def _series(field, colmap, scale=1.0):
    return {colmap[i]: v * scale for i, v in enumerate(field["values"]) if i in colmap and v is not None}

def _fit(series, actual, cols_rep):
    """median |log ratio| on reported quarters both sides have (None = no overlap)."""
    rs = [abs(math.log(series[p] / actual[p])) for p in cols_rep
          if p in series and actual.get(p) not in (None, 0) and series[p] and (series[p] > 0) == (actual[p] > 0)]
    return (statistics.median(rs), len(rs)) if rs else (None, 0)

def map_ticker(sheet, base):
    periods, lines = base["periods"], base["lines"]
    colmap = _match_periods(sheet["cols"], periods)
    actual_ids = {p["id"] for p in periods if p["actual"]}
    rep = [colmap[i] for i, c in enumerate(sheet["cols"]) if i in colmap and colmap[i] in actual_ids]
    top = [f for f in sheet["fields"] if not f["seg"]]
    chosen, report = {}, {}
    for line, prefixes in CANDIDATES.items():
        cands = [f for f in top if any(f["code"].startswith(p) for p in prefixes)]
        seen, uniq = set(), []
        for f in cands:  # first occurrence of each code
            if f["code"] not in seen: seen.add(f["code"]); uniq.append(f)
        # unverifiable ties fall back to the preferred (adjusted-first) order
        uniq.sort(key=lambda f: next(i for i, p in enumerate(prefixes) if f["code"].startswith(p)))
        best = None
        for f in uniq:
            if line == "gross_margin":
                rev = chosen.get("revenue", {})
                s = {p: rev[p] * v / 100 for p, v in _series(f, colmap).items() if p in rev}
                tgt = "gross_profit"
            else:
                s, tgt = _series(f, colmap), line
            fit, n = _fit(s, lines.get(tgt, {}), rep)
            score = fit if fit is not None else 9
            if s and (best is None or score < best[0]):
                best = (score, n, f["code"], s)
        if best:
            key = "gross_profit" if line == "gross_margin" else line
            if line == "gross_margin" and "gross_profit" in chosen and report["gross_profit"][0] <= best[0]:
                continue
            chosen[key] = best[3]; report[key] = (best[0], best[1], best[2])
    return colmap, rep, chosen, report

def consensus_lines(sheet, colmap, chosen, periods, model_lines):
    """Quarterly consensus for forward columns only, plus FY = consensus (or model
    actuals for already-reported quarters) summed over the four quarters."""
    fwd = {colmap[i] for i, c in enumerate(sheet["cols"]) if i in colmap and c[2]}
    actual = {p["id"] for p in periods if p["actual"]}
    out = {}
    for line, s in chosen.items():
        q = {p: v for p, v in s.items() if p in fwd and p not in actual}
        for fy in periods:
            if not fy["id"].startswith("FY") or fy["actual"]: continue
            qids = [x["id"] for x in periods if x["id"].startswith("Q") and x["fy"] == fy["fy"]]
            vals = [s.get(x) if x in s else (model_lines.get(line, {}).get(x) if x in actual else None) for x in qids]
            if len(qids) == 4 and all(v is not None for v in vals) and any(x in q for x in qids):
                q[fy["id"]] = sum(vals)
        out[line] = q
    return out


def import_consensus(conn: sqlite3.Connection, path: Path, as_of: str, dry_run: bool = False) -> list[dict]:
    """Attach consensus to every house model whose ticker has a sheet. Returns a
    per-ticker report (matched quarters, fit on reported quarters, fields used)."""
    from .model import load_base, save_base

    data = parse(path)
    rows = {r["ticker"].upper(): r["company"] for r in conn.execute("SELECT company, ticker FROM model_bases") if r["ticker"]}
    report = []
    for tk, sheet in data.items():
        company = rows.get(tk)
        if not company:
            report.append({"ticker": tk, "status": "no model"})
            continue
        base = load_base(conn, company)
        colmap, rep, chosen, fits = map_ticker(sheet, base)
        lines = consensus_lines(sheet, colmap, chosen, base["periods"], base["lines"])
        if not lines.get("revenue"):
            report.append({"ticker": tk, "status": "no periods matched"})
            continue
        base["consensus"] = {"lines": lines, "segments": {}, "source": f"Bloomberg ({Path(path).name})",
                             "as_of": as_of, "unit": sheet["unit"]}
        if not dry_run:
            save_base(conn, company, base.get("ticker") or tk, base, as_of=as_of)
        report.append({"ticker": tk, "status": "ok", "quarters": len(colmap), "verified_on": len(rep),
                       "fit": {k: (None if v[0] >= 9 else round(v[0] * 100, 2), v[2]) for k, v in fits.items()}})
    return report
