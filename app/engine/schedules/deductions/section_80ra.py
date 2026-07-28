"""
Section 80RA — Deduction for Patent / Royalty Income.

Deduction for any income by way of royalty in respect of a patent
registered under the Patents Act, 1970.

Conditions:
  - 100% of royalty income is deductible.
  - Patent must be registered under Patents Act, 1970.
  - Available to resident individuals only.
  - Available under old regime only.
  - Triggers AMT u/s 115JC.

ITR forms: ITR-3 only.
"""

from decimal import Decimal
from typing import Optional
from app.schemas.itr1 import Chapter6ADeductions, TaxRegime


def compute(ded: Optional[Chapter6ADeductions], regime: TaxRegime) -> Decimal:
    """Return the 80RA deduction amount."""
    if not ded or regime == TaxRegime.NEW:
        return Decimal("0")
    return ded.amount_80ra
