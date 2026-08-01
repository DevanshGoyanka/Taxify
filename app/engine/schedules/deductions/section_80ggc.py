"""Section 80GGC political-contribution eligibility computation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional

from app.schemas.itr1 import (
    Chapter6ADeductions,
    PoliticalContribution,
    Schedule80GGC,
    TaxRegime,
)

_ZERO = Decimal("0")
_PREVIOUS_YEAR_START = date(2025, 4, 1)
_PREVIOUS_YEAR_END = date(2026, 3, 31)


@dataclass(frozen=True)
class Section80GGCComputedRow:
    """Computed eligibility for one political contribution."""

    source: PoliticalContribution
    gross_amount: Decimal
    eligible_amount: Decimal


@dataclass(frozen=True)
class Section80GGCResult:
    """Complete Section 80GGC statutory computation result."""

    user_claim: Decimal = _ZERO
    gross_amount: Decimal = _ZERO
    cash_amount: Decimal = _ZERO
    other_mode_amount: Decimal = _ZERO
    statutory_eligible: Decimal = _ZERO
    allowed_deduction: Decimal = _ZERO
    rows: tuple[Section80GGCComputedRow, ...] = ()


def _is_complete_non_cash_row(
    contribution: PoliticalContribution,
    assessee_pan: Optional[str],
) -> bool:
    """Return whether a non-cash row has all statutory supporting details."""
    return bool(
        contribution.contribution_date
        and _PREVIOUS_YEAR_START
        <= contribution.contribution_date
        <= _PREVIOUS_YEAR_END
        and contribution.transaction_ref
        and contribution.ifsc_code
        and contribution.political_party_name
        and contribution.political_party_pan
        and contribution.political_party_pan != assessee_pan
    )


def compute_details(
    ded: Optional[Chapter6ADeductions],
    schedule: Optional[Schedule80GGC],
    available_gti: Decimal,
    regime: TaxRegime,
    assessee_pan: Optional[str] = None,
) -> Section80GGCResult:
    """Compute Section 80GGC from official political-contribution rows."""
    user_claim = ded.amount_80ggc if ded else _ZERO
    if ded is None or regime == TaxRegime.NEW or available_gti <= _ZERO:
        return Section80GGCResult(user_claim=user_claim)
    if schedule is None or not schedule.contributions:
        allowed = min(user_claim, available_gti)
        return Section80GGCResult(
            user_claim=user_claim,
            gross_amount=user_claim,
            other_mode_amount=user_claim,
            statutory_eligible=allowed,
            allowed_deduction=allowed,
        )

    raw_rows: list[Section80GGCComputedRow] = []
    for contribution in schedule.contributions:
        gross = contribution.cash_amount + contribution.other_mode_amount
        eligible = (
            contribution.other_mode_amount
            if _is_complete_non_cash_row(contribution, assessee_pan)
            else _ZERO
        )
        raw_rows.append(Section80GGCComputedRow(
            source=contribution,
            gross_amount=gross,
            eligible_amount=eligible,
        ))
    statutory = sum((row.eligible_amount for row in raw_rows), _ZERO)
    allowed = min(user_claim, statutory, available_gti)
    remaining = allowed
    rows: list[Section80GGCComputedRow] = []
    for row in raw_rows:
        row_allowed = min(row.eligible_amount, remaining)
        remaining -= row_allowed
        rows.append(Section80GGCComputedRow(
            source=row.source,
            gross_amount=row.gross_amount,
            eligible_amount=row_allowed,
        ))
    return Section80GGCResult(
        user_claim=user_claim,
        gross_amount=sum((row.gross_amount for row in raw_rows), _ZERO),
        cash_amount=sum((row.source.cash_amount for row in raw_rows), _ZERO),
        other_mode_amount=sum((row.source.other_mode_amount for row in raw_rows), _ZERO),
        statutory_eligible=statutory,
        allowed_deduction=allowed,
        rows=tuple(rows),
    )


def compute(
    ded: Optional[Chapter6ADeductions],
    regime: TaxRegime,
    schedule: Optional[Schedule80GGC] = None,
    available_gti: Decimal = Decimal("99999999999999"),
) -> Decimal:
    """Return the allowed Section 80GGC deduction for scalar callers."""
    return compute_details(ded, schedule, available_gti, regime).allowed_deduction
