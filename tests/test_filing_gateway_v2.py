"""Tests for the Phase 2 canonical filing gateway."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

import app.engine.filing_gateway_v2 as gateway
from app.schemas.return_draft import BankAccount, Employer, ReturnDraft, create_empty_draft


def _filing_ready_draft() -> ReturnDraft:
    """Create a minimally filing-ready canonical ITR-1 draft."""
    draft = create_empty_draft("2026-27", "ITR-1", "new")
    draft.personal.name = "Rahul Sharma"
    draft.personal.firstName = "Rahul"
    draft.personal.surnameOrOrgName = "Sharma"
    draft.personal.fatherName = "Mohan Sharma"
    draft.personal.pan = "ABCDE1234F"
    draft.personal.email = "rahul@example.com"
    draft.personal.mobile = "9876543210"
    draft.personal.dateOfBirth = "1990-01-15"
    draft.personal.flatNo = "12A"
    draft.personal.localityOrArea = "Central Delhi"
    draft.personal.city = "Delhi"
    draft.personal.stateCode = "07"
    draft.personal.countryCode = "91"
    draft.personal.pinCode = "110001"
    draft.verification.place = "Delhi"
    draft.verification.declarationAccepted = True
    draft.employers = [Employer(id="e1", basic=Decimal("800000"))]
    draft.bankAccounts = [BankAccount(
        id="b1",
        bankName="State Bank of India",
        accountNumber="1234567890",
        ifscCode="SBIN0001234",
        accountType="SB",
        useForRefund=True,
    )]
    return draft


def test_generate_reuses_one_computation_for_summary_and_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Generation calls compute_itr1 exactly once and reuses its result."""
    draft = _filing_ready_draft()
    real_compute = gateway.compute_itr1
    calls = 0
    seen: dict[str, Any] = {}

    def spy_compute(typed_input: Any) -> Any:
        nonlocal calls
        calls += 1
        return real_compute(typed_input)

    def fake_build(result: Any, typed_input: Any) -> dict[str, Any]:
        seen["result"] = result
        seen["typed_input"] = typed_input
        return {"ITR": {"ITR1": {"ok": True}}}

    monkeypatch.setattr(gateway, "compute_itr1", spy_compute)
    monkeypatch.setattr(gateway, "build_itr1_json", fake_build)
    monkeypatch.setattr(gateway, "validate_itr1_json", lambda document: None)

    official, summary = gateway.generate_cbdt_json(draft)
    assert calls == 1
    assert official["ITR"]["ITR1"]["ok"] is True
    assert summary["grossTotalIncome"] == float(seen["result"].gross_total_income)
    assert seen["typed_input"].filing_profile.pan == "ABCDE1234F"
    assert seen["typed_input"].property_profile.address_detail == "12A"


def test_generation_produces_official_schema_valid_json() -> None:
    """A filing-ready canonical draft passes the real official validator."""
    official, summary = gateway.generate_cbdt_json(_filing_ready_draft())
    gateway.validate_itr1_json(official)
    assert "ITR" in official
    assert summary["computedByFormEngine"] == "ITR-1"


def test_generation_requires_canonical_filing_fields() -> None:
    """Missing official profile data is rejected with actionable details."""
    draft = create_empty_draft("2026-27")
    with pytest.raises(gateway.FilingGatewayV2Error) as caught:
        gateway.generate_cbdt_json(draft)
    assert "required" in " ".join(caught.value.errors).lower()


def test_generation_rejects_unsupported_filing_section() -> None:
    """Official generation rejects sections unsupported by the CBDT builder."""
    draft = _filing_ready_draft()
    draft.filing.filingSection = "139(5)"
    with pytest.raises(gateway.FilingGatewayV2Error) as caught:
        gateway.generate_cbdt_json(draft)
    assert "139(1)" in " ".join(caught.value.errors)
