"""Per-security model: a shared base (imported vendor model, e.g. Canalyst) plus
each user's driver overrides, rendered by finmodel.compute.

Kept developments pin to the model line they move (thesis_hits.impact_line /
impact_year); the rendered model maps those to cells via `impact_cells`.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from datetime import datetime, timezone

from .finmodel import compute
from .theses import driver_label

log = logging.getLogger(__name__)

_OVERRIDE_KEY = re.compile(r"^[a-z_]+(:s\d+)?@(Q[1-4]-\d{4}|FY\d{4})$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def last_close(ticker: str | None) -> float | None:
    """Latest daily close from the vendored market-moves store (no API key)."""
    if not ticker:
        return None
    try:
        from moves.store.db import connect as moves_connect

        con = moves_connect(read_only=True)
        try:
            row = con.execute(
                "SELECT close FROM bars WHERE symbol = ? AND timeframe = 'day' "
                "ORDER BY ts DESC LIMIT 1",
                [ticker.upper()],
            ).fetchone()
        finally:
            con.close()
    except Exception as exc:  # store missing, locked by an ingest, or optional dep absent
        log.debug("last_close unavailable for %s: %s", ticker, exc)
        return None
    return float(row[0]) if row else None


# ── shared bases ─────────────────────────────────────────────────────────────


def save_base(conn: sqlite3.Connection, company: str, ticker: str | None, base: dict) -> None:
    conn.execute(
        "INSERT INTO model_bases (company, ticker, data, imported_at) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(company) DO UPDATE SET ticker = excluded.ticker, data = excluded.data, "
        "imported_at = excluded.imported_at",
        (company, ticker, json.dumps(base), _now()),
    )
    conn.commit()


def load_base(conn: sqlite3.Connection, company: str) -> dict | None:
    row = conn.execute("SELECT data FROM model_bases WHERE company = ?", (company,)).fetchone()
    return json.loads(row["data"]) if row else None


# ── per-user overrides ───────────────────────────────────────────────────────


def load_user_model(conn: sqlite3.Connection, user_id: int, company: str) -> dict:
    row = conn.execute(
        "SELECT data FROM security_models WHERE user_id = ? AND company = ?", (user_id, company)
    ).fetchone()
    data = json.loads(row["data"]) if row else {}
    return {
        "overrides": {k: v for k, v in (data.get("overrides") or {}).items() if _OVERRIDE_KEY.match(k)},
        "target_pe": data.get("target_pe"),
        "price": data.get("price"),
    }


def save_user_model(
    conn: sqlite3.Connection,
    user_id: int,
    company: str,
    overrides: dict,
    target_pe: float | None,
    price: float | None = None,
) -> None:
    clean = {k: float(v) for k, v in overrides.items() if v is not None and _OVERRIDE_KEY.match(k)}
    conn.execute(
        "INSERT INTO security_models (user_id, company, data, updated_at) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(user_id, company) DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at",
        (user_id, company, json.dumps({"overrides": clean, "target_pe": target_pe, "price": price}), _now()),
    )
    conn.commit()


def _impacts(conn: sqlite3.Connection, user_id: int, company: str) -> dict[str, dict]:
    """Kept hits, plus undecided signals, grouped by the model line they move."""
    rows = conn.execute(
        """
        SELECT h.id AS hit_id, h.impact_line, h.impact_year, h.impact_dir, h.decision, h.why, n.claim
        FROM thesis_hits h
        JOIN theses t  ON t.id = h.question_id
        JOIN nuggets n ON n.id = h.nugget_id
        WHERE t.user_id = ? AND t.company = ? AND t.active = 1
          AND h.impact_line IS NOT NULL
          AND (h.decision = 'kept' OR (h.decision = 'pending' AND h.tier = 'signal'))
        ORDER BY h.decision = 'kept' DESC, h.relevance DESC
        """,
        (user_id, company),
    ).fetchall()
    out: dict[str, dict] = {}
    for r in rows:
        cell = out.setdefault(f"{r['impact_line']}:{r['impact_year'] or ''}", {"up": 0, "down": 0, "hits": []})
        cell[r["impact_dir"]] = cell.get(r["impact_dir"], 0) + 1
        cell["hits"].append(
            {
                "hit_id": r["hit_id"],
                "claim": r["claim"],
                "why": r["why"],
                "impact_dir": r["impact_dir"],
                "decision": r["decision"],
                "label": driver_label(r["impact_line"], r["impact_year"]),
            }
        )
    return out


def build_model(conn: sqlite3.Connection, user_id: int, company: str, ticker: str | None) -> dict | None:
    """The user's rendered model for a security, or None when no base is loaded."""
    base = load_base(conn, company)
    if base is None:
        return None
    user = load_user_model(conn, user_id, company)
    market_price = last_close(ticker)
    price = user["price"] or market_price
    model = compute(base, user["overrides"], price=price, target_pe=user["target_pe"])
    model["market"]["market_price"] = market_price
    model["market"]["price_override"] = user["price"]
    model["impacts"] = _impacts(conn, user_id, company)
    model["override_count"] = len(user["overrides"])
    return model
