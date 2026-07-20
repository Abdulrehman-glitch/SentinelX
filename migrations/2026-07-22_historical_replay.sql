-- Historical Replay (Sprint 4-6, Stage 3)
-- One purely additive, audit-only table. Replay itself never writes to any
-- production table (anomaly_predictions, hybrid_decisions, alerts,
-- incidents, recovery_commands are all read-only from replay's point of
-- view) — this table only records who ran a replay and its parameters.
-- Hand-applied on existing databases; fresh dev databases get this from
-- Base.metadata.create_all (python -m app.db.init_db).
--
-- Rollback: DROP TABLE replay_runs;
-- (safe — no pre-existing table has a foreign key into replay_runs).

CREATE TABLE IF NOT EXISTS replay_runs (
    id UUID PRIMARY KEY,
    requested_by UUID REFERENCES users(id) ON DELETE SET NULL,
    device_class VARCHAR(50) NOT NULL,
    model_version VARCHAR(50),
    scoring_policy_version VARCHAR(20) NOT NULL,
    period_start TIMESTAMPTZ NOT NULL,
    period_end TIMESTAMPTZ NOT NULL,
    windows_considered INTEGER NOT NULL,
    decisions_count INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_replay_runs_device_class ON replay_runs(device_class);
CREATE INDEX IF NOT EXISTS ix_replay_runs_created_at ON replay_runs(created_at);
