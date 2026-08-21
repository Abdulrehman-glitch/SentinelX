import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

# Only the two point kinds SentinelX actually stores today. Histograms and
# exponential histograms are part of OTLP but are not persisted yet, and
# claiming otherwise in the schema would be a lie the query API cannot honour.
METRIC_KINDS = ("gauge", "sum")

# Where a series came from. Useful for operator diagnosis and for the
# retirement plan of the legacy system_metrics table.
METRIC_SOURCES = ("sentinelx_agent", "otlp_http", "embedded_bridge")


class MetricSeries(Base):
    """The stable identity of one measured thing over time.

    A series is `resource + metric name + unit + kind + canonical attributes`.
    Points reference it, so a device reporting CPU every 15 seconds for a year
    stores one series row and a lot of narrow point rows, instead of repeating
    the resource and dimension strings on every sample.

    This is also where cardinality becomes observable: "how many distinct series
    has this organisation created in the last hour" is a row count, which is what
    makes the limits in app/services/cardinality_service.py enforceable rather
    than aspirational.

    `series_hash` accelerates lookup; as with Resource it is never treated as
    proof of equality on its own. The caller compares the canonical attribute
    dict, and `collision_seq` keeps two genuinely different attribute sets apart
    if they ever hash alike.
    """

    __tablename__ = "metric_series"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "series_hash",
            "collision_seq",
            name="uq_metric_series_org_hash",
        ),
        Index("ix_metric_series_org_name", "organization_id", "metric_name"),
        # The cardinality budget counts new series per tenant per window on
        # every ingest request; without this it is a sequential scan.
        Index("ix_metric_series_org_first_seen", "organization_id", "first_seen_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
    )
    resource_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("resources.id", ondelete="CASCADE"),
        index=True,
    )

    metric_name: Mapped[str] = mapped_column(String(255))
    metric_unit: Mapped[str | None] = mapped_column(String(63), nullable=True)
    metric_kind: Mapped[str] = mapped_column(String(16), default="gauge")

    # The canonical dimension set. Empty dict is the common case for a simple
    # host gauge; `{"disk.device": "C:"}` distinguishes two disks on one host.
    attributes: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    series_hash: Mapped[str] = mapped_column(String(64))
    collision_seq: Mapped[int] = mapped_column(Integer, default=0)

    source: Mapped[str] = mapped_column(String(32), default="sentinelx_agent")

    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    resource = relationship("Resource")
