-- Mobile-agent telemetry extras on system_metrics (additive, nullable — safe to
-- apply to a live dev DB without a wipe). Desktop agents leave these null.
ALTER TABLE system_metrics ADD COLUMN IF NOT EXISTS battery_percent double precision;
ALTER TABLE system_metrics ADD COLUMN IF NOT EXISTS battery_charging boolean;
ALTER TABLE system_metrics ADD COLUMN IF NOT EXISTS network_transport varchar(32);
ALTER TABLE system_metrics ADD COLUMN IF NOT EXISTS latency_ms double precision;
