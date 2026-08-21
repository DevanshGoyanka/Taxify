# ITR-1 & ITR-4 Production-Readiness Audit — AY 2026-27

**Date:** 2026-08-21
**Scope:** End-to-end compliance audit of the ITR-1 and ITR-4 filing pipelines
against the official CBDT JSON schemas (`ITR-1_2026_Main_V1.1 (2).json`,
`ITR-4_2026_Main_V1.1 (2).json`), the frontend canonical `ReturnDraft` types,
the backend mappers, and the official-JSON builders.

**Method:** Ground-truth extracted directly from the official schema JSON
files (not from MD docs). A maximally-populated canonical draft was run
through `filing_gateway_v2.generate_cbdt_json` and the output JSON was
checked field-by-field against the schema's required-field inventory +
enum/capping inventory. Findings are evidence-backed with file:line
references.

---

## 1. Executive Summary

| Metric | ITR-1 | ITR-4 |
|---|---|---|
| Schema leaf fields (authoritative) | 601 | 655 |
| Required fields (deduplicated) | 247 | 236 |
| Enum/capping fields | 260 | 305 |
| Core-scenario coverage (present in generated JSON) | 92 / 247 | 94 / 236 |
| Schema gate (`validate_itr1/4_json`) | ✅ PASSES | ✅ PASSES |
| Frontend→backend→builder end-to-end | ✅ salary + HP + savings-int + salary-TDS | ✅ 44AD + 44ADA + 44AE |
| `print()` debug noise in pipeline | 0 (converted to `logger.debug`) | 0 |
| Known validator xfails | 0 (44AE conflict resolved) | 0 |

**Verdict:** Both ITR-1 and ITR-4 are **schema-compliant on the core
filing scenario** — `generate_cbdt_json` produces official JSON that
passes the full CBDT schema gate for every field the validator enforces
(enums, patterns, min/max cappings, required fields, type constraints).

The "missing" required fields surfaced by the audit are **conditional
schedules** (80G, 80GGA, 80GGC, 80D, 80E/EE/EEA/EEB, HRA, TDS-other-than-salary,
TCS, tax challans, LTCG-112A, co-owners, dividend date-ranges, 139(1) proviso).
These are only required **when the taxpayer has that income/deduction**; the
builder correctly omits them when inapplicable. The gaps below are
**frontend-capture gaps** (the field isn't collected) and **mapper
mismatches** (the field is collected but not wired to the builder), not
schema violations.

---

## 2. Critical Findings (P0 — must fix before broad production rollout)

### F1. `PersonalInfo.employerCategory` — frontend never captures it
- **Schema (ITR-1 & ITR-4):** `PersonalInfo.EmployerCategory` is **required**,
  enum `["CGOV","SGOV","PSU","PE","PESG","PEPS","PEO","OTH","NA"]`.
  Evidence: `audit_itr1_enums_cappings.csv` row `ITR.ITR1.PersonalInfo.EmployerCategory`.
- **Backend `ReturnDraft.PersonalInfo`:** `employerCategory: str` exists
  (`app/schemas/return_draft.py`).
- **Frontend `types.ts` `PersonalInfo`:** **MISSING the field** — see
  `frontend/src/domain/returns/types.ts:357-385` (fields end at
  `holdsUnlistedShares`).
- **`grep employerCategory frontend/src` → 0 matches** — the field appears
  nowhere in the frontend.
- **Builder behaviour:** `_filing_profile` defaults to `"OTH"`
  (`app/engine/filing_gateway_v2.py`): `employer_category=(personal.employerCategory or "OTH")`.
- **Risk:** `"OTH"` is schema-valid, so JSON passes — but a Central/State
  Govt employee is mislabelled as "OTH", which feeds the 80DD/80U and
  retrenchment rule branches in the CBDT validators
  (`app/engine/validators/itr1/input_rules.py`: rules keyed on
  `nature_of_employment` / `employer_category`). For ITR-1 this affects the
  standard-deduction and gratuity caps. **Capture gap, not a schema fail.**

### F2. `filingSection` → `ReturnFileSec` — incomplete mapping
- **Schema (ITR-1 & ITR-4):** `FilingStatus.ReturnFileSec` integer enum
  `[11, 12, 13, 14, 16, 17, 18, 20]`, min=11 max=20
  (`audit_itr1_enums_cappings.csv`).
- **Frontend `FilingStatus`:** `filingSection: '139(1)' | '139(4)' | '139(5)' | '119(2)(b)'`
  (`types.ts`).
- **Backend mapper** (`app/engine/filing_gateway_v2.py`):
  `section_codes = {"139(1)": 11, "139(4)": 12}` — **only 2 of 7 values mapped**.
- **Gap:** `139(5)` (revised, code 17) and `119(2)(b)` (code 16) are offered by
  the frontend but the mapper returns `None` for them → `return_file_section=None`
  → likely a schema violation OR an unintended default (11) for revised returns.
  Also codes 13, 14, 18, 20 (139(9), 167, CBDT notice, 173) aren't exposed at all.
- **Risk:** A revised return (`139(5)`) would be filed as `139(1)` original — a
  **filing-status mis-declaration**. P0 for production.

### F3. `stateCode` / `state` — typed `string`, not enum-constrained
- **Schema:** `PersonalInfo.Address.StateCode` enum `["01".."37"]` (ITR-1 & ITR-4);
  `PinCode` integer min=100000 max=999999.
- **Frontend `types.ts`:** `stateCode: string` (PersonalInfo),
  `state: string` (HouseProperty), `employerStateCode: string` (Employer) —
  **no enum union type**, no numeric capping on pin codes.
- **Backend:** mapper passes the string through; the schema gate rejects invalid
  values at generation time.
- **Risk:** The user can type any string into a state field; the backend rejects
  it only at CBDT-generation → the user loses work. Not a schema fail, but a
  **UX + data-quality gap**. The frontend should constrain state selection to
  the schema's enum (a `<select>` of 36 state codes).

### F4. `Employer.natureOfEmployment` — typed `string`, schema enum unconstrained
- **Schema (ITR-1):** drives `ITR1Input.nature_of_employment`; the CBDT rule
  suite branches on government/private/PSU (`app/engine/validators/itr1/input_rules.py`
  — rules keyed on `inp.nature_of_employment`).
- **Frontend `types.ts`:** `natureOfEmployment: string` — no enum.
- **Mapper** (`app/engine/draft_to_itr1_input.py:678`): sets
  `nature_of_employment` from `draft.employers[0].natureOfEmployment` (fixed in Phase 6).
- **Risk:** Free-text → mismatches the CBDT enum branches → Category A rule
  misfire or, if the schema validates the value, a generation failure.

---

## 3. Important Findings (P1 — correctness / completeness)

### F5. ITR-1 `deductions.section80D` — mapper reads a flat-blob shape, not the canonical typed list
- **Backend `ReturnDraft.Deductions`:** `section80D: list[Policy80D]`
  (`app/schemas/return_draft.py`).
- **ITR-1 mapper `_map_80d`** (`app/engine/draft_to_itr1_input.py:309`):
  reads `section.selfSeniorCitizen` directly on the **list** object →
  `AttributeError: 'list' object has no attribute 'selfSeniorCitizen'`.
- **Evidence:** The audit script crashed here
  (`build_full_itr1_draft` with `section80D` populated → mapper raises).
- **Impact:** **80D deduction mapping is broken for any draft that carries
  a 80D policy.** The CBDT `Schedule80D` block is never emitted for ITR-1.
  The 155 "missing" required fields in the ITR-1 audit include the entire
  `Schedule80D.*` subtree (12 fields) — this is why.
- **Fix:** `_map_80d` must iterate `draft.deductions.section80D` (a list of
  `Policy80D`) and build the `Sec80DSelfFamHIDtls` structure, not read scalar
  attributes off the list.

### F6. ITR-1 `deductions.section80C` — same shape as F5 (typed list)
- `section80C: list[Investment80C]` in the canonical model; the mapper
  (`_map_deductions` / `_map_80c`) must iterate the list. Verify it doesn't
  read scalar attributes off the list (same bug class as F5). The audit
  couldn't test this because F5 crashed first.

### F7. ITR-1 `employerCategory` capture — F1 above means the CBDT validators'
  government-employee branches never fire correctly.
  Evidence: `app/engine/validators/itr1/input_rules.py` rules keyed on
  `inp.nature_of_employment` (e.g. gratuity/retrenchment caps) — these take
  the "OTH" default path for every taxpayer.

### F8. TAN must match a city-prefix pattern, not just the `AAAAA9999A` regex
- **Schema (ITR-1):** `TDSonSalaries…EmployerOrDeductorOrCollectDetl.TAN`
  pattern is a long alternation of city prefixes
  (`DEL[A-Z][0-9]{5}[A-Z] | BLR... | MUM... | ...`).
- **Frontend `Employer.employerTAN: string`** — no pattern enforcement.
- **Evidence:** The audit's first TDS fixture used `ABCD12345E` → schema
  rejected it; switched to `DELX12345A` → passed.
- **Risk:** A taxpayer entering a syntactically-valid-but-city-wrong TAN is
  rejected only at generation. The frontend should validate against the city
  prefix list (or at least warn).

---

## 4. Coverage Detail — ITR-1 (core scenario)

**Generated JSON:** `audit_itr1_generated.json` — passes
`validate_itr1_json`.

**Present (92/247):** PersonalInfo (DOB, PAN, MobileNo, CountryCodeMobile,
SecondaryAdd, EmployerCategory), FilingStatus.ReturnFileSec,
CreationInfo.JSONCreationDate, GrossSalary, NetSalary, DeductionUs16,
IncomeFromSal, PropertyDetails[] (HPSNo, ALV, 30% std ded, IntOnBorwCap…),
TDSonSalaries.TDSonSalary[], TotalTDSCutSal, TotalTDS, TaxPaidTot,
ExmpIncSec10, GrossTotIncome, DeductionUndChapVIA, ChapterVIA,
TotalIncome, TotalTaxPayable, BalTaxPayable, plus all schedule totals.

**Missing (155) — all conditional, categorized by schedule:**

| Schedule | Fields missing | Conditional trigger |
|---|---|---|
| `Schedule80C` (3) | Schedule80CDtls[].Amount/IdentificationNo, TotalAmt | taxpayer claims 80C |
| `Schedule80D` (16) | Sch80DInsDtls[] (InsurerName/PolicyNo/HealthInsAmt), TotalPayments (×4 sub-blocks) | taxpayer claims 80D health insurance |
| `Schedule80DD`, `Schedule80U` (2) | DeductionAmount | disability deduction |
| `Schedule80E` (6) | LoanTknFrom/DateofLoan/TotalLoanAmt/Interest80E + Total | education-loan interest |
| `Schedule80EE`/`80EEA`/`80EEB` (18) | loan + interest fields | first-home / affordable housing / EV loans |
| `Schedule80G` (28) | Don100/50Percent (+ApprReqd) DoneeWithPan[], totals | donations u/s 80G |
| `Schedule80GGA` (8) | DonationDtlsSciRsrchRuralDev[], totals | scientific-research donations |
| `Schedule80GGC` (8) | Schedule80GGCDtls[], totals | political-party donations |
| `ScheduleEA10_13A` (8) | HRA schedule (Placeofwork, ActlHRARecv, RentPaid…) | HRA claim |
| `TDSonOthThanSals` (4) | AmtForTaxDeduct/TotTDSOnAmtPaid/ClaimOutOfTotTDSOnAmtPaid | non-salary TDS |
| `ScheduleTDS3Dtls` (4) | TDS3Details[] | tenant TDS (rent > 50L) |
| `ScheduleTCS` (5) | AmtTaxCollected/TotalTCS/AmtTCSClaimedThisYear | TCS credit |
| `TaxPayments` (4) | DateDep/SrlNoOfChaln/Amt/TotalTaxPayments | self-assessment challans |
| `LTCG112A` (3) | TotSaleCnsdrn/TotCstAcqisn/LongCap112A | listed-equity LTCG (rare in ITR-1) |
| `clauseiv7provisio139i` (2) | 139(1) proviso nature + amount | seventh-proviso filing |
| `AssesseeRep` (2) | CountryCodeRepMobileNo/RepMobileNo | representative assessee |
| `PropertyDetails[].CoOwners/TenantDetails` (2) | SNo | joint-owned / let-out property |
| `Section24B` (6) | loan details | home-loan interest on let-out HP |
| `DividendInc.DateRange` (5) | dividend bucket dates | dividend income |
| `AllwncExemptUs10`/`ExemptIncAgriOthUs10` (2) | SalOthAmount/OthAmount | exempt income |

**Conclusion:** Every missing field is conditional. To exercise them, the
draft must carry that income/deduction, AND the mapper+builder must wire it.
The blockers are F5 (80D) and F6 (80C) — the other schedules were not tested
because F5 crashed the audit; they need their own fixture + mapper review.

---

## 5. Coverage Detail — ITR-4 (core scenario, 44AD)

**Generated JSON:** `audit_itr4_generated.json` — passes
`validate_itr4_json`.

**Present (94/236):** CreationInfo, PersonalInfo (full), FilingStatus
(ReturnFileSec, ResidencyStatus, PrincipalPlace), Form_ITR4
(FormName/Description/AssessmentYear), ScheduleBP — **all 10 sub-sections
populated** (NatOfBus44AD, PersumptiveInc44AD, NatOfBus44ADA,
PersumptiveInc44ADA, NatOfBus44AE, GoodsDtlsUs44AE[], PersumptiveInc44AE,
TurnoverGrsRcptForGSTIN, TotalTurnoverGrsRcptGSTIN, FinanclPartclrOfBusiness),
ITR4_IncomeDeductions (GrossSalary, PresumptiveIncome, PGBPIncome,
IncomeFromBus, GrossTotIncome), TotalTaxPayable, etc.

**Missing (142) — conditional, same pattern as ITR-1:**
80G/80GGA/80GGC donations, 80CCC pension, co-owners/tenants, Section24B loan
details, dividend date-ranges, `clauseiv7provisio139i` (139 proviso),
`AssesseeRep` mobile, `AllwncExemptUs10`, TDS-other-than-salary (if no
non-salary TDS), ScheduleTDS3, ScheduleTCS.

**Note:** ITR-4's `GoodsDtlsUs44AE` is correctly `[]` for a 44AD draft
(no vehicles). The 44AE fixture (tested in `test_filing_gateway_v2_itr4.py`)
now emits the full `RegNumberGoodsCarriage`/`OwnedLeasedHiredFlag`/
`TonnageCapacity`/`HoldingPeriod`/`PresumptiveIncome` block (Phase 8b fix).

---

## 6. Field-by-Field Mapping: ITR-1

Schema path → frontend type → backend model → builder function. "✅" = wired
end-to-end and present in generated JSON; "⚠️" = captured but gap; "❌" = not
captured / not wired.

### 6.1 PersonalInfo (`ITR.ITR1.PersonalInfo`)
| CBDT schema field | Frontend `types.ts` | Backend `ReturnDraft.PersonalInfo` | Builder | Status |
|---|---|---|---|---|
| `Address.Name.FirstName` | `firstName: string` | `firstName` | `_filing_profile` | ✅ |
| `Address.Name.MiddleName` | `middleName` | `middleName` | `_filing_profile` | ✅ |
| `Address.Name.SurNameOrOrgName` | `surnameOrOrgName` | `surnameOrOrgName` | `_filing_profile` | ✅ |
| `PAN` | `pan` | `pan` | `_filing_profile` | ✅ |
| `DOB` (date pattern) | `dateOfBirth: string\|null` | `dateOfBirth` | `_filing_profile` | ✅ |
| `Address.CountryCodeMobile` | `countryCode: string` | `countryCode` | `_filing_profile` | ✅ |
| `Address.MobileNo` | `mobile: string` | `mobile` | `_filing_profile` | ✅ |
| `Address.StateCode` (enum 01-37) | `stateCode: string` ⚠️ | `stateCode` | `_filing_profile` | ⚠️ F3 |
| `Address.PinCode` (int 100000-999999) | `pinCode: string` | `pinCode` | `_filing_profile` | ⚠️ no capping |
| `EmployerCategory` (enum) | **MISSING** ❌ | `employerCategory` | defaults to `"OTH"` | ❌ F1 |
| `SecondaryAdd` (Y/N) | (not on PersonalInfo) | `secondaryAddressDifferent` | `_filing_profile` | ✅ |
| `Aadhaar` | `aadhaar` | `aadhaar` | `_filing_profile` | ✅ |
| `Status` (I/H/F) | (not exposed) | `status` | `_filing_profile` | ✅ defaults |

### 6.2 FilingStatus (`ITR.ITR1.FilingStatus`)
| CBDT field | Frontend | Backend | Builder | Status |
|---|---|---|---|---|
| `ReturnFileSec` (enum 11-20) | `filingSection: '139(1)'\|'139(4)'\|'139(5)'\|'119(2)(b)'` | `filing.filingSection` | `section_codes` map | ❌ F2 (only 2/7 mapped) |
| `ReturnType` (O/R) | `returnType: 'ORIGINAL'\|'REVISED'` | `filing.returnType` | `_filing_profile` | ✅ |

### 6.3 Salary / TDS (`ITR.ITR1.ITR1_IncomeDeductions` + `TDSonSalaries`)
| CBDT field | Frontend | Backend | Builder | Status |
|---|---|---|---|---|
| `GrossSalary` | `Employer.basic/da/...` | `Employer` list | `draft_to_itr1_input._map_salary` | ✅ |
| `TDSonSalaries[].EmployerOrDeductorOrCollectDetl.TAN` (city pattern) | `employerTAN: string` ⚠️ | `Employer.employerTAN` | `_tds_salary_from_input` | ⚠️ F8 |
| `TDSonSalaries[].EmployerOrDeductorOrCollectDetl.Name` | `employerName` | `Employer.employerName` | `_tds_salary_from_input` | ✅ |
| `NatureOfEmployment` (drives rules) | `natureOfEmployment: string` ⚠️ | `Employer.natureOfEmployment` | `draft_to_itr1_input:678` | ⚠️ F4 |

### 6.4 House Property (`PropertyDetails[]`)
| CBDT field | Frontend | Backend | Builder | Status |
|---|---|---|---|---|
| `Rentdetails.AnnualLetableValue` etc. | `HouseProperty.annualRent/...` | `HouseProperty` list | `_map_house_property` | ✅ (self-occ tested) |
| `CoOwners[].CoOwnersSNo` | `coOwners: CoOwner[]` | `HouseProperty.coOwners` | builder emits when `isCoOwned` | conditional ✅ |
| `Section24B.Section24BDtls[].LoanTknFrom/DateofLoan/...` | `HomeLoan.lenderType/lenderName/...` | `HouseProperty.homeLoans` | `_map_house_property` | conditional (let-out+loan) |
| `TenantDetails[].TenantSNo` | `tenantDetails: TenantDetail[]` | `HouseProperty.tenantDetails` | builder | conditional |

### 6.5 Deductions (Chapter VI-A) — **BLOCKED by F5/F6**
| CBDT schedule | Frontend | Backend | Mapper | Status |
|---|---|---|---|---|
| `Schedule80C.Schedule80CDtls[].Amount/IdentificationNo` | `Investment80C.amount/investmentType` | `Deductions.section80C: list[Investment80C]` | `_map_deductions` | ⚠️ verify (F6) |
| `Schedule80D.Sec80DSelfFamHIDtls.Sch80DInsDtls[]` | `Policy80D.policyType/premiumAmount` | `Deductions.section80D: list[Policy80D]` | `_map_80d` | ❌ F5 (crashes) |
| `Schedule80G/80GGA/80GGC` | `Donation80G` etc. | `Deductions.section80G` | `_schedule_80g` | not tested |
| `UsrDeductUndChapVIA.PensionContribution80CCC` | (not in types) | — | — | ❌ not captured |

### 6.6 Tax Payments / TDS-other / TCS
| CBDT field | Frontend | Backend | Builder | Status |
|---|---|---|---|---|
| `TaxPayments.TaxPayment[].DateDep/SrlNoOfChaln/Amt` | `TaxChallan` | `draft.taxes.challans` | builder emits when present | conditional |
| `TDSonOthThanSals.TDSonOthThanSal[]` | `TdsCredit` | `draft.taxes.tds` | builder emits non-salary TDS | conditional |
| `ScheduleTDS3Dtls` (tenant TDS) | `TdsCredit.schedule==='TDS3'` | `draft.taxes.tds` | `_schedule_tds3` | conditional |
| `ScheduleTCS.TCS[]` | `TcsCredit` | `draft.taxes.tcs` | `_schedule_tcs` | conditional |

---

## 7. Field-by-Field Mapping: ITR-4

### 7.1 PersonalInfo / FilingStatus — same as ITR-1 §6.1-6.2 (shares the model).
Same gaps (F1 employerCategory, F2 ReturnFileSec, F3 stateCode).

### 7.2 ScheduleBP (`ITR.ITR4.ScheduleBP`) — **fully wired**
| CBDT field | Frontend | Backend | Builder | Status |
|---|---|---|---|---|
| `NatOfBus44AD[].NameOfBusiness/CodeAD` | `Presumptive44AD.businessName/natureCode` | `Presumptive44AD` | `_generate_cbdt_json_itr4` | ✅ |
| `PersumptiveInc44AD.GrsTotalTrnOver/GrsTrnOverBank/...TotPersumptiveInc44AD` | `digitalReceipts/nonDigitalReceipts/declaredIncome` | `Presumptive44AD` | `_schedule_bp` | ✅ (all 7 fields present) |
| `NatOfBus44ADA/44AE` | `Presumptive44ADA/44AE` | typed models | builder | ✅ |
| `GoodsDtlsUs44AE[].RegNumberGoodsCarriage/OwnedLeasedHiredFlag/TonnageCapacity/HoldingPeriod/PresumptiveIncome` | `VehicleRecord.vehicleNumber/leasedOrHired/tonnage/ownedMonths` | `GoodsCarriageVehicle` (extended Phase 8b) | `_goods_dtls_44ae` | ✅ (Phase 8b) |
| `TurnoverGrsRcptForGSTIN[].GSTINNo/AmtTurnGrossRcptGSTIN` | `GstinTurnoverRow.gstin/turnover` | `Presumptive44AD.gstinTurnovers` | builder | ✅ |
| `FinanclPartclrOfBusiness` (14 fields) | `FinancialParticulars.*` | `Presumptive44AD.financialParticulars` | `_schedule_bp` | ✅ |

### 7.3 IncomeDeductions (`ITR.ITR4.IncomeDeductions`)
| CBDT field | Frontend | Backend | Builder | Status |
|---|---|---|---|---|
| `GrossSalary`, `SalaryNotIncPrkgs`, `AllowNotExempt` | `Employer.*` | `draft.employers` | ITR-4 salary mapper | ✅ |
| `PresumptiveIncome44AD/ADA/AE` | `Presumptive44AD/ADA/AE.declaredIncome` | typed | `_generate_cbdt_json_itr4` | ✅ |
| `IncomeFromHP` | `HouseProperty` | `draft.houseProperties` | shared HP mapper | conditional |
| `GrossTotIncome`, `TotalDeductionUndChapVIA`, `TotalIncome` | computed | computed | builder | ✅ |

### 7.4 Tax Payments / TDS — same shape as ITR-1 §6.6 (conditional schedules).

---

## 8. Enum & Numeric-Capping Compliance

The CBDT schema enforces **260 enum/capping fields (ITR-1)** and **305
(ITR-4)**. The validator (`validate_itr1/4_json`) runs on every
`generate_cbdt_json` call and rejects any violation, so **no non-compliant
JSON can be emitted**. Key constraint families:

| Constraint family | Count (ITR-1/4) | Enforced where |
|---|---|---|
| Integer money capping (min/max) | 0 / 281 | schema gate (every Money field) |
| String enums (state, category, Y/N) | 260 / 22 | schema gate + builder defaults |
| Numeric enums (ReturnFileSec, etc.) | shared | schema gate |
| Pattern (PAN/Aadhaar/TAN/dates) | many | schema gate |

**Frontend enforcement gap:** the frontend `types.ts` uses `string` for
most enum-capped fields (`stateCode`, `natureOfEmployment`, `employerTAN`,
`filingSection` partial). Only `propertyOwnerType`, `lenderType`,
`residentialStatus`, `propertyType` use union types. The schema gate is the
**sole** enforcement point for most enums — meaning invalid values surface
late (at CBDT-generation, not at input). **Recommendation:** add union types
or `<select>` validators in the frontend for the top enums: StateCode
(36), EmployerCategory (9), ReturnFileSec (7), natureOfEmployment, TAN city-prefix.

---

## 9. Action Items (prioritised)

| Pri | Finding | Fix |
|---|---|---|
| P0 | F2 ReturnFileSec map incomplete | Extend `section_codes` to all 7 values (incl. 139(5)→17, 119(2)(b)→16) in `filing_gateway_v2._filing_profile` |
| P0 | F5 80D mapper crashes on typed list | Rewrite `_map_80d` (`draft_to_itr1_input.py:309`) to iterate `draft.deductions.section80D` (list[Policy80D]) and build `Sec80DSelfFamHIDtls` |
| P1 | F1 employerCategory not captured | Add `employerCategory` to frontend `PersonalInfo` (`types.ts:357`) + a `<select>` UI bound to the 9-value enum |
| P1 | F6 80C mapper shape | Verify `_map_80c` iterates the typed list (same fix class as F5) |
| P1 | F3/F4 stateCode/nature enums | Frontend: constrain with union types or dropdowns |
| P1 | F8 TAN city-prefix | Frontend: validate TAN against city-prefix list at input |
| P2 | Exercise conditional schedules | Add fixtures + mapper coverage for 80G/80E/80EE/TDS-other/TCS/challans/HRA (build out the "missing 155/142") |

---

## 10. Evidence Files (generated by this audit)

- `audit_itr1_schema_fields.csv` — 601 leaf fields (path/type/required/constraints)
- `audit_itr4_schema_fields.csv` — 655 leaf fields
- `audit_itr1_enums_cappings.csv` — 260 enum/capping fields
- `audit_itr4_enums_cappings.csv` — 305 enum/capping fields
- `audit_itr1_generated.json` — official CBDT JSON from the audit draft (passes schema)
- `audit_itr4_generated.json` — official CBDT JSON from the audit draft (passes schema)
- `audit_itr1_present.csv` / `audit_itr1_missing.csv` — 92 present / 155 missing (conditional)
- `audit_itr4_present.csv` / `audit_itr4_missing.csv` — 94 present / 142 missing (conditional)

**Reproducible:** `python extract_schema_inventory.py && python extract_enums_cappings.py && python audit_itr_coverage.py`
