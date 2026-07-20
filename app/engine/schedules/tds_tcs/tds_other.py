"""
Schedule TDS2: TDS on Income Other Than Salary.

TDS deducted on:
  - Interest (bank FD, RD, bonds) — Section 194A
  - Rent — Section 194I
  - Professional/technical fees — Section 194J
  - Commission/brokerage — Section 194H
  - Contract payments — Section 194C
  - Dividend — Section 194
  - Capital gains — Section 194-IA (immovable property)
  - Lottery/crossword — Section 194B
  - And 50+ other TDS sections

Each entry must match with 26AS data for ITD validation.
"""

from decimal import Decimal
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class TdsOtherEntry:
    deductor_tan: str = ""
    deductor_name: str = ""
    tds_section: str = ""  # e.g., "194A", "194I", "194H"
    gross_amount: Decimal = Decimal("0")
    tds_deducted: Decimal = Decimal("0")
    tds_certificate_no: str = ""
    matched_with_26as: bool = False


@dataclass
class TdsOtherResult:
    entries: list = field(default_factory=list)
    total_tds: Decimal = Decimal("0")
    matched_tds: Decimal = Decimal("0")
    unmatched_tds: Decimal = Decimal("0")


def compute(entries: Optional[list[TdsOtherEntry]] = None) -> TdsOtherResult:
    if not entries:
        return TdsOtherResult()

    total = sum(e.tds_deducted for e in entries)
    matched = sum(e.tds_deducted for e in entries if e.matched_with_26as)
    unmatched = total - matched

    return TdsOtherResult(
        entries=entries,
        total_tds=total,
        matched_tds=matched,
        unmatched_tds=unmatched,
    )
