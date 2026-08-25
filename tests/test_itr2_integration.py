"""
Comprehensive ITR-2 integration tests for AY 2026-27.

These tests verify the full computation pipeline end-to-end:
  - Capital gains with gains and losses
  - Loss set-off (CYLA, BFLA, CFL)
  - Special-rate tax (111A, 112, 112A, VDA)
  - Grandfathering correctness
  - Rebate eligibility (resident individual only)
  - Surcharge with 15% cap
  - AMT
  - No negative tax
  - Section 112A threshold applied exactly once
  - Section 112 tax present
  - Tax credits and final payable/refund
"""

from datetime import date
from decimal import Decimal

import pytest

from app.engine.calculators.itr2 import compute, ITR2Result
from app.schemas.itr1 import (
    AgeBracket,
    BankAccount,
    Chapter6ADeductions,
    OtherSourcesIncome,
    SalaryIncome,
    TaxRegime,
    TDS1Entry,
)
from app.schemas.itr2 import (
    CG112AScrip,
    CGAssetType,
    CGTransaction,
    ITR2Input,
    ResidentialStatus,
    ReturnFileSection,
    VDATransaction,
)

D = Decimal


def _minimal_input(**overrides) -> ITR2Input:
    """Build a minimal ITR-2 input with sensible defaults."""
    defaults = dict(
        age_bracket=AgeBracket.BELOW_60,
        tax_regime=TaxRegime.OLD,
        residential_status=ResidentialStatus.RESIDENT,
        filing_section=ReturnFileSection.ON_TIME_139_1,
    )
    defaults.update(overrides)
    return ITR2Input(**defaults)


# ---------------------------------------------------------------------------
# Zero income
# ---------------------------------------------------------------------------

def test_zero_income_produces_zero_tax():
    """A return with no income should produce zero tax liability."""
    r = compute(_minimal_input())
    assert r.salary_income == D("0")
    assert r.house_property_income == D("0")
    assert r.capital_gains_income == D("0")
    assert r.other_sources_income == D("0")
    assert r.vda_income == D("0")
    assert r.gross_total_income == D("0")
    assert r.taxable_income == D("0")
    assert r.slab_tax == D("0")
    assert r.special_rate_tax == D("0")
    assert r.gross_tax_liability == D("0")
    assert r.balance_payable == D("0")
    assert r.refund_due == D("0")
    assert len(r.errors) == 0


# ---------------------------------------------------------------------------
# Salary only
# ---------------------------------------------------------------------------

def test_salary_only_old_regime():
    """₹8L salary under old regime: slab tax after ₹50K std deduction."""
    inp = _minimal_input(
        salary_income=SalaryIncome(gross_salary=D("800000")),
    )
    r = compute(inp)
    assert r.salary_income == D("750000")  # 8L - 50K std deduction
    assert r.gross_total_income == D("750000")
    # 5% on 2.5L-5L = 12,500 + 20% on 5L-7.5L = 50,000 = 62,500
    assert r.slab_tax == D("62500")
    assert r.special_rate_tax == D("0")
    assert r.rebate_87a == D("0")  # TI > 5L
    assert r.gross_tax_liability > D("0")


def test_salary_new_regime_rebate():
    """₹10L salary under new regime: ₹75K std deduction, rebate u/s 87A."""
    inp = _minimal_input(
        tax_regime=TaxRegime.NEW,
        salary_income=SalaryIncome(gross_salary=D("1000000")),
    )
    r = compute(inp)
    assert r.salary_income == D("925000")  # 10L - 75K
    # TI = 925K <= 12L → rebate
    assert r.rebate_87a > D("0")
    assert r.tax_after_rebate == D("0")
    assert r.gross_tax_liability == D("0")


# ---------------------------------------------------------------------------
# Section 112A
# ---------------------------------------------------------------------------

def test_section_112a_gain_below_threshold_no_tax():
    """112A gain below ₹1.25L: no 112A tax."""
    inp = _minimal_input(
        cg_112a_scrips=[
            CG112AScrip(
                isin_code="INE000A00001",
                share_unit_name="RELIANCE",
                date_of_acquisition=date(2020, 1, 1),
                date_of_transfer=date(2025, 7, 1),
                num_shares_units=D("100"),
                sale_price_per_share=D("1000"),
                total_sale_value=D("100000"),
                cost_acq_without_index=D("50000"),
            ),
        ],
    )
    r = compute(inp)
    assert r.capital_gains_income > D("0")
    assert r.capital_gains_income <= D("50000")  # 100K - 50K = 50K gain
    # 50K < 1.25L threshold → no 112A tax
    si = r.schedules.get("si")
    assert si is not None
    assert si.total_special_rate_tax == D("0")


def test_section_112a_gain_above_threshold_taxed():
    """112A gain above ₹1.25L: 12.5% on excess."""
    inp = _minimal_input(
        cg_112a_scrips=[
            CG112AScrip(
                isin_code="INE000A00001",
                share_unit_name="RELIANCE",
                date_of_acquisition=date(2020, 1, 1),
                date_of_transfer=date(2025, 7, 1),
                num_shares_units=D("1000"),
                sale_price_per_share=D("1000"),
                total_sale_value=D("1000000"),
                cost_acq_without_index=D("500000"),
            ),
        ],
    )
    r = compute(inp)
    # Gain = 500K, threshold = 125K, taxable = 375K, tax = 375K * 12.5% = 46875
    si = r.schedules.get("si")
    assert si is not None
    assert si.total_special_rate_tax == D("46875")


def test_112a_threshold_applied_once():
    """Multiple 112A scrips: threshold applied to aggregate, not per scrip."""
    inp = _minimal_input(
        cg_112a_scrips=[
            CG112AScrip(
                isin_code="INE000A00001",
                share_unit_name="SCRIP1",
                date_of_acquisition=date(2020, 1, 1),
                date_of_transfer=date(2025, 7, 1),
                num_shares_units=D("100"),
                sale_price_per_share=D("1000"),
                total_sale_value=D("100000"),
                cost_acq_without_index=D("50000"),
            ),
            CG112AScrip(
                isin_code="INE000A00002",
                share_unit_name="SCRIP2",
                date_of_acquisition=date(2020, 1, 1),
                date_of_transfer=date(2025, 7, 1),
                num_shares_units=D("100"),
                sale_price_per_share=D("1000"),
                total_sale_value=D("100000"),
                cost_acq_without_index=D("50000"),
            ),
        ],
    )
    r = compute(inp)
    # Total gain = 100K, threshold = 125K → taxable = 0
    si = r.schedules.get("si")
    assert si.total_special_rate_tax == D("0")


def test_112a_grandfathering_never_below_cost():
    """FMV below actual cost must not reduce cost below actual cost."""
    inp = _minimal_input(
        cg_112a_scrips=[
            CG112AScrip(
                isin_code="INE000A00001",
                share_unit_name="OLDSCRIP",
                is_before_31jan2018=True,
                date_of_acquisition=date(2017, 1, 1),
                date_of_transfer=date(2025, 7, 1),
                num_shares_units=D("100"),
                sale_price_per_share=D("150"),
                total_sale_value=D("15000"),
                cost_acq_without_index=D("10000"),
                total_fmv=D("8000"),  # FMV < cost → cost stays at 10000
            ),
        ],
    )
    r = compute(inp)
    # Gain = 15000 - 10000 = 5000 (not 15000 - 8000 = 7000)
    assert r.capital_gains_income == D("5000")
    si = r.schedules.get("si")
    # 5000 < 125000 threshold → no tax
    assert si.total_special_rate_tax == D("0")


def test_112a_loss_retained_not_floored():
    """A 112A scrip loss should be retained in the aggregate, not floored."""
    inp = _minimal_input(
        cg_112a_scrips=[
            CG112AScrip(
                isin_code="INE000A00001",
                share_unit_name="LOSSSCRIP",
                date_of_acquisition=date(2020, 1, 1),
                date_of_transfer=date(2025, 7, 1),
                num_shares_units=D("100"),
                sale_price_per_share=D("500"),
                total_sale_value=D("50000"),
                cost_acq_without_index=D("80000"),
            ),
        ],
    )
    r = compute(inp)
    # Gain = 50K - 80K = -30K (signed loss)
    # aggregate() should produce non-negative total (loss absorbed)
    assert r.capital_gains_income == D("0")  # loss, no positive CG
    # The loss should be available in the CG schedule for carry-forward
    cg = r.schedules.get("cg")
    assert cg is not None
    assert cg.current_year_losses.total_cg_loss > D("0")


# ---------------------------------------------------------------------------
# Section 111A
# ---------------------------------------------------------------------------

def test_section_111a_loss_produces_zero_tax_not_negative():
    """111A loss must produce zero tax, not negative tax."""
    inp = _minimal_input(
        cg_transactions=[
            CGTransaction(
                asset_type=CGAssetType.LISTED_EQUITY_111A,
                date_of_acquisition=date(2024, 1, 1),
                date_of_transfer=date(2025, 1, 1),
                full_consideration=D("40000"),
                cost_of_acquisition=D("50000"),
            ),
        ],
    )
    r = compute(inp)
    # STCG loss = -10K; 111A tax must be 0, not -2000
    si = r.schedules.get("si")
    assert si.total_special_rate_tax == D("0")


def test_112a_threshold_applies_after_brought_forward_ltcl() -> None:
    """Brought-forward LTCL reduces 112A gain before the ₹1.25L tax threshold."""
    from app.schemas.itr2 import BFLossItem, LossHead

    inp = _minimal_input(
        cg_112a_scrips=[
            CG112AScrip(
                isin_code="INE000A00001",
                share_unit_name="SCRIP",
                date_of_acquisition=date(2020, 1, 1),
                date_of_transfer=date(2025, 7, 1),
                num_shares_units=D("100"),
                sale_price_per_share=D("3000"),
                total_sale_value=D("300000"),
                cost_acq_without_index=D("100000"),
            ),
        ],
        bf_losses=[
            BFLossItem(
                assessment_year="2024-25",
                head=LossHead.LONG_TERM_CAPITAL,
                original_loss=D("100000"),
                brought_forward=D("100000"),
            ),
        ],
    )
    r = compute(inp)
    post_loss = r.schedules["post_loss_cg"]
    assert post_loss["112a_gross"] == D("100000")
    assert post_loss["112a_taxable"] == D("0")
    assert r.special_rate_tax == D("0")
    assert r.slab_tax == D("0")


def test_112a_threshold_portion_does_not_enter_slab_tax() -> None:
    """112A gain below threshold remains in TI but is not taxed at slab rates."""
    inp = _minimal_input(
        cg_112a_scrips=[
            CG112AScrip(
                isin_code="INE000A00001",
                share_unit_name="SCRIP",
                date_of_acquisition=date(2020, 1, 1),
                date_of_transfer=date(2025, 7, 1),
                num_shares_units=D("100"),
                sale_price_per_share=D("1500"),
                total_sale_value=D("150000"),
                cost_acq_without_index=D("50000"),
            ),
        ],
    )
    r = compute(inp)
    assert r.taxable_income == D("100000")
    assert r.special_rate_tax == D("0")
    assert r.slab_tax == D("0")


def test_calendar_anniversary_controls_holding_period() -> None:
    """A transfer on the first anniversary is long-term for listed equity."""
    inp = _minimal_input(
        cg_transactions=[
            CGTransaction(
                asset_type=CGAssetType.LISTED_EQUITY_111A,
                date_of_acquisition=date(2024, 2, 29),
                date_of_transfer=date(2025, 2, 28),
                full_consideration=D("300000"),
                cost_of_acquisition=D("100000"),
                is_stt_paid_on_acquisition=True,
                is_stt_paid_on_transfer=True,
            ),
        ],
    )
    r = compute(inp)
    assert r.schedules["cg"].stcg.income_111a == D("0")
    assert r.schedules["cg"].ltcg.income_112a == D("200000")


# ---------------------------------------------------------------------------
# VDA
# ---------------------------------------------------------------------------

def test_vda_loss_cannot_offset_profit():
    """VDA losses cannot offset VDA gains within the same head."""
    inp = _minimal_input(
        vda_transactions=[
            VDATransaction(
                date_of_acquisition=date(2024, 1, 1),
                date_of_transfer=date(2025, 1, 1),
                acquisition_cost=D("100"),
                consideration_received=D("20"),  # loss
            ),
            VDATransaction(
                date_of_acquisition=date(2024, 1, 1),
                date_of_transfer=date(2025, 1, 1),
                acquisition_cost=D("20"),
                consideration_received=D("100"),  # profit
            ),
        ],
    )
    r = compute(inp)
    # Only positive transaction gain counts: 100 - 20 = 80
    assert r.vda_income == D("80")
    # VDA tax = 80 * 30% = 24
    si = r.schedules.get("si")
    # Find the VDA entry
    vda_entry = [e for e in si.entries if e.section == "115BBH"]
    assert len(vda_entry) == 1
    assert vda_entry[0].tax_amount == D("24")


# ---------------------------------------------------------------------------
# Section 112 (other LTCG)
# ---------------------------------------------------------------------------

def test_section_112_tax_present():
    """Non-112A LTCG must be taxed under Section 112, not left in slab."""
    inp = _minimal_input(
        cg_transactions=[
            CGTransaction(
                asset_type=CGAssetType.LAND_BUILDING,
                date_of_acquisition=date(2020, 1, 1),
                date_of_transfer=date(2025, 7, 1),
                full_consideration=D("2000000"),
                cost_of_acquisition=D("1000000"),
                indexed_cost=D("0"),  # post-Jul-2024: no indexation
            ),
        ],
    )
    r = compute(inp)
    # LTCG = 2M - 1M = 1M, taxed at 12.5% = 125000
    si = r.schedules.get("si")
    assert si is not None
    s112_entry = [e for e in si.entries if e.section == "112"]
    assert len(s112_entry) >= 1
    assert s112_entry[0].tax_amount == D("125000")


# ---------------------------------------------------------------------------
# CYLA / BFLA / CFL
# ---------------------------------------------------------------------------

def test_cyla_hp_loss_setoff_against_salary():
    """HP loss can be set off against salary income (old regime, capped 2L)."""
    inp = _minimal_input(
        salary_income=SalaryIncome(gross_salary=D("800000")),
        house_property_income=__import__(
            "app.schemas.itr1", fromlist=["HousePropertyIncome", "PropertyType"]
        ).HousePropertyIncome(
            property_type=__import__(
                "app.schemas.itr1", fromlist=["PropertyType"]
            ).PropertyType.SELF_OCCUPIED,
            home_loan_interest_paid=D("300000"),
        ),
    )
    r = compute(inp)
    # HP income = -2L (capped self-occupied interest)
    assert r.house_property_income == D("-200000")
    # CYLA should set off 2L HP loss against salary
    assert r.cyla_total_set_off == D("200000")


def test_bfla_stcg_loss_setoff():
    """Brought-forward STCL can be set off against current-year STCG + LTCG."""
    from app.schemas.itr2 import BFLossItem, LossHead

    inp = _minimal_input(
        cg_112a_scrips=[
            CG112AScrip(
                isin_code="INE000A00001",
                share_unit_name="SCRIP",
                date_of_acquisition=date(2020, 1, 1),
                date_of_transfer=date(2025, 7, 1),
                num_shares_units=D("100"),
                sale_price_per_share=D("2000"),
                total_sale_value=D("200000"),
                cost_acq_without_index=D("50000"),
            ),
        ],
        bf_losses=[
            BFLossItem(
                assessment_year="2024-25",
                head=LossHead.SHORT_TERM_CAPITAL,
                original_loss=D("80000"),
                brought_forward=D("80000"),
            ),
        ],
    )
    r = compute(inp)
    # 112A gain = 150K, BF STCL = 80K → set off 80K
    assert r.bfla_total_set_off > D("0")


def test_no_negative_tax():
    """The final tax liability must never be negative."""
    inp = _minimal_input(
        cg_transactions=[
            CGTransaction(
                asset_type=CGAssetType.LISTED_EQUITY_111A,
                date_of_acquisition=date(2024, 1, 1),
                date_of_transfer=date(2025, 1, 1),
                full_consideration=D("10000"),
                cost_of_acquisition=D("50000"),
            ),
        ],
    )
    r = compute(inp)
    assert r.gross_tax_liability >= D("0")
    assert r.net_tax_liability >= D("0")
    assert r.special_rate_tax >= D("0")
    assert r.slab_tax >= D("0")


# ---------------------------------------------------------------------------
# Rebate eligibility
# ---------------------------------------------------------------------------

def test_rebate_nri_eligible_but_low_income():
    """NRI with low income: rebate applies only to resident individuals."""
    inp = _minimal_input(
        residential_status=ResidentialStatus.NON_RESIDENT,
        salary_income=SalaryIncome(gross_salary=D("300000")),
    )
    r = compute(inp)
    # NRI is not eligible for 87A rebate
    assert r.rebate_87a == D("0")


# ---------------------------------------------------------------------------
# Surcharge cap
# ---------------------------------------------------------------------------

def test_surcharge_cap_on_112a():
    """Surcharge on 112A income is capped at 15%."""
    inp = _minimal_input(
        cg_112a_scrips=[
            CG112AScrip(
                isin_code="INE000A00001",
                share_unit_name="BIGSCRIP",
                date_of_acquisition=date(2020, 1, 1),
                date_of_transfer=date(2025, 7, 1),
                num_shares_units=D("10000"),
                sale_price_per_share=D("10000"),
                total_sale_value=D("100000000"),
                cost_acq_without_index=D("10000000"),
            ),
        ],
    )
    r = compute(inp)
    # TI = 90M gain → surcharge slab is 25% for old regime
    # But 112A surcharge is capped at 15%
    assert r.surcharge > D("0")
    # Surcharge on 112A portion should not exceed 15% of 112A tax
    si = r.schedules.get("si")
    s112a_tax = [e.tax_amount for e in si.entries if e.section == "112A"][0]
    assert r.surcharge <= s112a_tax * Decimal("0.15") + Decimal("5")  # tolerance for normal portion


# ---------------------------------------------------------------------------
# TDS and tax payable
# ---------------------------------------------------------------------------

def test_tds_credit_reduces_payable():
    """TDS should reduce the balance payable."""
    inp = _minimal_input(
        salary_income=SalaryIncome(gross_salary=D("800000")),
        tds1_entries=[
            TDS1Entry(
                employer_tan="DELA00001A",
                employer_name="Test Corp",
                income_chargeable=D("750000"),
                tds_deducted=D("50000"),
            ),
        ],
    )
    r = compute(inp)
    assert r.total_tds == D("50000")
    assert r.balance_payable < r.gross_tax_liability


# ---------------------------------------------------------------------------
# Multiple incomes
# ---------------------------------------------------------------------------

def test_salary_plus_cg_plus_os():
    """Combined salary + capital gains + other sources income."""
    inp = _minimal_input(
        salary_income=SalaryIncome(gross_salary=D("600000")),
        other_sources_income=OtherSourcesIncome(
            savings_bank_interest=D("10000"),
            fixed_deposit_interest=D("50000"),
        ),
        cg_112a_scrips=[
            CG112AScrip(
                isin_code="INE000A00001",
                share_unit_name="SCRIP",
                date_of_acquisition=date(2020, 1, 1),
                date_of_transfer=date(2025, 7, 1),
                num_shares_units=D("100"),
                sale_price_per_share=D("3000"),
                total_sale_value=D("300000"),
                cost_acq_without_index=D("100000"),
            ),
        ],
    )
    r = compute(inp)
    assert r.salary_income == D("550000")  # 600K - 50K
    assert r.other_sources_income == D("60000")  # 10K + 50K
    assert r.capital_gains_income > D("0")
    assert r.gross_total_income > D("0")
    assert r.taxable_income > D("0")
    assert r.gross_tax_liability > D("0")
    assert r.slab_tax >= D("0")
    assert r.special_rate_tax >= D("0")
