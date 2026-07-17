import pytest
from decimal import Decimal
from pydantic import ValidationError
from app.schemas.itr4 import (
    ITR4Input,
    PresumptiveBusinessIncome44AD,
    PresumptiveProfessionalIncome44ADA,
    PresumptiveGoodsCarriage44AE,
    GoodsCarriageVehicle,
    PresumptiveScheme,
)
from app.schemas.itr1 import AgeBracket, TaxRegime, SalaryIncome, HousePropertyIncome, PropertyType

def test_presumptive_business_income_44ad():
    """Test valid and invalid PresumptiveBusinessIncome44AD."""
    bi = PresumptiveBusinessIncome44AD(
        total_turnover=Decimal("20000000"),
        digital_turnover=Decimal("19000000"),
        cash_turnover=Decimal("1000000"),
        income_declared=Decimal("1600000"),
    )
    assert bi.total_turnover == Decimal("20000000")
    assert bi.digital_turnover == Decimal("19000000")
    assert bi.cash_turnover == Decimal("1000000")
    assert bi.income_declared == Decimal("1600000")

    with pytest.raises(ValidationError):
        PresumptiveBusinessIncome44AD(total_turnover=Decimal("-100"))

def test_presumptive_professional_income_44ada():
    """Test valid and invalid PresumptiveProfessionalIncome44ADA."""
    pi = PresumptiveProfessionalIncome44ADA(
        gross_receipts=Decimal("4500000"),
        digital_receipts=Decimal("4400000"),
        cash_receipts=Decimal("100000"),
    )
    assert pi.gross_receipts == Decimal("4500000")
    assert pi.digital_receipts == Decimal("4400000")
    assert pi.cash_receipts == Decimal("100000")
    assert pi.income_declared is None

    with pytest.raises(ValidationError):
        PresumptiveProfessionalIncome44ADA(gross_receipts=Decimal("-50000"))

def test_goods_carriage_vehicle():
    """Test GoodsCarriageVehicle constraints."""
    vehicle = GoodsCarriageVehicle(
        is_heavy_goods_vehicle=True,
        gross_vehicle_weight_tons=Decimal("15.5"),
        months_owned=12,
        income_declared=Decimal("186000"),
    )
    assert vehicle.is_heavy_goods_vehicle is True
    assert vehicle.gross_vehicle_weight_tons == Decimal("15.5")
    assert vehicle.months_owned == 12
    assert vehicle.income_declared == Decimal("186000")

    with pytest.raises(ValidationError):
        # Months owned must be <= 12
        GoodsCarriageVehicle(
            is_heavy_goods_vehicle=False,
            months_owned=13,
        )

    with pytest.raises(ValidationError):
        # Months owned must be >= 1
        GoodsCarriageVehicle(
            is_heavy_goods_vehicle=False,
            months_owned=0,
        )

def test_presumptive_goods_carriage_44ae():
    """Test PresumptiveGoodsCarriage44AE list minimum length constraint."""
    with pytest.raises(ValidationError):
        # Vehicles cannot be empty
        PresumptiveGoodsCarriage44AE(vehicles=[])

    vehicle = GoodsCarriageVehicle(is_heavy_goods_vehicle=False, months_owned=6)
    gc = PresumptiveGoodsCarriage44AE(vehicles=[vehicle])
    assert len(gc.vehicles) == 1

def test_itr4_input_full():
    """Test full ITR4Input schema instantiation."""
    bi = PresumptiveBusinessIncome44AD(
        total_turnover=Decimal("15000000"),
        digital_turnover=Decimal("15000000"),
        cash_turnover=Decimal("0"),
    )
    sal = SalaryIncome(gross_salary=Decimal("400000"))
    hp = HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED, home_loan_interest_paid=Decimal("50000"))

    itr4_input = ITR4Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.NEW,
        presumptive_scheme=PresumptiveScheme.S44AD,
        business_income_44ad=bi,
        salary_income=sal,
        house_property_income=hp,
    )

    assert itr4_input.presumptive_scheme == PresumptiveScheme.S44AD
    assert itr4_input.business_income_44ad.total_turnover == Decimal("15000000")
    assert itr4_input.salary_income.gross_salary == Decimal("400000")
    assert itr4_input.house_property_income.property_type == PropertyType.SELF_OCCUPIED
    assert itr4_input.professional_income_44ada is None
    assert itr4_input.goods_carriage_44ae is None
