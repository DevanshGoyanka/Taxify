"""
Section 80-IB — Industrial Undertaking Deduction.

Deduction for profits from:
  - Industrial undertakings in industrially backward districts
  - Small-scale industries
  - Housing projects
  - Hotels in specified areas
  - Multiplex theatres
  - Convention centres
  - Hospitals in rural areas

Conditions vary by sub-section. Generally:
  - Separate books of account must be maintained.
  - Audit report (Form 10CCB) required.
  - Deduction is a % of profits for a specified number of years.

ITR forms: ITR-3 only.
"""

from decimal import Decimal
from typing import Optional
from app.schemas.itr1 import Chapter6ADeductions, TaxRegime


def compute(ded: Optional[Chapter6ADeductions], regime: TaxRegime) -> Decimal:
    if not ded or regime == TaxRegime.NEW:
        return Decimal("0")
    return ded.amount_80g
