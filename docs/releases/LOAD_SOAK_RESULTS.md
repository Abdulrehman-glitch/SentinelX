# Load/Soak Test Results (Sprint 7 Phase 7)

Run against the native staging stack only (`docs/releases/STAGING.md`,
`http://127.0.0.1:8200`) — never `sentinelx_dev` or production. Tooling:
`tests/load/locustfile.py` (Locust), simulating two realistic traffic
patterns — enrolled agents posting telemetry, and human operators browsing
the dashboard.

## A real bug found and fixed

The first load burst (20 users, spawn rate 3/s, 45s) surfaced a genuine,
previously-undetected bug: **every actual rate-limit trip crashed with a
500 Internal Server Error instead of returning 429**. 8 of 23 `/auth/login`
attempts failed this way once concurrent logins exceeded
`rate_limit_login` (15/minute).

Root cause: `slowapi`'s real `_rate_limit_exceeded_handler` is a
**synchronous** function returning a `JSONResponse` directly; `main.py`'s
`rate_limit_handler` unconditionally `await`ed it — which only worked by
accident against the "slowapi not installed" fallback stub (which *is*
async), and raised `TypeError: object JSONResponse can't be used in
'await' expression` against the real one. This had never been caught
before because the entire pytest suite runs with the rate limiter disabled
(`conftest.py`'s autouse `_no_rate_limit` fixture) — nothing exercised a
real rate-limit trip end-to-end until this load test did.

**Impact if shipped**: rate limiting — the exact mechanism meant to absorb
brute-force login attempts or API abuse — would itself crash under the
load it's designed to handle, turning a defensive control into an
availability bug.

**Fix**: `main.py` now checks `inspect.isawaitable()` on the handler's
return value before awaiting it, so it works correctly whether the real
(sync) or fallback (async) handler is active. Verified directly (`curl`
loop past the login limit → clean `429`s, no more `500`s) and via a new
regression test, `tests/backend/test_rate_limit_handler.py` (re-enables
the limiter, confirms a real trip returns 429, restores it after — since
nothing else in the suite ever exercises this path). Full suite: 118/118
green afterward.

## Load run (post-fix)

8 users, spawn rate 1/s, 45s. Mixed agent (telemetry) + dashboard traffic.

| Endpoint | Requests | Failures | Median | Max |
|---|---|---|---|---|
| `POST /metrics` | 49 | 0 | 73ms | 155ms |
| `GET /devices` | 16 | 0 | 8ms | 10ms |
| `GET /alerts` | 8 | 0 | 7ms | 9ms |
| `POST /devices/enroll` | 4 | 0 | 130ms | 145ms |
| `POST /auth/login` | 8 | 0 | ~68ms | 81ms |

96 total requests, **0 failures**. Raw CSV:
`docs/Evidence/sprint7_production_release/07_staging_and_e2e/load_soak/load_run_stats.csv`.

## Soak run (post-fix)

5 users, spawn rate 1/s, 150s (2.5 minutes) — checking for degradation or
instability over a longer window, not just a burst.

122 total requests, **0 failures**, response times stable throughout (no
upward trend — `/metrics` median 71ms at the end vs. 73ms in the load run
above; one outlier at 293ms, isolated, not a trend). Raw CSV:
`docs/Evidence/sprint7_production_release/07_staging_and_e2e/load_soak/soak_run_stats.csv`.

## Scope note

This is a single-process `uvicorn` dev server on a laptop, not a
production-topology multi-worker deployment — these numbers characterize
the application code path (query plans, middleware overhead, connection
handling), not the eventual Azure App Service F1 tier's real capacity
(which is separately constrained by its CPU quota — the reason load
testing never targets production directly, per the Phase 7 roadmap
decision).
