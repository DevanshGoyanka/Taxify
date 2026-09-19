"""Tests for ITR-3 Schedule OS (tracker row #24 -- Income from Other
Sources), covering the severe, tax-liability-breaking bugs closed on
2026-09-19.

**What was found**: ITR-3 never received the equivalent of ITR-2's own
extensive Schedule OS fix cycle. Two confirmed, reproduced, severe bugs:

1. Other-Sources-head Schedule SI income (lottery/115BB, unexplained
   income/115BBE, patent royalty/115BBF) was taxed via Schedule SI's flat
   rate but never added to Gross Total Income/Total Income -- a bare
   lottery win produced `gross_total_income == 0`, `taxable_income == 0`,
   while tax was still charged on it. Fixed via a new
   `_OS_HEAD_SI_SECTIONS` constant (`calculators/itr3.py`), mirroring
   ITR-2's own already-shipped, identically-named fix.
2. `_schedule_os()` returned `None` (omitting Schedule OS from the filed
   JSON entirely) whenever the only OS-head income was an `si_entries`
   row with no `other_sources_income` model set -- while Part B-TI
   simultaneously disclosed a nonzero `IncFromOS`, an internally
   self-contradictory return.

**Two further, independent, pre-existing bugs found and fixed in the same
region while closing the above** (both make Schedule OS's own JSON
unconditionally schema-invalid the moment it's populated, confirmed by
direct schema validation, not just a disclosure completeness gap):

3. `GrossIncChrgblTaxAtAppRate` (item 1, "gross income chargeable to tax
   at normal applicable rates") was wrongly set equal to the ALREADY-NET
   (post-57(iia)-deduction) `result.other_sources_income` figure, so item
   1 minus item 3 (deductions) never equalled the disclosed item 6
   (`BalanceNoRaceHorse`) whenever any deduction was actually claimed.
4. Eight of the nine Schedule-OS DateRange sub-blocks
   (`DividendIncUs115BBDA`/`...BBDAaiii`/`...115A1ai`/`...115AC`/
   `...115ACA`/`...115AD1i`/`NOT89A`/`DividendDTAA`) used a key
   (`"Upto15Of9"`) that does not exist anywhere in the official
   `DateRangeTypeOS` schema shape (`Up16Of6To15Of9` is the real key) --
   `additionalProperties: false` meant Schedule OS's JSON was
   unconditionally schema-invalid whenever any of these (always-zero,
   currently-unsupported) blocks was present, i.e. always. The
   `Deductions` sub-object was also missing its own required
   `Depreciation` key.

These four are grouped as one fix/one commit since they share the same
code region and the same root discovery pass -- see
`Docs/ITR3_SCHEDULE_IMPLEMENTATION_TRACKER.md`'s own Schedule 24 fix-log
entry for the full write-up, including what's deliberately NOT fixed here
(race horse activity, 56(2)(x) gift sub-breakdown, section 89A, DTAA-OS,
accumulated PF, the 115BBG/115BBJ/115BBA/111/115E SI-section family) --
those need new `ITR3Input` schema fields and mapper wiring the frontend
draft schema already captures but ITR-3's own mapper never reads, a
larger, separately-scoped follow-on build-out.
"""

from __future__ import annotations

from decimal import Decimal

from jsonschema import Draft4Validator

from app.engine.calculators.itr3 import compute as compute_itr3
from app.engine.itd.itr3 import _schedule_os, _partb_ti
from app.engine.itd.itr3_schema import get_itr3_schema_validator
from app.schemas.itr1 import OtherSourcesIncome
from app.schemas.itr2 import ScheduleSIEntry
from app.schemas.itr3 import ITR3Input


def _schedule_os_validator() -> Draft4Validator:
    full = get_itr3_schema_validator().schema
    definition = dict(full["definitions"]["ScheduleOS"])
    definition["definitions"] = full["definitions"]
    return Draft4Validator(definition)


def _lottery_entry(amount: Decimal) -> ScheduleSIEntry:
    return ScheduleSIEntry(section="115BB", gross_income=amount, tax_rate_pct=Decimal("30"))


# ---------------------------------------------------------------------------
# Bug 1: OS-head Schedule SI income must reach GTI/Total Income.
# ---------------------------------------------------------------------------

def test_lottery_income_reaches_gross_total_income_not_zero() -> None:
    """CORRECTION: a bare lottery win previously produced GTI=0, TI=0,
    while tax was still charged on it -- a direct, severe correctness
    bug, not a disclosure nicety."""
    typed = ITR3Input(
        age_bracket="below_60", tax_regime="new",
        si_entries=[_lottery_entry(Decimal("100000"))],
    )
    result = compute_itr3(typed)
    assert result.gross_total_income == Decimal("100000")
    assert result.taxable_income == Decimal("100000")
    assert result.special_rate_tax == Decimal("30000")


def test_unexplained_income_115bbe_reaches_gross_total_income() -> None:
    typed = ITR3Input(
        age_bracket="below_60", tax_regime="new",
        si_entries=[ScheduleSIEntry(section="115BBE", gross_income=Decimal("50000"))],
    )
    result = compute_itr3(typed)
    assert result.gross_total_income == Decimal("50000")
    assert result.taxable_income == Decimal("50000")


def test_normal_rate_os_income_unaffected_by_si_section_fix() -> None:
    """No regression: ordinary savings-interest OS income (no SI dispatch
    at all) must reach GTI exactly as before."""
    typed = ITR3Input(
        age_bracket="below_60", tax_regime="new",
        other_sources_income=OtherSourcesIncome(savings_bank_interest=Decimal("10000")),
    )
    result = compute_itr3(typed)
    assert result.gross_total_income == Decimal("10000")


# ---------------------------------------------------------------------------
# Bug 2: Schedule OS must not be omitted from the JSON when the only OS
# income is an si_entries row.
# ---------------------------------------------------------------------------

def test_schedule_os_present_and_valid_with_only_si_entries_income() -> None:
    typed = ITR3Input(
        age_bracket="below_60", tax_regime="new",
        si_entries=[_lottery_entry(Decimal("100000"))],
    )
    result = compute_itr3(typed)
    os_json = _schedule_os(result, typed)
    assert os_json is not None
    errors = list(_schedule_os_validator().iter_errors(os_json))
    assert not errors, "\n".join(e.message for e in errors)
    assert os_json["IncOthThanOwnRaceHorse"]["LtryPzzlChrgblUs115BB"] == 100000
    assert os_json["IncOthThanOwnRaceHorse"]["IncChargeableSpecialRates"] == 100000


def test_partb_ti_incfromos_agrees_with_gti_when_only_lottery_income() -> None:
    """Cross-schedule consistency: Part B-TI's own IncFromOS.TotIncFromOS
    must agree with the calculator's GrossTotalIncome -- previously
    Part B-TI showed a nonzero figure here while GTI was 0 and Schedule OS
    was entirely absent from the JSON."""
    typed = ITR3Input(
        age_bracket="below_60", tax_regime="new",
        si_entries=[_lottery_entry(Decimal("100000"))],
    )
    result = compute_itr3(typed)
    payload = _partb_ti(result)
    assert payload["IncFromOS"]["TotIncFromOS"] == 100000
    assert payload["IncFromOS"]["TotIncFromOS"] == result.gross_total_income


def test_schedule_os_absent_when_genuinely_no_os_income_at_all() -> None:
    """No regression: a return with no OS income and no OS-head si_entries
    must still correctly omit Schedule OS."""
    typed = ITR3Input(age_bracket="below_60", tax_regime="new")
    result = compute_itr3(typed)
    assert _schedule_os(result, typed) is None


# ---------------------------------------------------------------------------
# Bug 3: item 1 (GrossIncChrgblTaxAtAppRate) vs item 6 (BalanceNoRaceHorse)
# cross-foot.
# ---------------------------------------------------------------------------

def test_gross_income_item1_minus_deductions_equals_balance_item6() -> None:
    typed = ITR3Input(
        age_bracket="below_60", tax_regime="new",
        other_sources_income=OtherSourcesIncome(
            family_pension_received=Decimal("60000"), savings_bank_interest=Decimal("10000"),
        ),
    )
    result = compute_itr3(typed)
    os_json = _schedule_os(result, typed)
    block = os_json["IncOthThanOwnRaceHorse"]
    assert block["GrossIncChrgblTaxAtAppRate"] == 70000
    assert block["Deductions"]["TotDeductions"] == 20000  # min(60000/3, 25000)
    assert block["BalanceNoRaceHorse"] == 50000
    assert block["GrossIncChrgblTaxAtAppRate"] - block["Deductions"]["TotDeductions"] == block["BalanceNoRaceHorse"]


def test_mixed_normal_and_special_rate_os_income_splits_correctly() -> None:
    """A return with BOTH normal-rate (family pension + interest) and
    special-rate (lottery) OS income must split item 1/item 2/item 6/item 7
    correctly, with no double-counting anywhere, and Part B-TI must agree."""
    typed = ITR3Input(
        age_bracket="below_60", tax_regime="new",
        other_sources_income=OtherSourcesIncome(
            family_pension_received=Decimal("60000"), savings_bank_interest=Decimal("10000"),
        ),
        si_entries=[_lottery_entry(Decimal("100000"))],
    )
    result = compute_itr3(typed)
    os_json = _schedule_os(result, typed)
    block = os_json["IncOthThanOwnRaceHorse"]
    assert block["GrossIncChrgblTaxAtAppRate"] == 70000
    assert block["IncChargeableSpecialRates"] == 100000
    assert block["BalanceNoRaceHorse"] == 50000
    assert os_json["TotOthSrcNoRaceHorse"] == 150000  # item2 + item6
    errors = list(_schedule_os_validator().iter_errors(os_json))
    assert not errors, "\n".join(e.message for e in errors)

    partb = _partb_ti(result)
    assert partb["IncFromOS"]["OtherSrcThanOwnRaceHorse"] == 50000
    assert partb["IncFromOS"]["IncChargblSplRate"] == 100000
    assert partb["IncFromOS"]["TotIncFromOS"] == 150000
    assert result.gross_total_income == 150000


# ---------------------------------------------------------------------------
# Bug 4: schema-invalid DateRange keys / missing Deductions.Depreciation.
# ---------------------------------------------------------------------------

def test_schedule_os_passes_official_schema_validation() -> None:
    """CORRECTION: 8 of the 9 DateRange sub-blocks used a key
    ("Upto15Of9") absent from the official DateRangeTypeOS schema shape,
    and Deductions was missing its own required Depreciation key --
    Schedule OS's JSON was unconditionally schema-invalid whenever
    populated at all, for every ITR-3 return this engine could produce."""
    typed = ITR3Input(
        age_bracket="below_60", tax_regime="new",
        other_sources_income=OtherSourcesIncome(dividend_income=Decimal("5000")),
    )
    result = compute_itr3(typed)
    os_json = _schedule_os(result, typed)
    errors = list(_schedule_os_validator().iter_errors(os_json))
    assert not errors, "\n".join(e.message for e in errors)
