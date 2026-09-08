"""Section 80DD — Medical Treatment of Dependent with Disability.

Deduction for expenditure on medical treatment, training, and rehabilitation
of a dependent with disability.

  - Disability (40%+): ₹75,000 (flat deduction, no proof of actual spend)
  - Severe disability (80%+): ₹1,25,000

Not available under the new regime (Section 115BAC).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from app.engine.constants import (
    SECTION_80DD_LIMIT,
    SECTION_80DD_SEVERE_LIMIT,
)
from app.schemas.itr1 import (
    Chapter6ADeductions,
    DisabilitySeverity,
    Schedule80DD,
    TaxRegime,
)

_ZERO = Decimal("0")


@dataclass(frozen=True)
class Section80DDResult:
    """Complete Section 80DD statutory computation result."""

    user_claim: Decimal = _ZERO
    allowed_deduction: Decimal = _ZERO
    severity: DisabilitySeverity = DisabilitySeverity.NORMAL
    source: Optional[Schedule80DD] = None


def compute_details(
    ded: Optional[Chapter6ADeductions],
    schedule: Optional[Schedule80DD],
    regime: TaxRegime,
    is_severe: bool = False,
) -> Section80DDResult:
    """Compute Section 80DD from a typed disability schedule.

    Validates that the schedule's declared deduction amount matches the
    statutory flat limit for the selected severity before returning the
    allowed deduction.

    Args:
        ded: Chapter VI-A deductions carrying amount_80dd.
        schedule: Official Schedule 80DD disability details.
        regime: Tax regime — new regime disallows 80DD.
        is_severe: Whether the disability is severe (80%+).

    Returns:
        A typed result with the flat statutory deduction and source schedule.

    Raises:
        ValueError: If the schedule's deduction amount does not match the
            severity-based statutory limit.
    """
    user_claim = ded.amount_80dd if ded else _ZERO
    severity = DisabilitySeverity.SEVERE if is_severe else DisabilitySeverity.NORMAL
    if ded is None or regime == TaxRegime.NEW or user_claim <= _ZERO:
        return Section80DDResult(user_claim=user_claim, severity=severity)

    cap = SECTION_80DD_SEVERE_LIMIT if is_severe else SECTION_80DD_LIMIT
    if schedule is not None and schedule.deduction_amount > 0:
        expected = SECTION_80DD_SEVERE_LIMIT if is_severe else SECTION_80DD_LIMIT
        if schedule.deduction_amount != expected:
            raise ValueError(
                f"Schedule 80DD deduction must be Rs {expected} "
                "for the selected severity"
            )
    allowed = min(user_claim, cap)
    return Section80DDResult(
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
    """Return the allowed Section 80DD deduction for scalar callers."""
    if not ded or regime == TaxRegime.NEW:
        return _ZERO
    cap = SECTION_80DD_SEVERE_LIMIT if is_severe else SECTION_80DD_LIMIT
    return min(ded.amount_80dd, cap)
