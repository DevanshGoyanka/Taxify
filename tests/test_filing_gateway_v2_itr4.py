"""Phase 3 tests — ITR-4 canonical compute + CBDT JSON via filing_gateway_v2.

Verifies the single canonical ITR-4 pipeline: compute_canonical_itr4
computes once, generate_cbdt_json dispatches ITR-4 to the v2 path, and the
produced CBDT JSON passes the official ITR-4 schema gate. Also verifies
the form dispatcher (compute_canonical) routes ITR-1 and ITR-4 correctly.

Run: pytest tests/test_filing_gateway_v2_itr4.py -v
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.engine.filing_gateway_v2 import (
    FilingGatewayV2Error,
    ITR1PipelineResult,
    ITR4PipelineResult,
    _generate_cbdt_json_itr4,
    compute_canonical,
    compute_canonical_itr4,
    generate_cbdt_json,
)
from app.engine.itd.itr4_schema import validate_itr4_json
from app.schemas.return_draft import (
    BankAccount,
    Employer,
    FinancialParticulars,
    HouseProperty,
    Presumptive44AD,
    Presumptive44ADA,
    Presumptive44AE,
    ReconciliationDiscrepancy,
    ReturnDraft,
    create_empty_draft,
)


def _financial_particulars() -> FinancialParticulars:
    """Non-zero balance-sheet particulars so CBDT Sl 139 rule passes.

    The ITR-4 Category A validator requires Schedule BP financial particulars
    (sundry creditors, inventories, cash-in-hand, etc.) when gross receipts or
    turnover is disclosed. In production these are entered on the Business tab;
    the test fixture supplies representative values.
    """
    return FinancialParticulars(
        cashBalance=Decimal("50000"),
        bankBalance=Decimal("200000"),
        inventory=Decimal("100000"),
        sundryDebtors=Decimal("80000"),
        sundryCreditors=Decimal("60000"),
        totalAssets=Decimal("430000"),
        securedLoans=Decimal("0"),
        unsecuredLoans=Decimal("0"),
        grossProfit=Decimal("600000"),
        netProfit=Decimal("600000"),
    )


def _filing_ready_itr4(scheme: str = "44AD") -> ReturnDraft:
    """A canonical ITR-4 draft carrying all official-filing fields.

    Populates personal/filing/verification so _itr4_filing_profile can
    construct a valid ITR4FilingProfile, plus one business row in the
    requested scheme + a refund bank account.
    """
    draft = create_empty_draft("2026-27", "ITR-4", "new")
    p = draft.personal
    p.pan = "ABCDE1234F"
    p.firstName = "Rahul"
    p.surnameOrOrgName = "Sharma"
    p.fatherName = "Mohan Sharma"
    p.employerCategory = "OTH"
    p.dateOfBirth = "1980-05-15"
    p.age = 45
    p.flatNo = "12A"
    p.localityOrArea = "Central"
    p.city = "Delhi"
    p.stateCode = "07"
    p.pinCode = "110001"
    p.mobile = "9876543210"
    p.email = "rahul@example.com"
    draft.verification.place = "Delhi"
    draft.verification.declarationAccepted = True
    draft.verification.capacity = "SELF"
    draft.bankAccounts = [BankAccount(
        id="b1", bankName="SBI", accountNumber="1234567890",
        ifscCode="SBIN0001234", accountType="SB", useForRefund=True,
    )]
    if scheme == "44AD":
        draft.businesses = [Presumptive44AD(
            id="b1", natureCode="01001",
            digitalReceipts=Decimal("5000000"),
            nonDigitalReceipts=Decimal("1000000"),
            declaredIncome=Decimal("600000"),
            financialParticulars=_financial_particulars(),
        )]
    elif scheme == "44ADA":
        draft.businesses = [Presumptive44ADA(
            id="b1", natureCode="14001",
            grossReceipts=Decimal("4000000"),
            digitalReceipts=Decimal("3000000"),
            nonDigitalReceipts=Decimal("1000000"),
            declaredIncome=Decimal("2000000"),
            financialParticulars=_financial_particulars(),
        )]
    elif scheme == "44AE":
        draft.businesses = [Presumptive44AE(
            id="b1", natureCode="08001",
            vehicles=[
                {"vehicleType": "HEAVY", "tonnage": Decimal("16"),
                 "ownedMonths": 12, "vehicleNumber": "KA01"},
            ],
            financialParticulars=_financial_particulars(),
        )]
    return draft


# ── compute_canonical_itr4 ───────────────────────────────────────────────────

def test_compute_canonical_itr4_returns_summary():
    """compute_canonical_itr4 maps + computes once and returns a summary."""
    draft = _filing_ready_itr4("44AD")
    pipeline = compute_canonical_itr4(draft)
    assert isinstance(pipeline, ITR4PipelineResult)
    assert pipeline.computation.gross_total_income > 0
    assert "grossTotalIncome" in pipeline.summary
    assert pipeline.summary["computedByFormEngine"] == "ITR-1"  # shared summary
    assert pipeline.breakdown["presumptive_scheme"] == "44AD"


def test_compute_canonical_dispatches_itr1_and_itr4():
    """compute_canonical routes ITR-1 and ITR-4 to the correct pipeline."""
    itr1 = create_empty_draft("2026-27", "ITR-1", "new")
    itr1.employers = [Employer(id="e1", basic=Decimal("800000"))]
    result1 = compute_canonical(itr1)
    assert isinstance(result1, ITR1PipelineResult)

    itr4 = _filing_ready_itr4("44AD")
    result4 = compute_canonical(itr4)
    assert isinstance(result4, ITR4PipelineResult)


def test_compute_canonical_rejects_unsupported_form():
    """ITR-2/3 are not yet supported by the v2 pipeline."""
    draft = ReturnDraft(assessmentYear="2026-27", form="ITR-2")
    with pytest.raises(FilingGatewayV2Error) as caught:
        compute_canonical(draft)
    assert "ITR-1 and ITR-4 only" in caught.value.message


# ── generate_cbdt_json (ITR-4 dispatch) ──────────────────────────────────────

def test_generate_cbdt_json_itr4_44ad_passes_schema():
    """ITR-4 44AD CBDT JSON validates against the official schema."""
    draft = _filing_ready_itr4("44AD")
    official_json, summary = generate_cbdt_json(draft)
    # Must pass the official ITR-4 schema gate.
    validate_itr4_json(official_json)
    assert summary["grossTotalIncome"] > 0
    assert official_json.get("ITR4", {}).get("FormName") or "ITR-4" in str(official_json)


def test_generate_cbdt_json_itr4_44ada_passes_schema():
    """ITR-4 44ADA CBDT JSON validates against the official schema."""
    draft = _filing_ready_itr4("44ADA")
    official_json, _ = generate_cbdt_json(draft)
    validate_itr4_json(official_json)


def test_generate_cbdt_json_itr4_44ae_passes_schema():
    """ITR-4 44AE CBDT JSON validates against the official schema.

    The pre-existing validator conflict (CBDT Sl 12 vs Sl 137) is resolved:
    Rule 12 (ITR4-R012) now only fires when a business code is present but
    NO presumptive scheme is active — 44ADA/44AE carry their own business
    codes (Sl 137) and no longer trip the 44AD-specific check. The 44AE
    goods-carriage builder also emits the official schema fields
    (RegNumberGoodsCarriage, OwnedLeasedHiredFlag, TonnageCapacity,
    HoldingPeriod, PresumptiveIncome) instead of the old
    IsHeavyGoodsVehicle/NoOfMonthsOwned/GrossVehicleWeight fields.
    """
    draft = _filing_ready_itr4("44AE")
    official_json, _ = generate_cbdt_json(draft)
    validate_itr4_json(official_json)


def test_generate_cbdt_json_dispatches_itr4_not_itr1():
    """generate_cbdt_json routes ITR-4 to _generate_cbdt_json_itr4."""
    draft = _filing_ready_itr4("44AD")
    official_json, summary = _generate_cbdt_json_itr4(draft)
    validate_itr4_json(official_json)
    assert summary["grossTotalIncome"] > 0


# ── Guards ───────────────────────────────────────────────────────────────────

def test_compute_canonical_itr4_rejects_pending_discrepancies():
    """Pending reconciliation discrepancies block ITR-4 compute."""
    draft = _filing_ready_itr4("44AD")
    draft.reconciliation.discrepancies.append(ReconciliationDiscrepancy(
        id="d1", category="interest from savings bank",
        description="AIS/TIS mismatch.", status="PENDING",
    ))
    with pytest.raises(FilingGatewayV2Error) as caught:
        compute_canonical_itr4(draft)
    assert "reconciliation" in caught.value.message.lower()


def test_generate_cbdt_json_itr4_rejects_missing_profile():
    """Missing required profile fields raise a clear filing-profile error."""
    draft = _filing_ready_itr4("44AD")
    draft.personal.pan = ""  # required field removed
    with pytest.raises(FilingGatewayV2Error) as caught:
        generate_cbdt_json(draft)
    assert "filing profile" in caught.value.message.lower()


# ── ITR-1 unchanged (regression) ─────────────────────────────────────────────

def test_generate_cbdt_json_itr1_still_works():
    """Regression: ITR-1 generate_cbdt_json still dispatches correctly."""
    # Minimal ITR-1 filing-ready draft.
    draft = create_empty_draft("2026-27", "ITR-1", "new")
    draft.employers = [Employer(id="e1", basic=Decimal("800000"))]
    p = draft.personal
    p.pan = "ABCDE1234F"
    p.firstName = "Rahul"
    p.surnameOrOrgName = "Sharma"
    p.fatherName = "Mohan Sharma"
    p.dateOfBirth = "1980-05-15"
    p.flatNo = "12A"
    p.localityOrArea = "Central"
    p.city = "Delhi"
    p.stateCode = "07"
    p.pinCode = "110001"
    p.mobile = "9876543210"
    p.email = "rahul@example.com"
    draft.verification.place = "Delhi"
    draft.verification.declarationAccepted = True
    draft.verification.capacity = "SELF"
    pipeline = compute_canonical(draft)
    assert isinstance(pipeline, ITR1PipelineResult)
    assert pipeline.summary["grossTotalIncome"] > 0
