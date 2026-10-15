"""CIO Brain: one screen over everything a user follows.

  * Narrative velocity per sector — how fast high-signal chatter about a sector
    is arriving in the shared corpus this week vs its recent run-rate.
  * Per security: thesis status (green/yellow/red, inverted for shorts), the
    print / chatter / inside split, model-impact tallies, status flips, and the
    "ahead of print" flag — strong evidence piling up on a model line while
    consensus for that line hasn't moved (or moved the other way).
  * A tape of the newest signals and a "since your last visit" summary.
"""

from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from .securities import resolve, security_key
from .store import repo
from .theses import driver_label, question_statuses, source_class

_VELOCITY_SIGNAL = 0.7        # nugget signal_score counted as "high-signal" chatter
_AHEAD_MIN_NET = 3            # net signals on one model line before flagging
_FLAT_REVISION = 0.01         # |consensus revision| below this counts as "unchanged"
_FLIP_FRESH_HOURS = 48
_MIN_BASELINE = 2.0           # weekly items needed before showing an acceleration
_STATUS_ORDER = {"green": 2, "yellow": 1, "red": 0, "none": -1}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _status(supports: float, contradicts: float) -> str:
    total = supports + contradicts
    if not total:
        return "none"
    share = supports / total
    return "green" if share >= 0.65 else "red" if share <= 0.35 else "yellow"


def invert(status: str) -> str:
    """For a short, evidence against the thesis-positive reading is good news."""
    return {"green": "red", "red": "green"}.get(status, status)


# ── narrative velocity (shared corpus) ──────────────────────────────────────


def narrative_velocity(conn: sqlite3.Connection) -> list[dict]:
    now = _now()
    week = (now - timedelta(days=7)).isoformat()
    month = (now - timedelta(days=35)).isoformat()
    rows = conn.execute(
        """
        SELECT n.primary_sector AS sector,
               SUM(CASE WHEN COALESCE(st.created_at, e.published_at, n.created_at) >= ? THEN 1 ELSE 0 END) AS last7,
               SUM(CASE WHEN COALESCE(st.created_at, e.published_at, n.created_at) < ? THEN 1 ELSE 0 END) AS prior28
        FROM nuggets n
        JOIN episodes e ON e.id = n.episode_id
        LEFT JOIN scout_tweets st ON st.nugget_id = n.id
        WHERE e.owner_user_id IS NULL AND n.signal_score >= ?
          AND n.primary_sector IS NOT NULL AND n.primary_sector != 'Other'
          AND COALESCE(st.created_at, e.published_at, n.created_at) >= ?
        GROUP BY n.primary_sector
        """,
        (week, week, _VELOCITY_SIGNAL, month),
    ).fetchall()
    out = []
    for r in rows:
        weekly_avg = (r["prior28"] or 0) / 4
        # Too thin a baseline makes multiples meaningless (0.5/wk → "12×").
        accel = (r["last7"] / weekly_avg - 1) if weekly_avg >= _MIN_BASELINE else None
        out.append({"sector": r["sector"], "last7": r["last7"], "weekly_avg": round(weekly_avg, 1),
                    "acceleration": round(accel, 3) if accel is not None else None})
    return sorted(out, key=lambda x: -(x["last7"] or 0))


# ── status flips ──────────────────────────────────────────────────────────


def _record_flips(conn: sqlite3.Connection, user_id: int, statuses: dict[int, dict]) -> dict[int, dict]:
    """Persist each question's status; return {question_id: {from, to, at}} for changes."""
    now = _now().isoformat()
    stored = {
        r["question_id"]: r
        for r in conn.execute(
            "SELECT question_id, status, prev_status, changed_at FROM question_status WHERE user_id = ?",
            (user_id,),
        ).fetchall()
    }
    for qid, st in statuses.items():
        cur = st.get("status", "none")
        old = stored.get(qid)
        if old is None:
            conn.execute(
                "INSERT INTO question_status (user_id, question_id, status, prev_status, changed_at) "
                "VALUES (?, ?, ?, NULL, ?)",
                (user_id, qid, cur, now),
            )
        elif old["status"] != cur:
            conn.execute(
                "UPDATE question_status SET prev_status = status, status = ?, changed_at = ? "
                "WHERE user_id = ? AND question_id = ?",
                (cur, now, user_id, qid),
            )
    conn.commit()
    return {
        r["question_id"]: {"from": r["prev_status"], "to": r["status"], "at": r["changed_at"]}
        for r in conn.execute(
            "SELECT question_id, status, prev_status, changed_at FROM question_status "
            "WHERE user_id = ? AND prev_status IS NOT NULL",
            (user_id,),
        ).fetchall()
    }


# ── ahead of print ─────────────────────────────────────────────────────────


def _consensus_revisions(conn: sqlite3.Connection, company: str, fy_ids: list[str]) -> dict:
    """{(line, year_index): revision} between the oldest and newest consensus
    snapshots (revision = relative change; margins in percentage points)."""
    snaps = conn.execute(
        "SELECT as_of, data FROM consensus_snapshots WHERE company = ? ORDER BY as_of", (company,)
    ).fetchall()
    if len(snaps) < 2:
        return {}
    old, new = json.loads(snaps[0]["data"])["lines"], json.loads(snaps[-1]["data"])["lines"]

    def val(lines: dict, line: str, pid: str) -> float | None:
        if line in ("gross_margin", "op_margin"):
            num = lines.get("gross_profit" if line == "gross_margin" else "operating_income", {}).get(pid)
            den = lines.get("revenue", {}).get(pid)
            return num / den if num is not None and den else None
        return lines.get(line, {}).get(pid)

    out = {}
    for y, pid in enumerate(fy_ids, start=1):
        for line in ("revenue", "eps", "gross_margin", "op_margin"):
            a, b = val(old, line, pid), val(new, line, pid)
            if a is None or b is None:
                continue
            out[(line, y)] = (b - a) if line.endswith("margin") else ((b / a - 1) if a else None)
    return out


def _ahead_of_print(conn, company: str, impacts: dict, fy_ids: list[str], has_consensus: bool) -> list[dict]:
    revisions = _consensus_revisions(conn, company, fy_ids)
    flags = []
    for (line, year), t in impacts.items():
        net = t["up"] - t["down"]
        if abs(net) < _AHEAD_MIN_NET:
            continue
        label = driver_label(line, year)
        arrow = "↑" if net > 0 else "↓"
        if line == "multiple":
            flags.append({"line": line, "year": None, "net": net, "label": label,
                          "note": f"{abs(net)} net signals {arrow} on the multiple — moves before the numbers do"})
            continue
        rev = revisions.get((line, year))
        if rev is None:
            note = (f"{abs(net)} net signals {arrow} on {label}; "
                    + ("no consensus revision on record yet" if has_consensus else "no consensus loaded"))
        elif abs(rev) < _FLAT_REVISION:
            note = f"{abs(net)} net signals {arrow} on {label}; consensus unchanged"
        elif (rev > 0) != (net > 0):
            note = f"{abs(net)} net signals {arrow} on {label}; consensus moved the other way ({rev:+.1%})"
        else:
            continue  # consensus already moving with the evidence
        flags.append({"line": line, "year": year, "net": net, "label": label, "revision": rev, "note": note})
    return sorted(flags, key=lambda f: -abs(f["net"]))


# ── the screen ─────────────────────────────────────────────────────────────


def build_brain(conn: sqlite3.Connection, user_id: int, touch: bool = True) -> dict:
    """touch=False for background refreshes, so "since your last visit" keeps
    measuring from the last real visit."""
    now = _now()
    since30 = (now - timedelta(days=30)).isoformat()
    since7 = (now - timedelta(days=7)).isoformat()
    user = repo.get_user(conn, user_id)
    last_visit = user["last_brain_at"] if user and "last_brain_at" in user.keys() else None

    statuses = question_statuses(conn, user_id)
    flips = _record_flips(conn, user_id, statuses)
    theses = repo.list_theses(conn, user_id)
    q_by_company: dict[str, list] = defaultdict(list)
    for t in theses:
        q_by_company[t["company"]].append(t)

    hits = repo.thesis_hits_since(conn, user_id, since30, min_relevance=0.0, exclude_dropped=True)
    signals = [h for h in hits if h["tier"] == "signal"]

    securities = []
    for sec_row in repo.list_user_securities(conn, user_id):
        company = sec_row["company"]
        sec = resolve(conn, company) or {"company": company, "ticker": sec_row["ticker"], "category": sec_row["category"]}
        mine = [h for h in signals if h["company"] == company]
        supports = sum(h["relevance"] for h in mine if h["direction"] == "supports")
        contradicts = sum(h["relevance"] for h in mine if h["direction"] == "contradicts")
        by_class = {k: {"supports": 0, "contradicts": 0} for k in ("print", "chatter", "inside")}
        impacts: dict[tuple, dict] = defaultdict(lambda: {"up": 0, "down": 0})
        for h in mine:
            cls = source_class(h["show_format"], h["owner_user_id"] is not None)
            by_class[cls]["supports" if h["direction"] == "supports" else "contradicts"] += 1
            if h["impact_line"] and h["impact_dir"]:
                impacts[(h["impact_line"], h["impact_year"])][h["impact_dir"]] += 1
        status = _status(supports, contradicts)
        position = sec_row["position"] if "position" in sec_row.keys() else None

        base_row = conn.execute("SELECT data FROM model_bases WHERE company = ?", (company,)).fetchone()
        fy_ids, has_consensus = [], False
        if base_row:
            base = json.loads(base_row["data"])
            fy_ids = [p["id"] for p in sorted(base["periods"], key=lambda p: (p["fy"], p.get("q", 5)))
                      if p["kind"] == "FY" and not p["actual"]][:3]
            has_consensus = bool((base.get("consensus") or {}).get("lines"))

        q_flips = []
        for t in q_by_company.get(company, []):
            f = flips.get(t["id"])
            if f and f["at"] and datetime.fromisoformat(f["at"]) >= now - timedelta(hours=_FLIP_FRESH_HOURS):
                q_flips.append({"question": t["question"], **f})

        securities.append({
            "company": company,
            "ticker": sec.get("ticker"),
            "key": security_key(company, sec.get("ticker")),
            "category": sec.get("category") or sec_row["category"] or "Other",
            "position": position,
            "status": status,
            "display_status": invert(status) if position == "short" else status,
            "signals_7d": sum(1 for h in mine if (h["published_at"] or h["matched_at"]) >= since7),
            "signals_30d": len(mine),
            "supports": round(supports, 2),
            "contradicts": round(contradicts, 2),
            "by_class": by_class,
            "impacts": [
                {"line": line, "year": year, "label": driver_label(line, year), **t}
                for (line, year), t in sorted(impacts.items(), key=lambda kv: -(kv[1]["up"] + kv[1]["down"]))
            ],
            "ahead_of_print": _ahead_of_print(conn, company, impacts, fy_ids, has_consensus),
            "flips": q_flips,
            "questions": [
                {"id": t["id"], "question": t["question"],
                 "status": statuses.get(t["id"], {}).get("status", "none")}
                for t in q_by_company.get(company, [])
            ],
        })

    # Sector roll-up over the user's securities.
    sectors: dict[str, dict] = {}
    for s in securities:
        agg = sectors.setdefault(s["category"], {"category": s["category"], "supports": 0.0, "contradicts": 0.0,
                                                 "signals_7d": 0, "signals_30d": 0, "securities": 0})
        agg["supports"] += s["supports"]
        agg["contradicts"] += s["contradicts"]
        agg["signals_7d"] += s["signals_7d"]
        agg["signals_30d"] += s["signals_30d"]
        agg["securities"] += 1
    for agg in sectors.values():
        agg["status"] = _status(agg["supports"], agg["contradicts"])
        weekly = (agg["signals_30d"] - agg["signals_7d"]) / 3.3 if agg["signals_30d"] else 0
        agg["acceleration"] = round(agg["signals_7d"] / weekly - 1, 3) if weekly >= _MIN_BASELINE else None

    def strength(s: dict) -> float:
        net = s["supports"] - s["contradicts"]
        return net if s["position"] != "short" else -net

    longs = [s for s in securities if s["position"] != "short" and s["signals_30d"]]
    shorts = [s for s in securities if s["position"] == "short" and s["signals_30d"]]
    best_long = max(longs, key=strength, default=None)
    best_short = max(shorts, key=strength, default=None)
    # No shorts marked yet: suggest the weakest evidence among the rest.
    others = [s for s in longs if s is not best_long]
    short_candidate = None if best_short else min(others, key=lambda s: s["supports"] - s["contradicts"], default=None)

    tape = [
        {
            "hit_id": h["hit_id"], "company": h["company"], "ticker": h["ticker"],
            "question": h["question"], "claim": h["claim"], "direction": h["direction"],
            "impact": driver_label(h["impact_line"], h["impact_year"]) + (" ↑" if h["impact_dir"] == "up" else " ↓")
            if h["impact_line"] else None,
            "source_class": source_class(h["show_format"], h["owner_user_id"] is not None),
            "source": h["show_slug"], "published_at": h["published_at"] or h["matched_at"],
            "new": bool(last_visit and (h["matched_at"] or "") > last_visit),
        }
        for h in sorted(signals, key=lambda h: h["published_at"] or h["matched_at"], reverse=True)[:30]
    ]

    since = {
        "last_visit": last_visit,
        "new_signals": sum(1 for h in signals if last_visit and (h["matched_at"] or "") > last_visit),
        "flips": sum(1 for s in securities for f in s["flips"] if last_visit and f["at"] > last_visit),
    }
    if touch:
        conn.execute("UPDATE users SET last_brain_at = ? WHERE id = ?", (now.isoformat(), user_id))
        conn.commit()

    return {
        "generated_at": now.isoformat(),
        "since_last_visit": since,
        "velocity": narrative_velocity(conn),
        "sectors": sorted(sectors.values(), key=lambda a: -a["signals_30d"]),
        "securities": sorted(securities, key=lambda s: (s["category"], -_STATUS_ORDER[s["display_status"]], -s["signals_30d"])),
        "best_long": best_long and {"company": best_long["company"], "ticker": best_long["ticker"], "key": best_long["key"]},
        "best_short": best_short and {"company": best_short["company"], "ticker": best_short["ticker"], "key": best_short["key"]},
        "short_candidate": short_candidate and {"company": short_candidate["company"], "ticker": short_candidate["ticker"],
                                                "key": short_candidate["key"]},
        "tape": tape,
    }
