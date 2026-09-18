"""Tests for the ITR-3 Schedule CG special-rate tax-computation fix.

**The bug**: ITR-3's calculator never called ``compute_112()`` (section 112,
LTCG other than 112A, 12.5% for AY 2026-27) at all -- every ordinary
long-term capital gain outside 112A/111A was silently taxed at ORDINARY
SLAB rates instead of its own special rate. Root causes, all fixed here:

1. ``compute_ltcg()`` was never passed ``is_resident``, so the section
   112(1)(a) second-proviso relief (protects a resident who acquired
   land/building before 23-Jul-2024 from paying MORE tax under the new
   12.5%-non-indexed regime than the old 20%-indexed regime would have
   required) could never trigger.
2. CYLA/BFLA lumped EVERY capital-gain rate bucket (111A/112/112A/DTAA)
   into a single generic bucket with no rate differentiation at all.
3. Schedule SI entries (111A/112A) were built from RAW pre-loss values,
   not post-CYLA/BFLA values -- a loss set off against the lumped bucket
   never actually reduced the special-rate tax; its benefit was instead
   silently "wasted" via ``normal_income``'s own ``max(z, ...)`` clip.
4. There was no ``compute_112()`` call anywhere in the calculator.
5. ``cg_stcg_dtaa_entries``/``cg_ltcg_dtaa_entries`` and the NRI proviso-48/
   115F fields (``cg_nri_*``) were disclosed by the ITD builder but never
   merged into ``stcg_result``/``ltcg_result`` -- correctly shown on the
   filed JSON, but with ZERO effect on the actual tax computed.

Fixed by porting ITR-2's own already-correct architecture (calculators/
itr2.py) via the newly-shared ``app.engine.schedules.capital_gains.
post_loss_cg_baskets()`` (formerly ITR-2's own private
``_post_loss_cg_baskets()``), adapted for ITR-3's lack of an FII/FPI
assessee concept (ITR-3 has no genuine flat-30% STCG basket at all).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from jsonschema import Draft4Validator

from app.engine.calculators.itr3 import compute as compute_itr3
from app.engine.itd.itr3 import build_itr3_json
from app.engine.itd.itr3_schema import get_itr3_schema_validator
from app.schemas.itr1 import HousePropertyIncome, PropertyType
from app.schemas.itr2 import CGDtaaEntry, CGTransaction, CGAssetType, ResidentialStatus
from app.schemas.itr3 import ITR3Input


def _other_ltcg_transaction(consideration: Decimal, cost: Decimal) -> CGTransaction:
    return CGTransaction(
        asset_type=CGAssetType.OTHER,
        date_of_transfer=date(2026, 3, 31),
        explicit_long_term=True,
        full_consideration=consideration,
        cost_of_acquisition=cost,
    )


def test_ltcg_other_taxed_at_section_112_rate_not_slab() -> None:
    """The core bug: an 80L LTCG (non-112A, non-land) must be taxed at
    section 112's 12.5% (Rs 10,00,000), not folded into slab-rate
    ``normal_income`` (which would tax it far higher via the old-regime
    slabs)."""
    inp = ITR3Input(
        tax_regime="old", age_bracket="below_60",
        cg_transactions=[_other_ltcg_transaction(Decimal("10000000"), Decimal("2000000"))],
    )
    r = compute_itr3(inp)
    assert r.capital_gains_income == Decimal("8000000")
    assert r.special_rate_tax == Decimal("1000000")  # 8,000,000 * 12.5%
    assert r.slab_tax == Decimal("0")
    si_by_section = {e.section: e for e in r.schedules["si"].entries}
    assert "112" in si_by_section
    assert si_by_section["112"].taxable_income == Decimal("8000000")
    assert si_by_section["112"].tax_amount == Decimal("1000000")


def test_hp_loss_reduces_post_loss_special_rate_bucket_not_wasted() -> None:
    """A current-year HP loss set off (via CYLA) against the section-112
    bucket must correctly reduce the SPECIAL-RATE tax on that bucket --
    previously the loss was set off against the lumped CG total but the
    Schedule SI entry was still computed from the raw pre-loss figure, so
    the loss's benefit vanished into thin air (silently absorbed only by
    ``normal_income``'s floor-at-zero clip, which had nothing to clip since
    LTCG-other was never in ``normal_income`` to begin with pre-fix)."""
    hp = HousePropertyIncome(
        property_type=PropertyType.SELF_OCCUPIED,
        home_loan_interest_paid=Decimal("300000"),  # capped at 2L self-occupied
    )
    inp = ITR3Input(
        tax_regime="old", age_bracket="below_60",
        cg_transactions=[_other_ltcg_transaction(Decimal("10000000"), Decimal("2000000"))],
        house_property_income=hp,
    )
    r = compute_itr3(inp)
    assert r.house_property_income == Decimal("-200000")
    assert r.cyla_total_set_off == Decimal("200000")
    post_loss_cg = r.schedules["post_loss_cg"]
    assert post_loss_cg["112"] == Decimal("7800000")
    assert r.special_rate_tax == Decimal("975000")  # 7,800,000 * 12.5%
    assert r.capital_gains_income == Decimal("7800000")


def test_section_112_1a_second_proviso_relief_applies_for_resident() -> None:
    """A resident who acquired land/building before 23-Jul-2024, where
    indexation would have produced LESS tax under the old 20%-indexed
    regime than the new 12.5%-non-indexed regime, is protected by the
    second proviso to section 112(1)(a) -- `is_resident` must now reach
    `compute_ltcg()` (it never did before this fix, so this relief could
    never trigger for any ITR-3 filer)."""
    asset = CGTransaction(
        asset_type=CGAssetType.LAND_BUILDING,
        date_of_acquisition=date(2005, 1, 1),
        date_of_transfer=date(2026, 1, 1),
        full_consideration=Decimal("10000000"),
        cost_of_acquisition=Decimal("1000000"),
        indexed_cost=Decimal("8000000"),
    )
    inp = ITR3Input(tax_regime="old", age_bracket="below_60", cg_transactions=[asset])
    r = compute_itr3(inp)
    ltcg = r.schedules["cg"].ltcg
    # primary (non-indexed) taxable = 9,000,000 @ 12.5% = 1,125,000
    # eiB (indexed) taxable = 2,000,000 @ 20% = 400,000
    # excess to ignore = 1,125,000 - 400,000 = 725,000
    assert ltcg.total_excess_tax_112_1a == Decimal("725000")
    si_by_section = {e.section: e for e in r.schedules["si"].entries}
    assert si_by_section["112"].tax_amount == Decimal("400000")


def test_section_112_1a_second_proviso_relief_not_applied_for_non_resident() -> None:
    """The identical transaction for a non-resident gets NO relief --
    `compute_ltcg()`'s own `is_resident` gate must correctly zero it."""
    asset = CGTransaction(
        asset_type=CGAssetType.LAND_BUILDING,
        date_of_acquisition=date(2005, 1, 1),
        date_of_transfer=date(2026, 1, 1),
        full_consideration=Decimal("10000000"),
        cost_of_acquisition=Decimal("1000000"),
        indexed_cost=Decimal("8000000"),
    )
    inp = ITR3Input(
        tax_regime="old", age_bracket="below_60", cg_transactions=[asset],
        residential_status=ResidentialStatus.NON_RESIDENT,
    )
    r = compute_itr3(inp)
    ltcg = r.schedules["cg"].ltcg
    assert ltcg.total_excess_tax_112_1a == Decimal("0")
    si_by_section = {e.section: e for e in r.schedules["si"].entries}
    assert si_by_section["112"].tax_amount == Decimal("1125000")  # full, un-relieved tax


def test_nri_stcg_proviso48_entries_now_actually_taxed() -> None:
    """`cg_nri_stcg_stt_paid`/`cg_nri_stcg_stt_not_paid` (Schedule CG A3a/
    A3b) were previously disclosed by the ITD builder but never merged
    into `stcg_result` by the calculator -- zero tax effect. Confirm both
    now flow into the taxed total."""
    inp = ITR3Input(
        tax_regime="old", age_bracket="below_60",
        residential_status=ResidentialStatus.NON_RESIDENT,
        cg_nri_stcg_stt_paid=Decimal("500000"),
        cg_nri_stcg_stt_not_paid=Decimal("300000"),
    )
    r = compute_itr3(inp)
    assert r.capital_gains_income == Decimal("800000")
    si_by_section = {e.section: e for e in r.schedules["si"].entries}
    assert si_by_section["111A"].taxable_income == Decimal("500000")
    assert si_by_section["111A"].tax_amount == Decimal("100000")  # 20%
    # The STT-not-paid 300,000 lands in the ordinary slab-rate bucket, not
    # a special-rate row.
    assert r.slab_tax > Decimal("0")


def test_dtaa_ltcg_entry_generates_its_own_special_rate_si_row() -> None:
    """`cg_ltcg_dtaa_entries` (Schedule CG B12) previously had zero tax
    effect at all (`ltcg_dtaa` was hardcoded to zero in the calculator,
    never populated from this field). A DTAA claim re-tags part of an
    ALREADY-DECLARED ordinary CG transaction for special-rate treatment
    (mirrors ITR-2's own identical scoping decision -- it is not a
    separate additive income source) -- a chargeable-in-India claim must
    now produce its own Schedule SI row at its own treaty rate instead of
    taxing the same rupee at the ordinary section-112 rate."""
    dtaa = CGDtaaEntry(
        amount=Decimal("1000000"),
        item_no_incl="B1g",
        country_name="Mauritius",
        country_code="MU",
        dtaa_article="13",
        rate_as_per_treaty=Decimal("10"),
        sec_it_act="112",
        rate_as_per_it_act=Decimal("12.5"),
        applicable_rate=Decimal("10"),
    )
    inp = ITR3Input(
        tax_regime="old", age_bracket="below_60",
        residential_status=ResidentialStatus.NON_RESIDENT,
        cg_transactions=[_other_ltcg_transaction(Decimal("1000000"), Decimal("0"))],
        cg_ltcg_dtaa_entries=[dtaa],
    )
    r = compute_itr3(inp)
    assert r.capital_gains_income == Decimal("1000000")
    si_by_section = {e.section: e for e in r.schedules["si"].entries}
    assert "112" not in si_by_section  # fully re-tagged to DTAA, none left at the ordinary rate
    dtaa_entries = [e for e in r.schedules["si"].entries if e.tax_rate_pct == Decimal("10")]
    assert len(dtaa_entries) == 1
    assert dtaa_entries[0].taxable_income == Decimal("1000000")
    assert dtaa_entries[0].tax_amount == Decimal("100000")


def test_dtaa_ltcg_entry_not_chargeable_excluded_from_income_entirely() -> None:
    """A treaty rate of NIL (`rate_as_per_treaty=0`) means "not chargeable
    in India" (A8a/B11a) -- the declared gain it re-tags must vanish from
    taxable income entirely, not just skip the special-rate row."""
    dtaa = CGDtaaEntry(
        amount=Decimal("1000000"),
        item_no_incl="B1g",
        country_name="Mauritius",
        country_code="MU",
        dtaa_article="13",
        rate_as_per_treaty=Decimal("0"),
        sec_it_act="112",
        rate_as_per_it_act=Decimal("12.5"),
    )
    inp = ITR3Input(
        tax_regime="old", age_bracket="below_60",
        residential_status=ResidentialStatus.NON_RESIDENT,
        cg_transactions=[_other_ltcg_transaction(Decimal("1000000"), Decimal("0"))],
        cg_ltcg_dtaa_entries=[dtaa],
    )
    r = compute_itr3(inp)
    assert r.capital_gains_income == Decimal("0")
    assert r.special_rate_tax == Decimal("0")


def _minimal_draft():
    from app.schemas.return_draft import Presumptive44AD, create_empty_draft

    draft = create_empty_draft("2026-27", "ITR-3", "old")
    draft.personal.pan = "ABCDE1234F"
    draft.personal.firstName = "Ravi"
    draft.personal.surnameOrOrgName = "Kumar"
    draft.personal.dateOfBirth = "1980-01-01"
    draft.personal.flatNo = "1"
    draft.personal.localityOrArea = "Central"
    draft.personal.city = "Delhi"
    draft.personal.stateCode = "07"
    draft.personal.countryCode = "91"
    draft.personal.pinCode = "110001"
    draft.personal.mobile = "9876543210"
    draft.personal.email = "ravi@example.com"
    draft.verification.place = "Delhi"
    draft.verification.date = "2026-07-31"
    draft.verification.declarationAccepted = True
    draft.businesses = [
        Presumptive44AD(id="b1", natureCode="01001", digitalReceipts=Decimal("1000000"), declaredIncome=Decimal("60000")),
    ]
    return draft


def _schedule_validator(name: str) -> Draft4Validator:
    full = get_itr3_schema_validator().schema
    definition = dict(full["definitions"][name])
    definition["definitions"] = full["definitions"]
    return Draft4Validator(definition)


def test_ltcg_other_reaches_schedule_si_json_and_validates() -> None:
    """End-to-end: a filer with an ordinary section-112 LTCG (via the NRI
    proviso-48 bare-figure item, reused here purely as a real-world source
    of "LTCG other than 112A") must produce a schema-valid Schedule SI that
    actually carries a "21" (section 112) row -- not just a Schedule CG
    disclosure with no corresponding special-rate tax. (A full-document
    validation is not used here: `_minimal_draft()`'s bare Presumptive44AD
    business trips unrelated, pre-existing indirect-tax schedule
    requirements -- genuinely out of scope for this Schedule CG fix.)"""
    from app.engine.draft_to_itr3_input import draft_to_itr3_input

    draft = _minimal_draft()
    draft.capitalGainsSchedule.ltNriProviso48.ltcgWithoutBenefit = Decimal("8000000")
    typed_input, _ = draft_to_itr3_input(draft)
    result = compute_itr3(typed_input)
    document = build_itr3_json(result, typed_input)
    itr3_doc = document["ITR"]["ITR3"]

    cg_errors = list(_schedule_validator("ScheduleCGFor23").iter_errors(itr3_doc["ScheduleCGFor23"]))
    assert not cg_errors, "\n".join(e.message for e in cg_errors)
    si = itr3_doc["ScheduleSI"]
    si_errors = list(_schedule_validator("ScheduleSI").iter_errors(si))
    assert not si_errors, "\n".join(e.message for e in si_errors)

    codes = {row["SecCode"] for row in si["SplCodeRateTax"]}
    assert "21" in codes  # section 112, 12.5%, LTCG other than 112A
    assert result.special_rate_tax == Decimal("1000000")
