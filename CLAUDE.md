# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SentinelX is a distributed, multi-tenant monitoring and self-healing platform (COM668 Computing Project). The pipeline is:

```
Python Desktop Agent (psutil) ─┐
                               ├→ FastAPI Backend → PostgreSQL → React Dashboard
Arduino BLE/Serial Bridge ─────┘
```

| Path | Component |
|------|-----------|
| `backend/` | One authoritative FastAPI API — auth, RBAC, multi-tenant data, metric ingestion, alerts, incidents, audit & security logs |
| `frontend/` | React 19 + Vite dashboard, light "Operations Console" design system |
| `agents/desktop-python/` | Desktop agent v3.0.0 — psutil telemetry authenticated with a device token |
| `agents/android-native/` | Android agent v3.0.0 — Kotlin/Compose, batch metrics via `/metrics/batch` |
| `agents/ios-native/` | iOS mobile agent — Swift 6 / SwiftUI app (`ios/`) + FastAPI/SQLite mobile dev server (`server/`, port 8100) |
| `agents/embedded-bridge/` | Python BLE/serial bridge forwarding Arduino sensor data to the backend |
| `embedded/arduino_nano33_ble_sense_rev2/` | Arduino firmware (temperature, pressure, motion, impact) |
| `migrations/` | Versioned SQL files (no Alembic); applied deterministically via `python -m app.db.apply_migrations`, which tracks progress in a `schema_migrations` table |
| `tests/` | `conftest.py` + `helpers.py` are shared by `backend/`, `contract/` and `integration/`; `e2e/` needs a live backend; `load/` is Locust. Frontend tests live beside the code in `frontend/src/**/*.test.tsx` |
| `docs/` | `DEMO_USERS.md`, brand assets (`brand/`), local evidence pack (`Evidence/`, gitignored) |
| `docker-compose.yml` | Local Postgres 16 (`sentinelx_dev`) |
| `docs/adr/` | Architecture decision records — read these before revisiting auth, tenancy, hosting, CI policy, the telemetry model or the worker |
| `docs/protocol/` | **SentinelX Agent Protocol v1** — the agent wire contract, versioned and contract-tested |
| `docker/` | OpenTelemetry Collector config for the optional `otel` compose profile |

**Hosting is paused.** SentinelX runs locally only: there is no Azure, GCP, AWS or other hosted environment, and no active cloud dependency anywhere in the tree. Historical documents (`CHANGELOG.md`, `docs/PRODUCTION_READINESS_AUDIT.md`, `docs/releases/`) correctly record that an Azure deployment once existed — that is history, not a current instruction. See `docs/adr/0003-hosting-freeze.md`. Never create cloud resources for this project.

`AGENTS.md` is a local-only parallel guidance file for Codex. It is deliberately **not tracked in git** (`.gitignore` excludes agent tooling), so it exists on a developer machine or not at all — keep it in sync locally when architecture changes, but never assume a clone has it.

---

## Running the Components

Each component runs from its own directory with its own virtualenv / node_modules. Copy the matching `.env.example` to `.env` first.

### Backend (FastAPI)
```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
# http://127.0.0.1:8000 — Swagger UI at /docs
```

### Database bootstrap & seed
```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m app.db.init_db     # create tables (no Alembic)
python -m app.db.seed        # WIPES the DB, seeds demo orgs/users/devices
```
Seeding prints the raw device tokens (TechNova Laptop, Apex Arduino) **once** — they must be copied into `agents/desktop-python/.env` and `agents/embedded-bridge/.env` after every re-seed, since re-seeding regenerates tokens and device UUIDs. Seeded accounts are listed in `docs/DEMO_USERS.md` (shared password `SentinelX2026!`).

### Background worker
```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m app.worker            # drains the outbox until Ctrl+C
python -m app.worker --once     # one batch, then exit
```
The API works without it — jobs simply queue, which is visible in `/api/v1/health`
rather than silent.

### Desktop agent
```powershell
cd agents\desktop-python
.\.venv\Scripts\Activate.ps1
python -m sentinelx_agent.main
```

### Embedded bridge (choose one transport)
```powershell
cd agents\embedded-bridge
python serial_bridge.py   # USB Serial JSON
python ble_bridge.py      # BLE telemetry characteristic
```

### Bounded local load profile
```powershell
# with the backend and worker already running
python scriptsun_load_profile.py --scenario fleet --users 25 --duration 60 --interval 2
```
Scenarios are the Locust tags in `tests/load/locustfile.py` (`single-agent`, `fleet`, `batch`, `burst`, `query`, `stream`, `console`). The harness samples queue depth, oldest pending job, rate-limit backend health, process CPU/RSS and per-table storage growth alongside Locust's latency percentiles, and writes a JSON report under `docs/Evidence/load/` (gitignored). It refuses non-loopback hosts and caps users/duration.

### Frontend (React + Vite)
```powershell
cd frontend
npm run dev      # http://127.0.0.1:5173
npm run build    # tsc -b then vite build
npm run lint     # eslint
```

---

## Backend Architecture

**Entry:** `backend/app/main.py` — CORS middleware, SlowAPI rate limiter (`app.state.limiter`, defined in `core/limiter.py`; login and telemetry endpoints are rate-limited), and the API router.

**Routing:** `backend/app/api/router.py` — all route modules registered under `/api/v1`.

**Auth & RBAC:**
- JWT issued via `core/security.py`; passwords hashed with pwdlib (argon2)
- Two login paths: `POST /api/v1/auth/token` (OAuth2 password form — used by Swagger UI's Authorize button) and `POST /api/v1/auth/login` (JSON — used by the React app). Both open a real session.
- Six roles with a numeric hierarchy in `api/deps.py` (`ROLE_HIERARCHY`): `platform_admin > owner > admin > engineer > operator > viewer`
- `api/deps.py` dependencies: `get_current_user`, `require_role([...])`, `require_min_role("engineer")`, `get_org_scoped_user`, and `get_device_from_token` (raw Bearer device token → Device, verified against hashed `DeviceCredential` rows)
- **Sessions are server-side.** Access tokens are 15 minutes and carry `sid`/`typ`/`jti`/`iss`/`aud`; `get_current_user` resolves `sid` against `user_sessions` on every request, so logout, `POST /auth/logout-all`, deactivation and refresh-token replay all revoke immediately. The refresh token is opaque, stored only as a SHA-256, and delivered in an HttpOnly cookie scoped to `/api/v1/auth`; `POST /auth/refresh` rotates it and revokes the whole family on replay. `/auth/refresh` is CSRF-protected by a signed double-submit token derived from the session. Details and rationale: `docs/adr/0001-browser-session-architecture.md`
- When adding a route, do **not** mint tokens by hand — `session_service.create_session` then `create_access_token(subject, session_id)`. `create_access_token` requires a session id precisely so there is no un-revocable path

**Multi-tenancy:** every record is organization-scoped (`services/tenant.py` helps enforce scoping). Regular users only see their own org; `platform_admin` sees across tenants. Watch for org-scope leaks when adding queries.

**Database:**
- SQLAlchemy 2 (sync sessions) + psycopg3; session dependency `get_db()` in `db/session.py`
- `Base.metadata.create_all` — no Alembic; schema changes require drop + `init_db` + `seed` in dev
- All PKs are `UUID(as_uuid=True)`; `func.now()` for server-side timestamps

**Alert pipeline (core business logic):**
1. Agent POSTs metrics to `POST /api/v1/metrics` (device-token authenticated); the Android agent uses `POST /api/v1/metrics/batch`, which preserves client-side `recorded_at` timestamps and carries battery/network extras (nullable `system_metrics` columns)
2. `metrics.py` route evaluates enabled `AlertRule` rows via `alert_rule_service.py` (with cooldowns)
3. If no enabled rules match, falls back to hardcoded thresholds in `anomaly_service.py` (85%/95% for CPU/mem/disk)
4. Critical alerts auto-create `Incident` records
5. Significant events write `AuditLog` rows (`audit_log_service.py`); auth/device-token/rate-limit forensics go to the separate `SecurityLog` (`security_log_service.py`)

Embedded sensor data enters via `POST /api/v1/telemetry/embedded` (route `telemetry.py`, model `embedded_telemetry.py`).

**AI observability (shadow mode, separate from the alert pipeline above):** `POST /observability/pipeline/run` builds rolling feature windows from `system_metrics` and scores them with a deterministic statistical baseline plus (laptop devices only) a trained IsolationForest — see `docs/ai_observability_architecture.md`. Never triggered automatically, never creates `Alert`/`Incident`/`RecoveryAction` rows; results are `AnomalyPrediction` rows awaiting human review.

**Hybrid detection, model lifecycle & replay (Sprint 4-6, builds on AI observability above):** `POST /hybrid/decisions/run` (`hybrid_detection_service.py`) folds deterministic alert rules + the statistical baseline + IsolationForest + device criticality + open incidents + recent recovery activity into one versioned `HybridDecision` per feature window — rules stay authoritative (AI evidence can raise `combined_severity`, never lower it below a fired rule's). `AnomalyModel` rows now carry a governed `lifecycle_status` ladder (`candidate → shadow → advisory → alert_eligible`, or `retired`); promotion (`POST /observability/models/{id}/promote`) requires passing structural gates (schema/checksum) plus, past `shadow`, a linked `ModelEvaluationReport` (`POST /observability/models/{id}/evaluate`) showing ≥20 reviewed predictions and ≤30% false-positive rate. `POST /replay/run` (`replay_service.py`) re-runs the hybrid pipeline read-only against historical feature windows for backtesting — never writes `AnomalyPrediction`/`HybridDecision`/`Alert`/`Incident`/`RecoveryCommand`, only an audit-only `ReplayRun` row. `ai_recommendation_service.py` can propose a narrowly allowlisted (`collect_diagnostics`/`retry_telemetry_sync`) recovery command from a `HybridDecision`, gated by `self_healing_automation_enabled` (default `False`) and still going through the full policy/signing pipeline unchanged. See `docs/ai_observability_architecture.md` (Sprint 4-6 section) for full detail.

**Canonical telemetry model (v3.3):** `system_metrics` is still authoritative and every existing reader is untouched, but native samples now also project into a canonical model in the same transaction — `resources` (an observable thing identified by OpenTelemetry-style attributes), `metric_series` (resource + name + unit + kind + canonical attributes) and `metric_points` (the narrow append table). Identity hashes are lookup accelerators only: `resource_service`/`metric_series_service` compare the stored attribute JSONB for exact equality and carry a `collision_seq`, so a hash collision cannot fuse two resources. Cardinality is bounded by a per-tenant budget on *new* series per window (`cardinality_service`) — existing series always accept points. Kill switch: `CANONICAL_TELEMETRY_DUAL_WRITE_ENABLED`. Retirement path for the legacy table: `docs/adr/0009-canonical-telemetry-model.md`.

**OTLP ingestion (v3.3):** `POST /v1/metrics` — mounted at the OpenTelemetry spec's own path, deliberately NOT under `/api/v1`, because every exporter appends `/v1/metrics` to its endpoint. Protobuf only (`application/x-protobuf`), gzip supported with a decompression-bomb ceiling enforced *during* inflation, gauge and sum (delta/cumulative) points, OTLP partial success, `google.rpc.Status` error bodies. Authenticated by an organisation-scoped `IngestCredential` (`sxi_live_`), which is a third credential type and is NOT interchangeable with a device token. Managed via `/api/v1/ingest-credentials` (admin+, audited, rotatable with an overlap window). Not implemented and advertised as `null` in `/health`: OTLP logs, traces, gRPC, OTLP/JSON, histograms. See `docs/adr/0011-otlp-interoperability-boundary.md`.

**Metric query engine (v3.3):** `POST /api/v1/metric-query` is the read path for the canonical model, plus `GET /metric-query/catalog` and `GET /metric-query/series` for discovery. Every read has a ceiling — bucket width is derived from the requested range so the point budget holds however wide the range is, and a range past `METRIC_QUERY_MAX_RANGE_DAYS`, a page above `max_points`, or a grouping that would exceed `METRIC_QUERY_MAX_SERIES` lines is a 400 that explains itself. A statement timeout backstops the rest and surfaces as 504. Aggregations that would produce a meaningless number are refused rather than answered: summing a gauge or a cumulative counter across a time bucket is arithmetic without physics. Group keys reach SQL as bind parameters (`attributes ->> :gb0`), so an attribute key is data even though it shapes the result.

**Shared rate limiting (v3.3):** counters live in a shared store behind the `limits` Storage interface, so the ten existing `@limiter.limit(...)` decorators are unchanged. `RATE_LIMIT_BACKEND=auto` (default) means PostgreSQL — limits hold across API processes with no extra infrastructure; `valkey` points at a pinned local Valkey (`docker compose --profile valkey up valkey`); `memory` is per-process and correct only for one worker. An unreachable shared store falls back to per-process counting, `/health` reports `degraded` and says why, and it never starts allowing everything. See `docs/adr/0012-shared-rate-limiting-and-live-events.md`.

**Live event stream (v3.3):** `GET /api/v1/events/stream` is organisation-scoped SSE with event ids, heartbeats, `Last-Event-ID` resume over a 50-event overlap, and a session re-check every 30s so logout ends the stream. Fan-out is a poll of `domain_events` rather than a message bus: the worker already writes there, so worker-to-browser propagation crosses processes with no broker, and a reconnecting client resumes from durable history. Events are written into the producer's transaction, so the stream cannot announce something that then rolls back. Frames say *what changed*, never *the new state* — the browser refetches through the normal API (`useLiveEvents` → TanStack Query invalidation), so the console keeps working with the stream off. `GET /api/v1/events/recent` is the same data over REST.

**Transactional outbox and worker (v3.3):** `outbox_service.enqueue()` writes an `outbox_jobs` row into the **caller's** transaction and does not commit, so accepted telemetry and the obligation to process it are durable together or not at all. The worker is `python -m app.worker` — `FOR UPDATE SKIP LOCKED` claiming, one transaction per job, at-least-once delivery with idempotent handlers, and `attempts` incremented at *claim* time so a job that kills workers still ages into `dead`. Periodic maintenance needs no leader: jobs are enqueued with a time-bucketed `dedupe_key` and the unique constraint picks one winner. `purge_expired_sessions` is finally scheduled (hourly). Queue depth drives `/health` degradation and OTLP `Retry-After` shedding. See `docs/adr/0008-transactional-outbox-and-worker.md`.

**Config:** `pydantic_settings` reading `backend/.env`; `get_settings()` is `@lru_cache`.

---

## Agent Architecture

Single-loop process (`agents/desktop-python/sentinelx_agent/main.py`):
1. Registers/refreshes the local machine as a Device (idempotent by hostname; the seeded laptop device matches `SENTINELX_AGENT_HOSTNAME=laptop-agent-tn-01` + org slug `technova`)
2. Sends heartbeat and metrics on separate intervals; retries transient failures with backoff
3. All calls carry `SENTINELX_DEVICE_TOKEN` as a Bearer token — the agent will not work without it
4. Optionally logs a recovery action via `/recovery-actions/agent-log` when thresholds are breached (non-destructive — DB record only)

Config in `agents/desktop-python/.env` (see `.env.example` for the full variable list).

---

## Frontend Architecture

**Stack:** React 19, TypeScript 6, Vite 8, Tailwind CSS v4, TanStack Query v5, TanStack Table v8, React Router v8, Recharts v3, GSAP (+ ogl for the landing page), lucide-react icons. Tests: Vitest 4 + React Testing Library + jsdom + axe-core (`npm test`). The Auth0 scaffold was removed in the v3.2 sprint — there is one auth direction, the backend session flow (ADR 0005).

**Routing:** `src/App.tsx` — public landing page at `/` (scroll-animated cover), then two `ProtectedRoute` groups: one for all authenticated users, one `allowedRoles={["admin", "owner", "platform_admin"]}`.

**Shell:** `src/layouts/AppShell.tsx` — collapsible sidebar (desktop) + horizontal scroll nav (mobile); nav items carry optional `roles` filter.

**Auth:**
- `src/contexts/AuthContext.tsx` — user state, `login`/`signup`/`logout`/`hasRole`, cold-start session restore via `/auth/refresh`, and proactive renewal at 75% of token lifetime
- **The access token is held in memory only** (`src/lib/authStorage.ts`) — never localStorage or sessionStorage. On reload the app has no token and trades the HttpOnly refresh cookie for a new one
- `request()` in `src/lib/api.ts` sends `credentials: "include"` and the `X-CSRF-Token` header, and on a 401 performs one single-flight refresh then replays the request. The single-flight part is load-bearing: refresh rotates the token, so parallel refreshes would present a spent one and trip the server's replay detection

**API layer:** `src/lib/api.ts` exports a single `sentinelxApi` object; all HTTP goes through one `request<T>()`. Base URL from `VITE_API_BASE_URL`, default `http://127.0.0.1:8000/api/v1`.

**Data fetching:** hooks in `src/hooks/use*Query.ts` wrap TanStack Query; query key constants in `src/lib/queryKeys.ts`.

**Design system:** `src/styles/sentinelx.css` — light "Operations Console" look on a 60/30/10 Teal + Slate + Sand Brown palette: warm stone shell (`--sx-bg: #f6f6f4`, 60% neutrals), slate secondary text/icons (`--sx-muted: #475569`, 30%), teal actions/brand (`--sx-accent: #0d9488`, accent text `#0f766e` for AA), sand brown reserved for warnings/highlights (`--sx-amber/--sx-sand: #a16207`). Tokens are `--sx-*` CSS custom properties on `:root`; an explicit dark theme exists under `:root[data-theme="dark"]`, plus high-contrast and colour-blind (Okabe–Ito) override classes on `:root`. Fonts: Plus Jakarta Sans (UI + brand wordmark), JetBrains Mono (`.sx-mono`). Key utility classes: `.sx-panel`, `.sx-kpi`, `.sx-button-primary`, `.sx-button-secondary`, `.sx-input`, `.sx-animate-in` + `.sx-delay-1..6`, `.sx-live-dot`, `.sx-bar-animated`. Brand PNGs in `public/brand/` carry a teal glow (recolored from the old signal-red).

**Shared component patterns:**
- `ConsoleHeader` — page eyebrow/title/description block
- `DataTable` — TanStack Table wrapper with 5-row pagination
- `Badge` — status/severity chips with `tone` prop (`slate|green|amber|red|blue`)
- `PermissionGate` — inline role check for showing/hiding UI elements

**Code comments:** minimal, human-style — 1–2 lines at non-obvious points only; no decorative dividers or AI narration.

---

## Environment Files

| File | Purpose |
|------|---------|
| `backend/.env` | DB URL, JWT secret, CORS origins |
| `agents/desktop-python/.env` | Backend URL, **device token**, hostname/org slug, intervals, recovery thresholds |
| `agents/embedded-bridge/.env` | Bridge `SENTINELX_*` settings incl. Arduino device token |
| `frontend/.env` | `VITE_API_BASE_URL` (optional) |

---

## Key Constraints (coursework)

- No Alembic — fresh dev schema changes require drop + `init_db` (+ `seed`); changes to an *existing* database (a legacy snapshot, or production) go through hand-written SQL in `migrations/`, applied deterministically and idempotently via `python -m app.db.apply_migrations` (tracks progress in a `schema_migrations` table; chronological order is parsed from the filename's embedded date, not filename string order — the two formats used across files sort differently)
- Logout, logout-all and deactivation revoke server-side via `user_sessions`; there is no separate blacklist because the session row *is* the authority
- Recovery-command `parameters` are validated server-side per action in `services/recovery_parameter_schemas.py` before signing — unknown keys are rejected, not dropped. Adding an action means adding a schema there. The canonical signed payload (including its duplicated `expires_at`) must not change without a coordinated agent protocol bump
- Agent recovery actions execute real, narrowly allowlisted local operations (log rotation, queue/DB repair, service restarts, monitoring-mode toggles — see `agents/desktop-python/sentinelx_agent/executors.py` and Android's `CommandExecutor.kt`), never arbitrary shell/PowerShell
- Public self-registration (`POST /auth/signup`) is gated by `PUBLIC_SIGNUP_ENABLED`, which defaults to **False whenever `APP_ENV=production`** unless set explicitly — the endpoint stays mounted but returns 403. Bootstrap the first production admin with `python -m app.db.create_admin`; `seed.py` is unusable there because it wipes the database first
- Retention is enforced by `python -m app.db.data_retention_prune` (dry-run by default, `--execute` to delete, batched). `app/db/data_retention_report.py` remains read-only
- Test suites: **521 backend/contract/integration tests**, run by `.github/workflows/backend.yml` as one pytest invocation (`pytest ../tests/backend ../tests/contract ../tests/integration`) because all three share `tests/conftest.py`. v3.3 added `tests/backend/test_canonical_telemetry.py`, `test_outbox.py`, `test_worker.py`, `test_native_dual_write.py`, `test_otlp_ingest.py`, `test_ingest_credentials.py`, `test_metric_query.py`, `test_feature_window_slicing.py`, `test_shared_rate_limiting.py`, `test_live_events.py` and `tests/contract/test_agent_protocol_v1.py`. `tests/e2e/` needs a live backend and `tests/load/` is Locust — both are excluded from that invocation rather than skipped. `frontend/` has 74 Vitest tests. The CI Gate has its own suite at `.github/scripts/test_ci_gate.py` (28 tests); it lives there rather than under `tests/` because `tests/conftest.py` opens a database at import time and the gate must run without one
- Re-seeding invalidates device tokens/UUIDs — always re-wire `agents/desktop-python/.env` and `agents/embedded-bridge/.env` afterwards
