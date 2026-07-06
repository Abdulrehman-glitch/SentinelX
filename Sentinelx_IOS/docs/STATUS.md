# SentinelX Mobile Agent Status

This file is the shared coordination log for Claude Code and Codex.

## Current Phase

- Branch: `feature/ios-mobile-agent`
- Claude Code lane: `ios/` + dev server scaffold in `server/app/`
- Codex lane: `server/tools/` + `server/tests/` tasks from `docs/CODEX_ROADMAP.md`
- Dev server: done (2026-07-06 — 23 contract tests green, live boot verified)
- **Codex: C0–C5 all unblocked.** After handoff, `server/` is Codex's lane
  (including `app/` for C2–C4); Claude Code stays on `ios/`.

## Agent Memory

### Codex

- Read `AGENTS.md` and every file under `docs/`.
- Must not edit outside `Sentinelx_IOS/`.
- Must not modify `ios/` unless a reproduced Mac compile/test issue requires it.
- Dev server handoff is **done** — all roadmap tasks C0–C5 are unblocked.
- `server/` is now your lane, including `app/` (C2 rate limiting, C3 replay
  window, C4 alert engine all touch it). Read `server/README.md` first —
  it documents the contract quirks (secret rotation on re-register, refresh
  rotation, idempotency semantics, WS protocol).
- Keep `server\.venv\Scripts\python.exe -m pytest server/tests -q` green;
  don't break the 23 existing contract tests.

### Claude Code

- Dev server delivered 2026-07-06 (models, auth, telemetry ingest,
  config, WebSocket, dashboard queries, 23 contract tests, README).
- Back on `ios/` next: WebSocket client + upload pipeline in the Swift app
  (heartbeat, telemetry.event streaming, batch fallback) against this
  server on port 8100.

## Worklog

### 2026-07-06 - Claude Code (session 2)

- Resumed from the night session; read Codex's STATUS entry and inspection.
- Added roadmap task C0 (simulator payload generators, `server/tools/` +
  `server/tests/` only) so Codex can work in parallel while the dev server
  is finished — C0 has no precondition; C1–C5 still gated on
  `Dev server: done`.
- Divided `server/` ownership for this session: Claude Code = `server/app/`,
  Codex = `server/tools/` + `server/tests/test_simulator_payloads.py`.
- Added `docs/RESUME_GUIDE.md` (how to resume an interrupted agent session).
- Completed the dev server (`server/app/`): pydantic models, register/login/
  token-refresh (JWT, PBKDF2-hashed secrets, refresh rotation), telemetry
  single + batch ingest (idempotent by event_id, per-event batch rejection),
  payload validation per spec 05 §34, collector config endpoint, WebSocket
  channel (first-message auth, heartbeat.ack, telemetry.event/batch), and
  dashboard queries (device summaries with latest battery/thermal/network,
  filtered/paginated telemetry, alerts).
- 23 pytest contract tests green on Python 3.14 (`server/.venv`); live
  uvicorn boot on port 8100 smoke-tested (healthz + register over HTTP).
- `server/README.md` documents setup, run/test commands, and contract
  quirks for the C1 simulator.
- Handoff recorded: `Dev server: done` — C1–C5 unblocked for Codex.
- Next (Claude Code): Swift WebSocket client + upload pipeline in `ios/`
  targeting this server on port 8100.

### 2026-07-06 - Codex

- Read `AGENTS.md` and all documentation under `docs/`, including `CODEX_ROADMAP.md` and `docs/spec/00` through `10`.
- Verified current branch is `feature/ios-mobile-agent`.
- Confirmed `docs/STATUS.md` and `docs/DECISIONS.md` were missing before this entry.
- Inspected `server/`; found only a partial untracked scaffold (`app/config.py`, `app/errors.py`, `app/timeutil.py`, `requirements.txt`, `.gitignore`).
- Did not start C1 because `docs/CODEX_ROADMAP.md` requires a documented `Dev server: done` handoff before any server task.
- Next: wait for Claude Code to complete and record the dev server handoff, then mark C1 `IN PROGRESS - codex` and implement `server/tools/device_simulator.py`.
