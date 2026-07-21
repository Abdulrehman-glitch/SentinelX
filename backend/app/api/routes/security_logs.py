from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.db.session import get_db
from app.models.recovery_command import RecoveryCommand
from app.models.security_log import SecurityLog
from app.models.system_metric import SystemMetric
from app.models.user import User
from app.schemas.security_log import SecurityLogResponse
from app.services.tenant import require_org_user

router = APIRouter(prefix="/security-logs", tags=["Security Logs"])

_FAILED_AUTH_EVENT_TYPES = ("login_failure", "login_inactive_user", "device_auth_failure")


@router.get("", response_model=list[SecurityLogResponse])
def list_security_logs(
    limit: int = 100,
    severity: str | None = None,
    event_type: str | None = None,
    status_value: str | None = None,
    current_user: User = Depends(require_role(["admin", "owner", "platform_admin"])),
    db: Session = Depends(get_db),
) -> list[SecurityLog]:
    """Return security logs with strict tenant scoping.

    Platform admins can see platform-wide logs. Tenant admins/owners can only
    see events associated with their organization. Plain text tokens and
    passwords are never returned because only metadata summaries are stored.
    """
    safe_limit = min(max(limit, 1), 500)

    conditions = []
    if current_user.role != "platform_admin":
        conditions.append(SecurityLog.organization_id == require_org_user(current_user))
    if severity:
        conditions.append(SecurityLog.severity == severity.lower())
    if event_type:
        conditions.append(SecurityLog.event_type == event_type)
    if status_value:
        conditions.append(SecurityLog.status == status_value)

    statement = select(SecurityLog).order_by(SecurityLog.created_at.desc()).limit(safe_limit)
    if conditions:
        statement = statement.where(*conditions)

    return list(db.scalars(statement))


@router.get("/counters")
def get_security_counters(
    window_minutes: int = 1440,
    current_user: User = Depends(require_role(["admin", "owner", "platform_admin"])),
    db: Session = Depends(get_db),
) -> dict:
    """Operational counters for the last `window_minutes` (default 24h),
    tenant-scoped the same way as `list_security_logs` above.

    - failed_auth_count: user login failures/inactive-user attempts plus
      device-token authentication failures (SecurityLog).
    - recovery_command_verification_failures: recovery commands an agent
      locally rejected (bad signature/nonce/expiry — RecoveryCommand.status
      == "rejected"), not post-execution outcome verification.
    - telemetry_samples: raw metric ingestion volume in the window, plus a
      per-minute rate for at-a-glance load monitoring.
    """
    safe_window_minutes = min(max(window_minutes, 1), 10_080)  # cap at 7 days
    since = datetime.now(timezone.utc) - timedelta(minutes=safe_window_minutes)
    org_id = None if current_user.role == "platform_admin" else require_org_user(current_user)

    failed_auth_statement = select(func.count()).select_from(SecurityLog).where(
        SecurityLog.event_type.in_(_FAILED_AUTH_EVENT_TYPES),
        SecurityLog.created_at >= since,
    )
    rate_limit_statement = select(func.count()).select_from(SecurityLog).where(
        SecurityLog.event_type == "rate_limit_violation",
        SecurityLog.created_at >= since,
    )
    verification_failures_statement = select(func.count()).select_from(RecoveryCommand).where(
        RecoveryCommand.status == "rejected",
        RecoveryCommand.created_at >= since,
    )
    telemetry_statement = select(func.count()).select_from(SystemMetric).where(
        SystemMetric.recorded_at >= since,
    )

    if org_id is not None:
        failed_auth_statement = failed_auth_statement.where(SecurityLog.organization_id == org_id)
        rate_limit_statement = rate_limit_statement.where(SecurityLog.organization_id == org_id)
        verification_failures_statement = verification_failures_statement.where(
            RecoveryCommand.organization_id == org_id
        )
        telemetry_statement = telemetry_statement.where(SystemMetric.organization_id == org_id)

    failed_auth_count = db.scalar(failed_auth_statement) or 0
    rate_limit_violation_count = db.scalar(rate_limit_statement) or 0
    recovery_command_verification_failures = db.scalar(verification_failures_statement) or 0
    telemetry_samples = db.scalar(telemetry_statement) or 0

    return {
        "window_minutes": safe_window_minutes,
        "failed_auth_count": failed_auth_count,
        "rate_limit_violation_count": rate_limit_violation_count,
        "recovery_command_verification_failures": recovery_command_verification_failures,
        "telemetry_samples": telemetry_samples,
        "telemetry_samples_per_minute": round(telemetry_samples / safe_window_minutes, 3),
    }
