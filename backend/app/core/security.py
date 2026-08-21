import base64
import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pwdlib import PasswordHash

from app.core.config import BASE_DIR, get_settings


password_hash = PasswordHash.recommended()

_recovery_private_key: Ed25519PrivateKey | None = None


def hash_password(password: str) -> str:
    """
    Hashes a plaintext password using Argon2.
    """

    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """
    Verifies a plaintext password against a stored password hash.
    """

    return password_hash.verify(password, hashed_password)


ACCESS_TOKEN_TYPE = "access"


def create_access_token(
    subject: str,
    session_id: str,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """
    Creates a short-lived, signed JWT access token bound to a server-side
    session.

    Every token carries an explicit purpose (`typ`), an issuer, an audience,
    a unique id (`jti`) and the owning session (`sid`). `sid` is the load-
    bearing one: it is what lets logout and revocation take effect
    immediately instead of waiting out the token's expiry.

    `session_id` is required rather than optional on purpose — an optional
    session binding would leave a silent bypass for any caller that simply
    omitted it.
    """

    settings = get_settings()
    now = datetime.now(timezone.utc)

    payload: dict[str, Any] = {
        "sub": subject,
        "sid": session_id,
        "typ": ACCESS_TOKEN_TYPE,
        "jti": uuid.uuid4().hex,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": now,
        "nbf": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }

    if extra_claims:
        # Reserved claims are set above and must not be overridable by a
        # caller passing e.g. {"sid": ...} or {"exp": ...} in extra_claims.
        safe_claims = {
            key: value
            for key, value in extra_claims.items()
            if key not in {"sub", "sid", "typ", "jti", "iss", "aud", "iat", "nbf", "exp"}
        }
        payload.update(safe_claims)

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> dict[str, Any]:
    """
    Decodes a JWT and validates signature, expiry, issuer, audience and
    token purpose. Raises jwt.PyJWTError on any failure.

    `require` makes the claims mandatory rather than merely checked-if-present
    — PyJWT verifies `exp`/`iss`/`aud` only when the claim exists, so without
    this a token that simply omitted `exp` would validate forever.
    """

    settings = get_settings()

    payload = jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
        options={"require": ["exp", "iat", "sub", "sid", "typ", "iss", "aud"]},
    )

    if payload.get("typ") != ACCESS_TOKEN_TYPE:
        raise jwt.InvalidTokenError(
            f"Expected a '{ACCESS_TOKEN_TYPE}' token, got '{payload.get('typ')}'."
        )

    return payload


def generate_refresh_token() -> str:
    """A 48-byte CSPRNG refresh token. Opaque — never a JWT, so it carries no
    claims a client could read and cannot be accepted by decode_access_token."""

    return secrets.token_urlsafe(48)


def hash_refresh_token(raw_token: str) -> str:
    """SHA-256 hex of a refresh token, for storage and lookup.

    A slow KDF would be wrong here: the input is full-entropy random rather
    than a low-entropy human password, so there is nothing to brute-force,
    and this runs on the hot path of every token refresh.
    """

    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def derive_csrf_token(refresh_token_hash: str) -> str:
    """Derive a session's CSRF token from its stored refresh-token hash.

    This is the *signed* double-submit pattern rather than the naive one. A
    plain double-submit compares the cookie to the header, which an attacker
    who can write cookies for the site (a subdomain takeover, a compromised
    sibling app) defeats by simply setting both to a value they chose. Here
    the server recomputes the expected value from the session it actually
    resolved via the HttpOnly refresh cookie, so a forged pair does not match
    and the attacker cannot compute the real one without reading a cookie
    JavaScript is not allowed to see.
    """

    settings = get_settings()
    digest = hmac.new(
        settings.jwt_secret_key.encode("utf-8"),
        f"csrf:{refresh_token_hash}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return digest


def csrf_tokens_match(expected: str | None, presented: str | None) -> bool:
    """Constant-time comparison, so a mismatch leaks nothing by timing."""

    if not expected or not presented:
        return False
    return hmac.compare_digest(expected, presented)


def _resolve_recovery_key_path(configured: str) -> Path:
    path = Path(configured)
    if not path.is_absolute():
        path = BASE_DIR / path
    return path


def _load_recovery_private_key() -> Ed25519PrivateKey:
    """
    Lazily loads and caches the backend's Ed25519 recovery-command signing
    key from RECOVERY_SIGNING_PRIVATE_KEY_PATH. See
    scripts/generate_recovery_signing_key.py for dev key setup.
    """

    global _recovery_private_key

    if _recovery_private_key is None:
        settings = get_settings()
        key_path = _resolve_recovery_key_path(settings.recovery_signing_private_key_path)
        if not key_path.exists():
            raise FileNotFoundError(
                f"Recovery signing key not found at {key_path}. Run "
                "scripts/generate_recovery_signing_key.py to create one."
            )

        loaded_key = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
        if not isinstance(loaded_key, Ed25519PrivateKey):
            raise ValueError(f"Key at {key_path} is not an Ed25519 private key.")

        _recovery_private_key = loaded_key

    return _recovery_private_key


def sign_command_payload(canonical_payload: str) -> str:
    """
    Signs a canonical recovery-command payload string with the backend's
    Ed25519 private key. Returns a base64-encoded signature.
    """

    signature = _load_recovery_private_key().sign(canonical_payload.encode("utf-8"))
    return base64.b64encode(signature).decode("ascii")


def get_recovery_public_key_b64() -> str:
    """
    Returns the backend's Ed25519 public key (base64-encoded raw 32 bytes)
    for agents to fetch, cache, and use for local signature verification.
    """

    public_key = _load_recovery_private_key().public_key()
    raw_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return base64.b64encode(raw_bytes).decode("ascii")