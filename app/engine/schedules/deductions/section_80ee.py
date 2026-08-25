"""Section 80EE — Interest on Home Loan for First-Time Buyers.

Deduction for interest on loan taken for acquisition of a residential
house property by a first-time individual home buyer.

Conditions:
  - Loan sanctioned between 01-04-2016 and 31-03-2017 (FY 2016-17).
  - Loan amount <= ₹35 lakh; property value <= ₹50 lakh.
  - Assessee should not own any other residential house property on the
    date of loan sanction.
  - Maximum deduction: ₹50,000 per year.
  - This deduction is over and above Section 24(b) interest deduction.

Not available under the new regime (Section 115BAC).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from app.engine.constants import SECTION_80EE_LIMIT
from app.engine.schedules.deductions._loan_common import (
    LoanDeductionResult,
    allocate_loan_deduction,
)
from app.schemas.itr1 import (
    Chapter6ADeductions,
    ITR1Schedule80EELoanEntry,
    TaxRegime,
)

_ZERO = Decimal("0")


def compute_details(
    ded: Optional[Chapter6ADeductions],
    entries: Optional[list[ITR1Schedule80EELoanEntry]],
    available_gti: Decimal,
    regime: TaxRegime,
) -> LoanDeductionResult:
    """Compute Section 80EE from official home-loan rows.

    Args:
        ded: Chapter VI-A deductions carrying amount_80ee.
        entries: Official Schedule 80EE loan rows with interest_paid.
        available_gti: Remaining GTI available to this section.
        regime: Tax regime — new regime disallows 80EE.

    Returns:
        A typed result with per-row allocated eligibility capped at ₹50,000.
    """
    user_claim = ded.amount_80ee if ded else _ZERO
    if ded is None or regime == TaxRegime.NEW or user_claim <= _ZERO:
        return LoanDeductionResult(user_claim=user_claim)
    return allocate_loan_deduction(
        user_claim, entries, available_gti, section_cap=SECTION_80EE_LIMIT,
    )


def compute(
    ded: Optional[Chapter6ADeductions],
    regime: TaxRegime,
) -> Decimal:
    """Return the allowed Section 80EE deduction for scalar callers."""
    if not ded or regime == TaxRegime.NEW:
        return _ZERO
    return min(ded.amount_80ee, SECTION_80EE_LIMIT)
