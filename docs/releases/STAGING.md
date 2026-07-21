# Local Staging Stack (Sprint 7 Phase 7)

No Docker on this machine, so staging mirrors how local dev already works
(native Postgres), just fully isolated from `sentinelx_dev`/`sentinelx_test`
and from production: its own database, its own backend process on a
different port, its own frontend build pointed at that backend.

| Component | Value |
|---|---|
| Database | `sentinelx_staging` (native Postgres, owned by `sentinelx_app`, same server as dev) |
| Backend | `http://127.0.0.1:8200` |
| Frontend | `http://127.0.0.1:4300` (built with `VITE_API_BASE_URL` pointed at the backend above, served via `vite preview`) |
| `APP_ENV` | `staging` (not `production` — the Phase 4 default-JWT-secret boot guard only fires on `production`; not `development` so it's visibly distinct in `/health` and the dashboard header) |

## Stand up

```powershell
# 1. Database (once)
psql "postgresql://sentinelx_app:SentinelX_app_2026!@localhost:5432/postgres" -c "CREATE DATABASE sentinelx_staging;"

# 2. Schema + migrations + demo data
cd backend
.\.venv\Scripts\Activate.ps1
$env:DATABASE_URL = "postgresql+psycopg://sentinelx_app:SentinelX_app_2026!@localhost:5432/sentinelx_staging"
python -m app.db.init_db
python -m app.db.apply_migrations
python -m app.db.seed   # prints demo device tokens — needed for agent-facing scenarios

# 3. Backend
$env:APP_ENV = "staging"
$env:JWT_SECRET_KEY = "staging-only-secret-not-for-production-use"
$env:BACKEND_CORS_ORIGINS = "http://127.0.0.1:4300,http://localhost:4300"
uvicorn app.main:app --port 8200

# 4. Frontend (separate shell)
cd frontend
$env:VITE_API_BASE_URL = "http://127.0.0.1:8200/api/v1"
npm run build
npx vite preview --port 4300 --strictPort
```

Verified 2026-07-20: `GET /api/v1/health` reports
`{"environment": "staging", "version": "3.0.0", "ready": true, ...}`;
logged in through a real browser as the seeded TechNova admin
(`ops@technova.io`) and the dashboard rendered real staging data with the
header correctly reading "SentinelX API v3.0.0 · staging" and zero console
errors — screenshot at
`docs/Evidence/sprint7_production_release/07_staging_and_e2e/01_staging_login_dashboard.png`.

## Tear down

```powershell
# Stop the backend/frontend processes, then:
psql "postgresql://sentinelx_app:SentinelX_app_2026!@localhost:5432/postgres" -c "DROP DATABASE sentinelx_staging;"
```

## Guardrails

- Never point this stack at `sentinelx_dev`, `sentinelx_test`, or a
  production `DATABASE_URL`.
- Never reuse the production JWT secret or recovery signing key here;
  staging deliberately uses its own throwaway JWT secret (the recovery
  signing key file is shared with dev since it's just a local key file on
  disk, not customer data — low-risk to reuse for a local-only stack).
- This is for E2E functional and load/soak testing only — no production
  traffic or data ever flows through it.
