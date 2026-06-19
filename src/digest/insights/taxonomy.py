"""Nugget taxonomy, scoring rubric, and the extraction prompt.

Tuned for an *investing* lens (theses, numbers, contrarian calls, company moves),
high recall (capture everything notable; rank later), and no sector filtering
(sectors are tags, not gates).
"""

from __future__ import annotations

from ..sectors import VERTICALS

VALID_TYPES = {
    "thesis",
    "prediction",
    "data_point",
    "company_move",
    "contrarian",
    "mental_model",
    "watch_item",
}

SCORE_DIMENSIONS = (
    "specificity",
    "novelty",
    "conviction",
    "materiality",
    "evidence",
    "authority",
)

# Composite weights (investing lens). Tunable later from Step 5 triage feedback.
SCORE_WEIGHTS = {
    "specificity": 0.15,
    "novelty": 0.25,
    "conviction": 0.20,
    "materiality": 0.20,
    "evidence": 0.10,
    "authority": 0.10,
}


def composite_score(scores: dict | None) -> float:
    """Combine 1-5 dimension scores into a 0-1 signal score."""
    if not isinstance(scores, dict):
        return 0.0
    total = 0.0
    for dim, weight in SCORE_WEIGHTS.items():
        value = scores.get(dim)
        if isinstance(value, (int, float)):
            clamped = max(1.0, min(5.0, float(value)))
            total += weight * ((clamped - 1.0) / 4.0)
    return round(total, 4)


SYSTEM_PROMPT = """\
You extract investment-relevant insights ("nuggets") from podcast transcripts for \
a sector-research analyst covering AI, semiconductors, technology, and markets.

A nugget is a single, specific, self-contained claim worth an investor's attention. \
Extract with HIGH RECALL: capture every distinct nugget that clears a low bar. Do not \
summarize, do not merge distinct claims, do not editorialize. One nugget per claim.

Nugget types:
- thesis: a forward-looking or analytical argument about how something plays out
- prediction: a specific, falsifiable forecast (ideally with a timeframe)
- data_point: a concrete number or fact (figure, metric, price, benchmark, date)
- company_move: a named company/product doing something specific (launch, raise, deal, shift)
- contrarian: a view explicitly against consensus, or labeled surprising/counterintuitive
- mental_model: a reusable framework or causal explanation ("X happens because Y")
- watch_item: something the speaker flags to monitor going forward

For EACH nugget return:
- type: one of the types above
- claim: 1-2 sentence distillation in your own words, specific and standalone
- quote: a VERBATIM excerpt copied exactly from the transcript that supports it (do not paraphrase)
- speaker: the name of who said it, from the labels provided
- entities: {"companies": [], "people": [], "tickers": []} named in the nugget
- sectors: short tags, e.g. ["ai", "semiconductors", "infrastructure", "software", "markets", "venture", "energy"]
- scores: integer 1-5 for each of: specificity, novelty, conviction, materiality, evidence, authority

Scoring (1=low, 5=high):
- specificity: vague/general (1) vs precise with names/numbers (5)
- novelty: common knowledge (1) vs genuinely non-obvious/new (5)
- conviction: heavily hedged (1) vs strong or contrarian stance (5)
- materiality: trivial (1) vs decision-relevant for investors (5)
- evidence: bare assertion (1) vs backed by data/reasoning (5)
- authority: little standing on this topic (1) vs clear domain expert (5)

Do NOT extract: host banter, ads/sponsor reads, pleasantries, recaps of well-known \
facts, or vague platitudes.

Output STRICT JSON only: an array of nugget objects. No prose, no markdown fences.

Example of one nugget object:
{"type": "thesis", "claim": "Inference, not training, will dominate AI compute spend as usage scales.", "quote": "the real money is going to be in inference, training is almost a rounding error once these models are deployed at scale", "speaker": "Bill Gurley", "entities": {"companies": [], "people": [], "tickers": []}, "sectors": ["ai", "semiconductors"], "primary_sector": "AI & Foundation Models", "scores": {"specificity": 4, "novelty": 3, "conviction": 4, "materiality": 5, "evidence": 3, "authority": 5}}
"""

# Bake the controlled primary_sector into the extraction schema for new episodes.
SYSTEM_PROMPT += (
    '\n\nAlso include for EACH nugget a "primary_sector": the single best-fit vertical '
    "from EXACTLY this list - " + ", ".join(VERTICALS) + ". "
    'AI is the TOOL, not the subject: use "AI & Foundation Models" only when the AI '
    "industry itself (models, labs, AGI, AI compute) is the subject; if AI is applied to "
    'another domain, classify by that domain (e.g. AI for drug discovery -> "Biotech & Health").'
)


def build_user_prompt(show_name: str, episode_title: str, speakers: list[str], chunk: str) -> str:
    roster = ", ".join(speakers) if speakers else "(unknown)"
    return (
        f"Show: {show_name}\n"
        f"Episode: {episode_title}\n"
        f"Speakers in this episode: {roster}\n\n"
        "Transcript chunk (each line is `[#segment_index Speaker mm:ss] text`):\n"
        f"{chunk}\n\n"
        "Extract all nuggets from this chunk as a JSON array."
    )


# ─── newsletter prompt ────────────────────────────────────────────────────────

NEWSLETTER_SYSTEM_PROMPT = """\
You extract financially material nuggets from investment newsletter articles for a \
fundamental equity analyst. Your sole focus is claims that directly affect a public \
company's income statement, near-term financial guidance, or valuation.

EXTRACT only claims that touch one or more of:
  • Revenue / sales (actuals, run-rate, guidance, growth rates)
  • Gross profit or gross margin (and the drivers behind them: pricing, mix, ASP)
  • Operating income or operating margin (opex leverage, cost cuts, R&D spend)
  • Net income or EPS (diluted / adjusted), including forward guidance ranges
  • Free cash flow, capex, buybacks, or balance-sheet moves that affect earnings
  • Volume / unit demand signals tied to a named company's near-term P&L
  • Inventory dynamics, pricing power, or channel health with quantified impact
  • End-market demand signals that directly read through to a named company's revenue line

SKIP — do not extract:
  • Vague sentiment ("demand is strong", "the market is recovering") — no numbers, no names
  • General technology trends without a specific company P&L impact
  • Macro / rates / geopolitics unless the article ties them to a named company's guidance
  • Management or analyst opinions on culture, strategy, or moats — unless quantified
  • Product announcements or feature releases with no revenue quantification
  • Competitive positioning commentary without financial impact or numbers

A nugget must be SPECIFIC and STANDALONE: it names a company or ticker, contains a \
number or a direction (up/down/flat), and a reader could act on it without more context.

Nugget types:
- data_point: a concrete number — revenue figure, margin %, EPS, guidance range, ASP, unit volume
- thesis: a forward-looking analytical argument about how a company's P&L will develop
- prediction: a specific, falsifiable financial forecast (ideally with a quarter or year)
- company_move: a company action with direct P&L impact — pricing cut, cost program, capacity add
- watch_item: a financial risk or leading indicator the article flags for upcoming quarters
- contrarian: a view explicitly against consensus financial expectations (names the consensus)

For EACH nugget return:
- type: one of the six types above
- claim: 1-2 sentences, specific, includes the number or direction and the company name
- quote: VERBATIM excerpt from the article text that supports the claim
- entities: {"companies": [], "people": [], "tickers": []} — always populate tickers when mentioned
- sectors: short tags from ["semiconductors", "compute", "software", "markets", "ai", "energy", "other"]
- scores: integer 1-5 for: specificity, novelty, conviction, materiality, evidence, authority

Scoring priorities for newsletters:
- specificity (weight: high) — must include a concrete number or named metric, never vague
- materiality (weight: high) — must be decision-relevant for an equity investor in the next 1-4 quarters
- evidence (weight: medium) — backed by data, an earnings call reference, or a cited analyst

Output STRICT JSON only: an array of nugget objects. No prose, no markdown fences.

Example of one high-quality newsletter nugget:
{"type": "data_point", "claim": "Micron guided FQ4 FY25 revenue to ~$10.7B, above the ~$10.0B street consensus, driven by HBM pricing and NAND recovery.", "quote": "Management guided fiscal Q4 revenue to approximately $10.7 billion, roughly 7% above the consensus estimate, citing better-than-expected HBM pricing and a stabilising NAND market.", "entities": {"companies": ["Micron Technology"], "people": [], "tickers": ["MU"]}, "sectors": ["semiconductors"], "scores": {"specificity": 5, "novelty": 4, "conviction": 4, "materiality": 5, "evidence": 4, "authority": 3}}
"""

NEWSLETTER_SYSTEM_PROMPT += (
    '\n\nAlso include for EACH nugget a "primary_sector": the single best-fit vertical '
    "from EXACTLY this list — " + ", ".join(VERTICALS) + "."
)


def build_newsletter_user_prompt(show_name: str, article_title: str, chunk: str) -> str:
    return (
        f"Newsletter: {show_name}\n"
        f"Article: {article_title}\n\n"
        "Article text (paragraphs numbered for reference):\n"
        f"{chunk}\n\n"
        "Extract only income-statement-relevant nuggets as a JSON array. "
        "If nothing in this chunk clears the bar, return an empty array []."
    )
