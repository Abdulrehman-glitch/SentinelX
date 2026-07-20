"""Sprint 4-6 Stage 2 coverage: model lifecycle promotion gates, invalid
promotion, retired-model inference rejection, artifact checksum integrity,
evaluation calculations, incomplete labels."""

import uuid
from datetime import datetime, timedelta, timezone

import joblib
import numpy as np
import pytest
from sklearn.ensemble import IsolationForest

from app.ml import model_loader
from app.ml.feature_schemas import FEATURE_SCHEMA_VERSION, LAPTOP_WINDOWS_V1, LAPTOP_WINDOWS_V1_FEATURES
from app.models.anomaly_model import AnomalyModel
from app.models.device import Device
from app.models.model_evaluation_report import ModelEvaluationReport
from app.models.organization import Organization
from app.models.system_metric import SystemMetric
from app.services import feature_window_service, isolation_forest_service, model_evaluation_service
from app.services.model_promotion_service import MIN_REVIEWED_PREDICTIONS, PromotionError, promote, retire


def _make_laptop_device(db, org: Organization) -> Device:
    device = Device(
        hostname=f"laptop-{uuid.uuid4().hex[:8]}",
        os_name="Windows 11 Pro",
        device_type="desktop",
        agent_type="python_desktop_agent",
        organization_id=org.id,
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


def _seed_history(db, device: Device, *, hours: int = 12, interval_minutes: int = 5) -> None:
    now = datetime.now(timezone.utc)
    count = int(hours * 60 / interval_minutes)
    start = now - timedelta(hours=hours)
    for i in range(count):
        db.add(
            SystemMetric(
                organization_id=device.organization_id,
                device_id=device.id,
                event_id=uuid.uuid4(),
                cpu_percent=40.0 + (i % 7),
                memory_percent=55.0 + (i % 5),
                disk_percent=65.0,
                recorded_at=start + timedelta(minutes=i * interval_minutes),
            )
        )
    db.commit()


def _register_isolation_forest(db, artifact_dir, *, lifecycle_status: str = "shadow") -> AnomalyModel:
    rng = np.random.default_rng(42)
    matrix = rng.normal(loc=50.0, scale=5.0, size=(30, len(LAPTOP_WINDOWS_V1_FEATURES)))
    estimator = IsolationForest(n_estimators=50, contamination=0.05, random_state=42)
    estimator.fit(matrix)
    threshold = float(np.percentile(-estimator.decision_function(matrix), 95))

    artifact_path = artifact_dir / f"test_lifecycle_isolation_forest_{uuid.uuid4().hex}.joblib"
    joblib.dump(estimator, artifact_path)
    checksum = model_loader.compute_artifact_checksum(str(artifact_path))

    model = AnomalyModel(
        name=f"isolation_forest_{LAPTOP_WINDOWS_V1}",
        version=f"test-{uuid.uuid4().hex[:8]}",
        device_class=LAPTOP_WINDOWS_V1,
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        algorithm="isolation_forest",
        hyperparameters={"score_threshold": threshold, "feature_order": LAPTOP_WINDOWS_V1_FEATURES},
        dataset_hash="test",
        trained_at=datetime.now(timezone.utc),
        artifact_path=str(artifact_path),
        artifact_checksum=checksum,
        is_active=True,
        lifecycle_status=lifecycle_status,
    )
    db.add(model)
    db.commit()
    db.refresh(model)
    return model


def _make_evaluation(db, model: AnomalyModel, *, reviewed_count: int, true_positives: int, false_positives: int) -> ModelEvaluationReport:
    now = datetime.now(timezone.utc)
    labeled = true_positives + false_positives
    evaluation = ModelEvaluationReport(
        model_id=model.id,
        period_start=now - timedelta(days=1),
        period_end=now,
        prediction_count=reviewed_count + 5,
        reviewed_count=reviewed_count,
        true_positives=true_positives,
        false_positives=false_positives,
        expected_changes=0,
        precision=(true_positives / labeled) if labeled else None,
        false_positive_rate=(false_positives / labeled) if labeled else None,
        detector_agreement_breakdown={},
        supported_device_coverage=3,
        missing_feature_rate=0.0,
        inference_failures=None,
        anomaly_lead_time_seconds_avg=None,
        created_by=None,
    )
    db.add(evaluation)
    db.commit()
    db.refresh(evaluation)
    return evaluation


def _passing_evaluation(db, model: AnomalyModel) -> ModelEvaluationReport:
    return _make_evaluation(db, model, reviewed_count=25, true_positives=20, false_positives=2)


# -- promotion gates -------------------------------------------------------------


class TestPromotionGates:
    def test_promotion_requires_sequential_stage(self, db, org, tmp_path):
        model = _register_isolation_forest(db, tmp_path, lifecycle_status="candidate")
        with pytest.raises(PromotionError, match="one stage forward"):
            promote(db, model, target_status="advisory", actor_id=str(uuid.uuid4()))

    def test_candidate_to_shadow_needs_no_evaluation(self, db, org, tmp_path, admin_user):
        model = _register_isolation_forest(db, tmp_path, lifecycle_status="candidate")
        promote(db, model, target_status="shadow", actor_id=str(admin_user.id))
        assert model.lifecycle_status == "shadow"
        assert model.promoted_at is not None

    def test_shadow_to_advisory_requires_an_evaluation_report(self, db, org, tmp_path):
        model = _register_isolation_forest(db, tmp_path, lifecycle_status="shadow")
        with pytest.raises(PromotionError, match="requires a linked evaluation report"):
            promote(db, model, target_status="advisory", actor_id=str(uuid.uuid4()))

    def test_promotion_blocked_when_reviewed_predictions_insufficient(self, db, org, tmp_path):
        model = _register_isolation_forest(db, tmp_path, lifecycle_status="shadow")
        evaluation = _make_evaluation(db, model, reviewed_count=3, true_positives=2, false_positives=0)
        assert evaluation.reviewed_count < MIN_REVIEWED_PREDICTIONS
        with pytest.raises(PromotionError, match="Insufficient reviewed predictions"):
            promote(db, model, target_status="advisory", actor_id=str(uuid.uuid4()), evaluation=evaluation)

    def test_promotion_blocked_on_feature_schema_mismatch(self, db, org, tmp_path):
        model = _register_isolation_forest(db, tmp_path, lifecycle_status="shadow")
        model.feature_schema_version = "v0-stale"
        db.commit()
        evaluation = _passing_evaluation(db, model)
        with pytest.raises(PromotionError, match="Feature schema mismatch"):
            promote(db, model, target_status="advisory", actor_id=str(uuid.uuid4()), evaluation=evaluation)

    def test_promotion_blocked_on_artifact_checksum_mismatch(self, db, org, tmp_path):
        model = _register_isolation_forest(db, tmp_path, lifecycle_status="shadow")
        model.artifact_checksum = "0" * 64
        db.commit()
        evaluation = _passing_evaluation(db, model)
        with pytest.raises(PromotionError, match="checksum mismatch"):
            promote(db, model, target_status="advisory", actor_id=str(uuid.uuid4()), evaluation=evaluation)

    def test_promotion_blocked_when_false_positive_rate_too_high(self, db, org, tmp_path):
        model = _register_isolation_forest(db, tmp_path, lifecycle_status="shadow")
        evaluation = _make_evaluation(db, model, reviewed_count=25, true_positives=5, false_positives=15)
        with pytest.raises(PromotionError, match="False-positive rate too high"):
            promote(db, model, target_status="advisory", actor_id=str(uuid.uuid4()), evaluation=evaluation)

    def test_evaluation_report_must_belong_to_the_model(self, db, org, tmp_path):
        model_a = _register_isolation_forest(db, tmp_path, lifecycle_status="shadow")
        model_b = _register_isolation_forest(db, tmp_path, lifecycle_status="shadow")
        evaluation_for_b = _passing_evaluation(db, model_b)
        with pytest.raises(PromotionError, match="does not belong to this model"):
            promote(db, model_a, target_status="advisory", actor_id=str(uuid.uuid4()), evaluation=evaluation_for_b)

    def test_full_shadow_to_advisory_promotion_succeeds_when_gates_pass(self, db, org, tmp_path, admin_user):
        model = _register_isolation_forest(db, tmp_path, lifecycle_status="shadow")
        evaluation = _passing_evaluation(db, model)
        promote(db, model, target_status="advisory", actor_id=str(admin_user.id), evaluation=evaluation)
        assert model.lifecycle_status == "advisory"

    def test_cannot_promote_a_retired_model(self, db, org, tmp_path, admin_user):
        model = _register_isolation_forest(db, tmp_path, lifecycle_status="advisory")
        retire(db, model, actor_id=str(admin_user.id), reason="superseded")
        assert model.lifecycle_status == "retired"
        with pytest.raises(PromotionError, match="Cannot promote a retired model"):
            promote(db, model, target_status="alert_eligible", actor_id=str(admin_user.id))

    def test_cannot_retire_an_already_retired_model(self, db, org, tmp_path, admin_user):
        model = _register_isolation_forest(db, tmp_path, lifecycle_status="shadow")
        retire(db, model, actor_id=str(admin_user.id), reason="first retirement")
        with pytest.raises(PromotionError, match="already retired"):
            retire(db, model, actor_id=str(admin_user.id), reason="second retirement")


# -- retired models never score --------------------------------------------------


class TestRetiredModelInference:
    def test_retired_model_never_scores(self, db, org, tmp_path, admin_user):
        # The test DB schema is only reset once per session (see conftest.py),
        # so an earlier test's still-active isolation_forest row could
        # otherwise be picked up instead of the one this test just retired.
        db.query(AnomalyModel).filter(
            AnomalyModel.device_class == LAPTOP_WINDOWS_V1,
            AnomalyModel.algorithm == "isolation_forest",
        ).update({"is_active": False})
        db.commit()

        device = _make_laptop_device(db, org)
        _seed_history(db, device, hours=12)
        windows = feature_window_service.build_pending_windows(db, device, LAPTOP_WINDOWS_V1)
        db.commit()

        model = _register_isolation_forest(db, tmp_path, lifecycle_status="shadow")
        first_result = isolation_forest_service.score(db, windows[-1])
        assert first_result is not None
        db.delete(first_result)
        db.commit()

        retire(db, model, actor_id=str(admin_user.id), reason="test retirement")
        db.commit()

        assert isolation_forest_service.score(db, windows[-1]) is None


class TestArtifactChecksumIntegrity:
    def test_score_returns_none_when_artifact_checksum_mismatches(self, db, org, tmp_path):
        device = _make_laptop_device(db, org)
        _seed_history(db, device, hours=12)
        windows = feature_window_service.build_pending_windows(db, device, LAPTOP_WINDOWS_V1)
        db.commit()

        model = _register_isolation_forest(db, tmp_path, lifecycle_status="shadow")
        model.artifact_checksum = "0" * 64
        db.commit()

        assert isolation_forest_service.score(db, windows[-1]) is None


# -- evaluation calculations ------------------------------------------------------


class TestModelEvaluationService:
    def test_precision_and_false_positive_rate_calculations(self, db, org, tmp_path, admin_user):
        device = _make_laptop_device(db, org)
        _seed_history(db, device, hours=12)
        windows = feature_window_service.build_pending_windows(db, device, LAPTOP_WINDOWS_V1)
        db.commit()
        assert len(windows) >= 4

        model = _register_isolation_forest(db, tmp_path, lifecycle_status="shadow")

        scored = []
        for window in windows[-4:]:
            prediction = isolation_forest_service.score(db, window)
            if prediction is not None:
                scored.append(prediction)
        db.commit()
        assert len(scored) >= 2

        scored[0].review_status = "true_positive"
        scored[1].review_status = "false_positive"
        db.commit()

        now = datetime.now(timezone.utc)
        report = model_evaluation_service.generate_report(
            db, model, period_start=now - timedelta(days=1), period_end=now + timedelta(minutes=1), created_by=admin_user.id
        )
        db.commit()

        assert report.prediction_count == len(scored)
        assert report.reviewed_count == 2
        assert report.true_positives == 1
        assert report.false_positives == 1
        assert report.precision == 0.5
        assert report.false_positive_rate == 0.5

    def test_incomplete_labels_yield_null_precision_not_a_fabricated_number(self, db, org, tmp_path, admin_user):
        device = _make_laptop_device(db, org)
        _seed_history(db, device, hours=12)
        windows = feature_window_service.build_pending_windows(db, device, LAPTOP_WINDOWS_V1)
        db.commit()

        model = _register_isolation_forest(db, tmp_path, lifecycle_status="shadow")
        prediction = isolation_forest_service.score(db, windows[-1])
        db.commit()
        assert prediction.review_status == "unreviewed"

        now = datetime.now(timezone.utc)
        report = model_evaluation_service.generate_report(
            db, model, period_start=now - timedelta(days=1), period_end=now + timedelta(minutes=1), created_by=admin_user.id
        )
        assert report.reviewed_count == 0
        assert report.precision is None
        assert report.false_positive_rate is None

    def test_no_recall_field_on_report(self):
        assert not hasattr(ModelEvaluationReport, "recall")


# -- API: role gating + audit trail (promote/retire) ------------------------------


class TestModelLifecycleApi:
    def test_promote_and_retire_endpoints_work_and_are_role_gated(self, client, db, org, admin_headers, tmp_path):
        model = _register_isolation_forest(db, tmp_path, lifecycle_status="shadow")
        evaluation = _passing_evaluation(db, model)

        promote_resp = client.post(
            f"/api/v1/observability/models/{model.id}/promote",
            json={"target_status": "advisory", "evaluation_report_id": str(evaluation.id)},
            headers=admin_headers,
        )
        assert promote_resp.status_code == 200, promote_resp.text
        assert promote_resp.json()["lifecycle_status"] == "advisory"

        retire_resp = client.post(
            f"/api/v1/observability/models/{model.id}/retire",
            json={"reason": "superseded by newer model"},
            headers=admin_headers,
        )
        assert retire_resp.status_code == 200, retire_resp.text
        assert retire_resp.json()["lifecycle_status"] == "retired"

    def test_viewer_cannot_promote(self, client, db, org, tmp_path):
        model = _register_isolation_forest(db, tmp_path, lifecycle_status="shadow")
        evaluation = _passing_evaluation(db, model)

        from app.core.security import create_access_token, hash_password
        from app.models.user import User

        viewer = User(
            email=f"viewer-{uuid.uuid4().hex[:6]}@test.local",
            full_name="Viewer",
            password_hash=hash_password("x"),
            role="viewer",
            organization_id=org.id,
        )
        db.add(viewer)
        db.commit()
        viewer_headers = {"Authorization": f"Bearer {create_access_token(subject=str(viewer.id))}"}

        resp = client.post(
            f"/api/v1/observability/models/{model.id}/promote",
            json={"target_status": "advisory", "evaluation_report_id": str(evaluation.id)},
            headers=viewer_headers,
        )
        assert resp.status_code == 403
