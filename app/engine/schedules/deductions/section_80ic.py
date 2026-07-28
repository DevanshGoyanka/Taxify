"""
Section 80-IC — Deduction for Special Category States.

Deduction for profits from industrial undertakings located in:
  - Sikkim, Himachal Pradesh, Uttarakhand, North-Eastern states.

Conditions:
  - 100% of profits for first 5 years; 25% (non-corporate) or 30%
    (company) for next 5 years.
  - Available only if undertaking commenced on/after specified dates.
  - Available under old regime only.
  - Triggers AMT u/s 115JC.

ITR forms: ITR-3 only.
"""

from decimal import Decimal
from typing import Optional
from app.schemas.itr1 import Chapter6ADeductions, TaxRegime


def compute(ded: Optional[Chapter6ADeductions], regime: TaxRegime) -> Decimal:
    """Return the 80-IC deduction amount."""
    if not ded or regime == TaxRegime.NEW:
        return Decimal("0")
    return ded.amount_80ic
