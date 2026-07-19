from __future__ import annotations

from sentinelx_agent.store import AgentStore


def test_record_and_read_command_status(store):
    assert store.get_command_status("cmd-1") is None
    store.record_command_received("cmd-1", "nonce-1", "collect_diagnostics")
    assert store.get_command_status("cmd-1") == "received"

    store.update_command_status("cmd-1", "running")
    assert store.get_command_status("cmd-1") == "running"

    store.mark_command_completed("cmd-1")
    assert store.get_command_status("cmd-1") == "completed"


def test_nonce_seen(store):
    assert store.nonce_seen("nonce-xyz") is False
    store.record_command_received("cmd-2", "nonce-xyz", "collect_diagnostics")
    assert store.nonce_seen("nonce-xyz") is True


def test_record_command_received_is_idempotent(store):
    store.record_command_received("cmd-3", "nonce-a", "collect_diagnostics")
    store.update_command_status("cmd-3", "running")
    # A second "receipt" of the same command_id must not reset its status
    # (INSERT OR IGNORE — first receipt wins).
    store.record_command_received("cmd-3", "nonce-a", "collect_diagnostics")
    assert store.get_command_status("cmd-3") == "running"


def test_command_state_survives_process_restart(tmp_path):
    """
    Simulates a crash/restart mid-command: close the AgentStore, reopen the
    exact same SQLite file, and confirm the last durable state is still
    there — this is what lets commands.py resume instead of re-executing or
    losing the result after a real process restart.
    """
    db_path = tmp_path / "restart-test.db"

    store1 = AgentStore(db_path)
    store1.record_command_received("cmd-restart", "nonce-restart", "restart_sentinelx_agent")
    store1.update_command_status("cmd-restart", "acknowledged")
    store1.close()

    store2 = AgentStore(db_path)
    try:
        assert store2.get_command_status("cmd-restart") == "acknowledged"
        assert store2.nonce_seen("nonce-restart") is True
    finally:
        store2.close()


def test_drop_exhausted_removes_high_attempt_rows(store):
    store.enqueue_metric(cpu_percent=10.0, memory_percent=20.0, disk_percent=30.0)
    event_id = store.next_batch()[0].event_id

    for _ in range(25):
        store.mark_failed([event_id])

    dropped = store.drop_exhausted(max_attempts=20)
    assert dropped == 1
    assert store.queue_depth() == 0
