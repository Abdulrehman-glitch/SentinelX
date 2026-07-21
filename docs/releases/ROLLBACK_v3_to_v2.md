# Rolling back v3.0.0 → v2.0.0

Use this if a v3.0.0 production deployment (Phase 11) needs to be reverted.
Every migration shipped in this release chain is additive-only (new tables /
new nullable columns, no drops, no renames, no `NOT NULL` added to existing
columns) specifically so this rollback can be code-only in the common case.

## Decide which rollback you need

**Case A — backend/frontend misbehaving, schema is fine.**
This is the expected case, since the schema changes are additive and the
v2.0.0 backend code simply never queries the new tables/columns.

1. Redeploy the previous backend build (App Service — swap back to the prior
   deployment slot/package, or redeploy the last known-good commit).
2. Redeploy the previous frontend build (Storage static site — restore the
   prior build output).
3. Leave the database schema as-is. Do **not** run any "down" migration —
   there isn't one, and reverting schema is riskier than leaving unused new
   tables/columns in place.
4. Verify `GET /api/v1/health` reports the prior version and confirm core
   flows (login, metrics ingestion, alerts) work as they did pre-upgrade.

**Case B — data corruption or a migration went wrong.**
Only if Case A isn't sufficient — e.g. a migration was mis-applied and left
the schema in a bad state.

1. Stop the backend (App Service) to prevent further writes.
2. Restore the pre-upgrade `pg_dump` backup taken in the UPGRADE
   pre-upgrade step (or the Phase 0 baseline backup,
   `docs/Evidence/sprint7_production_release/00_baseline/prod_backup_v2.0.0_2026-07-20.dump`,
   if nothing more recent exists) into the production database.
3. Redeploy the previous backend/frontend builds as in Case A.
4. Confirm row counts and a spot-check of known records match the backup's
   expected state before reopening the backend to traffic.

## After either rollback

- Record what triggered the rollback (which phase/step, what broke) —
  this becomes an input to fixing forward and re-attempting the v3.0.0
  deployment.
- Rotate the recovery-command signing key and any credentials that were
  touched during the failed deployment attempt if there's any chance they
  were exposed (e.g. printed to deploy logs).
- Do not delete the failed v3.0.0 build artifacts — keep them for postmortem
  before cleaning up.

## What this rollback does not cover

- Desktop/Android agents already upgraded to 3.0.0 in the field: they are
  backward-compatible with a v2.0.0 backend (the metrics/recovery contract
  didn't change), so no agent-side rollback is required.
- A destructive Phase 6 data-lifecycle deletion (none is planned against
  production this sprint — see `docs/releases/RELEASE_CHECKLIST.md` and the
  Sprint 7 roadmap's Phase 6 scope).
