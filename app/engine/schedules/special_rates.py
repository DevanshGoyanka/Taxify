"""
Schedule SI: Income Chargeable at Special Rates.

Certain incomes are taxed at special/flat rates regardless of the slab
structure. These are taken OUT of normal income and taxed separately.

Section-wise special rate incomes:
  111A   — STCG on listed equity (STT paid): 15%/20%
  112    — LTCG other than 112A: 20% (with indexation) / 12.5% (w/o indexation)
  112A   — LTCG on listed equity (STT paid): 10%/12.5% (> ₹1.25L exemption)
  115BB  — Lottery, crossword, gambling: 30%
  115BBE — Unexplained cash credits/money: 60% (no deduction, no set-off)
  115BBF — Royalty on patents (resident): 10%
  115BBG — Transfer of carbon credits: 10%
  115BBH — Virtual Digital Assets (crypto): 30%
  115BBI — Offshore fund interest: 5%
  115BBJ — REIT/InvIT dividend: slab-rate (not special)

No deduction under Chapter VI-A is allowed against these incomes.
No set-off of losses against these incomes (except 111A/112A).

ITR-1: Limited to 112A only.
ITR-2/3/4: Full SI schedule.
"""

from decimal import Decimal
from enum import Enum
from typing import Optional
from dataclasses import dataclass, field
from app.engine.constants import (
    STCG_111A_RATE_PRE_JUL23,
    STCG_111A_RATE_POST_JUL23,
    LTCG_112A_RATE,
    LTCG_112A_RATE_POST_JUL23,
    LTCG_112A_EXEMPTION,
    LTCG_OTHER_RATE,
    LTCG_OTHER_RATE_POST_JUL23,
    LOTTERY_RATE,
    VDA_RATE,
    UNEXPLAINED_INCOME_RATE,
)


class SpecialRateSection(str, Enum):
    S111A = "111A"
    S112 = "112"
    S112A = "112A"
    S115BB = "115BB"
    S115BBE = "115BBE"
    S115BBF = "115BBF"
    S115BBG = "115BBG"
    S115BBH = "115BBH"


@dataclass
class SpecialRateEntry:
    section: str = ""
    description: str = ""
    gross_income: Decimal = Decimal("0")
    deductions: Decimal = Decimal("0")
    net_income: Decimal = Decimal("0")
    tax_rate_pct: Decimal = Decimal("0")
    tax_amount: Decimal = Decimal("0")
    exemption_available: Decimal = Decimal("0")
    taxable_income: Decimal = Decimal("0")


@dataclass
class SpecialRatesResult:
    entries: list = field(default_factory=list)
    total_special_rate_income: Decimal = Decimal("0")
    total_special_rate_tax: Decimal = Decimal("0")


def compute_112a(ltcg_112a: Decimal, cost_of_acquisition: Decimal = Decimal("0")) -> SpecialRateEntry:
    """Compute LTCG u/s 112A with ₹1.25 lakh exemption."""
    net = max(Decimal("0"), ltcg_112a - cost_of_acquisition)
    exemption = min(net, LTCG_112A_EXEMPTION)
    taxable = max(Decimal("0"), net - exemption)
    tax = taxable * LTCG_112A_RATE_POST_JUL23 / Decimal("100")

    return SpecialRateEntry(
        section="112A",
        description="LTCG on listed equity (STT paid)",
        gross_income=ltcg_112a,
        deductions=cost_of_acquisition,
        net_income=net,
        tax_rate_pct=LTCG_112A_RATE_POST_JUL23,
        tax_amount=tax,
        exemption_available=exemption,
        taxable_income=taxable,
    )


def compute_111a(stcg_111a: Decimal, is_post_jul23: bool = True) -> SpecialRateEntry:
    """Compute STCG u/s 111A."""
    rate = STCG_111A_RATE_POST_JUL23 if is_post_jul23 else STCG_111A_RATE_PRE_JUL23
    tax = stcg_111a * rate / Decimal("100")

    return SpecialRateEntry(
        section="111A",
        description="STCG on listed equity (STT paid)",
        gross_income=stcg_111a,
        net_income=stcg_111a,
        tax_rate_pct=rate,
        tax_amount=tax,
        taxable_income=stcg_111a,
    )


def compute_lottery(lottery_income: Decimal) -> SpecialRateEntry:
    """Compute tax on lottery/gambling u/s 115BB."""
    return SpecialRateEntry(
        section="115BB",
        description="Lottery / Gambling / Crossword",
        gross_income=lottery_income,
        net_income=lottery_income,
        tax_rate_pct=LOTTERY_RATE,
        tax_amount=lottery_income * LOTTERY_RATE / Decimal("100"),
        taxable_income=lottery_income,
    )


def compute_vda(vda_income: Decimal) -> SpecialRateEntry:
    """Compute tax on Virtual Digital Assets u/s 115BBH."""
    return SpecialRateEntry(
        section="115BBH",
        description="Virtual Digital Assets (Crypto)",
        gross_income=vda_income,
        net_income=vda_income,
        tax_rate_pct=VDA_RATE,
        tax_amount=vda_income * VDA_RATE / Decimal("100"),
        taxable_income=vda_income,
    )


def compute_115bbe(unexplained_income: Decimal) -> SpecialRateEntry:
    """Compute tax on unexplained income u/s 115BBE. No deductions allowed."""
    return SpecialRateEntry(
        section="115BBE",
        description="Unexplained cash credits / investments",
        gross_income=unexplained_income,
        net_income=unexplained_income,
        tax_rate_pct=UNEXPLAINED_INCOME_RATE,
        tax_amount=unexplained_income * UNEXPLAINED_INCOME_RATE / Decimal("100"),
        taxable_income=unexplained_income,
    )


def compute_115bbf(patent_royalty: Decimal) -> SpecialRateEntry:
    """Compute tax on patent royalty u/s 115BBF (10%)."""
    return SpecialRateEntry(
        section="115BBF",
        description="Royalty on patents (resident)",
        gross_income=patent_royalty,
        net_income=patent_royalty,
        tax_rate_pct=Decimal("10"),
        tax_amount=patent_royalty * Decimal("10") / Decimal("100"),
        taxable_income=patent_royalty,
    )


def aggregate(entries: list[SpecialRateEntry]) -> SpecialRatesResult:
    """Aggregate special rate entries into total."""
    return SpecialRatesResult(
        entries=entries,
        total_special_rate_income=sum(e.taxable_income for e in entries),
        total_special_rate_tax=sum(e.tax_amount for e in entries),
    )
