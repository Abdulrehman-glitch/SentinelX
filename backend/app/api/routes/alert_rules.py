import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.db.session import get_db
from app.models.alert_rule import AlertRule
from app.models.user import User
from app.schemas.alert_rule import AlertRuleCreateRequest, AlertRuleResponse, AlertRuleUpdateRequest
from app.services.audit_log_service import create_audit_log
from app.services.tenant import assert_same_org, require_org_user

router = APIRouter(prefix="/alert-rules", tags=["Alert Rules"])


def _get_rule_or_404(rule_id: uuid.UUID, current_user: User, db: Session) -> AlertRule:
    rule = db.get(AlertRule, rule_id)
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert rule not found")
    assert_same_org(rule.organization_id, current_user)
    return rule


@router.post("", response_model=AlertRuleResponse, status_code=status.HTTP_201_CREATED)
def create_alert_rule(
    payload: AlertRuleCreateRequest,
    current_user: User = Depends(require_role(["admin", "owner", "platform_admin"])),
    db: Session = Depends(get_db),
) -> AlertRule:
    org_id = None if current_user.role == "platform_admin" else require_org_user(current_user)

    rule = AlertRule(
        organization_id=org_id,
        name=payload.name.strip(),
        metric_type=payload.metric_type,
        operator=payload.operator,
        threshold=payload.threshold,
        severity=payload.severity,
        enabled=payload.enabled,
        description=payload.description,
        cooldown_seconds=payload.cooldown_seconds,
    )

    db.add(rule)

    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An alert rule with this name already exists.") from exc

    create_audit_log(
        db,
        organization_id=org_id,
        actor_type="user",
        actor_id=str(current_user.id),
        action="alert_rule_created",
        target_type="alert_rule",
        target_id=str(rule.id),
        severity="info",
        message=f"Alert rule created: {rule.name}",
        metadata={
            "metric_type": rule.metric_type,
            "operator": rule.operator,
            "threshold": rule.threshold,
            "rule_severity": rule.severity,
            "enabled": rule.enabled,
        },
    )

    db.commit()
    db.refresh(rule)
    return rule


@router.get("", response_model=list[AlertRuleResponse])
def list_alert_rules(
    limit: int = 100,
    enabled: bool | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AlertRule]:
    safe_limit = min(max(limit, 1), 500)

    statement = select(AlertRule).order_by(AlertRule.created_at.desc()).limit(safe_limit)
    conditions = []
    if current_user.role != "platform_admin":
        conditions.append(AlertRule.organization_id == require_org_user(current_user))
    if enabled is not None:
        conditions.append(AlertRule.enabled.is_(enabled))
    if conditions:
        statement = statement.where(*conditions)

    return list(db.scalars(statement))


@router.get("/{rule_id}", response_model=AlertRuleResponse)
def get_alert_rule(
    rule_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AlertRule:
    return _get_rule_or_404(rule_id=rule_id, current_user=current_user, db=db)


@router.patch("/{rule_id}", response_model=AlertRuleResponse)
def update_alert_rule(
    rule_id: uuid.UUID,
    payload: AlertRuleUpdateRequest,
    current_user: User = Depends(require_role(["admin", "owner", "platform_admin"])),
    db: Session = Depends(get_db),
) -> AlertRule:
    rule = _get_rule_or_404(rule_id=rule_id, current_user=current_user, db=db)

    changes = payload.model_dump(exclude_unset=True)
    for field_name, value in changes.items():
        if isinstance(value, str) and field_name == "name":
            value = value.strip()
        setattr(rule, field_name, value)

    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An alert rule with this name already exists.") from exc

    create_audit_log(
        db,
        organization_id=rule.organization_id,
        actor_type="user",
        actor_id=str(current_user.id),
        action="alert_rule_updated",
        target_type="alert_rule",
        target_id=str(rule.id),
        severity="info",
        message=f"Alert rule updated: {rule.name}",
        metadata={"changed_fields": sorted(changes.keys())},
    )

    db.commit()
    db.refresh(rule)
    return rule


@router.patch("/{rule_id}/toggle", response_model=AlertRuleResponse)
def toggle_alert_rule(
    rule_id: uuid.UUID,
    current_user: User = Depends(require_role(["admin", "owner", "platform_admin"])),
    db: Session = Depends(get_db),
) -> AlertRule:
    rule = _get_rule_or_404(rule_id=rule_id, current_user=current_user, db=db)
    rule.enabled = not rule.enabled

    create_audit_log(
        db,
        organization_id=rule.organization_id,
        actor_type="user",
        actor_id=str(current_user.id),
        action="alert_rule_toggled",
        target_type="alert_rule",
        target_id=str(rule.id),
        severity="info",
        message=f"Alert rule toggled to {'enabled' if rule.enabled else 'disabled'}: {rule.name}",
        metadata={"enabled": rule.enabled},
    )

    db.commit()
    db.refresh(rule)
    return rule
