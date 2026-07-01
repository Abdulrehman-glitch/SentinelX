from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.audit_log import AuditLogResponse
from app.services.tenant import require_org_user

router = APIRouter(prefix="/audit-logs", tags=["Audit Logs"])


@router.get("", response_model=list[AuditLogResponse])
def list_audit_logs(
    limit: int = 100,
    severity: str | None = None,
    action: str | None = None,
    current_user: User = Depends(require_role(["admin", "owner", "operator", "platform_admin"])),
    db: Session = Depends(get_db),
) -> list[AuditLog]:
    safe_limit = min(max(limit, 1), 500)
    conditions = []

    if current_user.role != "platform_admin":
        conditions.append(AuditLog.organization_id == require_org_user(current_user))
    if severity:
        conditions.append(AuditLog.severity == severity.lower())
    if action:
        conditions.append(AuditLog.action == action)

    statement = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(safe_limit)
    if conditions:
        statement = statement.where(*conditions)

    return list(db.scalars(statement))
