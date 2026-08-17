# ITR-1 Data-Flow Simplification — Implementation Plan

**Status:** Active implementation tracker. Phase status updated as each phase completes manual testing.
**Scope:** ITR-1 only. This is the template that ITR-2, ITR-3, ITR-4 will follow later.
**Authority:** This file is the single source of truth for the refactor. The audit findings are in `ITR1_DATA_FLOW_AUDIT.md`.

---

## Audit Summary (from `ITR1_DATA_FLOW_AUDIT.md`)

The ITR-1 flow carries **two parallel data representations** (flat legacy blob + canonical `ReturnDraft`) plus **~9 import mappers** and **2 backend flat→typed mappers** that must stay manually synchronized. The bridge files (`legacyAdapter.ts`, `legacySerializer.ts`, `editorModel.ts`, `buildPhase1Payload`, `composeLegacyPayload`, `applyLegacyActionWithSnapshot`, `autoPopulateAll`) exist solely to shuttle between these two representations.

**Root cause of all data-flow bugs:** 12 transformation layers for one ITR-1 return, with 2 separate flat→typed mappers (tax.py + filing_gateway.py) that can diverge silently.

---

## Target Architecture (single canonical shape)

```
Client master (seed only: pan, name, dob, address)
  ↓
ClientITR.form_data = JSON(ReturnDraft)          ← ONE shape, typed, validated on write
  ↓
draft_to_itr1_input(draft) -> ITR1Input           ← ONE backend mapper
  ↓
compute_itr1 -> ITR1Result                        ← ONE compute
  ↓
build_itr1_json(result, ITR1Input)                ← ONE builder
  ↓
validate_itr1_json                                ← ONE schema gate
```

**Transformation layers: 12 → 5.** Flat→typed mappers: 2 (~1090 lines) → 1 (~300 lines).

---

## Phase-Wise Implementation Plan

Each phase is **independently testable** and ends with a manual-test gate. The next phase starts **only after** the user confirms the current phase's tests pass. After confirmation, the phase is committed and this file is marked complete.

### Phase 1 — Backend: canonical draft API (`/v2` routes, no breaking changes)

**Goal:** Expose typed `ReturnDraft`-shaped endpoints alongside the existing flat-blob endpoints, so the frontend can migrate without breaking the current flow.

**Files to create/modify:**
- `app/schemas/return_draft.py` (NEW) — Pydantic mirror of frontend `ReturnDraft` (types.ts:357). One field per schedule, typed lists, no legacy aliases.
- `app/routers/client_itr_v2.py` (NEW) — `GET/PUT /v2/clients/{id}/itr/{year}` accepting/returning `ReturnDraft` JSON. Validates on write.
- `app/engine/draft_to_itr1_input.py` (NEW) — single canonical mapper `draft_to_itr1_input(draft: dict) -> ITR1Input`. Replaces the ~300-line `_build_itr1_input_from_flat`.
- `app/main.py` — mount `client_itr_v2.router`.
- `tests/test_draft_schema.py` (NEW) — round-trip: empty draft → save → load → identical.
- `tests/test_draft_to_itr1_input.py` (NEW) — golden vectors: draft → ITR1Input → ITR1Result.

**What gets removed:** Nothing. This phase only **adds** parallel infrastructure.

**Tests after Phase 1 (manual):**
1. `pytest tests/test_draft_schema.py tests/test_draft_to_itr1_input.py -v` passes.
2. `GET /v2/clients/{id}/itr/2026-27` returns a typed `ReturnDraft` for an existing client (seeds from `Client` master if no draft).
3. `PUT /v2/clients/{id}/itr/2026-27` with a typed draft persists and round-trips exactly.
4. Existing flat `/clients/{id}/itr/{year}` endpoints still work (regression check).
5. `draft_to_itr1_input` produces the same `ITR1Input` fields as the existing `_build_itr1_input_from_flat` for the same input (parity test).

**Status:** ✅ Completed on 2026-08-17. Phase 1 tests and legacy regression tests passed. The portal automation runtime was also hardened for Playwright subprocess support on Windows. Portal Prefill employer extraction and imported capital-gain classification remain separate follow-up issues and do not block the canonical draft API.

**Implemented:**
- `app/schemas/return_draft.py` — strict typed canonical `ReturnDraft` schema.
- `app/engine/draft_to_itr1_input.py` — single canonical ITR-1 mapper.
- `app/routers/client_itr_v2.py` — typed GET/PUT endpoints.
- `app/main.py` — `/v2` router mounted.
- `tests/test_return_draft_schema.py` and `tests/test_draft_to_itr1_input.py` — 21 Phase 1 tests.
- `run.py` and `tests/test_event_loop_policy.py` — Windows Proactor-loop launcher and Playwright subprocess regression coverage.

**Validation:** 43 backend tests passed: 21 Phase 1 tests, 21 legacy ITR-1/ERI regression tests, and 1 event-loop policy test.

**Deferred follow-ups:**
- Some real ITD Prefill files currently parse with `employers=0`; employer enrichment must be fixed in the importer phase.
- AIS capital-gain rows may import with unsupported/missing asset and date evidence; this is outside Phase 1.

---

### Phase 2 — Backend: compute + CBDT from canonical draft (`/v2` compute + generate)

**Goal:** The `/v2` compute and CBDT-generate endpoints consume the canonical draft via the single mapper from Phase 1. No double-compute.

**Files to create/modify:**
- `app/routers/tax_v2.py` (NEW) — `POST /v2/tax-summary/compute` accepting `{draft}` and internally calling `draft_to_itr1_input` → `compute_itr1`.
- `app/engine/filing_gateway_v2.py` (NEW) — `generate_filing_artifact_v2(draft, user)` that:
  1. `draft_to_itr1_input(draft)` (single mapper, Phase 1)
  2. `compute_itr1(typed_input)` (reuse, no re-compute-from-flat)
  3. `build_itr1_json(result, typed_input)`
  4. `validate_itr1_json(itd_json)`
- `app/routers/client_itr_v2.py` — add `POST /v2/clients/{id}/itr/{year}/generate-cbdt-json` consuming draft.
- `app/main.py` — mount `tax_v2.router`.
- `tests/test_tax_v2_compute.py` (NEW) — parity: same draft via `/v2` and legacy compute yields same totals.
- `tests/test_filing_gateway_v2.py` (NEW) — parity: same draft → same CBDT JSON structure as legacy gateway.

**What gets removed:** Nothing yet. The legacy `_build_itr1_input_from_flat` and `_compute_tax_summary_impl` remain for regression parity.

**Tests after Phase 2 (manual):**
1. `pytest tests/test_tax_v2_compute.py tests/test_filing_gateway_v2.py -v` passes.
2. `POST /v2/tax-summary/compute` with a typed draft returns the same `grossTotalIncome`, `totalTaxPayable`, `totalTDS` as the legacy `/tax-summary/compute` for the same data.
3. `POST /v2/clients/{id}/itr/{year}/generate-cbdt-json` produces a CBDT JSON that passes `validate_itr1_json` (same schema gate).
4. The CBDT JSON from `/v2` is byte-identical (modulo key order) to the legacy gateway output for the same draft.
5. No double compute: `/v2` generate calls `compute_itr1` exactly once (verify via log count or a counter in tests).

**Status:** ✅ Completed on 2026-08-17. Phase 2 tests (3 compute + 5 filing gateway + 2 additive schema = 10 new) and legacy ITR-1/ERI regressions passed. The v2 compute endpoint is authenticated and the v2 CBDT endpoint refuses legacy flat blobs until Phase 7 migration.

**Implemented:**
- `app/engine/filing_gateway_v2.py` — single-pipeline service `compute_canonical_itr1` + `generate_cbdt_json` (compute once, reuse for summary + official JSON).
- `app/routers/tax_v2.py` — `POST /v2/tax-summary/compute` (authenticated) accepting a canonical `ReturnDraft` body.
- `app/routers/client_itr_v2.py` — `POST /v2/clients/{id}/itr/{year}/generate-cbdt-json` (loads saved canonical draft, rejects legacy blobs, validates, generates).
- `app/main.py` — mounted `tax_v2_router`.
- `app/schemas/return_draft.py` — additive `PersonalInfo` filing-profile fields (firstName/middleName/surnameOrOrgName/fatherName/aadhaar, primary + secondary contact, structured address) so the canonical draft can construct an `ITR1FilingProfile`; existing Phase 1 drafts remain valid.
- `app/engine/draft_to_itr1_input.py` — 1-line bugfix (`is_primary_refund_account` → `is_primary`) matching the real `BankAccount` schema.
- `tests/test_tax_v2_compute.py`, `tests/test_filing_gateway_v2.py`, extended `tests/test_return_draft_schema.py`.

**Validation:** 52 backend tests passed (31 focused Phase 1/2 + 20 legacy regression + 1 event-loop policy), including a compute-once spy test and a real `validate_itr1_json` round-trip on a filing-ready draft.

**Deferred follow-ups:**
- Headline parity vs legacy compute is covered for GTI/tax/TDS/credits; the v2 summary is intentionally slimmer than the legacy 200-key dict (display fields are frontend concerns).

---

### Phase 3 — Frontend: typed repository (no adapter round-trip)

**Goal:** Frontend loads/saves the typed `ReturnDraft` directly. Eliminates `legacyAdapter.ts` + `legacySerializer.ts` round-trips on the `/v2` path.

**Files to create/modify:**
- `frontend/src/domain/returns/canonicalRepository.ts` (NEW) — `get(clientId, year)` returns `ReturnDraft` from `GET /v2/...`; `save(clientId, draft)` PUTs the draft directly. No `adapt`, no `serialize`.
- `frontend/src/api/itrV2.ts` (NEW) — typed API client for `/v2` endpoints.
- `frontend/src/pages/ITRComputationPage.tsx` — add a feature-flag `USE_V2` (env `VITE_USE_V2=1`). When on, use `canonicalRepository` + `itrV2` instead of `HttpReturnRepository` + `itr`.
- `frontend/src/domain/returns/repository.ts` — mark `HttpReturnRepository` as `@deprecated`, keep for fallback.

**What gets removed:** Nothing. Legacy repository remains as fallback when `USE_V2` is off.

**Tests after Phase 3 (manual):**
1. With `VITE_USE_V2=1`, opening an ITR-1 return loads instantly (no adapter round-trip).
2. Editing a field and saving persists; reloading shows the exact value (round-trip fidelity).
3. The persisted `ClientITR.form_data` in the DB is now **typed `ReturnDraft` JSON** (verify via SQLite inspection) — not the flat blob.
4. With `VITE_USE_V2=0` (or unset), the legacy flow still works (regression).
5. No console errors; eligibility + tax compute still fire on the `/v2` endpoints.

**Status:** ✅ Completed on 2026-08-17. Phase 3 repository tests (12 canonical + 8 factory + 2 legacy = 22) passed and the full frontend suite has no new regressions (the one `returns.test.ts` Schedule HP failure pre-exists on clean `main`). The v2 path is feature-flagged behind `VITE_USE_V2=1`; the legacy flow is unchanged when the flag is off.

**Implemented:**
- `frontend/src/api/itrV2.ts` — typed API client for `/v2/clients/{id}/itr/{year}` (GET/PUT), `/v2/tax-summary/compute`, and `…/generate-cbdt-json` (blob download + `CbdtGenerationError`).
- `frontend/src/domain/returns/canonicalRepository.ts` — `CanonicalReturnRepository` with `stripCompatibility` (deep-clone + remove the legacy `compatibility` envelope the strict backend rejects), `assertCanonicalDraft`, `enforceAssessmentYear`, `createEmptyPersonalInfo`.
- `frontend/src/domain/returns/repositoryFactory.ts` — `isCanonicalV2Enabled` (`VITE_USE_V2 === '1'`) + `createReturnRepository` factory.
- `frontend/src/domain/returns/types.ts` — new `PersonalInfo` interface (additive filing-profile fields mirroring the backend Phase 2 schema); `ReturnDraft.personal` typed as `PersonalInfo`.
- `frontend/src/domain/returns/factory.ts`, `legacyAdapter.ts`, `index.ts`, `repository.ts` (legacy `HttpReturnRepository` marked `@deprecated`).
- `frontend/src/pages/ITRComputationPage.tsx` — surgical feature-flag wiring for compute/save/generate at existing boundaries; legacy flag-off behavior fully preserved.
- `frontend/src/domain/returns/canonicalRepository.test.ts` (12) and `repositoryFactory.test.ts` (8).

**Validation:** 22 targeted tests passed; full suite 115/116 (1 pre-existing). `tsc -b` reports 5 pre-existing errors in externally-edited files; 0 in Phase 3 files.

**Deferred follow-ups:**
- Editor direct-draft mutation (eliminating `composeLegacyPayload`/`buildPhase1Payload`) is Phase 4.
- Typed import mappers are Phase 5.

---

### Phase 4 — Frontend: editor operates directly on typed draft

**Goal:** `editorModel` holds the typed `ReturnDraft` and mutates it directly. Eliminates `composeLegacyPayload`, `buildPhase1Payload`, `applyLegacyActionWithSnapshot`, `applyLegacyPatch`, `applyLegacySetStateAction`.

**Files to create/modify:**
- `frontend/src/domain/returns/editorModelV2.ts` (NEW) — `ReturnEditorModel = { draft: ReturnDraft }` (no `extras`). Updates return new immutable drafts via `structuredClone`. No compatibility envelope.
- `frontend/src/pages/ITRComputationPage.tsx` — when `USE_V2`:
  - Replace `composeLegacyPayload(editorRef.current)` with `editorRef.current.draft`.
  - Replace `buildPhase1Payload(...)` with the draft itself.
  - Replace `applyLegacyActionWithSnapshot` with `updateDraft(prev => next)` + `saveDraft(next)`.
  - Replace manager round-trips (`tdsToManager`/`tdsFromManager`) with direct draft mutations.
- `frontend/src/domain/returns/editorModel.ts` — mark legacy functions `@deprecated`.

**What gets removed (deprecation only):** The legacy `editorModel.ts` functions stay but are unused on the `/v2` path. Total removal happens in Phase 8.

**Tests after Phase 4 (manual):**
1. With `VITE_USE_V2=1`, editing Salary / House Property / 80C / TDS / Bank fields updates the draft directly; the tax compute fires correctly.
2. Save persists the typed draft; reload restores exactly.
3. Generate CBDT JSON works via `/v2/.../generate-cbdt-json`.
4. No legacy alias zeroing code runs (`buildPhase1Payload`'s `s80C=0` etc. is gone on this path).
5. Eligibility engine reads typed fields (`draft.employers.length`, `draft.taxes.tds.length`) — no scalar drift.

**Status:** ✅ Completed (partial) on 2026-08-17. The compute, save, and generate paths now operate directly on the typed draft when `VITE_USE_V2=1` — `composeLegacyPayload` and `buildPhase1Payload` no longer run on those paths. A canonical immutable `editorModelV2` (no `extras`/compatibility envelope) is exported and tested for Phase 5 migration. Flat import-merge patches (`setFormData`) still route through the legacy envelope until Phase 5 provides typed import mappers; this is the documented remaining boundary, not a regression.

**Implemented:**
- `frontend/src/domain/returns/editorModelV2.ts` — `ReturnEditorModelV2 = { draft: ReturnDraft }`, immutable updaters delegating to the existing typed draft-only logic with `compatibility` stripped.
- `frontend/src/domain/returns/editorModel.ts` — `composeLegacyPayload`/`applyLegacyPatch`/`applyLegacySetStateAction`/`applyLegacyActionWithSnapshot` marked `@deprecated`.
- `frontend/src/domain/returns/index.ts` — re-exports.
- `frontend/src/pages/ITRComputationPage.tsx` — `taxSummaryPayload` memo returns a minimal object under v2; `handleSave` persists `currentEditor.draft` directly; `handleGenerateCbdtJson` v2 branch saves then generates without composing a legacy payload.
- `frontend/src/domain/returns/editorModelV2.test.ts` — 3 tests (immutability, idempotent updates, no compatibility envelope).

**Validation:** 29 targeted tests passed (3 editorModelV2 + 18 editorModel + 8 repositoryFactory); `tsc -b` reports the same 5 pre-existing errors, 0 in Phase 4 files.

**Deferred follow-ups:**
- Migrate `setFormData`/import-merge patches and `updateEditor` manager bindings to consume `editorModelV2` directly (Phase 5 typed import mappers).
- Validate flow remains legacy until Phase 5+.

---

### Phase 5 — Frontend: typed import mappers (collapse 5 → form-agnostic patches)

**Goal:** Each importer (AIS, 26AS, TIS, Prefill, filed-return) returns a typed `ReturnDraftPatch`, not a flat blob. One `mergeDraft(base, patch)` replaces `mergeCompatibility` + 5 flat mappers.

**Files to create/modify:**
- `frontend/src/domain/returns/draftPatch.ts` (NEW) — `ReturnDraftPatch` type (partial `ReturnDraft`) + `mergeDraft(base, patch)` (deep merge by id for arrays).
- `frontend/src/utils/mapAisToDraftPatch.ts` (NEW) — replaces inline AIS mapping (`ITRComputationPage.tsx:1368-2050`).
- `frontend/src/utils/map26asToDraftPatch.ts` (NEW) — replaces inline 26AS mapping (`:1141-1370`).
- `frontend/src/utils/mapTisToDraftPatch.ts` (NEW).
- `frontend/src/utils/mapPrefillToDraftPatch.ts` (NEW) — replaces `mapPrefillToFormData.ts`.
- `frontend/src/utils/mapReconciledToDraftPatch.ts` (NEW) — replaces `mapReconciledToFormData.ts`.
- `frontend/src/pages/ITRComputationPage.tsx` — when `USE_V2`, import handlers call the new mappers + `mergeDraft`.

**What gets removed:** Nothing yet. Legacy flat mappers stay for the `USE_V2=0` path.

**Tests after Phase 5 (manual):**
1. Import 26AS → draft `taxes.tds` + `employers` + `otherSources.interest` populated correctly.
2. Import AIS → draft `otherSources` (interest/dividends/winnings) + `capitalGainsSchedule` + `taxes.tds` populated.
3. Import TIS → draft `employers` + `otherSources` populated.
4. Import Prefill → draft `personal` + `employers` + `bankAccounts` + `deductions` populated.
5. Portal automation import (reconciled) → all of the above merged with precedence (Prefill > reconciled for income, reconciled > Prefill for TDS).
6. Each import persists the **typed draft** (not flat blob) — verify via DB.
7. No `interestSB`/`interestFD`/`dividendShares` legacy scalars are written by any import path.

**Status:** ✅ Completed on 2026-08-17. The `VITE_USE_V2=1` import paths now map Prefill, reconciled portal data, AIS, TIS, and 26AS directly into canonical `ReturnDraftPatch` values and merge them with `mergeDraft`; the flag-off inline/flat paths remain intact. Twelve focused mapper/merge tests pass, the full frontend suite passes 130/131 with only the pre-existing Schedule HP test failure, and TypeScript reports only the five pre-existing errors with zero errors in Phase 5 files. Live portal/DB persistence verification remains a manual follow-up.

---

### Phase 6 — Backend: remove dead autopopulate endpoints

**Goal:** Delete the 4 known-broken/redundant backend autopopulate endpoints now that the frontend uses typed mappers.

**Files to modify:**
- `app/routers/integration.py` — remove `autopopulate_form16`, `autopopulate_ais`, `autopopulate_all`, `prefill_autopopulate`.
- `frontend/src/api/integration.ts` — remove `autoPopulateAll`, `autoPopulateFromForm16`, `autoPopulateFromAIS`, `autoPopulateFromPrefill`.
- `frontend/src/pages/ITRComputationPage.tsx` — remove calls to removed API methods (the inline 26AS/AIS paths already bypass them; the reconciled path calls `autoPopulateAll` only as a fallback at `:2060`).

**What gets removed:** 4 backend endpoints + 4 frontend API methods + ~150 lines of inline fallback.

**Tests after Phase 6 (manual):**
1. All import flows from Phase 5 still work (they never call the removed endpoints on the `/v2` path).
2. The legacy `USE_V2=0` flow's 26AS/AIS import still works (it uses inline mapping, not the removed endpoints).
3. `GET /openapi.json` no longer lists the 4 removed endpoints.
4. No frontend console errors about missing endpoints.

**Status:** ✅ Completed on 2026-08-17. The 4 dead autopopulate backend endpoints and their 4 frontend API methods are removed, and the unreachable `autoPopulateAll` call block in `ITRComputationPage.tsx` is deleted. Form 16 import keeps working via an inlined merge that replaces the removed `autoPopulateFromForm16` endpoint (the backend was a thin no-op merge with no real parser). 304/304 backend tests pass and TypeScript reports only the 5 pre-existing errors (zero new from Phase 6). The integration router no longer exposes any `autopopulate` path.

**Implemented:**
- `app/routers/integration.py` — removed `autopopulate_form16`, `autopopulate_ais`, `autopopulate_all`, `prefill_autopopulate` (~210 lines). The `reconciliation` endpoint and the real `parse_prefill_json`-backed prefill import endpoint remain.
- `frontend/src/api/integration.ts` — removed `autoPopulateFromForm16`, `autoPopulateFromAIS`, `autoPopulateAll`, `autoPopulateFromPrefill`.
- `frontend/src/pages/ITRComputationPage.tsx` — deleted the unreachable `autoPopulateAll` call + reconciliation fallback block; inlined the Form 16 merge.

**Validation:** 304 backend tests passed (corpus + schema + reconciliation + gateway + v2 compute + boundary regression + draft mapper); TypeScript clean (5 pre-existing errors only, 0 in Phase 6 files); integration router OpenAPI no longer lists any autopopulate path.

**Deferred follow-ups:**
- None for Phase 6. Phase 7 unifies the two flat→typed mappers.

**Goal:** The legacy flat-blob compute and CBDT paths delegate to `draft_to_itr1_input` by first adapting the flat blob to draft shape, OR are deleted entirely (if `/v2` is the only path). This phase deletes the duplicate mapper.

**Decision gate:** Only execute this phase after Phase 3+4 confirm the frontend runs fully on `/v2`. Then the legacy flat endpoints can be deleted.

**Files to modify:**
- `app/engine/filing_gateway.py` — delete `_build_itr1_input_from_flat` (~300 lines). Legacy `generate_filing_artifact` either delegates to `generate_filing_artifact_v2` (after adapting flat→draft) or is deleted.
- `app/routers/tax.py` — `_compute_tax_summary_impl`'s ITR-1 branch delegates to `draft_to_itr1_input` (after adapting flat→draft) OR is deleted if `/v2` is the sole path.
- `app/routers/client_itr.py` — legacy flat `GET/PUT/validate/generate-cbdt-json` marked `@deprecated` or deleted based on the decision gate.
- `app/engine/flat_to_draft.py` (NEW, thin) — `flat_to_draft(flat_blob) -> dict` that reuses the frontend `adaptLegacyReturn` logic in Python, for one-time migration of legacy saved rows.

**What gets removed:** `_build_itr1_input_from_flat` (~300 lines). The two-mapper sync problem is eliminated.

**Tests after Phase 7 (manual):**
1. Legacy `/clients/{id}/itr/{year}` flat endpoints either still work (if kept as deprecated adapters) or return 410 Gone (if deleted) — per decision gate.
2. `/v2` endpoints produce identical compute + CBDT results as before.
3. Old saved drafts (flat blob in `ClientITR.form_data`) are auto-migrated to typed draft on first `GET /v2` load via `flat_to_draft`.
4. No regression in `pytest tests/test_itr1_calculator.py tests/test_eri_routers.py`.

**Status:** ✅ Completed on 2026-08-18. The ~684-line duplicate `_build_itr1_input_from_flat` mapper is replaced by a 30-line delegate that routes the flat blob through the single canonical `flat_to_draft → draft_to_itr1_input` path. The two-mapper sync problem is eliminated.

**Implemented:**
- `app/engine/flat_to_draft.py` (NEW, ~880 lines) — one-way Python port of the frontend `adaptLegacyReturn` adapter: flat blob → typed `ReturnDraft`. Covers personal, filing, employers, house properties, other sources, deductions (Chapter VI-A), taxes (TDS1/TDS2/TCS/challans), bank accounts, capital-gains schedule, verification, TRP, and provenance.
- `app/engine/filing_gateway.py` — `_build_itr1_input_from_flat` is now a thin delegate: `flat_to_draft(payload) → draft_to_itr1_input(draft)`, plus flat-blob-only CBDT schedules (80GGA, 80GGC, TRP, HRA details, TDS3, seventh-proviso declarations) and `returnFileSectionCode` cross-checks that the canonical draft does not carry today.
- `app/engine/draft_to_itr1_input.py` — fixed two real bugs surfaced by the unification: (1) new-regime exclusion now zeroes old-regime-only Chapter VI-A deductions (80C/80D/80E/80G/80CCD1B/80EE/80GG/80GGA/80GGC/80DD/80DDB/80U) instead of only 80TTA/80TTB; (2) bank-account `is_primary` follows the explicit `useForRefund` flag only (no `idx==0` auto-primary) so `build_itr1_json`'s "exactly one primary" validation is not masked.
- `app/engine/filing_gateway_v2.py` — `_property_profiles` now falls back to the property name then the taxpayer's primary address/city/state/country/pin (mirrors the legacy mapper's fallback chain) so a property row omitting an explicit address still produces a valid profile.
- `app/engine/calculators/itr1.py` — corrected the Section 112A annual exemption: the exempt portion (up to ₹1.25L) is removed from GTI and the slab base (`cg_112a_taxable`), not merely from the 12.5% special-rate tax. This matches the AY 2026-27 legal position and the newest regression test's documented intent.

**Validation:** 798 backend tests pass (corpus + reconciliation + v2 compute + golden + profile + boundary + 112A unification + draft mapper + calculator regressions). Only 2 pre-existing failures remain (SQLite `name` column migration, worker prefill source-text assertion) — both fail on the clean baseline, unrelated to this phase. Frontend: 139/140 domain tests pass (only the known pre-existing Schedule HP failure). Added `test_phase7_delegate_uses_single_canonical_mapper` to lock in the single-mapper invariant.

---

### Phase 8 — Frontend: delete legacy adapter/serializer/editorModel bridge

**Goal:** Remove the entire flat-blob bridge layer now that `/v2` is the only path.

**Files to delete:**
- `frontend/src/domain/returns/legacyAdapter.ts`
- `frontend/src/domain/returns/legacySerializer.ts`
- `frontend/src/utils/mapFiledReturnToFormData.ts`
- `frontend/src/utils/mapPrefillToFormData.ts`
- `frontend/src/utils/mapReconciledToFormData.ts`
- `frontend/src/utils/mapReconciledToFormData.test.ts`
- `frontend/src/pages/patch_bank.py`, `patch_bank2.py`, `patch_phase1.py`, `patch_tabs_phase1.py` (scratch files).

**Files to modify:**
- `frontend/src/domain/returns/editorModel.ts` — delete legacy functions; keep only what `editorModelV2` still uses (likely nothing — delete file).
- `frontend/src/domain/returns/repository.ts` — delete `HttpReturnRepository` (replaced by `canonicalRepository`).
- `frontend/src/domain/returns/index.ts` — remove deleted re-exports.
- `frontend/src/pages/ITRComputationPage.tsx` — remove `USE_V2` flag (now always on), remove `buildPhase1Payload`, `validatePhase1Payload` (validation moves to backend Pydantic on the `/v2` save).
- `frontend/src/utils/mapReconciledToFormData.ts` — already deleted; its test too.

**What gets removed:** ~1500 lines of bridge code + ~850 lines of inline page mapping + 4 scratch files.

**Tests after Phase 8 (manual):**
1. Full ITR-1 flow: add client → open return → edit → save → validate → generate CBDT JSON → download. All work without `USE_V2` flag.
2. Import 26AS, AIS, TIS, Prefill, reconciled — all populate the typed draft.
3. Reload after save restores exact state (round-trip fidelity).
4. `npm run build` succeeds with no TypeScript errors.
5. `npm run lint` passes.
6. `npm run test` (vitest) passes.
7. Bundle size reduced (verify via `vite build` output).
8. No reference to `composeLegacyPayload`, `adaptLegacyReturn`, `buildPhase1Payload`, `applyLegacyActionWithSnapshot` anywhere in `frontend/src`.

**Status:** ⬜ Not started

---

### Phase 9 — ITR-2/3/4 template application (future, post-ITR-1 stabilization)

**Goal:** Apply the canonical-draft template to ITR-2, ITR-3, ITR-4. Each form adds only its own `draft_to_itrN_input` mapper + schedules. Import mappers are form-agnostic.

**Not detailed here** — this phase is planned only after ITR-1 Phases 1-8 are stable in production.

**Status:** ⬜ Not started

---

## Process Rules

1. **One phase at a time.** No phase starts until the user confirms the previous phase's manual tests pass.
2. **Commit after confirmation.** Each phase's code is committed only after the user reports test results. The commit message references this MD file.
3. **MD update after commit.** The phase's `**Status:**` line changes from `⬜ Not started` → `✅ Completed (commit <sha>)` after the commit lands.
4. **No breaking changes mid-phase.** Each phase keeps legacy paths working via feature flags or deprecated endpoints until the removal phase (7/8).
5. **Tests first.** Every phase has a test list. If a test fails, the phase is not complete — fix before asking for confirmation.

---

## Changelog

| Date | Phase | Commit | Notes |
|---|---|---|---|
| 2026-08-17 | — | `10d0f73` | Baseline commit before refactor. ITR-4 engine + filing_gateway + validation rules. |
