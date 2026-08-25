"""Section 80D — Health Insurance Premium.

Sub-limits:
  - Self, spouse, dependent children:
      - Non-senior: ₹25,000
      - Senior citizen (60+): ₹50,000
  - Parents:
      - Non-senior: ₹25,000
      - Senior citizen (60+): ₹50,000
  - Preventive health check-up: ₹5,000 (included within above limits)

Aggregate limit (self + parents): ₹1,00,000.
Not available under the new regime (Section 115BAC).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from app.engine.constants import (
    SECTION_80D_PARENTS_LIMIT,
    SECTION_80D_PARENTS_SENIOR_LIMIT,
    SECTION_80D_PREVENTIVE_CHECKUP_LIMIT,
    SECTION_80D_SELF_FAMILY_LIMIT,
    SECTION_80D_SELF_FAMILY_SENIOR_LIMIT,
)
from app.schemas.itr1 import (
    AgeBracket,
    Chapter6ADeductions,
    Schedule80D,
    TaxRegime,
)

_ZERO = Decimal("0")


@dataclass(frozen=True)
class Section80DResult:
    """Complete Section 80D statutory computation result."""

    self_premium: Decimal = _ZERO
    parents_premium: Decimal = _ZERO
    preventive_self: Decimal = _ZERO
    preventive_parents: Decimal = _ZERO
    eligible_self: Decimal = _ZERO
    eligible_parents: Decimal = _ZERO
    allowed_deduction: Decimal = _ZERO
    senior_self: bool = False
    senior_parents: bool = False
    source: Optional[Schedule80D] = None


def compute_details(
    ded: Optional[Chapter6ADeductions],
    age_bracket: AgeBracket,
    regime: TaxRegime,
    schedule: Optional[Schedule80D] = None,
    is_parents_senior: bool = False,
) -> Section80DResult:
    """Compute Section 80D from scalar claims and optional canonical schedule.

    Args:
        ded: Chapter VI-A deductions carrying self/parents/preventive amounts.
        age_bracket: Assessee age bracket determining the self-family cap.
        regime: Tax regime — new regime disallows Section 80D.
        schedule: Optional canonical Schedule 80D with policy rows and flags.
        is_parents_senior: Whether parents are senior citizens.

    Returns:
        A typed result with self/parents bucket eligibility, the shared
        preventive-checkup sub-limit allocation, and the total allowed
        deduction.
    """
    if not ded or regime == TaxRegime.NEW:
        return Section80DResult(source=schedule)

    is_senior = age_bracket in (AgeBracket.SIXTY_TO_80, AgeBracket.ABOVE_80)

    preventive_self = min(
        ded.amount_80d_preventive_self,
        SECTION_80D_PREVENTIVE_CHECKUP_LIMIT,
    )
    preventive_parents = min(
        ded.amount_80d_preventive_parents,
        max(_ZERO, SECTION_80D_PREVENTIVE_CHECKUP_LIMIT - preventive_self),
    )

    self_premium = ded.amount_80d_self_family
    parents_premium = ded.amount_80d_parents
    if schedule is not None:
        self_premium = (
            schedule.premium_1b_senior
            if is_senior
            else schedule.premium_1a_non_senior
        )
        parents_premium = (
            schedule.premium_2b_parents_senior
            if is_parents_senior
            else schedule.premium_2a_parents_non_senior
        )

    cap_self = (
        SECTION_80D_SELF_FAMILY_SENIOR_LIMIT
        if is_senior
        else SECTION_80D_SELF_FAMILY_LIMIT
    )
    medical_self = schedule.medical_expense_self_senior if schedule else _ZERO
    total_self = self_premium + preventive_self + medical_self
    eligible_self = min(total_self, cap_self)

    parents_cap = (
        SECTION_80D_PARENTS_SENIOR_LIMIT
        if is_parents_senior
        else SECTION_80D_PARENTS_LIMIT
    )
    medical_parents = (
        schedule.medical_expense_parents_senior if schedule else _ZERO
    )
    total_parents = parents_premium + preventive_parents + medical_parents
    eligible_parents = min(total_parents, parents_cap)

    return Section80DResult(
        self_premium=self_premium,
        parents_premium=parents_premium,
        preventive_self=preventive_self,
        preventive_parents=preventive_parents,
        eligible_self=eligible_self,
        eligible_parents=eligible_parents,
        allowed_deduction=eligible_self + eligible_parents,
        senior_self=is_senior,
        senior_parents=is_parents_senior,
        source=schedule,
    )


def compute(
    ded: Optional[Chapter6ADeductions],
    age_bracket: AgeBracket,
    regime: TaxRegime,
    is_parents_senior: bool = False,
) -> Decimal:
    """Return the allowed Section 80D deduction for scalar callers."""
    return compute_details(
        ded, age_bracket, regime, None, is_parents_senior,
    ).allowed_deduction
