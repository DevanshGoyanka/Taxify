"""Section 80QQB (royalty income of authors) and Section 80RRB (royalty on
patents).

Both are flat-ceiling deductions -- lower of the actual royalty income and
Rs 3,00,000 -- claimable only in the old regime. Neither is part of the
shared ``Chapter6ADeductions`` (that class is deliberately minimal for
ITR-1's salaried-filer scope, per its own docstring), so this module takes
plain ``Decimal`` arguments rather than a ``Chapter6ADeductions`` instance,
unlike every sibling module in this package.

80QQB has a real "royalty income" field to cap the claim against
(``ReturnDraft.Deductions.section80QQBRoyaltyIncome``); 80RRB does not --
the frontend has no equivalent field for it today, so 80RRB is capped only
against the flat statutory ceiling.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.engine.constants import SECTION_80QQB_LIMIT, SECTION_80RRB_LIMIT
from app.schemas.itr1 import TaxRegime

_ZERO = Decimal("0")


@dataclass(frozen=True)
class Section80QQBResult:
    """Section 80QQB statutory computation result."""

    user_claim: Decimal = _ZERO
    royalty_income: Decimal = _ZERO
    allowed_deduction: Decimal = _ZERO


@dataclass(frozen=True)
class Section80RRBResult:
    """Section 80RRB statutory computation result."""

    user_claim: Decimal = _ZERO
    allowed_deduction: Decimal = _ZERO


def compute_80qqb_details(
    claim: Decimal,
    royalty_income: Decimal,
    regime: TaxRegime,
) -> Section80QQBResult:
    """Compute the allowed Section 80QQB deduction: lower of the claim, the
    actual royalty income, and the ₹3,00,000 statutory ceiling."""
    if regime == TaxRegime.NEW or claim <= _ZERO:
        return Section80QQBResult(user_claim=claim, royalty_income=royalty_income)
    allowed = min(claim, royalty_income, SECTION_80QQB_LIMIT) if royalty_income > _ZERO else min(claim, SECTION_80QQB_LIMIT)
    return Section80QQBResult(
        user_claim=claim, royalty_income=royalty_income, allowed_deduction=allowed,
    )


def compute_80rrb_details(claim: Decimal, regime: TaxRegime) -> Section80RRBResult:
    """Compute the allowed Section 80RRB deduction: lower of the claim and
    the ₹3,00,000 statutory ceiling (no royalty-income field exists on the
    frontend draft for 80RRB today, so only the flat ceiling applies)."""
    if regime == TaxRegime.NEW or claim <= _ZERO:
        return Section80RRBResult(user_claim=claim)
    return Section80RRBResult(user_claim=claim, allowed_deduction=min(claim, SECTION_80RRB_LIMIT))
