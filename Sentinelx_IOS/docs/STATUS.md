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

### 2026-07-06 - Claude Code (session 2, continued) — iOS Phase 4

- Implemented the Phase 4 upload pipeline in `ios/`:
  - `WebSocketClient` (actor) — connects to `ws/{device_id}`, first-message
    auth via `AccessTokenProviding` (APIClient supplies/refreshes the JWT),
    heartbeat every 30 s, jittered exponential reconnect
    (`RetryPolicy.reconnect`), server pushes exposed via `serverMessages()`.
  - `SyncManager` (actor) — subscribes to `TelemetryManager.eventStream()`,
    sends each event over the WS; on stream failure buffers in memory and
    flushes REST batches (interval or batch-size threshold). The in-memory
    buffer is the Phase 4 stopgap; Phase 5 replaces it with SQLite.
  - `APIClient` gained `uploadTelemetry` / `uploadTelemetryBatch` /
    `currentAccessToken`; new `WSMessages.swift` + `UploadModels.swift` —
    batch items encode WITHOUT `device_id` per spec 03 §14, matching the
    dev server's strict `BatchEvent` model.
  - `AppContainer.startAgent()/stopAgent()` bring collectors + WS + sync up
    and down as one unit (MainTabView / SettingsView wired).
  - Default server URLs now point at the dev server port **8100**
    (project.yml Info.plist defaults + AppEnvironment fallbacks).
- Tests added (XCTest, scripted WS connection): handshake, auth-rejection
  reconnect, drop-reconnect, send-while-disconnected, heartbeat cadence,
  WS→REST fallback, batch-threshold flush, retry-after-failure, batch
  encoding contract. **Not yet run — needs a Mac** (xcodegen + xcodebuild);
  flagged for the next Mac session.
- Next (Claude Code): run the Swift suite on a Mac, then Phase 5 (SQLite
  offline queue); optionally verify end-to-end against the dev server with
  the C1 simulator as the reference client.

### 2026-07-06 - Codex

- Completed C3 replay-window validation.
- Extended telemetry validation to reject events older than
  `Settings.max_event_age_hours` (default 24h) or more than
  `Settings.max_event_future_minutes` ahead (default 5m).
- Wired replay checks through single REST upload, batch upload, and WebSocket
  telemetry ingest.
- Batch uploads reject stale/future events individually while still accepting
  fresh events in the same batch.
- Verification:
  `server\.venv\Scripts\python.exe -m pytest server\tests\test_telemetry.py
  -q --basetemp server\.pytest_tmp` passed (9 passed), and
  `server\.venv\Scripts\python.exe -m pytest server\tests -q --basetemp
  server\.pytest_tmp_full` passed (37 passed).
- Next: mark C4 `IN PROGRESS - codex` and implement the server-side alert
  engine.

### 2026-07-06 - Codex

- Completed C2 rate limiting per spec 03 section 22 (commit `5c0212e`).
- Added an in-memory fixed-window limiter on `app.state` with configurable
  defaults for register, login, telemetry, batch, and WebSocket messages.
- HTTP limits return the standard 429 error envelope with
  `details.retry_after_seconds`; WebSocket message limits return a typed
  `RATE_LIMITED` error with the same retry detail.
- Added tests for register, login, telemetry, and WebSocket message limits.
- Verification:
  `server\.venv\Scripts\python.exe -m pytest server\tests\test_rate_limiting.py
  -q --basetemp server\.pytest_tmp` passed (4 passed), and
  `server\.venv\Scripts\python.exe -m pytest server\tests -q --basetemp
  server\.pytest_tmp_full` passed (35 passed).
- Next: mark C3 `IN PROGRESS - codex` and implement replay-window validation.

### 2026-07-06 - Codex

- Completed C1 device simulator CLI (commit `7436dbd`) in
  `server/tools/device_simulator.py`.
- Simulator supports `--register`, persisted `.simulator_state.json`, login,
  first-message WebSocket auth, heartbeat, telemetry events, REST-only uploads,
  batch bursts, seeded payloads, chaos reconnects, and dashboard verification.
- Added simulator unit coverage for state persistence, registration payloads,
  batch shape, and WebSocket URL derivation.
- Updated `server/README.md` with simulator usage examples.
- Verification:
  `server\.venv\Scripts\python.exe -m pytest server\tests\test_simulator_payloads.py
  server\tests\test_device_simulator.py -q --basetemp server\.pytest_tmp`
  passed (8 passed), and
  `server\.venv\Scripts\python.exe -m pytest server\tests -q --basetemp
  server\.pytest_tmp_full` passed (31 passed).
- Live smoke: launched the dev server on port 8100, registered a simulator,
  streamed five categories over WebSocket, verified the dashboard summary, then
  sent a REST batch burst successfully.
- Next: mark C2 `IN PROGRESS - codex` and implement API/WebSocket rate
  limiting per spec 03 section 22.

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

- Completed C0 simulator payload generators (commit `21fc4d5`) in
  `server/tools/` with
  spec-aligned event envelopes and payloads for device, battery, thermal,
  storage, and network telemetry.
- Added deterministic seeded generator mode and standalone property-style tests
  covering 1000 iterations of spec 05 section 34 validation rules.
- Created `docs/DECISIONS.md` with ADR-001 for simulator curve and RNG choices.
- Created `server/.venv` and installed `server/requirements.txt`; the first
  sandboxed install failed due blocked network, then succeeded after approval.
- Verification: `server\.venv\Scripts\python.exe -m pytest
  server\tests\test_simulator_payloads.py -q` passed; full suite passed with
  workspace temp override:
  `server\.venv\Scripts\python.exe -m pytest server\tests -q --basetemp
  server\.pytest_tmp` (27 passed).
- Next: mark C1 `IN PROGRESS - codex` and implement
  `server/tools/device_simulator.py`.

### 2026-07-06 - Codex

- Read `AGENTS.md` and all documentation under `docs/`, including `CODEX_ROADMAP.md` and `docs/spec/00` through `10`.
- Verified current branch is `feature/ios-mobile-agent`.
- Confirmed `docs/STATUS.md` and `docs/DECISIONS.md` were missing before this entry.
- Inspected `server/`; found only a partial untracked scaffold (`app/config.py`, `app/errors.py`, `app/timeutil.py`, `requirements.txt`, `.gitignore`).
- Did not start C1 because `docs/CODEX_ROADMAP.md` requires a documented `Dev server: done` handoff before any server task.
- Next: wait for Claude Code to complete and record the dev server handoff, then mark C1 `IN PROGRESS - codex` and implement `server/tools/device_simulator.py`.
