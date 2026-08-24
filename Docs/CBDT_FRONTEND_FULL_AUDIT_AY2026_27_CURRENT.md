# Taxify Frontend vs CBDT ITR-1/2/3/4 Compliance Audit

**Assessment Year:** 2026-27
**Official schema version:** V1.1
**Audit date:** 6 August 2026
**Project:** `C:\Users\Devansh\Desktop\Taxify`
**Scope:** Current frontend, frontend state/persistence, API mapping, calculators, validators, ITD JSON builders, and official-download path.

---

## 1. Executive verdict

### Overall conclusion

**Taxify is not currently CBDT filing-compliant for any of ITR-1, ITR-2, ITR-3, or ITR-4 as an end-to-end frontend product.**

This does not mean every tax calculation is wrong. The project has meaningful and often sophisticated work in:

- Salary, house-property, other-source, deduction, TDS, challan, bank, and restricted section 112A editors.
- A normalized frontend return domain and compatibility serializer.
- Form-specific Pydantic models and tax calculators.
- Extensive ITR-1 and ITR-4 validation models.
- A comparatively mature canonical ITR-2 builder.

The decisive issue is that **the live frontend workflow does not turn the captured draft into an official, schema-validated CBDT artifact**. UI fields, persistence, computation, official serialization, and upload validation are separate layers; many fields exist in only one or two of those layers.

### Form-by-form readiness

| Form | Frontend capture | Active form computation | Official builder | Official schema validation | Filing readiness |
|---|---|---|---|---|---|
| ITR-1 | Broad common-income coverage; several dead/unmapped detail managers | Active for common inputs | Substantial typed builder, but disconnected from live draft | Not enforced by route | **Not filing-ready** |
| ITR-2 | Common editor plus restricted CG; most unique schedules missing | Active but highly lossy flat adapter | Broad prototype; 13 official blocks not emitted | Enforced only on direct typed endpoint | **Not filing-ready** |
| ITR-3 | No real ITR-3 business/accounting frontend | No active flat ITR-3 path; preview only | Stub-heavy, disconnected, structurally invalid | Not enforced | **Not implemented as a filing workflow** |
| ITR-4 | Partial 44AD/44ADA scalar UI; no live 44AE/details | Active presumptive computation | Ignores most typed input and fabricates critical values | Not enforced | **Not filing-ready** |

### Official schema sizes audited

| Form | Top-level blocks | Unconditionally required blocks | Resolved/nested field scale |
|---|---:|---:|---:|
| ITR-1 | 28 | 9 | 463 descendant property occurrences; 338 required occurrences |
| ITR-2 | 46 | 8 | 1,084 catalogued nested rows; 726 mandatory rows |
| ITR-3 | 69 | 12 | 3,469 resolved property nodes; 2,378 required occurrences |
| ITR-4 | 29 | 9 | 603 property occurrences; 374 required occurrences |

> “Optional” in a JSON schema means the block is not unconditionally present for every taxpayer. Many optional blocks become **conditionally mandatory** based on income, status, elections, deductions, assets, losses, audit applicability, or filing section.

---

## 2. Audit methodology and status definitions

### Authoritative sources

The audit used the local official AY 2026-27 V1.1 schemas:

- `ITD OFFICAL REFERENCE DOCS/AY 2026-27 Offical Schema JSON/ITR-1_2026_Main_V1.1 (1).json`
- `ITD OFFICAL REFERENCE DOCS/AY 2026-27 Offical Schema JSON/ITR-2_2026_Main_V1.1 (1).json`
- `ITD OFFICAL REFERENCE DOCS/AY 2026-27 Offical Schema JSON/ITR-3_2026_Main_V1.1 (1).json`
- `ITD OFFICAL REFERENCE DOCS/AY 2026-27 Offical Schema JSON/ITR-4_2026_Main_V1.1 (1).json`

The rule references in `tmp_itr1_rules.txt` through `tmp_itr4_rules.txt` and current validators were also inspected. For ITR-1, the file in the “schema validations txt” directory parses to the same schema structure and is not a separate rule matrix.

### Every field was evaluated across six layers

1. **Visible/editable UI** — Can a taxpayer enter the value?
2. **State persistence** — Does it survive save/reload?
3. **Active API mapping** — Does the live computation route consume it?
4. **Typed model/calculator** — Does it affect the correct form engine?
5. **ITD builder mapping** — Does it reach the official schema path?
6. **Artifact validation** — Is final JSON checked against the official V1.1 schema and rules?

### Status legend

| Status | Meaning |
|---|---|
| **Implemented** | Captured or legitimately derived, persisted, mapped, serialized, and validated end-to-end. |
| **Derived** | Correctly computed/generated from sufficient source evidence; no manual UI required. |
| **Partial** | Some fields or layers exist, but detail, conditionals, mapping, or validation is incomplete. |
| **Missing** | No usable frontend implementation. |
| **Dead/unmapped** | UI/state exists, but active computation or official serialization ignores it. |
| **Fabricated/defaulted** | Builder invents factual data rather than deriving it from taxpayer evidence. |
| **Invalid** | Mapping or output conflicts with the official schema/rules. |

---

## 3. Cross-form critical architectural failures

### C-01 — The frontend “JSON” button downloads an internal flat draft, not an official CBDT return

**Evidence:**

- `frontend/src/pages/ITRComputationPage.tsx` → `handleDownloadJson`
- `frontend/src/api/itr.ts` → GET `/clients/{clientId}/itr/{year}/download`
- `app/routers/client_itr.py:141-163`

The backend endpoint explicitly returns stored `form_data` as-is. It does not invoke a form calculator, ITD builder, official schema validator, digest generation, or conditional schedule validation.

**Impact:** The downloaded file is not guaranteed to contain the official `ITR` root, form object, required schedules, official field names, required arrays, metadata, or digest. This alone prevents end-to-end CBDT compliance for all four forms.

**Required fix:** Replace the live download with a typed artifact-generation endpoint that consumes the saved draft, chooses the selected form, runs form-specific validation/calculation, builds the official JSON, validates it against the official schema/rules, and only then downloads it.

### C-02 — Saving overwrites the selected form as only ITR-1 or ITR-4

**Evidence:** `app/routers/client_itr.py:35-49`.

The save endpoint derives `itr_type` only from turnover/profit. It ignores the selected `form`, ITR-2/ITR-3 requirements, residency, director status, unlisted shares, foreign assets, capital gains, losses, and other eligibility facts.

**Impact:** A selected or required ITR-2/ITR-3 can be persisted as ITR-1 or ITR-4.

### C-03 — The “Validate” action does not validate the official artifact

**Evidence:** `app/routers/client_itr.py:54-104` delegates to `/tax-summary/compute`.

It validates only the subset mapped into a computation model. It does not test:

- official JSON structure;
- all required properties;
- `additionalProperties: false`;
- nested array row requirements;
- final enums/patterns;
- cross-schedule rules;
- actual builder output.

A “Validation passed” message is therefore **not an uploadability result**.

### C-04 — Four overlapping data contracts drift independently

The project currently has:

1. Visible flat fields in `ITRComputationPage.tsx`.
2. Canonical `ReturnDraft` in `frontend/src/domain/returns/types.ts`.
3. Legacy serialization in `legacyAdapter.ts` / `legacySerializer.ts`.
4. Form-specific Pydantic inputs and separate flat mappers in `app/routers/tax.py`.

Unknown values are preserved in a compatibility envelope. This prevents data loss but allows dead fields to appear functional because they save/reload even when no filing model consumes them.

### C-05 — Official schema validation is asymmetric

- ITR-2 direct JSON generation calls an official-schema validator.
- ITR-1, ITR-3, and ITR-4 routes do not enforce equivalent final-schema validation.

All forms require one consistent artifact gateway.

### C-06 — Visible schedule checklist is informational, not proof of implementation

`frontend/src/domain/scheduleRegistry.ts` is useful but manually maintained and stale/inaccurate in places. A schedule marked “available” can still be lossy or dead in the active filing path. Missing schedules do not automatically create fields or block official generation.

---

# 4. ITR-1 detailed audit

## 4.1 Overall assessment

ITR-1 has the broadest live common-income UI, but no current live path creates and validates official ITR-1 JSON. Several detailed managers are more complete than old audits suggested, yet the active flat mapper reduces or drops their evidence.

### Top-level classification

| Classification | Count / blocks |
|---|---|
| Correctly derived inside typed builder but unreachable from live download | 4: CreationInfo, Form_ITR1, core TaxComputation, TaxPaid totals |
| Partial | 11: PersonalInfo, FilingStatus, IncomeDeductions, Refund, 80G, 80D, TDS1, TDS2, TaxPayments, LTCG112A, Verification |
| Dead/unmapped | 8: 80DD, 80U, 80E, 80EE, 80EEA, 80EEB, 80C details, Schedule EA 10(13A) |
| Missing | 4: 80GGA, 80GGC, TDS3, TaxReturnPreparer |
| Domain support but no usable live UI | 1: Schedule TCS |

## 4.2 Schedule-by-schedule matrix

| Official block | Mandatory status | Current implementation | Missing/incorrect implementation |
|---|---|---|---|
| `CreationInfo` | Always | Builder generates version, creator, date, city, digest | Live JSON button never invokes builder; no final schema validation |
| `Form_ITR1` | Always | Builder derives form/version/AY | Unreachable from normal frontend download |
| `PersonalInfo` | Always | Name, PAN, DOB, Aadhaar, contact and primary address visible | Canonical domain retains only name/PAN/email/mobile/DOB; alternate address absent; full typed filing profile not built; secondary contacts absent; status/contact mappings incomplete |
| `FilingStatus` | Always | Filing section and residential status visible; some revision fields exist in domain | Most conditional fields absent: seventh proviso details, notice cascade, assessee representative, complete revised return evidence; active mapper does not build official filing profile |
| `ITR1_IncomeDeductions` | Always | Core income totals computed | Many detailed source rows and deduction schedules are reduced to totals or dropped |
| `ITR1_TaxComputation` | Always | Tax engine computes core totals | Live official output path absent |
| `TaxPaid` | Always | TDS/TCS/challan totals calculated from valid rows | Invalid rows can remain in draft but be excluded; artifact path absent |
| `Refund` | Always | Full bank manager with six account types and refund flag now exists | Standalone `bankUseForRefund` checkbox is dead; exactly one refund account not enforced; official bank profile not reached |
| `Schedule80G` | Conditional | Four categories, donee PAN/address, cash/non-cash, ARN and references now captured | Active filing artifact bypasses builder; verify all schema names and qualifying-limit mapping; builder path must consume current rows |
| `Schedule80GGA` | Conditional | Backend typed support exists | No frontend manager, domain structure, flat mapping, or live artifact mapping |
| `Schedule80GGC` | Conditional | Backend typed support exists | No frontend capture or mapping |
| `Schedule80D` | Conditional | Four policy buckets, per-policy details, preventive checkup and medical expense UI exist | Active mapper reduces values; builder does not faithfully consume all policy/medical evidence in live flow |
| `Schedule80DD` | Conditional | UI has amount, nature/type, dependent, PAN/Aadhaar, UDID, Form 10-IA | **Dead:** active flat mapper does not construct typed schedule |
| `Schedule80U` | Conditional | UI has amount, nature/type, UDID, Form 10-IA | **Dead:** not mapped into active typed input |
| `Schedule80E` | Conditional | Structured multi-loan manager exists | Active mapper reads only scalar `s80E`; per-loan evidence is dropped |
| `Schedule80EE` | Conditional | Structured manager exists | Dead/unmapped |
| `Schedule80EEA` | Conditional | Structured loans and stamp-duty value exist | Dead/unmapped |
| `Schedule80EEB` | Conditional | Structured loans and vehicle registration exist | Dead/unmapped |
| `Schedule80C` | Conditional | Detailed investments with amount/date/institution/PAN/account now captured | Only aggregate affects calculation; official detail entries not constructed in active path |
| `ScheduleEA10_13A` | Conditional | Employer UI has basic, DA, HRA, rent, city/metro facts | Router expects separate `hraDetails`/`hraEntry`; canonical employer rows do not create it; official HRA schedule is dead/partial |
| `TDSonSalaries` | Conditional | Generic TDS editor and employer data exist | Employer/TDS row reconciliation not guaranteed; official path bypassed |
| `TDSonOthThanSals` | Conditional | Broad TDS section list and row fields | Deduction-year/carry-forward semantics incomplete; TCS codes incorrectly appear in TDS editor |
| `ScheduleTDS3Dtls` | Conditional | None | Missing tenant TDS schedule and identity/evidence model |
| `ScheduleTCS` | Conditional | Domain/serializer can preserve TCS | No rendered TCS manager; TCS entered in TDS selector maps incorrectly |
| `TaxPayments` | Conditional | Advance and self-assessment per-challan rows now captured | Conflicting BSR validation; final official mapping absent |
| `LTCG112A` | Conditional | Restricted eligible transaction editor and backend computation | Active typed evidence is reduced/lost before official builder; no final artifact validation |
| `Verification` | Always | Limited domain object exists | No complete visible declaration/capacity/place workflow; typed filing profile not constructed |
| `TaxReturnPreparer` | Conditional | None | Entire TRP block missing |

## 4.3 ITR-1 mandatory/conditional field gaps

### Personal and filing

**Missing or not end-to-end:**

- Explicit first/middle/surname model rather than unreliable full-name splitting.
- Alternate address and `SecondaryAdd` conditional block.
- Secondary mobile/email fields.
- Full filing-section enum and conditional evidence.
- Seventh proviso 139 flags, amounts, and detail rows.
- Revised/belated/notice details with schema patterns and conditionality.
- Representative assessee block.
- Complete verification declaration, capacity, place and date.
- Tax Return Preparer block.

### Salary

**Partial:**

- Detailed section 10 allowance rows are not faithfully serialized.
- Employer nature/address and salary-nature/perquisite-nature arrays are incomplete.
- HRA inputs are visible but do not reliably create `ScheduleEA10_13A`.
- Other statutory exemptions must be represented using official category codes rather than scattered scalar values.

### House property

The UI is now rich, including co-owners and loans, but typed official generation currently rejects common valid cases:

- Co-owned property.
- Positive section 24(b) interest without the separate typed schedule evidence expected by builder.

The active computation also uses only the first property aggregate in common paths. Property owner, address, co-owner, tenant, loan, and sequence evidence must be mapped directly to official rows.

### Other sources

- Gifts are captured but not reliably mapped into ITR-1 other-source income.
- Detailed nature-of-income rows remain incomplete.
- TCS must not be represented as TDS.
- ITR-1-ineligible winnings, racehorse, and VDA controls should be hidden/disabled or force a form switch immediately.

### Deductions

The frontend now contains more fields than older audits reported, but the active mapper still ignores most detail schedules. Required fixes include:

- Map 80C investment rows to typed `schedule_80c_entries`.
- Map 80DD and 80U complete schedule objects.
- Map all 80E/EE/EEA/EEB loan rows and 80EEA stamp-duty value.
- Implement 80GGA and 80GGC editors.
- Add 80GG/Form 10BA workflow if claimed.
- Ensure 80D policy and medical expense rows reach the builder exactly.

### Validation defects

- Save validator accepts alphanumeric BSR (`^[0-9]{3}[0-9A-Z]{4}$`) while editor/backend require seven digits.
- State code labels in the frontend dropdown do not match the standard ITD state code mapping.
- Client validation checks PAN length rather than the full official pattern.
- Exactly one refund account is not enforced.
- The official ITR-1 JSON is not validated against V1.1 before download.

---

# 5. ITR-2 detailed audit

## 5.1 Overall assessment

ITR-2 is currently a common-return editor with partial restricted capital gains. The repository contains a large canonical ITR-2 model/builder, but the live page bypasses the dedicated frontend `itr2Mapper.ts` and uses a lossy backend flat adapter.

### Key counts

- 46 official top-level blocks.
- 8 unconditionally required blocks.
- 13 official top-level schedules are not emitted by the canonical builder at all:
  - Schedule115AD
  - Schedule80C
  - Schedule80D
  - Schedule80G
  - Schedule80GGC
  - Schedule80DD
  - Schedule80U
  - Schedule80E
  - Schedule80EE
  - Schedule80EEA
  - Schedule80EEB
  - Schedule80GGA
  - TaxReturnPreparer

## 5.2 Schedule-by-schedule matrix

| Official block | Current status | Detailed gap |
|---|---|---|
| CreationInfo / Form_ITR2 | Derived | Only available through direct typed endpoint, not live JSON button |
| PartA_GEN1 | Mandatory gap | Active flat path does not construct `filing_profile`; alternate address, detailed filing status, director/unlisted rows, FII/FPI, representative and verification evidence missing |
| ScheduleS | Partial/lossy | Rich UI reduced to gross employer amounts; perquisites, profits in lieu, nature arrays and HRA evidence zero/empty in builder |
| ScheduleHP | Partial/lossy | UI supports multiple rich properties; active mapper uses first property and omits `property_filing_details` |
| ScheduleCGFor23 | Severe partial | UI supports only three restricted 112A asset types; almost all land/building, NRI, unlisted, other assets, exemptions, DTAA, pass-through, quarter accrual and loss matrix fields absent/zero |
| Schedule112A | Partial | ISIN/quantity/FMV UI exists, but active adapter drops several values and uses generic CG transaction; builder can default missing factual values |
| Schedule115AD | Missing | No UI, mapper, or builder output |
| ScheduleVDA | Dead/unmapped | Only aggregate `vdaGains`; no transaction dates/cost/consideration/head; not mapped into ITR2Input |
| ScheduleOS | Partial | Interest/dividend/pension map; winnings, gifts, racehorse, 89A, unexplained income, pass-through and DTAA detail absent or zero |
| ScheduleCYLA | Derived/partial | Computed from incomplete source baskets |
| ScheduleBFLA | Dead | UI has aggregate losses; active adapter maps none to `bf_losses` |
| ScheduleCFL | Missing in live path | No AY-wise loss ledger, filing date, head/subcategory rows |
| ScheduleVIA | Partial | Amount subset only; section-specific schedules absent |
| 80C/80D/80G/80DD/80U/loan schedules | Dead/unmapped | Detailed common UI does not become official ITR-2 schedules |
| Schedule80GGA / 80GGC | Missing | No frontend capture |
| ScheduleAMT / AMTC | Missing | No UI; canonical-only models cannot be reached from live page |
| ScheduleSPI | Missing | No specified-person clubbing editor |
| ScheduleSI | Dead/unmapped | Winnings UI computes local values but does not create `si_entries` |
| ScheduleEI | Dead/unmapped | Visible exempt fields are not mapped to ITR-2 exempt/agricultural models |
| SchedulePTI | Missing | No pass-through entity/head/TDS editor |
| ScheduleFSI | Missing | No country/TIN/head/tax-paid rows |
| ScheduleTR1 | Missing | No country/TIN/section/relief rows |
| ScheduleFA | Missing/severe partial | No UI; canonical generic asset model cannot faithfully cover all ten official FA categories |
| Schedule5A2014 | Missing | No spouse apportionment workflow |
| ScheduleAL | Missing/severe partial | No UI; canonical builder ignores immovable details |
| PartB-TI / PartB_TTI | Derived but unreliable | Computed from incomplete inputs; foreign asset flag and other facts can be wrong |
| ScheduleIT | Partial/dead | Challans captured, but active path does not create official rows |
| TDS1 / TDS2 | Partial | TDS2 builder forces head `OS`; current/brought-forward claims incomplete |
| TDS3 | Missing | No tenant TDS schedule |
| TCS | Partial | Domain lacks full section/year evidence; builder incomplete |
| Verification | Mandatory gap | Domain value exists but active path does not construct filing profile |
| TaxReturnPreparer | Missing | No capture/output |
| ScheduleESOP | Missing | No employee event/AY deferral editor; builder event details empty |

## 5.3 Capital-gains deficiencies

The visible asset selector supports only:

- listed equity;
- equity-oriented mutual fund;
- business trust unit.

The canonical ITR-2 model supports substantially more classifications, including land/building, 111A assets, unlisted shares, listed securities, debt/specified mutual funds, market-linked debentures, bonds/debentures, depreciable assets, jewellery, foreign assets, and other assets.

The active adapter drops or fails to collect:

- stamp-duty value;
- section 50CA FMV;
- indexed acquisition/improvement cost;
- improvement cost;
- explicit holding classification;
- complete 54/54B/54EC/54F/115F exemption and CGAS evidence;
- NRI/FII/DTAA/pass-through branches;
- quarter-wise accrual;
- complete current-year capital-loss set-off matrix.

**Invalid behavior:** missing transfer date is fabricated as `2026-03-31` in `app/routers/tax.py`. Missing filing evidence must block submission, not be invented.

## 5.4 Foreign, assets, losses and special income

These are the largest ITR-2 frontend omissions:

- Full FSI and TR schedules.
- Ten-category foreign asset schedule.
- AY-wise brought-forward and carried-forward losses.
- VDA transaction rows.
- SI rate-code rows.
- SPI clubbing.
- PTI pass-through income.
- Schedule 5A.
- Schedule AL.
- ESOP deferral events.
- AMT/AMTC where applicable.

### Incorrect Schedule AL trigger

`frontend/src/domain/scheduleRegistry.ts` uses `totalIncome > 50_000_000`, i.e. ₹5 crore, while its own description says ₹50 lakh and the audited validation reference indicates a different statutory threshold. This must be corrected from the official AY-specific rule source; a manually hard-coded registry predicate is unsafe.

---

# 6. ITR-3 detailed audit

## 6.1 Overall assessment

**ITR-3 is not operational.** It is currently a selectable label and provisional preview, not a functioning form-specific filing implementation.

### Confirmed critical failures

1. `/tax-summary/compute` has no ITR-3 branch.
2. Selected ITR-3 can fall through to ITR-1 or be treated as ITR-4 based on business scalar fields.
3. Minimal direct `ITR3Input` computation currently crashes due to stale CYLA arguments.
4. The builder accepts result aggregates rather than the complete ITR3Input, making most schedule serialization impossible.
5. Builder can emit only 36 of 69 official top-level blocks; 33 can never be emitted.
6. Synthetic builder output produced hundreds of official-schema errors.
7. No ITR-3-specific validation is integrated into direct routes despite validator modules existing.

## 6.2 Mandatory schedules

| Required schedule | Current state | Missing implementation |
|---|---|---|
| CreationInfo | Derived stub | No validated live artifact |
| Form_ITR3 | Derived stub | No live artifact |
| PartA_GEN1 | Partial/dead | Full filing identity/status not connected; defaults/hard-coded flags |
| PartA_GEN2 | Missing UI; fabricated builder | No audit/accountant/report/nature-of-business editor; builder emits all “N” and dummy code |
| PARTA_BS | Missing UI; invalid zero builder | No full capital, reserves, loans, assets, current assets/liabilities, provisions and cross-footing UI |
| PARTA_PL | Almost entirely missing | One scalar net profit is not a 167-field P&L; builder emits zero structure disconnected from taxpayer data |
| ITR3ScheduleBP | Severe partial | No full PGBP adjustment editor; dozens of disallowances, deemed incomes, depreciation, ICDS, specified/speculative branches absent |
| ScheduleCYLA | Broken | Calculator call is incompatible with current CYLAInput |
| ScheduleBFLA | Partial/dead | Scalar losses, no AY/head/subcategory ledger; no flat ITR-3 mapping |
| PartB-TI | Derived from broken/incomplete inputs | Not reliable |
| PartB_TTI | Derived with hard-coded refund data | Not reliable |
| Verification | Partial/dead | No complete editor; builder defaults values |

## 6.3 Business/accounting schedule audit

| Schedule | Status |
|---|---|
| ManufacturingAccount | Missing |
| TradingAccount | Missing |
| PARTA_OI | Missing |
| PARTA_QD | Missing |
| Audit information / accountant / report | Missing/dead |
| Nature of business | Partial typed model only; no UI; builder dummy value |
| Schedule GST | Empty builder; no regular-business UI |
| Schedule IF / partner in firm | Partial model; builder fabricates one firm and ignores actual rows |
| Schedule DPM | Missing |
| Schedule DOA | Missing |
| Schedule DEP | Zero summary, no asset-block source |
| Schedule DCG | Zero summary |
| Schedule UD | Inputs dead; calculator forces zero |
| Schedule ICDS | Only aggregate canonical values; no UI; builder zero |
| Schedule ESR | No input; builder zero stub |
| Schedule TPSA | Missing |
| Schedule 10AA / 80-IA / 80-IB / 80-IC / 80RA | Shared deduction totals may calculate, but dedicated builders emit dummy/zero structures |

### Full PGBP gaps

The UI currently exposes only:

- scheme;
- turnover;
- declared income;
- net profit;
- two brought-forward loss scalars.

A compliant ITR-3 needs, conditionally, detailed handling for:

- profit before tax;
- speculative and specified business;
- income credited but taxable under other heads;
- exempt income credited to P&L;
- expenses attributable to other/exempt heads;
- depreciation books vs Income-tax Act;
- sections 36, 37, 40, 40A, 43B and MSME disallowances;
- deemed incomes and section 41 etc.;
- ICDS increases/decreases;
- deductions allowable but not debited;
- section 35AD;
- rule 7/7A/7B/8 activities;
- presumptive sections within ITR-3 where legally applicable;
- full loss set-off interaction.

None of this is represented by the live business tab.

## 6.4 Missing ITR-3 top-level blocks

The current builder never emits 33 official blocks, including:

- ManufacturingAccount
- TradingAccount
- PARTA_OI
- PARTA_QD
- Schedule112A
- Schedule115AD
- Schedule5A2014
- Schedule80C/80D/80DD/80E/80EE/80EEA/80EEB/80G/80GGA/80GGC/80U
- ScheduleAL
- ScheduleAMT/AMTC
- ScheduleDOA/DPM
- ScheduleESOP
- ScheduleFA/FSI/TR1
- ScheduleIT
- SchedulePTI/SPI
- ScheduleTDS3
- ScheduleTPSA
- ScheduleVDA

## 6.5 Validation and output

The direct ITR-3 routes do not run the available ITR-3 validators. No official schema validator gates output. The builder also fabricates or defaults business identity, firm, bank, employer and schedule values.

**Conclusion:** ITR-3 requires a dedicated implementation project, not incremental field additions to the existing common page.

---

# 7. ITR-4 detailed audit

## 7.1 Overall assessment

ITR-4 calculation support is stronger than its frontend filing support. The live business UI exposes only 44AD, 44ADA and “Regular” scalar modes; it does not expose the richer normalized business model already present in TypeScript.

## 7.2 Presumptive schedule audit

| Area | UI | Active mapper | ITD builder | Verdict |
|---|---|---|---|---|
| 44AD | Turnover and declared income only | Can consume digital/non-digital only if nested imported data exists | Defaults BP kwargs to zero and hard-coded 44AD identity | Invalid/partial |
| 44ADA | Gross receipts and declared income only | Partial nested receipt mapping | Can serialize only if non-API `bp_scheme` kwarg is supplied; route does not supply it | Wrong-scheme/partial |
| 44AE | No live option/editor | Partial dormant vehicle mapping | Never emits vehicle rows | Missing |
| Business code/name/description | No live editor | Ignored | Hard-coded | Missing/fabricated |
| GSTIN turnover | Domain can persist | Ignored | Always empty/zero | Dead |
| Financial particulars | Partial dormant domain, no UI | Ignored | Always zero | Missing/dead |

### 44AD missing fields

- Digital/bank receipts.
- Cash receipts.
- Other-mode receipts.
- Separate 6% and 8% income.
- Business name.
- Official business code and description.
- GSTIN-wise turnover.
- Full financial particulars.

### 44ADA missing fields

- Digital/cash/other-mode split.
- Profession name/code/description.
- GSTIN turnover.
- Financial particulars.

### 44AE missing fields

- Vehicle registration number.
- Owned/leased/hired three-state value.
- Tonnage capacity.
- Holding period/months.
- Per-vehicle presumptive income.
- Nature-of-business rows.
- Partner salary/interest where applicable.

The dormant TypeScript boolean `leasedOrHired` cannot represent the official three-state enum `OWN/LEASE/HIRED`.

## 7.3 Schedule-by-schedule gaps

| Official block | Status | Detailed issue |
|---|---|---|
| PersonalInfo | Partial/fabricated | UI captures many fields, but builder ignores typed input and uses placeholder PAN/DOB/address/phone defaults |
| FilingStatus | Partial/dead | Only four filing choices; 10-IEA cascade, seventh proviso, representative and notice conditions absent; builder defaults values |
| IncomeDeductions | Aggregate only | Detailed salary, property and other-source rows empty |
| TaxComputation / TaxPaid | Derived | Computation totals exist; no final official validation |
| Refund | Dead/fabricated | Actual bank accounts ignored; builder emits placeholder account |
| Verification | Missing UI/fabricated | Domain default exists; builder uses father/PAN/place defaults |
| ScheduleBP | Severe partial/invalid | Route does not pass scheme/turnover kwargs; 44AD defaults; GST/financials zero; 44AE empty |
| ScheduleIT | Dead/fabricated | Actual challans discarded and replaced with fixed BSR/date/serial |
| TaxExmpIntIncDtls | Partial | Detailed exempt income rows empty |
| Schedule80G | Invalid | Actual rows ignored; non-zero builder uses field names that do not match official schema |
| Schedule80GGC | Missing/dead | Empty zeros only |
| Schedule80D | Dead | Detailed policies ignored; route supplies no aggregate kwargs, so zeros |
| Schedule80DD / 80U | Fabricated | Hard-coded disability and dependent identity rows emitted even without real evidence |
| Schedule80C / loans | Dead | Detailed rows captured but builder emits empty arrays and only totals |
| TDS salary / other | Dead builder | Actual typed lists ignored unless separate kwargs supplied |
| TDS3 | Missing | Comment only, no builder implementation |
| TCS | Fabricated | Actual collector rows replaced by one placeholder TAN |
| LTCG112A | Partial/strongest | Typed aggregate evidence is read; still needs end-to-end artifact validation |
| ScheduleEA10_13A | Missing | Not assembled despite HRA model availability |
| TaxReturnPreparer | Empty/default | No frontend workflow |

## 7.4 Critical false-data risks in ITR-4 builder

The builder currently invents or replaces factual taxpayer data:

- Default PAN/name/address/DOB/phone.
- Default filing status and due date choices.
- Hard-coded business code/name.
- Default scheme 44AD.
- Zero turnover despite typed business input.
- Fixed BSR, challan dates, and serial numbers.
- Placeholder bank account/IFSC.
- Placeholder verification father name/place.
- Fabricated 80DD/80U dependent PAN/Aadhaar and disability values.
- Placeholder TCS TAN.

A compliant builder must fail closed when required evidence is absent. It must never fabricate taxpayer declarations.

---

# 8. Cross-form frontend field gaps

## 8.1 Personal information and filing status

The shared Personal tab is not form-specific enough. Required additions include:

- Form-specific assessee status enum (Individual/HUF/Firm where allowed).
- Explicit name components.
- Correct state-code dictionary.
- Alternate address and secondary contacts.
- All `ReturnFileSec` values and conditional fields.
- Revised return acknowledgment/date.
- Notice section/number/date.
- Seventh proviso facts and amounts.
- Representative assessee.
- Form 10-IEA cascade for business forms.
- Director details and unlisted-share transaction details for ITR-2/3.
- FII/FPI and SEBI details.
- Verification acceptance, capacity, place, date.
- TRP details.

## 8.2 Salary

Current employer UI is broad, but official mappings need:

- Employer address and nature code per row.
- Nature-of-salary and nature-of-perquisite arrays.
- Exact section 10 allowance code rows.
- HRA schedule evidence mapping.
- 89A income/election details where relevant.
- Correct TDS1 linkage and reconciliation.

## 8.3 House property

Need end-to-end mapping for:

- Every allowed property.
- Structured address.
- Property owner enum and other-owner description.
- Co-owner serial/name/PAN/Aadhaar/share.
- Tenant array rather than single tenant fields where schema requires.
- Full rent/ALV facts.
- Section 24(b) per-loan rows.
- Arrears/unrealized rent.
- Pass-through property income.

## 8.4 Other sources

Need official source rows for:

- Interest categories.
- Dividend categories and quarter accrual.
- Family pension.
- Machinery/building rent.
- Gifts and inadequate consideration.
- Winnings, online games, racehorses.
- Section 68–69D unexplained income.
- 89A income.
- Pass-through income.
- DTAA income.
- Section 57/58/59 deductions/disallowances.

## 8.5 Deductions

Shared deduction managers must be wired to typed form inputs and official schedules. Missing editors include at least:

- 80GGA.
- 80GGC.
- 80GG/Form 10BA.
- Additional form-specific deductions such as QQB/RRB/business deductions where applicable.
- PRAN/fund-level evidence where the official schema requires it.

## 8.6 Tax credits and payments

- Separate TDS1, TDS2, TDS3 and TCS managers by official semantics.
- Deduction year/current-year claim/carry-forward values.
- Correct head-of-income selection.
- Actual BSR/date/serial mapping to official Schedule IT/TaxPayments.
- Exactly one refund account.
- Foreign-bank details when applicable.

---

# 9. Validation audit

## 9.1 Frontend validation is not schema-driven

The frontend currently mixes:

- save-time ad hoc checks;
- field-level visual checks;
- backend tax computation errors;
- schedule registry warnings;
- official validator modules used only by some direct routes.

This cannot guarantee compliance with hundreds of required, enum, pattern, bound, array-cardinality, and cross-field constraints.

## 9.2 Known validation problems

1. Conflicting BSR patterns.
2. Incorrect state-code labels.
3. PAN length-only check on client validation endpoint.
4. No exactly-one refund account rule.
5. Incomplete filing-section conditionality.
6. No official final-artifact validation for ITR-1/3/4.
7. ITR-3 direct routes do not run ITR-3 validators.
8. Eligibility checks use incomplete facts and manually maintained thresholds.
9. Missing facts can be replaced by fabricated builder defaults.
10. Presence of UI controls can mislead users when their values are dead/unmapped.

## 9.3 Required validation architecture

A return should have three explicit gates:

1. **Draft validation:** field syntax, required-if-visible, immediate UX.
2. **Form computation validation:** statutory calculation and eligibility rules.
3. **Artifact validation:** build official JSON, run official schema, run CBDT Category A/B/D rules against the exact artifact, and prevent download/upload on blocking errors.

---

# 10. Test results and what they prove

Executed during this audit:

- Frontend Vitest: **75 tests passed**.
- Frontend production build: **passed**, with one bundle-size warning.
- Selected ITR schema/integration tests: **34 passed**.

These results prove that current unit contracts and selected backend schemas are internally consistent. They do **not** prove end-to-end CBDT compliance because:

- There are no comprehensive component tests for the large filing editor.
- The live JSON action bypasses official builders.
- ITR-1/3/4 final output is not schema-gated.
- There is no full representative ITR-3 suite.
- Many tests validate models/calculators in isolation rather than UI → save → reload → official JSON.

Required end-to-end test pattern for each form:

1. Create a taxpayer draft through UI-level data structures.
2. Save and reload it.
3. Map to the correct typed input without defaults or loss.
4. Run form eligibility and Category A/B/D rules.
5. Compute.
6. Build official JSON.
7. Validate against official V1.1 schema.
8. Assert every entered factual value appears at its expected official path.
9. Assert no placeholder or fabricated identity/payment data exists.

---

# 11. Prioritized remediation plan

## Phase 0 — Stop false compliance signals (immediate)

1. Rename/disable the current “JSON” action until it generates official JSON.
2. Do not label a draft or schedule “CBDT compliant” solely from UI presence.
3. Block ITR-3 filing/download entirely until a real path exists.
4. Remove all builder-fabricated factual defaults; raise actionable missing-evidence errors.
5. Preserve the selected ITR form during save.

## Phase 1 — One canonical filing pipeline

1. Make `ReturnDraft` the sole frontend contract.
2. Create explicit complete typed mappers:
   - ReturnDraft → ITR1Input
   - ReturnDraft → ITR2Input
   - ReturnDraft → ITR3Input
   - ReturnDraft → ITR4Input
3. Remove or strictly isolate compatibility extras.
4. Ensure calculation, validation, and JSON generation consume the same typed input.
5. Add official schema validators for all four forms.
6. Make the live Download button call this pipeline.

## Phase 2 — Complete ITR-1 and ITR-4 first

### ITR-1

- Full filing profile and verification.
- Map current 80C/80D/80DD/80U/loan/80G managers.
- Implement 80GGA/80GGC/TCS/TDS3.
- Map property/co-owner/tenant/loan rows.
- Map HRA and allowance schedules.
- Enforce official schema and rule matrix.

### ITR-4

- Build a real multi-business presumptive editor.
- Add business/profession code dictionaries.
- Add digital/cash/other receipt splits.
- Add 44AE vehicle editor.
- Add GSTIN turnover and financial particulars.
- Rebuild builder to use `ITR4Input` directly.
- Map actual challans, banks, TDS/TCS, filing status and verification.

## Phase 3 — Dedicated ITR-2 frontend

Build dedicated schedule modules for:

- Full CG and 112A/115AD.
- VDA.
- BFLA/CFL.
- SI.
- FSI/TR1/FA.
- AL.
- AMT/AMTC.
- SPI/PTI.
- 5A.
- ESOP.
- All section-specific deduction schedules.

## Phase 4 — Dedicated ITR-3 implementation

Before UI expansion:

1. Fix the calculator crash.
2. Integrate ITR-3 validators.
3. Redesign builder to consume full ITR3Input.
4. Add official schema validation.

Then implement:

- PartA_GEN2.
- Full BS and P&L.
- PGBP adjustments.
- Manufacturing/trading/OI/QD.
- Depreciation blocks and UD.
- ICDS/ESR/TPSA.
- GST and partner-firm schedules.
- All shared ITR-2 schedules applicable to ITR-3.

## Phase 5 — Generated field catalog and traceability

Generate, from each official schema, a versioned catalog containing:

- JSON path.
- Type.
- Required status.
- Conditional rule references.
- Enum/pattern/min/max/cardinality.
- UI component/field ID.
- ReturnDraft path.
- typed input path.
- builder path.
- validation rule ID.
- test ID.

CI should fail whenever an official schema path lacks an approved classification: editable, legitimately derived, conditionally unsupported with filing blocker, or not applicable.

---

# 12. Final answer to the compliance question

### Is the entire frontend CBDT compliant for ITR-1 through ITR-4?

**No.**

### Does the frontend lack many mandatory and optional fields?

**Yes, especially for ITR-2 and ITR-3.** ITR-1 and ITR-4 now visibly contain more detail than older audit documents claim, but many of those newer fields are not connected to the active typed filing/serialization path.

### Most important distinction

A field is not implemented merely because:

- it appears on screen;
- it saves and reloads;
- a tax total changes; or
- a builder contains a similarly named key.

For compliance, it must survive the full chain:

**UI → canonical state → typed form input → statutory validation → calculator → official ITD path → official schema/rule validation → downloadable artifact.**

At present, that chain is incomplete for all four forms, and substantially absent for ITR-3.

---

## Appendix A — Primary source files reviewed

### Frontend

- `frontend/src/pages/ITRComputationPage.tsx`
- `frontend/src/pages/ITRComputationTabs.tsx`
- `frontend/src/components/EmployerEntryManager.tsx`
- `frontend/src/components/HousePropertyEntryManager.tsx`
- `frontend/src/components/CapitalGainsEntryManager.tsx`
- `frontend/src/components/Section80CManager.tsx`
- `frontend/src/components/Section80DManager.tsx`
- `frontend/src/components/DonationEntryManager.tsx`
- `frontend/src/components/DeductionLoanManager.tsx`
- `frontend/src/components/BankAccountManager.tsx`
- `frontend/src/domain/eligibility.ts`
- `frontend/src/domain/scheduleRegistry.ts`
- `frontend/src/domain/returns/types.ts`
- `frontend/src/domain/returns/legacyAdapter.ts`
- `frontend/src/domain/returns/legacySerializer.ts`
- `frontend/src/api/itr.ts`
- `frontend/src/api/itr2Mapper.ts`

### Backend

- `app/routers/tax.py`
- `app/routers/itr.py`
- `app/routers/client_itr.py`
- `app/schemas/itr1.py`
- `app/schemas/itr2.py`
- `app/schemas/itr3.py`
- `app/schemas/itr4.py`
- `app/engine/calculators/itr1.py`
- `app/engine/calculators/itr2.py`
- `app/engine/calculators/itr3.py`
- `app/engine/calculators/itr4.py`
- `app/engine/itd/itr1.py`
- `app/engine/itd/itr2.py`
- `app/engine/itd/itr3.py`
- `app/engine/itd/itr4.py`
- `app/engine/validators/itr1/*`
- `app/engine/validators/itr2/*`
- `app/engine/validators/itr3/*`
- `app/engine/validators/itr4/*`

## Appendix B — Verification commands

```text
npm --prefix frontend test
# 7 test files, 75 tests passed

npm --prefix frontend run build
# TypeScript and Vite build passed

py -m pytest tests/test_itr1_schemas.py tests/test_itr2_integration.py tests/test_itr4_schemas.py -q
# 34 passed
```

## Appendix C — Superseded audit warning

Older reports in the repository are useful historical references but are stale for current frontend presence. In particular, several previously reported missing fields now have UI managers (80C, 80D, deduction loans, refund-bank selection, advance-tax challans, disability details, state/country selectors). They remain listed as gaps in this audit only when their **active mapping or official serialization** is incomplete—not because the UI is absent.
