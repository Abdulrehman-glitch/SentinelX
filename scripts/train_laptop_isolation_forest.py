"""
Trains the first unsupervised laptop_windows_v1 IsolationForest model from
an exported Parquet dataset (see export_feature_dataset.py), and registers
it in the anomaly_models table. Deactivates any previously active model for
this device class so only one is ever active at a time.

Training is an offline, manual step by design — never triggered from a web
request. See docs/ai_observability_architecture.md.

Usage:
    python scripts/train_laptop_isolation_forest.py --dataset backend/datasets/laptop_windows_v1.parquet --version 1.0.0
"""

import argparse
import hashlib
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import joblib  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.ensemble import IsolationForest  # noqa: E402

from app.db.session import SessionLocal  # noqa: E402
from app.ml.feature_schemas import FEATURE_SCHEMA_VERSION, LAPTOP_WINDOWS_V1, LAPTOP_WINDOWS_V1_FEATURES  # noqa: E402
from app.models.anomaly_model import AnomalyModel  # noqa: E402

MODEL_NAME = f"isolation_forest_{LAPTOP_WINDOWS_V1}"
CONTAMINATION = 0.05
N_ESTIMATORS = 200
RANDOM_STATE = 42

ARTIFACT_DIR = Path(__file__).resolve().parents[1] / "backend" / "app" / "ml" / "artifacts"
REPO_ROOT = Path(__file__).resolve().parents[1]


def _dataset_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _code_commit() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT).decode().strip()
    except Exception:
        return None


def train(dataset_path: Path, version: str) -> AnomalyModel:
    frame = pd.read_parquet(dataset_path)
    if len(frame) < 20:
        raise ValueError(
            f"Need at least 20 training rows for a meaningful IsolationForest, got {len(frame)}. "
            "Run the observability pipeline against more device history first."
        )

    matrix = frame[LAPTOP_WINDOWS_V1_FEATURES].to_numpy()

    estimator = IsolationForest(n_estimators=N_ESTIMATORS, contamination=CONTAMINATION, random_state=RANDOM_STATE)
    estimator.fit(matrix)

    # Threshold = the contamination-th percentile of negated training scores
    # (same "higher = more anomalous" scale used at inference), stored so it
    # never needs recomputing from training data at scoring time.
    training_scores = -estimator.decision_function(matrix)
    score_threshold = float(np.percentile(training_scores, 100 * (1 - CONTAMINATION)))

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    artifact_path = ARTIFACT_DIR / f"{MODEL_NAME}__{version}.joblib"
    joblib.dump(estimator, artifact_path)

    db = SessionLocal()
    try:
        db.query(AnomalyModel).filter(
            AnomalyModel.device_class == LAPTOP_WINDOWS_V1,
            AnomalyModel.algorithm == "isolation_forest",
        ).update({"is_active": False})

        model_row = AnomalyModel(
            id=uuid.uuid4(),
            name=MODEL_NAME,
            version=version,
            device_class=LAPTOP_WINDOWS_V1,
            feature_schema_version=FEATURE_SCHEMA_VERSION,
            algorithm="isolation_forest",
            hyperparameters={
                "n_estimators": N_ESTIMATORS,
                "contamination": CONTAMINATION,
                "random_state": RANDOM_STATE,
                "score_threshold": score_threshold,
                "feature_order": LAPTOP_WINDOWS_V1_FEATURES,
            },
            dataset_hash=_dataset_hash(dataset_path),
            code_commit=_code_commit(),
            trained_at=datetime.now(timezone.utc),
            artifact_path=str(artifact_path),
            is_active=True,
        )
        db.add(model_row)
        db.commit()
        db.refresh(model_row)
        return model_row
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the laptop_windows_v1 IsolationForest model.")
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()

    model_row = train(args.dataset, args.version)
    print(f"Registered model {model_row.name}:{model_row.version} (id={model_row.id}) artifact={model_row.artifact_path}")


if __name__ == "__main__":
    main()
