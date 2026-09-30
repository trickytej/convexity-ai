"""'What Matters' thesis tracking: map new nuggets to per-company key questions.

The investor hand-authors 4-5 questions per followed company (the theses table).
match_episode_nuggets sends newly extracted nuggets plus ALL active questions to
the LLM in one call — no company prefilter, so attribution works even when a
nugget's entities are empty (X posts) or name the company loosely, and a nugget
can inform a company's question without naming the company at all (hyperscaler
capex news bears on an Nvidia demand question).
"""

from __future__ import annotations

import hashlib
import logging
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from .config import Settings, get_settings
from .store import repo
from .transcribe import llm

log = logging.getLogger(__name__)

_CHUNK_SIZE = 50            # nuggets per matcher call
_STORE_THRESHOLD = 0.4      # matcher hits below this are dropped
_DRAFT_NUGGET_CAP = 80      # recent nuggets fed to the AI-draft prompt
_DRAFT_WINDOW_DAYS = 120

_MATCH_SYSTEM = """\
You map newly extracted investment "nuggets" (insights from podcasts, newsletters, \
and tweets) to an investor's standing thesis questions. For each nugget, decide \
which questions (if any) it materially informs. A nugget matches only if it bears \
on the ANSWER to the question — merely mentioning the company is not a match. \
A nugget may be relevant to a company's question without naming the company \
(e.g. hyperscaler capex commentary informs an Nvidia demand question).

Output STRICT JSON only:
{"matches": [{"nugget": <n>, "question_id": <id>, "relevance": 0.0-1.0, \
"direction": "supports"|"contradicts"|"unclear", \
"why": "<one sentence: what this changes about the question>"}]}

relevance: 1.0 = directly answers/updates the question; 0.5 = meaningful indirect \
evidence; omit anything below 0.4. "supports" means the evidence pushes toward the \
thesis-positive reading of the question; "contradicts" the opposite. A nugget may \
match multiple questions; most nuggets match none — an empty matches array is fine. \
No prose outside the JSON."""

_DRAFT_SYSTEM = """\
You help a public-markets investor define "what matters" for a stock: the 4-5 key \
questions that will decide the investment outcome over the next 1-2 years. Good \
questions are specific, falsifiable, and trackable from podcast/newsletter/news \
evidence (e.g. "Is hyperscaler capex still accelerating?"), never generic ("Will \
the stock go up?"). Ground them in the supplied recent insights where possible, \
but cover the full bull/bear debate even where coverage is thin.

Output STRICT JSON only: {"questions": [{"question": "...", "note": "<one \
sentence on why this matters>"}]} with 4-6 entries. No prose outside the JSON."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def claim_hash(episode_id: int, claim: str) -> str:
    return hashlib.sha1(f"{episode_id}:{claim}".encode()).hexdigest()[:16]


def _questions_block(theses: list[sqlite3.Row]) -> str:
    by_company: dict[str, list[sqlite3.Row]] = defaultdict(list)
    for t in theses:
        by_company[t["company"]].append(t)
    blocks: list[str] = []
    for company, rows in by_company.items():
        ticker = rows[0]["ticker"]
        header = f"### {company} ({ticker})" if ticker else f"### {company}"
        blocks.append(header)
        for t in rows:
            line = f"[id {t['id']}] {t['question']}"
            if t["note"]:
                line += f" — {t['note']}"
            blocks.append(line)
    return "\n".join(blocks)


def _nugget_line(idx: int, n: sqlite3.Row) -> str:
    quote = (n["quote"] or "").strip().replace("\n", " ")
    if len(quote) > 280:
        quote = quote[:280] + "…"
    who = n["speaker_name"] or "unknown"
    line = f"[{idx}] ({n['type']}, {who} on {n['show_slug']}) {n['claim']}"
    if quote and quote != n["claim"]:
        line += f'\n    quote: "{quote}"'
    return line


def match_episode_nuggets(
    conn: sqlite3.Connection,
    episode_id: int,
    settings: Settings | None = None,
    client=None,
) -> int:
    """Evaluate this episode's not-yet-seen nuggets against all active theses.

    Returns the number of hits stored. Marks every evaluated nugget in
    thesis_match_seen (including zero-match ones) so re-runs are free.
    """
    settings = settings or get_settings()
    theses = repo.list_theses(conn)
    if not theses:
        return 0
    nuggets = repo.unseen_nuggets(conn, episode_id=episode_id)
    if not nuggets:
        return 0
    client = client or llm.get_client(settings)
    valid_ids = {t["id"] for t in theses}
    questions = _questions_block(theses)

    total_hits = 0
    for start in range(0, len(nuggets), _CHUNK_SIZE):
        chunk = nuggets[start : start + _CHUNK_SIZE]
        user = (
            "## Thesis questions\n\n" + questions
            + "\n\n## New nuggets\n\n"
            + "\n".join(_nugget_line(i + 1, n) for i, n in enumerate(chunk))
        )
        raw = llm.complete(
            client,
            system=_MATCH_SYSTEM,
            user=user,
            model=settings.anthropic_model,
            max_tokens=8000,
        )
        data = llm.extract_json(raw)
        matches = data.get("matches") if isinstance(data, dict) else None
        hits: list[dict] = []
        for m in matches or []:
            if not isinstance(m, dict):
                continue
            try:
                idx = int(m["nugget"])
                qid = int(m["question_id"])
                relevance = float(m["relevance"])
            except (KeyError, TypeError, ValueError):
                continue
            if qid not in valid_ids or not (1 <= idx <= len(chunk)):
                continue
            if relevance < _STORE_THRESHOLD:
                continue
            direction = m.get("direction")
            if direction not in ("supports", "contradicts", "unclear"):
                direction = "unclear"
            n = chunk[idx - 1]
            hits.append(
                {
                    "question_id": qid,
                    "nugget_id": n["id"],
                    "episode_id": n["episode_id"],
                    "claim_hash": claim_hash(n["episode_id"], n["claim"]),
                    "relevance": min(1.0, max(0.0, relevance)),
                    "direction": direction,
                    "why": (m.get("why") or "").strip() or None,
                    "model": settings.anthropic_model,
                }
            )
        if hits:
            repo.record_thesis_hits(conn, hits)
            total_hits += len(hits)
        repo.mark_nuggets_seen(conn, [(n["id"], n["episode_id"]) for n in chunk])
    if total_hits:
        log.info("thesis matcher: %d hits for episode %s", total_hits, episode_id)
    return total_hits


def run_brief_match(
    conn: sqlite3.Connection, settings: Settings | None = None, days: int = 2
) -> dict:
    """Catch-up sweep: evaluate every unseen nugget created in the window.

    Covers X tweets minted outside the episode pipeline and any episodes whose
    in-pipeline matcher hook failed. Idempotent via thesis_match_seen.
    """
    settings = settings or get_settings()
    result = {"episodes": 0, "nuggets_evaluated": 0, "hits": 0}
    if not repo.list_theses(conn):
        return result
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    unseen = repo.unseen_nuggets(conn, created_since=since)
    if not unseen:
        return result
    client = llm.get_client(settings)
    by_episode: dict[int, int] = defaultdict(int)
    for n in unseen:
        by_episode[n["episode_id"]] += 1
    for episode_id, count in by_episode.items():
        try:
            result["hits"] += match_episode_nuggets(
                conn, episode_id, settings, client=client
            )
            result["episodes"] += 1
            result["nuggets_evaluated"] += count
        except Exception as exc:
            log.warning("brief-match failed for episode %s: %s", episode_id, exc)
    return result


def draft_questions(
    conn: sqlite3.Connection,
    company: str,
    ticker: str | None,
    settings: Settings | None = None,
) -> list[dict]:
    """Propose 4-6 'what matters' questions for a company from its recent nuggets."""
    settings = settings or get_settings()
    since = (datetime.now(timezone.utc) - timedelta(days=_DRAFT_WINDOW_DAYS)).isoformat()
    patterns = [f"%{company}%"]
    if ticker:
        patterns.append(f"%{ticker}%")
    likes = " OR ".join(
        "(n.entities LIKE ? OR n.claim LIKE ? OR n.quote LIKE ?)" for _ in patterns
    )
    params: list = []
    for p in patterns:
        params.extend([p, p, p])
    rows = conn.execute(
        f"""
        SELECT n.*, e.show_slug, e.title AS episode_title
        FROM nuggets n JOIN episodes e ON e.id = n.episode_id
        WHERE n.created_at >= ? AND ({likes})
        ORDER BY n.signal_score DESC LIMIT ?
        """,
        [since, *params, _DRAFT_NUGGET_CAP],
    ).fetchall()

    label = f"{company} ({ticker})" if ticker else company
    user = f"Company: {label}\n\n"
    if rows:
        user += "Recent insights mentioning the company:\n\n" + "\n".join(
            _nugget_line(i + 1, n) for i, n in enumerate(rows)
        )
    else:
        user += "No recent insights on file — draft from the well-known debate."
    client = llm.get_client(settings)
    raw = llm.complete(
        client,
        system=_DRAFT_SYSTEM,
        user=user,
        model=settings.synthesis_model,
        max_tokens=4000,
        thinking=settings.synthesis_thinking,
        stream=True,
    )
    data = llm.extract_json(raw)
    out: list[dict] = []
    for q in (data.get("questions") if isinstance(data, dict) else None) or []:
        if isinstance(q, dict) and (q.get("question") or "").strip():
            out.append(
                {
                    "question": q["question"].strip(),
                    "note": (q.get("note") or "").strip() or None,
                }
            )
    return out[:6]


def build_brief(
    conn: sqlite3.Connection,
    since: str,
    until: str | None = None,
    min_relevance: float = 0.5,
) -> dict:
    """Assemble the Brief straight from thesis_hits — no stored artifact."""
    rows = repo.thesis_hits_since(conn, since, until=until, min_relevance=min_relevance)
    companies: dict[str, dict] = {}
    for r in rows:
        c = companies.setdefault(
            r["company"],
            {"company": r["company"], "ticker": r["ticker"], "hit_count": 0, "questions": {}},
        )
        q = c["questions"].setdefault(
            r["question_id"],
            {
                "question_id": r["question_id"],
                "question": r["question"],
                "note": r["question_note"],
                "hits": [],
            },
        )
        q["hits"].append(
            {
                "relevance": r["relevance"],
                "direction": r["direction"],
                "why": r["why"],
                "matched_at": r["matched_at"],
                "nugget": {
                    "id": r["nugget_id"],
                    "claim": r["claim"],
                    "quote": r["quote"],
                    "speaker_name": r["speaker_name"],
                    "episode_id": r["episode_id"],
                    "show_slug": r["show_slug"],
                    "episode_title": r["episode_title"],
                    "published_at": r["published_at"],
                    "start_ms": r["start_ms"],
                    "tweet_url": r["tweet_url"],
                },
            }
        )
        c["hit_count"] += 1
    out = []
    for c in sorted(companies.values(), key=lambda x: -x["hit_count"]):
        c["questions"] = list(c["questions"].values())
        out.append(c)
    return {"since": since, "until": until or _now_iso(), "companies": out}
