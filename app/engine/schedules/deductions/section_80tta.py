"""
Section 80TTA — Interest on Savings Account (Non-Senior Citizens).

Deduction for interest earned on savings bank accounts.
  - Applicable only for individuals/HUFs below 60 years of age.
  - Maximum: ₹10,000.
  - Only savings bank interest qualifies (not FD/RD interest).

Mutually exclusive with Section 80TTB (for senior citizens).
Not available under the new regime (Section 115BAC).
"""

from decimal import Decimal
from typing import Optional
from app.schemas.itr1 import Chapter6ADeductions, OtherSourcesIncome, AgeBracket, TaxRegime
from app.engine.constants import SECTION_80TTA_LIMIT


def compute(
    ded: Optional[Chapter6ADeductions],
    os_input: Optional[OtherSourcesIncome],
    age_bracket: AgeBracket,
    regime: TaxRegime,
) -> Decimal:
    if not ded or regime == TaxRegime.NEW:
        return Decimal("0")

    is_senior = age_bracket in (AgeBracket.SIXTY_TO_80, AgeBracket.ABOVE_80)
    if is_senior:
        return Decimal("0")  # Senior citizens must use 80TTB

    if not os_input or os_input.savings_bank_interest <= 0:
        return Decimal("0")

    return min(ded.amount_80tta, os_input.savings_bank_interest, SECTION_80TTA_LIMIT)
