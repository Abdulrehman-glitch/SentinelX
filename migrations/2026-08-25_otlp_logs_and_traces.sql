-- OTLP logs and traces (v4).
--
-- Two append-heavy tables, shaped like metric_points: a composite primary key
-- leading with time so range partitioning stays a migration rather than a
-- table rewrite, a BRIN index over that time column because rows arrive in
-- rough order, and a GIN index over the JSONB attribute bag so an attribute
-- filter is a scan of the index rather than of the table.
--
-- service_name / environment / service_version are denormalised off the
-- resource on purpose. Every meaningful log or trace query filters on them,
-- and joining `resources` for each one would put a join in front of the most
-- common query in the product.
--
-- Idempotent, like every migration here.

CREATE TABLE IF NOT EXISTS log_records (
    observed_at              TIMESTAMPTZ NOT NULL,
    id                       UUID        NOT NULL,
    organization_id          UUID        NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    resource_id              UUID        NOT NULL REFERENCES resources(id)     ON DELETE CASCADE,
    timestamp                TIMESTAMPTZ,
    severity_number          SMALLINT    NOT NULL DEFAULT 0,
    severity_text            VARCHAR(32),
    severity_band            VARCHAR(16) NOT NULL DEFAULT 'unspecified',
    body                     TEXT,
    attributes               JSONB       NOT NULL DEFAULT '{}'::jsonb,
    trace_id                 VARCHAR(32),
    span_id                  VARCHAR(16),
    scope_name               VARCHAR(255),
    scope_version            VARCHAR(63),
    service_name             VARCHAR(255),
    environment              VARCHAR(63),
    service_version          VARCHAR(63),
    dropped_attributes_count INTEGER     NOT NULL DEFAULT 0,
    redacted_keys            JSONB,
    ingested_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (observed_at, id)
);

CREATE INDEX IF NOT EXISTS ix_log_records_org_observed
    ON log_records (organization_id, observed_at);
CREATE INDEX IF NOT EXISTS ix_log_records_org_trace
    ON log_records (organization_id, trace_id);
CREATE INDEX IF NOT EXISTS ix_log_records_org_service_severity
    ON log_records (organization_id, service_name, severity_band, observed_at);
CREATE INDEX IF NOT EXISTS ix_log_records_severity_band
    ON log_records (severity_band);
CREATE INDEX IF NOT EXISTS ix_log_records_resource
    ON log_records (resource_id, observed_at);
CREATE INDEX IF NOT EXISTS ix_log_records_attributes
    ON log_records USING gin (attributes);
CREATE INDEX IF NOT EXISTS ix_log_records_observed_brin
    ON log_records USING brin (observed_at) WITH (pages_per_range = 128);


CREATE TABLE IF NOT EXISTS spans (
    start_time               TIMESTAMPTZ  NOT NULL,
    id                       UUID         NOT NULL,
    organization_id          UUID         NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    resource_id              UUID         NOT NULL REFERENCES resources(id)     ON DELETE CASCADE,
    trace_id                 VARCHAR(32)  NOT NULL,
    span_id                  VARCHAR(16)  NOT NULL,
    parent_span_id           VARCHAR(16),
    name                     VARCHAR(255) NOT NULL,
    kind                     VARCHAR(16)  NOT NULL DEFAULT 'unspecified',
    end_time                 TIMESTAMPTZ  NOT NULL,
    duration_ns              BIGINT       NOT NULL DEFAULT 0,
    status_code              VARCHAR(8)   NOT NULL DEFAULT 'unset',
    status_message           TEXT,
    attributes               JSONB        NOT NULL DEFAULT '{}'::jsonb,
    events                   JSONB,
    scope_name               VARCHAR(255),
    scope_version            VARCHAR(63),
    service_name             VARCHAR(255),
    environment              VARCHAR(63),
    service_version          VARCHAR(63),
    dropped_attributes_count INTEGER      NOT NULL DEFAULT 0,
    dropped_events_count     INTEGER      NOT NULL DEFAULT 0,
    redacted_keys            JSONB,
    ingested_at              TIMESTAMPTZ  NOT NULL DEFAULT now(),
    PRIMARY KEY (start_time, id)
);

-- (trace_id, span_id) is unique by definition in OTLP. Enforcing it is what
-- makes a collector's retry after a timeout idempotent instead of a permanent
-- duplication of the trace.
CREATE UNIQUE INDEX IF NOT EXISTS uq_spans_org_trace_span
    ON spans (organization_id, trace_id, span_id);

CREATE INDEX IF NOT EXISTS ix_spans_org_trace
    ON spans (organization_id, trace_id);
CREATE INDEX IF NOT EXISTS ix_spans_org_start
    ON spans (organization_id, start_time);
CREATE INDEX IF NOT EXISTS ix_spans_org_service_start
    ON spans (organization_id, service_name, start_time);
CREATE INDEX IF NOT EXISTS ix_spans_org_status_start
    ON spans (organization_id, status_code, start_time);
CREATE INDEX IF NOT EXISTS ix_spans_org_duration
    ON spans (organization_id, service_name, duration_ns);
CREATE INDEX IF NOT EXISTS ix_spans_attributes
    ON spans USING gin (attributes);
CREATE INDEX IF NOT EXISTS ix_spans_start_brin
    ON spans USING brin (start_time) WITH (pages_per_range = 128);
