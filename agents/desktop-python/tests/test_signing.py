from __future__ import annotations

from sentinelx_agent.signing import is_expired, verify_command_signature


def test_valid_signature_verifies(sign_command, keypair):
    _, public_key_b64 = keypair
    command = sign_command()
    assert verify_command_signature(command, public_key_b64) is True


def test_tampered_action_type_rejected(sign_command, keypair):
    _, public_key_b64 = keypair
    command = sign_command()
    command["action_type"] = "restart_allowlisted_service"
    assert verify_command_signature(command, public_key_b64) is False


def test_tampered_parameters_rejected(sign_command, keypair):
    _, public_key_b64 = keypair
    command = sign_command(parameters={"service_key": "sentinelx_agent"})
    command["parameters_json"] = {"service_key": "some_other_service"}
    assert verify_command_signature(command, public_key_b64) is False


def test_wrong_public_key_rejected(sign_command):
    import base64

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    command = sign_command()
    other_public_raw = Ed25519PrivateKey.generate().public_key().public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
    )
    other_public_b64 = base64.b64encode(other_public_raw).decode("ascii")

    assert verify_command_signature(command, other_public_b64) is False


def test_missing_signature_rejected(sign_command, keypair):
    _, public_key_b64 = keypair
    command = sign_command()
    command["signature"] = None
    assert verify_command_signature(command, public_key_b64) is False


def test_expired_command_detected(sign_command):
    command = sign_command(expires_in_seconds=-10)
    assert is_expired(command) is True


def test_non_expired_command_not_flagged(sign_command):
    command = sign_command(expires_in_seconds=300)
    assert is_expired(command) is False


def test_canonical_payload_stable_across_z_and_offset_representation(sign_command, keypair):
    """
    Regression test for the exact bug found & fixed in the backend during
    Sprint 3 Stage 3: a timestamp serialized as '...Z' vs '...+00:00' for the
    identical instant must still verify, because both are normalized to the
    same UTC representation before building the canonical string.
    """
    _, public_key_b64 = keypair
    command = sign_command()

    if command["expires_at"].endswith("+00:00"):
        command["expires_at"] = command["expires_at"][: -len("+00:00")] + "Z"

    assert verify_command_signature(command, public_key_b64) is True
