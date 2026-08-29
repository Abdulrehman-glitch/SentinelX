"""OTLP logs and traces ingestion.

The metric path already established the shape this follows: decode defensively,
resolve the resource canonically, reject what cannot be represented honestly,
and report per-item failures through OTLP partial success rather than failing
the batch. `otlp_ingest_service` owns the pieces both share - safe gunzip,
AnyValue flattening, timestamps - and this module owns what is specific to the
two new signals.

Three things are specific enough to be worth stating.

**Logs carry secrets by accident.** An HTTP instrumentation library that
records request headers will happily send `authorization: Bearer ...` as a log
attribute, and once that is in a queryable store it is a credential leak with
an index on it. Sensitive keys are redacted (or the record rejected) before
anything is written, and the keys that were redacted are recorded so an
operator can tell an empty field from a refused one. The matcher is
deliberately conservative: it looks at attribute *keys*, never at message
bodies, because scanning arbitrary application text for things that look secret
destroys legitimate logs and still misses the real leaks.

**Bodies and attribute sets are unbounded input.** A single log line can be a
megabyte of stack trace, and a span can carry hundreds of attributes. Both are
bounded at ingest against configured ceilings, and what was dropped is counted
rather than silently discarded.

**A span is not a tree.** Spans are stored flat with a parent pointer, because
children routinely arrive before parents and from different processes. Nothing
here tries to assemble a trace; that happens at read time.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.ingest_credential import IngestCredential
from app.models.log_record import LogRecord, severity_band
from app.models.span import Span, span_kind_name, span_status_name
from app.services.otlp_ingest_service import (
    MalformedPayload,
    PayloadTooLarge,
    _attributes_to_dict,
    _timestamp,
    safe_gunzip,
)
from app.services.resource_service import ResourceResolutionError, resolve_resource

# Attribute keys whose values are credentials often enough that storing them is
# never worth the risk. Matched case-insensitively as substrings of the key, so
# `http.request.header.authorization` and `Authorization` both hit.
#
# Keys only - never bodies. Scanning free text for secret-shaped strings
# mangles legitimate logs and still misses the real leaks.
SENSITIVE_KEY_FRAGMENTS = (
    "authorization",
    "api-key",
    "api_key",
    "apikey",
    "password",
    "passwd",
    "secret",
    "private-key",
    "private_key",
    "access-token",
    "access_token",
    "refresh-token",
    "refresh_token",
    "session-token",
    "session_token",
    "set-cookie",
    "cookie",
    "x-auth-token",
    "credential",
)

REDACTED = "[redacted by SentinelX]"

# What to do when a sensitive key is seen. Redaction keeps the record - and the
# fact that the field was present, which is diagnostically useful; rejection
# drops it entirely, for tenants whose policy is that such data must never be
# accepted at all.
REDACTION_MODES = ("redact", "reject")

REJECT_NO_RESOURCE_IDENTITY = "no_resource_identity"
REJECT_SENSITIVE_ATTRIBUTE = "sensitive_attribute"
REJECT_INVALID_SPAN = "invalid_span"
REJECT_TIMESTAMP_OUT_OF_RANGE = "timestamp_out_of_range"


@dataclass
class SignalOutcome:
    """What happened to one export, in OTLP's partial-success vocabulary."""

    accepted: int = 0
    rejected: int = 0
    reasons: dict[str, int] = field(default_factory=dict)

    def reject(self, reason: str, count: int = 1) -> None:
        self.rejected += count
        self.reasons[reason] = self.reasons.get(reason, 0) + count

    @property
    def error_message(self) -> str:
        if not self.reasons:
            return ""
        parts = [f"{count} {reason}" for reason, count in sorted(self.reasons.items())]
        return "Rejected: " + ", ".join(parts)


def decode_logs_request(body: bytes, *, content_encoding: str | None, settings: Settings):
    from opentelemetry.proto.collector.logs.v1 import logs_service_pb2

    return _decode(body, content_encoding, settings, logs_service_pb2.ExportLogsServiceRequest)


def decode_traces_request(body: bytes, *, content_encoding: str | None, settings: Settings):
    from opentelemetry.proto.collector.trace.v1 import trace_service_pb2

    return _decode(body, content_encoding, settings, trace_service_pb2.ExportTraceServiceRequest)


def _decode(body: bytes, content_encoding: str | None, settings: Settings, message_cls):
    if len(body) > settings.ingest_max_compressed_bytes:
        raise PayloadTooLarge(
            f"Request body is {len(body)} bytes; the limit is "
            f"{settings.ingest_max_compressed_bytes}."
        )

    if (content_encoding or "").strip().lower() == "gzip":
        body = safe_gunzip(body, max_output=settings.ingest_max_decompressed_bytes)

    message = message_cls()
    try:
        message.ParseFromString(body)
    except Exception as exc:
        raise MalformedPayload(f"Body is not a valid OTLP protobuf message: {exc}") from exc
    return message


def _redact(attributes: dict[str, Any], mode: str) -> tuple[dict[str, Any], list[str]]:
    """Strip credential-shaped attributes. Returns (attributes, redacted keys)."""
    redacted: list[str] = []
    cleaned: dict[str, Any] = {}
    for key, value in attributes.items():
        lowered = key.lower()
        if any(fragment in lowered for fragment in SENSITIVE_KEY_FRAGMENTS):
            redacted.append(key)
            if mode == "redact":
                cleaned[key] = REDACTED
            # mode == "reject": the key is dropped entirely, and the caller
            # decides whether to drop the whole record.
            continue
        cleaned[key] = value
    return cleaned, redacted


def _bounded_attributes(raw, settings: Settings, mode: str) -> tuple[dict[str, Any], list[str], int]:
    """Flatten, bound and redact one attribute set."""
    attributes = _attributes_to_dict(raw)
    dropped = 0

    if len(attributes) > settings.ingest_max_attributes:
        # Deterministic: sorted, so the same payload always keeps the same
        # attributes rather than whichever the dict happened to yield first.
        keep = sorted(attributes)[: settings.ingest_max_attributes]
        dropped = len(attributes) - len(keep)
        attributes = {key: attributes[key] for key in keep}

    bounded: dict[str, Any] = {}
    for key, value in attributes.items():
        key = key[: settings.ingest_max_attribute_key_length]
        if isinstance(value, str):
            value = value[: settings.ingest_max_attribute_value_length]
        bounded[key] = value

    cleaned, redacted = _redact(bounded, mode)
    return cleaned, redacted, dropped


def _body_text(body_value, settings: Settings) -> str | None:
    """OTLP log bodies are AnyValue; flatten to text, bounded.

    A structured body is rendered rather than discarded - the message is the
    thing an operator searches, and refusing to store a map because it is not a
    string would lose the log entirely.
    """
    which = body_value.WhichOneof("value")
    if which is None:
        return None
    if which == "string_value":
        text = body_value.string_value
    elif which == "bool_value":
        text = str(body_value.bool_value)
    elif which == "int_value":
        text = str(body_value.int_value)
    elif which == "double_value":
        text = str(body_value.double_value)
    elif which == "kvlist_value":
        text = str(_attributes_to_dict(body_value.kvlist_value.values))
    elif which == "array_value":
        text = str(
            [
                getattr(v, v.WhichOneof("value") or "string_value", None)
                for v in body_value.array_value.values
            ]
        )
    elif which == "bytes_value":
        text = f"<{len(body_value.bytes_value)} bytes>"
    else:
        return None
    return text[: settings.ingest_max_log_body_length]


def _timestamp_admissible(when: datetime, settings: Settings) -> bool:
    """Reject clocks that would write the future or resurrect deep history."""
    now = datetime.now(timezone.utc)
    if (when - now).total_seconds() > settings.ingest_max_future_skew_seconds:
        return False
    if (now - when).days > settings.ingest_max_backfill_age_days:
        return False
    return True


def _resolve(db: Session, credential: IngestCredential, resource_attributes: dict):
    """Resolve (or create) the Resource these records belong to.

    `resolve_resource` already owns identity splitting, resource typing and the
    reserved-attribute rules; an OTLP client is `trusted=False`, so it cannot
    pin a SentinelX identity by sending `sentinelx.*` attributes. Re-deriving
    any of that here would be a second, divergent copy of the rules the metric
    path already follows.
    """
    return resolve_resource(
        db,
        organization_id=credential.organization_id,
        attributes=resource_attributes,
        trusted=False,
        seen_at=datetime.now(timezone.utc),
    )


def _service_fields(resource) -> tuple[str | None, str | None, str | None]:
    """The three attributes every log and trace query filters on."""
    merged = {**(resource.identifying_attributes or {}), **(resource.attributes or {})}
    environment = (
        merged.get("deployment.environment.name") or merged.get("deployment.environment") or None
    )
    version = merged.get("service.version")
    service = merged.get("service.name")
    return (
        str(service)[:255] if service else None,
        str(environment)[:63] if environment else None,
        str(version)[:63] if version else None,
    )


def ingest_logs(
    db: Session, *, request, credential: IngestCredential, settings: Settings
) -> SignalOutcome:
    outcome = SignalOutcome()
    mode = settings.ingest_sensitive_attribute_mode
    rows: list[dict] = []

    for resource_logs in request.resource_logs:
        resource_attributes = _attributes_to_dict(resource_logs.resource.attributes)
        try:
            resource = _resolve(db, credential, resource_attributes)
        except ResourceResolutionError:
            count = sum(len(scope.log_records) for scope in resource_logs.scope_logs)
            outcome.reject(REJECT_NO_RESOURCE_IDENTITY, count or 1)
            continue

        service_name, environment, service_version = _service_fields(resource)

        for scope_logs in resource_logs.scope_logs:
            scope_name = scope_logs.scope.name or None
            scope_version = scope_logs.scope.version or None

            for record in scope_logs.log_records:
                if len(rows) >= settings.ingest_max_log_records_per_request:
                    outcome.reject("too_many_records")
                    continue

                attributes, redacted, dropped = _bounded_attributes(
                    record.attributes, settings, mode
                )
                if redacted and mode == "reject":
                    outcome.reject(REJECT_SENSITIVE_ATTRIBUTE)
                    continue

                # observed_time is what the collector saw; falling back to
                # `time` and then to now keeps a record that omits both, since
                # the alternative is losing a log because a producer was lax.
                observed_ns = record.observed_time_unix_nano or record.time_unix_nano
                observed_at = (
                    _timestamp(observed_ns) if observed_ns else datetime.now(timezone.utc)
                )
                if not _timestamp_admissible(observed_at, settings):
                    outcome.reject(REJECT_TIMESTAMP_OUT_OF_RANGE)
                    continue

                rows.append(
                    {
                        "id": uuid.uuid4(),
                        "organization_id": credential.organization_id,
                        "resource_id": resource.id,
                        "observed_at": observed_at,
                        "timestamp": (
                            _timestamp(record.time_unix_nano) if record.time_unix_nano else None
                        ),
                        "severity_number": record.severity_number or 0,
                        "severity_text": (record.severity_text or None)
                        and record.severity_text[:32],
                        "severity_band": severity_band(record.severity_number),
                        "body": _body_text(record.body, settings),
                        "attributes": attributes,
                        "trace_id": record.trace_id.hex() if record.trace_id else None,
                        "span_id": record.span_id.hex() if record.span_id else None,
                        "scope_name": scope_name[:255] if scope_name else None,
                        "scope_version": scope_version[:63] if scope_version else None,
                        "service_name": service_name,
                        "environment": environment,
                        "service_version": service_version,
                        "dropped_attributes_count": record.dropped_attributes_count + dropped,
                        "redacted_keys": redacted or None,
                    }
                )
                outcome.accepted += 1

    if rows:
        db.execute(pg_insert(LogRecord).values(rows))
    return outcome


def ingest_traces(
    db: Session, *, request, credential: IngestCredential, settings: Settings
) -> SignalOutcome:
    outcome = SignalOutcome()
    mode = settings.ingest_sensitive_attribute_mode
    rows: list[dict] = []

    for resource_spans in request.resource_spans:
        resource_attributes = _attributes_to_dict(resource_spans.resource.attributes)
        try:
            resource = _resolve(db, credential, resource_attributes)
        except ResourceResolutionError:
            count = sum(len(scope.spans) for scope in resource_spans.scope_spans)
            outcome.reject(REJECT_NO_RESOURCE_IDENTITY, count or 1)
            continue

        service_name, environment, service_version = _service_fields(resource)

        for scope_spans in resource_spans.scope_spans:
            scope_name = scope_spans.scope.name or None
            scope_version = scope_spans.scope.version or None

            for span in scope_spans.spans:
                if len(rows) >= settings.ingest_max_spans_per_request:
                    outcome.reject("too_many_spans")
                    continue

                # A span missing either id cannot be joined to anything and
                # cannot be de-duplicated. Storing it would create a row no
                # query can ever reach.
                if not span.trace_id or not span.span_id:
                    outcome.reject(REJECT_INVALID_SPAN)
                    continue

                start = _timestamp(span.start_time_unix_nano) if span.start_time_unix_nano else None
                end = _timestamp(span.end_time_unix_nano) if span.end_time_unix_nano else None
                if start is None or end is None or end < start:
                    outcome.reject(REJECT_INVALID_SPAN)
                    continue
                if not _timestamp_admissible(start, settings):
                    outcome.reject(REJECT_TIMESTAMP_OUT_OF_RANGE)
                    continue

                attributes, redacted, dropped = _bounded_attributes(span.attributes, settings, mode)
                if redacted and mode == "reject":
                    outcome.reject(REJECT_SENSITIVE_ATTRIBUTE)
                    continue

                events = _span_events(span, settings, mode)

                rows.append(
                    {
                        "id": uuid.uuid4(),
                        "organization_id": credential.organization_id,
                        "resource_id": resource.id,
                        "trace_id": span.trace_id.hex(),
                        "span_id": span.span_id.hex(),
                        "parent_span_id": (
                            span.parent_span_id.hex() if span.parent_span_id else None
                        ),
                        "name": (span.name or "(unnamed)")[:255],
                        "kind": span_kind_name(span.kind),
                        "start_time": start,
                        "end_time": end,
                        "duration_ns": max(0, span.end_time_unix_nano - span.start_time_unix_nano),
                        "status_code": span_status_name(span.status.code),
                        "status_message": (span.status.message or None),
                        "attributes": attributes,
                        "events": events or None,
                        "scope_name": scope_name[:255] if scope_name else None,
                        "scope_version": scope_version[:63] if scope_version else None,
                        "service_name": service_name,
                        "environment": environment,
                        "service_version": service_version,
                        "dropped_attributes_count": span.dropped_attributes_count + dropped,
                        "dropped_events_count": span.dropped_events_count,
                        "redacted_keys": redacted or None,
                    }
                )
                outcome.accepted += 1

    if rows:
        # A collector retrying a batch must not duplicate spans. (trace_id,
        # span_id) is unique by definition in OTLP, so a repeat is the same
        # span: ignored rather than counted as a rejection.
        statement = pg_insert(Span).values(rows)
        db.execute(
            statement.on_conflict_do_nothing(
                index_elements=["organization_id", "trace_id", "span_id"]
            )
        )
    return outcome


def _span_events(span, settings: Settings, mode: str) -> list[dict]:
    """Span events, bounded in count and in attribute size."""
    events: list[dict] = []
    for event in span.events[: settings.ingest_max_span_events]:
        attributes, _, _ = _bounded_attributes(event.attributes, settings, mode)
        events.append(
            {
                "name": (event.name or "")[:255],
                "time": (
                    _timestamp(event.time_unix_nano).isoformat() if event.time_unix_nano else None
                ),
                "attributes": attributes,
            }
        )
    return events
