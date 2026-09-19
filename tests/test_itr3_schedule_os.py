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
entry for the full write-up.

**Update (2026-09-19, same day): the follow-on build-out this file's own
docstring originally deferred (race horse activity, 56(2)(x) gift
sub-breakdown, section 89A, DTAA-OS, accumulated PF u/s 111, the
115BBG/115BBJ/115BBA/111/115A-family SI-section set, dividend/interest
sub-classification, and the richer Section 57 deduction set) is now
closed too, ported directly from ITR-2's own already-correct
implementation -- including two genuine bugs found and fixed IN ITR-2
itself first (CYLA special-rate contamination, item 4/5 gating), so this
port starts from the fixed logic, not the pre-fix version. See the
tests below this comment (`Section: full build-out`) and the tracker's
own updated Schedule 24 entry for the complete write-up.
"""

from __future__ import annotations

from decimal import Decimal

from jsonschema import Draft4Validator

from app.engine.calculators.itr3 import compute as compute_itr3
from app.engine.itd.itr3 import _schedule_os, _partb_ti
from app.engine.itd.itr3_schema import get_itr3_schema_validator
from app.schemas.itr1 import OtherSourcesIncome
from app.schemas.itr2 import (
    ScheduleSIEntry, OSGiftBreakdown, OSAccumulatedPFEntry, OSSpecialRateEntry,
    OSDtaaEntry, OSDeductions, OSRaceHorseActivity,
)
from app.schemas.itr3 import ITR3Input
from app.schemas.return_draft import create_empty_draft, WinningIncome, Presumptive44AD
from app.engine.draft_to_itr3_input import draft_to_itr3_input


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
    payload = _partb_ti(result, typed)
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

    partb = _partb_ti(result, typed)
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


# ===========================================================================
# Section: full build-out (2026-09-19) -- race horse, gifts, PF, section
# 89A, DTAA-OS, and the NRI/FII 115A-family, ported from ITR-2's own
# already-correct (and, for two bugs, freshly-corrected) implementation.
# ===========================================================================

def _base_draft():
    draft = create_empty_draft("2026-27", "ITR-3", "old")
    draft.personal.pan = "ABCDE1234F"
    draft.personal.firstName = "Test"
    draft.personal.surnameOrOrgName = "User"
    draft.personal.dateOfBirth = "1980-01-01"
    draft.personal.flatNo = "1"
    draft.personal.localityOrArea = "Central"
    draft.personal.city = "Delhi"
    draft.personal.stateCode = "07"
    draft.personal.countryCode = "91"
    draft.personal.pinCode = "110001"
    draft.personal.mobile = "9876543210"
    draft.personal.email = "test@example.com"
    draft.verification.place = "Delhi"
    draft.verification.date = "2026-07-31"
    draft.verification.declarationAccepted = True
    draft.businesses = [Presumptive44AD(id="b1", natureCode="01001", digitalReceipts=Decimal("1000000"), declaredIncome=Decimal("60000"))]
    return draft


def test_lottery_and_race_horse_profit_both_reach_gti_via_draft_mapper() -> None:
    """End-to-end: mapper -> calculator -> GTI, for a draft with both a
    lottery win and a race-horse-activity profit."""
    draft = _base_draft()
    draft.otherSources.winnings = [
        WinningIncome(id="w1", type="LOTTERY", grossAmount=Decimal("100000")),
        WinningIncome(id="w2", type="RACE_HORSE_ACTIVITY", receipts=Decimal("500000"), deductionUs57=Decimal("50000")),
    ]
    typed, _ = draft_to_itr3_input(draft)
    result = compute_itr3(typed)
    assert result.gross_total_income == Decimal("610000")  # 60000 biz + 100000 lottery + 450000 racehorse
    assert result.special_rate_tax == Decimal("30000")


def test_race_horse_loss_excluded_from_gti_and_carried_to_cfl() -> None:
    """Section 74A(3): a race-horse ACTIVITY loss never enters CYLA/BFLA --
    it carries straight to CFL with its own 4-year limit."""
    draft = _base_draft()
    draft.otherSources.winnings = [
        WinningIncome(id="w1", type="RACE_HORSE_ACTIVITY", receipts=Decimal("100000"), deductionUs57=Decimal("300000")),
    ]
    typed, _ = draft_to_itr3_input(draft)
    result = compute_itr3(typed)
    assert result.gross_total_income == Decimal("60000")  # business only, loss excluded
    cfl = result.schedules.get("cfl")
    assert {"head": "RaceHorse", "sub_category": None, "loss_cf": Decimal("200000")} in cfl


def test_hp_loss_does_not_absorb_against_lottery_income_itr3() -> None:
    """Mirrors the equivalent ITR-2 fix (row #260) -- special-rate OS
    income is not a valid CYLA loss-absorption target for ITR-3 either."""
    from app.schemas.itr1 import HousePropertyIncome, PropertyType
    from app.schemas.itr3 import BusinessIncome

    typed = ITR3Input(
        age_bracket="below_60", tax_regime="old", pti_entries=[],
        business_income=BusinessIncome(net_profit_before_tax=Decimal("0")),
        house_properties=[HousePropertyIncome(property_type=PropertyType.SELF_OCCUPIED, home_loan_interest_paid=Decimal("200000"))],
        si_entries=[_lottery_entry(Decimal("500000"))],
    )
    result = compute_itr3(typed)
    assert result.cyla_total_set_off == Decimal("0")
    assert result.gross_total_income == Decimal("500000")


def test_gift_pf_nri_family_and_dtaa_os_all_reach_gti_and_validate() -> None:
    """Gift income (56(2)(x)), accumulated PF (s.111), the NRI/FII
    115A-family dropdown, and DTAA-OS income all correctly reach GTI and
    produce schema-valid Schedule OS JSON, with no double-counting."""
    typed = ITR3Input(
        age_bracket="below_60", tax_regime="new", pti_entries=[],
        other_sources_income=OtherSourcesIncome(income_56_2_x=Decimal("60000")),
        os_gift_breakdown=OSGiftBreakdown(aggregate_without_consideration=Decimal("60000")),
        os_pf_income_benefit=Decimal("40000"), os_pf_tax_benefit=Decimal("8000"),
        os_pf_accumulated_entries=[OSAccumulatedPFEntry(assessment_year="2024-25", income_benefit=Decimal("40000"), tax_benefit=Decimal("8000"))],
        si_entries=[ScheduleSIEntry(section="111", gross_income=Decimal("40000"))],
        os_special_rate_entries=[OSSpecialRateEntry(source_description="5A1ai", source_amount=Decimal("200000"))],
        os_dtaa_entries=[OSDtaaEntry(
            amount=Decimal("50000"), nature_of_income="1c", country_name="USA", country_code="2",
            dtaa_article="11", rate_as_per_treaty=Decimal("15"), rate_as_per_it_act=Decimal("30"),
            tax_residency_certificate="Y", item_no_incl="56i", applicable_rate=Decimal("15"),
        )],
    )
    result = compute_itr3(typed)
    assert result.gross_total_income == Decimal("350000")  # 60000+40000+200000+50000

    os_json = _schedule_os(result, typed)
    errors = list(_schedule_os_validator().iter_errors(os_json))
    assert not errors, "\n".join(e.message for e in errors)
    block = os_json["IncOthThanOwnRaceHorse"]
    assert block["Tot562x"] == 60000
    assert block["TaxAccumulatedBalRecPF"]["TotalIncomeBenefit"] == 40000
    assert block["OthersGross"] == 200000
    assert block["IncChargblSplRateOS"]["NRIOsDTAA"]["NRIDTAADtlsSchOS"][0]["DTAAamt"] == 50000

    partb = _partb_ti(result, typed)
    assert partb["IncFromOS"]["TotIncFromOS"] == 350000
    assert partb["IncFromOS"]["TotIncFromOS"] == result.gross_total_income


def test_race_horse_json_block_and_schema_validates() -> None:
    typed = ITR3Input(
        age_bracket="below_60", tax_regime="old", pti_entries=[],
        os_race_horse=OSRaceHorseActivity(receipts=Decimal("500000"), deduction_us57=Decimal("50000"), balance=Decimal("450000")),
    )
    result = compute_itr3(typed)
    os_json = _schedule_os(result, typed)
    errors = list(_schedule_os_validator().iter_errors(os_json))
    assert not errors, "\n".join(e.message for e in errors)
    assert os_json["IncFromOwnHorse"]["BalanceOwnRaceHorse"] == 450000
    assert os_json["IncFromOwnHorse"]["Receipts"] == 500000


def test_general_section_57_deduction_excludes_special_rate_income() -> None:
    """The Section 57 general deduction (expenses/depreciation/eligible
    interest) must reduce ONLY normal-rate OS income, never special-rate
    SI-section income -- mirrors the equivalent ITR-2 fix."""
    typed = ITR3Input(
        age_bracket="below_60", tax_regime="new", pti_entries=[],
        other_sources_income=OtherSourcesIncome(savings_bank_interest=Decimal("10000")),
        os_deductions=OSDeductions(expenses=Decimal("100000")),  # far exceeds normal-rate income
        si_entries=[_lottery_entry(Decimal("500000"))],
    )
    result = compute_itr3(typed)
    # Normal-rate income fully absorbed by the deduction (floored at 0),
    # but the 500000 lottery income must remain fully taxed, untouched.
    assert result.special_rate_tax == Decimal("150000")
    assert result.gross_total_income == Decimal("500000")
