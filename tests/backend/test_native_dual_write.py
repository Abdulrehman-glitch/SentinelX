"""Native ingest, projected into the canonical model.

The transition strategy is dual-write: `system_metrics` stays authoritative and
every existing feature keeps reading it, while the same samples also land in
`metric_points` so the canonical store fills with real data before anything
depends on it. These tests hold both halves of that bargain — the legacy path
is unchanged, and the projection is genuinely happening.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select

from app.models.metric_point import MetricPoint
from app.models.metric_series import MetricSeries
from app.models.outbox_job import OutboxJob
from app.models.resource import Resource
from app.models.system_metric import SystemMetric
from app.services.outbox_service import JOB_BUILD_FEATURE_WINDOWS


def _post(client, token, **overrides):
    body = {"cpu_percent": 41.0, "memory_percent": 62.5, "disk_percent": 70.0}
    body.update(overrides)
    return client.post(
        "/api/v1/metrics",
        json=body,
        headers={"Authorization": f"Bearer {token}"},
    )


def _series_names(db, org_id):
    return set(
        db.scalars(select(MetricSeries.metric_name).where(MetricSeries.organization_id == org_id))
    )


def _points_for(db, org_id, name):
    return list(
        db.scalars(
            select(MetricPoint.value)
            .join(MetricSeries, MetricSeries.id == MetricPoint.series_id)
            .where(MetricSeries.organization_id == org_id, MetricSeries.metric_name == name)
        )
    )


class TestLegacyPathUnchanged:
    def test_the_response_contract_is_untouched(self, client, enrolled_device, db):
        """Existing agents parse these fields; the projection must be invisible."""
        device, token = enrolled_device
        response = _post(client, token, device_id=str(device.id))

        assert response.status_code == 201, response.text
        body = response.json()
        assert set(body) >= {"metric", "alerts_created", "duplicate"}
        assert body["metric"]["memory_percent"] == 62.5

    def test_the_legacy_row_is_still_written(self, client, enrolled_device, db):
        device, token = enrolled_device
        _post(client, token, device_id=str(device.id))

        stored = db.scalars(select(SystemMetric).where(SystemMetric.device_id == device.id)).all()
        assert len(stored) == 1
        assert stored[0].cpu_percent == 41.0


class TestCanonicalProjection:
    def test_a_sample_becomes_canonical_points(self, client, enrolled_device, db):
        device, token = enrolled_device
        _post(client, token, device_id=str(device.id))

        names = _series_names(db, device.organization_id)
        assert {
            "system.cpu.utilization",
            "system.memory.utilization",
            "system.filesystem.utilization",
        } <= names

        assert _points_for(db, device.organization_id, "system.cpu.utilization") == [41.0]

    def test_the_device_gets_exactly_one_resource(self, client, enrolled_device, db):
        device, token = enrolled_device
        for _ in range(3):
            _post(client, token, device_id=str(device.id))

        resources = db.scalars(select(Resource).where(Resource.device_id == device.id)).all()
        assert len(resources) == 1
        assert resources[0].resource_type == "host"

    def test_repeated_samples_reuse_one_series(self, client, enrolled_device, db):
        """Three samples, three points, still one series."""
        device, token = enrolled_device
        for i in range(3):
            _post(client, token, device_id=str(device.id), cpu_percent=float(i))

        series = db.scalars(
            select(MetricSeries).where(
                MetricSeries.organization_id == device.organization_id,
                MetricSeries.metric_name == "system.cpu.utilization",
            )
        ).all()
        assert len(series) == 1
        assert sorted(_points_for(db, device.organization_id, "system.cpu.utilization")) == [
            0.0,
            1.0,
            2.0,
        ]

    def test_percent_values_are_not_silently_rescaled(self, client, enrolled_device, db):
        """OTel's convention is a 0..1 ratio; SentinelX stores 0..100.

        Rescaling would make every existing alert threshold wrong by two orders
        of magnitude, so the unit is declared as "%" and the number is kept.
        """
        device, token = enrolled_device
        _post(client, token, device_id=str(device.id), cpu_percent=99.5)

        series = db.scalar(
            select(MetricSeries).where(
                MetricSeries.organization_id == device.organization_id,
                MetricSeries.metric_name == "system.cpu.utilization",
            )
        )
        assert series.metric_unit == "%"
        assert 99.5 in _points_for(db, device.organization_id, "system.cpu.utilization")

    def test_a_null_reading_is_skipped_not_zeroed(self, client, enrolled_device, db):
        """"Could not read CPU" and "CPU is idle" are different facts."""
        device, token = enrolled_device
        _post(client, token, device_id=str(device.id), cpu_percent=None)

        assert _points_for(db, device.organization_id, "system.cpu.utilization") == []
        # The readings that WERE available still land.
        assert _points_for(db, device.organization_id, "system.memory.utilization") == [62.5]

    def test_mobile_extras_are_projected(self, client, enrolled_device, db):
        device, token = enrolled_device
        _post(
            client,
            token,
            device_id=str(device.id),
            battery_percent=55.0,
            battery_temperature_c=31.5,
            latency_ms=42.0,
        )

        names = _series_names(db, device.organization_id)
        assert {
            "system.battery.level",
            "system.battery.temperature",
            "network.client.latency",
        } <= names

    def test_a_replayed_sample_does_not_duplicate_points(self, client, enrolled_device, db):
        """Idempotency must hold in the projection too, not just the legacy row."""
        device, token = enrolled_device
        event_id = str(uuid.uuid4())

        first = _post(client, token, device_id=str(device.id), event_id=event_id)
        second = _post(client, token, device_id=str(device.id), event_id=event_id)

        assert first.status_code == 201
        assert second.json()["duplicate"] is True
        assert _points_for(db, device.organization_id, "system.cpu.utilization") == [41.0]


class TestBatchProjection:
    def test_every_sample_in_a_batch_is_projected(self, client, enrolled_device, db):
        """Not just the newest — the batch is history, and history is the point."""
        device, token = enrolled_device
        response = client.post(
            "/api/v1/metrics/batch",
            json={
                "device_id": str(device.id),
                "samples": [
                    {"cpu_percent": 10.0, "memory_percent": 20.0, "disk_percent": 30.0},
                    {"cpu_percent": 11.0, "memory_percent": 21.0, "disk_percent": 31.0},
                    {"cpu_percent": 12.0, "memory_percent": 22.0, "disk_percent": 32.0},
                ],
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 201, response.text
        assert response.json()["stored"] == 3
        assert sorted(_points_for(db, device.organization_id, "system.cpu.utilization")) == [
            10.0,
            11.0,
            12.0,
        ]


class TestDownstreamScheduling:
    def test_ingest_enqueues_feature_window_work(self, client, enrolled_device, db):
        device, token = enrolled_device
        _post(client, token, device_id=str(device.id))

        jobs = db.scalars(
            select(OutboxJob).where(
                OutboxJob.job_type == JOB_BUILD_FEATURE_WINDOWS,
                OutboxJob.organization_id == device.organization_id,
            )
        ).all()
        assert len(jobs) == 1
        assert jobs[0].payload["device_id"] == str(device.id)

    def test_repeated_ingest_coalesces_into_one_job(self, client, enrolled_device, db):
        """A device sampling every 15s must not enqueue a job every 15s."""
        device, token = enrolled_device
        for _ in range(10):
            _post(client, token, device_id=str(device.id))

        count = db.scalar(
            select(func.count())
            .select_from(OutboxJob)
            .where(
                OutboxJob.job_type == JOB_BUILD_FEATURE_WINDOWS,
                OutboxJob.organization_id == device.organization_id,
            )
        )
        assert count == 1

    def test_the_job_is_committed_with_the_telemetry(self, client, enrolled_device, db):
        """Both durable or neither — the whole point of the outbox."""
        from app.db.session import SessionLocal

        device, token = enrolled_device
        _post(client, token, device_id=str(device.id))

        # A fresh session proves both were actually committed, not merely
        # pending in the request's session.
        fresh = SessionLocal()
        try:
            assert (
                fresh.scalar(
                    select(func.count())
                    .select_from(SystemMetric)
                    .where(SystemMetric.device_id == device.id)
                )
                == 1
            )
            assert (
                fresh.scalar(
                    select(func.count())
                    .select_from(OutboxJob)
                    .where(OutboxJob.job_type == JOB_BUILD_FEATURE_WINDOWS)
                )
                >= 1
            )
        finally:
            fresh.close()
