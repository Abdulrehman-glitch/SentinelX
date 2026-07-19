"""
Generates a new Ed25519 keypair for signing Safe Recovery Orchestration
commands (Sprint 3). Run once per environment; the private key is never
committed (backend/.secrets/ is gitignored).

Usage (from the repo root):
    python scripts/generate_recovery_signing_key.py
    python scripts/generate_recovery_signing_key.py backend/.secrets/custom_key.pem
"""

import base64
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "backend" / ".secrets" / "recovery_signing_key.pem"


def main() -> None:
    output_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUTPUT

    if output_path.exists():
        print(f"Refusing to overwrite existing key at {output_path}")
        sys.exit(1)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    private_key = Ed25519PrivateKey.generate()
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    output_path.write_bytes(pem)

    public_raw = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    public_b64 = base64.b64encode(public_raw).decode("ascii")

    print(f"Private key written to {output_path} (never commit this file).")
    print(f"Public key (base64, safe to document/share): {public_b64}")
    print("Set RECOVERY_SIGNING_PRIVATE_KEY_PATH in backend/.env if you used a custom output path.")


if __name__ == "__main__":
    main()
