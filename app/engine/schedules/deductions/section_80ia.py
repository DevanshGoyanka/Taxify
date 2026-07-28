"""
Section 80-IA — Deduction for Infrastructure Development.

Deduction for profits and gains derived by an undertaking from:
  - Infrastructure facility (road, bridge, port, airport, rail, water,
    sanitation, power generation/transmission/distribution).
  - Telecom services.
  - Industrial parks / SEZ development.
  - Cross-country natural gas / crude oil pipeline.

Conditions:
  - 100% of qualifying profits for 10 consecutive assessment years.
  - Cannot be claimed alongside 80-IB / 80-IC for the same profits.
  - Available under old regime only.
  - Triggers AMT u/s 115JC when total income exceeds Rs 20,00,000.

ITR forms: ITR-3 only.
"""

from decimal import Decimal
from typing import Optional
from app.schemas.itr1 import Chapter6ADeductions, TaxRegime


def compute(ded: Optional[Chapter6ADeductions], regime: TaxRegime) -> Decimal:
    """Return the 80-IA deduction amount.

    The deduction is 100% of qualifying infrastructure profits with no
    rupee cap per AY.  The caller (business schedule) computes the
    qualifying profit; this module simply returns the claimed amount
    from the schema.

    Old regime only.  AMT may apply post-cess (handled by calculator).
    """
    if not ded or regime == TaxRegime.NEW:
        return Decimal("0")
    return ded.amount_80ia
