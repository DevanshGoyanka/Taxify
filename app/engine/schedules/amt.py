"""
Schedule AMT: Alternate Minimum Tax (u/s 115JC).

Applicable to non-corporate assesses (individuals, HUFs, AOPs, BOIs,
firms, LLPs) who have claimed deductions under:
  - Section 80-IA (infrastructure)
  - Section 80-IB (industrial undertaking)
  - Section 80-IC / 80-IE (special category states)
  - Section 10AA (SEZ units)
  - Section 35AD (specified business capital expenditure)

AMT Rate: 18.5% of Adjusted Total Income (ATI).
ATI = Total Income + claimed deductions u/s 80-IA/IB/10AA/35AD + deduction
u/s 10AA.

Section 115JD: AMT credit = AMT paid - regular tax. Carried forward 15 years
and set off against regular tax in years where regular tax > AMT.

The AMT is the higher of:
  - Tax computed normally (slab + special rates + surcharge + cess)
  - Tax computed under 115JC (18.5% of ATI + surcharge + cess)

If AMT is triggered, the final tax = AMT.
AMT credit is computed but not applied automatically (requires Schedule AMTC).
"""

from decimal import Decimal
from dataclasses import dataclass, field
from app.engine.common.cess import compute as compute_cess
from app.engine.common.surcharge import compute as compute_surcharge
from app.engine.constants import HEALTH_EDUCATION_CESS_RATE


AMT_RATE: Decimal = Decimal("0.185")  # 18.5% u/s 115JC(1)


@dataclass
class AMTResult:
    adjusted_total_income: Decimal = Decimal("0")
    amt_tax: Decimal = Decimal("0")
    regular_tax: Decimal = Decimal("0")
    amt_applicable: bool = False
    amt_credit: Decimal = Decimal("0")
    final_tax: Decimal = Decimal("0")


def compute(
    total_income: Decimal,
    total_tax_before_cess: Decimal,
    deductions_triggers: dict,
    regime: str,
    age_bracket: str,
) -> AMTResult:
    """
    Compute AMT.

    ``deductions_triggers`` is a dict with keys matching
    the deduction sections that trigger AMT:
      {"80-IA": Decimal, "80-IB": Decimal, "10AA": Decimal, "35AD": Decimal}
    """
    from app.schemas.itr1 import TaxRegime

    trigger_amount = sum(deductions_triggers.values(), Decimal("0"))

    if trigger_amount <= 0 or regime == TaxRegime.NEW:
        return AMTResult(final_tax=total_tax_before_cess)

    ati = total_income + trigger_amount

    # s.115JC(4): AMT does not apply if Adjusted Total Income ≤ ₹20,00,000
    if ati <= Decimal("2000000"):
        return AMTResult(
            adjusted_total_income=ati,
            amt_tax=Decimal("0"),
            regular_tax=total_tax_before_cess,
            final_tax=total_tax_before_cess,
        )

    amt_tax_before_cess = ati * AMT_RATE
    amt_surcharge = compute_surcharge(ati, amt_tax_before_cess, regime, age_bracket)
    amt_cess = compute_cess(amt_tax_before_cess + amt_surcharge)
    amt_total = amt_tax_before_cess + amt_surcharge + amt_cess

    if amt_total > total_tax_before_cess:
        return AMTResult(
            adjusted_total_income=ati,
            amt_tax=amt_total,
            regular_tax=total_tax_before_cess,
            amt_applicable=True,
            amt_credit=amt_total - total_tax_before_cess,
            final_tax=amt_total,
        )

    return AMTResult(
        adjusted_total_income=ati,
        amt_tax=amt_total,
        regular_tax=total_tax_before_cess,
        final_tax=total_tax_before_cess,
    )
