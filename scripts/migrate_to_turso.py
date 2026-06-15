#!/usr/bin/env python
"""Copy the local SQLite digest.db into a hosted Turso database.

Usage:
    TURSO_DATABASE_URL=libsql://<db>-<org>.turso.io \\
    TURSO_AUTH_TOKEN=<token> \\
    .venv/bin/python scripts/migrate_to_turso.py [--source data/digest.db]

It (1) creates the schema on Turso (idempotent) and (2) copies every row with
INSERT OR REPLACE in FK-safe order, so it is safe to re-run.

Alternative one-liner (Turso CLI): turso db create <name> --from-file ./data/digest.db
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

# FK-safe order: parents before children.
TABLES = [
    "shows",
    "episodes",
    "transcripts",
    "segments",
    "nuggets",
    "reports",
    "episode_digests",
    "nugget_curation",
]

# Cap bound parameters per statement well under SQLite's limit; with multi-row
# INSERTs this means one network round-trip per (MAX_VARS / columns) rows — critical
# when the DB is far away (e.g. laptop in AU, DB in us-east).
MAX_VARS = 900


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", default="data/digest.db", help="local SQLite file")
    args = ap.parse_args()

    if not (os.environ.get("TURSO_DATABASE_URL") or os.environ.get("LIBSQL_URL")):
        print("ERROR: set TURSO_DATABASE_URL (and TURSO_AUTH_TOKEN).", file=sys.stderr)
        return 2

    src_path = Path(args.source)
    if not src_path.exists():
        print(f"ERROR: source DB not found: {src_path}", file=sys.stderr)
        return 2

    src = sqlite3.connect(str(src_path))
    src.row_factory = sqlite3.Row

    # Destination uses the app's connector, which goes remote when TURSO_* is set.
    from digest.store import db as dbmod

    dst = dbmod.connect(Path("data/_migrate_placeholder.db"))
    print("Ensuring schema on Turso…")
    dbmod.init_db(dst)

    existing = {r[0] for r in src.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}

    total = 0
    for table in TABLES:
        if table not in existing:
            print(f"  {table}: (absent in source, skipped)", flush=True)
            continue
        rows = src.execute(f"SELECT * FROM {table}").fetchall()
        if not rows:
            print(f"  {table}: 0", flush=True)
            continue
        cols = list(rows[0].keys())
        ncols = len(cols)
        collist = ", ".join(cols)
        row_ph = "(" + ", ".join(["?"] * ncols) + ")"
        chunk = max(1, MAX_VARS // ncols)
        data = [tuple(r[c] for c in cols) for r in rows]
        for i in range(0, len(data), chunk):
            batch = data[i : i + chunk]
            sql = (
                f"INSERT OR REPLACE INTO {table} ({collist}) "
                f"VALUES {', '.join([row_ph] * len(batch))}"
            )
            flat = [v for row in batch for v in row]
            dst.execute(sql, flat)
            dst.commit()
        print(f"  {table}: {len(rows)}", flush=True)
        total += len(rows)

    src.close()
    dst.close()
    print(f"Done. Copied {total} rows to Turso.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
