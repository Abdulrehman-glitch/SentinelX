"""Rate limits have to mean the same thing whatever the process count.

Each `PostgresStorage` instance here stands in for a separate API process: its
own engine, its own connection pool, no shared memory with the others. If two
of them agree on a counter, four uvicorn workers will too.
"""

import time
import uuid

import pytest
from limits import RateLimitItemPerMinute, parse
from limits.storage import MemoryStorage
from limits.strategies import FixedWindowRateLimiter

from app.core import rate_limit_storage as rls
from app.core.config import get_settings


@pytest.fixture()
def pg_uri():
    return "sentinelx+" + get_settings().database_url


@pytest.fixture()
def store(pg_uri):
    storage = rls.PostgresStorage(pg_uri)
    yield storage
    storage.dispose()


def _key():
    return f"test:{uuid.uuid4().hex}"


class TestCountersAreShared:
    def test_two_independent_stores_see_one_counter(self, pg_uri):
        """The whole point: process A's request is visible to process B."""
        process_a = rls.PostgresStorage(pg_uri)
        process_b = rls.PostgresStorage(pg_uri)
        key = _key()
        try:
            assert process_a.incr(key, 60) == 1
            assert process_b.incr(key, 60) == 2
            assert process_a.incr(key, 60) == 3
            assert process_b.get(key) == 3
        finally:
            process_a.clear(key)
            process_a.dispose()
            process_b.dispose()

    def test_a_limit_is_exhausted_across_processes_not_per_process(self, pg_uri):
        """Three per minute means three in total, not three each."""
        limit = RateLimitItemPerMinute(3)
        namespace = uuid.uuid4().hex

        process_a = rls.PostgresStorage(pg_uri)
        process_b = rls.PostgresStorage(pg_uri)
        try:
            limiter_a = FixedWindowRateLimiter(process_a)
            limiter_b = FixedWindowRateLimiter(process_b)

            assert limiter_a.hit(limit, namespace) is True
            assert limiter_b.hit(limit, namespace) is True
            assert limiter_a.hit(limit, namespace) is True
            # Fourth request in the same window, from either process.
            assert limiter_b.hit(limit, namespace) is False
            assert limiter_a.hit(limit, namespace) is False
        finally:
            process_a.clear(limit.key_for(namespace))
            process_a.dispose()
            process_b.dispose()

    def test_per_process_memory_storage_does_not_share(self):
        """The bug this replaces, pinned so nobody reintroduces it."""
        limit = RateLimitItemPerMinute(1)
        namespace = uuid.uuid4().hex
        a = FixedWindowRateLimiter(MemoryStorage())
        b = FixedWindowRateLimiter(MemoryStorage())

        assert a.hit(limit, namespace) is True
        # A second "process" has its own budget, which is exactly the problem.
        assert b.hit(limit, namespace) is True


class TestWindowSemantics:
    def test_an_expired_window_starts_over_rather_than_accumulating(self, store):
        key = _key()
        try:
            # A one-second window that has certainly elapsed by the next call.
            assert store.incr(key, 1) == 1
            time.sleep(1.2)
            assert store.incr(key, 60) == 1
        finally:
            store.clear(key)

    def test_get_reports_zero_for_an_expired_window(self, store):
        key = _key()
        try:
            store.incr(key, 1)
            time.sleep(1.2)
            assert store.get(key) == 0
        finally:
            store.clear(key)

    def test_get_reports_zero_for_a_key_never_seen(self, store):
        assert store.get(_key()) == 0

    def test_clear_resets_one_key_only(self, store):
        first, second = _key(), _key()
        try:
            store.incr(first, 60)
            store.incr(second, 60)
            store.clear(first)
            assert store.get(first) == 0
            assert store.get(second) == 1
        finally:
            store.clear(second)


class TestConfiguration:
    def test_auto_resolves_to_postgres(self, monkeypatch):
        monkeypatch.setattr(get_settings(), "rate_limit_backend", "auto")
        assert rls.resolve_storage_uri().startswith("sentinelx+postgresql")

    def test_memory_is_available_but_explicit(self, monkeypatch):
        monkeypatch.setattr(get_settings(), "rate_limit_backend", "memory")
        assert rls.resolve_storage_uri() == "memory://"

    def test_valkey_requires_a_url(self, monkeypatch):
        settings = get_settings()
        monkeypatch.setattr(settings, "rate_limit_backend", "valkey")
        monkeypatch.setattr(settings, "rate_limit_valkey_url", "")
        with pytest.raises(ValueError):
            rls.resolve_storage_uri()

    def test_a_configured_valkey_url_is_passed_through(self, monkeypatch):
        settings = get_settings()
        monkeypatch.setattr(settings, "rate_limit_backend", "valkey")
        monkeypatch.setattr(settings, "rate_limit_valkey_url", "valkey://127.0.0.1:6379")
        assert rls.resolve_storage_uri() == "valkey://127.0.0.1:6379"

    def test_an_unknown_backend_is_rejected_rather_than_ignored(self, monkeypatch):
        monkeypatch.setattr(get_settings(), "rate_limit_backend", "elasticsearch")
        with pytest.raises(ValueError):
            rls.resolve_storage_uri()


class TestDegradedBehaviour:
    def test_an_unreachable_store_falls_back_but_still_enforces(self, monkeypatch):
        """Unavailable shared state must not become unlimited requests."""
        settings = get_settings()
        monkeypatch.setattr(settings, "rate_limit_backend", "valkey")
        # Nothing is listening on this port.
        monkeypatch.setattr(settings, "rate_limit_valkey_url", "valkey://127.0.0.1:6399")
        rls.reset_shared_storage()
        try:
            shared = rls.SharedLimitStorage()
            assert shared.shared is False
            assert shared.health()["status"] == "degraded"

            # Still counting, just not across processes.
            limiter = FixedWindowRateLimiter(shared.active)
            limit = parse("2/minute")
            namespace = uuid.uuid4().hex
            assert limiter.hit(limit, namespace) is True
            assert limiter.hit(limit, namespace) is True
            assert limiter.hit(limit, namespace) is False
        finally:
            rls.reset_shared_storage()

    def test_health_reports_the_rate_limit_backend(self, client):
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        rate_limiting = response.json()["rate_limiting"]
        assert rate_limiting["backend"] in {"postgresql", "valkey", "memory", "none"}
        assert rate_limiting["status"] in {
            "healthy",
            "degraded",
            "single_process",
            "disabled",
        }


class TestCredentialsAreNeverLeaked:
    def test_a_dsn_password_is_redacted(self):
        redacted = rls.redact_uri("postgresql+psycopg://app:sup3r-s3cret@localhost:5432/db")
        assert "sup3r-s3cret" not in redacted
        assert "app:***@localhost:5432" in redacted

    def test_a_uri_without_credentials_is_unchanged(self):
        assert rls.redact_uri("valkey://127.0.0.1:6379") == "valkey://127.0.0.1:6379"

    def test_health_never_carries_a_password(self, client):
        body = client.get("/api/v1/health").json()
        detail = str(body["rate_limiting"].get("detail") or "")
        userinfo = get_settings().database_url.split("://", 1)[1].split("@")[0]
        if ":" in userinfo:
            secret = userinfo.split(":", 1)[1]
            assert secret
            assert secret not in detail
