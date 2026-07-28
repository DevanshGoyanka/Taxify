"""
Section 80-IB — Deduction for Industrial Undertakings.

Deduction for profits derived by an industrial undertaking from:
  - Small-scale / ancillary industrial undertakings.
  - Hotels in specified locations.
  - Multiplex theatres / convention centres.
  - Housing projects (affordable housing, etc.).
  - Cold chain facilities, warehousing for agricultural produce.
  - Hospitals in rural areas (100+ beds).
  - Other notified industrial undertakings.

Conditions:
  - Deduction ranges from 25% to 100% of qualifying profits depending
    on the category and year of claim.
  - Cannot overlap with 80-IA / 80-IC for the same profits.
  - Available under old regime only.
  - Triggers AMT u/s 115JC.

ITR forms: ITR-3 only.
"""

from decimal import Decimal
from typing import Optional
from app.schemas.itr1 import Chapter6ADeductions, TaxRegime


def compute(ded: Optional[Chapter6ADeductions], regime: TaxRegime) -> Decimal:
    """Return the 80-IB deduction amount.

    The caller (business schedule) computes the qualifying profit; this
    module returns the claimed amount from the schema.

    Old regime only.
    """
    if not ded or regime == TaxRegime.NEW:
        return Decimal("0")
    return ded.amount_80ib
