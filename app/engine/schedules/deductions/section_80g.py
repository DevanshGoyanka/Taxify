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

    without_limit = Decimal("0")
    limited_100 = Decimal("0")
    limited_50 = Decimal("0")
    donations = getattr(ded, "donations_80g", None) or []

    for d in donations:
        if not isinstance(d, Donation80G):
            continue

        cash_amt = d.cash_amount if d.cash_amount <= SECTION_80G_CASH_LIMIT else Decimal("0")
        total_donation = cash_amt + d.non_cash_amount
        if total_donation <= 0:
            continue

        is_full_rate = d.qualifying_percentage == "100%"
        is_limited = (d.limit_on_deduction or "").lower() == "with limit"
        if not is_limited:
            without_limit += total_donation if is_full_rate else total_donation * Decimal("0.5")
        elif is_full_rate:
            limited_100 += total_donation
        else:
            limited_50 += total_donation

    # The 10% adjusted-GTI ceiling is shared by all limited categories. Apply
    # it first to 100%-qualifying donations, then to 50%-qualifying donations.
    common_limit = adjusted_gti * Decimal("0.10")
    allowed_limited_100 = min(limited_100, common_limit)
    remaining_limit = max(Decimal("0"), common_limit - allowed_limited_100)
    allowed_limited_50 = min(limited_50, remaining_limit) * Decimal("0.5")
    total = without_limit + allowed_limited_100 + allowed_limited_50

    # Fallback: scalar field when donations_80g list is empty
    if not donations:
        total = min(ded.amount_80g, adjusted_gti)

    return min(total, adjusted_gti)
