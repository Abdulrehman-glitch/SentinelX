# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SentinelX is a distributed monitoring and self-healing platform for smart, industrial, and edge computing environments. It collects device health metrics, detects anomalies, and supports recovery action logging. Built as a COM668 Computing Project.

**Pipeline:** Python Agent → FastAPI Backend → PostgreSQL Database → React Dashboard

## Repository Structure

```
agent/       Lightweight Python monitoring agent (psutil, httpx)
backend/     FastAPI backend API (SQLAlchemy, Pydantic, psycopg)
frontend/    React + Vite + TypeScript dashboard (TanStack Query, Recharts, Tailwind CSS v4)
database/    Supplemental SQL index files (tables are managed by SQLAlchemy create_all)
```

## Development Commands

### Backend (from `backend/`)

```bash
# Activate the virtual environment
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # Unix

# Run the API server (hot reload)
uvicorn app.main:app --reload

# Initialize database tables (run once or after model changes)
python -m app.db.init_db
```

The backend requires `backend/.env`:
```
DATABASE_URL=postgresql+psycopg://sentinelx_app:SentinelX_app_2026!@localhost:5432/sentinelx_dev
BACKEND_CORS_ORIGINS=http://localhost:5173
```

API is available at `http://127.0.0.1:8000`. Interactive docs at `/docs`.

### Agent (from `agent/`)

```bash
.venv\Scripts\activate
python -m sentinelx_agent.main
```

Configure via `agent/.env` (all optional — defaults work out of the box):
```
SENTINELX_API_BASE_URL=http://127.0.0.1:8000/api/v1
SENTINELX_INTERVAL_SECONDS=10
SENTINELX_ENABLE_RECOVERY_LOGGING=true
SENTINELX_CPU_RECOVERY_THRESHOLD=95.0
SENTINELX_MEMORY_RECOVERY_THRESHOLD=95.0
SENTINELX_DISK_RECOVERY_THRESHOLD=95.0
SENTINELX_RECOVERY_COOLDOWN_SECONDS=120
```

### Frontend (from `frontend/`)

```bash
npm install
npm run dev      # dev server on http://localhost:5173
npm run build    # tsc + vite build
npm run lint     # eslint
```

The frontend reads `VITE_API_BASE_URL` from environment (defaults to `http://127.0.0.1:8000/api/v1`).

## Architecture

### Backend

- **Entry point:** `backend/app/main.py` — creates the FastAPI app, wires CORS, mounts the API router.
- **Router:** `backend/app/api/router.py` — single `api_router` mounted at `/api/v1`, aggregating all route modules.
- **Route modules** in `backend/app/api/routes/`: one file per resource (`devices`, `metrics`, `alerts`, `heartbeats`, `recovery_actions`, `overview`, `incidents`, `alert_rules`, `audit_logs`, `health`).
- **Database:** SQLAlchemy 2.0 with synchronous `Session`. `get_db()` in `app/db/session.py` is a FastAPI dependency injected per request. Tables are created via `create_all` (no Alembic yet).
- **Models** (`app/models/`): one SQLAlchemy model per table. All models must be imported in `app/models/__init__.py` so `create_all` discovers them.
- **Schemas** (`app/schemas/`): Pydantic v2 models for request validation and response serialisation, separate from ORM models.
- **Services** (`app/services/`):
  - `anomaly_service.py` — rule-based threshold detection (warning at 85%, critical at 95%).
  - `alert_rule_service.py` — evaluates user-defined `AlertRule` records; falls back to `anomaly_service` when no enabled rules match.
  - `health_score_service.py` — calculates a 0–100 health score from CPU/memory/disk pressure, heartbeat freshness, and unresolved alert count.
  - `audit_log_service.py` — writes `AuditLog` entries for significant system events.
- **Config:** `app/core/config.py` uses `pydantic-settings` with `lru_cache`; reads from `.env`.

### Alert pipeline (metric ingestion)

When `POST /api/v1/metrics` is called by the agent:
1. Metric is stored in `system_metrics`.
2. Enabled `AlertRule` records are evaluated first.
3. If no rules match, built-in `anomaly_service` thresholds are the fallback.
4. Each matching candidate creates an `Alert` record (with cooldown suppression for rule-based alerts).
5. Critical alerts automatically create an `Incident` (if no open incident of the same type already exists for the device).
6. All significant events write to `audit_logs`.

### Frontend

- **State management:** TanStack Query v5 — `staleTime: 15s`, no window-focus refetch, no retry on 4xx.
- **API client:** `src/lib/api.ts` — typed `sentinelxApi` object wrapping a single `request<T>()` helper. `ApiError` carries `status`, `statusText`, and `details`.
- **Query keys:** centralised in `src/lib/queryKeys.ts` — use these constants everywhere, not inline arrays.
- **Data hooks:** `src/hooks/use*Query.ts` — one hook per API resource, all built on `useQuery`. Mutations live in `useOperationalMutations.ts` and `useResolveAlertMutation.ts`.
- **Routing:** React Router v8 with a single `AppShell` layout wrapping all routes. Pages live in `src/pages/`.
- **Styling:** Tailwind CSS v4 (via `@tailwindcss/vite`). Custom design tokens are in `src/styles/sentinelx.css`.
- **Charts:** Recharts for metric history visualisation (`MetricHistoryChart.tsx`).
- **Tables:** TanStack Table v8 via the shared `DataTable.tsx` component.

### Agent

- Registers the local machine once on startup, then loops every `SENTINELX_INTERVAL_SECONDS`.
- Each iteration: collect metrics (`psutil`) → send heartbeat → `POST /metrics` → optionally log recovery action if thresholds exceeded (with cooldown).
- `collector.py` gathers CPU/memory/disk; `client.py` wraps all HTTP calls via `httpx`.

## Key Conventions

- **UUIDs** are used for all primary keys across every model.
- **`last_seen_at`** on `Device` is updated on every metric ingest and heartbeat — it drives heartbeat-freshness scoring.
- The database schema is currently managed by `create_all`. New models must be registered in `app/models/__init__.py`. Supplemental indexes go in the `database/` SQL files and must be applied manually after `init_db`.
- Frontend `types/api.ts` contains all shared TypeScript types — update these when the backend schemas change.
