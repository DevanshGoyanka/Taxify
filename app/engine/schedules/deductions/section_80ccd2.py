"""Section 80CCD(2) — Employer NPS Contribution.

Employer's contribution to NPS (Central/State Govt or other employer).
No upper limit. Allowed in BOTH old and new regimes (Section 115BAC).

For government employees: up to 14% of salary (salary = basic + DA).
For other employees: up to 10% of salary.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from app.schemas.itr1 import Chapter6ADeductions, TaxRegime

_ZERO = Decimal("0")


@dataclass(frozen=True)
class Section80CCD2Result:
    """Complete Section 80CCD(2) statutory computation result."""

    user_claim: Decimal = _ZERO
    allowed_deduction: Decimal = _ZERO


def compute_details(
    ded: Optional[Chapter6ADeductions],
    regime: TaxRegime,
) -> Section80CCD2Result:
    """Compute Section 80CCD(2) employer NPS contribution deduction.

    Args:
        ded: Chapter VI-A deductions carrying amount_80ccd2.
        regime: Tax regime — 80CCD(2) is allowed in both old and new regimes.

    Returns:
        A typed result with the allowed deduction (employer contribution,
        uncapped at the Chapter VI-A level).
    """
    user_claim = ded.amount_80ccd2 if ded else _ZERO
    if ded is None or user_claim <= _ZERO:
        return Section80CCD2Result(user_claim=user_claim)
    return Section80CCD2Result(
        user_claim=user_claim,
        allowed_deduction=user_claim,
    )


def compute(
    ded: Optional[Chapter6ADeductions],
    regime: TaxRegime,
) -> Decimal:
    """Return the allowed Section 80CCD(2) deduction for scalar callers."""
    return compute_details(ded, regime).allowed_deduction
