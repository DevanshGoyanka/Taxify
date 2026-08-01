"""Section 80C + 80CCC + 80CCD(1) — Combined ₹1,50,000 pool (u/s 80CCE).

Covers:
  - 80C: LIC, PPF, EPF, ELSS, NSC, tuition fees, home loan principal, etc.
  - 80CCC: Annuity plan premiums (LIC/other insurers)
  - 80CCD(1): Employee contribution to NPS

These three sections share a combined ceiling of ₹1,50,000 as per Section 80CCE.
Only 80C entries carry official detail rows in Schedule 80C; 80CCC and 80CCD(1)
contribute to the shared cap but do not produce separate schedule rows in ITR-1.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from app.engine.constants import SECTION_80C_LIMIT
from app.schemas.itr1 import (
    Chapter6ADeductions,
    Schedule80CEntry,
    TaxRegime,
)

_ZERO = Decimal("0")


@dataclass(frozen=True)
class Section80CComputedRow:
    """Computed eligibility for one Schedule 80C entry."""

    source: Schedule80CEntry
    gross_amount: Decimal
    eligible_amount: Decimal


@dataclass(frozen=True)
class Section80CResult:
    """Complete Section 80CCE statutory computation result."""

    user_claim: Decimal = _ZERO
    gross_amount: Decimal = _ZERO
    statutory_eligible: Decimal = _ZERO
    allowed_deduction: Decimal = _ZERO
    rows: tuple[Section80CComputedRow, ...] = ()


def compute_details(
    ded: Optional[Chapter6ADeductions],
    entries: Optional[list[Schedule80CEntry]],
    regime: TaxRegime,
) -> Section80CResult:
    """Compute the 80C component and allocate per-row eligibility.

    The combined 80CCE pool (80C + 80CCC + 80CCD(1)) is capped at
    ₹1,50,000 by Section 80CCE. This method allocates only the 80C
    component's share across the official Schedule 80C detail rows;
    80CCC and 80CCD(1) are emitted as separate Chapter VI-A line items
    and do not carry schedule rows in ITR-1.

    Args:
        ded: Chapter VI-A deductions carrying amount_80c, amount_80ccc, amount_80ccd1.
        entries: Official Schedule 80C detail rows (identifier + amount).
        regime: Tax regime — new regime disallows all 80CCE components.

    Returns:
        A typed result with per-row allocated eligibility for the 80C component
        only, with a deterministic whole-rupee residual on the final row.
    """
    user_claim = ded.amount_80c if ded else _ZERO
    if ded is None or regime == TaxRegime.NEW or user_claim <= _ZERO:
        return Section80CResult(user_claim=user_claim)

    raw_total_80cce = (
        ded.amount_80c + ded.amount_80ccc + ded.amount_80ccd1
    )
    capped_80cce = min(raw_total_80cce, SECTION_80C_LIMIT)
    # 80C component's share of the combined cap (proportional).
    if raw_total_80cce == 0:
        component_capped = _ZERO
    else:
        component_capped = min(
            user_claim,
            user_claim / raw_total_80cce * capped_80cce,
        )

    positive_entries = [
        entry for entry in (entries or []) if entry.amount > 0
    ]

    if not positive_entries:
        return Section80CResult(
            user_claim=user_claim,
            gross_amount=user_claim,
            statutory_eligible=component_capped,
            allowed_deduction=component_capped,
        )

    raw_total = sum((entry.amount for entry in positive_entries), _ZERO)
    allowed = min(user_claim, raw_total, component_capped)
    remaining = allowed
    rows: list[Section80CComputedRow] = []
    for index, entry in enumerate(positive_entries):
        if index == len(positive_entries) - 1:
            row_allowed = remaining
        else:
            row_allowed = (entry.amount / raw_total * allowed).quantize(
                Decimal("1")
            )
            row_allowed = min(row_allowed, remaining)
            remaining -= row_allowed
        rows.append(Section80CComputedRow(
            source=entry,
            gross_amount=entry.amount,
            eligible_amount=max(_ZERO, row_allowed),
        ))

    return Section80CResult(
        user_claim=user_claim,
        gross_amount=raw_total,
        statutory_eligible=allowed,
        allowed_deduction=allowed,
        rows=tuple(rows),
    )


def compute(
    ded: Optional[Chapter6ADeductions],
    regime: TaxRegime,
) -> Decimal:
    """Return the combined 80CCE pool (80C + 80CCC + 80CCD(1)) capped at ₹1.5L."""
    if not ded or regime == TaxRegime.NEW:
        return _ZERO
    raw = ded.amount_80c + ded.amount_80ccc + ded.amount_80ccd1
    return min(raw, SECTION_80C_LIMIT)


def compute_80ccc(
    ded: Optional[Chapter6ADeductions],
    regime: TaxRegime,
) -> Decimal:
    """Return the 80CCC proportional share of the 80CCE cap."""
    if not ded or regime == TaxRegime.NEW:
        return _ZERO
    raw_total = ded.amount_80c + ded.amount_80ccc + ded.amount_80ccd1
    if raw_total == 0:
        return _ZERO
    capped = min(raw_total, SECTION_80C_LIMIT)
    return min(ded.amount_80ccc, ded.amount_80ccc / raw_total * capped)


def compute_80ccd1(
    ded: Optional[Chapter6ADeductions],
    regime: TaxRegime,
) -> Decimal:
    """Return the 80CCD(1) proportional share of the 80CCE cap."""
    if not ded or regime == TaxRegime.NEW:
        return _ZERO
    raw_total = ded.amount_80c + ded.amount_80ccc + ded.amount_80ccd1
    if raw_total == 0:
        return _ZERO
    capped = min(raw_total, SECTION_80C_LIMIT)
    return min(ded.amount_80ccd1, ded.amount_80ccd1 / raw_total * capped)
