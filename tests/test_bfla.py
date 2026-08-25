"""Unit tests for BFLA (Brought Forward Loss Adjustment) schedule.

Updated for the 6-sub-basket BFLA API (STCG20Per/STCG30Per/STCGAppRate/
STCGDTAARate/LTCG12_5Per/LTCGDTAARate).
"""

from decimal import Decimal
from app.engine.schedules.loss_setoff.bfla import compute, BFLAInput

D = Decimal


def test_bfla_no_losses():
    inp = BFLAInput(bf_losses=[])
    result = compute(inp)
    assert result.total_bf_loss_set_off == D("0")


def test_bfla_hp_loss_setoff():
    inp = BFLAInput(
        hp_income=D("150000"),
        bf_losses=[{
            "assessment_year": "2024-25",
            "head": "HP",
            "sub_category": "",
            "original_loss": D("200000"),
            "brought_forward": D("200000"),
        }],
    )
    result = compute(inp)
    assert result.total_bf_loss_set_off == D("150000")
    assert result.hp_setoff == D("150000")
    assert result.total_bf_remaining == D("50000")


def test_bfla_stcg_loss_setoff():
    inp = BFLAInput(
        stcg30_income=D("40000"),
        ltcg125_income=D("30000"),
        bf_losses=[{
            "assessment_year": "2023-24",
            "head": "STCG",
            "sub_category": "",
            "original_loss": D("100000"),
            "brought_forward": D("100000"),
        }],
    )
    result = compute(inp)
    assert result.total_bf_loss_set_off == D("70000")
    assert result.cg_setoff == D("70000")


def test_bfla_ltcg_loss_setoff_only_ltcg():
    inp = BFLAInput(
        stcg30_income=D("200000"),
        ltcg125_income=D("50000"),
        bf_losses=[{
            "assessment_year": "2022-23",
            "head": "LTCG",
            "sub_category": "",
            "original_loss": D("100000"),
            "brought_forward": D("100000"),
        }],
    )
    result = compute(inp)
    assert result.cg_setoff == D("50000")
    assert result.stcg30_remaining == D("200000")


def test_bfla_non_spec_biz_setoff():
    inp = BFLAInput(
        non_spec_biz_income=D("300000"),
        bf_losses=[{
            "assessment_year": "2021-22",
            "head": "NonSpeculative",
            "sub_category": "",
            "original_loss": D("200000"),
            "brought_forward": D("200000"),
        }],
    )
    result = compute(inp)
    assert result.biz_setoff == D("200000")
    assert result.total_bf_remaining == D("0")


def test_bfla_expired_loss_excluded():
    inp = BFLAInput(
        hp_income=D("200000"),
        current_ay="2026-27",
        bf_losses=[{
            "assessment_year": "2016-17",
            "head": "HP",
            "sub_category": "",
            "original_loss": D("100000"),
            "brought_forward": D("100000"),
        }],
    )
    result = compute(inp)
    assert result.hp_setoff == D("0")
    assert result.total_bf_loss_set_off == D("0")


def test_bfla_speculative_4_year_expiry():
    inp = BFLAInput(
        spec_biz_income=D("100000"),
        current_ay="2026-27",
        bf_losses=[{
            "assessment_year": "2021-22",
            "head": "Speculative",
            "sub_category": "",
            "original_loss": D("50000"),
            "brought_forward": D("50000"),
        }],
    )
    result = compute(inp)
    assert result.total_bf_loss_set_off == D("0")
