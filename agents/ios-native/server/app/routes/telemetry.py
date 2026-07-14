"""Telemetry ingest: single event + batch (docs/spec/03 §13–14).
Idempotent by event_id; batch failures are per-event, never whole-batch."""

import sqlite3

from fastapi import APIRouter, Depends, Request

from .. import alerts, store
from ..config import Settings
from ..deps import get_conn, get_current_device, get_settings
from ..errors import APIError
from ..models import (
    BatchRequest,
    BatchResponse,
    RejectedEvent,
    TelemetryAccepted,
    TelemetryEvent,
)
from ..timeutil import now_iso
from ..validation import validate_event
from ..rate_limit import enforce_rate_limit

router = APIRouter()


@router.post("/telemetry", response_model=TelemetryAccepted)
def upload_event(
    body: TelemetryEvent,
    request: Request,
    device: sqlite3.Row = Depends(get_current_device),
    settings: Settings = Depends(get_settings),
    conn: sqlite3.Connection = Depends(get_conn),
) -> TelemetryAccepted:
    enforce_rate_limit(
        request,
        "telemetry",
        device["device_id"],
        settings.telemetry_limit_per_minute,
        "Too many telemetry events",
    )
    if body.device_id != device["device_id"]:
        raise APIError(403, "VALIDATION_ERROR", "device_id does not match authenticated device")
    reason = validate_event(
        body.category.value,
        body.timestamp,
        body.payload,
        settings.max_event_age_hours,
        settings.max_event_future_minutes,
    )
    if reason:
        raise APIError(422, "VALIDATION_ERROR", reason, {"event_id": str(body.event_id)})

    event = body.model_dump(mode="json")
    inserted = store.insert_event(conn, device["device_id"], event)
    if inserted:
        alerts.evaluate_event(conn, device["device_id"], body.category.value, body.payload)
    store.touch_last_seen(conn, device["device_id"])
    return TelemetryAccepted(
        accepted=True,
        event_id=body.event_id,
        stored_at=now_iso(),
        duplicate=not inserted,
    )


@router.post("/batch", response_model=BatchResponse)
def upload_batch(
    body: BatchRequest,
    request: Request,
    device: sqlite3.Row = Depends(get_current_device),
    settings: Settings = Depends(get_settings),
    conn: sqlite3.Connection = Depends(get_conn),
) -> BatchResponse:
    enforce_rate_limit(
        request,
        "batch",
        device["device_id"],
        settings.batch_limit_per_minute,
        "Too many telemetry batches",
    )
    if body.device_id != device["device_id"]:
        raise APIError(403, "VALIDATION_ERROR", "device_id does not match authenticated device")

    accepted = 0
    rejected: list[RejectedEvent] = []
    for event in body.events:
        reason = validate_event(
            event.category.value,
            event.timestamp,
            event.payload,
            settings.max_event_age_hours,
            settings.max_event_future_minutes,
        )
        if reason:
            rejected.append(RejectedEvent(event_id=str(event.event_id), reason=reason))
            continue
        event_data = event.model_dump(mode="json")
        inserted = store.insert_event(conn, device["device_id"], event_data)
        if inserted:
            alerts.evaluate_event(conn, device["device_id"], event.category.value, event.payload)
        accepted += 1  # duplicates count as accepted per spec 03 §25

    store.touch_last_seen(conn, device["device_id"])
    return BatchResponse(
        accepted=True,
        batch_id=body.batch_id,
        accepted_count=accepted,
        rejected_count=len(rejected),
        rejected_events=rejected,
    )
