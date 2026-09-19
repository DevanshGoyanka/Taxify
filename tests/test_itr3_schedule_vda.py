"""Tests for ITR-3 Schedule VDA (tracker row #23 -- Virtual Digital
Assets, section 115BBH).

**What was found**: unlike ITR-2, whose ``ScheduleVDA`` JSON schema
restricts ``HeadUndIncTaxed`` to ``["CG"]`` only, ITR-3's own official
schema requires the full ``["BI","CG"]`` split, with two separate
required totals (``TotIncBusiness``/``TotIncCapGain``) -- confirmed by
direct introspection of both forms' schema files, and by the ITR-3 form
PDF's own Schedule VDA page, which states the business total "feeds Item
No. A3g of Schedule BP" and the capital-gains total "feeds Item No. C2 of
Schedule CG". `_schedule_vda_typed()` (`app/engine/itd/itr3.py`) already
correctly builds this split. But `calculators/itr3.py` dropped the
per-transaction ``head`` when constructing its internal ``VDAEntry``
objects and dumped the FULL VDA total (business- and capital-gains-
classified together) into ``capital_gains_income`` unconditionally --
meaning a business-classified VDA transaction was disclosed correctly in
Schedule VDA's own table but silently misclassified as a pure capital
gain everywhere else (Schedule CG item C2, Part B-TI's ``CapGain``), with
NO automatic path into Schedule BP's business-income total at all (only
a wholly disconnected manual field, ``reallocation_income_115bbh``,
which the taxpayer would have to separately duplicate the same figure
into -- something the frontend's own Schedule VDA UI text incorrectly
implies happens automatically).

**A second, independent, pre-existing bug found while fixing the above**:
Schedule CG's own ``IncmFromVDATrnsf`` (item C2) read
``getattr(cg_result, "vda_income", zero)`` -- but `CGResult`'s real field
is named ``vda``, not ``vda_income``, so this ``getattr`` fallback
silently returned zero unconditionally, regardless of any real VDA
capital-gains income. (`SumOfCGIncm`/`TotScheduleCGFor23`, sourced from
`total_capital_gains`, were unaffected and already correct.)

**Fix**: the calculator now computes `vda_income_bi`/`vda_income_cg`
separately (via `compute_vda()`, called once per `head`, preserving the
existing per-transaction loss-disallowance rule for each split), credits
`vda_income_bi` directly to `business_income` (parallel to how VDA-CG is
already credited directly to `capital_gains_income`), and leaves
`capital_gains_income` sourced from `vda_income_cg` only. Section
115BBH's flat 30% rate is unaffected by `head` -- the full, combined
`vda_income` still flows through Schedule SI exactly as before. The
builder's `IncmFromVDATrnsf`/Part B-TI `CapGain`/Table F accrual bucket
now all correctly exclude business-classified VDA income, and Part B-TI's
`ProfGainNoSpecBus`/`TotProfBusGain` now include it (added back
explicitly when a business exists, since PGBP's own
`non_spec_net_income` has no VDA awareness at all).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from jsonschema import Draft4Validator

from app.engine.calculators.itr3 import compute as compute_itr3
from app.engine.itd.itr3 import _schedule_cg_for23_typed, _schedule_vda_typed, _partb_ti
from app.engine.itd.itr3_schema import get_itr3_schema_validator
from app.schemas.itr2 import VDATransaction
from app.schemas.itr3 import BusinessIncome, ITR3Input


def _vda(head: str, consideration: Decimal, cost: Decimal) -> VDATransaction:
    return VDATransaction(
        date_of_acquisition=date(2025, 6, 1),
        date_of_transfer=date(2026, 1, 15),
        acquisition_cost=cost,
        consideration_received=consideration,
        head=head,
    )


def _schedule_cg_validator() -> Draft4Validator:
    full = get_itr3_schema_validator().schema
    definition = dict(full["definitions"]["ScheduleCGFor23"])
    definition["definitions"] = full["definitions"]
    return Draft4Validator(definition)


# ---------------------------------------------------------------------------
# Calculator-level: head-based income classification
# ---------------------------------------------------------------------------

def test_cg_classified_vda_stays_in_capital_gains_head() -> None:
    typed = ITR3Input(
        age_bracket="below_60", tax_regime="new",
        assessee_pan="ABCDE1234F", assessee_dob="1980-01-01",
        vda_transactions=[_vda("CG", Decimal("500000"), Decimal("300000"))],
    )
    result = compute_itr3(typed)
    assert result.capital_gains_income == Decimal("200000")
    assert result.business_income == Decimal("0")
    assert result.vda_income_cg == Decimal("200000")
    assert result.vda_income_bi == Decimal("0")


def test_bi_classified_vda_moves_to_business_income_not_capital_gains() -> None:
    """The core fix: a business-classified VDA transaction must not be
    silently taxed as a capital gain -- it belongs in the business-income
    head, matching Schedule VDA's own disclosure and the form's own
    Schedule VDA -> Schedule BP item A3g cross-reference."""
    typed = ITR3Input(
        age_bracket="below_60", tax_regime="new",
        assessee_pan="ABCDE1234F", assessee_dob="1980-01-01",
        vda_transactions=[_vda("BI", Decimal("500000"), Decimal("300000"))],
    )
    result = compute_itr3(typed)
    assert result.capital_gains_income == Decimal("0")
    assert result.business_income == Decimal("200000")
    assert result.vda_income_cg == Decimal("0")
    assert result.vda_income_bi == Decimal("200000")


def test_mixed_bi_and_cg_vda_transactions_split_correctly() -> None:
    typed = ITR3Input(
        age_bracket="below_60", tax_regime="new",
        assessee_pan="ABCDE1234F", assessee_dob="1980-01-01",
        vda_transactions=[
            _vda("BI", Decimal("500000"), Decimal("300000")),   # 200000 business
            _vda("CG", Decimal("800000"), Decimal("650000")),   # 150000 capital gains
        ],
    )
    result = compute_itr3(typed)
    assert result.business_income == Decimal("200000")
    assert result.capital_gains_income == Decimal("150000")
    assert result.vda_income == Decimal("350000")


def test_vda_loss_disallowance_preserved_per_head_after_split() -> None:
    """Section 115BBH(2)(b): a VDA loss can never offset a VDA gain, even
    from a different transaction of the same head -- confirmed still true
    independently within each of the two new head-based splits."""
    typed = ITR3Input(
        age_bracket="below_60", tax_regime="new",
        assessee_pan="ABCDE1234F", assessee_dob="1980-01-01",
        vda_transactions=[
            _vda("BI", Decimal("300000"), Decimal("500000")),  # -200000 loss, ignored
            _vda("BI", Decimal("800000"), Decimal("650000")),  # +150000 gain
        ],
    )
    result = compute_itr3(typed)
    assert result.business_income == Decimal("150000")  # not 150000 - 200000


# ---------------------------------------------------------------------------
# Section 115BBH's flat 30% rate is unaffected by `head` -- both
# classifications are taxed identically via Schedule SI.
# ---------------------------------------------------------------------------

def test_vda_flat_30_percent_tax_applies_regardless_of_head() -> None:
    typed = ITR3Input(
        age_bracket="below_60", tax_regime="new",
        assessee_pan="ABCDE1234F", assessee_dob="1980-01-01",
        vda_transactions=[_vda("BI", Decimal("500000"), Decimal("300000"))],
    )
    result = compute_itr3(typed)
    si_by_section = {e.section: e for e in result.schedules["si"].entries}
    assert si_by_section["115BBH"].taxable_income == Decimal("200000")
    assert si_by_section["115BBH"].tax_amount == Decimal("60000")
    assert result.special_rate_tax == Decimal("60000")


# ---------------------------------------------------------------------------
# Builder-level: Schedule CG item C2 (`IncmFromVDATrnsf`)
# ---------------------------------------------------------------------------

def test_schedule_cg_incm_from_vda_trnsf_reflects_real_cg_income_not_zero() -> None:
    """CORRECTION: a second, independent, pre-existing bug -- this field
    read the wrong attribute name (`vda_income` instead of `vda`) off
    `CGResult` and was therefore ALWAYS zero, regardless of head."""
    typed = ITR3Input(
        age_bracket="below_60", tax_regime="new", pti_entries=[],
        vda_transactions=[_vda("CG", Decimal("500000"), Decimal("300000"))],
    )
    result = compute_itr3(typed)
    cg = _schedule_cg_for23_typed(result.schedules["cg"], typed)
    assert cg["IncmFromVDATrnsf"] == 200000
    errors = list(_schedule_cg_validator().iter_errors(cg))
    assert not errors, "\n".join(e.message for e in errors)


def test_schedule_cg_incm_from_vda_trnsf_excludes_business_classified() -> None:
    typed = ITR3Input(
        age_bracket="below_60", tax_regime="new", pti_entries=[],
        vda_transactions=[
            _vda("BI", Decimal("500000"), Decimal("300000")),  # excluded
            _vda("CG", Decimal("800000"), Decimal("650000")),  # 150000, included
        ],
    )
    result = compute_itr3(typed)
    cg = _schedule_cg_for23_typed(result.schedules["cg"], typed)
    assert cg["IncmFromVDATrnsf"] == 150000


# ---------------------------------------------------------------------------
# Builder-level: Part B-TI (`ProfBusGain`/`CapGain`) reconciliation
# ---------------------------------------------------------------------------

def test_partb_ti_credits_business_classified_vda_to_prof_bus_gain_no_pgbp() -> None:
    """No business declared at all (`pgbp is None`) -- `business_income`
    is the sole, already-correct source, so no double-add risk."""
    typed = ITR3Input(
        age_bracket="below_60", tax_regime="new",
        assessee_pan="ABCDE1234F", assessee_dob="1980-01-01",
        vda_transactions=[_vda("BI", Decimal("500000"), Decimal("300000"))],
    )
    result = compute_itr3(typed)
    payload = _partb_ti(result)
    assert payload["ProfBusGain"]["ProfGainNoSpecBus"] == 200000
    assert payload["ProfBusGain"]["TotProfBusGain"] == 200000
    assert payload["CapGain"]["CapGains30Per115BBH"] == 0
    assert payload["CapGain"]["TotalCapGains"] == 0


def test_partb_ti_credits_business_classified_vda_to_prof_bus_gain_with_pgbp() -> None:
    """A real business exists (`pgbp is not None`) -- `ProfGainNoSpecBus`
    sources from PGBP's own `non_spec_net_income` (bypassing
    `result.business_income` entirely), so the VDA-BI credit must be
    added back explicitly to avoid silently vanishing from this
    disclosure while still being present in `gross_total_income`."""
    typed = ITR3Input(
        age_bracket="below_60", tax_regime="new",
        assessee_pan="ABCDE1234F", assessee_dob="1980-01-01",
        business_income=BusinessIncome(net_profit_before_tax=Decimal("1000000")),
        vda_transactions=[_vda("BI", Decimal("500000"), Decimal("300000"))],
    )
    result = compute_itr3(typed)
    payload = _partb_ti(result)
    assert payload["ProfBusGain"]["ProfGainNoSpecBus"] == 1000000 + 200000
    assert payload["CapGain"]["CapGains30Per115BBH"] == 0
    assert payload["GrossTotalIncome"] == result.gross_total_income


def test_partb_ti_cap_gain_excludes_business_classified_vda() -> None:
    typed = ITR3Input(
        age_bracket="below_60", tax_regime="new",
        assessee_pan="ABCDE1234F", assessee_dob="1980-01-01",
        vda_transactions=[
            _vda("BI", Decimal("500000"), Decimal("300000")),  # excluded from CapGain
            _vda("CG", Decimal("800000"), Decimal("650000")),  # 150000, included
        ],
    )
    result = compute_itr3(typed)
    payload = _partb_ti(result)
    assert payload["CapGain"]["CapGains30Per115BBH"] == 150000
    assert payload["CapGain"]["TotalCapGains"] == 150000
    assert payload["ProfBusGain"]["TotProfBusGain"] == 200000


# ---------------------------------------------------------------------------
# Cross-schedule consistency: Schedule VDA's own A/B split must agree with
# the now-fixed Schedule CG/Part B-TI figures above.
# ---------------------------------------------------------------------------

def test_schedule_vda_own_split_agrees_with_schedule_cg_and_partb_ti() -> None:
    typed = ITR3Input(
        age_bracket="below_60", tax_regime="new", pti_entries=[],
        vda_transactions=[
            _vda("BI", Decimal("500000"), Decimal("300000")),
            _vda("CG", Decimal("800000"), Decimal("650000")),
        ],
    )
    result = compute_itr3(typed)
    vda_schedule = _schedule_vda_typed(typed)
    assert vda_schedule["TotIncBusiness"] == 200000
    assert vda_schedule["TotIncCapGain"] == 150000
    cg = _schedule_cg_for23_typed(result.schedules["cg"], typed)
    assert cg["IncmFromVDATrnsf"] == vda_schedule["TotIncCapGain"]
    partb = _partb_ti(result)
    assert partb["CapGain"]["CapGains30Per115BBH"] == vda_schedule["TotIncCapGain"]
