"""Spec-aligned telemetry payload generators for the mobile simulator."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
import math
import random
from typing import Any
from uuid import uuid4


CATEGORIES = ("device", "battery", "thermal", "storage", "network")

EVENT_DEFINITIONS = {
    "device": ("device.snapshot", "ios.uikit"),
    "battery": ("battery.snapshot", "ios.uidevice"),
    "thermal": ("thermal.state", "ios.processinfo"),
    "storage": ("storage.snapshot", "ios.filemanager"),
    "network": ("network.status", "ios.network"),
}

BATTERY_STATES = ("unknown", "unplugged", "charging", "full")
THERMAL_STATES = ("nominal", "fair", "serious", "critical", "unknown")
NETWORK_INTERFACES = (
    "wifi",
    "cellular",
    "wired_ethernet",
    "loopback",
    "other",
    "unavailable",
)


def utc_timestamp(at: datetime | None = None) -> str:
    """Return an ISO 8601 UTC timestamp using the API's trailing-Z style."""

    value = at or datetime.now(UTC)
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass
class PayloadGenerator:
    """Stateful simulator data source with deterministic seeded mode."""

    seed: int | None = None
    start_time: datetime | None = None
    rng: random.Random = field(init=False)

    def __post_init__(self) -> None:
        self.rng = random.Random(self.seed)
        base_time = self.start_time or datetime(2026, 7, 5, 18, 15, tzinfo=UTC)
        if base_time.tzinfo is None:
            base_time = base_time.replace(tzinfo=UTC)
        self.start_time = base_time.astimezone(UTC)

    def make_event(self, category: str, device_id: str, sequence: int) -> dict[str, Any]:
        if category not in EVENT_DEFINITIONS:
            raise ValueError(f"unsupported telemetry category: {category}")

        event_type, source = EVENT_DEFINITIONS[category]
        timestamp = self.start_time + timedelta(seconds=max(sequence, 0))
        return {
            "event_id": str(uuid4()),
            "device_id": device_id,
            "timestamp": utc_timestamp(timestamp),
            "category": category,
            "type": event_type,
            "source": source,
            "sequence": sequence,
            "payload": self.payload_for(category, sequence),
            "metadata": {
                "platform": "ios",
                "agent_version": "1.0.0",
                "collector_version": "1.0.0",
                "schema_version": "1.0",
            },
        }

    def payload_for(self, category: str, sequence: int) -> dict[str, Any]:
        if category == "device":
            return self.device_payload(sequence)
        if category == "battery":
            return self.battery_payload(sequence)
        if category == "thermal":
            return self.thermal_payload(sequence)
        if category == "storage":
            return self.storage_payload(sequence)
        if category == "network":
            return self.network_payload(sequence)
        raise ValueError(f"unsupported telemetry category: {category}")

    def device_payload(self, sequence: int = 0) -> dict[str, Any]:
        models = ("iPhone 15", "iPhone 15 Pro", "iPhone 14", "iPhone SE")
        widths = (390, 393, 402, 430)
        heights = (844, 852, 874, 932)
        index = sequence % len(models)
        return {
            "device_name": "SentinelX Simulator iPhone",
            "device_model": models[index],
            "system_name": "iOS",
            "system_version": "17.5",
            "locale": "en_GB",
            "timezone": "Europe/London",
            "screen_width": widths[index],
            "screen_height": heights[index],
            "screen_scale": 3,
        }

    def battery_payload(self, sequence: int = 0) -> dict[str, Any]:
        cycle = sequence % 240
        charging = cycle >= 160
        if charging:
            level = min(100, 15 + int((cycle - 160) * 1.08))
        else:
            level = max(5, 96 - int(cycle * 0.5))

        if level == 100:
            state = "full"
        elif charging:
            state = "charging"
        else:
            state = "unplugged"

        return {
            "level": level,
            "charging": charging,
            "state": state,
            "low_power_mode": level <= 20 and not charging,
        }

    def thermal_payload(self, sequence: int = 0) -> dict[str, Any]:
        walk = (
            "nominal",
            "nominal",
            "fair",
            "fair",
            "serious",
            "critical",
            "serious",
            "fair",
        )
        return {"state": walk[(sequence // 8) % len(walk)]}

    def storage_payload(self, sequence: int = 0) -> dict[str, Any]:
        total_bytes = 128_000_000_000
        drift = min(sequence * 45_000_000, total_bytes - 1)
        jitter = self.rng.randint(0, 120_000_000)
        used_bytes = min(total_bytes, 72_000_000_000 + drift + jitter)
        free_bytes = max(0, total_bytes - used_bytes)
        return {
            "total_bytes": total_bytes,
            "free_bytes": free_bytes,
            "used_bytes": used_bytes,
            "free_percent": round((free_bytes / total_bytes) * 100, 2),
        }

    def network_payload(self, sequence: int = 0) -> dict[str, Any]:
        flap = sequence % 30
        if flap in (14, 15):
            interface = "unavailable"
            reachable = False
        elif (sequence // 12) % 2 == 0:
            interface = "wifi"
            reachable = True
        else:
            interface = "cellular"
            reachable = True

        return {
            "reachable": reachable,
            "interface": interface,
            "expensive": interface == "cellular",
            "constrained": interface == "cellular" and sequence % 10 in (0, 1),
        }


def make_generator(seed: int | None = None) -> PayloadGenerator:
    return PayloadGenerator(seed=seed)


_DEFAULT_GENERATOR = PayloadGenerator()


def make_event(category: str, device_id: str, sequence: int) -> dict[str, Any]:
    return _DEFAULT_GENERATOR.make_event(category, device_id, sequence)


def battery_payload(sequence: int = 0, seed: int | None = None) -> dict[str, Any]:
    return PayloadGenerator(seed=seed).battery_payload(sequence)


def thermal_payload(sequence: int = 0, seed: int | None = None) -> dict[str, Any]:
    return PayloadGenerator(seed=seed).thermal_payload(sequence)


def network_payload(sequence: int = 0, seed: int | None = None) -> dict[str, Any]:
    return PayloadGenerator(seed=seed).network_payload(sequence)


def storage_payload(sequence: int = 0, seed: int | None = None) -> dict[str, Any]:
    return PayloadGenerator(seed=seed).storage_payload(sequence)


def device_payload(sequence: int = 0, seed: int | None = None) -> dict[str, Any]:
    return PayloadGenerator(seed=seed).device_payload(sequence)


def values_are_finite(payload: dict[str, Any]) -> bool:
    for value in payload.values():
        if isinstance(value, dict):
            if not values_are_finite(value):
                return False
        elif isinstance(value, (int, float)) and not math.isfinite(value):
            return False
    return True
