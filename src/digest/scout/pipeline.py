"""Scout detection cycle: search Listen Notes by founder/C-suite name."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .roster import COMPANIES
from .sources import search_episodes

log = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pub_date(ms: int | None) -> str | None:
    if not ms:
        return None
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()


# ── Guest-appearance filter ───────────────────────────────────────────────────
#
# Listen Notes `only_in=title` catches any episode where the person's name
# appears in the title — including analysis, news, and opinion episodes where
# the person is merely discussed.  These patterns separate actual appearances
# (person is a guest/speaker) from editorial coverage (person is a subject).

def _is_guest_appearance(person_name: str, title: str, description: str) -> bool:
    """Return True only when the episode is likely an actual guest appearance."""
    # Use last name for matching (avoids e.g. "Tim" matching unrelated people)
    last = re.escape(person_name.split()[-1].lower())
    title_l = title.lower()
    desc_l  = description.lower()[:2000]

    # ── Reject: editorial/analysis titles, not appearances ───────────────────
    noise_title = [
        rf"^(why|what|how|is|are|was|can|will|did)\s+{last}",   # "Why Jensen Huang..."
        rf"^(the|a|an)\s+\w+\s+of\s+{last}",                    # "The Rise of Jensen Huang"
        rf"\b{last}'s\b",                                         # "Jensen Huang's $3T bet"
        rf"\b(story|rise|fall|legacy|impact|future|vision|guide|profile)\s+of\s+{last}",
        rf"\b(about|analyzing|dissecting|breaking\s+down)\s+{last}",
        rf"\beverything\s+{last}\s+(said|told)",                  # "Everything X Said"
        rf"\bwhat\s+{last}\s+(said|told|revealed|thinks)",
    ]
    for pat in noise_title:
        if re.search(pat, title_l):
            log.debug("skip (editorial): %s | %s", person_name, title[:80])
            return False

    # ── Accept: title patterns that are almost always a guest appearance ──────
    guest_title = [
        rf"\b{last}\s*:",                           # "Jensen Huang: ..."        (most common)
        rf":\s*[^|]{{0,50}}\b{last}\b",            # "...: Jensen Huang"         (reversed)
        rf"\bwith\s+{last}\b",                      # "with Jensen Huang"
        rf"#\s*\d+[^|]{{0,60}}\b{last}\b",         # "#384 ... Jensen Huang"
        rf"\b{last}\b[^|]{{0,60}}#\s*\d+",         # "Jensen Huang ... #384"
        rf"\b(ep|episode)\s*\d+[^|]{{0,60}}\b{last}\b",
        rf"\b{last}\b[^|]{{0,60}}\b(ep|episode)\s*\d+",
        rf"\binterview\b[^|]{{0,60}}\b{last}\b",   # "Interview with Jensen Huang"
        rf"\b{last}\b[^|]{{0,60}}\binterview\b",
        rf"\b{last}\b[^|]{{0,60}}\bon\b\s+\w",     # "Jensen Huang on Chips..."
        rf"\b{last},\s",                             # "Jensen Huang, CEO of..."  (guest bio)
        rf"\b{last}\b[^|]{{0,10}}\|",               # "Jensen Huang | Podcast"   (pipe title)
        rf"\|\s*[^|]{{0,30}}\b{last}\b",            # "Podcast | Jensen Huang"
        rf"\b{last}\b[^|]{{0,60}}\b(joins?|joined)\b",
        rf"\b(guest|keynote|fireside)\b[^|]{{0,60}}\b{last}\b",
    ]
    for pat in guest_title:
        if re.search(pat, title_l):
            return True

    # ── Accept: description confirms the person is a guest/speaker ───────────
    guest_desc = [
        rf"\b{last}\b[^.{{0,120}}]\b(joins?|joining|joined)\b",
        rf"\b(joins?|joining|joined)\b[^.{{0,120}}]\b{last}\b",
        rf"\b(my|our|today.s|this week.s|special)\s+guest[^.{{0,120}}]\b{last}\b",
        rf"\b{last}\b[^.{{0,120}}]\b(discusses?|shares?|talks?\s+about|explains?)\b",
        rf"\b(welcome|welcoming)\b[^.{{0,120}}]\b{last}\b",
        rf"\binterview(?:ed|ing)?\b[^.{{0,120}}]\b{last}\b",
        rf"\b{last}\b[^.{{0,120}}]\binterview",
        rf"\bsits?\s+down\b[^.{{0,120}}]\b{last}\b",
        rf"\b{last}\b[^.{{0,120}}]\bsits?\s+down",
        rf"\bin\s+this\s+(episode|conversation|interview)[^.{{0,120}}]\b{last}\b",
        rf"\bspeak(?:s|ing)?\s+with\b[^.{{0,120}}]\b{last}\b",
        rf"\bin\s+conversation\s+with\b[^.{{0,120}}]\b{last}\b",
    ]
    for pat in guest_desc:
        if re.search(pat, desc_l):
            return True

    # No guest signal found — skip to avoid editorial noise
    log.debug("skip (no guest signal): %s | %s", person_name, title[:80])
    return False


# ── Main cycle ────────────────────────────────────────────────────────────────

@dataclass
class ScoutResult:
    new: int = 0
    skipped: int = 0
    filtered: int = 0
    errors: list[str] = field(default_factory=list)


def run_cycle(conn, *, days: int = 7) -> ScoutResult:
    """Search Listen Notes for every tracked person and persist confirmed appearances.

    Searches by person name in episode titles, then applies a guest-appearance
    filter to exclude editorial/analysis episodes where the person is discussed
    but not actually speaking.
    """
    result = ScoutResult()

    for company in COMPANIES:
        for person in company.get("people", []):
            person_name = person["name"]
            person_role = person["role"]

            episodes = search_episodes(person_name, days=days)
            for ep in episodes:
                ln_id = ep.get("id") or ""
                if not ln_id:
                    continue

                title     = (ep.get("title_original") or "").strip()
                podcast   = (ep.get("podcast") or {}).get("title_original") or ""
                url       = ep.get("link") or ""
                audio     = ep.get("audio") or ""
                thumbnail = ep.get("thumbnail") or ""
                desc_full = (ep.get("description_original") or "")
                pub       = _pub_date(ep.get("pub_date_ms"))

                # Filter: only keep actual guest appearances
                if not _is_guest_appearance(person_name, title, desc_full):
                    result.filtered += 1
                    continue

                desc_stored = desc_full[:600]

                try:
                    cur = conn.execute(
                        """
                        INSERT OR IGNORE INTO scout_appearances
                            (listennotes_id, company, person_name, person_role,
                             episode_title, podcast_name,
                             episode_url, audio_url, thumbnail, description,
                             published_at, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (ln_id, company["name"], person_name, person_role,
                         title, podcast, url, audio, thumbnail, desc_stored, pub, _now_iso()),
                    )
                    if cur.rowcount and cur.rowcount > 0:
                        result.new += 1
                        log.info("new appearance: %s — %s (%s)", person_name, title[:60], podcast)
                    else:
                        result.skipped += 1
                except Exception as exc:
                    result.errors.append(f"{person_name}: {exc}")
                    log.warning("insert failed for %s: %s", person_name, exc)

    conn.commit()
    return result
