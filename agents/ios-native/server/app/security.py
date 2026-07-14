"""Tokens and secret hashing for the dev server. JWT via PyJWT; device
secrets hashed with salted PBKDF2 (the production backend uses argon2 via
pwdlib — same contract, different KDF)."""

import hashlib
import hmac
import secrets
import uuid
from datetime import timedelta

import jwt

from .config import Settings
from .timeutil import utc_now

_PBKDF2_ITERATIONS = 100_000


def new_device_id() -> str:
    return "dev_" + uuid.uuid4().hex[:20]


def new_device_secret() -> str:
    return secrets.token_urlsafe(32)


def hash_secret(secret: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", secret.encode(), salt, _PBKDF2_ITERATIONS)
    return f"{salt.hex()}${digest.hex()}"


def verify_secret(secret: str, stored: str) -> bool:
    try:
        salt_hex, digest_hex = stored.split("$", 1)
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac("sha256", secret.encode(), bytes.fromhex(salt_hex), _PBKDF2_ITERATIONS)
    return hmac.compare_digest(digest.hex(), digest_hex)


def hash_token(token: str) -> str:
    # Refresh tokens are high-entropy JWTs; a plain digest is enough to
    # avoid storing them recoverably.
    return hashlib.sha256(token.encode()).hexdigest()


def issue_tokens(settings: Settings, device_id: str) -> tuple[str, str]:
    now = utc_now()
    access = jwt.encode(
        {
            "sub": device_id,
            "token_use": "access",
            "iat": now,
            "exp": now + timedelta(seconds=settings.access_token_ttl_seconds),
        },
        settings.jwt_secret,
        algorithm="HS256",
    )
    refresh = jwt.encode(
        {
            "sub": device_id,
            "token_use": "refresh",
            "jti": uuid.uuid4().hex,
            "iat": now,
            "exp": now + timedelta(seconds=settings.refresh_token_ttl_seconds),
        },
        settings.jwt_secret,
        algorithm="HS256",
    )
    return access, refresh


class TokenError(Exception):
    def __init__(self, code: str):
        self.code = code  # TOKEN_EXPIRED | INVALID_TOKEN


def decode_token(settings: Settings, token: str, expected_use: str) -> str:
    """Return the device_id or raise TokenError."""
    try:
        claims = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise TokenError("TOKEN_EXPIRED")
    except jwt.InvalidTokenError:
        raise TokenError("INVALID_TOKEN")
    if claims.get("token_use") != expected_use or not claims.get("sub"):
        raise TokenError("INVALID_TOKEN")
    return claims["sub"]
