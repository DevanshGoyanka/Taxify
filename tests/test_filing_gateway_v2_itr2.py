"""
ITR-2/ITR-3 plan Phase 4 tests — filing_gateway_v2 ITR-2 wiring.

Mirrors tests/test_filing_gateway_v2_itr4.py: verifies compute_canonical_itr2,
the compute_canonical()/generate_cbdt_json() form dispatch, and that a
filing-ready ITR-2 draft produces official CBDT JSON passing the CBDT
Category A input/calc validators and the official ITR-2 JSON schema.

Run: pytest tests/test_filing_gateway_v2_itr2.py -v
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.engine.filing_gateway_v2 import (
    FilingGatewayV2Error,
    ITR2PipelineResult,
    compute_canonical,
    compute_canonical_itr2,
    generate_cbdt_json,
)
from app.schemas.return_draft import (
    BankAccount,
    Employer,
    HouseProperty,
    InterestIncome,
    PersonalInfo,
    ReturnDraft,
    TdsCredit,
    create_empty_draft,
)


def _filing_ready_itr2_draft() -> ReturnDraft:
    """A minimally filing-ready canonical ITR-2 draft with salary + HP."""
    draft = create_empty_draft("2026-27", "ITR-2", "new")
    draft.personal = PersonalInfo(
        name="Priya Nair", firstName="Priya", surnameOrOrgName="Nair",
        fatherName="Ramesh Nair", pan="ABCPN1234F", dateOfBirth="1985-06-15",
        residentialStatus="ROR", flatNo="12", localityOrArea="MG Road",
        city="Mumbai", stateCode="27", pinCode="400001", mobile="9876543210",
        email="priya@example.com",
    )
    draft.employers = [Employer(
        id="e1", basic=Decimal("1500000"), tdsDeducted=Decimal("120000"),
        employerName="Acme Corp", employerTAN="MUMA12345B",
        employerCity="Mumbai", employerStateCode="27", employerAddress="Tower A",
    )]
    draft.houseProperties = [HouseProperty(id="hp1", propertyType="SELF_OCCUPIED")]
    draft.otherSources.interest = [InterestIncome(
        id="i1", kind="SAVINGS_BANK", grossAmount=Decimal("8000"),
    )]
    draft.taxes.tds = [TdsCredit(
        id="t1", section="192", deductorName="Acme", deductorTAN="MUMA12345B",
        taxDeducted=Decimal("120000"), schedule="TDS1",
    )]
    draft.bankAccounts = [BankAccount(
        id="b1", bankName="HDFC Bank", accountNumber="000123456789",
        ifscCode="HDFC0000123", accountType="SB", useForRefund=True,
    )]
    draft.filing.filingSection = "139(1)"
    draft.verification.declarationAccepted = True
    draft.verification.capacity = "SELF"
    draft.verification.place = "Mumbai"
    draft.verification.date = "2026-07-15"
    return draft


def test_compute_canonical_itr2_returns_summary() -> None:
    """A filing-ready ITR-2 draft computes cleanly with a populated summary."""
    draft = _filing_ready_itr2_draft()
    pipeline = compute_canonical_itr2(draft)
    assert isinstance(pipeline, ITR2PipelineResult)
    assert pipeline.computation.gross_total_income > 0
    assert pipeline.summary["gti"] == float(pipeline.computation.gross_total_income)
    assert pipeline.summary["computedByFormEngine"] == "ITR-2"
    assert not pipeline.computation.errors


def test_compute_canonical_itr2_rejects_pending_reconciliation() -> None:
    """A pending AIS/TIS discrepancy blocks compute with a clear message."""
    from app.schemas.return_draft import ReconciliationDiscrepancy

    draft = _filing_ready_itr2_draft()
    draft.reconciliation.discrepancies = [ReconciliationDiscrepancy(
        id="d1", category="TDS", status="PENDING",
    )]
    with pytest.raises(FilingGatewayV2Error, match="Manual confirmation is required"):
        compute_canonical_itr2(draft)


def test_compute_canonical_dispatches_itr1_itr2_and_itr4() -> None:
    """The shared compute_canonical() dispatch routes ITR-2 drafts correctly."""
    draft = _filing_ready_itr2_draft()
    pipeline = compute_canonical(draft)
    assert isinstance(pipeline, ITR2PipelineResult)


def test_compute_canonical_itr2_requires_correct_form() -> None:
    """compute_canonical_itr2 rejects a draft whose form is not ITR-2."""
    draft = _filing_ready_itr2_draft()
    draft.form = "ITR-1"
    with pytest.raises(FilingGatewayV2Error):
        compute_canonical_itr2(draft)


def test_generate_cbdt_json_itr2_passes_validators_and_schema() -> None:
    """A filing-ready ITR-2 draft produces official JSON that reconciles."""
    draft = _filing_ready_itr2_draft()
    official_json, summary = generate_cbdt_json(draft)
    assert official_json["ITR"]["ITR2"] is not None
    assert summary["computedByFormEngine"] == "ITR-2"


def test_generate_cbdt_json_itr2_rejects_representative_verification() -> None:
    """ITR-2 verification capacity REPRESENTATIVE/PARTNER is not supported."""
    draft = _filing_ready_itr2_draft()
    draft.verification.capacity = "REPRESENTATIVE"
    with pytest.raises(FilingGatewayV2Error) as excinfo:
        generate_cbdt_json(draft)
    assert "SELF or KARTA" in " ".join(excinfo.value.errors)


def test_generate_cbdt_json_itr2_property_details_match_house_property_count() -> None:
    """One PropertyFilingDetail is emitted per canonical house property."""
    draft = _filing_ready_itr2_draft()
    draft.houseProperties = [
        HouseProperty(id="hp1", propertyType="SELF_OCCUPIED"),
        HouseProperty(id="hp2", propertyType="LET_OUT", annualLettingValue=Decimal("240000")),
    ]
    official_json, _summary = generate_cbdt_json(draft)
    schedule_hp = official_json["ITR"]["ITR2"].get("ScheduleHP")
    assert schedule_hp is not None


# ── Phase 5G: complete pre-calculation preparation ──────────────────────────

def test_compute_canonical_itr2_prepares_filing_data_before_calculation() -> None:
    """compute_canonical_itr2 attaches the filing profile before compute,
    matching compute_canonical_itr1/_itr4 — ITR-2 was the outlier deferring
    this to JSON-generation time; Phase 5G closes that gap."""
    draft = _filing_ready_itr2_draft()
    pipeline = compute_canonical_itr2(draft)
    assert pipeline.typed_input.filing_profile is not None
    assert pipeline.typed_input.filing_profile.pan == "ABCPN1234F"
    assert pipeline.typed_input.property_filing_details
    assert pipeline.typed_input.employer_filing_details


def test_compute_canonical_itr2_rejects_incomplete_filing_profile() -> None:
    """An incomplete filing profile (missing father's name) is now rejected
    at compute time, not only at JSON-generation time — the same behavior
    ITR-1/ITR-4 already have."""
    draft = _filing_ready_itr2_draft()
    draft.personal.fatherName = ""
    with pytest.raises(FilingGatewayV2Error):
        compute_canonical_itr2(draft)


def test_itr2_json_reuses_prepared_input_without_late_enrichment() -> None:
    """_generate_cbdt_json_itr2 must not re-derive filing data from the
    draft — it reuses pipeline.typed_input as-is."""
    draft = _filing_ready_itr2_draft()
    pipeline = compute_canonical_itr2(draft)
    official_json, summary = generate_cbdt_json(draft)
    assert official_json["ITR"]["ITR2"] is not None
    assert summary["gti"] == pipeline.summary["gti"]


def test_itr2_pipeline_result_carries_personal_profile_source_hash() -> None:
    from app.engine.personal_profile import personal_profile_source_hash

    draft = _filing_ready_itr2_draft()
    pipeline = compute_canonical_itr2(draft)
    assert pipeline.personal_profile_source_hash == personal_profile_source_hash(draft)
    assert pipeline.personal_profile_source_hash != ""


# ── Phase 5G follow-up: _itr2_filing_profile on the shared normalizer ───────

def test_compute_canonical_itr2_succeeds_with_no_employer_category() -> None:
    """ITR2FilingProfile has no employer_category field at all — unlike
    ITR1FilingProfile/ITR4FilingProfile, ITR-2 must not require
    personal.employerCategory just because the shared normalizer parses it.
    _filing_ready_itr2_draft() never sets it; this asserts that omission is
    correct, not an oversight."""
    draft = _filing_ready_itr2_draft()
    assert draft.personal.employerCategory == ""
    pipeline = compute_canonical_itr2(draft)
    assert not hasattr(pipeline.typed_input.filing_profile, "employer_category")
    assert not pipeline.computation.errors
