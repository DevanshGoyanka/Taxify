"""Shared per-row allocation for interest-based deduction loans.

Sections 80E, 80EE, 80EEA, and 80EEB all share the same official row
shape (``OfficialDeductionLoanEntry`` with an ``interest_paid`` field)
and the same statutory allocation rule:

    allowed = min(user claim, total row interest, remaining GTI)

with per-row eligibility allocated proportionally and a deterministic
whole-rupee residual on the final eligible row.

Each section's dedicated module retains its statutory eligibility rule
(sections caps, date windows, property/vehicle evidence) and delegates
the mechanical row allocation here.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from app.schemas.itr1 import OfficialDeductionLoanEntry

_ZERO = Decimal("0")


@dataclass(frozen=True)
class LoanDeductionComputedRow:
    """Computed eligibility for one deduction-loan row."""

    source: OfficialDeductionLoanEntry
    gross_interest: Decimal
    eligible_interest: Decimal


@dataclass(frozen=True)
class LoanDeductionResult:
    """Complete interest-deduction statutory computation result."""

    user_claim: Decimal = _ZERO
    gross_interest: Decimal = _ZERO
    statutory_eligible: Decimal = _ZERO
    allowed_deduction: Decimal = _ZERO
    rows: tuple[LoanDeductionComputedRow, ...] = ()


def allocate_loan_deduction(
    user_claim: Decimal,
    entries: Optional[list[OfficialDeductionLoanEntry]],
    available_gti: Decimal,
    section_cap: Optional[Decimal] = None,
) -> LoanDeductionResult:
    """Allocate an interest deduction across official loan rows.

    Args:
        user_claim: The scalar amount claimed by the user for this section.
        entries: Official loan rows with ``interest_paid``.
        available_gti: Remaining GTI available to this section after prior
            Chapter VI-A deductions.
        section_cap: Optional per-section statutory cap (e.g. ₹50,000 for 80EE).

    Returns:
        A typed result with per-row allocated eligibility and a deterministic
        whole-rupee residual on the final eligible row.
    """
    if user_claim <= _ZERO or available_gti <= _ZERO:
        return LoanDeductionResult(user_claim=user_claim)

    positive_entries = [
        entry for entry in (entries or []) if entry.interest_paid > 0
    ]

    if not positive_entries:
        allowed = min(
            user_claim,
            available_gti,
            section_cap if section_cap is not None else available_gti,
        )
        return LoanDeductionResult(
            user_claim=user_claim,
            gross_interest=user_claim,
            statutory_eligible=allowed,
            allowed_deduction=allowed,
        )

    raw_interest = sum(
        (entry.interest_paid for entry in positive_entries), _ZERO
    )
    if user_claim > raw_interest:
        raise ValueError(
            f"Eligible Section deduction (Rs {user_claim}) must be positive and "
            f"not exceed row interest (Rs {raw_interest})"
        )
    cap = section_cap if section_cap is not None else available_gti
    statutory = min(raw_interest, cap)
    allowed = min(user_claim, statutory, available_gti)
    remaining = allowed
    rows: list[LoanDeductionComputedRow] = []
    for index, entry in enumerate(positive_entries):
        if index == len(positive_entries) - 1:
            row_interest = remaining
        else:
            row_interest = (
                entry.interest_paid / raw_interest * allowed
            ).quantize(Decimal("1"))
            row_interest = min(row_interest, remaining)
            remaining -= row_interest
        rows.append(LoanDeductionComputedRow(
            source=entry,
            gross_interest=entry.interest_paid,
            eligible_interest=max(_ZERO, row_interest),
        ))

    return LoanDeductionResult(
        user_claim=user_claim,
        gross_interest=raw_interest,
        statutory_eligible=statutory,
        allowed_deduction=allowed,
        rows=tuple(rows),
    )
