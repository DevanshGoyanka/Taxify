"""Section 80TTA — Interest on Savings Account (Non-Senior Citizens).

Deduction for interest earned on savings bank accounts.
  - Applicable only for individuals/HUFs below 60 years of age.
  - Maximum: ₹10,000.
  - Only savings bank interest qualifies (not FD/RD interest).

Mutually exclusive with Section 80TTB (for senior citizens).
Not available under the new regime (Section 115BAC).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from app.engine.constants import SECTION_80TTA_LIMIT
from app.schemas.itr1 import (
    AgeBracket,
    Chapter6ADeductions,
    OtherSourcesIncome,
    TaxRegime,
)

_ZERO = Decimal("0")


@dataclass(frozen=True)
class Section80TTAResult:
    """Complete Section 80TTA statutory computation result."""

    user_claim: Decimal = _ZERO
    savings_interest: Decimal = _ZERO
    allowed_deduction: Decimal = _ZERO
    is_senior: bool = False


def compute_details(
    ded: Optional[Chapter6ADeductions],
    os_input: Optional[OtherSourcesIncome],
    age_bracket: AgeBracket,
    regime: TaxRegime,
) -> Section80TTAResult:
    """Compute Section 80TTA savings-interest deduction.

    Args:
        ded: Chapter VI-A deductions carrying amount_80tta.
        os_input: Other-sources income with savings_bank_interest.
        age_bracket: Assessee age; senior citizens must use 80TTB.
        regime: Tax regime — new regime disallows 80TTA.

    Returns:
        A typed result with the allowed deduction (minimum of user claim,
        actual savings interest, and ₹10,000).
    """
    user_claim = ded.amount_80tta if ded else _ZERO
    is_senior = age_bracket in (AgeBracket.SIXTY_TO_80, AgeBracket.ABOVE_80)
    savings = os_input.savings_bank_interest if os_input else _ZERO
    if ded is None or regime == TaxRegime.NEW or is_senior:
        return Section80TTAResult(
            user_claim=user_claim,
            savings_interest=savings,
            is_senior=is_senior,
        )
    if savings <= 0:
        return Section80TTAResult(
            user_claim=user_claim,
            savings_interest=savings,
            is_senior=is_senior,
        )
    allowed = min(user_claim, savings, SECTION_80TTA_LIMIT)
    return Section80TTAResult(
        user_claim=user_claim,
        savings_interest=savings,
        allowed_deduction=allowed,
        is_senior=is_senior,
    )


def compute(
    ded: Optional[Chapter6ADeductions],
    os_input: Optional[OtherSourcesIncome],
    age_bracket: AgeBracket,
    regime: TaxRegime,
) -> Decimal:
    """Return the allowed Section 80TTA deduction for scalar callers."""
    return compute_details(ded, os_input, age_bracket, regime).allowed_deduction
