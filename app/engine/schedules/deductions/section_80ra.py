"""
Section 80QQB / 80RA — Royalty Income of Authors.

Deduction for royalty income earned by authors of books (other than textbooks).
  - Maximum: ₹3,00,000 (u/s 80QQB).
  - Deduction is the lower of royalty received or ₹3,00,000.

Section 80RRB — Royalty on Patents.
  - Maximum: ₹3,00,000.
  - Patent must be registered under Patents Act, 1970.

Placeholder: These are modelled as simple capped deductions;
the actual book/patent verification is a validation-layer concern.

ITR forms: ITR-3 only (business/profession).
"""

from decimal import Decimal
from typing import Optional
from app.schemas.itr1 import Chapter6ADeductions, TaxRegime


def compute(ded: Optional[Chapter6ADeductions], regime: TaxRegime) -> Decimal:
    if not ded or regime == TaxRegime.NEW:
        return Decimal("0")
    return ded.amount_80g
