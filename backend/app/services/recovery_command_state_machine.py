"""
Strict status transitions for RecoveryCommand. The backend owns transition
authority — clients (frontend, agents) only ever request an action; the
service/route layer maps that action to the single legal next status and
calls transition(), which writes the matching RecoveryCommandEvent row in
the same transaction. No endpoint accepts a raw status string from a client.
"""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.recovery_command import RecoveryCommand
from app.models.recovery_command_event import RecoveryCommandEvent


class IllegalTransitionError(Exception):
    def __init__(self, current_status: str, new_status: str):
        self.current_status = current_status
        self.new_status = new_status
        super().__init__(
            f"Cannot transition recovery command from '{current_status}' to '{new_status}'."
        )


VALID_TRANSITIONS: dict[str, set[str]] = {
    "proposed": {"awaiting_approval", "approved", "rejected"},
    "awaiting_approval": {"approved", "rejected", "expired"},
    "approved": {"dispatched", "rejected", "expired"},
    "dispatched": {"acknowledged", "expired"},
    "acknowledged": {"running", "expired", "failed"},
    "running": {"succeeded", "failed", "rejected", "expired"},
    "succeeded": {"verifying"},
    "verifying": {"verified", "ineffective", "inconclusive", "failed", "rolled_back"},
    # Terminal states — no outgoing edges.
    "rejected": set(),
    "expired": set(),
    "failed": set(),
    "verified": set(),
    "ineffective": set(),
    "inconclusive": set(),
    "rolled_back": set(),
}

TERMINAL_STATUSES = {status for status, edges in VALID_TRANSITIONS.items() if not edges}

_TIMESTAMP_FIELD_FOR_STATUS = {
    "approved": "approved_at",
    "dispatched": "dispatched_at",
    "acknowledged": "acknowledged_at",
    "running": "started_at",
}

_COMPLETED_STATUSES = {
    "succeeded", "failed", "rejected", "expired",
    "verified", "ineffective", "inconclusive", "rolled_back",
}


def transition(
    db: Session,
    command: RecoveryCommand,
    new_status: str,
    *,
    actor_type: str,
    actor_id: str | None = None,
    message: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> RecoveryCommand:
    """
    Validates and applies a single status transition, writing exactly one
    RecoveryCommandEvent row. Raises IllegalTransitionError on an invalid
    edge. Does not commit — the caller owns the transaction.
    """

    current_status = command.status
    allowed = VALID_TRANSITIONS.get(current_status, set())

    if new_status not in allowed:
        raise IllegalTransitionError(current_status, new_status)

    now = datetime.now(timezone.utc)

    command.status = new_status

    timestamp_field = _TIMESTAMP_FIELD_FOR_STATUS.get(new_status)
    if timestamp_field is not None and getattr(command, timestamp_field) is None:
        setattr(command, timestamp_field, now)

    if new_status in _COMPLETED_STATUSES and command.completed_at is None:
        command.completed_at = now

    event = RecoveryCommandEvent(
        id=uuid.uuid4(),
        command_id=command.id,
        organization_id=command.organization_id,
        event_type=f"status_changed:{new_status}",
        previous_status=current_status,
        new_status=new_status,
        actor_type=actor_type,
        actor_id=actor_id,
        message=message,
        metadata_json=metadata,
    )
    db.add(event)

    return command
