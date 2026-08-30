import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

# OpenTelemetry's severity number ranges, and the names SentinelX shows for
# them. The specification defines 1-24 in bands of four; the band is what an
# operator filters on, and the exact number is what the producer meant.
SEVERITY_BANDS: tuple[tuple[int, int, str], ...] = (
    (1, 4, "trace"),
    (5, 8, "debug"),
    (9, 12, "info"),
    (13, 16, "warn"),
    (17, 20, "error"),
    (21, 24, "fatal"),
)

SEVERITY_NAMES = tuple(band[2] for band in SEVERITY_BANDS)


def severity_band(severity_number: int | None) -> str:
    """Map an OTLP severity number onto a name a filter can use.

    Unset (0) is deliberately not "info": a producer that never set a severity
    has not told us it is informational, and quietly promoting it would hide
    records from a filter that excludes info.
    """
    if not severity_number:
        return "unspecified"
    for low, high, name in SEVERITY_BANDS:
        if low <= severity_number <= high:
            return name
    return "unspecified"


class LogRecord(Base):
    """One OTLP log record.

    Shaped for the questions a log explorer actually asks: everything in the
    WHERE clause of "errors from checkout-api in production over the last
    hour", plus the trace id that turns a log line into an investigation.

    Two denormalisations, both deliberate. `service_name`, `environment` and
    `service_version` are copied from the resource, because every meaningful
    log query filters on them and joining `resources` on each one would put a
    join in front of the most common query in the product. And the severity
    *band* is stored alongside the number, so "errors and worse" is an indexed
    equality rather than a range the planner has to reason about.

    The primary key leads with `observed_at` for the same reason
    `metric_points` leads with `recorded_at`: it makes range partitioning a
    later migration rather than a table rewrite, and gives the PK index a
    useful leading column instead of a random UUID.
    """

    __tablename__ = "log_records"
    __table_args__ = (
        # The explorer's default query: one tenant, newest first.
        Index("ix_log_records_org_observed", "organization_id", "observed_at"),
        # "logs for this trace" - the jump from a slow span to what it printed.
        Index("ix_log_records_org_trace", "organization_id", "trace_id"),
        # "errors from this service" - service and severity are almost always
        # filtered together, so they share an index with time.
        Index(
            "ix_log_records_org_service_severity",
            "organization_id",
            "service_name",
            "severity_band",
            "observed_at",
        ),
        # Attribute search. GIN over JSONB makes `attributes @> '{"k":"v"}'`
        # an index scan; without it every attribute filter is a full scan.
        Index("ix_log_records_attributes", "attributes", postgresql_using="gin"),
        # Appended in rough time order, which is exactly the physical
        # correlation BRIN needs, at a fraction of a B-tree's size.
        Index(
            "ix_log_records_observed_brin",
            "observed_at",
            postgresql_using="brin",
            postgresql_with={"pages_per_range": "128"},
        ),
        Index("ix_log_records_resource", "resource_id", "observed_at"),
    )

    # Composite PK leading with time: see the class docstring.
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE")
    )
    resource_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("resources.id", ondelete="CASCADE")
    )

    # When the producer says it happened. Distinct from observed_at, which is
    # when the collector saw it - the gap between them is pipeline lag, and
    # conflating the two makes that lag invisible.
    timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    severity_number: Mapped[int] = mapped_column(SmallInteger, default=0)
    severity_text: Mapped[str | None] = mapped_column(String(32), nullable=True)
    severity_band: Mapped[str] = mapped_column(String(16), default="unspecified", index=True)

    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    # Hex, exactly as OTLP transmits them, so a value pasted from a trace
    # header matches without conversion. Fixed width because they are.
    trace_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    span_id: Mapped[str | None] = mapped_column(String(16), nullable=True)

    # Instrumentation scope: which library emitted this.
    scope_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    scope_version: Mapped[str | None] = mapped_column(String(63), nullable=True)

    # Denormalised from the resource; see the class docstring.
    service_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    environment: Mapped[str | None] = mapped_column(String(63), nullable=True)
    service_version: Mapped[str | None] = mapped_column(String(63), nullable=True)

    # How many attributes the producer dropped before sending, per OTLP. Worth
    # keeping: a non-zero value explains why a record looks less detailed than
    # the code that wrote it suggests.
    dropped_attributes_count: Mapped[int] = mapped_column(Integer, default=0)

    # Set when redaction actually replaced something, so an operator can tell
    # "this field was empty" from "this field held a credential we refused to
    # store".
    redacted_keys: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)

    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    resource = relationship("Resource")
