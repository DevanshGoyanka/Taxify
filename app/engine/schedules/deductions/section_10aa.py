"""
Section 10AA — Deduction for SEZ Units.

Deduction for profits derived from export of articles/things or
services by a unit located in a Special Economic Zone (SEZ).

Conditions:
  - 100% of export profits for first 5 years.
  - 50% of export profits for next 5 years.
  - Not available after 15 years from commencement.
  - Available under old regime only.
  - Triggers AMT u/s 115JC.

ITR forms: ITR-3 only.
"""

from decimal import Decimal
from typing import Optional
from app.schemas.itr1 import Chapter6ADeductions, TaxRegime


def compute(ded: Optional[Chapter6ADeductions], regime: TaxRegime) -> Decimal:
    """Return the 10AA deduction amount."""
    if not ded or regime == TaxRegime.NEW:
        return Decimal("0")
    return ded.amount_10aa
