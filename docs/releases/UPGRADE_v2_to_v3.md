# Upgrading v2.0.0 → v3.0.0

This is an additive release: no destructive schema changes, no breaking API
contract changes for existing desktop/Android agents against the same
backend. The bulk of the "upgrade" work is closing a gap Phase 0's baseline
audit found, not adapting to new behaviour.

## Why this isn't a routine bump

The live v2.0.0 production deployment is running backend **code** roughly at
the Sprint 1 boundary, but its **database schema** predates Sprint 1 entirely
— `migrations/2026-07-17_trusted_agent_foundation.sql` and every migration
after it (AI observability, recovery orchestration, hybrid detection, model
lifecycle, replay) were never applied to production. Confirmed by probing
routes that depend on Sprint 1+ tables (401 = table exists but needs auth,
404 = route/table genuinely missing) and by restoring the real production
backup locally and running `\dt`. Upgrading to v3.0.0 must apply the **full**
migration chain in order, not just the newest files.

## Pre-upgrade

1. Take a fresh `pg_dump` of the production database (in addition to the
   Phase 0 baseline backup) and verify it restores cleanly to a scratch
   database before touching production.
2. Confirm `backend/.env` (or the App Service configuration) has no default
   placeholder values — `jwt_secret_key` must not be
   `"change-this-dev-secret-before-production"` in production (Phase 4 adds
   a boot-time guard for this).
3. Set `SENTINELX_COMMIT_SHA` in the deploy environment so `/health` reports
   the exact commit running in production, not a `git rev-parse` guess.
4. **Check for an explicit `APP_VERSION` app setting on the App Service.**
   Discovered during this bump: `backend/.env` (and `.env.example`) had
   `APP_VERSION=2.0.0` hardcoded, which silently overrides the code default
   via `pydantic-settings`' env-var loading — bumping `app_version` in
   `config.py` alone did **not** change what `/health` reported locally
   until this env var was fixed too. If production's App Service
   configuration has its own `APP_VERSION` application setting (likely,
   since `backend/.env` was almost certainly mirrored there during initial
   setup), it must be updated or removed as part of this deploy, or
   `/health` will keep reporting `2.0.0` even after the v3.0.0 code ships.

## Migration order

Run the apply script from `backend/` (with the target `DATABASE_URL` set):

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m app.db.apply_migrations
```

It applies every file under `migrations/` in **chronological** order (parsed
from the date embedded in each filename, not filename string order — those
disagree: `-` sorts before `_` in ASCII, so a naive sort would put
`2026-07-12_...` before `2026_06_26_...`, which is backwards), tracks what
has run in a `schema_migrations` table, and is safe to run more than once —
already-applied files are skipped, and every file's own DDL is written to be
a no-op on re-run. True chronological order:

```
2026_06_26_device_detail_indexes.sql
2026_06_26_operations_features_indexes.sql
2026_06_27_auth_rbac_indexes.sql
2026-07-12_mobile_metric_columns.sql
2026-07-17_trusted_agent_foundation.sql
2026-07-18_ai_observability_foundation.sql
2026-07-19_safe_recovery_orchestration.sql
2026-07-20_hybrid_detection_engine.sql
2026-07-21_model_lifecycle_and_evaluation.sql
2026-07-22_historical_replay.sql
```

Before running against production, restore the pre-upgrade backup into a
scratch database and run the script against that copy first (migration
readiness check — Phase 11) — see
`tests/backend/test_schema_migrations.py` for the equivalent automated
check against a reconstructed legacy schema.

After applying, verify the tables Phase 0 found missing now exist (at
minimum: enrolment codes, feature windows, anomaly predictions/models,
recovery commands, hybrid decisions, replay runs).

## Application upgrade

1. Deploy the v3.0.0 backend build (`app_version = "3.0.0"`).
2. Deploy the v3.0.0 frontend build (`package.json` version `"3.0.0"`).
3. Verify `GET /api/v1/health` returns `"version": "3.0.0"` and a real
   `commit_sha` (not `"unknown"`).
4. Existing desktop agents (`__version__ == "2.1.0"`) and Android installs
   (`versionName == "2.2.0"`) continue to work unchanged against the
   upgraded backend — device-token auth and the metrics/recovery contracts
   are unchanged. Upgrading agent installs to 3.0.0 is not required for
   compatibility; it's recommended so `/health`-style version reporting and
   future agent-side changes stay aligned. Desktop rollout is covered by
   Phase 8 (installer), Android by Phase 9 (real-device pass).

## Post-upgrade verification

- Re-run the route probes from the Phase 0 baseline; previously-401 routes
  that depend on new tables should now behave normally end-to-end, not just
  return "exists but needs auth".
- Confirm existing orgs/users/devices are intact (row counts unchanged
  except for new tables, which start empty).
- Watch `SecurityLog`/`AuditLog` for unexpected errors in the first
  monitoring window (see Phase 11 for the full deployment sequence and
  monitoring-window gate).
