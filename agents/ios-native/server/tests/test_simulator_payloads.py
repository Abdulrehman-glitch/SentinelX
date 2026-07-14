from __future__ import annotations

from datetime import datetime
from uuid import UUID

import pytest

from server.tools.simulator_payloads import (
    BATTERY_STATES,
    CATEGORIES,
    NETWORK_INTERFACES,
    THERMAL_STATES,
    PayloadGenerator,
    make_generator,
    values_are_finite,
)


DEVICE_ID = "dev_01JZIOS001"


def test_generates_spec_envelopes_for_core_categories() -> None:
    generator = make_generator(seed=42)

    for sequence, category in enumerate(CATEGORIES):
        event = generator.make_event(category, DEVICE_ID, sequence)

        UUID(event["event_id"])
        assert event["device_id"] == DEVICE_ID
        assert event["timestamp"].endswith("Z")
        datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))
        assert event["category"] == category
        assert event["type"].startswith(f"{category}.")
        assert event["source"].startswith("ios.")
        assert event["sequence"] == sequence
        assert isinstance(event["payload"], dict)
        assert event["metadata"]["platform"] == "ios"
        assert event["metadata"]["agent_version"] == "1.0.0"


def test_seeded_generator_is_deterministic_except_event_ids() -> None:
    first = PayloadGenerator(seed=7)
    second = PayloadGenerator(seed=7)

    first_events = [first.make_event(category, DEVICE_ID, index) for index, category in enumerate(CATEGORIES * 4)]
    second_events = [second.make_event(category, DEVICE_ID, index) for index, category in enumerate(CATEGORIES * 4)]

    for left, right in zip(first_events, second_events, strict=True):
        left_without_id = {key: value for key, value in left.items() if key != "event_id"}
        right_without_id = {key: value for key, value in right.items() if key != "event_id"}
        assert left_without_id == right_without_id


def test_property_style_validation_rules_hold_for_1000_iterations() -> None:
    generator = PayloadGenerator(seed=100)

    for sequence in range(1000):
        for category in CATEGORIES:
            event = generator.make_event(category, DEVICE_ID, sequence)
            payload = event["payload"]

            assert event["category"] in CATEGORIES
            assert isinstance(payload, dict)
            assert values_are_finite(payload)

            if category == "battery":
                assert 0 <= payload["level"] <= 100
                assert isinstance(payload["charging"], bool)
                assert payload["state"] in BATTERY_STATES
                assert isinstance(payload["low_power_mode"], bool)
            elif category == "thermal":
                assert payload["state"] in THERMAL_STATES
            elif category == "storage":
                assert payload["total_bytes"] > 0
                assert 0 <= payload["free_bytes"] <= payload["total_bytes"]
                assert payload["used_bytes"] == payload["total_bytes"] - payload["free_bytes"]
                assert 0 <= payload["free_percent"] <= 100
            elif category == "network":
                assert isinstance(payload["reachable"], bool)
                assert payload["interface"] in NETWORK_INTERFACES
                assert isinstance(payload["expensive"], bool)
                assert isinstance(payload["constrained"], bool)
                if not payload["reachable"]:
                    assert payload["interface"] == "unavailable"
            elif category == "device":
                assert payload["system_name"] == "iOS"
                assert payload["screen_width"] > 0
                assert payload["screen_height"] > 0
                assert payload["screen_scale"] > 0


def test_unknown_category_is_rejected() -> None:
    with pytest.raises(ValueError, match="unsupported telemetry category"):
        PayloadGenerator(seed=1).make_event("cpu", DEVICE_ID, 1)
