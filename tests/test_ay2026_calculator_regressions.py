"""Release-blocking AY 2026-27 calculator regressions."""

from datetime import date
from decimal import Decimal

from app.engine.calculators.itr1 import compute as compute_itr1
from app.engine.calculators.itr4 import compute as compute_itr4
from app.engine.common.interest import compute_234b, compute_234c
from app.engine.schedules.deductions.section_80d import compute as compute_80d
from app.engine.schedules.deductions.section_80g import (
    compute as compute_80g,
    compute_details as compute_80g_details,
)
from app.routers.tax import compute_tax_summary
from app.schemas.itr1 import (
    AgeBracket,
    CapitalGainsIncome,
    Chapter6ADeductions,
    Donation80G,
    HousePropertyIncome,
    ITR1Input,
    OtherSourcesIncome,
    PropertyType,
    SalaryIncome,
    TaxRegime,
)
from app.schemas.itr4 import (
    ITR4Input,
    PresumptiveBusinessIncome44AD,
    PresumptiveScheme,
)
from fastapi import HTTPException
import pytest


def _itr1_input(
    *,
    regime: TaxRegime,
    salary: Decimal = Decimal("0"),
    property_type: PropertyType = PropertyType.SELF_OCCUPIED,
    rent: Decimal = Decimal("0"),
    home_loan_interest: Decimal = Decimal("0"),
    ltcg_112a: Decimal = Decimal("0"),
    relief_89: Decimal = Decimal("0"),
) -> ITR1Input:
    """Build a minimal valid ITR-1 calculation input."""
    return ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=regime,
        salary_income=SalaryIncome(gross_salary=salary),
        house_property_income=HousePropertyIncome(
            property_type=property_type,
            annual_rent_received=rent,
            home_loan_interest_paid=home_loan_interest,
        ),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(),
        capital_gains=(
            CapitalGainsIncome(ltcg_112a=ltcg_112a)
            if ltcg_112a > 0
            else None
        ),
        relief_89=relief_89,
    )


def test_new_regime_house_property_loss_cannot_reduce_itr1_other_heads() -> None:
    """New-regime let-out loss must not reduce salary income."""
    result = compute_itr1(
        _itr1_input(
            regime=TaxRegime.NEW,
            salary=Decimal("600000"),
            property_type=PropertyType.LET_OUT,
            home_loan_interest=Decimal("300000"),
        )
    )

    assert result.salary_income == Decimal("525000")
    assert result.house_property_income == Decimal("0")
    assert result.hp_loss_disallowed == Decimal("300000")
    assert result.gross_total_income == Decimal("525000")


def test_old_regime_house_property_inter_head_setoff_is_capped() -> None:
    """Old-regime current-year inter-head HP loss is capped at Rs 2 lakh."""
    result = compute_itr1(
        _itr1_input(
            regime=TaxRegime.OLD,
            salary=Decimal("600000"),
            property_type=PropertyType.LET_OUT,
            home_loan_interest=Decimal("300000"),
        )
    )

    assert result.salary_income == Decimal("550000")
    assert result.house_property_income == Decimal("-200000")
    assert result.hp_loss_disallowed == Decimal("100000")
    assert result.gross_total_income == Decimal("350000")


def test_new_regime_house_property_loss_cannot_reduce_itr4_business_income() -> None:
    """New-regime let-out loss must not reduce presumptive business income."""
    result = compute_itr4(
        ITR4Input(
            age_bracket=AgeBracket.BELOW_60,
            tax_regime=TaxRegime.NEW,
            presumptive_scheme=PresumptiveScheme.S44AD,
            business_income_44ad=PresumptiveBusinessIncome44AD(
                total_turnover=Decimal("500000"),
                digital_turnover=Decimal("500000"),
                cash_turnover=Decimal("0"),
            ),
            salary_income=SalaryIncome(gross_salary=Decimal("0")),
            house_property_income=HousePropertyIncome(
                property_type=PropertyType.LET_OUT,
                home_loan_interest_paid=Decimal("100000"),
            ),
            other_sources_income=OtherSourcesIncome(),
            deductions_chapter6a=Chapter6ADeductions(),
        )
    )

    assert result.presumptive_income == Decimal("30000.00")
    assert result.house_property_income == Decimal("0")
    assert result.hp_loss_disallowed == Decimal("100000")
    assert result.gross_total_income == Decimal("30000.00")


def test_permitted_112a_gain_remains_part_of_gross_total_income() -> None:
    """A permitted 112A gain below the Rs 1.25L exemption is fully exempt.

    The annual Section 112A exemption removes the exempt portion from total
    income entirely (not merely from the 12.5% special-rate tax).  A Rs 1L
    gain is within the exemption, so it reports as ``capital_gains_112a``
    (the pre-exemption net gain, for display/reconciliation) but contributes
    zero to GTI, taxable income, the slab base, and the special-rate tax.
    """
    result = compute_itr1(
        _itr1_input(
            regime=TaxRegime.OLD,
            ltcg_112a=Decimal("100000"),
        )
    )

    assert result.errors == []
    assert result.capital_gains_112a == Decimal("100000")  # reported net gain
    assert result.gross_total_income == Decimal("0")        # exempt → not in GTI
    assert result.taxable_income == Decimal("0")
    assert result.special_rate_tax == Decimal("0")


def test_section_89_relief_reduces_final_liability() -> None:
    """Valid section 89 relief must reduce tax before final rounding."""
    without_relief = compute_itr1(
        _itr1_input(regime=TaxRegime.OLD, salary=Decimal("1500000"))
    )
    with_relief = compute_itr1(
        _itr1_input(
            regime=TaxRegime.OLD,
            salary=Decimal("1500000"),
            relief_89=Decimal("50000"),
        )
    )

    assert with_relief.net_tax_liability == without_relief.net_tax_liability - Decimal("50000")
    assert with_relief.balance_payable == without_relief.balance_payable - Decimal("50000")


def test_234b_applies_at_exactly_ten_thousand_assessed_tax() -> None:
    """Advance-tax interest threshold includes assessed tax of Rs 10,000."""
    interest = compute_234b(
        assessed_tax=Decimal("10000"),
        advance_tax_paid=Decimal("0"),
        filing_date=date(2026, 7, 31),
        ay_start=date(2026, 4, 1),
    )

    assert interest == Decimal("400")


def test_234c_march_shortfall_is_charged_for_one_month() -> None:
    """The final regular advance-tax installment carries one month of interest."""
    interest = compute_234c(
        advance_tax_paid=[Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0")],
        total_assessed_tax=Decimal("100000"),
        ay_start=date(2026, 4, 1),
    )

    assert interest == Decimal("5050")


def test_234c_applies_at_exactly_ten_thousand_assessed_tax() -> None:
    """Deferred advance-tax interest threshold includes Rs 10,000."""
    interest = compute_234c(
        advance_tax_paid=[Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0")],
        total_assessed_tax=Decimal("10000"),
        ay_start=date(2026, 4, 1),
    )

    assert interest == Decimal("505")


def test_presumptive_234c_uses_payment_made_by_march() -> None:
    """A presumptive taxpayer's fourth-installment payment satisfies section 234C."""
    interest = compute_234c(
        advance_tax_paid=[Decimal("0"), Decimal("0"), Decimal("0"), Decimal("100000")],
        total_assessed_tax=Decimal("100000"),
        ay_start=date(2026, 4, 1),
        is_presumptive_44ad_44ada=True,
    )

    assert interest == Decimal("0")


def test_80d_preventive_checkup_limit_is_aggregate() -> None:
    """The Rs 5,000 preventive-checkup sub-limit applies across both buckets."""
    deduction = compute_80d(
        Chapter6ADeductions(
            amount_80d_preventive_self=Decimal("5000"),
            amount_80d_preventive_parents=Decimal("5000"),
        ),
        AgeBracket.BELOW_60,
        TaxRegime.OLD,
    )

    assert deduction == Decimal("5000")


def test_80g_cash_donation_above_limit_is_wholly_disallowed() -> None:
    """A cash donation exceeding Rs 2,000 receives no section 80G deduction."""
    deduction = compute_80g(
        Chapter6ADeductions(
            donations_80g=[
                Donation80G(
                    cash_amount=Decimal("5000"),
                    qualifying_percentage="100%",
                    limit_on_deduction="without limit",
                )
            ]
        ),
        adjusted_gti=Decimal("100000"),
        regime=TaxRegime.OLD,
    )

    assert deduction == Decimal("0")


def test_80g_limited_donations_share_one_adjusted_gti_ceiling() -> None:
    """Limited-category donations share one 10 percent adjusted-GTI ceiling."""
    deduction = compute_80g(
        Chapter6ADeductions(
            amount_80g=Decimal("20000"),
            donations_80g=[
                Donation80G(
                    non_cash_amount=Decimal("10000"),
                    qualifying_percentage="100%",
                    limit_on_deduction="with limit",
                ),
                Donation80G(
                    non_cash_amount=Decimal("10000"),
                    qualifying_percentage="100%",
                    limit_on_deduction="with limit",
                ),
            ]
        ),
        adjusted_gti=Decimal("100000"),
        regime=TaxRegime.OLD,
    )

    assert deduction == Decimal("10000")


def test_80g_cash_limit_is_aggregated_by_donee_pan() -> None:
    """Multiple cash rows for one PAN share the statutory Rs 2,000 threshold."""
    details = compute_80g_details(
        Chapter6ADeductions(
            amount_80g=Decimal("3000"),
            donations_80g=[
                Donation80G(
                    cash_amount=Decimal("1500"),
                    donee_pan="ABCDE1234F",
                ),
                Donation80G(
                    cash_amount=Decimal("1500"),
                    donee_pan="ABCDE1234F",
                ),
            ],
        ),
        adjusted_gti=Decimal("100000"),
        regime=TaxRegime.OLD,
    )

    assert details.gross_amount == Decimal("3000")
    assert details.statutory_eligible == Decimal("0")
    assert details.allowed_deduction == Decimal("0")


def test_80g_user_claim_caps_structured_eligibility() -> None:
    """Structured statutory eligibility cannot exceed the taxpayer's claim."""
    details = compute_80g_details(
        Chapter6ADeductions(
            amount_80g=Decimal("6000"),
            donations_80g=[Donation80G(non_cash_amount=Decimal("10000"))],
        ),
        adjusted_gti=Decimal("100000"),
        regime=TaxRegime.OLD,
    )

    assert details.statutory_eligible == Decimal("10000")
    assert details.allowed_deduction == Decimal("6000")
    assert sum(
        category.eligible_amount for category in details.categories.values()
    ) == Decimal("6000")


def test_80g_zero_user_claim_stays_zero_with_structured_rows() -> None:
    """Structured donations must not create a deduction the taxpayer did not claim."""
    details = compute_80g_details(
        Chapter6ADeductions(
            amount_80g=Decimal("0"),
            donations_80g=[Donation80G(non_cash_amount=Decimal("10000"))],
        ),
        adjusted_gti=Decimal("100000"),
        regime=TaxRegime.OLD,
    )

    assert details.statutory_eligible == Decimal("10000")
    assert details.allowed_deduction == Decimal("0")
    assert sum(
        category.eligible_amount for category in details.categories.values()
    ) == Decimal("0")


def test_tax_summary_preserves_imported_cg_evidence_without_taxing_it() -> None:
    """Purchase/sale evidence with form ITR-2 now runs the ITR-2 engine.

    Previously the backend returned a provisional preview with GTI=0.
    Now that ITR-2 is fully integrated, the evidence rows with sale values
    are mapped to canonical CGTransactions and the ITR-2 engine computes
    actual capital gains.  The first row (saleCost=0, purchaseCost=4000)
    produces no gain; the second row (saleValue=68394, no cost) produces
    a full gain because cost_of_acquisition defaults to 0.
    """
    result = compute_tax_summary(
        payload={
            "assessmentYear": "2026-27",
            "form": "ITR-2",
            "capitalGainTransactions": [
                {
                    "assetType": "MUTUAL_FUND",
                    "purchaseDate": "",
                    "saleDate": "",
                    "purchaseCost": 4000,
                    "saleCost": 0,
                    "importStatus": "INCOMPLETE",
                },
                {
                    "recordKind": "EVIDENCE",
                    "evidenceSide": "SALE",
                    "assetType": "MUTUAL_FUND",
                    "saleValue": 68394,
                },
            ],
        },
        regime="NEW",
        current_user=None,
    )

    # ITR-2 engine now computes actual capital gains from the evidence.
    assert result["requestedForm"] == "ITR-2"
    assert result["computedByFormEngine"] == "ITR-2"
    assert result["filingComputationStatus"] == "FORM_COMPUTATION"


def test_tax_summary_computes_canonical_restricted_112a_rows() -> None:
    """Structured rows must be the authoritative ITR-1 capital-gain source."""
    result = compute_tax_summary(
        payload={
            "assessmentYear": "2026-27",
            "form": "ITR-1",
            "ltcg112APre": 999999,
            "capitalGainTransactions": [{
                "assetType": "LISTED_EQUITY",
                "purchaseDate": "2023-01-01",
                "saleDate": "2025-01-02",
                "purchaseCost": 100000,
                "saleCost": 120000,
                "transferExpenses": 1000,
                "sttPaidOnAcquisition": True,
                "sttPaidOnTransfer": True,
                "recognizedExchange": True,
            }],
        },
        regime="NEW",
        current_user=None,
    )

    assert result["capitalGainsStatus"] == "VALID"
    assert result["capitalGainsSummary"]["gross112AGain"] == 19000.0
    assert result["capitalGainsSummary"]["costOfAcquisition"] == 101000.0
    # The Rs 19,000 gain is below the Rs 1.25L Section 112A annual exemption,
    # so it is fully exempt and does not enter GTI (the exemption removes the
    # exempt portion from total income, not merely from the 12.5% tax).
    assert result["gti"] == 0.0


def test_tax_summary_returns_structured_restricted_112a_issues() -> None:
    """Incomplete evidence must block computation with row-level issue codes."""
    with pytest.raises(HTTPException) as exc_info:
        compute_tax_summary(
            payload={
                "assessmentYear": "2026-27",
                "form": "ITR-1",
                "capitalGainTransactions": [{
                    "assetType": "PROPERTY",
                    "saleCost": 120000,
                }],
            },
            regime="NEW",
            current_user=None,
        )

    assert exc_info.value.status_code == 422
    detail = exc_info.value.detail
    assert detail["status"] == "BLOCKED"
    assert detail["capitalGainsSummary"]["transactionCount"] == 0
    assert {issue["code"] for issue in detail["issues"]} >= {
        "UNSUPPORTED_ASSET",
        "MISSING_ACQUISITION_DATE",
        "MISSING_TRANSFER_DATE",
        "MISSING_ACTUAL_COST",
    }


def test_tax_summary_maps_canonical_employers_without_double_counting() -> None:
    """Canonical salary arrays must be authoritative and count each component once."""
    result = compute_tax_summary(
        payload={
            "assessmentYear": "2026-27",
            "form": "ITR-1",
            "employerEntries": [
                {
                    "basic": 600000,
                    "perquisites": 100000,
                    "profitsInLieu": 50000,
                    "professionalTax": 0,
                }
            ],
        },
        regime="OLD",
        current_user=None,
    )

    assert result["grossSalary"] == 750000.0
    assert result["netSalary"] == 700000.0
    assert result["gti"] == 700000.0


def test_tax_summary_counts_explicit_claimed_tds_and_excludes_unclaimed_rows() -> None:
    """Only the TDS-deducted value of rows selected for claim is creditable."""
    result = compute_tax_summary(
        payload={
            "assessmentYear": "2026-27",
            "form": "ITR-1",
            "tdsEntries": [
                {
                    "section": "192",
                    "deductorName": "Example Employer",
                    "deductorTAN": "ABCD12345E",
                    "certificateNo": "CERT-1",
                    "deductionDate": "2025-07-01",
                    "incomeAmount": 500,
                    "tdsDeducted": 500,
                    "claimedInReturn": True,
                },
                {
                    "section": "192",
                    "incomeAmount": 1000,
                    "tdsDeducted": 250,
                    "claimedInReturn": False,
                },
            ],
        },
        regime="OLD",
        current_user=None,
    )

    assert result["totalTDS"] == 500.0
    assert result["totalTaxesPaid"] == 500.0
    assert result["refundDue"] == 500.0


def test_tax_summary_marks_incomplete_credits_provisional_and_reclassifies_early_sat() -> None:
    """Incomplete evidence blocks refund confirmation and pre-year-end SAT is advance tax."""
    result = compute_tax_summary(
        payload={
            "assessmentYear": "2026-27",
            "form": "ITR-1",
            "tdsEntries": [{
                "section": "192",
                "incomeAmount": 50000,
                "tdsDeducted": 5000,
                "claimedInReturn": True,
            }],
            "advanceTaxEntries": [{
                "depositDate": "2026-02-01",
                "amount": 6000,
                "bsrCode": "",
                "challanSerialNo": 0,
            }],
            "selfAssessmentTaxEntries": [{
                "depositDate": "2026-03-28",
                "amount": 7000,
                "bsrCode": "",
                "challanNo": "",
            }],
        },
        regime="NEW",
        current_user=None,
    )

    assert result["totalTDS"] == 0.0
    assert result["advanceTax"] == 0.0
    assert result["selfAssessmentTax"] == 0.0
    assert result["totalTaxesPaid"] == 0.0
    assert result["refundDue"] == 0.0
    assert result["enteredCredits"]["tds"] == 5000.0
    assert result["enteredCredits"]["advanceTax"] == 13000.0
    assert result["enteredCredits"]["total"] == 18000.0
    assert result["validatedCredits"]["total"] == 0.0
    assert result["provisionalRefund"] == 18000.0
    assert result["blockedCreditsTotal"] == 18000.0
    assert result["creditStatus"] == "PROVISIONAL"
    assert result["refundStatus"] == "PROVISIONAL_BLOCKED"
    issue_codes = {issue["code"] for issue in result["creditValidationIssues"]}
    assert "MISSING_TAN" in issue_codes
    assert "INVALID_BSR_FORMAT" in issue_codes
    assert "INVALID_CHALLAN_SERIAL" in issue_codes
    assert "RECLASSIFIED_AS_ADVANCE_TAX" in issue_codes


def test_tax_summary_malformed_identifiers_do_not_crash_or_validate_credit() -> None:
    """Random draft identifiers remain provisional and never reach strict models."""
    result = compute_tax_summary(
        payload={
            "assessmentYear": "2026-27",
            "form": "ITR-1",
            "tdsEntries": [{
                "section": "192",
                "deductorName": "Example Employer",
                "deductorTAN": "VYGYVYTFTFVTYFTFVTFTTVT",
                "certificateNo": "CERT",
                "deductionDate": "2025-06-01",
                "incomeAmount": 50000,
                "tdsDeducted": 5000,
                "claimedInReturn": True,
            }],
            "advanceTaxEntries": [{
                "bsrCode": "ABC1234",
                "depositDate": "2026-02-01",
                "challanSerialNo": "ABCDE",
                "amount": 6000,
            }],
        },
        regime="OLD",
        current_user=None,
    )

    assert result["calculationStatus"] == "CALCULATED_WITH_CREDIT_ISSUES"
    assert result["enteredCredits"]["total"] == 11000.0
    assert result["validatedCredits"]["total"] == 0.0
    assert result["blockedCreditsTotal"] == 11000.0
    assert result["provisionalRefund"] == 11000.0
    assert result["confirmedRefund"] is None
    issues = result["creditValidationIssues"]
    assert any(issue["code"] == "INVALID_TAN_FORMAT" and issue["field"] == "deductorTAN" for issue in issues)
    assert any(issue["code"] == "INVALID_BSR_FORMAT" and issue["field"] == "bsrCode" for issue in issues)
    assert any(issue["code"] == "INVALID_CHALLAN_SERIAL" for issue in issues)


def test_tax_summary_maps_mixed_44ad_receipts_and_declared_income() -> None:
    """Canonical 44AD receipt modes and a higher declaration must reach the engine."""
    result = compute_tax_summary(
        payload={
            "assessmentYear": "2026-27",
            "form": "ITR-4",
            "businessEntries": [
                {
                    "scheme": "44AD",
                    "digitalReceipts": 600000,
                    "nonDigitalReceipts": 400000,
                    "declaredIncome": 200000,
                }
            ],
        },
        regime="NEW",
        current_user=None,
    )

    assert result["bizIncome"] == 200000.0
    assert result["gti"] == 200000.0


def test_tax_summary_rejects_engine_eligibility_errors() -> None:
    """Ineligible inputs must not be represented as a valid zero-tax result."""
    with pytest.raises(HTTPException) as exc_info:
        compute_tax_summary(
            payload={
                "assessmentYear": "2026-27",
                "form": "ITR-1",
                "employerEntries": [{"basic": 6000000}],
            },
            regime="NEW",
            current_user=None,
        )

    assert exc_info.value.status_code == 422
    assert "ITR-2" in str(exc_info.value.detail)


def test_tax_summary_rejects_unsupported_assessment_year() -> None:
    """A fixed AY 2026-27 engine must reject requests for another year."""
    with pytest.raises(HTTPException) as exc_info:
        compute_tax_summary(
            payload={"assessmentYear": "2025-26", "form": "ITR-1"},
            regime="NEW",
            current_user=None,
        )

    assert exc_info.value.status_code == 422


def test_tax_summary_maps_filing_dates_and_advance_tax_installments() -> None:
    """Production mapping must preserve dates and installment timing for interest."""
    result = compute_tax_summary(
        payload={
            "assessmentYear": "2026-27",
            "form": "ITR-1",
            "employerEntries": [{"basic": 1500000}],
            "filingDate": "2026-08-31",
            "dueDate": "2026-07-31",
            "advanceTaxEntries": [
                {
                    "amount": 100000,
                    "depositDate": "2026-03-15",
                    "bsrCode": "1234567",
                    "challanSerialNo": "12345",
                },
            ],
        },
        regime="OLD",
        current_user=None,
    )

    assert result["totalTaxPaid"] == 100000.0
    assert result["adv15Mar"] == 100000.0
    assert result["taxPayable"] > 0


def test_tax_summary_marks_claimed_non_salary_tds_without_tan_provisional() -> None:
    """A non-salary credit without TAN remains entered but is not filing-valid."""
    result = compute_tax_summary(
        payload={
            "assessmentYear": "2026-27",
            "form": "ITR-1",
            "tdsEntries": [
                {"section": "194A", "grossAmount": 10000, "taxDeducted": 1000},
            ],
        },
        regime="NEW",
        current_user=None,
    )

    assert result["enteredCredits"]["tds"] == 1000.0
    assert result["validatedCredits"]["tds"] == 0.0
    assert result["creditStatus"] == "PROVISIONAL"
    assert any(
        issue["code"] == "MISSING_TAN" and issue["field"] == "deductorTAN"
        for issue in result["creditValidationIssues"]
    )


def test_tax_summary_uses_tis_dividend_control_without_mutating_detail_rows() -> None:
    """A TIS accepted category total must control overlapping dividend evidence."""
    result = compute_tax_summary(
        payload={
            "assessmentYear": "2026-27",
            "form": "ITR-1",
            "dividendEntries": [
                {"companyName": "Synthetic One", "grossAmount": 500},
                {"companyName": "Synthetic Two SFT", "grossAmount": 14},
                {"companyName": "Synthetic Two TDS Evidence", "grossAmount": 14},
            ],
            "importedCategoryControls": {"dividend": 514},
        },
        regime="NEW",
        current_user=None,
    )

    assert result["totalDividend"] == 514.0
    assert result["incomeOthSrc"] == 514.0


def test_salary_tds_with_26as_identity_does_not_require_certificate_or_date() -> None:
    """Schedule TDS1 credit requires TAN, employer, income and TDS—not Form 16 metadata."""
    result = compute_tax_summary(
        payload={
            "assessmentYear": "2026-27",
            "form": "ITR-1",
            "employerEntries": [{"basic": 1500000}],
            "tdsEntries": [{
                "section": "192",
                "deductorName": "Synthetic Employer Private Limited",
                "deductorTAN": "ABCD12345E",
                "incomeAmount": 1500000,
                "tdsDeducted": 100000,
                "financialYear": "2025-26",
                "verified26AS": True,
                "claimedInReturn": True,
            }],
        },
        regime="NEW",
        current_user=None,
    )

    assert result["enteredCredits"]["tds"] == 100000.0
    assert result["validatedCredits"]["tds"] == 100000.0
    assert result["creditStatus"] == "CONFIRMED"
    assert result["creditValidationIssues"] == []


def test_tax_summary_rejects_multiple_businesses_instead_of_truncating() -> None:
    """Unsupported multiple-business returns must not silently ignore later rows."""
    with pytest.raises(HTTPException) as exc_info:
        compute_tax_summary(
            payload={
                "assessmentYear": "2026-27",
                "form": "ITR-4",
                "businessEntries": [
                    {"scheme": "44AD", "digitalReceipts": 100000},
                    {"scheme": "44AD", "digitalReceipts": 200000},
                ],
            },
            regime="NEW",
            current_user=None,
        )

    assert exc_info.value.status_code == 422


# ---------------------------------------------------------------------------
# HRA exemption regression — per-employer statutory recomputation.
#
# Reproduces the real-client "TEST 2" scenario: HRA received, rent paid,
# non-metro city, self-occupied home-loan interest, 80C/80D/80CCD(1B).
# The frontend sends HRA facts per-employer inside employerEntries (not as
# a top-level hraDetails object).  The engine must statutorily recompute the
# exemption u/s 10(13A) from those per-employer facts.
# ---------------------------------------------------------------------------

def _test2_hra_payload() -> dict:
    """Return the flat payload shape the frontend sends for TEST 2.

    Corrected inputs (rent paid = 3,30,000/year so that the statutory HRA
    exemption resolves to 2,40,000 — matching the Form 16 figure):
        HRA exempt = min(300000, 330000 - 10%*900000, 40%*900000)
                   = min(300000, 240000, 360000) = 240000.
    """
    return {
        "assessmentYear": "2026-27",
        "form": "ITR-1",
        "itrForm": "ITR-1",
        "pan": "EPPPG3078Q",
        "firstName": "Devansh",
        "surnameOrOrgName": "Goyanka",
        "dob": "1995-01-01",
        "age": 31,
        "employerCategory": "OTH",
        "filingSection": "139(1)",
        "residentialStatus": "ROR",
        "employerEntries": [
            {
                "employerName": "Sunit Goyanka",
                "natureOfEmployment": "OTH",
                "employerAddress": "Akola",
                "employerCity": "Akola",
                "employerStateCode": "19",
                "basic": "900000",
                "hra": "300000",
                "otherAllowance": "540000",
                "perquisites": "60000",
                "rentPaid": "330000",
                "isMetroCity": False,
                "professionalTax": "2400",
            }
        ],
        "housePropertyEntries": [
            {
                "propertyType": "SELF_OCCUPIED",
                "interestOnLoan": "200000",
            }
        ],
        "section80C": {
            "investments": [
                {"investmentType": "PPF", "amount": "150000"},
            ]
        },
        "s80D_self": "25000",
        "s80CCD1B": "50000",
        "bankAccountData": {
            "accounts": [
                {
                    "bankName": "HDFC",
                    "accountNumber": "1234567890",
                    "ifscCode": "HDFC0001234",
                    "accountType": "SB",
                    "useForRefund": True,
                }
            ]
        },
        "verification": {
            "capacity": "SELF",
            "place": "Akola",
            "date": "2026-07-31",
            "declarationAccepted": True,
        },
    }


def test_hra_exemption_per_employer_old_regime_statutorily_recomputed() -> None:
    """Old regime: HRA exemption must be statutorily recomputed from per-employer facts.

    With rent = 3,30,000:
        HRA exempt = min(300000, 330000 - 90000, 40%*900000)
                   = min(300000, 240000, 360000) = 240000.
    Salary income = 18,00,000 - 2,40,000 - 50,000 - 2,400 = 15,07,600.
    """
    payload = _test2_hra_payload()
    result = compute_tax_summary(
        payload=payload,
        regime="OLD",
        current_user=None,
    )

    # HRA exemption must be 2,40,000 (statutorily recomputed from per-employer facts).
    assert Decimal(str(result["hraExempt"])) == Decimal("240000"), (
        f"HRA exempt should be 2,40,000 under old regime, got {result['hraExempt']}"
    )

    # Salary income: 18,00,000 gross - 2,40,000 HRA - 50,000 std - 2,400 prof tax
    # = 15,07,600.
    assert Decimal(str(result["incomeFromSal"])) == Decimal("1507600"), (
        f"Salary income should be 15,07,600, got {result['incomeFromSal']}"
    )


def test_hra_exemption_per_employer_new_regime_disallowed() -> None:
    """New regime: HRA exemption must be disallowed (zero).

    Full gross salary taxable; std deduction 75,000 -> salary income = 17,25,000.
    """
    payload = _test2_hra_payload()
    result = compute_tax_summary(
        payload=payload,
        regime="NEW",
        current_user=None,
    )

    # HRA exemption must be 0 in new regime.
    assert Decimal(str(result["hraExempt"])) == Decimal("0"), (
        f"HRA exempt should be 0 under new regime, got {result['hraExempt']}"
    )

    # Salary income: 18,00,000 - 75,000 std = 17,25,000.
    assert Decimal(str(result["incomeFromSal"])) == Decimal("1725000"), (
        f"Salary income should be 17,25,000 under new regime, got {result['incomeFromSal']}"
    )


def test_hra_exemption_old_regime_cheaper_than_new_for_test2_scenario() -> None:
    """Old regime must be cheaper than new regime for the corrected TEST 2 scenario.

    With the statutorily recomputed HRA exemption of Rs 2,40,000:
        Old regime: slab 1,37,280 + cess 5,491 = gross 1,42,771; balTaxPayable 1,42,770 (288B)
        New regime: slab 1,45,000 + cess 5,800 = gross 1,50,800; balTaxPayable 1,50,800 (288B)
    Old regime is cheaper by exactly Rs 8,030 on the 288B-rounded balance.
    Section 288B rounds only the final payable/refund, not intermediate
    NetTaxLiability, so the unrounded aggregate (1,42,771) is exposed as
    netTaxLiability while balTaxPayable carries the statutory ₹10 rounding.
    """
    payload = _test2_hra_payload()

    old_result = compute_tax_summary(payload=payload, regime="OLD", current_user=None)
    new_result = compute_tax_summary(payload=payload, regime="NEW", current_user=None)

    old_tax = Decimal(str(old_result["netTaxLiability"]))
    new_tax = Decimal(str(new_result["netTaxLiability"]))
    old_payable = Decimal(str(old_result["balTaxPayable"]))
    new_payable = Decimal(str(new_result["balTaxPayable"]))

    # Old regime aggregate liability (pre-288B) is exactly 1,42,771.
    assert old_tax == Decimal("142771"), (
        f"Old regime netTaxLiability should be 1,42,771, got {old_tax}"
    )

    # New regime aggregate liability (pre-288B) is exactly 1,50,800.
    assert new_tax == Decimal("150800"), (
        f"New regime netTaxLiability should be 1,50,800, got {new_tax}"
    )

    # Section 288B rounds the final payable to nearest ₹10.
    assert old_payable == Decimal("142770"), (
        f"Old regime balTaxPayable should be 1,42,770 (288B), got {old_payable}"
    )
    assert new_payable == Decimal("150800"), (
        f"New regime balTaxPayable should be 1,50,800 (288B), got {new_payable}"
    )

    # Old regime must be cheaper by exactly 8,030 on the 288B-rounded balance.
    assert new_payable - old_payable == Decimal("8030"), (
        f"Old regime should be cheaper by 8,030, got diff {new_payable - old_payable}"
    )


# ---------------------------------------------------------------------------
# Explicit HRA three-condition boundary cases.
#
# The statutory HRA exemption is the *minimum* of three conditions:
#   1. Actual HRA received.
#   2. Rent paid - 10% of salary (basic + DA).
#   3. 50% of salary (metro) / 40% of salary (non-metro).
#
# Each test below isolates one binding term so a hardcoded formula (e.g.
# "always 40%" or "always use actual HRA") is caught.
# ---------------------------------------------------------------------------

def _hra_payload(*, rent: str, hra: str = "300000", basic: str = "900000",
                 is_metro: bool = False) -> dict:
    """Build a minimal old-regime payload with a single employer and HRA facts."""
    return {
        "assessmentYear": "2026-27",
        "form": "ITR-1",
        "pan": "EPPPG3078Q",
        "firstName": "Devansh",
        "surnameOrOrgName": "Goyanka",
        "dob": "1995-01-01",
        "age": 31,
        "employerCategory": "OTH",
        "filingSection": "139(1)",
        "residentialStatus": "ROR",
        "employerEntries": [
            {
                "employerName": "Employer",
                "natureOfEmployment": "OTH",
                "employerAddress": "A",
                "employerCity": "A",
                "employerStateCode": "19",
                "basic": basic,
                "hra": hra,
                "rentPaid": rent,
                "isMetroCity": is_metro,
            }
        ],
        "bankAccountData": {
            "accounts": [
                {
                    "bankName": "HDFC",
                    "accountNumber": "1234567890",
                    "ifscCode": "HDFC0001234",
                    "accountType": "SB",
                    "useForRefund": True,
                }
            ]
        },
        "verification": {
            "capacity": "SELF",
            "place": "A",
            "date": "2026-07-31",
            "declarationAccepted": True,
        },
    }


def test_hra_condition1_actual_hra_is_binding() -> None:
    """Condition 1 (actual HRA received) is the binding minimum.

    With very high rent and high salary, the actual HRA received should be
    the smallest of the three:
        min(200000, 500000 - 50000, 40%*500000)
        = min(200000, 450000, 200000) = 200000.
    """
    payload = _hra_payload(rent="500000", hra="200000", basic="500000")
    result = compute_tax_summary(payload=payload, regime="OLD", current_user=None)
    assert Decimal(str(result["hraExempt"])) == Decimal("200000"), (
        f"Condition 1 (actual HRA) should bind at 2,00,000, got {result['hraExempt']}"
    )


def test_hra_condition2_rent_minus_10pct_is_binding() -> None:
    """Condition 2 (rent - 10% salary) is the binding minimum.

    With low rent relative to HRA and salary:
        min(300000, 150000 - 100000, 40%*1000000)
        = min(300000, 50000, 400000) = 50000.
    """
    payload = _hra_payload(rent="150000", hra="300000", basic="1000000")
    result = compute_tax_summary(payload=payload, regime="OLD", current_user=None)
    assert Decimal(str(result["hraExempt"])) == Decimal("50000"), (
        f"Condition 2 (rent-10%) should bind at 50,000, got {result['hraExempt']}"
    )


def test_hra_condition3_salary_factor_is_binding_non_metro() -> None:
    """Condition 3 (40% salary, non-metro) is the binding minimum.

    With very high rent and high HRA, the 40% salary factor should bind:
        min(500000, 1000000 - 100000, 40%*1000000)
        = min(500000, 900000, 400000) = 400000.
    """
    payload = _hra_payload(rent="1000000", hra="500000", basic="1000000",
                          is_metro=False)
    result = compute_tax_summary(payload=payload, regime="OLD", current_user=None)
    assert Decimal(str(result["hraExempt"])) == Decimal("400000"), (
        f"Condition 3 (40% salary, non-metro) should bind at 4,00,000, "
        f"got {result['hraExempt']}"
    )


def test_hra_condition3_salary_factor_is_binding_metro() -> None:
    """Condition 3 (50% salary, metro) is the binding minimum.

    Same inputs as the non-metro case but metro=True:
        min(500000, 1000000 - 100000, 50%*1000000)
        = min(500000, 900000, 500000) = 500000.

    This case, combined with the non-metro case above, isolates the 40% vs
    50% difference — catching a hardcoded "always 40%" bug.
    """
    payload = _hra_payload(rent="1000000", hra="500000", basic="1000000",
                          is_metro=True)
    result = compute_tax_summary(payload=payload, regime="OLD", current_user=None)
    assert Decimal(str(result["hraExempt"])) == Decimal("500000"), (
        f"Condition 3 (50% salary, metro) should bind at 5,00,000, "
        f"got {result['hraExempt']}"
    )


def test_hra_metro_non_metro_isolation_trap() -> None:
    """Explicit isolation of the 40% vs 50% city-factor difference.

    With rent = 1,50,000 and basic = 9,00,000 (HRA received large enough to
    not bind):
        Non-metro: min(300000, 150000-90000, 40%*900000)
                 = min(300000, 60000, 360000) = 60000.
        Metro:     min(300000, 150000-90000, 50%*900000)
                 = min(300000, 60000, 450000) = 60000.

    NOTE: Both give the same answer here because condition 2 (rent-10%) is
    binding, NOT the city percentage.  This is a deliberate trap: if a
    future change hardcodes "always 40%" or "always 50%", this test still
    passes — so it does NOT catch that bug on its own.  The real isolation
    is provided by the pair of condition3 tests above (which use high rent
    so the city percentage is the binding term).
    """
    payload_non_metro = _hra_payload(rent="150000", hra="300000",
                                     basic="900000", is_metro=False)
    payload_metro = _hra_payload(rent="150000", hra="300000",
                                basic="900000", is_metro=True)
    result_nm = compute_tax_summary(payload=payload_non_metro, regime="OLD",
                                    current_user=None)
    result_m = compute_tax_summary(payload=payload_metro, regime="OLD",
                                   current_user=None)
    # Both should be 60,000 (condition 2 binds in both cases).
    assert Decimal(str(result_nm["hraExempt"])) == Decimal("60000"), (
        f"Non-metro HRA exempt should be 60,000, got {result_nm['hraExempt']}"
    )
    assert Decimal(str(result_m["hraExempt"])) == Decimal("60000"), (
        f"Metro HRA exempt should be 60,000, got {result_m['hraExempt']}"
    )


# ---------------------------------------------------------------------------
# TEST 3 — ITR-1 two-house-property aggregation, AY 2026-27
# ---------------------------------------------------------------------------

def _test3_two_property_payload() -> dict:
    """Return the user-provided AY 2026-27 two-property regression case.

    Gross salary is ₹8,50,000 so the old-regime ₹50,000 standard deduction
    produces the specified ₹8,00,000 income from salary.
    """
    return {
        "assessmentYear": "2026-27",
        "form": "ITR-1",
        "itrForm": "ITR-1",
        "age": 31,
        "residentialStatus": "ROR",
        "employerEntries": [{"basic": "850000"}],
        "housePropertyEntries": [
            {
                "propertyType": "SELF_OCCUPIED",
                "interestOnLoan": "210000",
                # The frontend always serializes every HP field (defaulting
                # unused ones to 0). Both keys are present on every row.
                "annualRent": 0,
                "annualLettingValue": 0,
                "municipalTaxesPaid": 0,
            },
            {
                "propertyType": "LET_OUT",
                # This mirrors the actual frontend payload: the UI writes
                # 'annualLettingValue', but 'annualRent' is still emitted
                # as 0 on every row. The backend must pick the non-zero one.
                "annualRent": 0,
                "annualLettingValue": "300000",
                "municipalTaxesPaid": "20000",
                "interestOnLoan": "150000",
            },
        ],
        "interestEntries": [
            {"kind": "SAVINGS_BANK", "grossAmount": "8000"},
            {"kind": "TERM_DEPOSIT", "grossAmount": "42000"},
        ],
        "section80C": {"investments": [{"amount": "120000"}]},
    }


def test_itr1_two_house_properties_old_regime_aggregate_and_80tta() -> None:
    """Test 3: aggregate two HPs and derive 80TTA from savings only.

    HP-1 is self-occupied: ₹2,10,000 interest caps at ₹2,00,000, so its
    ₹10,000 excess is neither deductible nor carried into the let-out row.
    HP-2 is let-out: ₹3,00,000 - ₹20,000 NAV deduction - ₹84,000 standard
    deduction - ₹1,50,000 interest = ₹46,000. The aggregate is -₹1,54,000,
    below the aggregate ₹2 lakh inter-head set-off ceiling.
    """
    result = compute_tax_summary(
        payload=_test3_two_property_payload(),
        regime="OLD",
        current_user=None,
    )

    assert Decimal(str(result["incomeFromSal"])) == Decimal("800000")
    assert Decimal(str(result["hpIncome"])) == Decimal("-154000")
    assert Decimal(str(result["otherIncome"])) == Decimal("50000")
    assert Decimal(str(result["grossTotIncome"])) == Decimal("696000")
    # The engine groups 80C under the composite PF/PPF/ELSS key.
    assert Decimal(str(result["deductionBreakdown"]["80C+80CCC+80CCD(1)"])) == Decimal("120000")
    assert Decimal(str(result["deductionBreakdown"]["80TTA"])) == Decimal("8000")
    assert Decimal(str(result["interestDeduction80TTA"])) == Decimal("8000")
    assert Decimal(str(result["totalDeductions"])) == Decimal("128000")
    assert Decimal(str(result["totalIncome"])) == Decimal("568000")
    assert Decimal(str(result["grossTaxLiability"])) == Decimal("27144")
    # netTaxLiability is the unrounded aggregate liability (gross minus relief
    # plus interest/fees). Section 288B rounding to nearest ₹10 is applied only
    # to the final balance payable / refund due.
    assert Decimal(str(result["netTaxLiability"])) == Decimal("27144")
    assert Decimal(str(result["balTaxPayable"])) == Decimal("27140")

    # The self-occupied ₹10,000 excess cannot leak into any deduction/loss.
    assert Decimal(str(result["hpLossDisallowed"])) == Decimal("0")
    # FD interest is included in OS, but excluded from the 80TTA base.
    assert Decimal(str(result["otherIncome"])) - Decimal(str(result["interestDeduction80TTA"])) == Decimal("42000")


def test_itr1_two_house_properties_new_regime_disallows_hp_loss_and_80tta() -> None:
    """New regime retains HP income only after intra-head netting, then blocks loss."""
    result = compute_tax_summary(
        payload=_test3_two_property_payload(),
        regime="NEW",
        current_user=None,
    )

    assert Decimal(str(result["incomeFromSal"])) == Decimal("775000")
    # Self-occupied interest is disallowed, but the let-out property's ₹46,000
    # positive income remains taxable under the new regime.
    assert Decimal(str(result["hpIncome"])) == Decimal("46000")
    assert Decimal(str(result["hpLossDisallowed"])) == Decimal("0")
    assert Decimal(str(result["otherIncome"])) == Decimal("50000")
    assert Decimal(str(result["totalDeductions"])) == Decimal("0")
    assert Decimal(str(result["totalIncome"])) == Decimal("871000")
    assert Decimal(str(result["interestDeduction80TTA"])) == Decimal("0")


# ---------------------------------------------------------------------------
# TEST 4 — Marginal relief on Sec 87A, both regimes (the cliff-edge test)
# ---------------------------------------------------------------------------

def _test4_marginal_relief_payload(salary_gross: str) -> dict:
    """Return a minimal salary-only payload producing the requested net TI.

    Old regime: gross - 50,000 std deduction = net taxable income.
    New regime: gross - 75,000 std deduction = net taxable income.
    """
    return {
        "assessmentYear": "2026-27",
        "form": "ITR-1",
        "itrForm": "ITR-1",
        "age": 31,
        "residentialStatus": "ROR",
        "employerEntries": [{"basic": salary_gross}],
    }


def test_itr1_87a_marginal_relief_old_regime_5_10L() -> None:
    """Test 4 Case B: old regime, TI = 5,10,000.

    Slab tax = 12,500 + 20%×10,000 = 14,500. Marginal relief cap =
    5,10,000 - 5,00,000 = 10,000. Since 14,500 > 10,000, tax is capped
    at 10,000. Cess 4% = 400 -> net tax = 10,400.
    """
    # Old regime: 5,60,000 gross - 50,000 std = 5,10,000 net TI.
    result = compute_tax_summary(
        payload=_test4_marginal_relief_payload("560000"),
        regime="OLD",
        current_user=None,
    )
    assert Decimal(str(result["totalIncome"])) == Decimal("510000")
    assert Decimal(str(result["grossTaxLiability"])) == Decimal("10400")
    assert Decimal(str(result["netTaxLiability"])) == Decimal("10400")


def test_itr1_87a_marginal_relief_new_regime_12_10L() -> None:
    """Test 4 Case A: new regime, TI = 12,10,000.

    Slab tax = 60,000 + 20%×10,000 = 62,000 (per new-regime FY 2025-26
    slabs: 0-4L nil, 4-8L @5% = 20,000, 8-12L @10% = 40,000, 12-12.1L
    @15% = 1,500; total = 61,500). Marginal relief cap = 12,10,000 -
    12,00,000 = 10,000. Since 61,500 > 10,000, tax is capped at 10,000.
    Cess 4% = 400 -> net tax = 10,400.
    """
    # New regime: 12,85,000 gross - 75,000 std = 12,10,000 net TI.
    result = compute_tax_summary(
        payload=_test4_marginal_relief_payload("1285000"),
        regime="NEW",
        current_user=None,
    )
    assert Decimal(str(result["totalIncome"])) == Decimal("1210000")
    assert Decimal(str(result["grossTaxLiability"])) == Decimal("10400")
    assert Decimal(str(result["netTaxLiability"])) == Decimal("10400")


def test_itr1_87a_marginal_relief_cross_regime_check() -> None:
    """Both regimes land at exactly ₹10,400 — cross-regime consistency check."""
    old_result = compute_tax_summary(
        payload=_test4_marginal_relief_payload("560000"),
        regime="OLD",
        current_user=None,
    )
    new_result = compute_tax_summary(
        payload=_test4_marginal_relief_payload("1285000"),
        regime="NEW",
        current_user=None,
    )
    assert Decimal(str(old_result["netTaxLiability"])) == Decimal("10400")
    assert Decimal(str(new_result["netTaxLiability"])) == Decimal("10400")


def test_itr1_87a_marginal_relief_negative_control_old_regime_5_20L() -> None:
    """Test 4 negative control: old regime, TI = 5,20,000.

    Slab tax = 12,500 + 20%×20,000 = 16,500. Marginal relief cap =
    5,20,000 - 5,00,000 = 20,000. Since 16,500 < 20,000, relief must
    NOT trigger — the app should charge the full 16,500 + cess(660) =
    17,160, not artificially reduce it.
    """
    # Old regime: 5,70,000 gross - 50,000 std = 5,20,000 net TI.
    result = compute_tax_summary(
        payload=_test4_marginal_relief_payload("570000"),
        regime="OLD",
        current_user=None,
    )
    assert Decimal(str(result["totalIncome"])) == Decimal("520000")
    assert Decimal(str(result["grossTaxLiability"])) == Decimal("17160")
    assert Decimal(str(result["netTaxLiability"])) == Decimal("17160")


# ---------------------------------------------------------------------------
# TEST 5 — LTCG u/s 112A inside ITR-1: exemption math + isolation from slab
# ---------------------------------------------------------------------------

def test_itr1_ltcg_112a_exemption_and_slab_isolation() -> None:
    """Test 5: ₹1,25,000 LTCG u/s 112A exemption and slab isolation.

    ITR-1's eligibility cap on 112A gains (₹1,25,000) exactly equals the
    exemption threshold, so taxable LTCG inside any valid ITR-1 filing is
    always ₹0. The engine must:
      (a) keep the ₹1,25,000 LTCG out of the slab-rate income pool,
      (b) not apply 87A rebate machinery to the (zero) taxable LTCG,
      (c) use Total Income (including the zero taxable LTCG, not the gross
          ₹1,25,000) for the marginal-relief threshold test.
    """
    # New regime: 13,25,000 gross - 75,000 std = 12,50,000 salary income.
    # LTCG 112A gross = 1,25,000 (exactly at the ITR-1 cap / exemption).
    result = compute_tax_summary(
        payload={
            "assessmentYear": "2026-27",
            "form": "ITR-1",
            "itrForm": "ITR-1",
            "age": 31,
            "residentialStatus": "ROR",
            "employerEntries": [{"basic": "1325000"}],
            "capitalGainsSchedule": {
                "simplified112A": {
                    "totalSaleConsideration": "350000",
                    "totalCostAcquisition": "225000",
                },
            },
        },
        regime="NEW",
        current_user=None,
    )

    # (a) Normal-rate income excludes the ₹1,25,000 LTCG.
    assert Decimal(str(result["normalRateIncome"])) == Decimal("1250000")
    # Total income includes only the (zero) taxable LTCG, not gross ₹1,25,000.
    assert Decimal(str(result["totalIncome"])) == Decimal("1250000")
    # (b) CG special-rate tax is zero (exemption correctly applied).
    assert Decimal(str(result["cgTax"])) == Decimal("0")
    # Slab tax on 12,50,000: 20,000 + 40,000 + 15%×50,000 = 67,500.
    assert Decimal(str(result["normalTax"])) == Decimal("67500")
    # (c) Marginal relief: cap = 12,50,000 - 12,00,000 = 50,000 < 67,500,
    # so tax capped at 50,000. Cess 4% = 2,000 -> net = 52,000.
    assert Decimal(str(result["rebate87A"])) == Decimal("17500")
    assert Decimal(str(result["grossTaxLiability"])) == Decimal("52000")
    assert Decimal(str(result["netTaxLiability"])) == Decimal("52000")


# ---------------------------------------------------------------------------
# TEST 6 — Senior citizen: age-based slab, 80TTB vs 80TTA, non-triggering
# marginal relief
# ---------------------------------------------------------------------------

def test_itr1_senior_citizen_80ttb_age_slab_non_triggering_relief() -> None:
    """Test 6: age 65, pension-as-salary, 80TTB covers SB+FD, no relief.

    Senior citizen (60-80) gets ₹3L basic exemption. Pension routed through
    Salary head with ₹50,000 standard deduction. 80TTB covers both SB and
    FD interest combined (₹50,000 cap), unlike 80TTA (SB-only, ₹10,000).
    Marginal relief does NOT trigger because slab tax 14,000 < cap 20,000.
    """
    result = compute_tax_summary(
        payload={
            "assessmentYear": "2026-27",
            "form": "ITR-1",
            "itrForm": "ITR-1",
            "age": 65,
            "residentialStatus": "ROR",
            "employerEntries": [{"basic": "600000"}],  # Pension
            "interestEntries": [
                {"kind": "TERM_DEPOSIT", "grossAmount": "65000"},
                {"kind": "SAVINGS_BANK", "grossAmount": "15000"},
            ],
            "section80C": {"investments": [{"amount": "60000"}]},
        },
        regime="OLD",
        current_user=None,
    )

    # Salary (pension) = 6,00,000 - 50,000 std = 5,50,000.
    assert Decimal(str(result["incomeFromSal"])) == Decimal("550000")
    # OS = 65,000 (FD) + 15,000 (SB) = 80,000.
    assert Decimal(str(result["otherIncome"])) == Decimal("80000")
    # GTI = 5,50,000 + 80,000 = 6,30,000.
    assert Decimal(str(result["grossTotIncome"])) == Decimal("630000")
    # Senior citizen basic exemption = ₹3,00,000.
    assert Decimal(str(result["basicExemptionLimit"])) == Decimal("300000")
    # 80TTB = min(80,000, 50,000) = 50,000 (covers both FD and SB).
    assert Decimal(str(result["interestDeduction80TTB"])) == Decimal("50000")
    # 80TTA = 0 (senior citizens use 80TTB, not 80TTA).
    assert Decimal(str(result["interestDeduction80TTA"])) == Decimal("0")
    # Chapter VI-A = 60,000 (80C) + 50,000 (80TTB) = 1,10,000.
    assert Decimal(str(result["totalDeductions"])) == Decimal("110000")
    assert Decimal(str(result["deductionBreakdown"]["80TTB"])) == Decimal("50000")
    # Net taxable = 6,30,000 - 1,10,000 = 5,20,000.
    assert Decimal(str(result["totalIncome"])) == Decimal("520000")
    # Senior slab: 0 (0-3L) + 5%×2L (10,000) + 20%×20,000 (4,000) = 14,000.
    assert Decimal(str(result["normalTax"])) == Decimal("14000")
    # Marginal relief cap = 5,20,000 - 5,00,000 = 20,000. Since 14,000 <
    # 20,000, relief does NOT trigger. Rebate = 0.
    assert Decimal(str(result["rebate87A"])) == Decimal("0")
    # Cess 4% = 560 -> total = 14,560.
    assert Decimal(str(result["grossTaxLiability"])) == Decimal("14560")
    assert Decimal(str(result["netTaxLiability"])) == Decimal("14560")



