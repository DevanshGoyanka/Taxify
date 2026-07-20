"""
Section 80EEB — Interest on Electric Vehicle Loan.

Deduction for interest on loan taken for purchase of an electric vehicle.

Conditions (Finance Act 2019):
  - Loan sanctioned between 01-04-2019 and 31-03-2023.
  - Loan from a financial institution for purchase of an EV for personal use.
  - Maximum: ₹1,50,000.
  - This is the total deduction available over the loan tenure (not per year),
    but the Act does not specify apportionment; the engine caps per-year claims
    at the statutory limit.

Not available under the new regime (Section 115BAC).
"""

from decimal import Decimal
from typing import Optional
from app.schemas.itr1 import Chapter6ADeductions, TaxRegime
from app.engine.constants import SECTION_80EEB_LIMIT


def compute(ded: Optional[Chapter6ADeductions], regime: TaxRegime) -> Decimal:
    if not ded or regime == TaxRegime.NEW:
        return Decimal("0")
    return min(ded.amount_80eeb, SECTION_80EEB_LIMIT)
