# Taxify ITR-4 AY 2026–27 Frontend Field Audit

## 1. Scope and starting point

This document begins the same depth of audit already completed for ITR-1
(`Docs/ITR1_FRONTEND_AND_SERIALIZATION_AUDIT_AY2026_27.md`, 24 sections): frontend field
coverage, schedule-by-schedule re-audit, systematic validator review, official CBDT Validation
Rules cross-reference, and official JSON schema constraint compliance — for ITR-4, per the
user's explicit instruction to move to ITR-4 next using the same methodology and
cross-reference documents.

This first entry covers what was found in the initial architecture reconnaissance pass,
dominated by one severe, shared-root-cause finding (§2) discovered before the systematic
per-section audit had properly begun. Later sections will fill in as the ITR-4-equivalent of
ITR-1's §2-§18 passes are completed.

### 1.1 Architecture starting point — ITR-4 is not a fresh audit target

Unlike where the ITR-1 audit started, ITR-4's mapper (`app/engine/draft_to_itr4_input.py`) is
not a duplicate, independently-drifting implementation. Its own docstring states it directly:

> "The duplicate-mapper problem the ITR-1 audit called out as 'the single biggest source of
> *works in compute, fails in CBDT* bugs' is eliminated for ITR-4 here."

Confirmed by reading it: salary, house property (single-property only — see §1.2), other
sources, Chapter VI-A deductions, capital gains (restricted 112A), TDS/TCS, and tax payments
all delegate to the *exact same* private helper functions already implemented and audited in
`app/engine/draft_to_itr1_input.py` (`_map_salary`, `_map_house_properties`, `_map_deductions`,
`_map_capital_gains`, `_map_tds`, `_map_tds3`, `_map_tcs`, `_map_tax_payments`, etc.) — one
implementation, not two. This means:

- **Every fix already made to a shared helper during the ITR-1 audit automatically applies to
  ITR-4 too**, with no separate ITR-4 code change needed — confirmed directly for the uniform
  allowance exemption fix (§20.6 of the ITR-1 doc): `_map_salary` is the shared function, so
  ITR-4 filers get the same actual-expenditure exemption computation for free.
- **Fixes made only at the *calculator* call-site level do NOT automatically apply**, since
  `app/engine/calculators/itr1.py` and `app/engine/calculators/itr4.py` are separate files that
  each call the shared schedule functions with their own arguments. This is exactly the shape
  of gap found in §3 below (the pre-1999 loan cap) and is the reason ITR-4 needs its own
  calculator-level audit pass even though the mapper is shared.
- ITR-4's own genuinely distinct territory (not shared with ITR-1 at all) is: the three
  presumptive-income schemes (44AD/44ADA/44AE), Schedule BP financial particulars and business
  nature/GSTIN rows, and the ITR-4-specific filing profile (`ITR4FilingProfile`, Form 10-IEA
  cascade, firm/HUF assessee-status handling). These are the areas most likely to still have
  ITR-1-audit-style undiscovered bugs, since nothing from the ITR-1 audit could have touched
  them structurally — they have never been audited at all.

### 1.2 A structural difference worth flagging early: ITR-4 supports only one house property

`ITR4Input.house_property_income: Optional[HousePropertyIncome]` — no `house_properties` list
field exists on `ITR4Input` at all (unlike `ITR1Input`, which supports up to two via
`reconciled_house_properties()`). The mapper's own field docstring says "ITR-4 allows one house
property, same as ITR-1" — inaccurate on its face (ITR-1 allows *two*), but the practical effect
is that `draft_to_itr4_input.py` only ever reads `hp_inputs[0]` from the shared
`_map_house_properties()` helper. Not yet verified whether the ITR-4 eligibility gate actually
*rejects* a draft with two properties (forcing ITR-2/3) or would silently drop the second one —
flagged for the schedule-level audit pass, not resolved here.

## 2. CRITICAL: `filing_date` never reached the real compute pipeline (2026-09-03)

**This is the single most severe finding of the ITR-4 audit so far, and it is not ITR-4-only —
see the full write-up, including the ITR-1 side, in
`Docs/ITR1_FRONTEND_AND_SERIALIZATION_AUDIT_AY2026_27.md` §24.** Recorded here in full as well,
scoped to what is specific to ITR-4, since this document is the ITR-4 audit's own record and a
future reader of *this* file should not have to cross-reference the ITR-1 document to learn
about a bug that shipped in ITR-4's own output.

### 2.1 The ITR-4-specific defect

`app/engine/draft_to_itr4_input.py` (before the fix) constructed `ITR4Input` with:

```python
filing_date=_to_date(draft.personal.dateOfBirth),  # placeholder; gateway sets filing_date
due_date=None,
```

The comment claimed a later step in `app/engine/filing_gateway_v2.py` would overwrite this
placeholder with the real filing date. It never did — grepping confirmed no `filing_date=`/
`due_date=` assignment existed anywhere in `filing_gateway_v2.py` before this fix. The
`model_copy(update={...})` inside `compute_canonical_itr4` (the single production dispatch
point for ITR-4 compute, per this codebase's own architecture) attached `filing_profile`/
`property_profile`/`bank_accounts`/`tax_return_preparer` but never `filing_date`/`due_date`.

**Consequence**: every ITR-4 return computed through `generate_cbdt_json` carried the
taxpayer's own **date of birth** as its "filing date" — e.g. a taxpayer born in 1985 would have
that treated as when they filed AY 2026-27's return, decades before any statutory due date.
`app/engine/calculators/itr4.py`'s interest/fee logic (`if filing_date and due_date:`) saw a
real, non-`None` `filing_date` (so the gate *did* run, unlike ITR-1's identical bug where
`filing_date` stayed `None` and the gate never ran at all) — but since that date was always far
earlier than the due date, `compute_234a`/`compute_234b`/`compute_234c`/`compute_234f`/
`compute_234i` all correctly computed **zero** for a "filing" that, as far as the calculator
could tell, happened decades before it was due. The net effect for ITR-4 was identical to
ITR-1's: `TotalIntrstPay` was always zero in the generated JSON, regardless of the taxpayer's
actual filing date.

One reassurance checked directly: `app/engine/itd/itr4.py` (the JSON builder) never reads
`filing_date` at all — the date-of-birth placeholder never leaked into any *displayed* field of
the official return (e.g. `Verification.Date`, which is built from `filing_profile` /
`draft.verification.date` separately and correctly). The defect was confined to the
interest/late-fee *calculation*, not the return's declared identity — bad, but not as
catastrophic as it could have been.

### 2.2 The fix (ITR-4 side)

- `app/engine/draft_to_itr4_input.py`: removed the date-of-birth placeholder. `filing_date`/
  `due_date` are now left `None` in the mapper, exactly matching ITR-1's mapper — the gateway is
  the single correct place to set them, not each per-form mapper guessing independently.
- `app/engine/filing_gateway_v2.py::compute_canonical_itr4`: `model_copy(update={...})` now also
  sets `"filing_date": _to_date(draft.verification.date)` and `"due_date": get_due_date("ITR-4",
  draft.assessmentYear or "2026-27")` — the correct ITR-4 due date (31 August, not ITR-1's 31
  July — `get_due_date` was already form-aware; it just was never being called for ITR-4 at this
  site).

### 2.3 Two more bugs this exposed — both shared with ITR-1, both fixed centrally

Because interest/fee computation is shared logic (`app/engine/common/interest.py`) and the
ITR-1-side of R190 is a shared-pattern validator bug, both of these were fixed once and benefit
ITR-4 automatically, exactly like §1.1 predicted for shared code:

- **`compute_234f`** (`app/engine/common/interest.py`, shared by every form) still implemented
  the pre-Finance-Act-2021 ₹10,000 late-fee tier for filing after 31 December. That tier was
  removed; the correct maximum is ₹5,000 (₹1,000 if total income ≤ ₹5L), confirmed independently
  by the official JSON schema's own `LateFilingFee234F` `maximum: 5000` constraint — which is
  what caught this, when the first real late-filing test (built for the ITR-1 side of this fix)
  hit the ceiling and failed schema validation outright. Fixed in the shared module; ITR-4
  inherits the fix automatically. Two existing unit tests had the wrong ₹10,000 "known answer"
  and were corrected to match current law.
- **`ITR1-R190`** (an ITR-1-only validator, not shared with ITR-4's separate validator suite) was
  coded to block *any* regime selection for a late filing, when the actual CBDT rule only blocks
  switching *to* the old regime. Fixed on the ITR-1 side (§24.3 of the ITR-1 doc). **Flagged as
  an open item for ITR-4's own validator audit**: `app/engine/validators/itr4/input_rules.py`
  has not yet been checked for whether it has its own copy of this same rule with the same
  overly-broad condition — not verified in this pass, noted for the systematic ITR-4 validator
  review still to come (§5).

### 2.4 Verification

- Empirical, through the real `generate_cbdt_json(draft)` pipeline (not a unit test of the
  formula in isolation): a 44AD-scheme ITR-4 draft filed under 139(4) on 2027-02-01 with
  ₹25,00,000 declared presumptive income (pushed above the new-regime 87A rebate threshold so
  there is genuine tax payable for 234A to accrue on) now shows non-zero
  `TaxComputation.IntrstPay.IntrstPayUs234A` and the correct `LateFilingFee234F: 5000`.
- 2 new permanent regression tests in `tests/test_filing_gateway_v2_itr4.py`:
  `test_itr4_filing_date_reaches_typed_input_from_verification_date` (asserts
  `typed_input.filing_date == date(2026, 7, 31)` and `typed_input.due_date == date(2026, 8,
  31)` for an on-time `_filing_ready_itr4()` draft) and
  `test_itr4_late_filing_computes_nonzero_interest_and_late_fee` (the real end-to-end scenario
  above).
- Full backend suite (excluding the pre-existing-broken collection files documented in
  CLAUDE.md): 1578 passed, same 3 pre-existing unrelated failures
  (`tests/test_tax_v2_compute.py`) as every prior run this session — no new failures.

### 2.5 Why this matters for the "is ITR-4 production ready" question

It doesn't answer it — this document has barely started. It does mean that *whatever* the
eventual ITR-4 production-readiness assessment says, it can no longer be undermined by "every
return silently omits interest and late fees," which was true of every ITR-4 JSON this platform
generated before today. This was the first thing found in the ITR-4 audit, before the
systematic section-by-section pass had even begun, which is itself informative: it suggests the
same "read the real production entrypoint end-to-end, not just the formula in isolation"
method that has repeatedly found the worst bugs in the ITR-1 audit (§15.4's TDS bug, §20.5's
R246 bug, this one) is likely to keep paying off for ITR-4's remaining, not-yet-audited surface.

## 3. Known open items carried over from the ITR-1 audit, applicable to ITR-4

These were found *while auditing ITR-1* but are ITR-4-scoped defects, flagged there and
repeated here since this is now the ITR-4 audit's own tracking document.

### 3.1 Pre-1999 self-occupied loan cap not wired for ITR-4 (found during this session's
reconnaissance, not yet fixed)

ITR-1's `app/engine/calculators/itr1.py` was fixed (ITR-1 audit doc §20.2) to pass
`loan_sanction_dates` into `schedules/house_property.py::compute()`, so a self-occupied loan
sanctioned before 1 April 1999 correctly caps interest at ₹30,000 instead of ₹2,00,000. This is
a **calculator call-site** change, not a shared-helper change (per §1.1's distinction above), so
it does **not** automatically apply to ITR-4. Confirmed directly:

```python
# app/engine/calculators/itr4.py, current state
hp = compute_hp(
    input_data.house_property_income,
    regime,
    (
        input_data.house_property_income.ownership_share_percentage
        if input_data.house_property_income is not None else Decimal("100")
    ),
)
```

No `loan_sanction_dates` argument — `compute_hp`'s new optional parameter simply defaults to
`None`, so ITR-4 self-occupied filers with a pre-1999 loan get the same wrong ₹2,00,000 cap the
ITR-1 audit already found and fixed on the other form. **Not fixed in this pass** — flagged for
the ITR-4 schedule audit, expected to be a small, low-risk fix mirroring the ITR-1 change
exactly (resolve the matching loan(s) from `input_data.loan_details_24b_list` by
`property_sequence_no`, pass their `sanction_date`s through).

### 3.2 `ITR4-R295` — the same multi-property false positive as `ITR1-R246` (found, not fixed)

`app/engine/validators/itr4/input_rules.py`'s `ITR4-R295` has the identical pattern to the bug
already fixed in `ITR1-R246` (ITR-1 audit doc §22): comparing one property's declared 24(b)
interest against the sum of loan rows across *all* properties instead of just its own. Given
§1.2 above (ITR-4 may only support one house property at all), this may turn out to be
**unreachable** rather than live — worth checking whether ITR-4's eligibility gate actually
blocks multi-property drafts before treating this as equally severe to the ITR-1 case. Not
verified in this pass. Not fixed.

### 3.3 `tds_claimed_this_year`-vs-`tds_claimed` field-name bug (found, not fixed)

Flagged in the ITR-1 audit doc §15.4: `app/engine/validators/itr4/input_rules.py` has the
identical bug already fixed in ITR-1's validators (a `getattr(e, 'tds_claimed_this_year', ...)`
call against `TDS3Entry`, whose actual field is `tds_claimed`, at two sites — approximately
lines 1951 and 1963 as of that finding). Unlike the underlying TDS2/TDS3 *credit computation*
bug (which was in shared code and is already fixed for ITR-4 — see the ITR-1 doc §15.4's own
note that `app/engine/calculators/itr4.py` was included in that fix), this specific instance is
in ITR-4's own, separate validator file and was explicitly left unfixed pending the ITR-4 audit
phase. Not fixed in this pass.

## 4. What's next

This document will be filled in section by section, following the same structure and rigor as
the ITR-1 audit: a systematic frontend-field-vs-mapper-vs-calculator cross-reference (the
method that found ITR-1's P0 bugs), a full schedule-by-schedule re-audit of the ITR-4-specific
presumptive-income schedules and Schedule BP, a systematic validator sweep of
`app/engine/validators/itr4/` (4,886 + 828 lines — larger than ITR-1's validator suite), the
official CBDT ITR-4 Validation Rules cross-reference, and official ITR-4 JSON schema
constraint compliance. §3's three carried-over items are the natural starting point for the
next phase, since they are already identified and mostly scoped.
