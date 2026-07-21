# Release Checklist

Repeatable checklist for cutting a SentinelX release. Written for v3.0.0
(Sprint 7) but scoped to apply to any future release, not just this one —
copy/tick per release rather than editing this master copy.

## Before starting

- [ ] Confirm the target version number and that every component will move
      together (backend `app_version`, frontend `package.json`, desktop
      agent `__version__`/`agent_version` default, Android
      `versionCode`/`versionName` + any duplicated literal like
      `CommandRepository.kt`'s `AGENT_VERSION`).
- [ ] Confirm no in-flight uncommitted work on `main`.
- [ ] Record the current production state as a rollback target (version,
      commit, `/health` output, DB backup) — see the Phase 0 baseline
      pattern in `docs/Evidence/sprint7_production_release/00_baseline/`.

## Versioning & scaffolding (Phase 1)

- [ ] Bump versions in all four components.
- [ ] `/health` reports the new version and a real `commit_sha`.
- [ ] `README.md` / `CLAUDE.md` / `AGENTS.md` have no stale version mentions.
- [ ] `CHANGELOG.md` has an entry for this version.
- [ ] `RELEASE_NOTES_vX.Y.Z.md`, `UPGRADE_*.md`, `ROLLBACK_*.md` exist and
      are accurate for this release's actual changes.

## Migrations

- [ ] Every file under `migrations/` needed for this release is accounted
      for in the upgrade doc, in chronological order (`python -m
      app.db.apply_migrations` computes this from the embedded date, not
      filename order — the two disagree for some files, see Phase 2).
- [ ] Migration test harness passes: `pytest tests/backend/test_schema_migrations.py`
      (fresh-install, upgrade-from-legacy-schema, idempotent re-run, FK/index
      integrity — Phase 2, done 2026-07-20).
- [ ] No migration in this release drops or destructively alters existing
      columns without an explicit, separately-approved plan.

## CI/CD

- [ ] Backend, frontend, desktop agent, and Android CI workflows are green
      on the release commit.
- [ ] Required-check branch protection is a separate, explicitly-approved
      decision — do not flip it as a side effect of adding workflow files.

## Security

- [x] No default/placeholder secrets reachable in production config —
      `Settings` (`backend/app/core/config.py`) refuses to construct with
      `APP_ENV=production` and the default `jwt_secret_key` placeholder
      (Phase 4, done 2026-07-20; see `tests/backend/test_config_security.py`).
- [x] `pip-audit` clean for `backend/` and `agents/desktop-python/`, `npm
      audit` clean for `frontend/`, Android's `security-crypto` bumped off
      an alpha release — see the Phase 4 entry in the sprint roadmap memory
      for the full list of CVEs fixed and versions bumped. No automated
      Gradle CVE scanner is wired in (documented, accepted gap — no
      offline/CI-friendly equivalent to pip-audit/npm-audit was available
      this sprint); dependency versions were checked manually instead.
      Secret scan (`detect-secrets`, in place of `gitleaks` which isn't
      installed locally) found only known/intentional matches (demo
      passwords, the JWT placeholder constant itself, test fixtures).
- [x] Rate limiting, CORS, and security headers verified strict in
      production config, not just present in code.

## Observability

- [x] `/health` reports uptime/readiness in addition to version/commit
      (`uptime_seconds`, `ready` — Phase 5, done 2026-07-20).
- [x] Structured logging includes a request-correlation ID (`X-Request-ID`
      middleware in `main.py`, JSON formatter in `core/logging_config.py`;
      accepts a client-supplied ID or generates one, echoes it on the
      response). Note: only application-level logs are JSON — uvicorn's own
      access/error logs keep their default format (accepted scope boundary,
      see the Phase 5 roadmap entry).
- [x] Admin counters endpoint (`GET /security-logs/counters`) surfaces
      failed-auth count, rate-limit-violation count, recovery-command
      verification failures, and telemetry sample rate over a capped
      time window, tenant-scoped like the rest of `/security-logs`.

## Data Lifecycle

- [x] Retention policy documented per table with rationale —
      `docs/releases/DATA_RETENTION_POLICY.md` (Phase 6, done 2026-07-20).
- [x] Read-only dry-run report (`python -m app.db.data_retention_report`)
      verified against real data (local `sentinelx_dev`: 0 rows past any
      cutoff yet, consistent with prod's schema only recently catching up
      through this sprint's migrations).
- [ ] No deletion job implemented this sprint — explicit, documented,
      accepted scope boundary (see the policy doc's "Why no deletion yet").

## Testing

- [x] Full backend test suite passes (`tests/backend/`) — 118/118, done 2026-07-20.
- [x] The 17 E2E release scenarios from the Sprint 7 brief pass against the
      staging stack, not just unit/integration tests — `tests/e2e/test_staging_release_scenarios.py`
      (scenarios 1-14, all real HTTP against the live staging backend) +
      a live migration/backup/rollback rehearsal for scenarios 15-17 — see
      `docs/Evidence/sprint7_production_release/07_staging_and_e2e/`.
- [x] Load/soak testing against staging only — never against the
      production App Service F1 instance (hard CPU quota risk). Found and
      fixed a real bug (rate-limit handler crashing with 500 instead of
      429 under load) — see `docs/releases/LOAD_SOAK_RESULTS.md`.

## Component releases

- [x] Desktop installer built, checksummed, and install/upgrade/uninstall
      tested in an isolated scratch environment — `docs/releases/DESKTOP_INSTALLER.md`,
      done 2026-07-20. Found and fixed two real bugs live (Python-detection
      via elevated PATH, and a PowerShell-invocation failure specific to
      the compiled uninstaller's process).
- [x] Android release build signed, checksummed, and tested on a real
      device (install/upgrade/uninstall/re-enrolment), not emulator-only —
      Pixel 4 XL over USB, backend reached via a Cloudflare Quick Tunnel
      (system-trusted HTTPS, release policy unweakened) — see the Phase 9
      entry in the sprint roadmap memory for full findings.
- [x] Frontend click-through against staging: auth lifecycle, RBAC, error
      states, no console errors, responsive layout — done 2026-07-21, real
      browser against the live staging stack (`:4300`/`:8200`). Found and
      fixed two real bugs (stuck "Resolving..." button after a mutation
      settles; stale "v2.0" sidebar version literal) — see the Phase 10
      entry in the sprint roadmap memory.

## Documentation & evidence

- [x] README/CLAUDE.md/AGENTS.md/architecture/ops-runbook/security-model
      docs reflect the release, not a prior sprint's state — done
      2026-07-21 (AGENTS.md was badly stale, fully rewritten to mirror
      CLAUDE.md; README fixed to drop removed dependencies and add
      Sprint 7 features).
- [x] `docs/Evidence/sprint7_production_release/` populated incrementally,
      not reconstructed after the fact.

## Production deployment — GATE: explicit user confirmation required

- [ ] Backup taken and restore-verified.
- [ ] Migration readiness confirmed against the backup.
- [ ] Backend deployed → migrated → smoke-tested.
- [ ] Frontend deployed → smoke-tested.
- [ ] Existing (un-upgraded) agents confirmed still compatible.
- [ ] End-to-end smoke test against the live production URL.
- [ ] Monitoring window observed before declaring done.

## Tag & final report — GATE: explicit user confirmation required

- [ ] Release commit created.
- [ ] `vX.Y.Z` tag created only after production verification passes.
- [ ] Final status report delivered.
