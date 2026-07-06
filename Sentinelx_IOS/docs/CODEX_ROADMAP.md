# Codex Roadmap — SentinelX Mobile Agent

Task queue for the Codex agent, assigned by Claude Code (architecture owner).
Read `AGENTS.md` in the workspace root first — the hard rules there apply to
every task below. Work top to bottom; each task should end in its own
conventional commit with passing tests.

**Precondition for tasks C1–C5:** the dev server scaffold in `server/app/`
(FastAPI app + SQLite storage + pytest contract tests) must exist. Claude
Code builds it — check `docs/STATUS.md` for "Dev server: done". If it is not
done yet, do C0 (no precondition), then stop and report instead of
scaffolding your own. **C0 has no precondition — start it immediately.**

Legend: `[AC]` = acceptance criteria. A task is done only when all AC pass
locally via `server\.venv\Scripts\python.exe -m pytest server/tests -q`.

---

## C0 — Simulator payload generators (DONE — commit 63c0b5c)

Pure-Python groundwork for C1 that does not touch `server/app/` (Claude
Code is building that concurrently — do not create or edit anything under
`server/app/`).

1. If `server/.venv` is missing, create it with
   `C:\Python314\python.exe -m venv server\.venv` and install
   `server/requirements.txt` into it.
2. Build `server/tools/simulator_payloads.py`: generator functions that
   produce plausible, spec-exact telemetry for the five core categories —
   battery (drain/charge curves, low-power flag), thermal (nominal→fair→
   serious→critical walks), network (wifi/cellular flaps, reachable flag),
   storage (slow drift, free ≤ total), device (snapshot). Payload fields,
   enums, and casing must match `docs/spec/05_Data_Models.md` §13–17
   exactly; envelope fields (event_id UUID, ISO 8601 UTC Z timestamps,
   category/type/source) per §10.
3. Include a `make_event(category, device_id, sequence)` helper returning a
   full envelope dict, and a deterministic mode (seeded RNG) for tests.
4. Tests in `server/tests/test_simulator_payloads.py` — must run standalone
   (no imports from `server/app/`), via
   `server\.venv\Scripts\python.exe -m pytest server/tests/test_simulator_payloads.py -q`.
5. Create `docs/DECISIONS.md` (ADR log, template header + ADR-001 recording
   any non-trivial choice you made here, e.g. RNG model or curve shapes).

[AC] Generators emit valid envelopes for ≥5 categories; enum/range rules
from spec 05 §34 hold under a 1000-iteration property-style test.
[AC] Deterministic with a fixed seed.
[AC] No file under `server/app/` created or modified.

## C1 — Device simulator CLI (highest value)

Build `server/tools/device_simulator.py`: a CLI that impersonates an iPhone
running the agent, end to end, against the dev server (later the real
backend). This is how we demo and load-test without a physical phone.

Behaviour:
- `--register` registers a device (persists `device_id`/`device_secret` to a
  local JSON state file, default `.simulator_state.json`, gitignored).
- Default run: login → open WebSocket `/api/v1/mobile/ws/{device_id}` →
  first-message auth → heartbeat every 30s → stream plausible battery /
  thermal / network / storage / device events on the spec intervals.
- `--rest-only` uses `POST /telemetry` + `/batch` instead of the WS.
- `--burst N` sends N events as one batch (tests idempotency + rate limits).
- `--chaos` randomly drops the WS to exercise reconnect/fallback logic.
- Payloads must match `docs/spec/05_Data_Models.md` §13–17 exactly
  (snake_case, valid enums, event_id UUID, ISO 8601 UTC timestamps) —
  reuse the C0 generators in `server/tools/simulator_payloads.py`.

[AC] Simulator can register, login, stream ≥5 categories over WS, and the
events land in the server DB (verify via dashboard endpoints).
[AC] `--rest-only` and `--burst` paths store events exactly once
(idempotent by event_id).
[AC] README section in `server/README.md` documenting usage.

## C2 — Rate limiting per contract §22

Implement the limits from `docs/spec/03_Backend_API.md` §22 on the dev
server (in-memory limiter is fine; structure it so the real backend can swap
in SlowAPI): register 10/min/IP, login 20/min/device, telemetry 120/min/
device, batch 30/min/device, WS messages 1200/min/device.

[AC] Exceeding a limit returns 429 with the standard error envelope
including `details.retry_after_seconds`.
[AC] Tests cover at least register, telemetry, and WS message limits.

## C3 — Replay-window validation

Reject telemetry with timestamps outside a configurable window (default:
older than 24h or more than 5 min in the future). Per-event rejection in
batches (envelope `rejected_events`), not whole-batch failure.

[AC] Stale/future events rejected with reason strings; fresh events in the
same batch still accepted; tests prove both.

## C4 — Server-side alert engine (spec Phase 10, brought forward)

Evaluate rules on ingest: `BATTERY_LOW` (<20%, warning), `BATTERY_CRITICAL`
(<10%, critical), `THERMAL_SERIOUS`/`THERMAL_CRITICAL`, `STORAGE_LOW`
(<10% free), `DEVICE_OFFLINE` (no heartbeat/event for 5 min — periodic
check), `NETWORK_LOSS` (reachable=false). Alerts stored in `mobile_alerts`,
deduplicated (no duplicate unresolved alert for same device+rule),
auto-resolved when the condition clears, and pushed as `alert.created` over
the device's WS connection.

[AC] Tests: rule fires once, dedupes, resolves, and appears in
`GET /devices/{id}/alerts`.

## C5 — Dashboard query endpoints hardening

Flesh out `GET /api/v1/mobile/devices`, `/devices/{device_id}`,
`/devices/{device_id}/telemetry` (filters: `category`, `from`, `to`,
`limit`, `page`), `/devices/{device_id}/alerts`. Summaries must include
latest battery/thermal/network snapshot values as in spec §21/§33.

[AC] Pagination + filter tests; summary reflects the latest event per
category; unknown device returns the standard 404 envelope.

## C6 — Continuous docs QA (ongoing)

After each task: cross-check anything you touched against
`docs/spec/03/05`; if Swift models in `ios/` have drifted from the spec or
your server behaviour, do NOT edit Swift — write findings to
`docs/DRIFT_REPORT.md` (create if missing) for Claude Code to resolve.

---

## Out of scope for Codex (do not start)

- Anything in `ios/` (Swift) — Claude Code's lane.
- React dashboard pages in `frontend/` — outside the workspace, frozen.
- Merging `server/` code into the real `backend/` — integration phase,
  user-approved only.
- CI workflows (`.github/`) — outside the workspace.

## Coordination protocol

- Before starting a task, mark it `IN PROGRESS — codex` here; when done,
  mark it `DONE (commit <sha>)` and log it in `docs/STATUS.md`.
- One task = one commit (plus follow-up fix commits if tests catch issues).
- If a task conflicts with the spec or existing code, stop and write the
  conflict into `docs/DRIFT_REPORT.md` rather than improvising.

Status: C0 done (commit 63c0b5c). Dev server handoff is DONE (2026-07-06) —
C1–C5 are unblocked; continue top to bottom with C1.
