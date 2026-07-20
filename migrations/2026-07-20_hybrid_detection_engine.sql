-- Hybrid Detection Engine (Sprint 4-6, Stage 1)
-- One purely additive table combining deterministic alert rules, the
-- statistical baseline, and IsolationForest into a single versioned
-- decision per feature window, plus one new column on devices. No existing
-- table is altered destructively (recovery_commands/alerts/incidents/
-- anomaly_predictions/telemetry_feature_windows stay untouched).
-- Hand-applied on existing databases; fresh dev databases get all of this
-- from Base.metadata.create_all (python -m app.db.init_db).
--
-- Rollback: DROP TABLE hybrid_decisions; ALTER TABLE devices DROP COLUMN criticality;
-- (safe — no pre-existing table has a foreign key into hybrid_decisions).

-- 1. Device business-criticality (used to weight operational_risk) ---------------
ALTER TABLE devices ADD COLUMN IF NOT EXISTS criticality VARCHAR(20) NOT NULL DEFAULT 'medium';
CREATE INDEX IF NOT EXISTS ix_devices_criticality ON devices(criticality);

-- 2. Hybrid decisions -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS hybrid_decisions (
    id UUID PRIMARY KEY,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    device_id UUID NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    feature_window_id UUID NOT NULL REFERENCES telemetry_feature_windows(id) ON DELETE CASCADE,
    rule_result JSONB NOT NULL,
    baseline_score DOUBLE PRECISION,
    model_prediction DOUBLE PRECISION,
    model_name VARCHAR(100),
    model_version VARCHAR(50),
    detector_agreement VARCHAR(30) NOT NULL,
    combined_severity VARCHAR(20) NOT NULL,
    operational_risk VARCHAR(20) NOT NULL,
    confidence VARCHAR(20) NOT NULL,
    affected_features JSONB NOT NULL DEFAULT '[]'::jsonb,
    explanation TEXT NOT NULL,
    scoring_policy_version VARCHAR(20) NOT NULL,
    alert_id UUID REFERENCES alerts(id) ON DELETE SET NULL,
    incident_id UUID REFERENCES incidents(id) ON DELETE SET NULL,
    recovery_command_id UUID REFERENCES recovery_commands(id) ON DELETE SET NULL,
    review_status VARCHAR(30) NOT NULL DEFAULT 'unreviewed',
    reviewed_by UUID REFERENCES users(id) ON DELETE SET NULL,
    reviewed_at TIMESTAMPTZ,
    review_note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_hybrid_decision_window_policy UNIQUE (feature_window_id, scoring_policy_version)
);
CREATE INDEX IF NOT EXISTS ix_hybrid_decisions_organization_id ON hybrid_decisions(organization_id);
CREATE INDEX IF NOT EXISTS ix_hybrid_decisions_device_id ON hybrid_decisions(device_id);
CREATE INDEX IF NOT EXISTS ix_hybrid_decisions_feature_window_id ON hybrid_decisions(feature_window_id);
CREATE INDEX IF NOT EXISTS ix_hybrid_decisions_detector_agreement ON hybrid_decisions(detector_agreement);
CREATE INDEX IF NOT EXISTS ix_hybrid_decisions_combined_severity ON hybrid_decisions(combined_severity);
CREATE INDEX IF NOT EXISTS ix_hybrid_decisions_operational_risk ON hybrid_decisions(operational_risk);
CREATE INDEX IF NOT EXISTS ix_hybrid_decisions_scoring_policy_version ON hybrid_decisions(scoring_policy_version);
CREATE INDEX IF NOT EXISTS ix_hybrid_decisions_review_status ON hybrid_decisions(review_status);
CREATE INDEX IF NOT EXISTS ix_hybrid_decisions_created_at ON hybrid_decisions(created_at);
