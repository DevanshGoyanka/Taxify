"""
Section 80U — Person with Disability.

Deduction for an individual who is a person with disability and
has not claimed deduction under Section 80DD for the same individual.

  - Disability (40%+): ₹75,000 (flat deduction)
  - Severe disability (80%+): ₹1,25,000

Not available under the new regime (Section 115BAC).
"""

from decimal import Decimal
from typing import Optional
from app.schemas.itr1 import Chapter6ADeductions, TaxRegime
from app.engine.constants import SECTION_80U_LIMIT, SECTION_80U_SEVERE_LIMIT


def compute(ded: Optional[Chapter6ADeductions], regime: TaxRegime, is_severe: bool = False) -> Decimal:
    if not ded or regime == TaxRegime.NEW:
        return Decimal("0")
    cap = SECTION_80U_SEVERE_LIMIT if is_severe else SECTION_80U_LIMIT
    return min(ded.amount_80u, cap)
