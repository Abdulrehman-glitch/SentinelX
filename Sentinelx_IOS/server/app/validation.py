"""Per-category payload validation (docs/spec/05 §34). Returns a reason
string when invalid, None when the event is acceptable. Timestamp replay
windows are Codex task C3 — only format is checked here."""

from datetime import datetime, timedelta, timezone
from typing import Any

THERMAL_STATES = {"nominal", "fair", "serious", "critical", "unknown"}


def _parse_iso(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _validate_replay_window(
    timestamp: datetime,
    max_age_hours: int | None,
    max_future_minutes: int | None,
) -> str | None:
    now = datetime.now(timezone.utc)
    if max_age_hours is not None and timestamp < now - timedelta(hours=max_age_hours):
        return f"timestamp is older than {max_age_hours} hours"
    if max_future_minutes is not None and timestamp > now + timedelta(minutes=max_future_minutes):
        return f"timestamp is more than {max_future_minutes} minutes in the future"
    return None


def validate_event(
    category: str,
    timestamp: str,
    payload: dict[str, Any],
    max_age_hours: int | None = None,
    max_future_minutes: int | None = None,
) -> str | None:
    parsed_timestamp = _parse_iso(timestamp)
    if parsed_timestamp is None:
        return "timestamp is not valid ISO 8601"
    replay_reason = _validate_replay_window(parsed_timestamp, max_age_hours, max_future_minutes)
    if replay_reason:
        return replay_reason

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
