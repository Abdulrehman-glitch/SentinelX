# Phase 5 Plan — Offline-First Queue

Prepared 2026-07-06 (Claude Code). Execution starts next session.
Spec anchors: `06_Implementation_Roadmap.md` Phase 5, `04_iOS_Architecture.md`
§22/§25/§26, `05_Data_Models.md` §30.

## 1. Where we are (past-steps analysis)

**Built and verified:**

| Layer | State |
|-------|-------|
| iOS Phases 1–3 | Auth, registration, telemetry framework, 5 collectors |
| iOS Phase 4 | `WebSocketClient` (first-msg auth, 30 s heartbeat, jittered reconnect) + `SyncManager` (WS primary, in-memory buffer → REST batch fallback) — CI green, .ipa artifact |
| Dev server | Full contract on port 8100: auth, idempotent ingest, WS, rate limits (C2), replay window (C3), alert engine (C4), dashboards (C5) — 45+ pytest green |
| Tooling | Device simulator CLI (C1), payload generators (C0), GitHub Actions macOS CI (build + test + unsigned .ipa) |

**What worked — keep doing:**
- Contract-first: the dev server as executable spec caught the batch
  `device_id` mismatch before any device testing.
- File-based two-agent coordination (STATUS.md / roadmap): Codex ran the
  entire C0–C5 queue in one session with zero collisions after lanes were
  split explicitly.
- CI-as-Mac: 4 fix rounds, all failures in code that had never been
  compiled. Lesson: **push early, compile early** — new Swift goes to CI
  the same session it's written.

**Weaknesses Phase 5 must fix:**
1. `SyncManager`'s buffer is in-memory: events die with the process, and
   only *failed* WS sends are buffered at all.
2. No delivery acknowledgement on the WS path — a socket write that
   "succeeds" can still be lost on a dying connection. Spec 04 §25 demands
   *delete only after acknowledgement*; today the WS path can't satisfy it.
3. `RetryPolicy.upload` exists but is unused — flush cadence is the only
   retry mechanism; there's no per-event retry counting or failure record.
4. No queue visibility for the user (spec Phase 5 requires an inspection
   screen).

**Process lessons applied below:** single-writer file sections (concurrent
STATUS.md edits caused two rebase-reads this session); every new Swift file
lands with its CI run in the same work block.

## 2. Design decisions

- **Storage:** raw `sqlite3` C API wrapped in a small `SQLiteStore` class
  (the project has zero third-party dependencies; GRDB/SwiftData would be
  the first — not worth it for one table). Schema **exactly** spec 05 §30
  `telemetry_queue`, WAL mode, file in Application Support.
- **Queue-first pipeline:** every event accepted by `TelemetryManager` is
  persisted `pending` *before* any network attempt (replaces "buffer only
  on WS failure"). Uploaders drain the queue; nothing is sent that isn't
  durable first.
- **Delivery semantics:**
  - REST batch: server response *is* the ack → `uploaded` (delete), rejected
    events → `failed` + `last_error`.
  - WS: needs a new `telemetry.ack` server message (Codex C8, contract
    extension to spec 03 §17). Until C8 is consumed on-device, WS-path
    events stay `in_flight` after send and are re-marked `pending` on
    reconnect — the server's event_id idempotency makes re-sends safe, so
    at-least-once holds even before the ack lands.
- **Retry:** `RetryPolicy.upload` per drain attempt; `retry_count`
  incremented per event batch failure; events exceeding max attempts →
  `failed` (kept for inspection, not retried automatically).
- **Cleanup:** `uploaded` rows deleted immediately; `pending` capped at
  5 000 (FIFO prune, count as dropped); `failed` capped at 200.
- **Out of scope for Phase 5:** BackgroundTasks/background flush (spec 04
  §26 — its own phase), motion/location collectors (Phase 6).

## 3. Claude Code roadmap (owner: `ios/`)

Work top to bottom; each step compiles green in CI before the next starts.

- **P5.1 — SQLiteStore + TelemetryQueue actor.** `Persistence/SQLiteStore.swift`
  (open/migrate/exec, WAL) and `Persistence/TelemetryQueue.swift` implementing
  spec 05 §30: `enqueue`, `nextBatch(limit:)` (FIFO, marks `in_flight`),
  `markUploaded(ids:)` (deletes), `markFailed(ids:reason:)`,
  `requeueInFlight()`, `counts()`, prune caps. Unit tests incl. reopen-the-
  file persistence and event_id uniqueness. *(largest step)*
- **P5.2 — SyncManager on the queue.** Replace the in-memory buffer:
  emit → enqueue; drain loop = WS single events when connected (→ `in_flight`),
  REST batches otherwise (response → uploaded/failed); `requeueInFlight()`
  on start and on WS disconnect; `RetryPolicy.upload` between failed drains.
  Existing Phase 4 tests updated; airplane-mode test: stream+REST both down
  → events persist across a simulated relaunch (new queue instance, same
  file) → recovery drains exactly once.
- **P5.3 — Consume `telemetry.ack`** (after Codex C8 lands): WS-path events
  `in_flight` → deleted on ack; `WSServerMessage` gains the case; SyncManager
  subscribes via `serverMessages()`. Behind a config flag until verified.
- **P5.4 — Queue inspection screen.** New "Queue" section (Settings tab or
  Status screen): pending/in-flight/failed counts, oldest pending age, last
  error, `Flush now` button, `Clear failed` (confirm dialog). ViewModel +
  snapshot polling, matching existing SwiftUI patterns.
- **P5.5 — CI + device pass.** Full suite green; sideload build; airplane-
  mode acceptance on the physical iPhone against the dev server
  (toggle Wi-Fi, kill app, relaunch, verify server totals — no loss, no
  dupes via dashboard counts).
- **P5.6 — Docs.** STATUS.md worklog, spec drift check, memory update,
  `feat: offline queue` conventional commit series.

## 4. Codex roadmap (owner: `server/` — tasks C8/C9 in CODEX_ROADMAP.md)

- **C8 — WS `telemetry.ack` (do first, blocks P5.3).** After ingesting
  `telemetry.event` / `telemetry.batch`, server sends
  `{"type": "telemetry.ack", "event_ids": [...], "server_time": ...}`
  (duplicates acked too — idempotency means they're durably stored).
  Update spec 03 §17 message table in the same commit (AGENTS rule 5) +
  contract tests + simulator support.
- **C9 — Offline chaos validation (after C7 + C8).** Extend simulator/demo
  with `--offline-window` connectivity gaps; assert via dashboard endpoints:
  stored events == unique sent events (no loss, no dupes) across ≥3 chaos
  cycles. This is the server-side mirror of the airplane-mode acceptance.
- **C6 (ongoing)** — after C8, cross-check spec 03/05 vs both sides;
  drift findings → `docs/DRIFT_REPORT.md`.

## 5. Sequencing

```
Codex:  C7 (demo script) → C8 (WS ack) ──────→ C9 (chaos validation)
Claude: P5.1 (queue) → P5.2 (sync rework) → P5.3 (consume ack) → P5.4 (UI)
                                                     ↑ needs C8
        → P5.5 (CI + iPhone pass) → P5.6 (docs)
```
P5.1/P5.2 don't depend on Codex — both agents start immediately next
session. Cross-lane contract: C8's exact message shape is specified above
and in the roadmap; neither side improvises beyond it.

## 6. Acceptance (spec 06 Phase 5)

| Criterion | Verified by |
|-----------|-------------|
| Airplane-mode test passes | P5.2 simulated-relaunch test (CI) + P5.5 physical iPhone |
| Events upload after reconnect | P5.2 recovery test + C9 chaos run |
| Duplicate prevention | event_id UNIQUE in queue + server idempotency + C9 dashboard totals |
| Queue inspection screen | P5.4 |
