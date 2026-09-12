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
    BankAccount,
    Chapter6ADeductions,
    DependentRelationship,
    FilingAddress,
    HousePropertyIncome,
    OtherSourcesIncome,
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
    CGDtaaEntry,
    CGTransaction,
    ITR2FilingProfile,
    ITR2Input,
    ESOPDeferralInput,
    CapitalGainExemptionClaim,
    CoOwnerDetail,
    EmployerFilingDetail,
    PropertyFilingDetail,
    ReturnFileSection,
    ResidentialStatus,
    FSICountryEntry,
    OS89ACountryEntry,
    OSDeductions,
    OSDtaaEntry,
    OSSection89A,
    TR1Entry,
    ScheduleSIEntry,
    VDATransaction,
)


def failed(results, rule_id: str) -> bool:
    return any(r.rule_id == rule_id and not r.passed for r in results)


def emitted(results, rule_id: str) -> bool:
    """True if a rule with this ID appears at all -- used for the
    non-blocking Severity.D advisories, which are `passed=True`
    (informational), not failures."""
    return any(r.rule_id == rule_id for r in results)


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
            co_owner_details=[CoOwnerDetail(name="Co-owner", percent_share=Decimal("50"))],
        )],
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-HP-004")


def test_HP_004_co_owned_share_at_100_fails():
    inp = _base_input(
        house_property_income=_ONE_LET_OUT_PROPERTY,
        property_filing_details=[PropertyFilingDetail(
            address_detail="A", city_or_town_or_district="City", state_code="27",
            pin_code="400001", co_owned=True, assessee_share_percent=Decimal("100"),
            co_owner_details=[CoOwnerDetail(name="Co-owner", percent_share=Decimal("0"))],
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


def test_HP_006_unrealised_rent_within_gross_rent_passes():
    inp = _base_input(house_property_income=HousePropertyIncome(
        property_type=PropertyType.LET_OUT,
        annual_rent_received=Decimal("240000"),
        rent_not_realized=Decimal("50000"),
    ))
    assert not failed(validate_itr2_input(inp), "ITR2-IN-HP-006")


def test_HP_006_unrealised_rent_exceeding_gross_rent_fails():
    inp = _base_input(house_property_income=HousePropertyIncome(
        property_type=PropertyType.LET_OUT,
        annual_rent_received=Decimal("240000"),
        rent_not_realized=Decimal("250000"),
    ))
    assert failed(validate_itr2_input(inp), "ITR2-IN-HP-006")


def test_HP_007_zero_share_without_interest_passes():
    inp = _base_input(
        house_property_income=HousePropertyIncome(
            property_type=PropertyType.SELF_OCCUPIED,
            ownership_share_percentage=Decimal("0.01"),
        ),
        property_filing_details=[PropertyFilingDetail(
            address_detail="A", city_or_town_or_district="City", state_code="27",
            pin_code="400001", co_owned=True, assessee_share_percent=Decimal("0.01"),
            co_owner_details=[CoOwnerDetail(name="Co-owner", percent_share=Decimal("99.99"))],
        )],
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-HP-007")


def test_HP_007_zero_share_with_interest_fails():
    inp = _base_input(
        house_property_income=HousePropertyIncome(
            property_type=PropertyType.SELF_OCCUPIED,
            ownership_share_percentage=Decimal("0.01"),
            home_loan_interest_paid=Decimal("100000"),
        ),
        property_filing_details=[PropertyFilingDetail(
            address_detail="A", city_or_town_or_district="City", state_code="27",
            pin_code="400001", co_owned=True, assessee_share_percent=Decimal("0"),
            co_owner_details=[CoOwnerDetail(name="Co-owner", percent_share=Decimal("100"))],
        )],
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-HP-007")


# ─── Phase 6d: Schedule HP co-ownership (share sum, bounds, PAN cross-check) ─

def test_HP_010_co_owner_shares_summing_to_100_passes():
    inp = _base_input(
        house_property_income=_ONE_LET_OUT_PROPERTY,
        property_filing_details=[PropertyFilingDetail(
            address_detail="A", city_or_town_or_district="City", state_code="27",
            pin_code="400001", co_owned=True, assessee_share_percent=Decimal("60"),
            co_owner_details=[CoOwnerDetail(name="Co-owner", percent_share=Decimal("40"))],
        )],
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-HP-010")


def test_HP_010_co_owner_shares_not_summing_to_100_fails():
    """Regression for Phase 6d: ITR2-IN-HP-004 only checked the assessee's
    own share is < 100 when co-owned, never summed it against every
    CoOwnerDetail.percent_share -- a co-owned property whose shares don't
    actually add up to 100% could reach the JSON unchecked."""
    inp = _base_input(
        house_property_income=_ONE_LET_OUT_PROPERTY,
        property_filing_details=[PropertyFilingDetail(
            address_detail="A", city_or_town_or_district="City", state_code="27",
            pin_code="400001", co_owned=True, assessee_share_percent=Decimal("60"),
            co_owner_details=[CoOwnerDetail(name="Co-owner", percent_share=Decimal("30"))],
        )],
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-HP-010")


def test_HP_011_co_owner_with_percent_share_passes():
    inp = _base_input(
        house_property_income=_ONE_LET_OUT_PROPERTY,
        property_filing_details=[PropertyFilingDetail(
            address_detail="A", city_or_town_or_district="City", state_code="27",
            pin_code="400001", co_owned=True, assessee_share_percent=Decimal("60"),
            co_owner_details=[CoOwnerDetail(name="Co-owner", percent_share=Decimal("40"))],
        )],
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-HP-011")


def test_HP_011_co_owner_missing_percent_share_fails():
    """Regression for Phase 6d: CoOwnerDetail.percent_share is Optional at
    the schema level -- a co-owned property could name a co-owner with no
    share at all and reach the JSON unchecked."""
    inp = _base_input(
        house_property_income=_ONE_LET_OUT_PROPERTY,
        property_filing_details=[PropertyFilingDetail(
            address_detail="A", city_or_town_or_district="City", state_code="27",
            pin_code="400001", co_owned=True, assessee_share_percent=Decimal("60"),
            co_owner_details=[CoOwnerDetail(name="Co-owner")],
        )],
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-HP-011")


def test_HP_012_co_owner_share_within_bounds_passes():
    inp = _base_input(
        house_property_income=_ONE_LET_OUT_PROPERTY,
        property_filing_details=[PropertyFilingDetail(
            address_detail="A", city_or_town_or_district="City", state_code="27",
            pin_code="400001", co_owned=True, assessee_share_percent=Decimal("50"),
            co_owner_details=[CoOwnerDetail(name="Co-owner", percent_share=Decimal("50"))],
        )],
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-HP-012")


def test_HP_012_co_owner_share_of_zero_fails():
    inp = _base_input(
        house_property_income=_ONE_LET_OUT_PROPERTY,
        property_filing_details=[PropertyFilingDetail(
            address_detail="A", city_or_town_or_district="City", state_code="27",
            pin_code="400001", co_owned=True, assessee_share_percent=Decimal("100"),
            co_owner_details=[CoOwnerDetail(name="Co-owner", percent_share=Decimal("0"))],
        )],
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-HP-012")


def test_HP_013_co_owner_pan_differing_from_assessee_passes():
    profile = ITR2FilingProfile.model_construct(pan="ABCDE1234F", date_of_birth_or_formation=date(1990, 1, 1))
    inp = _base_input(
        filing_profile=profile,
        house_property_income=_ONE_LET_OUT_PROPERTY,
        property_filing_details=[PropertyFilingDetail(
            address_detail="A", city_or_town_or_district="City", state_code="27",
            pin_code="400001", co_owned=True, assessee_share_percent=Decimal("50"),
            co_owner_details=[CoOwnerDetail(
                name="Co-owner", pan="ZYXWV9876G", percent_share=Decimal("50"),
            )],
        )],
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-HP-013")


def test_HP_013_co_owner_pan_matching_assessee_fails():
    """Regression for Phase 6d: no cross-check anywhere compared
    CoOwnerDetail.pan against the filer's own filing_profile.pan --
    mirrors ITR-4's own already-shipped ITR4-R351-2."""
    profile = ITR2FilingProfile.model_construct(pan="ABCDE1234F", date_of_birth_or_formation=date(1990, 1, 1))
    inp = _base_input(
        filing_profile=profile,
        house_property_income=_ONE_LET_OUT_PROPERTY,
        property_filing_details=[PropertyFilingDetail(
            address_detail="A", city_or_town_or_district="City", state_code="27",
            pin_code="400001", co_owned=True, assessee_share_percent=Decimal("50"),
            co_owner_details=[CoOwnerDetail(
                name="Co-owner", pan="ABCDE1234F", percent_share=Decimal("50"),
            )],
        )],
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-HP-013")


def test_FSI_003_nonresident_fsi_fails():
    inp = _base_input(
        residential_status=ResidentialStatus.NON_RESIDENT,
        fsi_entries=[FSICountryEntry(country_code="US", tax_identification_no="TIN", salary_income=Decimal("100"))],
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-FSI-003")


def test_FSI_003_resident_fsi_passes():
    inp = _base_input(
        fsi_entries=[FSICountryEntry(country_code="US", tax_identification_no="TIN", salary_income=Decimal("100"))],
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-FSI-003")


def test_TR1_003_nonresident_tr_fails():
    inp = _base_input(
        residential_status=ResidentialStatus.NON_RESIDENT,
        fsi_entries=[FSICountryEntry(country_code="US", tax_identification_no="TIN", salary_income=Decimal("1"))],
        tr1_entries=[TR1Entry(country_code="US", tax_identification_no="TIN", tax_paid_outside_india=Decimal("10"))],
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-TR1-003")


def test_TR1_004_and_005_tin_reconciliation_fails():
    inp = _base_input(
        fsi_entries=[FSICountryEntry(country_code="US", tax_identification_no="TIN", salary_income=Decimal("100"), tax_paid_outside_india=Decimal("10"), tax_payable_in_india=Decimal("8"))],
        tr1_entries=[TR1Entry(country_code="US", tax_identification_no="TIN", income_included_in_this_return=Decimal("100"), tax_paid_outside_india=Decimal("9"), relief_claimed=Decimal("7"), indian_tax_payable=Decimal("7"))],
    )
    ids = {r.rule_id for r in validate_itr2_input(inp) if not r.passed}
    assert {"ITR2-IN-TR1-004", "ITR2-IN-TR1-005"} <= ids


def test_TDS_002_claim_exceeding_gross_income_fails():
    inp = _base_input(tds2_entries=[TDS2Entry(
        deductor_tan="MUMA12345B", tds_section="194A", gross_amount=Decimal("1000"),
        tds_deducted=Decimal("100"), tds_claimed_this_year=Decimal("1001"),
    )])
    assert failed(validate_itr2_input(inp), "ITR2-IN-TDS-002")


def test_TDS_003_salary_tds_without_salary_fails():
    inp = _base_input(tds1_entries=[{"employer_tan": "MUMA12345B", "tds_deducted": Decimal("10")}])
    assert failed(validate_itr2_input(inp), "ITR2-IN-TDS-003")


def test_TDS_004_salary_tds_over_salary_fails():
    inp = _base_input(
        salary_income=SalaryIncome(gross_salary=Decimal("1000")),
        tds1_entries=[{"employer_tan": "MUMA12345B", "tds_deducted": Decimal("1001")}],
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-TDS-004")


def test_FORM_003_relief_89_without_salary_fails():
    assert failed(validate_itr2_input(_base_input(relief_89=Decimal("100"))), "ITR2-IN-FORM-003")


def test_VIA_005_and_006_missing_disability_schedules_fail():
    inp = _base_input(deductions_chapter6a=Chapter6ADeductions(amount_80u=Decimal("1"), amount_80dd=Decimal("1")))
    ids = {r.rule_id for r in validate_itr2_input(inp) if not r.passed}
    assert {"ITR2-IN-VIA-005", "ITR2-IN-VIA-006"} <= ids


def test_VIA_007_huf_80dd_requires_member_relationship():
    profile = ITR2FilingProfile.model_construct(
        assessee_status=AssesseeStatus.HUF,
        residential_status=ResidentialStatus.RESIDENT,
        return_file_section=ReturnFileSection.ON_TIME_139_1,
        portuguese_civil_code_applies=False,
    )
    inp = _base_input(
        filing_profile=profile,
        deductions_chapter6a=Chapter6ADeductions(amount_80dd=Decimal("1"), schedule_80dd={}),
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-VIA-007")




def test_TDS_005_claim_without_gross_income_fails():
    inp = _base_input(tds2_entries=[TDS2Entry(
        deductor_tan="MUMA12345B", tds_section="194A", tds_claimed_this_year=Decimal("1"),
    )])
    assert failed(validate_itr2_input(inp), "ITR2-IN-TDS-005")


def test_TDS_006_current_and_brought_forward_same_row_fails():
    inp = _base_input(tds2_entries=[TDS2Entry(
        deductor_tan="MUMA12345B", tds_section="194A", gross_amount=Decimal("100"),
        tds_deducted=Decimal("10"), brought_forward_tds=Decimal("5"),
    )])
    assert failed(validate_itr2_input(inp), "ITR2-IN-TDS-006")


def test_TDS_007_carry_forward_arithmetic_fails():
    inp = _base_input(tds2_entries=[TDS2Entry(
        deductor_tan="MUMA12345B", tds_section="194A", tds_deducted=Decimal("10"),
        tds_credit_carried_forward=Decimal("9"),
    )])
    assert failed(validate_itr2_input(inp), "ITR2-IN-TDS-007")


def test_TDS_008_huf_salary_tds_fails():
    profile = ITR2FilingProfile.model_construct(
        assessee_status=AssesseeStatus.HUF,
        date_of_birth_or_formation=date(1990, 1, 1),
    )
    inp = _base_input(filing_profile=profile, tds1_entries=[{"tds_deducted": Decimal("1")}])
    assert failed(validate_itr2_input(inp), "ITR2-IN-TDS-008")


def test_TDS_009_claim_without_tds3_receipt_fails():
    inp = _base_input(tds3_entries=[{
        "tenant_pan": "ABCPN1234F", "tenant_name": "Tenant", "tds_section": "194IB",
        "tds_claimed": Decimal("1"), "tds_deducted": Decimal("1"),
    }])
    assert failed(validate_itr2_input(inp), "ITR2-IN-TDS-009")


def test_ESOP_001_balance_arithmetic_fails():
    inp = _base_input(esop_deferrals=[ESOPDeferralInput(
        employer_pan="ABCDE1234F", dpiit_registration_number="DIPP12345",
        assessment_year="2025-26", tax_deferred_brought_forward=Decimal("100"),
        tax_payable_current_year=Decimal("20"), balance_tax_carried_forward=Decimal("90"),
    )])
    assert failed(validate_itr2_input(inp), "ITR2-IN-ESOP-001")


def test_CG_009_late_115f_investment_fails():
    claim = CapitalGainExemptionClaim(
        section="115F", transfer_date=date(2025, 4, 1), eligible_gain=Decimal("100"),
        investment_amount=Decimal("100"), investment_date=date(2025, 11, 1),
    )
    inp = _base_input(cg_transactions=[CGTransaction(
        asset_type=CGAssetType.FOREIGN_ASSET, date_of_acquisition=date(2020, 1, 1),
        date_of_transfer=date(2025, 4, 1), full_consideration=Decimal("100"), exemptions=[claim],
    )])
    assert failed(validate_itr2_input(inp), "ITR2-IN-CG-009")




def test_TDS_010_and_011_section_192_non_salary_rows_fail():
    inp = _base_input(
        tds2_entries=[TDS2Entry(deductor_tan="MUMA12345B", tds_section="192")],
        tds3_entries=[{"tenant_pan": "ABCPN1234F", "tenant_name": "Tenant", "tds_section": "192"}],
    )
    ids = {r.rule_id for r in validate_itr2_input(inp) if not r.passed}
    assert {"ITR2-IN-TDS-010", "ITR2-IN-TDS-011"} <= ids


def test_PROFILE_001_birth_date_before_fy_passes():
    profile = ITR2FilingProfile.model_construct(date_of_birth_or_formation=date(1990, 1, 1))
    assert not failed(validate_itr2_input(_base_input(filing_profile=profile)), "ITR2-IN-PROFILE-001")


def test_PROFILE_001_birth_date_in_fy_fails():
    profile = ITR2FilingProfile.model_construct(date_of_birth_or_formation=date(2025, 4, 1))
    assert failed(validate_itr2_input(_base_input(filing_profile=profile)), "ITR2-IN-PROFILE-001")


def test_HP_008_interest_without_property_details_fails():
    inp = _base_input(house_properties=[HousePropertyIncome(
        property_type=PropertyType.SELF_OCCUPIED, home_loan_interest_paid=Decimal("1"),
    )])
    assert failed(validate_itr2_input(inp), "ITR2-IN-HP-008")


def test_VIA_010_and_011_80cch_ineligible_fails():
    profile = ITR2FilingProfile.model_construct(date_of_birth_or_formation=date(1990, 1, 1))
    inp = _base_input(
        filing_profile=profile,
        deductions_chapter6a=Chapter6ADeductions(amount_80cch=Decimal("1")),
    )
    ids = {r.rule_id for r in validate_itr2_input(inp) if not r.passed}
    assert {"ITR2-IN-VIA-010", "ITR2-IN-VIA-011"} <= ids


def test_CG_010_cgas_without_matching_account_fails():
    claim = CapitalGainExemptionClaim(
        section="54", transfer_date=date(2025, 4, 1), eligible_gain=Decimal("10"),
        investment_amount=Decimal("0"), cgas_deposit_amount=Decimal("10"),
        cgas_deposit_date=date(2025, 5, 1), cgas_account_number="123", cgas_ifsc="ABCD0123456",
    )
    tx = CGTransaction(asset_type=CGAssetType.LAND_BUILDING, date_of_acquisition=date(2020, 1, 1),
                       date_of_transfer=date(2025, 4, 1), full_consideration=Decimal("20"), exemptions=[claim])
    assert failed(validate_itr2_input(_base_input(cg_transactions=[tx])), "ITR2-IN-CG-010")


def test_CG_010_cgas_matching_account_passes():
    claim = CapitalGainExemptionClaim(
        section="54", transfer_date=date(2025, 4, 1), eligible_gain=Decimal("10"),
        investment_amount=Decimal("0"), cgas_deposit_amount=Decimal("10"),
        cgas_deposit_date=date(2025, 5, 1), cgas_account_number="123", cgas_ifsc="ABCD0123456",
    )
    tx = CGTransaction(asset_type=CGAssetType.LAND_BUILDING, date_of_acquisition=date(2020, 1, 1),
                       date_of_transfer=date(2025, 4, 1), full_consideration=Decimal("20"), exemptions=[claim])
    account = BankAccount(account_number="123", ifsc_code="ABCD0123456", account_type="CGAS")
    assert not failed(validate_itr2_input(_base_input(cg_transactions=[tx], bank_accounts=[account])), "ITR2-IN-CG-010")




def test_VIA_012_80ddb_without_disease_details_fails():
    inp = _base_input(deductions_chapter6a=Chapter6ADeductions(amount_80ddb=Decimal("1")))
    assert failed(validate_itr2_input(inp), "ITR2-IN-VIA-012")


def test_VIA_012_zero_80ddb_without_details_passes():
    inp = _base_input(deductions_chapter6a=Chapter6ADeductions())
    assert not failed(validate_itr2_input(inp), "ITR2-IN-VIA-012")




def test_HP_009_new_regime_self_occupied_interest_fails():
    inp = _base_input(
        tax_regime=TaxRegime.NEW,
        house_properties=[HousePropertyIncome(
            property_type=PropertyType.SELF_OCCUPIED,
            home_loan_interest_paid=Decimal("1"),
        )],
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-HP-009")


def test_CG_011_exemption_exceeding_eligible_gain_fails():
    claim = CapitalGainExemptionClaim(
        section="54", transfer_date=date(2025, 4, 1), eligible_gain=Decimal("10"),
        investment_amount=Decimal("11"), investment_date=date(2025, 5, 1),
    )
    tx = CGTransaction(
        asset_type=CGAssetType.LAND_BUILDING, date_of_acquisition=date(2020, 1, 1),
        date_of_transfer=date(2025, 4, 1), full_consideration=Decimal("20"), exemptions=[claim],
    )
    assert failed(validate_itr2_input(_base_input(cg_transactions=[tx])), "ITR2-IN-CG-011")


def test_CG_010_cgas_ifsc_mismatch_fails():
    claim = CapitalGainExemptionClaim(
        section="54", transfer_date=date(2025, 4, 1), eligible_gain=Decimal("20"),
        investment_amount=Decimal("0"), cgas_deposit_amount=Decimal("10"), cgas_deposit_date=date(2025, 5, 1),
        cgas_account_number="123", cgas_ifsc="ABCD0123456",
    )
    tx = CGTransaction(
        asset_type=CGAssetType.LAND_BUILDING, date_of_acquisition=date(2020, 1, 1),
        date_of_transfer=date(2025, 4, 1), full_consideration=Decimal("20"), exemptions=[claim],
    )
    account = BankAccount(account_number="123", ifsc_code="EFGH0123456", account_type="CGAS")
    assert failed(validate_itr2_input(_base_input(cg_transactions=[tx], bank_accounts=[account])), "ITR2-IN-CG-010")


def test_TDS_012_tds3_carry_forward_arithmetic_fails():
    inp = _base_input(tds3_entries=[{
        "tenant_pan": "ABCPN1234F", "tenant_name": "Tenant", "tds_section": "194IB",
        "tds_deducted": Decimal("10"), "tds_claimed": Decimal("2"),
        "tds_credit_carried_forward": Decimal("9"),
    }])
    assert failed(validate_itr2_input(inp), "ITR2-IN-TDS-012")




def test_PROFILE_002_resident_fpi_fails():
    profile = ITR2FilingProfile.model_construct(
        residential_status=ResidentialStatus.RESIDENT, is_fii_fpi=True,
        sebi_registration_number="INABFP123456",
    )
    assert failed(validate_itr2_input(_base_input(filing_profile=profile)), "ITR2-IN-PROFILE-002")


def test_PROFILE_003_seventh_proviso_without_amounts_fails():
    profile = ITR2FilingProfile.model_construct(seventh_proviso_139=True)
    assert failed(validate_itr2_input(_base_input(filing_profile=profile)), "ITR2-IN-PROFILE-003")


def test_REGIME_001_old_regime_after_due_date_fails():
    assert failed(validate_itr2_input(_base_input(
        filing_date=date(2026, 8, 1), due_date=date(2026, 7, 31),
    )), "ITR2-IN-REGIME-001")


def test_SAL_009_old_regime_standard_deduction_over_cap_fails():
    inp = _base_input(salary_income=SalaryIncome(
        gross_salary=Decimal("1000000"), standard_deduction_claimed=Decimal("50001"),
    ))
    assert failed(validate_itr2_input(inp), "ITR2-IN-SAL-009")


def test_SAL_010_professional_tax_over_cap_fails():
    inp = _base_input(salary_income=SalaryIncome(
        gross_salary=Decimal("1000000"), professional_tax_paid=Decimal("2501"),
    ))
    assert failed(validate_itr2_input(inp), "ITR2-IN-SAL-010")




def test_CG_101_to_108_zero_consideration_expense_fails():
    tx = CGTransaction.model_construct(
        asset_type=CGAssetType.LAND_BUILDING,
        date_of_transfer=date(2025, 4, 1),
        full_consideration=Decimal("0"),
        expenditure_on_transfer=Decimal("1"),
    )
    ids = {r.rule_id for r in validate_itr2_input(_base_input(cg_transactions=[tx])) if not r.passed}
    assert {f"ITR2-IN-CG-{number}" for number in range(101, 109)} <= ids


def test_CG_101_to_108_positive_consideration_expense_passes():
    tx = CGTransaction.model_construct(
        asset_type=CGAssetType.LAND_BUILDING,
        date_of_transfer=date(2025, 4, 1),
        full_consideration=Decimal("10"),
        expenditure_on_transfer=Decimal("1"),
    )
    ids = {r.rule_id for r in validate_itr2_input(_base_input(cg_transactions=[tx])) if not r.passed}
    assert not ({f"ITR2-IN-CG-{number}" for number in range(101, 109)} & ids)


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


def test_VIA_004_old_regime_80ee_and_80eea_are_mutually_exclusive():
    inp = _base_input(
        tax_regime=TaxRegime.OLD,
        deductions_chapter6a=Chapter6ADeductions(
            amount_80ee=Decimal("50000"), amount_80eea=Decimal("50000"),
        ),
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-VIA-004")


def test_VIA_004_old_regime_allows_either_80ee_deduction():
    inp = _base_input(
        tax_regime=TaxRegime.OLD,
        deductions_chapter6a=Chapter6ADeductions(amount_80eea=Decimal("50000")),
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-VIA-004")


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


def _employer_detail(**overrides) -> EmployerFilingDetail:
    fields = dict(
        employer_name="Test Employer Pvt Ltd", address_detail="123 Test Street",
        city_or_town_or_district="Mumbai", state_code="19",
    )
    fields.update(overrides)
    return EmployerFilingDetail(**fields)


def test_FE_001_zero_tds_salaried_employee_with_employer_detail_passes():
    """Regression for audit §22.3: a salaried employee whose employer
    deducted zero TDS (first job, income below the TDS threshold, a Section
    197 nil-deduction certificate) is a legitimate, common scenario --
    ITR2-IN-FE-001 used to require len(employer_filing_details) ==
    len(tds1_entries) unconditionally once employer_filing_details was
    non-empty, rejecting this case even though the real ITD builder
    (_schedule_s(), app/engine/itd/itr2.py) only enforces the count match
    when tds1_entries is itself non-empty."""
    inp = _base_input(
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        employer_filing_details=[_employer_detail()],
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-FE-001")


def test_FE_001_mismatched_employer_and_tds1_counts_cannot_even_be_constructed():
    """The count-match case this rule guards against is already blocked one
    layer up, at ITR2Input's own construction time
    (ITR2Input.validate_cross_schedule_contract, app/schemas/itr2.py:1148),
    which carries the identical `and self.tds1_entries` guard -- so a
    mismatched, non-empty-tds1_entries state can never reach the validator
    in the first place. This confirms the fix above closes ITR2-IN-FE-001's
    only remaining live effect (which was a false positive on the
    zero-TDS-entries case, not a real protection)."""
    from app.schemas.itr1 import TDS1Entry
    with pytest.raises(ValueError, match="employer_filing_details must contain one row per TDS1 employer"):
        _base_input(
            salary_income=SalaryIncome(gross_salary=Decimal("600000")),
            employer_filing_details=[_employer_detail(), _employer_detail()],
            tds1_entries=[TDS1Entry(
                employer_tan="MUMA12345B", employer_name="Test Employer Pvt Ltd",
                income_chargeable=Decimal("600000"), tds_deducted=Decimal("0"),
            )],
        )


# ── Category B/D advisories (Phase 6a) ──────────────────────────────────────

def _fsi_entry(**overrides) -> FSICountryEntry:
    fields = dict(
        country_code="US", tax_identification_no="123-45-6789",
        os_income=Decimal("100000"), tax_paid_outside_india=Decimal("20000"),
        tax_payable_in_india=Decimal("20000"),
    )
    fields.update(overrides)
    return FSICountryEntry(**fields)


def test_FORM_004_form67_reminder_emitted_when_relief_claimed_without_filing():
    inp = _base_input(
        fsi_entries=[_fsi_entry()],
        tr1_entries=[TR1Entry(
            country_code="US", tax_identification_no="123-45-6789",
            income_included_in_this_return=Decimal("100000"),
            tax_paid_outside_india=Decimal("20000"), indian_tax_payable=Decimal("20000"),
            relief_claimed=Decimal("15000"), relief_section="90", form67_filed=False,
        )],
    )
    assert emitted(validate_itr2_input(inp), "ITR2-IN-FORM-004")


def test_FORM_004_no_reminder_when_form67_already_filed():
    inp = _base_input(
        fsi_entries=[_fsi_entry()],
        tr1_entries=[TR1Entry(
            country_code="US", tax_identification_no="123-45-6789",
            income_included_in_this_return=Decimal("100000"),
            tax_paid_outside_india=Decimal("20000"), indian_tax_payable=Decimal("20000"),
            relief_claimed=Decimal("15000"), relief_section="90", form67_filed=True,
        )],
    )
    assert not emitted(validate_itr2_input(inp), "ITR2-IN-FORM-004")


def test_FORM_007_form10f_reminder_emitted_for_nonresident_treaty_relief_without_filing():
    """Regression for Phase 6i-1: TR1Entry had no way to record whether Form
    10F was filed at all -- Category B/D row #21 was deliberately deferred
    in Phase 6a for exactly this reason."""
    inp = _base_input(
        residential_status=ResidentialStatus.NON_RESIDENT,
        fsi_entries=[_fsi_entry()],
        tr1_entries=[TR1Entry(
            country_code="US", tax_identification_no="123-45-6789",
            income_included_in_this_return=Decimal("100000"),
            tax_paid_outside_india=Decimal("20000"), indian_tax_payable=Decimal("20000"),
            relief_claimed=Decimal("15000"), relief_section="90", form_10f_filed=False,
        )],
    )
    assert emitted(validate_itr2_input(inp), "ITR2-IN-FORM-007")


def test_FORM_007_no_reminder_when_form10f_already_filed():
    inp = _base_input(
        residential_status=ResidentialStatus.NON_RESIDENT,
        fsi_entries=[_fsi_entry()],
        tr1_entries=[TR1Entry(
            country_code="US", tax_identification_no="123-45-6789",
            income_included_in_this_return=Decimal("100000"),
            tax_paid_outside_india=Decimal("20000"), indian_tax_payable=Decimal("20000"),
            relief_claimed=Decimal("15000"), relief_section="90", form_10f_filed=True,
        )],
    )
    assert not emitted(validate_itr2_input(inp), "ITR2-IN-FORM-007")


def test_FORM_007_no_reminder_for_section_91_unilateral_relief():
    """Section 91 is unilateral relief (no treaty involved), so Form
    10F/TRC are not applicable -- only 90/90A are treaty-based."""
    inp = _base_input(
        residential_status=ResidentialStatus.NON_RESIDENT,
        fsi_entries=[_fsi_entry()],
        tr1_entries=[TR1Entry(
            country_code="US", tax_identification_no="123-45-6789",
            income_included_in_this_return=Decimal("100000"),
            tax_paid_outside_india=Decimal("20000"), indian_tax_payable=Decimal("20000"),
            relief_claimed=Decimal("15000"), relief_section="91", form_10f_filed=False,
        )],
    )
    assert not emitted(validate_itr2_input(inp), "ITR2-IN-FORM-007")


def test_FORM_007_no_reminder_for_resident():
    """Form 10F is mandatory for NON-residents specifically, per the rule's
    own literal text -- a resident claiming DTAA relief is out of scope."""
    inp = _base_input(
        residential_status=ResidentialStatus.RESIDENT,
        fsi_entries=[_fsi_entry()],
        tr1_entries=[TR1Entry(
            country_code="US", tax_identification_no="123-45-6789",
            income_included_in_this_return=Decimal("100000"),
            tax_paid_outside_india=Decimal("20000"), indian_tax_payable=Decimal("20000"),
            relief_claimed=Decimal("15000"), relief_section="90", form_10f_filed=False,
        )],
    )
    assert not emitted(validate_itr2_input(inp), "ITR2-IN-FORM-007")


def test_FORM_005_form3cfa_reminder_emitted_for_115bbf_income():
    inp = _base_input(si_entries=[ScheduleSIEntry(section="115BBF", gross_income=Decimal("500000"))])
    assert emitted(validate_itr2_input(inp), "ITR2-IN-FORM-005")


def test_FORM_005_no_reminder_for_other_si_sections():
    inp = _base_input(si_entries=[ScheduleSIEntry(section="115BB", gross_income=Decimal("500000"))])
    assert not emitted(validate_itr2_input(inp), "ITR2-IN-FORM-005")


def _dtaa_entry(**overrides) -> OSDtaaEntry:
    fields = dict(
        amount=Decimal("50000"), nature_of_income="1ai", country_name="United States",
        country_code="US", dtaa_article="11", rate_as_per_treaty=Decimal("15"),
        rate_as_per_it_act=Decimal("20"), item_no_incl="1ai",
    )
    fields.update(overrides)
    return OSDtaaEntry(**fields)


def test_DTAA_001_resident_claiming_os_dtaa_rate_emits_advisory():
    inp = _base_input(residential_status=ResidentialStatus.RESIDENT, os_dtaa_entries=[_dtaa_entry()])
    assert emitted(validate_itr2_input(inp), "ITR2-IN-DTAA-001")


def test_DTAA_001_no_advisory_for_non_resident():
    inp = _base_input(residential_status=ResidentialStatus.NON_RESIDENT, os_dtaa_entries=[_dtaa_entry()])
    assert not emitted(validate_itr2_input(inp), "ITR2-IN-DTAA-001")


def test_DTAA_002_applicable_rate_at_lower_of_treaty_and_it_act_passes():
    inp = _base_input(
        residential_status=ResidentialStatus.NON_RESIDENT,
        os_dtaa_entries=[_dtaa_entry(
            rate_as_per_treaty=Decimal("15"), rate_as_per_it_act=Decimal("20"),
            applicable_rate=Decimal("15"),
        )],
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-DTAA-002")


def test_DTAA_002_applicable_rate_exceeding_lower_of_treaty_and_it_act_fails():
    """Regression for Phase 6e: OSDtaaEntry.applicable_rate was a
    free-standing field with no check against min(treaty rate, IT Act
    rate) -- the whole point of a tax treaty is relief, never a worse rate
    than either side's own figure."""
    inp = _base_input(
        residential_status=ResidentialStatus.NON_RESIDENT,
        os_dtaa_entries=[_dtaa_entry(
            rate_as_per_treaty=Decimal("15"), rate_as_per_it_act=Decimal("20"),
            applicable_rate=Decimal("18"),
        )],
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-DTAA-002")


def _cg_dtaa_entry(**overrides) -> CGDtaaEntry:
    fields = dict(
        amount=Decimal("50000"), item_no_incl="A5e", country_name="United States",
        country_code="US", dtaa_article="11", rate_as_per_treaty=Decimal("15"),
        sec_it_act="112", rate_as_per_it_act=Decimal("20"),
    )
    fields.update(overrides)
    return CGDtaaEntry(**fields)


def test_DTAA_003_stcg_applicable_rate_at_lower_of_treaty_and_it_act_passes():
    """Phase 6i-5: CGDtaaEntry.applicable_rate is capped at min(treaty rate,
    IT Act rate) for the STCG-side DTAA table, mirroring ITR2-IN-DTAA-002's
    already-shipped OS-side check."""
    inp = _base_input(
        residential_status=ResidentialStatus.NON_RESIDENT,
        cg_stcg_dtaa_entries=[_cg_dtaa_entry(
            rate_as_per_treaty=Decimal("15"), rate_as_per_it_act=Decimal("20"),
            applicable_rate=Decimal("15"),
        )],
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-DTAA-003")


def test_DTAA_003_stcg_applicable_rate_exceeding_lower_of_treaty_and_it_act_fails():
    inp = _base_input(
        residential_status=ResidentialStatus.NON_RESIDENT,
        cg_stcg_dtaa_entries=[_cg_dtaa_entry(
            rate_as_per_treaty=Decimal("15"), rate_as_per_it_act=Decimal("20"),
            applicable_rate=Decimal("18"),
        )],
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-DTAA-003")


def test_DTAA_004_ltcg_applicable_rate_at_lower_of_treaty_and_it_act_passes():
    """Same check, LTCG side (Schedule CG item B11)."""
    inp = _base_input(
        residential_status=ResidentialStatus.NON_RESIDENT,
        cg_ltcg_dtaa_entries=[_cg_dtaa_entry(
            rate_as_per_treaty=Decimal("10"), rate_as_per_it_act=Decimal("12.5"),
            applicable_rate=Decimal("10"),
        )],
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-DTAA-004")


def test_DTAA_004_ltcg_applicable_rate_exceeding_lower_of_treaty_and_it_act_fails():
    inp = _base_input(
        residential_status=ResidentialStatus.NON_RESIDENT,
        cg_ltcg_dtaa_entries=[_cg_dtaa_entry(
            rate_as_per_treaty=Decimal("10"), rate_as_per_it_act=Decimal("12.5"),
            applicable_rate=Decimal("12"),
        )],
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-DTAA-004")


# ─── Phase 6f: Schedule OS ───────────────────────────────────────────────────

def test_OS_001_interest_expense_within_20pct_of_dividend_passes():
    inp = _base_input(
        other_sources_income=OtherSourcesIncome(dividend_income=Decimal("100000")),
        os_deductions=OSDeductions(interest_expense_us57=Decimal("20000")),
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-OS-001")


def test_OS_001_interest_expense_exceeding_20pct_of_dividend_fails():
    """Regression for Phase 6f: OSDeductions.interest_expense_us57 had no
    cap against dividend income anywhere -- CBDT rule 216 states this
    claim cannot exceed 20% of dividend income."""
    inp = _base_input(
        other_sources_income=OtherSourcesIncome(dividend_income=Decimal("100000")),
        os_deductions=OSDeductions(interest_expense_us57=Decimal("25000")),
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-OS-001")


def _pf_entry(**overrides):
    from app.schemas.itr2 import OSAccumulatedPFEntry
    fields = dict(assessment_year="2024-25", income_benefit=Decimal("10000"), tax_benefit=Decimal("2000"))
    fields.update(overrides)
    return OSAccumulatedPFEntry(**fields)


def test_OS_002_003_pf_totals_matching_detail_rows_passes():
    inp = _base_input(
        os_pf_income_benefit=Decimal("10000"), os_pf_tax_benefit=Decimal("2000"),
        os_pf_accumulated_entries=[_pf_entry()],
    )
    results = validate_itr2_input(inp)
    assert not failed(results, "ITR2-IN-OS-002")
    assert not failed(results, "ITR2-IN-OS-003")


def test_OS_002_003_pf_totals_disagreeing_with_detail_rows_fails():
    """Regression for Phase 6f: TaxAccumulatedBalRecPF's header totals
    (os_pf_income_benefit/os_pf_tax_benefit) were never reconciled against
    their own per-assessment-year detail rows anywhere."""
    inp = _base_input(
        os_pf_income_benefit=Decimal("99999"), os_pf_tax_benefit=Decimal("88888"),
        os_pf_accumulated_entries=[_pf_entry()],
    )
    results = validate_itr2_input(inp)
    assert failed(results, "ITR2-IN-OS-002")
    assert failed(results, "ITR2-IN-OS-003")


def test_OS_004_race_horse_balance_matching_formula_passes():
    from app.schemas.itr2 import OSRaceHorseActivity
    inp = _base_input(os_race_horse=OSRaceHorseActivity(
        receipts=Decimal("100000"), deduction_us57=Decimal("30000"),
        amount_not_deductible_us58=Decimal("5000"), profit_chargeable_us59=Decimal("2000"),
        balance=Decimal("77000"),
    ))
    assert not failed(validate_itr2_input(inp), "ITR2-IN-OS-004")


def test_OS_005_individual_claiming_89a_relief_passes():
    inp = _base_input(
        filing_profile=_filing_profile(AssesseeStatus.INDIVIDUAL),
        os_section_89a=OSSection89A(income_notified=Decimal("200000"), relief=Decimal("50000")),
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-OS-005")


def test_OS_005_huf_claiming_89a_relief_fails():
    """Regression for Phase 6g: Section 89A (foreign-retirement-account
    income deferral) is only available to individuals -- nothing prevented
    an HUF from claiming it."""
    huf_profile = ITR2FilingProfile(
        pan="ABCPN1234F", assessee_status=AssesseeStatus.HUF, surname_or_org_name="Nair HUF",
        date_of_birth_or_formation=date(1985, 6, 15), father_name="Ramesh Nair",
        verification_place="Mumbai", verification_capacity="K", karta_pan="ABCPX1234F",
        primary_address=FilingAddress(
            residence_no="12", locality_or_area="MG Road", city_or_town_or_district="Mumbai",
            state_code="27", mobile_no="9876543210", email="priya@example.com",
        ),
    )
    inp = _base_input(
        filing_profile=huf_profile,
        os_section_89a=OSSection89A(income_notified=Decimal("200000"), relief=Decimal("50000")),
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-OS-005")


def test_OS_006_89a_relief_within_notified_income_passes():
    inp = _base_input(os_section_89a=OSSection89A(income_notified=Decimal("200000"), relief=Decimal("200000")))
    assert not failed(validate_itr2_input(inp), "ITR2-IN-OS-006")


def test_OS_006_89a_relief_exceeding_notified_income_fails():
    """Regression for Phase 6g: OSSection89A.relief had no cap against
    income_notified anywhere -- also structurally closes CBDT rule #226
    (relief allowed only if income is offered in Sl.1e), since a nonzero
    relief against a zero income_notified fails this same check."""
    inp = _base_input(os_section_89a=OSSection89A(income_notified=Decimal("100000"), relief=Decimal("150000")))
    assert failed(validate_itr2_input(inp), "ITR2-IN-OS-006")


def test_OS_006_89a_relief_without_notified_income_fails():
    inp = _base_input(os_section_89a=OSSection89A(income_notified=Decimal("0"), relief=Decimal("1")))
    assert failed(validate_itr2_input(inp), "ITR2-IN-OS-006")


def test_OS_004_race_horse_balance_not_matching_formula_fails():
    """Regression for Phase 6f: OSRaceHorseActivity.balance is trusted as
    raw user input with no recomputation from its own components (receipts
    - deduction u/s 57 + amounts not deductible u/s 58 + profits
    chargeable u/s 59), the form's own stated Sl.8e formula."""
    from app.schemas.itr2 import OSRaceHorseActivity
    inp = _base_input(os_race_horse=OSRaceHorseActivity(
        receipts=Decimal("100000"), deduction_us57=Decimal("30000"),
        amount_not_deductible_us58=Decimal("5000"), profit_chargeable_us59=Decimal("2000"),
        balance=Decimal("999999"),
    ))
    assert failed(validate_itr2_input(inp), "ITR2-IN-OS-004")


def _tds2(**overrides) -> TDS2Entry:
    fields = dict(deductor_tan="MUMA12345B", tds_section="194A", gross_amount=Decimal("100000"))
    fields.update(overrides)
    return TDS2Entry(**fields)


def _tds3(**overrides) -> TDS3Entry:
    fields = dict(tenant_pan="ABCPN1234F", tenant_name="Tenant Name", tds_section="195")
    fields.update(overrides)
    return TDS3Entry(**fields)


def test_TDS_013_business_indicating_section_under_tds2_emits_advisory():
    inp = _base_input(tds2_entries=[_tds2(tds_section="194Q")])
    assert emitted(validate_itr2_input(inp), "ITR2-IN-TDS-013")


def test_TDS_013_no_advisory_for_ordinary_interest_tds():
    inp = _base_input(tds2_entries=[_tds2(tds_section="194A")])
    assert not emitted(validate_itr2_input(inp), "ITR2-IN-TDS-013")


def test_TDS_014_business_indicating_section_under_tds3_emits_advisory():
    inp = _base_input(tds3_entries=[_tds3(tds_section="194C")])
    assert emitted(validate_itr2_input(inp), "ITR2-IN-TDS-014")


def test_TDS_014_no_advisory_for_ordinary_tds3_section():
    inp = _base_input(tds3_entries=[_tds3(tds_section="195")])
    assert not emitted(validate_itr2_input(inp), "ITR2-IN-TDS-014")


def test_TDS_015_vda_tds_without_vda_transaction_emits_advisory():
    inp = _base_input(tds2_entries=[_tds2(tds_section="194S")])
    assert emitted(validate_itr2_input(inp), "ITR2-IN-TDS-015")


def test_TDS_015_no_advisory_when_vda_transaction_is_disclosed():
    inp = _base_input(
        tds2_entries=[_tds2(tds_section="194S")],
        vda_transactions=[VDATransaction(
            date_of_acquisition=date(2025, 4, 1), date_of_transfer=date(2025, 6, 1),
            acquisition_cost=Decimal("10000"), consideration_received=Decimal("15000"),
        )],
    )
    assert not emitted(validate_itr2_input(inp), "ITR2-IN-TDS-015")


def test_TDS_016_lottery_tds_without_115bb_income_emits_advisory():
    inp = _base_input(tds2_entries=[_tds2(tds_section="194B")])
    assert emitted(validate_itr2_input(inp), "ITR2-IN-TDS-016")


def test_TDS_016_no_advisory_when_115bb_income_disclosed():
    inp = _base_input(
        tds2_entries=[_tds2(tds_section="194B")],
        si_entries=[ScheduleSIEntry(section="115BB", gross_income=Decimal("10000"))],
    )
    assert not emitted(validate_itr2_input(inp), "ITR2-IN-TDS-016")


def test_TDS_017_race_horse_tds_without_115bb_income_emits_advisory():
    inp = _base_input(tds2_entries=[_tds2(tds_section="194BB")])
    assert emitted(validate_itr2_input(inp), "ITR2-IN-TDS-017")


def test_TDS_017_no_advisory_when_115bb_income_disclosed():
    inp = _base_input(
        tds2_entries=[_tds2(tds_section="194BB")],
        si_entries=[ScheduleSIEntry(section="115BB", gross_income=Decimal("10000"))],
    )
    assert not emitted(validate_itr2_input(inp), "ITR2-IN-TDS-017")


def test_TDS_018_online_games_tds_without_115bbj_income_emits_advisory():
    inp = _base_input(tds2_entries=[_tds2(tds_section="194BA")])
    assert emitted(validate_itr2_input(inp), "ITR2-IN-TDS-018")


def test_TDS_018_no_advisory_when_115bbj_income_disclosed():
    inp = _base_input(
        tds2_entries=[_tds2(tds_section="194BA")],
        si_entries=[ScheduleSIEntry(section="115BBJ", gross_income=Decimal("10000"))],
    )
    assert not emitted(validate_itr2_input(inp), "ITR2-IN-TDS-018")


def test_FORM_006_form10ee_reminder_emitted_for_section_89a_income():
    inp = _base_input(os_section_89a=OSSection89A(income_notified=Decimal("200000")))
    assert emitted(validate_itr2_input(inp), "ITR2-IN-FORM-006")


def test_FORM_006_no_reminder_without_section_89a_income():
    inp = _base_input(os_section_89a=OSSection89A())
    assert not emitted(validate_itr2_input(inp), "ITR2-IN-FORM-006")


def test_TDS_019_section_194m_emits_advisory():
    inp = _base_input(tds2_entries=[_tds2(tds_section="194M")])
    assert emitted(validate_itr2_input(inp), "ITR2-IN-TDS-019")


def test_TDS_019_no_advisory_for_other_sections():
    inp = _base_input(tds2_entries=[_tds2(tds_section="194A")])
    assert not emitted(validate_itr2_input(inp), "ITR2-IN-TDS-019")


def test_CG_012_indexed_cost_mismatch_emits_advisory():
    inp = _base_input(cg_transactions=[CGTransaction(
        asset_type=CGAssetType.LISTED_SECURITY,
        date_of_acquisition=date(2015, 4, 1), date_of_transfer=date(2020, 6, 1),
        full_consideration=Decimal("500000"), cost_of_acquisition=Decimal("100000"),
        indexed_cost=Decimal("999999"),
    )])
    assert emitted(validate_itr2_input(inp), "ITR2-IN-CG-012")


def _loan_80ee_entry(**overrides):
    from app.schemas.itr1 import EducationLoanLenderType, ITR1Schedule80EELoanEntry
    fields = dict(
        loan_taken_from=EducationLoanLenderType.BANK, lender_name="HDFC Bank",
        account_or_reference_number="HL123456", loan_date=date(2016, 6, 1),
        total_loan_amount=Decimal("2000000"), outstanding_loan_amount=Decimal("1500000"),
        interest_paid=Decimal("50000"),
    )
    fields.update(overrides)
    return ITR1Schedule80EELoanEntry(**fields)


def test_VIA_009_80ee_loan_amount_within_ceiling_passes():
    inp = _base_input(
        deductions_chapter6a=Chapter6ADeductions(amount_80ee=Decimal("50000")),
        loan_details_80ee_list=[_loan_80ee_entry(total_loan_amount=Decimal("3000000"))],
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-VIA-009")


def test_VIA_009_80ee_loan_amount_exceeding_ceiling_fails():
    """Regression for Phase 6b: ITR-2 was missing the ₹35,00,000 Section 80EE
    loan-principal ceiling ITR-1/ITR-4 already enforce (ITR1-R227) for the
    identical loan_details_80ee_list.total_loan_amount field."""
    inp = _base_input(
        deductions_chapter6a=Chapter6ADeductions(amount_80ee=Decimal("50000")),
        loan_details_80ee_list=[_loan_80ee_entry(total_loan_amount=Decimal("4000000"))],
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-VIA-009")


def test_CG_012_no_advisory_when_indexed_cost_matches_formula():
    from app.engine.schedules.capital_gains import _indexed_cost
    acq, xfer = date(2015, 4, 1), date(2020, 6, 1)
    correct = _indexed_cost(Decimal("100000"), acq.isoformat(), xfer.isoformat())
    inp = _base_input(cg_transactions=[CGTransaction(
        asset_type=CGAssetType.LISTED_SECURITY,
        date_of_acquisition=acq, date_of_transfer=xfer,
        full_consideration=Decimal("500000"), cost_of_acquisition=Decimal("100000"),
        indexed_cost=correct,
    )])
    assert not emitted(validate_itr2_input(inp), "ITR2-IN-CG-012")


# ─── Phase 6c: Schedule S (salary) genuine gaps ─────────────────────────────

def test_SAL_011_gratuity_within_25l_ceiling_for_cg_employee_passes():
    inp = _base_input(
        salary_income=SalaryIncome(gross_salary=Decimal("2000000"), gratuity_received=Decimal("2500000")),
        employer_filing_details=[_employer_detail(nature_of_employment="CGOV")],
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-SAL-011")


def test_SAL_011_gratuity_exceeding_25l_ceiling_for_sg_pensioner_fails():
    inp = _base_input(
        salary_income=SalaryIncome(gross_salary=Decimal("2000000"), gratuity_received=Decimal("3000000")),
        employer_filing_details=[_employer_detail(nature_of_employment="PESG")],
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-SAL-011")


def test_SAL_012_gratuity_within_20l_ceiling_for_psu_employee_passes():
    inp = _base_input(
        salary_income=SalaryIncome(gross_salary=Decimal("2000000"), gratuity_received=Decimal("2000000")),
        employer_filing_details=[_employer_detail(nature_of_employment="PSU")],
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-SAL-012")


def test_SAL_012_gratuity_exceeding_20l_ceiling_for_others_fails():
    """Regression for Phase 6c: ITR-2 had zero gratuity-ceiling validator at
    all -- unlike ITR-1/ITR-4, which at least implement the coarser
    is_cg_sg-vs-not split (missing the CG/SG-Pensioner nuance ITR-2's own
    validator now correctly implements)."""
    inp = _base_input(
        salary_income=SalaryIncome(gross_salary=Decimal("3000000"), gratuity_received=Decimal("2500000")),
        employer_filing_details=[_employer_detail(nature_of_employment="OTH")],
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-SAL-012")


def test_SAL_013_retrenchment_compensation_for_private_employee_passes():
    inp = _base_input(
        salary_income=SalaryIncome(gross_salary=Decimal("500000"), retrenchment_compensation=Decimal("300000")),
        employer_filing_details=[_employer_detail(nature_of_employment="OTH")],
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-SAL-013")


def test_SAL_013_retrenchment_compensation_for_cg_pensioner_fails():
    """Regression for Phase 6c: Section 10(10B) retrenchment-compensation
    exemption is not available to Government employees/pensioners -- ITR-2
    had no eligibility gate at all (salary.py's retrenchment_exempt() takes
    no is_govt/is_cg_sg parameter, unlike its gratuity/leave-encashment/
    commuted-pension siblings)."""
    inp = _base_input(
        salary_income=SalaryIncome(gross_salary=Decimal("500000"), retrenchment_compensation=Decimal("300000")),
        employer_filing_details=[_employer_detail(nature_of_employment="PE")],
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-SAL-013")


def test_SAL_014_only_vrs_compensation_claimed_passes():
    inp = _base_input(salary_income=SalaryIncome(
        gross_salary=Decimal("500000"), vrs_compensation=Decimal("300000"),
    ))
    assert not failed(validate_itr2_input(inp), "ITR2-IN-SAL-014")


def test_SAL_014_vrs_and_retrenchment_compensation_both_claimed_fails():
    inp = _base_input(salary_income=SalaryIncome(
        gross_salary=Decimal("500000"),
        vrs_compensation=Decimal("100000"), retrenchment_compensation=Decimal("100000"),
    ))
    assert failed(validate_itr2_input(inp), "ITR2-IN-SAL-014")


def test_SAL_015_hra_exemption_matching_formula_passes():
    # Basic+DA = 300000; 50% (metro) = 150000; rent - 10% = 200000-30000 = 170000;
    # HRA received = 120000. min(120000, 170000, 150000) = 120000.
    inp = _base_input(
        salary_income=SalaryIncome(gross_salary=Decimal("500000"), hra_exempt_amount=Decimal("120000")),
        employer_filing_details=[_employer_detail(
            actual_hra_received=Decimal("120000"), actual_rent_paid=Decimal("200000"),
            salary_for_hra=Decimal("300000"), is_metro_city=True,
        )],
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-SAL-015")


def test_SAL_015_hra_exemption_exceeding_formula_fails():
    """Regression for Phase 6c: app/engine/itd/itr2.py's own Schedule
    10(13A) builder already hard-`raise`s ValueError on this exact mismatch
    -- this validator surfaces the identical check as a clean pre-compute
    message instead of a raw builder crash."""
    inp = _base_input(
        salary_income=SalaryIncome(gross_salary=Decimal("500000"), hra_exempt_amount=Decimal("160000")),
        employer_filing_details=[_employer_detail(
            actual_hra_received=Decimal("200000"), actual_rent_paid=Decimal("200000"),
            salary_for_hra=Decimal("300000"), is_metro_city=True,
        )],
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-SAL-015")


# ─── Phase 6i-3: gratuity/commuted-pension per-employer attribution ────────

def test_SAL_016_gratuity_claimed_against_two_employers_fails():
    inp = _base_input(
        salary_income=SalaryIncome(gross_salary=Decimal("2500000"), gratuity_received=Decimal("2000000")),
        employer_filing_details=[
            _employer_detail(employer_name="Employer A", gratuity_received=Decimal("1000000")),
            _employer_detail(employer_name="Employer B", gratuity_received=Decimal("1000000")),
        ],
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-SAL-016")


def test_SAL_016_gratuity_claimed_against_only_one_of_two_employers_passes():
    """A mid-year job change is the common legitimate multi-employer case --
    gratuity requires 5+ years' service, so a same-year new hire can never
    also show gratuity, and this must not false-positive."""
    inp = _base_input(
        salary_income=SalaryIncome(gross_salary=Decimal("2500000"), gratuity_received=Decimal("1000000")),
        employer_filing_details=[
            _employer_detail(employer_name="Old Employer", gratuity_received=Decimal("1000000")),
            _employer_detail(employer_name="New Employer"),
        ],
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-SAL-016")


def test_SAL_017_commuted_pension_claimed_against_two_employers_fails():
    inp = _base_input(
        salary_income=SalaryIncome(gross_salary=Decimal("1500000"), commuted_pension_received=Decimal("600000")),
        employer_filing_details=[
            _employer_detail(employer_name="Employer A", commuted_pension_received=Decimal("300000")),
            _employer_detail(employer_name="Employer B", commuted_pension_received=Decimal("300000")),
        ],
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-SAL-017")


def test_SAL_017_commuted_pension_claimed_against_only_one_of_two_employers_passes():
    inp = _base_input(
        salary_income=SalaryIncome(gross_salary=Decimal("1500000"), commuted_pension_received=Decimal("300000")),
        employer_filing_details=[
            _employer_detail(employer_name="Old Employer", commuted_pension_received=Decimal("300000")),
            _employer_detail(employer_name="New Employer"),
        ],
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-SAL-017")


# ─── Phase 6j-1: remaining Schedule S rows (#30/#31/#44/#49/#50/#52/#63/#64/#65) ──

def test_SAL_018_non_hra_exempt_allowances_exceeding_gross_less_hra_fails():
    inp = _base_input(salary_income=SalaryIncome(
        gross_salary=Decimal("500000"), lta_amount_received=Decimal("100000"),
        lta_exempt_amount=Decimal("100000"), sec10_6_embassy_exempt=Decimal("450000"),
    ))
    assert failed(validate_itr2_input(inp), "ITR2-IN-SAL-018")


def test_SAL_018_non_hra_exempt_allowances_within_ceiling_passes():
    inp = _base_input(salary_income=SalaryIncome(
        gross_salary=Decimal("500000"), lta_amount_received=Decimal("50000"),
        lta_exempt_amount=Decimal("50000"),
    ))
    assert not failed(validate_itr2_input(inp), "ITR2-IN-SAL-018")


def test_SAL_019_commuted_pension_received_exceeding_gross_salary_fails():
    inp = _base_input(salary_income=SalaryIncome(
        gross_salary=Decimal("200000"), commuted_pension_received=Decimal("300000"),
    ))
    assert failed(validate_itr2_input(inp), "ITR2-IN-SAL-019")


def test_SAL_019_commuted_pension_received_within_gross_salary_passes():
    inp = _base_input(salary_income=SalaryIncome(
        gross_salary=Decimal("500000"), commuted_pension_received=Decimal("100000"),
    ))
    assert not failed(validate_itr2_input(inp), "ITR2-IN-SAL-019")


def test_SAL_020_other_section10_exempt_exceeding_other_allowances_received_fails():
    inp = _base_input(salary_income=SalaryIncome(
        gross_salary=Decimal("500000"), other_allowances_received=Decimal("10000"),
        other_section10_exempt=Decimal("20000"),
    ))
    assert failed(validate_itr2_input(inp), "ITR2-IN-SAL-020")


def test_SAL_020_other_section10_exempt_within_other_allowances_received_passes():
    inp = _base_input(salary_income=SalaryIncome(
        gross_salary=Decimal("500000"), other_allowances_received=Decimal("20000"),
        other_section10_exempt=Decimal("10000"),
    ))
    assert not failed(validate_itr2_input(inp), "ITR2-IN-SAL-020")


def test_SAL_021_80gg_exceeding_55000_with_hra_claimed_fails():
    inp = _base_input(
        salary_income=SalaryIncome(gross_salary=Decimal("500000"), hra_exempt_amount=Decimal("10000")),
        deductions_chapter6a=Chapter6ADeductions(amount_80gg=Decimal("60000")),
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-SAL-021")


def test_SAL_021_80gg_within_55000_with_hra_claimed_passes():
    inp = _base_input(
        salary_income=SalaryIncome(gross_salary=Decimal("500000"), hra_exempt_amount=Decimal("10000")),
        deductions_chapter6a=Chapter6ADeductions(amount_80gg=Decimal("50000")),
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-SAL-021")


def test_SAL_022_duplicate_perquisite_nature_code_fails():
    inp = _base_input(
        salary_income=SalaryIncome(gross_salary=Decimal("500000")),
        employer_filing_details=[_employer_detail(nature_of_perquisites_rows=[
            {"NatureDesc": "MotorCar", "OthAmount": 1000},
            {"NatureDesc": "MotorCar", "OthAmount": 2000},
        ])],
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-SAL-022")


def test_SAL_022_unique_perquisite_nature_codes_pass():
    inp = _base_input(
        salary_income=SalaryIncome(gross_salary=Decimal("500000")),
        employer_filing_details=[_employer_detail(nature_of_perquisites_rows=[
            {"NatureDesc": "MotorCar", "OthAmount": 1000},
            {"NatureDesc": "Accommodation", "OthAmount": 2000},
        ])],
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-SAL-022")


def test_SAL_023_duplicate_profit_in_lieu_nature_code_fails():
    inp = _base_input(
        salary_income=SalaryIncome(gross_salary=Decimal("500000")),
        employer_filing_details=[_employer_detail(nature_of_profit_in_lieu_rows=[
            {"NatureDesc": "Compensation", "OthAmount": 1000},
            {"NatureDesc": "Compensation", "OthAmount": 2000},
        ])],
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-SAL-023")


def test_SAL_024_duplicate_89a_country_per_employer_fails():
    inp = _base_input(
        salary_income=SalaryIncome(gross_salary=Decimal("500000")),
        employer_filing_details=[_employer_detail(income_notified_89a_country_rows=[
            OS89ACountryEntry(country_code="US", amount=Decimal("1000")),
            OS89ACountryEntry(country_code="US", amount=Decimal("2000")),
        ])],
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-SAL-024")


def test_SAL_024_unique_89a_countries_per_employer_pass():
    inp = _base_input(
        salary_income=SalaryIncome(gross_salary=Decimal("500000")),
        employer_filing_details=[_employer_detail(income_notified_89a_country_rows=[
            OS89ACountryEntry(country_code="US", amount=Decimal("1000")),
            OS89ACountryEntry(country_code="UK", amount=Decimal("2000")),
        ])],
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-SAL-024")


# ─── Phase 6c: Section 80CCH PRAN + hard cap + percentage cap ───────────────

def test_VIA_013_80cch_with_pran_passes_pran_check():
    profile = ITR2FilingProfile.model_construct(date_of_birth_or_formation=date(2005, 1, 1))
    inp = _base_input(
        filing_profile=profile,
        salary_income=SalaryIncome(gross_salary=Decimal("500000")),
        deductions_chapter6a=Chapter6ADeductions(amount_80cch=Decimal("100000")),
        employer_filing_details=[_employer_detail(nature_of_employment="CGOV")],
        pran_number="123456789012",
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-VIA-013")


def test_VIA_013_80cch_without_pran_fails():
    profile = ITR2FilingProfile.model_construct(date_of_birth_or_formation=date(2005, 1, 1))
    inp = _base_input(
        filing_profile=profile,
        salary_income=SalaryIncome(gross_salary=Decimal("500000")),
        deductions_chapter6a=Chapter6ADeductions(amount_80cch=Decimal("100000")),
        employer_filing_details=[_employer_detail(nature_of_employment="CGOV")],
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-VIA-013")


def test_VIA_014_80cch_within_absolute_cap_passes():
    profile = ITR2FilingProfile.model_construct(date_of_birth_or_formation=date(2005, 1, 1))
    inp = _base_input(
        filing_profile=profile,
        salary_income=SalaryIncome(gross_salary=Decimal("10000000")),
        deductions_chapter6a=Chapter6ADeductions(amount_80cch=Decimal("288000")),
        employer_filing_details=[_employer_detail(nature_of_employment="CGOV")],
        pran_number="123456789012",
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-VIA-014")


def test_VIA_014_80cch_exceeding_absolute_cap_fails():
    """Regression for Phase 6c: this un-retracts and corrects the Phase 6b
    (2026-09-11) decision to retract the 80CCH cap finding -- that retraction
    was made without checking the primary CBDT PDF sources directly. ITR-1's
    ITR1-R186h and ITR-4's equivalent already enforce this identical
    ₹2,88,000 absolute cap; ITR-2 had none."""
    profile = ITR2FilingProfile.model_construct(date_of_birth_or_formation=date(2005, 1, 1))
    inp = _base_input(
        filing_profile=profile,
        salary_income=SalaryIncome(gross_salary=Decimal("10000000")),
        deductions_chapter6a=Chapter6ADeductions(amount_80cch=Decimal("300000")),
        employer_filing_details=[_employer_detail(nature_of_employment="CGOV")],
        pran_number="123456789012",
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-VIA-014")


def test_VIA_015_80cch_within_46_2_pct_of_salary_passes():
    profile = ITR2FilingProfile.model_construct(date_of_birth_or_formation=date(2005, 1, 1))
    inp = _base_input(
        filing_profile=profile,
        salary_income=SalaryIncome(gross_salary=Decimal("500000")),
        deductions_chapter6a=Chapter6ADeductions(amount_80cch=Decimal("200000")),
        employer_filing_details=[_employer_detail(nature_of_employment="CGOV")],
        pran_number="123456789012",
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-VIA-015")


def test_VIA_015_80cch_exceeding_46_2_pct_of_salary_fails():
    """Regression for Phase 6c: ITR-2's own official PDF text states a
    conflicting '60% of salary' figure (rule #347) with no absolute cap
    mentioned -- deliberately not followed since Section 80CCH is one Income
    Tax Act provision and ITR-1/ITR-4's official PDFs both independently
    state 46.2%/₹2,88,000 instead; see this rule's own code comment."""
    profile = ITR2FilingProfile.model_construct(date_of_birth_or_formation=date(2005, 1, 1))
    inp = _base_input(
        filing_profile=profile,
        salary_income=SalaryIncome(gross_salary=Decimal("500000")),
        deductions_chapter6a=Chapter6ADeductions(amount_80cch=Decimal("250000")),
        employer_filing_details=[_employer_detail(nature_of_employment="CGOV")],
        pran_number="123456789012",
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-VIA-015")
