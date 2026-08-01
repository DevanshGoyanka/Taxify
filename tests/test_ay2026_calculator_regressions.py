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
    """A permitted 112A gain is included in GTI even when no tax is due on it."""
    result = compute_itr1(
        _itr1_input(
            regime=TaxRegime.OLD,
            ltcg_112a=Decimal("100000"),
        )
    )

    assert result.errors == []
    assert result.capital_gains_112a == Decimal("100000")
    assert result.gross_total_income == Decimal("100000")
    assert result.taxable_income == Decimal("100000")
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
                {"amount": 100000, "depositDate": "2026-03-15"},
            ],
        },
        regime="OLD",
        current_user=None,
    )

    assert result["totalTaxPaid"] == 100000.0
    assert result["adv15Mar"] == 100000.0
    assert result["taxPayable"] > 0


def test_tax_summary_rejects_claimed_tds_without_tan() -> None:
    """A claimed non-salary credit without TAN must not be silently discarded."""
    with pytest.raises(HTTPException) as exc_info:
        compute_tax_summary(
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

    assert exc_info.value.status_code == 422


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
