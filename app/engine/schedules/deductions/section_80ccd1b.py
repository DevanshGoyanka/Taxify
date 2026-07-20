"""
Section 80CCD(1B) — Additional NPS Contribution.

Over and above the ₹1,50,000 combined limit of 80C+80CCC+80CCD(1).
Maximum deduction: ₹50,000.

Not available under the new regime (Section 115BAC).
"""

from decimal import Decimal
from typing import Optional
from app.schemas.itr1 import Chapter6ADeductions, TaxRegime
from app.engine.constants import SECTION_80CCD1B_LIMIT


def compute(ded: Optional[Chapter6ADeductions], regime: TaxRegime) -> Decimal:
    if not ded or regime == TaxRegime.NEW:
        return Decimal("0")
    return min(ded.amount_80ccd1b, SECTION_80CCD1B_LIMIT)
