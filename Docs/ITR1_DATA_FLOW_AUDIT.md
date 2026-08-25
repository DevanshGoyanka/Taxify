# ITR-1 Data-Flow Audit — Taxify

**Date:** 2026-08-17
**Scope:** ITR-1 data flow only. Every finding cites `file:line` in the real source. No MD docs were used as authority.

---

## Part A — The Two Competing Data Representations

The application carries **two parallel representations** of the same ITR-1 data. Almost every "complex" file exists only to shuttle between them.

### A1. The flat legacy formData blob (what gets saved & computed)

A single `Record<string, any>` with ~150+ keys — a mix of structured arrays AND legacy scalar aliases that mean the same thing.

| Concept | Structured form (array) | Legacy scalar alias (same value) |
|---|---|---|
| Salary | `employerEntries[]` | `basic`, `da`, `hra`, `bonus`, `allowances`, `perquisites`, `profitsInLieu`, `tdsS192` |
| House property | `housePropertyEntries[]` | `grossRent`, `munTax`, `homeLoanInt`, `sopLoanInt` |
| Interest | `interestEntries[]` / `bankInterestEntries[]` | `interestSB`, `interestFD`, `interestRD`, `nscInterest`, `scssInterest`, `postOfficeInterest`, `otherInterest` |
| Dividend | `dividendEntries[]` | `dividends`, `dividendShares`, `dividendMF`, `dividendUnits` |
| Winnings | `winningsEntries[]` | `lotteryIncome`, `horseRaceIncome`, `cardGameIncome`, `onlineGamingIncome` |
| Gifts | `giftEntries[]` | `giftsFromRelatives`, `giftsFromNonRelatives` |
| 80C | `section80C.investments[]` | `s80C_epf`, `s80C_ppf`, `s80C_elss`, `s80C_lic`, `s80C_home` |
| 80G | `donationEntries[]` | `s80G` |
| TDS | `tdsEntries[]` | `tdsS192`, `tds194A`, `tdsOther` |
| Advance tax | `advanceTaxEntries[]` | `adv15Jun`, `adv15Sep`, `adv15Dec`, `adv15Mar` |
| Self-assessment | `selfAssessmentTaxEntries[]` | `selfTax` |
| Capital gains | `capitalGainTransactions[]` + `capitalGainsSchedule` | `ltcgPre`, `ltcgPost`, `ltcg112APre`, `stcgPre`, `stcgPost`, `stcgOther` |
| Exempt income | `exemptIncomeSchedule.otherExemptIncome[]` | `ppfInterest`, `sukanyaSamriddhiInterest`, `otherExemptInterest`, `ltcgExempt`, `shareOfProfitFirm` |

**References:**
- `app/engine/filing_gateway.py:559-600` (salary mapping reads both `row.get("basic")` from `employerEntries` AND `payload["basic"]`).
- `app/routers/tax.py:391-399` (salary), `:521-528` (interest scalar fallback), `:557-563` (dividend scalar fallback).
- `frontend/src/domain/returns/legacyAdapter.ts` — the `known` Set (~line 50) lists every legacy key.
- `frontend/src/pages/ITRComputationPage.tsx:57-75` (`buildPhase1Payload` zeroes `s80C`, `s80D`, `s80E`, `s80G`, rebuilds `bankAccountDetails`, sets `adv15*=0`).

### A2. The canonical ReturnDraft (normalized, typed)

`frontend/src/domain/returns/types.ts:357-367` — `employers: Employer[]`, `houseProperties: HouseProperty[]`, `otherSources.interest: InterestIncome[]`, `deductions.section80C: Investment80C[]`, `taxes.tds: TdsCredit[]`, etc. Strongly typed elements at `types.ts:10-30` (Employer), `:205-228` (TdsCredit), `:233-247` (TcsCredit), `:249-257` (TaxChallan).

### A3. The bridge layer (the files you named)

The normalized draft **never touches the backend**. It is serialized back to the flat blob every time, and the backend re-parses it.

| File | Role | Reference |
|---|---|---|
| `legacyAdapter.ts` | flat blob → `ReturnDraft` | `frontend/src/domain/returns/legacyAdapter.ts:155` (`adaptLegacyReturn`) |
| `legacySerializer.ts` | `ReturnDraft` → flat blob | `frontend/src/domain/returns/legacySerializer.ts:13` (`serializeReturnDraftToLegacy`) |
| `editorModel.ts` | holds `{draft, extras}`, round-trips via `composeLegacyPayload` | `editorModel.ts:52-56`, `:65-67`, `:90-93` |
| `repository.ts` | save = serialize→flat→PUT; load = GET→adapt | `repository.ts:17-22`, `:27-33` |

> **Finding 1 (critical):** The normalized `ReturnDraft` is a write-only in-memory projection. Persisted as flat blob (`repository.ts:29`), loaded by re-adapting flat blob (`repository.ts:19`). Round-trip fidelity depends entirely on `legacyAdapter` ↔ `legacySerializer` being perfect inverses — and they are not (Part D).

---

## Part B — Actual ITR-1 Flow, Step by Step

### B1. Add Client → first-load seed

1. `POST /clients` → `clients.py` `create_client`. Stores `pan`, `name`, `dob` on `Client` table.
2. `GET /clients/{id}/itr/{year}` (`app/routers/client_itr.py:14-34`). When no `ClientITR` row exists, returns only client master fields (`name`, `pan`, `email`, `mobile`, `aadhaar`, `dob`) — `client_itr.py:27-33`. No `form`, no schedules.
3. Frontend `HttpReturnRepository.get` → `adaptLegacyReturn(data)` (`repository.ts:19`) → builds empty `ReturnDraft` seeded with personal info only.

### B2. Page load hydration (first round-trip)

`ITRComputationPage.tsx:506-525`:
- `createReturnEditorModelFromLegacy(emptyFormDataRef.current)` → empty editor.
- On `GET client + GET return`:
  - `createReturnEditorModelFromLegacy({...empty, ...composeLegacyPayload({draft, extras: {}})})` — merges empty draft with loaded, then composes back to flat to read fields.
  - `applyLegacyPatch(savedModel, {name, firstName, ..., pan, dob, age, address})` — overlays client master onto flat projection.
  - `editorRef.current = hydrated; setEditorModel(hydrated)`.

> **Finding 2 (design smell):** Load already incurs two full round-trips through the adapter (adapt → compose → adapt) before first render — `ITRComputationPage.tsx:520` then `:534-555`.

### B3. Every keystroke → compute (debounced)

1. `formData = useMemo(() => editorModel ? composeLegacyPayload(editorModel) : {}, [editorModel])` — `ITRComputationPage.tsx:566`.
2. `taxSummaryPayload = useMemo(() => ({ ...buildPhase1Payload(formData), form: itrForm }), [formData, itrForm])` — `:597`.
3. `useEffect` debounced 500ms → `itrApi.computeTaxSummary(...)` — `:615-640`.
4. `POST /tax-summary/compute?regime=...` with flat blob — `frontend/src/api/itr.ts:31-44`.
5. Backend `compute_tax_summary` → `_compute_tax_summary_impl(payload, regime, user)` — `app/routers/tax.py:352` (route), `:390` (impl).

> **Finding 3 (critical):** Flat blob recomputed on every keystroke (500ms debounce) — `ITRComputationPage.tsx:615`. Backend re-parses aliases, rebuilds `SalaryIncome`/`HousePropertyIncome`/`OtherSourcesIncome`/`Chapter6ADeductions` from scratch each call (`tax.py:391-478`). No typed input survives between frontend and backend.

### B4. Save

1. `handleSave` → `composeLegacyPayload(currentEditor)` → `buildPhase1Payload(snapshot)` — `ITRComputationPage.tsx:745-790`.
2. Manual zeroing of legacy aliases: `tdsS192=0, tds194A=0, tdsOther=0` (`:765-767`); `basic=0,da=0,hra=0,bonus=0` when `employerEntries` non-empty (`:772-776`); `s80G=0` when `donationEntries` non-empty (`:785`).
3. `itrApi.saveFormData(...)` → `PUT /clients/{id}/itr/{year}` — `frontend/src/api/itr.ts:9-12`.
4. Backend `save_client_itr` (`client_itr.py:37-71`): resolves form, persists `json.dumps(payload)` into `ClientITR.form_data`. **No validation, no schema enforcement** — `client_itr.py:62`.

> **Finding 4 (critical):** Save path manually zeroes legacy scalars based on which array is populated (`ITRComputationPage.tsx:765-785`) instead of one source of truth. Backend persists whatever JSON arrives (`client_itr.py:62`). This is why legacy aliases drift from arrays: a save zeroes `basic` but a later import sets it again, so both coexist and the backend's "first non-zero wins" (`_first_money`, `tax.py:410`) silently picks one.

### B5. Import — THREE different paths

#### Path 1: 26AS upload (inline, ~210 lines)
`ITRComputationPage.tsx:1141-1370`:
- Calls `integrationApi.import26AS` → backend `import_26as` (`integration.py:380-470`).
- Frontend hand-builds `employerEntriesFrom26AS`, `dividendEntriesFrom26AS`, `bankInterestEntriesFrom26AS`, `tdsEntriesForForm` — `:1195-1320`.
- Builds `formDataUpdate` with BOTH structured arrays AND legacy scalars (`interestSB`, `dividendShares`, `grossRent`, `ltcgProperty`, `bizTurnover`) — `:1355-1370`.
- `applyLegacyActionWithSnapshot(...)` → `saveFormData(..., applied.snapshot)` — `:1354-1358`.

#### Path 2: AIS/TIS upload (inline, ~650 lines)
`ITRComputationPage.tsx:1368-2050`:
- Calls `integrationApi.importAISJson` / `importTIS` → backend `import_ais_json` (`integration.py:209-290`) / `import_tis`.
- Hand-walks `aisData.income_heads`, splits B1 (TDS) vs B2 (SFT), dedupes, builds `allTdsEntries`, `b1InterestEntries`, `interestEntries` (B2), `dividendEntries`, `capitalGainTransactions`, `businessEntries` — `:1420-1990`.
- `formDataUpdate.capitalGainsSchedule = {...stImmovable, ltImmovable, ...}` — `:2010-2024`.
- Same apply+save pattern — `:2040-2043`.

#### Path 3: Portal automation (reconciled)
`ITRComputationPage.tsx:2050-2090`:
- `itrAutomationApi.startImport` → background `job_worker.py` downloads AIS/TIS/26AS/Prefill, calls `reconcile()` → `job.parsed_results: ReconciledResults`.
- Frontend `handleConfirmImport` → `mapReconciledToFormData(reconciledImportData)` — `:905`.
- Also calls `mapPrefillToFormData(prefillData)` — `:914`.
- Merge order `{...filedReturnUpdate, ...prefillUpdate, ...reconciledUpdate}` with empty-array preservation — `:960-975`.
- `applyLegacyActionWithSnapshot` + `saveFormData` — `:1068`.

> **Finding 5 (critical — the core complexity):** Three import paths produce three different `formDataUpdate` shapes in the same component:
> - Path 1 (26AS, `:1355`) sets `interestSB`, `interestFD`, `dividendShares` (scalars) + arrays.
> - Path 2 (AIS, `:1368-2050`) sets `interestEntries` with `itdTag` + `capitalGainsSchedule` + some scalars.
> - Path 3 (reconciled, `mapReconciledToFormData.ts:411-440`) sets `interestEntries` with `itdTag`, `bankInterestEntries` (legacy duplicate), `importedCategoryControls`, `capitalGainTransactions`.
>
> Each path calls a different backend endpoint returning a different shape. The frontend compensates with 850 lines of inline mapping.

> **Finding 6 (dead code in hot path):** `autoPopulateAll` backend endpoint (`integration.py:785-855`) is still wired (`ITRComputationPage.tsx:2060`) but the code above it says *"The autoPopulateAll backend endpoint only reads from TIS/26AS, not from the AIS summary. When only AIS is uploaded, it returns all zeros. Map the data directly here."* (`:1368-1371`). Backend endpoint exists, is called, known broken for AIS-only — frontend works around it with 650 inline lines.

### B6. Validate

1. `handleValidate` → `validatePhase1Payload` (client regex) — `ITRComputationPage.tsx:105-150`.
2. `itrApi.validate(...)` → `POST /clients/{id}/itr/{year}/validate` — `frontend/src/api/itr.ts:46-49`.
3. Backend `validate_client_itr` (`client_itr.py:74-120`): checks PAN/name/DOB, then **delegates to `compute_tax_summary`** (`client_itr.py:104-117`). Validation = "does compute accept it?"

> **Finding 7:** Validation is "run compute and see if it throws" (`client_itr.py:104-117`). The `/itr1/compute` route runs `itr1_input_val` + `itr1_calc_val` (`app/routers/itr.py:73-95`), but validate and save do not. A saved draft can be CBDT-invalid and only discover it at JSON-generation time.

### B7. Generate CBDT JSON

1. `handleGenerateCbdtJson` → `liveDraft = {...buildPhase1Payload(composeLegacyPayload(currentEditor)), form: itrForm, itrForm}` — `ITRComputationPage.tsx:846-848`.
2. `itrApi.generateCbdtJson(...)` → `POST /clients/{id}/itr/{year}/generate-cbdt-json` — `frontend/src/api/itr.ts:51-77`.
3. Backend `generate_client_cbdt_json` (`client_itr.py:122-170`): falls back to persisted `form_data` if no body, calls `generate_filing_artifact(flat_draft, user, db, include_official_json=True)` — `client_itr.py:153`.
4. `generate_filing_artifact` (`filing_gateway.py:83-180`):
   - **Step 1:** `compute_tax_summary(payload, regime, user)` — re-runs entire tax compute (`filing_gateway.py:119-157`). If compute fails, CBDT blocked.
   - **Step 2:** `_build_itr1_official_json(engine_payload, user)` (`:170`).
5. `_build_itr1_official_json` (`filing_gateway.py:185-225`):
   - `_build_itr1_input_from_flat(engine_payload)` → `ITR1Input` **WITH `ITR1FilingProfile`** (`filing_gateway.py:576-620`). (Contradicts stale MD docs — real code DOES build the profile.)
   - `_validate_itr1_cross_fields(typed_input)` — `filing_gateway.py:229-242`.
   - `compute_itr1(typed_input)` — `:215`.
   - `build_itr1_json(result, typed_input)` — `:219`.
   - `validate_itr1_json(itd_json)` — `:223`; schema loader at `app/engine/itd/itr1_schema.py:38-58`.

> **Finding 8 (redundancy):** `_build_itr1_input_from_flat` (`filing_gateway.py:461-760+`) re-implements the entire flat→typed mapping already in `app/routers/tax.py:390-1030` (`_compute_tax_summary_impl`). Gateway admits it: *"This is intentionally a thin, read-only mapping that mirrors the ITR-1 branch in `_compute_tax_summary_impl`."* (`filing_gateway.py:463-466`). Two ~300-line functions doing the same alias-parsing. When the compute mapping changes, CBDT mapping must change identically or they diverge.

> **Finding 9 (double compute):** CBDT pipeline calls `compute_tax_summary` **again** (`filing_gateway.py:119`) before building JSON, even though frontend already computed the same payload moments earlier (`ITRComputationPage.tsx:615`). Compute result not cached or reused.

---

## Part C — Import Mapper Proliferation

Five "map X to formData" utilities, each producing the flat-blob shape:

| Mapper | Input | Output | Reference |
|---|---|---|---|
| `mapReconciledToFormData` | `ReconciledResults` | flat `formDataUpdate` | `frontend/src/utils/mapReconciledToFormData.ts:411-470` |
| `mapPrefillToFormData` | `PrefillExtraction` dict | flat `formDataUpdate` | `frontend/src/utils/mapPrefillToFormData.ts:1-562` |
| `mapFiledReturnToFormData` | filed-return JSON | flat `formDataUpdate` | `frontend/src/utils/mapFiledReturnToFormData.ts:1-80` (**disabled** — `ITRComputationPage.tsx:41`, `:925-928`) |
| Inline 26AS mapper | 26AS parsed | flat `formDataUpdate` | `ITRComputationPage.tsx:1195-1370` |
| Inline AIS/TIS mapper | AIS `income_heads` | flat `formDataUpdate` | `ITRComputationPage.tsx:1368-2050` |

Plus 4 backend autopopulate endpoints doing the same server-side:
- `/integration/autopopulate/form16` (`integration.py:710-730`)
- `/integration/autopopulate/ais` (`integration.py:733-760`)
- `/prefill/autoPopulateAll` (`integration.py:785-855`) — known broken for AIS-only
- `/prefill/autopopulate` (`integration.py:860-925`)

> **Finding 10 (critical):** ~9 places map import data to the flat formData shape (5 frontend mappers + 4 backend autopopulate endpoints), each with its own field-naming conventions, each partially overlapping. `mapReconciledToFormData` produces `interestEntries` with `itdTag` (`:176`); inline AIS mapper produces `interestEntries` with `kind` (`ITRComputationPage.tsx:1420+`); `autoPopulateAll` produces `bankInterestEntries` only (`integration.py:830-834`). The legacy adapter reads both `kind` and `itdTag` (`legacyAdapter.ts` interest fn: `item.kind ?? item.itdTag`). This is why imports "sometimes work."

---

## Part D — Round-Trip Fidelity Bugs

Because the canonical draft is persisted as flat blob and re-parsed, any mismatch between `legacyAdapter` and `legacySerializer` is silent data-loss.

### D1. Interest `kind` vs `itdTag`
- Serialize (`legacySerializer.ts:46`): `interestEntries: ...map(x => ({...x, itdTag: x.kind}))` — writes `itdTag`.
- Adapt (`legacyAdapter.ts` interest fn): `kind: enumValue(item.kind ?? item.itdTag, ...)` — reads `kind` first then `itdTag`.
- Round-trip OK, but two canonical keys for the same field.

### D2. `bankInterestEntries` is display-only but persisted
- `legacySerializer.ts:47`: duplicates `interestEntries` under `bankInterestEntries`.
- `tax.py:521`: `interest_rows = _records(payload, "interestEntries") or _records(payload, "bankInterestEntries")` — reads either.
- `ITRComputationPage.tsx:786` comment: *"Do NOT zero interestSB/interestFD when bankInterestEntries exist. tax.py reads interestSB, interestFD... NOT bankInterestEntries. bankInterestEntries are for display/reference only."*

> **Finding 11 (critical):** Same interest data stored in three places (`interestEntries`, `bankInterestEntries`, `interestSB`/`interestFD` scalars). Rules about which the backend reads are encoded as code comments (`ITRComputationPage.tsx:786`), not a schema. Save handler (`:786`) refuses to zero scalars when array exists — proving team knows dual representation is dangerous but patched around it.

### D3. `composeLegacyPayload` merge order lets `extras` shadow canonical fields
- `editorModel.ts:65-67`: `composeLegacyPayload = mergeCompatibility(model.extras, serializeReturnDraftToLegacy(...))`.
- `mergeCompatibility` (`editorModel.ts:38-55`) deep-merges, overlay (serialized draft) winning over base (extras) at leaf level for records; arrays merge by `id`.

> **Finding 12:** `extras` (compatibility envelope for unknown fields, `editorModel.ts:52`) is preserved across edits and re-merged on every compose. Any unknown field that ever entered the blob survives indefinitely and can shadow canonical fields during deep merge. No expiry or cleanup.

### D4. `interestRD`, `nscInterest`, `scssInterest` have no array home
- These scalars are read by `tax.py:526-528` when `interestEntries` is empty.
- But `legacySerializer.ts:46` only emits `interestEntries` (no scalars) — once `interestEntries` is populated, the RD/NSC/SCSS scalars are gone from the persisted blob.
- On reload, `legacyAdapter.ts` interest fn only reads `grossAmount` per row; `kind=NSC`/`SCSS`/`TERM_DEPOSIT` carries the amount but the scalar aliases are permanently lost.

> **Finding 13 (data loss):** Saving a draft with `interestEntries` populated silently destroys `interestRD`/`nscInterest`/`scssInterest`/`postOfficeInterest`/`otherInterest` scalar values, because `legacySerializer.ts:46` doesn't emit them and `legacyAdapter.ts` doesn't restore them. A user who entered NSC interest as a scalar, then imported a bank interest entry, loses the NSC amount on next save.

---

## Part E — Backend's Flat-Blob Re-parsing Problem

Two independent flat→typed mappers must stay in sync:

| Mapper | Location | Purpose |
|---|---|---|
| `_compute_tax_summary_impl` | `app/routers/tax.py:390-1180` (~790 lines) | compute tax from flat blob |
| `_build_itr1_input_from_flat` | `app/engine/filing_gateway.py:461-760+` (~300 lines) | build typed `ITR1Input` for CBDT JSON |

Both:
- Parse `employerEntries` → `SalaryIncome` (`tax.py:391-411`, `filing_gateway.py:622-652`).
- Parse `housePropertyEntries` → `HousePropertyIncome` (`tax.py:486-516`, `filing_gateway.py:680-710`).
- Parse `interestEntries`/`bankInterestEntries` → interest scalars (`tax.py:521-528`, `filing_gateway.py:712-740`).
- Parse `tdsEntries` → `TDS1Entry`/`TDS2Entry` (`tax.py:762-810`, `filing_gateway.py:760+`).
- Parse `donationEntries` → `Donation80G` (`tax.py:623-660`, `filing_gateway.py:760+`).

> **Finding 14 (critical duplication):** Two ~300-790 line functions do the same alias parsing. `filing_gateway.py:463-466` explicitly says it "mirrors" `tax.py`. Not shared. A change to TDS parsing in `tax.py` must be manually replicated in `filing_gateway.py` or compute and CBDT-generation diverge. Single biggest source of "works in compute, fails in CBDT export" bugs.

> **Finding 15 (field-name guessing):** Both mappers use multi-alias `row.get("hra", row.get("hraReceived"))` (`tax.py:396`, `filing_gateway.py:628`) and `_first_money(prop.get("annualRent"), prop.get("annualLettingValue"), prop.get("grossRent"))` (`tax.py:505`, `filing_gateway.py:688`). `_first_money` exists because the frontend always serializes all keys (defaulting to 0), so `dict.get` with a default returns 0 and never reaches the real value (`tax.py:87-97` docstring). Direct consequence of dual representation — if there were one typed field, none of this guessing would be needed.

---

## Part F — Compute Endpoint's Form Inference

`_compute_tax_summary_impl` does not trust the frontend's `form` field for ITR-1 vs ITR-4:
- `is_itr4 = requested_form == "ITR-4" or bool(business_row) or biz_turnover > 0 or bp_profit > 0` (`tax.py:1036`).
- `computation_form = "ITR-4" if is_itr4 else "ITR-1"` (`:1039`).

If user selects "ITR-1" but has a `businessEntries` row, compute **silently uses ITR-4** (`tax.py:1036-1080`). Conversely, save endpoint (`client_itr.py:55-60`) persists the user's selected form exactly, ignoring business activity.

> **Finding 16 (inconsistency):** Save trusts the user's form selection (`client_itr.py:55-60`). Compute ignores it and re-infers from `bizTurnover` (`tax.py:1036`). Saved `itr_type` and computed `computation_form` can disagree. Frontend shows `computedByFormEngine` in result (`tax.py:1370`) but saved draft's `itr_type` is whatever the user picked.

---

## Part G — Eligibility Engine Running on Flat Data

`assessFormEligibility(formData, taxResult)` (`frontend/src/domain/eligibility.ts:120`) called on every render via `useMemo` (`ITRComputationPage.tsx:571-572`), and auto-switches the form unless locked (`:573-580`).

Reads flat scalars to derive facts:
- `hasSalary = m('basic') > 0 || employerEntries.length > 0` (`eligibility.ts:74`).
- `hasCapitalGains = m('stcgPre')>0 || m('ltcgPost')>0 || ...` (`:78-82`).
- `hasBusinessIncome = m('bizTurnover')>0 || m('bpNetProfit')>0` (`:84`).

> **Finding 17:** Eligibility engine reads flat scalars (`basic`, `bizTurnover`, `stcgPre`) — which the save handler zeroes when arrays are populated (`ITRComputationPage.tsx:765-785`). Eligibility facts depend on whether the user just saved (scalars zeroed) vs just imported (scalars set). Same draft can show different eligibility before and after a save.

---

## Part H — Redundancy Layers Summary

For one ITR-1 return, data passes through:

```
User input
  → component state (ITRComputationPage useState)         [layer 1]
  → updateEditor((model) => updateXxxFromManager(model))   [layer 2: manager→canonical, editorModel.ts:130-250]
  → editorModel.draft (ReturnDraft)                        [layer 3: canonical]
  → composeLegacyPayload (ReturnDraft → flat blob)         [layer 4: serialize, legacySerializer.ts]
  → buildPhase1Payload (flat blob → flat blob, zeroed)     [layer 5: patch, ITRComputationPage.tsx:57]
  → POST /tax-summary/compute                             [layer 6: HTTP]
  → _compute_tax_summary_impl (flat → typed ITR1Input)    [layer 7: tax.py:390+]
  → compute_itr1 (typed → ITR1Result)                     [layer 8: calculators/itr1.py]
  → response (flat JSON)                                  [layer 9: tax.py:1180+]
  → setBackendTaxResult                                    [layer 10]

For CBDT JSON, add:
  → _build_itr1_input_from_flat (flat → typed AGAIN)       [layer 7b: filing_gateway.py:461]
  → compute_itr1 AGAIN                                    [layer 8b: filing_gateway.py:215]
  → build_itr1_json (typed → CBDT JSON)                   [layer 11: itd/itr1.py]
  → validate_itr1_json (CBDT schema check)                [layer 12: itd/itr1_schema.py]
```

**12 transformation layers for one ITR-1 return, with 2 separate flat→typed mappers (layers 7 and 7b) that must stay manually in sync.**

---

## Part I — Priority Order

1. **Finding 14** — Unify the two flat→typed mappers. Highest risk: silent compute/CBDT divergence.
2. **Finding 13** — Data loss: `interestRD`/`nscInterest`/`scssInterest` scalars destroyed on save when `interestEntries` populated.
3. **Finding 11** — Triple representation of interest with comment-encoded rules.
4. **Finding 5** — Three import paths with three different `formDataUpdate` shapes.
5. **Finding 4** — Save zeroes legacy aliases conditionally instead of one source of truth.
6. **Finding 16** — Save trusts user form, compute re-infers it.
7. **Finding 17** — Eligibility reads flat scalars that save zeroes.
8. **Finding 8** — CBDT pipeline recomputes tax instead of reusing frontend's result.
9. **Finding 10** — 9 import-to-flat mappers; collapse to 5 typed FE, 0 BE.
10. **Finding 6** — `autoPopulateAll` known broken, still wired, worked around with 650 inline lines.

---

**Bottom line:** The complexity is structural, not accidental. The application carries two representations of ITR-1 data (flat blob + canonical draft) plus ~9 import mappers and 2 backend flat→typed mappers that must stay manually synchronized. The bridge files exist solely to shuttle between the two representations. Collapsing to one typed `ReturnDraft` — persisted as-is, computed from directly, CBDT-built from directly — eliminates ~60% of the ITR-1 codebase's complexity and removes the entire class of "round-trip fidelity" and "works in compute, fails in CBDT" bugs. ITR-2/3/4 then follow the same template.
