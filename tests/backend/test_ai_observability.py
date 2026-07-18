"""Sprint-2 coverage: feature math, quality validation, detectors, API, RBAC, tenant isolation."""

import uuid
from datetime import datetime, timedelta, timezone

from app.ml import statistics as stats
from app.ml.feature_schemas import FEATURE_SCHEMA_VERSION, LAPTOP_WINDOWS_V1, LAPTOP_WINDOWS_V1_FEATURES
from app.models.anomaly_model import AnomalyModel
from app.models.device import Device
from app.models.organization import Organization
from app.models.system_metric import SystemMetric
from app.services import device_class_service, feature_window_service, isolation_forest_service, statistical_baseline_service
from app.services.telemetry_quality_service import assess_quality


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _make_laptop_device(db, org: Organization) -> Device:
    device = Device(
        hostname=f"laptop-{uuid.uuid4().hex[:8]}",
        display_name="Test Laptop",
        os_name="Windows 11 Pro",
        device_type="desktop",
        agent_type="python_desktop_agent",
        status="online",
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


def _register_test_isolation_forest(db, artifact_dir) -> AnomalyModel:
    import joblib
    import numpy as np
    from sklearn.ensemble import IsolationForest

    rng = np.random.default_rng(42)
    matrix = rng.normal(loc=50.0, scale=5.0, size=(30, len(LAPTOP_WINDOWS_V1_FEATURES)))
    estimator = IsolationForest(n_estimators=50, contamination=0.05, random_state=42)
    estimator.fit(matrix)
    threshold = float(np.percentile(-estimator.decision_function(matrix), 95))

    artifact_path = artifact_dir / f"test_isolation_forest_{uuid.uuid4().hex}.joblib"
    joblib.dump(estimator, artifact_path)

    model = AnomalyModel(
        name=f"isolation_forest_{LAPTOP_WINDOWS_V1}",
        version=f"test-{uuid.uuid4().hex[:8]}",
        device_class=LAPTOP_WINDOWS_V1,
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        algorithm="isolation_forest",
        hyperparameters={"score_threshold": threshold, "feature_order": LAPTOP_WINDOWS_V1_FEATURES},
        dataset_hash="test",
        code_commit=None,
        trained_at=datetime.now(timezone.utc),
        artifact_path=str(artifact_path),
        is_active=True,
    )
    db.add(model)
    db.commit()
    db.refresh(model)
    return model


# -- feature calculations -----------------------------------------------------


class TestStatistics:
    def test_median_and_mad_known_values(self):
        values = [10.0, 12.0, 14.0, 12.0, 100.0]  # 100.0 is an outlier
        median = stats.median(values)
        assert median == 12.0
        mad = stats.mad(values, center=median)
        assert mad == 2.0 * 1.4826  # |10-12|,|12-12|,|14-12|,|12-12|,|100-12| -> median dev = 2.0

    def test_ewma_weights_recent_values_more(self):
        flat = stats.ewma([50.0, 50.0, 50.0], alpha=0.3)
        assert flat == 50.0
        rising = stats.ewma([10.0, 10.0, 90.0], alpha=0.5)
        assert rising > 10.0
        assert rising < 90.0

    def test_slope_detects_trend_direction(self):
        assert stats.slope([10.0, 20.0, 30.0, 40.0]) > 0
        assert stats.slope([40.0, 30.0, 20.0, 10.0]) < 0
        assert stats.slope([50.0, 50.0, 50.0]) == 0.0

    def test_modified_z_score_uses_mad_floor_on_flat_data(self):
        z = stats.modified_z_score(55.0, baseline_median=50.0, baseline_mad=0.0)
        assert z == (55.0 - 50.0) / stats.MAD_FLOOR


# -- data-quality validation ---------------------------------------------------


class TestTelemetryQuality:
    def _sample(self, **overrides) -> SystemMetric:
        defaults = dict(
            cpu_percent=50.0,
            memory_percent=50.0,
            disk_percent=50.0,
            event_id=uuid.uuid4(),
            recorded_at=datetime.now(timezone.utc),
        )
        defaults.update(overrides)
        return SystemMetric(**defaults)

    def test_out_of_range_value_penalised(self):
        good = [self._sample(recorded_at=datetime.now(timezone.utc) - timedelta(minutes=i * 5)) for i in range(6)]
        bad = list(good)
        bad[0] = self._sample(cpu_percent=150.0, recorded_at=good[0].recorded_at)
        assert assess_quality(bad).score < assess_quality(good).score

    def test_duplicate_event_id_penalised(self):
        shared_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        samples = [self._sample(event_id=shared_id, recorded_at=now - timedelta(minutes=i * 5)) for i in range(6)]
        report = assess_quality(samples)
        assert report.flags["duplicate_event_id_count"] == 5
        assert report.score < 1.0

    def test_stale_gap_penalised(self):
        now = datetime.now(timezone.utc)
        samples = [self._sample(recorded_at=now), self._sample(recorded_at=now + timedelta(hours=3))]
        report = assess_quality(samples)
        assert report.flags["stale_gap_count"] == 1
        assert report.score < 1.0

    def test_clock_skew_flagged_for_old_data(self):
        old = datetime.now(timezone.utc) - timedelta(days=2)
        samples = [self._sample(recorded_at=old - timedelta(minutes=i * 5)) for i in range(6)]
        report = assess_quality(samples)
        assert report.flags["clock_skew_seconds"] > 3600

    def test_null_cpu_is_informational_not_penalised(self):
        now = datetime.now(timezone.utc)
        with_null_cpu = [
            self._sample(cpu_percent=None, recorded_at=now - timedelta(minutes=i * 5)) for i in range(6)
        ]
        without_null_cpu = [self._sample(recorded_at=now - timedelta(minutes=i * 5)) for i in range(6)]
        assert assess_quality(with_null_cpu).score == assess_quality(without_null_cpu).score

    def test_empty_samples_returns_zero_score(self):
        assert assess_quality([]).score == 0.0


# -- device classification + feature windows -----------------------------------


class TestDeviceClassAndWindows:
    def test_windows_device_maps_to_laptop_windows_v1(self, db, org):
        device = _make_laptop_device(db, org)
        assert device_class_service.classify(device) == LAPTOP_WINDOWS_V1

    def test_unclassified_device_type_returns_none(self, db, org):
        device = Device(
            hostname=f"cnc-{uuid.uuid4().hex[:8]}",
            device_type="server",
            agent_type="python_desktop_agent",
            os_name="Linux Embedded",
            organization_id=org.id,
        )
        db.add(device)
        db.commit()
        assert device_class_service.classify(device) is None

    def test_build_pending_windows_is_idempotent(self, db, org):
        device = _make_laptop_device(db, org)
        _seed_history(db, device, hours=6)
        first_run = feature_window_service.build_pending_windows(db, device, LAPTOP_WINDOWS_V1)
        db.commit()
        assert len(first_run) > 0
        second_run = feature_window_service.build_pending_windows(db, device, LAPTOP_WINDOWS_V1)
        assert second_run == []


# -- deterministic inference + model loading ------------------------------------


class TestDeterministicInference:
    def test_statistical_baseline_rescoring_is_idempotent(self, db, org):
        device = _make_laptop_device(db, org)
        _seed_history(db, device, hours=12)
        windows = feature_window_service.build_pending_windows(db, device, LAPTOP_WINDOWS_V1)
        db.commit()
        assert len(windows) >= 6

        first = statistical_baseline_service.score(db, windows[-1])
        db.commit()
        second = statistical_baseline_service.score(db, windows[-1])

        assert first is not None
        assert second.id == first.id
        assert second.anomaly_score == first.anomaly_score
        assert second.feature_comparison == first.feature_comparison

    def test_isolation_forest_loads_model_and_scores_deterministically(self, db, org, tmp_path):
        device = _make_laptop_device(db, org)
        _seed_history(db, device, hours=12)
        windows = feature_window_service.build_pending_windows(db, device, LAPTOP_WINDOWS_V1)
        db.commit()

        _register_test_isolation_forest(db, tmp_path)

        first = isolation_forest_service.score(db, windows[-1])
        db.commit()
        second = isolation_forest_service.score(db, windows[-1])

        assert first is not None
        assert second.id == first.id
        assert second.anomaly_score == first.anomaly_score

    def test_isolation_forest_returns_none_without_active_model(self, db, org):
        """Model-version mismatch: no active registry row -> pipeline skips, never errors."""
        # The test DB schema is only reset once per session, so an earlier
        # test's registered model can still be "active" here — clear it to
        # genuinely test the no-active-model precondition regardless of order.
        db.query(AnomalyModel).filter(
            AnomalyModel.device_class == LAPTOP_WINDOWS_V1,
            AnomalyModel.algorithm == "isolation_forest",
        ).update({"is_active": False})
        db.commit()

        device = _make_laptop_device(db, org)
        _seed_history(db, device, hours=12)
        windows = feature_window_service.build_pending_windows(db, device, LAPTOP_WINDOWS_V1)
        db.commit()

        result = isolation_forest_service.score(db, windows[-1])
        assert result is None


# -- API: tenant isolation + RBAC -----------------------------------------------


class TestObservabilityApi:
    def test_pipeline_run_and_list_predictions(self, client, db, org, admin_headers):
        device = _make_laptop_device(db, org)
        _seed_history(db, device, hours=12)

        run_resp = client.post("/api/v1/observability/pipeline/run", json={"device_id": str(device.id)}, headers=admin_headers)
        assert run_resp.status_code == 200, run_resp.text
        body = run_resp.json()
        assert body["devices_processed"] == 1
        assert body["windows_built"] > 0
        assert body["predictions_created"] > 0

        list_resp = client.get(f"/api/v1/observability/anomaly-predictions?device_id={device.id}", headers=admin_headers)
        assert list_resp.status_code == 200
        predictions = list_resp.json()
        assert len(predictions) > 0
        assert all(p["shadow_mode"] is True for p in predictions)
        assert all(p["review_status"] == "unreviewed" for p in predictions)

    def test_review_sets_reviewer_and_timestamp(self, client, db, org, admin_headers, admin_user):
        device = _make_laptop_device(db, org)
        _seed_history(db, device, hours=12)
        client.post("/api/v1/observability/pipeline/run", json={"device_id": str(device.id)}, headers=admin_headers)
        prediction_id = client.get(
            f"/api/v1/observability/anomaly-predictions?device_id={device.id}", headers=admin_headers
        ).json()[0]["id"]

        review_resp = client.patch(
            f"/api/v1/observability/anomaly-predictions/{prediction_id}/review",
            json={"review_status": "expected_change", "review_note": "planned maintenance window"},
            headers=admin_headers,
        )
        assert review_resp.status_code == 200, review_resp.text
        body = review_resp.json()
        assert body["review_status"] == "expected_change"
        assert body["reviewed_by"] == str(admin_user.id)
        assert body["reviewed_at"] is not None

    def test_tenant_isolation_cross_org_404(self, client, db, org, admin_headers):
        device = _make_laptop_device(db, org)
        _seed_history(db, device, hours=12)
        client.post("/api/v1/observability/pipeline/run", json={"device_id": str(device.id)}, headers=admin_headers)
        prediction_id = client.get(
            f"/api/v1/observability/anomaly-predictions?device_id={device.id}", headers=admin_headers
        ).json()[0]["id"]

        from app.core.security import create_access_token, hash_password
        from app.models.user import User

        other_org = Organization(name=f"Other {uuid.uuid4().hex[:8]}", slug=f"other-{uuid.uuid4().hex[:8]}")
        db.add(other_org)
        db.commit()
        other_admin = User(
            email=f"other-admin-{uuid.uuid4().hex[:6]}@test.local",
            full_name="Other Admin",
            password_hash=hash_password("x"),
            role="admin",
            organization_id=other_org.id,
        )
        db.add(other_admin)
        db.commit()
        other_headers = _auth(create_access_token(subject=str(other_admin.id)))

        resp = client.get(f"/api/v1/observability/anomaly-predictions/{prediction_id}", headers=other_headers)
        assert resp.status_code == 404

        list_resp = client.get("/api/v1/observability/anomaly-predictions", headers=other_headers)
        assert list_resp.status_code == 200
        assert list_resp.json() == []

    def test_viewer_can_read_but_not_review_or_run_pipeline(self, client, db, org, admin_headers):
        device = _make_laptop_device(db, org)
        _seed_history(db, device, hours=12)
        client.post("/api/v1/observability/pipeline/run", json={"device_id": str(device.id)}, headers=admin_headers)

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
        viewer_headers = _auth(create_access_token(subject=str(viewer.id)))

        list_resp = client.get("/api/v1/observability/anomaly-predictions", headers=viewer_headers)
        assert list_resp.status_code == 200

        run_resp = client.post("/api/v1/observability/pipeline/run", json={"device_id": str(device.id)}, headers=viewer_headers)
        assert run_resp.status_code == 403

        prediction_id = list_resp.json()[0]["id"]
        review_resp = client.patch(
            f"/api/v1/observability/anomaly-predictions/{prediction_id}/review",
            json={"review_status": "true_positive"},
            headers=viewer_headers,
        )
        assert review_resp.status_code == 403
