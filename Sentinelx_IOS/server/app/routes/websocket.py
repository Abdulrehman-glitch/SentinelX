"""WebSocket telemetry channel (docs/spec/03 §16–19). First-message auth,
heartbeat/ack, telemetry.event and telemetry.batch ingest. The connection
manager also lets server code push (e.g. alert.created from C4)."""

import json
import sqlite3

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .. import alerts, database, store
from ..config import Settings
from ..security import TokenError, decode_token
from ..timeutil import now_iso
from ..validation import validate_event

router = APIRouter()


class ConnectionManager:
    def __init__(self) -> None:
        self.active: dict[str, WebSocket] = {}

    async def register(self, device_id: str, ws: WebSocket) -> None:
        self.active[device_id] = ws

    def unregister(self, device_id: str) -> None:
        self.active.pop(device_id, None)

    async def push(self, device_id: str, message: dict) -> bool:
        ws = self.active.get(device_id)
        if ws is None:
            return False
        await ws.send_json(message)
        return True


manager = ConnectionManager()


async def _authenticate(ws: WebSocket, device_id: str, settings: Settings, conn: sqlite3.Connection) -> bool:
    """First-message auth. Returns True when accepted, else closes the socket."""
    try:
        raw = await ws.receive_text()
        message = json.loads(raw)
    except (WebSocketDisconnect, json.JSONDecodeError):
        await ws.close(code=4401)
        return False

    token = message.get("access_token", "") if message.get("type") == "auth" else ""
    reason = None
    try:
        token_device = decode_token(settings, token, "access")
        if token_device != device_id or message.get("device_id") != device_id:
            reason = "WEBSOCKET_AUTH_FAILED"
    except TokenError as exc:
        reason = exc.code
    if reason is None and store.find_device(conn, device_id) is None:
        reason = "DEVICE_NOT_FOUND"

    if reason:
        await ws.send_json({"type": "auth.rejected", "reason": reason})
        await ws.close(code=4401)
        return False

    await ws.send_json({"type": "auth.accepted", "device_id": device_id, "server_time": now_iso()})
    return True


def _ingest(conn: sqlite3.Connection, settings: Settings, device_id: str, event: dict) -> dict:
    """Store one WS event dict and report accepted ID, errors, and alerts."""
    required = {"event_id", "timestamp", "category", "type", "source", "payload"}
    missing = required - set(event)
    if missing:
        return {"error": {"type": "error", "code": "VALIDATION_ERROR",
                          "message": f"missing fields: {sorted(missing)}"}}
    if event.get("device_id", device_id) != device_id:
        return {"error": {"type": "error", "code": "VALIDATION_ERROR",
                          "message": "device_id does not match connection"}}
    reason = validate_event(
        event["category"],
        event["timestamp"],
        event["payload"],
        settings.max_event_age_hours,
        settings.max_event_future_minutes,
    )
    if reason:
        return {"error": {"type": "error", "code": "VALIDATION_ERROR",
                          "message": reason, "event_id": str(event.get("event_id"))}}
    inserted = store.insert_event(conn, device_id, event)
    created_alerts = alerts.evaluate_event(conn, device_id, event["category"], event["payload"]) if inserted else []
    return {"accepted_event_id": str(event["event_id"]), "created_alerts": created_alerts}


def _ack(event_ids: list[str]) -> dict:
    return {"type": "telemetry.ack", "event_ids": event_ids, "server_time": now_iso()}


def _check_ws_rate(settings: Settings, ws: WebSocket, device_id: str) -> dict | None:
    retry_after = ws.app.state.rate_limiter.check(
        "ws_message",
        device_id,
        settings.ws_message_limit_per_minute,
    )
    if retry_after is None:
        return None
    return {
        "type": "error",
        "code": "RATE_LIMITED",
        "message": "Too many WebSocket messages",
        "details": {"retry_after_seconds": retry_after},
    }


@router.websocket("/ws/{device_id}")
async def telemetry_ws(ws: WebSocket, device_id: str) -> None:
    settings: Settings = ws.app.state.settings
    await ws.accept()
    conn = database.connect(settings.database_path)
    try:
        if not await _authenticate(ws, device_id, settings, conn):
            return
        await manager.register(device_id, ws)
        store.touch_last_seen(conn, device_id)

        while True:
            raw = await ws.receive_text()
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_json({"type": "error", "code": "VALIDATION_ERROR", "message": "not JSON"})
                continue

            kind = message.get("type")
            rate_error = _check_ws_rate(settings, ws, device_id)
            if rate_error:
                await ws.send_json(rate_error)
                continue

            if kind == "heartbeat":
                store.touch_last_seen(conn, device_id)
                await ws.send_json({"type": "heartbeat.ack", "server_time": now_iso()})
            elif kind == "telemetry.event":
                result = _ingest(conn, settings, device_id, message.get("event") or {})
                if result.get("error"):
                    await ws.send_json(result["error"])
                else:
                    for alert in result["created_alerts"]:
                        await ws.send_json({"type": "alert.created", "alert": alert})
                    store.touch_last_seen(conn, device_id)
                    await ws.send_json(_ack([result["accepted_event_id"]]))
            elif kind == "telemetry.batch":
                accepted_event_ids = []
                for event in message.get("events") or []:
                    result = _ingest(conn, settings, device_id, event)
                    if result.get("error"):
                        await ws.send_json(result["error"])
                        continue
                    accepted_event_ids.append(result["accepted_event_id"])
                    if result.get("created_alerts"):
                        for alert in result["created_alerts"]:
                            await ws.send_json({"type": "alert.created", "alert": alert})
                store.touch_last_seen(conn, device_id)
                await ws.send_json(_ack(accepted_event_ids))
            elif kind == "agent.status":
                store.touch_last_seen(conn, device_id)
            else:
                await ws.send_json({"type": "error", "code": "VALIDATION_ERROR",
                                    "message": f"unknown message type: {kind!r}"})
    except WebSocketDisconnect:
        pass
    finally:
        manager.unregister(device_id)
        conn.close()
