-- Model Lifecycle & Evaluation (Sprint 4-6, Stage 2)
-- Adds governed lifecycle columns to anomaly_models and one new purely
-- additive table for evaluation reports. No existing table is altered
-- destructively; is_active keeps its current meaning and behavior.
-- Hand-applied on existing databases; fresh dev databases get all of this
-- from Base.metadata.create_all (python -m app.db.init_db).
--
-- Rollback: DROP TABLE model_evaluation_reports;
-- ALTER TABLE anomaly_models DROP COLUMN lifecycle_status, DROP COLUMN
-- artifact_checksum, DROP COLUMN promoted_by, DROP COLUMN promoted_at;
-- (safe — no pre-existing table has a foreign key into model_evaluation_reports).

-- 1. Governed lifecycle columns on anomaly_models --------------------------------
ALTER TABLE anomaly_models ADD COLUMN IF NOT EXISTS lifecycle_status VARCHAR(20) NOT NULL DEFAULT 'shadow';
ALTER TABLE anomaly_models ADD COLUMN IF NOT EXISTS artifact_checksum VARCHAR(64);
ALTER TABLE anomaly_models ADD COLUMN IF NOT EXISTS promoted_by UUID REFERENCES users(id) ON DELETE SET NULL;
ALTER TABLE anomaly_models ADD COLUMN IF NOT EXISTS promoted_at TIMESTAMPTZ;
CREATE INDEX IF NOT EXISTS ix_anomaly_models_lifecycle_status ON anomaly_models(lifecycle_status);

-- 2. Model evaluation reports ------------------------------------------------------
CREATE TABLE IF NOT EXISTS model_evaluation_reports (
    id UUID PRIMARY KEY,
    model_id UUID NOT NULL REFERENCES anomaly_models(id) ON DELETE CASCADE,
    period_start TIMESTAMPTZ NOT NULL,
    period_end TIMESTAMPTZ NOT NULL,
    prediction_count INTEGER NOT NULL,
    reviewed_count INTEGER NOT NULL,
    true_positives INTEGER NOT NULL,
    false_positives INTEGER NOT NULL,
    expected_changes INTEGER NOT NULL,
    precision DOUBLE PRECISION,
    false_positive_rate DOUBLE PRECISION,
    detector_agreement_breakdown JSONB NOT NULL DEFAULT '{}'::jsonb,
    supported_device_coverage INTEGER NOT NULL,
    missing_feature_rate DOUBLE PRECISION,
    inference_failures INTEGER,
    anomaly_lead_time_seconds_avg DOUBLE PRECISION,
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_model_evaluation_reports_model_id ON model_evaluation_reports(model_id);
CREATE INDEX IF NOT EXISTS ix_model_evaluation_reports_created_at ON model_evaluation_reports(created_at);
