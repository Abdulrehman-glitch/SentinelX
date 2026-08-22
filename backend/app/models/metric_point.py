import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class MetricPoint(Base):
    """One numeric sample on a MetricSeries.

    Deliberately narrow: everything describing *what* is measured lives on the
    series, so this table stays cheap to append to and cheap to scan. It is the
    only table in SentinelX expected to reach eight figures.

    Two storage decisions worth stating explicitly, both measured rather than
    assumed (see docs/adr/0010-postgresql-telemetry-storage.md):

    * The primary key is `(recorded_at, id)`, not `id`. Postgres requires the
      partition key to be part of every unique constraint, so leading with
      `recorded_at` means introducing `PARTITION BY RANGE (recorded_at)` later
      is a migration rather than a full table rewrite. It also gives the PK
      index a useful leading column instead of a random UUID.
    * A BRIN index on `recorded_at` alongside the B-tree on
      `(series_id, recorded_at)`. Points are appended in rough timestamp order,
      which is exactly the physical correlation BRIN needs, and it costs a
      fraction of a B-tree's size on a table this shape.
    """

    __tablename__ = "metric_points"
    __table_args__ = (
        # Idempotent ingestion. Postgres treats NULLs as distinct, so points
        # carrying no client event id — the common OTLP case — are unaffected.
        UniqueConstraint("series_id", "event_id", name="uq_metric_point_series_event"),
        Index("ix_metric_points_series_time", "series_id", "recorded_at"),
        Index("ix_metric_points_org_time", "organization_id", "recorded_at"),
        Index(
            "ix_metric_points_recorded_at_brin",
            "recorded_at",
            postgresql_using="brin",
            postgresql_with={"pages_per_range": "128"},
        ),
    )

    # Composite PK: see the class docstring. `recorded_at` leads.
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Denormalised from the series so tenant-scoped queries and retention
    # deletes never have to join. Retention in particular deletes by
    # (organization_id, recorded_at) and must not fan out over series.
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
    )

    series_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("metric_series.id", ondelete="CASCADE"),
    )

    value: Mapped[float] = mapped_column(Float)

    # Client-supplied sample id, when the protocol carries one. NULL is normal.
    event_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    # When SentinelX accepted it, as opposed to when the client measured it.
    # The gap between the two is the ingestion lag an operator cares about.
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    series = relationship("MetricSeries")
