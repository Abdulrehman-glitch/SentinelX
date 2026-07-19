-- Safe Recovery Orchestration (Sprint 3)
-- Signed, verifiable, allowlisted recovery commands connecting the backend
-- to the desktop and Android agents. Four new, purely additive tables. No
-- existing table is altered or replaced (recovery_actions stays untouched).
-- Hand-applied on existing databases; fresh dev databases get all of this
-- from Base.metadata.create_all (python -m app.db.init_db).
--
-- Rollback: DROP TABLE recovery_command_events, agent_capabilities,
-- recovery_commands, recovery_policies;
-- (safe — no pre-existing table has a foreign key into any of these four;
-- drop child-to-parent order: events -> capabilities -> commands -> policies).

-- 1. Deterministic recovery policies -------------------------------------------
CREATE TABLE IF NOT EXISTS recovery_policies (
    id UUID PRIMARY KEY,
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    device_class VARCHAR(50),
    action_type VARCHAR(100) NOT NULL,
    trigger_conditions JSONB,
    risk_level VARCHAR(20) NOT NULL,
    approval_mode VARCHAR(20) NOT NULL,
    cooldown_seconds INTEGER NOT NULL DEFAULT 300,
    daily_execution_limit INTEGER NOT NULL DEFAULT 5,
    verification_window_seconds INTEGER NOT NULL DEFAULT 300,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_recovery_policies_organization_id ON recovery_policies(organization_id);
CREATE INDEX IF NOT EXISTS ix_recovery_policies_action_type ON recovery_policies(action_type);
CREATE INDEX IF NOT EXISTS ix_recovery_policies_enabled ON recovery_policies(enabled);

-- 2. Recovery command lifecycle -------------------------------------------------
CREATE TABLE IF NOT EXISTS recovery_commands (
    id UUID PRIMARY KEY,
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    device_id UUID NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    incident_id UUID REFERENCES incidents(id) ON DELETE SET NULL,
    alert_id UUID REFERENCES alerts(id) ON DELETE SET NULL,
    anomaly_prediction_id UUID REFERENCES anomaly_predictions(id) ON DELETE SET NULL,
    action_type VARCHAR(100) NOT NULL,
    parameters_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    risk_level VARCHAR(20) NOT NULL,
    reason TEXT,
    decision_source VARCHAR(20) NOT NULL DEFAULT 'manual',
    confidence DOUBLE PRECISION,
    status VARCHAR(30) NOT NULL DEFAULT 'proposed',
    approval_mode VARCHAR(20) NOT NULL DEFAULT 'manual',
    approved_by UUID REFERENCES users(id) ON DELETE SET NULL,
    approved_at TIMESTAMPTZ,
    command_nonce VARCHAR(64),
    payload_hash VARCHAR(64),
    signature TEXT,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    dispatched_at TIMESTAMPTZ,
    acknowledged_at TIMESTAMPTZ,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    result_code VARCHAR(50),
    result_message TEXT,
    result_data_json JSONB,
    pre_action_snapshot_json JSONB,
    post_action_snapshot_json JSONB,
    verification_status VARCHAR(20),
    verification_message TEXT,
    model_name VARCHAR(100),
    model_version VARCHAR(50),
    policy_id UUID REFERENCES recovery_policies(id) ON DELETE SET NULL,
    CONSTRAINT uq_recovery_command_nonce UNIQUE (command_nonce)
);
CREATE INDEX IF NOT EXISTS ix_recovery_commands_organization_id ON recovery_commands(organization_id);
CREATE INDEX IF NOT EXISTS ix_recovery_commands_device_id ON recovery_commands(device_id);
CREATE INDEX IF NOT EXISTS ix_recovery_commands_action_type ON recovery_commands(action_type);
CREATE INDEX IF NOT EXISTS ix_recovery_commands_status ON recovery_commands(status);
CREATE INDEX IF NOT EXISTS ix_recovery_commands_device_created_at ON recovery_commands (device_id, created_at DESC);

-- 3. Append-only command event timeline -----------------------------------------
CREATE TABLE IF NOT EXISTS recovery_command_events (
    id UUID PRIMARY KEY,
    command_id UUID NOT NULL REFERENCES recovery_commands(id) ON DELETE CASCADE,
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL,
    previous_status VARCHAR(30),
    new_status VARCHAR(30),
    actor_type VARCHAR(20) NOT NULL,
    actor_id VARCHAR(255),
    message TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_recovery_command_events_command_id ON recovery_command_events(command_id);
CREATE INDEX IF NOT EXISTS ix_recovery_command_events_organization_id ON recovery_command_events(organization_id);
CREATE INDEX IF NOT EXISTS ix_recovery_command_events_command_created_at ON recovery_command_events (command_id, created_at);

-- 4. Agent capability registry ---------------------------------------------------
CREATE TABLE IF NOT EXISTS agent_capabilities (
    id UUID PRIMARY KEY,
    device_id UUID NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    agent_type VARCHAR(50) NOT NULL,
    agent_version VARCHAR(50) NOT NULL,
    action_type VARCHAR(100) NOT NULL,
    action_version VARCHAR(20) NOT NULL DEFAULT '1',
    local_risk_level VARCHAR(20) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_agent_capability_device_action UNIQUE (device_id, action_type)
);
CREATE INDEX IF NOT EXISTS ix_agent_capabilities_device_id ON agent_capabilities(device_id);
CREATE INDEX IF NOT EXISTS ix_agent_capabilities_organization_id ON agent_capabilities(organization_id);
CREATE INDEX IF NOT EXISTS ix_agent_capabilities_action_type ON agent_capabilities(action_type);
