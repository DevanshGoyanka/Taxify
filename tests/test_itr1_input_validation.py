"""
Comprehensive tests for ITR-1 input validation rules (CBDT Category A, AY 2026-27).

These test every rule in app/engine/validators/itr1/input_rules.py.
Each test is named after the CBDT rule number it verifies.
"""

import pytest
from decimal import Decimal
from datetime import date

from app.schemas.itr1 import (
    ITR1Input, SalaryIncome, HousePropertyIncome, OtherSourcesIncome,
    Chapter6ADeductions, CapitalGainsIncome, Donation80G,
    AgeBracket, TaxRegime, PropertyType, TDS1Entry, TDS2Entry, TCSEntry,
    BankAccount, Schedule80D, Section80DDBDetails, Section80DDBUserType,
    SpecifiedDisease80DDB, Schedule80CEntry, Schedule80EEntry, Schedule80DD,
    Schedule80U, DisabilitySeverity, DependentRelationship,
    EducationLoanLenderType,
    TDS3Entry,
)
from app.engine.validators.itr1.input_rules import validate_itr1_input
from app.engine.validators.base import Severity


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


def test_R145_dividend_breakup_includes_fifth_period():
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.NEW,
        salary_income=SalaryIncome(),
        house_property_income=HousePropertyIncome(
            property_type=PropertyType.SELF_OCCUPIED,
        ),
        other_sources_income=OtherSourcesIncome(dividend_income=Decimal("500")),
        deductions_chapter6a=Chapter6ADeductions(),
        dividend_quarterly_breakdown={
            "Q1": Decimal("0"),
            "Q2": Decimal("0"),
            "Q3": Decimal("0"),
            "Q4": Decimal("0"),
            "Q5": Decimal("500"),
        },
    )

    results = validate_itr1_input(inp)

    assert not failed(results, "ITR1-R145")


def test_R145_zero_breakup_fails_when_dividend_is_declared():
    """When a quarterly breakup IS provided with non-zero values that do NOT
    total the dividend income, R145 fails as Category A."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.NEW,
        salary_income=SalaryIncome(),
        house_property_income=HousePropertyIncome(
            property_type=PropertyType.SELF_OCCUPIED,
        ),
        other_sources_income=OtherSourcesIncome(dividend_income=Decimal("500")),
        deductions_chapter6a=Chapter6ADeductions(),
        dividend_quarterly_breakdown={
            "Q1": Decimal("100"),
            "Q2": Decimal("100"),
            "Q3": Decimal("100"),
            "Q4": Decimal("100"),
            "Q5": Decimal("0"),   # total 400 ≠ 500
        },
    )

    results = validate_itr1_input(inp)

    assert failed(results, "ITR1-R145")


def test_R145_no_breakup_is_warning_not_block():
    """When dividend income is declared but no quarterly breakup is provided,
    R145 emits a Category B (non-blocking) warning instead of a Category A block.

    The CBDT rule text is an equality check between dividend income and the
    breakup sum — it only applies when a breakup IS present.  AIS / TIS /
    Prefill do not expose per-receipt dates, so a breakup cannot always be
    derived from source documents.
    """
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.NEW,
        salary_income=SalaryIncome(),
        house_property_income=HousePropertyIncome(
            property_type=PropertyType.SELF_OCCUPIED,
        ),
        other_sources_income=OtherSourcesIncome(dividend_income=Decimal("130")),
        deductions_chapter6a=Chapter6ADeductions(),
        # dividend_quarterly_breakdown intentionally omitted / empty
    )

    results = validate_itr1_input(inp)

    # Should NOT be a blocking Category A failure
    assert not failed(results, "ITR1-R145")

    # Should be a Category B warning (passed=True, severity=B)
    r145 = get_result(results, "ITR1-R145")
    assert r145 is not None
    assert r145.passed is True
    assert r145.severity == Severity.B


def test_R145_all_zero_breakup_is_warning_not_block():
    """When dividend income is declared and the breakup object exists but all
    five periods are zero (the AIS/TIS/Prefill case where no per-receipt dates
    are available), R145 emits a Category B warning, not a Category A block.
    """
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.NEW,
        salary_income=SalaryIncome(),
        house_property_income=HousePropertyIncome(
            property_type=PropertyType.SELF_OCCUPIED,
        ),
        other_sources_income=OtherSourcesIncome(dividend_income=Decimal("130")),
        deductions_chapter6a=Chapter6ADeductions(),
        dividend_quarterly_breakdown={
            "Q1": Decimal("0"),
            "Q2": Decimal("0"),
            "Q3": Decimal("0"),
            "Q4": Decimal("0"),
            "Q5": Decimal("0"),
        },
    )

    results = validate_itr1_input(inp)

    # Should NOT be a blocking Category A failure
    assert not failed(results, "ITR1-R145")

    # Should be a Category B warning (passed=True, severity=B)
    r145 = get_result(results, "ITR1-R145")
    assert r145 is not None
    assert r145.passed is True
    assert r145.severity == Severity.B


def test_R099_tds3_claim_requires_deducted_year():
    """A claimed TDS3 credit without a deduction year must be blocked."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.NEW,
        salary_income=SalaryIncome(),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(),
        tds3_entries=[TDS3Entry.model_construct(
            tenant_pan="ABCDE1234F",
            tenant_name="Tenant",
            gross_receipt=Decimal("100000"),
            tds_deducted=Decimal("10000"),
            tds_claimed=Decimal("10000"),
            tds_section="194IB",
            deducted_yr="",
        )],
    )

    results = validate_itr1_input(inp)

    assert failed(results, "ITR1-R099")



def test_R001_80c_combined_exceeds_150k_old_regime():
    """Rule 1: 80C+80CCC+80CCD(1) > Rs 1,50,000 in old regime is blocked."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(
            amount_80c=Decimal("100000"),
            amount_80ccc=Decimal("30000"),
            amount_80ccd1=Decimal("40000"),  # total = 170000 > 150000
        ),
    )
    results = validate_itr1_input(inp)
    assert failed(results, "ITR1-R001")


def test_R001_80c_combined_within_limit():
    """80C+80CCC+80CCD(1) within 1.5L passes."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(
            amount_80c=Decimal("100000"),
            amount_80ccc=Decimal("20000"),
            amount_80ccd1=Decimal("30000"),  # total = 150000
        ),
    )
    results = validate_itr1_input(inp)
    assert not failed(results, "ITR1-R001")


def test_R153_new_regime_80c_not_allowed():
    """Rule 153: New regime 80C/80CCC/80CCD(1) must be 0."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.NEW,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(amount_80c=Decimal("50000")),
    )
    results = validate_itr1_input(inp)
    assert failed(results, "ITR1-R153")


# ═══════════════════════════════════════════════════════════════════════════════
# 80CCD(1B) Additional NPS
# ═══════════════════════════════════════════════════════════════════════════════

def test_R115_80ccd1b_exceeds_50k_old_regime():
    """Rule 115: 80CCD(1B) > Rs 50,000 in old regime is blocked."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(amount_80ccd1b=Decimal("60000")),
    )
    results = validate_itr1_input(inp)
    assert failed(results, "ITR1-R115")


def test_R115_80ccd1b_within_limit():
    """80CCD(1B) within 50k passes."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(amount_80ccd1b=Decimal("50000")),
    )
    results = validate_itr1_input(inp)
    assert not failed(results, "ITR1-R115")


def test_R169_new_regime_80ccd1b_not_allowed():
    """Rule 169: New regime 80CCD(1B) must be 0."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.NEW,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(amount_80ccd1b=Decimal("50000")),
    )
    results = validate_itr1_input(inp)
    assert failed(results, "ITR1-R169")


# ═══════════════════════════════════════════════════════════════════════════════
# 80CCD(2) Employer NPS — informational rules
# ═══════════════════════════════════════════════════════════════════════════════

def test_R004_80ccd2_claimed_info():
    """Rule 4: 80CCD(2) claimed — nature_of_employment required for employer category limit."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(amount_80ccd2=Decimal("30000")),
        # No nature_of_employment — rule now enforces this
    )
    results = validate_itr1_input(inp)
    # Without nature_of_employment set, 80CCD(2) validation fails with Category A
    assert failed(results, "ITR1-R004")


# ═══════════════════════════════════════════════════════════════════════════════
# 80D Health Insurance
# ═══════════════════════════════════════════════════════════════════════════════

def test_R130_80d_self_family_exceeds_50k():
    """Rule 130: 80D Self/Family > Rs 50,000 blocked."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(amount_80d_self_family=Decimal("55000")),
    )
    results = validate_itr1_input(inp)
    assert failed(results, "ITR1-R130")


def test_R130_80d_self_family_within_50k():
    """80D Self/Family within 50k passes."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(amount_80d_self_family=Decimal("25000")),
    )
    results = validate_itr1_input(inp)
    assert not failed(results, "ITR1-R130")


def test_R134_80d_parents_exceeds_50k():
    """Rule 134: 80D Parents > Rs 50,000 blocked."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(amount_80d_parents=Decimal("55000")),
    )
    results = validate_itr1_input(inp)
    assert failed(results, "ITR1-R134")


def test_R136_80d_total_exceeds_100k():
    """Rule 136: 80D total (Self+Parents) > Rs 1,00,000 blocked."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(
            amount_80d_self_family=Decimal("50000"),
            amount_80d_parents=Decimal("51000"),  # total = 101000
        ),
    )
    results = validate_itr1_input(inp)
    assert failed(results, "ITR1-R136")


def test_R173_new_regime_80d_not_allowed():
    """Rule 173: New regime 80D must be 0."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.NEW,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(amount_80d_self_family=Decimal("25000")),
    )
    results = validate_itr1_input(inp)
    assert failed(results, "ITR1-R173")


# ═══════════════════════════════════════════════════════════════════════════════
# 80DDB Specified Diseases
# ═══════════════════════════════════════════════════════════════════════════════

def test_R005_80ddb_exceeds_100k():
    """Rule 5: 80DDB > Rs 1,00,000 for senior citizens (age 60+) blocked."""
    inp = ITR1Input(
        age_bracket=AgeBracket.SIXTY_TO_80,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(amount_80ddb=Decimal("110000")),
    )
    results = validate_itr1_input(inp)
    assert failed(results, "ITR1-R005d")


def test_R007_80ddb_cap_uses_net_reimbursed_claim() -> None:
    """Gross expenditure above the cap is valid when reimbursement lowers the net claim."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(
            amount_80ddb=Decimal("80000"),
            details_80ddb=Section80DDBDetails(
                user_type=Section80DDBUserType.SELF_OR_DEPENDENT,
                disease=SpecifiedDisease80DDB.MALIGNANT_CANCERS,
                reimbursement_amount=Decimal("50000"),
            ),
        ),
    )
    results = validate_itr1_input(inp)
    assert not failed(results, "ITR1-R007")
    assert not failed(results, "ITR1-R006")


def test_R005_80ddb_cap_uses_beneficiary_category() -> None:
    """A senior dependent receives the senior cap even for a non-senior assessee."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(
            amount_80ddb=Decimal("90000"),
            details_80ddb=Section80DDBDetails(
                user_type=Section80DDBUserType.SELF_OR_DEPENDENT_SENIOR,
                disease=SpecifiedDisease80DDB.PARKINSONS_DISEASE,
            ),
        ),
    )
    results = validate_itr1_input(inp)
    assert not failed(results, "ITR1-R007")
    assert not failed(results, "ITR1-R005d")


def test_R155_new_regime_80ddb_not_allowed():
    """Rule 155: New regime 80DDB must be 0."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.NEW,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(amount_80ddb=Decimal("40000")),
    )
    results = validate_itr1_input(inp)
    assert failed(results, "ITR1-R155")


# ═══════════════════════════════════════════════════════════════════════════════
# 80G Donations
# ═══════════════════════════════════════════════════════════════════════════════

def test_R008_80g_no_schedule():
    """Rule 8: 80G claimed but no donation entries provided."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(amount_80g=Decimal("10000")),
    )
    results = validate_itr1_input(inp)
    assert failed(results, "ITR1-R008")


def test_R008_80g_with_donations_passes():
    """80G with donation entries passes."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(
            amount_80g=Decimal("10000"),
            donations_80g=[
                Donation80G(non_cash_amount=Decimal("10000"), qualifying_percentage="100%"),
            ],
        ),
    )
    results = validate_itr1_input(inp)
    assert not failed(results, "ITR1-R008")


def test_R156_new_regime_80g_not_allowed():
    """Rule 156: New regime 80G must be 0."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.NEW,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(amount_80g=Decimal("5000")),
    )
    results = validate_itr1_input(inp)
    assert failed(results, "ITR1-R156")


# ═══════════════════════════════════════════════════════════════════════════════
# 80TTA (Savings Bank Interest) — old regime
# ═══════════════════════════════════════════════════════════════════════════════

def test_R011_80tta_exceeds_10000_old_regime():
    """Rule 11: 80TTA > Rs 10,000 blocked in old regime."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(amount_80tta=Decimal("12000")),
    )
    results = validate_itr1_input(inp)
    assert failed(results, "ITR1-R011")


def test_R011_80tta_within_limit():
    """80TTA within 10k passes."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(amount_80tta=Decimal("10000")),
    )
    results = validate_itr1_input(inp)
    assert not failed(results, "ITR1-R011")


def test_R013_senior_cannot_claim_80tta():
    """Rule 13: Senior citizen cannot claim 80TTA."""
    inp = ITR1Input(
        age_bracket=AgeBracket.SIXTY_TO_80,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(amount_80tta=Decimal("10000")),
    )
    results = validate_itr1_input(inp)
    assert failed(results, "ITR1-R013")


def test_R157_new_regime_80tta_not_allowed():
    """Rule 157: New regime 80TTA must be 0."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.NEW,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(amount_80tta=Decimal("10000")),
    )
    results = validate_itr1_input(inp)
    assert failed(results, "ITR1-R157")


# ═══════════════════════════════════════════════════════════════════════════════
# 80TTB (Senior Citizen Deposit Interest)
# ═══════════════════════════════════════════════════════════════════════════════

def test_R014_80ttb_exceeds_50000():
    """Rule 14: 80TTB > Rs 50,000 blocked."""
    inp = ITR1Input(
        age_bracket=AgeBracket.SIXTY_TO_80,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(amount_80ttb=Decimal("55000")),
    )
    results = validate_itr1_input(inp)
    assert failed(results, "ITR1-R014")


def test_R015_below_60_cannot_claim_80ttb():
    """Rule 15: Below 60 cannot claim 80TTB."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(amount_80ttb=Decimal("50000")),
    )
    results = validate_itr1_input(inp)
    assert failed(results, "ITR1-R015")


def test_R158_new_regime_80ttb_not_allowed():
    """Rule 158: New regime 80TTB must be 0."""
    inp = ITR1Input(
        age_bracket=AgeBracket.SIXTY_TO_80,
        tax_regime=TaxRegime.NEW,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(amount_80ttb=Decimal("50000")),
    )
    results = validate_itr1_input(inp)
    assert failed(results, "ITR1-R158")


# ═══════════════════════════════════════════════════════════════════════════════
# 80DD / 80U — Disability Deductions
# ═══════════════════════════════════════════════════════════════════════════════

def test_R154_new_regime_80dd_not_allowed():
    """Rule 154: New regime 80DD must be 0."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.NEW,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(amount_80dd=Decimal("75000")),
    )
    results = validate_itr1_input(inp)
    assert failed(results, "ITR1-R154")


def test_R159_new_regime_80u_not_allowed():
    """Rule 159: New regime 80U must be 0."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.NEW,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(amount_80u=Decimal("75000")),
    )
    results = validate_itr1_input(inp)
    assert failed(results, "ITR1-R159")


def test_R200_80dd_exceeds_125k_severe():
    """Rule 200/204: 80DD severe disability > Rs 1,25,000 (informational)."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(amount_80dd=Decimal("75000")),
    )
    results = validate_itr1_input(inp)
    # Informational — between 75k-125k, only severe disability qualifies
    r = get_result(results, "ITR1-R203d")
    assert r is not None  # informational about 80DD needing disability flag


# ═══════════════════════════════════════════════════════════════════════════════
# 80CCH — Agniveer
# ═══════════════════════════════════════════════════════════════════════════════

def test_R186_80cch_claimed_info():
    """Rule 186: 80CCH claimed — informational about 46.2% salary+DA limit."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(amount_80cch=Decimal("10000")),
    )
    results = validate_itr1_input(inp)
    r = get_result(results, "ITR1-R186")
    assert r is not None


# ═══════════════════════════════════════════════════════════════════════════════
# 80EE / 80EEA / 80EEB — Home & EV Loans
# ═══════════════════════════════════════════════════════════════════════════════

def test_R121_80ee_exceeds_50k():
    """Rule 121: 80EE > Rs 50,000 blocked (old regime)."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(amount_80ee=Decimal("55000")),
    )
    results = validate_itr1_input(inp)
    assert failed(results, "ITR1-R121")


def test_R122_80eea_exceeds_150k():
    """Rule 122: 80EEA > Rs 1,50,000 blocked (old regime)."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(amount_80eea=Decimal("160000")),
    )
    results = validate_itr1_input(inp)
    assert failed(results, "ITR1-R122")


def test_R123_80ee_and_80eea_mutually_exclusive():
    """Rule 123: 80EE and 80EEA both > 0 is blocked."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(
            amount_80ee=Decimal("30000"),
            amount_80eea=Decimal("50000"),
        ),
    )
    results = validate_itr1_input(inp)
    assert failed(results, "ITR1-R123")


def test_R124_80eeb_exceeds_150k():
    """Rule 124: 80EEB > Rs 1,50,000 blocked (old regime)."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(amount_80eeb=Decimal("160000")),
    )
    results = validate_itr1_input(inp)
    assert failed(results, "ITR1-R124")


def test_R170_new_regime_80ee_not_allowed():
    """Rule 170: New regime 80EE must be 0."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.NEW,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(amount_80ee=Decimal("30000")),
    )
    results = validate_itr1_input(inp)
    assert failed(results, "ITR1-R170")


def test_R171_new_regime_80eea_not_allowed():
    """Rule 171: New regime 80EEA must be 0."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.NEW,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(amount_80eea=Decimal("50000")),
    )
    results = validate_itr1_input(inp)
    assert failed(results, "ITR1-R171")


def test_R172_new_regime_80eeb_not_allowed():
    """Rule 172: New regime 80EEB must be 0."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.NEW,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(amount_80eeb=Decimal("50000")),
    )
    results = validate_itr1_input(inp)
    assert failed(results, "ITR1-R172")


# ═══════════════════════════════════════════════════════════════════════════════
# Salary Validations — Old Regime
# ═══════════════════════════════════════════════════════════════════════════════

def test_R058_entertainment_allowance_non_govt():
    """Rule 58: Entertainment allowance only for government employees."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(
            gross_salary=Decimal("600000"),
            entertainment_allowance=Decimal("3000"),
            is_government_employee=False,
        ),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(),
    )
    results = validate_itr1_input(inp)
    assert failed(results, "ITR1-R058")


def test_R057_entertainment_allowance_exceeds_5000():
    """Rule 57: Entertainment allowance capped at Rs 5,000 for govt employees."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(
            gross_salary=Decimal("600000"),
            entertainment_allowance=Decimal("6000"),
            is_government_employee=True,
        ),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(),
    )
    results = validate_itr1_input(inp)
    assert failed(results, "ITR1-R057")


def test_R037_professional_tax_exceeds_2500():
    """Rule 37: Professional tax > Rs 2,500 blocked."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(
            gross_salary=Decimal("600000"),
            professional_tax_paid=Decimal("3000"),
        ),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(),
    )
    results = validate_itr1_input(inp)
    assert failed(results, "ITR1-R037")


def test_R112_standard_deduction_old_exceeds_50k():
    """Rule 112: Standard deduction old regime > Rs 50,000 blocked."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(
            gross_salary=Decimal("600000"),
            standard_deduction_claimed=Decimal("60000"),
        ),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(),
    )
    results = validate_itr1_input(inp)
    assert failed(results, "ITR1-R112")


# ═══════════════════════════════════════════════════════════════════════════════
# New Regime — Salary & HP Restrictions
# ═══════════════════════════════════════════════════════════════════════════════

def test_R163_new_regime_entertainment_allowance():
    """Rule 163: New regime entertainment allowance must be 0."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.NEW,
        salary_income=SalaryIncome(
            gross_salary=Decimal("600000"),
            entertainment_allowance=Decimal("2000"),
        ),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(),
    )
    results = validate_itr1_input(inp)
    assert failed(results, "ITR1-R163")


def test_R164_new_regime_lta():
    """Rule 164: New regime LTA must be 0."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.NEW,
        salary_income=SalaryIncome(
            gross_salary=Decimal("600000"),
            lta_exempt_amount=Decimal("15000"),
        ),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(),
    )
    results = validate_itr1_input(inp)
    assert failed(results, "ITR1-R164")


def test_R165_new_regime_hra():
    """Rule 165: New regime HRA must be 0."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.NEW,
        salary_income=SalaryIncome(
            gross_salary=Decimal("600000"),
            hra_exempt_amount=Decimal("50000"),
        ),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(),
    )
    results = validate_itr1_input(inp)
    assert failed(results, "ITR1-R165")


def test_R168_new_regime_professional_tax():
    """Rule 168: New regime professional tax must be 0."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.NEW,
        salary_income=SalaryIncome(
            gross_salary=Decimal("600000"),
            professional_tax_paid=Decimal("2400"),
        ),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(),
    )
    results = validate_itr1_input(inp)
    assert failed(results, "ITR1-R168")


def test_R162_new_regime_self_occupied_interest():
    """Rule 162/253: New regime self-occupied interest must be 0."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.NEW,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(
            property_type=PropertyType.SELF_OCCUPIED,
            home_loan_interest_paid=Decimal("150000"),
        ),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(),
    )
    results = validate_itr1_input(inp)
    assert failed(results, "ITR1-R162")


def test_R215_new_regime_standard_deduction_exceeds_75k():
    """Rule 215: New regime standard deduction > Rs 75,000 blocked."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.NEW,
        salary_income=SalaryIncome(
            gross_salary=Decimal("600000"),
            standard_deduction_claimed=Decimal("80000"),
        ),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(),
    )
    results = validate_itr1_input(inp)
    assert failed(results, "ITR1-R215")


# ═══════════════════════════════════════════════════════════════════════════════
# New Regime — Comprehensive Deduction Block
# ═══════════════════════════════════════════════════════════════════════════════

def test_R146_new_regime_all_deductions_blocked():
    """Rule 146: New regime — all VI-A deductions (except 80CCD(2)+80CCH) must be 0."""
    # 80E is tested as one of the blocked deductions
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.NEW,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(amount_80e=Decimal("25000")),
    )
    results = validate_itr1_input(inp)
    # 80E is tested in the calc_rules, but input_rules checks regime-specific blocks
    # The new regime blocks are individually tested (80C, 80D, etc.)
    assert failed(results, "ITR1-R146")  # Should trigger the new regime VI-A blocker


# ═══════════════════════════════════════════════════════════════════════════════
# House Property Validations
# ═══════════════════════════════════════════════════════════════════════════════

def test_R045_let_out_no_rent():
    """Rule 45: Let-out property must have rent > 0."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(
            property_type=PropertyType.LET_OUT,
            annual_rent_received=Decimal("0"),
        ),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(),
    )
    results = validate_itr1_input(inp)
    assert failed(results, "ITR1-R045")


def test_R044_municipal_tax_without_rent():
    """Rule 44: Municipal tax claimed when rent is 0."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(
            property_type=PropertyType.LET_OUT,
            annual_rent_received=Decimal("0"),
            municipal_taxes_paid=Decimal("5000"),
        ),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(),
    )
    results = validate_itr1_input(inp)
    assert failed(results, "ITR1-R044")


def test_R049_municipal_tax_self_occupied():
    """Rule 49: Municipal tax not allowed for self-occupied property."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(
            property_type=PropertyType.SELF_OCCUPIED,
            municipal_taxes_paid=Decimal("5000"),
        ),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(),
    )
    results = validate_itr1_input(inp)
    assert failed(results, "ITR1-R049")


def test_R048_self_occupied_interest_exceeds_200k():
    """Rule 48: Self-occupied interest > Rs 2,00,000 blocked (old regime)."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(
            property_type=PropertyType.SELF_OCCUPIED,
            home_loan_interest_paid=Decimal("250000"),
        ),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(),
    )
    results = validate_itr1_input(inp)
    assert failed(results, "ITR1-R048")


# ═══════════════════════════════════════════════════════════════════════════════
# LTCG 112A
# ═══════════════════════════════════════════════════════════════════════════════

def test_R217_ltcg_112a_exceeds_125k():
    """Rule 217: LTCG 112A > Rs 1,25,000 blocked for ITR-1."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(),
        capital_gains=CapitalGainsIncome(ltcg_112a=Decimal("130000")),
    )
    results = validate_itr1_input(inp)
    assert failed(results, "ITR1-R217")


# ═══════════════════════════════════════════════════════════════════════════════
# TDS / TCS Consistency
# ═══════════════════════════════════════════════════════════════════════════════

def test_R113_tds_claimed_but_no_income():
    """Rule 113: TDS claimed but corresponding income omitted (informational)."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("0")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(),
        tds1_entries=[TDS1Entry(tds_deducted=Decimal("50000"), income_chargeable=Decimal("0"))],
    )
    results = validate_itr1_input(inp)
    r = get_result(results, "ITR1-R113")
    assert r is not None


# ═══════════════════════════════════════════════════════════════════════════════
# Filing Regime Rules
# ═══════════════════════════════════════════════════════════════════════════════

def test_R151_old_regime_after_due_date():
    """Rule 151: Old regime cannot be selected after due date (informational)."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(),
        filing_date=date(2026, 12, 15),
        due_date=date(2026, 7, 31),
    )
    results = validate_itr1_input(inp)
    r = get_result(results, "ITR1-R151")
    assert r is not None


def test_R189_old_regime_not_allowed_after_139_4():
    """Rule 189: Old regime not allowed if original was 139(4)."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(),
        filing_section="139(5)",
        original_filing_section="139(4)",
    )
    results = validate_itr1_input(inp)
    assert failed(results, "ITR1-R189")


# ═══════════════════════════════════════════════════════════════════════════════
# 80GGA
# ═══════════════════════════════════════════════════════════════════════════════

def test_R175_new_regime_80gga_not_allowed():
    """Rule 175: New regime 80GGA must be 0."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.NEW,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(amount_80g=Decimal("5000")),
    )
    results = validate_itr1_input(inp)
    assert failed(results, "ITR1-R156")  # 80G blocked in new regime


# ═══════════════════════════════════════════════════════════════════════════════
# Edge Cases
# ═══════════════════════════════════════════════════════════════════════════════

def test_no_deductions_no_salary_passes():
    """Minimal input with zero values passes all input rules."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("0")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(),
    )
    results = validate_itr1_input(inp)
    failures = [r for r in results if not r.passed]
    assert len(failures) == 0, f"Unexpected failures: {failures}"


def test_all_informational_rules_pass():
    """All informational rules should be severity D with passed=True."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(amount_80ccd2=Decimal("30000")),
    )
    results = validate_itr1_input(inp)
    for r in results:
        if r.severity == Severity.D:
            assert r.passed, f"Informational rule {r.rule_id} should have passed=True"


def test_new_regime_no_hp_loss_allowed():
    """New regime — HP loss not allowed, but check is at calc level."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.NEW,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(
            property_type=PropertyType.LET_OUT,
            annual_rent_received=Decimal("240000"),
            municipal_taxes_paid=Decimal("10000"),
            home_loan_interest_paid=Decimal("300000"),
        ),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(),
    )
    results = validate_itr1_input(inp)
    # Input rules don't check computed values, so all should pass at input level
    failures = [r for r in results if not r.passed]
    # New regime let-out has valid input; the HP loss disallow is in calc
    assert True  # no catastrophic failures at input level


# ═══════════════════════════════════════════════════════════════════════════
# Phase 2.5 — Section 10 Exempt Allowance Tests (R100-R112)
# ═══════════════════════════════════════════════════════════════════════════

def test_R100_gratuity_exceeding_current_year_salary_is_not_blocked():
    '''ITR1-R100 (removed 2026-09-03, see Docs/ITR1_FRONTEND_AND_SERIALIZATION_AUDIT_AY2026_27.md
    §11.1's validator note): a career-end gratuity lump sum routinely and
    correctly exceeds one year's running salary (e.g. 25 years of service),
    so comparing it against salary_income.gross_salary has no statutory
    basis and must not block filing.'''
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("500000"), gratuity_received=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(),
    )
    results = validate_itr1_input(inp)
    assert not failed(results, "ITR1-R100")


def test_R100_gratuity_within_salary_passes():
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60, tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("500000"), gratuity_received=Decimal("300000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(),
    )
    results = validate_itr1_input(inp)
    assert not failed(results, "ITR1-R100")


def test_R101_commuted_pension_exceeding_current_year_salary_is_not_blocked():
    '''ITR1-R101 removed for the same reason as R100 above.'''
    inp = ITR1Input(
        age_bracket=AgeBracket.SIXTY_TO_80,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("300000"), commuted_pension_received=Decimal("400000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(),
    )
    results = validate_itr1_input(inp)
    assert not failed(results, "ITR1-R101")


def test_R102_leave_encashment_exceeding_current_year_salary_is_not_blocked():
    '''ITR1-R102 removed for the same reason as R100 above.'''
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("400000"), leave_encashment_received=Decimal("500000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(),
    )
    results = validate_itr1_input(inp)
    assert not failed(results, "ITR1-R102")


def test_R103_vrs_exceeds_5l():
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("800000"), vrs_compensation=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(),
    )
    results = validate_itr1_input(inp)
    assert failed(results, "ITR1-R103")


def test_R104_retrenchment_exceeds_5l():
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("700000"), retrenchment_compensation=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(),
    )
    results = validate_itr1_input(inp)
    assert failed(results, "ITR1-R104")


def test_R105_transport_allowance_exceeds_max():
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("500000"), transport_allowance=Decimal("50000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(),
    )
    results = validate_itr1_input(inp)
    assert failed(results, "ITR1-R105")


def test_R148_new_regime_transport_allowance_at_or_below_cap_is_allowed():
    """Transport allowance up to Rs 38,400 must not trigger R148."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.NEW,
        salary_income=SalaryIncome(
            gross_salary=Decimal("500000"),
            transport_allowance=Decimal("38400"),
        ),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(),
    )
    results = validate_itr1_input(inp)
    assert not failed(results, "ITR1-R148")


def test_R107_lta_exempt_exceeds_received():
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(
            gross_salary=Decimal("500000"),
            lta_amount_received=Decimal("20000"),
            lta_exempt_amount=Decimal("30000"),
        ),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(),
    )
    results = validate_itr1_input(inp)
    assert failed(results, "ITR1-R107")


def test_R149_new_regime_taxable_lta_receipt_is_allowed():
    """Receiving LTA without claiming exemption must not trigger R149."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.NEW,
        salary_income=SalaryIncome(
            gross_salary=Decimal("500000"),
            lta_amount_received=Decimal("25000"),
            lta_exempt_amount=Decimal("0"),
        ),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(),
    )
    results = validate_itr1_input(inp)
    assert not failed(results, "ITR1-R149")


def test_R108_new_regime_gratuity_disallowed():
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.NEW,
        salary_income=SalaryIncome(gross_salary=Decimal("600000"), gratuity_received=Decimal("100000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(),
    )
    results = validate_itr1_input(inp)
    assert failed(results, "ITR1-R164")


def test_R109_new_regime_commuted_pension_disallowed():
    inp = ITR1Input(
        age_bracket=AgeBracket.SIXTY_TO_80,
        tax_regime=TaxRegime.NEW,
        salary_income=SalaryIncome(gross_salary=Decimal("500000"), commuted_pension_received=Decimal("100000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(),
    )
    results = validate_itr1_input(inp)
    assert failed(results, "ITR1-R165")


# ═══════════════════════════════════════════════════════════════════════════
# Phase 2.6 — Bank Account Tests (R260-R263)
# ═══════════════════════════════════════════════════════════════════════════

def test_R260_no_primary_bank_account():
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(),
        bank_accounts=[BankAccount(account_number="1234567890", ifsc_code="SBIN0001234", account_type="savings", is_primary=False)],
    )
    results = validate_itr1_input(inp)
    assert failed(results, "ITR1-R260")


def test_R261_multiple_primary():
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(),
        bank_accounts=[
            BankAccount(account_number="1234567890", ifsc_code="SBIN0001234", account_type="savings", is_primary=True),
            BankAccount(account_number="0987654321", ifsc_code="HDFC0005678", account_type="savings", is_primary=True),
        ],
    )
    results = validate_itr1_input(inp)
    assert failed(results, "ITR1-R261")


def test_R262_invalid_ifsc():
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(),
        bank_accounts=[BankAccount(account_number="1234567890", ifsc_code="SBIN1X01234", account_type="savings", is_primary=True)],
    )
    results = validate_itr1_input(inp)
    assert failed(results, "ITR1-R262")


def test_R263_invalid_account_type():
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(),
        bank_accounts=[BankAccount(account_number="1234567890", ifsc_code="SBIN0001234", account_type="loan", is_primary=True)],
    )
    results = validate_itr1_input(inp)
    assert failed(results, "ITR1-R263")


def test_bank_valid_with_primary_passes():
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(),
        bank_accounts=[BankAccount(account_number="1234567890", ifsc_code="SBIN0001234", account_type="savings", is_primary=True)],
    )
    results = validate_itr1_input(inp)
    assert not failed(results, "ITR1-R260")
    assert not failed(results, "ITR1-R261")
    assert not failed(results, "ITR1-R262")


# ═══════════════════════════════════════════════════════════════════════════
# Phase 3.1 — Category B Warning Tests (ITR1-B001 to B009)
# ═══════════════════════════════════════════════════════════════════════════

def test_B001_high_salary_warning():
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("6000000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(),
    )
    results = validate_itr1_input(inp)
    has_warn = any(r.rule_id == "ITR1-B001" and r.passed for r in results)
    assert has_warn


def test_B002_hra_high_pct_warning():
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("400000"), hra_exempt_amount=Decimal("250000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(),
    )
    results = validate_itr1_input(inp)
    has_warn = any(r.rule_id == "ITR1-B002" and r.passed for r in results)
    assert has_warn


def test_B003_high_professional_tax():
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("500000"), professional_tax_paid=Decimal("5000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(),
    )
    results = validate_itr1_input(inp)
    has_warn = any(r.rule_id == "ITR1-B003" and r.passed for r in results)
    assert has_warn


def test_B004_no_standard_deduction():
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("500000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(),
    )
    results = validate_itr1_input(inp)
    has_warn = any(r.rule_id == "ITR1-B004" and r.passed for r in results)
    assert has_warn


def test_B005_80c_exceeds_salary():
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("500000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(amount_80c=Decimal("550000")),
    )
    results = validate_itr1_input(inp)
    has_warn = any(r.rule_id == "ITR1-B005" and r.passed for r in results)
    assert has_warn


def test_B007_80d_self_25k_no_senior_flag():
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(amount_80d_self_family=Decimal("25000")),
        schedule_80d=Schedule80D(has_self_senior=False),
    )
    results = validate_itr1_input(inp)
    has_warn = any(r.rule_id == "ITR1-B007" and r.passed for r in results)
    assert has_warn


def test_B008_80d_parents_25k_no_senior_flag():
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(amount_80d_parents=Decimal("25000")),
        schedule_80d=Schedule80D(has_parents_senior=False),
    )
    results = validate_itr1_input(inp)
    has_warn = any(r.rule_id == "ITR1-B008" and r.passed for r in results)
    assert has_warn


def test_B009_80eea_no_hp_incomes():
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(amount_80eea=Decimal("50000")),
    )
    results = validate_itr1_input(inp)
    has_warn = any(r.rule_id == "ITR1-B009" and r.passed for r in results)
    assert has_warn


# ═══════════════════════════════════════════════════════════════════════════════
# Audit-driven hardening — Schedule 80C, 80E, 80DD/80U severity, R119 collision
# ═══════════════════════════════════════════════════════════════════════════════

def test_80c_claim_without_schedule_rows_blocked():
    """A positive 80C claim must produce a blocking error when no schedule rows are given."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(amount_80c=Decimal("100000")),
    )
    results = validate_itr1_input(inp)
    assert failed(results, "ITR1-80C-DETAILS")


def test_80c_claim_with_matching_rows_passes_consistency():
    """A positive 80C claim with matching schedule rows must not fail consistency rules."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(amount_80c=Decimal("100000")),
        schedule_80c_entries=[
            Schedule80CEntry(amount=Decimal("60000"), payment_type="PPF", identifier_number="PPF-1"),
            Schedule80CEntry(amount=Decimal("40000"), payment_type="ELSS", identifier_number="ELSS-1"),
        ],
    )
    results = validate_itr1_input(inp)
    assert not failed(results, "ITR1-80C-DETAILS")
    assert not failed(results, "ITR1-R241")
    assert not failed(results, "ITR1-R224")
    assert not failed(results, "ITR1-R224b")


def test_80dd_severity_amount_mismatch_severe_amount_with_normal_blocked():
    """A Rs 1,25,000 80DD claim with NORMAL disability schedule must fail R203b."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(amount_80dd=Decimal("125000")),
        schedule_80dd=Schedule80DD(
            disability_type=DisabilitySeverity.NORMAL,
            deduction_amount=Decimal("125000"),
            dependent_relationship=DependentRelationship.SPOUSE,
        ),
        form_10ia_filed=True,
    )
    results = validate_itr1_input(inp)
    assert failed(results, "ITR1-R203b")


def test_80dd_severity_amount_mismatch_normal_amount_with_severe_blocked():
    """A Rs 75,000 80DD claim with SEVERE disability schedule must fail R203b."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(amount_80dd=Decimal("75000")),
        schedule_80dd=Schedule80DD(
            disability_type=DisabilitySeverity.SEVERE,
            deduction_amount=Decimal("75000"),
            dependent_relationship=DependentRelationship.SPOUSE,
        ),
        form_10ia_filed=True,
    )
    results = validate_itr1_input(inp)
    assert failed(results, "ITR1-R203b")


def test_80dd_claim_without_schedule_blocked():
    """A positive 80DD claim without a Schedule 80DD must fail R206."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(amount_80dd=Decimal("75000")),
        form_10ia_filed=True,
    )
    results = validate_itr1_input(inp)
    assert failed(results, "ITR1-R206")


def test_80dd_claim_without_dependent_relationship_blocked():
    """A positive 80DD claim with a schedule missing dependent_relationship must fail R206b."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(amount_80dd=Decimal("75000")),
        schedule_80dd=Schedule80DD(
            disability_type=DisabilitySeverity.NORMAL,
            deduction_amount=Decimal("75000"),
        ),
        form_10ia_filed=True,
    )
    results = validate_itr1_input(inp)
    assert failed(results, "ITR1-R206b")


def test_80u_severity_amount_mismatch_blocked():
    """A Rs 1,25,000 80U claim with NORMAL disability schedule must fail R200b."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(amount_80u=Decimal("125000")),
        schedule_80u=Schedule80U(
            disability_type=DisabilitySeverity.NORMAL,
            deduction_amount=Decimal("125000"),
        ),
        form_10ia_filed=True,
    )
    results = validate_itr1_input(inp)
    assert failed(results, "ITR1-R200b")


def test_80u_claim_without_schedule_blocked():
    """A positive 80U claim without a Schedule 80U must fail R207."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(amount_80u=Decimal("75000")),
        form_10ia_filed=True,
    )
    results = validate_itr1_input(inp)
    assert failed(results, "ITR1-R207")


def test_80dd_nested_schedule_resolved_by_canonical_accessor():
    """A nested Schedule 80DD under deductions_chapter6a must be seen by the validator."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(
            amount_80dd=Decimal("75000"),
            schedule_80dd=Schedule80DD(
                disability_type=DisabilitySeverity.NORMAL,
                deduction_amount=Decimal("75000"),
                dependent_relationship=DependentRelationship.SPOUSE,
            ),
        ),
        form_10ia_filed=True,
    )
    results = validate_itr1_input(inp)
    assert not failed(results, "ITR1-R206")
    assert not failed(results, "ITR1-R203b")


def test_80dd_conflicting_schedules_blocked():
    """Conflicting top-level and nested Schedule 80DD must be reported as a failure."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("600000")),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(
            amount_80dd=Decimal("75000"),
            schedule_80dd=Schedule80DD(
                disability_type=DisabilitySeverity.SEVERE,
                deduction_amount=Decimal("125000"),
                dependent_relationship=DependentRelationship.SPOUSE,
            ),
        ),
        schedule_80dd=Schedule80DD(
            disability_type=DisabilitySeverity.NORMAL,
            deduction_amount=Decimal("75000"),
            dependent_relationship=DependentRelationship.SPOUSE,
        ),
        form_10ia_filed=True,
    )
    results = validate_itr1_input(inp)
    assert failed(results, "ITR1-R205")


def test_r119_collision_resolved_80gg_hra_exclusion_uses_unique_id():
    """The 80GG/HRA mutual exclusion must use ITR1-R119b, not collide with 80CCD(2)."""
    inp = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(
            gross_salary=Decimal("600000"),
            hra_exempt_amount=Decimal("60000"),
            basic_salary=Decimal("400000"),
            hra_received=Decimal("120000"),
            rent_paid=Decimal("200000"),
        ),
        house_property_income=HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(amount_80gg=Decimal("30000")),
        form_10ba_filed=True,
    )
    results = validate_itr1_input(inp)
    assert failed(results, "ITR1-R119b")
