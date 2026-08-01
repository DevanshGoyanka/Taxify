"""
Section 80C + 80CCC + 80CCD(1) — Combined ₹1,50,000 pool (u/s 80CCE).

Covers:
  - 80C: LIC, PPF, EPF, ELSS, NSC, tuition fees, home loan principal, etc.
  - 80CCC: Annuity plan premiums (LIC/other insurers)
  - 80CCD(1): Employee contribution to NPS

These three sections share a combined ceiling of ₹1,50,000 as per Section 80CCE.
"""

from decimal import Decimal
from typing import Optional
from app.schemas.itr1 import Chapter6ADeductions, TaxRegime
from app.engine.constants import SECTION_80C_LIMIT


def compute(ded: Optional[Chapter6ADeductions], regime: TaxRegime) -> Decimal:
    if not ded or regime == TaxRegime.NEW:
        return Decimal("0")
    raw = ded.amount_80c + ded.amount_80ccc + ded.amount_80ccd1
    return min(raw, SECTION_80C_LIMIT)


def _capped_component(
    component: Decimal,
    ded: Optional[Chapter6ADeductions],
    regime: TaxRegime,
) -> Decimal:
    """Return one component's proportional share of the Section 80CCE cap."""
    if not ded or regime == TaxRegime.NEW:
        return Decimal("0")
    raw_total = ded.amount_80c + ded.amount_80ccc + ded.amount_80ccd1
    if raw_total == 0:
        return Decimal("0")
    capped = min(raw_total, SECTION_80C_LIMIT)
    return min(component, component / raw_total * capped)


def compute_80ccc(ded: Optional[Chapter6ADeductions], regime: TaxRegime) -> Decimal:
    """Return the 80CCC portion after applying the shared 80CCE cap."""
    return _capped_component(ded.amount_80ccc if ded else Decimal("0"), ded, regime)


def compute_80ccd1(ded: Optional[Chapter6ADeductions], regime: TaxRegime) -> Decimal:
    """Return the 80CCD(1) portion after applying the shared 80CCE cap."""
    return _capped_component(ded.amount_80ccd1 if ded else Decimal("0"), ded, regime)
