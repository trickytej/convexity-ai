"""Scout detection cycle: search Podscan by founder/C-suite name."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .roster import COMPANIES
from .sources import PodscanAuthError, PodscanRateLimitError, search_episodes

log = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ScoutResult:
    new: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
    aborted: bool = False                # cycle stopped early (auth / quota) — not a full pass
    quota_reset_at: str | None = None    # ISO time the Podscan quota resets, when we hit it


def run_cycle(conn, *, days: int = 7) -> ScoutResult:
    """Search Podscan for every tracked person and persist confirmed appearances.

    Podscan's ``has_guests=true`` filter already limits results to actual guest
    appearances, so no additional regex filtering is needed here.
    """
    result = ScoutResult()

    for company in COMPANIES:
        for person in company.get("people", []):
            person_name = person["name"]
            person_role = person["role"]

            try:
                episodes = search_episodes(person_name, days=days)
            except PodscanAuthError as exc:
                result.errors.append(str(exc))
                result.aborted = True
                log.error("aborting scout cycle: %s", exc)
                conn.commit()  # keep appearances found before the abort
                return result
            except PodscanRateLimitError as exc:
                result.errors.append(str(exc))
                result.aborted = True
                if exc.reset_at is not None:
                    result.quota_reset_at = exc.reset_at.isoformat()
                log.error("aborting scout cycle: %s", exc)
                conn.commit()
                return result

            for ep in episodes:
                podscan_id = ep.get("podscan_id") or ""
                if not podscan_id:
                    continue

                try:
                    cur = conn.execute(
                        """
                        INSERT OR IGNORE INTO scout_appearances
                            (listennotes_id, company, person_name, person_role,
                             episode_title, podcast_name,
                             episode_url, audio_url, thumbnail, description,
                             published_at, duration_seconds, transcript, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            podscan_id,
                            company["name"],
                            person_name,
                            person_role,
                            ep["title"],
                            ep["podcast_name"],
                            ep["episode_url"],
                            ep["audio_url"],
                            ep["thumbnail"],
                            ep["description"],
                            ep["published_at"],
                            ep["duration"],
                            ep["transcript"],
                            _now_iso(),
                        ),
                    )
                    if cur.rowcount and cur.rowcount > 0:
                        result.new += 1
                        log.info(
                            "new appearance: %s — %s (%s)",
                            person_name,
                            ep["title"][:60],
                            ep["podcast_name"],
                        )
                    else:
                        result.skipped += 1
                except Exception as exc:
                    result.errors.append(f"{person_name}: {exc}")
                    log.warning("insert failed for %s: %s", person_name, exc)

    conn.commit()
    return result
