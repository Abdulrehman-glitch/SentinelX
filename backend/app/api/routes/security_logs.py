from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.db.session import get_db
from app.models.security_log import SecurityLog
from app.models.user import User
from app.schemas.security_log import SecurityLogResponse
from app.services.tenant import require_org_user

router = APIRouter(prefix="/security-logs", tags=["Security Logs"])


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
