import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

# OTLP SpanKind, as names rather than the wire enum. A stored integer would
# mean every query and every reader had to know the mapping.
SPAN_KINDS = ("internal", "server", "client", "producer", "consumer", "unspecified")

_KIND_BY_NUMBER = {
    0: "unspecified",
    1: "internal",
    2: "server",
    3: "client",
    4: "producer",
    5: "consumer",
}

SPAN_STATUS_CODES = ("unset", "ok", "error")

_STATUS_BY_NUMBER = {0: "unset", 1: "ok", 2: "error"}


def span_kind_name(kind_number: int | None) -> str:
    return _KIND_BY_NUMBER.get(kind_number or 0, "unspecified")


def span_status_name(status_number: int | None) -> str:
    return _STATUS_BY_NUMBER.get(status_number or 0, "unset")


class Span(Base):
    """One OTLP span.

    Spans are stored flat, not as a tree. The parent link is a column, and the
    waterfall is assembled at read time from every span sharing a trace id.
    That is the only shape that survives reality: spans from different services
    arrive in any order, sometimes minutes apart, and a child routinely lands
    before its parent. A stored tree would have to be rewritten on every late
    arrival.

    `duration_ns` is stored rather than derived. Latency is the single most
    queried property of a span - "slowest traces", "p99 for this service" - and
    computing `end - start` in the WHERE clause would forbid an index on the
    thing every latency query filters by.

    As with logs, service/environment/version are denormalised off the resource
    because every real query filters on them.
    """

    __tablename__ = "spans"
    __table_args__ = (
        # Assembling one trace. The most important index here: it is what turns
        # "show me this trace" into a single seek.
        Index("ix_spans_org_trace", "organization_id", "trace_id"),
        # The trace list: newest first within a tenant.
        Index("ix_spans_org_start", "organization_id", "start_time"),
        # Service health and slow-trace search, which always pair a service
        # with a time range and usually with status or duration.
        Index("ix_spans_org_service_start", "organization_id", "service_name", "start_time"),
        Index("ix_spans_org_status_start", "organization_id", "status_code", "start_time"),
        Index("ix_spans_org_duration", "organization_id", "service_name", "duration_ns"),
        Index("ix_spans_attributes", "attributes", postgresql_using="gin"),
        Index(
            "ix_spans_start_brin",
            "start_time",
            postgresql_using="brin",
            postgresql_with={"pages_per_range": "128"},
        ),
        # Idempotent ingestion: a collector retrying a batch must not duplicate
        # spans. (trace_id, span_id) is unique by definition in OTLP.
        Index("uq_spans_org_trace_span", "organization_id", "trace_id", "span_id", unique=True),
    )

    # Composite PK leading with time, for the same partitioning and index
    # reasons as metric_points and log_records.
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE")
    )
    resource_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("resources.id", ondelete="CASCADE")
    )

    # Hex as OTLP transmits them, so an id pasted from a header or a log line
    # matches without conversion.
    trace_id: Mapped[str] = mapped_column(String(32))
    span_id: Mapped[str] = mapped_column(String(16))
    # NULL means this is a root span - the entry point of the trace.
    parent_span_id: Mapped[str | None] = mapped_column(String(16), nullable=True)

    name: Mapped[str] = mapped_column(String(255))
    kind: Mapped[str] = mapped_column(String(16), default="unspecified")

    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # Nanoseconds, because that is the resolution OTLP carries; rounding to
    # milliseconds at ingest would throw away detail a p99 depends on.
    duration_ns: Mapped[int] = mapped_column(BigInteger, default=0)

    status_code: Mapped[str] = mapped_column(String(8), default="unset")
    status_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    attributes: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    # Span events, bounded at ingest. Stored inline rather than in their own
    # table: they are only ever read with their span, and a join would buy
    # nothing but a second index to maintain.
    events: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)

    scope_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    scope_version: Mapped[str | None] = mapped_column(String(63), nullable=True)

    service_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    environment: Mapped[str | None] = mapped_column(String(63), nullable=True)
    service_version: Mapped[str | None] = mapped_column(String(63), nullable=True)

    dropped_attributes_count: Mapped[int] = mapped_column(Integer, default=0)
    dropped_events_count: Mapped[int] = mapped_column(Integer, default=0)

    redacted_keys: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)

    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    resource = relationship("Resource")
