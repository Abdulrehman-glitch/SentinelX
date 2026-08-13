# SentinelX — Production Readiness Audit

**Date:** 13 August 2026
**Scope:** full-repository audit for public open-source release and public-internet deployment
**Deployment performed:** none. No cloud resource was created, modified or destroyed.

> **PROMOTIONAL, STUDENT AND TRIAL CREDITS ARE COUNTED AS £0 THROUGHOUT.**
> Every affordability statement below refers only to permanent, always-free allowances.

---

## A. Executive verdict

### `NO-GO — BLOCKING ISSUES REMAIN`

Two blockers remain, and neither can be closed by me:

| # | Blocker | Why it blocks | Owner action |
|---|---------|---------------|--------------|
| **B-1** | A real local PostgreSQL password is committed in reachable Git history (introduced in `e8ce6b1` "SentinelX v0.8", still present at `6928148`). | The repository is public. Removing it from the working tree — which I did — does not unpublish it. Anyone can recover it with `git log -p`. | Rotate the `sentinelx_app` Postgres role password on every machine that uses it, then decide whether to rewrite history (§F). |
| **B-2** | No `LICENSE` file exists. | Without a licence the project is "all rights reserved" by default. It cannot legitimately be called open source, and nobody may legally use or contribute to it. | Choose a licence (MIT or Apache-2.0). This is a legal decision with lasting consequences, so I deliberately have not chosen one for you. |

Everything else found has been fixed and tested, or is documented as non-blocking. **Once B-1 and B-2 are closed the verdict becomes `GO WITH NON-BLOCKING ISSUES`** — the remainder are quality and coverage gaps, not safety gaps.

Stated plainly: the application's own security engineering is genuinely strong. A sweep of all 95 API routes found **zero broken access control**, and the recovery-command pipeline — the highest-risk subsystem — is well designed and I could not find a way to subvert it.

---

## B. Repository baseline

| Item | Value |
|---|---|
| Repository root | `C:\SentinelX` |
| Remote | `https://github.com/Abdulrehman-glitch/SentinelX.git` (public) |
| Starting branch | `main` |
| **Starting commit** | **`cbc0eca2749d5e1315692cac4366f83b39f7270a`** |
| Audit branch | `audit/production-readiness-2026-08-13` |
| **Final commit** | **`abf02a6e996dc90899509a277b90ab57266103e3`** |
| Working tree at start | Clean except one untracked file, `AT3_Vohra_Abdulrehman_B00968573.zip` (left untouched) |
| Working tree at end | Clean; all changes committed to the audit branch |
| Tags | `android-v1.2.0`, `android-v1.2.1`, `android-v2.0.0` |
| History rewritten | **No.** Nothing was force-pushed, reset or deleted. Nothing was pushed at all. |

`main` is untouched and still points at `cbc0eca`. See §O for rollback.

---

## C. Architecture discovered

Verified by reading code, not the README. The documented architecture is accurate with one significant exception (iOS, §D).

```
                       ┌──────────────────────────────┐
 Desktop agent  ──────▶│                              │
 (Python/psutil)       │   FastAPI  /api/v1           │──▶ PostgreSQL
 Android agent  ──────▶│   95 routes, 23 modules      │    (SQLAlchemy 2, sync,
 (Kotlin/Compose)      │   JWT users + device tokens  │     psycopg3, UUID PKs)
 Arduino bridge ──────▶│                              │
                       └──────────────────────────────┘
 React dashboard ─────────────▶ same API
 iOS app ─────────▶ a DIFFERENT API (agents/ios-native/server, port 8100)
```

- **Backend** — FastAPI 0.139, SQLAlchemy 2 (sync), psycopg3, Pydantic v2. 95 route handlers across 23 modules under `/api/v1`. No Alembic; schema via `create_all` plus hand-written idempotent SQL in `migrations/` applied by `app.db.apply_migrations`.
- **Auth** — JWT HS256 via PyJWT, 24h expiry, stateless (no blacklist; `is_active` is the only revocation). Passwords argon2 via pwdlib. Agents use separate opaque Bearer tokens, argon2-hashed, v2 format `sxa_<credential-uuid>.<secret>` giving O(1) lookup.
- **RBAC** — 6 roles with a numeric hierarchy in `api/deps.py`; `platform_admin` bypasses all checks. Multi-tenant: every record organization-scoped.
- **Alert pipeline** — agent → `/metrics` or `/metrics/batch` → configurable `AlertRule` rows → fallback hardcoded thresholds → critical alerts auto-create an `Incident`.
- **AI observability** — shadow mode only; statistical baseline + IsolationForest, never auto-acts.
- **Recovery orchestration** — Ed25519-signed commands, deterministic policy engine, agent-side allowlist. Analysed in §E.
- **Background workers** — **none.** Every pipeline (`/observability/pipeline/run`, `/hybrid/decisions/run`, `/replay/run`) is request-triggered. A real advantage for serverless hosting: nothing needs an always-on instance.
- **WebSockets/SSE** — none in the main backend (only in the separate iOS dev server). Also good for Cloud Run.
- **Logging** — structured JSON with a per-request correlation ID (`X-Request-ID`, accepted from the client or generated), plus access logging.

---

## D. Client status

| Client | Verdict | Notes |
|---|---|---|
| **Backend** | ✅ **Production-capable** | 129 tests pass. No broken access control across all 95 routes. Needs the container and config in §L. |
| **Web dashboard** | ✅ **Production-capable** | Builds clean, lints clean, 0 npm vulnerabilities, route-level code splitting. Now GitHub Pages-ready (base path + router basename + 404 fallback added). |
| **Windows/Desktop agent** | ✅ **Production-capable** | 29 tests pass. Genuinely well-built: OS keyring for the token, persist-first SQLite queue, per-row exponential backoff, signature verification, nonce replay protection, durable idempotency. |
| **Android** | ✅ **Production-capable** | Strong posture: `EncryptedSharedPreferences` (Keystore AES256-GCM), `allowBackup="false"`, only `MainActivity` exported, minimal permissions, R8 minify + resource shrink, HTTPS enforced in release (explicit `http://` rejected), no hardcoded URL or secret, no TLS-verification bypass. Signing keys via `keystore.properties`/env, never committed. 4 unit tests. |
| **iOS** | ⚠️ **Functional prototype — NOT a client of this product's API** | See below. |

### iOS — honest assessment

The iOS work is substantial and well-organised (85 Swift files, 17 test files, mocked transport/keychain/websocket). It is not abandoned or fake. **But it does not talk to SentinelX.**

`agents/ios-native/ios/.../Networking/APIEndpoint.swift` defines exactly six endpoints:

```
register · login · token/refresh · profile · batch · config
```

None exist in the production backend, whose contract is `/auth/login`, `/auth/signup`, `/devices/enroll`, `/metrics/batch`, `/heartbeats`, `/agent/commands/next`. The iOS app targets its own FastAPI + SQLite dev server in `agents/ios-native/server/` on port 8100 — including a `token/refresh` endpoint the production backend does not implement at all.

| Component | Status |
|---|---|
| SwiftUI app, collectors, models, queue | Functional but incomplete (wrong backend) |
| Networking layer, Keychain token store | Functional but incomplete (wrong contract) |
| Mobile dev server (`server/`) | Prototype — a scaffold, not the product |
| Enrolment against real backend | **Missing** |
| Device-token authentication | **Missing** |
| Signed recovery-command support (Ed25519) | **Missing** — no verifier exists |
| Build/test verification on this machine | **BLOCKED** — no macOS/Xcode available |

**Do not describe iOS as a working SentinelX client.** Parity means rewriting its networking layer against `/api/v1` and implementing enrolment, device-token auth and command verification.

---

## E. Security findings

No secret values appear below.

| ID | Sev | Component | Finding | Status |
|---|---|---|---|---|
| AUD-001 | **High** | `core/limiter.py` | Rate-limit bypass | ✅ Fixed |
| AUD-002 | **High** | `api/deps.py` | Unauthenticated CPU-exhaustion amplifier | ✅ Fixed |
| AUD-003 | **High** | repo history | Committed database credential | ⚠️ Tree cleaned; **rotation BLOCKING** |
| AUD-004 | Medium | `routes/auth.py` | Spoofable `X-Forwarded-For` | ✅ Fixed |
| AUD-005 | Medium | `requirements.txt` | Vulnerable `cryptography` | ✅ Fixed |
| AUD-006 | Medium | frontend | 4 high npm advisories | ✅ Fixed |
| AUD-007 | Medium | repo root | No `LICENSE` | ⚠️ **BLOCKING — owner decision** |
| AUD-008 | Medium | `routes/health.py` | Unauthenticated DB-touching endpoint | ⚠️ Accepted, documented |
| AUD-009 | Low | `schemas/auth.py` | Misleading `role` field on signup | ✅ Verified safe + test added |
| AUD-010 | Low | `routes/auth.py` | Open public self-registration | ⚠️ Documented, owner decision |
| AUD-011 | Low | `core/security.py` | No `iss`/`aud` claim validation | ⚠️ Non-blocking |
| AUD-012 | Info | `services/recovery_command_service.py` | Duplicated field in signed payload | ⚠️ Cosmetic — do **not** "fix" |

### AUD-001 — Rate-limit bypass defeating login brute-force protection (High)

**Evidence.** `_rate_limit_key()` returned `bearer:<sha256(Authorization)>` whenever an `Authorization: Bearer …` header was present, falling back to client IP otherwise. `POST /auth/login`, `/auth/token`, `/auth/signup` and `/devices/enroll` require no authentication, but nothing stopped a caller *sending* the header anyway.

**Exploit.** Send each login attempt with a different random Bearer value. Every request hashes to a new bucket, so the `15/minute` limit never triggers. Unlimited password guessing, unlimited account enumeration via the `409 Conflict` on signup, unlimited enrolment-code guessing. On a serverless host, also an uncapped bill.

**Remediation.** Added `client_ip_key()`, which ignores the `Authorization` header entirely, applied via `key_func=` to all four unauthenticated endpoints. Authenticated agent endpoints keep per-token bucketing, which is safe there because an anonymous caller cannot reach them at all.

**Regression tests.** `test_login_rate_limit_key_ignores_client_supplied_bearer_token`, `test_auth_and_enrollment_modules_use_the_ip_only_key`.

### AUD-002 — Unauthenticated CPU-exhaustion amplifier in device-token auth (High)

**Evidence.** `_resolve_device_credential()` handled non-v2 tokens by selecting *every* active credential and running `verify_password()` (argon2, ~50 ms) against each until one matched.

**Exploit.** One unauthenticated request with a garbage opaque token costs `O(active credentials) × 50 ms` of CPU. At 200 devices that is ~10 seconds of CPU per request, from an anonymous caller, on a path reached before any authentication succeeds. Trivial denial of service; on Cloud Run, a direct conversion of attacker traffic into billable vCPU-seconds.

**Why it was dead code anyway.** Every path that mints a device token — `db/seed.py`, `routes/enrollment.py`, and both create and rotate in `routes/device_credentials.py` — calls `generate_device_token()`, which has produced the v2 `sxa_<uuid>.<secret>` format since Sprint 1. No legacy token can exist in any deployment built from this code.

**Remediation.** Gated behind `ALLOW_LEGACY_DEVICE_TOKENS`, default `False`. The v2 O(1) path is unchanged.

**Regression tests.** `test_legacy_opaque_device_token_is_rejected_without_scanning`, `test_minted_device_tokens_still_match_the_o1_lookup_format`.

### AUD-003 — Committed PostgreSQL credential in public history (High — BLOCKING)

**Evidence.** A working password for the local `sentinelx_app` Postgres role was committed in three tracked files (`backend/.env.example`, `docs/releases/STAGING.md`, `tests/e2e/test_staging_release_scenarios.py`). Introduced in `e8ce6b1`, re-added in `dd9278d`, still present at `6928148`.

**Impact.** The repository is public, so the credential is published. It is scoped to a `localhost` Postgres role, which bounds the direct blast radius — an attacker cannot reach `localhost:5432` remotely. The real risks are (a) password reuse elsewhere, and (b) an attacker who gains any foothold on a machine running that database.

**Remediation applied.** Removed from all three files: the two templates carry placeholders and the E2E test reads `SENTINELX_STAGING_DB_DSN` from the environment. **The working tree is clean — verified by a repository-wide search returning no matches.**

**Remediation still required (owner).** The credential remains in history and I did not rewrite it — §17 of the brief forbids rewriting public history without approval, and rewriting invalidates every existing clone and fork. See §F for both options. **Rotate the password regardless of which you choose; rotation is what actually closes this.**

### AUD-004 — Spoofable client IP in security logs and rate limiting (Medium)

**Evidence.** `_get_client_ip()` returned `X-Forwarded-For.split(",")[0]` whenever the header was present — a value entirely under the caller's control. It feeds `SecurityLog.ip_address`, the record used for abuse investigation.

**Exploit.** Any attacker sets `X-Forwarded-For: 1.2.3.4` and every failed login, rejected enrolment and rate-limit violation is attributed to an innocent third party, poisoning the forensic record. Combined with AUD-001 it also gave a second way to shard rate-limit buckets.

**Remediation.** Introduced `TRUSTED_PROXY_COUNT` (default `0`). At `0` the header is ignored completely. Above `0` the address is read *from the right* — the rightmost entries are appended by infrastructure we control, everything further left is caller-supplied. Set it to `1` behind Cloud Run.

**Regression test.** `test_forwarded_for_is_ignored_unless_a_proxy_count_is_configured`.

### AUD-005 / AUD-006 — Vulnerable dependencies (Medium)

- `cryptography==49.0.0` → **PYSEC-2026-3552**, fixed in 50.0.0. This is the library that signs and verifies every recovery command. Upgraded; all 129 backend tests pass on the new version.
- npm: `react-router` (GHSA-qwww-vcr4-c8h2, RSC-mode CSRF bypass — SentinelX does not use RSC mode, so exposure was limited), `postcss` ×2 path traversal, `nanoid` ×2 infinite loop. `npm audit fix` resolved all four with no major-version jump. **`npm audit` now reports 0 vulnerabilities**; build and lint clean.

### AUD-008 — Unauthenticated health endpoint opens a database connection (Medium, accepted)

`GET /api/v1/health` is public and performs `engine.connect()` + `SELECT 1` on every call. An attacker can drive connection-pool churn and DB load without authenticating, and each call is a billable Cloud Run request. It also discloses `commit_sha`, `environment` and `app_version` publicly.

Accepted rather than changed: it is the endpoint Cloud Run and uptime checks need, the disclosure is low-value for a public open-source project whose commits are readable anyway, and altering its shape risks breaking existing monitoring. **Mitigation:** the API rate limit applies and §L recommends `max-instances=1`, capping the worst case. To tighten later, split liveness (no DB) from readiness (DB, authenticated).

### AUD-009 — `role` accepted but ignored on signup (Low — verified safe)

`SignupRequest` declares `role: Literal["admin","engineer","viewer"] = "viewer"`, which reads like a privilege-escalation vector. It is not: `signup()` ignores the field entirely and computes `role = "admin" if total_users == 0 else "viewer"`. The schema is merely misleading. `test_signup_cannot_self_assign_a_privileged_role` keeps it that way.

### AUD-010 — Open public self-registration (Low — owner decision)

`POST /auth/signup` is public and unauthenticated; anyone on the internet can create an account. New users get `role="viewer"` and `organization_id=None`, so they see no tenant data — the org-scoping checks hold. The practical consequences are unbounded user-row growth and the first-ever signup silently becoming `admin`. **Before going public, either disable open signup or ensure the admin account already exists.**

### AUD-011 — No issuer/audience validation on JWTs (Low)

`decode_access_token()` validates signature and expiry but not `iss`/`aud`. With a single issuer and a secret used for nothing else this is not currently exploitable. It becomes relevant if the signing secret is ever shared with another service. Non-blocking.

### AUD-012 — `expires_at` appears twice in the signed payload (Informational)

`build_canonical_payload()` emits `expires_at_iso` on two consecutive lines (positions 6 and 7), almost certainly a copy-paste of an intended `created_at`. It is **not** a vulnerability: the desktop verifier (`signing.py`) and the Android verifier reproduce the identical structure, so signatures validate correctly, and the nonce plus TTL already provide replay protection. **Do not "fix" this** — changing it breaks signature verification for every deployed agent. Address only alongside a coordinated agent release.

### Autonomous recovery — threat model (no exploitable finding)

The highest-risk subsystem, and the strongest part of the codebase. Verified controls:

| Threat | Control | Verified |
|---|---|---|
| Arbitrary command execution | Fixed `EXECUTORS` dict; no `shell=True`, no `eval`, no dynamic dispatch | ✅ |
| Shell/command injection | `subprocess.run(["net","stop", name])` — list args; `name` comes from a **local** allowlist file, never from the command | ✅ |
| Path injection | No executor accepts a caller-supplied path | ✅ |
| Forged commands | Ed25519 signature over a canonical payload, verified agent-side before execution | ✅ |
| Replay | Per-dispatch `command_nonce`, persisted in agent SQLite, rejected on reuse | ✅ |
| Duplicate execution | Durable `command_log` status; a command recorded `completed` is never re-run | ✅ |
| Command expiry | TTL inside the signed payload, enforced server-side and agent-side | ✅ |
| Restart/reboot loops | Cooldown + 24h daily limit + circuit breaker (3 consecutive failures forces manual approval) | ✅ |
| Cross-device targeting | Commands scoped to `device.id` from the token; a foreign command 404s rather than leaking existence | ✅ |
| Privilege escalation via AI | AI proposals route through the identical `create_command()` policy path; `risk_level` and `policy_id` always come from the matched policy row, never the caller | ✅ |
| Fleet-wide destructive action | One active command per device per action type; no bulk endpoint exists | ✅ |
| Dangerous actions | Reboot, arbitrary process kill, file deletion, registry edits, firewall changes explicitly not implemented | ✅ |

One structural gap: `create_command()` does not validate `parameters` against a per-action schema, so an authorised admin can attach arbitrary JSON. The agent is the effective boundary — `restart_allowlisted_service` rejects any `service_key` absent from its local allowlist. Defence in depth is intact, but a server-side parameter schema would be worthwhile future hardening.

---

## F. Secret-history audit

**Current working tree — CLEAN.** Repository-wide search for the leaked credential returns zero matches.

**Git history — ONE REAL CREDENTIAL FOUND.**

Method (gitleaks/TruffleHog are not installed here, so I scanned directly rather than uploading the repository anywhere):
1. Enumerated every object across all refs (`git rev-list --objects --all`) and matched filenames against `.env`, `*.pem`, `*.p12`, `*.pfx`, `*.jks`, `*.keystore`, `id_rsa`, `*.key`, `keystore.properties`, `local.properties`, `serviceAccount*`, `credentials.json`, `google-services.json`, `GoogleService-Info.plist`.
2. Scanned every added line in every commit diff (`git log --all -p`) for private-key headers, DSNs with embedded passwords, and AWS/GitHub/Slack/OpenAI/Google/npm token formats.

| Check | Result |
|---|---|
| Secret-bearing **filenames** in history | **None.** Only `.env.example` templates and `keystore.properties.example`. No real `.env`, key or keystore was ever committed. |
| Private keys (`BEGIN … PRIVATE KEY`) | **None** |
| AWS / GitHub / Slack / OpenAI / Google / npm tokens | **None** |
| JWTs | **None** |
| **Database URLs with passwords** | **3 hits — one real credential** (AUD-003) |
| GitHub secret scanning configuration | Not verified — requires repository settings access (§M-4) |

**Credentials requiring rotation:** the `sentinelx_app` PostgreSQL role password. **Nothing else.** Given the volume of secret material this project handles (device tokens, an Ed25519 signing key, an Android keystore, JWT secrets), a single leaked localhost password is a genuinely good outcome — `.gitignore` hygiene has been effective.

### History-rewrite decision (owner)

| Option | Effect | Recommendation |
|---|---|---|
| **A — Rotate only** | Rotate the role password. History still shows a dead credential. No clone, fork or existing SHA is disturbed. | ✅ **Preferred.** The credential is localhost-scoped; once rotated it is worthless. Rewriting public history is disruptive and largely theatre here. |
| **B — Rotate + rewrite** | `git filter-repo` + force-push. Invalidates every clone/fork; old SHAs vanish; GitHub may retain unreferenced objects regardless. | Only if you consider the string itself unacceptable. **Requires your explicit approval — I have not done it.** |

---

## G. Dependency audit

| Ecosystem | Tool | Before | After |
|---|---|---|---|
| Python (backend) | `pip-audit` | 1 vulnerability (`cryptography` 49.0.0, PYSEC-2026-3552) | **0** |
| npm (frontend, prod) | `npm audit --omit=dev` | 3 high | **0** |
| npm (frontend, all) | `npm audit` | 4 high | **0** |
| Android/Gradle | manual review | No CVE found; version catalog, R8 enabled | — |
| iOS/Swift | manual review | No third-party package manifest | — |
| Docker base image | new | — | `python:3.12-slim`, Trivy-scanned in CI |
| GitHub Actions | manual review | Pinned to major tags (`@v4`) not SHAs | Non-blocking (below) |

**Not mass-upgraded, deliberately.** `pandas`/`pyarrow` were *removed from runtime* rather than upgraded, because nothing under `backend/app/**` imports them — verified by grep. They now live in `requirements-ml.txt` for the training scripts, cutting roughly 200 MB from the container.

**Non-blocking supply-chain note.** All workflows pin actions to mutable major tags (`actions/checkout@v4`), so a compromised upstream tag would execute in CI. Pinning to full commit SHAs is the hardened practice. Left as-is because it is the overwhelming community norm and the workflows hold no deployment credentials today; revisit when a Cloud Run deploy key is added.

---

## H. API compatibility matrix

| Endpoint group | Web | Desktop | Android | iOS |
|---|:--:|:--:|:--:|:--:|
| `/auth/*` (login, signup, me, logout) | ✅ | — | ✅ | ❌ different contract |
| `/devices/enroll`, `/devices/enrollment-codes` | ✅ | ✅ | ✅ | ❌ missing |
| `/devices`, `/devices/agent-sync` | ✅ | ✅ | ✅ | ❌ |
| `/metrics`, `/metrics/batch` | ✅ read | ✅ batch | ✅ batch | ❌ `batch` on another server |
| `/heartbeats` | ✅ read | ✅ | ✅ | ❌ |
| `/agent/public-key`, `/agent/capabilities`, `/agent/commands/*` | — | ✅ | ✅ | ❌ **missing entirely** |
| `/alerts`, `/incidents`, `/alert-rules` | ✅ | — | ✅ read | ❌ |
| `/recovery-commands/*` | ✅ | — | — | ❌ |
| `/observability/*`, `/hybrid/*`, `/replay/*` | ✅ | — | — | ❌ |
| `/audit-logs`, `/security-logs`, `/users`, `/organizations` | ✅ | — | — | ❌ |
| `/telemetry/embedded` | — | — | — | — (Arduino bridge) |

**Incompatibilities.**
1. **iOS is not a client of this API** (§D). Its six endpoints do not intersect the real contract, and it expects a `token/refresh` endpoint the backend does not implement.
2. **No refresh-token flow exists** anywhere in the backend. Access tokens live 24 hours and are stateless. The iOS prototype assumed otherwise.
3. `POST /metrics` (single) and `POST /metrics/batch` overlap. Both are used; batch is strictly better (idempotent, preserves timestamps). Not removed — that would be breaking. Candidate for `/api/v2` deprecation.

**No `/api/v1` behaviour was changed by this audit.** Every endpoint keeps its path, request body and response model. OpenAPI generates cleanly and drove the route sweep in §I.

---

## I. Test results

All commands run on this machine against local PostgreSQL 16. Nothing fabricated.

| Suite | Command | Result |
|---|---|---|
| Backend (pre-change baseline) | `pytest ../tests/backend/ -q` | **118 passed** in 40.18s |
| Backend (after security fixes) | `pytest ../tests/backend/ -q` | **118 passed** in 42.76s |
| **Backend (final, with new tests)** | `pytest ../tests/backend/ -q` | **✅ 129 passed** in 33.47s |
| New hardening regressions | `pytest ../tests/backend/test_production_hardening.py -q` | **✅ 11 passed** |
| Desktop agent | `pytest tests/ -q` | **✅ 29 passed** |
| Frontend build | `npm run build` | **✅** built in 4.76s |
| Frontend build (Pages base path) | `VITE_BASE_PATH=/SentinelX/ npm run build` | **✅** assets correctly prefixed |
| Frontend lint | `npm run lint` | **✅** clean |
| Frontend audit | `npm audit` | **✅ 0 vulnerabilities** |
| Python audit | `pip-audit -r requirements.txt` | **✅ 0 vulnerabilities** |
| **Unauthenticated route sweep** | all 95 routes, no credentials | **✅ only the 5 intended public endpoints responded** |

One transient failure occurred and was fixed: adding two fields to the frozen `AgentConfig` dataclass broke 16 agent tests that construct it directly. `tests/conftest.py` was updated and all 29 pass.

### BLOCKED — could not be executed here

| Suite | Why |
|---|---|
| **iOS unit tests** (17 files) | Requires macOS + Xcode. This is a Windows machine and the project has no Mac access. |
| **Android unit tests** (4 files) | Requires a JDK + Gradle toolchain and Android SDK; not verified this session. CI (`android.yml`) covers them. |
| **Docker image build + Trivy scan** | Docker is not installed on this machine. `backend/Dockerfile` is **written but never built** — its first CI run is a gate, not a formality. |
| **E2E staging scenarios** (17) | Requires a live staging backend on port 8200 plus a seeded staging database. |
| **Load/soak** (`tests/load/locustfile.py`) | Requires a running target. |

---

## J. Cloud free-tier readiness

> **PROMOTIONAL, STUDENT AND TRIAL CREDITS COUNTED AS £0.**

| Service | Free allowance relied on | Verdict |
|---|---|---|
| **GitHub (public repo)** | Unlimited public repos | ✅ **Safe** |
| **GitHub Actions** | Unlimited minutes for **public** repos on standard runners | ✅ **Safe** — all workflows use `ubuntu-latest`; no larger/paid runners. Removing the keep-warm cron eliminates ~4,320 wasted runs/month. |
| **GitHub Pages** | Free for public repos; 1 GB site, 100 GB/month soft bandwidth | ✅ **Safe** — built site ~1.5 MB, four orders of magnitude inside the limit. |
| **GHCR** | Free and unmetered for **public** images | ✅ **Safe** — and it lets us skip Artifact Registry entirely. |
| **Google Cloud Run** | 2,000,000 requests, 180,000 vCPU-s, 360,000 GiB-s per month | ⚠️ **Conditional** — safe with the §L configuration and the request reduction shipped here. |
| **Google Artifact Registry** | **0.5 GB storage only** | ❌ **AVOIDED** — the API image exceeds this. Cloud Run can deploy public GHCR images directly, so Artifact Registry is designed out. |
| **Google Cloud Build** | 120 build-min/day | ❌ **AVOIDED** — GitHub Actions builds the image for free. |
| **Cloud SQL / Load Balancer / VPC connector / Cloud NAT / static IP** | No adequate free tier | ❌ **NOT USED — must never be created.** A VPC connector alone bills ~£7+/month at zero traffic. |
| **Neon** | 0.5 GB storage, ~191 compute-hours/month, autosuspend | ⚠️ **Conditional** — storage is the binding constraint (§K). |
| **Vercel** | — | ✅ **NOT REQUIRED — eliminated** (§L). |

### Why Cloud Run is "conditional", not "safe"

Cloud Run's free tier is generous, but **request count is the binding constraint**, and SentinelX's own agents — not human dashboard users — dominate it. This was the single most important finding of the cost analysis and is why §K exists.

Critically, Cloud Run has **no hard spending cap**. Budget alerts notify; they do not stop. The only real protections are `max-instances`, scale-to-zero, and keeping request volume genuinely inside the allowance — which the changes in this audit deliver.

---

## K. Usage model

Derived from the actual code, not estimates: `metrics_interval_seconds=10`, `heartbeat_interval_seconds=30`, and — before this audit — a queue flush and a command poll on **every** 10-second tick (`main.py` loop).

### Requests per desktop agent

| | Before | After |
|---|---:|---:|
| Metric uploads (`POST /metrics/batch`) | 8,640/day | 1,440/day |
| Command polls (`GET /agent/commands/next`) | 8,640/day | 1,440/day |
| Heartbeats (`POST /heartbeats`) | 2,880/day | 2,880/day |
| **Total** | **20,160/day** | **4,800/day** |
| **Per 30-day month** | **~605,000** | **~144,000** |
| **Share of Cloud Run's 2M free requests** | **~30%** | **~7.2%** |

**Telemetry granularity is unchanged.** Samples are still captured every 10 seconds and each carries its own `recorded_at`, which `/metrics/batch` preserves. Batching alters how many HTTP requests carry the same rows, not the rows themselves. The only user-visible trade-off is that a sample now reaches the dashboard up to 60 seconds after capture instead of up to 10 — normal for monitoring products, and tunable via `SENTINELX_QUEUE_FLUSH_INTERVAL_SECONDS`.

### Fleet scaling (agents + ~5,000 dashboard requests/month)

| Devices | Requests/month | % of 2M | vCPU-s (100 ms billed) | % of 180k | Verdict |
|---:|---:|---:|---:|---:|---|
| 1 | ~149,000 | 7.5% | ~14,900 | 8.3% | ✅ Comfortable |
| 5 | ~725,000 | 36% | ~72,500 | 40% | ✅ Comfortable |
| 10 | ~1,445,000 | 72% | ~144,500 | 80% | ⚠️ Approaching limits |
| 50 | ~7,205,000 | **360%** | ~720,500 | **400%** | ❌ **Billable** |
| 100 | ~14,405,000 | **720%** | — | — | ❌ **Billable** |

**Before this audit the same table crossed the free tier at 3 devices.** It now holds to roughly 10. Beyond that, raise the intervals further (300 s supports ~50 devices) or accept charges.

### Database growth (Neon Free, 0.5 GB)

One `system_metrics` row every 10 s per device = 8,640 rows/day. At ~200 bytes/row plus indexes (~350 bytes effective):

| Devices | Rows/month | Storage/month | Time to fill 0.5 GB |
|---:|---:|---:|---|
| 1 | ~260,000 | ~91 MB | **~5.5 months** |
| 5 | ~1,300,000 | ~455 MB | **~1.1 months** |
| 10 | ~2,600,000 | ~910 MB | **~2.5 weeks** |

**Storage, not compute, is Neon's binding constraint.** Telemetry retention is mandatory, not optional. `docs/releases/DATA_RETENTION_POLICY.md` and `app/db/data_retention_report.py` already exist — a scheduled prune (e.g. GitHub Actions calling an authenticated endpoint) must be wired up before real fleet use. Neon Free suspends rather than auto-charging at the limit, which is the failure mode we want.

Neon compute (~191 h/month) is comfortable: autosuspend plus request-driven traffic keeps a single-device setup well under it.

### Pathological scenarios

| Scenario | Protection | Assessment |
|---|---|---|
| Backend unavailable | Bounded exponential backoff, `Retry-After` honoured, max 3 attempts, then samples queue in SQLite | ✅ Cannot run away |
| Agent retry loop | Per-row backoff to a 900 s ceiling; queue capped at 10,000 rows | ✅ Bounded |
| Duplicate telemetry | `event_id` idempotency, deduplicated server-side and within the batch | ✅ Safe |
| Runaway browser polling | TanStack Query with configured intervals; API limit 300/min | ✅ Bounded |
| Compromised client flooding | Per-token rate limiting; credential revocable | ✅ Bounded |
| **Anonymous flood** | Per-IP limits (now unbypassable — AUD-001), `max-instances=1` | ⚠️ **Residual: a distributed flood still consumes free-tier requests.** `max-instances=1` caps compute cost but not request count. Accept, or place Cloudflare in front later. |

---

## L. Deployment architecture recommendation

```
GitHub (public repo)
├── Actions ──▶ backend tests · frontend build · Android · container build + Trivy
│
├── Pages ────▶ React dashboard      ✅ free, unmetered, HTTPS
│                     │
│                     │  HTTPS + CORS
│                     ▼
└── GHCR ─────▶ Cloud Run (API)      ⚠️ free if configured as below
      public image          │
      (no Artifact Registry) │  TLS
                             ▼
                        Neon Free (PostgreSQL)
```

**The simplest architecture that is secure, maintainable and stays inside permanent free allowances.**

### Frontend: GitHub Pages — **Vercel eliminated**

GitHub Pages can host this application correctly. The three obstacles were real and are now fixed:

| Obstacle | Resolution |
|---|---|
| Vite `base` defaulted to `/`; assets would 404 under `/SentinelX/` | `VITE_BASE_PATH` added; **verified** — build emits `/SentinelX/favicon-32.png` etc. |
| `BrowserRouter` had no `basename`; routes would 404 | `basename={import.meta.env.BASE_URL}` added |
| Pages has no SPA rewrite; refreshing `/devices/<id>` 404s | `pages.yml` copies `index.html` → `404.html` |

Remaining requirements, all satisfied: no service worker exists; the API base URL is a build-time `VITE_API_BASE_URL` (public by nature — never put a secret in a `VITE_` variable); Pages serves HTTPS; CORS is handled by `BACKEND_CORS_ORIGINS`.

**Vercel adds nothing here and is dropped**, removing a vendor and an account from the architecture.

### Backend: Cloud Run, deployed from GHCR

| Setting | Value | Rationale |
|---|---|---|
| Image source | **public GHCR** | Verified supported. Skips Artifact Registry's 0.5 GB cap and Cloud Build minutes. |
| `--min-instances` | **0** | Never pay for idle. Accept cold starts. |
| `--max-instances` | **1** | Hard ceiling on runaway compute — the closest thing to a spending cap. Also required for correctness: the rate limiter is in-process. |
| `--cpu` / `--memory` | **1 / 512Mi** | Fits FastAPI + numpy/scikit-learn. Confirm on first deploy; raise only if OOM. |
| `--concurrency` | **80** | Fewer instance-seconds per request. |
| CPU throttling | **enabled** (default) | Request-based billing; no CPU charged between requests. |
| Public access | **yes** | Agents and browsers must reach it; app-level auth is the boundary. |
| VPC connector / Cloud NAT / LB / static IP | **none** | Each bills from the first hour. Neon is reached over public TLS. |
| Cloud SQL | **none** | No free tier. Neon replaces it. |

Required environment: `APP_ENV=production` (disables `/docs`, enables HSTS, and **refuses to start on the default JWT secret** — an existing control worth keeping), a strong `JWT_SECRET_KEY`, `DATABASE_URL` (Neon, `sslmode=require`), `BACKEND_CORS_ORIGINS` set to the exact Pages origin, **`TRUSTED_PROXY_COUNT=1`**, `ALLOW_LEGACY_DEVICE_TOKENS=False`, `SENTINELX_COMMIT_SHA`.

The Ed25519 recovery signing key must be mounted from **Secret Manager** (6 free secret versions), never baked into the image — `.dockerignore` already excludes `backend/.secrets/`.

### Observability

Cloud Run's built-in Cloud Logging is sufficient and free within allowance. The app already emits structured JSON with correlation IDs. **Do not add a paid observability vendor.** At ~150k requests/month, log volume will stay well inside the free logging tier.

---

## M. Blocking actions requiring the owner

Only items I genuinely cannot perform.

| # | Action | Why it needs you |
|---|---|---|
| **1** | **Rotate the `sentinelx_app` PostgreSQL password** on every machine using it. | Requires database superuser credentials I do not have. **This is what actually closes AUD-003** — the tree cleanup does not. |
| **2** | **Choose a licence** (MIT or Apache-2.0) and add `LICENSE`. | A legal decision with permanent consequences for a public project. Not mine to make. |
| **3** | **Decide on the history rewrite** (§F option A or B). | The brief forbids rewriting public history without explicit approval; rewriting breaks every clone and fork. |
| **4** | **Enable GitHub secret scanning + push protection** (Settings → Code security). | Requires repository admin in the browser. Free for public repos and worth enabling. |
| **5** | **Decide whether open signup stays enabled** (AUD-010). | Product decision. If it stays, create the admin account before going public so the first stranger to sign up does not become `admin`. |
| **6** | **Create the Google Cloud project and set `VITE_API_BASE_URL`** at deploy time. | Requires interactive `gcloud auth login` and console access. |
| **7** | **iOS: decide rebuild vs. shelve.** | Product/scope decision. Parity is a substantial rewrite (§D). |

---

## N. Changes made

All in commit `abf02a6` on `audit/production-readiness-2026-08-13`.

### Security
| File | Change | Why |
|---|---|---|
| `backend/app/core/limiter.py` | Added `client_ip_key()`; documented when token-bucketing is safe | AUD-001, AUD-004 |
| `backend/app/api/routes/auth.py` | `key_func=client_ip_key` on login/token/signup; `_get_client_ip` delegates to the trusted resolver | AUD-001, AUD-004 |
| `backend/app/api/routes/enrollment.py` | `key_func=client_ip_key` on `/devices/enroll` | AUD-001 |
| `backend/app/api/deps.py` | Legacy opaque-token scan gated off by default | AUD-002 |
| `backend/app/core/config.py` | Added `trusted_proxy_count`, `allow_legacy_device_tokens` | AUD-002, AUD-004 |
| `backend/.env.example` | Removed real password; documented new settings | AUD-003 |
| `docs/releases/STAGING.md` | Password → placeholder | AUD-003 |
| `tests/e2e/test_staging_release_scenarios.py` | Credentials read from environment | AUD-003 |
| `backend/requirements.txt` | `cryptography` 49.0.0 → 50.0.0 | AUD-005 |
| `frontend/package-lock.json` | `npm audit fix` — 4 high advisories cleared | AUD-006 |

### Cost / free-tier
| File | Change | Why |
|---|---|---|
| `agents/desktop-python/sentinelx_agent/config.py` | Added `queue_flush_interval_seconds`, `command_poll_interval_seconds` (default 60) | −76% requests/device |
| `agents/desktop-python/sentinelx_agent/main.py` | Flush and poll on their own timers, not every tick | −76% requests/device |
| `agents/desktop-python/.env.example` | Documented both, with the trade-off | Operability |
| `backend/requirements.txt`, `backend/requirements-ml.txt` | pandas/pyarrow moved out of runtime | −200 MB image |
| `backend/requirements-dev.txt` | Includes ML extras; added `pip-audit` | Keeps CI green |
| `.github/workflows/keepwarm.yml` | **Deleted** | Target 403s; keep-warm defeats scale-to-zero |

### Deployment
| File | Change |
|---|---|
| `backend/Dockerfile` | **New** — multi-stage, non-root uid 10001, honours `$PORT`, single uvicorn worker, no dev server |
| `.dockerignore` | **New** — excludes `.env`, `backend/.secrets/`, keystores, venvs, node_modules |
| `.github/workflows/docker.yml` | **New** — build + Trivy scan; pushes to GHCR on `main` only |
| `.github/workflows/pages.yml` | **New** — lint/build gates, then Pages deploy with base path + `404.html` |
| `frontend/vite.config.ts` | `base` from `VITE_BASE_PATH` (default `/`) |
| `frontend/src/main.tsx` | `BrowserRouter basename={import.meta.env.BASE_URL}` |

### Tests
| File | Change |
|---|---|
| `tests/backend/test_production_hardening.py` | **New** — 11 regressions incl. the 95-route public-surface sweep, viewer RBAC, inactive-user revocation, signup role assignment |
| `agents/desktop-python/tests/conftest.py` | Fixture updated for the two new `AgentConfig` fields |

**Not changed, deliberately:** no `/api/v1` endpoint, payload field or response model; no framework swap; no history rewrite; no cosmetic refactors; AUD-012 left alone to avoid breaking deployed agents.

---

## O. Rollback

`main` is untouched at `cbc0eca`. Nothing was pushed.

```bash
# Return to the exact pre-audit state
git checkout main            # already at cbc0eca

# Discard the audit branch entirely
git branch -D audit/production-readiness-2026-08-13

# Or keep the report and drop the code changes
git checkout main
git checkout audit/production-readiness-2026-08-13 -- docs/PRODUCTION_READINESS_AUDIT.md
```

Environment changes outside Git (revert only if you want the pre-audit state exactly):
- `backend/.venv`: `cryptography` 49.0.0 → 50.0.0, `pip-audit` installed
- `frontend/node_modules`: 4 packages updated by `npm audit fix`

```bash
cd backend && .venv/Scripts/pip install cryptography==49.0.0
cd frontend && git checkout main -- package-lock.json && npm ci
```

---

## P. Next command / run

### SentinelX is **NOT YET READY** for the production deployment run.

The engineering is ready. The paperwork and one credential are not.

**Close these three, in order:**

1. **Rotate the `sentinelx_app` PostgreSQL password.** (§M-1 — closes AUD-003.)
2. **Add a `LICENSE` file.** (§M-2 — closes AUD-007; without it this is not legally open source.)
3. **Merge `audit/production-readiness-2026-08-13` into `main` and confirm CI is green** — in particular the **first-ever Docker build**, which has never run (§I BLOCKED).

**Then verify, before touching any cloud console:**

4. Decide the open-signup question and create the admin account first (§M-5).
5. Enable GitHub secret scanning + push protection (§M-4).
6. Wire up telemetry retention pruning — at 5 devices Neon Free fills in ~1.1 months (§K).

**Recommended version for the merged branch: `v3.1.0`** — a minor bump. The changes are backwards-compatible security hardening plus new production capabilities (container, Pages, CI); no `/api/v1` contract was broken, so this is not a major. Not `v4`. **Do not tag the release until items 1–3 pass.**

When the deployment run begins, deploy in this order so each layer is verifiable before the next depends on it:

**Neon → Cloud Run (from GHCR) → set `BACKEND_CORS_ORIGINS` → GitHub Pages → enrol one desktop agent → observe for 24 h before adding devices.**
