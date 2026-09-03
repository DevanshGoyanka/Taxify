"""
Comprehensive tests for ITR-4 input validation rules (CBDT Category A, AY 2026-27).

These test every Category A rule in app/engine/validators/itr4/input_rules.py.
Each test is named after the CBDT rule number it verifies.

Informational-only rules (Severity.D) are tested for presence rather than failure.
"""

import pytest
from decimal import Decimal
from datetime import date

from app.schemas.itr1 import (
    AgeBracket, TaxRegime, PropertyType, AssesseeType,
    SalaryIncome, HousePropertyIncome, OtherSourcesIncome,
    Chapter6ADeductions, CapitalGainsIncome, Donation80G,
    TDS1Entry, TDS2Entry, TCSEntry,
    Schedule80D, Schedule80G, Schedule80GGA, Schedule80GGC,
    HRADetails, ITR1Schedule80EEALoanEntry, LoanDetail, LoanDetails,
)
from app.schemas.itr4 import (
    ITR4Input, PresumptiveScheme,
    PresumptiveBusinessIncome44AD,
    PresumptiveProfessionalIncome44ADA,
    GoodsCarriageVehicle,
    PresumptiveGoodsCarriage44AE,
)
from app.engine.validators.itr4.input_rules import validate_itr4_input
from app.engine.validators.base import Severity


# ── Helpers ──────────────────────────────────────────────────────────────────

_Z = Decimal("0")


def failed(results, rule_id: str) -> bool:
    """Check if a specific rule_id has a non-passed result."""
    for r in results:
        if r.rule_id == rule_id and not r.passed:
            return True
    return False


def get_result(results, rule_id: str):
    """Get a specific result by rule_id."""
    for r in results:
        if r.rule_id == rule_id:
            return r
    return None


def any_present(results, rule_id: str) -> bool:
    """Check if a rule_id is present in results (info or failure)."""
    return get_result(results, rule_id) is not None


def _base_input(**overrides) -> ITR4Input:
    """Factory for a minimal valid ITR4Input with 44AD scheme."""
    from app.schemas.itr4 import ScheduleBPFinancial
    defaults = dict(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        presumptive_scheme=PresumptiveScheme.S44AD,
        business_code="B001",
        business_income_44ad=PresumptiveBusinessIncome44AD(
            total_turnover=Decimal("500000"),
            digital_turnover=Decimal("500000"),
            cash_turnover=Decimal("0"),
        ),
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=None,
        nature_of_employment="Private",
        schedule_bp_financial=ScheduleBPFinancial(),
    )
    defaults.update(overrides)
    return ITR4Input(**defaults)


def test_R270_80eea_requires_exhausted_section_24b_limit():
    """80EEA is available only after the self-occupied 24(b) cap is used."""
    deduction_row = ITR1Schedule80EEALoanEntry(
        loan_taken_from="B",
        lender_name="Example Bank",
        account_or_reference_number="HOME123",
        loan_date=date(2020, 4, 1),
        total_loan_amount=Decimal("3000000"),
        outstanding_loan_amount=Decimal("2500000"),
        interest_paid=Decimal("50000"),
    )
    body = _base_input(
        house_property_income=HousePropertyIncome(
            property_type=PropertyType.SELF_OCCUPIED,
            home_loan_interest_paid=Decimal("150000"),
        ),
        deductions_chapter6a=Chapter6ADeductions(
            amount_80eea=Decimal("50000"),
        ),
        loan_details_80eea_list=[deduction_row],
        property_stamp_duty_value_80eea=Decimal("4000000"),
        loan_details_24b_list=[LoanDetail(
            lender_name="Example Bank",
            account_or_reference_number="HOME123",
            loan_amount=Decimal("3000000"),
            outstanding_loan_amount=Decimal("2500000"),
            sanction_date=date(2020, 4, 1),
            interest_paid_self_occupied=Decimal("150000"),
        )],
    )
    assert failed(validate_itr4_input(body), "ITR4-R270")

    exhausted = body.model_copy(update={
        "house_property_income": HousePropertyIncome(
            property_type=PropertyType.SELF_OCCUPIED,
            home_loan_interest_paid=Decimal("200000"),
        ),
        "loan_details_24b_list": [LoanDetail(
            lender_name="Example Bank",
            account_or_reference_number="HOME123",
            loan_amount=Decimal("3000000"),
            outstanding_loan_amount=Decimal("2500000"),
            sanction_date=date(2020, 4, 1),
            interest_paid_self_occupied=Decimal("200000"),
        )],
    })
    assert not failed(validate_itr4_input(exhausted), "ITR4-R270")


# ═══════════════════════════════════════════════════════════════════════════════
# ITR-4 Eligibility
# ═══════════════════════════════════════════════════════════════════════════════

def test_R140_no_presumptive_scheme():
    """Rule 140: No presumptive scheme selected."""
    inp = ITR4Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        presumptive_scheme=PresumptiveScheme.NONE,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R140")


def test_R265_ltcg_112a_exceeds_125k():
    """Rule 265: LTCG 112A exceeds Rs 1,25,000 ITR-4 limit."""
    inp = _base_input(
        capital_gains=CapitalGainsIncome(ltcg_112a=Decimal("150000")),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R265")


def test_R265_ltcg_112a_within_limit():
    """LTCG 112A within 1.25L passes."""
    inp = _base_input(
        capital_gains=CapitalGainsIncome(ltcg_112a=Decimal("100000")),
    )
    results = validate_itr4_input(inp)
    assert not failed(results, "ITR4-R265")


def test_R266_ltcg_112a_info():
    """Rule 266: LTCG 112A informational check."""
    inp = _base_input(
        capital_gains=CapitalGainsIncome(ltcg_112a=Decimal("50000")),
    )
    results = validate_itr4_input(inp)
    assert any_present(results, "ITR4-R266")


# ═══════════════════════════════════════════════════════════════════════════════
# 44AD — Presumptive Business Income
# ═══════════════════════════════════════════════════════════════════════════════

def test_R001a_44ad_no_schedule_bp():
    """Rule 1a: 44AD scheme selected but business_income_44ad is None."""
    inp = ITR4Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        presumptive_scheme=PresumptiveScheme.S44AD,
        business_income_44ad=None,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R001a")


def test_R008_44ad_income_exceeds_turnover():
    """Rule 8: 44AD income declared exceeds total turnover."""
    inp = _base_input(
        business_income_44ad=PresumptiveBusinessIncome44AD(
            total_turnover=Decimal("500000"),
            income_declared=Decimal("600000"),
        ),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R008")


def test_R008_44ad_income_within_turnover_passes():
    """44AD income declared within turnover passes."""
    inp = _base_input(
        business_income_44ad=PresumptiveBusinessIncome44AD(
            total_turnover=Decimal("500000"),
            income_declared=Decimal("400000"),
        ),
    )
    results = validate_itr4_input(inp)
    assert not failed(results, "ITR4-R008")


def test_R009_44ad_turnover_exceeds_3cr():
    """Rule 9: 44AD turnover exceeds Rs 3 crore — blocked by Pydantic validator."""
    with pytest.raises(ValueError):
        PresumptiveBusinessIncome44AD(total_turnover=Decimal("31000000"))


def test_R237_44ad_cash_gt_5pct_above_2cr():
    """Rule 237: 44AD > 2cr with cash > 5% triggers audit."""
    inp = _base_input(
        business_income_44ad=PresumptiveBusinessIncome44AD(
            total_turnover=Decimal("25000000"),
            digital_turnover=Decimal("23000000"),
            cash_turnover=Decimal("2000000"),  # 8% cash
        ),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R237")


def test_R237_44ad_cash_within_5pct_passes():
    """44AD > 2cr with cash <= 5% passes."""
    inp = _base_input(
        business_income_44ad=PresumptiveBusinessIncome44AD(
            total_turnover=Decimal("25000000"),
            digital_turnover=Decimal("24000000"),
            cash_turnover=Decimal("1000000"),  # 4% cash
        ),
    )
    results = validate_itr4_input(inp)
    assert not failed(results, "ITR4-R237")


def test_R239_44ad_turnover_split_mismatch():
    """Rule 239: 44AD digital + cash != total."""
    inp = _base_input(
        business_income_44ad=PresumptiveBusinessIncome44AD(
            total_turnover=Decimal("500000"),
            digital_turnover=Decimal("300000"),
            cash_turnover=Decimal("100000"),  # 300+100=400 != 500
        ),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R239")


def test_R239_44ad_turnover_split_matches():
    """44AD digital + cash == total passes."""
    inp = _base_input(
        business_income_44ad=PresumptiveBusinessIncome44AD(
            total_turnover=Decimal("500000"),
            digital_turnover=Decimal("300000"),
            cash_turnover=Decimal("200000"),
        ),
    )
    results = validate_itr4_input(inp)
    assert not failed(results, "ITR4-R239")


# ═══════════════════════════════════════════════════════════════════════════════
# 44ADA — Presumptive Professional Income
# ═══════════════════════════════════════════════════════════════════════════════

def test_R001b_44ada_no_schedule_bp():
    """Rule 1b: 44ADA selected but professional_income_44ada is None."""
    inp = ITR4Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        presumptive_scheme=PresumptiveScheme.S44ADA,
        professional_income_44ada=None,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R001b")


def test_R013_44ada_income_exceeds_receipts():
    """Rule 13: 44ADA income declared exceeds gross receipts."""
    inp = ITR4Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        presumptive_scheme=PresumptiveScheme.S44ADA,
        professional_income_44ada=PresumptiveProfessionalIncome44ADA(
            gross_receipts=Decimal("1000000"),
            income_declared=Decimal("1200000"),
        ),
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R013")


def test_R238_44ada_cash_gt_5pct_above_50l():
    """Rule 238: 44ADA > 50L with cash > 5% triggers audit."""
    inp = ITR4Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        presumptive_scheme=PresumptiveScheme.S44ADA,
        professional_income_44ada=PresumptiveProfessionalIncome44ADA(
            gross_receipts=Decimal("6000000"),
            digital_receipts=Decimal("5500000"),
            cash_receipts=Decimal("500000"),  # >5% of 60L
        ),
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R238")


def test_R240_44ada_receipts_split_mismatch():
    """Rule 240: 44ADA digital + cash != total."""
    inp = ITR4Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        presumptive_scheme=PresumptiveScheme.S44ADA,
        professional_income_44ada=PresumptiveProfessionalIncome44ADA(
            gross_receipts=Decimal("1000000"),
            digital_receipts=Decimal("700000"),
            cash_receipts=Decimal("200000"),  # 700+200=900 != 1000
        ),
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R240")


# ═══════════════════════════════════════════════════════════════════════════════
# 44AE — Presumptive Goods Carriage
# ═══════════════════════════════════════════════════════════════════════════════

def test_R001c_44ae_no_schedule_bp():
    """Rule 1c: 44AE selected but goods_carriage_44ae is None."""
    inp = ITR4Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        presumptive_scheme=PresumptiveScheme.S44AE,
        goods_carriage_44ae=None,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R001c")


def test_R135_44ae_no_vehicles():
    """Rule 135: 44AE vehicles empty — unreachable via normal flow due to Pydantic min_length=1.
    R001c fires when goods_carriage_44ae is None (the actual path)."""
    inp = ITR4Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        presumptive_scheme=PresumptiveScheme.S44AE,
        goods_carriage_44ae=None,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
    )
    results = validate_itr4_input(inp)
    # R001c: scheme active but no data; R135: vehicles list empty (caught by Pydantic first)
    assert failed(results, "ITR4-R001c")


def test_R141a_vehicle_months_exceeds_12():
    """Rule 141a: months > 12 caught by Pydantic le=12 validator before our rule runs."""
    with pytest.raises(ValueError):
        GoodsCarriageVehicle(
            is_heavy_goods_vehicle=False,
            months_owned=13,
        )


def test_R141a_vehicle_months_within_limit():
    """44AE per-vehicle months within 12 passes."""
    inp = ITR4Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        presumptive_scheme=PresumptiveScheme.S44AE,
        goods_carriage_44ae=PresumptiveGoodsCarriage44AE(
            vehicles=[
                GoodsCarriageVehicle(
                    is_heavy_goods_vehicle=False,
                    months_owned=12,
                ),
            ],
        ),
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
    )
    results = validate_itr4_input(inp)
    assert not failed(results, "ITR4-R141a")


def test_R141b_total_months_exceeds_120():
    """Rule 141b: Total months across vehicles exceeds 120."""
    vehicles = []
    for i in range(11):
        vehicles.append(
            GoodsCarriageVehicle(
                is_heavy_goods_vehicle=False,
                months_owned=11,
            )
        )
    # 11 vehicles × 11 months = 121 > 120
    inp = ITR4Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        presumptive_scheme=PresumptiveScheme.S44AE,
        goods_carriage_44ae=PresumptiveGoodsCarriage44AE(vehicles=vehicles),
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R141b")


def test_R144_vehicle_declared_below_statutory():
    """Rule 144: Per-vehicle declared income below statutory minimum."""
    inp = ITR4Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        presumptive_scheme=PresumptiveScheme.S44AE,
        goods_carriage_44ae=PresumptiveGoodsCarriage44AE(
            vehicles=[
                GoodsCarriageVehicle(
                    is_heavy_goods_vehicle=False,
                    months_owned=12,
                    income_declared=Decimal("50000"),  # below 7500*12=90000
                ),
            ],
        ),
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R144")


def test_R144_vehicle_heavy_below_statutory():
    """Rule 144: Heavy vehicle declared below statutory (₹1,000/ton/month)."""
    inp = ITR4Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        presumptive_scheme=PresumptiveScheme.S44AE,
        goods_carriage_44ae=PresumptiveGoodsCarriage44AE(
            vehicles=[
                GoodsCarriageVehicle(
                    is_heavy_goods_vehicle=True,
                    gross_vehicle_weight_tons=Decimal("20"),
                    months_owned=10,
                    income_declared=Decimal("100000"),  # below 1000*20*10=200000
                ),
            ],
        ),
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R144")


# ═══════════════════════════════════════════════════════════════════════════════
# Old Regime — 80C Combined Limit
# ═══════════════════════════════════════════════════════════════════════════════

def test_R021_80c_combined_exceeds_150k():
    """Rule 21: 80C+80CCC+80CCD(1) > Rs 1,50,000 in old regime."""
    inp = _base_input(
        deductions_chapter6a=Chapter6ADeductions(
            amount_80c=Decimal("100000"),
            amount_80ccc=Decimal("30000"),
            amount_80ccd1=Decimal("40000"),  # total=170000
        ),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R021")


def test_R021_80c_combined_within_limit():
    """80C combined within 1.5L passes."""
    inp = _base_input(
        deductions_chapter6a=Chapter6ADeductions(
            amount_80c=Decimal("100000"),
            amount_80ccc=Decimal("20000"),
            amount_80ccd1=Decimal("30000"),  # total=150000
        ),
    )
    results = validate_itr4_input(inp)
    assert not failed(results, "ITR4-R021")


# ═══════════════════════════════════════════════════════════════════════════════
# Old Regime — 80CCD
# ═══════════════════════════════════════════════════════════════════════════════

def test_R145_80ccd1b_exceeds_50k():
    """Rule 145: 80CCD(1B) > Rs 50,000."""
    inp = _base_input(
        deductions_chapter6a=Chapter6ADeductions(amount_80ccd1b=Decimal("60000")),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R145")


def test_R022a_80ccd1_pensioner_exceeds_20pct():
    """Rule 22a: 80CCD(1) pensioner > 20% salary.

    nature_of_employment carries the raw official code (PE/PESG/PEPS/PEO),
    never a human-readable label like "Pensioner" -- using the label here
    previously made this test pass only by accident, matching the same
    keyword-vs-raw-code bug already found and fixed in ITR-1's validators
    (§14.5) and now also in ITR-4's (Docs/ITR4_FRONTEND_AND_SERIALIZATION_
    AUDIT_AY2026_27.md)."""
    inp = _base_input(
        salary_income=SalaryIncome(gross_salary=Decimal("500000")),
        nature_of_employment="PE",
        deductions_chapter6a=Chapter6ADeductions(amount_80ccd1=Decimal("120000")),  # 20% of 5L=100000
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R022a")


# ═══════════════════════════════════════════════════════════════════════════════
# Old Regime — 80D Health Insurance
# ═══════════════════════════════════════════════════════════════════════════════

def test_R168_80d_self_non_senior_exceeds_25k():
    """Rule 168: 80D self/family non-senior > Rs 25,000."""
    inp = _base_input(
        age_bracket=AgeBracket.BELOW_60,
        deductions_chapter6a=Chapter6ADeductions(amount_80d_self_family=Decimal("30000")),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R168")


def test_R171_80d_self_senior_exceeds_50k():
    """Rule 171: 80D self/family senior > Rs 50,000."""
    inp = _base_input(
        age_bracket=AgeBracket.SIXTY_TO_80,
        deductions_chapter6a=Chapter6ADeductions(amount_80d_self_family=Decimal("55000")),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R171")


def test_R173_80d_parents_non_senior_exceeds_25k():
    """Rule 173: 80D parents non-senior > Rs 25,000."""
    inp = _base_input(
        deductions_chapter6a=Chapter6ADeductions(amount_80d_parents=Decimal("30000")),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R173")


def test_R175_80d_parents_senior_exceeds_50k():
    """Rule 175: 80D parents senior > Rs 50,000."""
    inp = _base_input(
        deductions_chapter6a=Chapter6ADeductions(amount_80d_parents=Decimal("55000")),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R175")


def test_R177_80d_combined_exceeds_100k():
    """Rule 177: 80D total (self+parents) > Rs 1,00,000."""
    inp = _base_input(
        deductions_chapter6a=Chapter6ADeductions(
            amount_80d_self_family=Decimal("55000"),
            amount_80d_parents=Decimal("55000"),  # total=110000
        ),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R177")


def test_R179_80d_claimed_no_schedule():
    """Rule 179: 80D claimed but no schedule_80d provided."""
    inp = _base_input(
        deductions_chapter6a=Chapter6ADeductions(
            amount_80d_self_family=Decimal("25000"),
        ),
        schedule_80d=None,
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R179")


def test_R179_80d_with_schedule_passes():
    """80D with schedule_80d passes."""
    inp = _base_input(
        deductions_chapter6a=Chapter6ADeductions(
            amount_80d_self_family=Decimal("25000"),
        ),
        schedule_80d=Schedule80D(
            premium_1a_non_senior=Decimal("25000"),
        ),
    )
    results = validate_itr4_input(inp)
    assert not failed(results, "ITR4-R179")


def test_R170a_preventive_checkup_self_exceeds_5k():
    """Rule 170a: Preventive health checkup self/family > Rs 5,000."""
    inp = _base_input(
        deductions_chapter6a=Chapter6ADeductions(
            amount_80d_self_family=Decimal("30000"),
        ),
        schedule_80d=Schedule80D(
            premium_1a_non_senior=Decimal("20000"),
            preventive_checkup_self=Decimal("6000"),  # > 5000
        ),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R170a")


def test_R170b_preventive_checkup_parents_exceeds_5k():
    """Rule 170b: Preventive health checkup parents > Rs 5,000."""
    inp = _base_input(
        deductions_chapter6a=Chapter6ADeductions(
            amount_80d_parents=Decimal("10000"),
        ),
        schedule_80d=Schedule80D(
            premium_2a_parents_non_senior=Decimal("5000"),
            preventive_checkup_parents=Decimal("6000"),
        ),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R170b")


# ═══════════════════════════════════════════════════════════════════════════════
# Old Regime — 80DD / 80U / 80DDB
# ═══════════════════════════════════════════════════════════════════════════════

def test_R147_80dd_exceeds_125k():
    """Rule 147: 80DD > Rs 1,25,000."""
    inp = _base_input(
        deductions_chapter6a=Chapter6ADeductions(amount_80dd=Decimal("150000")),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R147")


def test_R146_80dd_not_valid_amount():
    """Rule 146: 80DD not in (75000, 125000)."""
    inp = _base_input(
        form_10ia_filed=True,
        deductions_chapter6a=Chapter6ADeductions(amount_80dd=Decimal("100000")),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R446")


def test_R146_80dd_valid_amount_passes():
    """80DD = 75000 passes."""
    inp = _base_input(
        form_10ia_filed=True,
        deductions_chapter6a=Chapter6ADeductions(amount_80dd=Decimal("75000")),
    )
    results = validate_itr4_input(inp)
    assert not failed(results, "ITR4-R146")


def test_R287b_80dd_no_form_10ia():
    """Rule 287b: 80DD claimed but Form 10-IA not filed for 80DD."""
    from app.schemas.itr4 import Schedule80DD
    inp = _base_input(
        schedule_80dd=Schedule80DD(deduction_amount=Decimal("75000"), disability_type="Dependent with disability"),
        form_10ia_filed_80dd=False,
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R252")


def test_R148_80ddb_non_senior_exceeds_40k():
    """Rule 148: 80DDB non-senior > Rs 40,000."""
    inp = _base_input(
        age_bracket=AgeBracket.BELOW_60,
        deductions_chapter6a=Chapter6ADeductions(amount_80ddb=Decimal("50000")),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R148")


def test_R149_80ddb_senior_exceeds_100k():
    """Rule 149: 80DDB senior > Rs 1,00,000."""
    inp = _base_input(
        age_bracket=AgeBracket.SIXTY_TO_80,
        deductions_chapter6a=Chapter6ADeductions(amount_80ddb=Decimal("120000")),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R149")


def test_R182_80u_exceeds_125k():
    """Rule 182: 80U > Rs 1,25,000."""
    inp = _base_input(
        deductions_chapter6a=Chapter6ADeductions(amount_80u=Decimal("150000")),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R182")


def test_R182b_80u_not_valid_amount():
    """Rule 182b: 80U not in (75000, 125000)."""
    inp = _base_input(
        form_10ia_filed=True,
        deductions_chapter6a=Chapter6ADeductions(amount_80u=Decimal("100000")),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R182b")


def test_R287_80u_no_form_10ia():
    """Rule 287: 80U claimed but Form 10-IA not filed for 80U."""
    from app.schemas.itr4 import Schedule80U
    inp = _base_input(
        schedule_80u=Schedule80U(deduction_amount=Decimal("75000"), disability_type="Self with disability"),
        form_10ia_filed_80u=False,
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R253")


# ═══════════════════════════════════════════════════════════════════════════════
# Old Regime — 80EE / 80EEA / 80EEB
# ═══════════════════════════════════════════════════════════════════════════════

def test_R150_80ee_exceeds_50k():
    """Rule 150: 80EE > Rs 50,000."""
    inp = _base_input(
        deductions_chapter6a=Chapter6ADeductions(amount_80ee=Decimal("55000")),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R150")


def test_R156_80eea_exceeds_150k():
    """Rule 156: 80EEA > Rs 1,50,000."""
    inp = _base_input(
        deductions_chapter6a=Chapter6ADeductions(amount_80eea=Decimal("160000")),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R156")


def test_R157_80ee_and_80eea_mutual():
    """Rule 157: 80EE and 80EEA both claimed."""
    inp = _base_input(
        deductions_chapter6a=Chapter6ADeductions(
            amount_80ee=Decimal("30000"),
            amount_80eea=Decimal("50000"),
        ),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R157")


def test_R158_80eeb_exceeds_150k():
    """Rule 158: 80EEB > Rs 1,50,000."""
    inp = _base_input(
        deductions_chapter6a=Chapter6ADeductions(amount_80eeb=Decimal("160000")),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R158")


# ═══════════════════════════════════════════════════════════════════════════════
# Old Regime — 80TTA / 80TTB
# ═══════════════════════════════════════════════════════════════════════════════

def test_R152_80tta_exceeds_10k():
    """Rule 152: 80TTA > Rs 10,000."""
    inp = _base_input(
        deductions_chapter6a=Chapter6ADeductions(amount_80tta=Decimal("12000")),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R152")


def test_R038_80tta_exceeds_savings_interest():
    """Rule 38: 80TTA > savings bank interest."""
    inp = _base_input(
        other_sources_income=OtherSourcesIncome(savings_bank_interest=Decimal("5000")),
        deductions_chapter6a=Chapter6ADeductions(amount_80tta=Decimal("10000")),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R038")


def test_R039_80tta_senior_cannot_claim():
    """Rule 39: Senior citizen cannot claim 80TTA."""
    inp = _base_input(
        age_bracket=AgeBracket.SIXTY_TO_80,
        deductions_chapter6a=Chapter6ADeductions(amount_80tta=Decimal("10000")),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R039")


def test_R153_80ttb_exceeds_50k():
    """Rule 153: 80TTB > Rs 50,000."""
    inp = _base_input(
        age_bracket=AgeBracket.SIXTY_TO_80,
        deductions_chapter6a=Chapter6ADeductions(amount_80ttb=Decimal("55000")),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R153")


def test_R040_80ttb_non_senior_cannot_claim():
    """Rule 40: Non-senior cannot claim 80TTB."""
    inp = _base_input(
        age_bracket=AgeBracket.BELOW_60,
        deductions_chapter6a=Chapter6ADeductions(amount_80ttb=Decimal("50000")),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R040")


def test_R041_80ttb_exceeds_os_interest():
    """Rule 41: 80TTB > interest from other sources."""
    inp = _base_input(
        age_bracket=AgeBracket.SIXTY_TO_80,
        other_sources_income=OtherSourcesIncome(savings_bank_interest=Decimal("30000")),
        deductions_chapter6a=Chapter6ADeductions(amount_80ttb=Decimal("50000")),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R041")


# ═══════════════════════════════════════════════════════════════════════════════
# 80G / 80GG
# ═══════════════════════════════════════════════════════════════════════════════

def test_R034_80g_no_donations():
    """Rule 34: 80G claimed but no donation entries."""
    inp = _base_input(
        deductions_chapter6a=Chapter6ADeductions(amount_80g=Decimal("10000")),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R034")


def test_R034_80g_with_donations_passes():
    """80G with donation entries passes R034."""
    inp = _base_input(
        deductions_chapter6a=Chapter6ADeductions(
            amount_80g=Decimal("10000"),
            donations_80g=[
                Donation80G(non_cash_amount=Decimal("10000"), qualifying_percentage="100%"),
            ],
        ),
    )
    results = validate_itr4_input(inp)
    assert not failed(results, "ITR4-R034")


def test_R151_hra_and_80gg_mutual():
    """Rule 151: HRA + 80GG: 80GG > ₹55,000 blocked when HRA present."""
    inp = _base_input(
        salary_income=SalaryIncome(gross_salary=Decimal("600000"), hra_exempt_amount=Decimal("50000")),
        deductions_chapter6a=Chapter6ADeductions(amount_80gg=Decimal("60000")),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R151")


# ═══════════════════════════════════════════════════════════════════════════════
# New Regime — Deduction Restrictions
# ═══════════════════════════════════════════════════════════════════════════════

def test_R183_new_regime_all_blocked():
    """Rule 183: New regime blocks most deductions (bulk test)."""
    inp = _base_input(
        tax_regime=TaxRegime.NEW,
        deductions_chapter6a=Chapter6ADeductions(
            amount_80c=Decimal("50000"),
            amount_80d_self_family=Decimal("25000"),
            amount_80tta=Decimal("10000"),
        ),
    )
    results = validate_itr4_input(inp)
    # Should fail for multiple rules
    assert failed(results, "ITR4-R183") or failed(results, "ITR4-R189")
    # All new regime deduction checks should trigger under R183 (unified loop)
    assert failed(results, "ITR4-R183")


def test_R189_new_regime_80c_not_allowed():
    """Rule 189: New regime 80C/80CCC/80CCD(1) must be 0 — covered by unified R183."""
    inp = _base_input(
        tax_regime=TaxRegime.NEW,
        deductions_chapter6a=Chapter6ADeductions(amount_80c=Decimal("50000")),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R183")


def test_R190_new_regime_80g_not_allowed():
    """Rule 190: New regime 80G must be 0 — covered by unified R183."""
    inp = _base_input(
        tax_regime=TaxRegime.NEW,
        deductions_chapter6a=Chapter6ADeductions(amount_80g=Decimal("10000")),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R183")


def test_R191_new_regime_80gg_not_allowed():
    """Rule 191: New regime 80GG must be 0 — covered by unified R183."""
    inp = _base_input(
        tax_regime=TaxRegime.NEW,
        deductions_chapter6a=Chapter6ADeductions(amount_80gg=Decimal("30000")),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R183")


def test_R192_new_regime_80tta_not_allowed():
    """Rule 192: New regime 80TTA must be 0 — covered by unified R183."""
    inp = _base_input(
        tax_regime=TaxRegime.NEW,
        deductions_chapter6a=Chapter6ADeductions(amount_80tta=Decimal("10000")),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R183")


def test_R193_new_regime_80ttb_not_allowed():
    """Rule 193: New regime 80TTB must be 0 — covered by unified R183."""
    inp = _base_input(
        tax_regime=TaxRegime.NEW,
        age_bracket=AgeBracket.SIXTY_TO_80,
        deductions_chapter6a=Chapter6ADeductions(amount_80ttb=Decimal("50000")),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R183")


def test_R194_new_regime_80u_not_allowed():
    """Rule 194: New regime 80U must be 0 — covered by unified R183."""
    inp = _base_input(
        tax_regime=TaxRegime.NEW,
        deductions_chapter6a=Chapter6ADeductions(amount_80u=Decimal("75000")),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R183")


def test_R203_new_regime_80ccd1b_not_allowed():
    """Rule 203: New regime 80CCD(1B) must be 0 — covered by unified R183."""
    inp = _base_input(
        tax_regime=TaxRegime.NEW,
        deductions_chapter6a=Chapter6ADeductions(amount_80ccd1b=Decimal("50000")),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R183")


def test_R204_new_regime_80dd_not_allowed():
    """Rule 204: New regime 80DD must be 0 — covered by unified R183."""
    inp = _base_input(
        tax_regime=TaxRegime.NEW,
        deductions_chapter6a=Chapter6ADeductions(amount_80dd=Decimal("75000")),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R183")


def test_R205_new_regime_80ddb_not_allowed():
    """Rule 205: New regime 80DDB must be 0 — covered by unified R183."""
    inp = _base_input(
        tax_regime=TaxRegime.NEW,
        deductions_chapter6a=Chapter6ADeductions(amount_80ddb=Decimal("40000")),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R183")


def test_R206_new_regime_80ee_not_allowed():
    """Rule 206: New regime 80EE must be 0 — covered by unified R183."""
    inp = _base_input(
        tax_regime=TaxRegime.NEW,
        deductions_chapter6a=Chapter6ADeductions(amount_80ee=Decimal("30000")),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R183")


def test_R208_new_regime_80ccd1_not_allowed():
    """Rule 208: New regime 80CCD(1) must be 0 — covered by unified R183."""
    inp = _base_input(
        tax_regime=TaxRegime.NEW,
        deductions_chapter6a=Chapter6ADeductions(amount_80ccd1=Decimal("50000")),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R183")


def test_R209_new_regime_80eea_not_allowed():
    """Rule 209: New regime 80EEA must be 0 — covered by unified R183."""
    inp = _base_input(
        tax_regime=TaxRegime.NEW,
        deductions_chapter6a=Chapter6ADeductions(amount_80eea=Decimal("50000")),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R183")


def test_R210_new_regime_80eeb_not_allowed():
    """Rule 210: New regime 80EEB must be 0 — covered by unified R183."""
    inp = _base_input(
        tax_regime=TaxRegime.NEW,
        deductions_chapter6a=Chapter6ADeductions(amount_80eeb=Decimal("50000")),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R183")


def test_R211_new_regime_80d_not_allowed():
    """Rule 211: New regime 80D must be 0 — covered by unified R183."""
    inp = _base_input(
        tax_regime=TaxRegime.NEW,
        deductions_chapter6a=Chapter6ADeductions(
            amount_80d_self_family=Decimal("25000"),
            amount_80d_parents=Decimal("25000"),
        ),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R183")


def test_R195_new_regime_professional_tax():
    """Rule 195: New regime professional tax must be 0."""
    inp = _base_input(
        tax_regime=TaxRegime.NEW,
        salary_income=SalaryIncome(gross_salary=Decimal("600000"), professional_tax_paid=Decimal("2500")),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R195")


def test_R198_new_regime_lta():
    """Rule 198: New regime LTA must be 0."""
    inp = _base_input(
        tax_regime=TaxRegime.NEW,
        salary_income=SalaryIncome(gross_salary=Decimal("600000"), lta_exempt_amount=Decimal("30000")),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R198")


def test_R199_new_regime_hra():
    """Rule 199: New regime HRA must be 0."""
    inp = _base_input(
        tax_regime=TaxRegime.NEW,
        salary_income=SalaryIncome(gross_salary=Decimal("600000"), hra_exempt_amount=Decimal("50000")),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R199")


def test_R207_new_regime_self_occupied_interest():
    """Rule 207/302: New regime self-occupied HP interest must be 0."""
    inp = _base_input(
        tax_regime=TaxRegime.NEW,
        house_property_income=HousePropertyIncome(
            property_type=PropertyType.SELF_OCCUPIED,
            home_loan_interest_paid=Decimal("150000"),
        ),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R207")  # R207 and R302 now unified


# ═══════════════════════════════════════════════════════════════════════════════
# House Property Validations
# ═══════════════════════════════════════════════════════════════════════════════

def test_R055_nav_negative_let_out():
    """Rule 55: NAV should be positive for let-out property."""
    inp = _base_input(
        house_property_income=HousePropertyIncome(
            property_type=PropertyType.LET_OUT,
            annual_rent_received=Decimal("50000"),
            municipal_taxes_paid=Decimal("60000"),  # NAV = -10000
        ),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R055")


def test_R058_municipal_tax_no_rent():
    """Rule 58: Municipal tax without rent."""
    inp = _base_input(
        house_property_income=HousePropertyIncome(
            property_type=PropertyType.SELF_OCCUPIED,
            annual_rent_received=Decimal("0"),
            municipal_taxes_paid=Decimal("10000"),
        ),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R058")


def test_R059_let_out_no_rent():
    """Rule 59: Let-out property without rent."""
    inp = _base_input(
        house_property_income=HousePropertyIncome(
            property_type=PropertyType.LET_OUT,
            annual_rent_received=Decimal("0"),
        ),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R059")


def test_R061_municipal_tax_self_occupied():
    """Rule 61: Municipal tax on self-occupied property."""
    inp = _base_input(
        house_property_income=HousePropertyIncome(
            property_type=PropertyType.SELF_OCCUPIED,
            annual_rent_received=Decimal("0"),
            municipal_taxes_paid=Decimal("5000"),
        ),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R061")


def test_R154_self_occupied_interest_exceeds_2l():
    """Rule 154: Self-occupied interest > Rs 2,00,000 (old regime)."""
    inp = _base_input(
        house_property_income=HousePropertyIncome(
            property_type=PropertyType.SELF_OCCUPIED,
            home_loan_interest_paid=Decimal("250000"),
        ),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R154")


def test_R154_self_occupied_within_2l_passes():
    """Self-occupied interest within 2L (old regime) passes."""
    inp = _base_input(
        house_property_income=HousePropertyIncome(
            property_type=PropertyType.SELF_OCCUPIED,
            home_loan_interest_paid=Decimal("150000"),
        ),
    )
    results = validate_itr4_input(inp)
    assert not failed(results, "ITR4-R154")


# ═══════════════════════════════════════════════════════════════════════════════
# Salary Validations
# ═══════════════════════════════════════════════════════════════════════════════

def test_R068_entertainment_allowance_non_govt():
    """Rule 68: Entertainment allowance for non-govt employee."""
    inp = _base_input(
        salary_income=SalaryIncome(
            gross_salary=Decimal("600000"),
            is_government_employee=False,
            entertainment_allowance=Decimal("5000"),
        ),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R068")


def test_R067_entertainment_allowance_exceeds_5k():
    """Rule 67: Entertainment allowance > Rs 5,000 for govt employee."""
    inp = _base_input(
        salary_income=SalaryIncome(
            gross_salary=Decimal("600000"),
            is_government_employee=True,
            entertainment_allowance=Decimal("6000"),
        ),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R067")


def test_R143_standard_deduction_old_exceeds_50k():
    """Rule 143: Standard deduction old regime > Rs 50,000."""
    inp = _base_input(
        salary_income=SalaryIncome(gross_salary=Decimal("600000"), standard_deduction_claimed=Decimal("55000")),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R143")


def test_R262_standard_deduction_new_exceeds_75k():
    """Rule 262: Standard deduction new regime > Rs 75,000."""
    inp = _base_input(
        tax_regime=TaxRegime.NEW,
        salary_income=SalaryIncome(gross_salary=Decimal("600000"), standard_deduction_claimed=Decimal("80000")),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R262")


def test_R255_nature_of_employment_mandatory():
    """Rule 255: Nature of employment mandatory with salary."""
    inp = _base_input(
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        nature_of_employment=None,
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R255")


def test_R255_nature_of_employment_provided_passes():
    """Nature of employment provided passes."""
    inp = _base_input(
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        nature_of_employment="Private",
    )
    results = validate_itr4_input(inp)
    assert not failed(results, "ITR4-R255")


def test_R314_hra_exceeds_actual_received():
    """Rule 314: HRA exemption exceeds actual HRA received."""
    inp = _base_input(
        salary_income=SalaryIncome(gross_salary=Decimal("600000"), hra_exempt_amount=Decimal("80000")),
        hra_details=HRADetails(
            actual_hra_received=Decimal("60000"),
            rent_paid=Decimal("120000"),
            salary_for_hra=Decimal("500000"),
            is_metro_city=True,
        ),
        nature_of_employment="Private",
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R314")


def test_R314_hra_exceeds_permissible_limit():
    """Rule 314: HRA exemption exceeds permissible limit."""
    inp = _base_input(
        salary_income=SalaryIncome(gross_salary=Decimal("600000"), hra_exempt_amount=Decimal("50000")),
        hra_details=HRADetails(
            actual_hra_received=Decimal("80000"),
            rent_paid=Decimal("60000"),
            salary_for_hra=Decimal("500000"),
            is_metro_city=True,  # 50% of 5L = 250000; rent-10% = 60000-50000=10000; min=10000
        ),
        nature_of_employment="Private",
    )
    results = validate_itr4_input(inp)
    # HRA limit = min(80000, 10000, 250000) = 10000, claimed 50000 > 10000
    assert failed(results, "ITR4-R314")


def test_R314_uses_50_percent_for_metro_and_40_percent_for_non_metro():
    common = dict(
        salary_income=SalaryIncome(
            gross_salary=Decimal("600000"),
            hra_exempt_amount=Decimal("45000"),
        ),
        nature_of_employment="Private",
    )
    metro = _base_input(
        **common,
        hra_details=HRADetails(
            actual_hra_received=Decimal("100000"),
            rent_paid=Decimal("200000"),
            salary_for_hra=Decimal("100000"),
            is_metro_city=True,
        ),
    )
    non_metro = _base_input(
        **common,
        hra_details=HRADetails(
            actual_hra_received=Decimal("100000"),
            rent_paid=Decimal("200000"),
            salary_for_hra=Decimal("100000"),
            is_metro_city=False,
        ),
    )

    assert not failed(validate_itr4_input(metro), "ITR4-R314")
    assert failed(validate_itr4_input(non_metro), "ITR4-R314")


# ═══════════════════════════════════════════════════════════════════════════════
# TDS / TCS
# ═══════════════════════════════════════════════════════════════════════════════

def test_R111_tcs_zero_collected():
    """Rule 111: TCS entries present but total collected is zero."""
    inp = _base_input(
        tcs_entries=[TCSEntry(tcs_section="206C", collector_tan="AAAA12345A", tcs_collected=Decimal("0"))],
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R411")


def test_R113_tds2_zero_deducted():
    """Rule 113: TDS2 entry with gross > 0 but TDS = 0."""
    inp = _base_input(
        tds2_entries=[
            TDS2Entry(
                tds_section="194A",
                deductor_tan="AAAA12345A",
                gross_amount=Decimal("50000"),
                tds_deducted=Decimal("0"),
            ),
        ],
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R113")


def test_R142a_tds1_no_salary():
    """Rule 142a: TDS1 claimed but no salary income."""
    inp = _base_input(
        salary_income=SalaryIncome(gross_salary=Decimal("0")),
        tds1_entries=[
            TDS1Entry(
                tds_section="192",
                employer_tan="AAAA12345A",
                gross_salary=Decimal("500000"),
                tds_deducted=Decimal("30000"),
            ),
        ],
    )
    results = validate_itr4_input(inp)
    r = get_result(results, "ITR4-R142a")
    assert r is not None


def test_R142b_tds2_no_os_income():
    """Rule 142b: TDS2 claimed but no OS income."""
    inp = _base_input(
        salary_income=SalaryIncome(gross_salary=Decimal("0")),
        business_income_44ad=None,
        other_sources_income=OtherSourcesIncome(),
        tds2_entries=[
            TDS2Entry(
                tds_section="194A",
                deductor_tan="AAAA12345A",
                gross_amount=Decimal("50000"),
                tds_deducted=Decimal("5000"),
            ),
        ],
    )
    results = validate_itr4_input(inp)
    r = get_result(results, "ITR4-R142b")
    assert r is not None


# ═══════════════════════════════════════════════════════════════════════════════
# Informational Rules — Presence Checks
# ═══════════════════════════════════════════════════════════════════════════════

def test_informational_rules_present():
    """Verify all key informational rules appear in output."""
    inp = _base_input(
        capital_gains=CapitalGainsIncome(ltcg_112a=Decimal("50000")),
        deductions_chapter6a=Chapter6ADeductions(
            amount_80dd=Decimal("75000"),
            amount_80ddb=Decimal("30000"),
            amount_80u=Decimal("75000"),
            amount_80g=Decimal("10000"),
            donations_80g=[Donation80G(non_cash_amount=Decimal("10000"))],
            amount_80gg=Decimal("5000"),
        ),
        nature_of_employment="Private",
    )
    results = validate_itr4_input(inp)

    # These informational rules should be present
    info_rules = [
        "ITR4-R266",   # LTCG 112A informational
        "ITR4-R010",   # 44AD not for agents
        "ITR4-R535",   # 80G eligible amount info (no schedule)
        "ITR4-R029",   # 80DD description
        "ITR4-R030",   # 80DDB description
        "ITR4-R044",   # 80U description
        "ITR4-R037",   # 80GG max info
    ]
    for rule_id in info_rules:
        assert any_present(results, rule_id), f"Expected {rule_id} to be present"


# ═══════════════════════════════════════════════════════════════════════════════
# Edge Case — Empty/Minimal Input
# ═══════════════════════════════════════════════════════════════════════════════

def test_minimal_valid_input_passes():
    """A minimal but valid ITR4Input should not trigger Category A failures."""
    inp = _base_input()
    results = validate_itr4_input(inp)
    # R140 should not trigger (we have a scheme)
    assert not failed(results, "ITR4-R140")
    # Only informational rules and pass-through rules expected
    for r in results:
        if r.severity == Severity.A:
            assert r.passed, f"Rule {r.rule_id} unexpectedly failed: {r.message}"


def test_no_deductions_no_salary_passes():
    """No deductions, minimal salary — should pass."""
    inp = _base_input(
        salary_income=SalaryIncome(gross_salary=Decimal("0")),
        nature_of_employment=None,
    )
    results = validate_itr4_input(inp)
    # R255 only fires if salary > 0
    assert not failed(results, "ITR4-R255")
    # Should pass all Category A rules
    for r in results:
        if r.severity == Severity.A:
            assert r.passed, f"Rule {r.rule_id} unexpectedly failed: {r.message}"


# ═══════════════════════════════════════════════════════════════════════════════
# Newly converted enforcement rules (formerly informational)
# ═══════════════════════════════════════════════════════════════════════════════

# ── R108: 80G cash donation per entry > Rs 2,000 ─────────────────────────────

def test_R108_cash_donation_exceeds_2000_per_entry():
    """80G cash donation entry > Rs 2,000 must fail (per-entry check)."""
    from app.schemas.itr4 import Schedule80G, Donation80G as Donation80GSched
    inp = _base_input(
        deductions_chapter6a=Chapter6ADeductions(
            amount_80g=Decimal("5000"),
        ),
        schedule_80g=Schedule80G(
            donations=[
                Donation80GSched(
                    donee_pan="ABCDE1234F",
                    cash_amount=Decimal("2500"), non_cash_amount=Decimal("0"),
                    total_donation=Decimal("2500"),
                ),
            ],
            total_eligible_amount=Decimal("2500"),
        ),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R408")


def test_R108_cash_donation_at_2000_passes():
    """80G cash donation entry exactly at Rs 2,000 should pass (per-entry)."""
    from app.schemas.itr4 import Schedule80G, Donation80G as Donation80GSched
    inp = _base_input(
        deductions_chapter6a=Chapter6ADeductions(
            amount_80g=Decimal("2000"),
        ),
        schedule_80g=Schedule80G(
            donations=[
                Donation80GSched(
                    donee_pan="ABCDE1234F",
                    cash_amount=Decimal("2000"), non_cash_amount=Decimal("0"),
                    total_donation=Decimal("2000"),
                ),
            ],
            total_eligible_amount=Decimal("2000"),
        ),
    )
    results = validate_itr4_input(inp)
    assert not failed(results, "ITR4-R408")


def test_R108_cash_donation_below_2000_passes():
    """80G cash donation entry < Rs 2,000 should pass (per-entry)."""
    from app.schemas.itr4 import Schedule80G, Donation80G as Donation80GSched
    inp = _base_input(
        deductions_chapter6a=Chapter6ADeductions(
            amount_80g=Decimal("1500"),
        ),
        schedule_80g=Schedule80G(
            donations=[
                Donation80GSched(
                    donee_pan="ABCDE1234F",
                    cash_amount=Decimal("1500"), non_cash_amount=Decimal("0"),
                    total_donation=Decimal("1500"),
                ),
            ],
            total_eligible_amount=Decimal("1500"),
        ),
    )
    results = validate_itr4_input(inp)
    assert not failed(results, "ITR4-R408")


# ── R035/R036: 80G schedule cross-consistency ────────────────────────────────

def test_R035_schedule_80g_eligible_exceeds_via():
    """Schedule80G total_eligible_amount > VIA amount_80g must fail."""
    inp = _base_input(
        schedule_80g=Schedule80G(
            total_eligible_amount=Decimal("10000"),
            donations=[Donation80G(
                cash_amount=Decimal("5000"), non_cash_amount=Decimal("0"),
                qualifying_percentage="100%",
            )],
        ),
        deductions_chapter6a=Chapter6ADeductions(
            amount_80g=Decimal("5000"),
            donations_80g=[
                Donation80G(
                    cash_amount=Decimal("5000"), non_cash_amount=Decimal("0"),
                    qualifying_percentage="100%",
                ),
            ],
        ),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R035")


def test_R036_donations_sum_mismatch_with_schedule():
    """Donations list sum != schedule_80g donations total must fail."""
    inp = _base_input(
        schedule_80g=Schedule80G(
            total_eligible_amount=Decimal("8000"),
            donations=[
                Donation80G(
                    cash_amount=Decimal("8000"), non_cash_amount=Decimal("0"),
                    qualifying_percentage="100%",
                ),
            ],
        ),
        deductions_chapter6a=Chapter6ADeductions(
            amount_80g=Decimal("8000"),
            donations_80g=[
                Donation80G(
                    cash_amount=Decimal("5000"), non_cash_amount=Decimal("0"),
                    qualifying_percentage="100%",
                ),
            ],
        ),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R036")


def test_R035_R036_schedule_matches_deductions_passes():
    """Schedule80G and deductions in sync should pass both R035 and R036."""
    inp = _base_input(
        schedule_80g=Schedule80G(
            total_eligible_amount=Decimal("8000"),
            donations=[
                Donation80G(
                    cash_amount=Decimal("5000"), non_cash_amount=Decimal("3000"),
                    qualifying_percentage="100%",
                ),
            ],
        ),
        deductions_chapter6a=Chapter6ADeductions(
            amount_80g=Decimal("8000"),
            donations_80g=[
                Donation80G(
                    cash_amount=Decimal("5000"), non_cash_amount=Decimal("3000"),
                    qualifying_percentage="100%",
                ),
            ],
        ),
    )
    results = validate_itr4_input(inp)
    assert not failed(results, "ITR4-R035")
    assert not failed(results, "ITR4-R036")


# ── R179b: 80D schedule-to-VIA cross-consistency ─────────────────────────────

def test_R179b_80d_via_mismatch_with_schedule():
    """80D VIA total != Schedule80D total must fail."""
    inp = _base_input(
        schedule_80d=Schedule80D(
            premium_1a_non_senior=Decimal("15000"),
            premium_1b_senior=Decimal("0"),
            premium_2a_parents_non_senior=Decimal("10000"),
            premium_2b_parents_senior=Decimal("0"),
        ),
        deductions_chapter6a=Chapter6ADeductions(
            amount_80d_self_family=Decimal("15000"),
            amount_80d_parents=Decimal("8000"),
        ),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R179b")


def test_R179b_80d_via_matches_schedule_passes():
    """80D VIA total == Schedule80D total should pass."""
    inp = _base_input(
        schedule_80d=Schedule80D(
            premium_1a_non_senior=Decimal("15000"),
            premium_1b_senior=Decimal("0"),
            premium_2a_parents_non_senior=Decimal("10000"),
            premium_2b_parents_senior=Decimal("0"),
        ),
        deductions_chapter6a=Chapter6ADeductions(
            amount_80d_self_family=Decimal("15000"),
            amount_80d_parents=Decimal("10000"),
        ),
    )
    results = validate_itr4_input(inp)
    assert not failed(results, "ITR4-R179b")


# ── R241: 80GGA cash donations > Rs 2,000 ────────────────────────────────────

def test_R241_80gga_cash_exceeds_2000():
    """80GGA cash donations > Rs 2,000 must fail."""
    inp = _base_input(
        schedule_80gga=Schedule80GGA(
            cash_donations=Decimal("3000"),
            non_cash_donations=Decimal("5000"),
            total_claimed=Decimal("8000"),
        ),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R241")


def test_R241_80gga_cash_at_2000_passes():
    """80GGA cash donations exactly Rs 2,000 should pass."""
    inp = _base_input(
        schedule_80gga=Schedule80GGA(
            cash_donations=Decimal("2000"),
            non_cash_donations=Decimal("0"),
            total_claimed=Decimal("2000"),
        ),
    )
    results = validate_itr4_input(inp)
    assert not failed(results, "ITR4-R241")


# ── R242: 80GGA duplicate PAN ────────────────────────────────────────────────

def test_R242_80gga_duplicate_pan():
    """80GGA duplicate donee PAN must fail."""
    inp = _base_input(
        schedule_80gga=Schedule80GGA(
            cash_donations=Decimal("0"),
            non_cash_donations=Decimal("5000"),
            donee_pan_list=["ABCDE1234F", "ABCDE1234F"],
            total_claimed=Decimal("5000"),
        ),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R242")


def test_R242_80gga_unique_pans_passes():
    """80GGA unique donee PANs should pass."""
    inp = _base_input(
        schedule_80gga=Schedule80GGA(
            cash_donations=Decimal("0"),
            non_cash_donations=Decimal("5000"),
            donee_pan_list=["ABCDE1234F", "WXYZA6789G"],
            total_claimed=Decimal("5000"),
        ),
    )
    results = validate_itr4_input(inp)
    assert not failed(results, "ITR4-R242")


# ── R243: 80GGA total consistency ────────────────────────────────────────────

def test_R243_80gga_total_mismatch():
    """80GGA cash + non-cash != total_claimed must fail."""
    inp = _base_input(
        schedule_80gga=Schedule80GGA(
            cash_donations=Decimal("1000"),
            non_cash_donations=Decimal("5000"),
            total_claimed=Decimal("7000"),
        ),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R243")


def test_R243_80gga_total_matches_passes():
    """80GGA cash + non-cash == total_claimed should pass."""
    inp = _base_input(
        schedule_80gga=Schedule80GGA(
            cash_donations=Decimal("1000"),
            non_cash_donations=Decimal("5000"),
            total_claimed=Decimal("6000"),
        ),
    )
    results = validate_itr4_input(inp)
    assert not failed(results, "ITR4-R243")


# ── R244: 80GGC non-cash only ────────────────────────────────────────────────

def test_R244_80ggc_cash_included():
    """80GGC with cash contributions must fail (non-cash != total_claimed)."""
    inp = _base_input(
        schedule_80ggc=Schedule80GGC(
            non_cash_contributions=Decimal("5000"),
            total_claimed=Decimal("10000"),
        ),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R244")


def test_R244_80ggc_all_non_cash_passes():
    """80GGC with all non-cash contributions should pass."""
    inp = _base_input(
        schedule_80ggc=Schedule80GGC(
            non_cash_contributions=Decimal("10000"),
            total_claimed=Decimal("10000"),
        ),
    )
    results = validate_itr4_input(inp)
    assert not failed(results, "ITR4-R244")


# ═══════════════════════════════════════════════════════════════════════════════
# New rules: Exempt income, Form requirements, HRA
# ═══════════════════════════════════════════════════════════════════════════════

# ── R071: Agriculture income > ₹5,000 ────────────────────────────────────────

def test_R071_agriculture_income_exceeds_5000():
    """Agriculture income > ₹5,000 is eligible for ITR-4 — triggers partial integration."""
    inp = _base_input(agriculture_income=Decimal("6000"))
    results = validate_itr4_input(inp)
    # R071 is now informational (Category D), not a blocking error.
    # ITR-4 permits agricultural income; the calculator handles partial integration.
    assert not failed(results, "ITR4-R071")


def test_R071_agriculture_income_at_5000_passes():
    """Agriculture income exactly ₹5,000 should pass."""
    inp = _base_input(agriculture_income=Decimal("5000"))
    results = validate_itr4_input(inp)
    assert not failed(results, "ITR4-R071")


# ── R072: Exempt income dropdown duplicates ──────────────────────────────────

def test_R072_duplicate_exempt_dropdown():
    """Duplicate exempt income dropdown entries must fail."""
    inp = _base_input(
        exempt_income_dropdowns=["Agricultural Income", "Agricultural Income"],
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R072")


def test_R072_unique_dropdowns_passes():
    """Unique exempt income dropdowns should pass."""
    inp = _base_input(
        exempt_income_dropdowns=["Agricultural Income", "HRA Exemption"],
        exempt_income_breakdown={"Agricultural Income": Decimal("4000"), "HRA Exemption": Decimal("100000")},
    )
    results = validate_itr4_input(inp)
    assert not failed(results, "ITR4-R072")


# ── R074: Exempt income breakdown empty with dropdown selection ──────────────

def test_R074_dropdowns_no_breakdown_values():
    """Exempt income dropdowns selected but no breakdown values must fail."""
    inp = _base_input(
        exempt_income_dropdowns=["Agricultural Income"],
        exempt_income_breakdown={},
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R074")


# ── R282: 80GG requires Form 10BA ────────────────────────────────────────────

def test_R282_80gg_without_form_10ba():
    """80GG claimed but Form 10BA not filed must fail."""
    inp = _base_input(
        deductions_chapter6a=Chapter6ADeductions(amount_80gg=Decimal("30000")),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R282")


def test_R282_80gg_with_form_10ba_passes():
    """80GG with Form 10BA filed should pass."""
    inp = _base_input(
        deductions_chapter6a=Chapter6ADeductions(amount_80gg=Decimal("30000")),
        form_10ba_filed=True,
    )
    results = validate_itr4_input(inp)
    assert not failed(results, "ITR4-R282")


# ── R389: Form 10E requires salary or family pension ─────────────────────────

def test_R389_form_10e_without_salary_or_pension():
    """Form 10E filed but no salary or family pension must fail."""
    inp = _base_input(
        salary_income=SalaryIncome(gross_salary=Decimal("0")),
        nature_of_employment=None,  # No salary → R255 won't fire
        form_10e_filed=True,
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R389")


def test_R389_form_10e_with_salary_passes():
    """Form 10E filed with salary should pass."""
    inp = _base_input(form_10e_filed=True)
    results = validate_itr4_input(inp)
    assert not failed(results, "ITR4-R389")


# ── R288: 80DD/80U requires Form 10-IA ───────────────────────────────────────

def test_R288_80dd_without_form_10ia():
    """80DD claimed but Form 10-IA not filed must fail."""
    inp = _base_input(
        deductions_chapter6a=Chapter6ADeductions(amount_80dd=Decimal("75000")),
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R288")


def test_R288_80dd_with_form_10ia_passes():
    """80DD with Form 10-IA filed should pass."""
    inp = _base_input(
        deductions_chapter6a=Chapter6ADeductions(amount_80dd=Decimal("75000")),
        form_10ia_filed=True,
    )
    results = validate_itr4_input(inp)
    assert not failed(results, "ITR4-R288")


# ── R289/R295: 24(b) row sum must match the ONE property ITR-4 computes ────
# ITR-4 computes income for only property_sequence_no 1 (no house_properties
# list, unlike ITR-1's up-to-two). loan_details_24b_list can still carry a
# second property's loan tagged sequence_no 2 if a draft somehow has one
# (nothing in the pipeline rejects that outright). Both R289 and R295
# previously summed the WHOLE list regardless of sequence_no, producing a
# false-positive block for exactly that case -- the same pattern already
# fixed for ITR1-R246. See
# Docs/ITR4_FRONTEND_AND_SERIALIZATION_AUDIT_AY2026_27.md §3.2.

def test_R289_single_property_matching_loan_passes():
    inp = _base_input(
        house_property_income=HousePropertyIncome(
            property_type=PropertyType.SELF_OCCUPIED,
            home_loan_interest_paid=Decimal("150000"),
        ),
        loan_details_24b_list=[LoanDetail(
            property_sequence_no=1, lender_name="HDFC Bank",
            loan_amount=Decimal("2000000"),
            interest_paid_self_occupied=Decimal("150000"),
        )],
    )
    results = validate_itr4_input(inp)
    assert not failed(results, "ITR4-R289")
    assert not failed(results, "ITR4-R295")


def test_R289_genuine_mismatch_still_caught():
    inp = _base_input(
        house_property_income=HousePropertyIncome(
            property_type=PropertyType.SELF_OCCUPIED,
            home_loan_interest_paid=Decimal("150000"),
        ),
        loan_details_24b_list=[LoanDetail(
            property_sequence_no=1, lender_name="HDFC Bank",
            loan_amount=Decimal("2000000"),
            interest_paid_self_occupied=Decimal("100000"),
        )],
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R289")
    assert failed(results, "ITR4-R295")


def test_R289_second_property_loan_does_not_cause_false_positive():
    """The exact bug scenario: a second property's loan (sequence_no 2)
    must not be added into the sum checked against the one property ITR-4
    actually computes income for."""
    inp = _base_input(
        house_property_income=HousePropertyIncome(
            property_type=PropertyType.SELF_OCCUPIED,
            home_loan_interest_paid=Decimal("150000"),
        ),
        loan_details_24b_list=[
            LoanDetail(
                property_sequence_no=1, lender_name="HDFC Bank",
                loan_amount=Decimal("2000000"),
                interest_paid_self_occupied=Decimal("150000"),
            ),
            LoanDetail(
                property_sequence_no=2, lender_name="Axis Bank",
                loan_amount=Decimal("1000000"),
                interest_paid_let_out=Decimal("40000"),
            ),
        ],
    )
    results = validate_itr4_input(inp)
    assert not failed(results, "ITR4-R289")
    assert not failed(results, "ITR4-R295")


# ═══════════════════════════════════════════════════════════════════════════
# nature_of_employment keyword-vs-raw-code bug (10 sites, matching the
# identical pattern already found and fixed in ITR-1's validators, §14.5).
# Each test below checks both directions: a real CG/SG-employee or
# pensioner code that must now correctly pass/fail, and a non-CG/SG/
# non-pensioner code that must still behave the same as before. See
# Docs/ITR4_FRONTEND_AND_SERIALIZATION_AUDIT_AY2026_27.md.
# ═══════════════════════════════════════════════════════════════════════════

def test_R025_80ccd2_cgsg_employee_not_falsely_blocked_at_10pct():
    """R025 (non-CG/SG 10% cap) previously fired for EVERY employee,
    including genuine CG/SG ones, because "central government"/"state
    government" never matched the raw code "CGOV". A CG/SG employee
    claiming between 10% and 14% of salary must now correctly pass R025
    (R047's 14% cap governs them instead)."""
    inp = _base_input(
        salary_income=SalaryIncome(gross_salary=Decimal("1000000")),
        nature_of_employment="CGOV",
        deductions_chapter6a=Chapter6ADeductions(amount_80ccd2=Decimal("120000")),  # 12% of 10L
    )
    results = validate_itr4_input(inp)
    assert not failed(results, "ITR4-R025")


def test_R025_non_cgsg_employee_still_capped_at_10pct():
    inp = _base_input(
        salary_income=SalaryIncome(gross_salary=Decimal("1000000")),
        nature_of_employment="OTH",
        deductions_chapter6a=Chapter6ADeductions(amount_80ccd2=Decimal("120000")),  # 12% of 10L
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R025")


def test_R047_cgsg_employee_14pct_cap_now_reachable():
    """R047 (CG/SG 14% cap) was previously dormant -- "central government"
    never matched "CGOV", so this rule could never fire even for a genuine
    CG/SG employee exceeding 14%."""
    inp = _base_input(
        salary_income=SalaryIncome(gross_salary=Decimal("1000000")),
        nature_of_employment="CGOV",
        deductions_chapter6a=Chapter6ADeductions(amount_80ccd2=Decimal("150000")),  # 15% of 10L
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R047")


def test_R073_cgsg_gratuity_20l_cap_now_reachable():
    """R073 (non-CG/SG gratuity Rs 20L cap) previously fired for every
    employee including genuine CG/SG ones (fully exempt, no 20L cap) --
    now correctly does not fire for a real CGOV employee."""
    inp = _base_input(
        salary_income=SalaryIncome(gross_salary=Decimal("500000"), gratuity_received=Decimal("2200000")),
        nature_of_employment="CGOV",
    )
    results = validate_itr4_input(inp)
    assert not failed(results, "ITR4-R073")


def test_R073_non_cgsg_gratuity_20l_cap_still_enforced():
    inp = _base_input(
        salary_income=SalaryIncome(gross_salary=Decimal("500000"), gratuity_received=Decimal("2200000")),
        nature_of_employment="OTH",
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R073")


def test_R317_cgsg_gratuity_25l_cap_now_reachable():
    """R317 (CG/SG gratuity Rs 25L cap) was previously dormant."""
    inp = _base_input(
        salary_income=SalaryIncome(gross_salary=Decimal("500000"), gratuity_received=Decimal("2600000")),
        nature_of_employment="SGOV",
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R317")


def test_R075_cgsg_leave_encashment_not_falsely_blocked():
    """R075 (non-govt leave encashment Rs 25L cap) previously fired for
    every employee including genuine CG/SG ones (fully exempt)."""
    inp = _base_input(
        salary_income=SalaryIncome(gross_salary=Decimal("500000"), leave_encashment_received=Decimal("2600000")),
        nature_of_employment="SGOV",
    )
    results = validate_itr4_input(inp)
    assert not failed(results, "ITR4-R075")


def test_R185_cgsg_retrenchment_now_reachable():
    """R185 (10(10B) retrenchment not for CG/SG/pensioners) was previously
    dormant -- "central"/"state"/"pension" never matched the raw codes."""
    inp = _base_input(
        salary_income=SalaryIncome(gross_salary=Decimal("500000"), retrenchment_compensation=Decimal("100000")),
        nature_of_employment="CGOV",
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R185")


def test_R185_pensioner_retrenchment_now_reachable():
    inp = _base_input(
        salary_income=SalaryIncome(gross_salary=Decimal("500000"), retrenchment_compensation=Decimal("100000")),
        nature_of_employment="PE",
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R185")


def test_R185_private_employee_retrenchment_not_blocked():
    inp = _base_input(
        salary_income=SalaryIncome(gross_salary=Decimal("500000"), retrenchment_compensation=Decimal("100000")),
        nature_of_employment="OTH",
    )
    results = validate_itr4_input(inp)
    assert not failed(results, "ITR4-R185")


def test_R322_judge_exemption_cgsg_employee_not_falsely_blocked():
    """R322 (Judge Salaries Act exemption, CG/SG only) previously fired for
    EVERY filer claiming it, including genuine CGOV/SGOV judges, because
    "central government"/"state government" never matched the raw code."""
    inp = _base_input(
        exempt_income_dropdowns=["Judge Salaries Act"],
        nature_of_employment="CGOV",
    )
    results = validate_itr4_input(inp)
    assert not failed(results, "ITR4-R322")


def test_R322_non_cgsg_judge_exemption_still_blocked():
    inp = _base_input(
        exempt_income_dropdowns=["Judge Salaries Act"],
        nature_of_employment="OTH",
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R322")


def test_R263_new_regime_80ccd2_cgov_now_reachable():
    """R263 (new regime 80CCD(2) 14% cap for PSU/CG/SG/Others) used "CG"/
    "SG" instead of the real raw codes "CGOV"/"SGOV", so it was dormant for
    genuine CG/SG employees specifically (PSU/OTH already worked)."""
    inp = _base_input(
        tax_regime=TaxRegime.NEW,
        salary_income=SalaryIncome(gross_salary=Decimal("1000000")),
        nature_of_employment="CGOV",
        deductions_chapter6a=Chapter6ADeductions(amount_80ccd2=Decimal("150000")),  # 15%
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R263")


def test_R067_entertainment_allowance_cgov_now_reachable():
    """R067 (entertainment allowance cap, CG/SG/PSU only) used "CG"/"SG"
    instead of "CGOV"/"SGOV", so it was dormant for genuine CG/SG
    employees."""
    inp = _base_input(
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("500000"), entertainment_allowance=Decimal("8000")),
        nature_of_employment="CGOV",
    )
    results = validate_itr4_input(inp)
    assert failed(results, "ITR4-R067")


def test_R068_entertainment_allowance_cgov_not_falsely_blocked():
    """R068 has two implementations: one reading the correctly-derived
    SalaryIncome.is_government_employee (via the shared _map_salary, fixed
    during the ITR-1 audit's §5.2), and one (fixed here) reading
    nature_of_employment directly. Setting is_government_employee too,
    matching what the real mapper would produce for a CGOV employee, so
    this test isolates the nature_of_employment-based check that changed."""
    inp = _base_input(
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(
            gross_salary=Decimal("500000"), entertainment_allowance=Decimal("3000"),
            is_government_employee=True,
        ),
        nature_of_employment="CGOV",
    )
    results = validate_itr4_input(inp)
    assert not failed(results, "ITR4-R068")
