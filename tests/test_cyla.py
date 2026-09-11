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


def test_cyla_racehorse_profit_fully_absorbs_smaller_os_loss():
    """CBDT rule #267: normal OS loss (e.g. a machinery/plant-letting net
    loss) is set off first against race-horse profit -- confirmed by the
    official schema reserving OthSrcLossNoRaceHorseSetoff only on the
    OthSrcRaceHorse row, not OthSrcExclRaceHorse."""
    inp = CYLAInput(
        racehorse_income=D("50000"),
        os_loss=D("20000"),
        non_salary_income=D("50000"),
    )
    result = compute(inp)
    assert result.racehorse_setoff == D("20000")
    assert result.racehorse_remaining == D("30000")
    assert result.os_loss_total == D("20000")
    assert result.os_loss_setoff_total == D("20000")
    assert result.os_loss_remaining == D("0")
    assert result.total_loss_set_off == D("20000")


def test_cyla_os_loss_exceeding_racehorse_profit_cascades_cross_head():
    """Any non-racehorse OS loss race-horse profit can't fully absorb
    cascades cross-head (section 71) -- real income that could statutorily
    be set off elsewhere, not just quarantined against race-horse profit."""
    inp = CYLAInput(
        racehorse_income=D("10000"),
        os_loss=D("90000"),
        hp_income=D("30000"),
        ltcg125_income=D("25000"),
        non_salary_income=D("15000"),
    )
    result = compute(inp)
    assert result.racehorse_setoff == D("10000")
    assert result.racehorse_remaining == D("0")
    # other_pool (seeded from non_salary_income=15000) is first drained by
    # racehorse_setoff (10000) since it already counted that racehorse
    # profit as available capacity -- leaving 5000 for the "other" leg of
    # the cross-head cascade below. Remaining 80000 (90000-10000) cascades
    # hp -> cg -> other: 30000 (hp) + 25000 (cg/ltcg125) + 5000 (other) = 60000.
    assert result.os_loss_setoff_total == D("70000")
    assert result.os_loss_remaining == D("20000")
    assert result.ltcg125_remaining == D("0")
    assert result.total_loss_set_off == D("70000")
    assert result.total_loss_remaining == D("20000")


def test_cyla_os_loss_with_no_racehorse_income_lapses_unabsorbed():
    """With no income anywhere to absorb it, a normal OS loss simply
    lapses -- no carry-forward exists for non-racehorse OS loss under the
    Act, unlike race-horse's own loss (section 74A)."""
    inp = CYLAInput(os_loss=D("15000"))
    result = compute(inp)
    assert result.racehorse_setoff == D("0")
    assert result.os_loss_setoff_total == D("0")
    assert result.os_loss_remaining == D("15000")
    assert result.total_loss_set_off == D("0")
    assert result.total_loss_remaining == D("15000")
    # Recorded under head "OS" so the calculator's CFL-conversion filter
    # (only HP/STCG/LTCG convert) correctly excludes it -- non-racehorse OS
    # loss does not carry forward.
    os_entries = [e for e in result.entries if e.head == "OS"]
    assert len(os_entries) == 1
    assert os_entries[0].remaining_loss == D("15000")


def test_cyla_no_os_loss_or_racehorse_income_is_a_no_op():
    inp = CYLAInput(non_salary_income=D("100000"))
    result = compute(inp)
    assert result.racehorse_setoff == D("0")
    assert result.racehorse_remaining == D("0")
    assert result.os_loss_total == D("0")
    assert result.os_loss_setoff_total == D("0")
    assert result.os_loss_remaining == D("0")
    assert not [e for e in result.entries if e.head == "OS"]
