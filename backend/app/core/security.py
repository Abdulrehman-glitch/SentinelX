import base64
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


def create_access_token(subject: str, extra_claims: dict[str, Any] | None = None) -> str:
    """
    Creates a signed JWT access token.
    """

    settings = get_settings()

    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )

    payload: dict[str, Any] = {
        "sub": subject,
        "exp": expires_at,
        "iat": datetime.now(timezone.utc),
    }

    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> dict[str, Any]:
    """
    Decodes and validates a JWT access token.
    """

    settings = get_settings()

    return jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )


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