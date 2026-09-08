"""Section 80TTB — Interest on Deposits for Senior Citizens.

Deduction for interest on deposits (savings bank, fixed deposits, recurring
deposits, post office deposits) for senior citizens (age >= 60).

  - Maximum: ₹50,000.
  - Covers ALL deposit interest (unlike 80TTA which is savings-only).
  - Mutually exclusive with Section 80TTA (for non-seniors).

Not available under the new regime (Section 115BAC).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from app.engine.constants import SECTION_80TTB_LIMIT
from app.schemas.itr1 import (
    AgeBracket,
    Chapter6ADeductions,
    OtherSourcesIncome,
    TaxRegime,
)

_ZERO = Decimal("0")


@dataclass(frozen=True)
class Section80TTBResult:
    """Complete Section 80TTB statutory computation result."""

    user_claim: Decimal = _ZERO
    total_deposit_interest: Decimal = _ZERO
    allowed_deduction: Decimal = _ZERO
    is_senior: bool = False


def compute_details(
    ded: Optional[Chapter6ADeductions],
    os_input: Optional[OtherSourcesIncome],
    age_bracket: AgeBracket,
    regime: TaxRegime,
) -> Section80TTBResult:
    """Compute Section 80TTB deposit-interest deduction.

    Args:
        ded: Chapter VI-A deductions carrying amount_80ttb.
        os_input: Other-sources income with savings + fixed-deposit interest.
        age_bracket: Assessee age; non-seniors must use 80TTA.
        regime: Tax regime — new regime disallows 80TTB.

    Returns:
        A typed result with the allowed deduction (minimum of user claim,
        total deposit interest, and ₹50,000).
    """
    user_claim = ded.amount_80ttb if ded else _ZERO
    is_senior = age_bracket in (AgeBracket.SIXTY_TO_80, AgeBracket.ABOVE_80)
    total_interest = _ZERO
    if os_input:
        total_interest = (
            os_input.savings_bank_interest + os_input.fixed_deposit_interest
        )
    if ded is None or regime == TaxRegime.NEW or not is_senior:
        return Section80TTBResult(
            user_claim=user_claim,
            total_deposit_interest=total_interest,
            is_senior=is_senior,
        )
    if total_interest <= 0:
        return Section80TTBResult(
            user_claim=user_claim,
            total_deposit_interest=total_interest,
            is_senior=is_senior,
        )
    allowed = min(user_claim, total_interest, SECTION_80TTB_LIMIT)
    return Section80TTBResult(
        user_claim=user_claim,
        total_deposit_interest=total_interest,
        allowed_deduction=allowed,
        is_senior=is_senior,
    )


def compute(
    ded: Optional[Chapter6ADeductions],
    os_input: Optional[OtherSourcesIncome],
    age_bracket: AgeBracket,
    regime: TaxRegime,
) -> Decimal:
    """Return the allowed Section 80TTB deduction for scalar callers."""
    return compute_details(ded, os_input, age_bracket, regime).allowed_deduction
