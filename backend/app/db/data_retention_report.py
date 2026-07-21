"""Sprint 7 Phase 6: data lifecycle retention reporting.

Read-only. Reports how many rows in each retention-governed table are
older than the cutoff in docs/releases/DATA_RETENTION_POLICY.md. Never
issues a DELETE or UPDATE — this sprint only reports, it does not enforce.

Usage (from backend/):
    python -m app.db.data_retention_report
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm.attributes import InstrumentedAttribute

from app.db.session import SessionLocal
from app.models.agent_heartbeat import AgentHeartbeat
from app.models.anomaly_prediction import AnomalyPrediction
from app.models.audit_log import AuditLog
from app.models.embedded_telemetry import EmbeddedTelemetry
from app.models.hybrid_decision import HybridDecision
from app.models.recovery_command import RecoveryCommand
from app.models.recovery_command_event import RecoveryCommandEvent
from app.models.replay_run import ReplayRun
from app.models.security_log import SecurityLog
from app.models.system_metric import SystemMetric
from app.models.telemetry_feature_window import TelemetryFeatureWindow


@dataclass(frozen=True)
class RetentionRule:
    label: str
    timestamp_column: InstrumentedAttribute
    retention_days: int


# Periods and rationale documented in docs/releases/DATA_RETENTION_POLICY.md
# — keep the two in sync if either changes.
RETENTION_RULES: list[RetentionRule] = [
    RetentionRule("system_metrics", SystemMetric.recorded_at, 90),
    RetentionRule("agent_heartbeats", AgentHeartbeat.recorded_at, 90),
    RetentionRule("embedded_telemetry", EmbeddedTelemetry.recorded_at, 90),
    RetentionRule("telemetry_feature_windows", TelemetryFeatureWindow.window_end, 180),
    RetentionRule("anomaly_predictions", AnomalyPrediction.created_at, 365),
    RetentionRule("hybrid_decisions", HybridDecision.created_at, 365),
    RetentionRule("recovery_commands", RecoveryCommand.created_at, 365),
    RetentionRule("recovery_command_events", RecoveryCommandEvent.created_at, 365),
    RetentionRule("replay_runs", ReplayRun.created_at, 730),
    RetentionRule("audit_logs", AuditLog.created_at, 730),
    RetentionRule("security_logs", SecurityLog.created_at, 730),
]


def generate_report() -> list[dict]:
    """Returns one row per RETENTION_RULES entry: total row count, the
    policy cutoff timestamp, and how many rows are past it. Read-only."""
    now = datetime.now(timezone.utc)
    session = SessionLocal()
    try:
        rows = []
        for rule in RETENTION_RULES:
            table = rule.timestamp_column.class_
            cutoff = now - timedelta(days=rule.retention_days)

            total_rows = session.scalar(select(func.count()).select_from(table)) or 0
            rows_past_retention = (
                session.scalar(
                    select(func.count()).select_from(table).where(rule.timestamp_column < cutoff)
                )
                or 0
            )

            rows.append(
                {
                    "table": rule.label,
                    "retention_days": rule.retention_days,
                    "cutoff": cutoff.isoformat(),
                    "total_rows": total_rows,
                    "rows_past_retention": rows_past_retention,
                }
            )
        return rows
    finally:
        session.close()


def _print_report(rows: list[dict]) -> None:
    print(f"{'Table':<28} {'Retention':>10} {'Total rows':>12} {'Past cutoff':>12}")
    print("-" * 66)
    for row in rows:
        print(
            f"{row['table']:<28} {row['retention_days']:>9}d {row['total_rows']:>12} "
            f"{row['rows_past_retention']:>12}"
        )


if __name__ == "__main__":
    _print_report(generate_report())
