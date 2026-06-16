# SentinelX Monitoring Agent

The SentinelX monitoring agent is a lightweight Python process that collects local system metrics and sends them to the SentinelX FastAPI backend.

## Current MVP responsibilities

- Register the host machine as a monitored device.
- Send heartbeat signals.
- Collect CPU, memory, and disk utilisation using `psutil`.
- Send metrics to the backend.
- Allow the backend to generate alerts.
- Log non-destructive recovery actions when resource usage crosses configured thresholds.

## Run locally

Start the backend first in Terminal 1:

```cmd
cd /d C:\SentinelX\backend
.venv\Scripts\activate
uvicorn app.main:app --reload