import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Device(Base):
    """
    Monitored machine, edge device, or embedded agent endpoint.

    Belongs to exactly one organization. The (hostname, organization_id)
    pair is unique so the same hostname can exist across different tenants.
    """

    __tablename__ = "devices"
    __table_args__ = (
        UniqueConstraint("hostname", "organization_id", name="uq_device_hostname_org"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    hostname: Mapped[str] = mapped_column(String(255), index=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(100), nullable=True)
    os_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # desktop | server | embedded | sensor | gateway | virtual
    device_type: Mapped[str] = mapped_column(String(50), default="desktop", index=True)

    # low | medium | high — operator-assigned business importance, used by
    # hybrid_detection_service to weight operational_risk. Not inferred from
    # telemetry; defaults to "medium" until an operator sets it explicitly.
    criticality: Mapped[str] = mapped_column(String(20), default="medium", index=True)

    # python_desktop_agent | arduino_ble_agent | manual | other
    agent_type: Mapped[str] = mapped_column(String(100), default="python_desktop_agent")

    agent_version: Mapped[str | None] = mapped_column(String(50), nullable=True)

    status: Mapped[str] = mapped_column(String(50), default="online", index=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    organization = relationship("Organization", back_populates="devices")
    heartbeats = relationship("AgentHeartbeat", back_populates="device", cascade="all, delete-orphan")
    metrics = relationship("SystemMetric", back_populates="device", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="device", cascade="all, delete-orphan")
    recovery_actions = relationship("RecoveryAction", back_populates="device", cascade="all, delete-orphan")
    embedded_telemetry = relationship("EmbeddedTelemetry", back_populates="device", cascade="all, delete-orphan")
