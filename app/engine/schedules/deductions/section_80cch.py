"""
Section 80CCH — Agniveer Corpus Fund.

Deduction for contributions to the Agniveer Corpus Fund (Agneepath Scheme).
Maximum: ₹2,88,000 (FY 2024-25 onwards).

Allowed in BOTH old and new regimes (Section 115BAC).
"""

from decimal import Decimal
from typing import Optional
from app.schemas.itr1 import Chapter6ADeductions, TaxRegime
from app.engine.constants import SECTION_80CCH_LIMIT


def compute(ded: Optional[Chapter6ADeductions], regime: TaxRegime) -> Decimal:
    if not ded:
        return Decimal("0")
    return min(ded.amount_80cch, SECTION_80CCH_LIMIT)
