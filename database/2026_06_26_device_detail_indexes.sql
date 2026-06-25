-- SentinelX device detail query indexes
-- Purpose:
-- Improve read performance for device detail pages, latest metrics,
-- metric history, recent alerts, heartbeats, and recovery action lookups.

CREATE INDEX IF NOT EXISTS ix_system_metrics_device_recorded_at
ON system_metrics (device_id, recorded_at DESC);

CREATE INDEX IF NOT EXISTS ix_alerts_device_created_at
ON alerts (device_id, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_recovery_actions_device_created_at
ON recovery_actions (device_id, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_agent_heartbeats_device_recorded_at
ON agent_heartbeats (device_id, recorded_at DESC);