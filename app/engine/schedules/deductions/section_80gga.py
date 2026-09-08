"""Section 80GGA donation eligibility computation."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from app.engine.constants import SECTION_80G_CASH_LIMIT
from app.schemas.itr1 import (
    Chapter6ADeductions,
    Donation80GGA,
    Schedule80GGA,
    TaxRegime,
)

_ZERO = Decimal("0")


@dataclass(frozen=True)
class Section80GGAComputedRow:
    """Computed eligibility for one Section 80GGA donation row."""

    source: Donation80GGA
    gross_amount: Decimal
    eligible_amount: Decimal


@dataclass(frozen=True)
class Section80GGAResult:
    """Complete Section 80GGA statutory computation result."""

    user_claim: Decimal = _ZERO
    gross_amount: Decimal = _ZERO
    cash_amount: Decimal = _ZERO
    other_mode_amount: Decimal = _ZERO
    statutory_eligible: Decimal = _ZERO
    allowed_deduction: Decimal = _ZERO
    rows: tuple[Section80GGAComputedRow, ...] = ()


def compute_details(
    ded: Optional[Chapter6ADeductions],
    schedule: Optional[Schedule80GGA],
    available_gti: Decimal,
    regime: TaxRegime,
) -> Section80GGAResult:
    """Compute Section 80GGA from official donation rows."""
    user_claim = ded.amount_80gga if ded else _ZERO
    if ded is None or regime == TaxRegime.NEW or available_gti <= _ZERO:
        return Section80GGAResult(user_claim=user_claim)
    if schedule is None or not schedule.donations:
        allowed = min(user_claim, available_gti)
        return Section80GGAResult(
            user_claim=user_claim,
            gross_amount=user_claim,
            other_mode_amount=user_claim,
            statutory_eligible=allowed,
            allowed_deduction=allowed,
        )

    raw_rows: list[Section80GGAComputedRow] = []
    for donation in schedule.donations:
        eligible_cash = (
            donation.cash_amount
            if donation.cash_amount <= SECTION_80G_CASH_LIMIT
            else _ZERO
        )
        gross = donation.cash_amount + donation.other_mode_amount
        raw_rows.append(Section80GGAComputedRow(
            source=donation,
            gross_amount=gross,
            eligible_amount=eligible_cash + donation.other_mode_amount,
        ))

    statutory = sum((row.eligible_amount for row in raw_rows), _ZERO)
    allowed = min(user_claim, statutory, available_gti)
    remaining = allowed
    rows: list[Section80GGAComputedRow] = []
    for row in raw_rows:
        row_allowed = min(row.eligible_amount, remaining)
        remaining -= row_allowed
        rows.append(Section80GGAComputedRow(
            source=row.source,
            gross_amount=row.gross_amount,
            eligible_amount=row_allowed,
        ))
    return Section80GGAResult(
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
    schedule: Optional[Schedule80GGA] = None,
    available_gti: Decimal = Decimal("99999999999999"),
) -> Decimal:
    """Return the allowed Section 80GGA deduction for scalar callers."""
    return compute_details(ded, schedule, available_gti, regime).allowed_deduction
