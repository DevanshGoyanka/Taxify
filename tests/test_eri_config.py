"""Regression tests for app.eri.config.get_eri_credentials()'s env-var
resolution -- specifically that ERI_MODE/ERI_ENV are never defaulted.

Found during the filing/submission pipeline audit: get_eri_credentials()
used to default ERI_MODE to "type3" and ERI_ENV to "production" when
either was unset or blank. All four (mode, environment) credential sets
coexist in the same .env file, so a blanked ERI_ENV (the exact failure
mode of the Recovery incident documented in
Docs/DUAL_MODE_ERI_INTEGRATION_PLAN.md, where a careless full-file
rewrite blanked several .env secrets) would have silently resolved
production credentials instead of failing loudly -- the same class of
risk app.eri.config already guards against for ERI_BASE_URL ("there is
deliberately no default -- a wrong gateway must fail, not be guessed").
"""

from __future__ import annotations

import pytest

from app.eri.config import get_eri_credentials


def test_missing_eri_mode_raises_instead_of_defaulting(monkeypatch) -> None:
    monkeypatch.delenv("ERI_MODE", raising=False)
    monkeypatch.setenv("ERI_ENV", "uat")
    with pytest.raises(ValueError, match="ERI_MODE"):
        get_eri_credentials()


def test_blank_eri_mode_raises_instead_of_defaulting(monkeypatch) -> None:
    monkeypatch.setenv("ERI_MODE", "")
    monkeypatch.setenv("ERI_ENV", "uat")
    with pytest.raises(ValueError, match="ERI_MODE"):
        get_eri_credentials()


def test_missing_eri_env_raises_instead_of_defaulting_to_production(monkeypatch) -> None:
    monkeypatch.setenv("ERI_MODE", "type3")
    monkeypatch.delenv("ERI_ENV", raising=False)
    with pytest.raises(ValueError, match="ERI_ENV"):
        get_eri_credentials()


def test_blank_eri_env_raises_instead_of_defaulting_to_production(monkeypatch) -> None:
    monkeypatch.setenv("ERI_MODE", "type3")
    monkeypatch.setenv("ERI_ENV", "")
    with pytest.raises(ValueError, match="ERI_ENV"):
        get_eri_credentials()


def test_explicit_mode_and_env_still_resolve_normally(monkeypatch) -> None:
    """Regression fence: the real, always-explicit .env configuration must
    still resolve correctly after removing the defaults."""
    monkeypatch.setenv("ERI_MODE", "type3")
    monkeypatch.setenv("ERI_ENV", "uat")
    monkeypatch.setenv("ERI_SW_ID_TYPE3_UAT", "SW3TEST0001")
    monkeypatch.setenv("ERI_DIGEST_SECRET_KEY_TYPE3_UAT", "abcdef0123456789")
    monkeypatch.setenv("ERI_DIGEST_ITERATIONS_TYPE3_UAT", "5")
    creds = get_eri_credentials()
    assert creds.mode == "type3"
    assert creds.environment == "uat"
    assert creds.sw_id == "SW3TEST0001"
    assert creds.digest_secret_key == "abcdef0123456789"
    assert creds.digest_iterations == 5
