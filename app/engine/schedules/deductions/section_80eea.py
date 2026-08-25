"""Section 80EEA — Interest on Affordable Housing Loan.

Deduction for interest on loan taken for acquisition of an affordable
residential house property.

Conditions (Finance Act 2019):
  - Loan sanctioned between 01-04-2019 and 31-03-2022.
  - Stamp duty value of property <= ₹45 lakh.
  - Assessee should not own any other residential house property on the
    date of loan sanction.
  - Assessee is not eligible for deduction under Section 80EE.
  - Maximum: ₹1,50,000 per year.
  - This deduction is over and above Section 24(b) interest deduction.

Not available under the new regime (Section 115BAC).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from app.engine.constants import SECTION_80EEA_LIMIT
from app.engine.schedules.deductions._loan_common import (
    LoanDeductionResult,
    allocate_loan_deduction,
)
from app.schemas.itr1 import (
    Chapter6ADeductions,
    ITR1Schedule80EEALoanEntry,
    TaxRegime,
)

_ZERO = Decimal("0")


def compute_details(
    ded: Optional[Chapter6ADeductions],
    entries: Optional[list[ITR1Schedule80EEALoanEntry]],
    available_gti: Decimal,
    regime: TaxRegime,
) -> LoanDeductionResult:
    """Compute Section 80EEA from official affordable-housing-loan rows.

    Args:
        ded: Chapter VI-A deductions carrying amount_80eea.
        entries: Official Schedule 80EEA loan rows with interest_paid.
        available_gti: Remaining GTI available to this section.
        regime: Tax regime — new regime disallows 80EEA.

    Returns:
        A typed result with per-row allocated eligibility capped at ₹1,50,000.
    """
    user_claim = ded.amount_80eea if ded else _ZERO
    if ded is None or regime == TaxRegime.NEW or user_claim <= _ZERO:
        return LoanDeductionResult(user_claim=user_claim)
    return allocate_loan_deduction(
        user_claim, entries, available_gti, section_cap=SECTION_80EEA_LIMIT,
    )


def compute(
    ded: Optional[Chapter6ADeductions],
    regime: TaxRegime,
) -> Decimal:
    """Return the allowed Section 80EEA deduction for scalar callers."""
    if not ded or regime == TaxRegime.NEW:
        return _ZERO
    return min(ded.amount_80eea, SECTION_80EEA_LIMIT)
