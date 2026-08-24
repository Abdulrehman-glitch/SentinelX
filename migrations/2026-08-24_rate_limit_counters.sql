-- Shared rate-limit counters (v3.3).
--
-- app/core/rate_limit_storage.py also issues this DDL at startup, because a
-- rate limiter that refuses to start until someone has run a migration is a
-- rate limiter that gets switched off. That belt-and-braces is deliberate,
-- but it must not be the only place the table is defined: an existing
-- database is upgraded through migrations/, and a table that only ever
-- appears as a side effect of application start is invisible to anyone
-- reading the schema history.
--
-- Idempotent, like every migration here: safe to apply to a database where
-- the application has already created the table.

CREATE TABLE IF NOT EXISTS rate_limit_counters (
    bucket_key  TEXT PRIMARY KEY,
    count       BIGINT      NOT NULL,
    expires_at  TIMESTAMPTZ NOT NULL
);

-- The worker prunes expired windows using this
-- (maintenance.prune_rate_limits, every 6 hours). Correctness never depended
-- on the prune - an expired row is replaced rather than added to by the
-- increment that finds it - so this index is for housekeeping, and for an
-- operator asking what is currently throttled.
CREATE INDEX IF NOT EXISTS ix_rate_limit_counters_expires_at
    ON rate_limit_counters (expires_at);
