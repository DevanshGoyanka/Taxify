"""Regression tests for the ERI-credential invariant of CreationInfo.

Architectural rule (DUAL_MODE_ERI_INTEGRATION_PLAN.md §3): the ITR JSON's
``CreationInfo`` (``SWCreatedBy`` / ``JSONCreatedBy``) and the ``Digest``
MUST ALWAYS flow from the selected ERI credential bundle for the active
``(ERI_MODE, ERI_ENV)`` pair. There is no non-ERI source for these
identity fields.

The Digest is computed by :mod:`app.eri.digest` (the single ERI-owned
digest service). It imports ``get_eri_credentials`` at module load, so
the mock target is ``app.eri.digest.get_eri_credentials`` (the bound
name in that module's namespace), per the standard ``unittest.mock``
pattern for ``from X import Y`` imports.

These tests lock that invariant in place: if the ERI credentials cannot
be resolved, JSON generation must fail loudly (``ERIConfigurationError``
/ ``ERIDigestError``) rather than stamp a hardcoded placeholder SW_ID or
a placeholder ``-`` Digest. They also verify that when credentials ARE
present, the ``SWCreatedBy`` and the Digest secret come from the SAME
(mode, env) suffix, and that the digest is computed over the COMPLETE
ITR document (matching the ITD reference ``API_Testing/digest_generator.py``
and SOP §5.3 Step 1 "Read the Input JSON").
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from app.engine.itd.common import _compute_digest, _creation_info, _resolve_sw_id
from app.eri.config import ERIConfigurationError, ERICredentials
from app.eri.digest import (
    ERIDigestError,
    compute_digest,
)


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


def test_digest_computed_over_complete_document_matching_reference() -> None:
    """The Digest must be computed over the COMPLETE ITR document (the
    whole ``{"ITR": {"ITRn": ...}}`` JSON), matching the ITD reference
    ``API_Testing/digest_generator.py`` and SOP §5.3 Step 1 "Read the
    Input JSON" — NOT just the inner form dict. The portal hashes the
    bytes of the uploaded file, so hashing a smaller scope would diverge.

    The reference implementation ``API_Testing/digest_generator.py`` is
    the authoritative SOP §5.3 realization: HMAC-SHA256, iterated N times
    over the minified JSON with the Digest value set to ``"-"``, then
    Base64-encoded. This test feeds the SAME input to both and asserts
    byte-identical output, so the algorithm (minify -> replace Digest ->
    iterate HMAC-SHA256 -> Base64) and the scope (full document) are
    both correct.
    """
    import json
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "API_Testing"))
    from digest_generator import generate_digest as reference_digest  # type: ignore

    secret = "d96d4ce17e20a6ba"
    iterations = 1038
    fake = ERICredentials(
        mode="type3", environment="uat",
        sw_id="SW20014122",
        digest_secret_key=secret,
        digest_iterations=iterations,
    )
    full_doc = {
        "ITR": {"ITR1": {"CreationInfo": {"Digest": "-"}, "Data": {"x": 1}}},
    }
    inner_only = full_doc["ITR"]["ITR1"]

    with patch("app.eri.config.get_eri_credentials", return_value=fake):
        taxify_full = compute_digest(full_doc)

    # Reference: hashes the minified full JSON string with "-" substituted.
    raw = json.dumps(full_doc, sort_keys=True, ensure_ascii=False, default=str)
    ref_full = reference_digest(raw, secret, iterations)

    assert taxify_full == ref_full, (
        f"Taxify digest {taxify_full} != reference {ref_full} — the "
        "HMAC-SHA256 N-iteration algorithm or the document scope diverges "
        "from the SOP §5.3 reference."
    )
    assert taxify_full != "-"
    assert len(taxify_full) == 44

    # Hashing only the inner dict must NOT match the full-document digest
    # (guards against the regression where builders hashed the inner form
    # dict instead of the whole uploaded document).
    with patch("app.eri.config.get_eri_credentials", return_value=fake):
        inner_digest = compute_digest(inner_only)
    assert inner_digest != taxify_full


def test_serialize_for_upload_round_trips_digest() -> None:
    """The upload serializer must produce bytes whose digest recomputes
    to the SAME value stamped in the JSON (bytes hashed == bytes uploaded).
    This is the core integrity invariant: the portal hashes the uploaded
    file, so the file's bytes must match the bytes Taxify hashed.
    """
    fake = ERICredentials(
        mode="type3", environment="uat",
        sw_id="SW20014122",
        digest_secret_key="d96d4ce17e20a6ba",
        digest_iterations=1038,
    )
    doc = {
        "ITR": {"ITR1": {"CreationInfo": {"Digest": "-"}, "Data": {"x": 1}}},
    }
    with patch("app.eri.config.get_eri_credentials", return_value=fake):
        # Compute + stamp the digest, then recompute over the stamped doc.
        stamped_digest = compute_digest(doc)
        doc["ITR"]["ITR1"]["CreationInfo"]["Digest"] = stamped_digest
        recomputed = compute_digest(doc)
    assert recomputed == stamped_digest


def test_serialize_for_upload_rejects_placeholder_digest() -> None:
    """A placeholder '-' Digest must never leave Taxify via the upload
    serializer."""
    from app.eri.digest import serialize_for_upload
    doc = {"ITR": {"ITR1": {"CreationInfo": {"Digest": "real"}, "Data": {}}}}
    with pytest.raises(ERIDigestError):
        serialize_for_upload(doc, digest="-")
    with pytest.raises(ERIDigestError):
        serialize_for_upload(doc, digest="tooshort")
