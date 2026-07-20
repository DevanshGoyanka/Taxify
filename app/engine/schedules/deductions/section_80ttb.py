"""
Section 80TTB — Interest on Deposits for Senior Citizens.

Deduction for interest on deposits (savings bank, fixed deposits, recurring
deposits, post office deposits) for senior citizens (age >= 60).

  - Maximum: ₹50,000.
  - Covers ALL deposit interest (unlike 80TTA which is savings-only).
  - Mutually exclusive with Section 80TTA (for non-seniors).

Not available under the new regime (Section 115BAC).
"""

from decimal import Decimal
from typing import Optional
from app.schemas.itr1 import Chapter6ADeductions, OtherSourcesIncome, AgeBracket, TaxRegime
from app.engine.constants import SECTION_80TTB_LIMIT


def compute(
    ded: Optional[Chapter6ADeductions],
    os_input: Optional[OtherSourcesIncome],
    age_bracket: AgeBracket,
    regime: TaxRegime,
) -> Decimal:
    if not ded or regime == TaxRegime.NEW:
        return Decimal("0")

    is_senior = age_bracket in (AgeBracket.SIXTY_TO_80, AgeBracket.ABOVE_80)
    if not is_senior:
        return Decimal("0")  # Non-senior citizens must use 80TTA

    if not os_input:
        return Decimal("0")

    total_interest = os_input.savings_bank_interest + os_input.fixed_deposit_interest
    if total_interest <= 0:
        return Decimal("0")

    return min(ded.amount_80ttb, total_interest, SECTION_80TTB_LIMIT)
