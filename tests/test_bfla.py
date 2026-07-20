"""Unit tests for BFLA (Brought Forward Loss Adjustment) schedule."""

from decimal import Decimal
from app.engine.schedules.loss_setoff.bfla import compute, BFLAInput


def test_bfla_no_losses():
    inp = BFLAInput(bf_losses=[])
    result = compute(inp)
    assert result.total_bf_loss_set_off == Decimal("0")


def test_bfla_hp_loss_setoff():
    inp = BFLAInput(
        hp_income=Decimal("150000"),
        bf_losses=[{
            "assessment_year": "2024-25",
            "head": "HP",
            "sub_category": "",
            "original_loss": Decimal("200000"),
            "brought_forward": Decimal("200000"),
        }],
    )
    result = compute(inp)
    assert result.total_bf_loss_set_off == Decimal("150000")
    assert result.hp_setoff == Decimal("150000")
    assert result.total_bf_remaining == Decimal("50000")


def test_bfla_stcg_loss_setoff():
    inp = BFLAInput(
        stcg_income=Decimal("40000"),
        ltcg_income=Decimal("30000"),
        bf_losses=[{
            "assessment_year": "2023-24",
            "head": "STCG",
            "sub_category": "",
            "original_loss": Decimal("100000"),
            "brought_forward": Decimal("100000"),
        }],
    )
    result = compute(inp)
    assert result.total_bf_loss_set_off == Decimal("70000")
    assert result.cg_setoff == Decimal("70000")


def test_bfla_ltcg_loss_setoff_only_ltcg():
    inp = BFLAInput(
        stcg_income=Decimal("200000"),
        ltcg_income=Decimal("50000"),
        bf_losses=[{
            "assessment_year": "2022-23",
            "head": "LTCG",
            "sub_category": "",
            "original_loss": Decimal("100000"),
            "brought_forward": Decimal("100000"),
        }],
    )
    result = compute(inp)
    assert result.cg_setoff == Decimal("50000")


def test_bfla_non_spec_biz_setoff():
    inp = BFLAInput(
        non_spec_biz_income=Decimal("300000"),
        bf_losses=[{
            "assessment_year": "2021-22",
            "head": "NonSpeculative",
            "sub_category": "",
            "original_loss": Decimal("200000"),
            "brought_forward": Decimal("200000"),
        }],
    )
    result = compute(inp)
    assert result.biz_setoff == Decimal("200000")
    assert result.total_bf_remaining == Decimal("0")


def test_bfla_expired_loss_excluded():
    """Loss from 8+ years ago should not be set off."""
    inp = BFLAInput(
        hp_income=Decimal("200000"),
        current_ay="2026-27",
        bf_losses=[{
            "assessment_year": "2016-17",
            "head": "HP",
            "sub_category": "",
            "original_loss": Decimal("100000"),
            "brought_forward": Decimal("100000"),
        }],
    )
    result = compute(inp)
    assert result.hp_setoff == Decimal("0")
    assert result.total_bf_loss_set_off == Decimal("0")


def test_bfla_speculative_4_year_expiry():
    """Speculative business loss expires after 4 years."""
    inp = BFLAInput(
        spec_biz_income=Decimal("100000"),
        current_ay="2026-27",
        bf_losses=[{
            "assessment_year": "2021-22",
            "head": "Speculative",
            "sub_category": "",
            "original_loss": Decimal("50000"),
            "brought_forward": Decimal("50000"),
        }],
    )
    result = compute(inp)
    assert result.total_bf_loss_set_off == Decimal("0")
