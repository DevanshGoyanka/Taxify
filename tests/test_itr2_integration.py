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
    FilingAddress,
    OtherSourcesIncome,
    SalaryIncome,
    TaxRegime,
    TDS1Entry,
)
from app.schemas.itr2 import (
    AgriculturalIncome,
    AMTInput,
    CapitalGainExemptionClaim,
    CG112AScrip,
    CGAssetType,
    CGTransaction,
    ITR2FilingProfile,
    ITR2Input,
    OSDeductions,
    OSRaceHorseActivity,
    OSSpecialRateEntry,
    PTIEntry,
    ResidentialStatus,
    SPIEntry,
    ReturnFileSection,
    ScheduleSIEntry,
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
    # capital_gains_income stays GROSS of the section 112A ₹1.25L
    # threshold -- Schedule CG's own disclosure chain (Table E, Part C)
    # is defined by the form itself as pure sums with no threshold
    # subtraction anywhere (confirmed against the form PDF, pages 47-49);
    # only Schedule SI's own tax computation (si.total_special_rate_tax
    # below) actually applies the threshold.
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
    # Gain = 15000 - 10000 = 5000 (not 15000 - 8000 = 7000).
    # capital_gains_income stays GROSS of the section 112A threshold (see
    # the fix note on this field's own assignment in
    # app/engine/calculators/itr2.py) -- only Schedule SI's own tax
    # computation below applies it.
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
    """112A gain below threshold remains in Total Income but is not taxed
    at slab rates (and correctly attracts no 112A tax either, since it's
    below the threshold).

    Confirmed directly against the official form PDF (`Reference Docs by
    CBDT & ITD/Official ITR FORMS/ITR-2-2026-Eng.pdf`, pages 47-49 and
    66-68): Part B-TI item 3 (Capital gains) is defined verbatim from
    Schedule CG's own Table E figures, which are GROSS throughout with no
    section 112A ₹1.25L threshold subtraction anywhere in their
    definition (Schedule 112A's own per-scrip "column 14" has no
    aggregate threshold applied at all) -- so Total Income (item 12)
    correctly includes the full 100000 gain. The threshold only zeroes
    the actual 112A TAX (via Schedule SI, which uses the post-threshold
    taxable amount) and is excluded from slab tax specifically via
    `special_rate_income_for_slab` (which uses the same gross figure
    Total Income includes, so the two exactly cancel for slab-tax
    purposes) -- not by excluding it from Total Income itself. An earlier
    version of this test asserted the opposite (`taxable_income == 0`),
    based on a plausible-sounding but ultimately wrong general
    income-tax-law inference made without checking this literal form
    table first; confirmed wrong by live Type-2 UAT validateItr
    rejections once GTI/Total Income were correspondingly netted to
    match (2026-09-13, PAN GOYPT2026A).
    """
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
# Phase 2 cluster 1: Schedule Salary structurally-guaranteed caps
# (CBDT rules #30/#36/#56/#66 -- no pre-compute validator needed, the
# calculator already enforces each statutory ceiling by construction, and
# the ITD builder reads the calculator's capped result field, not the raw
# claim -- see app/engine/schedules/salary.py's _exempt_transport()/
# _exempt_vrs() and the entertainment-allowance min() formula in compute()).
# ---------------------------------------------------------------------------

def test_entertainment_allowance_capped_at_statutory_formula():
    """CBDT rule #36: entertainment allowance u/s 16(ii) is the least of
    Rs 5,000, 1/5th of salary, and 20% of salary, for CG/SG/PSU employees
    under the old regime -- verify a raw claim exceeding the formula is
    silently capped, not passed through."""
    inp = _minimal_input(
        salary_income=SalaryIncome(
            gross_salary=D("100000"), is_government_employee=True,
            entertainment_allowance=D("50000"),  # raw claim far above any cap
        ),
    )
    r = compute(inp)
    sal = r.schedules["salary"]
    # min(5000, (100000-50000)/5=10000, 100000*0.20=20000) = 5000
    assert sal.entertainment_allowance == D("5000")


def test_transport_allowance_disabled_capped_at_38400():
    """CBDT rule #56: transport allowance exemption for a disabled employee
    u/s 10(14)(ii) cannot exceed Rs 38,400/year."""
    inp = _minimal_input(
        salary_income=SalaryIncome(
            gross_salary=D("500000"), is_disabled_employee=True,
            transport_allowance=D("100000"),  # raw claim far above the cap
        ),
    )
    r = compute(inp)
    sal = r.schedules["salary"]
    assert sal.transport_exempt == D("38400")


def test_net_agricultural_income_subtracts_unabsorbed_loss():
    """CBDT rule #436: Net Agricultural income = Gross receipts -
    Expenditure - Unabsorbed agricultural loss of the previous eight
    assessment years -- the third term was previously never subtracted at
    all."""
    inp = _minimal_input(agricultural_income=AgriculturalIncome(
        gross_agricultural_income=D("800000"), agricultural_deductions=D("100000"),
        unabsorbed_agricultural_loss_previous_8_years=D("200000"),
    ))
    r = compute(inp)
    assert r.net_agricultural_income == D("500000")  # 800000 - 100000 - 200000


def test_retrenchment_compensation_capped_at_5_lakh():
    """CBDT rules #30/#66: retrenchment compensation exemption u/s
    10(10B)(ii) cannot exceed Rs 5,00,000."""
    inp = _minimal_input(
        salary_income=SalaryIncome(
            gross_salary=D("1000000"), retrenchment_compensation=D("800000"),
        ),
    )
    r = compute(inp)
    sal = r.schedules["salary"]
    assert sal.retrenchment_exempt == D("500000")


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


def test_rebate_rnor_low_income_eligible():
    """CBDT rule #535: RNOR (Resident but Not Ordinarily Resident) is a
    species of "resident" under section 6 -- only a non-resident is
    excluded from Section 87A. Previously this calculator's stricter
    ``== RESIDENT`` eligibility check denied RNOR the rebate
    unconditionally; fixed 2026-09-12 to match ordinary-resident treatment.
    """
    inp = _minimal_input(
        tax_regime=TaxRegime.NEW,
        residential_status=ResidentialStatus.NOT_ORDINARILY_RESIDENT,
        salary_income=SalaryIncome(gross_salary=D("1000000")),
    )
    r = compute(inp)
    # TI = 925K <= 12L new-regime rebate threshold -> rebate applies, same
    # as an ordinary resident with identical income (test_salary_new_regime_rebate).
    assert r.rebate_87a > D("0")
    assert r.tax_after_rebate == D("0")


def test_rebate_rnor_old_regime_above_5l_ineligible():
    """CBDT rule #535's own explicit carve-out: old regime, RNOR, total
    income above Rs.5L -> rebate is NOT available (same as an ordinary
    resident above the old-regime threshold) -- the fix must not make RNOR
    eligible unconditionally, only on the same terms as a resident.
    """
    inp = _minimal_input(
        tax_regime=TaxRegime.OLD,
        residential_status=ResidentialStatus.NOT_ORDINARILY_RESIDENT,
        salary_income=SalaryIncome(gross_salary=D("800000")),
    )
    r = compute(inp)
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


# ---------------------------------------------------------------------------
# Section 54B exemption on STCG land/building (form item A1d) -- must
# actually reduce the taxable total, not just the per-row disclosure.
# ---------------------------------------------------------------------------

def test_section_54b_exemption_reduces_stcg_when_no_ltcg_exists() -> None:
    """A valid §54B claim against STCG land/building must reduce the real
    taxable total even when the return has NO LTCG to absorb it.

    Previously the entire §54-series exemption pool -- including 54B
    claimed against an STCG land/building disposal -- was only ever netted
    against LTCG (`_post_loss_cg_baskets()`'s `[other_ltcg, section_112a]`
    consumption). A 54B claim was correctly disclosed per-row but silently
    never reduced actual tax whenever the return had no LTCG at all, as
    here: STCG land gain 20L - 10L = 10L, 5L claimed under 54B, no LTCG
    anywhere -- capital_gains_income must be 5L, not the full 10L.
    """
    inp = _minimal_input(
        cg_transactions=[
            CGTransaction(
                asset_type=CGAssetType.LAND_BUILDING,
                date_of_acquisition=date(2024, 1, 1),
                date_of_transfer=date(2025, 6, 1),
                full_consideration=D("2000000"),
                cost_of_acquisition=D("1000000"),
                exemptions=[
                    CapitalGainExemptionClaim(
                        section="54B",
                        transfer_date=date(2025, 6, 1),
                        eligible_gain=D("1000000"),
                        investment_amount=D("500000"),
                        investment_date=date(2025, 8, 1),
                    ),
                ],
            ),
        ],
    )
    r = compute(inp)
    assert r.schedules["cg"].stcg.total_stcg == D("1000000")  # pre-exemption, per-row disclosure
    assert r.capital_gains_income == D("500000")  # post-exemption, actual taxable amount
    assert r.gross_total_income == D("500000")


def test_section_54b_exemption_on_stcg_does_not_reduce_unrelated_ltcg() -> None:
    """A 54B claim against STCG land must not leak into netting LTCG too --
    only the LTCG-eligible sections (54/54EC/54F/115F, or leftover 54B) may
    reduce a positive LTCG bucket."""
    inp = _minimal_input(
        cg_transactions=[
            CGTransaction(
                asset_type=CGAssetType.LAND_BUILDING,
                date_of_acquisition=date(2024, 1, 1),
                date_of_transfer=date(2025, 6, 1),
                full_consideration=D("2000000"),
                cost_of_acquisition=D("1000000"),
                exemptions=[
                    CapitalGainExemptionClaim(
                        section="54B",
                        transfer_date=date(2025, 6, 1),
                        eligible_gain=D("1000000"),
                        investment_amount=D("500000"),
                        investment_date=date(2025, 8, 1),
                    ),
                ],
            ),
        ],
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
    # STCG side: 10L gain - 5L (54B) = 5L. LTCG side (112A): 2L gain, fully
    # untouched by the STCG-side 54B claim, and GROSS of the section 112A
    # threshold (Schedule CG's own disclosure chain never applies it --
    # see the fix note on capital_gains_income's own assignment in
    # app/engine/calculators/itr2.py).
    assert r.capital_gains_income == D("500000") + D("200000")


# ---------------------------------------------------------------------------
# Schedule OS -- section 57 general deductions (form item 3) apply against
# the whole normal-rate OS pool, not only machinery/plant/furniture rent.
# ---------------------------------------------------------------------------

def test_os_section_57_general_deduction_applies_without_machinery_rent() -> None:
    """A Section 57 expense claim must reduce taxable OS income even when
    the taxpayer has no machinery/plant/furniture letting income at all.

    Previously `os_deductions.expenses`/`.depreciation` were only ever
    subtracted when `os_machinery_plant_rent` was also nonzero, so a
    taxpayer with e.g. savings-bank interest and a genuine Section 57
    expense claim but no letting income got the deduction disclosed in
    the JSON but silently never subtracted from taxable income -- a real
    overstatement of tax.
    """
    inp = _minimal_input(
        other_sources_income=OtherSourcesIncome(savings_bank_interest=D("50000")),
        os_deductions=OSDeductions(expenses=D("5000")),
    )
    r = compute(inp)
    assert r.other_sources_income == D("45000")


def test_os_section_57_general_deduction_does_not_touch_race_horse_income() -> None:
    """The general Section 57 deduction must reduce only the normal-rate OS
    pool, never the separately-taxed race-horse sub-head."""
    inp = _minimal_input(
        other_sources_income=OtherSourcesIncome(savings_bank_interest=D("50000")),
        os_deductions=OSDeductions(expenses=D("5000")),
        os_race_horse=OSRaceHorseActivity(receipts=D("20000"), balance=D("20000")),
    )
    r = compute(inp)
    # Normal-rate pool: 50000 - 5000 = 45000. Race-horse: 20000 (untouched).
    assert r.other_sources_income == D("45000") + D("20000")


def test_os_section_57_general_deduction_still_applies_with_machinery_rent() -> None:
    """When machinery rent IS present, the general deduction still applies
    to the whole normal-rate pool (not double-counted, not dropped)."""
    inp = _minimal_input(
        other_sources_income=OtherSourcesIncome(savings_bank_interest=D("50000")),
        os_deductions=OSDeductions(expenses=D("5000")),
        os_machinery_plant_rent=D("30000"),
    )
    r = compute(inp)
    # (50000 + 30000) - 5000 = 75000.
    assert r.other_sources_income == D("75000")


# ---------------------------------------------------------------------------
# Section 80CCD(1)/(2) statutory salary-based caps (real bug: `salary` was
# never threaded into compute_deductions() for ITR-2 at all, so 80CCD(2)'s
# 10%/14%-of-salary ceiling was never enforced -- the full claimed amount was
# always allowed -- and the new 80CCD(1) 10%-of-salary/20%-of-GTI sub-cap
# (CBDT rule #348) fell back to the wrong branch for every salaried filer.)
# ---------------------------------------------------------------------------

def test_80ccd2_employer_nps_contribution_is_capped_to_salary_not_allowed_in_full():
    """A non-government employee claims an employer NPS contribution well
    above 10% of salary. Before the `salary=` wiring fix, section_80ccd2's
    own no-salary fallback (`ceiling = ... if salary > 0 else user_claim`)
    silently allowed the ENTIRE claim -- an unbounded deduction. It must now
    be capped at 10% of salary (old regime, non-government employer)."""
    inp = _minimal_input(
        salary_income=SalaryIncome(
            gross_salary=D("1000000"), is_government_employee=False, is_cg_sg_employee=False,
        ),
        deductions_chapter6a=Chapter6ADeductions(amount_80ccd2=D("300000")),  # 30% of salary
    )
    r = compute(inp)
    ccd2 = r.schedules["deductions"].section_details["80CCD(2)"]
    assert ccd2.statutory_ceiling == D("100000")  # 10% of 10L
    assert ccd2.allowed_deduction == D("100000")  # capped, not the full 300000 claim


def test_80ccd1_employee_nps_contribution_capped_at_10pct_of_salary():
    """Section 80CCD(1)'s own statutory sub-cap (CBDT rule #348): for an
    employee, the deductible NPS contribution is limited to 10% of salary,
    independent of the shared ₹1,50,000 80CCE pool. A ₹10L-salary employee
    claiming ₹2,00,000 (well within the pool cap) must still be limited to
    ₹1,00,000 (10% of salary), not the full pool-capped ₹1,50,000."""
    inp = _minimal_input(
        salary_income=SalaryIncome(gross_salary=D("1000000")),
        deductions_chapter6a=Chapter6ADeductions(amount_80ccd1=D("200000")),
    )
    r = compute(inp)
    assert r.schedules["deductions"].breakdown.get("80CCD(1)", D("0")) == D("100000")


def test_80ccd1_non_employee_capped_at_20pct_of_gti():
    """No salary income at all (e.g. a filer whose only income is house
    property / other sources): the 20%-of-GTI branch applies instead of
    10%-of-salary, and must bind below the ₹1,50,000 combined-pool cap when
    20% of GTI is itself smaller than that pool."""
    inp = _minimal_input(
        other_sources_income=OtherSourcesIncome(savings_bank_interest=D("500000")),
        deductions_chapter6a=Chapter6ADeductions(amount_80ccd1=D("300000")),
    )
    r = compute(inp)
    # GTI = 500,000; 20% = 100,000 -- below both the raw 300,000 claim and
    # the 150,000 combined-pool cap, so the GTI sub-cap is the binding one.
    assert r.schedules["deductions"].breakdown.get("80CCD(1)", D("0")) == D("100000")


# ---------------------------------------------------------------------------
# Schedule CFL: current-year race-horse-activity loss carry-forward (Section
# 74A(3)). Schedule OS item 8e's own negative balance was previously simply
# clamped to zero for GTI purposes (correct) with nothing downstream ever
# picking up the discarded negative remainder for Schedule CFL row xi --
# silently losing the taxpayer's statutory right to carry it forward.
# ---------------------------------------------------------------------------

def test_racehorse_current_year_loss_is_carried_forward_to_cfl():
    inp = _minimal_input(
        salary_income=SalaryIncome(gross_salary=D("800000")),
        os_race_horse=OSRaceHorseActivity(receipts=D("5000"), balance=D("-30000")),
    )
    r = compute(inp)
    # The loss must not reduce other-sources income (Schedule OS item 9
    # takes 8e as nil when negative) ...
    assert r.other_sources_income == D("0")
    # ... but it must appear as a fresh current-year CFL entry, carried
    # forward for 4 years (section 74A(3)), not the ordinary 8.
    cfl_entries = r.schedules["cfl"]
    race_horse_results = [
        entry for cfl in cfl_entries for entry in cfl.entries if entry.head == "RaceHorse"
    ]
    assert len(race_horse_results) == 1
    assert race_horse_results[0].loss_remaining == D("30000")
    assert race_horse_results[0].assessment_year_of_loss == "2026-27"


def test_racehorse_current_year_profit_produces_no_cfl_entry():
    """A positive balance must not spuriously create a CFL entry."""
    inp = _minimal_input(
        os_race_horse=OSRaceHorseActivity(receipts=D("30000"), balance=D("20000")),
    )
    r = compute(inp)
    cfl_entries = r.schedules["cfl"]
    race_horse_results = [
        entry for cfl in cfl_entries for entry in cfl.entries if entry.head == "RaceHorse"
    ]
    assert race_horse_results == []


# ---------------------------------------------------------------------------
# Capped-bucket special-rate income (dividend/FII 115A-family, and PTI
# capital gains) was silently absent from `special_rate_income_for_slab`,
# so once it reached GTI via `os_special_rate_entries` it was taxed BOTH at
# slab rate (via `normal_income`) AND, correctly, at its own Schedule SI
# rate -- a real, confirmed double-taxation defect.
# ---------------------------------------------------------------------------

def test_nri_dividend_special_rate_income_is_not_double_taxed():
    """A return whose only income is NRI dividend income taxable at a
    special SI rate (section 115A(1)(a)(A), 10%) must have ZERO slab tax --
    previously the same ₹10L was also taxed at ordinary slab rates on top
    of the correct flat 10% SI tax."""
    inp = _minimal_input(
        os_special_rate_entries=[
            OSSpecialRateEntry(source_description="5A1aA", source_amount=D("1000000")),
        ],
    )
    r = compute(inp)
    assert r.taxable_income == D("1000000")
    assert r.slab_tax == D("0")
    assert r.special_rate_tax == D("100000")  # 10% of 10L


def test_nri_dividend_alongside_ordinary_salary_income_taxes_each_correctly():
    """Mixed case: ordinary salary (slab-rate) plus NRI dividend (SI-rate,
    capped bucket) -- slab tax must apply only to the salary portion."""
    inp = _minimal_input(
        salary_income=SalaryIncome(gross_salary=D("800000")),
        os_special_rate_entries=[
            OSSpecialRateEntry(source_description="5A1aA", source_amount=D("500000")),
        ],
    )
    r = compute(inp)
    salary_only = compute(_minimal_input(salary_income=SalaryIncome(gross_salary=D("800000"))))
    assert r.slab_tax == salary_only.slab_tax
    assert r.special_rate_tax == D("50000")  # 10% of 5L


# ---------------------------------------------------------------------------
# SPI (clubbed) and PTI (pass-through) capital-gains income was computed
# then silently discarded / never added to GTI at all -- understating Total
# Income and, for SPI, understating tax outright (income vanished entirely).
# ---------------------------------------------------------------------------

def test_spi_clubbed_capital_gain_reaches_gross_total_income():
    """A capital gain clubbed from a minor child (head_of_income='CG') must
    actually increase Total Income -- previously it was added to a field
    that (a) never fed GTI and (b) was unconditionally overwritten later,
    so the clubbed income silently vanished."""
    inp = _minimal_input(
        spi_entries=[
            SPIEntry(
                specified_person_name="Minor Child", relationship="Son",
                amount_included=D("200000"), head_of_income="CG",
            ),
        ],
    )
    r = compute(inp)
    assert r.gross_total_income == D("200000")
    assert r.capital_gains_income == D("200000")
    assert r.taxable_income > D("0")


def test_pti_stcg_111a_reaches_gross_total_income_and_stays_out_of_slab():
    """PTI STCG taxed at 20% (section 111A pass-through) must be included
    in GTI/Total Income (Schedule CG's own A7 line item) while still being
    excluded from ordinary slab tax (it's taxed via Schedule SI instead)."""
    inp = _minimal_input(
        pti_entries=[
            PTIEntry(
                entity_name="ABC InvIT", entity_pan="AAACI1234A",
                income_head="STCG", section="111A", income_amount=D("300000"),
            ),
        ],
    )
    r = compute(inp)
    assert r.gross_total_income == D("300000")
    assert r.capital_gains_income == D("300000")
    assert r.slab_tax == D("0")
    assert r.special_rate_tax == D("60000")  # 20% of 3L


def test_pti_ltcg_other_reaches_gross_total_income_and_stays_out_of_slab():
    """PTI LTCG taxed at 12.5% (not section 112A) must likewise be included
    in GTI (Schedule CG's own B10 line item) and excluded from slab."""
    inp = _minimal_input(
        pti_entries=[
            PTIEntry(
                entity_name="XYZ REIT", entity_pan="AAACX1234B",
                income_head="LTCG", section="OTHER", income_amount=D("400000"),
            ),
        ],
    )
    r = compute(inp)
    assert r.gross_total_income == D("400000")
    assert r.capital_gains_income == D("400000")
    assert r.slab_tax == D("0")
    assert r.special_rate_tax == D("50000")  # 12.5% of 4L


# ---------------------------------------------------------------------------
# Schedule AMT item 2a: 80QQB/80RRB -- the only heading-C Chapter VI-A
# deductions an ITR-2 filer (no business income) can actually claim -- were
# never fed into the AMT addback list at all, so Adjusted Total Income
# silently omitted them.
# ---------------------------------------------------------------------------

def test_ordinary_other_assets_stcg_uses_applicable_rate_not_flat_30pct():
    """MAJOR finding: a plain, non-FII/FPI taxpayer's "other assets" STCG
    (jewellery, unlisted shares, land/building -- form item A5/A1) was
    being disclosed under Schedule CG Table E's "STCG@30%" row
    (post_loss_cg["normal_stcg"], CYLA/BFLA's "stcg30" bucket), which the
    form's own item A9 formula ("A1e+A2e+A3a+A3b+A4e+A5e+A6+A7-A8a+A(A)")
    and its own Table-E cross-check ("E(iii) STCG@30% = A4e+A7b+A(A)_30%")
    reserve EXCLUSIVELY for a genuine FII/FPI's own section 115AD(1)(ii)
    securities gain (item A4) -- not A1/A5 at all. Confirmed live
    (2026-09-14, Type-2 UAT validateItr, PAN GOYPT2026A) with a completely
    plain jewellery STCG transaction, no FII/PTI/SPI/buyback involvement
    whatsoever: errCd ITR2_INF26_InStcg30Per_CurrYearIncome, "STCG gain @
    30% should be equal to the sum of Sl. No. (A4e + A7b + A(A)_30%)" --
    this was blocking Type-2 submission for any ordinary resident with
    this extremely common transaction type. Must instead be taxed at slab
    rate (unaffected -- this was already correct) and disclosed under
    "applicable rate" (InStcgAppRate/STCGAppRate), not "30%"."""
    inp = _minimal_input(
        cg_transactions=[CGTransaction(
            asset_type=CGAssetType.JEWELLERY,
            date_of_acquisition=date(2025, 6, 1), date_of_transfer=date(2026, 1, 15),
            full_consideration=D("500000"), cost_of_acquisition=D("350000"),
        )],
    )
    r = compute(inp)
    assert r.taxable_income == D("150000")
    assert r.slab_tax == D("0")  # correctly below the basic exemption, unaffected by this fix
    assert r.capital_gains_income == D("150000")
    post_loss_cg = r.schedules["post_loss_cg"]
    # The OUTPUT bucket total is unchanged (still 150000) -- only its
    # INTERNAL CYLA source sub-bucket moved from stcg30 to stcg_app.
    assert post_loss_cg["normal_stcg"] == D("150000")
    cyla = r.schedules["cyla"]
    assert cyla.stcg30_remaining == D("0")
    assert cyla.stcg_app_remaining == D("150000")


def test_fii_fpi_other_stcg_still_uses_flat_30pct_bucket():
    """An FII/FPI's OWN section 115AD(1)(ii) securities gain genuinely IS a
    flat 30% and must still route through the "stcg30" bucket unchanged."""
    profile = ITR2FilingProfile(
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
    inp = _minimal_input(
        residential_status=ResidentialStatus.NON_RESIDENT,
        filing_profile=profile,
        cg_transactions=[CGTransaction(
            asset_type=CGAssetType.LISTED_SECURITY,
            date_of_acquisition=date(2025, 6, 1), date_of_transfer=date(2026, 1, 15),
            full_consideration=D("500000"), cost_of_acquisition=D("350000"),
        )],
    )
    r = compute(inp)
    post_loss_cg = r.schedules["post_loss_cg"]
    assert post_loss_cg["normal_stcg"] == D("150000")
    cyla = r.schedules["cyla"]
    assert cyla.stcg30_remaining == D("150000")
    assert cyla.stcg_app_remaining == D("0")


def test_amt_addition_includes_80qqb_deduction():
    inp = _minimal_input(
        salary_income=SalaryIncome(gross_salary=D("2200000")),
        deduction_80qqb=D("300000"),
        royalty_income_80qqb=D("300000"),
    )
    r = compute(inp)
    amt = r.schedules["amt"]
    assert amt.adjusted_total_income == r.taxable_income + D("300000")


# ---------------------------------------------------------------------------
# Part B-TTI item 5i: section 115BBE (unexplained income) carries a
# MANDATORY flat 25% surcharge, independent of the taxpayer's overall
# income-level surcharge slab -- previously this was entirely absent, so a
# return with modest total income (below the first surcharge threshold, 0%
# ordinary rate) got ZERO surcharge on the 115BBE component too.
# ---------------------------------------------------------------------------

def test_115bbe_gets_mandatory_25pct_surcharge_even_below_ordinary_threshold():
    inp = _minimal_input(
        si_entries=[ScheduleSIEntry(section="115BBE", gross_income=D("500000"))],
    )
    r = compute(inp)
    assert r.taxable_income == D("500000")
    assert r.special_rate_tax == D("300000")  # 60% of 5L
    assert r.surcharge == D("75000")  # 25% of 300000, despite 5L being well below any ordinary surcharge threshold
    # Cess and Gross Tax Liability must be based on the COMPLETE surcharge
    # (including the 115BBE portion) -- a real bug found live (2026-09-14,
    # Type-2 UAT validateItr, PAN GOYPT2026A): both were computed from a
    # stale local `surcharge` variable that excluded the 115BBE addition,
    # so GrossTaxLiability silently disagreed with its own declared
    # Tax+Surcharge+Cess components.
    assert r.health_education_cess == D("15000")  # 4% of (300000 + 75000)
    assert r.gross_tax_liability == D("300000") + D("75000") + D("15000")


def test_115bbe_surcharge_adds_on_top_of_ordinary_surcharge_on_other_income():
    inp = _minimal_input(
        salary_income=SalaryIncome(gross_salary=D("6000000")),  # crosses the 10% surcharge slab
        si_entries=[ScheduleSIEntry(section="115BBE", gross_income=D("500000"))],
    )
    r = compute(inp)
    salary_only = compute(_minimal_input(salary_income=SalaryIncome(gross_salary=D("6000000"))))
    # The 115BBE component's own flat-25% surcharge (75000) must be added
    # on top of whatever surcharge the ordinary salary income independently
    # generates -- not blended into a single overall rate.
    assert r.surcharge == salary_only.surcharge + D("75000")
