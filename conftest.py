"""Pytest configuration shared across the whole test suite.

Loads ``.env`` exactly once before any test module imports app code, so
that ERI-credential resolution (``app.eri.config.get_eri_credentials``)
and every builder that calls ``_resolve_sw_id()`` / ``_resolve_intermediary_city()``
find the active Type-2/Type-3 UAT/Production credentials. Without this,
unit test files that import builders directly (``test_itr1_itd_builder``,
``test_itr2_itd_builder``, ``test_filing_gateway_v2_itr4``, ...) never go
through ``app/main.py``'s ``load_dotenv()``, so ``os.environ`` is empty and
every test fails with ``ERIConfigurationError: Could not resolve ERI
credentials``.

This mirrors the existing pattern in the e2e test files
(``test_itr1_e2e.py``, ``test_itr4_e2e.py``) and the audit generator, which
all ``load_dotenv(os.path.join(PROJECT_ROOT, ".env"))`` before importing
app modules.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent

# Ensure the project root is importable so ``import app...`` works regardless
# of the pytest invocation directory.
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - python-dotenv is in requirements.txt
    load_dotenv = None  # type: ignore[assignment]

if load_dotenv is not None:
    _env_path = _PROJECT_ROOT / ".env"
    if _env_path.exists():
        # override=False so explicit shell-exported env vars still win
        # (matches the e2e / audit pattern).
        load_dotenv(str(_env_path), override=False)

# Sanity log for debugging which env loaded (visible with -s / -v).
_er = os.getenv("ERI_MODE", "type3")
_ev = os.getenv("ERI_ENV", "uat")
_city = os.getenv("ERI_INTERMEDIARY_CITY", "Akola")
print(f"[conftest] .env loaded — ERI_MODE={_er} ERI_ENV={_ev} city={_city}")
