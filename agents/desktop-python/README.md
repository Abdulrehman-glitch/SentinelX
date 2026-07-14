# SentinelX Desktop Monitoring Agent

The SentinelX desktop agent is a lightweight Python process that collects laptop/desktop system telemetry and sends it to the SentinelX backend as a monitored device.

## What this agent does

- Registers or refreshes the host machine in SentinelX.
- Sends authenticated heartbeats using a device token.
- Collects CPU, memory and disk usage with `psutil`.
- Sends authenticated telemetry to the backend.
- Lets the backend generate alerts/incidents from telemetry.
- Logs non-destructive recovery-action evidence when resource thresholds are crossed.
- Uses retry/backoff so temporary backend/network errors do not immediately kill the agent.
- Avoids aggressive retrying after rate-limit responses.

## What this agent does not do yet

This version does not run remote shell commands, browse files, kill processes, restart services, or reboot the machine. Recovery actions are logged only as safe evidence records for the coursework MVP.

## Required backend state

Run the backend seed command first:

```cmd
cd /d C:\SentinelX\backend
.venv\Scripts\activate
python -c "from app.db.seed import seed_db; seed_db()"
```

The seed command prints a raw token named:

```txt
TechNova Laptop Token: sx_agent_...
```

Copy that token into `agents\desktop-python\.env` as `SENTINELX_DEVICE_TOKEN`.

For the seeded demo, keep:

```txt
SENTINELX_AGENT_HOSTNAME=laptop-agent-tn-01
SENTINELX_ORGANIZATION_SLUG=technova-manufacturing
```

This makes `/devices/register` refresh the existing seeded Laptop Agent device instead of creating a new unmatched device.

## Install and run on Windows CMD

From a fresh terminal:

```cmd
cd /d C:\SentinelX\agent
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
notepad .env
```

Paste the TechNova Laptop Token into:

```txt
SENTINELX_DEVICE_TOKEN=
```

Start the backend in another terminal first:

```cmd
cd /d C:\SentinelX\backend
.venv\Scripts\activate
uvicorn app.main:app --reload
```

Then run the agent:

```cmd
cd /d C:\SentinelX\agent
.venv\Scripts\activate
python -m sentinelx_agent
```

Alternative:

```cmd
python -m sentinelx_agent.main
```

## Expected output

You should see output similar to:

```txt
Starting SentinelX desktop monitoring agent...
Backend API: http://127.0.0.1:8000/api/v1
Hostname: laptop-agent-tn-01
Organization slug: technova-manufacturing
Device token configured: yes
Using device ID: ...
[2026-06-30T...] CPU=12.4% | Memory=58.7% | Disk=71.0% | Alerts created=0
```

## Troubleshooting

### HTTP 401 Invalid or revoked device token

The token in `agents\desktop-python\.env` is wrong, missing, revoked, or not the raw token printed by the seed script. Re-run the backend seed command or generate a new device credential.

### HTTP 403 Device token does not match payload device_id

The device token belongs to a different device than the `device_id` being sent. For the seeded demo, keep:

```txt
SENTINELX_AGENT_HOSTNAME=laptop-agent-tn-01
SENTINELX_ORGANIZATION_SLUG=technova-manufacturing
SENTINELX_DEVICE_ID=
```

Leaving `SENTINELX_DEVICE_ID` blank lets the backend return the seeded laptop device ID.

### Connection error

Make sure the backend is running:

```txt
http://127.0.0.1:8000/api/v1/health
```

### Rate limit / HTTP 429

The backend is protecting telemetry ingestion. Increase `SENTINELX_METRICS_INTERVAL_SECONDS` and avoid running multiple agents with the same token.

## Files

```txt
agents/desktop-python/
├── .env.example
├── README.md
├── requirements.txt
└── sentinelx_agent/
    ├── __init__.py
    ├── __main__.py
    ├── client.py
    ├── collector.py
    ├── config.py
    └── main.py
```
