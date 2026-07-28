"""
Schedule CYLA: Current Year Loss Adjustment.

Under the IT Act (Sections 70-71), current-year losses from one head of
income can be set off against income from another head.

Set-off rules (Section 70, 71):
  - Loss from HP (Section 24): can be set off against any income.
    Self-occupied loss capped at Rs 2,00,000 (Section 24(b)).
  - Loss from Business (Non-speculative): can be set off against any income
    EXCEPT salary (Section 71(2A), Section 72(2)).
  - Loss from Speculative Business: can only be set off against speculative
    business income (Section 73(2)).
  - STCG loss: can be set off against STCG or LTCG (Section 74(1)(a)).
  - LTCG loss: can be set off only against LTCG (Section 74(1)(b)).
  - Loss from Other Sources: cannot be set off against any income
    (Section 74A, w.e.f. AY 2024-25).

ITR forms: ITR-2, ITR-3 only. ITR-1/4 do not permit loss set-off.
"""

from decimal import Decimal
from dataclasses import dataclass, field


@dataclass
class CylaLossEntry:
    head: str = ""
    sub_category: str = ""
    loss_amount: Decimal = Decimal("0")
    set_off_amount: Decimal = Decimal("0")
    remaining_loss: Decimal = Decimal("0")


@dataclass
class CYLAInput:
    # Income heads the loss can be set off against
    non_salary_income: Decimal = Decimal("0")   # GTI - salary - spec_biz
    hp_loss: Decimal = Decimal("0")             # negative = loss
    stcg_loss: Decimal = Decimal("0")           # negative = loss
    ltcg_loss: Decimal = Decimal("0")           # negative = loss
    non_spec_biz_loss: Decimal = Decimal("0")   # negative = loss
    spec_biz_loss: Decimal = Decimal("0")       # negative = loss
    # Income available to absorb the losses
    hp_income: Decimal = Decimal("0")
    stcg_income: Decimal = Decimal("0")
    ltcg_income: Decimal = Decimal("0")
    non_spec_biz_income: Decimal = Decimal("0")
    spec_biz_income: Decimal = Decimal("0")


@dataclass
class CYLAResult:
    entries: list = field(default_factory=list)
    total_loss_set_off: Decimal = Decimal("0")
    total_loss_remaining: Decimal = Decimal("0")
    # Breakout per head for downstream GTI adjustment
    hp_setoff: Decimal = Decimal("0")
    stcg_setoff: Decimal = Decimal("0")
    ltcg_setoff: Decimal = Decimal("0")
    non_spec_biz_setoff: Decimal = Decimal("0")
    spec_biz_setoff: Decimal = Decimal("0")


def compute(cy: CYLAInput) -> CYLAResult:
    """Apply current-year loss set-off per Sections 70-74A."""

    entries = []
    total_set_off = Decimal("0")
    total_remaining = Decimal("0")

    # --- HP loss: set off against any income (capped at 2L for self-occupied) ---
    hp_loss_val = abs(cy.hp_loss) if cy.hp_loss < 0 else Decimal("0")
    # Cap by (a) ₹2,00,000 statutory u/s 71(3A) AND (b) total positive income available
    # HP loss can be set off against ANY head of income (salary, business, OS, CG).
    # non_salary_income is populated by callers with salary_income + os_income.
    available_income = max(Decimal("0"),
        cy.non_salary_income + cy.hp_income + cy.stcg_income + cy.ltcg_income
        + cy.non_spec_biz_income + cy.spec_biz_income)
    hp_setoff = min(hp_loss_val, Decimal("200000"), available_income)
    hp_remaining = hp_loss_val - hp_setoff
    if hp_loss_val > 0:
        entries.append(CylaLossEntry(
            head="HP", sub_category="HouseProperty",
            loss_amount=hp_loss_val,
            set_off_amount=hp_setoff,
            remaining_loss=hp_remaining,
        ))
        total_set_off += hp_setoff
        total_remaining += hp_remaining

    # --- STCG loss: set off against STCG + LTCG ---
    stcg_loss_val = abs(cy.stcg_loss) if cy.stcg_loss < 0 else Decimal("0")
    stcg_setoff = max(Decimal("0"), min(stcg_loss_val, cy.stcg_income + cy.ltcg_income))
    stcg_remaining = stcg_loss_val - stcg_setoff
    if stcg_loss_val > 0:
        entries.append(CylaLossEntry(
            head="STCG", sub_category="STCG",
            loss_amount=stcg_loss_val,
            set_off_amount=stcg_setoff,
            remaining_loss=stcg_remaining,
        ))
        total_set_off += stcg_setoff
        total_remaining += stcg_remaining

    # --- LTCG loss: set off only against LTCG ---
    ltcg_loss_val = abs(cy.ltcg_loss) if cy.ltcg_loss < 0 else Decimal("0")
    ltcg_setoff = min(ltcg_loss_val, cy.ltcg_income)
    ltcg_remaining = ltcg_loss_val - ltcg_setoff
    if ltcg_loss_val > 0:
        entries.append(CylaLossEntry(
            head="LTCG", sub_category="LTCG",
            loss_amount=ltcg_loss_val,
            set_off_amount=ltcg_setoff,
            remaining_loss=ltcg_remaining,
        ))
        total_set_off += ltcg_setoff
        total_remaining += ltcg_remaining

    # --- Non-speculative biz loss: set off against any non-salary, non-spec-biz income ---
    nsb_loss_val = abs(cy.non_spec_biz_loss) if cy.non_spec_biz_loss < 0 else Decimal("0")
    eligible_income = cy.hp_income + cy.stcg_income + cy.ltcg_income + cy.spec_biz_income
    nsb_setoff = min(nsb_loss_val, eligible_income)
    nsb_remaining = nsb_loss_val - nsb_setoff
    if nsb_loss_val > 0:
        entries.append(CylaLossEntry(
            head="BUS", sub_category="NonSpeculative",
            loss_amount=nsb_loss_val,
            set_off_amount=nsb_setoff,
            remaining_loss=nsb_remaining,
        ))
        total_set_off += nsb_setoff
        total_remaining += nsb_remaining

    # --- Speculative biz loss: set off only against speculative income ---
    sb_loss_val = abs(cy.spec_biz_loss) if cy.spec_biz_loss < 0 else Decimal("0")
    sb_setoff = min(sb_loss_val, cy.spec_biz_income)
    sb_remaining = sb_loss_val - sb_setoff
    if sb_loss_val > 0:
        entries.append(CylaLossEntry(
            head="BUS", sub_category="Speculative",
            loss_amount=sb_loss_val,
            set_off_amount=sb_setoff,
            remaining_loss=sb_remaining,
        ))
        total_set_off += sb_setoff
        total_remaining += sb_remaining

    return CYLAResult(
        entries=entries,
        total_loss_set_off=total_set_off,
        total_loss_remaining=total_remaining,
        hp_setoff=hp_setoff,
        stcg_setoff=stcg_setoff,
        ltcg_setoff=ltcg_setoff,
        non_spec_biz_setoff=nsb_setoff,
        spec_biz_setoff=sb_setoff,
    )
