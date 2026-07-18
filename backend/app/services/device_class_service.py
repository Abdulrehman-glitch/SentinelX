"""
Maps a Device onto a v1 device-class feature schema, or None if the device
isn't in scope for scoring yet. Intentionally narrow: Linux servers,
gateways, and embedded/Arduino devices are not classified in v1 — that's a
deliberate scoping decision, not an oversight (see docs/ai_observability_architecture.md).
"""

from app.ml.feature_schemas import ANDROID_MOBILE_V1, LAPTOP_WINDOWS_V1
from app.models.device import Device


def classify(device: Device) -> str | None:
    if device.device_type == "desktop" and device.os_name and "windows" in device.os_name.lower():
        return LAPTOP_WINDOWS_V1
    if device.device_type == "mobile" and device.agent_type == "android_mobile_agent":
        return ANDROID_MOBILE_V1
    return None
