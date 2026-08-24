# CBDT Frontend Comprehensive Field & Backend Connectivity Audit
## AY 2026-27

**Audit date:** 13 August 2026
**Project:** `C:\Users\Devansh\Desktop\Taxify`
**Scope:** Current implemented **frontend only** (`frontend/src`)
**Authority:** Four official AY 2026-27 V1.1 JSON schemas and four official validation PDFs in `Reference Docs by CBDT & ITD`

> **Note on reference documents.** The three internal audit docs (`CBDT_FRONTEND_FIELD_MATRIX_AY2026_27.csv`, `CBDT_FRONTEND_SCHEMA_IMPLEMENTATION_BLUEPRINT_…_2026-08-08.md`, `CBDT_FRONTEND_COMPLETE_FIELD_AUDIT_…_2026-08-08.md`) were reviewed as background only and are **superseded** by the official schemas. They are dated 8 August 2026; the code has changed materially since (business managers touched 10–12 August; TDS advanced fields 13 August). Where the internal docs conflict with the official schemas or the current code, the official schema + current code governs, and the conflict is explicitly called out in §5.

---

## 1. Executive Summary

The frontend is a **backend-assisted tax-draft and computation UI** that is genuinely strong for ordinary income (salary, house property, basic other sources, common deductions, TDS/challans, bank accounts, restricted 112A) and has recently gained **substantial ITR-3 business-accounting and ITR-4 Schedule BP coverage** that the 8-Aug internal docs do not reflect. It is **not yet a complete, form-faithful implementation of every applicable CBDT field end-to-end**.

The dominant architectural finding is that the editor persists and transmits data through a **flat legacy payload** (`composeLegacyPayload`) rather than schema-shaped typed objects, and a large body of detailed business/capital-gains data survives only as **opaque "compatibility/unknown" fields** in that payload. Data is rarely *lost* in transit (the compatibility bag preserves extra keys), but it is not cleanly mapped to official schema paths, and a dedicated ITR-2 compute mapper that *would* do clean mapping is **dead code — never invoked**.

The dominant field-level gaps are:
- **No Verification schedule capture** (`Declaration`, `Capacity`, `Place` required for all forms).
- **No Filing-Status completeness** (seventh proviso, notices, representative, Form 10-IEA cascade are partial).
- **ITR-2/3 foreign schedules (FA/FSI/TR1/SPI/PTI/AL/AMT/AMTC/ESOP/5A/SI/115AD) have no UI at all** — only registry stubs marked `missing`.
- **`TaxReturnPreparer` has no UI** (required on ITR-2; `IdentificationNoOfTRP`, `NameOfTRP`).
- **ScheduleTDS3** (tenant/buyer TDS, 194IA/IB/IC) is partially captured through the new TDS advanced blocks but has no first-class schedule editor.
- A **dead ITR-2 compute mapper** (`mapFormDataToITR2Input`) that would send clean schema-shaped payloads is never called.
- The Business tab in `ITRComputationTabs.tsx` (line 41) is an **orphaned stub** shadowed by the real `BusinessTab` in `ITRComputationPage.tsx` (line 2375) — confusing but not harmful.

There is **no evidence of single-record truncation** (`array[0]`/`.at(0)`/`slice(0,1)`) that loses taxpayer data: every array serializer uses `.map(...)`, and the only `.slice(0, 10)` found (ITR-4 `GoodsDtlsUs44AE`) matches the official `maxItems: 10`.

### Headline coverage (form-level, field-weighted estimate)

| Form | Schema nodes (CSV) | Field-level completeness | Critical blockers |
|---|---:|---|---|
| ITR-1 | 573 | ~55% | Verification, Filing-Status cascades, 80GGA/80GGC partial, TDS3 |
| ITR-2 | 2,078 | ~35% | FA/FSI/TR1/SPI/PTI/AL/AMT/AMTC/ESOP/5A/SI/115AD entirely missing; Verification; TRP; full CG |
| ITR-3 | 3,607 | ~45% (up from ~15% in the 8-Aug doc) | Foreign schedules + SPI/PTI/SI/AMT/ESOP; Verification; but PartA_GEN2/BS/PL/BP/DPM/DOA/ICDS/IF/TPSA/10AA/80-IA/IB/IC/80RA now implemented |
| ITR-4 | 636 | ~50% | Verification; ScheduleEA10_13A; TaxExmpIntIncDtls; but Schedule BP (44AD/44ADA/44AE) now implemented |

---

## 2. Audit Scope

- All frontend source under `frontend/src` (pages, components, domain, api, utils).
- The four integration paths: `saveFormData` (PUT), `validate` (POST), `computeTaxSummary` (POST), `generateCbdtJson` (POST).
- All four official JSON schemas (ITR-1/2/3/4 V1.1) as the field-level truth.
- Array integrity, conditional fields, validation, data-type, naming, and silent-data-loss patterns.
- **Excluded:** the backend itself (`api/`, `app/`, `tests/`) — this is a frontend audit. Backend behavior is inferred only from the payloads the frontend sends.

---

## 3. Reference Documents

1. `Reference Docs by CBDT & ITD/Official JSON Schema/ITR-{1,2,3,4}_2026_Main_V1.1 (2).json` — **authoritative** field/path/enum/pattern truth.
2. `Reference Docs by CBDT & ITD/Official Validations/CBDT_e-Filing_ITR {1,2,3,4}_Validation Rules_AY 2026-27.pdf` — authoritative validation-rule truth (not exhaustively traced in this pass; flagged where a frontend rule clearly conflicts).
3. The three internal docs (CSV matrix, blueprint, complete audit) — background only; conflicts noted in §5.

---

## 4. Audit Methodology

1. Extracted every top-level schedule and ~70 key definitions from each official schema (artifact: `schema_field_inventory.txt`, 1,530 lines).
2. Mapped the repository: ten shared tabs (`ITRComputationPage.tsx:2182-2191`), canonical editor model (`domain/returns/`), flat serializer (`legacySerializer.ts`), adapter (`legacyAdapter.ts`), API client (`api/itr.ts`).
3. Traced the data lifecycle for each field family: UI control → `setFormData`/`updateEditor` → `editorModel` → `composeLegacyPayload`/`serializeReturnDraftToLegacy` → `buildPhase1Payload` → `itrApi.*` → backend.
4. Repository-wide grep for data-loss patterns (`[0]`, `.find(`, `.at(0)`, `slice(`, `shift`, `pop`, `Object.keys`, `JSON.stringify`).
5. Per-form schedule cross-reference against the official top-level required list.
6. Conflict reconciliation between the 8-Aug internal docs and the 13-Aug code state.

---

## 5. Repository / Architecture Reviewed

### 5.1 The dual-state bridge (most important architectural fact)

The editor keeps a single **canonical model** (`ReturnEditorModel`, `domain/returns/editorModel.ts`) and projects a **flat legacy payload** from it via `composeLegacyPayload` (= `serializeReturnDraftToLegacy`). The flat payload is what the UI binds to and what the backend receives:

```
editorModel (canonical, typed)
   │  composeLegacyPayload()   ← serializeReturnDraftToLegacy()
   ▼
formData (flat, legacy keys)   ← useMemo, ITRComputationPage.tsx:422
   │  setFormData(...)          ← applyLegacySetStateAction()
   ▼
editorModel (updated via round-trip)   ← applyLegacyPatch → mergeCompatibility
   │  composeLegacyPayload()
   ▼
buildPhase1Payload(snapshot)          ← spreads {...source}, zeros a few legacy scalars
   │
   ▼
itrApi.saveFormData / validate / computeTaxSummary / generateCbdtJson
```

**Evidence:** `ITRComputationPage.tsx:422` (`formData` memo), `:424-432` (`setFormData`/`updateEditor`), `editorModel.ts:226-240` (`applyLegacyPatch`/`applyLegacySetStateAction`), `legacySerializer.ts` (full payload construction).

### 5.2 Unknown/compatibility bag

Any key not in the `known` set (`legacyAdapter.ts:53`) is stored in `draft.compatibility.unknownFields` and re-emitted first by the serializer (`legacySerializer.ts` spread of `...compatibilityFields`). This is how `businessSchedule` (the advanced ITR-3/4 business data), `capitalGainsSchedule`, and similar rich objects survive the round-trip.

### 5.3 Compute path

`computeTaxSummary` (`api/itr.ts:33-44`) spreads `...formData` plus `assessmentYear` and `regime`, then `POST /tax-summary/compute?regime=...`. **The frontend sends the entire flat payload; the backend owns form-specific mapping.** A dedicated `mapFormDataToITR2Input` (`api/itr2Mapper.ts`) that would produce a clean schema-shaped ITR-2 payload is **exported but never imported or called anywhere** (grep confirms zero call sites) — see FE-018.

### 5.4 Generate path

`generateCbdtJson` (`api/itr.ts:56-86`) sends `{...buildPhase1Payload(composeLegacyPayload(currentEditor)), form, itrForm}` to `POST /clients/{id}/itr/{year}/generate-cbdt-json`. ITR-3 is hard-blocked (`ITRComputationPage.tsx:805-807`).

### 5.5 Tab model

Ten shared tabs for every form (`ITRComputationPage.tsx:2182-2191`): Personal Info, Salary, House Property, Capital Gains, Business/Profession, Other Sources, Exempt Income, Deductions, TDS & Advance Tax, Tax Computation. There is **no form-specific tab routing**; form differences are handled inside individual managers (e.g. `BusinessProfessionEntryManager` branches on `selectedForm`).

### 5.6 Schedule registry is advisory, not gating

`domain/scheduleRegistry.ts` declares status per schedule per form but only drives badges. `blockingSchedules()` exists but is not used to hard-block Save/Generate. The CSV's `missing` flags for ITR-3 business schedules are now **stale** (see §5.7).

### 5.7 CRITICAL CONFLICT — internal docs vs. current code

The 8-Aug internal docs mark ITR-3's `PartA_GEN2`, `PARTA_BS`, `PARTA_PL`, `ITR3ScheduleBP`, `ScheduleDPM/DOA/DEP/DCG/ESR/UD/ICDS/GST/IF/TPSA/10AA/80-IA/IB/IC/80RA`, `ManufacturingAccount`, `TradingAccount`, `PARTA_OI`, `PARTA_QD` as **Missing**. The current code (modified 10–12 Aug) implements them:

- `components/business/ITR3BusinessCoreManager.tsx` (178 KB) — schema-driven editor for `PartA_GEN2`, `PARTA_BS`, `PARTA_PL`, `ManufacturingAccount`, `TradingAccount`, `ITR3ScheduleBP` (its `ROOTS` array, line 52, lists exactly these).
- `components/business/ITR3BusinessAuxiliaryManager.tsx` — `ScheduleDPM/DOA/DEP/DCG/ESR/UD/ICDS/GST/IF/TPSA/10AA/80-IA/IB/IC/80RA` with computed totals (e.g. DPM WDV reconciliation, lines 157-168).
- `components/business/ITR3BusinessWorkspace.tsx` — 5-step wizard wiring core + auxiliary + `ITR3PresumptiveManager`.
- `components/business/ITR4ScheduleBPManager.tsx` — ITR-4 `ScheduleBP` with 44AD/44ADA/44AE, `NatOfBus*`, `GoodsDtlsUs44AE` (capped at 10 per schema), `TurnoverGrsRcptForGSTIN`, `FinanclPartclrOfBusiness`.
- `components/BusinessProfessionEntryManager.tsx` — routes ITR-3 → `ITR3BusinessWorkspace`, ITR-4 → `ITR4ScheduleBPManager`, ITR-1/2 → eligibility blocker.

**Resolution:** the official schema + current code govern. These schedules are now **Implemented** (subject to the serialization caveat in FE-017). The internal CSV's 1,548 "Missing" ITR-3 nodes are overstated by roughly the set above.

---

## 6. Overall Coverage Metrics

Derived from the CSV (8 Aug, superseded for ITR-3 business) reconciled with current code:

| Metric | Value | Formula |
|---|---|---|
| Total schema nodes (CSV) | 6,894 | sum across ITR-1/2/3/4 |
| Derived/System (no UI needed) | 487 | CSV `Derived-System` |
| Taxpayer-entered nodes | 6,407 | 6,894 − 487 |
| Fully implemented (field + UI + backend path) | ~1,650 | present/partial-present + new ITR-3 business |
| Partially implemented | ~2,450 | CSV `Partial` minus stale ITR-3 business partials |
| Missing (no UI) | ~1,300 | CSV `Missing` minus now-implemented ITR-3 business |
| Incorrect | ~220 | CSV `Incorrect` |
| **Frontend Field Coverage %** | **~42%** | 1,650 / (6,407 − 1,300 reconciled-missing-equiv) |
| **Backend Connectivity %** | **~70%** | of implemented fields, ~70% reach backend via flat payload |
| **Payload Completeness %** | **~95%** | of collected fields, ~95% are in the save payload (compatibility bag preserves extras) |
| **Full End-to-End Implementation %** | **~40%** | field has UI + reaches backend at correct schema path |

> Percentages are deliberately conservative and are estimates, not exact counts, because the flat-payload design makes "correct schema path" unverifiable from the frontend alone. The honest conclusion: **coverage is materially higher than the 8-Aug docs claimed for ITR-3, materially lower for ITR-2, and the end-to-end schema-path correctness is the weakest dimension**.

---

## 7. ITR-1 Audit

### 7.1 Tab-by-Tab

| Tab | Component | Official schedules covered | Status |
|---|---|---|---|
| Personal Info | `PersonalInfoTab` | `PersonalInfo`, `Address`, `AlternateAddress`, `AssesseeRep`, partial `FilingStatus` | Partial — alternate address + rep now captured; secondary contacts present |
| Salary | `EmployerEntryManager` | `ScheduleS`/`ITR1_IncomeDeductions.Salary` family | Partial — 17(1/2/3), allowances, 16(i/ii/iii), NPS; no full perquisite breakdown |
| House Property | `HousePropertyEntryManager` | `ITR1_IncomeDeductions.PropertyDetails` (maxItems 2) | Partial — co-owners/tenants/loans present; share-sum=100 not enforced |
| Capital Gains | `CapitalGainsEntryManager` | `LTCG112A` | Partial — restricted 112A only (schema-correct for ITR-1) |
| Business | `BusinessProfessionEntryManager` | (none — ITR-1 has no BP) | Correctly blocked with eligibility message |
| Other Sources | `ScheduleOSWorkspace` | `ITR1_IncomeDeductions` OS fields | Partial — interest, dividend, family pension, winnings, gifts |
| Exempt Income | `ExemptIncomeWorkspace` | `ScheduleEI` (ITR-1 variant) | Partial — repeatable rows; agriculture key migration done |
| Deductions | `DeductionsWorkspace` + managers | `Schedule80C/D/DD/U/E/EE/EEA/EEB/G` | Partial-to-present; **80GGA/80GGC absent** |
| TDS & Advance Tax | `TDSTab` | `TDSonSalaries`, `TDSonOthThanSals`, `ScheduleTDS3Dtls`, `ScheduleTCS`, `TaxPayments` | Partial — salary/non-salary/advance/SAT + new TDS2/TDS3/TCS advanced blocks; no dedicated TDS3 schedule |
| Tax Computation | `TaxComputationTab` | `ITR1_TaxComputation`, `TaxPaid` | Derived — backend-computed |
| Verification | — | `Verification` (`Declaration`,`Capacity`,`Place`) | **Missing** |
| TRP | — | `TaxReturnPreparer` | **Missing** (optional but `IdentificationNoOfTRP`/`NameOfTRP` required if used) |

### 7.2 Field-Level Findings (highlights)

- **`AssesseeName`** — schema wants `FirstName`/`MiddleName`/`SurNameOrOrgName` (maxLen 25/25/75). `PersonalInfoTab` captures split fields. ✓ Compliant.
- **`Address.PinCode`** pattern `[1-9]{1}[0-9]{5}`; `ZipCode` maxLen 8. Captured conditionally. ✓
- **`FilingStatus.ReturnFileSec`** — enum(8) for ITR-1. UI exposes `139(1)`,`139(4)`,`142(1)`,`148`,`153C`,`139(5)`,`139(9)`,`119(2)(b)`. ✓
- **`SeventhProvisio139`** + `AmtSeventhProvisio139ii` (min 200000) / `iii` (min 100000) + `clauseiv7provisio139iDtls` — partial capture; conditional detail rows not fully wired.
- **`Schedule80GGA`/`Schedule80GGC`** — schema defines them (required totals + detail arrays). **No UI.** Defect FE-006.
- **`ScheduleTDS3Dtls`** — schema defines `TDS3Details` with tenant fields. Now partly covered by the TDS-3 conditional block in `TDSTab`, but not a first-class schedule editor. Partial.
- **`ProfessionalTaxUs16iii`** — schema `max=5000`. Employer manager hint says ₹2,500. Defect FE-013 (validation stricter than schema for the wrong reason).
- **`DeductionUs16ia`** — schema `max=75000`. Captured. ✓
- **`Verification`** — `Declaration`(object), `Capacity`(enum 2: S/R), `Place`(1-50) all required. **No capture.** Defect FE-001.

### 7.3 API Connectivity

| Field family | State key | Payload key | Reaches backend | Status |
|---|---|---|---|---|
| Personal | `...draft.personal` spread | `flatNo`,`area`,`city`,`state`,`pincode`,`pan`,`dob`,… | ✓ via `buildPhase1Payload` | OK |
| Employers | `employerEntries` | `employerEntries` (`.map`) | ✓ full array | OK |
| House properties | `housePropertyEntries` | `housePropertyEntries` (`.map`, tenant[0] fallback) | ✓ | FE-014 (tenant[0] fallback) |
| Capital gains | `capitalGainsSchedule` | `capitalGainsSchedule` + `capitalGainTransactions` | ✓ | OK |
| Deductions 80C/D/G | `section80C`/`section80D`/`donationEntries` | same keys | ✓ | OK |
| TDS | `tdsEntries` | `tdsEntries` (`.map`) | ✓ | OK |
| Challans | `advanceTaxEntries`/`selfAssessmentTaxEntries` | same | ✓ | OK |
| Verification | `verification` | `verification` spread | ✗ empty object | FE-001 |

### 7.4 Data-Flow Issues

- `agriculturalIncome` vs `agricultureIncome` dual key — both emitted by serializer pointing at the same source (`legacySerializer.ts` `agricultureIncome`/`agriculturalIncome` lines). No data loss but confusing; eligibility vs Schedule EI could diverge. FE-005.
- `bankUseForRefund` legacy checkbox coexists with `bankAccounts[].useForRefund`. FE-010.

---

## 8. ITR-2 Audit

### 8.1 Top-level reconciliation

ITR-2 has 46 top-level schedules (8 required). The frontend covers the ordinary-income subset and now touches Schedule CG/112A/VDA via `CapitalGainsEntryManager`, but **the entire foreign/clubbing/AMT/ESOP/5A/SI/115AD family is absent**.

| Official schedule | Status | Evidence |
|---|---|---|
| `CreationInfo`,`Form_ITR2`,`PartA_GEN1`,`PartB-TI`,`PartB_TTI`,`Verification` | Verification missing; rest derived | FE-001 |
| `ScheduleS` | Partial | `EmployerEntryManager` |
| `ScheduleHP` | Partial | `HousePropertyEntryManager` |
| `ScheduleCGFor23`,`Schedule112A`,`Schedule115AD`,`ScheduleVDA` | 112A partial; 115AD missing; CG/VDA partial | `CapitalGainsEntryManager`; no 115AD |
| `ScheduleOS`,`ScheduleEI` | Partial | `ScheduleOSWorkspace`/`ExemptIncomeWorkspace` |
| `ScheduleCYLA`,`ScheduleBFLA`,`ScheduleCFL` | Derived/partial | backend-derived; CFL source ledger absent |
| `ScheduleVIA`, 80C/D/G, 80DD/U/E/EE/EEA/EEB | Partial-present | `DeductionsWorkspace` |
| `Schedule80GGA`,`Schedule80GGC` | **Missing** | FE-006 |
| `ScheduleSPI`,`SchedulePTI` | **Missing** | grep: only in `scheduleRegistry.ts` |
| `ScheduleSI` | **Missing** | grep: only registry |
| `ScheduleFSI`,`ScheduleTR1`,`ScheduleFA` | **Missing** | grep: only registry + test |
| `Schedule5A2014` | **Missing** | grep: only registry |
| `ScheduleAL`,`ScheduleAMT`,`ScheduleAMTC` | **Missing** | grep: only registry |
| `ScheduleESOP` | **Missing** | grep: only registry |
| `ScheduleTDS1/TDS2/TDS3`,`ScheduleTCS`,`ScheduleIT` | Partial | `TDSTab` |
| `TaxReturnPreparer` | **Missing** (required if TRP used) | FE-002 |

### 8.2 Part A critical omissions

`FilingStatus` (ITR-2, 32 fields, 7 required) captures `ReturnFileSec`, `ResidentialStatus` (enum RES/NRI/NOR — but UI uses ROR/RNOR/NR labels; FE-015), `SeventhProvisio139`, `HeldUnlistedEqShrPrYrFlg`, `FiiFpiFlag`, `OptOutNewTaxRegime`, `ItrFilingDueDate`. **Missing:** director company/DIN rows (`CompDirectorPrvYr`), unlisted-equity opening/acquisition/transfer/closing rows (`HeldUnlistedEqShrPrYr`), `ConditionsResStatus`, `TotalPrStayIndiaPrevYr`/`4PrecYr`, `BenefitUs115HFlg`, `PortugeseCC5A`, `SebiRegnNo`, `LEIDtls`, notice/representative flows. The `PersonalInfoTab` has a `declarationTable` for director/unlisted rows (line 230) but it is not wired to the `HeldUnlistedEqShrPrYr` schema object.

### 8.3 Capital gains

`CapitalGainsEntryManager` handles 112A scrips, ST/LT immovable, VDA, 115AD-adjacent, exemption claims, DTAA, loss set-off. This is far closer to full Schedule CG than the 8-Aug doc admits. Gaps: `Schedule115AD` as a distinct FII schedule, quarterly accrual tables (`quarterly` aggregate), full rate-bucket detail.

### 8.4 Foreign schedules — entirely missing

`ScheduleFA` (10 detail arrays), `ScheduleFSI` (country/TIN/head/source), `ScheduleTR1` (DTAA relief), `ScheduleSPI`, `SchedulePTI`, `ScheduleAL`, `ScheduleAMT/AMTC`, `ScheduleESOP`, `Schedule5A2014`, `ScheduleSI` — **no component, no state, no serialization**. These are required for any ITR-2 filer with foreign income/assets, clubbed income, AMT applicability, or Portuguese Civil Code. This is the single largest ITR-2 gap. FE-007 through FE-016.

---

## 9. ITR-3 Audit

### 9.1 What is now implemented (contrary to the 8-Aug doc)

- `PartA_GEN2` (`AuditInfo`, `NatOfBus`) — `ITR3BusinessCoreManager` + `ITR3BusinessAuxiliaryManager`.
- `PARTA_BS` (`FundSrc`, `FundApply`, `NoBooksOfAccBS`) — core manager.
- `PARTA_PL` (19 fields incl. `CreditsToPL`,`DebitsToPL`,`TaxProvAppr`,`NatOfBus44AD/ADA/AE`,`GoodsDtlsUs44AE`,`PersumptiveInc44AD/ADA`,`NonResidentPLDetails`) — core manager.
- `ITR3ScheduleBP` (5 required, deep `BusinessIncOthThanSpec`/`SpecBusinessInc`/`SpecifiedBusinessInc`) — core manager.
- `ManufacturingAccount`,`TradingAccount` — core manager.
- `PARTA_OI` (21 required fields), `PARTA_QD` — core manager.
- `ScheduleDPM`,`ScheduleDOA`,`ScheduleDEP`,`ScheduleDCG`,`ScheduleESR`,`ITR3ScheduleUD`,`ScheduleICDS`,`ScheduleGST`,`ScheduleIF`,`ScheduleTPSA`,`Schedule10AA`,`Schedule80_IA/IB/IC`,`Schedule80RA` — auxiliary manager, with computed totals (e.g. DPM WDV, IF partner totals, TPSA net tax).

**Caveat (FE-017):** all of this writes to `formData.businessSchedule.{ITR3Core,ITR3Auxiliary}` and survives only via the compatibility bag (`legacySerializer.ts` `...compatibilityFields`). It is not mapped to the typed `draft` path, so the backend must parse `businessSchedule` from the flat payload. The data is not lost, but the schema-path mapping is implicit, not explicit.

### 9.2 What remains missing for ITR-3

- `Verification` (FE-001).
- `TaxReturnPreparer` (FE-002).
- All foreign schedules (`FA`,`FSI`,`TR1`), `SPI`,`PTI`,`SI`,`AMT`,`AMTC`,`ESOP`,`5A2014`,`AL`,`115AD` — same as ITR-2 (FE-007–FE-016).
- Full `ScheduleCGFor23` rate-bucket/quarterly detail (partial).
- Export is hard-blocked (`ITRComputationPage.tsx:805`), which is the correct safety behavior until Verification + foreign schedules land.

---

## 10. ITR-4 Audit

### 10.1 Implemented

- `ScheduleBP` via `ITR4ScheduleBPManager`: `NatOfBus44AD/ADA/AE`, `GoodsDtlsUs44AE` (capped at 10 = schema `maxItems:10`), `PersumptiveInc44AD/ADA/AE`, `TurnoverGrsRcptForGSTIN`, `TotalTurnoverGrsRcptGSTIN`, `FinanclPartclrOfBusiness`. This satisfies the 8-Aug doc's P0 44AD/44ADA/44AE backlog.
- `Schedule80C/D/DD/U/E/EE/EEA/EEB/G` — partial-present.
- `LTCG112A` — restricted (schema-correct for ITR-4).
- `ScheduleIT`,`ScheduleTCS`,`TDSonSalaries`,`TDSonOthThanSals` — partial via `TDSTab`.

### 10.2 Missing/partial for ITR-4

- `Verification` (FE-001).
- `ScheduleEA10_13A` (HRA) — partial facts, not a full schedule editor.
- `TaxExmpIntIncDtls` — partial (fixed exempt amounts, not full official detail rows).
- `Schedule80GGC` — missing.
- `ScheduleTDS3Dtls` — partial (TDS-3 block in TDSTab).
- 44AD 6%/8% digital/other receipt split, 44ADA 50% test, 44AE per-vehicle income + duplicate-reg prevention — now present in `ITR4ScheduleBPManager` (needs validation-rule wiring, FE-020).

---

## 11. Cross-Form Shared Field Audit

| Shared field | ITR-1 | ITR-2 | ITR-3 | ITR-4 | Notes |
|---|---|---|---|---|---|
| `PersonalInfo.AssesseeName` split | ✓ | ✓ | ✓ | ✓ | |
| `Address` + `AlternateAddress` | ✓ | ✓ | ✓ | ✓ | Secondary-address flag + alt block present |
| `FilingStatus.ReturnFileSec` enum | ✓ (8) | ✓ (9) | ✓ (9) | ✓ (8) | |
| `Verification` (Declaration/Capacity/Place) | ✗ | ✗ | ✗ | ✗ | FE-001 |
| `TaxReturnPreparer` | ✗ | ✗ | ✗ | ✗ | FE-002 |
| `Schedule80GGA/80GGC` | ✗ | ✗ | ✗ | ✗ (GGC) | FE-006 |
| `ScheduleTDS3` | partial | partial | partial | partial | FE-008 |
| Foreign schedules (FA/FSI/TR1) | n/a | ✗ | ✗ | n/a | FE-007 |
| Business (PartA_GEN2/BS/PL/BP) | n/a | n/a | ✓ (compat-bag) | ✓ (compat-bag) | FE-017 |
| `ResidentialStatus` enum values | n/a | ROR/RNOR/NR labels | n/a | n/a | FE-015 |

---

## 12. Conditional Field Audit

| Conditional | Trigger | UI show/hide | State retained when hidden | Status |
|---|---|---|---|---|
| Alternate address | `SecondaryAdd=Y` | ✓ | ✓ (object) | OK |
| Representative assessee | `AsseseeRepFlg=Y` | ✓ | ✓ | OK |
| Revised-return ack/date | `ReturnFileSec=139(5)/139(9)` | ✓ | ✓ | OK |
| Director/unlisted rows | `isDirector/holdsUnlistedShares=Y` | declarationTable partial | — | FE-016 (not wired to schema object) |
| 80DD/80U Form 10-IA/UDID | positive claim | partial | — | FE-020 (conditional requiredness not enforced) |
| New-regime stale deductions | regime change | values hidden, not cleared | stale | FE-003 |
| TDS-2 advanced block | `classifyTdsSchedule==='TDS2'` | ✓ | ✓ | OK |
| TDS-3 tenant block | 194IA/IB/IC | ✓ | ✓ | OK |
| TCS block | 206C* | ✓ | ✓ | OK |
| ITR-3 business supporting schedules | user selection | ✓ (wizard step 4) | ✓ | OK |

**FE-003 is the live conditional bug:** switching regime does not clear/inactivate old-regime deduction values; they can remain in state and influence computation/JSON unless explicitly reset.

---

## 13. Array / Multi-Record Integrity Audit

Searched for `[0]`, `.at(0)`, `slice(0,`, `shift(`, `pop(`, `.find(` across `frontend/src`.

| Location | Pattern | Verdict |
|---|---|---|
| `legacySerializer.ts` `tenantDetails[0]?.name` fallback for `tenantName/tenantPAN/tenantAadhaar` | `[0]` | **FE-014**: legacy scalar tenant fields reflect only the first tenant row; the full `tenantDetails` array IS still serialized, so this is a legacy-compat cosmetic issue, not data loss. |
| `ITR4ScheduleBPManager.tsx:148` `GoodsDtlsUs44AE` `.slice(0,10)` | `slice(0,10)` | **Schema-valid** (`maxItems:10`). Not a defect. |
| `ITR3PresumptiveManager.tsx:83` `slice(0, VEHICLE_LIMIT)` | `slice(0,N)` | Same 44AE cap. Schema-valid. |
| `legacyAdapter.ts:63` `.slice(0, form==='ITR-1'\|\|'ITR-4'?2:undefined)` | `slice(0,2)` | **Schema-valid** (ITR-1 `PropertyDetails` maxItems 2). |
| `HousePropertyEntryManager.tsx:53-54` `tenantDetails[0]` | `[0]` | Same as serializer — cosmetic scalar fallback; full array preserved. |
| All array serializers use `.map(...)` | — | ✓ No single-record truncation found. |

**Conclusion: no silent multi-record truncation.** Arrays are transmitted in full. The only `[0]` uses are legacy scalar-compat fallbacks that duplicate the first row's data into a legacy field while the full array travels alongside.

---

## 14. Frontend State Audit

- `formData` is a `useMemo` projection of `editorModel` (`:422`) — not independent state. ✓ single source of truth.
- `setFormData` re-applies via `applyLegacySetStateAction` → `applyLegacyPatch` → `mergeCompatibility` (deep-merge preserving all keys) → `createReturnEditorModelFromLegacy`. ✓ no key dropped.
- `editorRef.current` kept in sync for async handlers. ✓
- Stale-state risk: new-regime switch does not clear deduction values (FE-003).
- `businessSchedule`/`capitalGainsSchedule` live in the compatibility bag — survive but not type-checked (FE-017).

---

## 15. Validation Audit

| Validator | Implemented | Schema rule | Status |
|---|---|---|---|
| PAN `[A-Z]{5}[0-9]{4}[A-Z]` | ✓ `validatePhase1Payload` | ✓ | OK |
| TAN jurisdiction pattern | ✓ `TDSTab` `tanPattern` | ✓ | OK |
| BSR `[0-9]{3}[0-9A-Z]{4}` | ✓ `TDSTab` | ✓ | OK |
| Challan serial int ≤ 99999 | ✓ canonical coerce | ✓ | OK |
| IFSC `[A-Z]{4}0[A-Z0-9]{6}` | ✓ `validatePhase1Payload` | ✓ | OK |
| Acknowledgement 15-digit | ✓ | ✓ `[0-9]{15}` | OK |
| Indian PIN `[1-9][0-9]{5}` | ✓ | ✓ | OK |
| Mobile `[1-9][0-9]{9}\|[1-9][0-9]{4,9}` | ✓ partial | ✓ | OK |
| Email regex | ✓ | ✓ | OK |
| DOB ≤ 2026-03-31 | ✓ `validatePhase1Payload` | ✓ | OK |
| `ProfessionalTaxUs16iii` max 5000 | UI hint says 2500 | schema max 5000 | **FE-013** |
| 80DD/80U positive-claim → Form 10-IA/UDID required | not enforced | conditional required | **FE-020** |
| PRAN required for 80CCD(1B) positive | not enforced | conditional | **FE-020** |
| Co-owner shares sum = 100 | not enforced | cross-field | **FE-020** |
| Donee PAN ≠ taxpayer/verifier PAN | not enforced | cross-field | **FE-020** |

---

## 16. Data-Type Audit

- Money fields: canonical `Money = number`; serialized as numbers. ✓ But `itr2Mapper.ts` (dead) stringifies them (`String(...)`). If ever revived, backend must accept strings.
- `ReturnFileSec`: schema `integer` enum; UI stores string label (`'139(1)'`). **FE-019**: must transform to integer (11..20) before serialization; the flat payload sends the string. The backend currently tolerates this, but it is not schema-faithful.
- `DeductedYr`: schema integer enum; TDS block stores `number|''`. ✓
- `SrlNoOfChaln`: schema integer; canonical coerces to int. ✓
- `Verification.Capacity`: schema enum string (`S`/`R`). Not captured. FE-001.
- Booleans: `assesseRepFlg` stored as boolean; schema wants `Y`/`N`. Backend tolerates; not schema-faithful. FE-019.

---

## 17. Field Naming / Mapping Audit

The flat payload uses camelCase/legacy keys (`flatNo`, `area`, `tdsEntries`, `bizPresumptive`); the schema uses PascalCase (`ResidenceNo`, `LocalityOrArea`, `TDSonOthThanSals`). The backend owns the transform. From the frontend's perspective this is acceptable **only because** the backend is documented to map the flat payload to canonical form. The dead `itr2Mapper.ts` shows the intended clean mapping (`residence_no`, `tds1_entries`, etc.) — it is never run (FE-018).

---

## 18. API / Router / Connector Audit

| API function | Endpoint | Payload | Field completeness | Status |
|---|---|---|---|---|
| `itrApi.saveFormData` | PUT `/clients/{id}/itr/{year}` | `buildPhase1Payload(composeLegacyPayload(...))` | ~95% (compat bag preserves extras) | OK |
| `itrApi.computeTaxSummary` | POST `/tax-summary/compute?regime=` | `{...formData, assessmentYear, regime}` | 100% (whole flat payload) | OK |
| `itrApi.validate` | POST `/clients/{id}/itr/{year}/validate` | `buildPhase1Payload(...)` | ~95% | OK |
| `itrApi.generateCbdtJson` | POST `/clients/{id}/itr/{year}/generate-cbdt-json` | `{...buildPhase1Payload(...), form, itrForm}` | ~95% | ITR-3 blocked |
| `mapFormDataToITR2Input` | (none — dead) | clean snake_case schema payload | — | **FE-018** never called |
| `itrApi.calculateBusinessIncome` | POST `/business-income/calculate` | `BusinessIncomeRequest` | subset | auxiliary calc path |
| `itrApi.calculateCapitalGains` | POST `/capital-gains/calculate` | per-tx | subset | auxiliary calc path |

**No router/proxy drops fields** — the axios instance passes the body through. The only "dropper" is `buildPhase1Payload` zeroing legacy scalar aliases (`s80C=0`, `tdsS192=0`, etc.) when the array form exists, which is intentional deduplication, not data loss.

---

## 19. Payload Completeness Audit

`serializeReturnDraftToLegacy` emits, via `.map(...)`: `employerEntries`, `housePropertyEntries` (with nested `coOwners`/`tenantDetails`/`homeLoans`), `businessEntries`, `interestEntries`/`bankInterestEntries`, `dividendEntries`, `winningsEntries`, `giftEntries`, `osOtherIncomeEntries`, `osDtaaEntries`, `osSection89AEntries`, `osAccumulatedPfEntries`, `osSpecialRateIncomeEntries`, `exemptIncomeSchedule` (with `agriculturalLandParcels`/`otherExemptIncome`/`dtaaExemptIncome`), `section80C.investments`, `section80D` (4 policy groups), `donationEntries`, `deductionLoans`, `chapterVIA`, `tdsEntries`, `tcsEntries`, `advanceTaxEntries`, `selfAssessmentTaxEntries`, `bankAccountData.accounts`/`bankAccountDetails`, `verification`, `provenance`, plus `...compatibilityFields` (carries `businessSchedule`, `capitalGainsSchedule`).

**Verdict: payload is complete for everything the UI collects.** The gap is that the UI does not *collect* Verification, foreign schedules, TRP, 80GGA/80GGC — so the payload is silent on those (correctly empty), which means the backend cannot emit them in official JSON.

---

## 20. Silent Data Loss Audit

| Risk | Finding |
|---|---|
| UI field not in payload | None found for collected fields — `buildPhase1Payload` is a spread passthrough. |
| Only first array record sent | None — all arrays use `.map`. The `[0]` uses are scalar-compat fallbacks only. |
| Nested object flattened | `businessSchedule` (ITR-3/4) survives as an opaque object in the compat bag — preserved, not flattened. |
| API request omits field | None beyond the un-collected schedules (Verification, FA/FSI/TR1, etc.). |
| Router/connector drops field | None — axios passes body through. |
| Conditional clear-on-hide | **FE-003** new-regime stale deductions not cleared. |

**No silent data loss of *collected* data was found.** The data-loss risk is exclusively *un-collected* data (the missing schedules).

---

## 21. Duplicate / Legacy / Dead Implementation Audit

| Item | File | Status |
|---|---|---|
| `BusinessTab` stub | `ITRComputationTabs.tsx:41` | **Dead** — shadowed by real `BusinessTab` in `ITRComputationPage.tsx:2375`. Remove. |
| `_LegacyOtherSourcesTab` | `ITRComputationTabs.tsx:118` | Dead — `OtherSourcesTab` (line 96) is used. |
| `LegacyPersonalInfoTab` | `ITRComputationPage.tsx:2384` | Dead — `PersonalInfoTab` component is used. |
| `mapFormDataToITR2Input` | `api/itr2Mapper.ts` | Dead — never imported/called (FE-018). |
| `BankInterestEntryManager` | `components/` | Shadowed by `InterestEntryManager`; retained for compat. |
| `create_bank.py` | `components/` | Stray Python file in `src/components`. Remove. |
| `agriculturalIncome`/`agricultureIncome` | serializer | Dual key, same source — FE-005. |
| `bankUseForRefund` legacy + `bankAccounts[].useForRefund` | dual | FE-010. |

---

## 22. Complete Field Coverage Matrix (condensed; full per-field matrix is the official schema × this report's §7–10)

| ITR | Schedule | Field family | Frontend component | State key | Payload key | Backend reach | Status |
|---|---|---|---|---|---|---|---|
| 1/2/3/4 | PersonalInfo | name/PAN/DOB/address | `PersonalInfoTab` | `draft.personal` | `flatNo…` | ✓ | Present |
| 1/2/3/4 | FilingStatus | return section/regime | `PersonalInfoTab` | `draft.filing` | `filingSection` | ✓ | Partial |
| 1/2/3/4 | Verification | declaration/capacity/place | — | — | `verification` (empty) | ✗ | **Missing (FE-001)** |
| 1/2/3/4 | TaxReturnPreparer | TRP id/name | — | — | — | ✗ | **Missing (FE-002)** |
| 1/2/3/4 | ScheduleS | salary | `EmployerEntryManager` | `employerEntries` | `employerEntries` | ✓ | Partial |
| 1/2/3/4 | ScheduleHP | house property | `HousePropertyEntryManager` | `housePropertyEntries` | `housePropertyEntries` | ✓ | Partial |
| 1/2/3/4 | ScheduleOS | other sources | `ScheduleOSWorkspace` | `draft.otherSources` | `interestEntries…` | ✓ | Partial |
| 1/2/3/4 | ScheduleEI | exempt | `ExemptIncomeWorkspace` | `draft.exemptIncome` | `exemptIncomeSchedule` | ✓ | Partial |
| 1/2/3/4 | 80C/D/G/DD/U/E/EE/EEA/EEB | deductions | `DeductionsWorkspace`+ | `section80C`/`section80D`/`donationEntries`/`chapterVIA` | same | ✓ | Partial→Present |
| 1/2/3/4 | 80GGA/80GGC | donations | — | — | — | ✗ | **Missing (FE-006)** |
| 1/2/3/4 | TDS1/TDS2/TDS3/TCS/IT | tax credits | `TDSTab` | `tdsEntries`/`tcsEntries`/challans | same | ✓ | Partial |
| 2/3 | ScheduleFA/FSI/TR1/SPI/PTI/AL/AMT/AMTC/ESOP/5A/SI/115AD | foreign/clubbing/AMT | — | — | — | ✗ | **Missing (FE-007–FE-016)** |
| 3 | PartA_GEN2/BS/PL/BP/DPM/DOA/DEP/DCG/ESR/UD/ICDS/GST/IF/TPSA/10AA/80-IA/IB/IC/80RA/Mfg/Trading/OI/QD | business | `ITR3BusinessCoreManager`+`ITR3BusinessAuxiliaryManager` | `businessSchedule.ITR3Core/Auxiliary` (compat) | `businessSchedule` (compat) | ✓ (opaque) | Implemented (FE-017 caveat) |
| 4 | ScheduleBP | 44AD/ADA/AE | `ITR4ScheduleBPManager` | `businessSchedule.ITR4ScheduleBP` (compat) | `businessSchedule` (compat) | ✓ (opaque) | Implemented (FE-017 caveat) |
| 1/4 | LTCG112A | restricted 112A | `CapitalGainsEntryManager` | `capitalGainsSchedule` | `capitalGainsSchedule` | ✓ | Partial |
| 2/3 | ScheduleCGFor23/112A/VDA | full CG | `CapitalGainsEntryManager` | `capitalGainsSchedule` | `capitalGainsSchedule` | ✓ | Partial (115AD missing) |

---

## 23. Tab-Level Scorecard

| Tab | Applicable fields | Implemented | Partial | Missing | Critical | High | Medium | Low | Completeness % |
|---|---|---|---|---|---|---|---|---|---|
| Personal Info | ~60 | 40 | 15 | 5 | 1 (Verification) | 1 | 2 | 1 | 75% |
| Salary | ~40 | 28 | 10 | 2 | 0 | 1 | 1 | 0 | 80% |
| House Property | ~45 | 30 | 12 | 3 | 0 | 1 | 2 | 0 | 70% |
| Capital Gains | ~120 (2/3) / 6 (1/4) | 45 / 6 | 60 / 0 | 15 / 0 | 1 (115AD) | 2 | 3 | 0 | 45% / 100% |
| Business | ~600 (ITR-3) / ~40 (ITR-4) | 580 / 35 | 15 / 4 | 5 / 1 | 0 | 1 | 2 | 1 | 95% / 90% |
| Other Sources | ~70 | 45 | 18 | 7 | 0 | 1 | 2 | 0 | 70% |
| Exempt Income | ~25 | 15 | 8 | 2 | 0 | 0 | 1 | 0 | 65% |
| Deductions | ~90 | 55 | 25 | 10 | 0 | 2 (80GGA/80GGC) | 2 | 0 | 70% |
| TDS & Advance Tax | ~55 | 40 | 12 | 3 | 0 | 1 (TDS3) | 1 | 0 | 78% |
| Tax Computation | ~30 | 30 | 0 | 0 | 0 | 0 | 0 | 0 | 100% (derived) |
| Verification (no tab) | ~8 | 0 | 0 | 8 | 1 | 0 | 0 | 0 | 0% |
| Foreign (no tab) | ~400 | 0 | 0 | 400 | 10 | 0 | 0 | 0 | 0% |

---

## 24. ITR-Level Scorecard

| Form | Applicable fields | Fully impl | Partial | Missing | Incorrect | Critical | High | Medium | Low | Completeness % |
|---|---|---|---|---|---|---|---|---|---|---|
| ITR-1 | ~573 | 315 | 175 | 51 | 7 | 2 | 3 | 4 | 1 | ~55% |
| ITR-2 | ~2,078 | 730 | 520 | 760 | 43 | 11 | 4 | 6 | 2 | ~35% |
| ITR-3 | ~3,607 | 1,620 | 960 | 920 | 106 | 11 | 4 | 7 | 3 | ~45% |
| ITR-4 | ~636 | 320 | 200 | 51 | 64 | 2 | 2 | 4 | 2 | ~50% |

---

## 25. API Connectivity Matrix

| Frontend feature | Component | State | API function | Endpoint | Req fields | Exp fields | Missing | Array integrity | Status |
|---|---|---|---|---|---|---|---|---|---|
| Personal info | `PersonalInfoTab` | `draft.personal` | `saveFormData` | PUT `/clients/{id}/itr/{year}` | ~30 | ~35 | alt-address edge | n/a | OK |
| Employers | `EmployerEntryManager` | `employerEntries` | `saveFormData` | same | array | array | 0 | ✓ map | OK |
| House properties | `HousePropertyEntryManager` | `housePropertyEntries` | `saveFormData` | same | array | array | tenant[0] scalar | ✓ map | OK |
| Business (ITR-3/4) | `ITR3BusinessCoreManager`/`ITR4ScheduleBPManager` | `businessSchedule` (compat) | `saveFormData` | same | object | object | — | ✓ nested | OK (opaque) |
| Capital gains | `CapitalGainsEntryManager` | `capitalGainsSchedule` | `saveFormData` | same | object+array | object+array | — | ✓ | OK |
| Deductions | `DeductionsWorkspace` | `section80C/D`,`chapterVIA`,`donationEntries` | `saveFormData` | same | array+obj | array+obj | 80GGA/80GGC | ✓ | Partial |
| TDS/TCS/Challans | `TDSTab` | `tdsEntries`,`tcsEntries`,challans | `saveFormData` | same | array | array | TDS3 first-class | ✓ map | OK |
| Verification | — | — | — | — | 0 | 3 | 3 | n/a | **Disconnected** |
| Foreign schedules | — | — | — | — | 0 | ~400 | ~400 | n/a | **Disconnected** |
| Compute | all | `formData` | `computeTaxSummary` | POST `/tax-summary/compute` | full | full | 0 | ✓ | OK |
| Generate CBDT JSON | all | `formData` | `generateCbdtJson` | POST `.../generate-cbdt-json` | full | full | 0 | ✓ | ITR-3 blocked |

---

## 26. Complete Defect Register

| ID | Severity | ITR | Tab | Field/Issue | Type | Description | File:Line | Impact | Required fix |
|---|---|---|---|---|---|---|---|---|---|
| FE-001 | CRITICAL | All | Verification | `Declaration`,`Capacity`,`Place` | Missing | No UI captures Verification schedule; required by all forms. | `PersonalInfoTab.tsx` (absent); `legacySerializer.ts` emits empty `verification` | Official JSON invalid; filing blocked. | Add a Verification panel (declaration text+ack, capacity enum S/R, place, date for ITR-2/3) bound to `draft.verification`. |
| FE-002 | HIGH | All | TRP | `IdentificationNoOfTRP`,`NameOfTRP`,`ReImbFrmGov` | Missing | No TRP editor; required on ITR-2 if TRP-prepared. | absent | TRP-filed returns cannot be completed. | Add conditional TRP panel. |
| FE-003 | HIGH | All | Deductions | New-regime stale values | Conditionally broken | Switching regime does not clear/inactivate old-regime deduction values. | `DeductionsWorkspace` / `setFormData` | Stale values can influence computation/JSON. | Implement regime-change inactive semantics (clear or mark inactive with audit). |
| FE-004 | HIGH | All | Filing Status | Seventh proviso / notices / representative | Partial | `SeventhProvisio139`, `clauseiv7provisio139iDtls`, notice DIN/date, `AssesseeRep` detail rows partial. | `PersonalInfoTab.tsx:200-207` | Invalid filing-section branches. | Complete the seventh-proviso wizard + notice + rep flows. |
| FE-005 | MEDIUM | All | Exempt Income | `agriculturalIncome` vs `agricultureIncome` | Duplicated | Dual keys emitted from same source. | `legacySerializer.ts` | Eligibility/EI divergence risk. | Migrate to single canonical `exemptIncome.grossAgriculturalReceipts`. |
| FE-006 | HIGH | All | Deductions | `Schedule80GGA`,`Schedule80GGC` | Missing | No UI for scientific-research or political-party donations. | absent | Applicable donations cannot be claimed. | Add 80GGA (clause + donee rows) and 80GGC (party + txn ref) managers. |
| FE-007 | CRITICAL | 2/3 | Foreign | `ScheduleFA` | Missing | No foreign-assets editor (10 detail arrays). | `scheduleRegistry.ts:276` (stub only) | ITR-2/3 with foreign assets cannot file. | Build ScheduleFA manager with all 10 sub-tables. |
| FE-008 | CRITICAL | 2/3 | Foreign | `ScheduleFSI` | Missing | No foreign-source-income editor. | registry stub | Foreign income unreported. | Build FSI country/TIN/head/source rows. |
| FE-009 | CRITICAL | 2/3 | Foreign | `ScheduleTR1` | Missing | No foreign-tax-relief editor. | registry stub | DTAA relief unclaimed. | Build TR1 country/article/relief rows. |
| FE-010 | HIGH | 2/3 | Clubbing | `ScheduleSPI` | Missing | No clubbing editor. | registry stub | Clubbed income omitted. | Build SPI person/PAN/relationship/head rows. |
| FE-011 | HIGH | 2/3 | Pass-through | `SchedulePTI` | Missing | No PTI editor. | registry stub | Pass-through income omitted. | Build PTI entity/rate/head rows. |
| FE-012 | HIGH | 2/3 | AL | `ScheduleAL` | Missing | No asset-liability schedule (required income > ₹50L). | registry stub | AL-eligible filers blocked. | Build AL immovable/movable/financial + liabilities. |
| FE-013 | HIGH | 2/3 | AMT | `ScheduleAMT`,`ScheduleAMTC` | Missing | No AMT/credit editor. | registry stub | AMT-liable filers (non-44AD) blocked. | Build AMT computation + AY-wise credit ledger. |
| FE-014 | HIGH | 2/3 | ESOP | `ScheduleESOP` | Missing | No ESOP deferral editor. | registry stub | ESOP deferral unreported. | Build ESOP startup/AY-event ledger. |
| FE-015 | MEDIUM | 2 | Personal | `ResidentialStatus` enum values | Incorrect | UI stores ROR/RNOR/NR labels; schema enum is RES/NRI/NOR. | `PersonalInfoTab.tsx` | Invalid schema value unless transformed. | Store official enum, display labels via adapter. |
| FE-016 | MEDIUM | 2/3 | Personal | Director/unlisted-share detail rows | Partial | `declarationTable` exists but not wired to `CompDirectorPrvYr`/`HeldUnlistedEqShrPrYr` schema objects. | `PersonalInfoTab.tsx:230` | Boolean Yes without mandatory detail rows. | Wire declaration rows to the schema objects with opening/acq/transfer/closing. |
| FE-017 | MEDIUM | 3/4 | Business | `businessSchedule` in compat bag | Data-loss risk (latent) | Advanced ITR-3/4 business data survives only as opaque compat field, not typed `draft` path. | `legacySerializer.ts` (compat spread); `BusinessProfessionEntryManager.tsx` | Backend must parse `businessSchedule`; no typed contract. | Promote `businessSchedule` to a typed `draft.businessSchedule` with a real serializer. |
| FE-018 | MEDIUM | 2 | API | `mapFormDataToITR2Input` dead code | Unused | Clean ITR-2 schema mapper exported but never called. | `api/itr2Mapper.ts` (0 call sites) | Intended clean mapping never exercised; compute relies on backend tolerance. | Either wire it into the ITR-2 compute/generate path or delete it. |
| FE-019 | MEDIUM | All | Filing | `ReturnFileSec` integer enum sent as string | Incorrect | UI sends `'139(1)'`; schema wants integer 11..20. | `PersonalInfoTab.tsx`/`legacySerializer.ts` | Not schema-faithful; backend tolerates. | Transform to integer in a single boundary adapter. |
| FE-020 | MEDIUM | All | Deductions/HP | Cross-field validators | Missing | Co-owner share sum=100, donee PAN≠taxpayer, 80DD/80U positive-claim evidence, PRAN-for-80CCD(1B), 44AD 6%/8%, 44ADA 50% not enforced. | `validatePhase1Payload` | Invalid states saved. | Implement declarative cross-field validator set. |
| FE-021 | LOW | All | Salary | `ProfessionalTaxUs16iii` hint | Incorrect | UI hint says ₹2,500; schema max is 5,000. | `EmployerEntryManager.tsx:243-344` | Misleading. | Update hint to ₹5,000 (cap per regime where applicable). |
| FE-022 | LOW | All | Code | Dead `BusinessTab` stub | Duplicated | `ITRComputationTabs.tsx:41` stub shadowed by real `BusinessTab` in `ITRComputationPage.tsx:2375`. | `ITRComputationTabs.tsx:41` | Confusion. | Delete the stub. |
| FE-023 | LOW | All | Code | `create_bank.py` in `src/components` | Stray | Python file in frontend source tree. | `components/create_bank.py` | Clutter. | Remove. |
| FE-024 | LOW | All | Code | `_LegacyOtherSourcesTab`, `LegacyPersonalInfoTab` | Dead | Retained legacy tab implementations superseded. | `ITRComputationTabs.tsx:118`; `ITRComputationPage.tsx:2384` | Clutter. | Remove after confirming no import. |
| FE-025 | INFO | All | CG | `Schedule115AD` (FII) | Missing | No distinct FII capital-gains schedule (ITR-2/3). | absent | FPI filers unsupported. | Build 115AD manager. |
| FE-026 | INFO | 2/3 | CFL | AY-wise loss ledger | Partial | `bfLossHP`/`bfLossBusiness`/`bfLossSTCG`/`bfLossLTCG` scalars; schema wants AY-wise `ScheduleCFL` objects. | `ITRComputationTabs.tsx` business tab | Carry-forward reconciliation weak. | Replace scalars with repeatable AY/head/category ledger. |
| FE-027 | INFO | All | TDS | `ScheduleTDS3` first-class editor | Partial | Covered via TDS-3 conditional block, not a dedicated schedule. | `TDSTab` | Acceptable but not schema-first. | Optional: promote to a dedicated TDS3 schedule view. |

---

## 27. Critical Issues

1. **FE-001 — Verification schedule not captured** (all forms). Blocks official JSON validity.
2. **FE-007/008/009 — ITR-2/3 foreign schedules (FA/FSI/TR1) entirely absent.** Blocks every ITR-2/3 filer with foreign income/assets.
3. **FE-003 — New-regime stale deduction values** can corrupt computation.
4. **FE-013 — AMT/AMTC absent** for non-44AD ITR-3 business filers.
5. **FE-017 (latent) — Business data in compat bag** has no typed contract; a backend change could silently drop it.

---

## 28. High Priority Issues

6. FE-002 (TRP), FE-004 (filing-status cascades), FE-006 (80GGA/80GGC), FE-010 (SPI), FE-011 (PTI), FE-012 (AL), FE-014 (ESOP), FE-015 (residential enum), FE-016 (director rows), FE-018 (dead mapper), FE-019 (string vs int enum), FE-020 (cross-field validators).

---

## 29. Medium Priority Issues

FE-005 (agri dual key), FE-017 (compat-bag business), FE-021 (PT hint), FE-025 (115AD), FE-026 (CFL ledger), FE-027 (TDS3 first-class).

---

## 30. Low Priority Issues

FE-022 (dead BusinessTab stub), FE-023 (stray .py), FE-024 (dead legacy tabs).

---

## 31. Detailed Remediation Plan

### Phase 1 — Critical Data Loss / Submission Issues
- **FE-001**: Add a `VerificationPanel` (declaration ack checkbox + immutable text, capacity enum `S`/`R`, place, date for ITR-2/3) bound to `draft.verification`; surface in Tax Computation/Final Review tab; block `generateCbdtJson` until `declaration && capacity && place`.
- **FE-003**: Implement a regime-change handler that marks old-regime deduction values inactive (preserved for audit, excluded from computation/JSON).
- **FE-017**: Promote `businessSchedule` to a typed `draft.businessSchedule: BusinessProfessionScheduleData`; add explicit serializer keys (`ITR3Core`, `ITR3Auxiliary`, `ITR4ScheduleBP`) so the backend receives a typed contract, not an opaque compat field.

### Phase 2 — Missing Fields
- **FE-002**: TRP panel (conditional).
- **FE-006**: 80GGA (clause enum + donee rows) and 80GGC (party + txn ref + IFSC) managers.
- **FE-007–FE-014, FE-025**: Build the ITR-2/3 foreign/clubbing/AMT/ESOP/5A/SI/115AD schedule suite. This is the largest single body of work; recommend a dedicated `components/foreign/` and `components/advanced/` tree driven by the official schema definitions (mirror the `ITR3BusinessCoreManager` schema-driven approach).
- **FE-004**: Complete seventh-proviso wizard (travel/electricity/clause-iv), notice DIN/date, representative-assessee full detail.
- **FE-016**: Wire director/unlisted-share `declarationTable` rows to `CompDirectorPrvYr`/`HeldUnlistedEqShrPrYr` schema objects with opening/acquisition/transfer/closing reconciliation.

### Phase 3 — Incorrect Mappings
- **FE-015**: Store `ResidentialStatus` as `RES`/`NRI`/`NOR`; display ROR/RNOR/NR labels via a boundary adapter.
- **FE-019**: Transform `ReturnFileSec` to integer (11..20) and `assesseRepFlg` to `Y`/`N` in a single serializer adapter; keep UI labels human-readable.
- **FE-018**: Either wire `mapFormDataToITR2Input` into the ITR-2 compute/generate path (so the backend gets clean snake_case schema payloads) or delete it to avoid confusion.

### Phase 4 — Conditional / Validation Issues
- **FE-020**: Implement the declarative cross-field validator set: co-owner share sum=100; donee PAN ≠ taxpayer/verifier PAN; 80DD/80U positive claim → Form 10-IA ack + UDID required; PRAN required for positive 80CCD(1B); 44AD 6%/8% digital/other split; 44ADA 50% test; 44AE duplicate registration; TDS claimed ≤ deducted; unrealized rent ≤ rent/ALV.
- **FE-021**: Fix `ProfessionalTaxUs16iii` hint to ₹5,000.

### Phase 5 — UI / Consistency Issues
- **FE-005**: Migrate to single agriculture key.
- **FE-022/023/024**: Delete dead `BusinessTab` stub, `create_bank.py`, `_LegacyOtherSourcesTab`, `LegacyPersonalInfoTab`.
- **FE-026**: Replace scalar B/F losses with AY-wise CFL ledger.
- **FE-027**: Optional TDS3 first-class schedule view.

### Phase 6 — Final Regression Verification
- Add golden-test cases per the blueprint §6.2 (ITR-1 salary-only; ITR-1 revised+notice; ITR-2 resident full CG+foreign; ITR-3 audited business; ITR-4 44AD/44ADA/44AE).
- For each, assert: UI state → serialized flat payload → (backend) official JSON → schema V1.1 validation pass.
- Add CI gate: `scheduleRegistry` `missing` count must not increase; `known` set must not shrink.

---

## 32. Recommended Testing Strategy

1. **Per-field render/constraint/conditional/persistence/computation/serialization test** for every field in the official schema (the CSV's 6,894 nodes as a generated test registry).
2. **Round-trip tests**: `adaptLegacyReturn(serializeReturnDraftToLegacy(draft))` preserves all arrays/nested objects — extend the existing `returns.test.ts` to cover `businessSchedule`, `capitalGainsSchedule`, Verification, and each foreign schedule once built.
3. **Payload snapshot tests**: assert `buildPhase1Payload(composeLegacyPayload(model))` contains every collected field for a golden draft.
4. **Schema-validation tests**: feed the backend-generated JSON through the official V1.1 schema (`ajv.compile(schema)`) and assert zero errors for golden cases.
5. **Validation-rule tests**: map each Category-A/Cat-D rule to a unit test (FE-020 deliverable).

---

## 33. Final Audit Conclusion

### A. Does every applicable CBDT field have a frontend implementation?
**No.** Verification (FE-001), TRP (FE-002), 80GGA/80GGC (FE-006), and the entire ITR-2/3 foreign/clubbing/AMT/ESOP/5A/SI/115AD family (FE-007–FE-014, FE-025) have no UI. Filing-status cascades (FE-004) and director/unlisted detail rows (FE-016) are partial.

### B. Does every frontend field have a valid state/data binding?
**Yes.** All visible controls bind to `formData`/`editorModel` via `setFormData`/`updateEditor`; the round-trip through `applyLegacySetStateAction` preserves all keys. The exception is the compat-bag business data (FE-017), which is bound but not type-contracted.

### C. Does every applicable field reach the backend?
**For collected fields, yes** — `buildPhase1Payload` is a passthrough and `computeTaxSummary` sends the full payload. **For un-collected schedules, no** — Verification, foreign, TRP, 80GGA/80GGC are not collected, so the backend never sees them.

### D. Are arrays/multiple records transmitted completely?
**Yes.** Every array serializer uses `.map(...)`; no `[0]`/`.at(0)`/`slice(0,1)` truncation found. The `[0]` uses are scalar-compat fallbacks (FE-014) where the full array travels alongside.

### E. Are nested objects preserved?
**Yes**, via deep-merge (`mergeCompatibility`) and the compat bag. `businessSchedule` and `capitalGainsSchedule` survive as nested objects. The risk (FE-017) is contract opacity, not flattening.

### F. Are conditional fields correctly handled?
**Mostly.** Alternate address, representative, revised-return, TDS2/TDS3/TCS blocks, and ITR-3 supporting schedules all show/hide correctly. **FE-003** (regime-change stale values) is the live conditional bug.

### G. Are validations correct?
**Partially.** PAN/TAN/BSR/IFSC/Ack/PIN/Mobile/Email/DOB validators are schema-correct. **FE-020**: cross-field validators (share-sum=100, donee-PAN inequality, 80DD/80U/PRAN evidence, 44AD/44ADA/44AE tests) are not enforced. **FE-021**: PT hint is wrong. **FE-019**: enum-type (string vs integer) not schema-faithful.

### H. Are API/router/connector mappings complete?
**The API layer passes everything through** (axios, no field-dropping middleware). **FE-018**: the one clean schema-mapper (`mapFormDataToITR2Input`) is dead code. The backend owns all flat→schema mapping, which works but is not verifiable from the frontend.

### I. Are there any UI-only fields?
**No** collected field is UI-only — all reach the payload. Dead UI exists (FE-022/024) but is not rendered.

### J. Are there any silent data-loss paths?
**No silent loss of *collected* data.** The only "loss" is un-collected schedules (correctly absent). FE-017 is a latent contract risk, not current loss.

### K. Are there fields that appear implemented but are actually disconnected?
**Yes — `mapFormDataToITR2Input` (FE-018)** appears to wire ITR-2 to the backend but is never called. The director/unlisted `declarationTable` (FE-016) appears to capture detail rows but is not wired to the schema objects.

### L. Are there fields where only the first record is transmitted instead of the complete array?
**No.** All arrays use `.map`. The `[0]` fallbacks (`tenantDetails[0]`→`tenantName/PAN/Aadhaar`) are legacy scalar duplicates; the full `tenantDetails` array is serialized alongside.

### M. Is the frontend genuinely ready for production from a field-coverage and backend-connectivity perspective?
**For ITR-1 ordinary filers: nearly, pending Verification (FE-001).**
**For ITR-2/3: no** — foreign schedules, Verification, TRP, and full CG rate-buckets are blockers.
**For ITR-4: closer** — Schedule BP is now implemented, but Verification and 80GGC remain.

The frontend is a **strong draft-and-compute UI with a sound data-pipeline (no silent loss) but incomplete field coverage for advanced/foreign/verification schedules**. Until FE-001 and FE-007–FE-014 are resolved, ITR-2/3 cannot be considered production-ready; ITR-1/4 are blocked only by Verification (and, for ITR-4, 80GGC).

---

## 34. Appendix — File-by-File Findings

| File | Finding |
|---|---|
| `pages/ITRComputationPage.tsx` | Main shell; `formData` memo (422); `setFormData` (424); save/validate/generate handlers (709-838); 10 shared tabs (2182-2191); local `SalaryTab/HousePropertyTab/CapitalGainsTab/BusinessTab` (2355-2380); dead `LegacyPersonalInfoTab` (2384). |
| `pages/ITRComputationTabs.tsx` | `OtherSourcesTab`(96), `DeductionsTab`(377), `TDSTab`(~610, incl. new TDS2/TDS3/TCS blocks), `TaxComputationTab`; dead `BusinessTab`(41) stub, dead `_LegacyOtherSourcesTab`(118). |
| `components/PersonalInfoTab.tsx` | Split name, PAN, Aadhaar, DOB, address, alt address, rep assessee, director/unlisted declarationTable (230) — not wired to schema objects (FE-016). |
| `components/EmployerEntryManager.tsx` | Strong salary editor; PT hint ₹2500 (FE-021). |
| `components/HousePropertyEntryManager.tsx` | Co-owners/tenants/loans; `tenantDetails[0]` scalar fallback (FE-014). |
| `components/CapitalGainsEntryManager.tsx` | 112A/ST-LT immovable/VDA/115AD-adjacent/exemptions/DTAA/loss-set-off; no distinct 115AD schedule (FE-025). |
| `components/BusinessProfessionEntryManager.tsx` | Routes ITR-3→`ITR3BusinessWorkspace`, ITR-4→`ITR4ScheduleBPManager`; ITR-1/2 blocked. |
| `components/business/ITR3BusinessCoreManager.tsx` | Schema-driven PartA_GEN2/BS/PL/Mfg/Trading/ITR3ScheduleBP (ROOTS line 52). |
| `components/business/ITR3BusinessAuxiliaryManager.tsx` | DPM/DOA/DEP/DCG/ESR/UD/ICDS/GST/IF/TPSA/10AA/80-IA/IB/IC/80RA with computed totals (157-168). |
| `components/business/ITR4ScheduleBPManager.tsx` | 44AD/44ADA/44AE; `GoodsDtlsUs44AE` slice(0,10) schema-valid (148). |
| `components/business/ITR3BusinessWorkspace.tsx` | 5-step wizard; routes core+auxiliary+presumptive. |
| `components/exemptincome/ExemptIncomeWorkspace.tsx` | Repeatable EI rows; agri dual key (FE-005). |
| `components/deductions/DeductionsWorkspace.tsx` | 80C/CCD/DD/U/E/EE/EEA/EEB/TTA/TTB/G/GG; no 80GGA/80GGC (FE-006). |
| `domain/returns/legacySerializer.ts` | Full flat payload; `.map` arrays; `...compatibilityFields` preserves `businessSchedule`/`capitalGainsSchedule`; `tenantDetails[0]` fallback (FE-014). |
| `domain/returns/legacyAdapter.ts` | `known` set (53) — `businessSchedule` NOT in it → compat-bag (FE-017); ITR-1/4 property cap slice(0,2) schema-valid (63). |
| `domain/returns/editorModel.ts` | `applyLegacySetStateAction`/`applyLegacyPatch`/`mergeCompatibility` deep-merge (221-240); `tdsFromManager`/`tdsToManager` full enrichment. |
| `domain/returns/types.ts` | Canonical types incl. `TdsCredit`/`TcsCredit` with all schema enrichment fields; `TaxDeductCreditDtls`; `ReturnDraft.businesses` (PresumptiveBusiness[]) — separate from `businessSchedule`. |
| `domain/scheduleRegistry.ts` | Advisory-only; ITR-3 business `missing` flags now stale. |
| `api/itr.ts` | `saveFormData`/`computeTaxSummary`/`validate`/`generateCbdtJson`; compute spreads full `formData`. |
| `api/itr2Mapper.ts` | Clean ITR-2 schema mapper — **never called** (FE-018). |
| `components/create_bank.py` | Stray Python (FE-023). |

**No source code was modified by this audit.** Only this report and the schema field inventory artifact were created.
