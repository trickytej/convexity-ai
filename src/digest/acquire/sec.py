"""SEC EDGAR filings for followed securities — the "consensus in print" source.

For each followed ticker, pulls recent filings that carry new information:
  - 8-K / 6-K: material events and earnings (press release + exhibits)
  - 10-Q / 10-K: the MD&A section only (the full document is mostly boilerplate)
Each filing becomes a shared corpus document (documents.SEC_SHOW), so its
nuggets are matched against every user's questions.

EDGAR's fair-access policy: <= 10 requests/second with a descriptive
User-Agent (Settings.sec_user_agent).
"""

from __future__ import annotations

import logging
import re
import sqlite3
import time
import warnings
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

import httpx
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

from ..config import Settings, get_settings

log = logging.getLogger(__name__)
# Filings are inline-XBRL XHTML; the HTML parser handles them fine.
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
_ARCHIVE = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}"

FORMS = ("8-K", "6-K", "10-Q", "10-K")
# 8-K items worth reading: results, Reg FD, other events, material agreements,
# acquisitions, leadership changes. Skips e.g. 5.07 (vote results) on its own.
_8K_ITEMS = {"1.01", "2.01", "2.02", "5.02", "7.01", "8.01"}
_MAX_EXHIBITS = 2
_MAX_CHARS = 60_000


@dataclass
class Filing:
    ticker: str
    cik: int
    form: str
    filed: date
    accession: str
    primary_doc: str
    items: str

    @property
    def url(self) -> str:
        return f"{_ARCHIVE.format(cik=self.cik, acc=self.accession.replace('-', ''))}/{self.primary_doc}"

    @property
    def title(self) -> str:
        what = {
            "8-K": "8-K", "6-K": "6-K", "10-Q": "10-Q (MD&A)", "10-K": "10-K (MD&A)",
        }[self.form]
        if self.form == "8-K" and "2.02" in self.items:
            what = "8-K earnings release"
        return f"{self.ticker} {what} · {self.filed.isoformat()}"


class EdgarClient:
    def __init__(self, settings: Settings | None = None) -> None:
        settings = settings or get_settings()
        self._http = httpx.Client(
            timeout=httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=10.0),
            headers={"User-Agent": settings.sec_user_agent},
            follow_redirects=True,
        )
        self._last = 0.0
        self._ciks: dict[str, int] | None = None

    def close(self) -> None:
        self._http.close()

    def _get(self, url: str) -> httpx.Response:
        wait = 0.15 - (time.monotonic() - self._last)  # stay well under 10 req/s
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()
        resp = self._http.get(url)
        resp.raise_for_status()
        return resp

    def cik(self, ticker: str) -> int | None:
        if self._ciks is None:
            data = self._get(_TICKERS_URL).json()
            self._ciks = {v["ticker"].upper(): int(v["cik_str"]) for v in data.values()}
        return self._ciks.get(ticker.upper())

    def recent_filings(self, ticker: str, since: date) -> list[Filing]:
        cik = self.cik(ticker)
        if cik is None:
            return []
        recent = self._get(_SUBMISSIONS_URL.format(cik=cik)).json()["filings"]["recent"]
        out: list[Filing] = []
        for i, form in enumerate(recent["form"]):
            filed = date.fromisoformat(recent["filingDate"][i])
            if filed < since:
                break  # newest first
            if form not in FORMS:
                continue
            items = recent["items"][i] or ""
            if form == "8-K" and not (set(items.split(",")) & _8K_ITEMS):
                continue
            out.append(
                Filing(ticker.upper(), cik, form, filed, recent["accessionNumber"][i],
                       recent["primaryDocument"][i], items)
            )
        return out

    def filing_text(self, f: Filing) -> str:
        """The substantive text of a filing (see module docstring)."""
        if f.form in ("10-Q", "10-K"):
            return _mdna(_html_text(self._get(f.url).text))
        base = _ARCHIVE.format(cik=f.cik, acc=f.accession.replace("-", ""))
        index = self._get(f"{base}/index.json").json()["directory"]["item"]
        exhibits = sorted(
            (
                i for i in index
                if i["name"].lower().endswith((".htm", ".html"))
                and i["name"] != f.primary_doc
                and not re.match(r"^R\d+\.htm$", i["name"])
                and "index" not in i["name"].lower()
            ),
            key=lambda i: -int(i.get("size") or 0),
        )[:_MAX_EXHIBITS]
        cover = _html_text(self._get(f.url).text)
        # Drop the cover-page boilerplate (registrant, addresses, checkboxes).
        item = re.search(r"\bItem\s+\d+\.\d+", cover)
        parts = [cover[item.start():] if item else cover]
        parts += [_html_text(self._get(f"{base}/{i['name']}").text) for i in exhibits]
        return "\n\n".join(parts)[:_MAX_CHARS]


def _html_text(html: str) -> str:
    """Filing HTML → paragraph text (one block per <p>/<div>/table row)."""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "ix:header"]):
        tag.decompose()
    lines = [
        re.sub(r"\s+", " ", ln).strip()
        for ln in soup.get_text(separator="\n").split("\n")
    ]
    blocks: list[str] = []
    current = ""
    for ln in lines:
        if not ln:
            continue
        if len(current) + len(ln) > 900 or (current.endswith((".", ":")) and len(current) > 200):
            blocks.append(current)
            current = ln
        else:
            current = f"{current} {ln}".strip()
    if current:
        blocks.append(current)
    return "\n\n".join(b for b in blocks if len(b) > 30)


def _mdna(text: str) -> str:
    """Slice the MD&A section out of a 10-Q/10-K (skipping the table of contents)."""
    hits = [m.start() for m in re.finditer(r"management['’]s discussion and analysis", text, re.I)]
    # The first mention is usually the TOC; take the first one followed by real prose.
    for start in hits:
        chunk = text[start : start + _MAX_CHARS]
        if len(re.findall(r"[.!?] ", chunk[:5000])) > 15:
            return chunk
    return text[:_MAX_CHARS]


def sync_filings(conn: sqlite3.Connection, settings: Settings | None = None, days: int = 7) -> dict:
    """Ingest recent filings for every followed ticker, then extract + match them."""
    from ..documents import SEC_SHOW, create_document, paragraphs_from_text, process_document

    settings = settings or get_settings()
    tickers = sorted(
        {
            r["ticker"].upper()
            for r in conn.execute(
                "SELECT DISTINCT ticker FROM user_securities WHERE ticker IS NOT NULL"
            ).fetchall()
            if r["ticker"]
        }
    )
    since = date.today() - timedelta(days=days)
    result = {"tickers": len(tickers), "filings": 0, "new": 0, "errors": 0}
    client = EdgarClient(settings)
    try:
        for ticker in tickers:
            try:
                filings = client.recent_filings(ticker, since)
            except httpx.HTTPError as exc:
                log.warning("EDGAR submissions failed for %s: %s", ticker, exc)
                result["errors"] += 1
                continue
            for f in filings:
                result["filings"] += 1
                if conn.execute(
                    "SELECT 1 FROM episodes WHERE show_slug = ? AND guid = ?",
                    (SEC_SHOW.slug, f.accession),
                ).fetchone():
                    continue
                try:
                    paragraphs = paragraphs_from_text(client.filing_text(f))
                except httpx.HTTPError as exc:
                    log.warning("EDGAR fetch failed for %s %s: %s", ticker, f.accession, exc)
                    result["errors"] += 1
                    continue
                if not paragraphs:
                    continue
                episode_id, created = create_document(
                    conn,
                    show=SEC_SHOW,
                    guid=f.accession,
                    title=f.title,
                    paragraphs=paragraphs,
                    url=f.url,
                    published_at=datetime(f.filed.year, f.filed.month, f.filed.day, tzinfo=timezone.utc),
                    settings=settings,
                )
                if created:
                    result["new"] += 1
                    process_document(conn, episode_id, settings)
    finally:
        client.close()
    return result
