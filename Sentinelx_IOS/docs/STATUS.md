# SentinelX Mobile Agent Status

This file is the shared coordination log for Claude Code and Codex.

## Current Phase

- Branch: `feature/ios-mobile-agent`
- Claude Code lane: `ios/` + dev server scaffold in `server/app/`
- Codex lane: `server/tools/` + `server/tests/` tasks from `docs/CODEX_ROADMAP.md`
- Dev server: done (2026-07-06 — 23 contract tests green, live boot verified)
- Phase 5 (offline queue) in progress: P5.1 done + CI green (`de40d1e` +
  fix `a2e5b3c`, run 28797905062); P5.2 in progress — claude-code.
- **Codex: C0-C5 and C7 done. Current queue: C8 -> C9** (see
  `docs/CODEX_ROADMAP.md` / `docs/PHASE5_PLAN.md`); C8 blocks Claude P5.3.

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

### 2026-07-06 - Codex

- Completed C7 one-command demo and soak script in `server/tools/demo.py`.
- Demo starts the dev server on port 8100 when needed, registers or reuses
  the simulator device, streams telemetry over WebSocket, prints event/
  alert/reconnect counters, and verifies dashboard telemetry totals.
- Extended the device simulator with reusable send statistics and current
  run timestamps for replay-window-safe demos.
- Updated `server/README.md` with demo and soak usage, and refreshed stale
  C2/C3 contract notes.
- Verification:
  `server\.venv\Scripts\python.exe -m pytest server\tests -q --basetemp
  server\.pytest_tmp_full_c7` passed (46 passed), and
  `server\.venv\Scripts\python.exe -m server.tools.demo --duration 3
  --interval 1 --state-file server\.simulator_state.json` passed (3 sent,
  3 stored).
- Next: C8 WebSocket `telemetry.ack` so Claude Code can consume acks in
  iOS P5.3.

### 2026-07-06 - Claude Code — P5.1 verified green in CI; P5.2 underway

- iOS Agent run **28797905062 is green** with the P5.1 queue on board
  (7 TelemetryQueue tests incl. persistence-across-reopen pass on the
  simulator). The first P5.1 push (run 28797373858) failed: deferring the
  event-stream subscription into SyncManager's consume task raced events
  emitted right after startup on slow CI schedulers. Fixed in `a2e5b3c` —
  subscription now happens before `start()` returns; CI poll timeouts
  widened in two test files.
- **Codex: the Phase 5 queue is live — C7 → C8 → C9** per
  `docs/CODEX_ROADMAP.md`. C8 (WS `telemetry.ack`) blocks Claude P5.3,
  so prioritise it right after C7. The exact ack shape is pinned in the
  roadmap; don't improvise beyond it.
- Next (Claude Code): P5.2 — rework SyncManager onto the durable queue
  (queue-first pipeline, drain loop, `requeueInFlight()` on start/disconnect).

### 2026-07-06 - Claude Code — Phase 5 planned (execution next session)

- Deep-dive into spec 04 §22/§25/§26, 05 §30, 06 Phase 5 + past-steps
  analysis → wrote **`docs/PHASE5_PLAN.md`** (design decisions, both
  agents' roadmaps, sequencing, acceptance matrix).
- Key design: queue-first pipeline (persist before send), spec-exact
  `telemetry_queue` SQLite table via raw sqlite3 (no third-party deps),
  REST response as ack, new WS `telemetry.ack` for the WS path.
- Codex queue extended: **C8** (WS telemetry.ack contract extension —
  blocks Claude P5.3, do right after C7) and **C9** (offline chaos
  validation). Exact ack message shape is pinned in the roadmap.
- P5.1 implemented same session: `Persistence/SQLiteTelemetryStore.swift`
  (raw sqlite3 wrapper, WAL) + `Persistence/TelemetryQueue.swift` (actor:
  enqueue/nextBatch/markUploaded/markForRetry/markFailed/requeueInFlight/
  counts, caps 5000 pending / 200 failed, max 8 attempts) + 7 XCTests incl.
  persistence-across-reopen. NOTE deliberate spec drift: queue table adds
  `source`/`sequence` columns beyond 05 §30 — the envelope (05 §10) needs
  them for re-upload; consistency order favours the envelope.
- Next (Claude Code): P5.2 (SyncManager rework onto the queue) per
  `docs/PHASE5_PLAN.md`; verify P5.1 CI run first.

### 2026-07-06 - Claude Code (session 2, continued) — CI GREEN, .ipa ready

- iOS Agent workflow run 28795606748 is **green**: full Swift test suite
  passed on the iOS simulator; unsigned `.ipa` artifact published
  (SentinelXMobileAgent-unsigned-ipa, ~0.4 MB, 14-day retention).
- Three strict-SDK fixes were needed in pre-existing code (never compiled
  before this pipeline existed): explicit `Date.ISO8601FormatStyle`
  construction in JSONCoding, `NSLock.withLock` in async test mocks, and
  `UserDefaults` transfer-on-construction in ConfigurationServiceTests.
- Codex completed the entire C0–C5 roadmap this session; added C7
  (one-command demo & soak script) to the queue, C6 continues as ongoing.
- Next (Claude Code): Phase 5 (SQLite offline queue) once the iPhone
  sideload is confirmed working.

### 2026-07-06 - Claude Code (session 2, continued) — no-Mac build pipeline

- **There is no Mac in this project** (user is Windows-only, iPhone in
  hand). GitHub Actions is the Mac from now on:
  `.github/workflows/ios.yml` (repo root, outside the workspace — Claude
  Code lane only) runs on the free macos-15 runner: xcodegen → simulator
  unit tests → unsigned `.ipa` build artifact (14-day retention).
  Triggers: push/PR touching `Sentinelx_IOS/ios/**`, or manual dispatch.
- `docs/IPHONE_INSTALL.md` — how to sideload the CI-built .ipa onto the
  iPhone from Windows (Sideloadly/AltStore + free Apple ID, 7-day resign
  cycle) and point the phone at the dev server over LAN.
- SettingsView gained editable API/WS URL override fields (backed by the
  `AppEnvironment.DefaultsKey` UserDefaults overrides, applied on next
  launch) so a phone build can target the laptop without rebuilding.
- Corrected the Phase 4 note below: the Swift suite runs in CI, not on a
  local Mac.

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
  encoding contract. Runs in the iOS Agent GitHub Actions workflow (no
  local Mac in this project).
- Next (Claude Code): get the CI run green, then Phase 5 (SQLite offline
  queue); verify end-to-end on the physical iPhone against the dev server.

### 2026-07-06 - Codex

- Completed C5 dashboard query endpoint hardening (commit `aa7ac49`).
- Added coverage proving device summaries use the latest event per category,
  telemetry queries support category/time-window pagination filters, and
  unknown devices return standard 404 envelopes for detail, telemetry, and
  alert endpoints.
- No server contract drift found against docs/spec/03 and docs/spec/05 for the
  touched dashboard query behavior.
- Verification:
  `server\.venv\Scripts\python.exe -m pytest server\tests\test_devices.py
  -q --basetemp server\.pytest_tmp` passed (7 passed), and
  `server\.venv\Scripts\python.exe -m pytest server\tests -q --basetemp
  server\.pytest_tmp_full` passed (43 passed).
- Next: C0-C5 are complete. Keep C6 docs QA ongoing and wait for the next
  Claude/user handoff before starting work outside this roadmap.

### 2026-07-06 - Codex

- Completed C4 server-side alert engine (commit `6a73342`).
- Added alert rule evaluation on successful telemetry ingest for battery low/
  critical, thermal serious/critical, storage low, network loss, and dashboard
  offline checks.
- Alert creation dedupes unresolved device+rule pairs and resolves matching
  alerts when healthy telemetry arrives.
- WebSocket telemetry sends `alert.created` messages for newly created alerts.
- Added tests for fire/dedupe/resolve behavior, dashboard alert visibility,
  WebSocket alert push, network-loss resolution, and offline alert creation.
- Verification:
  `server\.venv\Scripts\python.exe -m pytest server\tests\test_alerts.py
  -q --basetemp server\.pytest_tmp` passed (4 passed), and
  `server\.venv\Scripts\python.exe -m pytest server\tests -q --basetemp
  server\.pytest_tmp_full` passed (41 passed).
- Next: mark C5 `IN PROGRESS - codex` and harden dashboard query endpoints.

### 2026-07-06 - Codex

- Completed C3 replay-window validation (commit `a25a48c`).
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
