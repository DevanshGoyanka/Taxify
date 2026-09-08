"""Safety-contract tests for the foreground real-client filing script."""

from __future__ import annotations

import ast
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parent.parent
    / "scripts"
    / "test_type3_real_client.py"
)


def test_script_does_not_hardcode_client_pan_or_secrets() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "EPPPG3078Q" not in source
    assert "PORTAL_ENCRYPTION_KEY=" not in source
    assert "ERI_DIGEST_SECRET_KEY=" not in source
    ast.parse(source)


def test_script_requires_explicit_live_flag_and_confirmation() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "--submit-live" in source
    assert "if not args.submit_live:" in source
    assert "Type this exact confirmation to continue" in source
    assert "Live submission cancelled" in source
