"""Focused regressions for AY 2026-27 capital gains and loss set-off."""

from decimal import Decimal

from app.engine.schedules.capital_gains import (
    CG112AAsset,
    CGAsset,
    VDAEntry,
    aggregate,
    compute_112a,
    compute_ltcg,
    compute_stcg,
    compute_vda,
)
from app.engine.schedules.loss_setoff.bfla import BFLAInput, compute as compute_bfla
from app.engine.schedules.loss_setoff.cfl import CFLResult, CFLossEntry, compute as compute_cfl
from app.engine.schedules.loss_setoff.cyla import CYLAInput, compute as compute_cyla

D = Decimal


def test_112a_grandfathering_is_eligible_only_and_never_below_cost() -> None:
    eligible = CG112AAsset(
        total_sale_value=D("120"), cost_acq_without_index=D("100"), total_fmv=D("80"),
        date_of_acquisition="2017-01-01",
    )
    ineligible = CG112AAsset(
        total_sale_value=D("120"), cost_acq_without_index=D("50"), total_fmv=D("100"),
        date_of_acquisition="2019-01-01",
    )
    gain, exemption, taxable = compute_112a([eligible, ineligible])
    assert gain == D("90")
    assert exemption == D("90")
    assert taxable == D("0")


def test_112a_retains_scrip_losses_and_applies_threshold_once() -> None:
    gain, exemption, taxable = compute_112a([
        CG112AAsset(total_sale_value=D("300000"), cost_acq_without_index=D("100000")),
        CG112AAsset(total_sale_value=D("50000"), cost_acq_without_index=D("100000")),
    ])
    assert gain == D("150000")
    assert exemption == D("125000")
    assert taxable == D("25000")


def test_signed_baskets_and_vda_loss_isolation() -> None:
    stcg = compute_stcg(stcg_111a=D("-50000"), stcg_land_building=[CGAsset(full_consideration=D("20"), acquisition_cost=D("30"))])
    ltcg = compute_ltcg(ltcg_other=D("10000"))
    vda = compute_vda([
        # VDA loss cannot absorb the profitable transaction.
        VDAEntry(acquisition_cost=D("100"), consideration_received=D("20")),
        VDAEntry(acquisition_cost=D("20"), consideration_received=D("100")),
    ])
    result = aggregate(stcg, ltcg, vda)
    assert stcg.total_stcg == D("-50010")
    assert result.current_year_losses.total_cg_loss == D("50010")
    assert vda == D("80")
    assert result.total_capital_gains == D("80")


def test_ltcg_loss_cannot_absorb_stcg_income() -> None:
    result = aggregate(compute_stcg(stcg_111a=D("100")), compute_ltcg(ltcg_other=D("-80")))
    assert result.total_capital_gains == D("100")
    assert result.current_year_losses.ltcg125_loss == D("80")


def test_cyla_does_not_double_consume_capital_gain_pool() -> None:
    # 80 STCL absorbs 50 LTCG income (net basket), leaving 30 STCL unabsorbed
    result = compute_cyla(CYLAInput(
        stcg30_income=D("-80"), ltcg125_income=D("50"), non_salary_income=D("100")))
    assert result.total_loss_remaining == D("30")
    assert result.ltcg125_remaining == D("0")


def test_bfla_stcg_then_ltcg_uses_distinct_remaining_pools() -> None:
    result = compute_bfla(BFLAInput(
        stcg30_income=D("40"), ltcg125_income=D("60"),
        bf_losses=[
            {"assessment_year": "2022-23", "head": "STCG", "brought_forward": D("70")},
            {"assessment_year": "2023-24", "head": "LTCG", "brought_forward": D("50")},
        ],
    ))
    assert result.cg_setoff == D("100")
    assert result.stcg30_remaining == D("0")
    assert result.ltcg125_remaining == D("0")


def test_bfla_expired_loss_is_not_carried_forward() -> None:
    result = compute_bfla(BFLAInput(current_ay="2026-27", hp_income=D("100"), bf_losses=[
        {"assessment_year": "2016-17", "head": "HP", "brought_forward": D("90")},
    ]))
    assert result.entries[0].sub_category == "EXPIRED"
    assert result.entries[0].remaining_carry_forward == D("0")
    assert result.total_bf_remaining == D("0")


def test_cfl_is_typed_and_computes_expiry_ay() -> None:
    result = compute_cfl(cyla_remaining=D("40"), head="STCG", assessment_year="2026-27", original_loss=D("40"))
    assert isinstance(result, CFLResult)
    assert isinstance(result.entries[0], CFLossEntry)
    assert result.entries[0].expiry_ay == "2034-35"
    assert result.entries[0].years_remaining == 8
