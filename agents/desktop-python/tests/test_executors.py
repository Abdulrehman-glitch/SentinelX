from __future__ import annotations

from unittest.mock import MagicMock

from sentinelx_agent import executors
from sentinelx_agent.executors import ExecutorContext


def _make_context(store, agent_config, client=None):
    return ExecutorContext(config=agent_config, store=store, client=client or MagicMock(), device_id="device-1")


def test_collect_diagnostics_returns_required_fields(store, agent_config):
    ctx = _make_context(store, agent_config)
    result = executors.collect_diagnostics({}, ctx)

    assert result.result_code == "success"
    for field in ("cpu_percent", "memory_percent", "disk_percent", "uptime_seconds"):
        assert field in result.data


def test_rotate_agent_logs_no_file_present(store, agent_config, tmp_path, monkeypatch):
    monkeypatch.setattr("sentinelx_agent.store.default_data_dir", lambda: tmp_path / "nonexistent")
    ctx = _make_context(store, agent_config)
    result = executors.rotate_agent_logs({}, ctx)
    assert result.result_code == "success"
    assert result.data["rotated"] is False


def test_rotate_agent_logs_archives_and_clears(store, agent_config, tmp_path, monkeypatch):
    fake_data_dir = tmp_path / "fake-appdata"
    log_dir = fake_data_dir / "logs"
    log_dir.mkdir(parents=True)
    (log_dir / "agent.log").write_text("some log lines\n", encoding="utf-8")
    monkeypatch.setattr("sentinelx_agent.store.default_data_dir", lambda: fake_data_dir)

    ctx = _make_context(store, agent_config)
    result = executors.rotate_agent_logs({}, ctx)

    assert result.result_code == "success"
    assert result.data["rotated"] is True
    assert (log_dir / "agent.log").read_text(encoding="utf-8") == ""
    archives = list(log_dir.glob("agent.*.log"))
    assert len(archives) == 1


def test_repair_agent_queue_drops_exhausted_rows(store, agent_config):
    store.enqueue_metric(cpu_percent=1.0, memory_percent=2.0, disk_percent=3.0)
    event_id = store.next_batch()[0].event_id
    for _ in range(25):
        store.mark_failed([event_id])

    ctx = _make_context(store, agent_config)
    result = executors.repair_agent_queue({}, ctx)

    assert result.result_code == "success"
    assert result.data["dropped"] == 1
    assert store.queue_depth() == 0


def test_restart_sentinelx_agent_marks_pending_restart(store, agent_config):
    ctx = _make_context(store, agent_config)
    result = executors.restart_sentinelx_agent({}, ctx)

    assert result.result_code == "success"
    assert store.get_state("pending_self_restart") is True


def test_restart_allowlisted_service_rejects_missing_service_key(store, agent_config):
    ctx = _make_context(store, agent_config)
    result = executors.restart_allowlisted_service({}, ctx)
    assert result.result_code == "failure"
    assert "service_key" in result.message


def test_restart_allowlisted_service_rejects_unknown_key(store, agent_config):
    ctx = _make_context(store, agent_config)
    result = executors.restart_allowlisted_service({"service_key": "not_in_allowlist"}, ctx)
    assert result.result_code == "failure"
    assert "allowlist" in result.message


def test_restart_allowlisted_service_calls_net_commands_for_known_key(store, agent_config, monkeypatch):
    monkeypatch.setattr("sentinelx_agent.executors.platform.system", lambda: "Windows")

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return MagicMock(returncode=0)

    monkeypatch.setattr("sentinelx_agent.executors.subprocess.run", fake_run)

    ctx = _make_context(store, agent_config)
    result = executors.restart_allowlisted_service({"service_key": "sentinelx_agent"}, ctx)

    assert result.result_code == "success"
    assert calls == [["net", "stop", "SentinelXAgent"], ["net", "start", "SentinelXAgent"]]


def test_retry_telemetry_sync_flushes_queue(store, agent_config):
    store.enqueue_metric(cpu_percent=5.0, memory_percent=6.0, disk_percent=7.0)

    fake_client = MagicMock()
    fake_client.send_metrics_batch.return_value = {"stored": 1, "duplicates": 0, "alerts_created": 0}

    ctx = _make_context(store, agent_config, client=fake_client)
    result = executors.retry_telemetry_sync({}, ctx)

    assert result.result_code == "success"
    assert result.data["queue_depth_after"] == 0
    fake_client.send_metrics_batch.assert_called_once()
