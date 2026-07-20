"""
Schedule TCS: Tax Collected at Source.

TCS is collected by specified sellers (e.g., car dealers, jewellers, timber
sellers, foreign remittance agents) from buyers and deposited with the
government. The buyer can claim the TCS as a credit in their ITR.

TCS provisions applicable to individuals:
  - Section 206C(1H): Sale of goods > ₹50 lakh (0.1% TCS)
  - Section 206C(1G): Foreign remittance / overseas tour package
    - LRS remittance > ₹7 lakh: 20% (education/medical: 5% if loan)
  - Section 206CCA: Higher TCS for non-filers of ITR
  - Section 206C(1F): Sale of motor vehicle > ₹10 lakh (1% TCS)

TCS can only be claimed as credit if matched with 26AS.
"""

from decimal import Decimal
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class TcsEntry:
    collector_tan: str = ""
    collector_name: str = ""
    tcs_section: str = ""  # e.g., "206C(1G)", "206C(1H)"
    gross_amount: Decimal = Decimal("0")
    tcs_collected: Decimal = Decimal("0")
    matched_with_26as: bool = False


@dataclass
class TcsResult:
    entries: list = field(default_factory=list)
    total_tcs: Decimal = Decimal("0")
    matched_tcs: Decimal = Decimal("0")
    unmatched_tcs: Decimal = Decimal("0")


def compute(entries: Optional[list[TcsEntry]] = None) -> TcsResult:
    if not entries:
        return TcsResult()

    total = sum(e.tcs_collected for e in entries)
    matched = sum(e.tcs_collected for e in entries if e.matched_with_26as)
    unmatched = total - matched

    return TcsResult(
        entries=entries,
        total_tcs=total,
        matched_tcs=matched,
        unmatched_tcs=unmatched,
    )
