"""Unit tests for CYLA (Current Year Loss Adjustment) schedule.

Updated for the 6-sub-basket CYLA API (STCG20Per/STCG30Per/STCGAppRate/
STCGDTAARate/LTCG12_5Per/LTCGDTAARate).
"""

from decimal import Decimal
from app.engine.schedules.loss_setoff.cyla import compute, CYLAInput

D = Decimal


def test_cyla_no_losses():
    inp = CYLAInput()
    result = compute(inp)
    assert result.total_loss_set_off == D("0")
    assert result.total_loss_remaining == D("0")


def test_cyla_hp_loss_setoff():
    inp = CYLAInput(
        hp_loss=D("-150000"),
        non_salary_income=D("500000"),
    )
    result = compute(inp)
    assert result.total_loss_set_off == D("150000")
    assert result.total_loss_remaining == D("0")
    assert result.hp_setoff == D("150000")


def test_cyla_hp_loss_capped_at_2l():
    inp = CYLAInput(
        hp_loss=D("-250000"),
        non_salary_income=D("500000"),
    )
    result = compute(inp)
    assert result.hp_setoff == D("200000")
    assert result.total_loss_remaining == D("50000")


def test_cyla_stcg_loss_setoff_against_stcg_ltcg():
    inp = CYLAInput(
        stcg30_income=D("-80000"),
        ltcg125_income=D("100000"),
    )
    result = compute(inp)
    assert result.stcg30_remaining == D("0")
    assert result.ltcg125_remaining == D("20000")


def test_cyla_stcg_loss_partial_absorption():
    inp = CYLAInput(
        stcg30_income=D("-200000"),
        stcg20_income=D("30000"),
        ltcg125_income=D("20000"),
    )
    result = compute(inp)
    assert result.stcg20_remaining == D("0")
    assert result.ltcg125_remaining == D("0")
    assert result.total_loss_remaining == D("150000")


def test_cyla_ltcg_loss_setoff_only_against_ltcg():
    inp = CYLAInput(
        ltcg125_income=D("-100000"),
        stcg30_income=D("200000"),
        ltcg_dtaa_income=D("40000"),
    )
    result = compute(inp)
    # LTCL absorbs only LTCG (dtaa), not STCG
    assert result.stcg30_remaining == D("200000")
    assert result.total_loss_remaining == D("60000")


def test_cyla_non_spec_biz_loss_not_against_salary():
    inp = CYLAInput(
        non_spec_biz_loss=D("-200000"),
        hp_income=D("50000"),
        stcg30_income=D("30000"),
        ltcg125_income=D("20000"),
        spec_biz_income=D("0"),
    )
    result = compute(inp)
    assert result.non_spec_biz_setoff == D("100000")
    assert result.total_loss_remaining == D("100000")


def test_cyla_spec_biz_loss_only_against_spec():
    inp = CYLAInput(
        spec_biz_loss=D("-80000"),
        hp_income=D("50000"),
        spec_biz_income=D("30000"),
    )
    result = compute(inp)
    assert result.spec_biz_setoff == D("30000")
    assert result.total_loss_remaining == D("50000")


def test_cyla_multiple_losses():
    inp = CYLAInput(
        hp_loss=D("-100000"),
        stcg30_income=D("-50000"),
        ltcg125_income=D("-30000"),
        hp_income=D("0"),
        non_salary_income=D("100000"),
    )
    result = compute(inp)
    # STCL absorbs LTCG first, LTCL absorbs LTCG, then HP absorbs other income
    assert result.total_loss_remaining >= D("80000")
