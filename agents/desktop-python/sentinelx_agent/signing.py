"""Ed25519 signature verification for signed recovery commands.

Mirrors the canonical payload format the backend signs with
(backend/app/services/recovery_command_service.py::build_canonical_payload).
Must stay byte-for-byte identical or verification will always fail.

Timestamps are always re-normalized to UTC before joining — the backend
learned the hard way (Sprint 3 Stage 3) that a naive .isoformat() on a
value round-tripped through Postgres/JSON can carry a different UTC offset
representation for the exact same instant, which silently breaks a naive
string comparison. Parsing then re-formatting in UTC on both ends avoids
that class of bug entirely.
"""

from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


def _normalize_timestamp(raw: Any) -> str:
    if not raw:
        return ""
    text = str(raw).replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def build_canonical_payload(command: dict[str, Any]) -> str:
    canonical_params = json.dumps(command.get("parameters_json") or {}, sort_keys=True, separators=(",", ":"))
    expires_at_iso = _normalize_timestamp(command.get("expires_at"))
    return "\n".join(
        [
            str(command.get("id", "")),
            str(command.get("device_id", "")),
            str(command.get("action_type", "")),
            canonical_params,
            str(command.get("command_nonce") or ""),
            expires_at_iso,
            expires_at_iso,
            str(command.get("policy_id") or ""),
        ]
    )


def verify_command_signature(command: dict[str, Any], public_key_b64: str) -> bool:
    """Returns True iff the command's signature is valid for this exact payload."""

    signature_b64 = command.get("signature")
    if not signature_b64:
        return False

    try:
        public_key = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_b64))
        canonical = build_canonical_payload(command)
        public_key.verify(base64.b64decode(signature_b64), canonical.encode("utf-8"))
        return True
    except (InvalidSignature, ValueError, KeyError, TypeError):
        return False


def is_expired(command: dict[str, Any], *, now: datetime | None = None) -> bool:
    expires_at_raw = command.get("expires_at")
    if not expires_at_raw:
        return False
    text = str(expires_at_raw).replace("Z", "+00:00")
    expires_at = datetime.fromisoformat(text)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    current = now or datetime.now(timezone.utc)
    return current > expires_at
