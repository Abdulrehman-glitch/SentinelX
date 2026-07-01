# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SentinelX is a distributed monitoring and self-healing platform (COM668 Computing Project). The full pipeline is:

```
Python Agent (psutil) → FastAPI Backend → PostgreSQL → React Dashboard
```

Three independent components, each with its own virtualenv or node_modules.

---

## Running the Components

Each component must be started from its own directory with its own environment.

### Backend (FastAPI)
```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
# Runs on http://127.0.0.1:8000  — Swagger UI at /docs
```

### Database bootstrap (first run only, no Alembic)
```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m app.db.init_db
```

### Agent (psutil collector)
```powershell
cd agent
.\.venv\Scripts\Activate.ps1
python -m sentinelx_agent.main
```

### Frontend (React + Vite)
```powershell
cd frontend
npm run dev
# Runs on http://127.0.0.1:5173
```

### Frontend build & lint
```powershell
npm run build   # tsc then vite build
npm run lint    # eslint
```

---

## Backend Architecture

**Entry:** `backend/app/main.py` — mounts CORS middleware and the API router.

**Routing:** `backend/app/api/router.py` — all route modules are registered here under `/api/v1`.

**Auth & RBAC:**
- JWT tokens issued at login via `core/security.py` (`create_access_token`/`decode_access_token`)
- `api/deps.py` exports two FastAPI dependencies: `get_current_user` (Bearer token → User) and `require_role(["admin"])` (factory for role-protected endpoints)
- Roles are `"admin"` and `"viewer"` (stored on `User.role`)
- Tokens are stateless (no blacklist); logout is audit-log only

**Database:**
- SQLAlchemy 2 (sync sessions) + psycopg3 (psycopg-binary)
- Session dependency: `get_db()` in `db/session.py`
- Tables created with `Base.metadata.create_all` — no Alembic migrations yet
- All primary keys are `UUID(as_uuid=True)`; `func.now()` for server-side timestamps

**Alert pipeline (core business logic):**
1. Agent POSTs metrics to `POST /api/v1/metrics`
2. `metrics.py` route evaluates enabled `AlertRule` rows via `alert_rule_service.py`
3. If no enabled rules match, falls back to hardcoded thresholds in `anomaly_service.py` (85%/95% for CPU/mem/disk)
4. Critical alerts auto-create `Incident` records
5. All significant events write `AuditLog` rows via `audit_log_service.py`

**Services** (`backend/app/services/`):
- `anomaly_service.py` — threshold-based anomaly detection (no ML)
- `alert_rule_service.py` — evaluates configurable AlertRule rows and enforces cooldown
- `audit_log_service.py` — writes structured audit entries
- `health_score_service.py` — derives a device health score from recent metrics

**Config:** `pydantic_settings` reading from `backend/.env` (see `.env.example`). The `get_settings()` call is `@lru_cache`.

---

## Agent Architecture

Single-loop process (`agent/sentinelx_agent/main.py`):
1. Registers the local machine as a Device (idempotent by hostname)
2. Sends heartbeat each iteration
3. Collects CPU/memory/disk via psutil
4. POSTs metrics to the backend; receives alert count in response
5. Optionally logs a recovery action if thresholds are breached (non-destructive — DB record only)

Config is read from `agent/.env` (see `agent/.env.example`). Key variables: `SENTINELX_API_BASE_URL`, `SENTINELX_INTERVAL_SECONDS`, recovery thresholds.

---

## Frontend Architecture

**Stack:** React 19, TypeScript 6, Vite 8, Tailwind CSS v4, TanStack Query v5, TanStack Table v8, React Router v8, Recharts v3, Framer Motion, @xyflow/react (topology).

**Routing:** `src/App.tsx` — two `ProtectedRoute` groups: one for all authenticated users, one `allowedRoles={["admin"]}` only.

**Shell:** `src/layouts/AppShell.tsx` — fixed sidebar (desktop) + horizontal scroll nav (mobile); nav items carry optional `roles` filter.

**Auth:**
- `src/contexts/AuthContext.tsx` — manages user state, exposes `login`/`signup`/`logout`/`hasRole`
- Token stored in `localStorage` via `src/lib/authStorage.ts`
- All API calls attach the Bearer token automatically via the `request()` helper in `src/lib/api.ts`

**API layer:** `src/lib/api.ts` exports a single `sentinelxApi` object. All HTTP calls go through one `request<T>()` function. Base URL reads from `VITE_API_BASE_URL` env var, defaults to `http://127.0.0.1:8000/api/v1`.

**Data fetching:** Hooks in `src/hooks/use*Query.ts` wrap TanStack Query. Query key constants are in `src/lib/queryKeys.ts`.

**Design system:** `src/styles/sentinelx.css` — "Forge Edition", obsidian + amber palette. Design tokens are CSS custom properties on `:root` (e.g. `--sx-accent: #f59e0b`). Key utility classes: `.sx-panel`, `.sx-kpi`, `.sx-button-primary`, `.sx-button-secondary`, `.sx-input`, `.sx-animate-in` + `.sx-delay-1..6`, `.sx-live-dot`, `.sx-bar-animated`. Fonts: `Outfit` (UI), `JetBrains Mono` (mono labels, `.sx-mono`).

**Shared component patterns:**
- `ConsoleHeader` — page eyebrow/title/description block
- `DataTable` — TanStack Table wrapper with 5-row pagination
- `Badge` — status/severity chips with `tone` prop (`slate|green|amber|red|blue`)
- `PermissionGate` — inline role check for showing/hiding UI elements

---

## Environment Files

| File | Purpose |
|------|---------|
| `backend/.env` | DB URL, JWT secret, CORS origins |
| `agent/.env` | Backend API URL, polling interval, recovery thresholds |
| `frontend/.env` | `VITE_API_BASE_URL` (optional) |

Copy the corresponding `.env.example` files to get started.

---

## Key Constraints (coursework)

- No Alembic — schema changes require `drop + init_db` in dev
- No token blacklist — logout is audit-log only
- Agent recovery actions are DB records only — no actual process execution
- No test suite yet — `tests/` and `scripts/` directories are stubs
