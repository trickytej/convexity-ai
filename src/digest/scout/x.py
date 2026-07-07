"""X (Twitter) side of Scout: tracked accounts, timeline pulls, tweet→nugget sync.

Each tracked handle gets one long-lived episode (show slug ``x``, guid
``x:<handle>``) and every new tweet in the refresh window is minted verbatim
as one nugget on that episode — no LLM involved. From there the tweets ride
the exact same keep/kill curation → newsletter flow as podcast insights.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import httpx

from ..registry import Show
from ..store import repo
from ..store.models import Episode, EpisodeStatus, Nugget

log = logging.getLogger(__name__)

_BASE = "https://api.x.com/2"
_REQUEST_DELAY_SECONDS = 1.0
_MAX_PAGES_PER_HANDLE = 3      # 100 tweets/page — plenty for a refresh window

X_SHOW_SLUG = "x"
_X_SHOW = Show(
    slug=X_SHOW_SLUG,
    name="X",
    tier="B",
    transcript_source="asr",
    active=True,
)

_ACCOUNTS_META_KEY = "scout_x_accounts"
_USER_IDS_META_KEY = "scout_x_user_ids"   # handle(lower) -> X user id cache

# The API process never runs store.db.init_db (only the CLI does), so the
# hosted DB needs the table ensured before the first tweet sync touches it.
_TWEETS_DDL = """
CREATE TABLE IF NOT EXISTS scout_tweets (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    tweet_id    TEXT UNIQUE NOT NULL,
    handle      TEXT NOT NULL,
    author_name TEXT,
    text        TEXT NOT NULL,
    url         TEXT,
    created_at  TEXT,
    metrics     TEXT,
    episode_id  INTEGER,
    nugget_id   INTEGER,
    fetched_at  TEXT NOT NULL
);
"""


class XAuthError(Exception):
    """X_BEARER_TOKEN is missing or X rejected it (401/403)."""


class XRateLimitError(Exception):
    """X request quota exhausted (HTTP 429). Carries ``reset_at`` when known."""

    def __init__(self, message: str, reset_at: datetime | None = None) -> None:
        super().__init__(message)
        self.reset_at = reset_at


def ensure_schema(conn) -> None:
    conn.execute(_TWEETS_DDL)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_scout_tweets_handle ON scout_tweets(handle)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_scout_tweets_created ON scout_tweets(created_at DESC)"
    )
    conn.commit()


# ── Tracked accounts ──────────────────────────────────────────────────────────

def normalize_handle(raw: str) -> str:
    """`@Handle `, `x.com/Handle`, `Handle` → `Handle` (case preserved)."""
    h = raw.strip().lstrip("@")
    for prefix in ("https://", "http://"):
        if h.startswith(prefix):
            h = h[len(prefix):]
    for host in ("x.com/", "twitter.com/", "www.x.com/", "www.twitter.com/"):
        if h.lower().startswith(host):
            h = h[len(host):]
    return h.split("/")[0].split("?")[0].strip()


def load_accounts(conn) -> list[str]:
    raw = repo.meta_get(conn, _ACCOUNTS_META_KEY)
    if raw:
        try:
            handles = json.loads(raw)
            if isinstance(handles, list):
                return [h for h in handles if isinstance(h, str) and h]
        except ValueError:
            pass
    return []


def save_accounts(conn, handles: list[str]) -> list[str]:
    """Normalize, dedupe (case-insensitive, first spelling wins), persist."""
    seen: dict[str, str] = {}
    for raw in handles:
        h = normalize_handle(raw)
        if h and h.lower() not in seen:
            seen[h.lower()] = h
    cleaned = list(seen.values())
    repo.meta_set(conn, _ACCOUNTS_META_KEY, json.dumps(cleaned))
    return cleaned


# ── X API v2 client ───────────────────────────────────────────────────────────

_last_request_at = 0.0


def _throttle() -> None:
    global _last_request_at
    wait = _last_request_at + _REQUEST_DELAY_SECONDS - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    _last_request_at = time.monotonic()


def _rate_limit_error(resp: httpx.Response) -> XRateLimitError:
    reset_at = None
    raw = resp.headers.get("x-rate-limit-reset")
    if raw:
        try:
            reset_at = datetime.fromtimestamp(int(raw), tz=timezone.utc)
        except (ValueError, OverflowError, OSError):
            pass
    when = f" — resets at {reset_at.strftime('%Y-%m-%d %H:%M UTC')}" if reset_at else ""
    return XRateLimitError(f"X API rate limit exhausted (HTTP 429){when}", reset_at)


def _api_get(client: httpx.Client, path: str, params: dict, token: str) -> dict:
    _throttle()
    resp = client.get(
        f"{_BASE}{path}", params=params, headers={"Authorization": f"Bearer {token}"}
    )
    if resp.status_code == 429:
        raise _rate_limit_error(resp)
    if resp.status_code in (401, 403):
        raise XAuthError(
            f"X rejected the bearer token (HTTP {resp.status_code}) — check X_BEARER_TOKEN"
        )
    resp.raise_for_status()
    return resp.json()


def _resolve_user(client: httpx.Client, conn, handle: str, token: str) -> dict | None:
    """Return {"id": ..., "name": ...} for a handle, caching ids in app_meta so
    repeat refreshes don't burn a users-lookup request per handle."""
    cache: dict[str, dict] = {}
    raw = repo.meta_get(conn, _USER_IDS_META_KEY)
    if raw:
        try:
            cache = json.loads(raw)
        except ValueError:
            cache = {}

    cached = cache.get(handle.lower())
    if isinstance(cached, dict) and cached.get("id"):
        return cached

    data = _api_get(
        client, f"/users/by/username/{handle}", {"user.fields": "name"}, token
    )
    user = data.get("data")
    if not user or not user.get("id"):
        return None
    entry = {"id": user["id"], "name": user.get("name") or handle}
    cache[handle.lower()] = entry
    repo.meta_set(conn, _USER_IDS_META_KEY, json.dumps(cache))
    return entry


def fetch_tweets(
    client: httpx.Client, user_id: str, token: str, *, days: int
) -> list[dict]:
    """Original posts (no retweets/replies) from the last *days* days."""
    start_time = (
        (datetime.now(timezone.utc) - timedelta(days=days))
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )
    collected: list[dict] = []
    pagination_token: str | None = None

    for _ in range(_MAX_PAGES_PER_HANDLE):
        params: dict = {
            "max_results": 100,
            "start_time": start_time,
            "exclude": "retweets,replies",
            "tweet.fields": "created_at,public_metrics",
        }
        if pagination_token:
            params["pagination_token"] = pagination_token
        data = _api_get(client, f"/users/{user_id}/tweets", params, token)
        collected.extend(data.get("data") or [])
        pagination_token = (data.get("meta") or {}).get("next_token")
        if not pagination_token:
            break

    return collected


# ── Sync: tweets → scout_tweets rows + keep/kill nuggets ─────────────────────

@dataclass
class XSyncResult:
    new: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
    handles_synced: int = 0
    rate_limit_reset_at: str | None = None


def _ensure_handle_episode(conn, handle: str, author_name: str | None) -> int:
    """One persistent episode per handle buckets its tweet-nuggets."""
    if not conn.execute("SELECT slug FROM shows WHERE slug = ?", (X_SHOW_SLUG,)).fetchone():
        repo.sync_shows(conn, [_X_SHOW])

    guid = f"x:{handle.lower()}"
    existing = repo.get_episode_by_guid(conn, X_SHOW_SLUG, guid)
    if existing is not None:
        return existing.id

    ep = Episode(
        show_slug=X_SHOW_SLUG,
        guid=guid,
        title=f"@{handle}" + (f" — {author_name}" if author_name else "") + " on X",
        episode_url=f"https://x.com/{handle}",
        published_at=datetime.now(timezone.utc),
        status=EpisodeStatus.INSIGHTS_EXTRACTED,  # nuggets are minted directly
    )
    episode_id, _ = repo.upsert_episode(conn, ep)
    repo.set_status(conn, episode_id, EpisodeStatus.INSIGHTS_EXTRACTED)
    return episode_id


def _mint_tweet_nugget(conn, episode_id: int, handle: str, tweet: dict) -> int:
    """1 tweet = 1 keep/kill card, verbatim — curation is the filter."""
    return repo.add_nugget(
        conn,
        Nugget(
            episode_id=episode_id,
            type="watch_item",
            claim=tweet.get("text") or "",
            quote=None,
            speaker_name=f"@{handle}",
            signal_score=0.0,
            triage="pending",
            model="x-verbatim",
        ),
    )


def sync_x_accounts(conn, settings, *, days: int = 7) -> XSyncResult:
    """Pull the refresh window's tweets for every tracked handle and mint a
    nugget per new tweet. Commits per handle so a mid-run failure keeps
    everything already synced."""
    result = XSyncResult()

    handles = load_accounts(conn)
    if not handles:
        return result

    token = getattr(settings, "x_bearer_token", None)
    if not token:
        result.errors.append(
            "X accounts are tracked but X_BEARER_TOKEN is not set — tweets were not synced."
        )
        return result

    ensure_schema(conn)
    now_iso = datetime.now(timezone.utc).isoformat()

    with httpx.Client(timeout=20) as client:
        for handle in handles:
            try:
                user = _resolve_user(client, conn, handle, token)
                if user is None:
                    result.errors.append(f"@{handle}: account not found on X")
                    continue

                episode_id = _ensure_handle_episode(conn, handle, user.get("name"))

                for tweet in fetch_tweets(client, user["id"], token, days=days):
                    tweet_id = tweet.get("id")
                    text = (tweet.get("text") or "").strip()
                    if not tweet_id or not text:
                        continue
                    cur = conn.execute(
                        """
                        INSERT OR IGNORE INTO scout_tweets
                            (tweet_id, handle, author_name, text, url, created_at,
                             metrics, episode_id, fetched_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            tweet_id,
                            handle,
                            user.get("name"),
                            text,
                            f"https://x.com/{handle}/status/{tweet_id}",
                            tweet.get("created_at"),
                            json.dumps(tweet.get("public_metrics"))
                            if tweet.get("public_metrics") else None,
                            episode_id,
                            now_iso,
                        ),
                    )
                    if cur.rowcount and cur.rowcount > 0:
                        nugget_id = _mint_tweet_nugget(conn, episode_id, handle, tweet)
                        conn.execute(
                            "UPDATE scout_tweets SET nugget_id = ? WHERE tweet_id = ?",
                            (nugget_id, tweet_id),
                        )
                        result.new += 1
                    else:
                        result.skipped += 1

                conn.commit()
                result.handles_synced += 1

            except XAuthError as exc:
                result.errors.append(str(exc))
                conn.commit()
                return result  # every remaining handle would fail identically
            except XRateLimitError as exc:
                result.errors.append(str(exc))
                if exc.reset_at is not None:
                    result.rate_limit_reset_at = exc.reset_at.isoformat()
                conn.commit()
                return result
            except Exception as exc:
                result.errors.append(f"@{handle}: {exc}")
                log.warning("X sync failed for @%s: %s", handle, exc)

    conn.commit()
    return result


def list_tweet_buckets(conn, *, days: int = 7) -> list[dict]:
    """Tweets from the window grouped by handle, each carrying its nugget id —
    the frontend joins these to nuggets-with-curation for keep/kill cards."""
    ensure_schema(conn)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    rows = conn.execute(
        """
        SELECT t.tweet_id, t.handle, t.author_name, t.url, t.created_at, t.metrics,
               n.id, n.episode_id, n.type, n.claim, n.quote,
               n.speaker_name, n.start_ms, n.end_ms, n.entities, n.sectors,
               n.primary_sector, n.scores, n.signal_score, n.quote_verified, n.triage,
               nc.decision, nc.curator_rank, nc.contradicts_consensus,
               nc.note AS curation_note, nc.updated_at AS curation_updated_at
        FROM scout_tweets t
        JOIN nuggets n ON n.id = t.nugget_id
        LEFT JOIN nugget_curation nc ON nc.nugget_id = n.id
        WHERE t.created_at >= ?
        ORDER BY t.handle COLLATE NOCASE ASC, t.created_at DESC
        """,
        (cutoff,),
    ).fetchall()

    buckets: dict[str, dict] = {}
    for r in rows:
        key = r["handle"].lower()
        bucket = buckets.setdefault(
            key,
            {
                "handle": r["handle"],
                "author_name": r["author_name"],
                "episode_id": r["episode_id"],
                "tweets": [],
            },
        )
        bucket["tweets"].append(r)
    return list(buckets.values())
