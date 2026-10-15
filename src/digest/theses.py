"""'What Matters' thesis tracking: map new nuggets to per-company key questions.

Each user hand-authors 4-5 questions per followed company (the theses table).
The nugget corpus is shared; matching runs once per user. For each user,
match_episode_nuggets sends newly extracted nuggets plus ALL of that user's
active questions to the LLM in one call — no company prefilter, so attribution works even when a
nugget's entities are empty (X posts) or name the company loosely, and a nugget
can inform a company's question without naming the company at all (hyperscaler
capex news bears on an Nvidia demand question).
"""

from __future__ import annotations

import hashlib
import json
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
# A hit is a *signal* (shown as supports/contradicts and counted toward the
# question's status) only when it clears both bars; everything else that
# matched is kept as *reference*.
_SIGNAL_RELEVANCE = 0.75
_SIGNAL_EVIDENCE = 0.7
_STATUS_WINDOW_DAYS = 30

MODEL_LINES = ("revenue", "gross_margin", "op_margin", "eps", "multiple")
_DRAFT_NUGGET_CAP = 80      # recent nuggets fed to the AI-draft prompt
_DRAFT_WINDOW_DAYS = 120

_MATCH_SYSTEM = """\
You map newly extracted investment "nuggets" (insights from podcasts, newsletters, \
and tweets) to an investor's standing thesis questions, and you are a strict \
filter: the investor only wants to see evidence that genuinely changes the answer.

A nugget matches a question only if it bears on the ANSWER — merely mentioning \
the company is not a match. A nugget may be relevant without naming the company \
(e.g. hyperscaler capex commentary informs an Nvidia demand question).

For each match, grade two things separately:
- relevance (0-1): how directly it bears on the question. 1.0 = directly answers \
or updates it; 0.5 = meaningful but indirect. Omit anything below 0.4.
- evidence (0-1): the quality of the evidence itself, regardless of relevance.
  0.9-1.0: new, specific, verifiable information — hard numbers, guidance, orders, \
pricing, share data, a first-hand operator account of something that changed.
  0.7-0.8: a concrete, specific claim from a credible, well-placed source.
  0.4-0.6: informed opinion or analysis without new facts.
  0.0-0.3: generic commentary, restated consensus, vague hype, or speculation.
Be stingy: most matches should score below 0.7 on evidence.

direction: "supports" = pushes toward the thesis-positive reading of the question; \
"contradicts" = the opposite; "unclear" = relevant but cuts both ways or is neutral.

impact: which line of a 3-year model this evidence moves, if any — line is one of \
revenue, gross_margin, op_margin, eps, multiple; year is 1, 2 or 3 (null for \
multiple); direction is "up" or "down". Information that changes how the market \
will value the business before it shows up in numbers (new markets, durability, \
competitive position, narrative shifts) is "multiple". Prefer the question's \
listed drivers when they fit. Use null when there is no clear model impact.

Output STRICT JSON only:
{"matches": [{"nugget": <n>, "question_id": <id>, "relevance": 0.0-1.0, \
"evidence": 0.0-1.0, "direction": "supports"|"contradicts"|"unclear", \
"impact": {"line": "...", "year": 1|2|3|null, "direction": "up"|"down"} | null, \
"why": "<one sentence: what this changes about the question>"}]}

A nugget may match multiple questions; most nuggets match none — an empty \
matches array is fine. No prose outside the JSON."""

_DRAFT_SYSTEM = """\
You help a public-markets investor define "what matters" for a stock: the 4-5 key \
questions that will decide the investment outcome over the next 1-2 years. Good \
questions are specific, falsifiable, and trackable from podcast/newsletter/news \
evidence (e.g. "Is hyperscaler capex still accelerating?"), never generic ("Will \
the stock go up?"). Ground them in the supplied recent insights where possible, \
but cover the full bull/bear debate even where coverage is thin.

For each question also name the model drivers it bears on: line is one of \
revenue, gross_margin, op_margin, eps, multiple; year is 1, 2 or 3 (null for \
multiple). Questions about durability, competitive position or new markets \
usually drive the multiple.

Output STRICT JSON only: {"questions": [{"question": "...", "note": "<one \
sentence on why this matters>", "drivers": [{"line": "...", "year": 1|2|3|null}]}]} \
with 4-6 entries. No prose outside the JSON."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def claim_hash(episode_id: int, claim: str) -> str:
    return hashlib.sha1(f"{episode_id}:{claim}".encode()).hexdigest()[:16]


def classify_tier(relevance: float, evidence: float | None, direction: str) -> str:
    if (
        direction in ("supports", "contradicts")
        and relevance >= _SIGNAL_RELEVANCE
        and (evidence or 0.0) >= _SIGNAL_EVIDENCE
    ):
        return "signal"
    return "reference"


def source_class(show_format: str | None, private: bool = False) -> str:
    """CIO-Brain column: 'inside' (the user's own research), 'print' (filings
    and published writing), 'chatter' (podcasts, X)."""
    if private:
        return "inside"
    return "print" if show_format in ("newsletter", "filing") else "chatter"


def clean_drivers(raw) -> list[dict]:
    """Validate [{"line", "year"}] driver tags (from the editor or the LLM)."""
    out: list[dict] = []
    for d in raw or []:
        if not isinstance(d, dict) or d.get("line") not in MODEL_LINES:
            continue
        year = d.get("year")
        year = int(year) if year in (1, 2, 3, "1", "2", "3") and d["line"] != "multiple" else None
        item = {"line": d["line"], "year": year}
        if item not in out:
            out.append(item)
    return out


def _clean_impact(raw) -> dict | None:
    if not isinstance(raw, dict) or raw.get("direction") not in ("up", "down"):
        return None
    drivers = clean_drivers([raw])
    if not drivers:
        return None
    return {**drivers[0], "direction": raw["direction"]}


def driver_label(line: str, year: int | None) -> str:
    names = {
        "revenue": "Revenue", "gross_margin": "Gross margin", "op_margin": "Op margin",
        "eps": "EPS", "multiple": "Multiple",
    }
    return f"Y{year} {names[line]}" if year else names[line]


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
            drivers = clean_drivers(json.loads(t["drivers"])) if t["drivers"] else []
            if drivers:
                line += " [drivers: " + ", ".join(
                    driver_label(d["line"], d["year"]) for d in drivers
                ) + "]"
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
    user_id: int | None = None,
) -> int:
    """Evaluate this episode's not-yet-seen nuggets against each user's active
    theses (or only *user_id*'s).

    Returns the number of hits stored. Marks every evaluated nugget in
    thesis_match_seen per user (including zero-match ones) so re-runs are free.
    """
    settings = settings or get_settings()
    user_ids = [user_id] if user_id is not None else repo.list_users_with_active_theses(conn)
    total = 0
    for uid in user_ids:
        total += _match_for_user(conn, uid, episode_id, settings, client)
    return total


def _match_for_user(
    conn: sqlite3.Connection,
    user_id: int,
    episode_id: int,
    settings: Settings,
    client=None,
) -> int:
    # One call per user per chunk. If user count grows, send the union of all
    # users' questions per chunk instead (question ids are globally unique) and
    # fan the seen-ledger out per user.
    theses = repo.list_theses(conn, user_id)
    if not theses:
        return 0
    nuggets = repo.unseen_nuggets(conn, user_id, episode_id=episode_id)
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
            try:
                evidence = min(1.0, max(0.0, float(m.get("evidence"))))
            except (TypeError, ValueError):
                evidence = None
            relevance = min(1.0, max(0.0, relevance))
            impact = _clean_impact(m.get("impact")) or {}
            n = chunk[idx - 1]
            hits.append(
                {
                    "question_id": qid,
                    "nugget_id": n["id"],
                    "episode_id": n["episode_id"],
                    "claim_hash": claim_hash(n["episode_id"], n["claim"]),
                    "relevance": relevance,
                    "direction": direction,
                    "why": (m.get("why") or "").strip() or None,
                    "model": settings.anthropic_model,
                    "evidence": evidence,
                    "tier": classify_tier(relevance, evidence, direction),
                    "impact_line": impact.get("line"),
                    "impact_year": impact.get("year"),
                    "impact_dir": impact.get("direction"),
                }
            )
        if hits:
            repo.record_thesis_hits(conn, hits)
            total_hits += len(hits)
        repo.mark_nuggets_seen(conn, user_id, [(n["id"], n["episode_id"]) for n in chunk])
    if total_hits:
        log.info(
            "thesis matcher: %d hits for episode %s (user %s)", total_hits, episode_id, user_id
        )
    return total_hits


def run_brief_match(
    conn: sqlite3.Connection,
    settings: Settings | None = None,
    days: int = 2,
    user_id: int | None = None,
    rematch: bool = False,
) -> dict:
    """Catch-up sweep: evaluate every unseen nugget created in the window, for
    every user with active theses (or only *user_id*).

    Covers X tweets minted outside the episode pipeline, episodes whose
    in-pipeline matcher hook failed, and recently edited questions (see
    repo.reset_seen_window). Idempotent via thesis_match_seen.

    rematch=True re-grades the whole window from scratch (after a matcher or
    rubric change): existing hits there are demoted to reference first, then
    every nugget is re-evaluated and surviving hits re-tiered.
    """
    settings = settings or get_settings()
    result = {"users": 0, "episodes": 0, "nuggets_evaluated": 0, "hits": 0}
    user_ids = [user_id] if user_id is not None else repo.list_users_with_active_theses(conn)
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    client = None
    for uid in user_ids:
        if not repo.list_theses(conn, uid):
            continue
        if rematch:
            repo.demote_hits_since(conn, uid, since)
            repo.reset_seen_window(conn, uid, since)
        unseen = repo.unseen_nuggets(conn, uid, created_since=since)
        result["users"] += 1
        if not unseen:
            continue
        client = client or llm.get_client(settings)
        by_episode: dict[int, int] = defaultdict(int)
        for n in unseen:
            by_episode[n["episode_id"]] += 1
        for episode_id, count in by_episode.items():
            try:
                result["hits"] += _match_for_user(conn, uid, episode_id, settings, client)
                result["episodes"] += 1
                result["nuggets_evaluated"] += count
            except Exception as exc:
                log.warning(
                    "brief-match failed for episode %s (user %s): %s", episode_id, uid, exc
                )
    return result


def draft_questions(
    conn: sqlite3.Connection,
    company: str,
    ticker: str | None,
    settings: Settings | None = None,
    user_id: int | None = None,
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
          AND (e.owner_user_id IS NULL OR e.owner_user_id = ?)
        ORDER BY n.signal_score DESC LIMIT ?
        """,
        [since, *params, user_id, _DRAFT_NUGGET_CAP],
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
                    "drivers": clean_drivers(q.get("drivers")),
                }
            )
    return out[:6]


def build_brief(
    conn: sqlite3.Connection,
    user_id: int,
    since: str | None,
    until: str | None = None,
    min_relevance: float = 0.5,
    decision: str | None = "pending",
    company: str | None = None,
) -> dict:
    """Assemble a user's Brief straight from thesis_hits — no stored artifact.

    decision filters by keep/drop state (None = all)."""
    rows = repo.thesis_hits_since(
        conn, user_id, since, until=until, min_relevance=min_relevance,
        decision=decision, company=company,
    )
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
                "hit_id": r["hit_id"],
                "decision": r["decision"],
                "decided_at": r["decided_at"],
                "relevance": r["relevance"],
                "evidence": r["evidence"],
                "tier": r["tier"],
                "direction": r["direction"],
                "impact": (
                    {
                        "line": r["impact_line"],
                        "year": r["impact_year"],
                        "direction": r["impact_dir"],
                        "label": driver_label(r["impact_line"], r["impact_year"]),
                    }
                    if r["impact_line"]
                    else None
                ),
                "source_class": source_class(r["show_format"], r["owner_user_id"] is not None),
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
        if r["tier"] == "signal":
            c["signal_count"] = c.get("signal_count", 0) + 1
    out = []
    for c in sorted(
        companies.values(), key=lambda x: (-x.get("signal_count", 0), -x["hit_count"])
    ):
        c.setdefault("signal_count", 0)
        c["questions"] = list(c["questions"].values())
        for q in c["questions"]:  # signals first, then strongest
            q["hits"].sort(key=lambda h: (h["tier"] != "signal", -h["relevance"]))
        out.append(c)
    return {"since": since, "until": until or _now_iso(), "companies": out}


def question_statuses(
    conn: sqlite3.Connection,
    user_id: int,
    company: str | None = None,
    days: int = _STATUS_WINDOW_DAYS,
) -> dict[int, dict]:
    """Green / yellow / red per question from its recent signal hits.

    Weighs non-dropped signal hits in the window by relevance: green when
    supports carry >= 65% of the weight, red when <= 35%, yellow between, grey
    with no signals. Also counts signals per source class (print / chatter /
    inside) — the CIO Brain columns.
    """
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    rows = repo.thesis_hits_since(
        conn, user_id, since, min_relevance=0.0, company=company, exclude_dropped=True
    )
    out: dict[int, dict] = {}
    for r in rows:
        st = out.setdefault(
            r["question_id"],
            {"supports": 0.0, "contradicts": 0.0, "signals": 0, "references": 0,
             "by_class": {"print": [0, 0], "chatter": [0, 0], "inside": [0, 0]}},
        )
        if r["tier"] != "signal":
            st["references"] += 1
            continue
        st["signals"] += 1
        st[r["direction"]] += r["relevance"]
        col = st["by_class"][source_class(r["show_format"], r["owner_user_id"] is not None)]
        col[0 if r["direction"] == "supports" else 1] += 1
    for st in out.values():
        total = st["supports"] + st["contradicts"]
        if not total:
            st["status"] = "none"
        else:
            share = st["supports"] / total
            st["status"] = "green" if share >= 0.65 else "red" if share <= 0.35 else "yellow"
        st["supports"] = round(st["supports"], 2)
        st["contradicts"] = round(st["contradicts"], 2)
        st["by_class"] = {
            k: {"supports": v[0], "contradicts": v[1]} for k, v in st["by_class"].items()
        }
    return out
