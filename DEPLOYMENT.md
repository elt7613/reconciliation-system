# Deployment Guide — Dokploy

Three independently deployed apps + a managed database. Each app is its own
Dokploy application (Git-connected, built from its own Dockerfile). All apps in
the same Dokploy **environment** share the `dokploy-network` Docker network and
reach each other by app name as DNS hostname — no ports exposed between them.

```
browser ──▶ frontend app (SPA, static)      api.yourdomain.com ──▶ backend app (Django)
                     │                                                    │
                     └── calls https://api.yourdomain.com directly         ├──▶ ai-service app (FastAPI)
                     (URL baked in at build)                               │    http://ai-service:8000
                                                                          └──▶ Postgres (Dokploy database)
                                                                               postgresql://...@<db-app-name>:5432/db
```

## 1. Create the database

Dokploy → your project → **Add Database → PostgreSQL**. Note the app name you
give it (e.g. `recon-db`). Dokploy shows the **internal connection string** —
you'll paste it into the backend app's env as `DATABASE_URL`
(`postgresql://user:pass@recon-db:5432/dbname`).

## 2. Deploy the AI service (`ai-service/`)

1. **Add Application** → connect your Git repo → build type **Dockerfile**.
2. **Dockerfile Path**: `ai-service/Dockerfile` · **Build Path**: `/`. Leave
   **Docker Context Path** empty — the Dockerfiles expect the *repo root* as
   context (Dokploy's default) and prefix their `COPY` paths accordingly
   (e.g. `COPY ai-service/requirements.txt .`).
3. **App name**: `ai-service` (this exact name is the DNS host the backend will
   call — e.g. `http://ai-service:8000`).
4. **Environment variables** (Dokploy → Environment):

   | Variable | Value |
   |---|---|
   | `AI_SERVICE_API_KEY` | long random shared secret (generate: `openssl rand -hex 32`) |
   | `OPENROUTER_API_KEY` | your OpenRouter key |
   | `OPENROUTER_MODEL` | `google/gemini-2.5-flash` (2–5s responses; any OpenRouter model works) |
   | `LLM_TEMPERATURE` | `0.1` |
   | `LLM_MAX_RETRIES` | `1` (each retry is a full model round-trip — keep small) |
   | `LLM_TIMEOUT_SECONDS` | `45` |

   Do **not** open a domain for this service — it's internal-only (it is
   protected by the API key, but it doesn't need public exposure).

## 3. Deploy the backend (`backend/`)

1. **Add Application** → same Git repo → build type **Dockerfile**.
2. **Dockerfile Path**: `backend/Dockerfile` (context is the repo root by
   default — no context-path setting needed).
3. **App name**: e.g. `backend`.
4. **Environment variables**:

   | Variable | Value |
   |---|---|
   | `SECRET_KEY` | `openssl rand -hex 32` |
   | `DEBUG` | `False` |
   | `ALLOWED_HOSTS` | your backend domain, e.g. `api.yourdomain.com` |
   | `CORS_ALLOWED_ORIGINS` | your frontend domain, e.g. `https://recon.yourdomain.com` |
   | `DATABASE_URL` | the Postgres internal connection string from step 1 |
   | `AI_SERVICE_URL` | `http://ai-service:8000` (the app name from step 2) |
   | `AI_SERVICE_API_KEY` | same shared secret as the ai-service |
   | `AI_SERVICE_TIMEOUT_SECONDS` | `50` (must exceed the service's 45s) |
   | `AI_ENABLED` | `True` |

5. **Domain**: add one (e.g. `api.yourdomain.com`) — the frontend calls this
   URL and the browser JWT traffic goes through it. Migrations run
   automatically on container start; a demo account is seeded
   (`demo@example.com` / `DemoPass!123`).

## 4. Deploy the frontend (`frontend/`)

1. **Add Application** → same Git repo → build type **Dockerfile**.
2. **Dockerfile Path**: `frontend/Dockerfile` (repo-root context, like the others).
3. **Build Arguments** (Dokploy → Environment → Build Arguments — this is
   baked into the JS bundle at build time):

   | Build arg | Value |
   |---|---|
   | `VITE_API_BASE_URL` | `https://api.yourdomain.com` (your backend's public domain) |

4. **Domain**: add one (e.g. `recon.yourdomain.com`). That's the URL you hand
   to reviewers.

## 5. Verify

- Frontend domain → login page renders; sign up works.
- **Import → Load sample data** → dashboard shows 184 orders / 187 payments /
  174 matched pairs / $40,062.28 reconciled / $2,178.43 in dispute /
  $1,296.43 at risk.
- **Explain with AI** on any row → explanation in ~2–5s (if it says "AI
  unavailable", check the ai-service env and the shared `AI_SERVICE_API_KEY`
  matches on both apps).
- Backend container logs: `docker logs <backend>` if anything misbehaves; the
  AI service logs `Explain failed` / `Summarize failed` with the provider error.

## Health endpoints

- Backend: `GET /api/health/` → `{"status": "ok"}` (public liveness).
- AI service: `GET /health` (liveness) and `GET /ready` (reports LLM config
  state + model) — both public but contain no secrets.

## Why this layout

- **Independent scaling & failure domains**: a slow model call can never tie up
  Django workers (the service has its own process pool), and the SPA keeps
  working even if the AI service is entirely down (deterministic fallbacks).
- **Secrets stay put**: the OpenRouter key only exists in the ai-service
  environment; the frontend never sees any key; the two apps share only one
  internal secret.
- **Dokploy-native**: three Dockerfile apps + a managed DB is exactly the
  deployment shape Dokploy is built around — no compose file, no nginx config.

## Local development

```bash
# 1. AI service (FastAPI) — http://127.0.0.1:8001
cd ai-service
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # add OPENROUTER_API_KEY, set AI_SERVICE_API_KEY
uvicorn app.main:app --port 8001

# 2. Backend (Django) — http://localhost:8000
cd backend
python -m venv .venv && source .venv/bin/activate   # or: conda activate data-mont-sys
pip install -r requirements.txt
cp .env.example .env        # DATABASE_URL, AI_SERVICE_URL=http://127.0.0.1:8001, same AI_SERVICE_API_KEY
python manage.py migrate
python manage.py runserver

# 3. Frontend (Vite dev server, /api proxied to :8000) — http://localhost:5173
cd frontend
npm install && npm run dev
```

Tests (all hermetic — no network/LLM needed):

```bash
cd backend  && python -m pytest apps -q
cd ai-service && python -m pytest -q
```
