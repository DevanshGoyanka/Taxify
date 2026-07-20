"""
Section 80EE — Interest on Home Loan for First-Time Buyers.

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

from decimal import Decimal
from typing import Optional
from app.schemas.itr1 import Chapter6ADeductions, TaxRegime
from app.engine.constants import SECTION_80EE_LIMIT


def compute(ded: Optional[Chapter6ADeductions], regime: TaxRegime) -> Decimal:
    if not ded or regime == TaxRegime.NEW:
        return Decimal("0")
    return min(ded.amount_80ee, SECTION_80EE_LIMIT)
