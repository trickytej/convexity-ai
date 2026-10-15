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

from .finmodel import parse_canalyst
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
            base = parse_canalyst(path)
        except Exception as exc:
            results.append({"file": name, "ok": False, "error": f"could not read: {exc}"})
            continue
        sec = resolve(conn, base.get("ticker") or "")
        if not sec:
            results.append({"file": name, "ok": False, "error": f"ticker {base.get('ticker')!r} not in watchlist"})
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
