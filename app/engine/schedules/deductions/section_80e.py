"""
Section 80E — Interest on Education Loan.

Deduction for interest paid on education loan for higher studies.
  - For self, spouse, children, or student for whom assessee is legal guardian.
  - No upper ceiling on the amount.
  - Allowed for up to 8 assessment years starting from the year repayment begins.
  - Only interest component, not principal.
  - Loan must be from approved financial institution / charitable institution.

Not available under the new regime (Section 115BAC).
"""

from decimal import Decimal
from typing import Optional
from app.schemas.itr1 import Chapter6ADeductions, TaxRegime


def compute(ded: Optional[Chapter6ADeductions], regime: TaxRegime) -> Decimal:
    if not ded or regime == TaxRegime.NEW:
        return Decimal("0")
    return ded.amount_80e
