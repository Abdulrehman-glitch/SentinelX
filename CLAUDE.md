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
| `agents/desktop-python/` | Desktop agent v2.1 — psutil telemetry authenticated with a device token |
| `agents/android-native/` | Android agent v2.1.0 — Kotlin/Compose, batch metrics via `/metrics/batch` |
| `agents/ios-native/` | iOS mobile agent — Swift 6 / SwiftUI app (`ios/`) + FastAPI/SQLite mobile dev server (`server/`, port 8100) |
| `agents/mobile-expo/` | React Native / Expo cross-platform mobile agent (work in progress) |
| `agents/embedded-bridge/` | Python BLE/serial bridge forwarding Arduino sensor data to the backend |
| `embedded/arduino_nano33_ble_sense_rev2/` | Arduino firmware (temperature, pressure, motion, impact) |
| `migrations/` | Versioned, hand-applied index SQL files (no migration tool) |
| `tests/` | Test suites — `backend/`, `contract/`, `integration/`, `e2e/` (being populated) |
| `docs/` | `DEMO_USERS.md`, brand assets (`brand/`), local evidence pack (`Evidence/`, gitignored) |
| `docker-compose.yml` | Local Postgres 16 (`sentinelx_dev`) |
| `scripts/azure_teardown.ps1` | Tears down the Azure deployment |

`AGENTS.md` is a parallel guidance file for Codex — keep the two in sync when architecture changes.

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
- Two login paths: `POST /api/v1/auth/token` (OAuth2 password form — used by Swagger UI's Authorize button) and `POST /api/v1/auth/login` (JSON — used by the React app)
- Six roles with a numeric hierarchy in `api/deps.py` (`ROLE_HIERARCHY`): `platform_admin > owner > admin > engineer > operator > viewer`
- `api/deps.py` dependencies: `get_current_user`, `require_role([...])`, `require_min_role("engineer")`, `get_org_scoped_user`, and `get_device_from_token` (raw Bearer device token → Device, verified against hashed `DeviceCredential` rows)
- Tokens are stateless (no blacklist); logout is audit-log only

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

**Stack:** React 19, TypeScript 6, Vite 8, Tailwind CSS v4, TanStack Query v5, TanStack Table v8, React Router v8, Recharts v3, GSAP (+ ogl for the landing page), lucide-react icons. An `@auth0/auth0-react` scaffold exists (`Auth0CallbackPage`) but primary auth is the backend JWT flow.

**Routing:** `src/App.tsx` — public landing page at `/` (scroll-animated cover), then two `ProtectedRoute` groups: one for all authenticated users, one `allowedRoles={["admin", "owner", "platform_admin"]}`.

**Shell:** `src/layouts/AppShell.tsx` — collapsible sidebar (desktop) + horizontal scroll nav (mobile); nav items carry optional `roles` filter.

**Auth:**
- `src/contexts/AuthContext.tsx` — user state, `login`/`signup`/`logout`/`hasRole`
- Token in `localStorage` via `src/lib/authStorage.ts`; attached automatically by the `request()` helper in `src/lib/api.ts`

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

- No Alembic — schema changes require drop + `init_db` (+ `seed`) in dev; index tweaks live as raw SQL in `migrations/`
- No token blacklist — logout is audit-log only
- Agent recovery actions are DB records only — no actual process execution
- Backend test suite not written yet — `tests/{backend,contract,integration,e2e}/` are placeholders (the iOS mobile dev server has its own tests in `agents/ios-native/server/tests/`)
- Re-seeding invalidates device tokens/UUIDs — always re-wire `agents/desktop-python/.env` and `agents/embedded-bridge/.env` afterwards
