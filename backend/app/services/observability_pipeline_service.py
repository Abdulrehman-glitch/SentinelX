"""
Orchestrates the shadow-mode observability pipeline for one or more
devices: classify device class, build pending feature windows, then score
each new window above the quality/sample threshold with the statistical
baseline (always) and IsolationForest (laptop devices only, if a model is
registered). Never writes Alert/Incident/RecoveryAction rows.
"""

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.models.device import Device
from app.services import device_class_service, feature_window_service, isolation_forest_service, statistical_baseline_service
from app.services.telemetry_quality_service import MIN_QUALITY_SCORE_FOR_SCORING


@dataclass
class DeviceRunResult:
    device_id: str
    device_class: str | None
    windows_built: int = 0
    windows_scored: int = 0
    predictions_created: int = 0
    errors: list[str] = field(default_factory=list)
    skipped_reason: str | None = None


@dataclass
class PipelineRunResult:
    devices_processed: int = 0
    windows_built: int = 0
    windows_scored: int = 0
    predictions_created: int = 0
    device_results: list[DeviceRunResult] = field(default_factory=list)


def run_for_device(db: Session, device: Device) -> DeviceRunResult:
    device_class = device_class_service.classify(device)
    result = DeviceRunResult(device_id=str(device.id), device_class=device_class)

    if device_class is None:
        result.skipped_reason = "unclassified_device_type"
        return result

    try:
        windows = feature_window_service.build_pending_windows(db, device, device_class)
    except Exception as exc:  # noqa: BLE001 - one device's failure must not abort the batch
        result.errors.append(f"feature_window_build_failed: {exc}")
        return result

    result.windows_built = len(windows)

    for window in windows:
        if window.quality_score < MIN_QUALITY_SCORE_FOR_SCORING or window.sample_count < feature_window_service.MIN_SAMPLES_PER_WINDOW:
            continue

        result.windows_scored += 1

        try:
            if statistical_baseline_service.score(db, window) is not None:
                result.predictions_created += 1
        except Exception as exc:  # noqa: BLE001
            result.errors.append(f"statistical_baseline_failed:{window.id}:{exc}")

        try:
            if isolation_forest_service.score(db, window) is not None:
                result.predictions_created += 1
        except Exception as exc:  # noqa: BLE001
            result.errors.append(f"isolation_forest_failed:{window.id}:{exc}")

    return result


def run_for_devices(db: Session, devices: list[Device]) -> PipelineRunResult:
    summary = PipelineRunResult()
    for device in devices:
        device_result = run_for_device(db, device)
        summary.devices_processed += 1
        summary.windows_built += device_result.windows_built
        summary.windows_scored += device_result.windows_scored
        summary.predictions_created += device_result.predictions_created
        summary.device_results.append(device_result)
    return summary
