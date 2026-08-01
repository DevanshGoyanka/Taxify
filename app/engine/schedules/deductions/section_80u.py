"""Section 80U — Person with Disability.

Deduction for an individual who is a person with disability and
has not claimed deduction under Section 80DD for the same individual.

  - Disability (40%+): ₹75,000 (flat deduction)
  - Severe disability (80%+): ₹1,25,000

Not available under the new regime (Section 115BAC).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from app.engine.constants import (
    SECTION_80U_LIMIT,
    SECTION_80U_SEVERE_LIMIT,
)
from app.schemas.itr1 import (
    Chapter6ADeductions,
    DisabilitySeverity,
    Schedule80U,
    TaxRegime,
)

_ZERO = Decimal("0")


@dataclass(frozen=True)
class Section80UResult:
    """Complete Section 80U statutory computation result."""

    user_claim: Decimal = _ZERO
    allowed_deduction: Decimal = _ZERO
    severity: DisabilitySeverity = DisabilitySeverity.NORMAL
    source: Optional[Schedule80U] = None


def compute_details(
    ded: Optional[Chapter6ADeductions],
    schedule: Optional[Schedule80U],
    regime: TaxRegime,
    is_severe: bool = False,
) -> Section80UResult:
    """Compute Section 80U from a typed self-disability schedule.

    Validates that the schedule's declared deduction amount matches the
    statutory flat limit for the selected severity before returning the
    allowed deduction.

    Args:
        ded: Chapter VI-A deductions carrying amount_80u.
        schedule: Official Schedule 80U self-disability details.
        regime: Tax regime — new regime disallows 80U.
        is_severe: Whether the disability is severe (80%+).

    Returns:
        A typed result with the flat statutory deduction and source schedule.

    Raises:
        ValueError: If the schedule's deduction amount does not match the
            severity-based statutory limit.
    """
    user_claim = ded.amount_80u if ded else _ZERO
    severity = DisabilitySeverity.SEVERE if is_severe else DisabilitySeverity.NORMAL
    if ded is None or regime == TaxRegime.NEW or user_claim <= _ZERO:
        return Section80UResult(user_claim=user_claim, severity=severity)

    cap = SECTION_80U_SEVERE_LIMIT if is_severe else SECTION_80U_LIMIT
    if schedule is not None and schedule.deduction_amount > 0:
        expected = SECTION_80U_SEVERE_LIMIT if is_severe else SECTION_80U_LIMIT
        if schedule.deduction_amount != expected:
            raise ValueError(
                f"Schedule 80U deduction must be Rs {expected} "
                "for the selected severity"
            )
    allowed = min(user_claim, cap)
    return Section80UResult(
        user_claim=user_claim,
        allowed_deduction=allowed,
        severity=severity,
        source=schedule,
    )


def compute(
    ded: Optional[Chapter6ADeductions],
    regime: TaxRegime,
    is_severe: bool = False,
) -> Decimal:
    """Return the allowed Section 80U deduction for scalar callers."""
    if not ded or regime == TaxRegime.NEW:
        return _ZERO
    cap = SECTION_80U_SEVERE_LIMIT if is_severe else SECTION_80U_LIMIT
    return min(ded.amount_80u, cap)
