"""
Deterministic statistics helpers used by feature-window building and the
statistical baseline detector. Stdlib only — no numpy dependency here so
these stay usable before the ML extras (Stage 4) are installed.
"""

import statistics as _stdlib_statistics

# Scale factor that makes MAD a consistent estimator of the standard
# deviation for normally-distributed data (1 / Phi^-1(0.75)).
_MAD_CONSISTENCY_SCALE = 1.4826

# Floor applied to MAD before it's used as a divisor, so a perfectly flat
# window (MAD == 0) never produces an infinite/undefined z-score.
MAD_FLOOR = 0.5


def median(values: list[float]) -> float:
    return _stdlib_statistics.median(values)


def mad(values: list[float], *, center: float | None = None) -> float:
    """Median absolute deviation, scaled for consistency with std-dev."""
    if center is None:
        center = median(values)
    deviations = [abs(v - center) for v in values]
    return median(deviations) * _MAD_CONSISTENCY_SCALE


def ewma(values: list[float], *, alpha: float = 0.3) -> float:
    """Exponentially weighted moving average, returning the latest value."""
    result = values[0]
    for v in values[1:]:
        result = alpha * v + (1 - alpha) * result
    return result


def slope(values: list[float]) -> float:
    """Least-squares slope of values against their index (0, 1, 2, ...)."""
    n = len(values)
    if n < 2:
        return 0.0
    xs = list(range(n))
    mean_x = sum(xs) / n
    mean_y = sum(values) / n
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, values))
    denominator = sum((x - mean_x) ** 2 for x in xs)
    if denominator == 0:
        return 0.0
    return numerator / denominator


def modified_z_score(value: float, *, baseline_median: float, baseline_mad: float) -> float:
    """Robust z-score; baseline_mad is floored to avoid divide-by-zero on flat data."""
    effective_mad = max(baseline_mad, MAD_FLOOR)
    return (value - baseline_median) / effective_mad
