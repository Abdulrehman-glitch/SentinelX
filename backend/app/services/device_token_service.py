import secrets
import uuid


def generate_device_token(credential_id: uuid.UUID) -> str:
    """Mint a v2 device token: sxa_<credential id>.<secret>.

    Embedding the credential id makes auth an O(1) lookup instead of an
    argon2 scan over every active credential.
    """
    return f"sxa_{credential_id.hex}.{secrets.token_urlsafe(32)}"


def generate_enrollment_code(code_id: uuid.UUID) -> str:
    """Mint a single-use enrolment code: sxe_<code id>.<secret>."""
    return f"sxe_{code_id.hex}.{secrets.token_urlsafe(24)}"


def token_preview(raw: str) -> str:
    return f"{raw[:16]}..."
