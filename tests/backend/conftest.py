"""Backend test fixtures.

Uses a dedicated sentinelx_test database on the local Postgres server so the
suite never touches sentinelx_dev. DATABASE_URL is overridden before the app
is imported because get_settings() is cached.
"""

import os
import uuid

import psycopg
import pytest

_DEV_URL = os.environ.get("DATABASE_URL")
if not _DEV_URL:
    # Fall back to backend/.env for the credentials, swapping the database name.
    from pathlib import Path

    env_file = Path(__file__).resolve().parents[2] / "backend" / ".env"
    for line in env_file.read_text().splitlines():
        if line.strip().startswith("DATABASE_URL="):
            _DEV_URL = line.split("=", 1)[1].strip().strip('"')
            break

assert _DEV_URL, "DATABASE_URL not found; set it or populate backend/.env"

_TEST_URL = _DEV_URL.rsplit("/", 1)[0] + "/sentinelx_test"
os.environ["DATABASE_URL"] = _TEST_URL


def _admin_dsn() -> str:
    plain = _DEV_URL.replace("postgresql+psycopg", "postgresql")
    return plain.rsplit("/", 1)[0] + "/postgres"


def _ensure_test_database() -> None:
    with psycopg.connect(_admin_dsn(), autocommit=True) as conn:
        exists = conn.execute(
            "SELECT 1 FROM pg_database WHERE datname = 'sentinelx_test'"
        ).fetchone()
        if not exists:
            conn.execute("CREATE DATABASE sentinelx_test")


_ensure_test_database()

# Imports below rely on the overridden DATABASE_URL.
from fastapi.testclient import TestClient  # noqa: E402

from app.core.security import create_access_token, hash_password  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models.device import Device  # noqa: E402
from app.models.organization import Organization  # noqa: E402
from app.models.user import User  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _schema():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture(autouse=True)
def _no_rate_limit():
    app.state.limiter.enabled = False
    yield
    app.state.limiter.enabled = True


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def org(db):
    organization = Organization(name=f"Org {uuid.uuid4().hex[:8]}", slug=f"org-{uuid.uuid4().hex[:8]}")
    db.add(organization)
    db.commit()
    db.refresh(organization)
    return organization


@pytest.fixture()
def admin_user(db, org):
    user = User(
        email=f"admin-{uuid.uuid4().hex[:8]}@test.local",
        full_name="Test Admin",
        password_hash=hash_password("Password123!"),
        role="admin",
        is_active=True,
        organization_id=org.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture()
def admin_headers(admin_user):
    token = create_access_token(subject=str(admin_user.id))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def enrolled_device(client, admin_headers, db):
    """Full enrolment flow: mint a code, enrol a device, return (device, token)."""
    code_resp = client.post(
        "/api/v1/devices/enrollment-codes",
        json={"name": "pytest device", "expires_in_minutes": 10},
        headers=admin_headers,
    )
    assert code_resp.status_code == 201, code_resp.text
    raw_code = code_resp.json()["code"]

    enroll_resp = client.post(
        "/api/v1/devices/enroll",
        json={
            "enrollment_code": raw_code,
            "hostname": f"pytest-host-{uuid.uuid4().hex[:8]}",
            "os_name": "TestOS 1.0",
            "device_type": "desktop",
            "agent_type": "python_desktop_agent",
            "agent_version": "3.0.0",
        },
    )
    assert enroll_resp.status_code == 201, enroll_resp.text
    body = enroll_resp.json()
    device = db.get(Device, uuid.UUID(body["device"]["id"]))
    return device, body["device_token"]
