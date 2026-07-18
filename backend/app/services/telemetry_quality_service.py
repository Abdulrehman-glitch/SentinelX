"""
Data-quality validation for a candidate feature window's raw samples.

Produces a deterministic quality_score in [0, 1] plus explanatory flags —
covers value-range validity, missing/null fields, stale gaps between
samples, duplicate/null event_id ratio, and clock skew (staleness at
window-build time). Forward clock skew at ingestion is already impossible
post-Sprint-1's clamp in metrics.py, so this only measures how stale the
newest sample in a window is relative to "now".
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.models.system_metric import SystemMetric

# Matches the desktop/mobile agents' default telemetry interval.
EXPECTED_SAMPLE_INTERVAL_SECONDS = 300
STALE_GAP_MULTIPLIER = 3

_RANGE_BOUNDS: dict[str, tuple[float, float]] = {
    "cpu_percent": (0.0, 100.0),
    "memory_percent": (0.0, 100.0),
    "disk_percent": (0.0, 100.0),
    "battery_percent": (0.0, 100.0),
    "battery_temperature_c": (-40.0, 120.0),
}

MIN_QUALITY_SCORE_FOR_SCORING = 0.6


@dataclass(frozen=True)
class QualityReport:
    score: float
    flags: dict[str, Any]


def assess_quality(samples: list[SystemMetric]) -> QualityReport:
    if not samples:
        return QualityReport(score=0.0, flags={"reason": "no_samples"})

    ordered = sorted(samples, key=lambda s: s.recorded_at)
    n = len(ordered)
    now = datetime.now(timezone.utc)

    out_of_range = 0
    null_cpu = 0
    null_event_id = 0
    duplicate_event_ids = 0
    seen_event_ids: set = set()

    for sample in ordered:
        for field_name, (low, high) in _RANGE_BOUNDS.items():
            value = getattr(sample, field_name, None)
            if value is not None and not (low <= value <= high):
                out_of_range += 1
        if sample.cpu_percent is None:
            null_cpu += 1
        if sample.event_id is None:
            null_event_id += 1
        elif sample.event_id in seen_event_ids:
            duplicate_event_ids += 1
        else:
            seen_event_ids.add(sample.event_id)

    gaps = [(b.recorded_at - a.recorded_at).total_seconds() for a, b in zip(ordered, ordered[1:])]
    stale_gap_count = sum(1 for g in gaps if g > EXPECTED_SAMPLE_INTERVAL_SECONDS * STALE_GAP_MULTIPLIER)
    max_gap_seconds = max(gaps) if gaps else 0.0

    clock_skew_seconds = max((now - ordered[-1].recorded_at).total_seconds(), 0.0)

    out_of_range_ratio = out_of_range / n
    duplicate_ratio = duplicate_event_ids / n
    stale_ratio = stale_gap_count / max(len(gaps), 1)
    is_stale_window = clock_skew_seconds > EXPECTED_SAMPLE_INTERVAL_SECONDS * STALE_GAP_MULTIPLIER

    score = 1.0
    score -= min(out_of_range_ratio, 1.0) * 0.4
    score -= min(duplicate_ratio, 1.0) * 0.3
    score -= min(stale_ratio, 1.0) * 0.2
    score -= 0.1 if is_stale_window else 0.0
    score = max(0.0, min(1.0, score))

    flags = {
        "sample_count": n,
        "out_of_range_count": out_of_range,
        "out_of_range_ratio": round(out_of_range_ratio, 4),
        "null_cpu_ratio": round(null_cpu / n, 4),
        "null_event_id_ratio": round(null_event_id / n, 4),
        "duplicate_event_id_count": duplicate_event_ids,
        "max_gap_seconds": max_gap_seconds,
        "stale_gap_count": stale_gap_count,
        "clock_skew_seconds": clock_skew_seconds,
    }

    return QualityReport(score=score, flags=flags)
