import pytest
from decimal import Decimal
from app.schemas.itr1 import (
    ITR1Input,
    SalaryIncome,
    HousePropertyIncome,
    OtherSourcesIncome,
    Chapter6ADeductions,
    CapitalGainsIncome,
    AgeBracket,
    TaxRegime,
    PropertyType,
)
from app.engine.calculators.itr1 import compute as compute_itr1

def test_itr1_no_income():
    """Scenario 1: No income, zeros throughout."""
    itr_input = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("0")),
        house_property_income=HousePropertyIncome(
            property_type=PropertyType.SELF_OCCUPIED,
            home_loan_interest_paid=Decimal("0"),
        ),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(),
    )
    res = compute_itr1(itr_input)
    assert res.gross_total_income == Decimal("0")
    assert res.taxable_income == Decimal("0")
    assert res.net_tax_liability == Decimal("0")

def test_itr1_low_salary_exposes_complete_nil_tax_reconciliation():
    """Low salary must cap Section 16 deduction and explain nil slab tax."""
    itr_input = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.NEW,
        salary_income=SalaryIncome(gross_salary=Decimal("65000")),
        house_property_income=HousePropertyIncome(
            property_type=PropertyType.SELF_OCCUPIED,
            home_loan_interest_paid=Decimal("0"),
        ),
        other_sources_income=OtherSourcesIncome(
            savings_bank_interest=Decimal("1485"),
        ),
        deductions_chapter6a=Chapter6ADeductions(),
    )

    result = compute_itr1(itr_input)

    assert result.salary_net == Decimal("65000")
    assert result.salary_deduction_us16ia == Decimal("65000")
    assert result.salary_deduction_us16 == Decimal("65000")
    assert result.salary_income == Decimal("0")
    assert result.gross_total_income == Decimal("1485")
    assert result.total_income_before_288a == Decimal("1485")
    assert result.rounding_adjustment_288a == Decimal("5")
    assert result.taxable_income == Decimal("1490")
    assert result.basic_exemption_limit == Decimal("400000")
    assert result.normal_rate_income == Decimal("1490")
    assert result.income_chargeable_above_basic_exemption == Decimal("0")
    assert result.slab_tax == Decimal("0")
    assert result.rebate_87a == Decimal("0")
    assert result.nil_tax_reason == "BELOW_BASIC_EXEMPTION_LIMIT"


def test_itr1_old_regime_rebate_applies():
    """Scenario 2: Old regime, below 60, under slab threshold (3.5L), 87A rebate applies."""
    itr_input = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(
            gross_salary=Decimal("450000"),
            standard_deduction_claimed=Decimal("50000"),
        ),
        house_property_income=HousePropertyIncome(
            property_type=PropertyType.SELF_OCCUPIED,
            home_loan_interest_paid=Decimal("0"),
        ),
        other_sources_income=OtherSourcesIncome(
            savings_bank_interest=Decimal("10000"),
        ),
        deductions_chapter6a=Chapter6ADeductions(
            amount_80c=Decimal("50000"),
            amount_80tta=Decimal("10000"),
        ),
    )
    res = compute_itr1(itr_input)
    # Salary = 4.5L - 50k = 4L
    # Other sources = 10k
    # GTI = 4.1L
    # Deductions u/s 80C (50k) + 80TTA (10k) = 60k
    # Taxable Income = 4.1L - 60k = 3.5L
    assert res.gross_total_income == Decimal("410000")
    assert res.taxable_income == Decimal("350000")
    # Tax: 3.5L - 2.5L = 1L * 5% = 5,000
    assert res.slab_tax == Decimal("5000")
    # 87A rebate applies fully up to ₹12,500 since taxable income <= 5L
    assert res.rebate_87a == Decimal("5000")
    assert res.net_tax_liability == Decimal("0")

def test_itr1_old_regime_high_income():
    """Scenario 3: Old regime, below 60, high income (14.03L taxable)."""
    itr_input = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(
            gross_salary=Decimal("1500000"),
            standard_deduction_claimed=Decimal("50000"),
        ),
        house_property_income=HousePropertyIncome(
            property_type=PropertyType.LET_OUT,
            annual_rent_received=Decimal("300000"),
            municipal_taxes_paid=Decimal("10000"),
            home_loan_interest_paid=Decimal("150000"),
        ),
        other_sources_income=OtherSourcesIncome(
            fixed_deposit_interest=Decimal("50000"),
        ),
        deductions_chapter6a=Chapter6ADeductions(
            amount_80c=Decimal("150000"),
        ),
    )
    res = compute_itr1(itr_input)
    # Net Salary = 15L - 50k = 14.5L
    # HP: NAV = 3L - 10k = 2.9L. 24(a) = 87k. 24(b) = 1.5L. Arrears = 0. Income = 2.9L - 87k - 1.5L = 53k
    # OS = 50k
    # GTI = 14.5L + 53k + 50k = 15.53L
    # Ded = 1.5L
    # Taxable = 14.03L
    assert res.gross_total_income == Decimal("1553000")
    assert res.taxable_income == Decimal("1403000")
    # Tax slabs:
    # 0 to 2.5L: 0
    # 2.5L to 5L: 12.5k
    # 5L to 10L: 100k
    # 10L to 14.03L: 403,000 * 30% = 120,900
    # Total Slab Tax = 12.5k + 100k + 120,900 = 233,400
    assert res.slab_tax == Decimal("233400")
    assert res.rebate_87a == Decimal("0")
    # Cess = 233400 * 4% = 9336
    # Total tax payable = 233400 + 9336 = 242736 -> Round to nearest 10 = 242740
    assert res.net_tax_liability == Decimal("242740")

def test_itr1_new_regime_high_income():
    """Scenario 4: New regime, below 60, high income (15.28L taxable)."""
    itr_input = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.NEW,
        salary_income=SalaryIncome(
            gross_salary=Decimal("1500000"),
            standard_deduction_claimed=Decimal("75000"),
        ),
        house_property_income=HousePropertyIncome(
            property_type=PropertyType.LET_OUT,
            annual_rent_received=Decimal("300000"),
            municipal_taxes_paid=Decimal("10000"),
            home_loan_interest_paid=Decimal("150000"),
        ),
        other_sources_income=OtherSourcesIncome(
            fixed_deposit_interest=Decimal("50000"),
        ),
        deductions_chapter6a=Chapter6ADeductions(
            amount_80c=Decimal("150000"),  # ignored in New Regime
        ),
    )
    res = compute_itr1(itr_input)
    # Net Salary = 15L - 75k = 14.25L
    # HP = 53k
    # OS = 50k
    # GTI = 14.25L + 53k + 50k = 15.28L
    # Ded = 0 (New regime disallows 80C)
    # Taxable = 15.28L
    assert res.gross_total_income == Decimal("1528000")
    assert res.taxable_income == Decimal("1528000")
    # New Regime Slab Tax:
    # 0 to 4L: 0%
    # 4L to 8L: 20k (4L * 5%)
    # 8L to 12L: 40k (4L * 10%)
    # 12L to 15.28L: 3.28L * 15% = 49.2k
    # Total Slab Tax = 20k + 40k + 49.2k = 109.2k
    assert res.slab_tax == Decimal("109200")
    assert res.rebate_87a == Decimal("0")
    # Cess = 109.2k * 4% = 4368
    # Total payable = 109200 + 4368 = 113568 -> Rounded = 113570
    assert res.net_tax_liability == Decimal("113570")

def test_itr1_senior_citizen_old_regime():
    """Scenario 5: Senior citizen, Old regime, basic exemption 3L, self-occupied HP loss & 80TTB."""
    itr_input = ITR1Input(
        age_bracket=AgeBracket.SIXTY_TO_80,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("0")),
        house_property_income=HousePropertyIncome(
            property_type=PropertyType.SELF_OCCUPIED,
            home_loan_interest_paid=Decimal("250000"),
        ),
        other_sources_income=OtherSourcesIncome(
            fixed_deposit_interest=Decimal("650000"),
        ),
        deductions_chapter6a=Chapter6ADeductions(
            amount_80ttb=Decimal("50000"),
        ),
    )
    res = compute_itr1(itr_input)
    # HP interest allowed: min(250k, 200k) = 200k loss
    # OS = 650k
    # GTI = 650k - 200k = 450k
    # Deductions: 80TTB = min(50k, 650k interest, 50k cap) = 50k
    # Taxable = 450k - 50k = 400k
    assert res.gross_total_income == Decimal("450000")
    assert res.taxable_income == Decimal("400000")
    # Senior citizen old regime slabs:
    # 0 to 3L: 0%
    # 3L to 4L: 100k * 5% = 5k
    assert res.slab_tax == Decimal("5000")
    assert res.rebate_87a == Decimal("5000")
    assert res.net_tax_liability == Decimal("0")

def test_itr1_new_regime_marginal_rebate():
    """Scenario 6: New regime, marginal rebate (12.05L taxable income)."""
    itr_input = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.NEW,
        salary_income=SalaryIncome(
            gross_salary=Decimal("1280000"),
            standard_deduction_claimed=Decimal("75000"),
        ),
        house_property_income=HousePropertyIncome(
            property_type=PropertyType.SELF_OCCUPIED,
            home_loan_interest_paid=Decimal("0"),
        ),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(),
    )
    res = compute_itr1(itr_input)
    # GTI = Net Salary = 12.8L - 75k = 12.05L
    # Taxable = 12.05L
    assert res.taxable_income == Decimal("1205000")
    # Slab Tax = 20k (4-8L) + 40k (8-12L) + 750 (5k u/s 12-16L * 15%) = 60,750
    assert res.slab_tax == Decimal("60750")
    # Marginal Rebate: excess = 12.05L - 12L = 5,000
    # Rebate = 60,750 - 5,000 = 55,750
    assert res.rebate_87a == Decimal("55750")
    # Tax after rebate = 5,000
    assert res.tax_after_rebate == Decimal("5000")
    # Cess = 5,000 * 4% = 200
    # Total = 5,200
    assert res.net_tax_liability == Decimal("5200")


def test_professional_tax_cap_old_regime():
    """Professional tax paid = ₹8,000 (exceeds ₹2,500 statutory cap u/s 16(iii)/Art 276(2)). Expected: Only ₹2,500 deducted."""
    itr_input = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(
            gross_salary=Decimal("200000"),
            professional_tax_paid=Decimal("8000"),
        ),
        house_property_income=HousePropertyIncome(
            property_type=PropertyType.SELF_OCCUPIED,
            home_loan_interest_paid=Decimal("0"),
        ),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(),
    )
    res = compute_itr1(itr_input)
    # Salary = 200k - 50k (std ded) - 2.5k (prof tax cap u/s 16(iii)) = 147.5k
    assert res.salary_income == Decimal("147500")

def test_entertainment_allowance_non_govt_employee():
    """Entertainment allowance = ₹5,000 but NOT a govt employee. Expected: ₹0 deduction."""
    itr_input = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(
            gross_salary=Decimal("200000"),
            entertainment_allowance=Decimal("5000"),
            is_government_employee=False,
        ),
        house_property_income=HousePropertyIncome(
            property_type=PropertyType.SELF_OCCUPIED,
            home_loan_interest_paid=Decimal("0"),
        ),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(),
    )
    res = compute_itr1(itr_input)
    # Salary = 200k - 50k (std ded) - 0 = 150k
    assert res.salary_income == Decimal("150000")

def test_entertainment_allowance_govt_employee():
    """Entertainment allowance = ₹7,000 by govt employee. Expected: capped at ₹5,000."""
    itr_input = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(
            gross_salary=Decimal("200000"),
            entertainment_allowance=Decimal("7000"),
            is_government_employee=True,
        ),
        house_property_income=HousePropertyIncome(
            property_type=PropertyType.SELF_OCCUPIED,
            home_loan_interest_paid=Decimal("0"),
        ),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(),
    )
    res = compute_itr1(itr_input)
    # Salary = 200k - 50k - 5k = 145k
    assert res.salary_income == Decimal("145000")

def test_80ccd1b_limit():
    """80CCD1B claimed = ₹70,000 (exceeds ₹50,000 limit). Expected: Only ₹50,000 allowed."""
    itr_input = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("500000")),
        house_property_income=HousePropertyIncome(
            property_type=PropertyType.SELF_OCCUPIED,
            home_loan_interest_paid=Decimal("0"),
        ),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(
            amount_80ccd1b=Decimal("70000"),
        ),
    )
    res = compute_itr1(itr_input)
    # GTI = 500k - 50k = 450k, Deduction = 50k (cap), Taxable = 400k
    assert res.taxable_income == Decimal("400000")
    assert res.deductions_total == Decimal("50000")

def test_80cce_pool_limit():
    """80C=1L + 80CCC=30k + 80CCD1=40k = 1.7L (exceeds 1.5L pool). Expected: capped at ₹1.5L."""
    itr_input = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("400000")),
        house_property_income=HousePropertyIncome(
            property_type=PropertyType.SELF_OCCUPIED,
            home_loan_interest_paid=Decimal("0"),
        ),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(
            amount_80c=Decimal("100000"),
            amount_80ccc=Decimal("30000"),
            amount_80ccd1=Decimal("40000"),
        ),
    )
    res = compute_itr1(itr_input)
    # GTI = 400k - 50k = 350k, Pool capped at 150k, Taxable = 200k
    assert res.taxable_income == Decimal("200000")
    assert res.deductions_total == Decimal("150000")

def test_json_output_keys():
    """Verify output contains required keys."""
    itr_input = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=SalaryIncome(gross_salary=Decimal("200000")),
        house_property_income=HousePropertyIncome(
            property_type=PropertyType.SELF_OCCUPIED,
            home_loan_interest_paid=Decimal("0"),
        ),
        other_sources_income=OtherSourcesIncome(),
        deductions_chapter6a=Chapter6ADeductions(),
    )
    res = compute_itr1(itr_input)
    required_keys = [
        "salary_income", "house_property_income", "other_sources_income",
        "gross_total_income", "deductions_total", "taxable_income",
        "slab_tax", "rebate_87a", "tax_after_rebate", "surcharge",
        "health_education_cess", "net_tax_liability",
    ]
    for key in required_keys:
        assert hasattr(res, key), f"Missing attribute: {key}"
