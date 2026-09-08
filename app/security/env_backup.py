"""
Automatic .env backup — copies .env to .env.backup on every app startup.

Ensures a recent copy of .env (including all secrets) is always available
on disk if the live file is accidentally modified or corrupted.

The backup is written to: .env.backup  (overwritten each startup)

The backup file is added to .gitignore so it is never committed.

Call backup_env() once from app/main.py lifespan, before any other
startup logic. This guarantees the backup exists before any code
reads or modifies .env.
"""

from __future__ import annotations

import shutil
import logging
from pathlib import Path

_log = logging.getLogger("taxify.security.env_backup")

# Project root (three levels up from app/security/env_backup.py)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_ENV_PATH = _PROJECT_ROOT / ".env"
_BACKUP_PATH = _PROJECT_ROOT / ".env.backup"


def backup_env() -> None:
    """Copy .env to .env.backup if .env exists.

    Logs a warning if .env is missing. Does nothing if .env.backup already
    exists and is byte-identical to .env (avoids unnecessary writes).
    """
    if not _ENV_PATH.exists():
        _log.warning(".env not found at %s — skipping backup.", _ENV_PATH)
        return

    # Skip if backup is already identical (no-op on repeated starts)
    if _BACKUP_PATH.exists() and _ENV_PATH.read_bytes() == _BACKUP_PATH.read_bytes():
        _log.debug(".env.backup is up-to-date — no write needed.")
        return

    shutil.copy2(_ENV_PATH, _BACKUP_PATH)
    _log.info(".env backed up to %s", _BACKUP_PATH)
