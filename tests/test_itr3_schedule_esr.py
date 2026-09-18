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
    assert _normalize_esr_source({}) is None
    assert _normalize_esr_source({"DeductionUs35": {}}) is None


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
