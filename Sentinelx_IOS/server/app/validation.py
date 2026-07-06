"""Per-category payload validation (docs/spec/05 §34). Returns a reason
string when invalid, None when the event is acceptable. Timestamp replay
windows are Codex task C3 — only format is checked here."""

from datetime import datetime
from typing import Any

THERMAL_STATES = {"nominal", "fair", "serious", "critical", "unknown"}


def _parse_iso(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def validate_event(category: str, timestamp: str, payload: dict[str, Any]) -> str | None:
    if _parse_iso(timestamp) is None:
        return "timestamp is not valid ISO 8601"

    if category == "battery":
        level = payload.get("level")
        if not isinstance(level, (int, float)) or not 0 <= level <= 100:
            return "battery.level must be between 0 and 100"
        for flag in ("charging", "low_power_mode"):
            if flag in payload and not isinstance(payload[flag], bool):
                return f"battery.{flag} must be boolean"

    elif category == "thermal":
        state = payload.get("state")
        if state not in THERMAL_STATES:
            return f"thermal.state must be one of {sorted(THERMAL_STATES)}"

    elif category == "location":
        lat, lon = payload.get("latitude"), payload.get("longitude")
        if not isinstance(lat, (int, float)) or not -90 <= lat <= 90:
            return "location.latitude must be between -90 and 90"
        if not isinstance(lon, (int, float)) or not -180 <= lon <= 180:
            return "location.longitude must be between -180 and 180"

    elif category == "storage":
        total, free = payload.get("total_bytes"), payload.get("free_bytes")
        if not isinstance(total, (int, float)) or total <= 0:
            return "storage.total_bytes must be positive"
        if isinstance(free, (int, float)) and free > total:
            return "storage.free_bytes must not exceed total_bytes"

    return None
