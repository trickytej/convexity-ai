# Deployment

Hosted setup: **Turso** (database) · **Render** (API, always-on) · **Vercel**
(frontend, password-gated) · **GitHub Actions** (scheduled ingestion).

```
GitHub Action (cron)  ──writes──┐
                                ▼
   browser ──Basic Auth──▶ Vercel (Next) ──/api proxy + X-API-Key──▶ Render (FastAPI) ──▶ Turso
```

The web app needs only the ~4 MB database (transcripts are stored as segments in the
DB). Audio (~880 MB) is never hosted — it's transient during ingestion.

---

## 1. Database — Turso

```bash
# Install CLI + sign up (free)
curl -sSfL https://get.tur.so/install.sh | bash
turso auth signup

# Create the DB by importing the existing local SQLite file (one-shot migration)
turso db create research-digest --from-file ./data/digest.db

# Grab the connection details (save these)
turso db show research-digest --url           # -> TURSO_DATABASE_URL
turso db tokens create research-digest        # -> TURSO_AUTH_TOKEN
```

Re-syncing later (alternative to `--from-file`):

```bash
TURSO_DATABASE_URL=... TURSO_AUTH_TOKEN=... .venv/bin/python scripts/migrate_to_turso.py
```

## 2. Pick a shared API key

Generate one secret the frontend will send to the API:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"   # -> DIGEST_API_KEY
```

## 3. API — Render

1. Push the repo to GitHub (already `davidsous/research-digest`).
2. Render → **New → Blueprint** → select the repo (it reads `render.yaml`).
3. Set these env vars (dashboard, all secret):
   - `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN`
   - `DIGEST_API_KEY` (from step 2)
   - `ANTHROPIC_API_KEY` (for report/digest/newsletter generation)
   - `DIGEST_CORS_ORIGINS` = your Vercel URL (e.g. `https://research-digest.vercel.app`)
4. Deploy. Health check: `https://<api>.onrender.com/api/health` → `{"status":"ok"}`.

## 4. Frontend — Vercel

1. Vercel → **New Project** → same repo → **Root Directory = `frontend`**.
2. Env vars:
   - `API_BASE_URL` = the Render API URL (e.g. `https://research-digest-api.onrender.com`)
   - `DIGEST_API_KEY` = same value as the API (server-side only; the proxy injects it)
   - `SITE_USER`, `SITE_PASSWORD` = the Basic Auth login for you + Tejas
3. Deploy. Visiting the site prompts for the Basic Auth login.

## 5. Scheduled ingestion — GitHub Actions

Repo → **Settings → Secrets and variables → Actions** → add:

- `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN`
- `ASSEMBLYAI_API_KEY`, `ANTHROPIC_API_KEY`

`.github/workflows/ingest.yml` runs daily (06:00 UTC) and on demand
(**Actions → ingest → Run workflow**). It transcribes new episodes and writes
insights straight to Turso. Audio is downloaded on the runner and discarded.

---

## Environment variable reference

| Where | Variable | Purpose |
|------|----------|---------|
| API + Action | `TURSO_DATABASE_URL` / `TURSO_AUTH_TOKEN` | hosted DB connection |
| API | `DIGEST_API_KEY` | require `X-API-Key` on `/api/*` (open if unset) |
| API | `ANTHROPIC_API_KEY` | on-demand report/digest/newsletter LLM calls |
| API | `DIGEST_CORS_ORIGINS` | allowed browser origins (optional with the proxy) |
| Frontend | `API_BASE_URL` | backend base URL (server fetch + proxy target) |
| Frontend | `DIGEST_API_KEY` | sent to API by the server-side proxy (never to browser) |
| Frontend | `SITE_USER` / `SITE_PASSWORD` | Basic Auth gate for the whole site |
| Action | `ASSEMBLYAI_API_KEY` | transcription |

## Local development (unchanged)

With none of the hosting vars set, the app uses the local libSQL file
(`data/digest.db`), no API key, and no Basic Auth gate:

```bash
.venv/bin/digest serve            # API on :8000
cd frontend && npm run dev        # web on :3000
```
