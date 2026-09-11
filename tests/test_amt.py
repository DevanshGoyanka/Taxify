"""Unit tests for AMT (Alternate Minimum Tax u/s 115JC) schedule."""

from decimal import Decimal
from app.engine.schedules.amt import AMT_RATE, compute, compute_amtc
from app.schemas.itr2 import AMTCreditItem


def test_amt_no_triggers():
    result = compute(
        total_income=Decimal("1000000"),
        total_tax_before_cess=Decimal("150000"),
        deductions_triggers={},
        regime="old",
        age_bracket="BELOW_60",
    )
    assert result.amt_applicable is False
    assert result.final_tax == Decimal("150000")


def test_amt_applies_when_higher():
    """AMT = 18.5% of (TI + 80-IA) + surcharge + cess."""
    deductions = {"80-IA": Decimal("500000")}
    # TI = 16L, ATI = 21L (> ₹20L threshold), AMT before cess = 21L * 18.5% = 388,500
    result = compute(
        total_income=Decimal("1600000"),
        total_tax_before_cess=Decimal("100000"),  # regular tax very low
        deductions_triggers=deductions,
        regime="old",
        age_bracket="BELOW_60",
    )
    assert result.amt_applicable is True
    assert result.adjusted_total_income == Decimal("2100000")
    assert result.amt_credit > 0


def test_amt_does_not_apply_when_regular_higher():
    deductions = {"80-IA": Decimal("200000")}
    result = compute(
        total_income=Decimal("2000000"),
        total_tax_before_cess=Decimal("500000"),
        deductions_triggers=deductions,
        regime="old",
        age_bracket="BELOW_60",
    )
    assert result.amt_applicable is False


def test_amt_not_in_new_regime():
    deductions = {"80-IA": Decimal("500000")}
    result = compute(
        total_income=Decimal("1000000"),
        total_tax_before_cess=Decimal("100000"),
        deductions_triggers=deductions,
        regime="new",
        age_bracket="BELOW_60",
    )
    assert result.amt_applicable is False
    assert result.final_tax == Decimal("100000")


def test_amt_rate():
    assert AMT_RATE == Decimal("0.185")


# ─── Phase 6i-4: chapter_xii_ba_applicable ──────────────────────────────────

def test_chapter_applicable_true_when_amt_does_not_bind():
    """The 115JC comparison is genuinely made (and Schedule AMTC's own Sl.1-3
    need real figures) whenever qualifying deductions/old-regime/ATI>20L
    hold -- regardless of whether AMT actually wins the comparison."""
    result = compute(
        total_income=Decimal("2000000"),
        total_tax_before_cess=Decimal("500000"),
        deductions_triggers={"80-IA": Decimal("200000")},
        regime="old",
        age_bracket="BELOW_60",
    )
    assert result.amt_applicable is False
    assert result.chapter_xii_ba_applicable is True


def test_chapter_applicable_false_on_base_result():
    """No addback, new regime, or ATI at/below the threshold -- the chapter
    is not "in play" at all, distinct from being in play but not binding."""
    no_addback = compute(
        total_income=Decimal("3000000"), total_tax_before_cess=Decimal("500000"),
        deductions_triggers={}, regime="old", age_bracket="BELOW_60",
    )
    assert no_addback.chapter_xii_ba_applicable is False

    new_regime = compute(
        total_income=Decimal("3000000"), total_tax_before_cess=Decimal("500000"),
        deductions_triggers={"80-IA": Decimal("500000")}, regime="new", age_bracket="BELOW_60",
    )
    assert new_regime.chapter_xii_ba_applicable is False

    below_threshold = compute(
        total_income=Decimal("1000000"), total_tax_before_cess=Decimal("50000"),
        deductions_triggers={"80-IA": Decimal("500000")}, regime="old", age_bracket="BELOW_60",
    )
    assert below_threshold.adjusted_total_income <= Decimal("2000000")
    assert below_threshold.chapter_xii_ba_applicable is False


def test_amt_applicability_comparison_uses_fully_surcharge_inclusive_regular_tax():
    """Regression for Phase 6i-4: the AMT-applicability comparison
    (amt_total > regular_tax) previously compared apples to oranges when
    the caller passed a pre-surcharge regular-tax figure with
    regular_tax_includes_cess=False (only cess got added, never surcharge)
    -- understating regular_tax and making AMT wrongly more likely to bind
    for any taxpayer where surcharge is material. The fix is entirely on
    the CALLER's side (app/engine/calculators/itr2.py now passes the
    already-fully-inclusive gross_tax_liability with
    regular_tax_includes_cess=True) -- this test proves the two calling
    conventions genuinely diverge for a real scenario, confirming the old
    convention was not merely a cosmetic difference."""
    tax_before_cess = Decimal("1612500")
    surcharge = Decimal("161250")  # 10% surcharge tier, ~60L income
    cess_on_full = (tax_before_cess + surcharge) * Decimal("0.04")
    fully_inclusive_regular_tax = tax_before_cess + surcharge + cess_on_full

    old_calling_convention = compute(
        total_income=Decimal("6000000"), total_tax_before_cess=tax_before_cess,
        deductions_triggers={"80-IA": Decimal("2108108")}, regime="old", age_bracket="BELOW_60",
        regular_tax_includes_cess=False,
    )
    new_calling_convention = compute(
        total_income=Decimal("6000000"), total_tax_before_cess=fully_inclusive_regular_tax,
        deductions_triggers={"80-IA": Decimal("2108108")}, regime="old", age_bracket="BELOW_60",
        regular_tax_includes_cess=True,
    )
    # Same amt_total either way (only the regular-tax side of the
    # comparison changes) -- but the old, surcharge-omitting convention
    # wrongly flips amt_applicable to True.
    assert old_calling_convention.amt_tax == new_calling_convention.amt_tax
    assert old_calling_convention.amt_applicable is True
    assert new_calling_convention.amt_applicable is False


# ─── Phase 6i-4: compute_amtc() -- section 115JD credit utilization ────────

def test_amtc_fully_absorbs_single_entry_within_cap():
    result = compute_amtc(
        [AMTCreditItem(assessment_year="2023-24", credit_brought_forward=Decimal("50000"))],
        cap=Decimal("200000"), current_ay="2026-27",
    )
    assert result.total_utilised == Decimal("50000")
    assert result.entries[0].remaining_carry_forward == Decimal("0")


def test_amtc_fifo_oldest_year_first_regardless_of_input_order():
    result = compute_amtc(
        [
            AMTCreditItem(assessment_year="2023-24", credit_brought_forward=Decimal("300000")),
            AMTCreditItem(assessment_year="2022-23", credit_brought_forward=Decimal("200000")),
        ],
        cap=Decimal("285636"), current_ay="2026-27",
    )
    by_year = {e.assessment_year: e for e in result.entries}
    assert by_year["2022-23"].utilised == Decimal("200000")
    assert by_year["2022-23"].remaining_carry_forward == Decimal("0")
    assert by_year["2023-24"].utilised == Decimal("85636")
    assert by_year["2023-24"].remaining_carry_forward == Decimal("214364")
    assert result.total_utilised == Decimal("285636")


def test_amtc_zero_cap_utilizes_nothing():
    """A year AMT binds has a utilization cap of zero (item 7 <= item 1d) --
    brought-forward credit must pass through completely unset-off."""
    result = compute_amtc(
        [AMTCreditItem(assessment_year="2023-24", credit_brought_forward=Decimal("50000"))],
        cap=Decimal("0"), current_ay="2026-27",
    )
    assert result.total_utilised == Decimal("0")
    assert result.entries[0].remaining_carry_forward == Decimal("50000")


def test_amtc_credit_older_than_15_years_expires_unset_off():
    """Section 115JD(3): 15-assessment-year carry-forward window."""
    result = compute_amtc(
        [AMTCreditItem(assessment_year="2010-11", credit_brought_forward=Decimal("50000"))],
        cap=Decimal("200000"), current_ay="2026-27",
    )
    assert result.entries[0].expired is True
    assert result.entries[0].utilised == Decimal("0")
    assert result.entries[0].remaining_carry_forward == Decimal("0")
    assert result.total_utilised == Decimal("0")


def test_amtc_credit_exactly_at_15_year_boundary_still_valid():
    """AY2011-12 to AY2026-27 is exactly 15 years -- not yet expired."""
    result = compute_amtc(
        [AMTCreditItem(assessment_year="2011-12", credit_brought_forward=Decimal("50000"))],
        cap=Decimal("200000"), current_ay="2026-27",
    )
    assert result.entries[0].expired is False
    assert result.entries[0].utilised == Decimal("50000")
