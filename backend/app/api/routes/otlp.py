"""OTLP/HTTP metrics ingestion.

Mounted at `/v1/metrics`, the path the OpenTelemetry specification defines,
rather than under SentinelX's own `/api/v1` prefix. That is deliberate: every
OTLP exporter appends `/v1/metrics` to whatever endpoint it is given, so
serving it anywhere else would mean every client needed a custom path override
— and "OTLP support" that requires bespoke configuration is not really OTLP
support.

What is genuinely implemented, and nothing more:

  * OTLP/HTTP with `application/x-protobuf`
  * `Content-Encoding: gzip`, bounded against decompression bombs
  * Gauge and Sum (delta and cumulative) number data points
  * Partial success, per the specification's rules

Not implemented, and not pretended: OTLP logs, OTLP traces, gRPC transport,
histograms, exponential histograms and summaries. A histogram point is rejected
with a reason that says so, rather than being silently dropped.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Header, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_ingest_credential
from app.core.config import get_settings
from app.core.limiter import limiter
from app.db.session import get_db
from app.models.ingest_credential import IngestCredential
from app.services import ingest_credential_service as ics
from app.services import otlp_ingest_service as otlp
from app.services import outbox_service as ob
from app.services.security_log_service import create_security_log

_settings = get_settings()
_logger = logging.getLogger("sentinelx.otlp")

OTLP_PROTOBUF_CONTENT_TYPE = "application/x-protobuf"

router = APIRouter(tags=["OTLP"])


async def otlp_body(request: Request) -> bytes:
    """Read the raw body on the event loop, before the sync endpoint runs.

    The endpoint itself is sync so its database work happens in the threadpool
    rather than blocking the loop; an async endpoint would have to await the
    body but would then run every SQLAlchemy call on the loop as well.
    """
    return await request.body()


def _protobuf_response(payload: bytes, status_code: int = status.HTTP_200_OK) -> Response:
    return Response(
        content=payload,
        media_type=OTLP_PROTOBUF_CONTENT_TYPE,
        status_code=status_code,
    )


def _export_response(rejected: int = 0, error_message: str = "") -> bytes:
    """Build the protobuf response the specification requires.

    A fully successful export returns an EMPTY ExportMetricsServiceResponse —
    not one with `partial_success` set to zeroes. The specification is explicit
    that an empty `partial_success` means full success, and some clients treat
    a present-but-zero field as a partial failure.
    """
    from opentelemetry.proto.collector.metrics.v1 import metrics_service_pb2

    response = metrics_service_pb2.ExportMetricsServiceResponse()
    if rejected > 0:
        response.partial_success.rejected_data_points = rejected
        response.partial_success.error_message = error_message[:2048]
    return response.SerializeToString()


def _error_response(status_code: int, message: str, retry_after: int | None = None) -> Response:
    """OTLP errors are protobuf Status messages, not SentinelX JSON envelopes.

    A collector parses the body as `google.rpc.Status`; returning this API's
    usual JSON error would produce an unhelpful parse failure on the client
    side instead of the reason it was rejected.
    """
    from google.rpc import status_pb2

    payload = status_pb2.Status(code=status_code, message=message[:2048]).SerializeToString()
    response = _protobuf_response(payload, status_code=status_code)
    if retry_after is not None:
        response.headers["Retry-After"] = str(retry_after)
    return response


@router.post("/v1/metrics", summary="OTLP/HTTP metrics export")
@limiter.limit(_settings.rate_limit_telemetry)
def export_metrics(
    request: Request,
    body: bytes = Depends(otlp_body),
    content_type: str = Header(default="", alias="Content-Type"),
    content_encoding: str | None = Header(default=None, alias="Content-Encoding"),
    credential: IngestCredential = Depends(get_ingest_credential),
    db: Session = Depends(get_db),
) -> Response:
    if not ics.has_scope(credential, ics.SCOPE_METRICS_WRITE):
        return _error_response(
            status.HTTP_403_FORBIDDEN,
            f"This ingest credential lacks the {ics.SCOPE_METRICS_WRITE} scope.",
        )

    # Only protobuf. OTLP/JSON is a legitimate encoding this build does not
    # implement, and accepting the content type while mis-parsing the body
    # would be worse than an honest 415.
    base_content_type = content_type.split(";")[0].strip().lower()
    if base_content_type and base_content_type != OTLP_PROTOBUF_CONTENT_TYPE:
        return _error_response(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            f"SentinelX accepts {OTLP_PROTOBUF_CONTENT_TYPE}; OTLP/JSON is not implemented.",
        )

    # Backpressure before parsing. If the worker cannot drain what has already
    # been accepted, taking more work in helps nobody — and telling the client
    # to come back later is exactly what OTLP's retry semantics are for.
    backlog = ob.queue_stats(db).backlog
    if backlog >= _settings.ingest_backlog_shed_threshold:
        _logger.warning("shedding OTLP export: outbox backlog %s", backlog)
        return _error_response(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "SentinelX is shedding ingest load while its processing backlog drains.",
            retry_after=30,
        )

    try:
        parsed = otlp.decode_request(body, content_encoding=content_encoding, settings=_settings)
    except otlp.PayloadTooLarge as exc:
        _log_rejection(db, credential, request, "payload_too_large", str(exc))
        return _error_response(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, str(exc))
    except otlp.MalformedPayload as exc:
        _log_rejection(db, credential, request, "malformed_payload", str(exc))
        return _error_response(status.HTTP_400_BAD_REQUEST, str(exc))

    outcome = otlp.ingest_metrics(db, request=parsed, credential=credential, settings=_settings)

    if ics.touch_last_used(credential):
        db.add(credential)

    db.commit()

    if outcome.rejected_points:
        # Rejections are security-relevant: a runaway attribute, or a client
        # sending garbage, is something an operator needs to be able to see.
        _log_rejection(
            db,
            credential,
            request,
            "partial_rejection",
            outcome.error_message,
            rejected=outcome.rejected_points,
        )

    return _protobuf_response(_export_response(outcome.rejected_points, outcome.error_message))


def _log_rejection(
    db: Session,
    credential: IngestCredential,
    request: Request,
    event: str,
    detail: str,
    rejected: int = 0,
) -> None:
    try:
        create_security_log(
            db,
            event_type="telemetry_rejected",
            action=event,
            message=f"OTLP export rejected: {detail}"[:1000],
            severity="warning",
            actor_type="ingest_credential",
            actor_id=str(credential.id),
            organization_id=credential.organization_id,
            ip_address=request.client.host if request.client else None,
            resource_type="otlp_export",
            resource_id=str(credential.id),
            status="failure",
            metadata={"rejected_data_points": rejected, "credential_name": credential.name},
        )
        db.commit()
    except Exception:
        # Never fail an export because the audit write failed.
        db.rollback()
        _logger.exception("failed to record OTLP rejection security log")
