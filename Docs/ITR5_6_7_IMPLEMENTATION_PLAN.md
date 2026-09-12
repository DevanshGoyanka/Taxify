# ITR-5 / ITR-6 / ITR-7 — Detailed Implementation Plan (AY 2026-27)

> Matches the existing ITR-1/2/4 workflow end-to-end (canonical `ReturnDraft` → per-form typed
> input mapper → calculator → ITD builder → official schema validator → CBDT rule validator →
> ERI Type-2/3 filing) and extends the frontend (currently individual/HUF only) to support
> entity-focused forms: ITR-5 (firms/LLPs/AOPs/BOIs/estates), ITR-6 (companies, DSC-only),
> ITR-7 (trusts/institutions/political parties, needs-legal-review flag).
>
> Authority documents (already in repo): `Reference Docs by CBDT & ITD/Official ITR FORMS/`
> (`ITR-5-2026-Eng (2).pdf`, `ITR-6-2026-Eng 1.pdf`, `ITR-7-2026-Eng 1.pdf`),
> `Reference Docs by CBDT & ITD/Official JSON Schema/` (`ITR-5_2026_Main_V1.1.json` — 257 defs,
> `ITR-6_2026_Main_V1.0.json` — 295 defs, `ITR-7_2026_Main_V0.1.json` — 221 defs), and the
> Validation Rules PDFs under `Reference Docs by CBDT & ITD/Official Validations/`.
>
> This plan supersedes the stub sections in `Docs/ERI_UAT_EXPANSION_PLAN.md` Phases 14–16 and
> `Docs/THE_COMPLETE_TAXIFY.md` Phase D.1.1–D.1.3. It is written to be implemented top-to-bottom;
> no phase after the current one starts until the user has tested and approved the one before it.

---

## 0. Architecture Recap — the contract every form must satisfy

Taxify's ITR pipeline is a strict five-layer contract. Every form (1/2/4 today; 3 on a legacy
path) follows it identically. ITR-5/6/7 must follow it too:

```
ReturnDraft (canonical, app/schemas/return_draft.py, extra="forbid", Decimal money)
   │  draft_to_itrN_input.py  (pure mapper; reuses draft_to_itr1_input helpers)
   ▼
ITRNInput (typed Pydantic, app/schemas/itrN.py)           ← NEW per form
   │  calculators/itrN.py::compute(input) -> ITRNResult    ← NEW per form (pure)
   ▼
ITDNResult (dataclass)
   │  itd/itrN.py::build_itrN_json(result, input)          ← NEW per form
   │  itd/itrN_schema.py::validate_itrN_json(doc)           ← NEW per form (jsonschema Draft-4)
   ▼
official CBDT JSON {"ITR":{"ITRN":{...}}}  with CreationInfo.Digest injected
   │  validators/itrN/{input_rules,calc_rules,runner}.py   ← NEW per form
   ▼
ValidationReport (can_upload = no Category-A failures)
   │  filing_gateway_v2.py dispatch (compute_canonical + generate_cbdt_json)
   │  filing_orchestrator.py::produce_itd_json  (single JSON path, both ERI modes)
   ▼
ERI Type-2 (REST, sync) or Type-3 (Playwright portal, queued) → ARN
```

**Shared abstractions to reuse (do NOT re-implement):**

Backend (`app/engine/itd/common.py`):
- `_compute_digest(data)` — delegates to `app.eri.digest.compute_digest` (iterated HMAC-SHA256,
  `iterations + 1` operations, env-scoped credential bundle). **Never** hand-roll a digest.
- `_creation_info()` — `SWVersionNo`/`SWCreatedBy`/`JSONCreatedBy` (from `get_eri_credentials().sw_id`),
  `JSONCreationDate`, `IntermediaryCity` (from `ERI_INTERMEDIARY_CITY`, default "Akola"),
  `Digest: "-"` placeholder.
- `_form_itr(form_name)` — `FormName`/`Description`/`AssessmentYear`/`SchemaVer`/`FormVer`.
- `_verification(assessee_name, father_name, pan, place, capacity)`.
- `_personal_info_base(...)` — PAN/address/name/Dob base; per-form builders add form-specific keys
  (e.g. `Status`).
- `_tax_return_preparer(trp)`.
- `_to_rupees(...)` — **returns plain `int`, not `Decimal`**. Pitfall: `sum(gen, 0)` crashes on an
  empty generator (int has no `.quantize`). Use `Decimal("0")` start, route the accumulator through
  `_to_rupees()` exactly once. A `Decimal` that skips `_to_rupees()` fails `jsonschema type: integer`.

Backend (`app/engine/draft_to_itr1_input.py`) — shared form-agnostic head mappers imported by the
ITR-2 and ITR-4 mappers and to be imported by ITR-5/6/7 mappers:
- `_map_salary`, `_map_house_properties`, `_map_24b_loans`, `_map_other_sources`, `_map_capital_gains`,
  `_map_compact_exempt_income`, `_map_tds`/`_map_tds3`/`_map_tcs`, `_map_tax_payments`,
  `_map_bank_accounts`, `_map_80c`/`_map_80d`/`_map_donations`/`_map_80gga`/`_map_80ggc`,
  `_map_deduction_loans`, `_map_disability_schedules`, `_map_hra_details`, `_map_dividend_quarterly_breakdown`,
  `_age_bracket_from_dob`, `DraftMappingError`.

Backend (`app/engine/common/`) — shared arithmetic (slabs, rebate, surcharge, cess, interest,
rounding, due dates); constants in `app/engine/constants.py`; schedules in `app/engine/schedules/`.

Frontend (`frontend/src/domain/returns/`):
- `types.ts` — `ReturnDraft` (one canonical contract, ITR-2/3 additive fields are top-level
  nullable/optional).
- `factory.ts::createEmptyReturnDraft(ay, form, regime)` — the seed; ITR-2/3 additive schedules
  default to `[]`/`null`.
- `editorModelV2.ts` — `updateDraft(prev, updater)` + `replaceDraft` + ~40 typed field updaters +
  projection helpers (`interestToManager`, `tdsToManager`, etc.).
- `canonicalRepository.ts` — `CanonicalReturnRepository.get/save` + `stripCompatibility`,
  `assertCanonicalDraft`, `enforceAssessmentYear`, `normalizeLoadedDraft`.
- `eligibility.ts` — `EligibilityFacts`, `collectEligibilityFactsFromDraft`, `assessFormEligibilityFromDraft`,
  `evaluateEligibility` (rule engine).
- `scheduleRegistry.ts` — `SCHEDULE_REGISTRY`, `activeSchedules`, `blockingSchedules`.
- `filingPreflight.ts::validateCbdtFrontendFields(draft)` — pre-flight gates (PAN/Aadhaar/PIN/TAN/IFSC,
  father name, state code, verification place/declaration, filing-section due date).
- `draftPatch.ts::mergeDraft(base, patch)` — deep merge; identified arrays merge by `id`.
- `api/itrV2.ts` — `itrV2.get/put/compute/generate/download/downloadPdf` (form-agnostic).
- `components/itr2/ITR2SchedulesWorkspace.tsx` — generic `ListSection<T>`/`NullableSection<T>` +
  `validationFor`/`controlFor` renderer. **The template for entity-schedule workspaces.**

**The single migration seam (closed contract):** `ItrForm` is a closed 4-value union in three
places — `app/schemas/return_draft.py` (`ItrForm = Literal["ITR-1","ITR-2","ITR-3","ITR-4"]`),
`frontend/src/domain/returns/types.ts` (`export type ItrForm = ...`), and
`frontend/src/domain/returns/eligibility.ts` (re-exports its own copy). All three must be widened
together. `ReturnDraft` is `extra="forbid"`, so any new top-level entity field must be added
deliberately as a nullable additive field (mirroring the ITR-2/3 additive block), never ad hoc.

---

## 1. Scope, Eligibility & Domain Boundaries

### 1.1 ITR-5 — Firms, LLPs, AOPs, BOIs, artificial juridical persons, estates
- **Assessees:** Partnership firms (including LLPs), AOPs, BOIs, artificial juridical persons,
  estates of deceased, insolvent, dissolved firms, local authorities (authority-only cases), joint
  family (co-parceners not HUF).
- **NOT for:** Individuals, HUFs, companies, trusts/institutions u/s 11 (→ ITR-7), charitable/religious
  trusts (→ ITR-7), political parties (→ ITR-7).
- **Key schedules (official `Form_ITR5` definition, verified):** `PartA_GEN1`, `PartA_GEN2`,
  `PARTA_BS`, `PARTA_PL`, `PARTA_OI`, `PARTA_QD`, `ManufacturingAccount`, `TradingAccount`,
  `CorpScheduleBP`, `ScheduleHP`, `ScheduleOS`, `ScheduleEI`, `ScheduleCG`, `ScheduleVDA`,
  `Schedule112A`, `Schedule115AD`, `ScheduleIF` (interest from firms), `ScheduleICDS`, `ScheduleESR`,
  `ScheduleDEP`/`DOA`/`DPM`/`DCG` (depreciation), `ITRScheduleUD` (unabsorbed depreciation),
  `ScheduleCYLA`/`BFLA`/`CFL` (loss set-off), `ScheduleSI` (special-rate income), `ScheduleVIA`
  (Chapter VI-A), `Schedule80_IA`/`80_IB`/`80_IC`/`80IAC`/`80LA`/`80P`/`80RA`/`10AA`/`80G`/`80GGA`/`80GGC`,
  `ScheduleAMT`/`AMTC` (AMT — firms are AMT-applicable), `Schedule115TD` (TDS on accumulation u/s 11/10/21),
  `ScheduleTPSA` (transfer pricing secondary adjustment), `ScheduleGST`, `ScheduleFA`/`FSI`/`TR1`,
  `ScheduleTDS2`/`TDS3`/`TCS`, `ScheduleIT` (tax payments), `PartB-TI`, `PartB_TTI`, `Verification`,
  `CreationInfo`, `Form_ITR5`.
- **Filing mode:** EVC (firm partner can e-verify) OR DSC. No Aadhaar-OTP restriction for non-individual.
- **Presumptive:** 44AD/44ADA/44AE available for eligible firms (44AD only for resident firm; 44AE for
  goods carriages; 44ADA for eligible professions — firm partners' profession).

### 1.2 ITR-6 — Companies (except those claiming exemption u/s 11)
- **Assessees:** All companies — domestic, foreign, OPC, private, public, Section 8 (non-charity),
  co-op societies structured as companies. **DSC-only filing** — companies cannot use EVC.
- **NOT for:** Companies claiming exemption u/s 11 (→ ITR-7); LLPs (→ ITR-5); local authorities
  (generally ITR-5); AOPs/BOIs (→ ITR-5).
- **Key schedules (official `Form_ITR6` definition, verified):** `PartA_GEN1`, `PartA_GEN2For6`,
  `PARTA_BSFor6FrmAY13`, `PARTA_BSIndAS`, `PARTA_PL`, `PARTA_PLIndAS`, `PARTA_OI`, `PARTA_OL`,
  `PARTA_QD`, `ManufacturingAccount`, `ManufacturingAccountIndAS`, `TradingAccount`,
  `TradingAccountIndAS`, `CorpScheduleBP`, `ScheduleHP`, `ScheduleOS`, `ScheduleEI`, `ScheduleCG`,
  `ScheduleVDA`, `Schedule112A`, `Schedule115AD`, `ScheduleIF`, `ScheduleICDS`, `ScheduleESR`,
  depreciation set, `ITRScheduleUD`, loss set-off trio, `ScheduleSI`, `ScheduleVIA`, business
  deductions family, **`ScheduleMAT` + `ScheduleMATC`** (Minimum Alternate Tax u/s 115JB + credit),
  `ScheduleAL` (Schedule AL — advance-paid tax loc), `ScheduleSH` (shareholding — >10% shareholders),
  `ScheduleFD` (foreign dividend u/s 115A/115Bba), `Schedule115TD`, `ScheduleTPSA`, `ScheduleGST`,
  `ScheduleFA`/`FSI`/`TR1`, TDS/TCS, `ScheduleIT`, `PartB-TI`, `PartB_TTI`, `Verification`.
- **Special:** MAT (§115JB) is mandatory if book profit > regular taxable income; MAT credit
  (§115JAA) carried forward 15 years. 115BAA/115BAB concessional regimes (new-manufacturing/
  concessional-corporate) require Form 10-IDA election, reflected in PartA_GEN2For6.
- **Filing mode:** DSC only. The filing router must reject EVC for `ITR-6`.

### 1.3 ITR-7 — Trusts, institutions, political parties, universities, hospitals, research
- **Assessees:** Charitable/religious trusts u/s 11/12 (12A/12AB registered), universities/
  hospitals/research u/s 10(23C), political parties u/s 13A, scientific research associations,
  news channels/agencies u/s 10A/10AA, institutions u/s 10(23A)–(23FBB), trade unions, PF/
  superannuation funds, ESI, non-profit organisations.
- **NOT for:** Companies claiming u/s 11 exemption (they use ITR-7); individuals/HUFs/firms/
  companies not in the above categories.
- **Key schedules (official `Form_ITR7` definition, verified):** `PartA_GEN1`, `PartA_GEN2`,
  `PARTA_BS`, `PartB_TI`/`PartB_TI2`/`PartB_TI3` (three total-income variants), `PartB_TTI`,
  `CorpScheduleBP`, `ScheduleHP`, `ScheduleOS`, `ScheduleCG`, `ScheduleVDA`, `ScheduleCYLA`,
  `ScheduleAI` (accumulation u/s 11(2)/11(3)/11(3A) — corpus accumulation), `ScheduleVC`
  (voluntary contributions received — donations), `ScheduleCSR` (Corporate Social Responsibility
  u/s 135 Companies Act — for entities engaged in CSR), `ScheduleIE_I`/`IE_II`/`IE_III`/`IE_IV`
  (income/expenditure statement — 4 variants: charitable/religious/political/other), `ScheduleOA`
  (objects/achievements), `ScheduleET` (entities in which >2% voting power held), `ScheduleSH`
  (shareholding), `SchedulePP` (political party details — if §13A), `ScheduleD`/`DA` (donations
  to electoral trusts/parties), `ScheduleI`/`IA` (audit report details — 10B/10BB), `ScheduleJ`
  (scientific research), `ScheduleR` (rectification/revision details), `ScheduleFA`/`FSI`/`TR1`,
  `Schedule115TD`, `Schedule115BBI` (anonymous donations special rate), TDS/TCS, `ScheduleIT`,
  `Verification`.
- **Special:** 115BBC special rate (anonymous donations for trusts), 115BBI (anonymous donation
  tax), corpus/anonymous-donation handling, 12A/12AB/10(23C) registration numbers, 80G receipt
  details. **Needs-legal-review flag** before filing — trusts have the most complex compliance
  matrix (10A/10AB/12AB registration, 35(1AA)/35(1A) approvals, FCRA where foreign contributions).
- **Filing mode:** DSC for political parties (§13A mandates); EVC or DSC for other §11/12 trusts.

### 1.4 Official schema sizes (grounded)
| Form | Schema defs | Lines | Validation rules PDF |
|---|---|---|---|
| ITR-5 | 257 | ~22,983 | 1.36 MB |
| ITR-6 | 295 | ~28,352 | 1.26 MB |
| ITR-7 | 221 | ~15,702 | 0.58 MB |

---

## 2. Sequencing Strategy — why ITR-5 first, then ITR-6, then ITR-7

1. **ITR-5 is the natural bridge.** Its schedule inventory overlaps heavily with ITR-3/ITR-4
   (PGBP via `CorpScheduleBP`, `ScheduleBP`, depreciation, CYLA/BFLA/CFL, AMT) and with ITR-2
   (full capital gains, FA/FSI/TR1, PTI). The firm-specific layer (partner capital/current accounts,
   Section 40(b) remuneration/interest ceiling, Schedule IF) is a focused delta. Building it first
   de-risks the shared entity plumbing (P&L, Balance Sheet, depreciation blocks) that ITR-6 then
   reuses for companies.
2. **ITR-6 builds on ITR-5's entity plumbing** and adds the corporate-only layer: MAT/MATC
   (§115JB/115JAA), IndAS variants of BS/PL/Manufacturing/Trading, Schedule SH (shareholding),
   Schedule AL, Schedule FD, 115BAA/115BAB (Form 10-IDA). DSC-only enforcement is a router-level
   gate, not a compute concern.
3. **ITR-7 has a different shape** (accumulation/application-of-income schedules, IE/VC/CSR/PP/ET,
   115BBI/115BBC special rates, 12A/12AB/10(23C) registration matrix, political-party §13A
   DSC mandate). It is the smallest schema but the most compliance-heavy. The needs-legal-review
   flag is its defining feature.

---

## 3. Cross-Cutting Phase 0 — Widen the canonical contract (both ends)

This phase is shared by all three forms and **must land first** so each form phase can be
implemented without re-touching the contract.

### 3.1 Backend: widen `ItrForm` + entity additive fields

**File:** `app/schemas/return_draft.py`

- Widen the literal:
  ```python
  ItrForm = Literal["ITR-1", "ITR-2", "ITR-3", "ITR-4", "ITR-5", "ITR-6", "ITR-7"]
  ```
- Widen `AssesseeStatus` / `VerificationCapacity` literals to cover entities:
  - `AssesseeStatus`: add `"A"` (AOP/BOI), `"F"` (firm — already), `"C"` (company), `"T"` (trust),
    `"P"` (political party), `"J"` (artificial juridical person), `"L"` (local authority),
    `"E"` (estate of deceased), `"D"` (association — used by some forms for AOP).
  - `VerificationCapacity`: add `"MANAGING_PARTNER"`, `"PRINCIPAL_OFFICER"`, `"TRUSTEE"`,
    `"CHAIRPERSON"`, `"ADMINISTRATOR"`, `"LIQUIDATOR"` alongside existing `"SELF"`, `"REPRESENTATIVE"`,
    `"KARTA"`, `"PARTNER"`.
- Add a new **entity additive block** (mirroring the ITR-2/3 additive block pattern — top-level
  nullable fields ignored by ITR-1/2/4 mappers):
  ```python
  # ── ITR-5/6/7 additive fields (ignored by ITR-1/2/4) ─────────────────
  entityProfile: Optional["EntityProfile"] = None           # firm/company/trust identity
  partners: list["PartnerDetail"] = Field(default_factory=list)      # ITR-5/6 (partners/directors)
  shareholders: list["ShareholderDetail"] = Field(default_factory=list)  # ITR-6/7 (>10%)
  manufacturingAccount: Optional["ManufacturingAccount"] = None      # ITR-5/6
  tradingAccount: Optional["TradingAccount"] = None                  # ITR-5/6
  balanceSheet: Optional["BalanceSheet"] = None                     # ITR-5/6/7 (PARTA_BS)
  profitLossAccount: Optional["ProfitLossAccount"] = None          # ITR-5/6 (PARTA_PL)
  scheduleBp: Optional["ScheduleBPData"] = None                      # ITR-5/6/7 (CorpScheduleBP)
  depreciation: Optional["DepreciationSchedule"] = None             # ITR-5/6 (DEP/DOA/DPM/DCG/UD)
  matDetails: Optional["MATDetails"] = None                         # ITR-6 (MAT + MATC)
  trustCompliance: Optional["TrustComplianceDetails"] = None        # ITR-7 (12A/12AB/10(23C)/80G)
  corpusAccumulation: Optional["CorpusAccumulation"] = None         # ITR-7 (Schedule AI)
  voluntaryContributions: list["VoluntaryContribution"] = Field(default_factory=list)  # ITR-7 (VC)
  ```
  These are `Optional` with `None` defaults so existing ITR-1/2/4 drafts persist unchanged
  (`extra="forbid"` stays satisfied for old payloads; `normalizeLoadedDraft` backfills them on load).
- Add the matching Pydantic sub-models (`EntityProfile`, `PartnerDetail`, `ShareholderDetail`,
  `ManufacturingAccount`, `TradingAccount`, `BalanceSheet`, `ProfitLossAccount`, `ScheduleBPData`,
  `DepreciationSchedule`, `MATDetails`, `TrustComplianceDetails`, `CorpusAccumulation`,
  `VoluntaryContribution`) in the same file, all `_StrictModel` subclasses, all money fields `Decimal`.
  Field names mirror the official CBDT schema keys (e.g. `CorpScheduleBP.BusIncOthThanSpec`,
  `PARTA_BS.LiabilitiesAndAssets`) so the builder is a near-identity mapping.
- Extend `create_empty_draft`/`draft_from_client_seed`/`migrate_stored_draft_payload` to default
  the new additive fields to `None`/`[]`.

### 3.2 Frontend: widen `ItrForm` + `AssesseeStatus` + entity types

**Files (all three widened together):**
- `frontend/src/domain/returns/types.ts`:
  ```ts
  export type ItrForm = 'ITR-1' | 'ITR-2' | 'ITR-3' | 'ITR-4' | 'ITR-5' | 'ITR-6' | 'ITR-7';
  ```
  Widen `PersonalInfo.assesseeStatus` to include entity codes. Add TS interfaces mirroring each new
  backend sub-model (`EntityProfile`, `PartnerDetail`, etc.). Add `EMPTY_*` constants.
- `frontend/src/domain/returns/factory.ts::createEmptyReturnDraft` — add the new additive fields
  (all `[]`/`null` defaults), mirroring the ITR-2/3 block.
- `frontend/src/domain/returns/eligibility.ts` — `ITR_FORMS` becomes the 7-form array;
  `blockers: Record<ItrForm, string[]>` gains `ITR-5/6/7` keys. Add entity-type blockers
  (e.g. `blockers['ITR-6'].push('Companies cannot use EVC — DSC required')` — informational,
  surfaced as a warning not a hard block on selection).
- `frontend/src/domain/returns/canonicalRepository.ts::normalizeLoadedDraft` — backfill the new
  additive fields from `createEmptyReturnDraft` defaults (same pattern as the ITR-2/3 backfill).
- `frontend/src/domain/returns/scheduleRegistry.ts` — `ALL`/`statusRecord` base records widen to
  7 forms; declare the new schedules (entity schedules) with `forms` arrays including the relevant
  entity form(s), `status` starting at `'missing'` (wired to `'available'` as each phase lands).

### 3.3 Gateway dispatch — reserve branches (no-op stubs)

**File:** `app/engine/filing_gateway_v2.py`

Add placeholder branches in `compute_canonical` (line ~2009) and `generate_cbdt_json` (line ~2041):
```python
if draft.form == "ITR-5":
    raise FilingGatewayV2Error(
        "ITR-5 compute is not yet implemented.",
        ["ITR-5 lands in Phase ITR5-1 onwards."],
    )
# same for ITR-6, ITR-7
```
This makes the contract honest: a 501/422 with a clear message rather than a silent fall-through.
Each form phase replaces its stub with the real `compute_canonical_itrN`/`_generate_cbdt_json_itrN`.

### 3.4 Filing router — reserve branches

**Files:** `app/engine/filing_orchestrator.py` (`produce_itd_json` line ~79: widen the accepted set),
`app/routers/filing.py::_normalize_form` (line ~55: accept ITR-5/6/7) and the submit gates
(lines ~225, ~285: 501 for ITR-5/6/7 submit until the form's own phase opens the gate).

### 3.5 Phase 0 verification
- `pytest tests/test_itr1_calculator.py tests/test_itr4_calculator.py -v` stays green (no regression).
- `frontend/ npm run build && npm run lint && npm test` stays green.
- `migrate_stored_draft_payload` round-trips a saved ITR-1 draft unchanged (no additive field
  corruption).
- `POST /v2/clients/{id}/itr/{year}` with `form: "ITR-5"` persists and returns the seed draft
  (compute still 422 — expected).

---

## 4. Phase ITR5 — ITR-5 (Firms/LLPs/AOPs/BOIs/Estates)

Sub-phased: ITR5-1 (schema+mapper), ITR5-2 (calculator), ITR5-3 (ITD builder+schema validator),
ITR5-4 (validators), ITR5-5 (gateway dispatch+orchestrator+filing router), ITR5-6 (frontend),
ITR5-7 (tests+golden suite+live UAT).

### ITR5-1. Schema + mapper
**New files:**
- `app/schemas/itr5.py` — `ITR5Input` (Pydantic v2, `Decimal` money). Import shared capital-gains/
  loss/foreign types from `app/schemas/itr2.py` (as ITR-3 already does). Import
  `SalaryIncome`/`HousePropertyIncome`/`OtherSourcesIncome`/`Chapter6ADeductions`/TDS types from
  `app/schemas/itr1.py`. Firm-specific models: `PartnerDetail` (name/PAN/capital/current
  account/remuneration/interest u/s 40(b)), `FirmPresumptiveScheme` (44AD/44ADA/44AE for firms),
  `ScheduleIFEntry` (interest from firms — if the firm itself is a partner in another firm),
  `ScheduleGSTEntry`, `ScheduleBPPartA` (PGBP non-speculative/speculative), `ManufacturingAccountData`,
  `TradingAccountData`, `BalanceSheetData`, `ProfitLossAccountData`, `DepreciationBlock` (DEP/DOA/DPM/DCG/UD).
- `app/engine/draft_to_itr5_input.py::draft_to_itr5_input(draft) -> tuple[ITR5Input, breakdown]`.
  Reuse `draft_to_itr1_input.py` helpers for all shared heads. Firm-specific: map
  `draft.entityProfile`, `draft.partners`, `draft.balanceSheet`, `draft.profitLossAccount`,
  `draft.depreciation`, `draft.manufacturingAccount`, `draft.tradingAccount`, `draft.scheduleBp`.
  Reuse ITR-2's CG/foreign/loss mapping approach (the ITR-2 mapper is the template for those heads).

**Existing files touched:** `app/schemas/return_draft.py` (already widened in Phase 0).

### ITR5-2. Calculator
**New file:** `app/engine/calculators/itr5.py` — `compute(input_data: ITR5Input) -> ITR5Result`
(dataclass). Computation order (mirrors ITR-3's order for the PGBP-heavy forms, extended for
firm-specific items):
1. PGBP income (`CorpScheduleBP`): non-speculative, speculative, specified (35AD) — from
   `draft.scheduleBp` + `draft.profitLossAccount`. Apply Section 40(b) remuneration/interest ceiling
   (40(b)(v) — partner remuneration: lower of actual, ₹1.5L, or 90% of book profit for first
   ₹3L; 40(b)(iv) — interest on partner capital: 12% p.a. on agreed capital). Apply 43B
   disallowances (taxes, duties, bonus to employees if not paid by due date).
2. Presumptive (44AD/44ADA/44AE) if applicable — from `draft.businesses` (reuse `schedules.presumptive`).
3. Salary + HP + CG (full) + VDA + OS — reuse `schedules.salary`/`house_property`/`capital_gains`/
   `other_sources`/`special_rates`.
4. Clubbing (SPI) + Schedule IF (interest from firms) — pass-through, not taxed at firm level
   (firm is the assessee, not a partner).
5. CYLA → BFLA → unabsorbed depreciation (UD) set-off — reuse `schedules.loss_setoff.cyla/bfla`
   + `schedules.amt` for the UD.
6. Agricultural income → partial integration if applicable.
7. Chapter VI-A deductions (`scheduleVIA`) + business deductions (80IA/IB/IC/IAC/LA/P/RA/10AA).
8. TI = GTI − deductions (rounded to ₹10).
9. SI: special-rate tax (111A/112A/VDA/115BB family/lottery).
10. **AMT (§115JB-e equivalent for firms is AMT u/s 115JD — not MAT)** — firms compute AMT
    (Adjusted Total Income) via `schedules.amt` and claim AMTC credit. AMT applies to firms
    claiming 80IA-80RRB deductions or 35AD specified business.
11. Slab tax (firm rate 30% — AY 2026-27: 30% on ≤₹3L slab... actually firm flat 30% + cess + 12%
    surcharge above ₹1cr / 7% above ₹50L; marginal relief). Use `common.slab_tax`/`surcharge`/
    `cess` with firm-specific rates (extend `constants.py` with `FIRM_SLABS_AY2627`).
12. Rebate 87A (not available to firms — individual-only; skip).
13. Surcharge (12% > ₹1cr, 7% > ₹50L — firms do NOT get the 25%/37% tier individuals get; firm
    surcharge caps differ) + cess 4%.
14. Interest 234A/B/C + late fee 234F (234F applies to firms).
15. TDS/TCS credit + advance tax/SAT → net payable/refund.

**Existing files touched:** `app/engine/constants.py` (add `FIRM_TAX_RATE`, `FIRM_SURCHARGE_TIERS`,
`FIRM_AMT_RATE`), `app/engine/common/surcharge.py` (extend to entity-type rate tables if not already
parameterised).

### ITR5-3. ITD builder + official schema validator
**New files:**
- `app/engine/itd/itr5.py::build_itr5_json(result, input_data) -> dict` — assembles
  `{"ITR":{"ITR5":{...}}}`. Reuse `common._compute_digest`, `_creation_info`, `_form_itr("ITR-5")`,
  `_verification`, `_personal_info_base` (add `Status` for firm), `_tax_return_preparer`,
  `_to_rupees`. Build every applicable schedule from the typed input + result; omit empty schedules
  entirely (per the ITR-4 precedent: `Schedule80C` omitted when unclaimed, not an empty placeholder).
  Handle the 4 builder-level invariants CLAUDE.md flags (digest off-by-one, Form 10-IEA cascade,
  empty-schedule omission, AlternateAddress/SecondaryAdd always present).
- `app/engine/itd/itr5_schema.py` — copy `itr4_schema.py` structure. `@lru_cache` loader for
  `Reference Docs by CBDT & ITD/Official JSON Schema/ITR-5_2026_Main_V1.1.json` (Draft-4).
  `validate_itr5_json(document)` raises `ITR5SchemaValidationError(errors=[{path, schema_path, message}])`.
  `_SCHEMA_RELATIVE_PATH` points at the checked-in schema.

### ITR5-4. CBDT rule validators
**New files:** `app/engine/validators/itr5/` package:
- `__init__.py` — exposes `run_input_validation`, `run_calc_validation`, `run_all`.
- `input_rules.py` — pre-compute gates, `ITR5-R###` numbering (mirrors ITR-4). Write
  `official_rules_reference.py` (permanent CBDT rule transcription from the ITR-5 Validation Rules PDF).
- `calc_rules.py` — post-computation arithmetic/cross-schedule consistency, `ITR5-C###` numbering
  (distinct namespace, per the ITR-4 precedent that found ~90 collisions).
- `runner.py` — `run_input_validation(inp)` wraps `validate_itr5_input(inp)`;
  `run_calc_validation(inp, result)` wraps `validate_itr5_calculation(inp, result)`.

Before transcribing any rule, apply the CLAUDE.md filter: (1) is the field user-suppliable and not
already capped/computed? (2) does the Pydantic schema already reject the bad state via
`@model_validator`? (3) is there an existing rule covering it via a different path? Most PDF rules
are CBDT-UI dropdown consistency checks or calculator-formula behavior — they belong in the
calculator, not the validator.

### ITR5-5. Gateway dispatch + orchestrator + filing router
**Existing files touched:**
- `app/engine/filing_gateway_v2.py` — replace the Phase 0 stub:
  ```python
  if draft.form == "ITR-5":
      return compute_canonical_itr5(draft)
  # and in generate_cbdt_json:
  if draft.form == "ITR-5":
      return _generate_cbdt_json_itr5(draft)
  ```
  Add `compute_canonical_itr5` (line ~2009 region) + `_generate_cbdt_json_itr5` (line ~2041 region)
  following the ITR-1/2/4 contract exactly: pending-reconciliation gate → out-of-scope-evidence
  gate → `draft_to_itr5_input` → filing profile (`_itr5_filing_profile`, reuse
  `personal_profile.normalize_personal_profile`) → `compute_itr5` → `ITR5PipelineResult` (frozen
  dataclass). `_generate_cbdt_json_itr5`: compute once → `run_input_validation` →
  `run_calc_validation` → `build_itr5_json` → `validate_itr5_json` → return `(json, summary)`.
  **Must not** perform late `model_copy(update={...})` enrichment — reuse `pipeline.typed_input`.
- `app/engine/filing_orchestrator.py::produce_itd_json` — `ITR-5` accepted in the form set (line ~79),
  added to the `generate_cbdt_json` branch (line ~98).
- `app/routers/filing.py` — `_normalize_form` accepts `ITR-5`; the Type-2 submit gate (line ~225) and
  Type-3 submit gate (line ~285) open for ITR-5 (EVC or DSC — firm partners can e-verify).
- `app/routers/client_itr_v2.py::download_client_itr_pdf_v2` — the ITR-3 501 guard widens to allow
  ITR-5 (render Statement of Income context for the firm).

### ITR5-6. Frontend
**New files:**
- `frontend/src/components/itr5/ITR5SchedulesWorkspace.tsx` — generic `ListSection<T>`/`NullableSection<T>`
  editor (copy the `ITR2SchedulesWorkspace` pattern). Tabs: Partners · Balance Sheet · P&L ·
  Manufacturing/Trading · Depreciation · Schedule IF · GST · Schedule AMT.
- `frontend/src/components/business/ITR5ScheduleBPManager.tsx` — firm PGBP (reuse the
  `ITR4ScheduleBPManager` shape, extend with 40(b) partner remuneration/interest ceiling UI).
- `frontend/src/components/business/PartnerManager.tsx` — partner capital/current/remuneration/interest.
- `frontend/src/components/business/DepreciationManager.tsx` — DEP/DOA/DPM/DCG/UD block editor.
- `frontend/src/components/business/BalanceSheetManager.tsx` + `ProfitLossManager.tsx` — PARTA_BS/PL.
- `frontend/src/domain/returns/editorModelV2.ts` — add `updateEntityProfile`, `updatePartners`,
  `updateShareholders`, `updateManufacturingAccount`, `updateTradingAccount`, `updateBalanceSheet`,
  `updateProfitLossAccount`, `updateScheduleBp`, `updateDepreciation` (copy `updateAmt`/`updateAssetLiability` shape).
- `frontend/src/domain/returns/factory.ts` — seed the new additive fields in `createEmptyReturnDraft`.
- `frontend/src/domain/returns/scheduleRegistry.ts` — wire ITR-5 schedules to `'available'`.
- `frontend/src/domain/returns/eligibility.ts` — ITR-5 rule blocks (firm/LLP/AOP/BOI/estate
  eligibility; 44AB audit threshold; AMT applicability).

**Existing files touched:**
- `frontend/src/pages/ITRComputationPage.tsx` — widen the `tabs[]` array: when `itrForm === 'ITR-5'`,
  render `<ITR5SchedulesWorkspace>` as a conditional tab (mirrors the ITR-2 conditional tab at index 9).
  Widen `assessFormEligibilityFromDraft` so it recommends ITR-5 when the client's `assesseeStatus`
  is a firm/AOP/BOI/estate code. Lift the `handleGenerateCbdtJson`/`handleDirectSubmit` ITR-3 block
  to also gate on ITR-5 readiness (open when ITR5-5 lands).
- `frontend/src/api/itrV2.ts` — already form-agnostic; no change.
- `frontend/src/domain/returns/filingPreflight.ts` — add firm PAN `F`-suffix gate, 44AB audit-flag
  gate, partner-remuneration-ceiling sanity gate.

### ITR5-7. Testing + golden suite + live UAT
- `tests/test_itr5_calculator.py` — unit tests per schedule + AMT + 40(b) ceiling + slab/surcharge.
- `tests/test_itr5_mapper.py` — `draft_to_itr5_input` round-trip tests.
- `tests/test_itr5_builder.py` — `build_itr5_json` + `validate_itr5_json` on golden scenarios.
- `tests/test_itr5_validators.py` — `run_input_validation`/`run_calc_validation` rule coverage.
- `tests/test_itr5_golden_suite.py` — mirror `test_itr1_golden_suite.py`; scenarios: plain firm,
  firm with 44AD, firm with 40(b) partners, firm with AMT (80IA claim), firm with BFLA losses.
- **Official JSON-schema validation** against `ITR-5_2026_Main_V1.1.json` for every golden scenario.
- **Live Type-2 UAT** `validateItr` + `submitItr` for ≥1 ITR-5 scenario before "production-ready"
  (per `Docs/ERI_UAT_AND_PRODUCTION_REFERENCE.md` — email `erihelp@incometax.gov.in` for Type-3
  sanity check first).
- **Regression:** `pytest tests/test_itr1_*.py tests/test_itr4_*.py tests/test_itr2_*.py -v` green.

**Phase ITR5 exit gate:** compute + generate + validate + download-pdf for ≥5 firm scenarios;
official schema passes for all; live UAT `validateItr` accepted; no ITR-1/2/4 regression.

---

## 5. Phase ITR6 — ITR-6 (Companies; DSC-only)

Sub-phased: ITR6-1 (schema+mapper), ITR6-2 (calculator+MAT), ITR6-3 (ITD builder+schema validator),
ITR6-4 (validators), ITR6-5 (gateway+orchestrator+filing router with DSC-only enforcement),
ITR6-6 (frontend), ITR6-7 (tests+golden suite+live UAT).

### ITR6-1. Schema + mapper
**New files:**
- `app/schemas/itr6.py` — `ITR6Input`. Reuse shared types from `itr1.py`/`itr2.py` (as ITR-5 does).
  Company-specific models: `CompanyProfile` (domestic/foreign, IndAS-applicable y/n, 115BAA/115BAB
  election, Form 10-IDA ack), `DirectorDetail` (name/PAN/DIN/residency-status), `ShareholderDetail`
  (>10% holding — name/PAN/address/% shareholding/nationality), `ScheduleMATData` (book profit u/s 115JB:
  net profit per P&L + additions + deductions = book profit; tax @ 15% of book profit), `ScheduleMATCData`
  (MAT credit carried forward, 15-year set-off), `ScheduleALData`, `ScheduleFDData` (foreign dividend
  u/s 115A/115Bba — special rate), `ScheduleSHData`, `IndASBalanceSheet`, `IndASProfitLoss`,
  `IndASManufacturingAccount`, `IndASTradingAccount` (the four IndAS variants — Schedule III /
  Companies Act Ind-AS structure, distinct from the non-IndAS `PARTA_BSFor6FrmAY13`/`PARTA_PL`).
- `app/engine/draft_to_itr6_input.py::draft_to_itr6_input(draft) -> tuple[ITR6Input, breakdown]`.
  Map `draft.entityProfile` (company subtype + IndAS flag + 115BAA/115BAB election),
  `draft.shareholders`, `draft.balanceSheet`/`profitLossAccount` (route to IndAS vs non-IndAS based
  on the IndAS flag), `draft.matDetails`, `draft.depreciation`, `draft.scheduleBp`. Reuse all shared
  head mappers from `draft_to_itr1_input`.

### ITR6-2. Calculator + MAT
**New file:** `app/engine/calculators/itr6.py::compute(input_data: ITR6Input) -> ITR6Result`.
Computation order:
1. PGBP (`CorpScheduleBP`) — same as ITR-5 step 1, minus the 40(b) partner ceiling (companies have
   no partners; director remuneration is salary u/s 17(1), not 40(b)).
2. Salary (director salary) + HP + CG (full) + VDA + OS + Schedule FD (foreign dividend special rate).
3. CYLA → BFLA → UD set-off.
4. Agricultural → partial integration.
5. Chapter VI-A + business deductions (80IA/IB/IC/IAC/LA/RA/10AA — companies can claim 80IC for
   industrially-developed-state undertakings, 80-IB for housing/industrial, etc.).
6. TI = GTI − deductions (rounded ₹10).
7. SI special-rate tax (111A/112A/VDA/115BB family/115BBA/115BBDA/115Bba).
8. **MAT (§115JB):** compute book profit from P&L (net profit + additions per 115JB(2) — depreciation
   per books, income-tax, transfer to reserves, etc. − deductions) and tax @ 15% of book profit
   (AY 2026-27: 15% on book profit up to ₹... threshold then 22.5% on excess — verify rate against
   CBDT rate card; extend `constants.py` with `MAT_RATE`). If MAT > regular tax, MAT applies and the
   difference is MAT credit (§115JAA) carried forward 15 years.
9. Slab tax — **company rate AY 2026-27: 25% (turnover ≤₹400cr) / 30% (turnover >₹400cr), plus
   surcharge 7% (>₹1cr, domestic) / 2% (>₹1cr, ≤₹10cr foreign) / 5% (₹10cr-₹100cr foreign), plus
   115BAA concessional 22% (domestic, no surcharge/cess incentives) / 115BAB 15% (new-manufacturing
   domestic).** Extend `constants.py` with `COMPANY_TAX_RATES_AY2627` + `CONCESSIONAL_RATES_115BAA/BAB`.
10. Rebate 87A — not available to companies (skip).
11. Surcharge (company tiers; 115BAA: no surcharge; 115BAB: no surcharge; regular: 7%/12% with marginal
    relief) + cess 4% (115BAA/BAB cess differs — verify).
12. Tax payable = max(MAT, regular tax). MAT credit utilisation = max(0, regular − MAT), capped at MAT
    credit balance.
13. Interest 234A/B/C + late fee 234F (234F applies to companies).
14. TDS/TCS credit + advance tax/SAT → net payable/refund.

**Existing files touched:** `app/engine/constants.py` (company rate tables, MAT rate, concessional
rates), `app/engine/common/surcharge.py` (company surcharge tiers), **new**
`app/engine/schedules/mat.py` (book-profit computation + MAT + MATC — the §115JB/§115JAA module,
reused only by ITR-6; if a future entity form needs MAT it can import this).

### ITR6-3. ITD builder + official schema validator
**New files:**
- `app/engine/itd/itr6.py::build_itr6_json(result, input_data) -> dict` — assembles
  `{"ITR":{"ITR6":{...}}}`. Reuse all `common.py` helpers. Build the IndAS vs non-IndAS BS/PL/
  Manufacturing/Trading based on the company's IndAS flag (omit the unused variant entirely — do not
  emit an empty placeholder). Build `ScheduleMAT`/`MATC`, `ScheduleSH`, `ScheduleAL`, `ScheduleFD`,
  the 115BAA/115BAB election in `PartA_GEN2For6`. Handle the four CLAUDE.md builder invariants.
- `app/engine/itd/itr6_schema.py` — copy `itr5_schema.py` structure; `_SCHEMA_RELATIVE_PATH` →
  `Reference Docs by CBDT & ITD/Official JSON Schema/ITR-6_2026_Main_V1.0.json`. `validate_itr6_json`.

### ITR6-4. CBDT rule validators
**New files:** `app/engine/validators/itr6/` package — `__init__.py`, `input_rules.py`
(`ITR6-R###`), `calc_rules.py` (`ITR6-C###`), `runner.py`, `official_rules_reference.py`
(transcribe the ITR-6 Validation Rules PDF). MAT-specific rules (book-profit additions/deductions
consistency, MATC balance ≤ prior-year MATC carry-forward) go in `calc_rules.py`.

### ITR6-5. Gateway dispatch + orchestrator + filing router (DSC-only)
**Existing files touched:**
- `app/engine/filing_gateway_v2.py` — replace the Phase 0 stub with `compute_canonical_itr6` +
  `_generate_cbdt_json_itr6` (same contract as ITR-5; `_itr6_filing_profile` with
  `personal_profile.normalize_personal_profile` + `Status` for company + IndAS flag).
- `app/engine/filing_orchestrator.py::produce_itd_json` — `ITR-6` accepted.
- `app/routers/filing.py` — `_normalize_form` accepts `ITR-6`. **DSC-only enforcement:** the
  Type-2 submit gate (line ~225) and Type-3 submit gate (line ~285) open for `ITR-6` **but reject
  `verification_mode == "AADHAAR_OTP" or "BANK_EVC"`** — companies cannot use EVC. Return 422
  "ITR-6 requires DSC verification (companies cannot use EVC)". The Type-2 `_submit_via_type2_api`
  path must carry the DSC-signed envelope (already supported by `app/eri/envelope.py::sign_data`
  for `ERI_DSC_SIGNING_MODE == "token"` on Windows; the Linux Type-3 deployment needs DSC via the
  portal-upload utility, not the REST path). Confirm the `filingSubmit.ts` `VerificationMode` union
  widens to include `"DSC"` for ITR-6.

### ITR6-6. Frontend
**New files:**
- `frontend/src/components/itr6/ITR6SchedulesWorkspace.tsx` — tabs: Directors · Shareholders ·
  Balance Sheet (IndAS/non-IndAS toggle) · P&L · Manufacturing/Trading · Depreciation · MAT/MATC ·
  Schedule SH · Schedule AL · Schedule FD · 115BAA/115BAB election.
- `frontend/src/components/business/DirectorManager.tsx` — director name/PAN/DIN/residency.
- `frontend/src/components/business/ShareholderManager.tsx` — >10% shareholder disclosure.
- `frontend/src/components/business/MatManager.tsx` — MAT book-profit + MATC carry-forward editor.
- `frontend/src/components/business/IndASBalanceSheetManager.tsx` — Schedule III IndAS BS.
- `frontend/src/domain/returns/editorModelV2.ts` — `updateDirectors`, `updateMatDetails`,
  `updateShareholders` (already added in Phase 0 for ITR-7 reuse — extend here for company fields).
- `frontend/src/domain/returns/scheduleRegistry.ts` — wire ITR-6 schedules to `'available'`.
- `frontend/src/domain/returns/eligibility.ts` — ITR-6 rule blocks (company PAN `C`-suffix;
  DSC-required warning; IndAS applicability from company type; 115BAA/BAB eligibility).

**Existing files touched:**
- `frontend/src/pages/ITRComputationPage.tsx` — conditional `<ITR6SchedulesWorkspace>` tab when
  `itrForm === 'ITR-6'`. The form-select dropdown surfaces the DSC-required warning chip for ITR-6.
  `handleDirectSubmit` for ITR-6 routes to the DSC path (new `VerificationMode = 'DSC'`), not EVC.
- `frontend/src/api/filingSubmit.ts` — widen `VerificationMode` to include `'DSC'`; the submit
  payload for DSC carries the DSC token reference, not an OTP.
- `frontend/src/domain/returns/filingPreflight.ts` — company PAN `C`-suffix gate, 115BAA/BAB
  election-ack gate, MAT-book-profit-positive gate, director-PAN-present gate.

### ITR6-7. Testing + golden suite + live UAT
- `tests/test_itr6_calculator.py` — MAT + MATC + concessional regimes + company slab/surcharge.
- `tests/test_itr6_mapper.py` — `draft_to_itr6_input` round-trip (IndAS vs non-IndAS variants).
- `tests/test_itr6_builder.py` — `build_itr6_json` + `validate_itr6_json`; IndAS variant tests.
- `tests/test_itr6_validators.py` — MAT consistency rules, director/shareholder presence rules.
- `tests/test_itr6_golden_suite.py` — scenarios: domestic company (regular), company with MAT +
  MATC utilisation, 115BAA company, 115BAB new-manufacturing, foreign company with Schedule FD.
- **Official JSON-schema validation** against `ITR-6_2026_Main_V1.0.json` for every golden scenario.
- **Live Type-2 UAT** with **DSC-signed** `validateItr` + `submitItr` for ≥1 ITR-6 scenario (DSC
  token mode, Windows, per `Docs/ERI_UAT_AND_PRODUCTION_REFERENCE.md` §12 — detached CMS, full
  certificate chain, no authenticated attributes).
- **Regression:** all prior test suites green.

**Phase ITR6 exit gate:** compute + generate + validate + download-pdf for ≥5 company scenarios
(both IndAS and non-IndAS); official schema passes; live DSC-signed UAT `validateItr` accepted;
no prior-form regression.

---

## 6. Phase ITR7 — ITR-7 (Trusts/Institutions/Political Parties; needs-legal-review)

Sub-phased: ITR7-1 (schema+mapper), ITR7-2 (calculator), ITR7-3 (ITD builder+schema validator),
ITR7-4 (validators), ITR7-5 (gateway+orchestrator+filing router + needs-legal-review flag),
ITR7-6 (frontend), ITR7-7 (tests+golden suite+live UAT).

### ITR7-1. Schema + mapper
**New files:**
- `app/schemas/itr7.py` — `ITR7Input`. Trust-specific models: `TrustProfile` (entity subtype:
  charitable trust/religious trust/§10(23C) institution/political party §13A/scientific research/
  trade union/PF/superannuation/ESI/news agency/other; 12A/12AB/10(23C) registration number +
  date; 80G approval; FCRA number where applicable), `TrusteeDetail`, `CorpusAccumulationData`
  (§11(2) accumulation — amount set aside, purpose, time limit 5 years, Form 9A/10 filing),
  `VoluntaryContributionData` (§11(1)(d) — donations received, corpus-flagged vs revenue,
  anonymous donations segregated for 115BBI), `IncomeExpenditureData` (the IE_I-IV variants:
  charitable/religious/political/other), `ObjectsAchievementsData` (Schedule OA), `EntityHoldingData`
  (Schedule ET — >2% voting power), `PoliticalPartyDetails` (Schedule PP — §13A), `ElectoralTrustDonation`
  (Schedule D/DA), `AuditReportDetails` (Schedule I/IA — 10B/10BB), `AnonymousDonationData`
  (115BBI — special rate 30%/60%/100% per type), `ScientificResearchData` (Schedule J).
- `app/engine/draft_to_itr7_input.py::draft_to_itr7_input(draft) -> tuple[ITR7Input, breakdown]`.
  Map `draft.entityProfile` (trust subtype + registration numbers), `draft.corpusAccumulation`,
  `draft.voluntaryContributions`, `draft.balanceSheet`, `draft.scheduleBp`. Reuse shared head mappers.

### ITR7-2. Calculator
**New file:** `app/engine/calculators/itr7.py::compute(input_data: ITR7Input) -> ITR7Result`.
Computation order:
1. PGBP (`CorpScheduleBP`) — trust's business/profession income if it carries on any (e.g. a
   hospital's paying-patient revenue); apply 11(4A)/11(5) conditions (business must be incidental
   to the main objects and separate books maintained). 40(b) does not apply (no partners), but
   trustee remuneration is governed by the trust deed.
2. Salary (employees — not the §13A political-party rule) + HP + CG + VDA + OS.
3. Voluntary contributions (donations) classification: corpus (§11(1)(d) — not taxable), revenue
   (taxable unless §11/12 exemption applies), anonymous (§115BBI special rate unless political
   party §13A — which is fully exempt but capped at ₹20,000 anonymous per source for the party to
   retain exemption; above that, 30% u/s 115BBI).
4. Application of income: §11(1)(a) — 85% of income applied to objects in India = exempt; if not
   applied, 15% deemed income. §11(2) — accumulation up to 5 years (Form 9A/10), corpus accumulation.
   §11(3)/11(3A) — deemed application of accumulated income. Track the accumulation timeline and
   the 5-year forfeiture rule.
5. CYLA — no BFLA (trusts generally cannot carry forward losses; trust losses are restricted).
   Schedule CYLA only.
6. Chapter VI-A — trusts can claim 80G receipt details (donations received with 50%/100% deduction
   flags), but most trust deductions are under §11/12, not Chapter VI-A.
7. TI = GTI − §11/12 application − deductions (rounded ₹10).
8. **115BBI special rate** (anonymous donations: 30% on revenue anonymous, 60%/100% on
   immovable-property anonymous); **115BBC** (anonymous donation to trust — 30%, but political
   party §13A path differs). Route through `schedules.special_rates`.
9. Slab tax — **trust/company-as-trust rate: 30%** (same as company for non-charitable
   non-§11 trust; §11/12 charitable trusts pay tax only on non-applied income at 30% — the maximum
   marginal rate does not apply to trusts whose income is applied to charity). Political parties
   §13A — no tax on income from house property/voluntary contributions/capital gains (subject to
   the ₹20,000 anonymous cap). Extend `constants.py` with `TRUST_TAX_RATE` + `MAX_MARGINAL_RATE`.
10. Surcharge (trust: 12% > ₹1cr; §13A political party: 30% surcharge on total income — special
    political-party surcharge) + cess 4%.
11. Interest 234A/B/C + late fee 234F (234F applies to trusts if total income exceeds the threshold;
    §13A political parties are exempt from 234F — verify).
12. TDS/TCS credit + advance tax/SAT → net payable/refund.

**Existing files touched:** `app/engine/constants.py` (trust rate, §13A surcharge), **new**
`app/engine/schedules/trust_application.py` (§11/12 application-of-income module — the
accumulation/corpus/anonymous-donation classifier, reused by ITR-7 only).

### ITR7-3. ITD builder + official schema validator
**New files:**
- `app/engine/itd/itr7.py::build_itr7_json(result, input_data) -> dict` — assembles
  `{"ITR":{"ITR7":{...}}}`. Reuse all `common.py` helpers. Build `PartB_TI`/`PartB_TI2`/`PartB_TI3`
  (the three total-income variants — select based on trust subtype: TI = charitable/religious,
  TI2 = §10(23C) institution, TI3 = political party §13A). Build `ScheduleAI`/`VC`/`IE_I-IV`/`OA`/
  `ET`/`SH`/`PP`/`D`/`DA`/`I`/`IA`/`J`/`R`/`115BBI`/`115TD`. Omit inapplicable variants entirely.
- `app/engine/itd/itr7_schema.py` — `_SCHEMA_RELATIVE_PATH` →
  `Reference Docs by CBDT & ITD/Official JSON Schema/ITR-7_2026_Main_V0.1.json`. `validate_itr7_json`.

### ITR7-4. CBDT rule validators
**New files:** `app/engine/validators/itr7/` package — `__init__.py`, `input_rules.py`
(`ITR7-R###`), `calc_rules.py` (`ITR7-C###`), `runner.py`, `official_rules_reference.py`.
Trust-specific rules: §11(1)(a) 85%-application threshold, §11(2) 5-year accumulation forfeiture,
12A/12AB registration-number presence (structural via Pydantic first), 115BBI anonymous-donation
classification, §13A ₹20,000 anonymous cap, 80G receipt-deduction flag consistency.

### ITR7-5. Gateway + orchestrator + filing router + needs-legal-review flag
**Existing files touched:**
- `app/engine/filing_gateway_v2.py` — `compute_canonical_itr7` + `_generate_cbdt_json_itr7`
  (`_itr7_filing_profile`).
- `app/engine/filing_orchestrator.py::produce_itd_json` — `ITR-7` accepted.
- `app/routers/filing.py` — `_normalize_form` accepts `ITR-7`. Submit gate: §13A political parties
  require DSC; other §11/12 trusts allow EVC or DSC. Add a **`needs_legal_review` flag** on the
  `FilingRecord` (new column — see §6.1 below) that the submit endpoint checks: if `True`, the
  endpoint returns 422 "This return requires legal review before filing (ITR-7 trust compliance)"
  until an explicit review-clear action sets it to `False`.

### ITR7-5.1. Needs-legal-review flag — DB + API
**New column:** `app/db/models.py::FilingRecord.needs_legal_review: bool = False` (default `False`;
set `True` only for ITR-7 until cleared). **Migration:** add the column via a Alembic-style
migration script (or, given the repo's SQLite convention, a `scripts/migrate_filing_legal_review.py`
that runs `ALTER TABLE filing_records ADD COLUMN needs_legal_review BOOLEAN DEFAULT 0`).
**New endpoint:** `POST /api/v1/filing/{client}/{ay}/ITR-7/mark-legal-reviewed` — owner-only,
sets `needs_legal_review = False`, logs `log_filing_action(action="legal_review_clear")`.
**New service:** `app/services/filing_record_service.py::set_legal_review_status(...)`.

The frontend surfaces the flag as a blocking banner on `ITRComputationPage` for ITR-7: "⚠️ This
trust return requires legal review before filing. Have counsel sign off, then click 'Mark legally
reviewed'." The submit button is disabled until the flag clears.

### ITR7-6. Frontend
**New files:**
- `frontend/src/components/itr7/ITR7SchedulesWorkspace.tsx` — tabs: Trust Profile · Trustees ·
  Corpus Accumulation · Voluntary Contributions · Income/Expenditure (IE variant) · Objects &
  Achievements · Entity Holdings · Political Party Details (if §13A) · Audit Report (10B/10BB) ·
  Scientific Research · Schedule D/DA (electoral trust donations).
- `frontend/src/components/trust/TrustProfileManager.tsx` — registration-number matrix.
- `frontend/src/components/trust/CorpusAccumulationManager.tsx` — §11(2) accumulation + 5-year tracker.
- `frontend/src/components/trust/VoluntaryContributionsManager.tsx` — donation classifier (corpus/
  revenue/anonymous) with 115BBI preview.
- `frontend/src/components/trust/IncomeExpenditureManager.tsx` — IE_I-IV variant editor.
- `frontend/src/components/trust/PoliticalPartyManager.tsx` — §13A details + anonymous ₹20k cap.
- `frontend/src/domain/returns/editorModelV2.ts` — `updateTrustCompliance`, `updateCorpusAccumulation`,
  `updateVoluntaryContributions`.
- `frontend/src/domain/returns/scheduleRegistry.ts` — wire ITR-7 schedules to `'available'`.
- `frontend/src/domain/returns/eligibility.ts` — ITR-7 rule blocks (trust/institution/political
  subtype; 12A/12AB registration; §11/12 application; §13A flag).

**Existing files touched:**
- `frontend/src/pages/ITRComputationPage.tsx` — conditional `<ITR7SchedulesWorkspace>` tab; the
  needs-legal-review blocking banner + "Mark legally reviewed" button; `handleDirectSubmit` for
  ITR-7 routes to DSC for §13A political parties, EVC-or-DSC for other trusts.
- `frontend/src/api/filingSubmit.ts` — `markLegalReviewed(clientId, ay)` →
  `POST .../mark-legal-reviewed`; `getLegalReviewStatus(clientId, ay)`.
- `frontend/src/domain/returns/filingPreflight.ts` — trust registration-number gate, §11 85%-
  application sanity gate, §13A anonymous-cap gate, 10B/10BB audit-report-presence gate
  (§44AB threshold applies differently to trusts — verify threshold in `dueDates.ts`).

### ITR7-7. Testing + golden suite + live UAT
- `tests/test_itr7_calculator.py` — §11 application, 115BBI, §13A exemption + anonymous cap, AMT (if
  applicable to the trust type — verify), trust rate + surcharge.
- `tests/test_itr7_mapper.py` — `draft_to_itr7_input` round-trip per trust subtype.
- `tests/test_itr7_builder.py` — `build_itr7_json` + `validate_itr7_json`; the three PartB_TI variants.
- `tests/test_itr7_validators.py` — registration-presence, 85%-application, 5-year-forfeiture,
  §13A anonymous-cap rules.
- `tests/test_itr7_legal_review.py` — `needs_legal_review` flag set/clear lifecycle, submit-block
  behaviour, `mark-legal-reviewed` endpoint.
- `tests/test_itr7_golden_suite.py` — scenarios: charitable trust (§11/12), religious trust,
  §10(23C) institution, political party (§13A, DSC), trust with anonymous donations (115BBI),
  trust with corpus accumulation (§11(2) 5-year), trust with foreign contributions (FCRA check).
- **Official JSON-schema validation** against `ITR-7_2026_Main_V0.1.json` for every golden scenario.
- **Live Type-2 UAT** with DSC for §13A political party + EVC/DSC for charitable trust ≥1 each.
- **Regression:** all prior test suites green.

**Phase ITR7 exit gate:** compute + generate + validate + download-pdf for ≥5 trust scenarios
covering all three PartB_TI variants; official schema passes; live UAT `validateItr` accepted for
both §13A (DSC) and §11/12 (EVC/DSC); needs-legal-review lifecycle verified; no prior-form regression.

---

## 7. Verification (applies to every phase)

Mirrors `Docs/ERI_UAT_EXPANSION_PLAN.md`'s verification block:

- **Digest/SW_ID correctness:** `compute_digest(json) == stamped Digest` round-trip for every
  generated file, under both `(ERI_MODE, ERI_ENV)` credential bundles.
- **Schema validity:** every generated JSON passes `jsonschema` validation against the matching
  official `Reference Docs by CBDT & ITD/Official JSON Schema/ITR-N_...json`.
- **CBDT rule validity:** `run_input_validation`/`run_calc_validation` report `can_upload=True`,
  zero Category-A blocking errors.
- **Regression:** `pytest tests/test_itr1_*.py tests/test_itr4_*.py tests/test_itr2_*.py
  tests/test_itr5_*.py tests/test_itr6_*.py tests/test_itr7_*.py -v` stays green through every
  phase — prior forms must never regress while a new form is built.
- **ITD sanity-check control:** one generated JSON per form, Type-3 flavor, emailed to
  `erihelp@incometax.gov.in` for ITD's offline sanity check before the rest of that mode's pack
  is emailed (no live Type-3 UAT portal — see `Docs/ERI_UAT_AND_PRODUCTION_REFERENCE.md` §2.1).

## 8. Update Discipline

After each phase: this plan's phase section gains a **"Delivered"** block (files actually touched,
verification actually run, any deviation from what the section originally said — same convention
`Docs/ITR4_V2_PIPELINE_AND_LEGACY_DELETION_PLAN.md` uses throughout). `Docs/ERI_UAT_EXPANSION_PLAN.md`'s
Master Phase Table rows 14/15/16 flip to ✅ with a one-line result summary and the commit hash.
`Docs/THE_COMPLETE_TAXIFY.md` Phase D.1.1/D.1.2/D.1.3 bullets update to point at this plan as the
authority. No phase after the current one starts until the user has tested and approved the one
before it.

## 9. Risk Register

| # | Risk | Mitigation |
|---|---|---|
| 1 | ITR-6 DSC-only filing breaks the existing EVC submit path | Add `VerificationMode = 'DSC'` to `filingSubmit.ts` + a DSC-token-reference field; the backend `sign_data()` path is already DSC-capable for Type-2 (Windows token mode) — verify the Type-3 portal-upload utility also carries DSC, not just EVC. |
| 2 | IndAS vs non-IndAS BS/PL divergence (ITR-6) | The schema flag is the single discriminator; the builder emits exactly one variant and omits the other (no empty placeholders). Test both variants in the golden suite. |
| 3 | MAT (§115JB) book-profit computation is error-prone | Dedicated `app/engine/schedules/mat.py` module with its own unit tests; `ScheduleMAT` validator cross-checks book profit = net profit + additions − deductions. |
| 4 | Trust §11 85%-application threshold + 5-year accumulation forfeiture | Dedicated `app/engine/schedules/trust_application.py` module with timeline tracking; `ScheduleAI` validator enforces the 5-year rule. |
| 5 | `_to_rupees()` pitfall across all three builders | Route every fresh accumulator through `_to_rupees()` exactly once; use `Decimal("0")` start for `sum()`; add a lint-style test that asserts no `Decimal` reaches the final JSON without `_to_rupees()`. |
| 6 | `ReturnDraft` additive field drift between backend and frontend | The additive block is mirrored 1:1 (Pydantic ↔ TS interface); `normalizeLoadedDraft` backfills missing fields on load. Add a contract test that `createEmptyReturnDraft().model_dump_json()` round-trips through `ReturnDraft.model_validate`. |
| 7 | ITR-7 legal-review flag forgotten on submission | The submit endpoint hard-checks `needs_legal_review == False` for ITR-7; a 422 is returned otherwise. The frontend banner is non-dismissible until cleared. |
| 8 | ITR-5/6/7 builder reuse of ITR-4's four live-call-verified invariants | Each builder explicitly handles: digest `iterations + 1`, Form 10-IEA cascade default `"N"`, empty-schedule omission, AlternateAddress/SecondaryAdd always present. Codify as a shared `_apply_common_invariants()` helper in `common.py` if divergence appears. |
| 9 | Form-selection dropdown overload (7 forms) | `evaluateEligibility` recommends exactly one form based on `assesseeStatus` + income evidence; the dropdown shows recommended (`★`) + blocker counts; entity forms only surface when the client's `assesseeStatus` matches. |
| 10 | Live UAT for ITR-6 (DSC) requires the Windows hardware token + whitelisted IP tunnel | Already provisioned per `Docs/ERI_UAT_AND_PRODUCTION_REFERENCE.md` §12/§14; confirm the token is present and the WireGuard tunnel to `13.204.49.125` is up before the UAT round. |

## 10. Out of Scope (explicit)

- **ITR-U (updated return u/s 139(8A))** — tracked separately in `Docs/THE_COMPLETE_TAXIFY.md`
  Phase D.1.4; the additional-tax tier computation (25%/50%/100%) is a distinct calculator concern,
  not part of this ITR-5/6/7 plan.
- **Rectification u/s 154** — Phase D.1.5; separate router, reuses the JSON path.
- **GST/TDS/MCA/ROC** — separate phases (H, I) in `Docs/THE_COMPLETE_TAXIFY.md`.
- **Practice-management layer** — Phase K; orthogonal to the compute engine.
- **WhatsApp e-verify bot** — Phase M; reuses `app/eri/type2/everify.py` once the entity forms
  can file, but is a separate build.

---

## 11. File Inventory (complete — new + touched)

### New backend files (per form phase)
- `app/schemas/itr5.py`, `app/schemas/itr6.py`, `app/schemas/itr7.py`
- `app/engine/draft_to_itr5_input.py`, `draft_to_itr6_input.py`, `draft_to_itr7_input.py`
- `app/engine/calculators/itr5.py`, `itr6.py`, `itr7.py`
- `app/engine/itd/itr5.py`, `itr6.py`, `itr7.py` + `itr5_schema.py`, `itr6_schema.py`, `itr7_schema.py`
- `app/engine/validators/itr5/`, `itr6/`, `itr7/` (each: `__init__.py`, `input_rules.py`,
  `calc_rules.py`, `runner.py`, `official_rules_reference.py`)
- `app/engine/schedules/mat.py` (ITR-6 MAT/MATC), `app/engine/schedules/trust_application.py` (ITR-7 §11/12)
- `scripts/migrate_filing_legal_review.py` (ITR-7 DB migration)

### New frontend files
- `frontend/src/components/itr5/ITR5SchedulesWorkspace.tsx`, `itr6/ITR6SchedulesWorkspace.tsx`,
  `itr7/ITR7SchedulesWorkspace.tsx`
- `frontend/src/components/business/` — `PartnerManager.tsx`, `DirectorManager.tsx`,
  `ShareholderManager.tsx`, `DepreciationManager.tsx`, `BalanceSheetManager.tsx`,
  `ProfitLossManager.tsx`, `MatManager.tsx`, `IndASBalanceSheetManager.tsx`,
  `ITR5ScheduleBPManager.tsx`
- `frontend/src/components/trust/` — `TrustProfileManager.tsx`, `CorpusAccumulationManager.tsx`,
  `VoluntaryContributionsManager.tsx`, `IncomeExpenditureManager.tsx`, `PoliticalPartyManager.tsx`

### Existing files touched (Phase 0 + per form phase)
**Backend:**
- `app/schemas/return_draft.py` (widen `ItrForm`, `AssesseeStatus`, `VerificationCapacity`; entity additive block)
- `app/engine/filing_gateway_v2.py` (stub → real dispatch branches per form)
- `app/engine/filing_orchestrator.py::produce_itd_json` (accept ITR-5/6/7)
- `app/engine/constants.py` (firm/company/trust/political-party rate tables + MAT rate)
- `app/engine/common/surcharge.py` (entity-type surcharge tiers)
- `app/routers/filing.py` (`_normalize_form` + submit gates; DSC-only for ITR-6; §13A DSC for ITR-7;
  `mark-legal-reviewed` endpoint for ITR-7)
- `app/routers/client_itr_v2.py::download_client_itr_pdf_v2` (widen 501 guard)
- `app/db/models.py::FilingRecord` (add `needs_legal_review` column)
- `app/services/filing_record_service.py` (legal-review status setter)

**Frontend:**
- `frontend/src/domain/returns/types.ts` (widen `ItrForm`, `assesseeStatus`; add entity interfaces)
- `frontend/src/domain/returns/factory.ts::createEmptyReturnDraft` (entity additive defaults)
- `frontend/src/domain/returns/editorModelV2.ts` (entity updaters)
- `frontend/src/domain/returns/canonicalRepository.ts::normalizeLoadedDraft` (entity backfill)
- `frontend/src/domain/returns/eligibility.ts` (7-form rule engine)
- `frontend/src/domain/returns/scheduleRegistry.ts` (7-form registry + entity schedules)
- `frontend/src/domain/returns/filingPreflight.ts` (entity-specific gates)
- `frontend/src/pages/ITRComputationPage.tsx` (conditional entity-schedule tabs; needs-legal-review banner)
- `frontend/src/api/filingSubmit.ts` (`VerificationMode = 'DSC'`; `markLegalReviewed`)

### New test files
- `tests/test_itr5_{calculator,mapper,builder,validators,golden_suite}.py`
- `tests/test_itr6_{calculator,mapper,builder,validators,golden_suite}.py`
- `tests/test_itr7_{calculator,mapper,builder,validators,legal_review,golden_suite}.py`
- `tests/test_return_draft_entity_additive.py` (Phase 0 contract round-trip)

---

*Plan end. Implement top-to-bottom; do not start a phase until the user approves the prior one.*

