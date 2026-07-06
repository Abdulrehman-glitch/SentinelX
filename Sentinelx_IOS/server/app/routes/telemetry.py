"""Telemetry ingest: single event + batch (docs/spec/03 §13–14).
Idempotent by event_id; batch failures are per-event, never whole-batch."""

import sqlite3

from fastapi import APIRouter, Depends

from .. import store
from ..deps import get_conn, get_current_device
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

router = APIRouter()


@router.post("/telemetry", response_model=TelemetryAccepted)
def upload_event(
    body: TelemetryEvent,
    device: sqlite3.Row = Depends(get_current_device),
    conn: sqlite3.Connection = Depends(get_conn),
) -> TelemetryAccepted:
    if body.device_id != device["device_id"]:
        raise APIError(403, "VALIDATION_ERROR", "device_id does not match authenticated device")
    reason = validate_event(body.category.value, body.timestamp, body.payload)
    if reason:
        raise APIError(422, "VALIDATION_ERROR", reason, {"event_id": str(body.event_id)})

    inserted = store.insert_event(conn, device["device_id"], body.model_dump(mode="json"))
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
    device: sqlite3.Row = Depends(get_current_device),
    conn: sqlite3.Connection = Depends(get_conn),
) -> BatchResponse:
    if body.device_id != device["device_id"]:
        raise APIError(403, "VALIDATION_ERROR", "device_id does not match authenticated device")

    accepted = 0
    rejected: list[RejectedEvent] = []
    for event in body.events:
        reason = validate_event(event.category.value, event.timestamp, event.payload)
        if reason:
            rejected.append(RejectedEvent(event_id=str(event.event_id), reason=reason))
            continue
        store.insert_event(conn, device["device_id"], event.model_dump(mode="json"))
        accepted += 1  # duplicates count as accepted per spec 03 §25

    store.touch_last_seen(conn, device["device_id"])
    return BatchResponse(
        accepted=True,
        batch_id=body.batch_id,
        accepted_count=accepted,
        rejected_count=len(rejected),
        rejected_events=rejected,
    )
