-- SentinelX operations feature indexes
-- Tables are created by SQLAlchemy create_all during the current MVP phase.
-- These indexes improve read performance for frontend list/detail pages.

CREATE INDEX IF NOT EXISTS ix_audit_logs_action_created_at
ON audit_logs (action, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_audit_logs_severity_created_at
ON audit_logs (severity, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_incidents_status_created_at
ON incidents (status, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_incidents_severity_created_at
ON incidents (severity, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_incident_events_incident_created_at
ON incident_events (incident_id, created_at ASC);

CREATE INDEX IF NOT EXISTS ix_alert_rules_enabled_created_at
ON alert_rules (enabled, created_at DESC);