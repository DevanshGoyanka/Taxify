# ITR-2 & ITR-3 — v2 Canonical Pipeline Production Implementation Plan

**Status:** Active implementation tracker. No phase starts until the previous phase's tests
pass and the user has approved it. Updated immediately after each phase — status, files
touched, verification result — matching the convention of `ITR4_V2_PIPELINE_AND_LEGACY_DELETION_PLAN.md`.
**Date:** 2026-09-01 (created) · last phase update 2026-09-02
**Authority:** This is the single source of truth for building ITR-2 and ITR-3 to the exact
same production standard ITR-1 and ITR-4 already meet. It is verified against
`Docs/ITR1_ITR4_COMPLETE_PIPELINE_REFERENCE.md` (the ground-truth architecture audit) at every
step — nothing here is guessed from an older doc's claims.
**Relationship to `Docs/ERI_UAT_EXPANSION_PLAN.md`:** that doc owns the shared UAT-pack
tooling (credential-bundle switching, `scripts/eri_uat_sanity.py`) and the final
UAT-sample-generation step for ITD certification. Its Phases 2–11 (the ITR-2/ITR-3 build
items) are **superseded by this document** — treat this doc as the detailed phase plan those
items point to, not a duplicate.

## Progress at a glance

| Phase | What | Status |
|---|---|---|
| 1 | Type the capital-gains schedule (backend mirror of the frontend's shape) | ✅ Delivered 2026-09-01 |
| 2 | Extend `ReturnDraft`/`types.ts` — remaining ITR-2 fields | ✅ Delivered 2026-09-02 |
| 3 | ITR-2 canonical mapper (`draft_to_itr2_input.py`) | Not started |
| 4 | Wire ITR-2 into `filing_gateway_v2.py` | Not started |
| 5 | Complete the ITR-2 CBDT validator suite | Not started |
| 6 | Frontend: wire ITR-2 onto the canonical pipeline | Not started |
| 7 | ITR-2 v2 endpoints + Direct Submit allowlist | Not started |
| 8 | ITR-3 (mirrors 1–7, reusing ITR-2's types) | Not started |
| 9 | Delete the dead ITR-2 legacy path | Not started |
| 10 | Production hardening + final verification | Not started |

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

### Phase 1 — Type the capital-gains schedule on the backend (mirror, not redesign) ✅ Delivered 2026-09-01

**Correction found before implementing:** the frontend's `CapitalGainsSchedule` typing is
**already shipped** — a separate, earlier workstream
(`Docs/ITR1_ITR4_CAPITAL_GAINS_AND_UNIFIED_IMPORTS_IMPLEMENTATION_GUIDE.md`, Phases 1–2,
completed and live 2026-08-19) typed `frontend/src/domain/returns/types.ts`'s
`CapitalGainsSchedule` in full, including a **deliberate, already-shipped scope decision**
(that doc's own §Notes) to leave 10 sub-arrays — `stEquity`, `stNriUnlisted`, `stOtherAssets`,
`ltProviso112`, `ltNri112115`, `ltForeignAssets`, `ltOtherAssets`, `stSlumpSale`,
`ltSlumpSale`, `buyBackLosses` — as generic `JsonRow[]` rows, because
`CapitalGainsEntryManager.tsx` already edits them with its own field-spec validation and a
full retype was explicitly out of scope. That doc's own closing line: *"the typed schedule
from Phase 1 makes it ready for a future ITR-2 workstream"* — this phase is that workstream.

**Corrected scope: this phase only mirrors the existing, stable frontend shape on the
backend — it does not re-open the JsonRow[] scope decision.** The backend
`ReturnDraft.capitalGainsSchedule` is still an untyped `dict`; every other typed sub-array
(`schedule112A`, `schedule115AD`, `vda`, `stImmovable`/`ltImmovable`, `purchases`,
`deductionClaims`, `stUnutilized`/`ltUnutilized`, `stDtaa`/`ltDtaa`, `aggregates`,
`stSection48`, `ltNriProviso48`, `ltNri112A`, flags, `quarterly`, `lossSetOff`) gets a real
Pydantic model with field names matching `types.ts` exactly; the 10 `JsonRow[]`-equivalent
fields become `list[dict[str, Any]]` — matching, not fixing, the frontend's own decision.

**Files:**
- `app/schemas/return_draft.py` — replace `capitalGainsSchedule: dict` with the typed
  `CapitalGainsSchedule` model (new nested types added: `Simplified112ABlock`,
  `TransfereeDetail`, `ImprovementDetail`, `ExemptionClaim`, `ImmovableAssetGain`,
  `Scrip112A`, `Scrip115AD`, `VdaEntry`, `CapitalGainPurchase`, `DtaaEntry`,
  `DeductionClaim`, `UnutilizedDeposit`, `CapitalGainsAggregates`, plus two small aggregate
  blocks for `stSection48`/`ltNriProviso48`).
- **Every call site that touches `draft.capitalGainsSchedule` as a raw dict must be updated**
  (found by grepping the whole `app/` and `tests/` trees, not assumed): `app/engine/
  draft_to_itr1_input.py::_map_capital_gains` (dict `.get()` → attribute access),
  `app/engine/filing_gateway_v2.py`'s capital-gains-summary builder (same fix),
  `app/engine/flat_to_draft.py` (the legacy one-way migration adapter — wrap in
  `CapitalGainsSchedule.model_validate(...)` with a fallback to an empty schedule on
  failure, since old rows may not conform and this adapter must not crash migration),
  `audit_itr_coverage.py`'s two draft builders (construct the typed model, not a dict
  literal), and the two tests that currently assign a raw dict post-construction
  (`tests/test_filing_gateway_v2.py`, `tests/test_tax_v2_compute.py`) — `ReturnDraft` has no
  `validate_assignment=True`, so a raw-dict assignment after construction silently stores an
  unvalidated dict instead of coercing it, which would break every attribute-access read.
  (`tests/test_ay2026_calculator_regressions.py`'s `capitalGainsSchedule` dict is a raw JSON
  payload to the legacy `compute_tax_summary` flat-blob function, not a `ReturnDraft` —
  unaffected, confirmed by reading its call site.)

**Tests:** schema round-trip tests (typed CG schedule serializes/deserializes losslessly,
`extra="forbid"` still rejects unknown keys), ITR-1 regression suite stays green.

**Delivered (backend only — frontend was already done, confirmed no change needed):**
- `app/schemas/return_draft.py` — added `CapitalGainsSchedule` and 15 nested types
  (`Simplified112ABlock`, `CGTransfereeDetail`, `CGImprovementDetail`, `CGExemptionClaim`,
  `ImmovableAssetGain`, `Scrip112A`, `Scrip115AD`, `VdaEntry`, `CapitalGainPurchase`,
  `CGDtaaEntry`, `CGDeductionClaim`, `CGUnutilizedDeposit`, `CapitalGainsAggregates`,
  `CGSection48Block`, `CGNriProviso48Block`), field names matching `types.ts` exactly; the 10
  frontend-JsonRow[] fields became `list[dict[str, Any]]` — same scope, not re-typed.
  `ReturnDraft.capitalGainsSchedule` changed from `dict` to `CapitalGainsSchedule`.
- `app/engine/draft_to_itr1_input.py::_map_capital_gains` — `sched.get("simplified112A")`
  dict access → `draft.capitalGainsSchedule.simplified112A` attribute access.
- `app/engine/filing_gateway_v2.py`'s capital-gains-summary builder — same dict→attribute
  fix; the old `if simplified:` truthiness check (always true for a non-optional typed
  field) replaced with an explicit `has_simplified = sale > 0 or cost > 0` computed value,
  preserving the original "block present vs empty" semantics.
- `app/engine/flat_to_draft.py` — the legacy one-way migration adapter now constructs
  `CapitalGainsSchedule.model_validate(...)` with a fallback to an empty schedule on
  `ValidationError`, so an old, non-conforming saved row can't crash migration.
- `audit_itr_coverage.py` — both draft builders construct `CapitalGainsSchedule(...)`
  instead of a dict literal (one directly; one copies the already-typed attribute from
  another draft, unchanged).
- `tests/test_filing_gateway_v2.py`, `tests/test_tax_v2_compute.py` — updated the two
  post-construction dict assignments to construct `CapitalGainsSchedule(...)`.
- `tests/test_return_draft_schema.py` — 5 new tests: typed-empty-default, full round-trip
  (typed sub-arrays + generic rows together), `extra="forbid"` on the schedule itself, same
  on a typed sub-array element, and backward compatibility with the old
  simplified-112A-only shape every existing ITR-1/4 client has saved today.
- Frontend: confirmed via `Docs/ITR1_ITR4_CAPITAL_GAINS_AND_UNIFIED_IMPORTS_IMPLEMENTATION_GUIDE.md`
  that `types.ts`'s `CapitalGainsSchedule` was already fully typed and live (a separate,
  earlier, completed workstream) — no frontend change was needed for this phase.

**Verification (all run 2026-09-01):**
- `pytest tests/test_return_draft_schema.py` — 17 passed (12 existing + 5 new).
- `pytest tests/test_filing_gateway_v2.py tests/test_tax_v2_compute.py tests/test_itr1_calculator.py
  tests/test_itr4_calculator.py tests/test_draft_to_itr1_input.py tests/test_itr1_golden_suite.py
  tests/test_itr1_filing_gateway_profile.py tests/test_itr1_filing_gateway_profile_v2.py
  tests/test_112a_unification.py tests/test_filing_orchestrator.py tests/test_personal_info_contract.py
  tests/test_eri_creation_info_invariant.py tests/test_eri_routers.py` — 171 passed.
- `python -c "import app.main"` — OK.
- `npm run build` — clean, no type errors.
- **Pre-existing, unrelated finding surfaced during verification**: 18 tests in
  `tests/test_filing_gateway_v2_itr4.py` fail on today's date (2026-09-01) — confirmed via
  `git stash` that they fail identically on the pre-this-phase baseline. Root cause: ITR-4's
  due date is 31 August, and these fixtures are pinned to a pre-due-date filing scenario with
  no date-adaptive logic (the same class of bug `scripts/eri_uat_sanity.py`'s
  `_apply_current_filing_section` was built to route around for the UAT pack, but these
  particular test fixtures don't use it). Out of scope for this phase; flagged for separate
  follow-up, not fixed here.

### Phase 2 — Extend `ReturnDraft` / `types.ts` with the remaining ITR-2 fields ✅ Delivered 2026-09-02

Everything capital-gains-shaped is Phase 1's job; this phase covers the rest, using the
**already-drafted but unwired** types already sitting in `return_draft.py` (added, then
paused for this exact review) as the starting point — corrected per the naming decisions
below rather than redesigned from scratch:

- **Reuse frontend names, don't invent new ones**: `PersonalInfo.isDirector`,
  `PersonalInfo.holdsUnlistedShares` already exist on the frontend and are wired into
  `ClientsPage.tsx`'s intake questionnaire + `eligibility.ts` — the backend gets fields with
  these exact names, not `isCompanyDirector`/`heldUnlistedEquity`.
- **`residentialStatus`: correction found while implementing.** The official CBDT ITR-2 JSON
  Schema (`Reference Docs by CBDT & ITD/Official JSON Schema/ITR-2_2026_Main_V1.1 (2).json`)
  confirms the wire format really is `RES/NRI/NOR` — matching `itr2.py`'s existing enum. But
  `frontend/src/domain/eligibility.ts`'s `EligibilityFacts.residentialStatus:
  'ROR'|'RNOR'|'NR'` is **live, wired, tested code** (20+ references in
  `eligibility.test.ts`/`scheduleRegistry.test.ts`, two direct equality comparisons gating
  real form-recommendation logic) already reading from `draft.personal.residentialStatus`.
  Renaming its values would touch live eligibility logic for zero benefit. **Decision: the
  backend `PersonalInfo.residentialStatus` field uses `'ROR'|'RNOR'|'NR'`** — matching the
  already-shipped, already-tested frontend exactly, zero frontend change needed — and
  **`draft_to_itr2_input.py` (Phase 3) translates `ROR→RES, NR→NRI, RNOR→NOR`** when building
  `ITR2Input.residential_status`, the same way every existing mapper already translates
  draft-level friendly values into CBDT-exact codes (e.g. `SELF_OCCUPIED→S`, `SELF→S`).
- **New, no frontend collision** (confirmed zero prior representation via `scheduleRegistry.ts`
  marking all of these `status: 'missing'`): Schedule FSI, Schedule TR, Schedule FA, Schedule
  SPI (clubbing), Schedule PTI (pass-through income — name the field
  `passThroughIncomeEntries`, not `passThroughIncome`, to avoid confusion with the existing
  `HouseProperty.passThroughIncome` and `housePropertyPassThroughIncome` fields), AMT,
  Schedule AL, Schedule 5A (Portuguese Civil Code), ESOP deferral.
- **`BroughtForwardLosses` — correction found while implementing**: the frontend's existing
  `lossesBroughtForward: BroughtForwardLosses` (a flat current-year aggregate, 5 scalars) was
  already on `types.ts`/`factory.ts` but **not read by any Python code at all** — not even by
  ITR-1/4. ITR-2's `bf_losses: List[BFLossItem]` needs a genuinely different shape (per-AY
  entries), so this isn't an extension of a live field — it's two brand-new, separate
  top-level fields: `broughtForwardLossEntries`/`carriedForwardLossEntries`, added to both
  `return_draft.py` and `types.ts` since neither side had this shape before.
- **New declarations with no frontend field at all yet**: `sebiRegistrationNumber`,
  `isFiiFpi`, `portugueseCivilCodeApplies` — add to `FilingStatus` alongside the existing
  ITR-4 declaration-style fields.

**Files:** `app/schemas/return_draft.py` (revise the already-drafted block), 
`frontend/src/domain/returns/types.ts` (mirror in the same phase — per the user's explicit
"update the frontend mirror in lockstep" instruction, this is not deferred).

**Delivered:**
- `app/schemas/return_draft.py` — `PersonalInfo` gained `residentialStatus` (`ROR/RNOR/NR`,
  matching `eligibility.ts` exactly — not the CBDT wire codes, which the future mapper
  derives), `isDirector`, `holdsUnlistedShares` (both already-live frontend field names).
  `FilingStatus` gained `sebiRegistrationNumber`, `isFiiFpi`, `portugueseCivilCodeApplies`.
  `ReturnDraft` gained 11 new fields backed by 12 new types: `BroughtForwardLosses` (parity
  aggregate, mirrors the frontend's already-shipped-but-Python-unused type),
  `BroughtForwardLossEntry`/`CarriedForwardLossEntry` (new per-AY shape),
  `ForeignSourceIncomeEntry` (FSI), `ForeignTaxReliefEntry` (TR), `ForeignAssetEntry` (FA),
  `ClubbedIncomeEntry` (SPI), `PassThroughIncomeEntry` (PTI), `AMTDetails`/`AMTCreditEntry`,
  `AssetLiabilityDetails` (AL), `PortugueseCivilCodeDetails` (5A), `ESOPDeferralEntry`.
- `frontend/src/domain/returns/types.ts` — the 9 genuinely-new schedules mirrored field-for-
  field (12 new interfaces/types); `FilingStatus` gained the 3 new declarations.
  `residentialStatus`/`isDirector`/`holdsUnlistedShares` needed **no frontend change** —
  already live on `PersonalInfo` since before this phase.
- `frontend/src/domain/returns/factory.ts` — `createEmptyReturnDraft()` populates all 11 new
  `ReturnDraft` fields and the 3 new `FilingStatus` fields with their empty defaults;
  `tsc -b`'s required-property checking caught this automatically (a missing field here would
  have been a compile error, not a silent gap).
- `tests/test_return_draft_schema.py` — 3 new tests: empty-ITR-2-draft defaults, full
  round-trip of populated Phase 2 fields, and an ITR-1 regression confirming none of this
  changes ITR-1's behavior.

**Corrections found while implementing (both already folded into the description above,
recorded here for the audit trail):**
1. `residentialStatus` — reversed the original "align frontend to RES/NRI/NOR" decision after
   discovering `eligibility.ts`'s `'ROR'|'RNOR'|'NR'` is live, tested, wired logic (not a
   throwaway field) — translation belongs in the future mapper, not a frontend rename.
2. `BroughtForwardLosses` — the plan assumed extending an "already wired to ITR-1/4" type;
   grepping actual Python call sites found zero references anywhere, and the shape ITR-2
   needs (per-AY) is different from the existing flat aggregate anyway, so this became two
   new fields instead of an extension.

**Verification (all run 2026-09-02):**
- `python -c "import app.main"` — OK.
- `pytest tests/test_return_draft_schema.py tests/test_filing_gateway_v2.py
  tests/test_tax_v2_compute.py tests/test_itr1_calculator.py tests/test_itr4_calculator.py
  tests/test_draft_to_itr1_input.py tests/test_itr1_golden_suite.py
  tests/test_itr1_filing_gateway_profile.py tests/test_itr1_filing_gateway_profile_v2.py
  tests/test_112a_unification.py tests/test_filing_orchestrator.py
  tests/test_personal_info_contract.py tests/test_eri_creation_info_invariant.py
  tests/test_eri_routers.py` — 174 passed.
- `npx tsc -b` — 0 errors.
- `npx vitest run` — 21 files / 167 tests passed.
- `npm run build` — clean production build.

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
