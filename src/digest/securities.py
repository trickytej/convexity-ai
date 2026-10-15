"""The security universe users can follow: the Scout watchlist's companies.

Each security has a URL key: its ticker when it has one, else a slug of its name
(privates such as Anthropic have no ticker).
"""

from __future__ import annotations

import re
import sqlite3

from .scout import roster


def security_key(company: str, ticker: str | None) -> str:
    if ticker:
        return ticker.upper()
    return re.sub(r"[^a-z0-9]+", "-", company.lower()).strip("-")


def universe(conn: sqlite3.Connection) -> list[dict]:
    """Watchlist categories → companies (people stripped), each with its key."""
    out: list[dict] = []
    for category in roster.load_watchlist(conn):
        companies = [
            {
                "company": c["name"],
                "ticker": c.get("ticker") or None,
                "key": security_key(c["name"], c.get("ticker")),
                "category": category.get("label"),
            }
            for c in category.get("companies", [])
            if c.get("name")
        ]
        if companies:
            out.append({"label": category.get("label"), "companies": companies})
    return out


def resolve(conn: sqlite3.Connection, key: str) -> dict | None:
    """Find a universe security by key, ticker, or exact company name."""
    k = key.strip()
    for category in universe(conn):
        for c in category["companies"]:
            if k.upper() == c["key"].upper() or k.lower() == c["company"].lower():
                return c
    return None
