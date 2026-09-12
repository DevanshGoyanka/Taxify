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
from pydantic import ValidationError

from app.engine.validators.itr2.input_rules import validate_itr2_input
from app.schemas.itr1 import (
    BankAccount,
    Chapter6ADeductions,
    DependentRelationship,
    Donation80G,
    FilingAddress,
    HousePropertyIncome,
    ITR1Schedule80EEALoanEntry,
    ITR1Schedule80EEBLoanEntry,
    ITR1Schedule80EELoanEntry,
    Donation80GGA,
    DonationAddress,
    InsurancePolicy,
    OtherSourcesIncome,
    PoliticalContribution,
    Schedule80CCCEntry,
    PropertyType,
    SalaryIncome,
    Section80GGAClause,
    TaxPaymentDetail,
    Schedule80CEntry,
    Schedule80D,
    Schedule80DD,
    Schedule80EEntry,
    Schedule80GGA,
    Schedule80GGC,
    Schedule80U,
    TaxRegime,
    TCSEntry,
    TDS2Entry,
    TDS3Entry,
)
from app.schemas.itr2 import (
    AgeBracket,
    AssesseeRepresentativeProfile,
    AssesseeStatus,
    CG112AScrip,
    CGAssetType,
    CGDtaaEntry,
    CGTransaction,
    ITR2FilingProfile,
    ITR2Input,
    AMTInput,
    ESOPDeferralInput,
    CapitalGainExemptionClaim,
    CoOwnerDetail,
    EmployerFilingDetail,
    PropertyFilingDetail,
    ReturnFileSection,
    ResidentialStatus,
    FSICountryEntry,
    HomeLoanDetail,
    OS89ACountryEntry,
    OSDeductions,
    OSDividendEntry,
    OSDtaaEntry,
    OSGiftBreakdown,
    OSQuarterlyAmount,
    OSOtherIncomeEntry,
    OSSection89A,
    OSSpecialRateEntry,
    PTIEntry,
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
    inp = _base_input(
        filing_profile=_filing_profile(AssesseeStatus.HUF),
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
    inp = _base_input(
        filing_profile=_filing_profile(AssesseeStatus.HUF),
        tds1_entries=[{"tds_deducted": Decimal("1")}],
    )
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


def test_ESOP_002_payable_nonzero_without_sale_or_cessation_fails():
    """CBDT rule #482: not sold + not ceased forces Sl.7 (tax payable) to zero."""
    inp = _base_input(esop_deferrals=[ESOPDeferralInput(
        employer_pan="ABCDE1234F", dpiit_registration_number="DIPP12345",
        assessment_year="2025-26", tax_deferred_brought_forward=Decimal("100"),
        tax_payable_current_year=Decimal("20"), balance_tax_carried_forward=Decimal("80"),
        security_type="NS", ceased_employee=False,
    )])
    assert failed(validate_itr2_input(inp), "ITR2-IN-ESOP-002")


def test_ESOP_002_payable_zero_without_sale_or_cessation_passes():
    inp = _base_input(esop_deferrals=[ESOPDeferralInput(
        employer_pan="ABCDE1234F", dpiit_registration_number="DIPP12345",
        assessment_year="2025-26", tax_deferred_brought_forward=Decimal("100"),
        tax_payable_current_year=Decimal("0"), balance_tax_carried_forward=Decimal("100"),
        security_type="NS", ceased_employee=False,
    )])
    assert not failed(validate_itr2_input(inp), "ITR2-IN-ESOP-002")


def test_ESOP_002_sold_security_with_nonzero_payable_passes():
    inp = _base_input(esop_deferrals=[ESOPDeferralInput(
        employer_pan="ABCDE1234F", dpiit_registration_number="DIPP12345",
        assessment_year="2025-26", tax_deferred_brought_forward=Decimal("100"),
        tax_payable_current_year=Decimal("20"), balance_tax_carried_forward=Decimal("80"),
        security_type="FS", ceased_employee=False,
    )])
    assert not failed(validate_itr2_input(inp), "ITR2-IN-ESOP-002")


def test_ESOP_003_ceased_employee_payable_not_equal_bf_fails():
    """CBDT rule #483: ceasing employment forces Sl.7 to equal Sl.3."""
    inp = _base_input(esop_deferrals=[ESOPDeferralInput(
        employer_pan="ABCDE1234F", dpiit_registration_number="DIPP12345",
        assessment_year="2025-26", tax_deferred_brought_forward=Decimal("100"),
        tax_payable_current_year=Decimal("20"), balance_tax_carried_forward=Decimal("80"),
        security_type="NS", ceased_employee=True,
    )])
    assert failed(validate_itr2_input(inp), "ITR2-IN-ESOP-003")


def test_ESOP_003_ceased_employee_payable_equals_bf_passes():
    inp = _base_input(esop_deferrals=[ESOPDeferralInput(
        employer_pan="ABCDE1234F", dpiit_registration_number="DIPP12345",
        assessment_year="2025-26", tax_deferred_brought_forward=Decimal("100"),
        tax_payable_current_year=Decimal("100"), balance_tax_carried_forward=Decimal("0"),
        security_type="NS", ceased_employee=True,
    )])
    assert not failed(validate_itr2_input(inp), "ITR2-IN-ESOP-003")


def test_VIA_050_80ccc_claimed_without_schedule_rows_fails():
    """CBDT rule #758: 80CCC claimed but no per-row schedule details."""
    inp = _base_input(deductions_chapter6a=Chapter6ADeductions(amount_80ccc=Decimal("50000")))
    assert failed(validate_itr2_input(inp), "ITR2-IN-VIA-050")


def test_VIA_050_80ccc_claimed_with_schedule_rows_passes():
    inp = _base_input(
        deductions_chapter6a=Chapter6ADeductions(amount_80ccc=Decimal("50000")),
        schedule_80ccc_entries=[Schedule80CCCEntry(
            amount=Decimal("50000"), identifier_type="PRAN", identifier_name="123456789012",
        )],
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-VIA-050")


def test_VIA_051_80ccc_row_sum_mismatch_fails():
    """CBDT rule #693: Schedule 80CCC row amounts must sum to the VIA total."""
    inp = _base_input(
        deductions_chapter6a=Chapter6ADeductions(amount_80ccc=Decimal("50000")),
        schedule_80ccc_entries=[Schedule80CCCEntry(
            amount=Decimal("30000"), identifier_type="PRAN", identifier_name="123456789012",
        )],
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-VIA-051")


def test_VIA_051_80ccc_row_sum_matches_passes():
    inp = _base_input(
        deductions_chapter6a=Chapter6ADeductions(amount_80ccc=Decimal("50000")),
        schedule_80ccc_entries=[Schedule80CCCEntry(
            amount=Decimal("50000"), identifier_type="PRAN", identifier_name="123456789012",
        )],
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-VIA-051")


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




def test_PROFILE_002_resident_fpi_rejected_at_schema_construction():
    """CBDT rule #20: a Resident/RNOR taxpayer cannot be an FII/FPI. This
    used to be re-checked in validate_itr2_input() as ITR2-IN-PROFILE-002,
    but that check was dead code -- ITR2FilingProfile's own model validator
    (schemas/itr2.py) already raises for every state it tested, so no such
    profile could ever be constructed to reach it. Enforcement moved
    entirely to the schema boundary; this test exercises that directly."""
    with pytest.raises(ValidationError, match="FII/FPI status requires non-resident"):
        ITR2FilingProfile(
            pan="ABCPN1234F", surname_or_org_name="Nair",
            date_of_birth_or_formation=date(1985, 6, 15), father_name="Ramesh Nair",
            verification_place="Mumbai",
            primary_address=FilingAddress(
                residence_no="12", locality_or_area="MG Road", city_or_town_or_district="Mumbai",
                state_code="27", mobile_no="9876543210", email="priya@example.com",
            ),
            residential_status=ResidentialStatus.RESIDENT, is_fii_fpi=True,
            sebi_registration_number="INABFP123456",
        )


def _cg_112a_scrip() -> CG112AScrip:
    return CG112AScrip(
        isin_code="INE000A00001", share_unit_name="RELIANCE",
        date_of_acquisition=date(2020, 1, 1), date_of_transfer=date(2025, 7, 1),
        num_shares_units=Decimal("100"), sale_price_per_share=Decimal("1000"),
        total_sale_value=Decimal("100000"), cost_acq_without_index=Decimal("50000"),
    )


def _fii_fpi_profile(is_fii_fpi: bool) -> ITR2FilingProfile:
    """A fully-valid ITR2FilingProfile (not `.model_construct()`, which
    leaves required fields like `date_of_birth_or_formation` unset and
    raises AttributeError the moment `StrictModel` revalidates it as a
    nested field of `ITR2Input`)."""
    return ITR2FilingProfile(
        pan="ABCPN1234F", surname_or_org_name="Nair",
        date_of_birth_or_formation=date(1985, 6, 15), father_name="Ramesh Nair",
        verification_place="Mumbai",
        primary_address=FilingAddress(
            residence_no="12", locality_or_area="MG Road", city_or_town_or_district="Mumbai",
            state_code="27", mobile_no="9876543210", email="priya@example.com",
        ),
        residential_status=(
            ResidentialStatus.NON_RESIDENT if is_fii_fpi else ResidentialStatus.RESIDENT
        ),
        is_fii_fpi=is_fii_fpi,
        sebi_registration_number="INABFP123456" if is_fii_fpi else None,
    )


def test_CG_111_fii_fpi_using_112a_schedule_fails():
    """CBDT rule #177: an FII/FPI taxpayer must use Schedule 115AD(1)(b)(iii)
    proviso, not Schedule 112A."""
    inp = _base_input(
        residential_status=ResidentialStatus.NON_RESIDENT,
        filing_profile=_fii_fpi_profile(True), cg_112a_scrips=[_cg_112a_scrip()],
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-CG-111")


def test_CG_111_fii_fpi_using_115ad_schedule_passes():
    inp = _base_input(
        residential_status=ResidentialStatus.NON_RESIDENT,
        filing_profile=_fii_fpi_profile(True), cg_115ad_scrips=[_cg_112a_scrip()],
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-CG-111")
    assert not failed(validate_itr2_input(inp), "ITR2-IN-CG-112")


def test_CG_112_non_fii_using_115ad_schedule_fails():
    """CBDT rule #187: a non-FII/FPI taxpayer must use Schedule 112A, not
    Schedule 115AD(1)(b)(iii) proviso."""
    inp = _base_input(filing_profile=_fii_fpi_profile(False), cg_115ad_scrips=[_cg_112a_scrip()])
    assert failed(validate_itr2_input(inp), "ITR2-IN-CG-112")


def test_CG_112_non_fii_using_112a_schedule_passes():
    inp = _base_input(filing_profile=_fii_fpi_profile(False), cg_112a_scrips=[_cg_112a_scrip()])
    assert not failed(validate_itr2_input(inp), "ITR2-IN-CG-111")
    assert not failed(validate_itr2_input(inp), "ITR2-IN-CG-112")


def test_PROFILE_003_seventh_proviso_without_amounts_fails():
    profile = _fii_fpi_profile(False).model_copy(update={"seventh_proviso_139": True})
    assert failed(validate_itr2_input(_base_input(filing_profile=profile)), "ITR2-IN-PROFILE-003")


def _revised_return_profile(original_filing_section) -> ITR2FilingProfile:
    return ITR2FilingProfile(
        pan="ABCPN1234F", surname_or_org_name="Nair",
        date_of_birth_or_formation=date(1985, 6, 15), father_name="Ramesh Nair",
        verification_place="Mumbai",
        primary_address=FilingAddress(
            residence_no="12", locality_or_area="MG Road", city_or_town_or_district="Mumbai",
            state_code="27", mobile_no="9876543210", email="priya@example.com",
        ),
        return_file_section=ReturnFileSection.REVISED_139_5,
        receipt_number="123456789012345", original_return_date=date(2026, 6, 1),
        original_return_filing_section=original_filing_section,
    )


def test_PROFILE_007_revised_return_against_142_1_original_fails():
    """CBDT rule #4: a revised return cannot be filed against an original
    return filed under a section 142(1) notice."""
    profile = _revised_return_profile(ReturnFileSection.NOTICE_142_1)
    inp = _base_input(filing_profile=profile, filing_section=ReturnFileSection.REVISED_139_5)
    assert failed(validate_itr2_input(inp), "ITR2-IN-PROFILE-007")


def test_PROFILE_007_revised_return_against_139_1_original_passes():
    profile = _revised_return_profile(ReturnFileSection.ON_TIME_139_1)
    inp = _base_input(filing_profile=profile, filing_section=ReturnFileSection.REVISED_139_5)
    assert not failed(validate_itr2_input(inp), "ITR2-IN-PROFILE-007")


def test_PROFILE_007_revised_return_without_original_section_known_is_a_no_op():
    profile = _revised_return_profile(None)
    inp = _base_input(filing_profile=profile, filing_section=ReturnFileSection.REVISED_139_5)
    assert not failed(validate_itr2_input(inp), "ITR2-IN-PROFILE-007")


def _defective_notice_response_profile(original_tax_regime) -> ITR2FilingProfile:
    return ITR2FilingProfile(
        pan="ABCPN1234F", surname_or_org_name="Nair",
        date_of_birth_or_formation=date(1985, 6, 15), father_name="Ramesh Nair",
        verification_place="Mumbai",
        primary_address=FilingAddress(
            residence_no="12", locality_or_area="MG Road", city_or_town_or_district="Mumbai",
            state_code="27", mobile_no="9876543210", email="priya@example.com",
        ),
        return_file_section=ReturnFileSection.DEFECTIVE_139_9,
        notice_number="NOTICE123", notice_date=date(2026, 6, 1),
        original_return_tax_regime=original_tax_regime,
    )


def test_PROFILE_010_defective_notice_response_regime_mismatch_fails():
    """CBDT rule #599: a defective-notice response must use the same tax
    regime as the original return."""
    profile = _defective_notice_response_profile(TaxRegime.OLD)
    inp = _base_input(
        filing_profile=profile, filing_section=ReturnFileSection.DEFECTIVE_139_9,
        tax_regime=TaxRegime.NEW,
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-PROFILE-010")


def test_PROFILE_010_defective_notice_response_regime_match_passes():
    profile = _defective_notice_response_profile(TaxRegime.OLD)
    inp = _base_input(
        filing_profile=profile, filing_section=ReturnFileSection.DEFECTIVE_139_9,
        tax_regime=TaxRegime.OLD,
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-PROFILE-010")


def test_PROFILE_010_original_regime_unknown_is_a_no_op():
    profile = _defective_notice_response_profile(None)
    inp = _base_input(
        filing_profile=profile, filing_section=ReturnFileSection.DEFECTIVE_139_9,
        tax_regime=TaxRegime.NEW,
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-PROFILE-010")


def test_PROFILE_008_resident_115h_unanswered_fails():
    """CBDT rule #83: a Resident/RNOR individual must explicitly answer the
    Section 115H question -- unanswered (None) is not acceptable."""
    profile = _fii_fpi_profile(False)
    assert profile.benefit_us_115h is None
    assert failed(validate_itr2_input(_base_input(filing_profile=profile)), "ITR2-IN-PROFILE-008")


def test_PROFILE_008_resident_115h_answered_no_passes():
    profile = _fii_fpi_profile(False).model_copy(update={"benefit_us_115h": False})
    assert not failed(validate_itr2_input(_base_input(filing_profile=profile)), "ITR2-IN-PROFILE-008")


def test_PROFILE_008_non_resident_unanswered_is_a_no_op():
    """115H is not applicable to a plain non-resident at all (see the
    model-level validator forbidding NON_RESIDENT + benefit_us_115h)."""
    profile = _fii_fpi_profile(True)
    assert not failed(validate_itr2_input(
        _base_input(residential_status=ResidentialStatus.NON_RESIDENT, filing_profile=profile)
    ), "ITR2-IN-PROFILE-008")


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


def test_CG_115_improvement_cost_without_year_fails():
    """CBDT rule #186: year of improvement is mandatory when improvement cost is declared."""
    inp = _base_input(cg_transactions=[CGTransaction(
        asset_type=CGAssetType.LAND_BUILDING,
        date_of_acquisition=date(2020, 4, 1), date_of_transfer=date(2026, 2, 1),
        full_consideration=Decimal("8000000"), cost_of_acquisition=Decimal("3000000"),
        improvement_cost=Decimal("500000"),
    )])
    assert failed(validate_itr2_input(inp), "ITR2-IN-CG-115")


def test_CG_115_improvement_cost_with_year_passes():
    inp = _base_input(cg_transactions=[CGTransaction(
        asset_type=CGAssetType.LAND_BUILDING,
        date_of_acquisition=date(2020, 4, 1), date_of_transfer=date(2026, 2, 1),
        full_consideration=Decimal("8000000"), cost_of_acquisition=Decimal("3000000"),
        improvement_cost=Decimal("500000"), year_of_improvement="2022-23",
    )])
    assert not failed(validate_itr2_input(inp), "ITR2-IN-CG-115")


def test_CG_115_no_improvement_cost_is_a_no_op():
    inp = _base_input(cg_transactions=[CGTransaction(
        asset_type=CGAssetType.LAND_BUILDING,
        date_of_acquisition=date(2020, 4, 1), date_of_transfer=date(2026, 2, 1),
        full_consideration=Decimal("8000000"), cost_of_acquisition=Decimal("3000000"),
    )])
    assert not failed(validate_itr2_input(inp), "ITR2-IN-CG-115")


def test_CG_116_buyback_loss_without_os_dividend_detail_fails():
    """CBDT rule #600: a buyback capital loss requires the corresponding
    Section 2(22)(f) dividend detail in Schedule OS Sl. No. 1a(iii)."""
    inp = _base_input(cg_transactions=[CGTransaction(
        asset_type=CGAssetType.UNLISTED_SHARES,
        date_of_acquisition=date(2020, 4, 1), date_of_transfer=date(2026, 2, 1),
        full_consideration=Decimal("0"), cost_of_acquisition=Decimal("500000"),
        is_buyback_loss=True,
    )])
    assert failed(validate_itr2_input(inp), "ITR2-IN-CG-116")


def test_CG_116_buyback_loss_with_os_dividend_detail_passes():
    inp = _base_input(
        cg_transactions=[CGTransaction(
            asset_type=CGAssetType.UNLISTED_SHARES,
            date_of_acquisition=date(2020, 4, 1), date_of_transfer=date(2026, 2, 1),
            full_consideration=Decimal("0"), cost_of_acquisition=Decimal("500000"),
            is_buyback_loss=True,
        )],
        os_dividend_entries=[OSDividendEntry(section="10(22f)", amount=Decimal("500000"))],
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-CG-116")


def test_CG_116_no_buyback_loss_is_a_no_op():
    inp = _base_input(cg_transactions=[CGTransaction(
        asset_type=CGAssetType.UNLISTED_SHARES,
        date_of_acquisition=date(2020, 4, 1), date_of_transfer=date(2026, 2, 1),
        full_consideration=Decimal("500000"), cost_of_acquisition=Decimal("300000"),
    )])
    assert not failed(validate_itr2_input(inp), "ITR2-IN-CG-116")


def test_CG_117_nri_unquoted_shares_disposal_without_section_code_fails():
    """CBDT rule #597: a section code is mandatory when Schedule CG's Sl.B5
    NRI unquoted-shares block is filled."""
    inp = _base_input(cg_transactions=[CGTransaction(
        asset_type=CGAssetType.UNLISTED_SHARES,
        date_of_acquisition=date(2020, 4, 1), date_of_transfer=date(2026, 2, 1),
        full_consideration=Decimal("500000"), cost_of_acquisition=Decimal("300000"),
        is_nri_unquoted_shares_disposal=True,
    )])
    assert failed(validate_itr2_input(inp), "ITR2-IN-CG-117")


def test_CG_117_nri_unquoted_shares_disposal_with_section_code_passes():
    inp = _base_input(cg_transactions=[CGTransaction(
        asset_type=CGAssetType.UNLISTED_SHARES,
        date_of_acquisition=date(2020, 4, 1), date_of_transfer=date(2026, 2, 1),
        full_consideration=Decimal("500000"), cost_of_acquisition=Decimal("300000"),
        is_nri_unquoted_shares_disposal=True, section_code="115AD",
    )])
    assert not failed(validate_itr2_input(inp), "ITR2-IN-CG-117")


def test_CG_118_resident_claims_112_1_c_without_115h_fails():
    """CBDT rule #153: a Resident cannot claim 112(1)(c) without electing 115H."""
    inp = _base_input(
        filing_profile=_fii_fpi_profile(False),
        cg_transactions=[CGTransaction(
            asset_type=CGAssetType.UNLISTED_SHARES,
            date_of_acquisition=date(2020, 4, 1), date_of_transfer=date(2026, 2, 1),
            full_consideration=Decimal("500000"), cost_of_acquisition=Decimal("300000"),
            is_nri_unquoted_shares_disposal=True, section_code="112_1_c",
        )],
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-CG-118")


def test_CG_118_resident_claims_115ac_without_115h_fails():
    """CBDT rule #155: same check for Section 115AC."""
    inp = _base_input(
        filing_profile=_fii_fpi_profile(False),
        cg_transactions=[CGTransaction(
            asset_type=CGAssetType.UNLISTED_SHARES,
            date_of_acquisition=date(2020, 4, 1), date_of_transfer=date(2026, 2, 1),
            full_consideration=Decimal("500000"), cost_of_acquisition=Decimal("300000"),
            is_nri_unquoted_shares_disposal=True, section_code="115AC",
        )],
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-CG-118")


def test_CG_118_115ad_has_no_115h_restriction():
    """115AD is FII/FPI-specific already -- no 115H gate applies."""
    inp = _base_input(
        filing_profile=_fii_fpi_profile(False),
        cg_transactions=[CGTransaction(
            asset_type=CGAssetType.UNLISTED_SHARES,
            date_of_acquisition=date(2020, 4, 1), date_of_transfer=date(2026, 2, 1),
            full_consideration=Decimal("500000"), cost_of_acquisition=Decimal("300000"),
            is_nri_unquoted_shares_disposal=True, section_code="115AD",
        )],
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-CG-118")


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
    # HUF requires Karta/representative verification capacity (and a
    # Karta PAN for capacity "K") -- an HUF caller with the default "S"
    # capacity fails ITR2FilingProfile's own validator before ever reaching
    # whatever rule the test actually wants to exercise.
    is_huf = assessee_status == AssesseeStatus.HUF
    return ITR2FilingProfile(
        pan="ABCPN1234F", assessee_status=assessee_status, surname_or_org_name="Nair",
        date_of_birth_or_formation=date(1985, 6, 15), father_name="Ramesh Nair",
        verification_place="Mumbai",
        verification_capacity="K" if is_huf else "S",
        karta_pan="ABCPX1234F" if is_huf else None,
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


# ─── Phase 2 cluster 1: Schedule Salary (CBDT rules #51/#59/#60/#601/#606) ──

def test_SAL_027_duplicate_section10_exemption_code_fails():
    inp = _base_input(
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        employer_filing_details=[_employer_detail(section10_exemption_rows=[
            {"SalNatureDesc": "10(6)", "SalOthNatOfInc": "Diplomatic", "SalOthAmount": 1000},
            {"SalNatureDesc": "10(6)", "SalOthNatOfInc": "Diplomatic again", "SalOthAmount": 2000},
        ])],
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-SAL-027")


def test_SAL_027_distinct_section10_exemption_codes_pass():
    inp = _base_input(
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        employer_filing_details=[_employer_detail(section10_exemption_rows=[
            {"SalNatureDesc": "10(6)", "SalOthNatOfInc": "Diplomatic", "SalOthAmount": 1000},
            {"SalNatureDesc": "10(7)", "SalOthNatOfInc": "Foreign service", "SalOthAmount": 2000},
        ])],
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-SAL-027")


def test_SAL_028_eic_judge_code_requires_cgov_sgov_fails():
    """CBDT rule #601: the 'EIC' judges'-exempt-income code requires a
    Central/State Government employer."""
    inp = _base_input(
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        employer_filing_details=[_employer_detail(
            nature_of_employment="PSU",
            section10_exemption_rows=[
                {"SalNatureDesc": "EIC", "SalOthNatOfInc": "Judge income", "SalOthAmount": 5000},
            ],
        )],
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-SAL-028")


def test_SAL_028_eic_judge_code_with_cgov_employer_passes():
    inp = _base_input(
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        employer_filing_details=[_employer_detail(
            nature_of_employment="CGOV",
            section10_exemption_rows=[
                {"SalNatureDesc": "EIC", "SalOthNatOfInc": "Judge income", "SalOthAmount": 5000},
            ],
        )],
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-SAL-028")


def test_SAL_029_relief_89a_exceeding_income_notified_fails():
    """CBDT rule #60: Section 89A relief cannot exceed the notified income
    (Sl.1d) it relates to."""
    inp = _base_input(salary_income=SalaryIncome(
        gross_salary=Decimal("600000"),
        income_notified_89a=Decimal("10000"), relief_89a=Decimal("15000"),
    ))
    assert failed(validate_itr2_input(inp), "ITR2-IN-SAL-029")


def test_SAL_029_relief_89a_within_income_notified_passes():
    inp = _base_input(salary_income=SalaryIncome(
        gross_salary=Decimal("600000"),
        income_notified_89a=Decimal("10000"), relief_89a=Decimal("10000"),
    ))
    assert not failed(validate_itr2_input(inp), "ITR2-IN-SAL-029")


def test_FORM_010_huf_relief_89a_fails():
    """CBDT rule #59: Section 89A relief is an individual-only concession,
    not available to a HUF assessee. Builds its own valid HUF profile
    (verification_capacity="K"/karta_pan set) -- `_filing_profile(
    assessee_status=HUF)` now does the same thing itself (fixed alongside
    the former baseline test_VIA_007/TDS_008/VIA_002 HUF failures), but
    this one predates that fix and there's no need to churn a passing test."""
    profile = ITR2FilingProfile(
        pan="ABCPH1234F", assessee_status=AssesseeStatus.HUF, surname_or_org_name="Nair HUF",
        date_of_birth_or_formation=date(2000, 6, 15), father_name="NA",
        verification_place="Mumbai", verification_capacity="K", karta_pan="ABCPN1234F",
        primary_address=FilingAddress(
            residence_no="12", locality_or_area="MG Road", city_or_town_or_district="Mumbai",
            state_code="27", mobile_no="9876543210", email="priya@example.com",
        ),
    )
    inp = _base_input(
        filing_profile=profile,
        salary_income=SalaryIncome(gross_salary=Decimal("600000"), relief_89a=Decimal("5000")),
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-FORM-010")


def test_FORM_010_individual_relief_89a_passes():
    inp = _base_input(
        salary_income=SalaryIncome(gross_salary=Decimal("600000"), relief_89a=Decimal("5000"),
                                    income_notified_89a=Decimal("5000")),
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-FORM-010")


def test_SAL_026_table_10_13a_total_exceeding_gross_salary_fails():
    """CBDT rule #606: Basic + DA + actual HRA received (Table 10(13A))
    cannot exceed gross salary u/s 17(1)."""
    inp = _base_input(
        salary_income=SalaryIncome(gross_salary=Decimal("500000")),
        employer_filing_details=[_employer_detail(
            salary_for_hra=Decimal("300000"), actual_hra_received=Decimal("300000"),
        )],
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-SAL-026")


def test_SAL_026_table_10_13a_total_within_gross_salary_passes():
    inp = _base_input(
        salary_income=SalaryIncome(gross_salary=Decimal("1000000")),
        employer_filing_details=[_employer_detail(
            salary_for_hra=Decimal("300000"), actual_hra_received=Decimal("120000"),
        )],
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-SAL-026")


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


def test_OS_018_dividend_115ac_mismatches_special_rate_entry_fails():
    """CBDT rule #220: Schedule OS Sl.10's dividend quarterly breakdown for
    a special-rate section must equal the corresponding Sl.2d/2e amount --
    os_dividend_entries is disclosure-only, never read by the calculator,
    so it can silently diverge from what os_special_rate_entries actually
    taxes without this cross-check."""
    inp = _base_input(
        residential_status=ResidentialStatus.NON_RESIDENT,
        os_dividend_entries=[OSDividendEntry(section="115AC", amount=Decimal("30000"))],
        os_special_rate_entries=[OSSpecialRateEntry(
            source_description="5AC1abD", source_amount=Decimal("20000"),
        )],
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-OS-018")


def test_OS_018_dividend_115ac_matches_special_rate_entry_passes():
    inp = _base_input(
        residential_status=ResidentialStatus.NON_RESIDENT,
        os_dividend_entries=[OSDividendEntry(section="115AC", amount=Decimal("30000"))],
        os_special_rate_entries=[OSSpecialRateEntry(
            source_description="5AC1abD", source_amount=Decimal("30000"),
        )],
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-OS-018")


def test_OS_019_dividend_dtaa_mismatches_dtaa_entries_fails():
    """CBDT rule #219: DTAA-rate dividend quarterly breakdown vs Sl.2f."""
    inp = _base_input(
        residential_status=ResidentialStatus.NON_RESIDENT,
        os_dividend_entries=[OSDividendEntry(section="DTAA", amount=Decimal("15000"))],
        os_dtaa_entries=[_dtaa_entry(amount=Decimal("10000"), nature_of_income="2d")],
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-OS-019")


def test_OS_020_plain_dividend_mismatches_formula_fails():
    """CBDT rule #214: plain-dividend (Sl.10 "194") quarterly breakdown
    must equal gross dividend income less DTAA dividend less eligible
    interest expenditure u/s 57."""
    inp = _base_input(
        other_sources_income=OtherSourcesIncome(dividend_income=Decimal("100000")),
        os_dividend_entries=[OSDividendEntry(section="194", amount=Decimal("100000"))],
        os_deductions=OSDeductions(interest_expense_eligible_us57=Decimal("10000")),
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-OS-020")


def test_OS_020_plain_dividend_matches_formula_passes():
    inp = _base_input(
        other_sources_income=OtherSourcesIncome(dividend_income=Decimal("100000")),
        os_dividend_entries=[OSDividendEntry(section="194", amount=Decimal("90000"))],
        os_deductions=OSDeductions(interest_expense_eligible_us57=Decimal("10000")),
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-OS-020")


def test_EI_001_duplicate_exempt_sub_category_fails():
    """CBDT rules #698-745: the same Section 10 sub-category cannot be
    selected more than once in Schedule EI's other-exempt-income rows."""
    from app.schemas.itr2 import ExemptIncome, ExemptIncomeOtherEntry
    inp = _base_input(exempt_income=ExemptIncome(other_exempt_entries=[
        ExemptIncomeOtherEntry(category="SRPC", sub_category="10(16)", description="A", amount=Decimal("1000")),
        ExemptIncomeOtherEntry(category="OTH", sub_category="10(16)", description="B", amount=Decimal("2000")),
    ]))
    assert failed(validate_itr2_input(inp), "ITR2-IN-EI-001")


def test_EI_001_distinct_exempt_sub_categories_pass():
    from app.schemas.itr2 import ExemptIncome, ExemptIncomeOtherEntry
    inp = _base_input(exempt_income=ExemptIncome(other_exempt_entries=[
        ExemptIncomeOtherEntry(category="SRPC", sub_category="10(16)", description="A", amount=Decimal("1000")),
        ExemptIncomeOtherEntry(category="OTH", sub_category="10(17A)", description="B", amount=Decimal("2000")),
    ]))
    assert not failed(validate_itr2_input(inp), "ITR2-IN-EI-001")


def test_EI_002_pti_exempt_income_without_matching_pti_entry_fails():
    """CBDT rule #432: Schedule EI Sl.5 must equal Schedule PTI's own exempt total."""
    from app.schemas.itr2 import ExemptIncome
    inp = _base_input(exempt_income=ExemptIncome(pti_exempt_income=Decimal("5000")))
    assert failed(validate_itr2_input(inp), "ITR2-IN-EI-002")


def test_EI_002_pti_exempt_income_matching_pti_entry_passes():
    from app.schemas.itr2 import ExemptIncome
    inp = _base_input(
        exempt_income=ExemptIncome(pti_exempt_income=Decimal("5000")),
        pti_entries=[PTIEntry(
            entity_name="ABC Trust", entity_pan="ABCTR1234E", income_head="OS",
            section="115UA", income_amount=Decimal("0"), exempt_income_23fbb=Decimal("5000"),
        )],
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-EI-002")


def test_EI_002_zero_pti_exempt_income_with_no_pti_entries_is_a_no_op():
    inp = _base_input()
    assert not failed(validate_itr2_input(inp), "ITR2-IN-EI-002")


def test_OS_020_no_plain_dividend_row_is_a_no_op():
    inp = _base_input(other_sources_income=OtherSourcesIncome(dividend_income=Decimal("100000")))
    assert not failed(validate_itr2_input(inp), "ITR2-IN-OS-020")


def test_OS_019_dividend_dtaa_matches_dtaa_entries_passes():
    inp = _base_input(
        residential_status=ResidentialStatus.NON_RESIDENT,
        os_dividend_entries=[OSDividendEntry(section="DTAA", amount=Decimal("10000"))],
        os_dtaa_entries=[_dtaa_entry(amount=Decimal("10000"), nature_of_income="2d")],
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-OS-019")


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


def test_DTAA_002_applicable_rate_below_lower_of_treaty_and_it_act_fails():
    """CBDT rule #207: the applicable rate must EQUAL the lower of the two
    rates, not merely be capped by it -- a too-low rate (understating
    relief) must also fail."""
    inp = _base_input(
        residential_status=ResidentialStatus.NON_RESIDENT,
        os_dtaa_entries=[_dtaa_entry(
            rate_as_per_treaty=Decimal("15"), rate_as_per_it_act=Decimal("20"),
            applicable_rate=Decimal("10"),
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


def test_DTAA_003_stcg_applicable_rate_below_lower_of_treaty_and_it_act_fails():
    """CBDT rule #152: exact-equality fix, STCG side."""
    inp = _base_input(
        residential_status=ResidentialStatus.NON_RESIDENT,
        cg_stcg_dtaa_entries=[_cg_dtaa_entry(
            rate_as_per_treaty=Decimal("15"), rate_as_per_it_act=Decimal("20"),
            applicable_rate=Decimal("10"),
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


def test_DTAA_004_ltcg_applicable_rate_below_lower_of_treaty_and_it_act_fails():
    """CBDT rule #152: exact-equality fix, LTCG side."""
    inp = _base_input(
        residential_status=ResidentialStatus.NON_RESIDENT,
        cg_ltcg_dtaa_entries=[_cg_dtaa_entry(
            rate_as_per_treaty=Decimal("10"), rate_as_per_it_act=Decimal("12.5"),
            applicable_rate=Decimal("5"),
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


def test_SAL_025_hra_claimed_without_table_10_13a_fails():
    """CBDT rule #605: a claim with hra_exempt_amount > 0 but zero Table
    10(13A) rows must be flagged, not silently skipped. Previously the
    single guard on ITR2-IN-SAL-015 (`... and inp.employer_filing_details`)
    meant an empty employer_filing_details list bypassed HRA validation
    entirely instead of being caught as "table not filled"."""
    inp = _base_input(
        salary_income=SalaryIncome(gross_salary=Decimal("500000"), hra_exempt_amount=Decimal("120000")),
        employer_filing_details=[],
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-SAL-025")


def test_SAL_025_no_hra_claim_without_table_passes():
    inp = _base_input(
        salary_income=SalaryIncome(gross_salary=Decimal("500000")),
        employer_filing_details=[],
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-SAL-025")


def test_SAL_025_hra_claimed_with_table_does_not_also_fail_025():
    inp = _base_input(
        salary_income=SalaryIncome(gross_salary=Decimal("500000"), hra_exempt_amount=Decimal("120000")),
        employer_filing_details=[_employer_detail(
            actual_hra_received=Decimal("120000"), actual_rent_paid=Decimal("200000"),
            salary_for_hra=Decimal("300000"), is_metro_city=True,
        )],
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-SAL-025")


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


# ─── Phase 6j-3: Section 115H gating (#153/#154/#155) ───────────────────────

def test_OS_007_resident_claiming_115ac_dividend_without_115h_fails():
    inp = _base_input(
        filing_profile=_filing_profile().model_copy(update={
            "residential_status": ResidentialStatus.RESIDENT, "benefit_us_115h": False,
        }),
        residential_status=ResidentialStatus.RESIDENT,
        os_dividend_entries=[OSDividendEntry(section="115AC", amount=Decimal("10000"))],
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-OS-007")


def test_OS_007_rnor_claiming_115ac_dividend_with_115h_passes():
    """Section 115H itself is only available to RNOR (ITR2FilingProfile's own
    model_validator: "Section 115H benefit requires RNOR resident status"),
    not a fully Resident-and-Ordinarily-Resident taxpayer -- ITR2-IN-OS-007's
    own residential_status == RESIDENT check therefore targets the
    ResidentialStatus.RESIDENT (ROR) enum value specifically, which can never
    legitimately claim 115AC at all since it can never hold benefit_us_115h."""
    inp = _base_input(
        filing_profile=_filing_profile().model_copy(update={
            "residential_status": ResidentialStatus.NOT_ORDINARILY_RESIDENT, "benefit_us_115h": True,
        }),
        residential_status=ResidentialStatus.NOT_ORDINARILY_RESIDENT,
        os_dividend_entries=[OSDividendEntry(section="115AC", amount=Decimal("10000"))],
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-OS-007")


def _os_dtaa_entry(**overrides) -> OSDtaaEntry:
    fields = dict(
        amount=Decimal("1000"), nature_of_income="1ai", country_name="Singapore",
        country_code="65", dtaa_article="11", rate_as_per_treaty=Decimal("10"),
        rate_as_per_it_act=Decimal("20"), item_no_incl="1ai",
    )
    fields.update(overrides)
    return OSDtaaEntry(**fields)


def test_OS_008_dtaa_dividend_claim_exceeding_declared_dividend_income_fails():
    inp = _base_input(
        residential_status=ResidentialStatus.NON_RESIDENT,
        other_sources_income=OtherSourcesIncome(dividend_income=Decimal("5000")),
        os_dtaa_entries=[_os_dtaa_entry(nature_of_income="1ai", amount=Decimal("6000"))],
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-OS-008")


def test_OS_008_dtaa_dividend_claim_within_declared_dividend_income_passes():
    inp = _base_input(
        residential_status=ResidentialStatus.NON_RESIDENT,
        other_sources_income=OtherSourcesIncome(dividend_income=Decimal("10000")),
        os_dtaa_entries=[_os_dtaa_entry(nature_of_income="1ai", amount=Decimal("6000"))],
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-OS-008")


def test_OS_008_dtaa_115bb_claim_exceeding_si_entries_gross_fails():
    inp = _base_input(
        residential_status=ResidentialStatus.NON_RESIDENT,
        si_entries=[ScheduleSIEntry(section="115BB", gross_income=Decimal("1000"))],
        os_dtaa_entries=[_os_dtaa_entry(nature_of_income="2ai", amount=Decimal("2000"))],
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-OS-008")


def test_OS_009_89a_income_notified_not_matching_country_rows_fails():
    inp = _base_input(os_section_89a=OSSection89A(
        income_notified=Decimal("10000"),
        country_entries=[OS89ACountryEntry(country_code="US", amount=Decimal("6000"))],
    ))
    assert failed(validate_itr2_input(inp), "ITR2-IN-OS-009")


def test_OS_009_89a_income_notified_matching_country_rows_passes():
    inp = _base_input(os_section_89a=OSSection89A(
        income_notified=Decimal("6000"),
        country_entries=[OS89ACountryEntry(country_code="US", amount=Decimal("6000"))],
    ))
    assert not failed(validate_itr2_input(inp), "ITR2-IN-OS-009")


def test_OS_010_duplicate_89a_country_in_schedule_os_fails():
    inp = _base_input(os_section_89a=OSSection89A(
        income_notified=Decimal("12000"),
        country_entries=[
            OS89ACountryEntry(country_code="US", amount=Decimal("6000")),
            OS89ACountryEntry(country_code="US", amount=Decimal("6000")),
        ],
    ))
    assert failed(validate_itr2_input(inp), "ITR2-IN-OS-010")


def test_OS_011_non_resident_claiming_115bbf_fails():
    inp = _base_input(
        residential_status=ResidentialStatus.NON_RESIDENT,
        si_entries=[ScheduleSIEntry(section="115BBF", gross_income=Decimal("50000"))],
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-OS-011")


def test_OS_011_resident_claiming_115bbf_passes():
    inp = _base_input(
        residential_status=ResidentialStatus.RESIDENT,
        si_entries=[ScheduleSIEntry(section="115BBF", gross_income=Decimal("50000"))],
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-OS-011")


def test_OS_012_dividend_row_quarterly_breakdown_not_matching_amount_fails():
    inp = _base_input(os_dividend_entries=[
        OSDividendEntry(section="194", amount=Decimal("10000"), q1=Decimal("5000"), q2=Decimal("2000")),
    ])
    assert failed(validate_itr2_input(inp), "ITR2-IN-OS-012")


def test_OS_012_dividend_row_quarterly_breakdown_matching_amount_passes():
    inp = _base_input(os_dividend_entries=[
        OSDividendEntry(section="194", amount=Decimal("7000"), q1=Decimal("5000"), q2=Decimal("2000")),
    ])
    assert not failed(validate_itr2_input(inp), "ITR2-IN-OS-012")


def test_OS_013_lottery_quarterly_breakdown_not_matching_si_gross_fails():
    inp = _base_input(
        si_entries=[ScheduleSIEntry(section="115BB", gross_income=Decimal("10000"))],
        os_lottery_quarters=OSQuarterlyAmount(q1=Decimal("5000")),
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-OS-013")


def test_OS_013_lottery_quarterly_breakdown_matching_si_gross_passes():
    inp = _base_input(
        si_entries=[ScheduleSIEntry(section="115BB", gross_income=Decimal("5000"))],
        os_lottery_quarters=OSQuarterlyAmount(q1=Decimal("5000")),
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-OS-013")


def test_OS_014_gaming_quarterly_breakdown_not_matching_si_gross_fails():
    inp = _base_input(
        si_entries=[ScheduleSIEntry(section="115BBJ", gross_income=Decimal("8000"))],
        os_gaming_quarters=OSQuarterlyAmount(q1=Decimal("1000")),
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-OS-014")


def test_OS_015_depreciation_claimed_without_machinery_rent_income_fails():
    inp = _base_input(os_deductions=OSDeductions(depreciation=Decimal("5000")))
    assert failed(validate_itr2_input(inp), "ITR2-IN-OS-015")


def test_OS_015_depreciation_claimed_with_machinery_rent_income_passes():
    inp = _base_input(
        os_machinery_plant_rent=Decimal("50000"),
        os_deductions=OSDeductions(depreciation=Decimal("5000")),
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-OS-015")


def test_OS_016_expenses_claimed_without_any_os_income_fails():
    inp = _base_input(os_deductions=OSDeductions(expenses=Decimal("2000")))
    assert failed(validate_itr2_input(inp), "ITR2-IN-OS-016")


def test_OS_016_expenses_claimed_with_qualifying_os_income_passes():
    inp = _base_input(
        other_sources_income=OtherSourcesIncome(savings_bank_interest=Decimal("50000")),
        os_deductions=OSDeductions(expenses=Decimal("2000")),
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-OS-016")


def test_OS_017_gift_breakdown_matches_income_56_2_x_passes():
    inp = _base_input(
        other_sources_income=OtherSourcesIncome(income_56_2_x=Decimal("75000")),
        os_gift_breakdown=OSGiftBreakdown(aggregate_without_consideration=Decimal("75000")),
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-OS-017")


def test_OS_017_gift_breakdown_missing_entirely_fails():
    inp = _base_input(other_sources_income=OtherSourcesIncome(income_56_2_x=Decimal("75000")))
    assert failed(validate_itr2_input(inp), "ITR2-IN-OS-017")


def test_OS_017_gift_breakdown_sum_mismatch_fails():
    inp = _base_input(
        other_sources_income=OtherSourcesIncome(income_56_2_x=Decimal("75000")),
        os_gift_breakdown=OSGiftBreakdown(
            aggregate_without_consideration=Decimal("50000"),
            other_property_without_consideration=Decimal("10000"),
        ),
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-OS-017")


def test_OS_017_no_gift_income_at_all_passes():
    inp = _base_input()
    assert not failed(validate_itr2_input(inp), "ITR2-IN-OS-017")


def test_VIA_034_senior_citizen_old_regime_80tta_claim_emits_advisory():
    inp = _base_input(
        age_bracket=AgeBracket.SIXTY_TO_80,
        deductions_chapter6a=Chapter6ADeductions(amount_80tta=Decimal("8000")),
    )
    assert emitted(validate_itr2_input(inp), "ITR2-IN-VIA-034")


def test_VIA_034_non_senior_old_regime_80tta_claim_no_advisory():
    inp = _base_input(
        age_bracket=AgeBracket.BELOW_60,
        deductions_chapter6a=Chapter6ADeductions(amount_80tta=Decimal("8000")),
    )
    assert not emitted(validate_itr2_input(inp), "ITR2-IN-VIA-034")


def test_VIA_034_senior_citizen_no_80tta_claim_no_advisory():
    inp = _base_input(
        age_bracket=AgeBracket.SIXTY_TO_80,
        deductions_chapter6a=Chapter6ADeductions(amount_80tta=Decimal("0")),
    )
    assert not emitted(validate_itr2_input(inp), "ITR2-IN-VIA-034")


def test_OS_007_non_resident_claiming_115ac_dividend_passes():
    inp = _base_input(
        filing_profile=_filing_profile().model_copy(update={
            "residential_status": ResidentialStatus.NON_RESIDENT,
        }),
        residential_status=ResidentialStatus.NON_RESIDENT,
        os_dividend_entries=[OSDividendEntry(section="115AC", amount=Decimal("10000"))],
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-OS-007")


# ─── Phase 6j-8: Chapter VI-A "details required when claimed" family ───────

def test_HP_014_home_loan_interest_claimed_without_loan_details_fails():
    inp = _base_input(
        house_property_income=HousePropertyIncome(
            property_type=PropertyType.SELF_OCCUPIED, home_loan_interest_paid=Decimal("150000"),
        ),
        property_filing_details=[
            PropertyFilingDetail(
                address_detail="1 MG Road", city_or_town_or_district="Pune",
                state_code="27", pin_code="411001",
            ),
        ],
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-HP-014")


def test_HP_014_home_loan_interest_claimed_with_loan_details_passes():
    inp = _base_input(
        house_property_income=HousePropertyIncome(
            property_type=PropertyType.SELF_OCCUPIED, home_loan_interest_paid=Decimal("150000"),
        ),
        property_filing_details=[
            PropertyFilingDetail(
                address_detail="1 MG Road", city_or_town_or_district="Pune",
                state_code="27", pin_code="411001",
                home_loan_details=[HomeLoanDetail(
                    loan_taken_from="B", bank_or_institution_name="SBI",
                    loan_account_or_ref_no="LN123", date_of_loan=date(2020, 1, 1),
                    total_loan_amount=Decimal("2000000"), loan_outstanding_amount=Decimal("1500000"),
                    interest_this_year=Decimal("150000"),
                )],
            ),
        ],
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-HP-014")


def test_VIA_016_017_80d_self_senior_flag_mismatch_fails():
    inp = _base_input(schedule_80d=Schedule80D(has_self_senior=True, premium_1a_non_senior=Decimal("10000")))
    assert failed(validate_itr2_input(inp), "ITR2-IN-VIA-016")

    inp2 = _base_input(schedule_80d=Schedule80D(has_self_senior=False, premium_1b_senior=Decimal("10000")))
    assert failed(validate_itr2_input(inp2), "ITR2-IN-VIA-017")


def test_VIA_018_019_80d_parents_senior_flag_mismatch_fails():
    inp = _base_input(schedule_80d=Schedule80D(has_parents_senior=True, premium_2a_parents_non_senior=Decimal("5000")))
    assert failed(validate_itr2_input(inp), "ITR2-IN-VIA-018")

    inp2 = _base_input(schedule_80d=Schedule80D(has_parents_senior=False, premium_2b_parents_senior=Decimal("5000")))
    assert failed(validate_itr2_input(inp2), "ITR2-IN-VIA-019")


def test_VIA_016_correctly_flagged_80d_premiums_pass():
    inp = _base_input(schedule_80d=Schedule80D(
        has_self_senior=False, premium_1a_non_senior=Decimal("10000"),
        has_parents_senior=True, premium_2b_parents_senior=Decimal("5000"),
    ))
    results = validate_itr2_input(inp)
    for rid in ("ITR2-IN-VIA-016", "ITR2-IN-VIA-017", "ITR2-IN-VIA-018", "ITR2-IN-VIA-019"):
        assert not failed(results, rid)


def test_VIA_020_80ttb_claimed_by_non_resident_fails():
    inp = _base_input(
        residential_status=ResidentialStatus.NON_RESIDENT,
        deductions_chapter6a=Chapter6ADeductions(amount_80ttb=Decimal("30000")),
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-VIA-020")


def test_VIA_021_80ggc_contribution_missing_date_fails():
    inp = _base_input(schedule_80ggc=Schedule80GGC(
        contributions=[PoliticalContribution(amount=Decimal("5000"), other_mode_amount=Decimal("5000"))],
    ))
    assert failed(validate_itr2_input(inp), "ITR2-IN-VIA-021")


def test_VIA_022_80ggc_other_mode_missing_bank_details_fails():
    inp = _base_input(schedule_80ggc=Schedule80GGC(
        contributions=[PoliticalContribution(
            amount=Decimal("5000"), other_mode_amount=Decimal("5000"),
            contribution_date=date(2025, 6, 1),
        )],
    ))
    assert failed(validate_itr2_input(inp), "ITR2-IN-VIA-022")


def test_VIA_023_80ggc_missing_party_name_and_pan_fails():
    inp = _base_input(schedule_80ggc=Schedule80GGC(
        contributions=[PoliticalContribution(
            amount=Decimal("5000"), other_mode_amount=Decimal("5000"),
            contribution_date=date(2025, 6, 1), transaction_ref="TXN1", ifsc_code="SBIN0001234",
        )],
    ))
    assert failed(validate_itr2_input(inp), "ITR2-IN-VIA-023")


def test_VIA_024_80u_claimed_without_certificate_details_fails():
    inp = _base_input(schedule_80u=Schedule80U(deduction_amount=Decimal("75000")))
    assert failed(validate_itr2_input(inp), "ITR2-IN-VIA-024")


def test_VIA_024_80u_claimed_with_udid_passes():
    inp = _base_input(schedule_80u=Schedule80U(deduction_amount=Decimal("75000"), udid_number="UDID12345"))
    assert not failed(validate_itr2_input(inp), "ITR2-IN-VIA-024")


def test_VIA_025_80dd_claimed_without_certificate_details_fails():
    inp = _base_input(schedule_80dd=Schedule80DD(deduction_amount=Decimal("75000")))
    assert failed(validate_itr2_input(inp), "ITR2-IN-VIA-025")


def test_VIA_026_80c_row_claimed_without_details_fails():
    inp = _base_input(schedule_80c_entries=[Schedule80CEntry(amount=Decimal("10000"))])
    assert failed(validate_itr2_input(inp), "ITR2-IN-VIA-026")


def test_VIA_026_80c_row_with_details_passes():
    inp = _base_input(schedule_80c_entries=[
        Schedule80CEntry(amount=Decimal("10000"), payment_type="LIC", identifier_number="POL123"),
    ])
    assert not failed(validate_itr2_input(inp), "ITR2-IN-VIA-026")


def _loan_entry(cls, **overrides):
    fields = dict(
        loan_taken_from="B", lender_name="SBI", account_or_reference_number="LN123",
        loan_date=date(2020, 6, 1), total_loan_amount=Decimal("500000"),
        outstanding_loan_amount=Decimal("400000"), interest_paid=Decimal("20000"),
    )
    fields.update(overrides)
    return cls(**fields)


def test_VIA_027_80e_claimed_without_loan_details_fails():
    inp = _base_input(deductions_chapter6a=Chapter6ADeductions(amount_80e=Decimal("20000")))
    assert failed(validate_itr2_input(inp), "ITR2-IN-VIA-027")


def test_VIA_027_80ee_claimed_without_loan_details_fails():
    inp = _base_input(deductions_chapter6a=Chapter6ADeductions(amount_80ee=Decimal("20000")))
    assert failed(validate_itr2_input(inp), "ITR2-IN-VIA-027")


def test_VIA_027_80e_claimed_with_loan_details_passes():
    inp = _base_input(
        deductions_chapter6a=Chapter6ADeductions(amount_80e=Decimal("20000")),
        schedule_80e_entries=[_loan_entry(Schedule80EEntry)],
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-VIA-027")


def test_VIA_028_80ee_loan_sanction_date_outside_window_fails():
    inp = _base_input(
        deductions_chapter6a=Chapter6ADeductions(amount_80ee=Decimal("20000")),
        loan_details_80ee_list=[_loan_entry(ITR1Schedule80EELoanEntry, loan_date=date(2020, 1, 1))],
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-VIA-028")


def test_VIA_028_80ee_loan_sanction_date_within_window_passes():
    inp = _base_input(
        deductions_chapter6a=Chapter6ADeductions(amount_80ee=Decimal("20000")),
        loan_details_80ee_list=[_loan_entry(ITR1Schedule80EELoanEntry, loan_date=date(2016, 6, 1))],
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-VIA-028")


def test_VIA_029_80g_donation_missing_donee_pan_fails():
    inp = _base_input(deductions_chapter6a=Chapter6ADeductions(
        donations_80g=[Donation80G(cash_amount=Decimal("5000"))],
    ))
    assert failed(validate_itr2_input(inp), "ITR2-IN-VIA-029")


# ─── Phase 6j-12: TDS/TCS ownership and ceiling checks ──────────────────────

def test_TDS_020_tds2_other_person_credit_missing_pan_fails():
    inp = _base_input(tds2_entries=[TDS2Entry(
        deductor_tan="ABCD12345E", tds_section="194A", gross_amount=Decimal("50000"),
        tds_deducted=Decimal("5000"), tds_claimed_this_year=Decimal("5000"), ownership="O",
    )])
    assert failed(validate_itr2_input(inp), "ITR2-IN-TDS-020")


def test_TDS_020_tds2_self_credit_passes():
    inp = _base_input(tds2_entries=[TDS2Entry(
        deductor_tan="ABCD12345E", tds_section="194A", gross_amount=Decimal("50000"),
        tds_deducted=Decimal("5000"), tds_claimed_this_year=Decimal("5000"), ownership="S",
    )])
    assert not failed(validate_itr2_input(inp), "ITR2-IN-TDS-020")


def test_TCS_002_other_person_credit_missing_pan_fails():
    inp = _base_input(tcs_entries=[TCSEntry(
        collector_tan="ABCD12345E", tcs_section="206C", gross_amount=Decimal("50000"),
        tcs_collected=Decimal("5000"), tcs_credit_claimed_spouse_or_other=Decimal("5000"),
        ownership="2",
    )])
    assert failed(validate_itr2_input(inp), "ITR2-IN-TCS-002")


def test_TCS_003_full_ceiling_exceeded_fails():
    inp = _base_input(tcs_entries=[TCSEntry(
        collector_tan="ABCD12345E", tcs_section="206C", gross_amount=Decimal("50000"),
        tcs_collected=Decimal("5000"), tcs_credit_claimed=Decimal("5000"),
        tcs_credit_claimed_spouse_or_other=Decimal("3000"),
    )])
    assert failed(validate_itr2_input(inp), "ITR2-IN-TCS-003")


def test_TCS_004_carried_forward_mismatch_fails():
    inp = _base_input(tcs_entries=[TCSEntry(
        collector_tan="ABCD12345E", tcs_section="206C", gross_amount=Decimal("50000"),
        tcs_collected=Decimal("10000"), tcs_credit_claimed=Decimal("4000"),
        tds_credit_carried_forward=Decimal("1000"),
    )])
    assert failed(validate_itr2_input(inp), "ITR2-IN-TCS-004")


def test_TCS_004_carried_forward_correct_passes():
    inp = _base_input(tcs_entries=[TCSEntry(
        collector_tan="ABCD12345E", tcs_section="206C", gross_amount=Decimal("50000"),
        tcs_collected=Decimal("10000"), tcs_credit_claimed=Decimal("4000"),
        tds_credit_carried_forward=Decimal("6000"),
    )])
    assert not failed(validate_itr2_input(inp), "ITR2-IN-TCS-004")


def test_TCS_005_brought_forward_and_current_year_in_same_row_fails():
    inp = _base_input(tcs_entries=[TCSEntry(
        collector_tan="ABCD12345E", tcs_section="206C", gross_amount=Decimal("50000"),
        tcs_collected=Decimal("5000"), brought_forward_tds=Decimal("2000"),
        tcs_credit_claimed=Decimal("5000"),
    )])
    assert failed(validate_itr2_input(inp), "ITR2-IN-TCS-005")


# ─── Phase 6j-14: remaining Part-A/misc rows ────────────────────────────────

def test_VIA_031_80g_donee_pan_matches_assessee_pan_fails():
    inp = _base_input(
        filing_profile=_filing_profile(),
        deductions_chapter6a=Chapter6ADeductions(
            donations_80g=[Donation80G(cash_amount=Decimal("5000"), donee_pan="ABCPN1234F")],
        ),
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-VIA-031")


def _representative_filing_profile(representative_pan) -> ITR2FilingProfile:
    return ITR2FilingProfile(
        pan="ABCPN1234F", surname_or_org_name="Nair",
        date_of_birth_or_formation=date(1985, 6, 15), father_name="Ramesh Nair",
        verification_place="Mumbai", verification_capacity="R",
        assessee_representative=AssesseeRepresentativeProfile(
            name="Rep Person", email="rep@example.com", mobile_country_code=91,
            mobile_no="9123456780", pan=representative_pan,
        ),
        primary_address=FilingAddress(
            residence_no="12", locality_or_area="MG Road", city_or_town_or_district="Mumbai",
            state_code="27", mobile_no="9876543210", email="priya@example.com",
        ),
    )


def test_VIA_031_80g_donee_pan_matches_representative_pan_fails():
    """CBDT rule #277: a donee's PAN cannot equal the PAN at Verification --
    the representative assessee's own PAN when filed by a representative."""
    inp = _base_input(
        filing_profile=_representative_filing_profile("REPPN5678K"),
        deductions_chapter6a=Chapter6ADeductions(
            donations_80g=[Donation80G(cash_amount=Decimal("5000"), donee_pan="REPPN5678K")],
        ),
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-VIA-031")


def test_VIA_032_80gga_donee_pan_matches_representative_pan_fails():
    """CBDT rule #313: same check for Schedule 80GGA."""
    inp = _base_input(
        filing_profile=_representative_filing_profile("REPPN5678K"),
        schedule_80gga=Schedule80GGA(donations=[Donation80GGA(
            relevant_clause=Section80GGAClause.RURAL_DEVELOPMENT, donee_name="Charity Trust",
            address=DonationAddress(
                address_line="1 Trust Road", city_or_district="Mumbai", state_code="27",
                pin_code=400001,
            ),
            donee_pan="REPPN5678K", other_mode_amount=Decimal("5000"),
        )]),
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-VIA-032")


def test_VIA_031_80g_donee_pan_distinct_from_representative_pan_passes():
    inp = _base_input(
        filing_profile=_representative_filing_profile("REPPN5678K"),
        deductions_chapter6a=Chapter6ADeductions(
            donations_80g=[Donation80G(cash_amount=Decimal("5000"), donee_pan="AAAPD1234D")],
        ),
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-VIA-031")


def test_PROFILE_009_representative_capacity_without_pan_fails():
    """CBDT rule #8: the representative assessee's own PAN is required for
    the Verification declaration."""
    inp = _base_input(filing_profile=_representative_filing_profile(None))
    assert failed(validate_itr2_input(inp), "ITR2-IN-PROFILE-009")


def test_PROFILE_009_representative_capacity_with_pan_passes():
    inp = _base_input(filing_profile=_representative_filing_profile("REPPN5678K"))
    assert not failed(validate_itr2_input(inp), "ITR2-IN-PROFILE-009")


def test_PROFILE_009_self_capacity_is_a_no_op():
    inp = _base_input(filing_profile=_filing_profile())
    assert not failed(validate_itr2_input(inp), "ITR2-IN-PROFILE-009")


def test_VIA_033_80g_same_pan_in_two_categories_fails():
    inp = _base_input(deductions_chapter6a=Chapter6ADeductions(donations_80g=[
        Donation80G(cash_amount=Decimal("5000"), donee_pan="AAAPD1234D", donation_category="A"),
        Donation80G(cash_amount=Decimal("3000"), donee_pan="AAAPD1234D", donation_category="B"),
    ]))
    assert failed(validate_itr2_input(inp), "ITR2-IN-VIA-033")


def test_VIA_033_exempt_pan_across_categories_passes():
    inp = _base_input(deductions_chapter6a=Chapter6ADeductions(donations_80g=[
        Donation80G(cash_amount=Decimal("5000"), donee_pan="AAAAR1077P", donation_category="A"),
        Donation80G(cash_amount=Decimal("3000"), donee_pan="AAAAR1077P", donation_category="B"),
    ]))
    assert not failed(validate_itr2_input(inp), "ITR2-IN-VIA-033")


def _huf_profile_full() -> ITR2FilingProfile:
    return ITR2FilingProfile(
        pan="ABCPN1234F", assessee_status=AssesseeStatus.HUF, surname_or_org_name="Nair HUF",
        date_of_birth_or_formation=date(1985, 6, 15), father_name="Ramesh Nair",
        verification_place="Mumbai", verification_capacity="K", karta_pan="ABCPX1234F",
        primary_address=FilingAddress(
            residence_no="12", locality_or_area="MG Road", city_or_town_or_district="Mumbai",
            state_code="27", mobile_no="9876543210", email="priya@example.com",
        ),
    )


def test_FORM_008_huf_claiming_relief_89_fails():
    inp = _base_input(filing_profile=_huf_profile_full(), relief_89=Decimal("5000"))
    assert failed(validate_itr2_input(inp), "ITR2-IN-FORM-008")


def test_IT_001_self_assessment_dated_before_fy_end_fails():
    inp = _base_input(tax_payment_entries=[TaxPaymentDetail(
        amount=Decimal("5000"), payment_type="self_assessment",
        payment_date=date(2026, 1, 15), bsr_code="1234567", challan_serial_number="12345",
    )])
    assert failed(validate_itr2_input(inp), "ITR2-IN-IT-001")


def test_IT_002_advance_tax_dated_after_fy_end_fails():
    inp = _base_input(tax_payment_entries=[TaxPaymentDetail(
        amount=Decimal("5000"), payment_type="advance",
        payment_date=date(2026, 6, 15), bsr_code="1234567", challan_serial_number="12345",
    )])
    assert failed(validate_itr2_input(inp), "ITR2-IN-IT-002")


def test_IT_001_002_correctly_dated_payments_pass():
    inp = _base_input(tax_payment_entries=[
        TaxPaymentDetail(
            amount=Decimal("5000"), payment_type="advance",
            payment_date=date(2025, 12, 15), bsr_code="1234567", challan_serial_number="12345",
        ),
        TaxPaymentDetail(
            amount=Decimal("3000"), payment_type="self_assessment",
            payment_date=date(2026, 6, 1), bsr_code="7654321", challan_serial_number="54321",
        ),
    ])
    results = validate_itr2_input(inp)
    assert not failed(results, "ITR2-IN-IT-001")
    assert not failed(results, "ITR2-IN-IT-002")


def test_PROFILE_004_representative_email_matches_own_fails():
    profile = _filing_profile().model_copy(update={
        "verification_capacity": "R",
        "assessee_representative": AssesseeRepresentativeProfile(
            name="Rep Name", email="priya@example.com",
            mobile_country_code=91, mobile_no="9876543210",
        ),
    })
    inp = _base_input(filing_profile=profile)
    assert failed(validate_itr2_input(inp), "ITR2-IN-PROFILE-004")


def test_PROFILE_006_regime_optout_after_due_date_fails():
    profile = _filing_profile().model_copy(update={"opted_out_new_tax_regime": True})
    inp = _base_input(
        filing_profile=profile,
        filing_date=date(2026, 8, 15), due_date=date(2026, 7, 31),
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-PROFILE-006")


# ─── Phase 6j-13: AMT Sl.2a auto-derivation (#421) ──────────────────────────

def test_AMT_003_80ia_addition_not_matching_actual_claims_fails():
    inp = _base_input(
        deductions_chapter6a=Chapter6ADeductions(amount_80ia=Decimal("100000")),
        amt_input=AMTInput(deduction_80ia_to_80rrb_except_80p=Decimal("50000")),
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-AMT-003")


def test_AMT_003_80ia_addition_matching_actual_claims_passes():
    inp = _base_input(
        deductions_chapter6a=Chapter6ADeductions(amount_80ia=Decimal("100000")),
        amt_input=AMTInput(deduction_80ia_to_80rrb_except_80p=Decimal("100000")),
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-AMT-003")


def test_AMT_004_10aa_addition_not_matching_actual_claim_fails():
    inp = _base_input(
        deductions_chapter6a=Chapter6ADeductions(amount_10aa=Decimal("200000")),
        amt_input=AMTInput(deduction_10aa=Decimal("150000")),
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-AMT-004")


# ─── Phase 6j-4: Schedule 112A/115AD grandfathering cutoff (#174) ───────────

def test_CG_109_112a_scrip_fmv_nonzero_after_cutoff_fails():
    inp = _base_input(cg_112a_scrips=[CG112AScrip(
        isin_code="INE000A00001", share_unit_name="TEST SCRIP",
        is_before_31jan2018=False,
        date_of_transfer=date(2025, 5, 1), num_shares_units=Decimal("10"),
        sale_price_per_share=Decimal("100"), total_sale_value=Decimal("1000"),
        cost_acq_without_index=Decimal("500"), fmv_per_share=Decimal("80"),
        total_fmv=Decimal("800"),
    )])
    assert failed(validate_itr2_input(inp), "ITR2-IN-CG-109")


def test_CG_110_115ad_scrip_fmv_nonzero_after_cutoff_fails():
    inp = _base_input(cg_115ad_scrips=[CG112AScrip(
        isin_code="INE000A00001", share_unit_name="TEST SCRIP",
        is_before_31jan2018=False,
        date_of_transfer=date(2025, 5, 1), num_shares_units=Decimal("10"),
        sale_price_per_share=Decimal("100"), total_sale_value=Decimal("1000"),
        cost_acq_without_index=Decimal("500"), total_fmv=Decimal("800"),
    )])
    assert failed(validate_itr2_input(inp), "ITR2-IN-CG-110")


def test_CG_109_112a_scrip_zero_fmv_after_cutoff_passes():
    inp = _base_input(cg_112a_scrips=[CG112AScrip(
        isin_code="INE000A00001", share_unit_name="TEST SCRIP",
        is_before_31jan2018=False,
        date_of_transfer=date(2025, 5, 1), num_shares_units=Decimal("10"),
        sale_price_per_share=Decimal("100"), total_sale_value=Decimal("1000"),
        cost_acq_without_index=Decimal("500"),
    )])
    assert not failed(validate_itr2_input(inp), "ITR2-IN-CG-109")


def test_CG_113_112a_scrip_total_fmv_mismatches_per_share_times_units_fails():
    """CBDT rule #87: Col.11 Total FMV must equal Col.4 (num shares) *
    Col.10 (FMV per share)."""
    inp = _base_input(cg_112a_scrips=[CG112AScrip(
        isin_code="INE000A00001", share_unit_name="TEST SCRIP",
        is_before_31jan2018=True,
        date_of_transfer=date(2025, 5, 1), num_shares_units=Decimal("10"),
        sale_price_per_share=Decimal("100"), total_sale_value=Decimal("1000"),
        cost_acq_without_index=Decimal("500"), fmv_per_share=Decimal("80"),
        total_fmv=Decimal("900"),
    )])
    assert failed(validate_itr2_input(inp), "ITR2-IN-CG-113")


def test_CG_113_112a_scrip_total_fmv_matches_per_share_times_units_passes():
    inp = _base_input(cg_112a_scrips=[CG112AScrip(
        isin_code="INE000A00001", share_unit_name="TEST SCRIP",
        is_before_31jan2018=True,
        date_of_transfer=date(2025, 5, 1), num_shares_units=Decimal("10"),
        sale_price_per_share=Decimal("100"), total_sale_value=Decimal("1000"),
        cost_acq_without_index=Decimal("500"), fmv_per_share=Decimal("80"),
        total_fmv=Decimal("800"),
    )])
    assert not failed(validate_itr2_input(inp), "ITR2-IN-CG-113")


def test_CG_114_115ad_scrip_total_fmv_mismatch_fails():
    """CBDT rule #94: same check as #87, applied to cg_115ad_scrips."""
    inp = _base_input(cg_115ad_scrips=[CG112AScrip(
        isin_code="INE000A00001", share_unit_name="TEST SCRIP",
        is_before_31jan2018=True,
        date_of_transfer=date(2025, 5, 1), num_shares_units=Decimal("10"),
        sale_price_per_share=Decimal("100"), total_sale_value=Decimal("1000"),
        cost_acq_without_index=Decimal("500"), fmv_per_share=Decimal("80"),
        total_fmv=Decimal("900"),
    )])
    assert failed(validate_itr2_input(inp), "ITR2-IN-CG-114")


def test_FSI_004_salary_relief_exceeding_actual_gross_salary_fails():
    inp = _base_input(
        salary_income=SalaryIncome(gross_salary=Decimal("500000")),
        fsi_entries=[FSICountryEntry(
            country_code="US", tax_identification_no="123-45-6789",
            salary_income=Decimal("600000"), tax_paid_outside_india=Decimal("50000"),
            tax_payable_in_india=Decimal("60000"),
        )],
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-FSI-004")


def test_FSI_004_salary_relief_within_actual_gross_salary_passes():
    inp = _base_input(
        salary_income=SalaryIncome(gross_salary=Decimal("800000")),
        fsi_entries=[FSICountryEntry(
            country_code="US", tax_identification_no="123-45-6789",
            salary_income=Decimal("600000"), tax_paid_outside_india=Decimal("50000"),
            tax_payable_in_india=Decimal("60000"),
        )],
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-FSI-004")


def test_VIA_030_80g_non_cash_donation_missing_donee_name_fails():
    inp = _base_input(deductions_chapter6a=Chapter6ADeductions(
        donations_80g=[Donation80G(non_cash_amount=Decimal("5000"), donee_pan="AAAPD1234D")],
    ))
    assert failed(validate_itr2_input(inp), "ITR2-IN-VIA-030")


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


# ─── Phase 2 cluster 3: Chapter VI-A/deductions (CBDT #314-761 cluster) ────

def test_VIA_035_80gga_claimed_without_schedule_fails():
    inp = _base_input(deductions_chapter6a=Chapter6ADeductions(amount_80gga=Decimal("10000")))
    assert failed(validate_itr2_input(inp), "ITR2-IN-VIA-035")


def test_VIA_035_80gga_claimed_with_schedule_passes():
    donation = Donation80GGA(
        relevant_clause=Section80GGAClause.RURAL_DEVELOPMENT, donee_name="Trust",
        address=DonationAddress(
            address_line="1 MG Road", city_or_district="Pune", state_code="27", pin_code=411001,
        ),
        donee_pan="ABCPN1234F", cash_amount=Decimal("0"), other_mode_amount=Decimal("10000"),
    )
    inp = _base_input(
        deductions_chapter6a=Chapter6ADeductions(amount_80gga=Decimal("10000")),
        schedule_80gga=Schedule80GGA(donations=[donation]),
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-VIA-035")


def test_VIA_036_80gga_claim_mismatches_schedule_total_fails():
    donation = Donation80GGA(
        relevant_clause=Section80GGAClause.RURAL_DEVELOPMENT, donee_name="Trust",
        address=DonationAddress(
            address_line="1 MG Road", city_or_district="Pune", state_code="27", pin_code=411001,
        ),
        donee_pan="ABCPN1234F", cash_amount=Decimal("0"), other_mode_amount=Decimal("10000"),
    )
    inp = _base_input(
        deductions_chapter6a=Chapter6ADeductions(amount_80gga=Decimal("15000")),
        schedule_80gga=Schedule80GGA(donations=[donation]),
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-VIA-036")


def test_VIA_037_80qqb_non_resident_fails():
    inp = _base_input(
        residential_status=ResidentialStatus.NON_RESIDENT, deduction_80qqb=Decimal("50000"),
        os_other_income_entries=[OSOtherIncomeEntry(nature="Royalty", amount=Decimal("50000"))],
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-VIA-037")


def test_VIA_037_80qqb_resident_passes():
    inp = _base_input(
        deduction_80qqb=Decimal("50000"),
        os_other_income_entries=[OSOtherIncomeEntry(nature="Royalty", amount=Decimal("50000"))],
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-VIA-037")


def test_VIA_038_80rrb_non_resident_fails():
    inp = _base_input(
        residential_status=ResidentialStatus.NON_RESIDENT, deduction_80rrb=Decimal("50000"),
        os_other_income_entries=[OSOtherIncomeEntry(nature="Royalty", amount=Decimal("50000"))],
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-VIA-038")


def test_VIA_039_80qqb_plus_80rrb_exceeds_os_royalty_income_fails():
    inp = _base_input(
        deduction_80qqb=Decimal("40000"), deduction_80rrb=Decimal("40000"),
        os_other_income_entries=[OSOtherIncomeEntry(nature="Royalty", amount=Decimal("50000"))],
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-VIA-039")


def test_VIA_039_80qqb_plus_80rrb_within_os_royalty_income_passes():
    inp = _base_input(
        deduction_80qqb=Decimal("20000"), deduction_80rrb=Decimal("20000"),
        os_other_income_entries=[OSOtherIncomeEntry(nature="Royalty", amount=Decimal("50000"))],
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-VIA-039")


def test_VIA_040_80qqb_filed_after_due_date_fails():
    inp = _base_input(
        deduction_80qqb=Decimal("50000"),
        os_other_income_entries=[OSOtherIncomeEntry(nature="Royalty", amount=Decimal("50000"))],
        filing_date=date(2026, 8, 1), due_date=date(2026, 7, 31),
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-VIA-040")


def test_VIA_040_80qqb_filed_within_due_date_passes():
    inp = _base_input(
        deduction_80qqb=Decimal("50000"),
        os_other_income_entries=[OSOtherIncomeEntry(nature="Royalty", amount=Decimal("50000"))],
        filing_date=date(2026, 7, 1), due_date=date(2026, 7, 31),
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-VIA-040")


def test_VIA_052_80qqb_without_form_10ccd_ack_fails():
    """CBDT rule #648: Form 10CCD ack number is mandatory to claim 80QQB."""
    inp = _base_input(
        deduction_80qqb=Decimal("50000"),
        os_other_income_entries=[OSOtherIncomeEntry(nature="Royalty", amount=Decimal("50000"))],
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-VIA-052")


def test_VIA_052_80qqb_with_form_10ccd_ack_passes():
    inp = _base_input(
        deduction_80qqb=Decimal("50000"), form_10ccd_ack_number_80qqb="ACK123456",
        os_other_income_entries=[OSOtherIncomeEntry(nature="Royalty", amount=Decimal("50000"))],
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-VIA-052")


def test_VIA_053_80rrb_without_form_10cce_ack_fails():
    """CBDT rule #649: Form 10CCE ack number is mandatory to claim 80RRB."""
    inp = _base_input(
        deduction_80rrb=Decimal("50000"),
        os_other_income_entries=[OSOtherIncomeEntry(nature="Royalty", amount=Decimal("50000"))],
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-VIA-053")


def test_VIA_053_80rrb_with_form_10cce_ack_passes():
    inp = _base_input(
        deduction_80rrb=Decimal("50000"), form_10cce_ack_number_80rrb="ACK654321",
        os_other_income_entries=[OSOtherIncomeEntry(nature="Royalty", amount=Decimal("50000"))],
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-VIA-053")


def test_VIA_042_80ccd2_all_pensioner_employers_fails():
    inp = _base_input(
        deductions_chapter6a=Chapter6ADeductions(amount_80ccd2=Decimal("50000")),
        employer_filing_details=[_employer_detail(nature_of_employment="PE")],
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-VIA-042")


def test_VIA_042_80ccd2_active_employer_passes():
    inp = _base_input(
        deductions_chapter6a=Chapter6ADeductions(amount_80ccd2=Decimal("50000")),
        employer_filing_details=[_employer_detail(nature_of_employment="CGOV")],
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-VIA-042")


def test_VIA_043_80ccd1_claimed_without_pran_fails():
    inp = _base_input(deductions_chapter6a=Chapter6ADeductions(amount_80ccd1=Decimal("50000")))
    assert failed(validate_itr2_input(inp), "ITR2-IN-VIA-043")


def test_VIA_043_80ccd1_claimed_with_pran_passes():
    inp = _base_input(
        deductions_chapter6a=Chapter6ADeductions(amount_80ccd1=Decimal("50000")),
        pran_number="123456789012",
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-VIA-043")


def test_VIA_044_pran_present_without_ccd_claim_emits_advisory():
    inp = _base_input(pran_number="123456789012")
    assert emitted(validate_itr2_input(inp), "ITR2-IN-VIA-044")
    assert not failed(validate_itr2_input(inp), "ITR2-IN-VIA-044")


def test_VIA_045_80d_policy_row_missing_insurer_details_fails():
    inp = _base_input(schedule_80d=Schedule80D(
        premium_1a_non_senior=Decimal("10000"),
        policies=[InsurancePolicy(section="1a", premium_paid=Decimal("10000"))],
    ))
    assert failed(validate_itr2_input(inp), "ITR2-IN-VIA-045")


def test_VIA_045_80d_policy_row_with_insurer_details_passes():
    inp = _base_input(schedule_80d=Schedule80D(
        premium_1a_non_senior=Decimal("10000"),
        policies=[InsurancePolicy(
            section="1a", premium_paid=Decimal("10000"),
            insurer_name="LIC", policy_number="POL123",
        )],
    ))
    assert not failed(validate_itr2_input(inp), "ITR2-IN-VIA-045")


def test_VIA_046_80d_bucket_breakup_mismatches_premium_fails():
    inp = _base_input(schedule_80d=Schedule80D(
        premium_1a_non_senior=Decimal("15000"),
        policies=[InsurancePolicy(
            section="1a", premium_paid=Decimal("10000"),
            insurer_name="LIC", policy_number="POL123",
        )],
    ))
    assert failed(validate_itr2_input(inp), "ITR2-IN-VIA-046")


def test_VIA_046_80d_bucket_breakup_matches_premium_passes():
    inp = _base_input(schedule_80d=Schedule80D(
        premium_1a_non_senior=Decimal("10000"),
        policies=[InsurancePolicy(
            section="1a", premium_paid=Decimal("10000"),
            insurer_name="LIC", policy_number="POL123",
        )],
    ))
    assert not failed(validate_itr2_input(inp), "ITR2-IN-VIA-046")


def test_VIA_047_80ee_claimed_before_24b_limit_exhausted_fails():
    inp = _base_input(
        deductions_chapter6a=Chapter6ADeductions(amount_80ee=Decimal("30000")),
        house_property_income=HousePropertyIncome(
            property_type=PropertyType.SELF_OCCUPIED, home_loan_interest_paid=Decimal("100000"),
        ),
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-VIA-047")


def test_VIA_047_80ee_claimed_after_24b_limit_exhausted_passes():
    inp = _base_input(
        deductions_chapter6a=Chapter6ADeductions(amount_80ee=Decimal("30000")),
        house_property_income=HousePropertyIncome(
            property_type=PropertyType.LET_OUT, home_loan_interest_paid=Decimal("250000"),
            annual_rent_received=Decimal("300000"),
        ),
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-VIA-047")


# ─── Phase 3: completing Partially Implemented rules (#152/#207/#342/#547/
# #549/#596/#621/#622/#464) ─────────────────────────────────────────────

def test_VIA_048_80qqb_80rrb_new_regime_fails():
    inp = _base_input(
        tax_regime=TaxRegime.NEW, deduction_80qqb=Decimal("50000"),
        os_other_income_entries=[OSOtherIncomeEntry(nature="Royalty", amount=Decimal("50000"))],
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-VIA-048")


def test_VIA_048_80qqb_80rrb_old_regime_passes():
    inp = _base_input(
        deduction_80qqb=Decimal("50000"),
        os_other_income_entries=[OSOtherIncomeEntry(nature="Royalty", amount=Decimal("50000"))],
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-VIA-048")


def test_SAL_030_new_regime_standard_deduction_excess_fails():
    inp = _base_input(
        tax_regime=TaxRegime.NEW,
        salary_income=SalaryIncome(gross_salary=Decimal("500000"), standard_deduction_claimed=Decimal("80000")),
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-SAL-030")


def test_SAL_030_new_regime_standard_deduction_within_cap_passes():
    inp = _base_input(
        tax_regime=TaxRegime.NEW,
        salary_income=SalaryIncome(gross_salary=Decimal("500000"), standard_deduction_claimed=Decimal("75000")),
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-SAL-030")


def test_SAL_032_judge_exemption_under_new_regime_fails():
    """CBDT rule #686: the judge's Section 10 exemption (EIC) is not
    available under the new tax regime."""
    inp = _base_input(
        tax_regime=TaxRegime.NEW,
        salary_income=SalaryIncome(gross_salary=Decimal("500000")),
        employer_filing_details=[_employer_detail(section10_exemption_rows=[
            {"SalNatureDesc": "EIC", "SalOthNatOfInc": "Judge exemption", "SalOthAmount": Decimal("50000")},
        ])],
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-SAL-032")


def test_SAL_032_judge_exemption_under_old_regime_passes():
    inp = _base_input(
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("500000")),
        employer_filing_details=[_employer_detail(section10_exemption_rows=[
            {"SalNatureDesc": "EIC", "SalOthNatOfInc": "Judge exemption", "SalOthAmount": Decimal("50000")},
        ])],
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-SAL-032")


def test_SAL_032_new_regime_without_judge_exemption_is_a_no_op():
    inp = _base_input(
        tax_regime=TaxRegime.NEW,
        salary_income=SalaryIncome(gross_salary=Decimal("500000")),
        employer_filing_details=[_employer_detail(section10_exemption_rows=[
            {"SalNatureDesc": "10(17)", "SalOthNatOfInc": "MP/MLA allowance", "SalOthAmount": Decimal("10000")},
        ])],
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-SAL-032")


def test_HP_015_80ee_loan_not_in_table_24b_fails():
    inp = _base_input(
        deductions_chapter6a=Chapter6ADeductions(amount_80ee=Decimal("50000")),
        loan_details_80ee_list=[_loan_80ee_entry(account_or_reference_number="HL999")],
        house_property_income=HousePropertyIncome(
            property_type=PropertyType.SELF_OCCUPIED, home_loan_interest_paid=Decimal("100000"),
        ),
        property_filing_details=[PropertyFilingDetail(
            address_detail="1 MG Road", city_or_town_or_district="Pune", state_code="27",
            pin_code="411001",
            home_loan_details=[HomeLoanDetail(
                loan_taken_from="B", bank_or_institution_name="SBI",
                loan_account_or_ref_no="HL111", date_of_loan=date(2020, 1, 1),
                total_loan_amount=Decimal("2000000"), loan_outstanding_amount=Decimal("1500000"),
                interest_this_year=Decimal("100000"),
            )],
        )],
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-HP-015")


def test_HP_015_80ee_loan_in_table_24b_passes():
    inp = _base_input(
        deductions_chapter6a=Chapter6ADeductions(amount_80ee=Decimal("50000")),
        loan_details_80ee_list=[_loan_80ee_entry(account_or_reference_number="HL111")],
        house_property_income=HousePropertyIncome(
            property_type=PropertyType.SELF_OCCUPIED, home_loan_interest_paid=Decimal("100000"),
        ),
        property_filing_details=[PropertyFilingDetail(
            address_detail="1 MG Road", city_or_town_or_district="Pune", state_code="27",
            pin_code="411001",
            home_loan_details=[HomeLoanDetail(
                loan_taken_from="B", bank_or_institution_name="SBI",
                loan_account_or_ref_no="HL111", date_of_loan=date(2020, 1, 1),
                total_loan_amount=Decimal("2000000"), loan_outstanding_amount=Decimal("1500000"),
                interest_this_year=Decimal("100000"),
            )],
        )],
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-HP-015")


def test_TDS_021_tds2_claimed_without_head_of_income_fails():
    inp = _base_input(tds2_entries=[{
        "deductor_tan": "MUMA12345B", "tds_section": "194A",
        "gross_amount": Decimal("10000"), "tds_deducted": Decimal("1000"),
        "tds_claimed_this_year": Decimal("1000"),
    }])
    assert failed(validate_itr2_input(inp), "ITR2-IN-TDS-021")


def test_TDS_021_tds2_claimed_with_head_of_income_passes():
    inp = _base_input(tds2_entries=[{
        "deductor_tan": "MUMA12345B", "tds_section": "194A",
        "gross_amount": Decimal("10000"), "tds_deducted": Decimal("1000"),
        "tds_claimed_this_year": Decimal("1000"), "head_of_income": "OS",
    }])
    assert not failed(validate_itr2_input(inp), "ITR2-IN-TDS-021")


def test_VIA_049_80ggc_contribution_outside_ay_date_range_fails():
    inp = _base_input(schedule_80ggc=Schedule80GGC(contributions=[{
        "amount": Decimal("10000"), "contribution_date": "2024-06-01",
    }]))
    assert failed(validate_itr2_input(inp), "ITR2-IN-VIA-049")


def test_VIA_049_80ggc_contribution_within_ay_date_range_passes():
    inp = _base_input(schedule_80ggc=Schedule80GGC(contributions=[{
        "amount": Decimal("10000"), "contribution_date": "2025-06-01",
    }]))
    assert not failed(validate_itr2_input(inp), "ITR2-IN-VIA-049")


def test_HP_017_co_owner_missing_pan_fails():
    inp = _base_input(
        house_property_income=HousePropertyIncome(
            property_type=PropertyType.LET_OUT, annual_rent_received=Decimal("100000"),
        ),
        property_filing_details=[PropertyFilingDetail(
            address_detail="1 MG Road", city_or_town_or_district="Pune", state_code="27",
            pin_code="411001", co_owned=True, assessee_share_percent=Decimal("50"),
            co_owner_details=[CoOwnerDetail(name="Co-Owner", percent_share=Decimal("50"))],
        )],
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-HP-017")


def test_SAL_031_new_regime_old_only_section10_code_fails():
    """CBDT rule #54: the plain (non-115BAC) 10(14)(i)/10(14)(ii)/10(17)
    codes are old-regime-only."""
    inp = _base_input(
        tax_regime=TaxRegime.NEW,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        employer_filing_details=[_employer_detail(section10_exemption_rows=[
            {"SalNatureDesc": "10(17)", "SalOthNatOfInc": "MP allowance", "SalOthAmount": 5000},
        ])],
    )
    assert failed(validate_itr2_input(inp), "ITR2-IN-SAL-031")


def test_SAL_031_new_regime_115bac_variant_passes():
    inp = _base_input(
        tax_regime=TaxRegime.NEW,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        employer_filing_details=[_employer_detail(section10_exemption_rows=[
            {"SalNatureDesc": "10(14)(i)(115BAC)", "SalOthNatOfInc": "Rule 2BB", "SalOthAmount": 5000},
        ])],
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-SAL-031")


def test_SAL_031_old_regime_plain_code_passes():
    inp = _base_input(
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        employer_filing_details=[_employer_detail(section10_exemption_rows=[
            {"SalNatureDesc": "10(17)", "SalOthNatOfInc": "MP allowance", "SalOthAmount": 5000},
        ])],
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-SAL-031")


def test_HP_017_co_owner_with_pan_passes():
    inp = _base_input(
        house_property_income=HousePropertyIncome(
            property_type=PropertyType.LET_OUT, annual_rent_received=Decimal("100000"),
        ),
        property_filing_details=[PropertyFilingDetail(
            address_detail="1 MG Road", city_or_town_or_district="Pune", state_code="27",
            pin_code="411001", co_owned=True, assessee_share_percent=Decimal("50"),
            co_owner_details=[CoOwnerDetail(
                name="Co-Owner", pan="XYZPN9876G", percent_share=Decimal("50"),
            )],
        )],
    )
    assert not failed(validate_itr2_input(inp), "ITR2-IN-HP-017")
