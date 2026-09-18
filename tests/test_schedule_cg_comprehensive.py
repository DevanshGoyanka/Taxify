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
    CGDtaaEntry,
    CGTransaction,
    CGAssetType,
    ITR2Input,
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
# **Two genuine, previously-undiscovered bugs surfaced while writing this
# section** (found via direct calculator calls, not assumed -- see the two
# dedicated bug-pinning tests at the end of this section). Both are
# flagged to the user, neither is fixed here:
#
# Bug 1 (ITR-3-only): `calculators/itr3.py`'s brought-forward-loss list
# construction does `"head": str(item.head)`, but `BFLossItem.head` is a
# `LossHead(str, Enum)` -- `str(LossHead.LONG_TERM_CAPITAL)` renders as
# `"LossHead.LONG_TERM_CAPITAL"`, not `"LTCG"`, on this Python/pydantic
# version. `bfla.py`'s own head dispatch (`elif head == "LTCG": ...`) never
# matches, so a brought-forward loss has ZERO effect on ITR-3's BFLA at
# all -- not even the GTI-level reduction, unlike Bug 2 below. ITR-2's own
# equivalent line already handles this correctly
# (`item.head.value if hasattr(item.head, "value") else str(item.head)`) --
# ITR-3's was never given the same treatment.
#
# Bug 2 (pre-existing in ITR-2, inherited unchanged by the shared
# `post_loss_cg_baskets()` extraction -- so it now also latently affects
# ITR-3, once Bug 1 above is fixed): the function reads
# `cyla.stcg20_remaining`/`cyla.stcg30_remaining`/`cyla.stcg_app_remaining`/
# `cyla.stcg_dtaa_remaining` (the PRE-BFLA, CYLA-level residual) for the
# `"111a"`/`"normal_stcg"`/`"stcg_dtaa"` post-loss buckets, but
# `bfla.ltcg125_remaining`/`bfla.ltcg_dtaa_remaining` (the POST-BFLA
# residual) for `"112"`/`"ltcg_dtaa"`. A brought-forward STCG-head loss
# absorbed into an STCG-rate bucket (111A/normal-rate/DTAA) is therefore
# correctly reflected in `bfla.stcg20_remaining` etc. and in the
# GTI-level `r.bfla_total_set_off` subtraction, but INVISIBLE to Schedule
# SI's own special-rate tax computation for that bucket -- the disclosed
# "loss set off" amount and the actual special-rate tax charged silently
# diverge. Brought-forward losses absorbed into an LTCG-rate bucket are
# unaffected (that side already reads the correct post-BFLA value).
# ===========================================================================

def test_itr3_bfla_never_applies_any_brought_forward_loss_str_enum_bug() -> None:
    """Bug 1, pinned: an ordinary LTCG-head brought-forward loss, which
    ITR-2 (this exact scenario) correctly absorbs, has ZERO effect for
    ITR-3 today."""
    bf = BFLossItem(assessment_year="2024-25", head="LTCG", sub_category="LTCG", original_loss=D("300000"), brought_forward=D("300000"))
    txn = _txn(CGAssetType.OTHER, D("1000000"), D("400000"), explicit_long_term=True)  # 6L LTCG
    r2 = _compute("itr2", cg_transactions=[txn], bf_losses=[bf])
    r3 = _compute("itr3", cg_transactions=[txn], bf_losses=[bf])
    assert r2.bfla_total_set_off == D("300000")
    assert r3.bfla_total_set_off == D("0")  # BUG: should also be 300000
    bfla3 = r3.schedules["bfla"]
    assert bfla3.entries[0].head == "LossHead.LONG_TERM_CAPITAL"  # the literal str(enum) artifact
    assert bfla3.entries[0].set_off_this_year == D("0")


@pytest.mark.parametrize("form", _FORMS)
def test_brought_forward_expired_loss_after_8_years_never_applies(form) -> None:
    """Section 74's 8-year carry-forward limit -- an AY2016-17 LTCG loss
    is expired for AY2026-27 (10 years old) and must not reduce anything.
    (For ITR-3, this passes for the same reason Bug 1 above makes ANY
    brought-forward loss inert -- not confirmation the expiry LOGIC itself
    runs correctly for ITR-3; the dedicated bug-pin test above is the
    honest signal for that.)"""
    bf = BFLossItem(assessment_year="2016-17", head="LTCG", sub_category="LTCG", original_loss=D("500000"), brought_forward=D("500000"))
    txn = _txn(CGAssetType.OTHER, D("1000000"), D("400000"), explicit_long_term=True)  # 6L LTCG
    r = _compute(form, cg_transactions=[txn], bf_losses=[bf])
    assert r.bfla_total_set_off == D("0")
    post_loss_cg = r.schedules["post_loss_cg"]
    assert post_loss_cg["112"] == D("600000")  # fully untouched -- expired, not applied


def test_itr2_brought_forward_ltcg_loss_reduces_current_year_section_112() -> None:
    """The LTCG side works correctly on ITR-2 today (its own bucket
    correctly reads the post-BFLA value) -- the baseline Bug 2's own
    docstring above contrasts against."""
    bf = BFLossItem(assessment_year="2024-25", head="LTCG", sub_category="LTCG", original_loss=D("300000"), brought_forward=D("300000"))
    txn = _txn(CGAssetType.OTHER, D("1000000"), D("400000"), explicit_long_term=True)  # 6L LTCG
    r = _compute("itr2", cg_transactions=[txn], bf_losses=[bf])
    assert r.bfla_total_set_off == D("300000")
    post_loss_cg = r.schedules["post_loss_cg"]
    assert post_loss_cg["112"] == D("300000")
    si = _si(r)
    assert si["112"].taxable_income == D("300000")
    assert si["112"].tax_amount == D("37500")


def test_itr2_bfla_stcg_bucket_correctly_reduced_but_schedule_si_stays_stale_bug() -> None:
    """Bug 2, pinned: `bfla.stcg20_remaining` (the BFLA schedule's own,
    correct output) shows the 111A bucket reduced by the brought-forward
    STCG loss, but `post_loss_cg["111a"]`/Schedule SI's own 111A row --
    what actually drives the special-rate TAX -- still uses the STALE,
    pre-BFLA CYLA-level figure. The disclosed loss set-off and the actual
    tax charged silently diverge."""
    bf = BFLossItem(assessment_year="2024-25", head="STCG", sub_category="STCG", original_loss=D("100000"), brought_forward=D("100000"))
    stcg_111a = _txn(CGAssetType.LISTED_EQUITY_111A, D("500000"), D("100000"), explicit_long_term=False)  # 4L
    r = _compute("itr2", cg_transactions=[stcg_111a], bf_losses=[bf])
    assert r.bfla_total_set_off == D("100000")  # BFLA itself correctly recorded the set-off
    bfla = r.schedules["bfla"]
    assert bfla.stcg20_remaining == D("300000")  # BFLA's OWN output is correct: 400,000 - 100,000
    si = _si(r)
    # BUG: Schedule SI's own 111A row is still built from the pre-BFLA
    # (CYLA-level) 400,000, not BFLA's correct 300,000 -- si["111A"] is
    # OVERTAXED by the un-applied brought-forward loss.
    assert si["111A"].taxable_income == D("400000")


# ===========================================================================
# Section F -- exemptions (54/54B/54EC/54F) ordering and capping
# ===========================================================================

def test_itr2_54b_on_stcg_land_reduces_stcg_not_ltcg() -> None:
    """Section 54B is the ONLY exemption STCG land/building may claim, and
    it must reduce THAT bucket first, not simply flow to LTCG."""
    stcg_land = _txn(
        CGAssetType.LAND_BUILDING, D("2000000"), D("1000000"),
        date_of_acquisition=date(2025, 6, 1), date_of_transfer=date(2025, 12, 1),
        deduction_us54b=D("400000"),
    )  # 10L gain, 4L exemption -> 6L taxable, slab rate
    ltcg_other = _txn(CGAssetType.OTHER, D("1000000"), D("400000"), explicit_long_term=True)  # 6L LTCG, no exemption
    r = _compute("itr2", cg_transactions=[stcg_land, ltcg_other])
    post_loss_cg = r.schedules["post_loss_cg"]
    assert post_loss_cg["normal_stcg"] == D("600000")  # 1,000,000 - 400,000
    assert post_loss_cg["112"] == D("600000")  # untouched by the 54B claim


def test_itr3_54b_on_stcg_land_never_applied_at_all_bug() -> None:
    """Bug 3, pinned, ITR-3-only: the IDENTICAL scenario as the ITR-2 test
    above produces a DIFFERENT result on ITR-3 -- the section 54B claim on
    a short-term land/building sale has ZERO tax effect. Root cause,
    confirmed by direct code reading, is two-fold: (1) `calculators/
    itr3.py`'s transaction loop only accumulates `exempt_54*` legacy
    scalars in the LONG-term land/building branch (`else:` after
    `if is_short:`) -- the short-term branch (`stcg_land_cg.append(asset)`)
    never reads `tx.deduction_us54b` at all; (2) separately, the `CGAsset`
    this loop constructs never populates `.exemptions` either (a narrower,
    already-flagged disclosure-precision gap, tracked in
    `Docs/ITR3_SCHEDULE_IMPLEMENTATION_TRACKER.md`'s cross-form-issues
    section), so even the OTHER exemption-total mechanism
    (`stcg_land_54b = sum(asset.exemption_total ...)` in
    `post_loss_cg_baskets()`) is also a dead end for ITR-3. A resident
    taxpayer claiming 54B against short-term agricultural-land gain on
    ITR-3 today gets NO tax benefit from that claim whatsoever."""
    stcg_land = _txn(
        CGAssetType.LAND_BUILDING, D("2000000"), D("1000000"),
        date_of_acquisition=date(2025, 6, 1), date_of_transfer=date(2025, 12, 1),
        deduction_us54b=D("400000"),
    )
    r = _compute("itr3", cg_transactions=[stcg_land])
    post_loss_cg = r.schedules["post_loss_cg"]
    assert post_loss_cg["normal_stcg"] == D("1000000")  # BUG: should be 600,000 (1,000,000 - 400,000)


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


def test_itr2_leftover_54_exemption_after_stcg_reduces_ltcg() -> None:
    """Any 54B exemption pool NOT fully consumed by STCG land carries over
    to reduce LTCG (the remaining-pool consumption chain). (ITR-2 only --
    see `test_itr3_54b_on_stcg_land_never_applied_at_all_bug` above for
    why ITR-3 cannot demonstrate this today.)"""
    stcg_land = _txn(
        CGAssetType.LAND_BUILDING, D("500000"), D("400000"),
        date_of_acquisition=date(2025, 6, 1), date_of_transfer=date(2025, 12, 1),
        deduction_us54b=D("300000"),
    )  # 1L gain, but 3L claimed -- only 1L actually usable here
    r = _compute("itr2", cg_transactions=[stcg_land])
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


def test_fii_fpi_other_stcg_uses_flat_30_percent_bucket() -> None:
    txn = _txn(
        CGAssetType.OTHER, D("500000"), D("350000"),
        date_of_acquisition=date(2025, 6, 1), date_of_transfer=date(2026, 1, 15),
    )
    r = _compute(
        "itr2", residential_status=ResidentialStatus.NON_RESIDENT,
        filing_profile=_fii_filing_profile(), cg_transactions=[txn],
    )
    cyla = r.schedules["cyla"]
    assert cyla.stcg30_remaining == D("150000")
    assert cyla.stcg_app_remaining == D("0")


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
# Section K -- ITR-3-only: slump sale / unutilized CGAS deposits
# (documented as DISCLOSURE-ONLY today -- confirmed by direct grep that
# neither `cg_slump_sale_*` nor `cg_*_unutilized_*` is read anywhere in
# `app/engine/calculators/itr3.py`. This is a real, found-but-not-fixed
# gap, flagged to the user rather than silently treated as working; these
# tests exist to PIN today's actual behavior, not to certify it correct.)
# ===========================================================================

def test_slump_sale_currently_has_zero_tax_effect_disclosure_only() -> None:
    from app.schemas.itr3 import ITR3SlumpSaleRow

    row = ITR3SlumpSaleRow(fmv_11uae_2=D("8000000"), fmv_11uae_3=D("8200000"), net_worth=D("3000000"))
    r = _compute("itr3", cg_slump_sale_ltcg=[row])
    assert r.capital_gains_income == D("0")
    assert r.special_rate_tax == D("0")
    assert r.slab_tax == D("0")


def test_unutilized_cgas_deposit_currently_has_zero_tax_effect_disclosure_only() -> None:
    from app.schemas.itr3 import ITR3UnutilizedCGRow

    row = ITR3UnutilizedCGRow(
        prev_year_transferred="2023-24", section_claimed="54F",
        year_asset_acquired="2025-26", amount_utilized=D("0"), amount_unutilized=D("500000"),
    )
    r = _compute("itr3", cg_ltcg_unutilized_flag="Y", cg_ltcg_unutilized_deposits=[row])
    assert r.capital_gains_income == D("0")
    assert r.special_rate_tax == D("0")


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
