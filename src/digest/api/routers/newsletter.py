"""Layer 2: newsletter — kept nuggets rendered for distribution."""

from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

from ...store import repo
from ..deps import get_db
from ..schemas import NewsletterNuggetOut, NewsletterOut, StockMentionOut

router = APIRouter(tags=["newsletter"])


def _parse_date(value: str, param: str, *, end_of_day: bool = False) -> str:
    """Validate YYYY-MM-DD and return as ISO string with time component."""
    try:
        d = date.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"{param} must be YYYY-MM-DD")
    if end_of_day:
        return datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=timezone.utc).isoformat()
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc).isoformat()


def _nugget_out(row: sqlite3.Row) -> NewsletterNuggetOut:
    entities = json.loads(row["entities"]) if row["entities"] else {}
    sectors = json.loads(row["sectors"]) if row["sectors"] else []
    tickers = entities.get("tickers", []) or []
    return NewsletterNuggetOut(
        id=row["id"],
        episode_id=row["episode_id"],
        show_slug=row["show_slug"],
        episode_title=row["episode_title"],
        episode_published_at=row["episode_published_at"],
        type=row["type"],
        claim=row["claim"],
        quote=row["quote"],
        speaker_name=row["speaker_name"],
        start_ms=row["start_ms"],
        sectors=sectors if isinstance(sectors, list) else [],
        primary_sector=row["primary_sector"] if "primary_sector" in row.keys() else None,
        tickers=tickers if isinstance(tickers, list) else [],
        curator_rank=row["curator_rank"],
        contradicts_consensus=bool(row["contradicts_consensus"] or 0),
        curation_note=row["curation_note"],
    )


_STANCE_PRIORITY = {"bearish": 0, "bullish": 1, "owned": 2, "mentioned": 3}
_STANCE_SORT = {"bearish": 0, "bullish": 0, "owned": 1, "mentioned": 2}


def _build_stock_readthrough_from_digests(digest_stocks: list[dict]) -> list[StockMentionOut]:
    """Aggregate LLM-generated stock entries from episode digests."""
    company_data: dict[str, dict] = defaultdict(
        lambda: {"stance": "mentioned", "summaries": [], "source_episode_id": None, "source_start_ms": None, "count": 0}
    )
    for s in digest_stocks:
        company = (s.get("company") or "").strip()
        if not company:
            continue
        d = company_data[company]
        d["count"] += 1
        if _STANCE_PRIORITY.get(s.get("stance", "mentioned"), 3) < _STANCE_PRIORITY.get(d["stance"], 3):
            d["stance"] = s.get("stance", "mentioned")
        summary = (s.get("summary") or "").strip()
        if summary and summary not in d["summaries"]:
            d["summaries"].append(summary)
        if d["source_episode_id"] is None:
            sources = s.get("sources") or []
            if sources:
                d["source_episode_id"] = sources[0].get("episode_id")
                d["source_start_ms"] = sources[0].get("start_ms")
    return sorted(
        [
            StockMentionOut(
                company=company,
                tickers=[],
                mention_count=data["count"],
                nugget_ids=[],
                stance=data["stance"],
                summary=" · ".join(data["summaries"]),
                source_episode_id=data["source_episode_id"],
                source_start_ms=data["source_start_ms"],
            )
            for company, data in company_data.items()
        ],
        key=lambda s: (_STANCE_SORT.get(s.stance, 2), -s.mention_count, s.company),
    )


def _build_stock_readthrough_from_nuggets(rows: list[sqlite3.Row]) -> list[StockMentionOut]:
    """Fallback: group kept nuggets by company when no episode digest exists."""
    company_data: dict[str, dict] = defaultdict(
        lambda: {"tickers": set(), "ids": [], "summary": "", "episode_id": None, "start_ms": None}
    )
    for row in rows:
        entities = json.loads(row["entities"]) if row["entities"] else {}
        companies = entities.get("companies") or []
        tickers = entities.get("tickers") or []
        for company in companies:
            d = company_data[company]
            d["tickers"].update(tickers)
            d["ids"].append(row["id"])
            if not d["summary"]:
                raw = (row["curation_note"] or "").strip() or (row["claim"] or "").strip()
                d["summary"] = raw[:150] + ("…" if len(raw) > 150 else "")
                d["episode_id"] = row["episode_id"]
                d["start_ms"] = row["start_ms"]
    return sorted(
        [
            StockMentionOut(
                company=company,
                tickers=sorted(data["tickers"]),
                mention_count=len(data["ids"]),
                nugget_ids=data["ids"],
                stance="mentioned",
                summary=data["summary"],
                source_episode_id=data["episode_id"],
                source_start_ms=data["start_ms"],
            )
            for company, data in company_data.items()
        ],
        key=lambda s: (-s.mention_count, s.company),
    )


def _render_markdown(
    from_date: str | None,
    to_date: str | None,
    lead: list[NewsletterNuggetOut],
    good_to_know: list[NewsletterNuggetOut],
    stocks: list[StockMentionOut],
    episode_count: int,
    kept_count: int,
) -> str:
    from_label = from_date[:10] if from_date else "all time"
    to_label = to_date[:10] if to_date else ""
    date_range = f"{from_label} – {to_label}" if to_label else from_label
    lines: list[str] = [
        f"# Research Digest · {date_range}",
        "",
        f"_{episode_count} episode{'s' if episode_count != 1 else ''} · "
        f"{kept_count} kept insight{'s' if kept_count != 1 else ''}_",
        "",
        "---",
        "",
    ]

    if lead:
        lines += ["## 🔥 Lead", ""]
        for n in lead:
            lines.append(f"**{n.speaker_name or 'Unknown'}** · {n.show_slug}")
            if n.quote:
                lines.append(f"> {n.quote}")
            if n.curation_note:
                lines.append(f"_{n.curation_note}_")
            if n.start_ms is not None:
                lines.append(
                    f"[In context →](http://localhost:3000/episode/{n.episode_id}?t={n.start_ms})"
                )
            lines.append("")
        lines += ["---", ""]

    if good_to_know:
        lines += ["## 📌 Good to Know", ""]
        for n in good_to_know:
            speaker = f"**{n.speaker_name}**" if n.speaker_name else ""
            rank_label = f" _(rank {n.curator_rank})_" if n.curator_rank else ""
            lines.append(f"- {speaker} · {n.show_slug}{rank_label}")
            if n.quote:
                lines.append(f"  > {n.quote}")
            if n.curation_note:
                lines.append(f"  _{n.curation_note}_")
            lines.append("")
        lines += ["---", ""]

    if stocks:
        lines += ["## Stock Read-Through", ""]
        for s in stocks:
            stance_label = s.stance.capitalize()
            lines.append(f"**{s.company}** · _{stance_label}_")
            if s.summary:
                lines.append(s.summary)
            lines.append("")
        lines += ["---", ""]

    lines.append(f"_Generated by research-digest · {datetime.now(timezone.utc).date()}_")
    return "\n".join(lines)


@router.get("/newsletter", response_model=NewsletterOut)
def get_newsletter(
    from_date: str | None = Query(None, alias="from", description="YYYY-MM-DD"),
    to_date: str | None = Query(None, alias="to", description="YYYY-MM-DD"),
    show: str | None = Query(None, description="Filter by show slug"),
    episode_ids: list[int] = Query(default=[], description="Restrict to specific episode ids"),
    db: sqlite3.Connection = Depends(get_db),
) -> NewsletterOut:
    from_iso = _parse_date(from_date, "from") if from_date else None
    to_iso = _parse_date(to_date, "to", end_of_day=True) if to_date else None
    if from_iso and to_iso and from_iso > to_iso:
        raise HTTPException(status_code=422, detail="'from' must be before 'to'")

    rows = repo.list_kept_nuggets_for_newsletter(
        db, from_iso, to_iso, episode_ids or None, show_slug=show
    )

    lead = [_nugget_out(r) for r in rows if r["curator_rank"] == 1]
    good_to_know = [_nugget_out(r) for r in rows if r["curator_rank"] != 1]

    ep_ids = list({r["episode_id"] for r in rows})
    digest_stocks = repo.list_digest_stocks_for_episodes(db, ep_ids)
    stocks = (
        _build_stock_readthrough_from_digests(digest_stocks)
        if digest_stocks
        else _build_stock_readthrough_from_nuggets(rows)
    )

    episode_count = len(ep_ids)
    kept_count = len(rows)

    markdown = _render_markdown(
        from_date, to_date, lead, good_to_know, stocks, episode_count, kept_count
    )

    return NewsletterOut(
        from_date=from_date,
        to_date=to_date,
        episode_count=episode_count,
        kept_count=kept_count,
        lead=lead,
        good_to_know=good_to_know,
        stock_readthrough=stocks,
        markdown=markdown,
    )
