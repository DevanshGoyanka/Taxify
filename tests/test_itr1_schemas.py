import pytest
from decimal import Decimal
from pydantic import ValidationError
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

def test_salary_income_valid():
    """Test valid SalaryIncome instantiation and defaults."""
    sal = SalaryIncome(
        gross_salary=Decimal("600000"),
        hra_exempt_amount=Decimal("50000"),
        lta_exempt_amount=Decimal("15000"),
        standard_deduction_claimed=Decimal("50000"),
        professional_tax_paid=Decimal("2400"),
    )
    assert sal.gross_salary == Decimal("600000")
    assert sal.hra_exempt_amount == Decimal("50000")
    assert sal.lta_exempt_amount == Decimal("15000")
    assert sal.standard_deduction_claimed == Decimal("50000")
    assert sal.professional_tax_paid == Decimal("2400")

    # Test defaults
    sal_default = SalaryIncome(gross_salary=Decimal("500000"))
    assert sal_default.hra_exempt_amount == Decimal("0")
    assert sal_default.lta_exempt_amount == Decimal("0")
    assert sal_default.standard_deduction_claimed == Decimal("0")
    assert sal_default.professional_tax_paid == Decimal("0")

def test_salary_income_invalid():
    """Test invalid SalaryIncome fields (e.g. negative values)."""
    with pytest.raises(ValidationError):
        SalaryIncome(gross_salary=Decimal("-100"))
    
    with pytest.raises(ValidationError):
        SalaryIncome(gross_salary=Decimal("500000"), hra_exempt_amount=Decimal("-1"))

def test_house_property_income_valid():
    """Test valid HousePropertyIncome instantiation with all PropertyTypes."""
    hp_self = HousePropertyIncome(
        property_type=PropertyType.SELF_OCCUPIED,
        home_loan_interest_paid=Decimal("150000"),
    )
    assert hp_self.property_type == PropertyType.SELF_OCCUPIED
    assert hp_self.annual_rent_received == Decimal("0")
    assert hp_self.municipal_taxes_paid == Decimal("0")
    assert hp_self.home_loan_interest_paid == Decimal("150000")

    hp_let = HousePropertyIncome(
        property_type=PropertyType.LET_OUT,
        annual_rent_received=Decimal("240000"),
        municipal_taxes_paid=Decimal("12000"),
        home_loan_interest_paid=Decimal("80000"),
        arrears_unrealised_rent_received=Decimal("30000"),
    )
    assert hp_let.property_type == PropertyType.LET_OUT
    assert hp_let.annual_rent_received == Decimal("240000")
    assert hp_let.municipal_taxes_paid == Decimal("12000")
    assert hp_let.home_loan_interest_paid == Decimal("80000")
    assert hp_let.arrears_unrealised_rent_received == Decimal("30000")

def test_house_property_income_invalid():
    """Test negative values in HousePropertyIncome."""
    with pytest.raises(ValidationError):
        HousePropertyIncome(
            property_type=PropertyType.SELF_OCCUPIED,
            home_loan_interest_paid=Decimal("-1000"),
        )

def test_other_sources_income():
    """Test valid and invalid OtherSourcesIncome."""
    osi = OtherSourcesIncome(
        savings_bank_interest=Decimal("12000"),
        fixed_deposit_interest=Decimal("45000"),
        family_pension_received=Decimal("36000"),
    )
    assert osi.savings_bank_interest == Decimal("12000")
    assert osi.fixed_deposit_interest == Decimal("45000")
    assert osi.family_pension_received == Decimal("36000")

    with pytest.raises(ValidationError):
        OtherSourcesIncome(savings_bank_interest=Decimal("-5"))

def test_chapter6a_deductions():
    """Test valid and invalid Chapter6ADeductions."""
    ded = Chapter6ADeductions(
        amount_80c=Decimal("150000"),
        amount_80ccd1b=Decimal("50000"),
        amount_80d_self_family=Decimal("25000"),
        amount_80d_parents=Decimal("30000"),
        amount_80tta=Decimal("10000"),
        amount_80ttb=Decimal("0"),
        amount_80e=Decimal("40000"),
    )
    assert ded.amount_80c == Decimal("150000")
    assert ded.amount_80ccd1b == Decimal("50000")
    assert ded.amount_80d_self_family == Decimal("25000")
    assert ded.amount_80d_parents == Decimal("30000")
    assert ded.amount_80tta == Decimal("10000")
    assert ded.amount_80ttb == Decimal("0")
    assert ded.amount_80e == Decimal("40000")

    with pytest.raises(ValidationError):
        Chapter6ADeductions(amount_80c=Decimal("-10"))

def test_capital_gains_income():
    """Test CapitalGainsIncome validation."""
    cg = CapitalGainsIncome(
        ltcg_112a=Decimal("120000"),
        cost_of_acquisition=Decimal("50000"),
    )
    assert cg.ltcg_112a == Decimal("120000")
    assert cg.cost_of_acquisition == Decimal("50000")

    with pytest.raises(ValidationError):
        CapitalGainsIncome(ltcg_112a=Decimal("-5000"))

def test_itr1_input_full():
    """Test full ITR1Input model serialization and verification."""
    sal = SalaryIncome(gross_salary=Decimal("1200000"))
    hp = HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED, home_loan_interest_paid=Decimal("120000"))
    other = OtherSourcesIncome(savings_bank_interest=Decimal("15000"))
    ded = Chapter6ADeductions(amount_80c=Decimal("150000"), amount_80tta=Decimal("10000"))
    cg = CapitalGainsIncome(ltcg_112a=Decimal("80000"))

    itr1_input = ITR1Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        salary_income=sal,
        house_property_income=hp,
        other_sources_income=other,
        deductions_chapter6a=ded,
        capital_gains=cg,
    )

    assert itr1_input.age_bracket == AgeBracket.BELOW_60
    assert itr1_input.tax_regime == TaxRegime.OLD
    assert itr1_input.salary_income.gross_salary == Decimal("1200000")
    assert itr1_input.house_property_income.property_type == PropertyType.SELF_OCCUPIED
    assert itr1_input.capital_gains.ltcg_112a == Decimal("80000")
