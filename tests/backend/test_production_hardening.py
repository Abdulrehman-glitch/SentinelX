"""Regressions for the production-readiness audit (2026-08-13).

Each test pins down a specific finding from that audit so the fix cannot be
silently undone. They are deliberately behavioural — they assert what an
attacker or a cost model would observe, not how the code is written.
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.api.deps import _resolve_device_credential
from app.core.config import get_settings
from app.core.limiter import client_ip_key
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.user import User


class _FakeRequest:
    """Minimal stand-in for a Starlette Request for key-function tests."""

    def __init__(self, headers: dict | None = None, host: str = "203.0.113.9"):
        self.headers = headers or {}
        self.client = type("Client", (), {"host": host})()


# --- AUD-001: rate-limit bypass via a client-supplied Authorization header ---

def test_login_rate_limit_key_ignores_client_supplied_bearer_token():
    """The login bucket must not be shardable by the caller.

    The default limiter key buckets by Bearer token when one is present. On an
    endpoint that does not require authentication that is a bypass: an attacker
    varies the header per request, lands in a fresh bucket every time, and never
    trips the limit. Auth endpoints must therefore key on IP alone.
    """
    first = client_ip_key(_FakeRequest({"Authorization": "Bearer aaaaaaaaaaaa"}))
    second = client_ip_key(_FakeRequest({"Authorization": "Bearer bbbbbbbbbbbb"}))
    absent = client_ip_key(_FakeRequest({}))

    assert first == second == absent == "203.0.113.9"


def test_auth_and_enrollment_modules_use_the_ip_only_key():
    """Guards against a future edit dropping key_func from those decorators."""
    from app.api.routes import auth, enrollment

    assert auth.client_ip_key is client_ip_key
    assert enrollment.client_ip_key is client_ip_key


# --- AUD-002: X-Forwarded-For must not be trusted by default ---

def test_forwarded_for_is_ignored_unless_a_proxy_count_is_configured():
    request = _FakeRequest({"X-Forwarded-For": "1.2.3.4, 5.6.7.8"}, host="10.0.0.1")

    assert get_settings().trusted_proxy_count == 0
    # Default posture: a forged header is ignored entirely.
    assert client_ip_key(request) == "10.0.0.1"


# --- AUD-003: legacy device-token scan is an unauthenticated CPU amplifier ---

def test_legacy_opaque_device_token_is_rejected_without_scanning(db):
    """A non-v2 token must not trigger an argon2 verify per active credential.

    With the fallback disabled the resolver returns None immediately. If this
    regresses, one unauthenticated request costs O(fleet) x ~50ms of hashing —
    a trivial denial-of-service and, on a serverless host, a direct bill.
    """
    assert get_settings().allow_legacy_device_tokens is False
    assert _resolve_device_credential("totally-opaque-legacy-token", db) is None


def test_minted_device_tokens_still_match_the_o1_lookup_format():
    from app.api.deps import _V2_DEVICE_TOKEN
    from app.services.device_token_service import generate_device_token

    assert _V2_DEVICE_TOKEN.match(generate_device_token(uuid.uuid4())) is not None


# --- AUD-004: the unauthenticated surface must stay exactly this small ---

EXPECTED_PUBLIC_ENDPOINTS = {
    ("GET", "/api/v1/health"),
    ("POST", "/api/v1/auth/signup"),
    ("POST", "/api/v1/auth/login"),
    ("POST", "/api/v1/auth/token"),
    ("POST", "/api/v1/devices/enroll"),
}


def test_no_new_endpoint_becomes_publicly_reachable():
    """Every route but the five intentional ones must reject anonymous callers.

    This is the regression net for broken access control: adding a route without
    an auth dependency fails here rather than in production.
    """
    client = TestClient(app)
    spec = app.openapi()

    reachable = set()
    for path, operations in spec["paths"].items():
        for method in operations:
            if method not in ("get", "post", "put", "patch", "delete"):
                continue
            concrete = path
            while "{" in concrete:
                start, end = concrete.index("{"), concrete.index("}")
                concrete = concrete[:start] + str(uuid.uuid4()) + concrete[end + 1:]

            response = client.request(method.upper(), concrete, json={})
            # 401/403 = correctly gated; 405 = method not allowed on that path.
            if response.status_code not in (401, 403, 405):
                reachable.add((method.upper(), path))

    assert reachable == EXPECTED_PUBLIC_ENDPOINTS


# --- AUD-005: server-side RBAC, not hidden frontend buttons ---

@pytest.fixture()
def viewer_headers(db, org):
    user = User(
        email=f"viewer-{uuid.uuid4().hex[:8]}@test.local",
        full_name="Test Viewer",
        password_hash=hash_password("Password123!"),
        role="viewer",
        is_active=True,
        organization_id=org.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"Authorization": f"Bearer {create_access_token(subject=str(user.id))}"}


@pytest.mark.parametrize(
    "method,path,body",
    [
        # Minting an enrolment code is how a device joins the fleet.
        ("POST", "/api/v1/devices/enrollment-codes", {"name": "x", "expires_in_minutes": 10}),
        # Recovery commands execute real actions on a real machine.
        (
            "POST",
            "/api/v1/recovery-commands",
            {"device_id": str(uuid.uuid4()), "action_type": "collect_diagnostics", "parameters": {}},
        ),
        # User administration.
        ("POST", "/api/v1/users", {"email": "x@y.z", "full_name": "X", "password": "Password123!"}),
    ],
)
def test_viewer_cannot_perform_privileged_actions(client, viewer_headers, method, path, body):
    response = client.request(method, path, json=body, headers=viewer_headers)
    assert response.status_code in (403, 404), (
        f"viewer unexpectedly allowed {method} {path} -> {response.status_code}"
    )


def test_inactive_user_token_is_rejected(client, db, org):
    """A deactivated account's still-valid JWT must stop working immediately.

    Tokens are stateless with no blacklist, so is_active is the only revocation
    mechanism that exists — it has to be enforced on every request.
    """
    user = User(
        email=f"inactive-{uuid.uuid4().hex[:8]}@test.local",
        full_name="Inactive",
        password_hash=hash_password("Password123!"),
        role="admin",
        is_active=True,
        organization_id=org.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    headers = {"Authorization": f"Bearer {create_access_token(subject=str(user.id))}"}
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200

    user.is_active = False
    db.commit()

    assert client.get("/api/v1/auth/me", headers=headers).status_code == 403


# --- AUD-006: signup must never let the caller choose its own role ---

def test_signup_cannot_self_assign_a_privileged_role(client, db):
    """SignupRequest advertises a `role` field; the handler must ignore it."""
    existing_users = db.query(User).count()
    email = f"selfpromo-{uuid.uuid4().hex[:8]}@test.local"

    response = client.post(
        "/api/v1/auth/signup",
        json={
            "email": email,
            "full_name": "Self Promoter",
            "password": "Password123!",
            "role": "admin",
        },
    )
    assert response.status_code == 201, response.text

    granted = response.json()["user"]["role"]
    # Only the very first user in an empty database legitimately bootstraps as admin.
    assert granted == ("admin" if existing_users == 0 else "viewer")
