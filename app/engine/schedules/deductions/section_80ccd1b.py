"""Section 80CCD(1B) — Additional NPS Contribution.

Over and above the ₹1,50,000 combined limit of 80C+80CCC+80CCD(1).
Maximum deduction: ₹50,000.

Not available under the new regime (Section 115BAC).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from app.engine.constants import SECTION_80CCD1B_LIMIT
from app.schemas.itr1 import Chapter6ADeductions, TaxRegime

_ZERO = Decimal("0")


@dataclass(frozen=True)
class Section80CCD1BResult:
    """Complete Section 80CCD(1B) statutory computation result."""

    user_claim: Decimal = _ZERO
    statutory_eligible: Decimal = _ZERO
    allowed_deduction: Decimal = _ZERO


def compute_details(
    ded: Optional[Chapter6ADeductions],
    regime: TaxRegime,
) -> Section80CCD1BResult:
    """Compute Section 80CCD(1B) additional NPS contribution deduction.

    Args:
        ded: Chapter VI-A deductions carrying amount_80ccd1b.
        regime: Tax regime — new regime disallows 80CCD(1B).

    Returns:
        A typed result with the allowed deduction capped at ₹50,000.
    """
    user_claim = ded.amount_80ccd1b if ded else _ZERO
    if ded is None or regime == TaxRegime.NEW or user_claim <= _ZERO:
        return Section80CCD1BResult(user_claim=user_claim)
    allowed = min(user_claim, SECTION_80CCD1B_LIMIT)
    return Section80CCD1BResult(
        user_claim=user_claim,
        statutory_eligible=allowed,
        allowed_deduction=allowed,
    )


def compute(
    ded: Optional[Chapter6ADeductions],
    regime: TaxRegime,
) -> Decimal:
    """Return the allowed Section 80CCD(1B) deduction for scalar callers."""
    return compute_details(ded, regime).allowed_deduction
