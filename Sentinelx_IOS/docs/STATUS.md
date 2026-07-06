# SentinelX Mobile Agent Status

This file is the shared coordination log for Claude Code and Codex.

## Current Phase

- Branch: `feature/ios-mobile-agent`
- Claude Code lane: `ios/` + dev server scaffold in `server/app/`
- Codex lane: `server/tools/` + `server/tests/` tasks from `docs/CODEX_ROADMAP.md`
- Dev server: IN PROGRESS — Claude Code (2026-07-06 session)
- **Codex: start C0 now** — it has no dev-server precondition (see roadmap)

## Agent Memory

### Codex

- Read `AGENTS.md` and every file under `docs/`.
- Must not edit outside `Sentinelx_IOS/`.
- Must not modify `ios/` unless a reproduced Mac compile/test issue requires it.
- Roadmap C1–C5 blocked until this file records `Dev server: done`.
- **C0 (simulator payload generators) is unblocked — work only in
  `server/tools/` and `server/tests/`, never `server/app/`, which Claude
  Code is editing concurrently this session.**

### Claude Code

- Owns `server/app/` (FastAPI dev server) until handoff; scaffold from the
  2026-07-05 night session: `config.py`, `database.py` (full spec §31 SQLite
  schema), `errors.py` (spec §5 envelope), `timeutil.py`.
- Remaining for handoff: pydantic models, auth (register/login/refresh,
  JWT), telemetry ingest (single + batch, idempotent), config endpoint,
  WebSocket (first-message auth, heartbeat, telemetry), dashboard queries,
  contract tests, `server/README.md`, venv verified green.

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
- Next: finish dev server app + contract tests, verify venv green, then
  record `Dev server: done` here.

### 2026-07-06 - Codex

- Read `AGENTS.md` and all documentation under `docs/`, including `CODEX_ROADMAP.md` and `docs/spec/00` through `10`.
- Verified current branch is `feature/ios-mobile-agent`.
- Confirmed `docs/STATUS.md` and `docs/DECISIONS.md` were missing before this entry.
- Inspected `server/`; found only a partial untracked scaffold (`app/config.py`, `app/errors.py`, `app/timeutil.py`, `requirements.txt`, `.gitignore`).
- Did not start C1 because `docs/CODEX_ROADMAP.md` requires a documented `Dev server: done` handoff before any server task.
- Next: wait for Claude Code to complete and record the dev server handoff, then mark C1 `IN PROGRESS - codex` and implement `server/tools/device_simulator.py`.
