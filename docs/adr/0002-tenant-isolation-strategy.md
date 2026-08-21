# ADR 0002 — Tenant isolation stays in the application layer; RLS is deferred

- **Status:** Accepted
- **Date:** 2026-08-21

## Context

Every tenant-owned table carries `organization_id`, and isolation is enforced
in application code through `app/services/tenant.py`: `org_condition()` on list
queries, `assert_same_org()` on id lookups, `get_scoped_device_or_404()` for
device-scoped routes. `platform_admin` is exempt and sees across tenants.

PostgreSQL Row Level Security was evaluated as defence in depth: a policy such
as `USING (organization_id = current_setting('sentinelx.org_id')::uuid)` would
make a missing `WHERE` clause in a new query fail closed instead of leaking.

## Decision

**Keep application-layer scoping. Do not adopt RLS in this sprint.** Compensate
with the comprehensive automated isolation suite in
`tests/backend/test_tenant_isolation.py` (25 tests).

### Why RLS is deferred rather than adopted

1. **`platform_admin` would become brittle.** Cross-tenant access is a real,
   used capability. Under RLS it needs either `BYPASSRLS` on a second role, or
   a sentinel GUC value that policies special-case. Both put a "see everything"
   switch in session state; a single missing `SET LOCAL` on a pooled connection
   silently converts a tenant request into a platform-admin one. That is a
   worse failure than the one RLS is being adopted to prevent.

2. **Session state and connection pooling are a genuine hazard here.**
   SQLAlchemy's pool reuses connections across requests. RLS would require a
   `SET LOCAL sentinelx.org_id` on every checkout *and* a guaranteed reset on
   return. Any path that gets this wrong — a background job, the migration
   runner, `apply_migrations`, the retention prune, the observability pipeline,
   the replay service — either sees nothing or sees everything.

3. **Partial protection is actively misleading.** Not every table is
   tenant-scoped (`organizations`, `schema_migrations`, `anomaly_models`), and
   several services legitimately operate across tenants. RLS covering only some
   tables would create a false sense that "the database enforces it", which is
   precisely the belief that stops people writing the application-level checks
   that actually do the work today.

4. **The failure mode RLS prevents is already covered by tests.** The concrete
   risk is a new query forgetting its org filter. `test_tenant_isolation.py`
   asserts, per resource family, that list endpoints exclude other tenants and
   that id endpoints answer 404 — so that mistake fails in CI. Tests are not as
   strong as a database guarantee, but they are strong against *this* mistake
   and carry none of the operational hazards above.

### What would change the decision

Adopt RLS when any of these becomes true:

- a second application or a direct SQL/BI consumer gains access to the database
  (at that point the application layer is no longer the only door);
- connections stop being shared across tenant requests (per-tenant pools or a
  request-scoped connection make the `SET LOCAL` contract enforceable);
- `platform_admin` moves to a separate service or role with its own credentials,
  removing the need for an in-session bypass.

## Consequences

- Isolation correctness depends on reviewers and tests, so
  `tests/backend/test_tenant_isolation.py` must grow whenever a tenant-owned
  resource family is added. It is not an example suite; it is the guarantee.
- Id endpoints answer **404, not 403**, for another tenant's rows. A 403 would
  confirm the row exists and turn every id route into an existence oracle for
  enumerating a rival's fleet. The tests assert 404 specifically.
- An org-less, non-platform-admin user is refused (403) rather than treated as
  matching `organization_id IS NULL` — asserted, because that is the shape a
  "fail open" bug would take.
