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

### 3.4 §3.1/§3.2/§3.3 — resolved (2026-09-03, same-day follow-up)

All three carried-over items above are now closed:

- **§3.1 (pre-1999 loan cap)** — fixed. `app/engine/calculators/itr4.py`'s `compute_hp()` call
  now passes `loan_sanction_dates` filtered to `property_sequence_no == 1` (ITR-4 computes
  income for only the first house-property row, so no ITR-1-style multi-property iteration is
  needed — just the same single filter). 2 new tests in `tests/test_itr4_calculator.py`.
- **§3.2 (`ITR4-R295` multi-property false positive)** — fixed, and worse than first estimated:
  there were actually **two** independent implementations of this check, `ITR4-R289` and
  `ITR4-R295`, both comparing the one property ITR-4 computes against an *unfiltered* sum of
  `loan_details_24b_list` (which can carry a second property's loan under `property_sequence_no
  2` — nothing in this pipeline rejects a second house-property row outright, confirmed by
  grepping for any such rejection and finding none). Both fixed to filter to
  `property_sequence_no == 1`, and a third, purely tautological "R295" block (comparing a value
  to a differently-scoped copy of itself, added no real check) was removed rather than fixed. 3
  new tests in `tests/test_itr4_input_validation.py`.
- **§3.3 (`tds_claimed_this_year`/`tds_claimed`)** — **confirmed a false alarm, not a real bug.**
  Re-verified directly against the schema (`TDS2Entry` has only `tds_claimed_this_year`;
  `TDS3Entry` has only `tds_claimed` — confirmed via `model_fields`) and re-read all 4 call
  sites in `app/engine/validators/itr4/input_rules.py`: every one correctly matches the right
  field name to the right entry type. The ITR-1 audit's §15.4 flag for this file was inaccurate
  — recorded here so a future reader doesn't re-chase it, matching this document's practice
  (established in the ITR-1 doc) of correcting a prior claim rather than silently dropping it.

One new gap found and fixed while closing §3.1: `app/engine/calculators/itr4.py`'s
`ITR4Result` didn't expose `salary_uniform_allowance_exempt` at all, and ITR-4's own,
*separate* copy of the JSON-building `_allowance_rows` function (`app/engine/itd/itr4.py`)
never folded the uniform-allowance exemption (fixed for ITR-1 in that audit's §20.6) into the
`"10(14)(i)"` bucket — meaning a real ITR-4 filer's correctly-computed uniform-allowance
exemption (the underlying tax computation was already correct, since `schedules/salary.py` is
shared) was silently missing from the official JSON's own allowance breakdown. Fixed by
mirroring the exact ITR-1 fix on ITR-4's separate copy. 1 new test confirming the exemption
reaches `IncomeDeductions.AllwncExemptUs10.AllwncExemptUs10Dtls`.

## 4. Frontend field audit — Schedule BP (44AD/44ADA/44AE)

Read `frontend/src/components/business/ITR4ScheduleBPManager.tsx` (393 lines) and its
bidirectional translation layer `frontend/src/domain/returns/scheduleBpAdapter.ts` in full —
the ITR-4-specific frontend surface with no ITR-1 equivalent (salary/HP/OS/deductions UI is
shared with ITR-1 and already covered by that audit). This is a genuinely different shape than
most of the ITR-1 audit's targets: the frontend component's own state (`ITR4ScheduleBPData`)
uses the *official CBDT field names directly* (`NatOfBus44AD`, `GrsTotalTrnOver`,
`GoodsDtlsUs44AE`, etc.), not the semantic `camelCase` shape `draft.businesses` uses — so a
real bidirectional adapter exists and was the focus of this review, since a broken adapter here
would be exactly the "frontend captures data that never reaches computation, or reaches it
under the wrong semantics" class of bug the ITR-1 audit found repeatedly.

**No defect found in the adapter itself** — verified directly, not merely by matching field
names: the `index === 0`-only value placement in `businessesFromScheduleBp` for 44AD/44ADA
(every "Nature of business" row after the first gets zeroed money fields) correctly mirrors
`ITR4ScheduleBPManager.tsx`'s own UI, which only renders the shared aggregate turnover/income
fields under the *first* nature-of-business row's expanded details panel — the round trip
(`scheduleBpFromBusinesses` sums across all rows on load, `businessesFromScheduleBp` zero-pads
every row but the first on save) is internally consistent given that UI design, not a bug.
Financial-particulars and GSTIN-turnover handling (attached once, at the schedule level, to
every business row or just the first) is likewise consistent with the backend mapper's own
`_map_schedule_bp_financial(businesses)` (reads `businesses[0]` only).

**One real, if lower-severity, gap found**: Section 44AD's `PresumptiveBusinessIncome44AD`
schema explicitly documents that "the assessee may declare income higher than the presumptive
[6%/8%] rate" (`income_declared`, honored by `schedules/presumptive.py::_compute_44ad` only
when it exceeds the statutory floor) — but `ITR4ScheduleBPManager.tsx`'s "Total presumptive
income u/s 44AD" field is `readOnly` and *always* derived as exactly `6%-income + 8%-income`
(`derive()`'s `p.TotPersumptiveInc44AD = sum([...6%, ...8%])`), with no UI input anywhere to
enter a genuinely higher figure. Section 44ADA's equivalent field, by contrast, *is* editable
(`onChange` wired, not derived) — a real asymmetry, not a mirrored design choice. A 44AD
taxpayer who legitimately wants to declare income above the statutory floor (a real right under
the Act) currently has no way to do so from this UI. **Not fixed in this pass** — flagged as a
genuine, scoped frontend gap for a future phase (add an editable override field, mirroring
44ADA's pattern, distinct from the derived 6%/8% breakdown).

**Investigated and confirmed safe by design, not a bug**: 44AE's `PresumptiveIncome` field
defaults to a flat `7500` for every newly-added vehicle regardless of tonnage or months-owned —
initially looked like it could silently understate a heavy vehicle's income or a
multiple-months light vehicle's income. Traced into `schedules/presumptive.py::_compute_44ae`:
the "declared" value is used **only when it exceeds** the correctly-computed statutory amount
(`Decimal("1000") * tons * months` for heavy, `Decimal("7500") * months` for light) — since the
7500 UI default can never exceed either formula for any realistic tonnage/months combination
(the sole exception being a heavy vehicle left with tonnage at its 0 default, a narrow input-
validation gap worth a UI required-field nudge, not a computation bug), the flat default never
actually overrides the correct engine-computed figure in practice.

## 5. Validator sweep — the `nature_of_employment` keyword-matching bug, 18 sites (2026-09-03)

Confirmed the exact bug class already found and fixed 10 times in ITR-1's validators (that
audit's §14.5) is independently present in ITR-4's own, separate validator file — not shared
code, so ITR-1's fix did not help here. `inp.nature_of_employment` carries the raw official code
(`CGOV`/`SGOV`/`PSU`/`PE`/`PESG`/`PEPS`/`PEO`/`OTH`, confirmed via
`app/engine/draft_to_itr4_input.py`, sourced from the same `draft.employers[0].natureOfEmployment`
field ITR-1's mapper reads), never a human-readable label — so any keyword or hardcoded-string
match against it was either permanently dormant or permanently (over-)blocking.

**Two distinct variants of the same underlying mistake, found by two different searches:**

- **10 sites** using `.lower()` + keyword substring matching (`"pension" in emp.lower()`,
  `"central government" not in emp.lower()`, etc.) — the identical pattern to ITR-1's bug,
  affecting `ITR4-R022a`/`R155` (80CCD(1) pensioner/non-pensioner caps), `ITR4-R025`/`R047`
  (80CCD(2) non-CG-SG/CG-SG caps), `ITR4-R161` (80CCD(2) pensioner block), `ITR4-R073` (gratuity
  non-CG/SG cap), `ITR4-R075` (leave encashment non-govt cap), `ITR4-R185` (10(10B) retrenchment
  CG/SG/pensioner block), `ITR4-R317` (gratuity CG/SG cap), `ITR4-R322` (Judge Salaries Act
  exemption, CG/SG only).
- **8 more sites** found by a second, targeted search after fixing the first batch — a
  *different* variant using a hardcoded whitelist/blacklist of wrong short strings (`"CG"`,
  `"SG"`, `"CGP"`, `"SGP"`, `"PES"` instead of the real `"CGOV"`, `"SGOV"`, `"PESG"`) — affecting
  three *further, entirely redundant* implementations of rules already covered by the first
  batch's fix (a second `R073`, a second `R317`, a second `R181` which is itself a third
  redundant copy of the already-fixed `R075` under yet another rule number, a second `R161`),
  plus three **not** previously covered: `ITR4-R263` (new-regime 80CCD(2) 14% cap for
  PSU/CG/SG/Others), `ITR4-R067`/`R068` (entertainment allowance eligibility, CG/SG/PSU only —
  and confirmed `R068` has a *second*, independent, already-correct implementation reading
  `SalaryIncome.is_government_employee`, itself derived via the shared `_map_salary` fixed
  during the ITR-1 audit's §5.2, so this specific rule was only half-broken).

**Fix**: added the same `_is_cg_sg_employee()`/`_is_pensioner()` helper pair ITR-1's validators
use (identical code sets: `{"CGOV","SGOV"}` / `{"PE","PESG","PEPS","PEO"}`) to
`app/engine/validators/itr4/input_rules.py`. All 10 keyword-matching sites now call the
helpers. Of the 8 wrong-whitelist sites: the 5 that were pure duplicates of an already-fixed
rule (`R073`, `R317`, `R181`, `R161` — 4 blocks) were **removed** rather than fixed in place,
consolidating onto the one correct implementation of each rule; the 3 non-duplicate sites
(`R263`, `R067`, `R068`) had their wrong strings corrected in place (`"CG"`/`"SG"` →
`"CGOV"`/`"SGOV"`).

**Consequence, both directions, matching the exact shape of ITR-1's finding**: false-positive
over-blocking for genuine CG/SG employees and judges (`R025`, `R067`/`R068`'s duplicate,
`R073`'s duplicates, `R075`, `R317`'s duplicate, `R391`, `R322`) who were being checked against
the *stricter* non-government rule or blocked outright regardless of their real employment;
permanently dormant checks (`R022a`, `R047`, `R073`, `R161`'s duplicate, `R185`, `R263`,
`R317`) that never caught a genuine invalid claim from a real pensioner or CG/SG employee,
silently letting excess claims through unchecked.

### 5.1 Verification

- 21 new tests across `tests/test_itr4_input_validation.py`: both directions (a real CG/SG-
  employee/pensioner/judge case that must now pass or correctly fail, and a non-CG/SG/non-
  pensioner case whose existing behavior must be unchanged) for every affected rule
  (`R022a`, `R025`, `R047`, `R067`, `R068`, `R073`, `R075`, `R161`'s remaining implementation,
  `R185`, `R263`, `R289`, `R295`, `R317`, `R322`).
- One pre-existing test (`test_R022a_80ccd1_pensioner_exceeds_20pct`) had used the human-
  readable string `"Pensioner"` instead of the real raw code — passing only by the same
  accidental keyword-substring match this fix removes. Corrected to use the real code `"PE"`,
  with a comment explaining why, matching the ITR-1 audit's identical correction for its own
  equivalent pre-existing tests.
- Full backend suite (same pre-existing-exclusion list as every ITR-1-phase run): 1599 passed,
  same 3 pre-existing unrelated failures (`test_tax_v2_compute.py`) — no new failures.

## 6. Official ITR-4 JSON schema constraint compliance (2026-09-03)

Same methodology as the ITR-1 audit's §17: build diverse `ReturnDraft` scenarios, run them
through the **real** production `generate_cbdt_json(draft)` pipeline (not a hand-built minimal
input), and validate the output against the official schema
(`Reference Docs by CBDT & ITD/Official JSON Schema/ITR-4_2026_Main_V1.1 (2).json`, Draft-04,
534 leaf properties catalogued: 347 required, 82 with a pattern, 283 with a min/max bound, 56
with an enum).

Four deliberately diverse drafts:

1. **44AD** business, old regime, self-occupied HP with a matching 24(b) loan, salary + TDS
   (implicit via employer), 80C, 80D (flat).
2. **44ADA** profession, new regime, LTCG 112A via `simplified112A`, TDS (other-than-salary),
   TCS.
3. **44AE** goods carriage (one heavy + one light vehicle), let-out HP, 80DD disability with
   Form 10-IA, 80G donation (non-cash, IFSC + transaction ref), representative-assessee
   filing, GSTIN turnover.
4. Salary + TDS1 (on-salary), structured 80D (self + parents, per-policy), 80E education loan,
   80CCC/`PensionContribution80CCC`, 80GGC political contribution, ScheduleIT (advance +
   self-assessment tax challans), alternate/secondary address, Tax Return Preparer.

**Result: zero schema violations across all four scenarios**, after fixing each fixture's own
real mistakes along the way (an unbalanced `FinancialParticulars` capital/liability cross-foot,
an invalid TDS3 fixture that actually needs tenant fields — TDS3 in this schema is specifically
the Section 194IB rent-TDS schedule, not a generic "any other TDS" bucket — an invalid
44ADA nature code, TAN city-code prefixes that must match the official RBI/GIFT list, and a TDS
section code format that drops the leading "1" for some sections, e.g. `"94J-A"` not
`"194J"`) — each a fixture-construction mistake caught by the real validators/schema, not a
product defect.

### 6.1 Honest scope caveat — paths not exercised by any of the four drafts

Re-running the coverage check after all four drafts: 104 of 534 required-leaf paths (down from
153 after the first three) and roughly 90 optional paths remain unexercised. As with the
ITR-1 audit's identical caveat (§17.3 there), most of these are fields "required" only *inside*
an optional parent object none of the four drafts happened to populate together (e.g. all three
approval-category blocks of Schedule 80G's structured donee-PAN rows, all four of Schedule
80D's structured senior/non-senior self/parent policy blocks, the 80E/80EE/80EEA/80EEB per-loan
detail blocks) — not a known defect, just unverified by this specific check. Recorded honestly
rather than chased to 100%, matching the established practice; a fifth or sixth draft would
close most of the remainder but was not built in this pass given the scope already covered.

## 7. Not yet done — the official CBDT ITR-4 Validation Rules cross-reference

The ITR-1 audit's §16 (its single most labor-intensive section — transcribing all 349 official
rules from the CBDT PDF by hand and cross-referencing each against the implementation) has
**no ITR-4 equivalent yet**. `Reference Docs by CBDT & ITD/Official Validations/CBDT_e-Filing_ITR
4_Validation Rules_AY 2026-27 (1).pdf` (652 KB — larger than ITR-1's 543 KB PDF) has not been
read. Given `app/engine/validators/itr4/input_rules.py` cites rule numbers up into the `R400`s
in its own comments (vs. ITR-1's ~339), this document likely catalogs materially more official
rules than ITR-1's 349. This is the largest remaining piece of unfinished work in this audit —
named explicitly here rather than silently left for "later," per this document's own established
practice of recording scope honestly.

A related, smaller finding from the sweep that led to §5: `app/engine/validators/itr4/
input_rules.py` has **76 rule IDs invoked more than once** (a mechanical count, not a semantic
one), of which this pass fully investigated and resolved 8 (`R073`, `R317`, `R181`/`R075`,
`R161`, plus `R289`/`R295` from §3.1). The remaining ~68 duplicate IDs have **not** been
individually checked — some are certainly legitimate (e.g. an old-regime-gated and a
new-regime-gated version of the same rule number, correctly mutually exclusive), but given this
pass found real, high-severity bugs in essentially every duplicate-ID group it *did* check, the
remaining ones are a reasonable, concrete starting point for the next phase of this audit,
alongside the CBDT rules cross-reference above.

## 8. Summary of open items after this pass

1. **Not yet done, largest remaining item**: the official CBDT ITR-4 Validation Rules
   cross-reference (§7) — the PDF has not been read yet.
2. **Not yet done**: the remaining ~68 mechanically-duplicate rule IDs in
   `app/engine/validators/itr4/input_rules.py` have not been individually audited (§7).
3. **Not fixed, scoped, lower severity**: Section 44AD has no UI path to declare income above
   the statutory 6%/8% floor, unlike 44ADA's equivalent (already-editable) field (§4).
4. **Not fixed, deliberately out of scope**: ITR-2/ITR-3 remain untouched, matching the
   established ITR-1-then-ITR-4-then-ITR-2-then-ITR-3 sequencing.
5. **Recorded, not chased**: ~104 required schema paths not exercised by any of the four §6
   drafts — no known defect, just unverified.
6. **Closed this pass**: the critical `filing_date` bug (§2), all three originally-carried-over
   items (§3), the Schedule BP frontend adapter review (§4, one real gap found and flagged, not
   fixed), the 18-site `nature_of_employment` bug (§5), and JSON schema compliance (§6).
