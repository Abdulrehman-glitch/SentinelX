"""
Versioned, device-class-specific feature schemas.

Feature order matters: it's the vector order models are trained and scored
on. Never reorder an existing list — add a new schema version instead.
"""

FEATURE_SCHEMA_VERSION = "v1"

LAPTOP_WINDOWS_V1 = "laptop_windows_v1"
ANDROID_MOBILE_V1 = "android_mobile_v1"

_CORE_FEATURES = [
    "cpu_median",
    "cpu_mad",
    "cpu_ewma",
    "cpu_slope",
    "memory_median",
    "memory_mad",
    "memory_ewma",
    "memory_slope",
    "disk_median",
    "disk_mad",
    "disk_ewma",
    "disk_slope",
]

LAPTOP_WINDOWS_V1_FEATURES = list(_CORE_FEATURES)

ANDROID_MOBILE_V1_FEATURES = _CORE_FEATURES + [
    "battery_drain_rate",
    "battery_temperature_median",
    "thermal_hot_ratio",
    "network_metered_ratio",
]

FEATURE_SCHEMAS: dict[str, list[str]] = {
    LAPTOP_WINDOWS_V1: LAPTOP_WINDOWS_V1_FEATURES,
    ANDROID_MOBILE_V1: ANDROID_MOBILE_V1_FEATURES,
}
