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
    ITR4FilingProfile,
    ITR4FilingAddress,
    ITR4BankAccount,
)
from app.schemas.itr1 import AgeBracket, TaxRegime, SalaryIncome, HousePropertyIncome, PropertyType, Chapter6ADeductions, CapitalGainsIncome
from app.engine.calculators.itr4 import compute as compute_itr4
from app.engine.itd.itr4 import build_itr4_json
from datetime import date


def _minimal_filing_profile() -> ITR4FilingProfile:
    """Build a minimal ITR-4 filing profile for builder unit tests."""
    return ITR4FilingProfile(
        pan="ABCDE1234F",
        first_name="Test",
        surname="Taxpayer",
        date_of_birth=date(1990, 1, 1),
        primary_address=ITR4FilingAddress(
            residence_no="1",
            locality_or_area="Locality",
            city_or_town_or_district="City",
            state_code="07",
            country_code="91",
            pin_code="110001",
            mobile_country_code=91,
            mobile_no="9999999999",
            email="test@example.com",
        ),
        father_name="Father",
        verification_place="Delhi",
    )


def _minimal_bank_account() -> ITR4BankAccount:
    """Build a minimal bank account for builder unit tests."""
    return ITR4BankAccount(
        account_number="12345678901",
        ifsc_code="SBIN0000001",
        bank_name="Test Bank",
        account_type="savings",
        is_primary=True,
    )


def test_itr4_builder_projects_canonical_restricted_112a_schedule():
    """ITR-4 official JSON must consume canonical restricted transactions."""
    capital_gains = CapitalGainsIncome(transactions=[{
        "assetType": "LISTED_EQUITY",
        "purchaseDate": "2023-01-01",
        "saleDate": "2025-01-02",
        "purchaseCost": "100000",
        "saleCost": "120000",
        "transferExpenses": "1000",
        "sttPaidOnAcquisition": True,
        "sttPaidOnTransfer": True,
        "recognizedExchange": True,
    }])
    itr_input = ITR4Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.NEW,
        presumptive_scheme=PresumptiveScheme.S44AD,
        business_income_44ad=PresumptiveBusinessIncome44AD(
            total_turnover=Decimal("0"), digital_turnover=Decimal("0"), cash_turnover=Decimal("0")),
        capital_gains=capital_gains,
        filing_profile=_minimal_filing_profile(),
        bank_accounts=[_minimal_bank_account()],
    )
    result = compute_itr4(itr_input)
    schedule = build_itr4_json(result, itr_input)["ITR"]["ITR4"]["LTCG112A"]
    assert schedule == {
        "TotSaleCnsdrn": 120000,
        "TotCstAcqisn": 101000,
        "LongCap112A": 19000,
    }


def test_itr4_no_income():
    """Scenario 1: No income, scheme S44AD with zero turnover."""
    itr_input = ITR4Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        presumptive_scheme=PresumptiveScheme.S44AD,
        business_income_44ad=PresumptiveBusinessIncome44AD(
            total_turnover=Decimal("0"), digital_turnover=Decimal("0"), cash_turnover=Decimal("0")),
        salary_income=SalaryIncome(gross_salary=Decimal("0")),
    )
    res = compute_itr4(itr_input)
    assert res.gross_total_income == Decimal("0")
    assert res.taxable_income == Decimal("0")
    assert res.net_tax_liability == Decimal("0")

def test_itr4_44ad_business_old_regime():
    """Scenario 2: 44AD presumptive business, old regime, standard deduction & 80C, 87A rebate applies."""
    itr_input = ITR4Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        presumptive_scheme=PresumptiveScheme.S44AD,
        business_income_44ad=PresumptiveBusinessIncome44AD(
            total_turnover=Decimal("1500000"),
            digital_turnover=Decimal("1000000"),
            cash_turnover=Decimal("500000"),
        ),
        salary_income=SalaryIncome(
            gross_salary=Decimal("300000"),
            standard_deduction_claimed=Decimal("50000"),
        ),
        deductions_chapter6a=Chapter6ADeductions(
            amount_80c=Decimal("50000"),
        ),
    )
    res = compute_itr4(itr_input)
    # Presumptive PGBP: (10L * 6%) + (5L * 8%) = 60k + 40k = 100k
    # Net Salary: 300k - 50k = 250k
    # GTI: 250k + 100k = 350k
    # Deductions: 50k
    # Taxable Income: 300k
    assert res.presumptive_income == Decimal("100000")
    assert res.gross_total_income == Decimal("350000")
    assert res.taxable_income == Decimal("300000")
    # Slab Tax (Old): (300k - 250k) * 5% = 2,500
    assert res.slab_tax == Decimal("2500")
    # Rebate u/s 87A: 100% since taxable_income <= 5L
    assert res.rebate_87a == Decimal("2500")
    assert res.net_tax_liability == Decimal("0")

def test_itr4_44ada_professional_new_regime():
    """Scenario 3: 44ADA presumptive professional, new regime, 87A rebate crossover (exact 12L)."""
    itr_input = ITR4Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.NEW,
        presumptive_scheme=PresumptiveScheme.S44ADA,
        professional_income_44ada=PresumptiveProfessionalIncome44ADA(
            gross_receipts=Decimal("2400000"),
            digital_receipts=Decimal("2400000"),
            cash_receipts=Decimal("0"),
        ),
    )
    res = compute_itr4(itr_input)
    # Presumptive PGBP: 24L * 50% = 12L
    # GTI = 12L. Taxable = 12L
    assert res.presumptive_income == Decimal("1200000")
    assert res.taxable_income == Decimal("1200000")
    # Slab Tax (New regime slabs):
    # 0 to 4L: 0%
    # 4L to 8L: 20k
    # 8L to 12L: 40k
    # Total Slab Tax = 60,000
    assert res.slab_tax == Decimal("60000")
    # Rebate 87A (New regime): 100% u/s 87A since taxable_income <= 12L
    assert res.rebate_87a == Decimal("60000")
    assert res.net_tax_liability == Decimal("0")

def test_itr4_44ae_goods_carriage_high_income():
    """Scenario 4: 44AE goods carriage business, old regime, high income (16.16L taxable)."""
    itr_input = ITR4Input(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        presumptive_scheme=PresumptiveScheme.S44AE,
        goods_carriage_44ae=PresumptiveGoodsCarriage44AE(
            vehicles=[
                # Vehicle 1: Non-heavy (Light), owned for 12 months.
                GoodsCarriageVehicle(
                    is_heavy_goods_vehicle=False,
                    months_owned=12,
                ),
                # Vehicle 2: Heavy (16 tons), owned for 6 months.
                GoodsCarriageVehicle(
                    is_heavy_goods_vehicle=True,
                    gross_vehicle_weight_tons=Decimal("16"),
                    months_owned=6,
                ),
                # Vehicle 3: Non-heavy, owned for 10 months, higher income declared.
                GoodsCarriageVehicle(
                    is_heavy_goods_vehicle=False,
                    months_owned=10,
                    income_declared=Decimal("80000"),  # statutory is 7.5k * 10 = 75k
                ),
            ]
        ),
        salary_income=SalaryIncome(
            gross_salary=Decimal("1550000"),
            standard_deduction_claimed=Decimal("50000"),
        ),
        deductions_chapter6a=Chapter6ADeductions(
            amount_80c=Decimal("150000"),
        ),
    )
    res = compute_itr4(itr_input)
    # Vehicle 1: 7,500 * 12 = 90k
    # Vehicle 2: 1,000 * 16 * 6 = 96k
    # Vehicle 3: 80k (declared > 75k statutory)
    # Total presumptive = 90k + 96k + 80k = 266k
    # Salary net = 15.5L - 50k = 15L
    # GTI = 15L + 266k = 17.66L
    # Deductions = 1.5L
    # Taxable = 16.16L
    assert res.presumptive_income == Decimal("266000")
    assert res.gross_total_income == Decimal("1766000")
    assert res.taxable_income == Decimal("1616000")
    # Slab Tax (Old slabs):
    # 0 to 2.5L: 0
    # 2.5L to 5L: 12.5k
    # 5L to 10L: 100k
    # 10L to 16.16L: 616,000 * 30% = 184,800
    # Total Slab Tax = 297,300
    assert res.slab_tax == Decimal("297300")
    # Cess = 297,300 * 4% = 11,892
    # Aggregate liability = 297,300 + 11,892 = 309,192. Section 288B rounding
    # is applied only to balance_payable / refund_due, not to the intermediate
    # net_tax_liability aggregate.
    assert res.gross_tax_liability == Decimal("309192")
    assert res.net_tax_liability == Decimal("309192")
    assert res.balance_payable == Decimal("309190")

def test_itr4_validation_failures():
    """Scenario 5: 44AD limits and vehicle count validation checks."""
    # Case 5a: Turnover exceeds ₹3 crore cap
    with pytest.raises(ValidationError, match="exceeds ₹3 crore limit"):
        compute_itr4(
            ITR4Input(
                age_bracket=AgeBracket.BELOW_60,
                tax_regime=TaxRegime.OLD,
                presumptive_scheme=PresumptiveScheme.S44AD,
                business_income_44ad=PresumptiveBusinessIncome44AD(
                    total_turnover=Decimal("35000000"),
                    digital_turnover=Decimal("35000000"),
                    cash_turnover=Decimal("0"),
                ),
            )
        )

    # Case 5b: Turnover in ₹2Cr - ₹3Cr range but cash receipts > 5%
    result = compute_itr4(
        ITR4Input(
            age_bracket=AgeBracket.BELOW_60,
            tax_regime=TaxRegime.OLD,
            presumptive_scheme=PresumptiveScheme.S44AD,
            business_income_44ad=PresumptiveBusinessIncome44AD(
                total_turnover=Decimal("25000000"),
                digital_turnover=Decimal("23000000"),
                cash_turnover=Decimal("2000000"),  # 8% cash > 5% limit
            ),
        )
    )
    assert any("cash receipts" in e.lower() and "5%" in e for e in result.errors)

    # Case 5c: More than 10 vehicles owned u/s 44AE
    result = compute_itr4(
        ITR4Input(
            age_bracket=AgeBracket.BELOW_60,
            tax_regime=TaxRegime.OLD,
            presumptive_scheme=PresumptiveScheme.S44AE,
            goods_carriage_44ae=PresumptiveGoodsCarriage44AE(
                vehicles=[GoodsCarriageVehicle(is_heavy_goods_vehicle=False, months_owned=12)] * 11
            ),
        )
    )
    assert any("10" in e and "vehicles" in e.lower() for e in result.errors)

def test_itr4_44ada_validation_failures():
    """Scenario 6: 44ADA gross receipts limits validation checks."""
    # Case 6a: Gross receipts exceed ₹75 lakh cap
    with pytest.raises(ValidationError, match="exceed .*75 lakh limit"):
        compute_itr4(
            ITR4Input(
                age_bracket=AgeBracket.BELOW_60,
                tax_regime=TaxRegime.OLD,
                presumptive_scheme=PresumptiveScheme.S44ADA,
                professional_income_44ada=PresumptiveProfessionalIncome44ADA(
                    gross_receipts=Decimal("8000000"),
                    digital_receipts=Decimal("8000000"),
                    cash_receipts=Decimal("0"),
                ),
            )
        )

    # Case 6b: Gross receipts in ₹50L - ₹75L range but cash receipts > 5%
    result = compute_itr4(
        ITR4Input(
            age_bracket=AgeBracket.BELOW_60,
            tax_regime=TaxRegime.OLD,
            presumptive_scheme=PresumptiveScheme.S44ADA,
            professional_income_44ada=PresumptiveProfessionalIncome44ADA(
                gross_receipts=Decimal("6000000"),
                digital_receipts=Decimal("5500000"),
                cash_receipts=Decimal("500000"),  # 8.3% cash > 5% limit
            ),
        )
    )
    assert any("cash receipts" in e.lower() and "5%" in e for e in result.errors)
