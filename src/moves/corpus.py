"""Read-only bridge to the research-digest podcast corpus (digest.db).

Lets a price move be cross-referenced against what investors were *saying* on the
podcasts around that date — a differentiated attribution source. Matches nuggets
to a ticker via the entities JSON (which carries both tickers and company names)
and links each mention back to the exact transcript segment.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from moves.config import get_settings

# Common-name aliases per ticker (entities also store company names). The ticker
# itself is always matched as a quoted JSON token to avoid short-symbol noise.
TICKER_ALIASES: dict[str, list[str]] = {
    "NVDA": ["Nvidia"],
    "AMD": ["Advanced Micro"],
    "AVGO": ["Broadcom"],
    "MU": ["Micron"],
    "STX": ["Seagate"],
    "WDC": ["Western Digital", "SanDisk"],
    "TSM": ["TSMC", "Taiwan Semiconductor"],
    "ASML": ["ASML"],
    "AAPL": ["Apple"],
    "MSFT": ["Microsoft"],
    "GOOGL": ["Google", "Alphabet"],
    "AMZN": ["Amazon"],
    "META": ["Meta Platforms", "Facebook"],
    "SPY": ["S&P 500"],
    "QQQ": ["Nasdaq 100"],
    "SMH": ["semiconductor"],
}


@dataclass
class PodcastMention:
    nugget_id: int
    episode_id: int
    show_slug: str
    episode_title: str
    published_at: str | None
    speaker_name: str | None
    claim: str
    quote: str | None
    start_ms: int | None
    signal_score: float
    episode_url: str | None


def corpus_available() -> bool:
    return get_settings().resolved_digest_db_path is not None


def _patterns(ticker: str) -> list[str]:
    ticker = ticker.upper()
    pats = [f'%"{ticker}"%']  # quoted ticker token in entities
    pats += [f"%{alias}%" for alias in TICKER_ALIASES.get(ticker, [])]
    return pats


def find_mentions(
    ticker: str, since_date: str, until_date: str, *, limit: int = 8
) -> list[PodcastMention]:
    """Top podcast nuggets mentioning ``ticker`` in [since_date, until_date] (YYYY-MM-DD)."""
    path = get_settings().resolved_digest_db_path
    if path is None:
        return []
    patterns = _patterns(ticker)
    like = " OR ".join(["n.entities LIKE ?"] * len(patterns))
    sql = f"""
        SELECT n.id, n.episode_id, e.show_slug, e.title, e.published_at,
               n.speaker_name, n.claim, n.quote, n.start_ms, n.signal_score, e.episode_url
        FROM nuggets n JOIN episodes e ON e.id = n.episode_id
        WHERE e.published_at IS NOT NULL
          AND substr(e.published_at, 1, 10) BETWEEN ? AND ?
          AND ({like})
        ORDER BY n.signal_score DESC
        LIMIT ?
    """
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        rows = con.execute(sql, [since_date, until_date, *patterns, limit]).fetchall()
    finally:
        con.close()
    return [
        PodcastMention(
            nugget_id=r[0],
            episode_id=r[1],
            show_slug=r[2],
            episode_title=r[3],
            published_at=r[4],
            speaker_name=r[5],
            claim=r[6],
            quote=r[7],
            start_ms=r[8],
            signal_score=r[9] or 0.0,
            episode_url=r[10],
        )
        for r in rows
    ]


def deep_link(mention: PodcastMention) -> str:
    """Deep link to the transcript segment in the research-digest web app."""
    base = get_settings().digest_web_base.rstrip("/")
    anchor = f"#t-{mention.start_ms}" if mention.start_ms is not None else ""
    return f"{base}/episode/{mention.episode_id}{anchor}"
