# research-digest

Turn a curated set of podcasts into a weekly sector-research digest.

This repo currently implements **Step 1–2** of the pipeline: discover episodes
from podcast feeds and produce one clean, **diarized, speaker-attributed,
proper-noun-corrected transcript per episode**. Insight generation, aggregation,
the triage dashboard, and the newsletter output (Steps 3–6) build on top of this.

## How transcripts are acquired (hybrid, accuracy-first)

The hard part for these shows is getting technical **proper nouns** right
(company/people names, jargon), so the strategy is:

- **Tier A — reuse free official transcripts** where a show publishes them
  (human-grade, zero ASR cost). Working: **Dwarkesh**.
- **Tier B — transcribe from audio** with AssemblyAI (best-in-class speaker
  diarization) + a domain **word-boost glossary**, then an **LLM proper-noun
  correction pass** (Anthropic Claude). Shows: SemiAnalysis, Cheeky Pint, All-In,
  BG2, No Priors, Capital Allocators.
- Tier A fetchers **fall back to Tier B automatically** when the official
  transcript can't be retrieved (e.g. Invest Like the Best / Colossus serves the
  page inconsistently; Capital Allocators gates transcripts as premium content).

TBPN is deferred (near-daily, multi-hour) until the weekly pipeline is proven.

## Pipeline stages

```
poll  -> discover episodes from RSS feeds          (no API keys)
acquire -> Tier A: fetch official transcript        (no API keys)
           Tier B: download audio enclosure         (no API keys)
transcribe -> ASR + diarization (AssemblyAI)        (needs ASSEMBLYAI_API_KEY)
              speaker-name mapping (Claude)          (needs ANTHROPIC_API_KEY)
              proper-noun correction (Claude)        (needs ANTHROPIC_API_KEY)
```

Each episode moves through statuses: `discovered → acquired → transcribed`
(Tier A goes straight to `transcribed`). The output is a normalized transcript
in `data/transcripts/<show>/<episode_id>.json` plus rows in SQLite.

## Setup

Requires Python 3.11+ (this project was built with 3.12 via Homebrew).

```bash
# from the project root
/opt/homebrew/bin/python3.12 -m venv .venv
.venv/bin/python -m pip install -U pip
.venv/bin/python -m pip install -e .

cp .env.example .env   # then add ASSEMBLYAI_API_KEY and ANTHROPIC_API_KEY
```

## Usage

```bash
.venv/bin/digest init                 # create db + sync show registry
.venv/bin/digest shows                # list configured shows
.venv/bin/digest poll                 # discover episodes from all feeds
.venv/bin/digest poll -s dwarkesh     # one show only

.venv/bin/digest acquire -s dwarkesh -n 4   # Tier A: fetch official transcripts
.venv/bin/digest acquire -s bg2 -n 2        # Tier B: download audio

.venv/bin/digest transcribe -s semianalysis -n 2   # ASR + diarize + correct
.venv/bin/digest transcribe -s bg2 --no-correct    # skip the LLM pass

.venv/bin/digest episodes -s dwarkesh -n 10        # list stored episodes
.venv/bin/digest status                            # per-show counts by stage
```

## Configuration

- `config/shows.yaml` — the curated feed registry (RSS URL, tier, host roster per
  show). Feed URLs verified against Apple's podcast directory.
- `config/glossary.yaml` — domain vocabulary (companies, people, technical/finance
  terms, known mistranscriptions). Feeds both ASR word-boosting and the LLM
  correction pass. **Maintain this as the main accuracy lever.**
- `.env` — API keys and optional overrides (`DIGEST_ANTHROPIC_MODEL`,
  `DIGEST_ASSEMBLYAI_SPEECH_MODEL`, etc.).

## Layout

```
config/        shows.yaml, glossary.yaml
src/digest/
  feeds.py            RSS parsing + episode discovery
  registry.py         load/validate shows + glossary
  net.py              HTTP (retries, streaming download)
  acquire/            audio downloader + official-transcript fetchers
  transcribe/         AssemblyAI client, speaker mapping, correction, LLM wrapper
  store/              SQLite schema, models, repository
  pipeline.py         orchestration (discover / acquire / transcribe)
  cli.py              `digest` command
data/          audio/, transcripts/, digest.db   (git-ignored)
```
