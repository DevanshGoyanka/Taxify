"""
Section 80GGC — Contributions to Political Parties.

Deduction for contributions made by an individual (not a company or
artificial juridical person) to:
  - A political party registered under Section 29A of the
    Representation of the People Act, 1951.
  - An electoral trust.

Conditions:
  - 100% of contribution is deductible.
  - No upper limit.
  - Payment must be by any mode other than cash.

ITR forms: ITR-2 (applicable for non-business assessees).
"""

from decimal import Decimal
from typing import Optional
from app.schemas.itr1 import Chapter6ADeductions, TaxRegime


def compute(ded: Optional[Chapter6ADeductions], regime: TaxRegime) -> Decimal:
    if not ded or regime == TaxRegime.NEW:
        return Decimal("0")
    return ded.amount_80ggc
