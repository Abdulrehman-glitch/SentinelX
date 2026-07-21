# Changelog

All notable changes to SentinelX are documented in this file. Format loosely
follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/); versioning
follows [SemVer](https://semver.org/).

Component versions move together under one release number (backend, frontend,
desktop agent, Android agent). The Android agent additionally carries its own
build-level `versionCode`/`versionName` history in
`agents/android-native/CHANGELOG.md`; the iOS agent and Expo mobile scaffold
are tracked separately and are not yet part of this release train.

Formal changelog tracking starts with 3.0.0 — entries below 3.0.0 are
reconstructed retroactively from git history and sprint documentation for
context, not logged in real time.

## [3.0.0] — Unreleased (Sprint 7 — Production Hardening)

The coursework's final sprint: hardens the platform that Sprints 1–6 built
into a versioned, tested, documented release, without changing product
behaviour. Full scope tracked in the Sprint 7 roadmap; sections below fill in
as each phase lands.

### Added
- Explicit semantic versioning (`3.0.0`) across backend, frontend, desktop
  agent, and Android agent — previously inconsistent or entirely absent.
- `commit_sha` field on `GET /api/v1/health`, resolved from
  `SENTINELX_COMMIT_SHA` (set by CI/deploy) or a local `git rev-parse`
  fallback for dev, so a running deployment can be tied back to an exact
  commit.
- Release documentation: this changelog, `docs/releases/RELEASE_NOTES_v3.0.0.md`,
  `docs/releases/UPGRADE_v2_to_v3.md`, `docs/releases/ROLLBACK_v3_to_v2.md`,
  `docs/releases/RELEASE_CHECKLIST.md`.
- *(Phases 2–12 append here as they land: deterministic migrations, CI/CD,
  security hardening, observability, data lifecycle, staging/load testing,
  desktop installer, Android device pass, frontend/docs readiness,
  production deployment.)*

### Fixed
- `agents/android-native/.../CommandRepository.kt` carried a hardcoded
  `AGENT_VERSION = "2.2.0"` that had drifted from `build.gradle.kts`'s actual
  `versionName` — now `3.0.0` and tracked as part of this bump.
- Stale version references in `README.md` and `CLAUDE.md` (root docs still
  said `v1.0`/`v2.1.0` after the platform had moved well past that).

## [2.0.0] and earlier — pre-versioning baseline (reconstructed)

No component carried a real semantic version before this sprint; the backend
hardcoded `app_version = "2.0.0"` as a static label, not a tracked release.
The live Azure deployment (`sentinelx-api.azurewebsites.net`,
`sentinelx.z28.web.core.windows.net`) that Sprint 7 treats as the v2.0
rollback target corresponds roughly to the state after the commits below.

- **Sprint 4–6 — Hybrid detection, model lifecycle, replay** (`d6e8101`,
  `427a1ab`, `848509b`): versioned `HybridDecision` combining deterministic
  alert rules, statistical baseline, and IsolationForest evidence; governed
  `AnomalyModel` lifecycle (`candidate → shadow → advisory → alert_eligible`)
  with promotion gates; read-only historical replay via `ReplayRun`; Hybrid
  Detection Centre frontend.
- **Sprint 3 — Signed recovery orchestration** (`dce8c1f`): Ed25519-signed,
  TTL-bound `RecoveryCommand`s with allowlisted execution on the desktop and
  Android agents.
- **Sprint 2 — AI observability shadow mode** (`fa735dd`): statistical
  baseline + IsolationForest anomaly scoring over rolling feature windows,
  writing `AnomalyPrediction` rows for human review only — never wired into
  the alert/incident pipeline.
- **Sprint 1 — Trusted Agent Foundation** (`370345e`): enrolment codes,
  device-credential rotation, telemetry idempotency.
- Teal/slate/sand "Operations Console" rebrand (`cc8e13c`), Android v2.2.0
  brand release, iOS mobile agent (Swift 6, offline-first SQLite queue),
  repo restructure into `agents/`, `migrations/`, `docs/`.
