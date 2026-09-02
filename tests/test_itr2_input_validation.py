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

import pytest

from app.engine.validators.itr2.input_rules import validate_itr2_input
from app.schemas.itr1 import (
    Chapter6ADeductions,
    FilingAddress,
    HousePropertyIncome,
    PropertyType,
    SalaryIncome,
    TaxRegime,
    TDS2Entry,
    TDS3Entry,
)
from app.schemas.itr2 import (
    AgeBracket,
    AssesseeStatus,
    CG112AScrip,
    CGAssetType,
    CGTransaction,
    ITR2FilingProfile,
    ITR2Input,
    PropertyFilingDetail,
    ResidentialStatus,
    ScheduleSIEntry,
    VDATransaction,
)


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


# ── Phase 5C: Chapter VI-A deductions ───────────────────────────────────────

def _filing_profile(assessee_status: AssesseeStatus = AssesseeStatus.INDIVIDUAL) -> ITR2FilingProfile:
    return ITR2FilingProfile(
        pan="ABCPN1234F", assessee_status=assessee_status, surname_or_org_name="Nair",
        date_of_birth_or_formation=date(1985, 6, 15), father_name="Ramesh Nair",
        verification_place="Mumbai",
        primary_address=FilingAddress(
            residence_no="12", locality_or_area="MG Road", city_or_town_or_district="Mumbai",
            state_code="27", mobile_no="9876543210", email="priya@example.com",
        ),
    )


def test_VIA_001_new_regime_without_chapter6a_claims_passes():
    inp = _base_input(tax_regime=TaxRegime.NEW, deductions_chapter6a=Chapter6ADeductions())
    assert not failed(validate_itr2_input(inp), "ITR2-IN-VIA-001")


def test_VIA_001_new_regime_with_80c_claim_fails():
    inp = _base_input(tax_regime=TaxRegime.NEW, deductions_chapter6a=Chapter6ADeductions(
        amount_80c=Decimal("50000"),
    ))
    assert failed(validate_itr2_input(inp), "ITR2-IN-VIA-001")


def test_VIA_002_individual_with_80e_claim_passes():
    inp = _base_input(
        filing_profile=_filing_profile(AssesseeStatus.INDIVIDUAL),
        deductions_chapter6a=Chapter6ADeductions(amount_80e=Decimal("30000")),
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-VIA-002")


def test_VIA_002_huf_with_80e_claim_fails():
    inp = _base_input(
        filing_profile=_filing_profile(AssesseeStatus.HUF),
        deductions_chapter6a=Chapter6ADeductions(amount_80e=Decimal("30000")),
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-VIA-002")


def test_VIA_003_resident_with_80dd_claim_passes():
    inp = _base_input(
        residential_status=ResidentialStatus.RESIDENT,
        deductions_chapter6a=Chapter6ADeductions(amount_80dd=Decimal("75000")),
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-VIA-003")


def test_VIA_003_non_resident_with_80dd_claim_fails():
    inp = _base_input(
        residential_status=ResidentialStatus.NON_RESIDENT,
        deductions_chapter6a=Chapter6ADeductions(amount_80dd=Decimal("75000")),
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-VIA-003")


# ── Phase 5D: Schedule OS / Schedule SI / CYLA-BFLA-CFL ─────────────────────

def test_SI_001_online_game_winnings_without_deduction_passes():
    inp = _base_input(si_entries=[ScheduleSIEntry(
        section="115BBJ", gross_income=Decimal("20000"),
    )])
    assert not failed(validate_itr2_input(inp), "ITR2-IN-SI-001")


def test_SI_001_online_game_winnings_with_deduction_fails():
    inp = _base_input(si_entries=[ScheduleSIEntry(
        section="115BBJ", gross_income=Decimal("20000"), deductions=Decimal("1000"),
    )])
    assert failed(validate_itr2_input(inp), "ITR2-IN-SI-001")


def test_SI_001_other_section_with_deduction_passes():
    inp = _base_input(si_entries=[ScheduleSIEntry(
        section="115BBF", gross_income=Decimal("50000"), deductions=Decimal("5000"),
    )])
    assert not failed(validate_itr2_input(inp), "ITR2-IN-SI-001")


# ── Phase 5E: AMT/TDS reconciliation, Schedule AL, Form reminders ──────────

def test_TDS_001_claim_within_deducted_plus_brought_forward_passes():
    inp = _base_input(tds2_entries=[TDS2Entry(
        deductor_tan="MUMA12345B", tds_section="194A",
        tds_deducted=Decimal("10000"), brought_forward_tds=Decimal("5000"),
        tds_claimed_this_year=Decimal("15000"),
    )])
    assert not failed(validate_itr2_input(inp), "ITR2-IN-TDS-001")


def test_TDS_001_claim_ignoring_deducted_alone_would_have_failed_but_brought_forward_covers_it():
    """A claim that exceeds tds_deducted alone is fine once brought_forward_tds covers it —
    this is the exact false-rejection this rule's CBDT-rule-466 fix corrects."""
    inp = _base_input(tds2_entries=[TDS2Entry(
        deductor_tan="MUMA12345B", tds_section="194A",
        tds_deducted=Decimal("10000"), brought_forward_tds=Decimal("5000"),
        tds_claimed_this_year=Decimal("12000"),
    )])
    assert not failed(validate_itr2_input(inp), "ITR2-IN-TDS-001")


def test_TDS_001_claim_exceeding_deducted_plus_brought_forward_fails():
    inp = _base_input(tds2_entries=[TDS2Entry(
        deductor_tan="MUMA12345B", tds_section="194A",
        tds_deducted=Decimal("10000"), brought_forward_tds=Decimal("5000"),
        tds_claimed_this_year=Decimal("15001"),
    )])
    assert failed(validate_itr2_input(inp), "ITR2-IN-TDS-001")


def test_tds3entry_schema_allows_claim_within_deducted_plus_brought_forward():
    """TDS3's own model_validator (app/schemas/itr1.py) enforces CBDT rule
    466/467 directly — no ITR2-IN-TDS rule is needed for TDS3 as a result,
    since a violating TDS3Entry can never be constructed in the first place."""
    entry = TDS3Entry(
        tenant_pan="ABCPN1234F", tenant_name="Tenant", tds_section="194IB",
        tds_deducted=Decimal("10000"), brought_forward_tds=Decimal("5000"),
        tds_claimed=Decimal("15000"),
    )
    assert entry.tds_claimed == Decimal("15000")


def test_tds3entry_schema_rejects_claim_exceeding_deducted_plus_brought_forward():
    with pytest.raises(ValueError, match="cannot exceed deducted credit plus brought-forward"):
        TDS3Entry(
            tenant_pan="ABCPN1234F", tenant_name="Tenant", tds_section="194IB",
            tds_deducted=Decimal("10000"), brought_forward_tds=Decimal("5000"),
            tds_claimed=Decimal("15001"),
        )


def test_FORM_001_relief_89_claimed_emits_category_d_reminder():
    inp = _base_input(relief_89=Decimal("5000"))
    results = validate_itr2_input(inp)
    matches = [r for r in results if r.rule_id == "ITR2-IN-FORM-001"]
    assert matches and matches[0].passed


def test_FORM_001_no_relief_89_emits_nothing():
    inp = _base_input(relief_89=Decimal("0"))
    results = validate_itr2_input(inp)
    assert not [r for r in results if r.rule_id == "ITR2-IN-FORM-001"]


def test_FORM_002_80gg_claimed_emits_category_d_reminder():
    inp = _base_input(deductions_chapter6a=Chapter6ADeductions(amount_80gg=Decimal("30000")))
    results = validate_itr2_input(inp)
    matches = [r for r in results if r.rule_id == "ITR2-IN-FORM-002"]
    assert matches and matches[0].passed


def test_FORM_002_no_80gg_emits_nothing():
    inp = _base_input(deductions_chapter6a=Chapter6ADeductions())
    results = validate_itr2_input(inp)
    assert not [r for r in results if r.rule_id == "ITR2-IN-FORM-002"]
