-- Trusted Agent Foundation (audit sprint 1)
-- Hand-applied on existing databases; fresh dev databases get all of this
-- from Base.metadata.create_all (python -m app.db.init_db).

-- 1. Enrolment codes -------------------------------------------------------
CREATE TABLE IF NOT EXISTS enrollment_codes (
    id UUID PRIMARY KEY,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    code_hash VARCHAR(500) NOT NULL,
    code_preview VARCHAR(100) NOT NULL,
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,
    used_by_device_id UUID REFERENCES devices(id) ON DELETE SET NULL,
    revoked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_enrollment_codes_organization_id ON enrollment_codes(organization_id);
CREATE INDEX IF NOT EXISTS ix_enrollment_codes_code_preview ON enrollment_codes(code_preview);

-- 2. Credential lifecycle --------------------------------------------------
ALTER TABLE device_credentials
    ADD COLUMN IF NOT EXISTS last_used_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS replaces_credential_id UUID REFERENCES device_credentials(id) ON DELETE SET NULL;

-- 3. Telemetry idempotency + unified mobile contract ------------------------
ALTER TABLE system_metrics
    ADD COLUMN IF NOT EXISTS event_id UUID,
    ADD COLUMN IF NOT EXISTS battery_temperature_c DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS thermal_status VARCHAR(32),
    ADD COLUMN IF NOT EXISTS network_validated BOOLEAN,
    ADD COLUMN IF NOT EXISTS network_metered BOOLEAN;

-- Unknown CPU must be storable as NULL (mobile agents), never fabricated 0%.
ALTER TABLE system_metrics ALTER COLUMN cpu_percent DROP NOT NULL;

-- Retried uploads cannot duplicate a sample. NULL event_ids (legacy agents)
-- are exempt because Postgres treats NULLs as distinct.
ALTER TABLE system_metrics
    ADD CONSTRAINT uq_metric_device_event UNIQUE (device_id, event_id);
