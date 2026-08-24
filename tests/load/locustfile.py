"""Bounded local load scenarios for SentinelX.

LOCAL ONLY. There is no hosted environment to point this at, and the numbers it
produces are only meaningful next to the hardware they ran on -
scripts/run_load_profile.py records that alongside the results.

Each user class is one traffic shape SentinelX actually serves. Pick one with
Locust's tag filter rather than running them all at once: a mixed run tells you
the aggregate is slow without telling you which shape made it so.

    locust -f tests/load/locustfile.py --host http://127.0.0.1:8000 \
        --headless -u 20 -r 5 -t 60s --tags fleet

Shapes:

    single-agent / fleet  enrolled devices on a realistic interval
                          (enrolment happens at run start and is itself rate
                          limited to 10/minute per IP, so a fleet larger than
                          that enrols over the first minutes of the run)
    batch                 the mobile /metrics/batch path
    burst                 deliberately faster than any real agent
    query                 reads competing with writes
    stream                SSE clients holding connections open
    console               a human clicking around the dashboard

Every class is bounded: fixed payload sizes, capped batch counts, wait times
that keep a laptop usable. Nothing here generates unbounded data.
"""

from __future__ import annotations

import os
import random
import threading
import time
import uuid

from locust import HttpUser, between, constant_pacing, events, tag, task

# Status-code accounting, separate from Locust's pass/fail.
#
# Deliberate backpressure (429 from the rate limiter, 503 from the queue shed
# threshold) is correct behaviour, so those responses are not failures. But
# "not a failure" is not the same as "invisible": a run where nine requests in
# ten were shed looks identical to a healthy one in the latency percentiles.
# This counts them so the rejection rate can be reported honestly.
STATUS_COUNTS: dict[int, int] = {}
_status_lock = threading.Lock()


@events.request.add_listener
def _count_status(response=None, **_kwargs) -> None:
    code = getattr(response, "status_code", None)
    if code is None:
        return
    with _status_lock:
        STATUS_COUNTS[code] = STATUS_COUNTS.get(code, 0) + 1


@events.quitting.add_listener
def _dump_status(**_kwargs) -> None:
    """Written where the harness can read it without parsing Locust's output."""
    path = os.environ.get("SENTINELX_LOAD_STATUS_FILE")
    if not path:
        return
    import json

    with _status_lock:
        snapshot = dict(sorted(STATUS_COUNTS.items()))
    try:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(snapshot, handle)
    except OSError:
        pass


ADMIN_EMAIL = os.environ.get("SENTINELX_LOAD_EMAIL", "ops@technova.io")
PASSWORD = os.environ.get("SENTINELX_LOAD_PASSWORD", "SentinelX2026!")

API = "/api/v1"

# A real desktop agent reports every 60s. Anything faster is a burst test, and
# is labelled as one rather than quietly inflating the throughput numbers.
#
# The interval can be compressed for a short run (SENTINELX_LOAD_INTERVAL),
# because a 60-second cadence over a 45-second test produces roughly one sample
# per device and measures nothing. Compressing time is honest as long as it is
# reported: run_load_profile.py records the interval it used next to the
# throughput it observed.
AGENT_INTERVAL_SECONDS = float(os.environ.get("SENTINELX_LOAD_INTERVAL", "60"))

# One admin login for the whole run, cached across users.
#
# Without this, spawning 20 users means 20 logins inside a few seconds, which
# trips the login rate limiter - and then the scenario is measuring the
# limiter's correctness rather than the ingest path. An operator enrols a fleet
# from one session anyway, so sharing the token is also the realistic shape.
_admin_token: str | None = None
_admin_lock = threading.Lock()


def _admin_login(client) -> str:
    global _admin_token
    with _admin_lock:
        if _admin_token is None:
            _admin_token = _login(client)
        return _admin_token


def _login(client) -> str:
    response = client.post(
        f"{API}/auth/login",
        json={"email": ADMIN_EMAIL, "password": PASSWORD},
        name=f"{API}/auth/login",
    )
    response.raise_for_status()
    return response.json()["access_token"]


def _enrol_device(client, admin_token: str) -> tuple[str, str]:
    """Enrol one device and return (device_id, device_token)."""
    code = client.post(
        f"{API}/devices/enrollment-codes",
        json={"name": f"load-{uuid.uuid4().hex[:8]}", "expires_in_minutes": 60},
        headers={"Authorization": f"Bearer {admin_token}"},
        name=f"{API}/devices/enrollment-codes",
    )
    code.raise_for_status()

    enrolled = client.post(
        f"{API}/devices/enroll",
        json={
            "enrollment_code": code.json()["code"],
            "hostname": f"load-host-{uuid.uuid4().hex[:10]}",
            "os_name": "LoadTest 1.0",
            "device_type": "desktop",
            "agent_type": "python_desktop_agent",
            "agent_version": "3.0.0",
        },
        name=f"{API}/devices/enroll",
    )
    enrolled.raise_for_status()
    body = enrolled.json()
    return body["device"]["id"], body["device_token"]


def _sample(device_id: str) -> dict:
    """One plausible telemetry sample.

    Values stay inside the alerting thresholds by default so a load run does
    not manufacture thousands of alerts and incidents - that would measure the
    alert pipeline under a synthetic emergency rather than measuring ingestion.
    """
    return {
        "device_id": device_id,
        "event_id": str(uuid.uuid4()),
        "cpu_percent": round(random.uniform(10, 70), 2),
        "memory_percent": round(random.uniform(30, 75), 2),
        "disk_percent": round(random.uniform(40, 80), 2),
    }


class _AgentBase(HttpUser):
    abstract = True

    def on_start(self) -> None:
        admin_token = _admin_login(self.client)
        self.device_id, self.device_token = _enrol_device(self.client, admin_token)
        self.headers = {"Authorization": f"Bearer {self.device_token}"}


@tag("single-agent", "fleet")
class NativeAgentUser(_AgentBase):
    """One desktop agent on its real reporting interval.

    constant_pacing, not a random wait: an agent's interval is a timer, so the
    request rate should be a function of the user count and nothing else.
    """

    wait_time = constant_pacing(AGENT_INTERVAL_SECONDS)

    @task(4)
    def post_metrics(self) -> None:
        self.client.post(
            f"{API}/metrics",
            json=_sample(self.device_id),
            headers=self.headers,
            name=f"{API}/metrics",
        )

    @task(1)
    def heartbeat(self) -> None:
        self.client.post(
            f"{API}/heartbeats",
            json={"device_id": self.device_id, "status": "online"},
            headers=self.headers,
            name=f"{API}/heartbeats",
        )


@tag("batch")
class BatchAgentUser(_AgentBase):
    """The mobile path: several buffered samples in one request.

    Batch size is capped well under the server's per-request ceiling. The point
    is to measure the normal shape; `burst` is what probes the limit.
    """

    wait_time = constant_pacing(AGENT_INTERVAL_SECONDS)
    BATCH_SIZE = 12

    @task
    def post_batch(self) -> None:
        now = time.time()
        samples = []
        for index in range(self.BATCH_SIZE):
            sample = _sample(self.device_id)
            sample.pop("device_id")
            # Preserved client timestamps, which is the whole reason this
            # endpoint exists.
            sample["recorded_at"] = time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime(now - (self.BATCH_SIZE - index) * 15)
            )
            samples.append(sample)

        self.client.post(
            f"{API}/metrics/batch",
            json={"device_id": self.device_id, "samples": samples},
            headers=self.headers,
            name=f"{API}/metrics/batch",
        )


@tag("burst")
class BurstIngestUser(_AgentBase):
    """Deliberately faster than any real agent.

    This is how the shed threshold and the rate limiter get exercised: 429 and
    503 are expected results here, not failures, so they are marked as
    successes rather than inflating the error rate.
    """

    wait_time = between(0.05, 0.2)

    @task
    def hammer(self) -> None:
        with self.client.post(
            f"{API}/metrics",
            json=_sample(self.device_id),
            headers=self.headers,
            name=f"{API}/metrics [burst]",
            catch_response=True,
        ) as response:
            if response.status_code in (200, 201, 429, 503):
                response.success()


@tag("query")
class QueryUser(HttpUser):
    """Reads while writes are happening.

    Queries are bounded the way the console bounds them - an hour of history at
    a few hundred points - because an unbounded query would measure the
    validator rejecting it rather than the engine answering it.
    """

    wait_time = between(1, 3)

    def on_start(self) -> None:
        self.headers = {"Authorization": f"Bearer {_login(self.client)}"}

    @task(3)
    def query_cpu(self) -> None:
        now = time.time()
        self.client.post(
            f"{API}/metric-query",
            json={
                "metric": "system.cpu.utilization",
                "start": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now - 3600)),
                "end": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
                "aggregation": "avg",
                "group_by": ["resource"],
                "max_points": 240,
            },
            headers=self.headers,
            name=f"{API}/metric-query",
        )

    @task(2)
    def devices(self) -> None:
        self.client.get(f"{API}/devices", headers=self.headers, name=f"{API}/devices")

    @task(1)
    def catalog(self) -> None:
        self.client.get(
            f"{API}/metric-query/catalog",
            headers=self.headers,
            name=f"{API}/metric-query/catalog",
        )


@tag("console")
class ConsoleUser(HttpUser):
    """A human moving around the dashboard.

    Slower than any machine client, but it fans out across several endpoints
    per "page", which is what makes it worth measuring separately.
    """

    wait_time = between(3, 8)

    def on_start(self) -> None:
        self.headers = {"Authorization": f"Bearer {_login(self.client)}"}

    @task(3)
    def dashboard(self) -> None:
        for path in (f"{API}/overview", f"{API}/devices", f"{API}/alerts"):
            self.client.get(path, headers=self.headers, name=path)

    @task(2)
    def incidents(self) -> None:
        self.client.get(f"{API}/incidents", headers=self.headers, name=f"{API}/incidents")

    @task(1)
    def events(self) -> None:
        self.client.get(
            f"{API}/events/recent?limit=50", headers=self.headers, name=f"{API}/events/recent"
        )


@tag("stream")
class StreamUser(HttpUser):
    """Holds an SSE connection open, the way a browser tab does.

    Measures the cost of connections that exist rather than requests that
    complete: each one is a poll per second against domain_events.
    """

    wait_time = between(20, 30)
    STREAM_SECONDS = 20

    def on_start(self) -> None:
        self.headers = {"Authorization": f"Bearer {_login(self.client)}"}

    @task
    def hold_stream(self) -> None:
        started = time.perf_counter()
        with self.client.get(
            f"{API}/events/stream",
            headers={**self.headers, "Accept": "text/event-stream"},
            stream=True,
            name=f"{API}/events/stream",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"stream refused: {response.status_code}")
                return
            for _ in response.iter_lines():
                if time.perf_counter() - started > self.STREAM_SECONDS:
                    break
            response.success()
