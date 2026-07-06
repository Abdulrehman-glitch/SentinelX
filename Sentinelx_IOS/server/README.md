# SentinelX Mobile API — Dev Server

Development harness for the iOS agent: a faithful implementation of the
API contract in `../docs/spec/03_Backend_API.md` over SQLite. It is **not**
the production backend (`C:\SentinelX\backend`) — merging this behaviour
into the real backend is a later, user-approved integration phase.

## Setup (Windows, PowerShell)

```powershell
cd C:\SentinelX\Sentinelx_IOS\server
C:\Python314\python.exe -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Run the server

```powershell
cd C:\SentinelX\Sentinelx_IOS\server
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8100
# Swagger UI: http://127.0.0.1:8100/docs
```

Port 8100 so it never collides with the production backend on 8000.

## Run the tests

```powershell
cd C:\SentinelX\Sentinelx_IOS
server\.venv\Scripts\python.exe -m pytest server/tests -q
```

(Also works from inside `server/` as `.venv\Scripts\python.exe -m pytest -q`.)

## Environment

| Variable | Default | Purpose |
|----------|---------|---------|
| `SENTINELX_MOBILE_DB` | `sentinelx_mobile_dev.db` | SQLite file path |
| `SENTINELX_MOBILE_JWT_SECRET` | dev-only value | JWT signing secret |

## Layout

```
app/
  main.py        app factory + router registration (/api/v1/mobile)
  config.py      Settings (env-driven)
  database.py    SQLite schema (mirrors spec 05 §31) + connections
  models.py      Pydantic request/response models (spec 03/05)
  security.py    JWT issue/verify, PBKDF2 secret hashing
  store.py       data access (devices, credentials, telemetry, alerts)
  validation.py  per-category payload rules (spec 05 §34)
  errors.py      standard error envelope (spec 03 §5)
  deps.py        request deps: settings, DB conn, authenticated device
  routes/
    auth.py       POST /register /login /token/refresh
    telemetry.py  POST /telemetry /batch (idempotent by event_id)
    devices.py    GET/PATCH /profile, dashboard queries
    config.py     GET /config (collector intervals)
    websocket.py  WS /ws/{device_id} — first-message auth, heartbeat, ingest
tests/           pytest contract tests (fresh temp DB per test)
tools/           Codex lane — device simulator + payload generators
```

## Device simulator

Register a simulator device and save its device secret locally:

```powershell
cd C:\SentinelX\Sentinelx_IOS
server\.venv\Scripts\python.exe -m server.tools.device_simulator --register
```

Stream telemetry over WebSocket. Use `--max-events 10` for a finite smoke test;
omit it for a continuous run:

```powershell
server\.venv\Scripts\python.exe -m server.tools.device_simulator --max-events 10 --verify
```

Send a REST-only batch burst:

```powershell
server\.venv\Scripts\python.exe -m server.tools.device_simulator --rest-only --burst 25 --verify
```

Useful options:

- `--api-base http://127.0.0.1:8100/api/v1/mobile`
- `--state-file .simulator_state.json`
- `--seed 42` for deterministic payload curves
- `--chaos` to randomly drop and reconnect the WebSocket

## Contract notes for the simulator (C1)

- Re-registering the same `vendor_identifier` keeps the `device_id` but
  **rotates the device secret** (only hashes are stored server-side) —
  persist the newest secret.
- Refresh tokens rotate on every `/token/refresh`; the previous refresh
  token is invalidated.
- Telemetry is idempotent by `event_id`: duplicates return
  `accepted: true, duplicate: true` and store nothing.
- Batch uploads reject invalid events individually (`rejected_events`),
  never the whole batch.
- WS protocol: send `{"type": "auth", "access_token", "device_id"}` first;
  then `heartbeat` / `telemetry.event` / `telemetry.batch`. Invalid events
  get an `error` message back; the connection stays open.
- Rate limiting (C2) and replay-window validation (C3) are not implemented
  yet — the `Settings` fields for C3 already exist in `app/config.py`.
