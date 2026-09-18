"""Tests for ITR-3 Schedule ESR (tracker row #19 -- Expenditure on
Scientific Research, deduction under section 35/35CCC/35CCD).

**Root cause, confirmed (not assumed) by reading both sides directly**:
the mapper (``draft_to_itr3_input.py``) read only
``draft.itr3BusinessWorkspace.scheduleESR`` (a typed field with zero
frontend writers anywhere, confirmed by grep) or
``draft.itr3BusinessWorkspace.core.get("ScheduleESR")`` -- but the real,
working editor (``ITR3BusinessAuxiliaryManager.tsx``, already covers
ScheduleESR in its own manifest) writes into
``draft.itr3BusinessWorkspace.auxiliary["ScheduleESR"]`` instead, traced
all the way up through ``ITR3BusinessWorkspace.tsx`` ->
``BusinessProfessionEntryManager.tsx`` -> ``ITRComputationPage.tsx``'s own
``handleChange``, which writes ``ITR3Auxiliary`` straight into
``draft.itr3BusinessWorkspace.auxiliary``. The exact same root cause
already found and fixed for Schedule DPM/DOA (tracker rows #15-18).

**A second, independent bug, same shape as DPM/DOA's own "realistic
partial input" fix**: the frontend's lazy ``pathSet()`` only ever creates
the exact nested path a taxpayer touches -- a return using only some of
Schedule ESR's 9 section rows leaves the other section keys genuinely
ABSENT from the saved draft, not present with zero values. The official
schema requires all 10 keys (9 sections + "Total") unconditionally, so
validating the raw dict directly would crash. Every section/leaf is now
defaulted to 0, and ``TotUs35`` (the "Total" row) is recomputed
server-side rather than trusted from the frontend's own last-sent value,
since it now feeds real tax computation (see below), not just disclosure.

**The "deduction not reflected in tax" prior finding was investigated and
found STALE, not true as of this push**: Schedule 14's own full closure
(2026-09-18, earlier this push) already wired Schedule BP's own item 28
(``DebPLUs35ExcessAmt``) into ``compute_pgbp()``'s real ``total_additions``
computation -- but via an INDEPENDENTLY-entered Schedule-BP-workspace
field, not derived from Schedule ESR's own typed total at all. Since the
official form's own item 28 text explicitly cites this figure as literally
"item x(4) of Schedule ESR" (not an independently-re-derived same-concept
number), this push additionally makes Schedule ESR's own computed total
authoritative for item 28 WHENEVER Schedule ESR data exists, falling back
to the raw Schedule-BP-entered value otherwise -- so a taxpayer's own
itemized ESR breakdown can never silently disagree with what Schedule BP
disclosed and what was actually taxed.

**A third, independent bug found on re-verification ("recheck if Schedule
19 is implemented end-to-end")**: the frontend's own ``AmtUs35Allowable``/
``ExcessAmtOverDebPL`` fields are marked ``readonly`` in its editor
(implying "auto-computed") but nothing computes them anywhere -- not the
frontend's own ``recompute()`` (confirmed by reading it in full), not the
mapper before this fix. Defaulting an absent field to 0 (this codebase's
general policy for genuinely-untouched fields elsewhere) would be WRONG
here: it would silently disclose a Rs.0 allowable deduction against real,
entered R&D expenditure. Verified against the actual current law (all 9
section-35 sub-clauses' historical 150%/200% weighted deductions were
phased down to a flat 100% by Finance Act 2020, effective AY 2021-22, with
no subsequent reversal) that the correct default is 100% of AmtDebPL --
*except* under the NEW tax regime, where CBDT's own official ITR-3
Validation Rules for AY 2026-27 (rule #354, quoted verbatim in the
mapper's own code comment) disallow 5 of the 9 sections entirely (the
third-party research-contribution ones: 35(1)(ii)/(iia)/(iii), 35(2AA),
35CCC). A first attempt at this regime check used ``str(values["tax_regime"])
== "new"`` -- genuinely wrong (Python's Enum ``__str__`` returns
``"TaxRegime.NEW"``, not ``"new"``, so this always evaluated False and
silently defeated the whole regime check) -- caught by the dedicated
new-regime test below actually exercising the path, not just by
inspection; fixed to a direct value comparison. A fourth bug, found while
tracing the tax-computation consequence of the regime disallowance
through to its end: when a new-regime section is disallowed (allowable <
debited), the shortfall is a disallowed EXPENSE that must be added BACK
into taxable business income (official rule #286: Schedule BP item
24(e)) -- without this, the already-debited-to-P&L expenditure would
silently escape tax entirely under the new regime. Wired via
``_esr_shortfall_addback()``, additive with (not replacing) the
taxpayer's own separately-entered item 24 figure.
"""

from __future__ import annotations

from decimal import Decimal

from jsonschema import Draft4Validator

from app.engine.itd.itr3_schema import get_itr3_schema_validator
from app.engine.draft_to_itr3_input import draft_to_itr3_input, _business_income, _normalize_esr_source
from app.engine.calculators.itr3 import compute as compute_itr3
from app.engine.itd.itr3 import build_itr3_json
from app.schemas.itr3 import ScheduleESR


def _schedule_validator(name: str) -> Draft4Validator:
    full = get_itr3_schema_validator().schema
    definition = dict(full["definitions"][name])
    definition["definitions"] = full["definitions"]
    return Draft4Validator(definition)


def _minimal_draft():
    from app.schemas.return_draft import Presumptive44AD, create_empty_draft

    draft = create_empty_draft("2026-27", "ITR-3", "new")
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


def _esr_section(amt_deb_pl: int, amt_allowable: int) -> dict:
    return {"DeductUs35": {
        "AmtDebPL": amt_deb_pl,
        "AmtUs35Allowable": amt_allowable,
        "ExcessAmtOverDebPL": max(0, amt_allowable - amt_deb_pl),
    }}


def test_esr_source_from_auxiliary_workspace_reaches_typed_schedule() -> None:
    """The real, working frontend write path -- confirms the auxiliary
    dead-end is fixed, not just the core/scheduleESR paths that were
    already (uselessly) checked before this fix."""
    draft = _minimal_draft()
    draft.itr3BusinessWorkspace.auxiliary["ScheduleESR"] = {
        "DeductionUs35": {
            "Section35_1_i": _esr_section(100000, 100000),
        }
    }
    typed_input, _ = draft_to_itr3_input(draft)
    assert typed_input.schedule_esr is not None
    assert typed_input.schedule_esr.DeductionUs35.Section35_1_i.DeductUs35.AmtDebPL == Decimal("100000")


def test_esr_realistic_partial_input_defaults_untouched_sections_to_zero() -> None:
    """A taxpayer who only used 2 of the 9 section rows -- the other 7
    section keys are genuinely absent from the raw dict, matching exactly
    what the frontend's lazy pathSet() actually produces. Must not crash."""
    draft = _minimal_draft()
    draft.itr3BusinessWorkspace.auxiliary["ScheduleESR"] = {
        "DeductionUs35": {
            "Section35_1_i": _esr_section(50000, 50000),
            "Section35_2AB": _esr_section(200000, 300000),
            # Every other section key (Section35_1_ii/iia/iii/iv, 2AA,
            # CCC, CCD, and the frontend's own TotUs35) is deliberately
            # absent here -- this is the realistic shape, not a contrived
            # edge case.
        }
    }
    typed_input, _ = draft_to_itr3_input(draft)
    esr = typed_input.schedule_esr
    assert esr is not None
    assert esr.DeductionUs35.Section35_1_ii.DeductUs35.AmtDebPL == Decimal("0")
    assert esr.DeductionUs35.Section35_CCD.DeductUs35.AmtDebPL == Decimal("0")
    # TotUs35 is recomputed server-side as the sum of the 9 sections, not
    # trusted from the (absent, in this case) frontend-sent value.
    assert esr.DeductionUs35.TotUs35.DeductUs35.AmtDebPL == Decimal("250000")
    assert esr.DeductionUs35.TotUs35.DeductUs35.AmtUs35Allowable == Decimal("350000")
    assert esr.DeductionUs35.TotUs35.DeductUs35.ExcessAmtOverDebPL == Decimal("100000")


def test_esr_all_zero_data_treated_as_no_genuine_claim() -> None:
    """A schedule explicitly present with every leaf at 0 (e.g. a section
    typed into then cleared back to 0) must not be mistaken for a real
    claim -- matching the established DPM/DOA precedent for this exact
    shape of ambiguity."""
    draft = _minimal_draft()
    draft.itr3BusinessWorkspace.auxiliary["ScheduleESR"] = {
        "DeductionUs35": {"Section35_1_i": _esr_section(0, 0)}
    }
    typed_input, _ = draft_to_itr3_input(draft)
    assert typed_input.schedule_esr is None


def test_esr_absent_from_workspace_stays_none() -> None:
    draft = _minimal_draft()
    typed_input, _ = draft_to_itr3_input(draft)
    assert typed_input.schedule_esr is None


def test_esr_normalize_source_returns_none_for_empty_mapping() -> None:
    assert _normalize_esr_source({}, is_new_regime=False) is None
    assert _normalize_esr_source({"DeductionUs35": {}}, is_new_regime=False) is None


def test_esr_new_regime_disallows_five_third_party_contribution_sections() -> None:
    """Official CBDT ITR-3 Validation Rules for AY 2026-27, rule #354
    (quoted verbatim in the mapper's own comment): under the new regime,
    column 3 (AmtUs35Allowable) cannot exceed zero for 35(1)(ii)/(iia)/
    (iii), 35(2AA), and 35CCC -- third-party research-contribution
    sections the new regime disallows, same principle as 80G/80C. The
    other 4 sections (the taxpayer's own direct R&D/skill-development
    expenditure) remain 100% allowable under either regime."""
    draft = _minimal_draft()  # _minimal_draft() uses the NEW regime.
    draft.itr3BusinessWorkspace.auxiliary["ScheduleESR"] = {
        "DeductionUs35": {
            # Disallowed under the new regime -- AmtUs35Allowable must
            # come out as 0 despite real expenditure being debited.
            "Section35_1_ii": {"DeductUs35": {"AmtDebPL": 100000}},
            "Section35_2AA": {"DeductUs35": {"AmtDebPL": 50000}},
            # NOT in the disallowed list -- stays 100% allowable even
            # under the new regime.
            "Section35_1_i": {"DeductUs35": {"AmtDebPL": 200000}},
            "Section35_2AB": {"DeductUs35": {"AmtDebPL": 80000}},
        }
    }
    typed_input, _ = draft_to_itr3_input(draft)
    esr = typed_input.schedule_esr
    assert esr is not None
    assert esr.DeductionUs35.Section35_1_ii.DeductUs35.AmtDebPL == Decimal("100000")
    assert esr.DeductionUs35.Section35_1_ii.DeductUs35.AmtUs35Allowable == Decimal("0")
    assert esr.DeductionUs35.Section35_2AA.DeductUs35.AmtUs35Allowable == Decimal("0")
    assert esr.DeductionUs35.Section35_1_i.DeductUs35.AmtUs35Allowable == Decimal("200000")
    assert esr.DeductionUs35.Section35_2AB.DeductUs35.AmtUs35Allowable == Decimal("80000")
    # Total allowable = 200000 + 80000 only (the two disallowed sections
    # contribute 0, not their AmtDebPL).
    assert esr.DeductionUs35.TotUs35.DeductUs35.AmtUs35Allowable == Decimal("280000")


def test_esr_new_regime_shortfall_added_back_into_business_income() -> None:
    """The disallowed new-regime expenditure (already debited to P&L,
    reducing net profit) must be added BACK into taxable business income
    via item 24(e) -- official rule #286 -- or it would silently escape
    tax entirely. Additive with the taxpayer's own separately-entered
    item 24 figure, not a replacement."""
    draft = _minimal_draft()  # new regime
    draft.itr3BusinessWorkspace.core["ITR3ScheduleBP"] = {
        "BusinessIncOthThanSpec": {
            "ProfBfrTaxPL": 500000,
            # An unrelated, real item-24 entry that must be preserved
            # alongside the ESR-derived addback, not overwritten by it.
            "AnyOthIncNotInclInExpDisallowPL": 10000,
        }
    }
    draft.itr3BusinessWorkspace.auxiliary["ScheduleESR"] = {
        "DeductionUs35": {
            "Section35_1_ii": {"DeductUs35": {"AmtDebPL": 100000}},  # disallowed -> 100000 shortfall
            "Section35_1_i": {"DeductUs35": {"AmtDebPL": 40000}},   # allowed -> 0 shortfall
        }
    }
    typed_input, _ = draft_to_itr3_input(draft)
    # 10000 (taxpayer's own entry) + 100000 (ESR shortfall) + 0 (allowed section).
    assert typed_input.business_income.other_additions == Decimal("110000")


def test_esr_old_regime_no_shortfall_addback() -> None:
    """Under the old regime, every section is 100% allowable, so there is
    never a shortfall to add back -- item 24 must equal only whatever the
    taxpayer separately entered."""
    from app.schemas.return_draft import create_empty_draft, Presumptive44AD

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
    draft.itr3BusinessWorkspace.core["ITR3ScheduleBP"] = {
        "BusinessIncOthThanSpec": {"AnyOthIncNotInclInExpDisallowPL": 5000}
    }
    draft.itr3BusinessWorkspace.auxiliary["ScheduleESR"] = {
        "DeductionUs35": {"Section35_1_ii": {"DeductUs35": {"AmtDebPL": 100000}}}
    }
    typed_input, _ = draft_to_itr3_input(draft)
    assert typed_input.business_income.other_additions == Decimal("5000")


def test_esr_old_regime_allows_all_nine_sections_at_100_percent() -> None:
    """Same five sections that are disallowed under the new regime (see
    test above) must reach 100% allowable under the OLD regime -- the
    new-regime restriction must not leak into old-regime returns."""
    from app.schemas.return_draft import create_empty_draft, Presumptive44AD

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
    draft.itr3BusinessWorkspace.auxiliary["ScheduleESR"] = {
        "DeductionUs35": {
            "Section35_1_ii": {"DeductUs35": {"AmtDebPL": 100000}},
            "Section35_CCC": {"DeductUs35": {"AmtDebPL": 30000}},
        }
    }
    typed_input, _ = draft_to_itr3_input(draft)
    esr = typed_input.schedule_esr
    assert esr is not None
    assert esr.DeductionUs35.Section35_1_ii.DeductUs35.AmtUs35Allowable == Decimal("100000")
    assert esr.DeductionUs35.Section35_CCC.DeductUs35.AmtUs35Allowable == Decimal("30000")


def test_business_income_derives_section35_excess_deduction_from_esr_total() -> None:
    """Schedule BP's own item 28 (DebPLUs35ExcessAmt) must reflect
    Schedule ESR's own computed total whenever ESR data exists -- the
    official form's own item 28 text cites this figure as literally 'item
    x(4) of Schedule ESR', not an independent re-entry."""
    draft = _minimal_draft()
    draft.itr3BusinessWorkspace.core["ITR3ScheduleBP"] = {
        "BusinessIncOthThanSpec": {
            "ProfBfrTaxPL": 500000,
            # A stale/independently-entered value that must be OVERRIDDEN
            # by the real Schedule ESR total below, not silently trusted.
            "DebPLUs35ExcessAmt": 999999,
        }
    }
    draft.itr3BusinessWorkspace.auxiliary["ScheduleESR"] = {
        "DeductionUs35": {
            "Section35_2AB": _esr_section(100000, 150000),  # excess = 50000
        }
    }
    typed_input, _ = draft_to_itr3_input(draft)
    assert typed_input.business_income.section35_excess_deduction == Decimal("50000")


def test_business_income_falls_back_to_raw_bp_value_when_no_esr_data() -> None:
    """A taxpayer who only ever used Schedule BP's own quick field (never
    touched Schedule ESR at all) must keep working exactly as before this
    push -- the established Schedule 14 precedent, unregressed."""
    draft = _minimal_draft()
    draft.itr3BusinessWorkspace.core["ITR3ScheduleBP"] = {
        "BusinessIncOthThanSpec": {
            "ProfBfrTaxPL": 500000,
            "DebPLUs35ExcessAmt": 75000,
        }
    }
    typed_input, _ = draft_to_itr3_input(draft)
    assert typed_input.schedule_esr is None
    assert typed_input.business_income.section35_excess_deduction == Decimal("75000")


def test_business_income_direct_call_esr_none_uses_raw_field() -> None:
    """Unit-level proof that `_business_income` itself (not just the full
    mapper) honors the None-schedule_esr fallback path."""
    draft = _minimal_draft()
    draft.itr3BusinessWorkspace.core["ITR3ScheduleBP"] = {
        "BusinessIncOthThanSpec": {"DebPLUs35ExcessAmt": 12345}
    }
    bi = _business_income(draft, schedule_esr=None)
    assert bi.section35_excess_deduction == Decimal("12345")


def test_schedule_esr_reaches_json_and_validates_against_official_schema() -> None:
    draft = _minimal_draft()
    draft.itr3BusinessWorkspace.auxiliary["ScheduleESR"] = {
        "DeductionUs35": {
            "Section35_1_i": _esr_section(100000, 100000),
            "Section35_1_ii": _esr_section(50000, 75000),
            "Section35_2AB": _esr_section(200000, 300000),
        }
    }
    typed_input, _ = draft_to_itr3_input(draft)
    document = build_itr3_json(compute_itr3(typed_input), typed_input)
    itr3_doc = document["ITR"]["ITR3"]
    assert "ScheduleESR" in itr3_doc
    errors = list(_schedule_validator("ScheduleESR").iter_errors(itr3_doc["ScheduleESR"]))
    assert not errors, "\n".join(e.message for e in errors)
    tot = itr3_doc["ScheduleESR"]["DeductionUs35"]["TotUs35"]["DeductUs35"]
    assert tot["AmtDebPL"] == 350000
    assert tot["AmtUs35Allowable"] == 475000
    assert tot["ExcessAmtOverDebPL"] == 125000
    # Every one of the 6 untouched sections must still be present (schema
    # requires all 10 keys) and explicitly zero, not fabricated nonzero.
    assert itr3_doc["ScheduleESR"]["DeductionUs35"]["Section35_1_iii"]["DeductUs35"]["AmtDebPL"] == 0
    # And Schedule BP's own item 28 must equal ESR's own total -- the two
    # numbers can never silently disagree.
    bp = itr3_doc["ITR3ScheduleBP"]["BusinessIncOthThanSpec"]
    assert bp["DebPLUs35ExcessAmt"] == 125000


def test_schedule_esr_omitted_when_no_data_entered() -> None:
    draft = _minimal_draft()
    typed_input, _ = draft_to_itr3_input(draft)
    document = build_itr3_json(compute_itr3(typed_input), typed_input)
    itr3_doc = document["ITR"]["ITR3"]
    assert "ScheduleESR" not in itr3_doc


def test_esr_deduction_detail_bounds_match_official_schema() -> None:
    """Every one of the three leaf fields in `DeductUs35` carries the
    schema's own ge=0/le=99999999999999 bound, matching the established
    bound-fidelity precedent from Schedules 8/9/10."""
    import pytest
    from pydantic import ValidationError
    from app.schemas.itr3 import ESRDeductionDetail

    with pytest.raises(ValidationError):
        ESRDeductionDetail(AmtDebPL=Decimal("-1"), AmtUs35Allowable=Decimal("0"), ExcessAmtOverDebPL=Decimal("0"))
    with pytest.raises(ValidationError):
        ESRDeductionDetail(AmtDebPL=Decimal("100000000000000"), AmtUs35Allowable=Decimal("0"), ExcessAmtOverDebPL=Decimal("0"))
    # A default-constructed detail is valid (every leaf defaults to 0,
    # matching the schema's own per-field default).
    assert ESRDeductionDetail().AmtDebPL == Decimal("0")


def test_schedule_esr_extra_field_rejected() -> None:
    """`extra=\"forbid\"` on every ESR class fails fast on a field-name
    mismatch instead of silently misshaping the JSON (Schedule 9's own
    established precedent for this class of bug)."""
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ScheduleESR.model_validate({"DeductionUs35": {
            **{k: {"DeductUs35": {"AmtDebPL": 0, "AmtUs35Allowable": 0, "ExcessAmtOverDebPL": 0}}
               for k in ("Section35_1_i", "Section35_1_ii", "Section35_1_iia", "Section35_1_iii",
                         "Section35_1_iv", "Section35_2AA", "Section35_2AB", "Section35_CCC",
                         "Section35_CCD", "TotUs35")},
            "BogusExtraKey": 1,
        }})
