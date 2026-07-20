"""
Schedule BFLA: Brought Forward Loss Adjustment (Section 72-74).

Carried-forward losses set off against current-year income per IT Act rules.

Carry-forward periods:
  - HP loss: 8 years; set off against HP income only.
  - Non-speculative business: 8 years; set off against business income only.
  - Speculative business: 4 years; set off against speculative business only.
  - STCG: 8 years; set off against STCG + LTCG.
  - LTCG: 8 years; set off against LTCG only.
  - Unabsorbed depreciation (u/s 32): indefinite; any income except salary.

ITR forms: ITR-2, ITR-3 only.
"""

from decimal import Decimal
from dataclasses import dataclass, field
from datetime import date


def _ay_to_fiscal_year_end(ay_str: str) -> int:
    """Convert 'AY 2026-27' or '2026-27' to integer fiscal year (2026)."""
    s = ay_str.replace("AY", "").replace(" ", "").strip()
    return int(s.split("-")[0])


@dataclass
class BFLossEntry:
    assessment_year: str = ""
    head: str = ""
    sub_category: str = ""
    original_loss: Decimal = Decimal("0")
    brought_forward: Decimal = Decimal("0")
    set_off_this_year: Decimal = Decimal("0")
    remaining_carry_forward: Decimal = Decimal("0")


@dataclass
class BFLAInput:
    hp_income: Decimal = Decimal("0")
    non_spec_biz_income: Decimal = Decimal("0")
    spec_biz_income: Decimal = Decimal("0")
    stcg_income: Decimal = Decimal("0")
    ltcg_income: Decimal = Decimal("0")
    bf_losses: list = field(default_factory=list)      # list[dict] from schema
    current_ay: str = "2026-27"


@dataclass
class BFLAResult:
    entries: list = field(default_factory=list)
    total_bf_loss_set_off: Decimal = Decimal("0")
    total_bf_remaining: Decimal = Decimal("0")
    hp_setoff: Decimal = Decimal("0")
    biz_setoff: Decimal = Decimal("0")
    cg_setoff: Decimal = Decimal("0")


_MAX_CARRY_FWD: dict[str, int] = {
    "HP": 8,
    "NonSpeculative": 8,
    "Speculative": 4,
    "STCG": 8,
    "LTCG": 8,
}


def compute(bf: BFLAInput) -> BFLAResult:
    """Apply brought-forward loss set-off."""
    entries = []
    total_set_off = Decimal("0")
    total_remaining = Decimal("0")
    hp_setoff = Decimal("0")
    biz_setoff = Decimal("0")
    cg_setoff = Decimal("0")

    current_fy = _ay_to_fiscal_year_end(bf.current_ay)

    for item in bf.bf_losses:
        head = item.get("head", "") if isinstance(item, dict) else getattr(item, "head", "")
        amount = abs(Decimal(str(item.get("brought_forward", 0)))) if isinstance(item, dict) else abs(getattr(item, "brought_forward", Decimal("0")))
        ay_str = item.get("assessment_year", "") if isinstance(item, dict) else getattr(item, "assessment_year", "")

        loss_fy = _ay_to_fiscal_year_end(ay_str) if ay_str else 0
        max_years = _MAX_CARRY_FWD.get(head, 8)
        if loss_fy and (current_fy - loss_fy) > max_years:
            remaining = amount
            total_remaining += remaining
            entries.append(BFLossEntry(
                assessment_year=ay_str, head=head, sub_category="EXPIRED",
                original_loss=amount, brought_forward=amount,
            ))
            continue

        if head == "HP":
            set_off = min(amount, bf.hp_income)
            hp_setoff += set_off
        elif head == "NonSpeculative":
            set_off = min(amount, bf.non_spec_biz_income)
            biz_setoff += set_off
        elif head == "Speculative":
            set_off = min(amount, bf.spec_biz_income)
            biz_setoff += set_off
        elif head == "STCG":
            set_off = min(amount, bf.stcg_income + bf.ltcg_income)
            cg_setoff += set_off
        elif head == "LTCG":
            set_off = min(amount, bf.ltcg_income)
            cg_setoff += set_off
        else:
            set_off = Decimal("0")

        remaining = amount - set_off
        entries.append(BFLossEntry(
            assessment_year=ay_str, head=head,
            sub_category=item.get("sub_category", "") if isinstance(item, dict) else getattr(item, "sub_category", ""),
            original_loss=abs(Decimal(str(item.get("original_loss", 0)))) if isinstance(item, dict) else abs(getattr(item, "original_loss", Decimal("0"))),
            brought_forward=amount,
            set_off_this_year=set_off,
            remaining_carry_forward=remaining,
        ))
        total_set_off += set_off
        total_remaining += remaining

    return BFLAResult(
        entries=entries,
        total_bf_loss_set_off=total_set_off,
        total_bf_remaining=total_remaining,
        hp_setoff=hp_setoff,
        biz_setoff=biz_setoff,
        cg_setoff=cg_setoff,
    )
