"""
Exports telemetry_feature_windows into a reproducible Parquet dataset for
offline model training.

Reproducible: for a fixed DB state, the same query + deterministic
(device_id, window_start) row ordering always produces byte-identical
output.

Usage:
    python scripts/export_feature_dataset.py --device-class laptop_windows_v1 --out backend/datasets/laptop_windows_v1.parquet
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import pandas as pd  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.db.session import SessionLocal  # noqa: E402
from app.ml.feature_schemas import FEATURE_SCHEMA_VERSION, FEATURE_SCHEMAS  # noqa: E402
from app.models.telemetry_feature_window import TelemetryFeatureWindow  # noqa: E402
from app.services.telemetry_quality_service import MIN_QUALITY_SCORE_FOR_SCORING  # noqa: E402

PROVENANCE_COLUMNS = ["device_id", "organization_id", "window_start", "window_end", "quality_score"]


def export_dataset(device_class: str, out_path: Path, *, min_quality: float = MIN_QUALITY_SCORE_FOR_SCORING) -> Path:
    feature_order = FEATURE_SCHEMAS[device_class]

    db = SessionLocal()
    try:
        windows = list(
            db.scalars(
                select(TelemetryFeatureWindow)
                .where(
                    TelemetryFeatureWindow.device_class == device_class,
                    TelemetryFeatureWindow.feature_schema_version == FEATURE_SCHEMA_VERSION,
                    TelemetryFeatureWindow.quality_score >= min_quality,
                )
                .order_by(TelemetryFeatureWindow.device_id, TelemetryFeatureWindow.window_start)
            )
        )
    finally:
        db.close()

    rows = []
    for window in windows:
        if any(name not in window.features for name in feature_order):
            continue
        row = {name: window.features[name] for name in feature_order}
        row.update(
            device_id=str(window.device_id),
            organization_id=str(window.organization_id),
            window_start=window.window_start.isoformat(),
            window_end=window.window_end.isoformat(),
            quality_score=window.quality_score,
        )
        rows.append(row)

    frame = pd.DataFrame(rows, columns=feature_order + PROVENANCE_COLUMNS)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(out_path, index=False)
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Export a reproducible Parquet training dataset.")
    parser.add_argument("--device-class", required=True, choices=sorted(FEATURE_SCHEMAS.keys()))
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--min-quality", type=float, default=MIN_QUALITY_SCORE_FOR_SCORING)
    args = parser.parse_args()

    out_path = export_dataset(args.device_class, args.out, min_quality=args.min_quality)
    print(f"Exported dataset to {out_path}")


if __name__ == "__main__":
    main()
