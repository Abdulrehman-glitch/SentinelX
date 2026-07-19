import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RecoveryCommand(Base):
    """
    A signed, verifiable command lifecycle record. Additive and parallel to
    RecoveryAction (which stays passive-logging-only) — this table drives
    actual agent-executed actions. See recovery_command_state_machine.py for
    the legal status transitions and core/security.py for the Ed25519
    signing helpers used when a command is dispatched to a device.
    """

    __tablename__ = "recovery_commands"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True
    )
    device_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"), index=True
    )

    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="SET NULL"), nullable=True
    )
    alert_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("alerts.id", ondelete="SET NULL"), nullable=True
    )
    anomaly_prediction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("anomaly_predictions.id", ondelete="SET NULL"), nullable=True
    )

    action_type: Mapped[str] = mapped_column(String(100), index=True)
    parameters_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    risk_level: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision_source: Mapped[str] = mapped_column(String(20), default="manual")
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    # State machine — see recovery_command_state_machine.py. Never set directly
    # from a raw client-supplied string; only via transition().
    status: Mapped[str] = mapped_column(String(30), default="proposed", index=True)
    approval_mode: Mapped[str] = mapped_column(String(20), default="manual")
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Populated once, at the approved -> dispatched transition (first agent poll).
    command_nonce: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    payload_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    signature: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    result_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    result_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_data_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    pre_action_snapshot_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    post_action_snapshot_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    verification_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    verification_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    model_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    policy_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("recovery_policies.id", ondelete="SET NULL"), nullable=True
    )

    device = relationship("Device")
