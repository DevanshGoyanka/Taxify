"""
Section 10AA — SEZ Unit Deduction.

Deduction for newly established units in Special Economic Zones (SEZs).

Key rules:
  - First 5 years: 100% of export profits.
  - Next 5 years: 50% of export profits.
  - Next 5 years: 50% of export profits, subject to amount credited
    to SEZ Re-Investment Reserve Account (max 50%).

Conditions:
  - Unit must begin manufacture/production of articles/things or
    provide services on or after 01-04-2005.
  - Separate books of account.
  - Audit report (Form 56F) required.

ITR forms: ITR-3 only.
"""

from decimal import Decimal
from typing import Optional
from app.schemas.itr1 import Chapter6ADeductions, TaxRegime


def compute(ded: Optional[Chapter6ADeductions], regime: TaxRegime) -> Decimal:
    if not ded or regime == TaxRegime.NEW:
        return Decimal("0")
    return ded.amount_80g
