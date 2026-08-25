"""Brought-forward loss adjustment under sections 72 through 74.

Implements the statutory brought-forward loss set-off with six CG
sub-baskets matching the official ITR-2 Schedule BFLA schema.
"""

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

_ZERO = Decimal("0")
_MAX_CARRY_FWD: dict[str, int] = {"HP": 8, "NonSpeculative": 8, "Speculative": 4, "STCG": 8, "LTCG": 8}


def _ay_start(assessment_year: str) -> int:
    """Parse the starting year from an assessment-year label."""
    cleaned = assessment_year.upper().replace("AY", "").replace(" ", "")
    if not cleaned:
        return 0
    try:
        return int(cleaned.split("-")[0])
    except (TypeError, ValueError):
        return 0


def _amount(value: Any) -> Decimal:
    """Coerce any value into a nonnegative Decimal."""
    try:
        return abs(Decimal(str(value)))
    except (InvalidOperation, TypeError, ValueError):
        return _ZERO


def _field(item: object, name: str, default: Any = "") -> Any:
    """Get a field from a dict or dataclass-like object."""
    return item.get(name, default) if isinstance(item, dict) else getattr(item, name, default)


@dataclass
class BFLossEntry:
    """One brought-forward loss and its current-year disposition."""

    assessment_year: str = ""
    head: str = ""
    sub_category: str = ""
    original_loss: Decimal = _ZERO
    brought_forward: Decimal = _ZERO
    set_off_this_year: Decimal = _ZERO
    remaining_carry_forward: Decimal = _ZERO


@dataclass
class BFLAInput:
    """Post-CYLA income pools and brought-forward losses.

    CG sub-basket incomes are the post-CYLA residual amounts split across
    six statutory rate baskets.
    """

    hp_income: Decimal = _ZERO
    non_spec_biz_income: Decimal = _ZERO
    spec_biz_income: Decimal = _ZERO
    stcg20_income: Decimal = _ZERO
    stcg30_income: Decimal = _ZERO
    stcg_app_income: Decimal = _ZERO
    stcg_dtaa_income: Decimal = _ZERO
    ltcg125_income: Decimal = _ZERO
    ltcg_dtaa_income: Decimal = _ZERO
    bf_losses: list[object] = field(default_factory=list)
    current_ay: str = "2026-27"


@dataclass
class BFLAResult:
    """Brought-forward set-offs, still-valid carry-forward losses, and
    per-basket residual incomes for the JSON builder."""

    entries: list[BFLossEntry] = field(default_factory=list)
    total_bf_loss_set_off: Decimal = _ZERO
    total_bf_remaining: Decimal = _ZERO
    hp_setoff: Decimal = _ZERO
    biz_setoff: Decimal = _ZERO
    cg_setoff: Decimal = _ZERO
    # Per-basket residual income after BFLA (for builder)
    stcg20_remaining: Decimal = _ZERO
    stcg30_remaining: Decimal = _ZERO
    stcg_app_remaining: Decimal = _ZERO
    stcg_dtaa_remaining: Decimal = _ZERO
    ltcg125_remaining: Decimal = _ZERO
    ltcg_dtaa_remaining: Decimal = _ZERO


def compute(bf: BFLAInput) -> BFLAResult:
    """Set off oldest valid brought-forward losses against post-CYLA pools.

    Args:
        bf: Current post-CYLA incomes, losses, and assessment year.

    Returns:
        Entries including expired markers; expired amounts are not presented as
        carry-forward balances. Per-basket residual incomes are populated.
    """
    hp_pool = max(_ZERO, bf.hp_income)
    nsb_pool = max(_ZERO, bf.non_spec_biz_income)
    spec_pool = max(_ZERO, bf.spec_biz_income)
    stcg20_pool = max(_ZERO, bf.stcg20_income)
    stcg30_pool = max(_ZERO, bf.stcg30_income)
    stcg_app_pool = max(_ZERO, bf.stcg_app_income)
    stcg_dtaa_pool = max(_ZERO, bf.stcg_dtaa_income)
    ltcg125_pool = max(_ZERO, bf.ltcg125_income)
    ltcg_dtaa_pool = max(_ZERO, bf.ltcg_dtaa_income)
    current_year = _ay_start(bf.current_ay)
    indexed = list(enumerate(bf.bf_losses or []))
    indexed.sort(key=lambda pair: (_ay_start(str(_field(pair[1], "assessment_year", ""))) or 9999, pair[0]))

    entries: list[BFLossEntry] = []
    hp_setoff = biz_setoff = cg_setoff = _ZERO
    total_setoff = total_remaining = _ZERO

    for _, item in indexed:
        head = str(_field(item, "head", ""))
        ay = str(_field(item, "assessment_year", ""))
        subcategory = str(_field(item, "sub_category", ""))
        brought = _amount(_field(item, "brought_forward", _ZERO))
        original = _amount(_field(item, "original_loss", brought))
        loss_year = _ay_start(ay)
        limit = _MAX_CARRY_FWD.get(head)
        expired = limit is not None and loss_year > 0 and current_year > 0 and current_year - loss_year > limit
        if expired:
            entries.append(BFLossEntry(ay, head, "EXPIRED", original, brought, _ZERO, _ZERO))
            continue

        setoff = _ZERO
        if head == "HP":
            setoff = min(brought, hp_pool)
            hp_pool -= setoff
            hp_setoff += setoff
        elif head == "NonSpeculative":
            setoff = min(brought, nsb_pool)
            nsb_pool -= setoff
            biz_setoff += setoff
        elif head == "Speculative":
            setoff = min(brought, spec_pool)
            spec_pool -= setoff
            biz_setoff += setoff
        elif head == "STCG":
            # STCG BF loss absorbs STCG baskets first, then LTCG baskets
            cg_pools = [stcg20_pool, stcg30_pool, stcg_app_pool, stcg_dtaa_pool, ltcg125_pool, ltcg_dtaa_pool]
            remaining_bf = brought
            for i in range(len(cg_pools)):
                used = min(remaining_bf, cg_pools[i])
                cg_pools[i] -= used
                remaining_bf -= used
                setoff += used
                if remaining_bf <= _ZERO:
                    break
            stcg20_pool, stcg30_pool, stcg_app_pool, stcg_dtaa_pool, ltcg125_pool, ltcg_dtaa_pool = cg_pools
            cg_setoff += setoff
        elif head == "LTCG":
            # LTCG BF loss absorbs LTCG baskets only
            ltcg_pools = [ltcg125_pool, ltcg_dtaa_pool]
            remaining_bf = brought
            for i in range(len(ltcg_pools)):
                used = min(remaining_bf, ltcg_pools[i])
                ltcg_pools[i] -= used
                remaining_bf -= used
                setoff += used
                if remaining_bf <= _ZERO:
                    break
            ltcg125_pool, ltcg_dtaa_pool = ltcg_pools
            cg_setoff += setoff

        remaining = brought - setoff
        entries.append(BFLossEntry(ay, head, subcategory, original, brought, setoff, remaining))
        total_setoff += setoff
        total_remaining += remaining

    return BFLAResult(
        entries=entries,
        total_bf_loss_set_off=total_setoff,
        total_bf_remaining=total_remaining,
        hp_setoff=hp_setoff,
        biz_setoff=biz_setoff,
        cg_setoff=cg_setoff,
        stcg20_remaining=stcg20_pool,
        stcg30_remaining=stcg30_pool,
        stcg_app_remaining=stcg_app_pool,
        stcg_dtaa_remaining=stcg_dtaa_pool,
        ltcg125_remaining=ltcg125_pool,
        ltcg_dtaa_remaining=ltcg_dtaa_pool,
    )
