"""Unit tests for CYLA (Current Year Loss Adjustment) schedule."""

from decimal import Decimal
from app.engine.schedules.loss_setoff.cyla import compute, CYLAInput


def test_cyla_no_losses():
    inp = CYLAInput()
    result = compute(inp)
    assert result.total_loss_set_off == Decimal("0")
    assert result.total_loss_remaining == Decimal("0")


def test_cyla_hp_loss_setoff():
    inp = CYLAInput(
        hp_loss=Decimal("-150000"),
        non_salary_income=Decimal("500000"),
    )
    result = compute(inp)
    assert result.total_loss_set_off == Decimal("150000")
    assert result.total_loss_remaining == Decimal("0")
    assert result.hp_setoff == Decimal("150000")


def test_cyla_hp_loss_capped_at_2l():
    """Self-occupied HP loss capped at Rs 2,00,000 regardless of non-salary income."""
    inp = CYLAInput(
        hp_loss=Decimal("-250000"),
        non_salary_income=Decimal("500000"),
    )
    result = compute(inp)
    assert result.hp_setoff == Decimal("200000")
    assert result.total_loss_remaining == Decimal("50000")


def test_cyla_stcg_loss_setoff_against_stcg_ltcg():
    inp = CYLAInput(
        stcg_loss=Decimal("-80000"),
        stcg_income=Decimal("50000"),
        ltcg_income=Decimal("100000"),
    )
    result = compute(inp)
    assert result.stcg_setoff == Decimal("80000")  # fully absorbed
    assert result.total_loss_remaining == Decimal("0")


def test_cyla_stcg_loss_partial_absorption():
    inp = CYLAInput(
        stcg_loss=Decimal("-200000"),
        stcg_income=Decimal("30000"),
        ltcg_income=Decimal("20000"),
    )
    result = compute(inp)
    assert result.stcg_setoff == Decimal("50000")
    assert result.total_loss_remaining == Decimal("150000")


def test_cyla_ltcg_loss_setoff_only_against_ltcg():
    inp = CYLAInput(
        ltcg_loss=Decimal("-100000"),
        stcg_income=Decimal("200000"),
        ltcg_income=Decimal("40000"),
    )
    result = compute(inp)
    assert result.ltcg_setoff == Decimal("40000")
    assert result.total_loss_remaining == Decimal("60000")


def test_cyla_non_spec_biz_loss_not_against_salary():
    """Non-speculative business loss: allowed against non-salary income only."""
    inp = CYLAInput(
        non_spec_biz_loss=Decimal("-200000"),
        hp_income=Decimal("50000"),
        stcg_income=Decimal("30000"),
        ltcg_income=Decimal("20000"),
        spec_biz_income=Decimal("0"),
    )
    result = compute(inp)
    assert result.non_spec_biz_setoff == Decimal("100000")
    assert result.total_loss_remaining == Decimal("100000")


def test_cyla_spec_biz_loss_only_against_spec():
    inp = CYLAInput(
        spec_biz_loss=Decimal("-80000"),
        hp_income=Decimal("50000"),
        spec_biz_income=Decimal("30000"),
    )
    result = compute(inp)
    assert result.spec_biz_setoff == Decimal("30000")
    assert result.total_loss_remaining == Decimal("50000")


def test_cyla_multiple_losses():
    """HP loss + STCG loss + LTCG loss all at once."""
    inp = CYLAInput(
        hp_loss=Decimal("-100000"),
        stcg_loss=Decimal("-50000"),
        ltcg_loss=Decimal("-30000"),
        hp_income=Decimal("0"),
        stcg_income=Decimal("40000"),
        ltcg_income=Decimal("60000"),
    )
    result = compute(inp)
    # HP: 100K set off
    # STCG: 50K set off against 40+60=100K CG
    # LTCG: 30K set off against 60K LTCG
    assert result.hp_setoff == Decimal("100000")
    assert result.stcg_setoff == Decimal("50000")
    assert result.ltcg_setoff == Decimal("30000")
    assert result.total_loss_set_off == Decimal("180000")
