"""Current-year loss adjustment under sections 70 and 71.

Implements the statutory intra-head and inter-head set-off order with
six CG sub-baskets matching the official ITR-2 Schedule CYLA schema:

  - STCG20Per  (section 111A, 20% rate)
  - STCG30Per  (section 112 at 30%/other normal-rate STCG)
  - STCGAppRate (applicable-rate STCG)
  - STCGDTAARate (DTAA-rate STCG)
  - LTCG12_5Per (section 112/112A at 12.5%)
  - LTCGDTAARate (DTAA-rate LTCG)
"""

from dataclasses import dataclass, field
from decimal import Decimal

_ZERO = Decimal("0")


@dataclass
class CylaLossEntry:
    """One current-year loss adjustment entry."""

    head: str = ""
    sub_category: str = ""
    loss_amount: Decimal = _ZERO
    set_off_amount: Decimal = _ZERO
    remaining_loss: Decimal = _ZERO


@dataclass
class CylaIncomeBasket:
    """Per-basket income remaining after intra-head CG set-off.

    Maps to the official Schedule CYLA IncCYLA sub-structure for each
    capital-gain rate basket.
    """

    inc_of_cur_yr: Decimal = _ZERO
    hp_loss_setoff: Decimal = _ZERO
    oth_src_loss_setoff: Decimal = _ZERO
    inc_of_cur_yr_after_setoff: Decimal = _ZERO


@dataclass
class CYLAInput:
    """Income and loss pools available for current-year adjustment.

    CG sub-basket incomes are passed as signed values (negative = loss).
    Non-CG losses (HP, business) are passed as positive loss magnitudes.
    """

    non_salary_income: Decimal = _ZERO
    hp_loss: Decimal = _ZERO
    stcg20_income: Decimal = _ZERO
    stcg30_income: Decimal = _ZERO
    stcg_app_income: Decimal = _ZERO
    stcg_dtaa_income: Decimal = _ZERO
    ltcg125_income: Decimal = _ZERO
    ltcg_dtaa_income: Decimal = _ZERO
    non_spec_biz_loss: Decimal = _ZERO
    spec_biz_loss: Decimal = _ZERO
    hp_income: Decimal = _ZERO
    non_spec_biz_income: Decimal = _ZERO
    spec_biz_income: Decimal = _ZERO


@dataclass
class CYLAResult:
    """Current-year set-off amounts and unabsorbed losses.

    Per-basket fields populate the six official CG sub-basket structures.
    """

    entries: list[CylaLossEntry] = field(default_factory=list)
    total_loss_set_off: Decimal = _ZERO
    total_loss_remaining: Decimal = _ZERO
    hp_setoff: Decimal = _ZERO
    stcg20_setoff: Decimal = _ZERO
    stcg30_setoff: Decimal = _ZERO
    stcg_app_setoff: Decimal = _ZERO
    stcg_dtaa_setoff: Decimal = _ZERO
    ltcg125_setoff: Decimal = _ZERO
    ltcg_dtaa_setoff: Decimal = _ZERO
    non_spec_biz_setoff: Decimal = _ZERO
    spec_biz_setoff: Decimal = _ZERO
    # Per-basket residual income after CG loss set-off (for builder)
    stcg20_remaining: Decimal = _ZERO
    stcg30_remaining: Decimal = _ZERO
    stcg_app_remaining: Decimal = _ZERO
    stcg_dtaa_remaining: Decimal = _ZERO
    ltcg125_remaining: Decimal = _ZERO
    ltcg_dtaa_remaining: Decimal = _ZERO
    # Section-70 intra-Schedule-CG set-off detail (current-year capital
    # losses against current-year capital gains ONLY -- distinct from this
    # same function's own later section-71 cross-head absorption of
    # business/HP losses into the same CG pools, and computed as a
    # snapshot taken before that later step runs). Matches the official
    # ITR-2 form's own Schedule CG "Table E" (item E), keyed by the same
    # six bucket names used above (without the "stcg_"/"ltcg_" income/
    # setoff/remaining suffixes): stcg20, stcg30, stcg_app, stcg_dtaa,
    # ltcg125, ltcg_dtaa.
    cg_gross_income: dict = field(default_factory=dict)
    cg_gross_loss: dict = field(default_factory=dict)
    # (source_bucket, target_bucket) -> amount of `source`'s current-year
    # loss set off against `target`'s current-year gain.
    cg_setoff_matrix: dict = field(default_factory=dict)
    # Per-TARGET-bucket gain remaining after intra-head set-off only (i.e.
    # before section-71 cross-head absorption runs) -- Table E's own
    # "CurrYrCapGain" per row.
    cg_intra_head_remaining: dict = field(default_factory=dict)
    # Per-SOURCE-bucket totals -- Table E's "TotLossSetOff"/"LossRemainSetOff".
    cg_source_setoff_total: dict = field(default_factory=dict)
    cg_source_loss_remaining: dict = field(default_factory=dict)


def _positive(value: Decimal) -> Decimal:
    """Return the nonnegative portion of a value."""
    return max(_ZERO, value)


def _loss(value: Decimal) -> Decimal:
    """Return the magnitude of a negative value, else zero."""
    return max(_ZERO, -value)


def compute(cy: CYLAInput) -> CYLAResult:
    """Apply current-year losses sequentially to nonnegative income pools.

    Capital losses are adjusted intra-head first (STCL before LTCL). Business
    and house-property adjustments then see only income left in their eligible
    pools, preventing the same income from absorbing multiple losses.

    The six CG sub-baskets are tracked individually so the builder can
    populate every official Schedule CYLA row.

    Args:
        cy: Current-year income and loss pools.

    Returns:
        Ordered loss adjustments, remaining positive loss magnitudes, and
        per-basket residual incomes.
    """
    hp_pool = _positive(cy.hp_income)
    stcg20_pool = _positive(cy.stcg20_income)
    stcg30_pool = _positive(cy.stcg30_income)
    stcg_app_pool = _positive(cy.stcg_app_income)
    stcg_dtaa_pool = _positive(cy.stcg_dtaa_income)
    ltcg125_pool = _positive(cy.ltcg125_income)
    ltcg_dtaa_pool = _positive(cy.ltcg_dtaa_income)
    nsb_pool = _positive(cy.non_spec_biz_income)
    spec_pool = _positive(cy.spec_biz_income)
    other_pool = _positive(cy.non_salary_income)
    entries: list[CylaLossEntry] = []

    def record(head: str, sub_category: str, amount: Decimal, setoff: Decimal) -> None:
        """Append a CYLA entry when the loss is nonzero."""
        if amount > _ZERO:
            entries.append(CylaLossEntry(head, sub_category, amount, setoff, amount - setoff))

    # Intra-head CG loss set-off (section 70): each STCL sub-basket absorbs
    # other STCG buckets, then LTCG buckets; each LTCL sub-basket absorbs
    # LTCG buckets only. A bucket's own gain/loss are mutually exclusive by
    # construction (max(0, x) and max(0, -x) can never both be nonzero), so
    # there is no "self-setoff" case -- every absorption is into a
    # different bucket. Tracked here as a full source-bucket x
    # target-bucket matrix (not just aggregate totals) because the
    # official form's own Schedule CG "Table E" (`CurrYrLosses`) discloses
    # exactly this detail, per bucket pair. When more than one loss
    # sub-basket is nonzero at once, sources are processed in the same
    # fixed bucket order as targets below -- a deterministic convention
    # this engine must pick somewhere, since neither the buckets' own sign
    # nor the statute dictates which specific loss source gets priority
    # access to shared target capacity when it's insufficient for all
    # sources (mirrors the FIFO convention already used for AMT credit
    # utilization). This waterfall is associative in the AGGREGATE: the
    # final remaining amount in each TARGET bucket is the same regardless
    # of source-processing order (only the per-source attribution differs),
    # so this refactor changes no existing aggregate/remaining value below.
    _STCG_ORDER = ("stcg20", "stcg30", "stcg_app", "stcg_dtaa")
    _LTCG_ORDER = ("ltcg125", "ltcg_dtaa")
    cg_income_raw = {
        "stcg20": cy.stcg20_income, "stcg30": cy.stcg30_income,
        "stcg_app": cy.stcg_app_income, "stcg_dtaa": cy.stcg_dtaa_income,
        "ltcg125": cy.ltcg125_income, "ltcg_dtaa": cy.ltcg_dtaa_income,
    }
    cg_gross_income = {name: _positive(value) for name, value in cg_income_raw.items()}
    cg_gross_loss = {name: _loss(value) for name, value in cg_income_raw.items()}
    cg_pool = dict(cg_gross_income)
    cg_setoff_matrix: dict = {}

    def _absorb_cg(source: str, targets: tuple) -> None:
        remaining = cg_gross_loss[source]
        if remaining <= _ZERO:
            return
        for target in targets:
            if target == source:
                continue
            used = min(remaining, cg_pool[target])
            if used > _ZERO:
                cg_pool[target] -= used
                cg_setoff_matrix[(source, target)] = used
                remaining -= used
            if remaining <= _ZERO:
                break

    for source in _STCG_ORDER:
        _absorb_cg(source, _STCG_ORDER + _LTCG_ORDER)
    for source in _LTCG_ORDER:
        _absorb_cg(source, _LTCG_ORDER)

    cg_intra_head_remaining = dict(cg_pool)
    cg_source_setoff_total = {
        source: sum((amt for (src, _tgt), amt in cg_setoff_matrix.items() if src == source), _ZERO)
        for source in _STCG_ORDER + _LTCG_ORDER
    }
    cg_source_loss_remaining = {
        source: cg_gross_loss[source] - cg_source_setoff_total[source]
        for source in _STCG_ORDER + _LTCG_ORDER
    }

    stcg20_pool, stcg30_pool, stcg_app_pool, stcg_dtaa_pool = (
        cg_pool["stcg20"], cg_pool["stcg30"], cg_pool["stcg_app"], cg_pool["stcg_dtaa"]
    )
    ltcg125_pool, ltcg_dtaa_pool = cg_pool["ltcg125"], cg_pool["ltcg_dtaa"]

    stcg_loss_total = cg_gross_loss["stcg20"] + cg_gross_loss["stcg30"] + cg_gross_loss["stcg_app"] + cg_gross_loss["stcg_dtaa"]
    total_stcg_setoff = sum((cg_source_setoff_total[s] for s in _STCG_ORDER), _ZERO)
    # Record aggregate STCG entry; per-basket breakdown is available via result fields
    if stcg_loss_total > _ZERO:
        record("STCG", "STCG", stcg_loss_total, total_stcg_setoff)

    ltcl_total = cg_gross_loss["ltcg125"] + cg_gross_loss["ltcg_dtaa"]
    total_ltcg_setoff = sum((cg_source_setoff_total[s] for s in _LTCG_ORDER), _ZERO)
    if ltcl_total > _ZERO:
        record("LTCG", "LTCG", ltcl_total, total_ltcg_setoff)

    # Speculative business loss
    spec_loss = _loss(cy.spec_biz_loss)
    spec_setoff = min(spec_loss, spec_pool)
    spec_pool -= spec_setoff
    record("BUS", "Speculative", spec_loss, spec_setoff)

    # Non-speculative business loss — absorbs nsb, then hp, stcg, ltcg, other
    nsb_loss = _loss(cy.non_spec_biz_loss)
    nsb_setoff = _ZERO
    cg_pools = [stcg20_pool, stcg30_pool, stcg_app_pool, stcg_dtaa_pool, ltcg125_pool, ltcg_dtaa_pool]
    for pool_name in ("nsb", "hp", "cg", "other"):
        if pool_name == "cg":
            for i in range(len(cg_pools)):
                used = min(nsb_loss - nsb_setoff, cg_pools[i])
                cg_pools[i] -= used
                nsb_setoff += used
        else:
            pool = {"nsb": nsb_pool, "hp": hp_pool, "other": other_pool}[pool_name]
            used = min(nsb_loss - nsb_setoff, pool)
            nsb_setoff += used
            if pool_name == "nsb":
                nsb_pool -= used
            elif pool_name == "hp":
                hp_pool -= used
            else:
                other_pool -= used
    stcg20_pool, stcg30_pool, stcg_app_pool, stcg_dtaa_pool, ltcg125_pool, ltcg_dtaa_pool = cg_pools
    record("BUS", "NonSpeculative", nsb_loss, nsb_setoff)

    # HP loss — capped at ₹2L for inter-head set-off
    hp_loss = _loss(cy.hp_loss)
    hp_eligible = min(hp_loss, Decimal("200000"))
    hp_setoff = _ZERO
    for pool_name in ("other", "nsb", "spec", "cg"):
        if pool_name == "cg":
            for i in range(len(cg_pools)):
                used = min(hp_eligible - hp_setoff, cg_pools[i])
                cg_pools[i] -= used
                hp_setoff += used
        else:
            pool = {"other": other_pool, "nsb": nsb_pool, "spec": spec_pool}[pool_name]
            used = min(hp_eligible - hp_setoff, pool)
            hp_setoff += used
            if pool_name == "other":
                other_pool -= used
            elif pool_name == "nsb":
                nsb_pool -= used
            else:
                spec_pool -= used
    stcg20_pool, stcg30_pool, stcg_app_pool, stcg_dtaa_pool, ltcg125_pool, ltcg_dtaa_pool = cg_pools
    record("HP", "HouseProperty", hp_loss, hp_setoff)

    total_setoff = hp_setoff + total_stcg_setoff + total_ltcg_setoff + nsb_setoff + spec_setoff
    total_remaining = sum((entry.remaining_loss for entry in entries), _ZERO)

    # Compute per-basket setoff (original income - remaining)
    stcg20_setoff = _positive(cy.stcg20_income) - stcg20_pool if cy.stcg20_income > _ZERO else _ZERO
    stcg30_setoff = _positive(cy.stcg30_income) - stcg30_pool if cy.stcg30_income > _ZERO else _ZERO
    stcg_app_setoff = _positive(cy.stcg_app_income) - stcg_app_pool if cy.stcg_app_income > _ZERO else _ZERO
    stcg_dtaa_setoff = _positive(cy.stcg_dtaa_income) - stcg_dtaa_pool if cy.stcg_dtaa_income > _ZERO else _ZERO
    ltcg125_setoff = _positive(cy.ltcg125_income) - ltcg125_pool if cy.ltcg125_income > _ZERO else _ZERO
    ltcg_dtaa_setoff = _positive(cy.ltcg_dtaa_income) - ltcg_dtaa_pool if cy.ltcg_dtaa_income > _ZERO else _ZERO

    return CYLAResult(
        entries=entries,
        total_loss_set_off=total_setoff,
        total_loss_remaining=total_remaining,
        hp_setoff=hp_setoff,
        stcg20_setoff=stcg20_setoff,
        stcg30_setoff=stcg30_setoff,
        stcg_app_setoff=stcg_app_setoff,
        stcg_dtaa_setoff=stcg_dtaa_setoff,
        ltcg125_setoff=ltcg125_setoff,
        ltcg_dtaa_setoff=ltcg_dtaa_setoff,
        non_spec_biz_setoff=nsb_setoff,
        spec_biz_setoff=spec_setoff,
        stcg20_remaining=stcg20_pool,
        stcg30_remaining=stcg30_pool,
        stcg_app_remaining=stcg_app_pool,
        stcg_dtaa_remaining=stcg_dtaa_pool,
        ltcg125_remaining=ltcg125_pool,
        ltcg_dtaa_remaining=ltcg_dtaa_pool,
        cg_gross_income=cg_gross_income,
        cg_gross_loss=cg_gross_loss,
        cg_setoff_matrix=cg_setoff_matrix,
        cg_intra_head_remaining=cg_intra_head_remaining,
        cg_source_setoff_total=cg_source_setoff_total,
        cg_source_loss_remaining=cg_source_loss_remaining,
    )
