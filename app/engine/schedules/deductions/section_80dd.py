"""
Section 80DD — Medical Treatment of Dependent with Disability.

Deduction for expenditure on medical treatment, training, and rehabilitation
of a dependent with disability.

  - Disability (40%+): ₹75,000 (flat deduction, no proof of actual spend)
  - Severe disability (80%+): ₹1,25,000

Not available under the new regime (Section 115BAC).
"""

from decimal import Decimal
from typing import Optional
from app.schemas.itr1 import Chapter6ADeductions, TaxRegime
from app.engine.constants import SECTION_80DD_LIMIT, SECTION_80DD_SEVERE_LIMIT


def compute(ded: Optional[Chapter6ADeductions], regime: TaxRegime, is_severe: bool = False) -> Decimal:
    if not ded or regime == TaxRegime.NEW:
        return Decimal("0")
    cap = SECTION_80DD_SEVERE_LIMIT if is_severe else SECTION_80DD_LIMIT
    return min(ded.amount_80dd, cap)
