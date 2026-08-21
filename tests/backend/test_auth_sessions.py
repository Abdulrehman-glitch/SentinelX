"""Browser session architecture: rotation, revocation, CSRF, JWT hardening.

These tests exist because the previous design had no way to fail: a bearer
JWT in localStorage was valid for 24 hours, logout only wrote an audit row,
and nothing was revocable. Each test below pins one property of the
replacement so a regression shows up here rather than in production.

See docs/adr/0001-browser-session-architecture.md.
"""

import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    derive_csrf_token,
    hash_password,
    hash_refresh_token,
)
from app.models.user import User
from app.models.user_session import UserSession
from app.services import session_service
from helpers import auth_headers_for

SETTINGS = get_settings()
PASSWORD = "Password123!"


@pytest.fixture()
def account(db, org):
    user = User(
        email=f"session-{uuid.uuid4().hex[:8]}@test.local",
        full_name="Session User",
        password_hash=hash_password(PASSWORD),
        role="admin",
        is_active=True,
        organization_id=org.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _login(client, user):
    response = client.post("/api/v1/auth/login", json={"email": user.email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return response


def _csrf(client) -> str:
    value = client.cookies.get(SETTINGS.csrf_cookie_name)
    assert value, "login should have set a CSRF cookie"
    return value


def _bearer(response) -> dict[str, str]:
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _session_by_raw_refresh(db, raw_refresh: str) -> UserSession | None:
    return db.scalar(
        select(UserSession).where(UserSession.refresh_token_hash == hash_refresh_token(raw_refresh))
    )


class TestLoginIssuesASession:
    def test_login_sets_httponly_refresh_cookie_and_readable_csrf_cookie(self, client, account):
        response = _login(client, account)
        raw = response.headers.get_list("set-cookie")

        refresh_header = next(h for h in raw if h.startswith(f"{SETTINGS.session_cookie_name}="))
        csrf_header = next(h for h in raw if h.startswith(f"{SETTINGS.csrf_cookie_name}="))

        # The refresh token must be unreachable from JavaScript — that is the
        # entire reason this design replaced localStorage.
        assert "HttpOnly" in refresh_header
        assert "HttpOnly" not in csrf_header
        assert f"Path={SETTINGS.session_cookie_path}" in refresh_header
        assert "samesite=lax" in refresh_header.lower()

    def test_refresh_token_is_never_returned_in_the_response_body(self, client, account):
        body = _login(client, account).json()
        raw_refresh = client.cookies.get(SETTINGS.session_cookie_name)

        assert raw_refresh
        assert raw_refresh not in str(body)
        assert "refresh" not in body

    def test_access_token_is_short_lived_and_advertised(self, client, account):
        body = _login(client, account).json()
        assert body["expires_in"] == SETTINGS.access_token_expire_minutes * 60
        assert SETTINGS.access_token_expire_minutes <= 60, "access tokens must stay short-lived"

    def test_only_the_hash_of_the_refresh_token_is_stored(self, client, db, account):
        _login(client, account)
        raw_refresh = client.cookies.get(SETTINGS.session_cookie_name)

        stored = _session_by_raw_refresh(db, raw_refresh)
        assert stored is not None
        assert stored.refresh_token_hash != raw_refresh
        assert stored.user_id == account.id


class TestJwtHardening:
    def test_token_carries_issuer_audience_type_session_and_jti(self, client, account):
        token = _login(client, account).json()["access_token"]
        claims = decode_access_token(token)

        assert claims["iss"] == SETTINGS.jwt_issuer
        assert claims["aud"] == SETTINGS.jwt_audience
        assert claims["typ"] == "access"
        assert claims["sub"] == str(account.id)
        assert uuid.UUID(claims["sid"])
        assert claims["jti"]

    @pytest.mark.parametrize(
        "override",
        [
            {"iss": "somebody-else"},
            {"aud": "another-service"},
            {"typ": "refresh"},
        ],
    )
    def test_token_minted_for_another_issuer_audience_or_purpose_is_rejected(
        self, client, db, account, override
    ):
        session, _ = session_service.create_session(db, account)
        db.commit()

        now = datetime.now(timezone.utc)
        claims = {
            "sub": str(account.id),
            "sid": str(session.id),
            "typ": "access",
            "jti": uuid.uuid4().hex,
            "iss": SETTINGS.jwt_issuer,
            "aud": SETTINGS.jwt_audience,
            "iat": now,
            "exp": now + timedelta(minutes=5),
        }
        claims.update(override)
        forged = jwt.encode(claims, SETTINGS.jwt_secret_key, algorithm=SETTINGS.jwt_algorithm)

        response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {forged}"})
        assert response.status_code == 401

    def test_token_without_a_session_claim_is_rejected(self, client, account):
        """A pre-sprint bearer token has no `sid`, so it could never be
        revoked. It must not be honoured, or the revocation guarantee becomes
        opt-out."""

        now = datetime.now(timezone.utc)
        legacy = jwt.encode(
            {
                "sub": str(account.id),
                "typ": "access",
                "iss": SETTINGS.jwt_issuer,
                "aud": SETTINGS.jwt_audience,
                "iat": now,
                "exp": now + timedelta(minutes=5),
            },
            SETTINGS.jwt_secret_key,
            algorithm=SETTINGS.jwt_algorithm,
        )

        response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {legacy}"})
        assert response.status_code == 401

    def test_token_without_an_expiry_is_rejected(self, client, db, account):
        session, _ = session_service.create_session(db, account)
        db.commit()

        eternal = jwt.encode(
            {
                "sub": str(account.id),
                "sid": str(session.id),
                "typ": "access",
                "iss": SETTINGS.jwt_issuer,
                "aud": SETTINGS.jwt_audience,
                "iat": datetime.now(timezone.utc),
            },
            SETTINGS.jwt_secret_key,
            algorithm=SETTINGS.jwt_algorithm,
        )

        response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {eternal}"})
        assert response.status_code == 401

    def test_reserved_claims_cannot_be_overridden_by_extra_claims(self, db, account):
        session, _ = session_service.create_session(db, account)
        db.commit()
        other_session = uuid.uuid4()

        token = create_access_token(
            subject=str(account.id),
            session_id=str(session.id),
            extra_claims={"sid": str(other_session), "role": "viewer", "exp": 1},
        )
        claims = decode_access_token(token)

        assert claims["sid"] == str(session.id)
        assert claims["role"] == "viewer"  # non-reserved claims still pass through


class TestRefreshRotation:
    def test_refresh_issues_a_new_access_token_and_rotates_the_refresh_cookie(
        self, client, account
    ):
        _login(client, account)
        original_refresh = client.cookies.get(SETTINGS.session_cookie_name)

        response = client.post(
            "/api/v1/auth/refresh",
            headers={SETTINGS.csrf_header_name: _csrf(client)},
        )
        assert response.status_code == 200, response.text

        rotated_refresh = client.cookies.get(SETTINGS.session_cookie_name)
        assert rotated_refresh != original_refresh
        assert response.json()["user"]["email"] == account.email

    def test_refreshed_access_token_works_against_a_protected_route(self, client, account):
        _login(client, account)
        refreshed = client.post(
            "/api/v1/auth/refresh", headers={SETTINGS.csrf_header_name: _csrf(client)}
        )

        me = client.get("/api/v1/auth/me", headers=_bearer(refreshed))
        assert me.status_code == 200
        assert me.json()["email"] == account.email

    def test_refresh_without_a_csrf_header_is_rejected(self, client, account):
        _login(client, account)
        assert client.post("/api/v1/auth/refresh").status_code == 403

    def test_refresh_with_a_forged_csrf_header_is_rejected(self, client, account):
        _login(client, account)
        response = client.post(
            "/api/v1/auth/refresh",
            headers={SETTINGS.csrf_header_name: "not-the-right-token"},
        )
        assert response.status_code == 403

    def test_forging_both_csrf_cookie_and_header_still_fails(self, client, account):
        """The signed double-submit property: an attacker who can write
        cookies but cannot read the HttpOnly refresh cookie still cannot
        produce a matching pair, because the server derives the expected
        value from the session it resolved rather than from the cookie."""

        _login(client, account)
        client.cookies.set(
            SETTINGS.csrf_cookie_name, "attacker-chosen", path=SETTINGS.session_cookie_path
        )

        response = client.post(
            "/api/v1/auth/refresh",
            headers={SETTINGS.csrf_header_name: "attacker-chosen"},
        )
        assert response.status_code == 403

    def test_refresh_without_a_cookie_is_401(self, client):
        response = client.post(
            "/api/v1/auth/refresh", headers={SETTINGS.csrf_header_name: "anything"}
        )
        assert response.status_code == 401

    def test_replaying_a_spent_refresh_token_revokes_the_whole_family(self, client, db, account):
        _login(client, account)
        stolen_refresh = client.cookies.get(SETTINGS.session_cookie_name)
        stolen_csrf = _csrf(client)

        # Legitimate client rotates.
        first = client.post(
            "/api/v1/auth/refresh", headers={SETTINGS.csrf_header_name: stolen_csrf}
        )
        assert first.status_code == 200

        # Attacker replays the token captured before that rotation.
        client.cookies.set(
            SETTINGS.session_cookie_name, stolen_refresh, path=SETTINGS.session_cookie_path
        )
        client.cookies.set(
            SETTINGS.csrf_cookie_name, stolen_csrf, path=SETTINGS.session_cookie_path
        )
        replay = client.post(
            "/api/v1/auth/refresh", headers={SETTINGS.csrf_header_name: stolen_csrf}
        )
        assert replay.status_code == 401

        # And the legitimate client is signed out too — the server cannot
        # tell which party is the thief, so it fails closed.
        db.expire_all()
        sessions = db.scalars(select(UserSession).where(UserSession.user_id == account.id)).all()
        assert sessions
        assert all(not s.is_active for s in sessions)
        assert any(s.revoked_reason == "refresh_token_reuse" for s in sessions)

    def test_refresh_rebuilds_claims_from_the_live_user_row(self, client, db, account):
        _login(client, account)

        account.role = "viewer"
        db.commit()

        refreshed = client.post(
            "/api/v1/auth/refresh", headers={SETTINGS.csrf_header_name: _csrf(client)}
        )
        claims = decode_access_token(refreshed.json()["access_token"])
        assert claims["role"] == "viewer"

    def test_refresh_for_a_deactivated_user_revokes_the_session(self, client, db, account):
        _login(client, account)

        account.is_active = False
        db.commit()

        response = client.post(
            "/api/v1/auth/refresh", headers={SETTINGS.csrf_header_name: _csrf(client)}
        )
        assert response.status_code == 401

        db.expire_all()
        sessions = db.scalars(select(UserSession).where(UserSession.user_id == account.id)).all()
        assert all(not s.is_active for s in sessions)


class TestRevocation:
    def test_logout_immediately_invalidates_the_access_token(self, client, account):
        """The headline fix. Previously logout wrote an audit row and the
        bearer token kept working for the rest of its 24-hour life."""

        login = _login(client, account)
        headers = _bearer(login)

        assert client.get("/api/v1/auth/me", headers=headers).status_code == 200

        logout = client.post("/api/v1/auth/logout", headers=headers)
        assert logout.status_code == 200

        assert client.get("/api/v1/auth/me", headers=headers).status_code == 401

    def test_logout_works_even_when_the_access_token_has_expired(self, client, db, account):
        _login(client, account)
        raw_refresh = client.cookies.get(SETTINGS.session_cookie_name)

        # No Authorization header at all — the cookie is the only credential,
        # which is exactly the situation after a token lapses.
        assert client.post("/api/v1/auth/logout").status_code == 200

        db.expire_all()
        session = _session_by_raw_refresh(db, raw_refresh)
        assert session is not None
        assert not session.is_active
        assert session.revoked_reason == "user_logout"

    def test_logout_by_an_anonymous_caller_is_a_harmless_200(self, client):
        response = client.post("/api/v1/auth/logout")
        assert response.status_code == 200
        assert response.json()["message"] == "Signed out."

    def test_logout_all_revokes_every_session(self, client, db, account):
        first = _login(client, account)
        first_headers = _bearer(first)

        # A second, independent sign-in (a different browser).
        second_session, _ = session_service.create_session(db, account)
        db.commit()
        assert len(session_service.list_active_sessions(db, account.id)) == 2

        assert client.post("/api/v1/auth/logout-all", headers=first_headers).status_code == 200

        db.expire_all()
        assert session_service.list_active_sessions(db, account.id) == []
        assert client.get("/api/v1/auth/me", headers=first_headers).status_code == 401
        assert db.get(UserSession, second_session.id).is_active is False

    def test_a_revoked_session_rejects_its_access_token(self, client, db, account):
        headers = auth_headers_for(db, account)
        assert client.get("/api/v1/auth/me", headers=headers).status_code == 200

        session = session_service.list_active_sessions(db, account.id)[0]
        session_service.revoke_session(db, session, reason="test_revocation")
        db.commit()

        assert client.get("/api/v1/auth/me", headers=headers).status_code == 401

    def test_an_expired_session_rejects_its_access_token(self, client, db, account):
        headers = auth_headers_for(db, account)
        session = session_service.list_active_sessions(db, account.id)[0]

        session.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()

        assert client.get("/api/v1/auth/me", headers=headers).status_code == 401

    def test_a_token_whose_session_belongs_to_another_user_is_rejected(
        self, client, db, account, admin_user
    ):
        """Defence against a mix-and-match forgery: a valid session id from
        one user pasted into a token claiming to be another."""

        other_session, _ = session_service.create_session(db, admin_user)
        db.commit()

        token = create_access_token(subject=str(account.id), session_id=str(other_session.id))
        response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401


class TestSessionListing:
    def test_lists_only_the_callers_own_sessions(self, client, db, account, admin_user):
        headers = auth_headers_for(db, account)
        session_service.create_session(db, account)
        session_service.create_session(db, admin_user)
        db.commit()

        response = client.get("/api/v1/auth/sessions", headers=headers)
        assert response.status_code == 200

        mine = {str(s.id) for s in session_service.list_active_sessions(db, account.id)}
        assert {entry["id"] for entry in response.json()} == mine

    def test_session_listing_never_exposes_token_material(self, client, db, account):
        headers = auth_headers_for(db, account)
        response = client.get("/api/v1/auth/sessions", headers=headers)

        assert "refresh_token_hash" not in response.text
        assert "previous_token_hash" not in response.text

    def test_listing_requires_authentication(self, client):
        assert client.get("/api/v1/auth/sessions").status_code == 401


class TestCsrfDerivation:
    def test_csrf_token_is_bound_to_the_session_and_not_reversible(self, db, account):
        session_a, _ = session_service.create_session(db, account)
        session_b, _ = session_service.create_session(db, account)
        db.commit()

        token_a = derive_csrf_token(session_a.refresh_token_hash)
        token_b = derive_csrf_token(session_b.refresh_token_hash)

        assert token_a != token_b
        assert token_a == derive_csrf_token(session_a.refresh_token_hash)  # deterministic
        assert session_a.refresh_token_hash not in token_a
