# Frontend — Reconciliation Dashboard SPA

React + TypeScript + Vite + Tailwind CSS + Recharts.

## Structure

```
src/
  api/          typed API clients (auth, ingestion, reconciliation) over the shared
                axios instance with JWT attach + auto-refresh
  auth/         AuthContext (login/signup/logout, session restore via /me)
  pages/        Login, Signup, Import (upload + sample data), Dashboard
  components/   Layout, HeadlineCards (headline + risk buckets), TypeChart,
                DiscrepancyTable (filters/search/pagination), DetailDrawer
                (raw records + AI explain flow)
```

## Commands

```bash
npm install
npm run dev      # dev server on :5173, proxies /api to the Django backend on :8000
npm run build    # production bundle to dist/ (assets under dist/assets)
npx tsc -b --noEmit   # typecheck
```

## Notes

- Assets are built with the default base (`/`): the SPA is served at its own
  domain root (`serve -s` in its own container), routes are normal
  (`/`, `/login`, `/assets/...`).
- All state for the LLM features has explicit loading / error+retry / degraded
  handling — see `pages/Dashboard.tsx` (AI summary) and `components/DetailDrawer.tsx`
  (per-finding explanation).
- Auth tokens live in localStorage only (no cookies); the axios interceptor
  refreshes once on 401 and logs out if refresh fails.

See the repo-root README for the full system architecture and DEPLOYMENT.md for
how this app is built and served in production.
