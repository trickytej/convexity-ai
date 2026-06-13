"""Nugget taxonomy, scoring rubric, and the extraction prompt.

Tuned for an *investing* lens (theses, numbers, contrarian calls, company moves),
high recall (capture everything notable; rank later), and no sector filtering
(sectors are tags, not gates).
"""

from __future__ import annotations

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
{"type": "thesis", "claim": "Inference, not training, will dominate AI compute spend as usage scales.", "quote": "the real money is going to be in inference, training is almost a rounding error once these models are deployed at scale", "speaker": "Bill Gurley", "entities": {"companies": [], "people": [], "tickers": []}, "sectors": ["ai", "semiconductors"], "scores": {"specificity": 4, "novelty": 3, "conviction": 4, "materiality": 5, "evidence": 3, "authority": 5}}
"""


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
