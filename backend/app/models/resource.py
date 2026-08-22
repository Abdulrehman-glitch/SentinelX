import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

# Resource kinds SentinelX can describe. `host` covers the laptops and servers
# the desktop agent reports; `embedded_node` covers the Arduino bridge. The
# remainder exist so an OTLP client describing a service or a container is not
# forced to masquerade as a machine.
RESOURCE_TYPES = ("host", "service", "application", "embedded_node", "container")


class Resource(Base):
    """A single observable thing, named the way OpenTelemetry names things.

    SentinelX used to assume everything observable was a Device with a CPU, a
    memory percentage and a disk percentage. That is true of a laptop and false
    of a service, an application or a container. A Resource is the general form:
    an organisation-scoped entity described by attributes drawn from the
    OpenTelemetry resource semantic conventions (`host.name`, `service.name`,
    `deployment.environment.name`, ...).

    Identity comes from `identifying_attributes` — the canonical subset that
    says *which* thing this is, as opposed to merely describing it. Two payloads
    carrying the same identifying attributes resolve to the same Resource even
    if the descriptive attributes have drifted.

    `identity_hash` exists to make that lookup an index seek rather than a JSONB
    comparison. It is an accelerator, never proof: callers still compare
    `identifying_attributes` for exact equality, and `collision_seq`
    distinguishes the (astronomically unlikely) case of two different attribute
    sets hashing alike. See app/services/resource_service.py.
    """

    __tablename__ = "resources"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "identity_hash",
            "collision_seq",
            name="uq_resource_org_identity",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
    )

    resource_type: Mapped[str] = mapped_column(String(32), default="host")

    identity_hash: Mapped[str] = mapped_column(String(64))
    # Always 0 in practice. Non-zero only if two distinct attribute sets ever
    # collide under SHA-256, which the lookup path detects rather than assumes.
    collision_seq: Mapped[int] = mapped_column(Integer, default=0)

    identifying_attributes: Mapped[dict[str, Any]] = mapped_column(JSONB)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    # Set when this resource is one of the Devices SentinelX already manages, so
    # the existing fleet views, alerts and recovery pipeline keep working
    # unchanged while telemetry moves to the canonical model. NULL for a
    # resource that only ever arrived over OTLP.
    device_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("devices.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    organization = relationship("Organization")
    device = relationship("Device")
