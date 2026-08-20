"""
One-time recovery script: null out Client.portal_password ciphertext rows
that were encrypted with the now-lost PORTAL_ENCRYPTION_KEY.

After scripts/regen_portal_key.py has installed a new key, all previously
stored portal passwords are cryptographically undecryptable (AES-256-GCM
authenticates against the key; a different key fails). Keeping the stale
ciphertext in the DB would cause every automation job to fail at the
"Failed to decrypt portal password" guard.

This script:
  1. Loads .env (to ensure the new PORTAL_ENCRYPTION_KEY is in scope, so a
     future save flow works).
  2. Finds all Client rows with a non-empty portal_password.
  3. Reports how many will be cleared.
  4. Nulls them out (sets portal_password = None).
  5. Commits.

The operator must then re-enter each client's portal password via the UI
(the PUT /clients/{id} endpoint will re-encrypt with the new key).

Run once after regen_portal_key.py:
    python scripts/clear_broken_portal_passwords.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(str(ROOT / ".env"), override=True)

from app.db.database import SessionLocal
from app.db.models import Client


def main() -> None:
    db = SessionLocal()
    try:
        clients_with_pw = (
            db.query(Client)
            .filter(Client.portal_password.isnot(None))
            .filter(Client.portal_password != "")
            .all()
        )
        count = len(clients_with_pw)
        if count == 0:
            print("No clients with a stored portal_password — nothing to clear.")
            return

        print(f"Found {count} client(s) with stored portal_password ciphertext.")
        print("These are undecryptable with the new key and will be cleared:")
        for c in clients_with_pw:
            print(f"  - id={c.id} pan={c.pan or '<none>'} name={c.name!r}")

        print()
        for c in clients_with_pw:
            c.portal_password = None
        db.commit()
        print(f"Cleared portal_password on {count} client(s).")
        print()
        print("ACTION REQUIRED: re-enter each client's portal password via the")
        print("frontend (PUT /clients/{id}); it will be re-encrypted with the new key.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
