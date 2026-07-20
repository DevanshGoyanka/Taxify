"""
Schedule TDS3: TDS on Rent (Deductor Side).

When an individual/HUF paying rent exceeding ₹50,000 per month is required
to deduct TDS under Section 194-IB (now Section 194M in some cases).

This schedule captures TDS details from the taxpayer's perspective as a
DEDUCTOR (not deductee). The TDS deposited is claimed as a credit.

For ITR-4 filers: this is relevant when the assessee deducts TDS on
property rent payments and needs to report it.
"""

from decimal import Decimal
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class TdsPropertyEntry:
    tenant_pan: str = ""
    tenant_name: str = ""
    property_address: str = ""
    rent_paid: Decimal = Decimal("0")
    tds_deducted: Decimal = Decimal("0")
    tds_deposited: Decimal = Decimal("0")
    challan_serial_no: str = ""
    bsr_code: str = ""
    deposit_date: str = ""


@dataclass
class TdsPropertyResult:
    entries: list = field(default_factory=list)
    total_rent: Decimal = Decimal("0")
    total_tds: Decimal = Decimal("0")


def compute(entries: Optional[list[TdsPropertyEntry]] = None) -> TdsPropertyResult:
    if not entries:
        return TdsPropertyResult()

    total_rent = sum(e.rent_paid for e in entries)
    total_tds = sum(e.tds_deposited for e in entries)

    return TdsPropertyResult(
        entries=entries,
        total_rent=total_rent,
        total_tds=total_tds,
    )
