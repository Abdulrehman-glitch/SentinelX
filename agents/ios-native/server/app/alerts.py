"""Server-side alert rules for mobile telemetry ingest."""

from __future__ import annotations

from datetime import timedelta
import sqlite3
from typing import Any

from . import store
from .timeutil import utc_now
from .validation import _parse_iso

OFFLINE_WINDOW = timedelta(minutes=5)


def _alert(
    conn: sqlite3.Connection,
    device_id: str,
    severity: str,
    category: str,
    rule: str,
    message: str,
) -> dict[str, Any] | None:
    if store.find_active_alert(conn, device_id, rule) is not None:
        return None
    return store.create_alert(conn, device_id, severity, category, rule, message)


def _resolve(conn: sqlite3.Connection, device_id: str, rule: str) -> None:
    store.resolve_alert(conn, device_id, rule)


def evaluate_event(
    conn: sqlite3.Connection,
    device_id: str,
    category: str,
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    created: list[dict[str, Any]] = []

    if category == "battery":
        level = payload.get("level")
        if isinstance(level, (int, float)) and level < 10:
            alert = _alert(conn, device_id, "critical", "battery", "BATTERY_CRITICAL",
                           "Battery level is below 10%")
            if alert:
                created.append(alert)
        else:
            _resolve(conn, device_id, "BATTERY_CRITICAL")

        if isinstance(level, (int, float)) and level < 20:
            alert = _alert(conn, device_id, "warning", "battery", "BATTERY_LOW",
                           "Battery level is below 20%")
            if alert:
                created.append(alert)
        else:
            _resolve(conn, device_id, "BATTERY_LOW")

    elif category == "thermal":
        state = payload.get("state")
        if state == "critical":
            alert = _alert(conn, device_id, "critical", "thermal", "THERMAL_CRITICAL",
                           "Device thermal state is critical")
            if alert:
                created.append(alert)
        else:
            _resolve(conn, device_id, "THERMAL_CRITICAL")

        if state == "serious":
            alert = _alert(conn, device_id, "warning", "thermal", "THERMAL_SERIOUS",
                           "Device thermal state is serious")
            if alert:
                created.append(alert)
        else:
            _resolve(conn, device_id, "THERMAL_SERIOUS")

    elif category == "storage":
        free_percent = payload.get("free_percent")
        if free_percent is None and payload.get("total_bytes"):
            free_percent = (payload.get("free_bytes", 0) / payload["total_bytes"]) * 100
        if isinstance(free_percent, (int, float)) and free_percent < 10:
            alert = _alert(conn, device_id, "warning", "storage", "STORAGE_LOW",
                           "Device storage free space is below 10%")
            if alert:
                created.append(alert)
        else:
            _resolve(conn, device_id, "STORAGE_LOW")

    elif category == "network":
        if payload.get("reachable") is False:
            alert = _alert(conn, device_id, "warning", "network", "NETWORK_LOSS",
                           "Device network is unreachable")
            if alert:
                created.append(alert)
        elif payload.get("reachable") is True:
            _resolve(conn, device_id, "NETWORK_LOSS")

    return created


def evaluate_offline_devices(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    created: list[dict[str, Any]] = []
    rows = conn.execute("SELECT device_id, last_seen FROM mobile_devices WHERE status = 'active'").fetchall()
    now = utc_now()
    for row in rows:
        last_seen = _parse_iso(row["last_seen"]) if row["last_seen"] else None
        if last_seen is None or now - last_seen > OFFLINE_WINDOW:
            alert = _alert(conn, row["device_id"], "critical", "device", "DEVICE_OFFLINE",
                           "Device has not sent telemetry or heartbeat for 5 minutes")
            if alert:
                created.append(alert)
        else:
            _resolve(conn, row["device_id"], "DEVICE_OFFLINE")
    return created
