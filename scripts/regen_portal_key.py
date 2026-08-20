"""
One-time recovery script: generate a new PORTAL_ENCRYPTION_KEY, write it
into .env (replacing the empty/placeholder line), and verify the round-trip.

Run once:
    python scripts/regen_portal_key.py

The script:
  1. Generates a fresh 32-byte AES-256 key, base64-encoded (44 chars).
  2. Reads .env, replaces the PORTAL_ENCRYPTION_KEY line in place (only that
     line; all other secrets are left untouched byte-for-byte).
  3. Reloads .env and verifies _get_key() decodes 32 bytes.
  4. Verifies encrypt -> decrypt round-trip.
  5. Prints the key ONCE so the operator can record it in a secure backup
     (password manager / offline vault). The key is NOT printed again.

IMPORTANT: This script does NOT clear the existing (now-undecryptable)
Client.portal_password ciphertext rows. Run scripts/clear_broken_portal_passwords.py
after this to null those out so the operator can re-save fresh passwords.
"""

from __future__ import annotations

import base64
import os
import re
import sys
from pathlib import Path

# Allow running from project root without installing the package
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def generate_key() -> str:
    """Generate a fresh 32-byte AES-256 key, base64-encoded."""
    return base64.b64encode(os.urandom(32)).decode("ascii")


def write_key_to_env(env_path: Path, key: str) -> None:
    """Replace the PORTAL_ENCRYPTION_KEY line in .env, preserving everything else.

    Raises if the line is not found, to avoid silently creating a duplicate.
    """
    text = env_path.read_text(encoding="utf-8")
    pattern = re.compile(r"^PORTAL_ENCRYPTION_KEY=.*$", re.MULTILINE)
    if not pattern.search(text):
        raise SystemExit(
            "ERROR: 'PORTAL_ENCRYPTION_KEY=' line not found in .env. "
            "Add the line manually first."
        )
    new_text = pattern.sub(f"PORTAL_ENCRYPTION_KEY={key}", text)
    env_path.write_text(new_text, encoding="utf-8")


def verify_round_trip() -> None:
    """Reload .env and confirm the key decodes to 32 bytes + encrypt/decrypt works."""
    from dotenv import load_dotenv
    load_dotenv(str(ROOT / ".env"), override=True)
    from app.schemas.security.portal_crypto import (
        _get_key, encrypt_portal_password, decrypt_portal_password,
    )
    key_bytes = _get_key()
    assert len(key_bytes) == 32, f"expected 32-byte key, got {len(key_bytes)}"
    ciphertext = encrypt_portal_password("taxify-rt-test")
    assert decrypt_portal_password(ciphertext) == "taxify-rt-test"
    return len(key_bytes)


def main() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        raise SystemExit(f".env not found at {env_path}")

    key = generate_key()
    write_key_to_env(env_path, key)
    key_len = verify_round_trip()

    print("=" * 70)
    print("PORTAL_ENCRYPTION_KEY regenerated and written to .env successfully.")
    print(f"Key length: 44 base64 chars -> {key_len} bytes (AES-256-GCM).")
    print()
    print("RECORD THIS KEY IN A SECURE BACKUP (password manager / offline vault):")
    print(key)
    print()
    print("Next step: run scripts/clear_broken_portal_passwords.py to null out")
    print("the now-undecryptable Client.portal_password rows so they can be")
    print("re-saved by the operator.")
    print("=" * 70)


if __name__ == "__main__":
    main()
