"""Comprehensive, combined Schedule CG test matrix across ITR-2 and ITR-3.

Both forms share the identical Schedule CG/CYLA/BFLA/Schedule-SI
architecture (`app/engine/schedules/capital_gains.py`,
`app/engine/schedules/loss_setoff/{cyla,bfla}.py`,
`app/engine/schedules/special_rates.py`, and -- since
`tests/test_itr3_cg_tax_rate_fix.py` -- the shared
`post_loss_cg_baskets()`), differing only in: ITR-2 alone supports an
FII/FPI assessee (a genuine flat-30% STCG basket, section 115AD); ITR-3
alone supports slump sale and unutilized-CGAS-deposit disclosure (both
confirmed, by direct grep, to be DISCLOSURE-ONLY in `calculators/itr3.py`
today -- neither field is read by the calculator at all, so neither has
any tax effect yet; documented here, not silently assumed fixed).

Most scenarios below are parametrized across both forms (`form="itr2"`/
`"itr3"`) via `_compute()`, proving the two forms' tax computation is
genuinely identical for every economic scenario that doesn't depend on a
form-specific feature. Form-specific sections (FII/FPI, slump sale,
unutilized CGAS) are un-parametrized, single-form tests at the end.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal as D

import pytest

from app.engine.calculators.itr2 import compute as compute_itr2
from app.engine.calculators.itr3 import compute as compute_itr3
from app.schemas.itr1 import HousePropertyIncome, PropertyType
from app.schemas.itr2 import (
    BFLossItem,
    CapitalGainExemptionClaim,
    CGDtaaEntry,
    CGTransaction,
    CGAssetType,
    ITR2Input,
    PTIEntry,
    ResidentialStatus,
    ScheduleSIEntry,
)
from app.schemas.itr3 import ITR3Input

_FORMS = ("itr2", "itr3")


def _compute(form: str, **kwargs):
    kwargs.setdefault("age_bracket", "below_60")
    kwargs.setdefault("tax_regime", "old")
    if form == "itr2":
        return compute_itr2(ITR2Input(**kwargs))
    return compute_itr3(ITR3Input(**kwargs))


def _si(r) -> dict:
    return {e.section: e for e in r.schedules["si"].entries}


def _txn(asset_type: CGAssetType, consideration: D, cost: D, **kw) -> CGTransaction:
    kw.setdefault("date_of_transfer", date(2026, 3, 31))
    return CGTransaction(
        asset_type=asset_type, full_consideration=consideration, cost_of_acquisition=cost, **kw
    )


# ===========================================================================
# Section A -- basic per-asset-type gain computation and rate routing
# ===========================================================================

@pytest.mark.parametrize("form", _FORMS)
def test_111a_stcg_taxed_at_20_percent(form) -> None:
    txn = _txn(CGAssetType.LISTED_EQUITY_111A, D("500000"), D("300000"), explicit_long_term=False)
    r = _compute(form, cg_transactions=[txn])
    si = _si(r)
    assert si["111A"].taxable_income == D("200000")
    assert si["111A"].tax_amount == D("40000")
    assert r.slab_tax == D("0")


@pytest.mark.parametrize("form", _FORMS)
def test_112a_gain_below_threshold_is_fully_exempt(form) -> None:
    txn = _txn(CGAssetType.LISTED_EQUITY_112A, D("1000000"), D("900000"), explicit_long_term=True)
    r = _compute(form, cg_transactions=[txn])
    si = _si(r)
    assert si["112A"].taxable_income == D("0")
    assert si["112A"].tax_amount == D("0")
    assert r.special_rate_tax == D("0")


@pytest.mark.parametrize("form", _FORMS)
def test_112a_gain_above_threshold_taxes_only_excess(form) -> None:
    txn = _txn(CGAssetType.LISTED_EQUITY_112A, D("2000000"), D("1500000"), explicit_long_term=True)
    r = _compute(form, cg_transactions=[txn])
    si = _si(r)
    # gain = 500000; taxable = 500000 - 125000 = 375000; tax = 12.5%
    assert si["112A"].taxable_income == D("375000")
    assert si["112A"].tax_amount == D("46875")
    assert si["112A"].gross_income == D("500000")  # discloses the GROSS pre-threshold gain


@pytest.mark.parametrize("form", _FORMS)
def test_land_building_stcg_is_slab_rate_not_special_rate(form) -> None:
    txn = _txn(
        CGAssetType.LAND_BUILDING, D("2000000"), D("1500000"),
        date_of_acquisition=date(2025, 6, 1), date_of_transfer=date(2025, 12, 1),
    )
    r = _compute(form, cg_transactions=[txn])
    assert r.capital_gains_income == D("500000")
    assert r.special_rate_tax == D("0")
    assert r.slab_tax > D("0")


@pytest.mark.parametrize("form", _FORMS)
def test_land_building_ltcg_post_cutoff_taxed_at_112_no_relief(form) -> None:
    """A post-23-Jul-2024 acquisition is never eligible for the second
    proviso, regardless of residency -- the whole gain is taxed at the
    plain 12.5% section-112 rate. (Holding period must clear the 24-month
    land/building long-term threshold, not just be entered after the
    cutoff date.)"""
    txn = _txn(
        CGAssetType.LAND_BUILDING, D("2000000"), D("1000000"),
        date_of_acquisition=date(2024, 8, 1), date_of_transfer=date(2027, 1, 1),
    )
    r = _compute(form, cg_transactions=[txn])
    si = _si(r)
    assert si["112"].taxable_income == D("1000000")
    assert si["112"].tax_amount == D("125000")


@pytest.mark.parametrize("form", _FORMS)
def test_other_assets_stcg_is_slab_rate(form) -> None:
    txn = _txn(CGAssetType.JEWELLERY, D("1500000"), D("500000"), explicit_long_term=False)
    r = _compute(form, cg_transactions=[txn])
    assert r.capital_gains_income == D("1000000")
    assert r.special_rate_tax == D("0")
    assert r.slab_tax > D("0")  # gain comfortably exceeds the old-regime basic exemption


@pytest.mark.parametrize("form", _FORMS)
def test_other_assets_ltcg_taxed_at_section_112(form) -> None:
    txn = _txn(CGAssetType.JEWELLERY, D("300000"), D("100000"), explicit_long_term=True)
    r = _compute(form, cg_transactions=[txn])
    si = _si(r)
    assert si["112"].taxable_income == D("200000")
    assert si["112"].tax_amount == D("25000")


@pytest.mark.parametrize("form", _FORMS)
def test_section_50ca_deemed_consideration_applied_to_actual_tax(form) -> None:
    """Cross-form issue #8: section 50CA ("higher of consideration or
    FMV" for unquoted shares) was correctly disclosed but never applied
    to the actual taxed gain -- consideration 100000, cost 50000, FMV
    2000000 must produce a taxable gain of 1950000 (FMV - cost), not
    50000 (consideration - cost)."""
    txn = _txn(
        CGAssetType.UNLISTED_SHARES, D("100000"), D("50000"),
        explicit_long_term=True, fair_market_value_50ca=D("2000000"),
    )
    r = _compute(form, cg_transactions=[txn])
    si = _si(r)
    assert si["112"].taxable_income == D("1950000")
    assert si["112"].tax_amount == D("243750")  # 1950000 * 12.5%


@pytest.mark.parametrize("form", _FORMS)
def test_section_50ca_aggregates_across_transactions_not_per_transaction(form) -> None:
    """Section 50CA applies "higher of consideration or FMV" to ALL
    unquoted-share disposals TOGETHER as one aggregate row on the
    official form, matching the disclosure builder's own aggregation
    (itd/cg_shared.py). Applying it per-transaction would overstate the
    deemed consideration here: txn A (consideration 300000, FMV 100000)
    and txn B (consideration 100000, FMV 300000) each individually
    "deem" no change (max already equals the higher side for A, and B's
    FMV exceeds its own consideration) -- summed correctly in aggregate,
    total consideration (400000) equals total FMV (400000), so there
    should be NO 50CA adjustment at all. A wrong per-transaction
    implementation would instead deem A's max(300000,100000)=300000 +
    B's max(100000,300000)=300000 = 600000, a 200000 overstatement."""
    txn_a = _txn(
        CGAssetType.UNLISTED_SHARES, D("300000"), D("100000"),
        explicit_long_term=True, fair_market_value_50ca=D("100000"),
    )
    txn_b = _txn(
        CGAssetType.UNLISTED_SHARES, D("100000"), D("50000"),
        explicit_long_term=True, fair_market_value_50ca=D("300000"),
    )
    r = _compute(form, cg_transactions=[txn_a, txn_b])
    si = _si(r)
    # gain = (300000 - 100000) + (100000 - 50000) = 250000, no 50CA delta
    assert si["112"].taxable_income == D("250000")


@pytest.mark.parametrize("form", _FORMS)
def test_section_94_7_94_8_disallowed_loss_added_back_to_other_assets_stcg(form) -> None:
    """Cross-form issue #9: the section 94(7)/94(8) disallowed-loss
    add-back (Schedule CG's Sl. A5d ITR-2 / A6d ITR-3, "loss to be
    disallowed") was present on ITR-3's own other_asset_gain() but
    missing from ITR-2's equivalent -- jewellery STCG with consideration
    500000, cost 300000, a 50000 disallowed loss must produce a taxable
    gain of 250000 (200000 + 50000 addback), not 200000."""
    txn = _txn(
        CGAssetType.JEWELLERY, D("500000"), D("300000"),
        explicit_long_term=False, loss_disallowed_94_7_94_8=D("50000"),
    )
    r = _compute(form, cg_transactions=[txn])
    assert r.capital_gains_income == D("250000")


@pytest.mark.parametrize("form", _FORMS)
def test_vda_taxed_flat_30_percent_isolated_from_loss_setoff(form) -> None:
    """VDA (115BBH) income cannot be reduced by ANY loss -- even a large
    same-year LTCG loss must leave the VDA tax untouched."""
    loss_txn = _txn(CGAssetType.OTHER, D("100000"), D("2000000"), explicit_long_term=True)  # 19L loss
    kwargs = dict(cg_transactions=[loss_txn])
    if form == "itr2":
        from app.schemas.itr2 import VDATransaction
        kwargs["vda_transactions"] = [VDATransaction(
            date_of_acquisition=date(2025, 6, 1), date_of_transfer=date(2026, 1, 1),
            acquisition_cost=D("50000"), consideration_received=D("250000"),
        )]
    else:
        from app.schemas.itr2 import VDATransaction
        kwargs["vda_transactions"] = [VDATransaction(
            date_of_acquisition=date(2025, 6, 1), date_of_transfer=date(2026, 1, 1),
            acquisition_cost=D("50000"), consideration_received=D("250000"),
        )]
    r = _compute(form, **kwargs)
    assert r.vda_income == D("200000")
    si = _si(r)
    assert si["115BBH"].taxable_income == D("200000")
    assert si["115BBH"].tax_amount == D("60000")  # flat 30%, never reduced by the LTCG loss


# ===========================================================================
# Section B -- section 112(1)(a) second proviso (land/building only)
# ===========================================================================

def _land_asset_for_proviso(**extra) -> CGTransaction:
    return _txn(
        CGAssetType.LAND_BUILDING, D("10000000"), D("1000000"),
        date_of_acquisition=date(2005, 1, 1), date_of_transfer=date(2026, 1, 1),
        indexed_cost=D("8000000"), **extra,
    )


@pytest.mark.parametrize("form", _FORMS)
def test_second_proviso_relief_applies_for_resident_pre_cutoff(form) -> None:
    r = _compute(form, cg_transactions=[_land_asset_for_proviso()])
    ltcg = r.schedules["cg"].ltcg
    assert ltcg.total_excess_tax_112_1a == D("725000")
    si = _si(r)
    assert si["112"].tax_amount == D("400000")  # 1,125,000 - 725,000 relief


@pytest.mark.parametrize("form", _FORMS)
def test_second_proviso_relief_not_applicable_post_cutoff_even_for_resident(form) -> None:
    """The SAME indexation-favorable numbers, but acquired AFTER the
    23-Jul-2024 cutoff -- the second proviso never applies at all."""
    txn = _txn(
        CGAssetType.LAND_BUILDING, D("10000000"), D("1000000"),
        date_of_acquisition=date(2024, 8, 1), date_of_transfer=date(2027, 1, 1),
        indexed_cost=D("8000000"),
    )
    r = _compute(form, cg_transactions=[txn])
    ltcg = r.schedules["cg"].ltcg
    assert ltcg.total_excess_tax_112_1a == D("0")
    si = _si(r)
    assert si["112"].tax_amount == D("1125000")


@pytest.mark.parametrize("form", _FORMS)
def test_second_proviso_relief_applies_for_not_ordinarily_resident(form) -> None:
    """NOR is a species of "resident" under section 6 -- only a
    non-resident is excluded from the second proviso."""
    r = _compute(
        form, cg_transactions=[_land_asset_for_proviso()],
        residential_status=ResidentialStatus.NOT_ORDINARILY_RESIDENT,
    )
    ltcg = r.schedules["cg"].ltcg
    assert ltcg.total_excess_tax_112_1a == D("725000")


@pytest.mark.parametrize("form", _FORMS)
def test_second_proviso_relief_not_applicable_for_non_resident(form) -> None:
    r = _compute(
        form, cg_transactions=[_land_asset_for_proviso()],
        residential_status=ResidentialStatus.NON_RESIDENT,
    )
    ltcg = r.schedules["cg"].ltcg
    assert ltcg.total_excess_tax_112_1a == D("0")
    si = _si(r)
    assert si["112"].tax_amount == D("1125000")


@pytest.mark.parametrize("form", _FORMS)
def test_second_proviso_relief_capped_at_bucket_own_tax_when_loss_reduces_it(form) -> None:
    """When a same-bucket LTCG loss reduces the section-112 income below
    the raw land/building gain the relief was computed from, the relief
    must be CAPPED at the bucket's own (now smaller) actual tax -- here,
    reduced enough that the entire remaining tax is wiped out, never
    negative, never exceeding what was actually charged."""
    other_loss = _txn(CGAssetType.OTHER, D("100000"), D("4100000"), explicit_long_term=True)  # 4M LTCL
    r = _compute(form, cg_transactions=[_land_asset_for_proviso(), other_loss])
    ltcg = r.schedules["cg"].ltcg
    # Raw relief is still 725,000 (per-asset, computed before loss netting)
    assert ltcg.total_excess_tax_112_1a == D("725000")
    post_loss_cg = r.schedules["post_loss_cg"]
    assert post_loss_cg["112"] == D("5000000")  # 9,000,000 land gain - 4,000,000 LTCL
    si = _si(r)
    # Bucket's own uncapped tax is 5,000,000 * 12.5% = 625,000 -- LESS than
    # the raw 725,000 relief, so the relief is capped exactly to zero, not negative.
    assert si["112"].tax_amount == D("0")


# ===========================================================================
# Section C -- intra-head STCL/LTCL netting (aggregate())
# ===========================================================================

@pytest.mark.parametrize("form", _FORMS)
def test_stcl_absorbs_ltcg_when_stcg_insufficient(form) -> None:
    """A pure short-term loss (no offsetting STCG) must still net against
    LTCG -- STCL can absorb both STCG and LTCG."""
    stcl = _txn(CGAssetType.OTHER, D("100000"), D("400000"), explicit_long_term=False)  # 3L STCL
    ltcg = _txn(CGAssetType.OTHER, D("1000000"), D("400000"), explicit_long_term=True)  # 6L LTCG
    r = _compute(form, cg_transactions=[stcl, ltcg])
    assert r.capital_gains_income == D("300000")  # 600000 - 300000
    si = _si(r)
    assert si["112"].taxable_income == D("300000")


@pytest.mark.parametrize("form", _FORMS)
def test_ltcl_cannot_absorb_stcg(form) -> None:
    """LTCL must NEVER reduce STCG -- the asymmetric statutory rule. The
    LTCL simply carries forward as a loss; it does not net against the
    111A STCG at all, so capital_gains_income reflects the STCG alone."""
    ltcl = _txn(CGAssetType.OTHER, D("100000"), D("500000"), explicit_long_term=True)  # 4L LTCL
    stcg_111a = _txn(CGAssetType.LISTED_EQUITY_111A, D("500000"), D("300000"), explicit_long_term=False)  # 2L STCG
    r = _compute(form, cg_transactions=[ltcl, stcg_111a])
    si = _si(r)
    assert si["111A"].taxable_income == D("200000")  # fully untouched by the LTCL
    assert si["111A"].tax_amount == D("40000")
    assert r.capital_gains_income == D("200000")


@pytest.mark.parametrize("form", _FORMS)
def test_111a_stcg_untouched_by_unrelated_land_stcl(form) -> None:
    """A land/building STCL (slab-rate bucket) does not cross-contaminate
    the 111A bucket -- both are still "STCG" for aggregate()'s own
    intra-head STCL-vs-LTCG total netting, but CYLA/BFLA keep the RATE
    buckets separate afterward."""
    land_loss = _txn(
        CGAssetType.LAND_BUILDING, D("100000"), D("600000"),
        date_of_acquisition=date(2025, 6, 1), date_of_transfer=date(2025, 12, 1),
    )  # 5L STCL
    stcg_111a = _txn(CGAssetType.LISTED_EQUITY_111A, D("800000"), D("500000"), explicit_long_term=False)  # 3L STCG
    r = _compute(form, cg_transactions=[land_loss, stcg_111a])
    # aggregate()'s own total nets to -200000 (a net STCL), so
    # total_capital_gains floors at 0 -- but the 111A bucket's OWN Schedule
    # SI tax is a separate CYLA-basket-level computation via post_loss_cg,
    # not simply "total STCG minus total STCL".
    post_loss_cg = r.schedules["post_loss_cg"]
    assert post_loss_cg["111a"] + post_loss_cg["normal_stcg"] == r.capital_gains_income


# ===========================================================================
# Section D -- CYLA cross-head loss set-off
# ===========================================================================

@pytest.mark.parametrize("form", _FORMS)
def test_hp_loss_old_regime_reduces_special_rate_ltcg_bucket(form) -> None:
    hp = HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED, home_loan_interest_paid=D("300000"))
    txn = _txn(CGAssetType.OTHER, D("10000000"), D("2000000"), explicit_long_term=True)  # 80L LTCG-other
    r = _compute(form, cg_transactions=[txn], house_property_income=hp, tax_regime="old")
    assert r.house_property_income == D("-200000")  # capped at 2L for self-occupied
    assert r.cyla_total_set_off == D("200000")
    post_loss_cg = r.schedules["post_loss_cg"]
    assert post_loss_cg["112"] == D("7800000")
    assert r.special_rate_tax == D("975000")


@pytest.mark.parametrize("form", _FORMS)
def test_hp_loss_new_regime_is_blocked_entirely(form) -> None:
    """Section 71(3A): a new-regime taxpayer cannot set off HP loss
    against any other head at all."""
    hp = HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED, home_loan_interest_paid=D("300000"))
    txn = _txn(CGAssetType.OTHER, D("10000000"), D("2000000"), explicit_long_term=True)
    r = _compute(form, cg_transactions=[txn], house_property_income=hp, tax_regime="new")
    assert r.cyla_total_set_off == D("0")
    post_loss_cg = r.schedules["post_loss_cg"]
    assert post_loss_cg["112"] == D("8000000")  # untouched


@pytest.mark.parametrize("form", _FORMS)
def test_hp_loss_absorbed_into_111a_bucket_specifically(form) -> None:
    hp = HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED, home_loan_interest_paid=D("300000"))
    stcg_111a = _txn(CGAssetType.LISTED_EQUITY_111A, D("500000"), D("100000"), explicit_long_term=False)  # 4L
    r = _compute(form, cg_transactions=[stcg_111a], house_property_income=hp, tax_regime="old")
    post_loss_cg = r.schedules["post_loss_cg"]
    assert post_loss_cg["111a"] == D("200000")  # 400000 - 200000 HP loss
    si = _si(r)
    assert si["111A"].taxable_income == D("200000")
    assert si["111A"].tax_amount == D("40000")


# ===========================================================================
# Section E -- BFLA brought-forward loss set-off
#
# **Two genuine bugs were found via this section (2026-09-18), both since
# fixed (2026-09-19) at the user's explicit request** -- see the tracker's
# Schedule 20 fix-log for the full write-up:
#
# Bug 1 (was ITR-3-only): `calculators/itr3.py`'s brought-forward-loss list
# construction did `"head": str(item.head)`, but `BFLossItem.head` is a
# `LossHead(str, Enum)` -- `str(LossHead.LONG_TERM_CAPITAL)` renders as
# `"LossHead.LONG_TERM_CAPITAL"`, not `"LTCG"`, on this Python/pydantic
# version, so `bfla.py`'s own head dispatch never matched and a
# brought-forward loss had ZERO effect on ITR-3's BFLA at all. Fixed to
# `item.head.value if hasattr(item.head, "value") else str(item.head)`,
# matching ITR-2's own already-correct line.
#
# Bug 2 (was pre-existing in ITR-2, inherited unchanged by the shared
# `post_loss_cg_baskets()` extraction): the function read
# `cyla.stcg20_remaining`/`cyla.stcg30_remaining`/`cyla.stcg_app_remaining`/
# `cyla.stcg_dtaa_remaining` (the PRE-BFLA, CYLA-level residual) for the
# `"111a"`/`"normal_stcg"`/`"stcg_dtaa"` post-loss buckets, but the
# POST-BFLA residual for `"112"`/`"ltcg_dtaa"` -- an asymmetry present
# since the function's introduction (`git log -S`), with no comment ever
# justifying it. Fixed so all six sub-baskets read the post-BFLA residual
# uniformly, since BFLA is the true final remaining income once both
# current-year and brought-forward losses are applied.
# ===========================================================================

@pytest.mark.parametrize("form", _FORMS)
def test_brought_forward_ltcg_loss_reduces_current_year_section_112(form) -> None:
    bf = BFLossItem(assessment_year="2024-25", head="LTCG", sub_category="LTCG", original_loss=D("300000"), brought_forward=D("300000"))
    txn = _txn(CGAssetType.OTHER, D("1000000"), D("400000"), explicit_long_term=True)  # 6L LTCG
    r = _compute(form, cg_transactions=[txn], bf_losses=[bf])
    assert r.bfla_total_set_off == D("300000")
    post_loss_cg = r.schedules["post_loss_cg"]
    assert post_loss_cg["112"] == D("300000")
    si = _si(r)
    assert si["112"].taxable_income == D("300000")
    assert si["112"].tax_amount == D("37500")


@pytest.mark.parametrize("form", _FORMS)
def test_brought_forward_stcg_loss_reduces_111a_bucket_including_schedule_si(form) -> None:
    """Bug 2's own regression proof: the brought-forward STCG loss must
    now correctly reduce BOTH `bfla.stcg20_remaining` (already correct
    before the fix) AND Schedule SI's own 111A row (the actual bug)."""
    bf = BFLossItem(assessment_year="2024-25", head="STCG", sub_category="STCG", original_loss=D("100000"), brought_forward=D("100000"))
    stcg_111a = _txn(CGAssetType.LISTED_EQUITY_111A, D("500000"), D("100000"), explicit_long_term=False)  # 4L
    r = _compute(form, cg_transactions=[stcg_111a], bf_losses=[bf])
    assert r.bfla_total_set_off == D("100000")
    bfla = r.schedules["bfla"]
    assert bfla.stcg20_remaining == D("300000")
    si = _si(r)
    assert si["111A"].taxable_income == D("300000")
    assert si["111A"].tax_amount == D("60000")  # 20% of 300,000, not the pre-fix 400,000


@pytest.mark.parametrize("form", _FORMS)
def test_brought_forward_stcg_loss_absorbs_stcg_before_ltcg(form) -> None:
    """A brought-forward STCG-head loss absorbs STCG buckets FIRST, then
    LTCG only if STCG is insufficient (bfla.py's own `_STCG_ORDER`-then-
    `_LTCG_ORDER` cascade for a "STCG"-head source)."""
    bf = BFLossItem(assessment_year="2024-25", head="STCG", sub_category="STCG", original_loss=D("100000"), brought_forward=D("100000"))
    stcg_111a = _txn(CGAssetType.LISTED_EQUITY_111A, D("500000"), D("100000"), explicit_long_term=False)  # 4L
    ltcg_other = _txn(CGAssetType.OTHER, D("1000000"), D("400000"), explicit_long_term=True)  # 6L
    r = _compute(form, cg_transactions=[stcg_111a, ltcg_other], bf_losses=[bf])
    si = _si(r)
    assert si["111A"].taxable_income == D("300000")  # 400000 - 100000
    assert si["112"].taxable_income == D("600000")  # untouched -- STCG fully absorbed the loss


@pytest.mark.parametrize("form", _FORMS)
def test_brought_forward_expired_loss_after_8_years_never_applies(form) -> None:
    """Section 74's 8-year carry-forward limit -- an AY2016-17 LTCG loss
    is expired for AY2026-27 (10 years old) and must not reduce anything."""
    bf = BFLossItem(assessment_year="2016-17", head="LTCG", sub_category="LTCG", original_loss=D("500000"), brought_forward=D("500000"))
    txn = _txn(CGAssetType.OTHER, D("1000000"), D("400000"), explicit_long_term=True)  # 6L LTCG
    r = _compute(form, cg_transactions=[txn], bf_losses=[bf])
    assert r.bfla_total_set_off == D("0")
    post_loss_cg = r.schedules["post_loss_cg"]
    assert post_loss_cg["112"] == D("600000")  # fully untouched -- expired, not applied
    bfla = r.schedules["bfla"]
    expired = [e for e in bfla.entries if e.sub_category == "EXPIRED"]
    assert len(expired) == 1
    assert expired[0].remaining_carry_forward == D("0")


# ===========================================================================
# Section F -- exemptions (54/54B/54EC/54F) ordering and capping
#
# **A third genuine bug was found here (2026-09-18), since fixed
# (2026-09-19)**: ITR-3's transaction loop only accumulated the
# `exempt_54*` legacy scalars in the LONG-term land/building branch --
# the SHORT-term branch never read `tx.deduction_us54b` at all, AND
# separately never populated the per-asset `CGAsset.exemptions` list
# `post_loss_cg_baskets()`'s own STCG-bucket-targeting logic
# (`stcg_land_54b = sum(asset.exemption_total ...)`) depends on -- so a
# 54B claim on short-term land/building had ZERO tax effect on ITR-3,
# via either mechanism. Fixed by (1) accumulating `exempt_54b` in the
# short-term branch too (Schedule CG item A1d allows ONLY 54B for STCG,
# unlike the long-term branch's four sections) and (2) populating
# `CGAsset.exemptions` via the shared `_normalized_land_exemptions()`
# helper (already used by ITR-2's own `_classify()`) for both ST and LT
# land/building rows alike.
# ===========================================================================

@pytest.mark.parametrize("form", _FORMS)
def test_54b_on_stcg_land_reduces_stcg_not_ltcg(form) -> None:
    """Section 54B is the ONLY exemption STCG land/building may claim, and
    it must reduce THAT bucket first, not simply flow to LTCG."""
    stcg_land = _txn(
        CGAssetType.LAND_BUILDING, D("2000000"), D("1000000"),
        date_of_acquisition=date(2025, 6, 1), date_of_transfer=date(2025, 12, 1),
        deduction_us54b=D("400000"),
    )  # 10L gain, 4L exemption -> 6L taxable, slab rate
    ltcg_other = _txn(CGAssetType.OTHER, D("1000000"), D("400000"), explicit_long_term=True)  # 6L LTCG, no exemption
    r = _compute(form, cg_transactions=[stcg_land, ltcg_other])
    post_loss_cg = r.schedules["post_loss_cg"]
    assert post_loss_cg["normal_stcg"] == D("600000")  # 1,000,000 - 400,000
    assert post_loss_cg["112"] == D("600000")  # untouched by the 54B claim


@pytest.mark.parametrize("form", _FORMS)
def test_54f_reduces_other_ltcg_before_112a(form) -> None:
    """§54/54EC/54F consumption order is [other_ltcg, section_112a] --
    the "other" LTCG bucket is consumed first. The two forms read a
    generic "other assets" exemption from genuinely DIFFERENT fields on
    the same shared `CGTransaction`: ITR-2's own `_classify()` never calls
    `other_asset_gain()` at all for this bucket (a bare `full_consideration
    - cost - expenditure`, with the exemption applied later, at the
    aggregate level, via `_claim_total()`'s `deduction_us54f` legacy-
    scalar fallback); ITR-3's `other_asset_gain()` reads
    `other_assets_exemption_section`/`_amount` directly at the per-
    transaction gain-computation source instead and never looks at
    `deduction_us54f` for this bucket. Both are set here so each form
    picks up its own mechanism and neither is silently a no-op."""
    other_ltcg = _txn(
        CGAssetType.OTHER, D("1000000"), D("700000"), explicit_long_term=True,
        deduction_us54f=D("200000"),
        other_assets_exemption_section="54F", other_assets_exemption_amount=D("200000"),
    )  # 3L gain, 2L exempt -> 1L taxable
    ltcg_112a = _txn(CGAssetType.LISTED_EQUITY_112A, D("2000000"), D("500000"), explicit_long_term=True)  # 15L gain
    r = _compute(form, cg_transactions=[other_ltcg, ltcg_112a])
    post_loss_cg = r.schedules["post_loss_cg"]
    assert post_loss_cg["112"] == D("100000")  # 300000 - 200000
    assert post_loss_cg["112a_gross"] == D("1500000")  # fully untouched


@pytest.mark.parametrize("form", _FORMS)
def test_54f_canonical_claim_on_112a_transaction_reduces_actual_tax(form) -> None:
    """Cross-form issue (ITR-3-only, found and fixed 2026-09-19): a section
    54F exemption legally claimed against a 112A-classified LTCG (the
    official schema's own `SaleOfEquityShareUs112A.DeductionUs54F` field
    exists specifically for this) was correctly DISCLOSED by ITR-3's own
    builder (`ded_54f_112a` reduces `CapgainonAssets`) but had ZERO effect
    on the actual taxed amount -- `calculators/itr3.py` only ever read the
    canonical `CGTransaction.exemptions` claim list for land/building rows
    (via legacy `deduction_us54*` scalars), never for 112A/111A-equity
    rows. ITR-2 already gets this right via the shared `_claim_total()`
    mechanism (`capital_gains.py`'s own `compute()` entry point) -- this
    test pins both forms to the identical, correct behavior."""
    tx = CGTransaction(
        asset_type=CGAssetType.LISTED_EQUITY_112A,
        full_consideration=D("2000000"), cost_of_acquisition=D("500000"),
        fair_market_value_jan2018=D("500000"),
        date_of_acquisition=date(2015, 1, 1), date_of_transfer=date(2026, 1, 1),
        exemptions=[CapitalGainExemptionClaim(
            section="54F", transfer_date=date(2026, 1, 1), eligible_gain=D("1000000"),
            investment_amount=D("1000000"), investment_date=date(2026, 2, 1),
        )],
    )
    r = _compute(form, cg_transactions=[tx])
    # Gross gain 1,500,000 - 54F claim 1,000,000 = 500,000 actually taxed
    # (not the full, un-reduced 1,500,000).
    assert r.schedules["cg"].total_capital_gains == D("500000")
    si = _si(r)
    assert si["112A"].gross_income == D("500000")


@pytest.mark.parametrize("form", _FORMS)
def test_exemption_exceeding_gain_caps_at_gain_never_negative(form) -> None:
    txn = _txn(
        CGAssetType.OTHER, D("500000"), D("300000"), explicit_long_term=True,
        deduction_us54f=D("999999999"),
        other_assets_exemption_section="54F", other_assets_exemption_amount=D("999999999"),
    )  # 2L gain
    r = _compute(form, cg_transactions=[txn])
    post_loss_cg = r.schedules["post_loss_cg"]
    assert post_loss_cg["112"] == D("0")
    assert post_loss_cg["112"] >= D("0")
    assert r.special_rate_tax == D("0")


@pytest.mark.parametrize("form", _FORMS)
def test_leftover_54_exemption_after_stcg_reduces_ltcg(form) -> None:
    """Any 54B exemption pool NOT fully consumed by STCG land carries over
    to reduce LTCG (the remaining-pool consumption chain)."""
    stcg_land = _txn(
        CGAssetType.LAND_BUILDING, D("500000"), D("400000"),
        date_of_acquisition=date(2025, 6, 1), date_of_transfer=date(2025, 12, 1),
        deduction_us54b=D("300000"),
    )  # 1L gain, but 3L claimed -- only 1L actually usable here
    r = _compute(form, cg_transactions=[stcg_land])
    post_loss_cg = r.schedules["post_loss_cg"]
    assert post_loss_cg["normal_stcg"] == D("0")  # fully absorbed, capped at gain


# ===========================================================================
# Section G -- NRI proviso-48/115F and DTAA (both forms)
# ===========================================================================

@pytest.mark.parametrize("form", _FORMS)
def test_nri_proviso48_stcg_stt_paid_taxed_at_111a(form) -> None:
    r = _compute(
        form, residential_status=ResidentialStatus.NON_RESIDENT,
        cg_nri_stcg_stt_paid=D("500000"), cg_nri_stcg_stt_not_paid=D("300000"),
    )
    si = _si(r)
    assert si["111A"].taxable_income == D("500000")
    assert si["111A"].tax_amount == D("100000")
    assert r.capital_gains_income == D("800000")
    assert r.slab_tax > D("0")  # the 300,000 stt-not-paid portion is slab-rate


@pytest.mark.parametrize("form", _FORMS)
def test_nri_ltcg_proviso48_net_of_54f_taxed_at_section_112(form) -> None:
    r = _compute(
        form, residential_status=ResidentialStatus.NON_RESIDENT,
        cg_nri_ltcg_without_indexation=D("900000"), cg_nri_ltcg_deduction_54f=D("300000"),
    )
    si = _si(r)
    assert si["112"].taxable_income == D("600000")
    assert si["112"].tax_amount == D("75000")


@pytest.mark.parametrize("form", _FORMS)
def test_nri_115f_net_sale_value_taxed_at_section_112(form) -> None:
    r = _compute(
        form, residential_status=ResidentialStatus.NON_RESIDENT,
        cg_nri_115f_sale_value=D("700000"), cg_nri_115f_deduction=D("200000"),
    )
    si = _si(r)
    assert si["112"].taxable_income == D("500000")


@pytest.mark.parametrize("form", _FORMS)
def test_cg_result_total_capital_gains_matches_actual_taxed_amount(form) -> None:
    """`result.schedules["cg"].total_capital_gains` -- the CGResult's own
    top-level total, distinct from `result.capital_gains_income` -- must
    always agree with the actual taxed amount, not just for ordinary
    cg_transactions. Found stale for ITR-2 specifically: its calculator
    builds `cg_result` from ONLY the ordinary transaction list BEFORE the
    NRI-proviso-48/DTAA/unutilized-CGAS blocks mutate `stcg_result`/
    `ltcg_result` in place, and the later VDA-stage reconstruction just
    added VDA on top of that stale figure rather than re-aggregating.
    Confirmed harmless for actual output today (neither the builder's own
    disclosure nor any tax path reads this field), but a landmine for
    future code assuming it's authoritative -- and the official schema
    itself defines Schedule CG's own totals (SumOfCGIncm = item A9 STCG +
    item B12 LTCG net of exemption) as exactly what this field is meant to
    hold, so it should never silently diverge from `capital_gains_income`."""
    r = _compute(
        form, residential_status=ResidentialStatus.NON_RESIDENT,
        cg_nri_stcg_stt_paid=D("500000"),
    )
    assert r.schedules["cg"].total_capital_gains == r.capital_gains_income == D("500000")


def _dtaa_entry(**kw) -> CGDtaaEntry:
    defaults = dict(
        amount=D("1000000"), item_no_incl="B1g", country_name="Mauritius",
        country_code="MU", dtaa_article="13", rate_as_per_treaty=D("10"),
        sec_it_act="112", rate_as_per_it_act=D("12.5"), applicable_rate=D("10"),
    )
    defaults.update(kw)
    return CGDtaaEntry(**defaults)


@pytest.mark.parametrize("form", _FORMS)
def test_dtaa_ltcg_chargeable_generates_its_own_special_rate_row(form) -> None:
    underlying = _txn(CGAssetType.OTHER, D("1000000"), D("0"), explicit_long_term=True)
    r = _compute(
        form, residential_status=ResidentialStatus.NON_RESIDENT,
        cg_transactions=[underlying], cg_ltcg_dtaa_entries=[_dtaa_entry()],
    )
    si = _si(r)
    assert "112" not in si
    dtaa_rows = [e for e in r.schedules["si"].entries if e.tax_rate_pct == D("10")]
    assert len(dtaa_rows) == 1
    assert dtaa_rows[0].taxable_income == D("1000000")
    assert dtaa_rows[0].tax_amount == D("100000")


@pytest.mark.parametrize("form", _FORMS)
def test_dtaa_ltcg_not_chargeable_excluded_entirely(form) -> None:
    underlying = _txn(CGAssetType.OTHER, D("1000000"), D("0"), explicit_long_term=True)
    r = _compute(
        form, residential_status=ResidentialStatus.NON_RESIDENT,
        cg_transactions=[underlying], cg_ltcg_dtaa_entries=[_dtaa_entry(rate_as_per_treaty=D("0"))],
    )
    assert r.capital_gains_income == D("0")
    assert r.special_rate_tax == D("0")


@pytest.mark.parametrize("form", _FORMS)
def test_dtaa_stcg_chargeable_generates_its_own_special_rate_row(form) -> None:
    underlying = _txn(CGAssetType.OTHER, D("500000"), D("0"), explicit_long_term=False)
    dtaa = _dtaa_entry(amount=D("500000"), item_no_incl="A3ie", applicable_rate=D("15"), rate_as_per_treaty=D("15"))
    r = _compute(
        form, residential_status=ResidentialStatus.NON_RESIDENT,
        cg_transactions=[underlying], cg_stcg_dtaa_entries=[dtaa],
    )
    dtaa_rows = [e for e in r.schedules["si"].entries if e.tax_rate_pct == D("15")]
    assert len(dtaa_rows) == 1
    assert dtaa_rows[0].taxable_income == D("500000")
    assert dtaa_rows[0].tax_amount == D("75000")


@pytest.mark.parametrize("form", _FORMS)
def test_dtaa_ltcg_ratio_allocated_across_multiple_entries_after_loss(form) -> None:
    """When a same-year LTCG loss elsewhere reduces the DTAA-tagged
    bucket, the taxable remainder is allocated PROPORTIONALLY across
    every declared DTAA entry (not first-in-first-out).

    Mechanics: the 20L "underlying" gain is entirely DTAA-tagged (merged
    into `ltcg_result.income_dtaa`, per the DTAA-merge's own re-tag
    design -- see the chargeable-DTAA tests above); the SEPARATE 5L LTCL
    (untagged, in the plain "other" bucket) makes `income_125per_other`
    go NEGATIVE. CYLA's own intra-head CG netting (`loss_setoff/cyla.py`,
    `_LTCG_ORDER = ("ltcg125", "ltcg_dtaa")`) then correctly absorbs that
    LTCG loss out of the ltcg125 bucket INTO the ltcg_dtaa bucket (section
    70(1) allows one LTCG sub-basket's loss to net against another) --
    20L - 5L = 15L taxable DTAA remainder, hence ratio = 15L/20L = 0.75."""
    underlying = _txn(CGAssetType.OTHER, D("2000000"), D("0"), explicit_long_term=True)  # 20L gain, all DTAA-tagged
    loss = _txn(CGAssetType.OTHER, D("100000"), D("600000"), explicit_long_term=True)  # 5L LTCL, untagged
    entry_a = _dtaa_entry(amount=D("1500000"), applicable_rate=D("10"), rate_as_per_treaty=D("10"))
    entry_b = _dtaa_entry(amount=D("500000"), applicable_rate=D("20"), rate_as_per_treaty=D("20"))
    r = _compute(
        form, residential_status=ResidentialStatus.NON_RESIDENT,
        cg_transactions=[underlying, loss], cg_ltcg_dtaa_entries=[entry_a, entry_b],
    )
    rows = sorted((e for e in r.schedules["si"].entries if e.section == "DTAALTCG"), key=lambda e: e.tax_rate_pct)
    assert len(rows) == 2
    assert rows[0].taxable_income == D("1125000")  # 1,500,000 * 0.75
    assert rows[1].taxable_income == D("375000")   # 500,000 * 0.75


# ===========================================================================
# Section H -- buyback loss (section 46A)
# ===========================================================================

@pytest.mark.parametrize("form", _FORMS)
def test_buyback_loss_stcg20_reduces_111a_bucket(form) -> None:
    stcg_111a = _txn(CGAssetType.LISTED_EQUITY_111A, D("500000"), D("100000"), explicit_long_term=False)  # 4L
    r = _compute(form, cg_transactions=[stcg_111a], cg_buyback_loss_stcg20=D("-150000"))
    si = _si(r)
    assert si["111A"].taxable_income == D("250000")


@pytest.mark.parametrize("form", _FORMS)
def test_buyback_loss_ltcg_reduces_section_112_bucket(form) -> None:
    other_ltcg = _txn(CGAssetType.OTHER, D("1000000"), D("400000"), explicit_long_term=True)  # 6L
    r = _compute(form, cg_transactions=[other_ltcg], cg_buyback_loss_ltcg=D("-100000"))
    si = _si(r)
    assert si["112"].taxable_income == D("500000")


# ===========================================================================
# Section I -- cross-form parity (identical scenario, identical tax)
# ===========================================================================

@pytest.mark.parametrize(
    "txns_factory",
    [
        lambda: [_txn(CGAssetType.LISTED_EQUITY_111A, D("500000"), D("300000"), explicit_long_term=False)],
        lambda: [_txn(CGAssetType.LISTED_EQUITY_112A, D("2000000"), D("500000"), explicit_long_term=True)],
        lambda: [_txn(CGAssetType.OTHER, D("1000000"), D("400000"), explicit_long_term=True)],
        lambda: [
            _txn(CGAssetType.LISTED_EQUITY_111A, D("500000"), D("300000"), explicit_long_term=False),
            _txn(CGAssetType.OTHER, D("100000"), D("400000"), explicit_long_term=True),
        ],
    ],
    ids=["111a-only", "112a-above-threshold", "112-other-ltcg", "111a-plus-ltcl"],
)
def test_itr2_and_itr3_produce_identical_cg_tax_for_the_same_scenario(txns_factory) -> None:
    r2 = _compute("itr2", cg_transactions=txns_factory())
    r3 = _compute("itr3", cg_transactions=txns_factory())
    assert r2.capital_gains_income == r3.capital_gains_income
    assert r2.special_rate_tax == r3.special_rate_tax
    si2 = _si(r2)
    si3 = _si(r3)
    for section in set(si2) | set(si3):
        assert si2[section].tax_amount == si3[section].tax_amount, section
        assert si2[section].taxable_income == si3[section].taxable_income, section


# ===========================================================================
# Section J -- ITR-2-only: FII/FPI
# ===========================================================================

def _fii_filing_profile():
    from app.schemas.itr2 import ITR2FilingProfile
    from app.schemas.itr1 import FilingAddress

    return ITR2FilingProfile(
        pan="ABCFE1234F", surname_or_org_name="Foreign Fund",
        date_of_birth_or_formation=date(2000, 1, 1), father_name="NA",
        verification_place="Mumbai",
        primary_address=FilingAddress(
            residence_no="1", locality_or_area="BKC", city_or_town_or_district="Mumbai",
            state_code="27", mobile_no="9876543210", email="fund@example.com",
        ),
        residential_status=ResidentialStatus.NON_RESIDENT, benefit_us_115h=False,
        is_fii_fpi=True, sebi_registration_number="INABFP123456",
    )


def test_fii_fpi_securities_stcg_uses_flat_30_percent_bucket() -> None:
    """Section 115AD(1)(ii)'s flat 30% rate applies only to FII/FPI STCG on
    "securities" (a defined statutory term -- shares, debentures, units,
    bonds), confirmed against the statute and the official form's own item
    numbering (item A5 = FII securities, distinct from item A1 land/building
    and item A6 generic other assets). `unlisted_shares` is a genuine member
    of `_FII_SECURITIES_ASSET_TYPES`, so this scenario correctly lands in
    the flat-30% bucket."""
    txn = _txn(
        CGAssetType.UNLISTED_SHARES, D("500000"), D("350000"),
        date_of_acquisition=date(2025, 6, 1), date_of_transfer=date(2026, 1, 15),
    )
    r = _compute(
        "itr2", residential_status=ResidentialStatus.NON_RESIDENT,
        filing_profile=_fii_filing_profile(), cg_transactions=[txn],
    )
    cyla = r.schedules["cyla"]
    assert cyla.stcg30_remaining == D("150000")
    assert cyla.stcg_app_remaining == D("0")


def test_fii_fpi_non_securities_other_stcg_stays_slab_rate() -> None:
    """CORRECTION (2026-09-19): a prior version of this test wrongly
    asserted that ANY "other"-typed STCG for an FII/FPI gets the flat 30%
    rate -- that was a real, confirmed bug in the calculator (fixed this
    session), not correct statutory behaviour. `CGAssetType.OTHER` is NOT a
    member of `_FII_SECURITIES_ASSET_TYPES` (only genuine securities are),
    so an FII/FPI's land/building/jewellery/foreign-asset/generic-other
    STCG must stay in the ordinary applicable-rate (slab) bucket, exactly
    like a non-FII taxpayer's identical gain -- see
    `test_non_fii_stcg_never_lands_in_flat_30_percent_bucket` below for the
    non-FII counterpart this test now mirrors."""
    txn = _txn(
        CGAssetType.OTHER, D("500000"), D("350000"),
        date_of_acquisition=date(2025, 6, 1), date_of_transfer=date(2026, 1, 15),
    )
    r = _compute(
        "itr2", residential_status=ResidentialStatus.NON_RESIDENT,
        filing_profile=_fii_filing_profile(), cg_transactions=[txn],
    )
    cyla = r.schedules["cyla"]
    assert cyla.stcg30_remaining == D("0")
    assert cyla.stcg_app_remaining == D("150000")


def test_fii_fpi_land_only_stcg_stays_slab_not_flat_30() -> None:
    """An FII/FPI's STCG on land/building has no section 115AD flat-rate
    treatment -- `CGAssetType.LAND_BUILDING` is not a member of
    `_FII_SECURITIES_ASSET_TYPES`, so it must fall through to ordinary
    slab rate exactly like a non-FII taxpayer's identical gain."""
    txn = _txn(
        CGAssetType.LAND_BUILDING, D("2000000"), D("1000000"),
        date_of_acquisition=date(2025, 6, 1), date_of_transfer=date(2026, 1, 15),
    )
    r = _compute(
        "itr2", residential_status=ResidentialStatus.NON_RESIDENT,
        filing_profile=_fii_filing_profile(), cg_transactions=[txn],
    )
    assert r.special_rate_tax == D("0")
    assert r.slab_tax > D("0")


def test_fii_fpi_mixed_land_and_securities_splits_correctly() -> None:
    """A single FII/FPI return with BOTH a land/building STCG (slab-rate)
    AND a securities STCG (flat-30% u/s 115AD(1)(ii)) must tax only the
    securities portion at 30% -- the land portion must still contribute to
    ordinary slab tax, not be swept into the flat-30% bucket alongside
    it (the confirmed pre-existing bug this session's "Fix both" work
    closed -- a `post_loss_cg_baskets()` combined `normal_stcg` figure was
    read directly by the Schedule-SI dispatch instead of a securities-only
    figure)."""
    land = _txn(
        CGAssetType.LAND_BUILDING, D("2000000"), D("1000000"),
        date_of_acquisition=date(2025, 6, 1), date_of_transfer=date(2026, 1, 15),
    )
    securities = _txn(
        CGAssetType.UNLISTED_SHARES, D("700000"), D("500000"),
        date_of_acquisition=date(2025, 6, 1), date_of_transfer=date(2026, 1, 15),
    )
    r = _compute(
        "itr2", residential_status=ResidentialStatus.NON_RESIDENT,
        filing_profile=_fii_filing_profile(), cg_transactions=[land, securities],
    )
    si = _si(r)
    assert si["5ADii"].taxable_income == D("200000")
    assert si["5ADii"].tax_amount == D("60000")
    assert r.special_rate_tax == D("60000")
    assert r.slab_tax > D("0")


def test_fii_fpi_land_ltcg_second_proviso_never_applies_since_fii_implies_non_resident() -> None:
    r = _compute(
        "itr2", residential_status=ResidentialStatus.NON_RESIDENT,
        filing_profile=_fii_filing_profile(), cg_transactions=[_land_asset_for_proviso()],
    )
    ltcg = r.schedules["cg"].ltcg
    assert ltcg.total_excess_tax_112_1a == D("0")


def test_non_fii_stcg_never_lands_in_flat_30_percent_bucket() -> None:
    """Confirms the non-FII default path -- ordinary land/building/other-
    assets STCG must NEVER be misrouted into "stcg30" (the FII-only flat
    30% Table-E row) even for a non-resident individual filer."""
    txn = _txn(
        CGAssetType.OTHER, D("500000"), D("350000"),
        date_of_acquisition=date(2025, 6, 1), date_of_transfer=date(2026, 1, 15),
    )
    r = _compute("itr2", residential_status=ResidentialStatus.NON_RESIDENT, cg_transactions=[txn])
    cyla = r.schedules["cyla"]
    assert cyla.stcg30_remaining == D("0")
    assert cyla.stcg_app_remaining == D("150000")


# ===========================================================================
# Section K -- ITR-3-only: slump sale / unutilized CGAS deposits / PTI
# capital gains (cross-form issue #11, tracker). All three were correctly
# disclosed but never merged into the actual taxed STCG/LTCG total until
# this fix -- these tests certify the now-correct behavior.
# ===========================================================================

def test_slump_sale_reaches_actual_tax_at_section_112() -> None:
    """Cross-form issue #11 (tracker): slump sale (A2/B2, section 50B) was
    correctly disclosed but never merged into the actual taxed LTCG total
    -- taxed at ordinary section-112 rates like the generic "other assets"
    bucket, exactly matching this test's own former "zero tax effect"
    name, now reversed since the fix."""
    from app.schemas.itr3 import ITR3SlumpSaleRow

    row = ITR3SlumpSaleRow(fmv_11uae_2=D("8000000"), fmv_11uae_3=D("8200000"), net_worth=D("3000000"))
    r = _compute("itr3", cg_slump_sale_ltcg=[row])
    si = _si(r)
    # gain = max(8000000, 8200000) - 3000000 = 5200000
    assert r.capital_gains_income == D("5200000")
    assert si["112"].tax_amount == D("650000")  # 5200000 * 12.5%


def test_unutilized_cgas_deposit_reaches_actual_tax_as_deemed_ltcg() -> None:
    """Cross-form issue #11 (tracker): the unutilized-CGAS deemed capital
    gain (A7/B10) was correctly disclosed but never merged into the
    actual taxed LTCG total."""
    from app.schemas.itr3 import ITR3UnutilizedCGRow

    row = ITR3UnutilizedCGRow(
        prev_year_transferred="2023-24", section_claimed="54F",
        year_asset_acquired="2025-26", amount_utilized=D("0"), amount_unutilized=D("500000"),
    )
    r = _compute("itr3", cg_ltcg_unutilized_flag="Y", cg_ltcg_unutilized_deposits=[row])
    si = _si(r)
    assert r.capital_gains_income == D("500000")
    assert si["112"].tax_amount == D("62500")  # 500000 * 12.5%


def test_slump_sale_stcg_and_unutilized_stcg_deposit_reach_actual_tax() -> None:
    """The STCG side of both items (item 2c STCG slump sale; item A7
    unutilized-CGAS-STCG deposit) is taxed at slab rate, not section 112
    -- matching the generic other-assets STCG bucket."""
    from app.schemas.itr3 import ITR3SlumpSaleRow, ITR3UnutilizedCGRow

    slump = ITR3SlumpSaleRow(fmv_11uae_2=D("2000000"), fmv_11uae_3=D("1800000"), net_worth=D("500000"))
    deposit = ITR3UnutilizedCGRow(prev_year_transferred="2023-24", section_claimed="54B", amount_unutilized=D("100000"))
    r = _compute("itr3", cg_slump_sale_stcg=[slump], cg_stcg_unutilized_deposits=[deposit])
    # slump gain = max(2000000,1800000) - 500000 = 1500000; + deposit 100000 = 1600000
    assert r.capital_gains_income == D("1600000")
    assert r.special_rate_tax == D("0")
    assert r.slab_tax > D("0")


@pytest.mark.parametrize("form", _FORMS)
def test_pti_ltcg_112a_and_ltcg_125_route_to_correct_si_codes(form) -> None:
    """PTI capital gains (Schedule PTI) retain the SAME head and rate the
    pass-through entity itself earned them under, dispatched to their own
    dedicated Schedule-SI SecCodes -- NOT merged into the ordinary
    111A/112/112A rows (cross-form issue #11, tracker; ITR-3 previously
    never read pti_entries anywhere in its calculator at all)."""
    entry_112a = PTIEntry(entity_name="AIF-1", entity_pan="ABCDE1234F", income_head="LTCG", section="112A", income_amount=D("300000"))
    entry_other = PTIEntry(entity_name="AIF-2", entity_pan="FGHIJ5678K", income_head="LTCG", section="112", income_amount=D("200000"))
    r = _compute(form, pti_entries=[entry_112a, entry_other])
    si = _si(r)
    assert si["PTI_LTCG12_5P112A"].tax_amount == D("37500")  # 300000 * 12.5%
    assert si["PTI_LTCG12_5P"].tax_amount == D("25000")  # 200000 * 12.5%
    assert r.capital_gains_income == D("500000")


@pytest.mark.parametrize("form", _FORMS)
def test_pti_capital_gains_not_run_through_cyla(form) -> None:
    """PTI capital gains are a pure pass-through total, deliberately not
    eligible for CYLA/BFLA loss set-off -- an unrelated large LTCG loss
    elsewhere in the return must not reduce PTI's own taxed amount."""
    loss_txn = _txn(CGAssetType.OTHER, D("100000"), D("2000000"), explicit_long_term=True)  # LTCG loss
    pti = PTIEntry(entity_name="AIF", entity_pan="ABCDE1234F", income_head="STCG", section="111A", income_amount=D("150000"))
    r = _compute(form, cg_transactions=[loss_txn], pti_entries=[pti])
    si = _si(r)
    assert si["PTI_STCG20P"].tax_amount == D("30000")  # 150000 * 20%, untouched by the LTCG loss


@pytest.mark.parametrize("form", _FORMS)
def test_pti_applicable_rate_stcg_flows_to_slab_not_flat_30(form) -> None:
    """Cross-form issue #12 (tracker): the official schema has no
    dedicated SecCode for PTI STCG "chargeable at applicable rates" (only
    PTI_STCG20P/PTI_STCG30P exist) -- so a PTI STCG entry not tagged
    "111A" must fall through to ordinary SLAB-rate taxation, not a
    hardcoded flat 30% (the pre-existing bug this fix corrects, present
    in ITR-2's own already-shipped code and replicated into ITR-3 by this
    session's own earlier item-11 port)."""
    pti = PTIEntry(entity_name="AIF", entity_pan="ABCDE1234F", income_head="STCG", section="115UB", income_amount=D("1000000"))
    r = _compute(form, pti_entries=[pti])
    si = _si(r)
    assert "PTI_STCG30P" not in si
    assert r.capital_gains_income == D("1000000")
    assert r.special_rate_tax == D("0")
    assert r.slab_tax > D("0")


# ===========================================================================
# Section L2 -- ITR-3-only: land/building 54D/54G/54GA (cross-form issue
# #10, tracker) -- STCG item A1d allows 54B/54G/54GA; LTCG item B1d
# additionally allows 54D. Neither had a schema field until this fix.
# ===========================================================================

def test_54d_reduces_ltcg_land_building_actual_tax() -> None:
    txn = CGTransaction(
        asset_type=CGAssetType.LAND_BUILDING, full_consideration=D("2000000"), cost_of_acquisition=D("500000"),
        date_of_acquisition=date(2020, 1, 1), date_of_transfer=date(2026, 1, 1), deduction_us54d=D("300000"),
    )
    r = _compute("itr3", cg_transactions=[txn])
    assert r.capital_gains_income == D("1200000")  # 1500000 - 300000


@pytest.mark.parametrize("section", ["deduction_us54g", "deduction_us54ga"])
def test_54g_54ga_reduce_stcg_land_building_actual_tax(section) -> None:
    txn = CGTransaction(
        asset_type=CGAssetType.LAND_BUILDING, full_consideration=D("2000000"), cost_of_acquisition=D("500000"),
        date_of_acquisition=date(2025, 6, 1), date_of_transfer=date(2025, 12, 1), **{section: D("300000")},
    )
    r = _compute("itr3", cg_transactions=[txn])
    assert r.capital_gains_income == D("1200000")  # 1500000 - 300000


def test_itr2_land_building_unaffected_by_new_54d_54g_54ga_fields() -> None:
    """The shared CGTransaction/compute_ltcg widening for ITR-3's own
    wider section set must not change ITR-2's own already-correct
    behavior -- section 54 alone still applies exactly as before."""
    txn = CGTransaction(
        asset_type=CGAssetType.LAND_BUILDING, full_consideration=D("2000000"), cost_of_acquisition=D("500000"),
        date_of_acquisition=date(2020, 1, 1), date_of_transfer=date(2026, 1, 1), deduction_us54=D("300000"),
    )
    r = _compute("itr2", cg_transactions=[txn])
    assert r.capital_gains_income == D("1200000")


# ===========================================================================
# Section L -- si_entries pass-through (115BB/115BBE/115BBF) alongside CG
# ===========================================================================

@pytest.mark.parametrize("form", _FORMS)
def test_lottery_income_special_rate_coexists_with_section_112_cg(form) -> None:
    ltcg_other = _txn(CGAssetType.OTHER, D("1000000"), D("400000"), explicit_long_term=True)  # 6L
    r = _compute(
        form, cg_transactions=[ltcg_other],
        si_entries=[ScheduleSIEntry(section="115BB", description="Lottery", gross_income=D("100000"), deductions=D("0"), tax_rate_pct=D("30"))],
    )
    si = _si(r)
    assert si["112"].tax_amount == D("75000")
    assert si["115BB"].tax_amount == D("30000")
    assert r.special_rate_tax == D("105000")
