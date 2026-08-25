"""Section 80G donation eligibility and category-level computation."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from app.engine.constants import SECTION_80G_CASH_LIMIT
from app.schemas.itr1 import Chapter6ADeductions, Donation80G, TaxRegime

_ZERO = Decimal("0")
_HALF = Decimal("0.5")
_TEN_PERCENT = Decimal("0.10")


@dataclass(frozen=True)
class Section80GComputedRow:
    """Computed eligibility for one Section 80G donation row."""

    source: Donation80G
    category: str
    gross_amount: Decimal
    eligible_amount: Decimal


@dataclass(frozen=True)
class Section80GCategoryResult:
    """Computed totals for one official Section 80G category."""

    rows: tuple[Section80GComputedRow, ...] = ()
    cash_amount: Decimal = _ZERO
    other_mode_amount: Decimal = _ZERO
    gross_amount: Decimal = _ZERO
    eligible_amount: Decimal = _ZERO


@dataclass(frozen=True)
class Section80GResult:
    """Complete Section 80G statutory computation result."""

    user_claim: Decimal = _ZERO
    gross_amount: Decimal = _ZERO
    cash_amount: Decimal = _ZERO
    other_mode_amount: Decimal = _ZERO
    statutory_eligible: Decimal = _ZERO
    allowed_deduction: Decimal = _ZERO
    categories: dict[str, Section80GCategoryResult] = field(default_factory=dict)


def _category(donation: Donation80G) -> str:
    """Return the official category identifier for a donation row."""
    if donation.category is not None:
        if donation.category.qualifying_percentage == "100%":
            return (
                "100_with_limit"
                if donation.category.has_qualifying_limit
                else "100_without_limit"
            )
        return (
            "50_with_limit"
            if donation.category.has_qualifying_limit
            else "50_without_limit"
        )
    full_rate = donation.qualifying_percentage == "100%"
    limited = (donation.limit_on_deduction or "").lower() == "with limit"
    if full_rate and not limited:
        return "100_without_limit"
    if not full_rate and not limited:
        return "50_without_limit"
    if full_rate:
        return "100_with_limit"
    return "50_with_limit"


def _allocate(
    rows: list[tuple[Donation80G, Decimal]],
    category: str,
    qualifying_base: Decimal,
    rate: Decimal,
) -> Section80GCategoryResult:
    """Allocate category eligibility deterministically across donation rows."""
    computed: list[Section80GComputedRow] = []
    remaining = max(_ZERO, qualifying_base)
    for donation, base_amount in rows:
        qualified = min(base_amount, remaining)
        remaining -= qualified
        computed.append(Section80GComputedRow(
            source=donation,
            category=category,
            gross_amount=donation.cash_amount + donation.non_cash_amount,
            eligible_amount=qualified * rate,
        ))
    return Section80GCategoryResult(
        rows=tuple(computed),
        cash_amount=sum((row[0].cash_amount for row in rows), _ZERO),
        other_mode_amount=sum((row[0].non_cash_amount for row in rows), _ZERO),
        gross_amount=sum(
            (row[0].cash_amount + row[0].non_cash_amount for row in rows),
            _ZERO,
        ),
        eligible_amount=sum((row.eligible_amount for row in computed), _ZERO),
    )


def _cap_categories(
    categories: dict[str, Section80GCategoryResult],
    allowed: Decimal,
) -> dict[str, Section80GCategoryResult]:
    """Allocate the final user/GTI cap across computed category rows."""
    remaining = allowed
    capped: dict[str, Section80GCategoryResult] = {}
    for key, category in categories.items():
        rows: list[Section80GComputedRow] = []
        for row in category.rows:
            row_allowed = min(row.eligible_amount, remaining)
            remaining -= row_allowed
            rows.append(Section80GComputedRow(
                source=row.source,
                category=row.category,
                gross_amount=row.gross_amount,
                eligible_amount=row_allowed,
            ))
        capped[key] = Section80GCategoryResult(
            rows=tuple(rows),
            cash_amount=category.cash_amount,
            other_mode_amount=category.other_mode_amount,
            gross_amount=category.gross_amount,
            eligible_amount=sum((row.eligible_amount for row in rows), _ZERO),
        )
    return capped


def compute_details(
    ded: Optional[Chapter6ADeductions],
    adjusted_gti: Decimal,
    regime: TaxRegime,
) -> Section80GResult:
    """Compute complete Section 80G eligibility from structured donation rows."""
    if ded is None or regime == TaxRegime.NEW or adjusted_gti <= _ZERO:
        return Section80GResult(user_claim=ded.amount_80g if ded else _ZERO)

    donations = [row for row in (ded.donations_80g or []) if isinstance(row, Donation80G)]
    if not donations:
        allowed = min(ded.amount_80g, adjusted_gti)
        return Section80GResult(
            user_claim=ded.amount_80g,
            gross_amount=ded.amount_80g,
            other_mode_amount=ded.amount_80g,
            statutory_eligible=allowed,
            allowed_deduction=allowed,
        )

    cash_by_pan: dict[str, Decimal] = {}
    for index, donation in enumerate(donations):
        pan_key = donation.donee_pan or f"__row_{index}"
        cash_by_pan[pan_key] = cash_by_pan.get(pan_key, _ZERO) + donation.cash_amount

    grouped: dict[str, list[tuple[Donation80G, Decimal]]] = {
        "100_without_limit": [],
        "50_without_limit": [],
        "100_with_limit": [],
        "50_with_limit": [],
    }
    for index, donation in enumerate(donations):
        pan_key = donation.donee_pan or f"__row_{index}"
        eligible_cash = (
            donation.cash_amount
            if cash_by_pan[pan_key] <= SECTION_80G_CASH_LIMIT
            else _ZERO
        )
        grouped[_category(donation)].append(
            (donation, eligible_cash + donation.non_cash_amount)
        )

    limited_ceiling = adjusted_gti * _TEN_PERCENT
    limited_100_base = min(
        sum((base for _, base in grouped["100_with_limit"]), _ZERO),
        limited_ceiling,
    )
    remaining_limited = max(_ZERO, limited_ceiling - limited_100_base)
    limited_50_base = min(
        sum((base for _, base in grouped["50_with_limit"]), _ZERO),
        remaining_limited,
    )
    categories = {
        "100_without_limit": _allocate(
            grouped["100_without_limit"],
            "100_without_limit",
            sum((base for _, base in grouped["100_without_limit"]), _ZERO),
            Decimal("1"),
        ),
        "50_without_limit": _allocate(
            grouped["50_without_limit"],
            "50_without_limit",
            sum((base for _, base in grouped["50_without_limit"]), _ZERO),
            _HALF,
        ),
        "100_with_limit": _allocate(
            grouped["100_with_limit"],
            "100_with_limit",
            limited_100_base,
            Decimal("1"),
        ),
        "50_with_limit": _allocate(
            grouped["50_with_limit"],
            "50_with_limit",
            limited_50_base,
            _HALF,
        ),
    }
    statutory = sum((category.eligible_amount for category in categories.values()), _ZERO)
    effective_user_claim = ded.amount_80g
    allowed = min(effective_user_claim, statutory, adjusted_gti)
    categories = _cap_categories(categories, allowed)
    return Section80GResult(
        user_claim=ded.amount_80g,
        gross_amount=sum(
            (donation.cash_amount + donation.non_cash_amount for donation in donations),
            _ZERO,
        ),
        cash_amount=sum((donation.cash_amount for donation in donations), _ZERO),
        other_mode_amount=sum((donation.non_cash_amount for donation in donations), _ZERO),
        statutory_eligible=statutory,
        allowed_deduction=allowed,
        categories=categories,
    )


def compute(
    ded: Optional[Chapter6ADeductions],
    adjusted_gti: Decimal,
    regime: TaxRegime,
) -> Decimal:
    """Return the allowed Section 80G deduction for scalar callers."""
    return compute_details(ded, adjusted_gti, regime).allowed_deduction
