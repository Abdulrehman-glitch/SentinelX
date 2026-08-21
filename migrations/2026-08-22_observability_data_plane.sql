-- SentinelX v3.3 — Observability Data Plane
--
-- Brings an existing database up to the schema Base.metadata.create_all now
-- produces. Purely additive: six new tables, no existing table altered and
-- nothing dropped, so `system_metrics` and every feature built on it keep
-- working untouched while telemetry migrates to the canonical model.
--
-- Idempotent throughout (IF NOT EXISTS), as apply_migrations.py requires.

-- ─────────────────────────────────────────────────────────────────────────
-- resources — the canonical "observable thing"
--
-- Identity is the SHA-256 of the canonical identifying attribute set.
-- collision_seq exists so two genuinely different attribute sets that happen
-- to hash alike stay distinct rows; the lookup path compares the JSONB and
-- never trusts the hash alone.
-- ─────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS resources (
    id                      UUID NOT NULL,
    organization_id         UUID NOT NULL,
    resource_type           VARCHAR(32) NOT NULL,
    identity_hash           VARCHAR(64) NOT NULL,
    collision_seq           INTEGER NOT NULL,
    identifying_attributes  JSONB NOT NULL,
    attributes              JSONB NOT NULL,
    device_id               UUID,
    display_name            VARCHAR(255),
    first_seen_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at            TIMESTAMPTZ,
    PRIMARY KEY (id),
    CONSTRAINT uq_resource_org_identity UNIQUE (organization_id, identity_hash, collision_seq),
    FOREIGN KEY (organization_id) REFERENCES organizations (id) ON DELETE CASCADE,
    FOREIGN KEY (device_id) REFERENCES devices (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_resources_device_id ON resources (device_id);
CREATE INDEX IF NOT EXISTS ix_resources_last_seen_at ON resources (last_seen_at);

-- ─────────────────────────────────────────────────────────────────────────
-- metric_series — resource + name + unit + kind + canonical attributes
--
-- One row per distinct measured thing. This is where cardinality becomes a
-- countable quantity rather than a hope.
-- ─────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS metric_series (
    id                UUID NOT NULL,
    organization_id   UUID NOT NULL,
    resource_id       UUID NOT NULL,
    metric_name       VARCHAR(255) NOT NULL,
    metric_unit       VARCHAR(63),
    metric_kind       VARCHAR(16) NOT NULL,
    attributes        JSONB NOT NULL,
    series_hash       VARCHAR(64) NOT NULL,
    collision_seq     INTEGER NOT NULL,
    source            VARCHAR(32) NOT NULL,
    first_seen_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at      TIMESTAMPTZ,
    PRIMARY KEY (id),
    CONSTRAINT uq_metric_series_org_hash UNIQUE (organization_id, series_hash, collision_seq),
    FOREIGN KEY (organization_id) REFERENCES organizations (id) ON DELETE CASCADE,
    FOREIGN KEY (resource_id) REFERENCES resources (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_metric_series_org_name ON metric_series (organization_id, metric_name);
CREATE INDEX IF NOT EXISTS ix_metric_series_resource_id ON metric_series (resource_id);
-- The cardinality budget counts new series per tenant per window on every
-- ingest request; without this it is a sequential scan.
CREATE INDEX IF NOT EXISTS ix_metric_series_org_first_seen ON metric_series (organization_id, first_seen_at);

-- ─────────────────────────────────────────────────────────────────────────
-- metric_points — the only table expected to reach eight figures
--
-- The primary key deliberately leads with recorded_at rather than id.
-- Postgres requires the partition key to appear in every unique constraint,
-- so this shape means introducing PARTITION BY RANGE (recorded_at) later is a
-- migration instead of a full table rewrite. See ADR 0010 for the measured
-- threshold at which that becomes worth doing.
--
-- BRIN on recorded_at because points arrive in rough timestamp order, which
-- is exactly the physical correlation BRIN needs, at a fraction of a B-tree's
-- size. The B-tree on (series_id, recorded_at) serves the actual query shape:
-- one series over one time range.
-- ─────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS metric_points (
    recorded_at      TIMESTAMPTZ NOT NULL,
    id               UUID NOT NULL,
    organization_id  UUID NOT NULL,
    series_id        UUID NOT NULL,
    value            DOUBLE PRECISION NOT NULL,
    event_id         UUID,
    ingested_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (recorded_at, id),
    -- Idempotent ingest. NULLs are distinct in Postgres, so points without a
    -- client event id (the usual OTLP case) are unconstrained.
    CONSTRAINT uq_metric_point_series_event UNIQUE (series_id, event_id),
    FOREIGN KEY (organization_id) REFERENCES organizations (id) ON DELETE CASCADE,
    FOREIGN KEY (series_id) REFERENCES metric_series (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_metric_points_series_time ON metric_points (series_id, recorded_at);
CREATE INDEX IF NOT EXISTS ix_metric_points_org_time ON metric_points (organization_id, recorded_at);
CREATE INDEX IF NOT EXISTS ix_metric_points_recorded_at_brin
    ON metric_points USING brin (recorded_at) WITH (pages_per_range = 128);

-- ─────────────────────────────────────────────────────────────────────────
-- ingest_credentials — organisation-scoped OTLP keys
--
-- A third credential type, separate from browser sessions and device tokens.
-- Only the SHA-256 is stored; the plaintext is shown once at creation.
-- ─────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ingest_credentials (
    id                   UUID NOT NULL,
    organization_id      UUID NOT NULL,
    name                 VARCHAR(120) NOT NULL,
    key_prefix           VARCHAR(16) NOT NULL,
    key_last_four        VARCHAR(4) NOT NULL,
    token_hash           VARCHAR(64) NOT NULL,
    scopes               JSONB NOT NULL,
    created_by_user_id   UUID,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_used_at         TIMESTAMPTZ,
    revoked_at           TIMESTAMPTZ,
    expires_at           TIMESTAMPTZ,
    PRIMARY KEY (id),
    FOREIGN KEY (organization_id) REFERENCES organizations (id) ON DELETE CASCADE,
    FOREIGN KEY (created_by_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_ingest_credentials_token_hash ON ingest_credentials (token_hash);
CREATE INDEX IF NOT EXISTS ix_ingest_credentials_org_active ON ingest_credentials (organization_id, revoked_at);

-- ─────────────────────────────────────────────────────────────────────────
-- outbox_jobs — durable downstream work
--
-- Written in the SAME transaction as the telemetry it describes, which is the
-- guarantee a broker cannot give without two-phase commit: there is no window
-- where the sample committed but the follow-up work vanished.
--
-- Kept deliberately thin on indexes. This table is written on every enqueue
-- and again on every state transition, so each index is paid repeatedly:
-- ix_outbox_claimable is the worker's claim query, ix_outbox_lease_expiry
-- reclaims work abandoned by a crashed worker, created_at drives retention.
-- ─────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS outbox_jobs (
    id                UUID NOT NULL,
    organization_id   UUID,
    job_type          VARCHAR(64) NOT NULL,
    payload           JSONB NOT NULL,
    dedupe_key        VARCHAR(255),
    status            VARCHAR(16) NOT NULL,
    attempts          INTEGER NOT NULL,
    max_attempts      INTEGER NOT NULL,
    run_after         TIMESTAMPTZ NOT NULL DEFAULT now(),
    lease_expires_at  TIMESTAMPTZ,
    claimed_by        VARCHAR(64),
    last_error        TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ,
    completed_at      TIMESTAMPTZ,
    PRIMARY KEY (id),
    -- Makes enqueueing idempotent: re-ingesting a batch must not schedule the
    -- same downstream work twice.
    CONSTRAINT uq_outbox_dedupe_key UNIQUE (dedupe_key),
    FOREIGN KEY (organization_id) REFERENCES organizations (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_outbox_claimable ON outbox_jobs (status, run_after);
CREATE INDEX IF NOT EXISTS ix_outbox_lease_expiry ON outbox_jobs (lease_expires_at);
CREATE INDEX IF NOT EXISTS ix_outbox_jobs_created_at ON outbox_jobs (created_at);

-- ─────────────────────────────────────────────────────────────────────────
-- domain_events — the replayable history behind the live stream
--
-- Written before publishing to Valkey, so a browser that missed a pub/sub
-- message can recover it. Postgres is the history; Valkey is only the fast
-- path and is never the only copy.
-- ─────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS domain_events (
    id               UUID NOT NULL,
    sequence         BIGINT GENERATED BY DEFAULT AS IDENTITY,
    organization_id  UUID NOT NULL,
    event_type       VARCHAR(64) NOT NULL,
    device_id        UUID,
    resource_id      UUID,
    payload          JSONB NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    UNIQUE (sequence),
    FOREIGN KEY (organization_id) REFERENCES organizations (id) ON DELETE CASCADE,
    FOREIGN KEY (device_id) REFERENCES devices (id) ON DELETE CASCADE,
    FOREIGN KEY (resource_id) REFERENCES resources (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_domain_events_org_sequence ON domain_events (organization_id, sequence);
CREATE INDEX IF NOT EXISTS ix_domain_events_created_at ON domain_events (created_at);
