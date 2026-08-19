# ITR-1/4 Capital Gains Tab + Unified Import Pipeline — Implementation Guide

**Created:** 2026-08-19
**Status:** In progress
**Spec:** `C:\Users\Devansh\.factory\specs\2026-08-19-itr-1-4-capital-gains-tab-unified-import-pipeline.md`

---

## Executive Summary

Two interdependent workstreams to make ITR-1 and ITR-4 production-ready:

- **Workstream A — Unified Import Pipeline:** Make the automation import path and the manual single-document import path use the same parsers, the same reconciliation engine, and the same merge logic. Most importantly, **project capital-gains evidence** (currently parsed and reconciled server-side but never auto-populated into the draft) into the typed CG schedule.
- **Workstream B — Capital Gains Tab:** Replace the opaque `Record<string, unknown>` CG schedule field with a fully-typed `CapitalGainsSchedule` interface; migrate the `CapitalGainsTab` to the typed draft + `editorModelV2` updater; auto-populate Schedule 112A from AIS; enforce ITR-1/4 eligibility (₹1.25L threshold, non-112A escalation); compute 112A via the proper restricted-112A engine.

Both workstreams are sequenced into **5 phases**. After each phase: update this MD, commit, push to GitHub, and **wait for the user to test** before proceeding.

---

## Audit Findings (current state)

### Capital Gains tab — what exists
1. `CapitalGainsEntryManager.tsx` — a full, form-gated, CBDT-faithful Schedule CG editor covering all sub-rows (A1–B6, 112A, 115AD, VDA, DTAA, buy-back, deductions, unutilized, quarterly, loss set-off).
2. `validateCapitalGainsSchedule` — a thorough per-row validator (ISIN/PAN/transferee/VDA-date/DTAA/exemption rules). **Defined but not invoked at the render path.**
3. `hasNonSimplifiedCapitalGains` — tested helper for ITR-1/4 form-gating.
4. `_map_capital_gains` in `draft_to_itr1_input.py` — maps `simplified112A` → `CapitalGainsIncome.ltcg_112a`.
5. Eligibility engine — full 112A threshold (₹1.25L) + non-112A escalation logic from evidence rows.
6. `sourceClassification.ts` — classifies every CG-relevant AIS code / TIS category / 26AS section into `RESTRICTED_112A_TAXABLE` vs `OUT_OF_SCOPE_TAXABLE`.

### Capital Gains tab — what's missing/broken
1. **No canonical `CapitalGainsSchedule` type** in `types.ts` — the draft field is `Record<string, unknown>`. Every other schedule is typed; CG is the lone opaque blob.
2. **No `editorModelV2` updater for CG** — the UI uses raw `replaceDraft` whole-blob replacement.
3. **`CapitalGainsTab` is a local `any`-typed wrapper** in `ITRComputationPage.tsx`, not exported from `ITRComputationTabs.tsx` like the other tabs.
4. **`entries` prop (`capitalGainTransactions`) is dead** — no writer, barely read; a stale legacy field.
5. **Typo in eligibility `hasCapitalGainsRows`** — checks `schedule115V` instead of `schedule115AD`.
6. **`validateCapitalGainsSchedule` has no visible call site** at the render path.
7. **ITR-1 silently zeroes non-112A CG** — `_map_capital_gains` ignores all full-schedule arrays without raising.
8. **Test coverage is minimal** — only `hasNonSimplifiedCapitalGains` is tested.

### Import pipeline — what exists
1. AIS parser (`ais_extractor/extractor.py`) — PyMuPDF state machine. **Has full CG transaction-detail parsers** for SFT-17-LES (listed equity) and SFT-18-EMF (equity MF) extracting ISIN, security name, quantity, sale price per unit, sales consideration, cost of acquisition, FMV, unit FMV, STT, indexed cost, asset type (long/short term), transaction date.
2. TIS parser (`ais_extractor/tis_extractor.py`) — state machine. Category-level accepted/processed totals; no CG transaction detail.
3. 26AS parser (`ais_extractor/as26_extractor.py`) — pdfplumber tables. Parts I–X. No securities CG; Part IV (194IA property sales) parsed but no purchase-date/indexed-cost/holding-period.
4. Prefill parser (`app/engine/importers/prefill_parser.py`) — `parse_prefill_json` + `PrefillExtraction` dataclass (1848 lines).
5. Reconciliation engine (`ais_extractor/reconciliation.py`) — `reconcile(ais, tis, as26)`. Produces `capital_gain_evidence` (rich `CapitalGainEvidence` dataclass with ISIN, quantity, sale_price_per_unit, acquisition_cost, FMV, STT, etc.), `capital_gain_controls`, `capital_gain_control_discrepancies`.
6. Real document corpus: 62 AIS JSONs, 68 26AS JSONs, 61 TIS JSONs in `ais_extractor/test_output*/`. Raw PDFs in `downloads/`.

### Import pipeline — what's missing/broken
1. **No frontend mapper consumes `capital_gain_evidence`** — CG data is parsed and reconciled server-side but **never auto-populated into the draft**. The single biggest CG gap.
2. **`mapDirectImportsToDraftPatch.ts` implementation is missing** — only the test file exists.
3. **Automation vs manual paths diverge:** automation stores raw `reconcile()` output; manual 26AS runs through `_map_legacy_26as` (a transformation absent from automation), so the two paths feed **different shapes** to the same `map26asToDraftPatch`.
4. **Prefill is never reconciled** with AIS/TIS/26AS — attached as a sibling object.
5. **Manual imports persist to `ImportedDocument`; automation imports don't** — automation results live only on `AutomationJob.parsed_results`.
6. `mapPrefillToDraftPatch` ignores `PrefillExtraction.capital_gains_property`.

---

## Phase Plan

### Phase 1 — Canonical CapitalGainsSchedule type + updater (A1)

**Goal:** Replace `capitalGainsSchedule: Record<string, unknown>` with a fully-typed `CapitalGainsSchedule` interface; add `EMPTY_CAPITAL_GAINS_SCHEDULE` constant + `updateCapitalGainsSchedule` updater.

**Files to change:**
- `frontend/src/domain/returns/types.ts` — add `CapitalGainsSchedule`, `Scrip112A`, `Scrip115AD`, `VdaEntry`, `ImmovableAssetGain`, `TransfereeDetail`, `ImprovementDetail`, `ExemptionClaim`, `DtaaEntry`, `DeductionClaim`, `UnutilizedDeposit`, `CapitalGainsAggregates`, `LossSetOff`, `QuarterlyMatrix` interfaces. Change `ReturnDraft.capitalGainsSchedule` from `Record<string, unknown>` to `CapitalGainsSchedule`. Add `EMPTY_CAPITAL_GAINS_SCHEDULE` constant.
- `frontend/src/domain/returns/factory.ts` — update `createEmptyReturnDraft` to use `EMPTY_CAPITAL_GAINS_SCHEDULE`.
- `frontend/src/domain/returns/editorModelV2.ts` — add `updateCapitalGainsSchedule(model, schedule)` updater.
- `frontend/src/domain/returns/index.ts` — re-export new types.

**Test plan (user):**
- `npx tsc -b` compiles clean (no new errors).
- `npx vitest run` — all existing tests pass.
- Factory creates a draft with `capitalGainsSchedule: EMPTY_CAPITAL_GAINS_SCHEDULE`.
- `updateCapitalGainsSchedule` immutably replaces the schedule.

**Validation:** `tsc -b` zero new errors; `vitest run` green.

---

### Phase 2 — CG auto-population mappers + unified import endpoint (A3 + A2)

**Goal:** Create `mapCapitalGainsToDraftPatch.ts` that consumes `capital_gain_evidence` and projects it into the typed `CapitalGainsSchedule`. Wire it into all four import mappers. Add a unified backend endpoint `POST /v2/imports/parse-reconcile`.

**Files to change:**
- `frontend/src/utils/mapCapitalGainsToDraftPatch.ts` (new) — `mapCapitalGainsEvidence(evidence)` → `CapitalGainsSchedule` patch. AIS SFT-17-LES → `schedule112A[]`; SFT-18-EMF → `schedule115AD[]` or `schedule112A[]`; SFT-012/194IA → `stImmovable[]`/`ltImmovable[]`; VDA → `vda[]`; aggregate → `simplified112A`.
- `frontend/src/utils/mapAisToDraftPatch.ts` — consume `capital_gain_evidence` from parsed AIS.
- `frontend/src/utils/mapTisToDraftPatch.ts` — consume TIS category-level CG totals as evidence.
- `frontend/src/utils/map26asToDraftPatch.ts` — consume 194IA property-sale rows into `stImmovable[]`/`ltImmovable[]`.
- `frontend/src/utils/mapReconciledToDraftPatch.ts` — consume `capital_gain_evidence` from reconciled payload.
- `frontend/src/utils/mapPrefillToDraftPatch.ts` — consume `PrefillExtraction.capital_gains_property`.
- `frontend/src/utils/mapDirectImportsToDraftPatch.ts` (new) — single orchestrator.
- `app/routers/tax_v2.py` — add `POST /v2/imports/parse-reconcile` endpoint.
- `app/automation/job_worker.py` — call the unified endpoint internally.

**Test plan (user):**
- Import the COVPC5929M AIS sample → `schedule112A[]` (or `schedule115AD[]`) populates with ISIN, quantity, sale price, cost.
- Import a 194IA 26AS row → `stImmovable[]`/`ltImmovable[]` stubs populate.
- Automation job → reconciled payload → `mapReconciledToDraftPatch` → CG schedule populated.
- `capital_gain_evidence` survives through `reconcile()` → `parsed_results` → frontend.

**Validation:** New unit tests `mapCapitalGainsToDraftPatch.test.ts`; corpus compliance tests pass.

---

### Phase 3 — Typed CapitalGainsTab + auto-populate from AIS (B1 + B2 + B3)

**Goal:** Move `CapitalGainsTab` into `ITRComputationTabs.tsx` with a typed signature; wire `onChange` through `updateCapitalGainsSchedule`; auto-populate `simplified112A` from imported scrips for ITR-1/4.

**Files to change:**
- `frontend/src/pages/ITRComputationTabs.tsx` — add exported `CapitalGainsTab({ draft, taxResult, itrForm, onChange })`.
- `frontend/src/pages/ITRComputationPage.tsx` — delete the local `CapitalGainsTab`; use the imported one; wire `onChange` through `updateEditor((model) => updateCapitalGainsSchedule(model, schedule))`.
- `frontend/src/components/CapitalGainsEntryManager.tsx` — keep the full Schedule CG editor; ensure it accepts the typed `CapitalGainsScheduleData` (already matches); add "Populate from imported scrips" button for ITR-1/4 that aggregates `schedule112A[]` into `simplified112A`.

**Test plan (user):**
- Load a client with imported AIS CG scrips → Capital Gains tab shows populated `schedule112A[]` rows.
- For ITR-1/4, the simplified 112A aggregate shows sale consideration + cost.
- Editing a scrip updates the typed draft (not a raw blob).
- "Populate from imported scrips" button aggregates into `simplified112A`.

**Validation:** `tsc -b` clean; `vitest run` green; manual UI test confirms population.

---

### Phase 4 — Eligibility fix + 112A compute (B4 + B5)

**Goal:** Fix the `schedule115AD` typo in `eligibility.ts`; wire `validateCapitalGainsSchedule` into the render; extend `_map_capital_gains` to invoke `restricted_112a.py` for proper 112A computation when scrips are present; surface `taxResult.capitalGainsSummary`.

**Files to change:**
- `frontend/src/domain/eligibility.ts` — fix `schedule115V` → `schedule115AD` typo in `hasCapitalGainsRows`.
- `frontend/src/pages/ITRComputationTabs.tsx` (or `CapitalGainsEntryManager.tsx`) — wire `validateCapitalGainsSchedule` at render; surface inline field errors.
- `app/engine/draft_to_itr1_input.py` — extend `_map_capital_gains` to invoke `app/engine/schedules/restricted_112a.py` when `schedule112A[]` scrips are present (per-scrip FMV, lower-of-cost/FMV, ₹1.25L exemption, grandfathering).
- `app/engine/filing_gateway_v2.py` — surface `capitalGainsSummary` (transactions, gain, exemption, balance) in the summary.
- `frontend/src/components/CapitalGainsEntryManager.tsx` — `overlayComputedReadouts` already overlays `summary.transactions[i]`; ensure it reads the new summary shape.

**Test plan (user):**
- ITR-1 with 112A scrips → tax summary shows proper LTCG (sale − cost, ₹1.25L exemption applied).
- ITR-1 with 112A > ₹1.25L → form escalates to ITR-2.
- ITR-1 with non-112A CG (property sale) → form escalates to ITR-2.
- Validation errors surface inline.

**Validation:** `tsc -b` clean; `vitest run` green; backend `pytest` green; manual compute shows correct 112A tax.

---

### Phase 5 — Corpus hardening + validation + tests (A4 + A5 + B6)

**Goal:** Run all 191 real corpus samples through the hardened parsers; fix any extraction regressions; add comprehensive test coverage.

**Files to change:**
- `tests/test_real_ais_corpus_capital_gains.py` (new) — pin CG extraction against all 62 AIS samples.
- `tests/test_real_tis_corpus_capital_gains.py` (new) — pin TIS CG category totals against all 61 samples.
- `tests/test_real_26as_corpus_property_sales.py` (new) — pin 194IA property-sale extraction against all 68 samples.
- `frontend/src/components/CapitalGainsTab.test.tsx` (new) — render, onChange contract, form-gating, AIS-population, backend overlay.
- `frontend/src/utils/mapCapitalGainsToDraftPatch.test.ts` (new) — SFT-17-LES → schedule112A, SFT-18-EMF → 115AD, SFT-012 → stImmovable, VDA → vda, aggregate → simplified112A.
- `ais_extractor/reconciliation.py` — extend `_extract_capital_gain_ledger` to cross-foot AIS sale-detail vs AIS purchase-aggregate vs TIS accepted-total at the transaction level.

**Test plan (user):**
- All 191 corpus samples parse without errors.
- All new tests pass.
- End-to-end: automation job → reconcile → CG populated → compute → correct 112A tax.

**Validation:** Full `pytest` + `vitest run` green; corpus compliance green; manual end-to-end test.

---

## Progress Log

| Date | Phase | Commit | Status |
|---|---|---|---|
| 2026-08-19 | 1 | `<pending push>` | ✅ Complete — awaiting user test |

---

## Phase 1 — Completed 2026-08-19

### Changes shipped
1. **`frontend/src/domain/returns/types.ts`** — added fully-typed `CapitalGainsSchedule` interface with typed element interfaces:
   - `Scrip112A` (listed equity/MF scrips with ISIN, quantity, sale price, cost, FMV, transfer expenses)
   - `Scrip115AD` (FII/FPI scrips — same shape as 112A)
   - `VdaEntry` (VDA transactions with acquisition cost, consideration, head of income)
   - `ImmovableAssetGain` (STCG/LTCG land/building with nested `TransfereeDetail[]`, `ImprovementDetail[]`, `ExemptionClaim[]`)
   - `DtaaEntry`, `DeductionClaim`, `UnutilizedDeposit`, `CapitalGainsAggregates`, `LossSetOff`, `QuarterlyMatrix`
   - `JsonRow` type alias (for sub-arrays the existing `CapitalGainsEntryManager` edits with field-spec validation — full rewrite out of scope)
   - `EMPTY_CAPITAL_GAINS_SCHEDULE` constant
   - Changed `ReturnDraft.capitalGainsSchedule` from `Record<string, unknown>` to `CapitalGainsSchedule`
2. **`frontend/src/domain/returns/factory.ts`** — `createEmptyReturnDraft` now seeds `capitalGainsSchedule: { ...EMPTY_CAPITAL_GAINS_SCHEDULE }`.
3. **`frontend/src/domain/returns/editorModelV2.ts`** — added `updateCapitalGainsSchedule(model, schedule)` updater (deep-clone whole-replacement, same pattern as `updateBpNetProfit`).
4. **`frontend/src/components/CapitalGainsEntryManager.tsx`** — broadened `Props.data` and `hasNonSimplifiedCapitalGains` to accept `CanonicalCapitalGainsSchedule` (the typed schedule) in addition to the local `CapitalGainsScheduleData`. This avoids a massive rewrite of the field-spec-driven editor while letting the typed draft flow in.
5. **`frontend/src/domain/returns/editorModelV2.test.ts`** — added 2 tests:
   - `seeds the capital gains schedule as the typed EMPTY_CAPITAL_GAINS_SCHEDULE`
   - `replaces the capital gains schedule immutably via updateCapitalGainsSchedule`

### Validation
- `tsc -b`: zero new errors (only pre-existing `api/reconciliation.ts` missing `./client` module).
- `vitest run`: 15 files / 120 tests pass (118 existing + 2 new).
- `vite build`: clean production bundle (939 kB main chunk).

### User test plan
1. Restart the frontend (`npm run dev` in `frontend/`).
2. Load any client — the ITR computation page should render without crashes (the CG tab now reads the typed `EMPTY_CAPITAL_GAINS_SCHEDULE`).
3. Open the Capital Gains tab — it should render the full Schedule CG editor (simplified 112A quick-entry enabled for ITR-1/4; full Schedule CG sections greyed-out with "Switch to ITR-2/ITR-3" badges).
4. Switch form to ITR-2 — the full Schedule CG sections should become enabled.
5. Editing any CG field should update the typed draft (no console errors).
6. Run `npx vitest run` — 120 tests pass.
7. Run `npx tsc -b` — no new errors.

Once you confirm Phase 1 is green, I'll update this MD, commit, push, and proceed to Phase 2 (CG auto-population mappers + unified import endpoint).

---

## Notes

- **Scope:** This workstream targets ITR-1 and ITR-4 CG (112A simplified + 112A full Schedule + VDA where allowed). ITR-2/3 full Schedule CG (DTAA, slump sale, foreign assets) stays as-is — the typed schedule from Phase 1 makes it ready for a future ITR-2 workstream.
- **Testing cadence:** After each phase, the user tests the implementation. Only after the user passes it do I update this MD, commit, push to GitHub, and proceed to the next phase.
- **Debug logging:** Temporary `print("[DEBUG ...]")` statements in `app/engine/filing_gateway_v2.py` will be removed in Phase 4 (when 112A compute is wired properly).
