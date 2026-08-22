"""Projecting native agent samples into the canonical metric model.

SentinelX's own agents send a fixed-shape payload — CPU, memory, disk, plus
some mobile extras — into `system_metrics`. That table and everything built on
it (alert rules, the AI feature windows, the device detail page) keeps working
exactly as before. This adapter additionally projects each accepted sample into
`metric_points`, in the same transaction, so the canonical store fills with real
data while the legacy representation is still authoritative.

That ordering matters. Dual-write, then move readers, then retire the writer —
so at no point is there a feature reading from a store nothing has populated.
The retirement path is written down in ADR 0009.

On units. OpenTelemetry's `system.cpu.utilization` is a ratio in 0..1, whereas
SentinelX has always collected and alerted on 0..100 percentages, and silently
rescaling them would make every existing threshold wrong by two orders of
magnitude. So the names follow the semantic conventions and the unit is declared
honestly as "%". Because the unit participates in series identity, an OTLP
client sending the conventional ratio form lands in a *different* series rather
than being mixed into the same one — the ambiguity resolves itself instead of
corrupting an average.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.device import Device
from app.models.metric_point import MetricPoint
from app.models.system_metric import SystemMetric
from app.services.cardinality_service import SeriesBudget, load_series_budget
from app.services.metric_series_service import SeriesResolver
from app.services.resource_service import device_resource_attributes, resolve_resource
from app.services.telemetry_identity import resource_identity_hash, split_resource_identity


@dataclass(frozen=True)
class _Projection:
    """One legacy column's canonical form."""

    attribute: str
    metric_name: str
    unit: str


# Names follow the OpenTelemetry system semantic conventions so an operator
# querying SentinelX uses the same vocabulary as the rest of the ecosystem.
_PROJECTIONS: tuple[_Projection, ...] = (
    _Projection("cpu_percent", "system.cpu.utilization", "%"),
    _Projection("memory_percent", "system.memory.utilization", "%"),
    _Projection("disk_percent", "system.filesystem.utilization", "%"),
    # Mobile extras. Null on desktop agents, and a null reading is skipped
    # rather than stored as zero — "unknown" and "empty battery" are not the
    # same fact, and conflating them would fire real alerts.
    _Projection("battery_percent", "system.battery.level", "%"),
    _Projection("battery_temperature_c", "system.battery.temperature", "Cel"),
    _Projection("latency_ms", "network.client.latency", "ms"),
)


def project_samples(
    db: Session,
    *,
    device: Device,
    samples: list[SystemMetric],
    settings: Settings,
    budget: SeriesBudget | None = None,
) -> int:
    """Write the canonical projection of `samples`. Returns points written.

    Called inside the ingest transaction, after the legacy rows are flushed.
    Never fails ingest on cardinality: the native payload has a fixed, small set
    of metric names, so the budget can only bite if a tenant is already far past
    its limit — in which case the legacy write still succeeds and only the
    projection is skipped. Ingest must not start failing because a *secondary*
    representation hit a limit.
    """
    if not samples or device.organization_id is None:
        return 0

    attributes = device_resource_attributes(device)
    resource = resolve_resource(
        db,
        organization_id=device.organization_id,
        attributes=attributes,
        device=device,
        trusted=True,
    )
    identifying, _descriptive, _type = split_resource_identity(attributes)
    identity = resource_identity_hash(identifying)

    resolver = SeriesResolver(
        db=db,
        organization_id=device.organization_id,
        budget=budget or load_series_budget(db, device.organization_id, settings),
        source="sentinelx_agent",
    )

    rows: list[dict] = []
    for projection in _PROJECTIONS:
        series = None
        for sample in samples:
            value = getattr(sample, projection.attribute, None)
            if value is None:
                continue

            if series is None:
                series, rejection = resolver.resolve(
                    resource=resource,
                    resource_identity=identity,
                    metric_name=projection.metric_name,
                    metric_unit=projection.unit,
                    metric_kind="gauge",
                    attributes={},
                )
                if rejection is not None:
                    break  # budget spent; skip this metric, keep the rest

            rows.append(
                {
                    "id": uuid.uuid4(),
                    "recorded_at": sample.recorded_at,
                    "organization_id": device.organization_id,
                    "series_id": series.id,
                    "value": float(value),
                    # Derived from the legacy sample's event id, so replaying
                    # the same sample is idempotent here too. None for legacy
                    # agents that send no event_id, which the unique constraint
                    # then ignores.
                    "event_id": _derive_event_id(sample.event_id, series.id),
                }
            )

    if not rows:
        return 0

    db.execute(
        pg_insert(MetricPoint)
        .values(rows)
        # A retried batch must not duplicate points. The legacy path already
        # de-duplicates by (device, event_id); this is the same guarantee for
        # the canonical projection.
        .on_conflict_do_nothing(constraint="uq_metric_point_series_event")
    )
    return len(rows)


def _derive_event_id(sample_event_id: uuid.UUID | None, series_id: uuid.UUID) -> uuid.UUID | None:
    """One legacy sample becomes several points, one per metric.

    Deriving the id per series keeps it stable across replays: UUID5 gives the
    same answer every time for the same inputs, which is exactly what
    idempotency needs.
    """
    if sample_event_id is None:
        return None
    return uuid.uuid5(series_id, str(sample_event_id))
