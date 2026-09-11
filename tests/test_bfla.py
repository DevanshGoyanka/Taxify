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


def test_bfla_racehorse_setoff_against_current_racehorse_income():
    """Section 74A(3): a brought-forward race-horse-activity loss may only
    be set off against current-year race-horse profit (post-CYLA
    remaining), never any other pool."""
    inp = BFLAInput(
        racehorse_income=D("80000"),
        current_ay="2026-27",
        bf_losses=[{
            "assessment_year": "2024-25",
            "head": "RaceHorse",
            "sub_category": "",
            "original_loss": D("50000"),
            "brought_forward": D("50000"),
        }],
    )
    result = compute(inp)
    assert result.racehorse_setoff == D("50000")
    assert result.racehorse_remaining == D("30000")
    assert result.total_bf_loss_set_off == D("50000")
    assert result.total_bf_remaining == D("0")


def test_bfla_racehorse_loss_without_current_racehorse_income_passes_through_unset_off():
    """No current-year race-horse profit to absorb against -- the loss
    simply carries forward unset-off this year (matches the pre-fix
    behaviour `test_schedule_cfl_reports_race_horse_loss_instead_of_
    dropping_it` in tests/test_itr2_itd_builder.py documents, now for the
    correctly-reasoned reason -- an explicit "RaceHorse" branch with an
    empty pool -- rather than the previous no-branch-matches accident)."""
    inp = BFLAInput(
        current_ay="2026-27",
        bf_losses=[{
            "assessment_year": "2024-25",
            "head": "RaceHorse",
            "sub_category": "",
            "original_loss": D("40000"),
            "brought_forward": D("40000"),
        }],
    )
    result = compute(inp)
    assert result.racehorse_setoff == D("0")
    assert result.total_bf_loss_set_off == D("0")
    assert result.total_bf_remaining == D("40000")


def test_bfla_racehorse_4_year_expiry():
    inp = BFLAInput(
        racehorse_income=D("100000"),
        current_ay="2026-27",
        bf_losses=[{
            "assessment_year": "2021-22",
            "head": "RaceHorse",
            "sub_category": "",
            "original_loss": D("50000"),
            "brought_forward": D("50000"),
        }],
    )
    result = compute(inp)
    assert result.racehorse_setoff == D("0")
    assert result.total_bf_loss_set_off == D("0")
