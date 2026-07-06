"""Device profile + dashboard query endpoints (docs/spec/03 §9–10, §21).
C5 hardens the dashboard side further; this is the working baseline."""

import sqlite3
from datetime import timedelta

from fastapi import APIRouter, Depends, Query

from .. import store
from ..deps import get_conn, get_current_device
from ..errors import APIError
from ..models import (
    Alert,
    AlertList,
    DeviceList,
    DeviceSummary,
    ProfileResponse,
    ProfileUpdateRequest,
    ProfileUpdateResponse,
    TelemetryPage,
)
from ..timeutil import utc_now
from ..validation import _parse_iso

router = APIRouter()

ONLINE_WINDOW = timedelta(minutes=5)


@router.get("/profile", response_model=ProfileResponse)
def get_profile(device: sqlite3.Row = Depends(get_current_device)) -> ProfileResponse:
    return ProfileResponse(
        device_id=device["device_id"],
        platform=device["platform"],
        device_name=device["device_name"],
        device_model=device["device_model"],
        os_version=device["os_version"],
        app_version=device["app_version"],
        status=device["status"],
        last_seen=device["last_seen"],
    )


@router.patch("/profile", response_model=ProfileUpdateResponse)
def update_profile(
    body: ProfileUpdateRequest,
    device: sqlite3.Row = Depends(get_current_device),
    conn: sqlite3.Connection = Depends(get_conn),
) -> ProfileUpdateResponse:
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise APIError(422, "VALIDATION_ERROR", "No updatable fields provided")
    updated_at = store.update_profile(conn, device["device_id"], updates)
    return ProfileUpdateResponse(success=True, updated_at=updated_at)


def _presence(last_seen: str | None) -> str:
    if last_seen is None:
        return "offline"
    seen = _parse_iso(last_seen)
    if seen is None:
        return "offline"
    return "online" if utc_now() - seen <= ONLINE_WINDOW else "offline"


def _summarise(conn: sqlite3.Connection, row: sqlite3.Row) -> DeviceSummary:
    battery = store.latest_payload(conn, row["device_id"], "battery")
    thermal = store.latest_payload(conn, row["device_id"], "thermal")
    network = store.latest_payload(conn, row["device_id"], "network")
    return DeviceSummary(
        device_id=row["device_id"],
        device_name=row["device_name"],
        platform=row["platform"],
        status=_presence(row["last_seen"]),
        last_seen=row["last_seen"],
        battery=int(battery["level"]) if battery and "level" in battery else None,
        thermal=thermal.get("state") if thermal else None,
        network=network.get("interface") if network else None,
        active_alerts=store.count_active_alerts(conn, row["device_id"]),
    )


@router.get("/devices", response_model=DeviceList)
def list_devices(conn: sqlite3.Connection = Depends(get_conn)) -> DeviceList:
    rows = conn.execute("SELECT * FROM mobile_devices ORDER BY registered_at").fetchall()
    return DeviceList(items=[_summarise(conn, row) for row in rows])


def _get_device_or_404(conn: sqlite3.Connection, device_id: str) -> sqlite3.Row:
    row = store.find_device(conn, device_id)
    if row is None:
        raise APIError(404, "DEVICE_NOT_FOUND", "Device not found")
    return row


@router.get("/devices/{device_id}", response_model=DeviceSummary)
def get_device(device_id: str, conn: sqlite3.Connection = Depends(get_conn)) -> DeviceSummary:
    return _summarise(conn, _get_device_or_404(conn, device_id))


@router.get("/devices/{device_id}/telemetry", response_model=TelemetryPage)
def device_telemetry(
    device_id: str,
    category: str | None = None,
    time_from: str | None = Query(default=None, alias="from"),
    time_to: str | None = Query(default=None, alias="to"),
    limit: int = Query(default=100, ge=1, le=1000),
    page: int = Query(default=1, ge=1),
    conn: sqlite3.Connection = Depends(get_conn),
) -> TelemetryPage:
    _get_device_or_404(conn, device_id)
    items, total = store.query_events(conn, device_id, category, time_from, time_to, limit, page)
    return TelemetryPage(items=items, page=page, limit=limit, total=total)


@router.get("/devices/{device_id}/alerts", response_model=AlertList)
def device_alerts(device_id: str, conn: sqlite3.Connection = Depends(get_conn)) -> AlertList:
    _get_device_or_404(conn, device_id)
    return AlertList(
        items=[
            Alert(
                alert_id=row["alert_id"],
                device_id=row["device_id"],
                severity=row["severity"],
                category=row["category"],
                rule=row["rule"],
                message=row["message"],
                created_at=row["created_at"],
                resolved=bool(row["resolved"]),
                resolved_at=row["resolved_at"],
            )
            for row in store.list_alerts(conn, device_id)
        ]
    )
