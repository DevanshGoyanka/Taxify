"""Section 80EEB — Interest on Electric Vehicle Loan.

Deduction for interest on loan taken for purchase of an electric vehicle.

Conditions (Finance Act 2019):
  - Loan sanctioned between 01-04-2019 and 31-03-2023.
  - Loan from a financial institution for purchase of an EV for personal use.
  - Maximum: ₹1,50,000.
  - This is the total deduction available over the loan tenure (not per year),
    but the Act does not specify apportionment; the engine caps per-year claims
    at the statutory limit.

Not available under the new regime (Section 115BAC).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from app.engine.constants import SECTION_80EEB_LIMIT
from app.engine.schedules.deductions._loan_common import (
    LoanDeductionResult,
    allocate_loan_deduction,
)
from app.schemas.itr1 import (
    Chapter6ADeductions,
    ITR1Schedule80EEBLoanEntry,
    TaxRegime,
)

_ZERO = Decimal("0")


def compute_details(
    ded: Optional[Chapter6ADeductions],
    entries: Optional[list[ITR1Schedule80EEBLoanEntry]],
    available_gti: Decimal,
    regime: TaxRegime,
) -> LoanDeductionResult:
    """Compute Section 80EEB from official electric-vehicle-loan rows.

    Args:
        ded: Chapter VI-A deductions carrying amount_80eeb.
        entries: Official Schedule 80EEB loan rows with interest_paid and
            vehicle registration number.
        available_gti: Remaining GTI available to this section.
        regime: Tax regime — new regime disallows 80EEB.

    Returns:
        A typed result with per-row allocated eligibility capped at ₹1,50,000.
    """
    user_claim = ded.amount_80eeb if ded else _ZERO
    if ded is None or regime == TaxRegime.NEW or user_claim <= _ZERO:
        return LoanDeductionResult(user_claim=user_claim)
    return allocate_loan_deduction(
        user_claim, entries, available_gti, section_cap=SECTION_80EEB_LIMIT,
    )


def compute(
    ded: Optional[Chapter6ADeductions],
    regime: TaxRegime,
) -> Decimal:
    """Return the allowed Section 80EEB deduction for scalar callers."""
    if not ded or regime == TaxRegime.NEW:
        return _ZERO
    return min(ded.amount_80eeb, SECTION_80EEB_LIMIT)
