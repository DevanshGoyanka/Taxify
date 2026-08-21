"""Tests for the Phase 2 canonical filing gateway."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

import app.engine.filing_gateway_v2 as gateway
from app.schemas.return_draft import (
    BankAccount,
    Employer,
    ReconciliationDiscrepancy,
    ReconciliationEvidence,
    ReturnDraft,
    create_empty_draft,
)


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
    """Official generation rejects filing sections outside the CBDT enum."""
    draft = _filing_ready_draft()
    draft.filing.filingSection = "NOT_A_REAL_SECTION"
    with pytest.raises(gateway.FilingGatewayV2Error) as caught:
        gateway.generate_cbdt_json(draft)
    assert "ReturnFileSec" in " ".join(caught.value.errors) or caught.value.message


def test_generation_accepts_revised_filing_section() -> None:
    """Filing section 139(5) (revised return) maps to CBDT code 17."""
    draft = _filing_ready_draft()
    draft.filing.filingSection = "139(5)"
    draft.filing.returnType = "REVISED"
    draft.filing.originalAcknowledgementNumber = "123456789012345"
    # Must not raise the unsupported-section error (it may still fail on
    # other gates, but not on the ReturnFileSec map).
    try:
        gateway.generate_cbdt_json(draft)
    except gateway.FilingGatewayV2Error as exc:
        assert "ReturnFileSec" not in " ".join(exc.errors)
        assert "not supported" not in exc.message.lower()


def test_compute_canonical_itr1_rejects_pending_reconciliation() -> None:
    """Pending reconciliation discrepancies block the canonical gateway."""
    draft = _filing_ready_draft()
    draft.reconciliation.discrepancies.append(ReconciliationDiscrepancy(
        id="reconciliation-1",
        category="interest from savings bank",
        description="AIS/TIS mismatch.",
        aisAmount=Decimal("157"),
        tisAcceptedAmount=Decimal("90"),
        as26Amount=Decimal("0"),
        difference=Decimal("67"),
        status="PENDING",
    ))
    with pytest.raises(gateway.FilingGatewayV2Error) as caught:
        gateway.compute_canonical_itr1(draft)
    assert "reconciliation" in " ".join(caught.value.errors).lower()


def test_compute_canonical_itr1_allows_confirmed_reconciliation() -> None:
    """A confirmed discrepancy no longer blocks the gateway."""
    draft = _filing_ready_draft()
    draft.reconciliation.discrepancies.append(ReconciliationDiscrepancy(
        id="reconciliation-1",
        category="interest from savings bank",
        description="AIS/TIS mismatch.",
        aisAmount=Decimal("157"),
        tisAcceptedAmount=Decimal("90"),
        as26Amount=Decimal("0"),
        difference=Decimal("67"),
        status="CONFIRMED_AIS",
    ))
    result = gateway.compute_canonical_itr1(draft)
    assert result.computation.gross_total_income >= Decimal("0")


def test_compute_canonical_itr1_rejects_out_of_scope_import_evidence() -> None:
    """Imported taxable evidence outside ITR-1 forces form escalation."""
    draft = _filing_ready_draft()
    draft.reconciliation.evidence.append(ReconciliationEvidence(
        id="ais-sft-012-1",
        source="AIS",
        sourceCode="SFT-012",
        sourceSection="B2",
        incomeHead="Capital gains",
        category="Sale of immovable property",
        description="Property sale evidence.",
        sourceName="Sub-registrar",
        sourceIdentifier="",
        role="OUT_OF_SCOPE_TAXABLE",
        relatedTab="CAPITAL_GAINS",
        canonicalDestination="none",
        evidenceKind="SOURCE_DETAIL",
        reportedAmount=Decimal("5000000"),
        processedAmount=Decimal("5000000"),
        acceptedAmount=Decimal("0"),
        taxAmount=Decimal("0"),
        status="SFT-012",
        requiresReview=True,
        raw={"information_code": "SFT-012"},
    ))
    with pytest.raises(gateway.FilingGatewayV2Error) as caught:
        gateway.compute_canonical_itr1(draft)
    message = f"{caught.value} {' '.join(caught.value.errors)}".lower()
    assert "outside itr-1" in message
    assert "sft-012" in message


def test_compute_canonical_itr1_purchase_only_does_not_fabricate_112a_gain() -> None:
    """A purchase-only MF entry (no sale) must never be treated as a 112A gain.

    Reproduces the bug where a client with a ₹4,99,975 MF purchase and no sale
    was blocked with "LTCG u/s 112A of Rs 499975 exceeds Rs 125000 limit".
    A purchase is an acquisition, not a disposal — there is no gain event.
    """
    draft = _filing_ready_draft()
    # Simulate the simplified 112A block with only a cost (purchase) and no sale.
    draft.capitalGainsSchedule = {
        "simplified112A": {
            "totalSaleConsideration": 0,
            "totalCostAcquisition": Decimal("499975"),
        },
    }
    result = gateway.compute_canonical_itr1(draft)
    # The gain must be 0 (sale - cost floored at 0), so ITR-1 stays eligible.
    assert result.computation.capital_gains_112a == Decimal("0")
    assert not result.computation.errors

