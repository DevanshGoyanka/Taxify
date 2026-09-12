"""
ITR-2 post-computation validation rules (CBDT Category A, AY 2026-27).

Phase 5E of Docs/ITR2_ITR3_V2_PIPELINE_PRODUCTION_PLAN.md — rules that need a
completed ``ITR2Result`` (not just the pre-compute ``ITR2Input``), starting
with Schedule AL's total-income threshold.

Run: pytest tests/test_itr2_calc_validation.py -v
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.engine.calculators.itr2 import compute as compute_itr2, ITR2Result
from app.engine.schedules.amt import AMTResult
from app.engine.schedules.capital_gains import CGResult, CurrentYearLossCG
from app.engine.validators.itr2.calc_rules import run_calc_validation
from app.schemas.itr1 import Chapter6ADeductions, FilingAddress, SalaryIncome, TaxRegime
from app.schemas.itr2 import (
    AgeBracket, AgriculturalIncome, AgriculturalLandDetail, AMTInput, AssetLiabilityInput,
    ITR2FilingProfile, ITR2Input, OtherSourcesIncome, ReturnFileSection,
)


def failed(report, rule_id: str) -> bool:
    return any(r.rule_id == rule_id and not r.passed for r in report.results)


def emitted(report, rule_id: str) -> bool:
    """True if a rule with this ID appears at all -- used for the
    non-blocking Severity.D advisories, which are `passed=True`
    (informational), not failures."""
    return any(r.rule_id == rule_id for r in report.results)


def _high_income_input(**overrides) -> ITR2Input:
    fields = dict(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.NEW,
        salary_income=SalaryIncome(gross_salary=Decimal("20000000")),
    )
    fields.update(overrides)
    return ITR2Input(**fields)


def test_CALC_027_schedule_al_present_above_1cr_passes():
    inp = _high_income_input(asset_liability=AssetLiabilityInput(
        immovable_property=Decimal("50000000"),
    ))
    result = compute_itr2(inp)
    assert result.taxable_income > Decimal("10000000")
    assert not failed(run_calc_validation(inp, result), "ITR2-CALC-027")


def test_CALC_027_schedule_al_missing_above_1cr_fails():
    inp = _high_income_input(asset_liability=None)
    result = compute_itr2(inp)
    assert result.taxable_income > Decimal("10000000")
    assert failed(run_calc_validation(inp, result), "ITR2-CALC-027")


def test_CALC_027_schedule_al_missing_below_1cr_passes():
    inp = ITR2Input(
        age_bracket=AgeBracket.BELOW_60, tax_regime=TaxRegime.NEW,
        salary_income=SalaryIncome(gross_salary=Decimal("1500000")),
        asset_liability=None,
    )
    result = compute_itr2(inp)
    assert result.taxable_income <= Decimal("10000000")
    assert not failed(run_calc_validation(inp, result), "ITR2-CALC-027")


def _amt_triggering_input() -> ITR2Input:
    """Same proven AMT-trigger fixture as
    tests/test_itr2_itd_builder.py::_amt_triggering_input -- old regime,
    a Section 10AA add-back large enough to push AMT-computed tax past
    regular tax, confirmed empirically via `result.amt_tax > 0`."""
    return ITR2Input(
        age_bracket=AgeBracket.BELOW_60, tax_regime=TaxRegime.OLD,
        other_sources_income=OtherSourcesIncome(savings_bank_interest=Decimal("10000")),
        amt_input=AMTInput(deduction_10aa=Decimal("2500000"), amt_credits=[]),
    )


def test_CALC_028_form_29c_reminder_emitted_when_amt_exceeds_normal_tax():
    """B/D #1: AMT tax exceeding normal tax must emit a Form 29C reminder."""
    inp = _amt_triggering_input()
    result = compute_itr2(inp)
    assert result.amt_tax > 0
    assert emitted(run_calc_validation(inp, result), "ITR2-CALC-028")


def test_CALC_028_no_reminder_when_amt_does_not_apply():
    inp = ITR2Input(
        age_bracket=AgeBracket.BELOW_60, tax_regime=TaxRegime.NEW,
        salary_income=SalaryIncome(gross_salary=Decimal("1500000")),
    )
    result = compute_itr2(inp)
    assert result.amt_tax == 0
    assert not emitted(run_calc_validation(inp, result), "ITR2-CALC-028")


def test_CALC_029_surcharge_at_low_amt_income_emits_advisory():
    """B/D #2: AMT adjusted total income at or below ₹50L with a surcharge
    still present in Part B-TTI is worth a second look -- tests the
    validator's own reading of these two fields directly (constructing the
    ITR2Result/AMTResult combination by hand, since naturally triggering
    both a low-adjusted-AMT-income and a real surcharge simultaneously via
    the full calculator would require an unrelated, harder-to-follow
    special-rate-income fixture)."""
    inp = ITR2Input(age_bracket=AgeBracket.BELOW_60, tax_regime=TaxRegime.OLD)
    result = ITR2Result(
        surcharge=Decimal("50000"),
        schedules={"amt": AMTResult(adjusted_total_income=Decimal("4000000"), amt_applicable=True)},
    )
    assert emitted(run_calc_validation(inp, result), "ITR2-CALC-029")


def test_CALC_029_no_advisory_when_amt_income_above_threshold():
    inp = ITR2Input(age_bracket=AgeBracket.BELOW_60, tax_regime=TaxRegime.OLD)
    result = ITR2Result(
        surcharge=Decimal("50000"),
        schedules={"amt": AMTResult(adjusted_total_income=Decimal("6000000"), amt_applicable=True)},
    )
    assert not emitted(run_calc_validation(inp, result), "ITR2-CALC-029")


def _belated_filing_profile() -> ITR2FilingProfile:
    return ITR2FilingProfile(
        pan="AAAPA1234A", first_name="Asha", surname_or_org_name="Sharma",
        date_of_birth_or_formation=date(1990, 1, 1), father_name="Arun Sharma",
        verification_place="Delhi", return_file_section=ReturnFileSection.BELATED_139_4,
        primary_address=FilingAddress(
            residence_no="12", locality_or_area="Model Town",
            city_or_town_or_district="Delhi", state_code="07",
            pin_code="110009", mobile_no="9876543210", email="asha@example.com",
        ),
    )


def test_CALC_030_belated_return_with_current_year_cg_loss_emits_advisory():
    """B/D #26: current-year capital losses cannot be carried forward on a
    belated (139(4)) return -- a positive current-year CG loss aggregate on
    such a return is worth flagging."""
    inp = ITR2Input(
        age_bracket=AgeBracket.BELOW_60, tax_regime=TaxRegime.OLD,
        filing_profile=_belated_filing_profile(),
        filing_section=ReturnFileSection.BELATED_139_4,
    )
    result = ITR2Result(schedules={"cg": CGResult(
        current_year_losses=CurrentYearLossCG(total_cg_loss=Decimal("50000")),
    )})
    assert emitted(run_calc_validation(inp, result), "ITR2-CALC-030")


def test_CALC_030_no_advisory_for_ontime_return_with_cg_loss():
    inp = ITR2Input(age_bracket=AgeBracket.BELOW_60, tax_regime=TaxRegime.OLD)
    result = ITR2Result(schedules={"cg": CGResult(
        current_year_losses=CurrentYearLossCG(total_cg_loss=Decimal("50000")),
    )})
    assert not emitted(run_calc_validation(inp, result), "ITR2-CALC-030")


def test_CALC_030_no_advisory_for_belated_return_with_no_cg_loss():
    inp = ITR2Input(
        age_bracket=AgeBracket.BELOW_60, tax_regime=TaxRegime.OLD,
        filing_profile=_belated_filing_profile(),
        filing_section=ReturnFileSection.BELATED_139_4,
    )
    result = ITR2Result(schedules={"cg": CGResult(
        current_year_losses=CurrentYearLossCG(total_cg_loss=Decimal("0")),
    )})
    assert not emitted(run_calc_validation(inp, result), "ITR2-CALC-030")


def test_CALC_031_80ccd1_exceeds_10_pct_of_salary_fails():
    """CBDT rule #348: Section 80CCD(1) is limited to 10% of salary for a
    salaried individual (a sub-ceiling independent of the shared 80CCE pool
    cap that section_80c.py's compute_80ccd1() already applies)."""
    inp = ITR2Input(
        age_bracket=AgeBracket.BELOW_60, tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("500000")),
        deductions_chapter6a=Chapter6ADeductions(amount_80ccd1=Decimal("100000")),
    )
    result = compute_itr2(inp)
    assert failed(run_calc_validation(inp, result), "ITR2-CALC-031")


def test_CALC_031_80ccd1_within_10_pct_of_salary_passes():
    inp = ITR2Input(
        age_bracket=AgeBracket.BELOW_60, tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("500000")),
        deductions_chapter6a=Chapter6ADeductions(amount_80ccd1=Decimal("40000")),
    )
    result = compute_itr2(inp)
    assert not failed(run_calc_validation(inp, result), "ITR2-CALC-031")


def test_CALC_031_80ccd1_within_20_pct_of_gti_for_non_salaried_passes():
    inp = ITR2Input(
        age_bracket=AgeBracket.BELOW_60, tax_regime=TaxRegime.OLD,
        other_sources_income=OtherSourcesIncome(savings_bank_interest=Decimal("1000000")),
        deductions_chapter6a=Chapter6ADeductions(amount_80ccd1=Decimal("150000")),
    )
    result = compute_itr2(inp)
    assert not failed(run_calc_validation(inp, result), "ITR2-CALC-031")


def test_CALC_032_tax_payment_disclosed_with_zero_gti_fails():
    """CBDT rule #538: tax-payment details disclosed with zero gross total
    income anywhere is a genuine data-quality gap."""
    from app.schemas.itr1 import TDS2Entry
    inp = ITR2Input(
        age_bracket=AgeBracket.BELOW_60, tax_regime=TaxRegime.OLD,
        tds2_entries=[TDS2Entry(
            deductor_tan="MUMA12345B", deductor_name="Bank", tds_section="194A",
            gross_amount=Decimal("10000"), tds_deducted=Decimal("1000"),
            tds_claimed_this_year=Decimal("1000"),
        )],
    )
    result = compute_itr2(inp)
    assert failed(run_calc_validation(inp, result), "ITR2-CALC-032")


def test_CALC_032_tax_payment_disclosed_with_positive_gti_passes():
    inp = ITR2Input(
        age_bracket=AgeBracket.BELOW_60, tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        advance_tax_paid=Decimal("10000"),
    )
    result = compute_itr2(inp)
    assert not failed(run_calc_validation(inp, result), "ITR2-CALC-032")


def test_CALC_032_no_tax_payment_and_zero_gti_passes():
    inp = ITR2Input(age_bracket=AgeBracket.BELOW_60, tax_regime=TaxRegime.OLD)
    result = compute_itr2(inp)
    assert not failed(run_calc_validation(inp, result), "ITR2-CALC-032")


def test_CALC_033_high_agricultural_income_without_land_details_fails():
    """CBDT rule #445: agricultural land details are mandatory when net
    agricultural income for the year exceeds Rs.5,00,000."""
    inp = ITR2Input(
        age_bracket=AgeBracket.BELOW_60, tax_regime=TaxRegime.OLD,
        agricultural_income=AgriculturalIncome(gross_agricultural_income=Decimal("800000")),
    )
    result = compute_itr2(inp)
    assert result.net_agricultural_income > Decimal("500000")
    assert failed(run_calc_validation(inp, result), "ITR2-CALC-033")


def test_CALC_033_high_agricultural_income_with_land_details_passes():
    inp = ITR2Input(
        age_bracket=AgeBracket.BELOW_60, tax_regime=TaxRegime.OLD,
        agricultural_income=AgriculturalIncome(
            gross_agricultural_income=Decimal("800000"),
            land_details=[AgriculturalLandDetail(
                name_of_district="Nashik", pin_code="422001",
                measurement_of_land=Decimal("2.5"), owned_flag="O", irrigated_flag="IRG",
            )],
        ),
    )
    result = compute_itr2(inp)
    assert not failed(run_calc_validation(inp, result), "ITR2-CALC-033")


def test_CALC_033_low_agricultural_income_without_land_details_passes():
    inp = ITR2Input(
        age_bracket=AgeBracket.BELOW_60, tax_regime=TaxRegime.OLD,
        agricultural_income=AgriculturalIncome(gross_agricultural_income=Decimal("100000")),
    )
    result = compute_itr2(inp)
    assert not failed(run_calc_validation(inp, result), "ITR2-CALC-033")
