"""OTLP/HTTP metric ingestion: decode it safely, then store it canonically.

Everything arriving here is hostile until proven otherwise, and the two most
interesting attacks need no credentials to attempt.

A decompression bomb is the first. A few hundred kilobytes of gzip can inflate
to gigabytes, so checking the size *after* decompressing is checking after the
damage. `safe_gunzip` inflates incrementally with a hard output ceiling and
stops at the ceiling rather than at the end of the stream, so the memory an
attacker can make the process allocate is bounded by configuration rather than
by their payload.

A cardinality bomb is the second, and it is subtler because the request is
small and perfectly well-formed. That one is handled by the series budget in
`cardinality_service`, enforced here per data point.

The response follows the OTLP specification's partial-success rules. A batch
where one point is malformed and 499 are fine must store the 499 and report the
one, because a client that gets a blanket rejection will retry the whole batch
forever and never discover which point it should fix.
"""

from __future__ import annotations

import uuid
import zlib
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.ingest_credential import IngestCredential
from app.models.metric_point import MetricPoint
from app.services import cardinality_service as cs
from app.services.metric_series_service import SeriesResolver
from app.services.resource_service import ResourceResolutionError, resolve_resource
from app.services.telemetry_identity import (
    canonical_attributes,
    resource_identity_hash,
    split_resource_identity,
)

# gzip's window-size flag. 16 + MAX_WBITS selects gzip framing rather than raw
# deflate, which is what OTLP/HTTP `Content-Encoding: gzip` means.
_GZIP_WBITS = 16 + zlib.MAX_WBITS

# Point kinds OTLP defines that SentinelX does not store. Named explicitly so
# the rejection tells the client the truth instead of "invalid payload".
_UNSUPPORTED_KINDS = {
    "histogram": "histogram",
    "exponential_histogram": "exponential histogram",
    "summary": "summary",
}

REJECT_UNSUPPORTED_METRIC_TYPE = "unsupported_metric_type"
REJECT_NO_RESOURCE_IDENTITY = "no_resource_identity"
REJECT_NO_VALUE = "no_value"


class PayloadTooLarge(ValueError):
    """The request exceeded a size ceiling, compressed or inflated."""


class MalformedPayload(ValueError):
    """The bytes are not a parseable OTLP metrics request."""


@dataclass
class IngestOutcome:
    """What happened, in the shape OTLP's partial success needs."""

    accepted_points: int = 0
    rejected_points: int = 0
    new_series: int = 0
    rejections: list[cs.Rejection] = field(default_factory=list)

    def reject(self, rejection: cs.Rejection) -> None:
        self.rejected_points += 1
        # One example per distinct reason is enough to fix the problem; a
        # thousand identical strings helps nobody and makes the error message
        # itself a payload.
        if not any(r.reason == rejection.reason for r in self.rejections):
            self.rejections.append(rejection)

    @property
    def error_message(self) -> str:
        if not self.rejections:
            return ""
        return "; ".join(f"{r.reason} ({r.subject}): {r.detail}" for r in self.rejections)


def safe_gunzip(payload: bytes, *, max_output: int) -> bytes:
    """Inflate with a hard output ceiling.

    `decompressobj.decompress(data, max_length)` is the load-bearing detail: it
    stops producing output at the ceiling and leaves the rest of the *input* in
    `unconsumed_tail`, so a bomb is detected by there being input left over
    rather than by measuring a buffer already allocated.
    """
    decompressor = zlib.decompressobj(_GZIP_WBITS)
    try:
        inflated = decompressor.decompress(payload, max_output)
    except zlib.error as exc:
        raise MalformedPayload(f"Body is not valid gzip: {exc}") from exc

    if decompressor.unconsumed_tail or not decompressor.eof:
        raise PayloadTooLarge(f"Decompressed body exceeds the {max_output} byte limit.")

    return inflated


def decode_request(body: bytes, *, content_encoding: str | None, settings: Settings):
    """Bytes on the wire to a parsed ExportMetricsServiceRequest."""
    # Imported lazily so the rest of the backend does not pay the protobuf
    # import cost, and so a missing optional dependency surfaces at the OTLP
    # endpoint rather than at application start.
    from opentelemetry.proto.collector.metrics.v1 import metrics_service_pb2

    if len(body) > settings.ingest_max_compressed_bytes:
        raise PayloadTooLarge(
            f"Request body is {len(body)} bytes; the limit is "
            f"{settings.ingest_max_compressed_bytes}."
        )

    if (content_encoding or "").lower() == "gzip":
        body = safe_gunzip(body, max_output=settings.ingest_max_decompressed_bytes)
    elif len(body) > settings.ingest_max_decompressed_bytes:
        raise PayloadTooLarge(
            f"Request body is {len(body)} bytes; the limit is "
            f"{settings.ingest_max_decompressed_bytes}."
        )

    request = metrics_service_pb2.ExportMetricsServiceRequest()
    try:
        request.ParseFromString(body)
    except Exception as exc:  # protobuf raises several distinct types
        raise MalformedPayload(f"Body is not a valid OTLP metrics request: {exc}") from exc

    return request


def _attributes_to_dict(key_values) -> dict:
    """OTLP AnyValue is a oneof; flatten it to something storable."""
    out = {}
    for kv in key_values:
        value = kv.value
        which = value.WhichOneof("value")
        if which == "string_value":
            out[kv.key] = value.string_value
        elif which == "bool_value":
            out[kv.key] = value.bool_value
        elif which == "int_value":
            out[kv.key] = value.int_value
        elif which == "double_value":
            out[kv.key] = value.double_value
        elif which == "array_value":
            out[kv.key] = [
                getattr(v, v.WhichOneof("value") or "string_value", None)
                for v in value.array_value.values
            ]
        elif which == "bytes_value":
            # Not a dimension anyone can query on; keep it out of identity.
            continue
        elif which == "kvlist_value":
            out[kv.key] = _attributes_to_dict(value.kvlist_value.values)
    return out


def _timestamp(time_unix_nano: int) -> datetime:
    return datetime.fromtimestamp(time_unix_nano / 1_000_000_000, tz=timezone.utc)


def _point_value(point) -> float | None:
    which = point.WhichOneof("value")
    if which == "as_double":
        return point.as_double
    if which == "as_int":
        return float(point.as_int)
    return None


def _metric_kind(metric) -> tuple[str | None, str | None]:
    """(kind, unsupported_label). Exactly one is non-None."""
    which = metric.WhichOneof("data")
    if which == "gauge":
        return "gauge", None
    if which == "sum":
        # Delta and cumulative sums mean different things: one is an increment,
        # the other a running total. Folding them into one series would make
        # every aggregate over it meaningless, so the temporality is part of
        # the kind and therefore part of series identity.
        temporality = metric.sum.aggregation_temporality
        return ("sum_delta" if temporality == 1 else "sum_cumulative"), None
    if which in _UNSUPPORTED_KINDS:
        return None, _UNSUPPORTED_KINDS[which]
    return None, "unknown"


def ingest_metrics(
    db: Session,
    *,
    request,
    credential: IngestCredential,
    settings: Settings,
    now: datetime | None = None,
) -> IngestOutcome:
    """Store what is storable, and say precisely what was not.

    The organisation comes from the credential and never from the payload —
    that is the whole tenant boundary, and an attribute claiming otherwise is
    just an attribute.
    """
    now = now or datetime.now(timezone.utc)
    outcome = IngestOutcome()
    organization_id = credential.organization_id

    budget = cs.load_series_budget(db, organization_id, settings)
    resolver = SeriesResolver(
        db=db, organization_id=organization_id, budget=budget, source="otlp_http"
    )

    rows: list[dict] = []
    total_points = 0

    for resource_metrics in request.resource_metrics:
        raw_resource_attributes = _attributes_to_dict(resource_metrics.resource.attributes)

        try:
            resource = resolve_resource(
                db,
                organization_id=organization_id,
                attributes=raw_resource_attributes,
                # An OTLP client is not trusted to pin a SentinelX identity.
                trusted=False,
                seen_at=now,
            )
        except ResourceResolutionError as exc:
            for scope_metrics in resource_metrics.scope_metrics:
                for metric in scope_metrics.metrics:
                    outcome.reject(
                        cs.Rejection(
                            REJECT_NO_RESOURCE_IDENTITY,
                            metric.name or "<unnamed>",
                            str(exc),
                        )
                    )
            continue

        identifying, _descriptive, _type = split_resource_identity(raw_resource_attributes)
        identity = resource_identity_hash(identifying)

        for scope_metrics in resource_metrics.scope_metrics:
            for metric in scope_metrics.metrics:
                kind, unsupported = _metric_kind(metric)
                if kind is None:
                    outcome.reject(
                        cs.Rejection(
                            REJECT_UNSUPPORTED_METRIC_TYPE,
                            metric.name or "<unnamed>",
                            f"SentinelX stores gauges and sums; {unsupported} points are not "
                            "persisted yet.",
                        )
                    )
                    continue

                name_rejection = cs.validate_metric_name(metric.name, settings)
                if name_rejection is not None:
                    outcome.reject(name_rejection)
                    continue

                data = getattr(metric, metric.WhichOneof("data"))
                for point in data.data_points:
                    total_points += 1
                    if total_points > settings.ingest_max_points_per_request:
                        outcome.reject(
                            cs.Rejection(
                                cs.REJECT_TOO_MANY_POINTS,
                                metric.name,
                                f"Request carries more than "
                                f"{settings.ingest_max_points_per_request} data points.",
                            )
                        )
                        continue

                    row = _prepare_point(
                        point=point,
                        metric=metric,
                        kind=kind,
                        resource=resource,
                        identity=identity,
                        resolver=resolver,
                        organization_id=organization_id,
                        settings=settings,
                        outcome=outcome,
                        now=now,
                    )
                    if row is not None:
                        rows.append(row)

    if rows:
        db.execute(
            pg_insert(MetricPoint)
            .values(rows)
            .on_conflict_do_nothing(constraint="uq_metric_point_series_event")
        )
        outcome.accepted_points = len(rows)

    outcome.new_series = resolver.created_count
    return outcome


def _prepare_point(
    *,
    point,
    metric,
    kind: str,
    resource,
    identity: str,
    resolver: SeriesResolver,
    organization_id,
    settings: Settings,
    outcome: IngestOutcome,
    now: datetime,
) -> dict | None:
    """Validate one data point and turn it into an insertable row."""
    value = _point_value(point)
    if value is None:
        outcome.reject(
            cs.Rejection(
                REJECT_NO_VALUE, metric.name, "Data point carries neither as_double nor as_int."
            )
        )
        return None

    value_rejection = cs.validate_value(value, settings, subject=metric.name)
    if value_rejection is not None:
        outcome.reject(value_rejection)
        return None

    recorded_at = _timestamp(point.time_unix_nano) if point.time_unix_nano else now
    time_rejection = cs.validate_timestamp(recorded_at, settings, subject=metric.name, now=now)
    if time_rejection is not None:
        outcome.reject(time_rejection)
        return None

    attributes = canonical_attributes(_attributes_to_dict(point.attributes))
    attribute_rejection = cs.validate_attributes(attributes, settings, subject=metric.name)
    if attribute_rejection is not None:
        outcome.reject(attribute_rejection)
        return None

    series, series_rejection = resolver.resolve(
        resource=resource,
        resource_identity=identity,
        metric_name=metric.name,
        metric_unit=metric.unit or None,
        metric_kind=kind,
        attributes=attributes,
        seen_at=now,
    )
    if series_rejection is not None:
        outcome.reject(series_rejection)
        return None

    return {
        "id": uuid.uuid4(),
        "recorded_at": recorded_at,
        "organization_id": organization_id,
        "series_id": series.id,
        "value": value,
        # OTLP carries no per-point idempotency key. Leaving this NULL is
        # correct rather than convenient: Postgres treats NULLs as distinct, so
        # the unique constraint simply does not apply to these points, and a
        # fabricated key would silently discard legitimate re-sends.
        "event_id": None,
    }
