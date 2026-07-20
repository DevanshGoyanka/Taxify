"""
Section 80EEA — Interest on Affordable Housing Loan.

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

from decimal import Decimal
from typing import Optional
from app.schemas.itr1 import Chapter6ADeductions, TaxRegime
from app.engine.constants import SECTION_80EEA_LIMIT


def compute(ded: Optional[Chapter6ADeductions], regime: TaxRegime) -> Decimal:
    if not ded or regime == TaxRegime.NEW:
        return Decimal("0")
    return min(ded.amount_80eea, SECTION_80EEA_LIMIT)
