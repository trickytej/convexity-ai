"""Controlled sector taxonomy + classifier.

`sectors` (on a nugget) stays a free-text set of cross-cutting tags (incl. AI);
`primary_sector` is ONE controlled vertical used for grouping. The classifier's
core rule: AI is usually the *tool*, not the subject - pick "AI & Foundation
Models" only when the AI industry itself is the subject.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from collections.abc import Callable

from .config import Settings, get_settings
from .store import repo
from .transcribe import llm

log = logging.getLogger(__name__)

# Controlled verticals (one is primary). Descriptions guide the classifier.
VERTICALS: dict[str, str] = {
    "Semiconductors": "chips, accelerators, foundries, memory (HBM/DRAM), semicap equipment",
    "Compute & Infrastructure": "data centers, cloud, networking, interconnect, the compute buildout",
    "Software & Apps": "enterprise/consumer software, SaaS, developer tools, applications",
    "Internet & Consumer": "internet platforms, social, advertising, consumer tech and products",
    "AI & Foundation Models": (
        "the AI industry ITSELF - foundation models, AI labs, AGI, training/inference "
        "economics. Use only when AI is the subject, not when AI is a tool applied elsewhere"
    ),
    "Markets & Macro": "public markets, valuations, rates, macro, commodities, market structure",
    "Venture & Private": "venture capital, startups, private financings, fund strategy",
    "Energy & Power": "electricity, the grid, nuclear, power generation, energy commodities",
    "Biotech & Health": "biology, drug discovery, protein/genomics, healthcare, life sciences",
    "Robotics & Autonomy": "robots, autonomous vehicles, drones, physical automation",
    "Defense & Space": "defense, aerospace, space, satellites, national security",
    "Crypto & Fintech": "crypto, stablecoins, payments, fintech, banking technology",
    "Other": "none of the above",
}
VERTICAL_SET = set(VERTICALS)

_TAXONOMY_BLOCK = "\n".join(f"- {name}: {desc}" for name, desc in VERTICALS.items())

CLASSIFY_SYSTEM = f"""\
You classify investment-research insights into exactly ONE primary sector from a \
fixed list. The primary sector is the SUBJECT-MATTER domain of the insight.

CRITICAL RULE: AI is usually the TOOL, not the subject. Choose "AI & Foundation \
Models" ONLY when the insight is about the AI industry itself (models, labs, AGI, \
AI compute economics). When AI is merely applied to another domain, classify by that \
domain - e.g. AI used for drug discovery -> "Biotech & Health"; AI used in defense -> \
"Defense & Space"; an AI data-center buildout -> "Compute & Infrastructure".

Sectors:
{_TAXONOMY_BLOCK}

For each input item, return its id and chosen sector. Output STRICT JSON only:
[{{"id": <int>, "sector": "<one of the sectors above>"}}]
No prose outside the JSON."""

_BATCH = 40


def classify_sectors(client, model: str, items: list[dict]) -> dict[int, str]:
    """items: [{id, claim}] -> {id: sector}. Invalid/missing sectors are dropped."""
    user = "Classify these insights:\n" + json.dumps(items, ensure_ascii=False)
    try:
        raw = llm.complete(client, system=CLASSIFY_SYSTEM, user=user, model=model, max_tokens=2048)
        data = llm.extract_json(raw)
    except llm.LLMError:
        return {}
    mapping: dict[int, str] = {}
    if isinstance(data, list):
        for it in data:
            if not isinstance(it, dict) or "id" not in it:
                continue
            sector = str(it.get("sector", "")).strip()
            if sector in VERTICAL_SET:
                try:
                    mapping[int(it["id"])] = sector
                except (TypeError, ValueError):
                    continue
    return mapping


def reclassify(
    conn: sqlite3.Connection,
    settings: Settings | None = None,
    *,
    only_missing: bool = True,
    progress: Callable[[int, int], None] | None = None,
) -> int:
    """Assign primary_sector to existing nuggets in batches. Returns count updated."""
    settings = settings or get_settings()
    client = llm.get_client(settings)  # raises LLMError if no key
    model = settings.anthropic_model

    rows = repo.nuggets_for_classification(conn, only_missing=only_missing)
    total = len(rows)
    updated = 0
    for start in range(0, total, _BATCH):
        batch = rows[start : start + _BATCH]
        items = [{"id": r["id"], "claim": r["claim"]} for r in batch]
        mapping = classify_sectors(client, model, items)
        for r in batch:
            sector = mapping.get(r["id"])
            if sector:
                repo.set_primary_sector(conn, r["id"], sector)
                updated += 1
        conn.commit()
        if progress is not None:
            progress(min(start + _BATCH, total), total)
    return updated
