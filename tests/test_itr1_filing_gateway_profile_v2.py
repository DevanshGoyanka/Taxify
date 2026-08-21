"""Canonical v2 ITR-1 filing-profile regression tests.

Parallel to ``test_itr1_filing_gateway_profile.py`` (which tests the legacy
``_build_itr1_input_from_flat`` flat-blob mapper), these tests verify the
v2 canonical pipeline produces the same filing-profile identity fields and
schema-valid official JSON — but from a typed ``ReturnDraft``, not a flat
blob. The legacy tests are deleted in Phase 7 when the legacy mapper is
removed; these canonical tests replace them.

Run: pytest tests/test_itr1_filing_gateway_profile_v2.py -v
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.engine.filing_gateway_v2 import (
    FilingGatewayV2Error,
    _filing_profile,
    compute_canonical_itr1,
    generate_cbdt_json,
)
from app.engine.itd.itr1_schema import validate_itr1_json
from app.schemas.return_draft import (
    BankAccount,
    Employer,
    ReturnDraft,
    create_empty_draft,
)


def _canonical_itr1_draft() -> ReturnDraft:
    """A canonical ITR-1 draft carrying the same identity as the legacy fixture."""
    draft = create_empty_draft("2026-27", "ITR-1", "old")
    p = draft.personal
    p.pan = "ABCDE1234F"
    p.firstName = "Asha"
    p.middleName = "Rani"
    p.surnameOrOrgName = "Sharma"
    p.name = "Asha Rani Sharma"
    p.dateOfBirth = "1990-01-15"
    p.aadhaar = "123456789012"
    p.fatherName = "Ramesh Sharma"
    p.employerCategory = "OTH"
    p.flatNo = "12A"
    p.roadOrStreet = "MG Road"
    p.localityOrArea = "Central Colony"
    p.city = "Delhi"
    p.stateCode = "07"
    p.countryCode = "91"
    p.pinCode = "110001"
    p.mobile = "9876543210"
    p.email = "asha.sharma@example.com"
    draft.filing.filingSection = "139(1)"
    draft.verification.capacity = "SELF"
    draft.verification.place = "Delhi"
    draft.verification.declarationAccepted = True
    draft.bankAccounts = [BankAccount(
        id="b1", bankName="State Bank of India",
        accountNumber="1234567890", ifscCode="SBIN0001234",
        accountType="SB", useForRefund=True,
    )]
    draft.employers = [Employer(
        id="e1", employerName="Acme", basic=Decimal("600000"),
        natureOfEmployment="PE",
    )]
    return draft


def test_canonical_filing_profile_uses_draft_identity() -> None:
    """The v2 filing profile must use the draft's identity, never placeholders."""
    draft = _canonical_itr1_draft()
    profile = _filing_profile(draft)
    assert profile.pan == "ABCDE1234F"
    assert profile.surname == "Sharma"
    assert profile.primary_address.city_or_town_or_district == "Delhi"
    assert profile.verification_place == "Delhi"
    assert profile.return_file_section == 11


def test_canonical_compute_builds_typed_input_with_profile() -> None:
    """compute_canonical_itr1 maps the draft once and returns the typed input."""
    draft = _canonical_itr1_draft()
    pipeline = compute_canonical_itr1(draft)
    assert pipeline.typed_input is not None
    assert pipeline.typed_input.assessee_pan == "ABCDE1234F"
    assert pipeline.summary["grossTotalIncome"] > 0


def test_canonical_generate_cbdt_json_passes_schema() -> None:
    """generate_cbdt_json produces schema-valid official ITR-1 JSON."""
    draft = _canonical_itr1_draft()
    official_json, summary = generate_cbdt_json(draft)
    validate_itr1_json(official_json)
    assert summary["grossTotalIncome"] > 0


def test_canonical_generate_rejects_missing_profile() -> None:
    """A draft missing required profile fields raises a clear filing-profile error."""
    draft = _canonical_itr1_draft()
    draft.personal.pan = ""
    with pytest.raises(FilingGatewayV2Error) as caught:
        generate_cbdt_json(draft)
    assert "filing profile" in caught.value.message.lower()
