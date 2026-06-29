"""Layer 2: newsletter — kept nuggets rendered for distribution."""

from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from datetime import date, datetime, timezone

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ...config import get_settings
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
    companies = entities.get("companies", []) or []
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
        companies=companies if isinstance(companies, list) else [],
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
        db, from_iso, to_iso, episode_ids or None, show_slug=show,
        exclude_show_slugs=["scout"] if not show and not episode_ids else None,
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


# --- email send ----------------------------------------------------------


class _NuggetEmail(BaseModel):
    claim: str
    quote: str | None = None
    speaker_name: str | None = None
    curation_note: str | None = None
    show_slug: str = ""


class _StockEmail(BaseModel):
    company: str
    stance: str = "mentioned"
    summary: str = ""


class NewsletterSendIn(BaseModel):
    to: list[str]
    subject: str
    show_name: str = ""
    lead: list[_NuggetEmail] = []
    good_to_know: list[_NuggetEmail] = []
    stocks: list[_StockEmail] = []


_STANCE_COLOR = {
    "owned": "#059669",
    "bullish": "#2563eb",
    "bearish": "#dc2626",
    "mentioned": "#71717a",
}


def _build_html(body: NewsletterSendIn) -> str:
    def nugget_html(n: _NuggetEmail) -> str:
        parts = [f'<p style="margin:0 0 4px;font-weight:600;color:#111">{n.claim}</p>']
        if n.quote:
            attr = f" — {n.speaker_name}" if n.speaker_name else ""
            parts.append(
                f'<blockquote style="margin:4px 0 4px 0;padding-left:10px;'
                f'border-left:3px solid #a5b4fc;color:#52525b;font-style:italic">'
                f'{n.quote}<span style="font-style:normal;color:#71717a">{attr}</span>'
                f'</blockquote>'
            )
        if n.curation_note:
            parts.append(f'<p style="margin:4px 0 0;font-size:12px;color:#71717a;font-style:italic">{n.curation_note}</p>')
        return (
            '<div style="padding:14px 0;border-bottom:1px solid #f4f4f5">'
            + "".join(parts)
            + "</div>"
        )

    def section_html(title: str, nuggets: list[_NuggetEmail]) -> str:
        if not nuggets:
            return ""
        items = "".join(nugget_html(n) for n in nuggets)
        return (
            f'<h2 style="font-size:15px;font-weight:700;color:#111;margin:28px 0 4px">{title}</h2>'
            + items
        )

    nuggets_html = section_html("Relevant Nuggets", body.lead) + section_html("Good to Know", body.good_to_know)

    stocks_html = ""
    if body.stocks:
        rows = ""
        for s in body.stocks:
            color = _STANCE_COLOR.get(s.stance, "#71717a")
            rows += (
                f'<tr style="border-bottom:1px solid #f4f4f5">'
                f'<td style="padding:8px 12px;font-weight:600;white-space:nowrap;color:#111">{s.company}</td>'
                f'<td style="padding:8px 8px"><span style="background:{color};color:#fff;border-radius:9999px;'
                f'padding:2px 8px;font-size:11px;font-weight:600">{s.stance.capitalize()}</span></td>'
                f'<td style="padding:8px 8px;font-size:13px;color:#52525b">{s.summary}</td>'
                f'</tr>'
            )
        stocks_html = (
            '<h2 style="font-size:15px;font-weight:700;color:#111;margin:28px 0 8px">Stock Read-Through</h2>'
            f'<table style="width:100%;border-collapse:collapse">{rows}</table>'
        )

    date_str = datetime.now(timezone.utc).strftime("%B %d, %Y")
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:system-ui,sans-serif;max-width:680px;margin:0 auto;padding:24px 16px;color:#111;background:#fff">
  <p style="font-size:12px;color:#a1a1aa;margin:0 0 4px">{date_str}</p>
  <h1 style="font-size:22px;font-weight:700;margin:0 0 4px">{body.show_name}</h1>
  <p style="font-size:13px;color:#71717a;margin:0 0 24px">Podcast Insights Digest</p>
  <hr style="border:none;border-top:1px solid #e4e4e7;margin:0 0 8px">
  {nuggets_html}
  {stocks_html}
  <hr style="border:none;border-top:1px solid #e4e4e7;margin:28px 0 8px">
  <p style="font-size:11px;color:#a1a1aa">Generated by TMTB: Podcast Insights</p>
</body></html>"""


@router.post("/newsletter/send", status_code=200)
def send_newsletter(body: NewsletterSendIn) -> dict:
    settings = get_settings()
    if not settings.smtp_host or not settings.smtp_user:
        raise HTTPException(
            status_code=503,
            detail="SMTP not configured. Set DIGEST_SMTP_HOST, DIGEST_SMTP_USER, DIGEST_SMTP_PASS, DIGEST_SMTP_FROM in .env",
        )
    if not body.to:
        raise HTTPException(status_code=422, detail="No recipients provided")

    html = _build_html(body)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = body.subject or f"{body.show_name} — Podcast Insights"
    msg["From"] = settings.smtp_from or settings.smtp_user
    msg["To"] = ", ".join(body.to)
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(settings.smtp_user, settings.smtp_pass)
            smtp.sendmail(msg["From"], body.to, msg.as_string())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Send failed: {exc}") from exc

    return {"sent": len(body.to)}
