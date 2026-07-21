"""Sprint 7 Phase 7: the 17 E2E release scenarios, run for real against the
live native staging stack (docs/releases/STAGING.md) — real HTTP over the
wire against a real running backend process + real Postgres, never
TestClient, never sentinelx_dev/prod/DevPulse.

Covers scenarios 1-14 (15-17 — migration/backup/rollback — are covered
separately, see docs/releases/STAGING.md and the Phase 7 roadmap note, since
they're about the database/deploy pipeline rather than the running API).

Two steps use direct DB access rather than pure HTTP, both documented
inline rather than hidden:
  - Recovery policies (scenarios 9/10): no HTTP endpoint exists yet to
    create a RecoveryPolicy row, and the seed script creates none — a real,
    separately-noted gap. Inserted directly for this run.
  - Scenario 8's fired-rule Alert: the hybrid pipeline only reads Alert
    rows whose created_at falls inside the (already-closed, ~30-minute)
    feature window being scored. Waiting 30 real minutes for a window to
    close naturally isn't practical here, so the qualifying Alert is
    inserted directly with a backdated created_at instead of waiting.
    Every other assertion in scenarios 6-8 is a real HTTP round trip.

Run (staging stack must already be up per docs/releases/STAGING.md):
    cd backend && PYTHONPATH=. .venv/Scripts/python.exe -m pytest \
        ../tests/e2e/test_staging_release_scenarios.py -v -s
"""

import time
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import psycopg
import pytest

BASE_URL = "http://127.0.0.1:8200/api/v1"
DB_DSN = "postgresql://sentinelx_app:SentinelX_app_2026!@localhost:5432/sentinelx_staging"
PASSWORD = "SentinelX2026!"


def _log(msg: str) -> None:
    print(f"[E2E] {msg}")


@pytest.fixture(scope="module")
def client():
    with httpx.Client(base_url=BASE_URL, timeout=15.0) as c:
        yield c


@pytest.fixture(scope="module")
def db_conn():
    conn = psycopg.connect(DB_DSN, autocommit=True)
    yield conn
    conn.close()


def _login(client: httpx.Client, email: str) -> str:
    resp = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 200, f"login failed for {email}: {resp.text}"
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def technova_admin_token(client):
    return _login(client, "ops@technova.io")


@pytest.fixture(scope="module")
def apex_admin_token(client):
    return _login(client, "ops@apexrobotics.io")


@pytest.fixture(scope="module")
def viewer_token(client):
    return _login(client, "viewer@technova.io")


@pytest.fixture(scope="module")
def platform_admin_token(client):
    return _login(client, "admin@sentinelx.io")


@pytest.fixture(scope="module")
def recovery_policies(db_conn):
    """Direct-DB setup (see module docstring): no HTTP endpoint exists yet
    to create RecoveryPolicy rows, and none are seeded. Global (org-agnostic)
    policies for two allowlisted actions used by scenarios 9-12."""
    with db_conn.cursor() as cur:
        cur.execute("DELETE FROM recovery_policies WHERE action_type IN ('collect_diagnostics', 'restart_sentinelx_agent')")
        cur.execute(
            """
            INSERT INTO recovery_policies (id, organization_id, action_type, risk_level, approval_mode, enabled, cooldown_seconds, daily_execution_limit, verification_window_seconds)
            VALUES
                (%s, NULL, 'collect_diagnostics', 'low', 'auto', true, 0, 100, 300),
                (%s, NULL, 'restart_sentinelx_agent', 'medium', 'manual', true, 0, 100, 300)
            """,
            (str(uuid.uuid4()), str(uuid.uuid4())),
        )
    _log("Inserted global recovery policies: collect_diagnostics=low/auto, restart_sentinelx_agent=medium/manual")
    yield


# ---------------------------------------------------------------------------
# Scenario 1: User authentication and RBAC
# ---------------------------------------------------------------------------

def test_scenario_01_authentication_and_rbac(client):
    _log("Scenario 1: user authentication and RBAC")

    ok = client.post("/auth/login", json={"email": "ops@technova.io", "password": PASSWORD})
    assert ok.status_code == 200
    token = ok.json()["access_token"]
    _log(f"  login OK for ops@technova.io, token issued (len={len(token)})")

    bad = client.post("/auth/login", json={"email": "ops@technova.io", "password": "wrong-password"})
    assert bad.status_code == 401
    _log("  wrong password correctly rejected with 401")

    me = client.get("/auth/me", headers=_auth(token))
    assert me.status_code == 200
    assert me.json()["role"] == "admin"
    _log(f"  /auth/me confirms role=admin for the logged-in user")


# ---------------------------------------------------------------------------
# Scenario 2: One-time agent enrolment
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def enrolled_device(client, technova_admin_token):
    _log("Scenario 2: one-time agent enrolment")
    hostname = f"e2e-desktop-{uuid.uuid4().hex[:8]}"

    code_resp = client.post(
        "/devices/enrollment-codes",
        json={"name": f"e2e-code-{uuid.uuid4().hex[:6]}", "expires_in_minutes": 15},
        headers=_auth(technova_admin_token),
    )
    assert code_resp.status_code == 201, code_resp.text
    raw_code = code_resp.json()["code"]
    _log(f"  minted enrollment code {code_resp.json()['code_preview']}...")

    enroll_resp = client.post(
        "/devices/enroll",
        json={
            "enrollment_code": raw_code,
            "hostname": hostname,
            "os_name": "E2E Test OS",
            "device_type": "desktop",
            "agent_type": "python_desktop_agent",
            "agent_version": "3.0.0",
        },
    )
    assert enroll_resp.status_code == 201, enroll_resp.text
    body = enroll_resp.json()
    device_id = body["device"]["id"]
    device_token = body["device_token"]
    _log(f"  enrolled device {device_id} ({hostname}), device_token issued")

    replay = client.post(
        "/devices/enroll",
        json={
            "enrollment_code": raw_code,
            "hostname": f"{hostname}-replay-attempt",
            "device_type": "desktop",
            "agent_type": "python_desktop_agent",
        },
    )
    assert replay.status_code in (400, 401, 409, 422), (
        f"expected re-use of a one-time enrolment code to be rejected, got {replay.status_code}: {replay.text}"
    )
    _log(f"  re-using the same one-time code correctly rejected with {replay.status_code}")

    return {"device_id": device_id, "hostname": hostname, "device_token": device_token}


def test_scenario_02_one_time_enrolment(enrolled_device):
    assert enrolled_device["device_id"]
    assert enrolled_device["device_token"].startswith("sxa_")


# ---------------------------------------------------------------------------
# Scenario 3: Android telemetry collection while offline and later replay
# (server-side contract only — a live Android device pass is Phase 9, not
# reproducible from this shell. This proves the mechanism that makes
# offline-then-replay work: batched historical samples keep their
# client-captured timestamps rather than landing as "now".)
# ---------------------------------------------------------------------------

def test_scenario_03_offline_batch_preserves_historical_timestamps(client, enrolled_device):
    _log("Scenario 3: offline telemetry batch replay (server-side contract; Android live-device pass is Phase 9)")
    device_id = enrolled_device["device_id"]
    token = enrolled_device["device_token"]

    now = datetime.now(timezone.utc)
    captured_offline = [now - timedelta(minutes=m) for m in (40, 35, 30, 25, 20)]
    samples = [
        {
            "event_id": str(uuid.uuid4()),
            "recorded_at": ts.isoformat(),
            "cpu_percent": 40.0,
            "memory_percent": 50.0,
            "disk_percent": 60.0,
            "battery_percent": 55.0,
        }
        for ts in captured_offline
    ]

    resp = client.post(
        "/metrics/batch",
        json={"device_id": device_id, "samples": samples},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    _log(f"  flushed {len(samples)}-sample offline batch: {body}")


def test_scenario_03b_historical_timestamps_are_queryable_by_an_admin(client, technova_admin_token, enrolled_device):
    device_id = enrolled_device["device_id"]
    resp = client.get(f"/metrics/device/{device_id}", headers=_auth(technova_admin_token))
    assert resp.status_code == 200, resp.text
    samples = resp.json()
    assert len(samples) >= 5
    recorded_ats = sorted(s["recorded_at"] for s in samples)
    oldest, newest = recorded_ats[0], recorded_ats[-1]
    assert oldest != newest, "batched samples should retain distinct historical recorded_at values, not collapse to 'now'"
    _log(f"  confirmed {len(samples)} samples retained distinct historical recorded_at values ({oldest} .. {newest})")


# ---------------------------------------------------------------------------
# Scenario 4: Desktop SQLite queue replay — the real desktop agent package
# (not mocked), a real local SQLite queue, flushed against the real staging
# server over real HTTP.
# ---------------------------------------------------------------------------

def test_scenario_04_desktop_sqlite_queue_replay(tmp_path, enrolled_device):
    _log("Scenario 4: desktop SQLite queue replay (real sentinelx_agent package, real HTTP, real SQLite file)")
    import sys
    from pathlib import Path

    desktop_agent_root = Path(__file__).resolve().parents[2] / "agents" / "desktop-python"
    sys.path.insert(0, str(desktop_agent_root))
    try:
        from sentinelx_agent.store import AgentStore  # noqa: PLC0415

        store_path = tmp_path / "e2e-agent-queue.db"
        store = AgentStore(store_path, max_queue_rows=1000)
        try:
            now = datetime.now(timezone.utc)
            for i, minutes_ago in enumerate((30, 24, 18, 12, 6, 1)):
                store.enqueue_metric(
                    cpu_percent=45.0 + i,
                    memory_percent=55.0,
                    disk_percent=65.0,
                    captured_at=now - timedelta(minutes=minutes_ago),
                )
            _log(f"  enqueued 6 samples into a real on-disk SQLite queue at {store_path} (simulating an offline window)")
        finally:
            store.close()

        # Reopen fresh, simulating a process restart while still offline —
        # proves the queue survives a restart, not just an in-memory list.
        store = AgentStore(store_path, max_queue_rows=1000)
        try:
            assert store.queue_depth() == 6
            batch = store.next_batch(limit=100)
            assert len(batch) == 6
            _log(f"  reopened the store after a simulated restart — all 6 rows survived (queue_depth={store.queue_depth()})")

            device_id = enrolled_device["device_id"]
            device_token = enrolled_device["device_token"]
            resp = httpx.post(
                f"{BASE_URL}/metrics/batch",
                json={"device_id": device_id, "samples": [row.to_sample() for row in batch]},
                headers=_auth(device_token),
                timeout=15.0,
            )
            assert resp.status_code == 201, resp.text
            store.mark_delivered([row.event_id for row in batch])
            assert store.queue_depth() == 0
            _log(f"  flushed the real queue against the live staging server over real HTTP: {resp.json()}; queue now empty")
        finally:
            store.close()
    finally:
        sys.path.remove(str(desktop_agent_root))


# ---------------------------------------------------------------------------
# Scenario 5: Duplicate telemetry event rejection
# ---------------------------------------------------------------------------

def test_scenario_05_duplicate_telemetry_event_rejected(client, enrolled_device):
    _log("Scenario 5: duplicate telemetry event rejection")
    device_id = enrolled_device["device_id"]
    token = enrolled_device["device_token"]
    event_id = str(uuid.uuid4())
    payload = {
        "device_id": device_id,
        "event_id": event_id,
        "cpu_percent": 33.0,
        "memory_percent": 44.0,
        "disk_percent": 55.0,
    }

    first = client.post("/metrics", json=payload, headers=_auth(token))
    assert first.status_code == 201, first.text
    assert first.json()["duplicate"] is False
    metric_id = first.json()["metric"]["id"]
    _log(f"  first POST with event_id={event_id} stored, metric id={metric_id}")

    second = client.post("/metrics", json=payload, headers=_auth(token))
    assert second.status_code == 201, second.text
    assert second.json()["duplicate"] is True
    assert second.json()["metric"]["id"] == metric_id
    _log("  retried POST with the same event_id acknowledged as a duplicate, not stored twice")


# ---------------------------------------------------------------------------
# Scenarios 6-8: hybrid detection generation + rule authority over AI
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def hybrid_test_device(client, technova_admin_token):
    """A dedicated device for scenarios 6-8, so their crafted feature
    windows don't interact with scenarios 3-5's data on the shared
    enrolled_device."""
    code_resp = client.post(
        "/devices/enrollment-codes",
        json={"name": f"e2e-hybrid-code-{uuid.uuid4().hex[:6]}", "expires_in_minutes": 15},
        headers=_auth(technova_admin_token),
    )
    assert code_resp.status_code == 201
    enroll_resp = client.post(
        "/devices/enroll",
        json={
            "enrollment_code": code_resp.json()["code"],
            "hostname": f"e2e-hybrid-{uuid.uuid4().hex[:8]}",
            "device_type": "desktop",
            "agent_type": "python_desktop_agent",
            "os_name": "Windows 11 Pro",  # device_class_service.classify() requires "windows" in os_name
        },
    )
    assert enroll_resp.status_code == 201
    body = enroll_resp.json()
    return {"device_id": body["device"]["id"], "device_token": body["device_token"]}


def _post_closed_window_batch(client, device_id, token, *, cpu_percent, windows_ago=3):
    """Posts 7 samples inside a single, already-closed 30-minute tumbling
    window (feature_window_service.WINDOW_MINUTES=30, floored to :00/:30
    wall-clock boundaries — MUST align explicitly, or samples spanning an
    arbitrary N-minute range can straddle two windows and under-fill both).
    windows_ago=1 is the most recently closed window; higher numbers go
    further back, so independent calls land in distinct, non-overlapping
    windows without waiting for anything to close in real time."""
    now = datetime.now(timezone.utc)
    floored_now = now.replace(minute=(now.minute // 30) * 30, second=0, microsecond=0)
    window_start = floored_now - timedelta(minutes=30 * windows_ago)

    samples = [
        {
            "event_id": str(uuid.uuid4()),
            "recorded_at": (window_start + timedelta(minutes=offset)).isoformat(),
            "cpu_percent": cpu_percent,
            "memory_percent": 50.0,
            "disk_percent": 50.0,
        }
        for offset in (2, 6, 10, 14, 18, 22, 26)
    ]
    resp = client.post("/metrics/batch", json={"device_id": device_id, "samples": samples}, headers=_auth(token))
    assert resp.status_code == 201, resp.text
    return window_start, window_start + timedelta(minutes=30)


def test_scenario_06_hybrid_decision_generation(client, technova_admin_token, hybrid_test_device):
    _log("Scenario 6: hybrid detection decision generation")
    device_id = hybrid_test_device["device_id"]
    token = hybrid_test_device["device_token"]

    _post_closed_window_batch(client, device_id, token, cpu_percent=50.0, windows_ago=4)

    pipeline = client.post("/observability/pipeline/run", json={"device_id": device_id}, headers=_auth(technova_admin_token))
    assert pipeline.status_code == 200, pipeline.text
    _log(f"  observability pipeline run: {pipeline.json()}")

    hybrid = client.post("/hybrid/decisions/run", json={"device_id": device_id}, headers=_auth(technova_admin_token))
    assert hybrid.status_code == 200, hybrid.text
    _log(f"  hybrid decisions run: {hybrid.json()}")
    assert hybrid.json()["decisions_created"] >= 1

    decisions = client.get("/hybrid/decisions", params={"device_id": device_id}, headers=_auth(technova_admin_token))
    assert decisions.status_code == 200
    assert len(decisions.json()) >= 1
    _log(f"  {len(decisions.json())} HybridDecision row(s) now queryable for this device")


def test_scenario_07_model_only_anomaly_stays_advisory(client, technova_admin_token, hybrid_test_device):
    _log("Scenario 7: model-only anomaly remains advisory (never reaches 'critical' without a fired rule)")
    device_id = hybrid_test_device["device_id"]
    token = hybrid_test_device["device_token"]

    # A second, later, still-normal window — no deterministic rule can have
    # fired for it (no Alert exists for this device at all at this point).
    _post_closed_window_batch(client, device_id, token, cpu_percent=52.0, windows_ago=3)
    client.post("/observability/pipeline/run", json={"device_id": device_id}, headers=_auth(technova_admin_token))
    client.post("/hybrid/decisions/run", json={"device_id": device_id}, headers=_auth(technova_admin_token))

    decisions = client.get("/hybrid/decisions", params={"device_id": device_id}, headers=_auth(technova_admin_token)).json()
    assert decisions, "expected at least one hybrid decision"
    for decision in decisions:
        assert decision["combined_severity"] != "critical", (
            f"decision {decision['id']} reached 'critical' with no fired rule behind it: {decision}"
        )
        assert decision["review_status"] == "unreviewed"
    _log(f"  all {len(decisions)} decision(s) with no fired rule stayed below 'critical' and unreviewed (advisory only)")


def test_scenario_08_critical_rule_retains_authority_over_ai(client, technova_admin_token, db_conn, hybrid_test_device):
    _log("Scenario 8: a fired critical deterministic rule retains authority over AI evidence")
    device_id = hybrid_test_device["device_id"]
    token = hybrid_test_device["device_token"]

    window_start, window_end = _post_closed_window_batch(
        client, device_id, token, cpu_percent=50.0, windows_ago=2
    )

    # Direct-DB setup (see module docstring): a critical Alert backdated to
    # fall inside this specific closed window, standing in for what the
    # live /metrics ingestion path (anomaly_service.py's 95% CPU threshold)
    # would itself have created had this window still been open when a
    # critical sample arrived.
    alert_id = str(uuid.uuid4())
    with db_conn.cursor() as cur:
        cur.execute("SELECT organization_id FROM devices WHERE id = %s", (device_id,))
        (org_id,) = cur.fetchone()
        backdated_at = window_start + (window_end - window_start) / 2
        cur.execute(
            """
            INSERT INTO alerts (id, organization_id, device_id, alert_type, severity, message, resolved, created_at)
            VALUES (%s, %s, %s, 'cpu_high', 'critical', 'E2E scenario 8: simulated fired critical rule', false, %s)
            """,
            (alert_id, org_id, device_id, backdated_at),
        )
    _log(f"  inserted a backdated critical Alert ({alert_id}) inside the closed window {window_start}..{window_end}")

    client.post("/observability/pipeline/run", json={"device_id": device_id}, headers=_auth(technova_admin_token))
    hybrid = client.post("/hybrid/decisions/run", json={"device_id": device_id}, headers=_auth(technova_admin_token))
    assert hybrid.status_code == 200, hybrid.text

    decisions = client.get("/hybrid/decisions", params={"device_id": device_id}, headers=_auth(technova_admin_token)).json()
    matching = [d for d in decisions if d["rule_result"].get("fired") and alert_id in d["rule_result"].get("alert_ids", [])]
    assert matching, f"expected a decision whose rule_result references alert {alert_id}; got {decisions}"
    decision = matching[0]
    assert decision["combined_severity"] == "critical", decision
    _log(f"  decision {decision['id']}: rule_result.fired=True, combined_severity=critical — rule authority upheld")


# ---------------------------------------------------------------------------
# Scenarios 9-12: recovery command lifecycle
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def recovery_test_device(client, technova_admin_token, recovery_policies):
    code_resp = client.post(
        "/devices/enrollment-codes",
        json={"name": f"e2e-recovery-code-{uuid.uuid4().hex[:6]}", "expires_in_minutes": 15},
        headers=_auth(technova_admin_token),
    )
    assert code_resp.status_code == 201
    enroll_resp = client.post(
        "/devices/enroll",
        json={
            "enrollment_code": code_resp.json()["code"],
            "hostname": f"e2e-recovery-{uuid.uuid4().hex[:8]}",
            "device_type": "desktop",
            "agent_type": "python_desktop_agent",
        },
    )
    assert enroll_resp.status_code == 201
    body = enroll_resp.json()
    device_id, device_token = body["device"]["id"], body["device_token"]

    # A command only gets dispatched to a device that has reported it
    # supports the action_type (recovery_command_service.get_next_command_for_device
    # rejects the command outright otherwise) — mirrors what a real agent
    # does on startup via POST /agent/capabilities.
    caps = client.post(
        "/agent/capabilities",
        json={
            "agent_type": "python_desktop_agent",
            "agent_version": "3.0.0",
            "capabilities": [
                {"action_type": "collect_diagnostics", "local_risk_level": "low"},
                {"action_type": "restart_sentinelx_agent", "local_risk_level": "medium"},
            ],
        },
        headers=_auth(device_token),
    )
    assert caps.status_code == 204, caps.text

    return {"device_id": device_id, "device_token": device_token}


def test_scenario_09_low_risk_signed_command_executes_successfully(client, technova_admin_token, recovery_test_device):
    _log("Scenario 9: low-risk signed recovery command executes successfully")
    device_id = recovery_test_device["device_id"]
    device_token = recovery_test_device["device_token"]

    create = client.post(
        "/recovery-commands",
        json={"device_id": device_id, "action_type": "collect_diagnostics", "parameters": {}, "reason": "E2E scenario 9"},
        headers=_auth(technova_admin_token),
    )
    assert create.status_code == 201, create.text
    command = create.json()
    assert command["risk_level"] == "low"
    assert command["status"] == "approved", f"expected auto-approval for a low-risk policy, got {command}"
    _log(f"  command {command['id']} auto-approved by policy (risk_level=low)")

    next_cmd = client.get("/agent/commands/next", headers=_auth(device_token))
    assert next_cmd.status_code == 200
    dispatched = next_cmd.json()
    assert dispatched is not None and dispatched["id"] == command["id"]
    assert dispatched["status"] == "dispatched"
    assert dispatched["signature"], "dispatched command must be signed"
    _log(f"  agent polled and received the command dispatched+signed (signature len={len(dispatched['signature'])})")

    # Verify the signature for real, using the actual backend public key and
    # the actual canonical-payload/verify routine the desktop agent ships.
    import sys
    from pathlib import Path

    desktop_agent_root = Path(__file__).resolve().parents[2] / "agents" / "desktop-python"
    sys.path.insert(0, str(desktop_agent_root))
    try:
        from sentinelx_agent.signing import verify_command_signature  # noqa: PLC0415

        pubkey_resp = client.get("/agent/public-key", headers=_auth(device_token))
        assert pubkey_resp.status_code == 200
        public_key_b64 = pubkey_resp.json()["public_key"]

        verify_payload = {
            "id": dispatched["id"],
            "device_id": device_id,
            "action_type": dispatched["action_type"],
            "parameters_json": dispatched["parameters_json"],
            "command_nonce": dispatched["command_nonce"],
            "expires_at": dispatched["expires_at"],
            "policy_id": dispatched["policy_id"],
            "signature": dispatched["signature"],
        }
        assert verify_command_signature(verify_payload, public_key_b64) is True
        _log("  signature independently verified with the real desktop-agent signing.verify_command_signature()")
    finally:
        sys.path.remove(str(desktop_agent_root))

    ack = client.post(f"/agent/commands/{command['id']}/acknowledge", headers=_auth(device_token))
    assert ack.status_code == 200, ack.text

    started = client.post(f"/agent/commands/{command['id']}/start", headers=_auth(device_token))
    assert started.status_code == 200, started.text

    completed = client.post(
        f"/agent/commands/{command['id']}/complete",
        json={
            "result_code": "success",
            "result_message": "diagnostics collected",
            "result_data": {"cpu_percent": 41.0, "memory_percent": 52.0, "disk_percent": 63.0, "uptime_seconds": 12345},
        },
        headers=_auth(device_token),
    )
    assert completed.status_code == 200, completed.text
    final = completed.json()
    assert final["status"] == "verified", final
    assert final["verification_status"] == "verified"
    _log(f"  command executed end-to-end: dispatched -> acknowledged -> running -> succeeded -> verifying -> {final['status']}")


def test_scenario_10_medium_risk_requires_explicit_approval(client, technova_admin_token, recovery_test_device):
    _log("Scenario 10: medium-risk recovery action requires explicit approval")
    device_id = recovery_test_device["device_id"]
    device_token = recovery_test_device["device_token"]

    create = client.post(
        "/recovery-commands",
        json={"device_id": device_id, "action_type": "restart_sentinelx_agent", "parameters": {}, "reason": "E2E scenario 10"},
        headers=_auth(technova_admin_token),
    )
    assert create.status_code == 201, create.text
    command = create.json()
    assert command["risk_level"] == "medium"
    assert command["status"] == "awaiting_approval", f"expected manual approval to be required, got {command}"
    _log(f"  command {command['id']} correctly landed in awaiting_approval (risk_level=medium)")

    not_yet = client.get("/agent/commands/next", headers=_auth(device_token))
    assert not_yet.status_code == 200
    assert not_yet.json() is None, "an unapproved command must never be dispatched to the agent"
    _log("  agent correctly receives nothing until the command is approved")

    approve = client.patch(f"/recovery-commands/{command['id']}/approve", headers=_auth(technova_admin_token))
    assert approve.status_code == 200, approve.text
    assert approve.json()["status"] == "approved"
    _log("  admin explicitly approved the command")

    # Drain it fully so it doesn't sit in the device's queue ahead of later
    # scenarios' commands (get_next_command_for_device always returns the
    # oldest active command first).
    dispatched = client.get("/agent/commands/next", headers=_auth(device_token)).json()
    assert dispatched["id"] == command["id"]
    client.post(f"/agent/commands/{command['id']}/acknowledge", headers=_auth(device_token))
    client.post(f"/agent/commands/{command['id']}/start", headers=_auth(device_token))
    client.post(
        f"/agent/commands/{command['id']}/complete",
        json={"result_code": "success", "result_message": "scenario 10 cleanup", "result_data": {}},
        headers=_auth(device_token),
    )


def test_scenario_11_recovery_verified_via_post_action_telemetry(client, technova_admin_token, recovery_test_device):
    _log("Scenario 11: recovery is verified using post-action telemetry")
    device_id = recovery_test_device["device_id"]
    device_token = recovery_test_device["device_token"]

    create = client.post(
        "/recovery-commands",
        json={"device_id": device_id, "action_type": "restart_sentinelx_agent", "parameters": {}, "reason": "E2E scenario 11"},
        headers=_auth(technova_admin_token),
    )
    assert create.status_code == 201, create.text
    command = create.json()
    client.patch(f"/recovery-commands/{command['id']}/approve", headers=_auth(technova_admin_token))

    dispatched = client.get("/agent/commands/next", headers=_auth(device_token)).json()
    assert dispatched["id"] == command["id"]
    client.post(f"/agent/commands/{command['id']}/acknowledge", headers=_auth(device_token))
    client.post(f"/agent/commands/{command['id']}/start", headers=_auth(device_token))

    # Post-action telemetry: a fresh heartbeat and metric sample, both
    # "now" — this is exactly what recovery_verification_service.verify()
    # looks for to confirm a restart actually worked.
    hb = client.post(
        "/heartbeats", json={"device_id": device_id, "status": "online", "message": "post-restart heartbeat"}, headers=_auth(device_token)
    )
    assert hb.status_code == 201, hb.text
    metric = client.post(
        "/metrics",
        json={"device_id": device_id, "event_id": str(uuid.uuid4()), "cpu_percent": 30.0, "memory_percent": 40.0, "disk_percent": 50.0},
        headers=_auth(device_token),
    )
    assert metric.status_code == 201, metric.text
    _log("  posted a fresh heartbeat + metric sample immediately after 'restart' to simulate resumed telemetry")

    completed = client.post(
        f"/agent/commands/{command['id']}/complete",
        json={"result_code": "success", "result_message": "service restarted", "result_data": {}},
        headers=_auth(device_token),
    )
    assert completed.status_code == 200, completed.text
    final = completed.json()
    assert final["verification_status"] == "verified", final
    assert "heartbeat" in final["verification_message"].lower() or "telemetry" in final["verification_message"].lower()
    _log(f"  verification resolved to 'verified' from fresh post-action telemetry: {final['verification_message']}")


def test_scenario_12_expired_and_replayed_commands_rejected(client, technova_admin_token, db_conn, recovery_test_device):
    _log("Scenario 12: replayed and expired recovery commands are rejected")
    device_id = recovery_test_device["device_id"]
    device_token = recovery_test_device["device_token"]

    # -- expired --
    create = client.post(
        "/recovery-commands",
        json={"device_id": device_id, "action_type": "collect_diagnostics", "parameters": {}, "reason": "E2E scenario 12 expiry"},
        headers=_auth(technova_admin_token),
    )
    assert create.status_code == 201, create.text
    command_id = create.json()["id"]
    with db_conn.cursor() as cur:
        cur.execute(
            "UPDATE recovery_commands SET expires_at = %s WHERE id = %s",
            (datetime.now(timezone.utc) - timedelta(minutes=5), command_id),
        )
    _log(f"  backdated command {command_id}'s expires_at into the past")

    next_cmd = client.get("/agent/commands/next", headers=_auth(device_token))
    assert next_cmd.status_code == 200
    assert next_cmd.json() is None, "an expired command must never be dispatched"

    detail = client.get(f"/recovery-commands/{command_id}", headers=_auth(technova_admin_token))
    assert detail.status_code == 200
    assert detail.json()["status"] == "expired"
    _log(f"  command auto-transitioned to 'expired' on the agent's next poll, never dispatched")

    # -- replayed: acknowledging/completing an already-terminal command again --
    replay_ack = client.post(f"/agent/commands/{command_id}/acknowledge", headers=_auth(device_token))
    assert replay_ack.status_code == 409, replay_ack.text
    _log(f"  replaying acknowledge() against the terminal (expired) command correctly rejected with 409")


# ---------------------------------------------------------------------------
# Scenarios 13-14: RBAC / tenant isolation
# ---------------------------------------------------------------------------

def test_scenario_13_viewer_permission_denial_enforced(client, viewer_token, technova_admin_token):
    _log("Scenario 13: viewer permission denial is enforced")

    code_attempt = client.post(
        "/devices/enrollment-codes",
        json={"name": "should-be-denied", "expires_in_minutes": 5},
        headers=_auth(viewer_token),
    )
    assert code_attempt.status_code == 403, code_attempt.text
    _log("  viewer correctly denied (403) minting an enrolment code (admin-only action)")

    counters = client.get("/security-logs/counters", headers=_auth(viewer_token))
    assert counters.status_code == 403
    _log("  viewer correctly denied (403) the admin security counters endpoint")

    read_only = client.get("/devices", headers=_auth(viewer_token))
    assert read_only.status_code == 200
    _log("  viewer correctly retains read access to the device list (not a blanket lockout, just write/admin actions)")


def test_scenario_14_cross_tenant_access_rejected(client, technova_admin_token, apex_admin_token, enrolled_device):
    _log("Scenario 14: cross-tenant access is rejected")
    technova_device_id = enrolled_device["device_id"]

    cross = client.get(f"/devices/{technova_device_id}", headers=_auth(apex_admin_token))
    assert cross.status_code in (403, 404), cross.text
    _log(f"  Apex Robotics admin correctly denied ({cross.status_code}) access to a TechNova device")

    own = client.get(f"/devices/{technova_device_id}", headers=_auth(technova_admin_token))
    assert own.status_code == 200
    _log("  TechNova admin retains access to their own device")
