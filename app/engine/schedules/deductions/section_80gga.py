"""
Section 80GGA — Donations for Scientific Research / Rural Development.

Deduction for donations to:
  - Approved scientific research associations (u/s 35(1)(ii))
  - Approved universities/colleges for research (u/s 35(1)(iii))
  - Approved rural development programmes
  - Approved conservation of natural resources

Conditions:
  - 100% of donation amount is deductible.
  - No upper limit.
  - NOT allowed if the assessee has business income (ITR-2 only).
  - Cash donations NOT allowed (Section 80GGA(2A)).

ITR forms: ITR-2 (applicable for non-business assessees).
"""

from decimal import Decimal
from typing import Optional
from app.schemas.itr1 import Chapter6ADeductions, TaxRegime


def compute(ded: Optional[Chapter6ADeductions], regime: TaxRegime) -> Decimal:
    if not ded or regime == TaxRegime.NEW:
        return Decimal("0")
    return ded.amount_80g
