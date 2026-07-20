"""
Section 80G — Donations to Charitable Institutions and Funds.

Deduction in respect of donations to certain funds, charitable institutions, etc.

Four categories of donations:
  1. 100% without limit: PMNRF, PM CARES, National Defence Fund, etc.
  2. 50% without limit: Jawaharlal Nehru Memorial Fund, PM Drought Relief, etc.
  3. 100% subject to 10% of adjusted GTI: Govt/local authority for family planning,
     notified institutions for specific purposes.
  4. 50% subject to 10% of adjusted GTI: Other charitable trusts/institutions
     approved under Section 80G(5).

Cash donation cap: ₹2,000 per donation entry (Section 80G(5D)).

adjusted_gti = GTI minus all other Chapter VI-A deductions (except 80G/80GG).

Not available under the new regime (Section 115BAC).
"""

from decimal import Decimal
from typing import Optional
from app.schemas.itr1 import Chapter6ADeductions, TaxRegime, Donation80G
from app.engine.constants import SECTION_80G_CASH_LIMIT


def compute(ded: Optional[Chapter6ADeductions], adjusted_gti: Decimal, regime: TaxRegime) -> Decimal:
    if not ded or regime == TaxRegime.NEW:
        return Decimal("0")

    total = Decimal("0")
    donations = getattr(ded, "donations_80g", None) or []

    for d in donations:
        if not isinstance(d, Donation80G):
            continue

        cash_amt = min(d.cash_amount, SECTION_80G_CASH_LIMIT)
        non_cash_amt = d.non_cash_amount
        total_donation = cash_amt + non_cash_amt

        if total_donation <= 0:
            continue

        pct = d.qualifying_percentage
        factor = Decimal("1") if pct == "100%" else Decimal("0.5")
        qualifying_amount = total_donation * factor

        limit_on_ded = (d.limit_on_deduction or "").lower()
        if limit_on_ded == "with limit":
            total += min(qualifying_amount, adjusted_gti * Decimal("0.10"))
        else:
            total += qualifying_amount

    # Fallback: scalar field when donations_80g list is empty
    if not donations:
        total = min(ded.amount_80g, adjusted_gti)

    return total
