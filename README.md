# research-digest

Turn a curated set of podcasts into a weekly sector-research digest.

## What it does

A two-layer pipeline that goes from raw podcast audio to a distributable newsletter:

**Layer 1 — transcripts**
Discover episodes from RSS feeds, download audio, and produce clean diarized transcripts with speaker attribution and proper-noun correction.

**Layer 2 — triage & newsletter**
Extract investment insights ("nuggets") from transcripts, curate them in a review UI (keep/kill/rank), and render the kept ones as a distributable digest with a stock read-through.

---

## Quickstart (for collaborators)

**Prerequisites**
- Python 3.11+ (macOS: `brew install python@3.12`)
- Node 18+ (macOS: `brew install node`)
- An **AssemblyAI** API key — https://www.assemblyai.com/ (transcription + diarization)
- An **Anthropic** API key — https://console.anthropic.com/ (speaker mapping, correction, insights, digest)

**Setup**
```bash
git clone https://github.com/dav-s-git/research-digest.git
cd research-digest
python3.12 -m venv .venv
.venv/bin/python -m pip install -U pip
.venv/bin/python -m pip install -e .
cp .env.example .env          # paste your two API keys into .env
```

**Verify the install (no API keys needed)**
```bash
.venv/bin/digest init         # create local DB + load the show registry
.venv/bin/digest poll         # discovers episodes across all feeds
.venv/bin/digest status       # per-show counts by stage
```

**First real run**
```bash
# Layer 1 — transcribe the last 7 days (~a few dollars for a week of episodes)
.venv/bin/digest ingest --days 7

# Layer 2 — extract insights from transcribed episodes
.venv/bin/digest insights --days 7

# Start the web app (two terminals)
.venv/bin/digest serve          # API at http://127.0.0.1:8000
cd frontend && npm install && npm run dev   # UI at http://localhost:3000
```

**Guardrails**
- Never commit `.env` — it's git-ignored and your keys are your own.
- `data/` (audio, transcripts, SQLite DB) is local and git-ignored; you build your own corpus from scratch.

---

## Layer 1: transcript pipeline

### How transcripts are acquired

- **Tier A — official transcripts** where a show publishes them (human-grade, zero ASR cost). Working: **Dwarkesh**.
- **Tier B — ASR from audio** via AssemblyAI (best-in-class diarization) + a domain word-boost glossary, then an LLM proper-noun correction pass. Shows: SemiAnalysis, Cheeky Pint, All-In, BG2, No Priors, Capital Allocators.
- Tier A fetchers fall back to Tier B automatically when the official transcript can't be retrieved.

### Pipeline stages

```
poll       → discover episodes from RSS feeds          (no API keys)
acquire    → Tier A: fetch official transcript         (no API keys)
             Tier B: download audio enclosure          (no API keys)
transcribe → ASR + diarization (AssemblyAI)
             speaker-name mapping (Claude)
             proper-noun correction (Claude)
insights   → extract investment nuggets (Claude)
```

### CLI reference

```bash
.venv/bin/digest init                        # create DB + sync show registry
.venv/bin/digest shows                       # list configured shows
.venv/bin/digest poll                        # discover episodes from all feeds
.venv/bin/digest poll -s bg2                 # one show only

.venv/bin/digest acquire -s bg2 -n 2        # download audio
.venv/bin/digest transcribe -s bg2 -n 1     # ASR + diarize + correct
.venv/bin/digest ingest --days 7            # weekly driver: discover+acquire+transcribe

.venv/bin/digest insights -s bg2 -n 1       # extract nuggets from latest episode
.venv/bin/digest insights --days 7          # extract from all transcribed in window

.venv/bin/digest episodes -s bg2 -n 10      # list stored episodes
.venv/bin/digest status                      # per-show counts by stage
```

---

## Layer 2: triage & newsletter

### Web app

```bash
# Terminal 1 — API (http://127.0.0.1:8000, interactive docs at /docs)
.venv/bin/digest serve

# Terminal 2 — frontend (http://localhost:3000)
cd frontend && npm run dev
```

**Pages:**
- `/` — **Podcasts** — card grid of configured shows with episode counts; click a show to jump to its insights
- `/episodes` — **Insights** — browse and filter transcribed episodes by show
- `/episode/{id}` — episode detail with three tabs:
  - **Digest** — TMTB-style synthesized summary (themes + stock read-through), generated on demand via Claude
  - **Transcript** — full diarized transcript with color-coded speakers and timestamps
  - **Review** — nugget triage: keep/kill each insight, set rank (1 = lead, 2–3 = good-to-know), flag contrarian takes, add a curator note
- `/newsletter` — **Newsletter** — select a podcast, auto-renders its kept nuggets as a distributable digest with drag-to-reorder and PDF export

### Triage (Review tab)

Open any episode that has been through `digest insights` and click **Review**. For each nugget:

- **Keep / Kill** — toggle the curation decision
- **Rank** (1 / 2 / 3) — 1 = lead item, 2–3 = good-to-know; the model's suggested rank is shown
- **Contradicts consensus** — flag for contrarian takes
- **Note** — your "why it matters" framing line, shown in the newsletter under the quote

All changes autosave instantly via `PATCH /api/nuggets/{id}/curation`. Curator decisions survive nugget re-extraction: if you re-run `digest insights --force`, orphaned curation rows are retained and excluded via JOIN, not deleted.

### Newsletter

**Via the web UI:**
1. Go to `/newsletter`
2. Click a podcast pill — the digest builds automatically
3. Drag nuggets to reorder; click **Export PDF** to save

The output has three sections:
- **Relevant Nuggets** — rank-1 kept insights: claim (bold) → quote (italic, speaker-attributed)
- **Good to Know** — rank 2–3 insights, same layout
- **Stock Read-Through** — pulled from the episode digest's LLM-generated stock analysis (Bullish/Bearish/Owned/Mentioned with summaries), falls back to entity frequency from kept nuggets if no digest exists
- A **Markdown** tab with one-click copy for distribution

**Via CLI:**
```bash
# Write markdown to a file
.venv/bin/digest newsletter --days 7 --output digest-2026-W24.md

# Stream to stdout
.venv/bin/digest newsletter --from 2026-06-01 --to 2026-06-13

# API
GET /api/newsletter?from=2026-06-01&to=2026-06-13
```

### Episode digest (TMTB-style)

After reviewing nuggets, generate a synthesized per-episode digest from the episode's Digest tab. This produces:
- Thematic sections with bullet points and source citations
- A stock read-through with LLM-assigned stance (Bullish/Bearish/Owned/Mentioned) and one-sentence summary per company

This is the data source the newsletter's stock read-through section draws from.

---

## Configuration

- `config/shows.yaml` — curated feed registry (RSS URL, tier, host roster per show)
- `config/glossary.yaml` — domain vocabulary (companies, people, technical/finance terms, known mistranscriptions). Feeds ASR word-boosting and the LLM correction pass. **Main accuracy lever.**
- `.env` — API keys and optional overrides (`DIGEST_ANTHROPIC_MODEL`, `DIGEST_ASSEMBLYAI_SPEECH_MODELS`, etc.)

---

## Layout

```
config/          shows.yaml, glossary.yaml
src/digest/
  feeds.py             RSS parsing + episode discovery
  registry.py          load/validate shows + glossary
  net.py               HTTP (retries, streaming download)
  acquire/             audio downloader + official-transcript fetchers
  transcribe/          AssemblyAI client, speaker mapping, correction, LLM wrapper
  store/               SQLite schema, models, repository functions
  insights/            Step 3: nugget taxonomy + extraction
  synthesis.py         per-episode TMTB-style digest generation
  api/                 FastAPI web API (routers, schemas, deps)
  pipeline.py          orchestration (discover / acquire / transcribe / insights)
  cli.py               `digest` CLI (incl. `serve`)
frontend/        Next.js + Tailwind app
  app/
    episode/[id]/      transcript + digest + review tabs
    episodes/          episode browser
    insights/          weekly insights view
    newsletter/        newsletter builder
data/            audio/, transcripts/, digest.db  (git-ignored)
```
