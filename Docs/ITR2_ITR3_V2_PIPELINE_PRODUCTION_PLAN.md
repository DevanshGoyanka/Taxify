# ITR-2 & ITR-3 — v2 Canonical Pipeline Production Implementation Plan

**Status:** Active implementation tracker. Phases 1–5D are delivered; Phase 5E remains, followed by the mandatory shared canonical-profile and complete-preparer migration before frontend or direct-submit work begins. Updated immediately after each phase — status, files touched, verification result — matching the convention of `ITR4_V2_PIPELINE_AND_LEGACY_DELETION_PLAN.md`.
**Date:** 2026-09-01 (created) · last phase update 2026-09-02
**Authority:** This is the single source of truth for building ITR-2 and ITR-3 on the same complete-preparation standard now established by the ITR-1 and ITR-4 canonical flows. It is verified against `Docs/ITR1_ITR4_COMPLETE_PIPELINE_REFERENCE.md` and `Docs/design/CANONICAL_RETURN_PIPELINE_MIGRATION_PLAN.md` at every step — nothing here is guessed from an older doc's claims.
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
| 3 | ITR-2 canonical mapper (`draft_to_itr2_input.py`) | ✅ Delivered 2026-09-02 |
| 4 | Wire ITR-2 into `filing_gateway_v2.py` | ✅ Delivered 2026-09-02 |
| 5 | Complete the ITR-2 CBDT validator suite (5A–5E ✅ Delivered 2026-09-02; 5F/5G architecture gates still required before Phase 6) | ✅ Delivered 2026-09-02 |
| 5F | Shared canonical personal-profile foundation | Not started — mandatory before frontend/ITR-3 |
| 5G | Migrate ITR-2 to complete pre-calculation preparation | Not started |
| 6 | Frontend: wire ITR-2 onto the canonical `ReturnDraft` | Blocked until 5G |
| 7 | ITR-2 v2 endpoints + Direct Submit allowlist | Blocked until 5G |
| 8 | ITR-3 on the shared complete-preparation contract | Not started |
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

ITR-2 and ITR-3 do not yet meet the complete-preparation standard. ITR-2 now has substantial delivered foundation work — typed draft fields, canonical mapping, v2 dispatch, JSON generation, and validator coverage through 5D — but its filing-detail enrichment still requires the Phase 5F/5G migration. ITR-3 remains without a canonical mapper, v2 dispatch, or production frontend path. Verified current state (research conducted this session, cross-checked against actual code):

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
5. **Preparation before calculation.** Every form must construct one complete typed input — including filing profile, property/employer/TDS details, bank accounts, verification, representative data, and TRP where applicable — before invoking its calculator. JSON generation may only serialize the prepared input.
6. **No shortcut code.** Everything touched in `app/eri/`, `app/engine/`, or the filing
   pipeline is production-grade and reused unchanged later — this is a hard constraint from
   the user, not a suggestion.
7. **Never route through `app/engine/filing_gateway.py`.** Confirmed dead/unreachable for
   ITR-1/ITR-4 (`ITR1_ITR4_COMPLETE_PIPELINE_REFERENCE.md` §4) and was never a real fallback
   for ITR-2/ITR-3 either — every live route hard-normalizes to ITR-1/ITR-4 before reaching
   it. `filing_gateway_v2.py`'s dispatch is the only place new forms get added.

## 3. Target architecture (after this plan)

The non-negotiable invariant is the same one now used by the completed ITR-1 and ITR-4 flows:

```text
One persisted ReturnDraft
    → one complete form-specific prepared input
        → input validation
        → one calculation result
            ├── compute summary
            └── CBDT JSON
                → official schema validation
                → digest / submission
```

Taxpayer-level filing facts are prepared before calculation, even when CBDT represents them as separate wire blocks:

```text
ReturnDraft
  → normalize_return_draft()
  → prepare_personal_profile()
       ├── identity, contact, addresses
       ├── filing status and eligibility
       ├── verification and representative details
       ├── bank accounts
       └── tax-return-preparer
  → form-specific preparer
       ├── prepare_itr1()  [existing reference implementation]
       ├── prepare_itr2()
       ├── prepare_itr3()
       └── prepare_itr4()  [existing reference implementation]
  → complete typed input
  → input validation
  → calculator
  → calculation validation
  → PreparedReturn
  → serializer reads only the prepared typed input
```

The serializer may emit separate CBDT `PersonalInfo`, `FilingStatus`, `Verification`,
`Refund.BankAccountDtls`, `TaxReturnPreparer`, and schedule blocks. It must not reconstruct
those values from `ReturnDraft` or perform `model_copy(update={...})` enrichment after
calculation. ITR-2-specific property, employer, and TDS3 filing-detail arrays remain
schedule-level data, but they must be assembled by the same preparer before calculation.

```text
ClientITR.form_data = JSON(ReturnDraft)
  ├─ ITR-1: complete prepared input → compute_itr1 → build_itr1_json
  ├─ ITR-4: complete prepared input → compute_itr4 → build_itr4_json
  ├─ ITR-2: complete prepared input → compute_itr2 → build_itr2_json
  └─ ITR-3: complete prepared input → compute_itr3 → build_itr3_json
       each gated by input + calculation validation
```

Deleted only after all consumers are repointed through the complete preparer (Phase 9):
  ✗ `app/routers/tax.py::_compute_itr2_from_flat_payload`
  ✗ `frontend/src/api/itr2Mapper.ts`
  ✗ dead legacy `/itr{2,3}/compute[-json]` routes

Current ITR-2 v2 compute and JSON code is foundational but not yet architecture-complete:
its mapper/calculator/validator work is valuable and retained, while its filing profile and
schedule-detail enrichment must move into the pre-calculation preparer phases below.

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

### Phase 3 — Canonical mapper: `app/engine/draft_to_itr2_input.py` ✅ Delivered 2026-09-02

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

**Delivered:**
- `app/engine/draft_to_itr2_input.py` (new, ~420 lines) — `draft_to_itr2_input(draft) ->
  (ITR2Input, breakdown)`. Reuses 9 shared helpers from `draft_to_itr1_input.py` unchanged
  (`_age_bracket_from_dob`, `_map_salary`, `_map_house_properties`, `_map_other_sources`,
  `_map_deductions`, `_map_tds`, `_map_tds3`, `_map_tcs`, `_map_tax_payments`, `_to_date`).
  New ITR-2-specific mapping functions: `_map_residential_status` (ROR/RNOR/NR → RES/NRI/NOR),
  `_map_112a_scrips`, `_map_immovable_gains`, `_map_vda_transactions`, `_map_bf_losses`,
  `_map_agricultural_income`, `_map_exempt_income`, `_map_fsi_entries`, `_map_tr1_entries`,
  `_map_foreign_assets`, `_map_spi_entries`, `_map_pti_entries`, `_map_amt_input`,
  `_map_si_entries`. `filing_profile`/`employer_filing_details`/`property_filing_details`/
  `tds3_filing_details`/`bank_accounts` left empty/`None`, matching ITR-4's exact pattern —
  Phase 4 constructs those (official-JSON concerns, not compute concerns).
- **Schema gap found and closed additively**: `app/schemas/return_draft.py`'s `Scrip112A`
  (shipped by an earlier, separate CG workstream) had no acquisition/transfer date fields at
  all, but CBDT's `CG112AScrip` requires a transfer date. Added
  `dateOfAcquisition`/`dateOfTransfer` as `Optional[str]` (zero risk to existing construction
  sites) to both `return_draft.py` and `frontend/src/domain/returns/types.ts`. The mapper
  **skips** (does not fabricate) a scrip missing a transfer date, surfacing the count via
  `breakdown["cg_112a_scrips_skipped_no_date"]` — until the capture UI is extended to record
  per-scrip dates (a follow-up frontend task), 112A scrips entered today won't reach Schedule
  112A in the CBDT JSON. This is a real, visible limitation, not a silent one.
- **Real, pre-existing bug found and fixed**: `app/schemas/itr2.py`'s
  `FSICountryEntry.derive_and_validate_total` unconditionally reassigned
  `self.total_income` inside a `mode="after"` validator on a model with
  `validate_assignment=True` — every assignment re-triggered the same validator, causing
  infinite recursion (Python's recursion limit) on **every** construction, not something this
  phase introduced. This mapper is apparently the first real caller to ever construct one
  without pre-supplying a matching `total_income`. Fixed with a `!= computed` guard before
  the assignment (checked every other `model_validator(mode="after")` in the file — this was
  the only instance of the pattern).
- Explicitly NOT mapped this phase (documented in the module docstring, not silently
  dropped): the capital-gains schedule's 10 generic-row fields (`stEquity`, `stNriUnlisted`,
  `stOtherAssets`, `ltProviso112`, `ltNri112115`, `ltForeignAssets`, `ltOtherAssets`,
  `stSlumpSale`, `ltSlumpSale`, `buyBackLosses`) — no fixed key shape exists for them yet;
  mapping them requires reading `CapitalGainsEntryManager.tsx`'s exact field-spec key names
  rather than guessing.
- `tests/test_draft_to_itr2_input.py` (new) — 8 tests exercising every mapped ITR-2-specific
  head end-to-end through `compute_itr2` (112A scrip with/without date, immovable LTCG, VDA,
  FSI/TR/FA/SPI/PTI, AMT + Schedule SI, brought-forward losses, new-regime deduction zeroing).

**Verification (all run 2026-09-02):**
- `pytest tests/test_draft_to_itr2_input.py` — 8 passed.
- `pytest tests/test_itr2_integration.py tests/test_itr2_itd_builder.py
  tests/test_itr2_production_path.py tests/test_itr2_validators.py` — 40 passed (confirms the
  `FSICountryEntry` fix doesn't disturb existing ITR-2 coverage).
- `pytest tests/test_return_draft_schema.py tests/test_filing_gateway_v2.py
  tests/test_tax_v2_compute.py tests/test_itr1_calculator.py tests/test_itr4_calculator.py
  tests/test_draft_to_itr1_input.py tests/test_draft_to_itr2_input.py
  tests/test_itr1_golden_suite.py tests/test_itr1_filing_gateway_profile.py
  tests/test_itr1_filing_gateway_profile_v2.py tests/test_112a_unification.py
  tests/test_filing_orchestrator.py tests/test_personal_info_contract.py
  tests/test_eri_creation_info_invariant.py tests/test_eri_routers.py
  tests/test_itr2_integration.py tests/test_itr2_itd_builder.py
  tests/test_itr2_production_path.py tests/test_itr2_validators.py` — 222 passed.
- Full-repo sweep (`pytest tests/ --continue-on-collection-errors`, excluding the known
  ITR-4 date-bomb file and live-client/e2e tests): **1319 passed, 0 failed** — 9 pre-existing
  collection errors (stale `app.eri.login` imports from before the Type-2 module reorg, e.g.
  `test_acknowledgement.py`), unrelated to this phase.
- `npx tsc -b` — 0 errors. `npx vitest run` — 167 passed. `npm run build` — clean.

### Phase 4 — Wire ITR-2 into `filing_gateway_v2.py` + CBDT validators

Extends the two dispatch points currently hardcoded to ITR-1/ITR-4 only
(`compute_canonical()` and `generate_cbdt_json()`, `filing_gateway_v2.py:1202-1255`):
add `compute_canonical_itr2()` and `_generate_cbdt_json_itr2()`, mirroring
`compute_canonical_itr4`/`_generate_cbdt_json_itr4` exactly — including running
`run_input_validation` + `run_calc_validation` from `app.engine.validators.itr2` before
`build_itr2_json`, so Category A failures block generation instead of reaching the portal.

**Tests:** `tests/test_filing_gateway_v2_itr2.py` (new, mirrors `test_filing_gateway_v2_itr4.py`).

**Delivered 2026-09-02.**

- **`app/engine/filing_gateway_v2.py`** — added the full ITR-2 gateway section
  (`ITR2PipelineResult`, `_itr2_filing_profile`, `_itr2_property_filing_details`,
  `_itr2_employer_filing_details`, `_itr2_tds3_filing_details`, `compute_canonical_itr2`,
  `_generate_cbdt_json_itr2`) mirroring the ITR-4 pattern (`_itr4_filing_profile` /
  `compute_canonical_itr4` / `_generate_cbdt_json_itr4`), and extended both
  `compute_canonical()` and `generate_cbdt_json()` dispatch with an ITR-2 branch. Real gaps
  found and fixed while wiring, not glossed over:
  - `_itr2_filing_profile` restricts `verification.capacity` to `SELF`/`KARTA` only —
    `ITR2FilingProfile.verification_capacity: Literal["S","K"]` has no representative-filing
    slot at all (unlike ITR-1's `S`/`R`), so a `REPRESENTATIVE`/`PARTNER` capacity is rejected
    with a clear `FilingGatewayV2Error` before it ever reaches JSON generation.
  - `_itr2_property_filing_details` / `_itr2_employer_filing_details` / `_itr2_tds3_filing_details`
    must produce exactly one row per `property_filing_details`/`tds1_entries`/`tds3_entries`
    row (`ITR2Input.validate_cross_schedule_contract`). The employer/TDS3 helpers do **not**
    walk `draft.employers`/`draft.taxes.tds` independently — they replay the identical
    accept/reject filter `draft_to_itr1_input._map_tds`/`_map_tds3` already use to build
    `tds1_entries`/`tds3_entries` (claimed-in-return, non-TDS3, valid TAN, salary section),
    including sourcing `employer_name` from the exact same `row.deductorName` value TDS1Entry
    uses — `build_itr2_json`'s Schedule S rejects any filing-detail row whose name doesn't
    match its TDS1 entry byte-for-byte, so deriving the name from `draft.employers` instead
    (a plausible first attempt) fails at JSON-build time whenever the two names differ.
  - Added a dedicated `_itr2_summary_from_result`/`_itr2_capital_gains_summary` rather than
    reusing ITR-1/4's `_summary_from_result`/`_capital_gains_summary`: `ITR2Result` does not
    share `ITR1Result`'s `capital_gains_112a`/`advance_tax_paid`/`self_assessment_tax_paid`
    attribute names (`capital_gains_income`/`total_advance_tax`/`total_self_assessment_tax`
    instead), so blind reuse raises `AttributeError` at runtime; and ITR-1/4's capital-gains
    summary is explicitly the *simplified 112A aggregate* overlay keyed to
    `draft.capitalGainsSchedule.simplified112A`, which ITR-2 doesn't use (it carries the full
    per-transaction Schedule CG). The new summary reads real STCG/LTCG/total figures straight
    off the engine's own `result.schedules["cg"]` instead of fabricating a per-row overlay.
  - Found and fixed a genuine pre-existing bug in **`app/engine/validators/itr2/calc_rules.py`**
    (ITR2-CALC-018/019): the balance-payable/refund-due reconciliation checks compared against
    a ₹1 tolerance, but both fields are `round_to_nearest_10(...)` (section 288B) in
    `app/engine/calculators/itr2.py` — so any return whose raw payable/refund isn't already a
    multiple of 10 false-positived as a Category-A blocking error. Fixed to use the same ₹10
    tolerance ITR-1's equivalent rules (`ITR1-R105`/`R106`) already use for the identical
    reason — this was blocking every realistic filing-ready draft from generating.
- **`app/engine/draft_to_itr2_input.py`** — small Phase-3 scope correction made just before
  this phase started: `bank_accounts` is now mapped directly via the shared
  `_map_bank_accounts` (reused from `draft_to_itr1_input`), since `ITR2Input.bank_accounts`
  is `list[app.schemas.itr1.BankAccount]` — the same shared type ITR-1 uses, unlike ITR-4's
  distinct bank-account type that genuinely needs gateway-layer construction.
- **`tests/test_filing_gateway_v2_itr2.py`** (new) — 7 tests: compute returns a populated
  summary; pending AIS/TIS reconciliation blocks compute; `compute_canonical()` dispatches
  ITR-2 to the new pipeline; `compute_canonical_itr2` rejects a non-ITR-2 draft;
  `generate_cbdt_json` produces official JSON that passes the CBDT Category A validators and
  the official JSON schema; representative verification capacity is rejected; and
  `PropertyFilingDetail` rows are emitted 1:1 with canonical house properties.
- **Updated for the new ITR-2 dispatch branch** (both were asserting "ITR-2/3 unsupported",
  which stopped being true for ITR-2 this phase — updated to assert against ITR-3, which is
  still correctly unsupported pending Phase 8):
  `tests/test_filing_gateway_v2_itr4.py::test_compute_canonical_rejects_unsupported_form`,
  `tests/test_tax_v2_compute.py::test_compute_v2_rejects_non_itr1_form_with_422`.
- **Verification:**
  - `pytest tests/test_filing_gateway_v2_itr2.py tests/test_filing_gateway_v2.py
    tests/test_draft_to_itr2_input.py -q` — 41 passed.
  - `pytest tests/ -q` (deselecting `test_filing_gateway_v2_itr4.py` and the pre-existing
    stale-`app.eri.login`-import collection failures already logged in Phase 3's delivered
    note) — **1327 passed, 0 failed.** `test_filing_gateway_v2_itr4.py` itself carries 18
    pre-existing failures, confirmed via `git stash` to be present identically on the
    pre-Phase-4 commit — the AY2026-27 due dates (31-Jul/31-Aug-2026) have now passed relative
    to the system clock (2026-09-02+), so ITR-4 test fixtures using an on-time 139(1) section
    without an explicit past `verification.date` now hit the real due-date guard. Unrelated to
    this phase's changes; not fixed here (out of scope — a test-fixture dating issue, not a
    Phase 4 wiring defect).
  - `npx tsc -b` — 0 errors. `npx vitest run` — 167 passed. `npm run build` — clean (Phase 4
    touched no frontend files; run for full-verification discipline anyway).

### Phase 5 — Complete the ITR-2 CBDT validator suite

**The hardest phase — bigger than originally scoped.** Reading the full official
`Reference Docs by CBDT & ITD/Official Validations/CBDT__e-Filing_ITR 2_Validation Rules_AY
2026-27_V1.0 (1).pdf` (51 pages, done 2026-09-02) surfaced **764 Category A (blocking) rules
+ 26 Category B/D rules = 790 total** — comparable in density to ITR-1's 4,431-line suite,
against a materially more complex form. `app/engine/validators/itr2/input_rules.py` (365
lines) and `calc_rules.py` (260/266 lines as of Phase 4) cover a small fraction of that.

A meaningful share of the 790 are **not independently checkable against this codebase's
architecture** — they're consistency checks between a CBDT dropdown-UI's sub-fields and their
own displayed totals (e.g. "sum of drop-downs in Sl.No. 1a of Schedule S should equal Sl.No.
1a"). This repo has no such UI; `build_itr2_json` constructs the JSON programmatically from
typed fields, so those identities are already guaranteed by construction and add no value as
a runtime check. The genuinely applicable rules are the real business-logic ones: deduction
caps by regime/status/age, HRA/exemption formulas, mandatory-detail-when-claimed checks,
regime-conditional restrictions, due-date-gated deductions, and cross-schedule reconciliation.

Per user decision 2026-09-02: split into sub-phases by rule cluster, each following the exact
`ValidationRule`/Category A-B-D/`ValidationReport.can_upload`/`blocking_errors` pattern
`itr1/input_rules.py` already establishes (no new validation framework), each with its own
Delivered block, tests, verification, and commit — same checkpoint discipline as Phases 1–4,
just more of them:

- **5A — Schedule S (Salary) + Schedule HP (House Property)**, including the 24(b)/80EE/80EEA
  loan cross-checks that live between the two.
- **5B — Schedule CG / 112A / 115AD(1)(b)(iii) / VDA** (capital gains, the largest single
  computational schedule).
- **5C — Chapter VI-A deduction suite** (80C/80CCC/80CCD/80D/80DD/80DDB/80E/80EE/80EEA/80EEB/
  80G/80GG/80GGA/80GGC/80QQB/80RRB/80TTA/80TTB/80U/80CCH) — the largest rule cluster (~150
  rules), mostly a repeating "eligible amount ≤ user-enterable amount, mandatory detail when
  claimed, regime/status/age gate" pattern.
- **5D — Schedule OS (Other Sources) + Schedule SI + CYLA/BFLA/CFL loss set-off.**
- **5E — AMT/AMTC, Schedule EI (exempt income), PTI, FSI/TR/FA, Schedule 5A, Schedule AL,
  TDS/TCS/IT reconciliation, Part B-TI/TTI final reconciliation, and the 26 Category B/D
  rules.**

**Tests:** `tests/test_itr2_input_validation.py`, `tests/test_itr2_calc_validation.py` — one
test per new rule, known-good and known-bad cases, same pattern as ITR-1's R145 tests.

**5A Delivered 2026-09-02.**

- **`app/engine/validators/itr2/input_rules.py`** — added 8 Schedule S (Salary) rules
  (`ITR2-IN-SAL-001`..`008`) and 5 Schedule HP (House Property) rules (`ITR2-IN-HP-001`..
  `005`), all Category A. Scoped deliberately to what's genuinely checkable and non-redundant
  against this codebase's architecture — read `app/engine/schedules/salary.py` and
  `house_property.py` in full before writing any rule, which changed the plan in three ways:
  - **Most of the CBDT catalog's salary-exemption cap rules are structurally already
    guaranteed and were *not* re-implemented as validators**: CBDT rules 28 (gratuity, 20L/25L
    caps), 36 (entertainment allowance formula — least of ₹5,000/⅕ salary/20% basic), 40
    (₹50,000 old-regime standard-deduction cap), 44 (commuted pension — ⅓ formula for
    non-govt), 45 (leave encashment, 25L cap), 46 (VRS compensation, 5L cap), 56 (disabled-
    employee transport allowance, ₹38,400 cap), and 66 (retrenchment compensation, 5L cap) are
    all computed by the engine from the taxpayer's *gross received* amount with the statutory
    ceiling applied via `min()`/formula inside `app/engine/schedules/salary.py`'s `compute()`
    itself — there is no user-suppliable "exempt amount" field for those that could violate the
    cap, so a pre-compute validator re-checking the cap would just be dead code. The rules
    actually implemented (`SAL-001`..`004`, CBDT rules 41/42/43/48) are the ones where the
    schema *does* take a direct pass-through exempt-amount claim from the user (LTA, embassy/
    foreign-service allowance, 10(10CC) employer-paid perquisite tax) — those genuinely need a
    ceiling check.
  - `SAL-005` is CBDT rule 35 (entertainment allowance restricted to government employees).
  - **New-regime rules `SAL-006`/`007`/`008` (CBDT rules 54/58/57 respectively) catch claims
    the calculator currently discards silently rather than rejecting.** `salary.py`'s
    new-regime branch unconditionally zeroes HRA/LTA/entertainment/professional-tax regardless
    of what the user submitted — filing a new-regime return with those fields populated
    previously produced a correct *result* but with no signal to the taxpayer that their claim
    was dropped. These rules surface that as a pre-compute Category A error instead. (Rule 54
    also names Sec 10(14)(i)/(ii) and Sec 10(17) MP/MLA/MLC allowances; not included in
    `SAL-006` — 10(14)(i)/(ii) already always compute to a zero exemption regardless of regime
    in this engine's `_exempt_children_education`/`_exempt_hostel`, since the number-of-children
    input those need is hardcoded to 0, and there is no Sec 10(17) field on `SalaryIncome` at
    all — so extending the rule to them would either be redundant or unrepresentable.)
  - **A planned rule was discovered to be dead code before being written and was dropped**:
    `HousePropertyIncome.ownership_share_percentage` has a schema-level `Gt(gt=0)` constraint,
    so "block interest deduction when co-owned share is zero" (CBDT rule 70) can never fire —
    Pydantic itself never lets that state exist. Caught by the test-first pass (the known-bad
    case for it wouldn't even construct), not shipped.
  - `HP-001` is CBDT rule 71 (no municipal tax when gross rent is zero); `HP-002` is rule 74
    (let-out/deemed-let-out requires positive rent); `HP-003` is rule 80 (max two self-occupied
    properties).
  - **`HP-004`/`005` (CBDT rules 751/753, co-owned share consistency) read
    `property_filing_details`** — a gateway-attached field, not compute-relevant — since that's
    the only place `co_owned` and `assessee_share_percent` live together; `HousePropertyIncome`
    itself has no co-owned flag, only the resulting share percentage.
  - **Not implemented, and explicitly out of scope for 5A**: CBDT rule 29 (old-regime HRA ≤
    50% of Basic+DA) — `SalaryIncome` has no Basic/DA breakout to check it against, and no
    proxy was fabricated in its place; CBDT rule 82 (co-owner PAN must differ from assessee
    PAN) — `PropertyFilingDetail` captures no co-owner PAN field at all; the Schedule
    24(b)/80EE/80EEA loan-detail cross-checks (rules 607–639) — `ITR2Input` has no granular
    loan-detail schedule the way ITR-1/4 do. All three are genuine schema gaps, not omissions
    of convenience.
  - The literal-cap self-occupied-interest rules (72: old regime ≤ ₹2L; 81: new regime ₹0)
    were deliberately **not** implemented as Category A blocks: `house_property.py` already
    caps/disallows correctly (clamping with carry-forward, not rejecting) for both regimes —
    over-limit interest is legal input the engine handles correctly, so a hard block there
    would incorrectly reject valid returns.
- **`tests/test_itr2_input_validation.py`** (new) — 26 tests (one known-good + one known-bad
  per rule, 13 rules × 2), mirroring `test_itr1_input_validation.py`'s pattern.
- **`tests/test_filing_gateway_v2_itr2.py`** — one pre-existing fixture (`HouseProperty(...,
  propertyType="LET_OUT")` with no rent) legitimately started failing under the new `HP-002`
  rule — a genuinely invalid draft (a let-out property can't have zero rent), not a rule bug.
  Fixed the fixture to supply `annualLettingValue`, not loosened the rule.
- **Verification:** `pytest tests/test_itr2_input_validation.py -v` — 26 passed.
  `pytest tests/test_itr2_validators.py tests/test_itr2_integration.py
  tests/test_itr2_itd_builder.py tests/test_itr2_production_path.py -q` — 40 passed (no
  conflicts with the new rule IDs). Full suite (`pytest tests/ -q`, same deselect list as
  Phase 4's note plus the pre-existing `test_26as_batch.py::test_single_file` fixture-config
  error) — **1354 passed, 0 failed.** `npx tsc -b` — 0 errors. `npx vitest run` — 167 passed.
  `npm run build` — clean (5A touched no frontend files; run for full-verification discipline).

**5B Delivered 2026-09-02.**

- **`app/engine/validators/itr2/input_rules.py`** — added 2 new Schedule CG rules
  (`ITR2-IN-CG-007`/`008`), 1 Schedule 112A rule (`ITR2-IN-112A-008`), and 1 Schedule VDA rule
  (`ITR2-IN-VDA-004`), plus a `_financial_year_end(inp)` helper (31 March of the AY's
  financial year, reusing the existing `_current_assessment_year` derivation). A much smaller
  addition than 5A's 13 rules — most of the CBDT catalog's ~150 Schedule CG rules turned out
  to be either (a) column-arithmetic identities against the official form's raw sub-schedule
  layout that `build_itr2_json` already guarantees by constructing the JSON programmatically
  rather than summing user-edited dropdowns, or (b) already forced by *existing* rules once
  actually traced through:
  - `ITR2-IN-CG-007` (CBDT rule 750): a `LAND_BUILDING` transaction's `date_of_transfer` cannot
    fall after 31 March of the financial year.
  - `ITR2-IN-CG-008` (CBDT rule 591): `deduction_us54ec` (§54EC bonds) is capped at ₹50,00,000
    — the only one of the four capital-gain exemption sections (54/54B/54EC/54F) with a flat
    statutory rupee cap in the catalog; the other three are reinvestment-conditioned with no
    flat cap, so no equivalent rule was added for them.
  - `ITR2-IN-112A-008` (CBDT rules 173/174): a scrip acquired on/after 1 February 2018
    (`is_before_31jan2018=False`) cannot carry a 31-Jan-2018 FMV — grandfathering doesn't apply
    to it.
  - `ITR2-IN-VDA-004` (CBDT rule 748): a VDA transaction's acquisition or transfer date cannot
    fall after 31 March of the financial year.
  - **Two planned rules were traced to existing coverage and dropped before being written**:
    the CBDT catalog's "zero consideration ⇒ zero transfer expenses" pattern (rules 101–108)
    is unreachable for `CGTransaction` — `ITR2-IN-CG-003` already forces `full_consideration >
    0` unconditionally for every transaction — and for `CG112AScrip` the same zero-consideration
    state is already caught by the existing `ITR2-IN-112A-002`–`004` chain (positive quantity,
    positive unit price, and their product reconciling to `total_sale_value`) whenever those
    two factors are positive, and by `112A-002`/`003` directly when they aren't. Adding either
    would have been dead-or-redundant code, so neither was written.
  - **Not implemented, and explicitly out of scope for 5B**: CBDT rules 175/176 (10% stamp-duty
    safe-harbor threshold for immovable-property full value of consideration) and 184/185
    (24-month holding-period long/short classification) are calculator *formula* behavior, not
    input-shape validation — fixing either belongs to `app/engine/calculators/itr2.py`, not a
    Category A pre-compute gate, and auditing the calculator's own correctness is outside this
    validator-completion phase's mandate. CBDT rule 186 (year-of-improvement mandatory when
    cost-of-improvement is declared) is not representable — `CGTransaction` has no
    year-of-improvement field. CBDT rule 590 (mandatory CGAS/investment detail when an
    exemption amount is claimed) targets `CapitalGainExemptionClaim`, a second, parallel
    per-claim schema on `CGTransaction.exemptions` that is not confirmed to be populated by
    `draft_to_itr2_input.py` (the mapper only writes the flat `deduction_us54*` scalars) — not
    validated against an unconfirmed-live path. The Schedule 115AD(1)(b)(iii) proviso block
    (rules 91–97, 142, 174, 177, 187 — the FII/FPI non-resident LTCG equivalent of Schedule
    112A) is not representable at all — `ITR2Input` has no separate 115AD scrip list.
- **`tests/test_itr2_input_validation.py`** — added 8 tests (one known-good + one known-bad per
  rule, 4 rules × 2) under a new "Phase 5B" section.
- **Verification:** `pytest tests/test_itr2_input_validation.py -v` — 34 passed.
  `pytest tests/test_draft_to_itr2_input.py tests/test_filing_gateway_v2_itr2.py
  tests/test_itr2_validators.py tests/test_itr2_integration.py tests/test_itr2_itd_builder.py
  tests/test_itr2_production_path.py -q` — 81 passed, no regressions from the new CG/112A/VDA
  rules against existing fixtures. Full suite (`pytest tests/ -q`, same deselect list as 5A's
  note) — **1365 passed, 0 failed.** `npx tsc -b` — 0 errors. `npx vitest run` — 167 passed.
  `npm run build` — clean (5B touched no frontend files; run for full-verification discipline).

**5C Delivered 2026-09-02.**

- **`app/engine/validators/itr2/input_rules.py`** — added 3 Chapter VI-A rules
  (`ITR2-IN-VIA-001`/`002`/`003`), by far the smallest of the four rule sets shipped so far
  despite Chapter VI-A being the *largest* CBDT rule cluster (~150 rules). Before writing
  anything, read every one of the 24 modules in `app/engine/schedules/deductions/` in full
  (`section_80c.py`, `section_80d.py`, `section_80dd.py`, `section_80ddb.py`, `section_80e.py`,
  `section_80ee.py`/`80eea.py`/`80eeb.py`, `section_80g.py`, `section_80gg.py`,
  `section_80gga.py`/`80ggc.py`, `section_80tta.py`/`80ttb.py`, `section_80u.py`,
  `section_80ccd1b.py`/`80ccd2.py`/`80cch.py`) — every single one already self-caps to its
  statutory limit via `min()` and independently zeroes under the new regime by checking
  `regime == TaxRegime.NEW` (except 80CCD(2) and 80CCH, correctly, since both remain claimable
  under the new regime per actual law) — even section_80gg.py's HRA/80GG mutual-exclusivity
  cross-check (CBDT rule 52) is already engine-enforced. This makes essentially the entire
  literal-cap and per-section-new-regime portion of the catalog (CBDT rules 277–365, 611–697,
  and more) exactly what 5A found for Schedule S: dead code if re-implemented as validators.
  What none of the 24 modules take as a parameter, at all, is assessee status or residential
  status — `compute_all()`'s signature is `(ded, gti, age_bracket, regime, os_input, ...)`, no
  HUF/non-resident gate anywhere — so a HUF or non-resident assessee claiming an
  individual-only or resident-only deduction would currently compute a materially wrong
  (too-low) tax liability with no error. That gap is where all three shipped rules are aimed:
  - `ITR2-IN-VIA-001` (consolidates CBDT rule 342 + the per-section rules it summarizes: 304,
    315, 323, 350, etc.): claiming any of 80C/80CCC/80CCD(1)/80CCD(1B)/80D/80DD/80DDB/80E/
    80EE/80EEA/80EEB/80G/80GG/80GGA/80GGC/80TTA/80TTB/80U under the new regime is rejected
    pre-compute — same "surface the silent drop, don't let it compute a correct-but-unwanted
    result" rationale as `SAL-006`/`007`/`008`. One consolidated rule rather than ~17 near-
    duplicates, listing exactly which claimed sections triggered it. 80CCD(2)/80CCH
    deliberately excluded — they're legitimately claimable under the new regime.
  - `ITR2-IN-VIA-002` (CBDT rules 317–321, 324–326): a HUF assessee (`filing_profile.
    assessee_status == AssesseeStatus.HUF`) cannot claim 80CCD(1)/80CCD(1B)/80CCD(2)/80E/
    80EE/80EEA/80EEB/80U. Guarded on `filing_profile is not None`, since it's a
    gateway-attached field not populated during bare `compute_canonical_itr2`.
  - `ITR2-IN-VIA-003` (CBDT rules 327–329): a non-resident (`inp.residential_status ==
    ResidentialStatus.NON_RESIDENT`, always populated — defaults to `RESIDENT`, unlike
    `filing_profile`) cannot claim 80DD/80DDB/80U.
  - **Not implemented**: 80TTA's senior-citizen exclusion and 80TTB's non-senior exclusion
    (CBDT rules 322/323) — both already engine-enforced via the `age_bracket`-derived
    `is_senior` flag `compute_all()` already threads into `section_80tta.py`/`section_80ttb.py`.
    80QQB/80RRB (CBDT rules 333–336, 340–341, 630–635, 691–692) are not representable at all —
    `Chapter6ADeductions` has no field for either section.
- **`tests/test_itr2_input_validation.py`** — added 6 tests (one known-good + one known-bad per
  rule, 3 rules × 2) under a new "Phase 5C" section, including a `_filing_profile()` helper for
  constructing a minimal valid `ITR2FilingProfile` (needed only for `VIA-002`'s HUF check).
- **Verification:** `pytest tests/test_itr2_input_validation.py -v` — 40 passed.
  `pytest tests/test_draft_to_itr2_input.py tests/test_filing_gateway_v2_itr2.py
  tests/test_itr2_validators.py tests/test_itr2_integration.py tests/test_itr2_itd_builder.py
  tests/test_itr2_production_path.py -q` — 89 passed, no regressions. Full suite (`pytest
  tests/ -q`, same deselect list as 5A/5B's notes) — **1371 passed, 0 failed.** `npx tsc -b` —
  0 errors. `npx vitest run` — 167 passed. `npm run build` — clean (5C touched no frontend
  files; run for full-verification discipline).

**5D Delivered 2026-09-02.**

- **`app/engine/validators/itr2/input_rules.py`** — added 1 Schedule SI rule
  (`ITR2-IN-SI-001`). The smallest of the five rule sets shipped in Phase 5 — Schedule OS,
  CYLA/BFLA/CFL, and most of Schedule SI turned out to have essentially nothing left to add:
  - **Schedule OS is almost entirely non-representable, not just already-guaranteed.**
    `OtherSourcesIncome` (shared with ITR-1) is a flat gross-income-bucket model with no
    expense/deduction sub-schedule, no racehorse-income field, no dividend-interest-expenditure
    field. ITR-1's own three Schedule-OS rules (`R050`/`R052`/`R145`) all key off
    ITR1Input-only fields — `other_sources_dropdowns`, `other_sources_total`,
    `dividend_quarterly_breakdown` — none of which exist on `ITR2Input`, so there was nothing
    to adapt from ITR-1 here, unlike Chapter VI-A's reusable pattern in 5C. The one cap that
    *is* representable (57(iia) family-pension deduction) is engine-computed in
    `app/engine/schedules/other_sources.py` exactly like 5A's salary exemptions — `min(fp/3,
    cap)`, only applied `if fp > 0` — so it needs no separate validator.
  - **`ITR2Input.cf_losses` is a vestigial input field**: grepping
    `app/engine/calculators/itr2.py` confirms it is never read — the calculator's own "cfl"
    schedule is derived entirely from `bf_losses` and current-year losses, not from
    `inp.cf_losses`. A validator against an input the calculator never consumes would check
    something with no effect on the filed return, so none was written. The remaining CYLA/
    BFLA/CFL catalog rules (234–274) are column-arithmetic identities against
    `build_itr2_json`'s own output construction — build-time-guaranteed, same as 5B's Schedule
    CG finding.
  - **`ITR2-IN-SI-001` (Section 58(4), no deduction against 115BBJ online-game winnings)**:
    `ScheduleSIEntry` itself already carries a `reject_disallowed_deductions` model validator
    blocking a nonzero `deductions` claim for sections `115BB`/`115BBE` — discovered mid-test
    (the known-bad case for 115BB wouldn't even construct, same dead-code-before-shipping
    pattern as 5A's dropped HP rule), so that half of the originally planned rule was dropped.
    `115BBJ` (winnings from online games — the same Section 58(4) "no deduction" rule applies)
    is the one section the schema does *not* already cover, and is genuinely representable, so
    the rule was narrowed to just that. `.deductions` and `.tax_rate_pct` are both ignored by
    every `compute_*` function in `app/engine/schedules/special_rates.py` (hardcoded rate
    constants; only `.gross_income` is read) — but unlike the caps found elsewhere in 5A–5C,
    that isn't a reason to skip the rule: the claim is legally invalid under Section 58(4), not
    merely uncomputed, so it's worth rejecting outright rather than letting it silently vanish.
- **`tests/test_itr2_input_validation.py`** — added 3 tests under a new "Phase 5D" section
  (one for `115BBJ` with a deduction failing, one without passing, one confirming an
  unrelated section — `115BBF`, which does permit deductions — is unaffected).
- **Verification:** `pytest tests/test_itr2_input_validation.py -v` — 43 passed.
  `pytest tests/test_draft_to_itr2_input.py tests/test_filing_gateway_v2_itr2.py
  tests/test_itr2_validators.py tests/test_itr2_integration.py tests/test_itr2_itd_builder.py
  tests/test_itr2_production_path.py -q` — 95 passed, no regressions. Full suite (`pytest
  tests/ -q`, same deselect list as prior sub-phases' notes) — **1374 passed, 0 failed.**
  `npx tsc -b` — 0 errors. `npx vitest run` — 167 passed. `npm run build` — clean (5D touched
  no frontend files; run for full-verification discipline).

### Phase 5E — Remaining ITR-2 validation rules (✅ Delivered 2026-09-02)

Phase 5E is the remaining part of the ITR-2 validator suite and must be completed before Phase 5F or any frontend/direct-submit work begins. It covers the rules that were intentionally left after Phases 5A–5D and must use the same disciplined rule-tracing method: implement only checks that are genuinely representable, user-suppliable, and not already guaranteed elsewhere in the pipeline.

**Scope:**

- AMT/AMTC consistency;
- Schedule EI required-detail relationships and total reconciliation;
- PTI detail/count reconciliation;
- FSI/TR/FA cross-schedule consistency;
- Schedule 5A consistency;
- Schedule AL consistency;
- TDS/TCS/advance-tax/self-assessment and IT reconciliation;
- Part B-TI/TTI final reconciliation;
- the remaining Category B and Category D rules.

**Implementation method:**

1. Read the official ITR-2 validation rule and identify its exact CBDT category.
2. Trace every referenced field through `ReturnDraft`, `draft_to_itr2_input.py`, the relevant schedule/calculator, and `build_itr2_json`.
3. Write a known-bad construction test first. If Pydantic rejects the state, classify the rule as `STRUCTURALLY_GUARANTEED` rather than adding dead validator code.
4. If the calculator already caps, derives, or rejects the state, classify it as `CALCULATOR_ENFORCED`.
5. If programmatic JSON construction guarantees the identity, classify it as `BUILDER_GUARANTEED`.
6. If a required field is absent from the canonical models, classify it as `NOT_REPRESENTABLE`; do not fabricate a proxy field.
7. If the rule requires portal, database, or external data unavailable to the local pipeline, classify it as `EXTERNAL_CHECK`.
8. Implement only the remaining applicable rules as `ValidationRule` entries with Category A/B/D severity and actionable messages.

For every omitted official rule, record:

```text
Official rule:
Disposition: IMPLEMENTED | STRUCTURALLY_GUARANTEED | CALCULATOR_ENFORCED |
             BUILDER_GUARANTEED | NOT_REPRESENTABLE | EXTERNAL_CHECK | PENDING
Reason:
Test/evidence:
```

Do not mechanically add validators for fields the calculator does not consume, duplicated arithmetic that the builder already derives, or formula behavior that belongs in the calculator rather than an input gate. Phase 5E must not claim full official-rule coverage merely because the PDF contains a fixed number of rules.

**Files:**

- `app/engine/validators/itr2/input_rules.py` — applicable Category A input rules;
- `app/engine/validators/itr2/calc_rules.py` — applicable post-calculation reconciliation rules;
- `tests/test_itr2_input_validation.py` — known-good and known-bad input cases;
- `tests/test_itr2_calc_validation.py` — calculation and cross-schedule cases;
- the Phase 5 validation inventory/documentation, recording every omitted rule's disposition.

**Exit criteria:**

- Every considered 5E rule has a recorded disposition and evidence.
- Each implemented rule has a passing known-good case and a failing known-bad case.
- `run_input_validation` and `run_calc_validation` block invalid returns with specific messages.
- A known-good ITR-2 fixture reaches `can_upload=True` with no Category-A blocking errors.
- ITR-2 mapper, calculator, builder, official-schema, and production-path tests remain green.
- ITR-1 and ITR-4 regression suites remain green.
- Frontend type-check, Vitest, and production build remain green.

**Tests:** extend `tests/test_itr2_input_validation.py` and `tests/test_itr2_calc_validation.py`; run the ITR-2 integration, builder, production-path, ITR-1/ITR-4 regression, frontend type/build, and applicable full suite before marking 5E delivered.

**Delivered 2026-09-02.** Disposition record for every 5E-scope area considered, per the
method above:

**AMT/AMTC:**
```text
Official rule: AMT tax = adjusted total income × AMT rate (rule 428); AMT credit utilised ≤
               brought forward (rules 426-429)
Disposition: IMPLEMENTED (pre-existing, ITR2-IN-AMT-001/002 — predate Phase 5, not newly
             added this phase)
Reason: These validate AMTInput.amt_tax/.adjusted_total_income/.amt_credit_* directly.
Test/evidence: tests/test_itr2_validators.py (pre-existing)
```
```text
Official rule: (discovery, not a numbered catalog rule) — do AMT-001/002 validate fields the
               calculator actually uses?
Disposition: PENDING — documented, not fixed this phase
Reason: Grepping app/engine/calculators/itr2.py's `amt_in.` usage confirms ONLY
        `.deduction_10aa`/`.deduction_80ia_to_80rrb_except_80p`/
        `.deduction_35ad_net_depreciation` are read; `.amt_tax`, `.adjusted_total_income`,
        `.amt_rate_pct`, `.amt_credit_brought_forward`, `.amt_credit_utilised` are never
        consumed, and `_map_amt_input` in draft_to_itr2_input.py never sets them (all sit at
        Pydantic zero-defaults for every real draft). AMT-001/002 are therefore harmless in
        production today (0 == 0×rate) but exercise nothing real. The genuinely computed AMT
        figure is `result.amt_tax` (from `app/engine/schedules/amt.py::compute`, which
        correctly applies the ₹20L threshold — verified by reading the module), already
        covered by ITR2-CALC-009 (inclusion in total tax) and the nonnegative sweep in
        ITR2-CALC-021. Removing/rewiring AMT-001/002 was judged out of this phase's scope
        (a Phase 5-predating rule, not part of 5E's own additions) and is left for a future
        pass rather than risk changing pre-existing, already-tested behavior in this commit.
Test/evidence: grep evidence in app/engine/validators/itr2/input_rules.py's inline comment
               above the AMT block; no test added (nothing to assert beyond documentation)
```

**Schedule EI (exempt income):**
```text
Official rule: ~47 near-duplicate rules (699-745) — "In Schedule EI, '10(x)...' drop-down
               cannot be selected more than once under Other Exempt Income"
Disposition: STRUCTURALLY_GUARANTEED
Reason: `ExemptIncome` has one named field per exemption category (ppf_interest,
        sukanya_samriddhi_interest, tax_free_bond_interest, nre_interest,
        share_of_profit_from_firm, other_exempt) rather than a repeatable
        dropdown-plus-amount row list — duplicate selection of the same category is not a
        state the schema can represent at all, so there is nothing to reject.
Test/evidence: schema inspection — no repeatable-row field exists to duplicate
```
```text
Official rule: 436 — Net agricultural income = gross receipts − expenditure − unabsorbed loss
Disposition: CALCULATOR_ENFORCED
Reason: `result.net_agricultural_income = ag_result.total_net_agricultural_income`
        (app/engine/calculators/itr2.py:615) — computed entirely by the agricultural-income
        schedule module from `AgriculturalIncome`'s three raw fields; no user-suppliable
        "net" field exists to independently violate the formula.
Test/evidence: grep of app/engine/calculators/itr2.py confirms the assignment
```
```text
Official rule: 433-435 — EI sub-totals (other exempt income total, DTAA-exempt total, overall
               total) equal the sum of their components
Disposition: BUILDER_GUARANTEED
Reason: `build_itr2_json` constructs Schedule EI's totals programmatically from the typed
        `ExemptIncome` fields; there is no raw editable total field for a user to enter
        inconsistently.
Test/evidence: itd/itr2.py Schedule-EI construction (existing, not modified this phase)
```

**PTI (pass-through income):**
```text
Official rule: 437-441 (Col 9 = Col7−Col8; iia = ai+aii; iib = bi+bii; iii = a+b; iv = a+b+c)
Disposition: NOT_REPRESENTABLE
Reason: The official Schedule PTI captures a per-entity sub-breakdown (separate STCG-15%/
        STCG-30%/other columns per pass-through source) that `PTIEntry` does not model —
        this codebase's PTIEntry is coarser (one `income_head` + one `income_amount` per
        entity), so the columns these rules reconcile do not exist to check.
Test/evidence: schema inspection — app/schemas/itr2.py PTIEntry field list
```

**FSI/TR (foreign tax relief):**
```text
Official rule: 442 — Tax relief available should be lower of tax paid outside India or tax
               payable on such income in India
Disposition: IMPLEMENTED (pre-existing, ITR2-IN-TR1-001 — predates Phase 5)
Reason: `if tr.relief_claimed > min(tr.tax_paid_outside_india, tr.indian_tax_payable): error`
        is exactly this rule, already shipped in an earlier phase.
Test/evidence: tests/test_itr2_validators.py (pre-existing)
```
```text
Official rule: 443/453 — Schedule FSI/TR not applicable if residential status is non-resident
Disposition: PENDING — deliberately not touched this phase
Reason: `ITR2Input.validate_cross_schedule_contract` already hard-blocks Schedule FA for a
        non-resident, but the existing `ITR2-IN-FSI-002` rule takes the opposite stance for
        Schedule FSI — it's a Category-D *warning* ("verify Indian taxability") that
        deliberately *allows* FSI entries for a non-resident rather than rejecting them.
        Reclassifying 443 as a Category-A block would change already-shipped Phase 3/4-era
        behavior; doing that inside a phase whose own stated method is "implement only new,
        genuinely representable gaps" risks an unreviewed behavior change smuggled into a
        rule-completion phase. Left for a dedicated future review rather than resolved by
        guessing which of the two existing signals is correct.
Test/evidence: ITR2-IN-FSI-002 in input_rules.py; validate_cross_schedule_contract in
               app/schemas/itr2.py
```

**FA (foreign assets):**
```text
Official rule: 746 — Schedule FA must be filled if Part B-TTI's foreign-asset flag is "Yes"
Disposition: NOT_REPRESENTABLE
Reason: `ITR2FilingProfile` has no standalone "do you hold foreign assets" boolean to cross-
        check against `foreign_assets` — the only signal is the list's own presence, which is
        self-consistent by construction (a non-empty list always produces Schedule FA rows;
        an empty one never does). There is nothing separate to reconcile against.
Test/evidence: schema inspection — ITR2FilingProfile field list (Phase 4 delivered note)
```

**Schedule 5A (Portuguese Civil Code):**
```text
Official rule: 449 — PAN of spouse mandatory when governed by Portuguese Civil Code
Disposition: STRUCTURALLY_GUARANTEED
Reason: `Schedule5AInput.spouse_pan` has no default (Pydantic-required) — constructing a
        `Schedule5AInput` at all already forces spouse_pan to be supplied.
Test/evidence: schema inspection — app/schemas/itr2.py Schedule5AInput
```
```text
Official rule: 450 — Sl.No.4 total = sum of Sl.No.(1+2+3) for all columns
Disposition: BUILDER_GUARANTEED
Reason: `Schedule5AInput` has no separate "total" field — `build_itr2_json` derives the total
        from hp/cg/os_amount_apportioned programmatically.
Test/evidence: schema inspection — no total field exists on the input model to diverge

Official rule: 657/658 (PTI Sl.No. iii/iv sums — filed here for completeness, functionally
               part of the PTI NOT_REPRESENTABLE finding above)
Disposition: NOT_REPRESENTABLE (see PTI section)
```

**Schedule AL (assets and liabilities):**
```text
Official rule: 456 — Schedule AL mandatory when total income exceeds ₹1 crore
Disposition: IMPLEMENTED — new ITR2-CALC-027 in calc_rules.py
Reason: "Total income" is `result.taxable_income`, a calculator output — not present on the
        pre-compute ITR2Input — so this belongs in calc_rules.py, not input_rules.py, unlike
        every other rule this phase.
Test/evidence: tests/test_itr2_calc_validation.py (new file) — 3 tests
```

**TDS/TCS/advance-tax/self-assessment/IT reconciliation:**
```text
Official rule: 466/467 — TDS claimed cannot exceed TDS deducted plus TDS brought-forward
               (not deducted alone)
Disposition: IMPLEMENTED, with a real pre-existing bug fixed at two different layers
Reason: The pre-existing ITR2-IN-TDS-001 (TDS2) checked `tds_claimed_this_year >
        tds_deducted`, ignoring the model's own `brought_forward_tds` field entirely — a live
        false-rejection risk, since `draft_to_itr1_input._map_tds` maps a real, user-editable
        draft field (`TdsCredit.broughtFwdTDSAmt`) into it. Fixed to check against
        `tds_deducted + brought_forward_tds`. The identical bug existed one layer deeper for
        TDS3: `TDS3Entry`'s own `@model_validator` in app/schemas/itr1.py (shared with ITR-1)
        checked `tds_claimed > tds_deducted` with the same omission — fixed at the schema
        level, which is the correct location for a check on the type itself, and is strictly
        permissive (loosening a `>` bound can only newly *allow* previously-rejected valid
        states, never reject a previously-valid one, so it cannot regress ITR-1). A separate
        ITR2-IN-TDS-002 was written first, then confirmed unreachable dead code once the
        schema fix landed (a violating TDS3Entry can no longer be constructed at all) and
        removed before shipping — same dead-code-before-shipping pattern as three earlier
        findings this phase 5.
Test/evidence: tests/test_itr2_input_validation.py (TDS_001 tests, tds3entry_schema tests);
               full ITR-1 regression (tests/test_itr1_calculator.py,
               tests/test_itr1_input_validation.py, tests/test_itr1_itd_builder.py,
               tests/test_draft_to_itr1_input.py, tests/test_itr1_filing_gateway_profile.py)
               and tests/test_itr4_calculator.py all still green after the shared-schema fix
```
```text
Official rule: 458 — TCS "Amount claimed this year" cannot exceed "Tax collected"
Disposition: IMPLEMENTED (pre-existing, ITR2-IN-TCS-001 — predates Phase 5)
Reason: TCSEntry has no brought-forward field (unlike TDS2/TDS3), so the existing
        `tcs_credit_claimed > tcs_collected` check was already correct as written — no fix
        needed.
Test/evidence: schema inspection — app/schemas/itr1.py TCSEntry field list
```
```text
Official rule: 520/521 — Part B-TTI self-assessment tax / advance tax must equal the sum of
               Schedule IT payments whose deposit date falls after/within the FY
Disposition: CALCULATOR_ENFORCED
Reason: `TaxPaymentDetail` rows are classified into advance-tax vs self-assessment-tax buckets
        by the mapper/calculator from each row's own date, not from a user-editable bucket
        total — there is no separate raw "self-assessment tax total" input field to diverge
        from the date-based classification.
Test/evidence: schema inspection — no independent total field on TaxPaymentDetail/ITR2Input
```

**Part B-TI/TTI final reconciliation:**
```text
Official rule: 486-541 (~35 rules) — GTI/deductions/taxable-income/tax-payable/refund
               reconciliation across Part B-TI and B-TTI
Disposition: Mostly CALCULATOR_ENFORCED / BUILDER_GUARANTEED, already covered by the general
             reconciliation sweep ITR2-CALC-001 through 026 shipped in Phases 4-5D (gross
             total income, deductions, taxable income, tax before/after rebate, surcharge,
             cess, interest, TDS/TCS/advance/self-assessment totals, balance payable/refund
             all already cross-checked against their component result fields).
Reason: Part B-TI/TTI is exactly what `build_itr2_json` renders from `ITR2Result` — the
        reconciliation catalog for it is a re-statement, field by field, of relationships the
        existing calc_rules.py suite already checks generically off the result object rather
        than the official form's exact field-naming.
Test/evidence: app/engine/validators/itr2/calc_rules.py (existing, Phases 4-5D)
```

**Category B/D (26 rules):**
```text
Official rule: 5 — Form 10E required to claim relief u/s 89
Disposition: IMPLEMENTED — new ITR2-IN-FORM-001 (Category D reminder)
Reason: `relief_89` is genuinely calculator-consumed (r.relief_89 = input_data.relief_89,
        confirmed by grep), so this is a real reminder on a live field, not noise.
Test/evidence: tests/test_itr2_input_validation.py — 2 tests
```
```text
Official rule: 6 — Form 10BA required to claim deduction u/s 80GG
Disposition: IMPLEMENTED — new ITR2-IN-FORM-002 (Category D reminder)
Reason: Same rationale — `amount_80gg` is a real, calculator-consumed field
        (app/engine/schedules/deductions/section_80gg.py).
Test/evidence: tests/test_itr2_input_validation.py — 2 tests
```
```text
Official rule: 9/10 — TDS/TCS credited to another person allowed only if that person declares
               it in their own return
Disposition: EXTERNAL_CHECK
Reason: Verifying another taxpayer's return content is outside this pipeline's data — no
        local field can confirm or deny it.
```
```text
Official rule: remaining 22 of 26 (Form 29C/3CFA/10EE/10F reminders, DTAA-for-residents
               warnings, TDS-vs-income-not-offered checks, LEI-number-for-large-refund,
               Aadhaar-PAN linkage)
Disposition: PENDING — not implemented this phase
Reason: Each would need either data this pipeline doesn't independently hold (Aadhaar-PAN
        linkage status, LEI registry), or overlaps functionality already covered by an
        implemented Category A rule (TDS-vs-income-not-offered is adjacent to the existing
        FSI/TR reconciliation), or was judged lower-value relative to the two reminders
        shipped. Left for a future pass rather than added speculatively.
```

**Exit-criteria check:**
- Every 5E-scope area has a recorded disposition above. ✅
- Each implemented rule (AMT — pre-existing; CALC-027; TDS-001 fix; FORM-001/002) has a
  passing known-good and known-bad case. ✅ (`tests/test_itr2_input_validation.py`,
  `tests/test_itr2_calc_validation.py`)
- `run_input_validation`/`run_calc_validation` block invalid returns with specific messages —
  verified via the new tests plus the existing
  `test_filing_gateway_v2_itr2.py::test_generate_cbdt_json_itr2_passes_validators_and_schema`
  (a known-good ITR-2 fixture still reaches `can_upload=True`). ✅
- ITR-2 mapper/calculator/builder/production-path tests green:
  `pytest tests/test_draft_to_itr2_input.py tests/test_filing_gateway_v2_itr2.py
  tests/test_itr2_validators.py tests/test_itr2_integration.py tests/test_itr2_itd_builder.py
  tests/test_itr2_production_path.py tests/test_itr2_input_validation.py
  tests/test_itr2_calc_validation.py -q` — **110 passed.**
- ITR-1/ITR-4 regression green (extra scrutiny — `app/schemas/itr1.py` is shared):
  `pytest tests/test_itr1_calculator.py tests/test_itr1_input_validation.py
  tests/test_itr1_itd_builder.py tests/test_draft_to_itr1_input.py
  tests/test_itr1_filing_gateway_profile.py tests/test_itr4_calculator.py -q` —
  **247 passed.**
- Full suite (`pytest tests/ -q`, same deselect list as prior sub-phases' notes) —
  **1387 passed, 3 failed.** The 3 failures (`test_tax_v2_compute.py::
  test_compute_v2_returns_compatible_headline_keys`,
  `::test_compute_v2_surfaces_per_row_capital_gains_for_simplified_112a`,
  `::test_compute_v2_allows_confirmed_reconciliation_discrepancies`) are **confirmed
  pre-existing** via `git stash` against the pre-Phase-5E commit — identical failures with
  none of this phase's changes applied. Same "date-bomb" family as the Phase 4/5A finding
  (ITR-1 fixtures relying on default/relative dates now failing real portal-address/due-date
  gates as the system clock has advanced) — unrelated to this phase, not fixed here.
- Frontend green: `npx tsc -b` — 0 errors. `npx vitest run` — 169 passed (22 files; +1 file/+2
  tests vs the prior sub-phase's baseline, confirmed via `git status` to be pre-existing
  drift unrelated to this phase — no frontend files were touched). `npm run build` — clean.

**Note on scope vs. the original "5A-5E" split:** this document's Progress-at-a-glance table
above still lists 5A-5D as separate delivered sub-phases from an earlier, less formal
narrative-style tracking approach (before this detailed 5E/5F/5G specification existed in this
file). 5E as delivered here supersedes that narrative style with the disposition-record method
now established as the standard going forward — Phase 8 (ITR-3, reusing these same schedule
types) should use this same method and record format from the start rather than the looser
5A-5D narrative.

### Phase 5F — Shared canonical personal-profile foundation

**Mandatory architecture gate before frontend wiring, direct submission, or ITR-3 implementation.**

Create one shared internal representation for taxpayer-level information rather than allowing form gateways or JSON builders to map the same facts independently. The profile owns identity, contact and addresses, filing status, eligibility declarations, verification, representative details, bank accounts, and optional tax-return-preparer details.

Normalize values once, validate conditional relationships once, construct bank/verification/TRP rows once, and expose calculation readiness separately from filing readiness. A deterministic source hash is required so profile changes are observable and prepared data cannot be silently reused after the draft changes.

**Exit criteria:** all four forms consume the same complete personal-profile contract; JSON builders do not independently map bank accounts, verification, representative details, or TRP; profile changes alter the source hash; warnings, calculation-blocking errors, and filing-blocking errors are separate; ITR-1 and ITR-4 remain green.

### Phase 5G — Migrate ITR-2 to complete pre-calculation preparation

Replace the current ITR-2 split flow:

```text
current: draft_to_itr2_input → compute_itr2 → late filing/detail enrichment → JSON
required: ReturnDraft → prepare_itr2 → complete ITR2Input → validate → compute → JSON
```

Introduce a preparer equivalent to the completed ITR-1/ITR-4 lifecycle:

```python
def prepare_itr2(draft: ReturnDraft) -> PreparedReturn[ITR2Input, ITR2Result]:
    """Prepare and calculate one complete ITR-2 return."""
```

Preparation order: normalize the draft and check reconciliation; build the shared personal profile; map all ITR-2 income, loss, deduction, tax, and filing-detail schedules; construct one complete `ITR2Input`; run input validation; calculate; run calculation validation; compute filing readiness; return the prepared input, result, breakdown, summary, readiness, and source hash.

The existing `_itr2_filing_profile()`, `_itr2_property_filing_details()`, `_itr2_employer_filing_details()`, and `_itr2_tds3_filing_details()` functions must move into or delegate to this preparer. After migration, `_generate_cbdt_json_itr2()` passes the already-prepared `pipeline.typed_input` to `build_itr2_json()` and never performs late `model_copy(update={...})` enrichment or reads filing data from `ReturnDraft` again.

**Production-status rule:** ITR-2 is not filing-ready merely because Phase 5E validators pass. Phases 5F and 5G must pass before frontend or Direct Submit is enabled.


### Phase 6 ? Frontend: wire ITR-2 onto the canonical `ReturnDraft`

Starts only after Phases 5E, 5F, and 5G pass. The editor persists one `ReturnDraft`, and the generic v2 gateway consumes the same complete prepared input for computation and JSON. Personal/profile/verification/refund/TRP fields remain personal-profile concerns; property/employer/TDS3 details remain schedule concerns.

`itrV2.ts`/`canonicalRepository.ts` already handle generic `ReturnDraft` operations. Form-aware UI work includes `PersonalInfoTab`, `CapitalGainsTab`/`CapitalGainsEntryManager`, and capture tabs for FSI/TR/FA/SPI/PTI/AMT/AL/5A/ESOP. The schedule registry must not mark fields as supported until the corresponding mapper, preparer, validator, and JSON path are complete.

**Scope note:** polished capture UI for missing schedules may require sub-phases after the canonical data contract is locked; no UI phase may introduce a second filing/computation representation.

### Phase 7 ? ITR-2 v2 endpoints + Direct Submit extension

- Confirm `client_itr_v2.py` routes consume the complete prepared pipeline without ITR-2-specific enrichment.
- Extend `app/routers/filing.py::_normalize_form` to ITR-2 only after Phases 5E?5G and frontend tests pass.
- Remove the frontend ITR-2 Direct Submit gate only after backend and UAT integration tests pass.

**Tests:** integration test a full ITR-2 draft through generation, UAT submission, polling, and acknowledgement.

### Phase 8 ? ITR-3: build on the shared complete-preparation contract

ITR-3 must not copy the current ITR-2 split mapper/gateway pattern. It starts only after Phase 5F establishes the shared personal profile and Phase 5G proves the complete-preparer lifecycle.

```text
ReturnDraft ? prepare_personal_profile()
  ? ITR-3 schedule preparer (PGBP, balance sheet, audit, CG, FSI/TR/FA, etc.)
  ? complete ITR3Input
  ? input validation ? compute_itr3
  ? calculation validation ? PreparedReturn
  ? build_itr3_json(prepared.typed_input)
```

Reuse the shared personal profile and semantically identical schedule helpers, but do not reuse whole ITR-2 input models where ITR-3 semantics differ. ITR-3-specific preparation includes PGBP, balance sheet, audit information, depreciation, disallowances, speculative/specified business, partners, and unabsorbed depreciation.

The ITR-3 validator work requires a separate rule inventory. Classify every official rule as `IMPLEMENTED`, `CALCULATOR_ENFORCED`, `SCHEMA_ENFORCED`, `BUILDER_GUARANTEED`, `NOT_REPRESENTABLE`, `EXTERNAL`, or `PENDING`; do not infer production readiness from PDF rule count alone.

**Sub-phases:** 8.1 extend draft fields, 8.2 close schema imports, 8.3 build the complete canonical mapper/preparer, 8.4 wire gateway dispatch, 8.5 build the classified validator suite, 8.6 wire the frontend, and 8.7 extend endpoints/Direct Submit. Every sub-phase must preserve the same single prepared input for computation and JSON.

### Phase 9 — Delete the now-dead ITR-2 legacy path

Once Phases 5E–5G, Phase 6, and Phase 7 are tested and the frontend no longer calls the flat-payload path:
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
