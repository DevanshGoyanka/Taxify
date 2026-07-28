"""
Section 80CCH — Agniveer Corpus Fund.

Deduction for contributions to the Agniveer Corpus Fund (Agneepath Scheme).
Section 80CCH has NO statutory rupee ceiling — the full contribution amount
is deductible.

Allowed in BOTH old and new regimes (Section 115BAC).
"""

from decimal import Decimal
from typing import Optional
from app.schemas.itr1 import Chapter6ADeductions, TaxRegime


def compute(ded: Optional[Chapter6ADeductions], regime: TaxRegime) -> Decimal:
    if not ded:
        return Decimal("0")
    return ded.amount_80cch  # No statutory cap — full contribution deductible
