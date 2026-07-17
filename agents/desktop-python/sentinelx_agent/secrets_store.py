"""Secure device-token storage.

Preferred backend is the OS keyring (Windows Credential Manager / macOS
Keychain / Secret Service). SENTINELX_DEVICE_TOKEN in .env remains a
development fallback so the old workflow still runs, but tokens obtained
through enrolment are never written to disk in plain text.
"""

from __future__ import annotations

import logging

log = logging.getLogger("sentinelx.agent")

_SERVICE = "SentinelX Desktop Agent"
_ACCOUNT = "device-token"

try:
    import keyring
    from keyring.errors import KeyringError

    _KEYRING_AVAILABLE = True
except ImportError:  # pragma: no cover - environment without keyring
    keyring = None
    KeyringError = Exception
    _KEYRING_AVAILABLE = False


def load_device_token(env_fallback: str | None) -> str | None:
    """Keyring first; .env only as a development fallback."""
    if _KEYRING_AVAILABLE:
        try:
            stored = keyring.get_password(_SERVICE, _ACCOUNT)
            if stored:
                return stored
        except KeyringError as exc:
            log.warning("Keyring unavailable (%s); falling back to environment token.", exc)
    if env_fallback:
        log.warning(
            "Using SENTINELX_DEVICE_TOKEN from .env. Prefer enrolment (SENTINELX_ENROLLMENT_CODE) "
            "so the token lives in the OS credential store instead of plain text."
        )
    return env_fallback


def save_device_token(token: str) -> bool:
    """Returns True when the token landed in the OS credential store."""
    if not _KEYRING_AVAILABLE:
        log.error(
            "keyring is not installed — cannot store the device token securely. "
            "Install requirements and re-enrol, or set SENTINELX_DEVICE_TOKEN manually (dev only)."
        )
        return False
    try:
        keyring.set_password(_SERVICE, _ACCOUNT, token)
        return True
    except KeyringError as exc:
        log.error("Could not write device token to the OS credential store: %s", exc)
        return False


def clear_device_token() -> None:
    if not _KEYRING_AVAILABLE:
        return
    try:
        keyring.delete_password(_SERVICE, _ACCOUNT)
    except KeyringError:
        pass
