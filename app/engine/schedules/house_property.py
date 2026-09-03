"""
Schedule HP: House Property Income (u/s 22-27).

Section 23: Gross Annual Value (GAV)
  For let-out / deemed let-out property:
    GAV is the AnnualLetableValue reported in the official Schedule HP.

  For self-occupied property: GAV = Nil.

The caller provides this value as ``annual_rent_received`` for backward
compatibility with the existing typed compute contract. Canonical drafts map
``HouseProperty.annualLettingValue`` to that field.

Section 24(a): 30% standard deduction on NAV (Net Annual Value = GAV - municipal taxes)
Section 24(b): Interest on borrowed capital
  - Self-occupied: capped at 2L (old regime) / disallowed (new regime)
  - Let-out: fully deductible in both regimes
Section 25A: Arrears of rent / unrealized rent

New regime (s.115BAC): HP loss from let-out property cannot be set off against
other heads and cannot be carried forward. Intra-head netting (two let-out
properties, one in profit and one in loss) IS permitted. The loss is passed
through as signed income_chargeable and blocked at the CYLA level.
"""

from datetime import date
from decimal import Decimal
from typing import Optional
from dataclasses import dataclass
from app.engine.constants import (
    HOUSE_PROPERTY_STANDARD_DEDUCTION,
    HOUSE_PROPERTY_INTEREST_LIMIT_SELF_OCCUPIED,
    HOUSE_PROPERTY_INTEREST_LIMIT_SELF_OCCUPIED_PRE_1999,
)
from app.schemas.itr1 import HousePropertyIncome, PropertyType, TaxRegime

# Sec 24(b) proviso cutoff: a self-occupied loan sanctioned before this date
# is capped at Rs 30,000 instead of the usual Rs 2,00,000.
_SEC_24B_PRE_1999_CUTOFF = date(1999, 4, 1)


@dataclass
class HPResult:
    property_type: str = ""
    gross_annual_value: Decimal = Decimal("0")
    rent_not_realized: Decimal = Decimal("0")
    municipal_taxes: Decimal = Decimal("0")
    net_annual_value: Decimal = Decimal("0")
    annual_value_owned: Decimal = Decimal("0")
    standard_deduction_30pct: Decimal = Decimal("0")
    interest_on_loan: Decimal = Decimal("0")
    arrears_unrealised_rent: Decimal = Decimal("0")
    income_chargeable: Decimal = Decimal("0")
    loss_disallowed: Decimal = Decimal("0")
    loss_carried_forward: Decimal = Decimal("0")


@dataclass
class HPLossSetoffResult:
    """House-property income allowed in GTI and current-year disallowed loss."""

    allowed_income: Decimal = Decimal("0")
    disallowed_loss: Decimal = Decimal("0")


def apply_inter_head_loss_limit(hp_result: HPResult, regime: TaxRegime) -> HPLossSetoffResult:
    """Apply current-year inter-head house-property loss restrictions."""
    income = hp_result.income_chargeable
    if income >= 0:
        return HPLossSetoffResult(allowed_income=income)
    if regime == TaxRegime.NEW:
        return HPLossSetoffResult(disallowed_loss=abs(income))
    limit = Decimal("200000")
    allowed_income = max(income, -limit)
    return HPLossSetoffResult(
        allowed_income=allowed_income,
        disallowed_loss=abs(income - allowed_income),
    )


def compute(
    input_data: Optional[HousePropertyIncome],
    regime: TaxRegime,
    ownership_share_percentage: Decimal = Decimal("100"),
    loan_sanction_dates: Optional[list[Optional[date]]] = None,
) -> HPResult:
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
            interest_limit = HOUSE_PROPERTY_INTEREST_LIMIT_SELF_OCCUPIED
            if loan_sanction_dates and any(
                d is not None and d < _SEC_24B_PRE_1999_CUTOFF
                for d in loan_sanction_dates
            ):
                interest_limit = HOUSE_PROPERTY_INTEREST_LIMIT_SELF_OCCUPIED_PRE_1999
            allowed_interest = min(interest, interest_limit)
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

    # Let Out / Deemed Let Out: canonical input is the official Schedule HP
    # AnnualLetableValue. Municipal/fair-rent helper fields are not part of
    # the ITR-1/ITR-4 JSON contract and must not silently override it.
    gav = input_data.annual_rent_received

    balance_alv = max(
        Decimal("0"),
        gav - input_data.rent_not_realized - input_data.municipal_taxes_paid,
    )
    annual_value_owned = (
        balance_alv * ownership_share_percentage / Decimal("100")
    )
    std_ded = (
        annual_value_owned * HOUSE_PROPERTY_STANDARD_DEDUCTION
        if annual_value_owned > 0 else Decimal("0")
    )
    interest = input_data.home_loan_interest_paid
    arrears = input_data.arrears_unrealised_rent_received
    # Section 25A: Only 70% of arrears/unrealised rent is taxable
    # (30% deduction is deemed to cover collection costs)
    hp_income = (
        annual_value_owned - std_ded - interest + (arrears * Decimal("0.7"))
    )

    # For new regime: pass through signed income (losses blocked at CYLA,
    # not at schedule level — allows intra-head netting between two let-out properties).
    # loss_disallowed captures the negative portion for CYLA to block cross-head.
    if hp_income < 0 and regime == TaxRegime.NEW:
        return HPResult(
            property_type=pt,
            gross_annual_value=gav,
            rent_not_realized=input_data.rent_not_realized,
            municipal_taxes=input_data.municipal_taxes_paid,
            net_annual_value=balance_alv,
            annual_value_owned=annual_value_owned,
            standard_deduction_30pct=std_ded,
            interest_on_loan=interest,
            arrears_unrealised_rent=arrears,
            income_chargeable=hp_income,      # pass negative through for intra-head netting
            loss_disallowed=hp_income,         # CYLA will use this to block cross-head setoff
        )

    return HPResult(
        property_type=pt,
        gross_annual_value=gav,
        rent_not_realized=input_data.rent_not_realized,
        municipal_taxes=input_data.municipal_taxes_paid,
        net_annual_value=balance_alv,
        annual_value_owned=annual_value_owned,
        standard_deduction_30pct=std_ded,
        interest_on_loan=interest,
        arrears_unrealised_rent=arrears,
        income_chargeable=hp_income,
    )
