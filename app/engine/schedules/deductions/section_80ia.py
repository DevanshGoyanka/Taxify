"""
Section 80-IA — Infrastructure Development Deduction.

Deduction for profits from:
  - Infrastructure facility (road, bridge, rail, port, airport, etc.)
  - Telecommunication services
  - Industrial park / SEZ development
  - Power generation, transmission, distribution

Key rules:
  - 100% of profits for first 10 consecutive assessment years
    (out of initial 15/20 years, depending on the project type).
  - Separate books of account must be maintained.
  - Audit report (Form 10CCB) mandatory.

ITR forms: ITR-3 only (business/profession income required).
"""

from decimal import Decimal
from typing import Optional
from app.schemas.itr1 import Chapter6ADeductions, TaxRegime


def compute(ded: Optional[Chapter6ADeductions], regime: TaxRegime) -> Decimal:
    if not ded or regime == TaxRegime.NEW:
        return Decimal("0")
    return ded.amount_80g
