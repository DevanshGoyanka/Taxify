"""
Section 80CCD(2) — Employer NPS Contribution.

Employer's contribution to NPS (Central/State Govt or other employer).
No upper limit. Allowed in BOTH old and new regimes (Section 115BAC).

For government employees: up to 14% of salary (salary = basic + DA).
For other employees: up to 10% of salary.
"""

from decimal import Decimal
from typing import Optional
from app.schemas.itr1 import Chapter6ADeductions, TaxRegime


def compute(ded: Optional[Chapter6ADeductions], regime: TaxRegime) -> Decimal:
    if not ded:
        return Decimal("0")
    return ded.amount_80ccd2
