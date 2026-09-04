# Reconciliation Dashboard

A full-stack web application that ingests an online store's **order-system export** and its
**payment-processor export**, reconciles them with a deterministic engine, and presents the
result as a dashboard a revenue owner can act on — headline figures, discrepancy taxonomy with
charts, drill-down to the individual rows, and AI-assisted explanations layered **on top of**
the deterministic results.

---

## Quick start (local)

**With Docker (recommended):**

```bash
cp .env.example .env                 # add your OPENROUTER_API_KEY for AI features
docker compose up --build -d         # app on http://localhost:8000
```

First run migrates the DB and seeds a demo account (`demo@example.com` / `DemoPass!123`).
Sign up fresh if you prefer. Click **Import → Load sample data** to see the full dashboard
populated with the bundled CSVs.

> If your host already runs Postgres/uses ports 5432/8000, remap:
> `DB_PORT=5433 APP_PORT=8001 docker compose up --build -d`

**Without Docker:**

```bash
# backend
python -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
cd backend
python manage.py migrate
python manage.py runserver          # http://localhost:8000

# frontend (dev mode with HMR, separate terminal)
cd frontend
npm install && npm run dev          # http://localhost:5173 (proxies /api to :8000)
```

**Tests:**

```bash
cd backend && python -m pytest apps -q
```

---

## Architecture

```
React SPA (Vite + TypeScript + Tailwind + Recharts)
        │  REST / JWT
        ▼
Django + Django REST Framework
    ├── accounts app        signup/login (SimpleJWT), email-based custom user
    ├── ingestion app       CSV upload → parse/normalize → Postgres
    ├── reconciliation app  pure engine + run/discrepancy APIs
    └── explain app         pydantic-ai agents → OpenRouter (backend only)
                                    ├── explainer  (one finding → structured explanation)
                                    └── summarizer (run-level executive summary)
        │
        ▼
PostgreSQL (append-only: every import batch and run is kept forever)
```

Design decisions worth defending:

- **One deployable unit.** Django serves the built SPA, so frontend/backend/db is three
  hosted things, not four. The SPA fallback is one `re_path`; API routes stay clean.
- **The engine is pure Python** (`apps/reconciliation/engine/`) — no Django, no DB, no I/O.
  It takes parsed dataclasses in and returns findings + stats out. That makes it trivially
  unit-testable (golden tests assert exact outputs) and provably deterministic.
- **Append-only storage.** `ImportBatch → ReconciliationRun → Discrepancy` rows are never
  mutated or deleted (FKs are `PROTECT`). The run selector on the dashboard browses history.
- **LLM strictly explains.** The engine's classification is ground truth; the model receives
  the facts and is instructed to explain, never re-classify (see below).

## Reconciliation logic

### Ingestion & normalization

| Rule | Why |
|---|---|
| Join key: order reference `strip().upper()` | The data contains `' ord-1801 '` and `'ord-1802'` in the payments file. Matching on raw refs would invent two fake "missing payments." Normalization is recorded (raw + normalized fields both stored) and surfaced as an ingestion warning. |
| Payment dates parsed `DD/MM/YYYY` (day-first) | 116 payment rows have day > 12, which proves the file is day-first; the remaining 70 ambiguous rows are consistent with it. Order dates are ISO — a deliberate export inconsistency. |
| Exact-duplicate order rows dropped, first kept | ORD-1004 appears twice, byte-identical. A duplicate row is an export artifact, not a second order. Recorded as a warning; counted in the 184 unique orders (from 185 rows). |
| Empty `discount` → 0; empty `email`/`processed_at` → NULL | Missing values are flagged as data-quality warnings, never silently guessed. |
| All money as `Decimal` | Float arithmetic on currency is how false discrepancies get born. |

### Matching

Orders and payments are matched on the normalized order reference. Per order, its payments
are grouped by `type` (charge/refund) and `status` (settled/pending/failed). Everything
below is evaluated on the unique-order level, sorted by stable keys → same input, same output,
always.

### Discrepancy taxonomy

| Type | Severity | Trigger | Risk formula |
|---|---|---|---|
| `missing_payment` | high | completed order, zero charges | order net |
| `orphan_charge` | high | settled charge referencing a nonexistent order | charge amount |
| `duplicate_charge` | high | >1 settled charge for one order | sum of extra charges |
| `amount_mismatch` | high | settled charge differs from order net beyond tolerance | \|delta\| |
| `charged_after_cancellation` | high | cancelled order with a settled charge | charge amount |
| `failed_payment` | medium | completed order, charge attempt failed | charge amount |
| `pending_payment` | medium | completed order, charge still pending | charge amount |
| `partial_refund` | medium | refunded order where refund < charge | charge − refund |
| `refund_of_completed_order` | medium | settled refund against a completed order | refund amount |
| `currency_mismatch` | medium | order currency ≠ charge currency | charge amount (FX-dependent) |
| `late_settlement` | low | settled > 7 days after order date | 0 (timing) |
| `rounding_variance` | info | \|delta\| ≤ $0.05 | 0 (tolerated) |

**One primary classification per order cluster** — an order can't be both "duplicate charge"
and "amount mismatch", so headline money can't be double-counted. Data-quality notes
(duplicate rows, dirty refs) live on the *batch* as ingestion warnings, separate from
money-findings.

### Tolerances (the two judgment calls)

**Amount tolerance: $0.05.** The dataset contains three orders off by 1–2 cents
(ORD-1901/1902/1903) — classic processor rounding. Calling those "disputes" would inflate
the problem set with noise; ignoring them silently would leave totals that don't tie out.
So they're classified `rounding_variance` (info, $0 at risk) — visible, counted, but excluded
from dispute/at-risk figures. Anything above $0.05 in this dataset is a deliberate mismatch
($18.50–$60), so the cutoff cleanly separates rounding from reality.

**Settlement window: 7 days.** Card settlement normally takes 1–3 days. The dataset has one
payment settled 29 days after the order (ORD-2101) — a real anomaly worth surfacing, but
"real" needs a window that doesn't fire on ordinary weekend/batch delays. 7 days is the
standard "definitely late" line in card processing.

**Currency is exact-match.** ORD-1601 (USD order) was charged in EUR and ORD-1602 (EUR order)
in USD — same numerals, wrong currency. Matching on amount alone would call these "matched".
Currency equality is a hard gate before any amount comparison; the $355 is routed to
"needs investigation" because the real dollar impact depends on FX rates these files don't
contain.

### Money-at-risk buckets

Because "money at risk" means different things to a revenue owner:

- **Uncollected revenue** ($787.85): the store believes it earned this money but never
  received it — missing payments, undercharges, failed/pending charges.
- **Refund obligations** ($508.58): the store is holding money that isn't theirs —
  double charges, overcharges, charges after cancellation.
- **Needs investigation** ($882.00): unexplainable from these two files alone — orphan
  charges, partial refunds, refunds of completed orders, currency swaps.

Money at risk = uncollected + refund obligations = **$1,296.43**.

## What the data actually says

On the provided files: **184 unique orders, 187 payments, 174 clean matches, $40,062.28
reconciled, $2,178.43 in dispute.** The 20 material findings:

| Finding | Count | Money |
|---|---|---|
| Completed orders never charged (ORD-1201–1204) | 4 | $392.35 uncollected |
| Charges for orders that don't exist (1301–1303) | 3 | $308.00 unexplained |
| Amount mismatches (over $60 + $25, under $18.50) | 3 | $103.50 |
| Double charges 29 minutes apart (1501–1502) | 2 | $248.58 to refund |
| Cancelled order still charged (1701) | 1 | $175.00 |
| Refunded order only partially refunded (1702) | 1 | $120.00 remainder |
| Completed order fully refunded (1703) | 1 | $99.00 |
| Currency swapped on charge (1601–1602) | 2 | $355.00 FX-dependent |
| Failed (2001) and pending (2002) charges | 2 | $377.00 |
| Settled 29 days late (2101) | 1 | — |

Plus the traps: a duplicated order row (1004), dirty references that only match after
normalization (18xx), three rounding variances (19xx), and missing fields (22xx).

**Business reading:** the biggest leak is revenue the store booked but never collected
($787.85 including the failed charge), and the scariest category is the $308 of settled
charges with no corresponding order — that's either an export gap or charge activity the
store doesn't know about, and both possibilities deserve a human today. The double charges
are mechanically certain (identical amounts, 29 minutes apart) and are the fastest
customer-trust win to fix.

## LLM approach

- **Where:** backend only (`apps/explain/`). The key never leaves the server; the frontend
  only ever sees rendered explanation JSON.
- **Stack:** [Pydantic AI](https://ai.pydantic.dev) with its native OpenRouter provider
  (`OpenRouterModel` + `OpenRouterProvider`), configured entirely via env:
  `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` (default `google/gemini-2.5-flash`),
  `OPENROUTER_BASE_URL`, `LLM_TEMPERATURE`, `LLM_MAX_RETRIES`, `LLM_TIMEOUT_SECONDS`,
  `LLM_ENABLED`. Swap provider/model with zero code changes.
- **Two agents, no orchestration framework:** the flows are linear —
  *explain one finding* and *summarize a set of findings*. A graph orchestrator would add
  a dependency and a "why did you need this?" question with no honest answer. Plain agent
  calls from Django views, each with a typed output model
  (`summary / likely_cause / recommended_action / urgency`).
- **Temperature 0.1.** These are financial explanations where consistency and faithfulness
  matter and creativity is a defect — the same finding should produce (nearly) the same
  explanation every time. 0.0 is defensible too; 0.1 leaves the model a hair of freedom on
  phrasing while keeping structure and facts pinned.
- **Malformed/unexpected output:** Pydantic AI validates the response against the output
  model and *automatically re-prompts* on validation failure, up to `LLM_MAX_RETRIES` (2).
  If it still fails — or the provider is down, unconfigured, or `LLM_ENABLED=false` — the
  endpoint returns a **deterministic fallback** built from the engine's facts, flagged
  `degraded: true` so the UI can say "AI unavailable, here are the raw facts." The dashboard
  never breaks because the LLM did.
- **Guardrail:** prompts state the classification is ground truth produced by exact rules;
  the model explains, never re-classifies. The LLM has no role whatsoever in matching.

## Frontend states

Loading skeletons and error+retry on the AI summary and per-finding explanation; empty
states for no-data/no-results; the auth gate redirects unauthenticated users; table errors
retry inline; the explanation panel distinguishes fresh AI, cached, and degraded fallback.

## What I'd build next

- **Resolution workflow:** mark findings resolved/investigating (state machine per finding),
  so the dashboard becomes a worklist, not just a report.
- **Trend comparisons:** batch-over-batch diffs ("what changed since last import") — the
  append-only schema already supports it.
- **CSV export** of the filtered discrepancy set for finance teams living in spreadsheets.
- **Auth hardening:** rate limiting on login, email verification.
- **Engine configurability:** tolerances as env vars, plus a "strict mode" that counts
  rounding variances as disputes for teams that want zero tolerance.

## AI tools note

Built with an AI coding agent (pair-programming style): architecture and data analysis were
done with systematic verification (the anomaly findings were derived by scripted analysis of
the CSVs, not eyeballing), the engine's expected outputs were pinned by golden tests before
being trusted, and every piece here — including every line the agent wrote — was reviewed,
understood, and is defensible in conversation.

## API surface (summary)

```
POST /api/auth/signup/ · login/ · refresh/        GET /api/auth/me/
POST /api/imports/            (multipart upload)  POST /api/imports/sample/
GET  /api/batches/            POST /api/runs/  (re-run latest)
GET  /api/runs/               GET /api/runs/:id/
GET  /api/runs/:id/discrepancies/?type=&severity=&search=&page=
GET  /api/discrepancies/:id/
POST /api/discrepancies/:id/explain/  ·  /api/runs/:id/summarize/
```

All routes require JWT auth; every query is scoped to the requesting user's own batches and
runs (enforced in the query layer, tested in the API tests).
