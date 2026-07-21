"""Sprint 7 Phase 7: load/soak test. STAGING ONLY — see docs/releases/STAGING.md.

Never point --host at sentinelx_dev or production; the App Service F1 tier
has a hard CPU quota and no headroom for load testing (see the Phase 7
roadmap decision). Run against the local staging backend on :8200.

Usage:
    locust -f tests/load/locustfile.py --host http://127.0.0.1:8200/api/v1 \
        --headless -u 20 -r 3 -t 45s --csv=load_run
"""

import random
import uuid

from locust import HttpUser, between, task

TECHNOVA_ADMIN_EMAIL = "ops@technova.io"
PASSWORD = "SentinelX2026!"


class AgentUser(HttpUser):
    """Simulates one enrolled device continuously posting telemetry — the
    highest-frequency real traffic pattern this backend serves."""

    wait_time = between(2, 5)

    def on_start(self):
        admin_login = self.client.post(
            "/auth/login", json={"email": TECHNOVA_ADMIN_EMAIL, "password": PASSWORD}, name="/auth/login [agent enrol]"
        )
        admin_token = admin_login.json()["access_token"]

        code_resp = self.client.post(
            "/devices/enrollment-codes",
            json={"name": f"load-{uuid.uuid4().hex[:8]}", "expires_in_minutes": 30},
            headers={"Authorization": f"Bearer {admin_token}"},
            name="/devices/enrollment-codes [agent enrol]",
        )
        raw_code = code_resp.json()["code"]

        enroll_resp = self.client.post(
            "/devices/enroll",
            json={
                "enrollment_code": raw_code,
                "hostname": f"load-agent-{uuid.uuid4().hex[:8]}",
                "device_type": "desktop",
                "agent_type": "python_desktop_agent",
            },
            name="/devices/enroll [agent enrol]",
        )
        body = enroll_resp.json()
        self.device_id = body["device"]["id"]
        self.device_token = body["device_token"]

    @task
    def post_metrics(self):
        self.client.post(
            "/metrics",
            json={
                "device_id": self.device_id,
                "event_id": str(uuid.uuid4()),
                "cpu_percent": round(random.uniform(20, 70), 1),
                "memory_percent": round(random.uniform(30, 80), 1),
                "disk_percent": round(random.uniform(40, 90), 1),
            },
            headers={"Authorization": f"Bearer {self.device_token}"},
            name="/metrics [agent]",
        )


class DashboardUser(HttpUser):
    """Simulates a human operator browsing the dashboard."""

    wait_time = between(3, 8)

    def on_start(self):
        resp = self.client.post(
            "/auth/login", json={"email": TECHNOVA_ADMIN_EMAIL, "password": PASSWORD}, name="/auth/login [dashboard]"
        )
        self.token = resp.json()["access_token"]

    @task(3)
    def view_devices(self):
        self.client.get("/devices", headers={"Authorization": f"Bearer {self.token}"}, name="/devices [dashboard]")

    @task(2)
    def view_alerts(self):
        self.client.get("/alerts", headers={"Authorization": f"Bearer {self.token}"}, name="/alerts [dashboard]")

    @task(1)
    def view_health(self):
        self.client.get("/health", name="/health [dashboard]")
