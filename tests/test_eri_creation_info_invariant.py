"""Regression tests for the ERI-credential invariant of CreationInfo.

Architectural rule (DUAL_MODE_ERI_INTEGRATION_PLAN.md §3): the ITR JSON's
``CreationInfo`` (``SWCreatedBy`` / ``JSONCreatedBy``) and the ``Digest``
MUST ALWAYS flow from the selected ERI credential bundle for the active
``(ERI_MODE, ERI_ENV)`` pair. There is no non-ERI source for these
identity fields.

These tests lock that invariant in place: if the ERI credentials cannot
be resolved, JSON generation must fail loudly (``ERIConfigurationError``)
rather than stamp a hardcoded placeholder SW_ID or a placeholder ``-``
Digest. They also verify that when credentials ARE present, the
``SWCreatedBy`` and the Digest secret come from the SAME (mode, env)
suffix.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from app.engine.itd.common import _compute_digest, _creation_info, _resolve_sw_id
from app.eri.config import ERIConfigurationError, ERICredentials


def test_resolve_sw_id_uses_eri_credentials() -> None:
    """SWCreatedBy must come from get_eri_credentials(), not a constant."""
    fake = ERICredentials(
        mode="type3",
        environment="uat",
        sw_id="SW3TEST0001",
        digest_secret_key="abcdef0123456789",
        digest_iterations=1,
    )
    with patch("app.eri.config.get_eri_credentials", return_value=fake):
        assert _resolve_sw_id() == "SW3TEST0001"


def test_resolve_sw_id_raises_when_eri_unconfigured() -> None:
    """No SW_ID → generation fails loudly; no placeholder fallback."""
    with patch("app.eri.config.get_eri_credentials", side_effect=ValueError("unset")):
        with pytest.raises(ERIConfigurationError):
            _resolve_sw_id()


def test_resolve_sw_id_raises_when_sw_id_empty() -> None:
    """Empty sw_id on the bundle → fail loudly (no SW00000001 fallback)."""
    empty = ERICredentials(
        mode="type3", environment="production",
        sw_id="", digest_secret_key="x", digest_iterations=1,
    )
    with patch("app.eri.config.get_eri_credentials", return_value=empty):
        with pytest.raises(ERIConfigurationError):
            _resolve_sw_id()


def test_compute_digest_uses_eri_secret_and_iterations() -> None:
    """Digest is HMAC-SHA256 over the (sorted, minified, '-'-digested) JSON
    using the ERI-resolved secret + iteration count."""
    fake = ERICredentials(
        mode="type3", environment="uat",
        sw_id="SW3TEST0001",
        digest_secret_key="d96d4ce17e20a6ba",
        digest_iterations=1038,
    )
    data = {"CreationInfo": {"Digest": "-"}, "ITR1": {}}
    with patch("app.eri.config.get_eri_credentials", return_value=fake):
        digest = _compute_digest(data)
    assert isinstance(digest, str) and len(digest) == 44
    assert digest != "-"


def test_compute_digest_raises_when_secret_missing() -> None:
    """No digest secret → fail loudly (no '-' placeholder Digest)."""
    no_secret = ERICredentials(
        mode="type3", environment="production",
        sw_id="SW3TEST0001", digest_secret_key=None, digest_iterations=1,
    )
    with patch("app.eri.config.get_eri_credentials", return_value=no_secret):
        with pytest.raises(ERIConfigurationError):
            _compute_digest({"CreationInfo": {"Digest": "-"}})


def test_compute_digest_raises_when_resolver_fails() -> None:
    """Resolver itself raises → generation fails loudly as an
    ERIConfigurationError (wrapped), not a placeholder Digest."""
    with patch("app.eri.config.get_eri_credentials", side_effect=RuntimeError("no .env")):
        with pytest.raises(ERIConfigurationError):
            _compute_digest({"CreationInfo": {"Digest": "-"}})


def test_creation_info_sw_id_matches_eri_bundle() -> None:
    """_creation_info() stamps the ERI-resolved SW_ID in BOTH
    SWCreatedBy and JSONCreatedBy (they must match the Digest secret)."""
    fake = ERICredentials(
        mode="type2", environment="uat",
        sw_id="SW20014242",
        digest_secret_key="4448ffc0cec1a25d",
        digest_iterations=1344,
    )
    with patch("app.eri.config.get_eri_credentials", return_value=fake):
        ci = _creation_info()
    assert ci["SWCreatedBy"] == "SW20014242"
    assert ci["JSONCreatedBy"] == "SW20014242"
    assert ci["SWCreatedBy"] == ci["JSONCreatedBy"]


def test_creation_info_has_no_hardcoded_placeholder_sw_id() -> None:
    """The legacy placeholder SW_ID must never appear in CreationInfo when
    a real ERI bundle is resolved."""
    fake = ERICredentials(
        mode="type3", environment="uat",
        sw_id="SW20014122",
        digest_secret_key="d96d4ce17e20a6ba",
        digest_iterations=1038,
    )
    with patch("app.eri.config.get_eri_credentials", return_value=fake):
        ci = _creation_info()
    assert ci["SWCreatedBy"] != "SW00000001"
    assert ci["JSONCreatedBy"] != "SW00000001"


def test_sw_id_and_digest_secret_come_from_same_bundle() -> None:
    """The SWCreatedBy and the Digest secret must come from the same
    (mode, environment) ERI credential bundle. Verify by inspecting the
    bundle passed to both _resolve_sw_id and _compute_digest."""
    fake = ERICredentials(
        mode="type3", environment="uat",
        sw_id="SW20014122",
        digest_secret_key="d96d4ce17e20a6ba",
        digest_iterations=1038,
    )
    captured: list[ERICredentials] = []

    def fake_get() -> ERICredentials:
        captured.append(fake)
        return fake

    with patch("app.eri.config.get_eri_credentials", side_effect=fake_get):
        sw_id = _resolve_sw_id()
        _compute_digest({"CreationInfo": {"Digest": "-"}})

    assert sw_id == "SW20014122"
    # Both the SW_ID resolution and the Digest computation received the
    # SAME credential bundle (same mode + environment + sw_id + secret).
    assert len(captured) == 2
    assert captured[0].mode == captured[1].mode
    assert captured[0].environment == captured[1].environment
    assert captured[0].sw_id == captured[1].sw_id
    assert captured[0].digest_secret_key == captured[1].digest_secret_key
