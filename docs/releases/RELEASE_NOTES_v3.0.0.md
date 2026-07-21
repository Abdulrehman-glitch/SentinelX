# SentinelX v3.0.0 Release Notes

**Status: DRAFT — living document, updated as each Sprint 7 phase completes.
Not final until Phase 12 (tag & final report).**

## What this release is

v3.0.0 is a production-hardening release. It does not add end-user features;
it makes the platform built across Sprints 1–6 (trusted-agent enrolment, AI
observability shadow mode, signed recovery orchestration, hybrid detection,
model lifecycle governance, historical replay) safe to operate as a real
production service: versioned, migration-tracked, tested end-to-end, CI'd,
security-reviewed, observable, and documented.

If you are only interested in product capability, nothing in this release
changes how the platform behaves for a device, an operator, or an
administrator — see `CHANGELOG.md`'s 2.0.0-and-earlier section for the
feature history this release hardens.

## Highlights (filled in per phase)

- **Versioning** — backend, frontend, desktop agent, and Android agent now
  all report `3.0.0`. `GET /api/v1/health` includes `commit_sha` so a running
  deployment can be tied to an exact commit.
- **Deterministic migrations** — *(Phase 2, pending)*
- **CI/CD** — *(Phase 3, pending)*
- **Security hardening** — *(Phase 4, pending)*
- **Observability** — *(Phase 5, pending)*
- **Data lifecycle** — *(Phase 6, pending)*
- **Staging & load testing** — *(Phase 7, pending)*
- **Desktop installer** — *(Phase 8, pending)*
- **Android release** — *(Phase 9, pending)*
- **Frontend readiness & docs** — *(Phase 10, pending)*

## Upgrading

See `docs/releases/UPGRADE_v2_to_v3.md`. In short: this is an additive
release — no destructive schema changes, no breaking API changes for
existing agents. The main upgrade action is bringing the production database
schema current, since Phase 0's baseline audit found production still on a
pre-Sprint-1 schema despite running newer backend code.

## Rolling back

See `docs/releases/ROLLBACK_v3_to_v2.md` if a production deployment of this
release needs to be reverted.

## Known limitations carried into this release

- No token blacklist — logout is audit-log only (unchanged design decision,
  not a regression).
- No Alembic — schema changes are hand-applied SQL files under `migrations/`;
  Phase 2 adds a tracking table and idempotent apply script, not a migration
  framework swap.
- iOS agent and Expo mobile scaffold are not part of this release's version
  bump or deployment gate — they continue on their own tracks.
