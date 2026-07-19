"""
Tracks which allowlisted actions a specific device's agent binary actually
supports. The backend refuses to dispatch a command for an action_type with
no matching capability row for that device — see device_supports() below.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent_capability import AgentCapability


def upsert_capabilities(
    db: Session,
    *,
    device_id: uuid.UUID,
    organization_id: uuid.UUID | None,
    agent_type: str,
    agent_version: str,
    capabilities: list[dict[str, str]],
) -> list[AgentCapability]:
    """
    capabilities: list of {"action_type", "action_version", "local_risk_level"}.
    Upserts one row per (device_id, action_type). Called at enrolment and on
    every agent process start, so this always fully reconciles the reported
    capability set for that agent version.
    """

    now = datetime.now(timezone.utc)
    result: list[AgentCapability] = []

    for capability in capabilities:
        existing = db.scalar(
            select(AgentCapability).where(
                AgentCapability.device_id == device_id,
                AgentCapability.action_type == capability["action_type"],
            )
        )
        if existing is not None:
            existing.agent_type = agent_type
            existing.agent_version = agent_version
            existing.action_version = capability.get("action_version", "1")
            existing.local_risk_level = capability["local_risk_level"]
            existing.updated_at = now
            result.append(existing)
        else:
            row = AgentCapability(
                id=uuid.uuid4(),
                device_id=device_id,
                organization_id=organization_id,
                agent_type=agent_type,
                agent_version=agent_version,
                action_type=capability["action_type"],
                action_version=capability.get("action_version", "1"),
                local_risk_level=capability["local_risk_level"],
            )
            db.add(row)
            result.append(row)

    return result


def device_supports(db: Session, *, device_id: uuid.UUID, action_type: str) -> bool:
    existing = db.scalar(
        select(AgentCapability).where(
            AgentCapability.device_id == device_id,
            AgentCapability.action_type == action_type,
        )
    )
    return existing is not None
