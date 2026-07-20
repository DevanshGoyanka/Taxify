"""
Schedule HP: House Property Income (u/s 22-27).

Section 23: Gross Annual Value (GAV)
  For let-out / deemed let-out property:
    GAV = max(Municipal Value, Fair Rent, Actual Rent received/receivable)

  For self-occupied property: GAV = Nil.

The caller provides the pre-computed GAV as ``annual_rent_received``.
When ``municipal_value`` and ``fair_rent`` are also provided, the engine
re-computes GAV = max(municipal_value, fair_rent, annual_rent_received).

Section 24(a): 30% standard deduction on NAV (Net Annual Value = GAV - municipal taxes)
Section 24(b): Interest on borrowed capital
  - Self-occupied: capped at 2L (old regime) / disallowed (new regime)
  - Let-out: fully deductible
Section 25A: Arrears of rent / unrealized rent
"""

from decimal import Decimal
from typing import Optional
from dataclasses import dataclass
from app.engine.constants import (
    HOUSE_PROPERTY_STANDARD_DEDUCTION,
    HOUSE_PROPERTY_INTEREST_LIMIT_SELF_OCCUPIED,
)
from app.schemas.itr1 import HousePropertyIncome, PropertyType, TaxRegime


@dataclass
class HPResult:
    property_type: str = ""
    gross_annual_value: Decimal = Decimal("0")
    municipal_taxes: Decimal = Decimal("0")
    net_annual_value: Decimal = Decimal("0")
    standard_deduction_30pct: Decimal = Decimal("0")
    interest_on_loan: Decimal = Decimal("0")
    arrears_unrealised_rent: Decimal = Decimal("0")
    income_chargeable: Decimal = Decimal("0")
    loss_disallowed: Decimal = Decimal("0")
    loss_carried_forward: Decimal = Decimal("0")


def compute(input_data: Optional[HousePropertyIncome], regime: TaxRegime) -> HPResult:
    if not input_data:
        return HPResult()

    pt = input_data.property_type.value

    if input_data.property_type == PropertyType.SELF_OCCUPIED:
        interest = input_data.home_loan_interest_paid
        if regime == TaxRegime.NEW:
            hp_income = Decimal("0")
            loss_disallowed = -interest
            loss_cf = Decimal("0")
        else:
            allowed_interest = min(interest, HOUSE_PROPERTY_INTEREST_LIMIT_SELF_OCCUPIED)
            hp_income = -allowed_interest
            loss_disallowed = Decimal("0")
            loss_cf = -interest - hp_income if interest > allowed_interest else Decimal("0")

        return HPResult(
            property_type=pt,
            interest_on_loan=interest,
            income_chargeable=hp_income,
            loss_disallowed=loss_disallowed,
            loss_carried_forward=loss_cf,
        )

    # Let Out / Deemed Let Out: GAV = max(Municipal Value, Fair Rent, Actual Rent)
    actual_rent = input_data.annual_rent_received
    muni_val = getattr(input_data, 'municipal_value', None)
    fair_rent = getattr(input_data, 'fair_rent', None)
    if muni_val is not None and fair_rent is not None:
        gav = max(muni_val, fair_rent, actual_rent)
    else:
        gav = actual_rent

    nav = max(Decimal("0"), gav - input_data.municipal_taxes_paid)
    std_ded = nav * HOUSE_PROPERTY_STANDARD_DEDUCTION if nav > 0 else Decimal("0")
    interest = input_data.home_loan_interest_paid
    arrears = input_data.arrears_unrealised_rent_received
    hp_income = nav - std_ded - interest + arrears

    if hp_income < 0 and regime == TaxRegime.NEW:
        return HPResult(
            property_type=pt,
            gross_annual_value=gav,
            municipal_taxes=input_data.municipal_taxes_paid,
            net_annual_value=nav,
            standard_deduction_30pct=std_ded,
            interest_on_loan=interest,
            arrears_unrealised_rent=arrears,
            income_chargeable=Decimal("0"),
            loss_disallowed=hp_income,
        )

    return HPResult(
        property_type=pt,
        gross_annual_value=gav,
        municipal_taxes=input_data.municipal_taxes_paid,
        net_annual_value=nav,
        standard_deduction_30pct=std_ded,
        interest_on_loan=interest,
        arrears_unrealised_rent=arrears,
        income_chargeable=hp_income,
    )
