"""
Builds tumbling telemetry feature windows for a device from raw
system_metrics samples. Idempotent: re-running never reprocesses a window
already stored (advances a cursor derived from the latest existing window,
or from the device's earliest metric on first run).
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ml import statistics as stats
from app.ml.feature_schemas import ANDROID_MOBILE_V1, FEATURE_SCHEMA_VERSION
from app.models.device import Device
from app.models.system_metric import SystemMetric
from app.models.telemetry_feature_window import TelemetryFeatureWindow
from app.services.telemetry_quality_service import assess_quality

WINDOW_MINUTES = 30
MIN_SAMPLES_PER_WINDOW = 6
# Bounds worst-case backlog processing in one call (100 hours of 30-min windows).
MAX_WINDOWS_PER_CALL = 200

_HOT_THERMAL_STATES = {"moderate", "severe", "critical", "emergency", "shutdown"}
_RAW_TO_PREFIX = {"cpu_percent": "cpu", "memory_percent": "memory", "disk_percent": "disk"}


def _floor_to_window(dt: datetime) -> datetime:
    floored_minute = (dt.minute // WINDOW_MINUTES) * WINDOW_MINUTES
    return dt.replace(minute=floored_minute, second=0, microsecond=0)


def _compute_features(samples: list[SystemMetric], device_class: str) -> dict[str, float]:
    features: dict[str, float] = {}

    for raw_field, prefix in _RAW_TO_PREFIX.items():
        values = [getattr(s, raw_field) for s in samples if getattr(s, raw_field) is not None]
        if not values:
            continue
        median = stats.median(values)
        features[f"{prefix}_median"] = median
        features[f"{prefix}_mad"] = stats.mad(values, center=median)
        features[f"{prefix}_ewma"] = stats.ewma(values)
        features[f"{prefix}_slope"] = stats.slope(values)

    if device_class == ANDROID_MOBILE_V1:
        battery_points = sorted(
            ((s.recorded_at, s.battery_percent) for s in samples if s.battery_percent is not None),
            key=lambda pair: pair[0],
        )
        if len(battery_points) >= 2:
            elapsed_hours = (battery_points[-1][0] - battery_points[0][0]).total_seconds() / 3600
            if elapsed_hours > 0:
                # Positive = draining, negative = charging over the window.
                features["battery_drain_rate"] = (battery_points[0][1] - battery_points[-1][1]) / elapsed_hours

        temps = [s.battery_temperature_c for s in samples if s.battery_temperature_c is not None]
        if temps:
            features["battery_temperature_median"] = stats.median(temps)

        thermal_values = [s.thermal_status for s in samples if s.thermal_status is not None]
        if thermal_values:
            hot_count = sum(1 for t in thermal_values if t in _HOT_THERMAL_STATES)
            features["thermal_hot_ratio"] = hot_count / len(thermal_values)

        metered_values = [s.network_metered for s in samples if s.network_metered is not None]
        if metered_values:
            features["network_metered_ratio"] = sum(1 for v in metered_values if v) / len(metered_values)

    return features


def build_pending_windows(db: Session, device: Device, device_class: str) -> list[TelemetryFeatureWindow]:
    if device.organization_id is None:
        return []

    now = datetime.now(timezone.utc)

    latest_window = db.scalar(
        select(TelemetryFeatureWindow)
        .where(
            TelemetryFeatureWindow.device_id == device.id,
            TelemetryFeatureWindow.feature_schema_version == FEATURE_SCHEMA_VERSION,
        )
        .order_by(TelemetryFeatureWindow.window_end.desc())
        .limit(1)
    )

    if latest_window is not None:
        cursor = latest_window.window_end
    else:
        earliest_recorded_at = db.scalar(
            select(SystemMetric.recorded_at)
            .where(SystemMetric.device_id == device.id)
            .order_by(SystemMetric.recorded_at.asc())
            .limit(1)
        )
        if earliest_recorded_at is None:
            return []
        cursor = _floor_to_window(earliest_recorded_at)

    window_delta = timedelta(minutes=WINDOW_MINUTES)
    created: list[TelemetryFeatureWindow] = []

    for _ in range(MAX_WINDOWS_PER_CALL):
        window_start = cursor
        window_end = window_start + window_delta
        if window_end > now:
            break

        samples = list(
            db.scalars(
                select(SystemMetric)
                .where(
                    SystemMetric.device_id == device.id,
                    SystemMetric.recorded_at >= window_start,
                    SystemMetric.recorded_at < window_end,
                )
                .order_by(SystemMetric.recorded_at.asc())
            )
        )

        cursor = window_end

        if not samples:
            continue

        features = _compute_features(samples, device_class)
        if not features:
            continue

        quality = assess_quality(samples)

        window = TelemetryFeatureWindow(
            organization_id=device.organization_id,
            device_id=device.id,
            device_class=device_class,
            feature_schema_version=FEATURE_SCHEMA_VERSION,
            window_start=window_start,
            window_end=window_end,
            sample_count=len(samples),
            quality_score=quality.score,
            quality_flags=quality.flags,
            features=features,
        )
        db.add(window)
        db.flush()
        created.append(window)

    return created
