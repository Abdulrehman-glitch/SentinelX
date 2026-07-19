# SentinelX Desktop Monitoring Agent

The SentinelX desktop agent is a lightweight Python process that collects laptop/desktop system telemetry and streams it to the SentinelX backend as a monitored device. This guide reflects the 2026-07-18 Trusted Agent Foundation rewrite — anonymous self-registration is gone; the agent now **enrols** with a single-use code, stores its device token in the OS credential store, and queues telemetry locally before uploading it in idempotent batches.

## What this agent does

- Enrols itself against the backend with a single-use enrolment code (preferred), or a manually-copied dev token (fallback) — see "First run: identity" below.
- Stores its device token in the OS credential store (Windows Credential Manager via `keyring`), never in plain text on disk once enrolled.
- Collects CPU, memory and disk usage every `SENTINELX_METRICS_INTERVAL_SECONDS` (default 10 s) with `psutil`.
- Queues every sample in a local SQLite database (`%LOCALAPPDATA%\SentinelX\agent.db`) **before** attempting upload, then flushes in idempotent batches (`event_id`-deduplicated `POST /metrics/batch`) — an unreachable backend produces a backlog, not a data gap.
- Sends heartbeats on a separate interval (`SENTINELX_HEARTBEAT_INTERVAL_SECONDS`, default 30 s), including a final "offline" heartbeat on clean shutdown.
- Lets the backend generate alerts/incidents from telemetry (rule-based, not this agent's job).
- Logs non-destructive recovery-action evidence after a **restart-safe** sustained breach — the consecutive-breach counter and cooldown timestamp live in SQLite, not memory, so restarting the agent no longer resets the cooldown.
- Retries transient backend/network errors with backoff; a fatal auth error (bad/revoked token) stops the loop instead of retrying forever.
- Can run as a Windows Service (WinSW) for unattended operation — see "Running as a Windows Service" below.
- Polls for signed recovery commands (`SENTINELX_COMMAND_POLLING_ENABLED`, default on) and executes the allowlisted ones it receives — see "Safe Recovery Orchestration" below.

## What this agent does not do

It never runs arbitrary shell commands, PowerShell, or CMD text, and never accepts a free-text service name, executable path, or script content from the server. It does not browse files, kill arbitrary processes, delete files, modify the registry, change firewall rules, touch security software, or reboot the machine.

## Safe Recovery Orchestration (Sprint 3)

Since Sprint 3, the agent can execute six typed, individually allowlisted, Ed25519-signed recovery actions dispatched by the backend: `collect_diagnostics`, `rotate_agent_logs`, `retry_telemetry_sync`, `repair_agent_queue` (low-risk, auto-approved by policy), and `restart_sentinelx_agent`, `restart_allowlisted_service` (medium-risk, require human approval in the dashboard). Every command is verified locally (signature, expiry, device match, nonce replay, allowlist membership) before execution — see `sentinelx_agent/signing.py` and `sentinelx_agent/commands.py`. `restart_allowlisted_service` only ever restarts a service named in the local `service_allowlist.json` file (a logical key → real Windows service name mapping under this machine's control, never a value supplied by the server). The older passive-logging path (`backend/app/api/routes/recovery_actions.py`) is unchanged and still exists separately.

## Setup

```powershell
cd C:\SentinelX\agents\desktop-python
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
```

Start the backend in another terminal first (see `CLAUDE.md` for the full command), then confirm it's reachable: `http://127.0.0.1:8000/api/v1/health`.

## First run: identity

Edit `.env`. Two ways to give the agent an identity — pick one:

### Preferred: enrolment code

An org admin mints a single-use code (via Swagger UI at `<backend-url>/docs` → Authorize as admin/owner → `POST /api/v1/devices/enrollment-codes`). Copy the `code` field from the response, then in `.env`:

```env
SENTINELX_ENROLLMENT_CODE=sxe_...
```

Leave `SENTINELX_DEVICE_TOKEN` blank. On its first run, the agent exchanges the code for a device + token, stores the token in the OS credential store (Windows Credential Manager), and logs a reminder to delete the now-used code from `.env` (codes are single-use — leaving it in doesn't hurt, but it's dead weight).

### Fallback: plain-text dev token

For quick local dev without minting a code, set `SENTINELX_DEVICE_TOKEN` directly (e.g. copied from a seeded device — see `docs/DEMO_USERS.md` — or from `POST /device-credentials`). This is a **development-only** path: the token stays in `.env` in plain text, is used every run, and is never promoted into the OS credential store.

Either way, also set (or leave at the seeded defaults):

```env
SENTINELX_AGENT_HOSTNAME=laptop-agent-tn-01
SENTINELX_AGENT_DISPLAY_NAME=Laptop Agent
SENTINELX_DEVICE_TYPE=desktop
SENTINELX_AGENT_TYPE=python_desktop_agent
```

`SENTINELX_ORGANIZATION_SLUG` only matters for the legacy dev-token flow tied to a pre-existing seeded device; an enrolment code already carries its organization, so the agent ignores the slug when enrolling fresh.

## Run it

```powershell
cd C:\SentinelX\agents\desktop-python
.\.venv\Scripts\Activate.ps1
python -m sentinelx_agent
```

Expected output on a fresh enrolment:

```txt
Starting SentinelX desktop agent v3.0.0
Backend API: http://127.0.0.1:8000/api/v1 | hostname: laptop-agent-tn-01
No stored device token — enrolling with the provided one-time code...
Device token stored in the OS credential store.
Enrolled as device 3f2c...-...-.... Remove SENTINELX_ENROLLMENT_CODE from .env (codes are single-use).
Using device ID: 3f2c...
CPU=12.4% | Memory=58.7% | Disk=71.0% | queued=0
```

On subsequent runs (token already in the credential store), it skips straight to `agent_sync` (a lightweight self-refresh, not a new registration) and starts the loop.

## Auto telemetry telecasting (the monitoring loop)

Every cycle of `run_agent()` (`sentinelx_agent/main.py`):

1. Collect a `psutil` sample (CPU/memory/disk). A collector failure is logged and skipped — it never kills the loop.
2. Enqueue the sample into the local SQLite queue immediately (durability first).
3. Send a heartbeat if `heartbeat_interval_seconds` has elapsed since the last one.
4. Flush due queued samples via `POST /metrics/batch` — the backend deduplicates by `event_id`, so retried batches after a dropped response never double-count.
5. Evaluate sustained-breach recovery logging (see below).
6. Sleep `metrics_interval_seconds`, repeat.

On shutdown (Ctrl+C, or service stop), it sends one final "offline" heartbeat before closing cleanly. If the backend is unreachable, the loop keeps running and the queue keeps growing (bounded by `SENTINELX_QUEUE_MAX_ROWS`, default 10000) — nothing is lost, it's just delayed.

**Sustained-breach recovery logging**: a resource threshold breach only gets logged after `SENTINELX_RECOVERY_SUSTAINED_SAMPLES` (default 3) *consecutive* breaching samples, then gated by `SENTINELX_RECOVERY_COOLDOWN_SECONDS` (default 120 s) so it doesn't spam. Both the breach counter and the last-logged timestamp are persisted in SQLite, so restarting the agent mid-breach doesn't reset the cooldown clock.

## Running as a Windows Service

For unattended operation (survives logout/reboot), install via [WinSW](https://github.com/winsw/winsw):

```powershell
# 1. Complete Setup + First run above interactively at least once, so
#    enrolment stores the device token under the account the service will run as.
# 2. From an elevated PowerShell:
cd C:\SentinelX\agents\desktop-python\service
.\install_service.ps1
```

This downloads WinSW, wires it to the agent's venv `python.exe -m sentinelx_agent`, installs it as `SentinelXAgent` (auto-restart on failure, 10 s then 60 s backoff), and starts it immediately. Check status with `.\sentinelx-agent.exe status`; logs land at `%LOCALAPPDATA%\SentinelX\logs\agent.log` (rotating, 2 MB × 5 files) either way, service or interactive. Uninstall with `.\uninstall_service.ps1`.

## Troubleshooting

### `No device identity available`

Neither `SENTINELX_ENROLLMENT_CODE` nor `SENTINELX_DEVICE_TOKEN` is set (or the credential store has nothing stored and both are blank). Mint a fresh enrolment code or set a dev token.

### HTTP 401 on enrolment (`Invalid, expired, or already-used enrolment code`)

Enrolment codes are single-use and expire (default 15 min). Mint a new one.

### HTTP 401 `Invalid or revoked device token` (after a prior successful enrolment)

The stored token was revoked (credential rotation, manual revoke, or the backend DB was re-seeded — re-seeding regenerates all device credentials). Clear the stale entry and re-enrol:

```powershell
python -c "from sentinelx_agent import secrets_store; secrets_store.clear_device_token()"
```

Then set a fresh `SENTINELX_ENROLLMENT_CODE` and run again.

### HTTP 403 `Device token does not match payload device_id`

Shouldn't happen in normal operation — the agent always sends its own resolved `device_id`. If you see this after manually editing `.env`, delete the stored token (see above) and re-enrol cleanly rather than mixing an old device ID with a new token.

### Connection error

Confirm the backend is up: `http://127.0.0.1:8000/api/v1/health`. If the agent is on a different machine than the backend, use the backend's LAN/HTTPS URL in `SENTINELX_API_BASE_URL`, not `127.0.0.1`.

### Rate limit / HTTP 429

The backend protects telemetry ingestion. Increase `SENTINELX_METRICS_INTERVAL_SECONDS` and make sure only one agent process is running per device token.

## Files

```txt
agents/desktop-python/
├── .env.example
├── README.md
├── requirements.txt
├── service/                    # Windows Service (WinSW) install/uninstall
│   ├── install_service.ps1
│   ├── uninstall_service.ps1
│   └── sentinelx-agent.xml
└── sentinelx_agent/
    ├── __init__.py
    ├── __main__.py
    ├── client.py                # HTTP client: enrol, agent_sync, send_metrics_batch, heartbeat, recovery log
    ├── collector.py              # psutil telemetry + device identity collection
    ├── config.py                 # .env-backed AgentConfig
    ├── main.py                   # run_agent() — the monitoring loop
    ├── secrets_store.py           # OS credential store (keyring) for the device token
    └── store.py                   # SQLite offline queue + restart-safe recovery state
```
