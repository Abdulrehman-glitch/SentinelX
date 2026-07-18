-- AI Observability Foundation (audit sprint 2)
-- Shadow-mode anomaly detection: three new, purely additive tables. No
-- existing table is altered. Hand-applied on existing databases; fresh dev
-- databases get all of this from Base.metadata.create_all (python -m app.db.init_db).
--
-- Rollback: DROP TABLE anomaly_predictions, telemetry_feature_windows, anomaly_models;
-- (safe — no pre-existing table has a foreign key into any of these three).

-- 1. Rolling feature windows --------------------------------------------------
CREATE TABLE IF NOT EXISTS telemetry_feature_windows (
    id UUID PRIMARY KEY,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    device_id UUID NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    device_class VARCHAR(50) NOT NULL,
    feature_schema_version VARCHAR(20) NOT NULL,
    window_start TIMESTAMPTZ NOT NULL,
    window_end TIMESTAMPTZ NOT NULL,
    sample_count INTEGER NOT NULL,
    quality_score DOUBLE PRECISION NOT NULL,
    quality_flags JSONB,
    features JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_feature_window_device_schema_start UNIQUE (device_id, feature_schema_version, window_start)
);
CREATE INDEX IF NOT EXISTS ix_telemetry_feature_windows_organization_id ON telemetry_feature_windows(organization_id);
CREATE INDEX IF NOT EXISTS ix_telemetry_feature_windows_device_id ON telemetry_feature_windows(device_id);
CREATE INDEX IF NOT EXISTS ix_telemetry_feature_windows_device_class ON telemetry_feature_windows(device_class);
CREATE INDEX IF NOT EXISTS ix_telemetry_feature_windows_feature_schema_version ON telemetry_feature_windows(feature_schema_version);
CREATE INDEX IF NOT EXISTS ix_telemetry_feature_windows_device_window_end ON telemetry_feature_windows (device_id, window_end DESC);

-- 2. Model registry -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS anomaly_models (
    id UUID PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    version VARCHAR(50) NOT NULL,
    device_class VARCHAR(50) NOT NULL,
    feature_schema_version VARCHAR(20) NOT NULL,
    algorithm VARCHAR(50) NOT NULL,
    hyperparameters JSONB NOT NULL,
    dataset_hash VARCHAR(64) NOT NULL,
    code_commit VARCHAR(40),
    trained_at TIMESTAMPTZ NOT NULL,
    artifact_path VARCHAR(500),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_anomaly_model_name_version UNIQUE (name, version)
);
CREATE INDEX IF NOT EXISTS ix_anomaly_models_name ON anomaly_models(name);
CREATE INDEX IF NOT EXISTS ix_anomaly_models_device_class ON anomaly_models(device_class);
CREATE INDEX IF NOT EXISTS ix_anomaly_models_is_active ON anomaly_models(is_active);

-- 3. Predictions (shadow mode, human-reviewable) ------------------------------
CREATE TABLE IF NOT EXISTS anomaly_predictions (
    id UUID PRIMARY KEY,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    device_id UUID NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    feature_window_id UUID NOT NULL REFERENCES telemetry_feature_windows(id) ON DELETE CASCADE,
    model_name VARCHAR(100) NOT NULL,
    model_version VARCHAR(50) NOT NULL,
    feature_schema_version VARCHAR(20) NOT NULL,
    anomaly_score DOUBLE PRECISION NOT NULL,
    threshold DOUBLE PRECISION NOT NULL,
    is_anomalous BOOLEAN NOT NULL,
    confidence VARCHAR(20) NOT NULL,
    feature_comparison JSONB NOT NULL,
    explanation TEXT NOT NULL,
    shadow_mode BOOLEAN NOT NULL DEFAULT TRUE,
    review_status VARCHAR(30) NOT NULL DEFAULT 'unreviewed',
    reviewed_by UUID REFERENCES users(id) ON DELETE SET NULL,
    reviewed_at TIMESTAMPTZ,
    review_note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_anomaly_prediction_window_model UNIQUE (feature_window_id, model_name)
);
CREATE INDEX IF NOT EXISTS ix_anomaly_predictions_organization_id ON anomaly_predictions(organization_id);
CREATE INDEX IF NOT EXISTS ix_anomaly_predictions_device_id ON anomaly_predictions(device_id);
CREATE INDEX IF NOT EXISTS ix_anomaly_predictions_feature_window_id ON anomaly_predictions(feature_window_id);
CREATE INDEX IF NOT EXISTS ix_anomaly_predictions_model_name ON anomaly_predictions(model_name);
CREATE INDEX IF NOT EXISTS ix_anomaly_predictions_review_status ON anomaly_predictions(review_status);
CREATE INDEX IF NOT EXISTS ix_anomaly_predictions_device_created_at ON anomaly_predictions (device_id, created_at DESC);
