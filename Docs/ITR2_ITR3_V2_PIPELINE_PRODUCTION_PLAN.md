# ITR-2 & ITR-3 — v2 Canonical Pipeline Production Implementation Plan

**Status:** Active implementation tracker. No phase starts until the previous phase's tests
pass and the user has approved it. Updated immediately after each phase — status, files
touched, verification result — matching the convention of `ITR4_V2_PIPELINE_AND_LEGACY_DELETION_PLAN.md`.
**Date:** 2026-09-01
**Authority:** This is the single source of truth for building ITR-2 and ITR-3 to the exact
same production standard ITR-1 and ITR-4 already meet. It is verified against
`Docs/ITR1_ITR4_COMPLETE_PIPELINE_REFERENCE.md` (the ground-truth architecture audit) at every
step — nothing here is guessed from an older doc's claims.
**Relationship to `Docs/ERI_UAT_EXPANSION_PLAN.md`:** that doc owns the shared UAT-pack
tooling (credential-bundle switching, `scripts/eri_uat_sanity.py`) and the final
UAT-sample-generation step for ITD certification. Its Phases 2–11 (the ITR-2/ITR-3 build
items) are **superseded by this document** — treat this doc as the detailed phase plan those
items point to, not a duplicate.

---

## 1. Background — why this plan exists

`Docs/ITR1_ITR4_COMPLETE_PIPELINE_REFERENCE.md` §6 states the exact checklist a
production-ready form satisfies: one canonical mapper, dispatch added to
`filing_gateway_v2.py` (never the dead `filing_gateway.py`), CBDT validators actually wired
in before JSON emission, frontend hitting only `/v2/*` and `/api/v1/filing/*`, persistence
via `ClientITR.form_data` as serialized `ReturnDraft`, Digest via `app/eri/digest.py`, and
Type-3 submission working via the existing form-agnostic uploader.

ITR-2 and ITR-3 meet **none** of this today. Verified current state (research conducted this
session, cross-checked against actual code):

| | ITR-2 | ITR-3 |
|---|---|---|
| Pydantic input schema | `app/schemas/itr2.py`, 655 lines, complete | `app/schemas/itr3.py`, 263 lines — imports ITR-2's CG/VDA/FSI/TR/SPI/AMT types directly, adds PGBP/balance-sheet/audit types |
| Calculator | `app/engine/calculators/itr2.py`, 914 lines, complete | `app/engine/calculators/itr3.py`, 581 lines, complete |
| ITD JSON builder | `app/engine/itd/itr2.py`, 1677 lines, ~25 schedules, complete | `app/engine/itd/itr3.py`, 1130 lines, complete |
| CBDT validators | `app/engine/validators/itr2/`, 625 lines total (~15% of ITR-1's 4431) | `app/engine/validators/itr3/`, **57 lines total — a stub, not a partial suite** |
| Canonical `ReturnDraft` mapper | **Does not exist** | **Does not exist** |
| `filing_gateway_v2.py` dispatch | **Rejects** ITR-2 explicitly (`"ITR-2/3 not yet supported by the v2 pipeline"`) | Same rejection |
| Live production path today | A **third, separate** flat-payload path: `app/routers/tax.py::_compute_itr2_from_flat_payload` → `compute_itr2` (no `ReturnDraft`, no CBDT rule validation before JSON, no Direct Submit) | No live compute path found at all — `/itr3/compute` (`app/routers/itr.py`) is a dead route (§ pipeline reference doc's route inventory) |
| Frontend | `frontend/src/api/itr2Mapper.ts` (flat, non-`ReturnDraft`), computable/selectable in the UI but not v2-pipeline-backed | Selectable in the UI (`ITRComputationPage.tsx` form selector), but no confirmed working compute path |
| Type-3 UAT sample | Not generated | Not generated |

This plan closes every one of these gaps, in the same order and with the same rigor
`ITR4_V2_PIPELINE_AND_LEGACY_DELETION_PLAN.md` used to bring ITR-4 to parity.

## 2. Guiding principles (non-negotiable — copied from the ITR-4 plan, still binding)

1. **ITR-1 and ITR-4 must not break.** No commit lands that turns either regression suite red.
2. **One phase at a time**, each independently testable, each ending with a green-test gate.
3. **Tests first.** Every phase has a test list; not complete until its own tests pass **and**
   the ITR-1/ITR-4 suites stay green.
4. **Commit per phase**, referencing this doc; this doc's status flips ⬜→✅ after tests pass.
5. **No shortcut code.** Everything touched in `app/eri/`, `app/engine/`, or the filing
   pipeline is production-grade and reused unchanged later — this is a hard constraint from
   the user, not a suggestion.
6. **Never route through `app/engine/filing_gateway.py`.** Confirmed dead/unreachable for
   ITR-1/ITR-4 (`ITR1_ITR4_COMPLETE_PIPELINE_REFERENCE.md` §4) and was never a real fallback
   for ITR-2/ITR-3 either — every live route hard-normalizes to ITR-1/ITR-4 before reaching
   it. `filing_gateway_v2.py`'s dispatch is the only place new forms get added.

## 3. Target architecture (after this plan)

```
ClientITR.form_data = JSON(ReturnDraft)        ← ONE typed shape, all four forms
  ├─ ITR-1: draft_to_itr1_input → compute_itr1 → build_itr1_json      (existing)
  ├─ ITR-4: draft_to_itr4_input → compute_itr4 → build_itr4_json      (existing)
  ├─ ITR-2: draft_to_itr2_input → compute_itr2 → build_itr2_json      (this plan)
  └─ ITR-3: draft_to_itr3_input → compute_itr3 → build_itr3_json      (this plan)
       each gated by run_input_validation + run_calc_validation (CBDT Category A/B/D)

Deleted once ITR-2/ITR-3 are repointed (Phase 9):
  ✗ app/routers/tax.py::_compute_itr2_from_flat_payload
  ✗ frontend/src/api/itr2Mapper.ts
  ✗ app/routers/itr.py's dead /itr{2,3}/compute[-json] routes (already unreachable, formally removed)
```

---

## 4. Phase-wise plan

### Phase 1 — Type the capital-gains schedule (backend + frontend)

**The single biggest schema gap, and the reason this starts here rather than with the
mapper.** Per the user's explicit direction: reuse the frontend's existing capital-gains
structure rather than adding parallel fields. Research findings (verified against
`frontend/src/domain/returns/types.ts`):

- `CapitalGainsSchedule` already has **typed** `schedule112A: Scrip112A[]`, `vda: VdaEntry[]`,
  `schedule115AD: Scrip115AD[]`, `stImmovable`/`ltImmovable: ImmovableAssetGain[]`,
  `purchases: CapitalGainPurchase[]`, `deductionClaims: DeductionClaim[]`,
  `stUnutilized`/`ltUnutilized: UnutilizedDeposit[]`, `stDtaa`/`ltDtaa: DtaaEntry[]`,
  `aggregates: CapitalGainsAggregates`, `lossSetOff: LossSetOff`.
- Still **untyped** `JsonRow[]`: `stEquity`, `stOtherAssets`, `stNriUnlisted`, `ltProviso112`,
  `ltNri112115`, `ltForeignAssets`, `ltOtherAssets`, `stSlumpSale`, `ltSlumpSale`,
  `buyBackLosses` — these need real types before ITR-2's calculator can consume them
  (`compute_itr2` needs `asset_type`, both acquisition/transfer dates, consideration, cost,
  STT flags, per-transaction exemption claims — see Phase 3's field table).
- The **backend** `ReturnDraft.capitalGainsSchedule` is still `dict` — untyped. This phase
  replaces it with a real nested Pydantic model mirroring the frontend's field names exactly
  (`schedule112A`, `vda`, `stImmovable`, etc.), so there is one shape, not two.

**Files:**
- `app/schemas/return_draft.py` — replace `capitalGainsSchedule: dict` with a typed
  `CapitalGainsSchedule` model. **Must stay backward-compatible with ITR-1's existing
  `simplified112A` dict read** (`app/engine/draft_to_itr1_input.py:793`,
  `sched.get("simplified112A")`) — either keep `simplified112A` as a field on the new typed
  model, or provide a `model_validator` that accepts the old dict shape during the
  transition. Verify against ITR-1's regression suite, not assumption.
- `frontend/src/domain/returns/types.ts` — type the 10 remaining `JsonRow[]` fields listed
  above with real interfaces (matching the fields ITR-2's `CGTransaction` needs — asset type,
  dates, consideration, cost basis, STT flags, exemption claims).
- `frontend/src/components/CapitalGainsEntryManager.tsx` — currently edits some of these as
  untyped rows; once typed, this component's form fields get real validation. (Scope check
  when this phase starts: does the full UI rework belong in this phase or a follow-up? Default
  assumption — type the data model now, defer full UI polish to a later pass, since the
  mapper only needs the *data* to be typed correctly, not the editing experience to be final.)

**Tests:** schema round-trip tests (typed CG schedule serializes/deserializes losslessly),
ITR-1 regression suite stays green (still reads `simplified112A` correctly).

### Phase 2 — Extend `ReturnDraft` / `types.ts` with the remaining ITR-2 fields

Everything capital-gains-shaped is Phase 1's job; this phase covers the rest, using the
**already-drafted but unwired** types already sitting in `return_draft.py` (added, then
paused for this exact review) as the starting point — corrected per the naming decisions
below rather than redesigned from scratch:

- **Reuse frontend names, don't invent new ones**: `PersonalInfo.isDirector`,
  `PersonalInfo.holdsUnlistedShares` already exist on the frontend and are wired into
  `ClientsPage.tsx`'s intake questionnaire + `eligibility.ts` — the backend gets fields with
  these exact names, not `isCompanyDirector`/`heldUnlistedEquity`.
- **`residentialStatus`: `"RES"|"NRI"|"NOR"`** (confirmed) — matches the backend `ITR2Input`
  schema that must actually be produced and `itr2Mapper.ts`'s existing enum. The frontend's
  `PersonalInfo.residentialStatus?: 'ROR'|'RNOR'|'NR'` (a pre-existing, already-inconsistent,
  unwired field) needs a coordinated fix in this same phase — align it to `RES/NRI/NOR` so
  there is one enum, not two, across the whole codebase.
- **New, no frontend collision** (confirmed zero prior representation via `scheduleRegistry.ts`
  marking all of these `status: 'missing'`): Schedule FSI, Schedule TR, Schedule FA, Schedule
  SPI (clubbing), Schedule PTI (pass-through income — name the field
  `passThroughIncomeEntries`, not `passThroughIncome`, to avoid confusion with the existing
  `HouseProperty.passThroughIncome` and `housePropertyPassThroughIncome` fields), AMT,
  Schedule AL, Schedule 5A (Portuguese Civil Code), ESOP deferral.
- **`BroughtForwardLosses`**: frontend's existing type is a flat current-year aggregate (5
  scalars), already wired to ITR-1/4's CYLA/BFLA. ITR-2 needs per-AY entries — extend the
  existing type additively with a new `entries: BroughtForwardLossEntry[]` field rather than
  adding an unrelated top-level list.
- **New declarations with no frontend field at all yet**: `sebiRegistrationNumber`,
  `isFiiFpi`, `portugueseCivilCodeApplies` — add to `FilingStatus` alongside the existing
  ITR-4 declaration-style fields.

**Files:** `app/schemas/return_draft.py` (revise the already-drafted block), 
`frontend/src/domain/returns/types.ts` (mirror in the same phase — per the user's explicit
"update the frontend mirror in lockstep" instruction, this is not deferred).

**Tests:** `tests/test_return_draft_schema.py` — additive-field round-trip tests, ITR-1/4
regression suites stay green, `extra="forbid"` still rejects unknown keys.

### Phase 3 — Canonical mapper: `app/engine/draft_to_itr2_input.py`

Mirrors `draft_to_itr4_input.py`'s structure exactly: single public
`draft_to_itr2_input(draft) -> (ITR2Input, breakdown)`, imports shared-head helpers
(`_map_salary`, `_map_house_properties`, `_map_deductions`, `_map_tds`, `_map_tcs`,
`_map_tax_payments`, `_map_80d_schedule`, etc.) from `draft_to_itr1_input.py` rather than
reimplementing them — confirmed established convention.

**Confirmed field-shape traps to get right on the first pass** (from direct reading of
`app/engine/calculators/itr2.py` and `app/engine/itd/itr2.py`):
- `cg_transactions` and `cg_112a_scrips` are **unioned** by the calculator before the ₹1.25L
  112A threshold is applied — the mapper must populate both from the typed capital-gains
  schedule (Phase 1), not just one.
- The ITD builder **independently re-derives** Schedule 112A rows from raw `cg_transactions`
  rather than reusing the calculator's already-classified result — date/asset-type logic is
  effectively duplicated between calculator and builder today (an existing characteristic of
  `itd/itr2.py`, not something this mapper can paper over — just be aware both consumers need
  correct raw per-transaction fields).
- `deductions_chapter6a` fields are read via `getattr(..., default)` by the calculator — a
  missing attribute silently produces `False`/`None` rather than erroring, so the mapper must
  populate the full set explicitly rather than relying on partial construction to "just work."
- `filing_date`/`due_date`: per `ITR1_ITR4_COMPLETE_PIPELINE_REFERENCE.md`'s flagged gap,
  these are never populated in the v2 pipeline today for *any* form — do not invent a new,
  inconsistent convention for ITR-2 (i.e., don't wire them up here as a drive-by fix; leave
  them `None` matching ITR-1/4's actual current behavior, and track the fix as the
  cross-form gap it already is).
- Age bracket: ITR-2 has no `assessee_status`-driven age convention like ITR-4's explicit
  `personal.age`; follow ITR-1's DOB-derived `_age_bracket_from_dob` pattern instead, since
  ITR-2's `age_bracket` semantics match ITR-1's, not ITR-4's.

**Tests:** `tests/test_draft_to_itr2_input.py` — golden vectors, draft → `ITR2Input` →
`compute_itr2` → sane `ITR2Result`.

### Phase 4 — Wire ITR-2 into `filing_gateway_v2.py` + CBDT validators

Extends the two dispatch points currently hardcoded to ITR-1/ITR-4 only
(`compute_canonical()` and `generate_cbdt_json()`, `filing_gateway_v2.py:1202-1255`):
add `compute_canonical_itr2()` and `_generate_cbdt_json_itr2()`, mirroring
`compute_canonical_itr4`/`_generate_cbdt_json_itr4` exactly — including running
`run_input_validation` + `run_calc_validation` from `app.engine.validators.itr2` before
`build_itr2_json`, so Category A failures block generation instead of reaching the portal.

**Tests:** `tests/test_filing_gateway_v2_itr2.py` (new, mirrors `test_filing_gateway_v2_itr4.py`).

### Phase 5 — Complete the ITR-2 CBDT validator suite

**The hardest phase**, same reason Type-3's own validation layer was flagged as the hardest
part of that plan. `app/engine/validators/itr2/input_rules.py` (365 lines) and
`calc_rules.py` (260 lines) cover ~15% of ITR-1's suite. Extended from the official
`Reference Docs by CBDT & ITD/Official Validations/CBDT__e-Filing_ITR 2_Validation Rules_AY
2026-27_V1.0 (1).pdf` (already in the repo), following the exact `ValidationRule`/Category
A-B-D/`ValidationReport.can_upload`/`blocking_errors` pattern `itr1/input_rules.py` already
establishes — no new validation framework, filling in the existing one.

**Tests:** `tests/test_itr2_input_validation.py`, `tests/test_itr2_calc_validation.py` — one
test per new rule, known-good and known-bad cases, same pattern as ITR-1's R145 tests.

### Phase 6 — Frontend: wire ITR-2 onto the canonical `ReturnDraft`

Mirrors `ITR4_V2_PIPELINE_AND_LEGACY_DELETION_PLAN.md` Phase 4 exactly: `itrV2.ts`/
`canonicalRepository.ts` already handle any form via the generic `ReturnDraft` — no new API
client code needed there. What needs form-aware UI work: `PersonalInfoTab` (already
`itrForm`-aware per the pipeline reference doc), `CapitalGainsTab`/`CapitalGainsEntryManager`
(consuming Phase 1's newly-typed schedule fields instead of raw `JsonRow[]`), and any new tab
needed for FSI/TR/FA/SPI/PTI/AMT/AL/5A/ESOP capture (`scheduleRegistry.ts` currently marks all
of these `status: 'missing'` — this phase is what changes that).

**Scope note for when this phase starts:** the *data* being capturable (typed fields existing,
mapper consuming them) is this plan's job; a fully polished capture UI for all 9 previously-
missing schedules is a large frontend undertaking in its own right and may warrant its own
sub-phase breakdown once Phase 1/2's types are locked in — sized precisely at that point, not
guessed now.

### Phase 7 — ITR-2 v2 endpoints + Direct Submit extension

- `client_itr_v2.py`'s existing `generate-cbdt-json`/`download`/`download-pdf` routes already
  dispatch generically on `draft.form` via `filing_gateway_v2` — confirm no ITR-2-specific
  branching is needed there (per the pipeline reference doc, they call `generate_cbdt_json`
  generically already).
- `app/routers/filing.py::_normalize_form` currently hard-restricts to ITR-1/ITR-4 — extend
  the allowlist to include ITR-2 once Phases 1–5 are done and tested. This is confirmed to be
  a small, contained change — the uploader/worker (`app/filing_automation/`) is already
  form-agnostic (reads the form type from the generated JSON itself, per
  `uploader.py::_filing_section_from_json`).
- Frontend: `ITRComputationPage.tsx`'s `handleDirectSubmit` currently hard-gates out ITR-2/3
  (`"Direct Submit is available for ITR-1 and ITR-4 only this season"`) — remove ITR-2 from
  that gate once the backend allowlist change lands and is tested end-to-end on UAT.

**Tests:** integration test posting a full ITR-2 draft through generate → submit (UAT mode) →
poll → acknowledgement, mirroring the existing Direct Submit UAT checklist from
`DUAL_MODE_ERI_INTEGRATION_PLAN.md` Phase 3.

### Phase 8 — ITR-3: repeat Phases 1–7's applicable subset

ITR-3 reuses ITR-2's schedule types **directly by import** — confirmed:
`app/schemas/itr3.py:43-48` already imports `CGTransaction`, `CG112AScrip`, `VDATransaction`,
`BFLossItem`, `ScheduleSIEntry`, `AgriculturalIncome`, `ExemptIncome`, `FSICountryEntry`,
`TR1Entry`, `SPIEntry`, `AMTInput` from `itr2.py` verbatim — so Phase 1/2's `ReturnDraft`
additions serve ITR-3 with **no redesign**, only a new mapper + validators + PGBP-specific
draft fields.

**Known gap to close first:** `itr3.py` does **not** import or redefine `CFLLossItem`,
`ForeignAssetEntry`, `Schedule5AInput`, or `ESOPDeferralInput` from `itr2.py` — before ITR-3's
mapper can use the draft's foreign-assets/Schedule-5A/ESOP fields, `itr3.py` needs those four
imports added (a small, low-risk change, matching the exact reuse pattern already established
for the other 10 types).

**ITR-3-specific additive draft fields** (business/PGBP — `app/engine/schedules/business.py`
already computes this for the calculator, so the draft needs the *input* shape): business
identity, disallowances (u/36, u/37, u/40, u/40A, u/43B), deemed incomes, depreciation
(books vs IT), ICDS adjustment, speculative/specified-business baskets, balance sheet, audit
info (44AB/44AA/92E), nature-of-business codes, partner-in-firm entries, unabsorbed-
depreciation entries. `ITR3BusinessCoreManager.tsx` already exists on the frontend — confirm
in Phase 8.1 whether it already captures this shape or needs the same typed-field treatment
Phase 1 gave capital gains.

**Validator suite**: `app/engine/validators/itr3/` is 57 lines total — essentially
unimplemented, the largest single validator-authoring task in this whole plan. Built from
`Reference Docs by CBDT & ITD/Official Validations/CBDT_e-filing_ITR-3_Validation Rules_V1.0_AY
26-27 (1).pdf` (already in the repo), same pattern as Phase 5, from near-zero.

**Sub-phases** (mirroring Phases 1–7 above, applied to ITR-3): 8.1 extend `ReturnDraft` for
PGBP/balance-sheet/audit fields, 8.2 fix `itr3.py`'s missing imports, 8.3 canonical mapper
(`draft_to_itr3_input.py`), 8.4 wire into `filing_gateway_v2.py`, 8.5 complete validators
(largest sub-phase), 8.6 frontend wiring, 8.7 v2 endpoints + Direct Submit allowlist.

### Phase 9 — Delete the now-dead ITR-2 legacy path

Once Phases 1–7 are tested and the frontend no longer calls the flat-payload path:
- `app/routers/tax.py::_compute_itr2_from_flat_payload` and its call sites.
- `frontend/src/api/itr2Mapper.ts` (already confirmed to have zero external importers even
  today — safe to remove regardless of timing, but grouped here for a single clean commit).
- Confirm `app/routers/itr.py`'s `/itr2/compute`, `/itr2/compute-json` routes (already dead
  per the pipeline reference doc's route inventory) are formally removed, not just unused.

**Tests:** full regression suite green with the legacy path physically absent, not just unused.

### Phase 10 — Production hardening + final verification

Mirrors `ITR4_V2_PIPELINE_AND_LEGACY_DELETION_PLAN.md` Phase 8: sweep for debug prints, confirm
no `getattr`-silent-default masks a real validation gap, run the full ITR-1/2/3/4 regression
suite together, generate a Type-3 UAT sample for ITR-2 and ITR-3 via
`scripts/eri_uat_sanity.py` (registering both forms' draft builders per
`Docs/ERI_UAT_EXPANSION_PLAN.md` Phases 6/11), and manually upload one sample per form to the
ITD UAT portal as the control step before any UAT pack is emailed.

---

## 5. Verification (applies throughout)

- `pytest tests/test_itr1_*.py tests/test_itr4_*.py -v` stays green after every phase.
- Every new `ITR2Input`/`ITR3Input` construction round-trips through `compute_itr{2,3}` →
  `build_itr{2,3}_json` → `validate_itr{2,3}_json` (official CBDT schema) without error.
- `run_input_validation`/`run_calc_validation` report `can_upload=True`, zero Category-A
  blocking errors, for a known-good fixture.
- `npm run build` (`tsc -b && vite build`) clean after every frontend-touching phase.
- Manual portal-upload control before any UAT pack is emailed (Phase 10).

## 6. Update discipline

Same as every other tracker in this repo: after each phase, this file's phase heading gains a
**Delivered** block (files touched, tests run, any deviation from what this section
originally said) before the next phase starts. No phase begins without the previous one
tested and approved.
