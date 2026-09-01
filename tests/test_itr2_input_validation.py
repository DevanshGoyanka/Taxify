"""
ITR-2 input validation rules (CBDT Category A, AY 2026-27).

Phase 5A of Docs/ITR2_ITR3_V2_PIPELINE_PRODUCTION_PLAN.md — Schedule S (Salary)
and Schedule HP (House Property) rules; Phase 5B — Schedule CG/112A/VDA
(capital gains) rules. Both extracted from the official CBDT ITR-2 Validation
Rules PDF. One known-good and one known-bad case per rule.

Run: pytest tests/test_itr2_input_validation.py -v
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.engine.validators.itr2.input_rules import validate_itr2_input
from app.schemas.itr1 import HousePropertyIncome, PropertyType, SalaryIncome, TaxRegime
from app.schemas.itr2 import AgeBracket, CG112AScrip, CGAssetType, CGTransaction, ITR2Input, PropertyFilingDetail, VDATransaction


def failed(results, rule_id: str) -> bool:
    return any(r.rule_id == rule_id and not r.passed for r in results)


def _base_input(**overrides) -> ITR2Input:
    fields = dict(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
    )
    fields.update(overrides)
    return ITR2Input(**fields)


def test_SAL_001_lta_exempt_within_lta_received_passes():
    inp = _base_input(salary_income=SalaryIncome(
        gross_salary=Decimal("500000"),
        lta_amount_received=Decimal("20000"), lta_exempt_amount=Decimal("20000"),
    ))
    assert not failed(validate_itr2_input(inp), "ITR2-IN-SAL-001")


def test_SAL_001_lta_exempt_exceeding_received_fails():
    inp = _base_input(salary_income=SalaryIncome(
        gross_salary=Decimal("500000"),
        lta_amount_received=Decimal("20000"), lta_exempt_amount=Decimal("25000"),
    ))
    assert failed(validate_itr2_input(inp), "ITR2-IN-SAL-001")


def test_SAL_002_embassy_exempt_within_gross_salary_passes():
    inp = _base_input(salary_income=SalaryIncome(
        gross_salary=Decimal("500000"), sec10_6_embassy_exempt=Decimal("100000"),
    ))
    assert not failed(validate_itr2_input(inp), "ITR2-IN-SAL-002")


def test_SAL_002_embassy_exempt_exceeding_gross_salary_fails():
    inp = _base_input(salary_income=SalaryIncome(
        gross_salary=Decimal("500000"), sec10_6_embassy_exempt=Decimal("600000"),
    ))
    assert failed(validate_itr2_input(inp), "ITR2-IN-SAL-002")


def test_SAL_003_foreign_allowance_within_gross_salary_passes():
    inp = _base_input(salary_income=SalaryIncome(
        gross_salary=Decimal("500000"), sec10_7_foreign_allowance=Decimal("100000"),
    ))
    assert not failed(validate_itr2_input(inp), "ITR2-IN-SAL-003")


def test_SAL_003_foreign_allowance_exceeding_gross_salary_fails():
    inp = _base_input(salary_income=SalaryIncome(
        gross_salary=Decimal("500000"), sec10_7_foreign_allowance=Decimal("600000"),
    ))
    assert failed(validate_itr2_input(inp), "ITR2-IN-SAL-003")


def test_SAL_004_10_10cc_within_perquisite_value_passes():
    inp = _base_input(salary_income=SalaryIncome(
        gross_salary=Decimal("500000"), perquisites_value=Decimal("50000"),
        sec10_10cc_perquisite_tax=Decimal("50000"),
    ))
    assert not failed(validate_itr2_input(inp), "ITR2-IN-SAL-004")


def test_SAL_004_10_10cc_exceeding_perquisite_value_fails():
    inp = _base_input(salary_income=SalaryIncome(
        gross_salary=Decimal("500000"), perquisites_value=Decimal("50000"),
        sec10_10cc_perquisite_tax=Decimal("60000"),
    ))
    assert failed(validate_itr2_input(inp), "ITR2-IN-SAL-004")


def test_SAL_005_entertainment_allowance_for_govt_employee_passes():
    inp = _base_input(salary_income=SalaryIncome(
        gross_salary=Decimal("500000"), is_government_employee=True,
        entertainment_allowance=Decimal("5000"),
    ))
    assert not failed(validate_itr2_input(inp), "ITR2-IN-SAL-005")


def test_SAL_005_entertainment_allowance_for_non_govt_employee_fails():
    inp = _base_input(salary_income=SalaryIncome(
        gross_salary=Decimal("500000"), is_government_employee=False,
        entertainment_allowance=Decimal("5000"),
    ))
    assert failed(validate_itr2_input(inp), "ITR2-IN-SAL-005")


def test_SAL_006_new_regime_without_hra_lta_passes():
    inp = _base_input(tax_regime=TaxRegime.NEW, salary_income=SalaryIncome(
        gross_salary=Decimal("500000"),
    ))
    assert not failed(validate_itr2_input(inp), "ITR2-IN-SAL-006")


def test_SAL_006_new_regime_with_hra_fails():
    inp = _base_input(tax_regime=TaxRegime.NEW, salary_income=SalaryIncome(
        gross_salary=Decimal("500000"), hra_exempt_amount=Decimal("10000"),
    ))
    assert failed(validate_itr2_input(inp), "ITR2-IN-SAL-006")


def test_SAL_007_new_regime_without_entertainment_allowance_passes():
    inp = _base_input(tax_regime=TaxRegime.NEW, salary_income=SalaryIncome(
        gross_salary=Decimal("500000"),
    ))
    assert not failed(validate_itr2_input(inp), "ITR2-IN-SAL-007")


def test_SAL_007_new_regime_with_entertainment_allowance_fails():
    inp = _base_input(tax_regime=TaxRegime.NEW, salary_income=SalaryIncome(
        gross_salary=Decimal("500000"), entertainment_allowance=Decimal("5000"),
    ))
    assert failed(validate_itr2_input(inp), "ITR2-IN-SAL-007")


def test_SAL_008_new_regime_without_professional_tax_passes():
    inp = _base_input(tax_regime=TaxRegime.NEW, salary_income=SalaryIncome(
        gross_salary=Decimal("500000"),
    ))
    assert not failed(validate_itr2_input(inp), "ITR2-IN-SAL-008")


def test_SAL_008_new_regime_with_professional_tax_fails():
    inp = _base_input(tax_regime=TaxRegime.NEW, salary_income=SalaryIncome(
        gross_salary=Decimal("500000"), professional_tax_paid=Decimal("2500"),
    ))
    assert failed(validate_itr2_input(inp), "ITR2-IN-SAL-008")


def test_HP_001_municipal_tax_with_rent_passes():
    inp = _base_input(house_property_income=HousePropertyIncome(
        property_type=PropertyType.LET_OUT,
        annual_rent_received=Decimal("240000"), municipal_taxes_paid=Decimal("5000"),
    ))
    assert not failed(validate_itr2_input(inp), "ITR2-IN-HP-001")


def test_HP_001_municipal_tax_without_rent_fails():
    inp = _base_input(house_property_income=HousePropertyIncome(
        property_type=PropertyType.LET_OUT,
        annual_rent_received=Decimal("0"), municipal_taxes_paid=Decimal("5000"),
    ))
    assert failed(validate_itr2_input(inp), "ITR2-IN-HP-001")


def test_HP_002_let_out_with_positive_rent_passes():
    inp = _base_input(house_property_income=HousePropertyIncome(
        property_type=PropertyType.LET_OUT, annual_rent_received=Decimal("240000"),
    ))
    assert not failed(validate_itr2_input(inp), "ITR2-IN-HP-002")


def test_HP_002_let_out_with_zero_rent_fails():
    inp = _base_input(house_property_income=HousePropertyIncome(
        property_type=PropertyType.LET_OUT, annual_rent_received=Decimal("0"),
    ))
    assert failed(validate_itr2_input(inp), "ITR2-IN-HP-002")


def test_HP_003_two_self_occupied_properties_passes():
    inp = _base_input(house_properties=[
        HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
    ])
    assert not failed(validate_itr2_input(inp), "ITR2-IN-HP-003")


def test_HP_003_three_self_occupied_properties_fails():
    inp = _base_input(house_properties=[
        HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
    ])
    assert failed(validate_itr2_input(inp), "ITR2-IN-HP-003")


_ONE_LET_OUT_PROPERTY = HousePropertyIncome(
    property_type=PropertyType.LET_OUT, annual_rent_received=Decimal("240000"),
)


def test_HP_004_co_owned_share_below_100_passes():
    inp = _base_input(
        house_property_income=_ONE_LET_OUT_PROPERTY,
        property_filing_details=[PropertyFilingDetail(
            address_detail="A", city_or_town_or_district="City", state_code="27",
            pin_code="400001", co_owned=True, assessee_share_percent=Decimal("50"),
        )],
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-HP-004")


def test_HP_004_co_owned_share_at_100_fails():
    inp = _base_input(
        house_property_income=_ONE_LET_OUT_PROPERTY,
        property_filing_details=[PropertyFilingDetail(
            address_detail="A", city_or_town_or_district="City", state_code="27",
            pin_code="400001", co_owned=True, assessee_share_percent=Decimal("100"),
        )],
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-HP-004")


def test_HP_005_non_co_owned_share_at_100_passes():
    inp = _base_input(
        house_property_income=_ONE_LET_OUT_PROPERTY,
        property_filing_details=[PropertyFilingDetail(
            address_detail="A", city_or_town_or_district="City", state_code="27",
            pin_code="400001", co_owned=False, assessee_share_percent=Decimal("100"),
        )],
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-HP-005")


def test_HP_005_non_co_owned_share_below_100_fails():
    inp = _base_input(
        house_property_income=_ONE_LET_OUT_PROPERTY,
        property_filing_details=[PropertyFilingDetail(
            address_detail="A", city_or_town_or_district="City", state_code="27",
            pin_code="400001", co_owned=False, assessee_share_percent=Decimal("60"),
        )],
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-HP-005")


# ── Phase 5B: Schedule CG / 112A / VDA ──────────────────────────────────────

def test_CG_007_land_building_transfer_within_financial_year_passes():
    inp = _base_input(cg_transactions=[CGTransaction(
        asset_type=CGAssetType.LAND_BUILDING,
        date_of_acquisition=date(2020, 4, 1), date_of_transfer=date(2026, 2, 1),
        full_consideration=Decimal("8000000"), cost_of_acquisition=Decimal("3000000"),
    )])
    assert not failed(validate_itr2_input(inp), "ITR2-IN-CG-007")


def test_CG_007_land_building_transfer_after_financial_year_end_fails():
    inp = _base_input(cg_transactions=[CGTransaction(
        asset_type=CGAssetType.LAND_BUILDING,
        date_of_acquisition=date(2020, 4, 1), date_of_transfer=date(2026, 4, 1),
        full_consideration=Decimal("8000000"), cost_of_acquisition=Decimal("3000000"),
    )])
    assert failed(validate_itr2_input(inp), "ITR2-IN-CG-007")


def test_CG_008_54ec_deduction_within_cap_passes():
    inp = _base_input(cg_transactions=[CGTransaction(
        asset_type=CGAssetType.LAND_BUILDING,
        date_of_acquisition=date(2020, 4, 1), date_of_transfer=date(2025, 12, 1),
        full_consideration=Decimal("8000000"), cost_of_acquisition=Decimal("3000000"),
        deduction_us54ec=Decimal("5000000"),
    )])
    assert not failed(validate_itr2_input(inp), "ITR2-IN-CG-008")


def test_CG_008_54ec_deduction_exceeding_cap_fails():
    inp = _base_input(cg_transactions=[CGTransaction(
        asset_type=CGAssetType.LAND_BUILDING,
        date_of_acquisition=date(2020, 4, 1), date_of_transfer=date(2025, 12, 1),
        full_consideration=Decimal("8000000"), cost_of_acquisition=Decimal("3000000"),
        deduction_us54ec=Decimal("5000001"),
    )])
    assert failed(validate_itr2_input(inp), "ITR2-IN-CG-008")


def _base_112a_scrip(**overrides) -> CG112AScrip:
    fields = dict(
        isin_code="INE001A01036", share_unit_name="Reliance Industries",
        date_of_transfer=date(2025, 12, 1),
        num_shares_units=Decimal("100"), sale_price_per_share=Decimal("3000"),
        total_sale_value=Decimal("300000"), cost_acq_without_index=Decimal("100000"),
    )
    fields.update(overrides)
    return CG112AScrip(**fields)


def test_112A_008_post_2018_scrip_without_fmv_passes():
    inp = _base_input(cg_112a_scrips=[_base_112a_scrip(is_before_31jan2018=False)])
    assert not failed(validate_itr2_input(inp), "ITR2-IN-112A-008")


def test_112A_008_post_2018_scrip_with_fmv_fails():
    inp = _base_input(cg_112a_scrips=[_base_112a_scrip(
        is_before_31jan2018=False, fmv_per_share=Decimal("1000"),
    )])
    assert failed(validate_itr2_input(inp), "ITR2-IN-112A-008")


def test_VDA_004_dates_within_financial_year_passes():
    inp = _base_input(vda_transactions=[VDATransaction(
        date_of_acquisition=date(2025, 6, 1), date_of_transfer=date(2026, 1, 1),
        acquisition_cost=Decimal("50000"), consideration_received=Decimal("90000"),
    )])
    assert not failed(validate_itr2_input(inp), "ITR2-IN-VDA-004")


def test_VDA_004_transfer_date_after_financial_year_end_fails():
    inp = _base_input(vda_transactions=[VDATransaction(
        date_of_acquisition=date(2025, 6, 1), date_of_transfer=date(2026, 4, 1),
        acquisition_cost=Decimal("50000"), consideration_received=Decimal("90000"),
    )])
    assert failed(validate_itr2_input(inp), "ITR2-IN-VDA-004")
