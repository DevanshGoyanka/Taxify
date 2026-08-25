"""
Schedule OS: Income from Other Sources (u/s 56-59).

Categories:
  - Savings bank interest
  - Fixed deposit interest
  - Family pension (gross, deduction u/s 57(iia) handled in deductions)
  - Dividend income (taxable in hands of recipient)

OpenTax note: Family pension is reported at gross in OS. The 1/3rd
deduction u/s 57(iia) is applied in the deductions phase.
"""

from decimal import Decimal
from typing import Optional
from dataclasses import dataclass
from app.schemas.itr1 import OtherSourcesIncome, TaxRegime


@dataclass
class OSResult:
    savings_bank_interest: Decimal = Decimal("0")
    fixed_deposit_interest: Decimal = Decimal("0")
    family_pension_gross: Decimal = Decimal("0")
    dividend_income: Decimal = Decimal("0")
    interest_on_it_refund: Decimal = Decimal("0")
    income_56_2_x: Decimal = Decimal("0")
    income_56_2_vib: Decimal = Decimal("0")
    other_income: Decimal = Decimal("0")
    deduction_57iia: Decimal = Decimal("0")
    income_chargeable: Decimal = Decimal("0")


def compute(input_data: Optional[OtherSourcesIncome], regime: TaxRegime) -> OSResult:
    if not input_data:
        return OSResult()

    sb = input_data.savings_bank_interest
    fd = input_data.fixed_deposit_interest
    fp = input_data.family_pension_received
    div = input_data.dividend_income
    tax_refund_interest = input_data.interest_on_it_refund
    sec56_2x = input_data.income_56_2_x
    sec56_2vib = input_data.income_56_2_vib
    other_inc = input_data.other_income

    # 57(iia): 1/3rd of family pension or statutory cap
    # Old regime: ₹15,000 cap | New regime: ₹25,000 cap (FA 2024 amendment)
    ded_57iia = Decimal("0")
    if fp > 0:
        cap = Decimal("25000") if regime == TaxRegime.NEW else Decimal("15000")
        ded_57iia = min(fp / Decimal("3"), cap)

    chargeable = sb + fd + fp + div + tax_refund_interest + sec56_2x + sec56_2vib + other_inc - ded_57iia

    return OSResult(
        savings_bank_interest=sb,
        fixed_deposit_interest=fd,
        family_pension_gross=fp,
        dividend_income=div,
        interest_on_it_refund=tax_refund_interest,
        income_56_2_x=sec56_2x,
        income_56_2_vib=sec56_2vib,
        other_income=other_inc,
        deduction_57iia=ded_57iia,
        income_chargeable=max(Decimal("0"), chargeable),
    )
