# Sprint evidence — Industrial baseline (v3.2)

**Date:** 2026-08-21
**Branch:** `sprint/industrial-baseline-v3.2`
**Baseline commit:** `b72852b` (main — "docs: record merge, post-merge CI and the published GHCR image digest")

Goal: raise the v3.1 foundation to an industry-grade engineering baseline before
the observability data-plane work, without creating any billable usage.

---

## 1. Cost and external-service boundary

Verified against **current official GitHub documentation**, not repository
comments:

| Claim | Source | Verdict |
|---|---|---|
| Actions free for public repos on standard runners | Billing → About billing for GitHub Actions | Confirmed |
| `macos-15` is a **standard** runner (3-core M1) | Actions → Reference → GitHub-hosted runners | Confirmed — only *larger* runners are billed for public repos |
| Artifact retention range for public repos | Repo settings → Managing GitHub Actions settings | 1–90 days, minimum 1, **not retroactive** |
| Cache is a separate allowance | Billing docs | 10 GB per repository, not the billed artifact storage |
| Public packages are free | Billing → About billing for GitHub Packages | "GitHub Packages usage is free for public packages" |

**Read-only usage audit of this repository:**

| Source | Live size | Note |
|---|---|---|
| Actions artifacts — 4 `.dockerbuild` build records | ~202 KB | produced by `docker/build-push-action`'s **default** record upload |
| Actions artifacts — 8 unsigned `.ipa` (14-day retention) | ~3.4 MB | all expired at audit time; recurring |
| Actions caches — 4 CodeQL overlay databases | 72 MB | free allowance, not billed |
| GHCR `sentinelx-api` | not enumerable (token lacks `read:packages`) | package is **public** — anonymous `ghcr.io/v2/.../tags/list` returned HTTP 200, so unmetered |

Conclusion: this repository was **not** the main consumer of the exhausted
account quota, but it was adding to it on every push for no benefit while
hosting is paused.

**Nothing billable was created during this sprint.** No cloud resource, no
larger runner, no paid service, no scheduled job, no deployment.

---

## 2. Architecture changes

| Area | Before | After |
|---|---|---|
| Browser auth | 24-hour bearer JWT in `localStorage` | 15-min in-memory access token + rotating HttpOnly refresh cookie + server-side `user_sessions` (ADR 0001) |
| Logout | Audit-log only; token kept working | Revokes the session; token dies on next request |
| Revocation | None | `logout`, `logout-all`, deactivation, refresh-replay — all immediate |
| JWT validation | Signature + expiry | + `iss`, `aud`, `typ`, `jti`, `nbf`, and `require` so missing claims fail |
| CSRF | N/A | Signed double-submit derived from the session (defeats a cookie-writing attacker) |
| Recovery params | Unvalidated into the signed payload | Per-action server-side schemas; unknown keys rejected |
| Tenant isolation | App-layer, thinly tested | App-layer + 25 systematic tests; RLS deferred with reasons (ADR 0002) |
| Command state machine | `rejected` only from `running` | Also from `dispatched`/`acknowledged`, so a pre-execution refusal is auditable |
| Security headers | 4 headers | + CSP, COOP, CORP (Swagger-aware) |

---

## 3. Tests run — exact counts

All run locally on this machine before pushing.

| Suite | Command | Result |
|---|---|---|
| Backend | `pytest ../tests/backend` | **218 passed** |
| Contract | `pytest ../tests/contract` | **34 passed** |
| Integration | `pytest ../tests/integration` | **10 passed** |
| Backend + contract + integration | one invocation | **262 passed**, 0 failed |
| Frontend | `npm test` (Vitest) | **63 passed** (5 files) |
| Frontend lint | `npm run lint` | clean |
| Frontend type-check + build | `npm run build` | clean |
| Desktop agent | `pytest tests/` | **29 passed** |
| **Total** | | **354 passed, 0 failed** |

Baseline before the sprint was 137 backend tests and 0 frontend tests.

Not run locally, with reasons:
- `tests/e2e/` (17 scenarios) — requires a live staging backend; hosting is paused.
- `tests/load/locustfile.py` — a load harness, not a pytest suite.
- Android `gradle testDebugUnitTest` — no Gradle on PATH on this machine; CI runs it.
- iOS `xcodebuild test` — no Mac; CI runs it on a free standard macOS runner.

---

## 4. Dependency and security audit

| Ecosystem | Tool | Result |
|---|---|---|
| Backend Python | `pip-audit` | **No known vulnerabilities** |
| Frontend npm (prod + dev) | `npm audit` | **0 vulnerabilities** |
| Desktop agent Python | `pip-audit` | 4 findings → **fixed**, now clean |
| Embedded bridge Python | `pip-audit -r` | **No known vulnerabilities** |
| Android/Gradle | OSV batch query | 2 BouncyCastle advisories → **fixed**; okhttp/retrofit/room/security-crypto clean |
| iOS/Swift | `project.yml` inspection | **No external SPM dependencies** — nothing to audit |
| Docker base | `python:3.12-slim` | Trivy HIGH/CRITICAL scan runs on every backend change and fails the build |
| GitHub Actions | manual review | All actions on current major versions |
| Expo | `npm audit` | **20 advisories (11 high, 9 moderate)** → component retired (ADR 0005) |

### Changes made

- `agents/desktop-python/requirements.txt`: `cryptography 49.0.0 → 50.0.0`
  (PYSEC-2026-3552). This is the Ed25519 verification path — worth doing
  properly. Desktop tests re-run: 29 passed.
- `agents/desktop-python/requirements-dev.txt`: `pytest 8.3.4 → 9.1.1`
  (PYSEC-2026-1845), matching the backend's pin.
- The desktop venv also reported `cryptography 44.0.0` and stale `pip`. That
  was a **stale local virtualenv**, not the declared pin — `requirements.txt`
  already said 49.0.0. Venv resynced so local runs match CI.
- `agents/android-native/.../libs.versions.toml`: `bouncyCastle 1.79 → 1.84`
  (GHSA-574f-3g2m-x479, GHSA-c3fc-8qff-9hwx). Neither advisory is reachable —
  the app uses BouncyCastle solely for Ed25519 verification, no GOST, no LDAP,
  no CRL — but it is a one-line change and `CommandSigningVerifierTest` covers
  the only surface that could regress.

### Deliberately NOT upgraded

The rest of the Android catalog (AGP 8.7.3, Kotlin 2.1.0, Compose BOM
2024.12.01, Room 2.6.1, WorkManager 2.10.0) is dated but carries **no known
advisories**. Upgrading a Kotlin/AGP/Compose stack that cannot be built on this
machine would be changing code nobody can verify. Left for a sprint that can
run the Android build.

---

## 5. CI workflow changes and storage protection

| Workflow | Change |
|---|---|
| `pages.yml` | **Deleted** — uploaded ~7.5 MB per frontend push, duplicated `frontend.yml` |
| `docker.yml` | `load: true` instead of push; GHCR login, `packages: write` and push removed; `DOCKER_BUILD_RECORD_UPLOAD: false` (the default that produced every `.dockerbuild` artifact). Smoke test and Trivy scan unchanged |
| `container-publish.yml` | **New** — the only publisher. `workflow_dispatch` only, plus a typed `publish` confirmation re-checked as a job `if:` |
| `ios.yml` | Simulator tests **and** the Release/iphoneos device build kept; only `.ipa` packaging/upload moved behind a manual input, at `retention-days: 1` |
| `backend.yml` | Now runs backend + contract + integration in one invocation; watches `tests/**` |
| `frontend.yml` | Now runs `npm test` between lint and build |

**Net effect:** exactly one `upload-artifact` step remains in the repository,
and it is unreachable from `push` or `pull_request`. Routine SentinelX CI can
no longer increase artifact-storage pressure at all.

---

## 6. Components retired

| Component | Reason |
|---|---|
| `agents/mobile-expo/` | Third mobile stack duplicating two shipped native agents; boilerplate README; no tests, no CI, no functional commits; 20 npm advisories, 882 lockfile packages (ADR 0005) |
| Auth0 scaffold (`@auth0/auth0-react`, provider, callback page, config, route, button, 2 env vars) | Never wired to anything; carrying a second auth direction through an auth rewrite is how the wrong one gets used (ADR 0005) |
| `.github/workflows/pages.yml` | Artifact cost with no publishing benefit (ADR 0004) |
| `scripts/azure_teardown.ps1` | Unreferenced; nothing left to tear down (ADR 0003) |

---

## 7. Defects found and fixed along the way

1. **Agent could not report a pre-execution refusal.** `rejected` was only
   reachable from `running`, so an agent failing a local signature check had to
   claim it had started running or stay silent — and silence is
   indistinguishable from an offline agent.
2. **Login page white-screened without WebGL.** `LineWaves` threw while
   constructing its `ogl` renderer; unguarded, on the one route every user must
   reach. Now degrades to no background.
3. **Password toggle had no accessible name** and was removed from the tab
   order (`tabIndex={-1}`). Found by axe. Now labelled and reachable.
4. **A test helper silently inverted its own tests.** `jsonResponse(body, 401)`
   was parsed as an options object, produced a 200, and turned error-path
   assertions into happy-path assertions that still passed.

---

## 8. Residual risks

| # | Risk | Assessment |
|---|---|---|
| 1 | **Repository-wide artifact retention is still 90 days** | No REST endpoint exists for it; owner-only UI action. Impact is low now that only one manual workflow uploads anything, and that one is pinned to 1 day. |
| 2 | **Historical artifacts are not deleted** | Deliberately not touched — deleting remote data is the owner's call. Almost all are already expired. |
| 3 | **Android dependency stack is dated** | No known advisories, but unverifiable locally. Needs a sprint with a working Gradle toolchain. |
| 4 | **No RLS** | Deferred with reasons in ADR 0002; compensated by 25 isolation tests. Revisit if a second database consumer appears. |
| 5 | **No browser-level E2E** | Deferred with reasons in ADR 0006. The listed journeys are covered in jsdom against the real API client. |
| 6 | **HttpOnly enforcement is asserted server-side only** | jsdom's cookie jar does not enforce `HttpOnly`, so "JavaScript cannot read the refresh token" is proven by the `Set-Cookie` attributes, not by a browser. |
| 7 | **Accessibility is machine-checked only** | axe finds a real class of defect and found one here, but no manual assistive-technology testing has been done. |
| 8 | **iOS is still not a client of `/api/v1`** | Unchanged by this sprint. The refresh flow it expected now exists, but its endpoint shapes still differ. |
| 9 | **Access-token claims are up to 15 minutes stale** | A role change takes effect on the next refresh. Deliberate trade; `logout-all` is the immediate lever. |

---

## 9. Deferred to the next sprint — Observability Data Plane

Directly relevant handover:

- `tests/contract/` is the place to pin any new ingestion contract **before**
  agents encode it. The batch limit (500) and `event_id` idempotency are
  already pinned there.
- `services/session_service.purge_expired_sessions()` exists and is wired to
  nothing. The retention prune job should call it.
- Feature-window construction and the hybrid pipeline currently re-read raw
  `system_metrics` on every run; that is the hot path the data-plane work will
  need to address.
- `tests/integration/` already asserts that the observability pipeline creates
  no `Alert`/`Incident`/`RecoveryCommand`. Keep that assertion as the pipeline
  grows — it is the product guarantee.
