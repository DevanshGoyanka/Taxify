"""Section 80E — Interest on Education Loan.

Deduction for interest paid on education loan for higher studies.
  - For self, spouse, children, or student for whom assessee is legal guardian.
  - No upper ceiling on the amount.
  - Allowed for up to 8 assessment years starting from the year repayment begins.
  - Only interest component, not principal.
  - Loan must be from approved financial institution / charitable institution.

Not available under the new regime (Section 115BAC).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from app.engine.schedules.deductions._loan_common import (
    LoanDeductionResult,
    allocate_loan_deduction,
)
from app.schemas.itr1 import (
    Chapter6ADeductions,
    OfficialDeductionLoanEntry,
    Schedule80EEntry,
    TaxRegime,
)

_ZERO = Decimal("0")


def compute_details(
    ded: Optional[Chapter6ADeductions],
    entries: Optional[list[Schedule80EEntry]],
    available_gti: Decimal,
    regime: TaxRegime,
) -> LoanDeductionResult:
    """Compute Section 80E from official education-loan rows.

    Args:
        ded: Chapter VI-A deductions carrying amount_80e.
        entries: Official Schedule 80E loan rows with interest_paid.
        available_gti: Remaining GTI available to this section.
        regime: Tax regime — new regime disallows 80E.

    Returns:
        A typed result with per-row allocated eligibility.
    """
    user_claim = ded.amount_80e if ded else _ZERO
    if ded is None or regime == TaxRegime.NEW or user_claim <= _ZERO:
        return LoanDeductionResult(user_claim=user_claim)
    return allocate_loan_deduction(user_claim, entries, available_gti)


def compute(
    ded: Optional[Chapter6ADeductions],
    regime: TaxRegime,
) -> Decimal:
    """Return the allowed Section 80E deduction for scalar callers."""
    if not ded or regime == TaxRegime.NEW:
        return _ZERO
    return ded.amount_80e
