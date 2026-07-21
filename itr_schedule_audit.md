# Taxify CBDT Compliance Audit: Every Field, Every Schedule, Every ITR (AY 2026-27)

**Audit Scope:** Taxify's ITD JSON output (`app/engine/itd_json.py`), Pydantic input schemas (`app/schemas/itr*.py`), calculators (`app/engine/calculators/itr*.py`), schedule modules (`app/engine/schedules/`), and validation engine (`app/engine/validators.py`) vs. four CBDT JSON schemas and four CBDT validation rules PDFs.

**Legend:**
- **ERROR**: Field mismatch causing ITD portal rejection (`additionalProperties: false`)
- **WARNING**: Deviation from CBDT spec but won't block upload
- **MISSING**: Required field absent from implementation
- **MATCH**: Correctly implemented

---

## EXECUTIVE SUMMARY

| Metric | ITR-1 | ITR-2 | ITR-3 | ITR-4 |
|---|---|---|---|---|
| **ITD JSON Builder Status** | Implemented | NOT IMPLEMENTED (stub) | NOT IMPLEMENTED (stub) | Implemented |
| **Critical Schema Field Errors** | 15+ fields | N/A (no builder) | N/A (no builder) | 20+ fields |
| **Missing Required Fields** | 8+ fields | N/A | N/A | 15+ fields |
| **Validation Rules Coverage** | 13/339 rules (3.8%) | 4/? rules | 0/? rules | 5/365+ rules (<2%) |
| **Calculator Schedule Accuracy** | Mostly correct | Partial | Partial | Mostly correct |
| **Input Schema Completeness** | Good | Fair (core schedules) | Fair (core schedules) | Good |

**CRITICAL VERDICT:**
- **ITR-1 JSON WILL BE REJECTED** by the ITD portal. Root cause: 11 field name mismatches in Schedule80G plus 4 typos in Schedule80D, plus hardcoded-zero salary deduction fields and tax payment fields.
- **ITR-4 JSON WILL BE REJECTED** by the ITD portal. Root cause: Missing `PersonalInfo.Status` field, missing 13 Form10IEA fields in FilingStatus, wrong exempt income schedule, plus all ITR-1 Schedule80G/80D errors inherited.
- **ITR-2 and ITR-3 JSON builders do not exist.** The system cannot produce any ITD-compliant output for these forms.
- **Validation engine covers <4% of CBDT blocking rules.** Returns that "pass" Taxify validation will be rejected by the ITD portal.

---

# PART A: ITR-1 COMPLETE FIELD AUDIT

## A.1 Root Object: `ITR.ITR1`

| CBDT Required Schedule | In Taxify? | Status |
|---|---|---|
| `CreationInfo` | YES | MATCH |
| `Form_ITR1` | YES | MATCH |
| `PersonalInfo` | YES | MATCH |
| `FilingStatus` | YES | MATCH |
| `ITR1_IncomeDeductions` | YES | MATCH |
| `ITR1_TaxComputation` | YES | MATCH |
| `TaxPaid` | YES | MATCH |
| `Refund` | YES | MATCH |
| `Verification` | YES | MATCH |

## A.2 `CreationInfo` — 6/6 required fields, all MATCH

| CBDT Field | Taxify Value | CBDT Constraint | Status |
|---|---|---|---|
| `SWVersionNo` | `"1.0"` | maxLength 10, min 1 | MATCH |
| `SWCreatedBy` | `"SW00000001"` | pattern `^SW[0-9]{8}$` | MATCH |
| `JSONCreatedBy` | `"SW00000001"` | pattern `^SW[0-9]{8}$` | MATCH |
| `JSONCreationDate` | today's date | YYYY-MM-DD | MATCH |
| `IntermediaryCity` | `"Delhi"` | maxLength 25, min 1 | MATCH |
| `Digest` | 44-char SHA256 | pattern `-` or 44 chars | MATCH |

## A.3 `Form_ITR1` — 5/5 required fields, all MATCH

| CBDT Field | Taxify Value | Status |
|---|---|---|
| `FormName` | `"ITR-1"` | MATCH |
| `Description` | `"For AY 2026-27"` | MATCH |
| `AssessmentYear` | `"2026"` | MATCH |
| `SchemaVer` | `"Ver1.0"` | MATCH |
| `FormVer` | `"Ver1.0"` | MATCH |

## A.4 `PersonalInfo` — Field-by-Field

| CBDT Field | Required? | In Taxify? | Status |
|---|---|---|---|
| `AssesseeName.FirstName` | NOT required (max 25) | Present | MATCH |
| `AssesseeName.MiddleName` | NOT required (max 25) | Present | MATCH |
| `AssesseeName.SurNameOrOrgName` | YES (min 1, max 75) | Present | MATCH |
| `PAN` | YES (pattern `[A-Z]{5}[0-9]{4}[A-Z]`) | Present | MATCH |
| `Address.ResidenceNo` | YES (min 1, max 50) | Present | MATCH |
| `Address.ResidenceName` | NOT required (max 50) | Hardcoded `""` | WARNING |
| `Address.RoadOrStreet` | NOT required (max 50) | Hardcoded `""` | WARNING |
| `Address.LocalityOrArea` | YES (min 1, max 50) | Present | MATCH |
| `Address.CityOrTownOrDistrict` | YES (min 1, max 50) | Present | MATCH |
| `Address.StateCode` | YES | Present | MATCH |
| `Address.CountryCode` | YES | Present | MATCH |
| `Address.PinCode` | YES (100000-999999) | Present, default 110001 | MATCH |
| `Address.ZipCode` | NOT required (max 8) | Hardcoded `""` | MATCH |
| `Address.Phone` (STDcode+PhoneNo) | NOT required for ITR-1 | MISSING | WARNING (not blocking) |
| `Address.CountryCodeMobile` | NOT required for ITR-1 | Hardcoded 91 | MATCH |
| `Address.MobileNo` | NOT required for ITR-1 | Default 9999999999 | MATCH |
| `Address.CountryCodeMobileNoSec` | NOT required | Hardcoded 0 | MATCH |
| `Address.MobileNoSec` | NOT required | Hardcoded 0 | MATCH |
| `Address.EmailAddress` | YES (min 1, max 125, email) | Always populated | MATCH |
| `Address.EmailAddressSec` | NOT required | Hardcoded `""` | MATCH |
| `SecondaryAdd` | YES (enum `Y`/`N`) | Present | MATCH |
| `AlternateAddress` | Conditional (if SecondaryAdd=Y) | Always emitted | WARNING |
| `DOB` | YES (YYYY-MM-DD) | Present | MATCH |
| `EmployerCategory` | YES (9-value enum: CGOV/SGOV/PSU/PE/PESG/PEPS/PEO/OTH/NA) | Present as `OTH` default | WARNING: Taxify uses short form `OTH`, CBDT uses `OTH` — but Taxify input schema uses `OTH` not `NA`. Verify if `NA` is needed for non-salary. |
| `AadhaarCardNo` | NOT required | Always emitted even when `None` | WARNING |
| `Status` (I/H/F) | NOT in ITR-1 schema | N/A | N/A (ITR-4 only) |

## A.5 `FilingStatus`

| CBDT Field | Required? | Taxify | CBDT Constraint | Status |
|---|---|---|---|---|
| `ReturnFileSec` | YES | Present | enum 11-20 | MATCH |
| `OptOutNewTaxRegime` | YES | Present | enum Y/N | MATCH |
| `SeventhProvisio139` | NOT required | Hardcoded `"N"` | enum Y/N | MATCH |
| `AsseseeRepFlg` | NOT required | Hardcoded `"N"` | enum Y/N | MATCH |
| `ItrFilingDueDate` | NOT required | Hardcoded `"2026-07-31"` | date | MATCH |

## A.6 `ITR1_IncomeDeductions` — Every Field

| CBDT Field | Required? | Taxify | Status |
|---|---|---|---|
| `GrossSalary` | YES | Mapped from `result.salary_income` | MATCH |
| `Salary` | YES | `net_salary + ded_us16` (ded_us16 always 0) | MATCH |
| `PerquisitesValue` | YES | **Hardcoded 0** | **ERROR: Always 0, should use `salary_input.perquisites_value`** |
| `ProfitsInSalary` | YES | **Hardcoded 0** | **ERROR: Always 0, should use `salary_input.profits_in_lieu_of_salary`** |
| `AllwncExemptUs10.AllwncExemptUs10Dtls` | NOT required | Empty `[]` | MATCH |
| `AllwncExemptUs10.TotalAllwncExemptUs10` | NOT required | Hardcoded 0 | MATCH |
| `NetSalary` | YES | `max(0, result.salary_income)` | MATCH |
| `DeductionUs16` | YES | **Hardcoded 0** | **ERROR: Should = 16(ia+ii+iii) from salary schedule** |
| `DeductionUs16ia` | YES | **Hardcoded 0** | **ERROR: Should be 50000 (old) or 75000 (new)** |
| `EntertainmentAlw16ii` | YES | **Hardcoded 0** | **ERROR: Should use salary schedule** |
| `ProfessionalTaxUs16iii` | YES | **Hardcoded 0** | **ERROR: Should use salary schedule** |
| `IncomeFromSal` | YES | `result.salary_income` | MATCH |
| `PropertyDetails` | NOT required | Empty `[]` | MATCH |
| `TotalIncomeChargeableUnHP` | YES | `result.house_property_income` | MATCH |
| `IncomeOthSrc` | YES | `result.other_sources_income` | MATCH |
| `OthersInc.OthersIncDtlsOthSrc` | NOT required | Empty `[]` | MATCH |
| `DeductionUs57iia` | NOT required | Hardcoded 0 | MATCH |
| `GrossTotIncome` | YES | `gti - cg_112a_income` | MATCH |
| `GrossTotIncomeIncLTCG112A` | YES | `gti + cg_112a_income` | MATCH |
| `UsrDeductUndChapVIA` (all 20 sub-fields) | YES | Present with `TotalChapVIADeductions` | MATCH |
| `DeductUndChapVIA` (all 20 sub-fields) | YES | Same structure | MATCH |
| `TotalIncome` | YES | `result.taxable_income` | MATCH |
| `ExemptIncAgriOthUs10` | NOT required | Present with empty details | MATCH |

## A.7 `ITR1_TaxComputation` — Every Field

| CBDT Field | Required? | Taxify | Status |
|---|---|---|---|
| `TotalTaxPayable` | YES | `slab_tax` (= slab + special rate) | MATCH |
| `Rebate87A` | YES | Present | MATCH |
| `TaxPayableOnRebate` | YES | Present | MATCH |
| `EducationCess` | YES | Present | MATCH |
| `GrossTaxLiability` | YES | Present | MATCH |
| `Section89` | YES | Present | MATCH |
| `NetTaxLiability` | YES | Present | MATCH |
| `TotalIntrstPay` | NOT required | Present | MATCH |
| `IntrstPay.IntrstPayUs234A` | YES | Present | MATCH |
| `IntrstPay.IntrstPayUs234B` | YES | Present (always 0) | WARNING: 234B not computed |
| `IntrstPay.IntrstPayUs234C` | YES | Present (always 0) | WARNING: 234C not computed |
| `IntrstPay.LateFilingFee234F` | YES | Present | MATCH |
| `IntrstPay.FeeFurnish234I` | NOT required | Present, hardcoded 0 | MATCH |
| `TotTaxPlusIntrstPay` | NOT required | Present | MATCH |

## A.8 `TaxPaid` + `Refund`

| CBDT Field | Required? | Taxify | Status |
|---|---|---|---|
| `TaxesPaid.AdvanceTax` | YES | **Hardcoded 0** | **ERROR: Ignores `input_data.advance_tax_paid`** |
| `TaxesPaid.TDS` | YES | `result.total_tds` | MATCH |
| `TaxesPaid.TCS` | YES | `result.total_tcs` | MATCH |
| `TaxesPaid.SelfAssessmentTax` | YES | **Hardcoded 0** | **ERROR: Ignores `input_data.self_assessment_tax_paid`** |
| `TaxesPaid.TotalTaxesPaid` | YES | Sum of above | WARNING: Wrong because 2/4 inputs ignored |
| `BalTaxPayable` | NOT required | `result.balance_payable` | MATCH |
| `Refund.RefundDue` | YES | `result.refund_due` | MATCH |
| `Refund.BankAccountDtls.AddtnlBankDetails` | YES | Present with `IFSCCode`, `BankName`, `BankAccountNo`, `AccountType`, `UseForRefund` | MATCH |

## A.9 `Verification`

| CBDT Field | Required? | Taxify | Status |
|---|---|---|---|
| `Declaration.AssesseeVerName` | YES (min 1, max 127) | Present | MATCH |
| `Declaration.FatherName` | YES (min 1, max 125) | Present | MATCH |
| `Declaration.AssesseeVerPAN` | YES (pattern `[A-Z]{5}[0-9]{4}[A-Z]`) | Present | MATCH |
| `Capacity` | YES (enum S/R) | Hardcoded `"S"` | MATCH |
| `Place` | NOT required (max 50 per CBDT ITR-1 schema) | Present | MATCH |
| `Date` | NOT required in ITR-1 schema | MISSING | WARNING: CBDT schema has `Date` property but not in `required` |

## A.10 `TaxReturnPreparer`

| CBDT Field | Required? | Taxify | Status |
|---|---|---|---|
| `IdentificationNoOfTRP` | YES (pattern `^T[0-9]{9}\|[0-9]{6}$`) | Hardcoded `"T000000000"` | MATCH |
| `NameOfTRP` | YES (min 1, max 125) | Hardcoded `"Tax Preparer"` | MATCH |
| `ReImbFrmGov` | NOT required | Hardcoded 0 | MATCH |

## A.11 `Schedule80G` — CRITICAL: 11 FIELD NAME MISMATCHES

**The ITD portal will REJECT the JSON because all CBDT objects use `additionalProperties: false`.**

### Category: `Don100Percent` sub-object (all fields MATCH)

| CBDT Field | Taxify Field | Status |
|---|---|---|
| `TotDon100PercentCash` | `TotDon100PercentCash` | MATCH |
| `TotDon100PercentOtherMode` | `TotDon100PercentOtherMode` | MATCH |
| `TotDon100Percent` | `TotDon100Percent` | MATCH |
| `TotEligibleDon100Percent` | `TotEligibleDon100Percent` | MATCH |

### Category: `Don50PercentNoApprReqd` sub-object (4 ERRORS)

| CBDT Field | Taxify Field | Status |
|---|---|---|
| `TotDon50PercentNoApprReqdCash` | `TotDon50PercentNoAppReqCash` | **ERROR: `NoApprReqd` vs `NoAppReq`** |
| `TotDon50PercentNoApprReqdOtherMode` | `TotDon50PercentNoAppReqOtherMode` | **ERROR** |
| `TotDon50PercentNoApprReqd` | `TotDon50PercentNoAppReq` | **ERROR** |
| `TotEligibleDon50Percent` | `TotEligibleDon50PercentNoAppReq` | **ERROR: CBDT uses `TotEligibleDon50Percent` (without suffix) but Taxify appends `NoAppReq`** |

### Category: `Don100PercentApprReqd` sub-object (4 ERRORS)

| CBDT Field | Taxify Field | Status |
|---|---|---|
| `TotDon100PercentApprReqdCash` | `TotDon100PercentAppReqCash` | **ERROR: `ApprReqd` vs `AppReq`** |
| `TotDon100PercentApprReqdOtherMode` | `TotDon100PercentAppReqOtherMode` | **ERROR** |
| `TotDon100PercentApprReqd` | `TotDon100PercentAppReq` | **ERROR** |
| `TotEligibleDon100PercentApprReqd` | `TotEligibleDon100PercentAppReq` | **ERROR** |

### Category: `Don50PercentApprReqd` sub-object (4 ERRORS)

| CBDT Field | Taxify Field | Status |
|---|---|---|
| `TotDon50PercentApprReqdCash` | `TotDon50PercentAppReqCash` | **ERROR** |
| `TotDon50PercentApprReqdOtherMode` | `TotDon50PercentAppReqOtherMode` | **ERROR** |
| `TotDon50PercentApprReqd` | `TotDon50PercentAppReq` | **ERROR** |
| `TotEligibleDon50PercentApprReqd` | `TotEligibleDon50PercentAppReq` | **ERROR** |

### Top-level 80G fields (4 MATCH)

| CBDT Field | Taxify Field | Status |
|---|---|---|
| `TotalDonationsUs80GCash` | `TotalDonationsUs80GCash` | MATCH |
| `TotalDonationsUs80GOtherMode` | `TotalDonationsUs80GOtherMode` | MATCH |
| `TotalDonationsUs80G` | `TotalDonationsUs80G` | MATCH |
| `TotalEligibleDonationsUs80G` | `TotalEligibleDonationsUs80G` | MATCH |

**Root cause:** `_schedule_80g()` at ~line 390 of `itd_json.py`. All 11 mismatched fields must be renamed. The CBDT schema uses `ApprReqd` (double-r, ends in d) — Taxify writes `AppReq` (single r, no d). Similarly `NoApprReqd` is written as `NoAppReq`.

## A.12 `Schedule80D` — 4 TYPO ERRORS in Subtitle Fields

| CBDT Field (per schema) | Taxify Field | Status |
|---|---|---|
| `SeniorCitizenFlag` | Yes | MATCH |
| `SelfAndFamily` | Yes | MATCH |
| `HealthInsPremSlfFam` | `HlthInsPremSlfFam` | **ERROR: `Hlth` vs `Health` typo** |
| `Sec80DSelfFamHIDtls` | Yes | MATCH |
| `PrevHlthChckUpSlfFam` | Yes (0) | MATCH |
| `SelfAndFamilySeniorCitizen` | Yes | MATCH |
| `HealthInsPremSlfFamSrCtzn` | `HlthInsPremSlfFamSrCtzn` | **ERROR: typo** |
| `Sec80DSelfFamSrCtznHIDtls` | Yes | MATCH |
| `PrevHlthChckUpSlfFamSrCtzn` | Yes (0) | MATCH |
| `MedicalExpSlfFamSrCtzn` | Yes (0) | MATCH |
| `ParentsSeniorCitizenFlag` | Yes | MATCH |
| `Parents` | Yes | MATCH |
| `HealthInsPremParents` | `HlthInsPremParents` | **ERROR: typo** |
| `Sec80DParentsHIDtls` | Yes | MATCH |
| `PrevHlthChckUpParents` | Yes (0) | MATCH |
| `ParentsSeniorCitizen` | Yes | MATCH |
| `HealthInsPremParentsSrCtzn` | `HlthInsPremParentsSrCtzn` | **ERROR: typo** |
| `Sec80DParentsSrCtznHIDtls` | Yes | MATCH |
| `PrevHlthChckUpParentsSrCtzn` | Yes (0) | MATCH |
| `MedicalExpParentsSrCtzn` | Yes (0) | MATCH |
| `EligibleAmountOfDedn` | Yes | MATCH |

Note: The 4 `HealthInsPrem*` fields are NOT in the CBDT `required` array for `Sec80DSelfFamSrCtznHealth`, so these might not block upload — but they are mismatched properties in an `additionalProperties: false` object.

## A.13 `Schedule80DD` — Missing Fields

| CBDT Field | Required? | Taxify | Status |
|---|---|---|---|
| `NatureOfDisability` | YES | Hardcoded `"1"` | WARNING: not parameterized |
| `TypeOfDisability` | YES | Hardcoded `"2"` | WARNING |
| `DeductionAmount` | YES | Hardcoded 0 | **ERROR: not connected to deduction engine** |
| `DependentType` | YES | Hardcoded `"1"` | WARNING |
| `DependentPan` | NOT in required but schema property | **MISSING** | **ERROR: field absent** |
| `DependentAadhaar` | NOT in required but schema property | **MISSING** | **ERROR: field absent** |
| `Form10IAAckNum` | NOT required | Hardcoded `""` | MATCH |
| `UDIDNum` | NOT required | Hardcoded `""` | MATCH |

## A.14 `Schedule80U` — Missing Fields

| CBDT Field | Required? | Taxify | Status |
|---|---|---|---|
| `NatureOfDisability` | YES | Hardcoded `"1"` | WARNING |
| `TypeOfDisability` | YES | Hardcoded `"2"` | WARNING |
| `DeductionAmount` | YES | Hardcoded 0 | **ERROR: not connected** |
| `Form10IAAckNum` | NOT in required (max 15) | **MISSING** | **ERROR** |
| `UDIDNum` | NOT in required (max 18) | **MISSING** | **ERROR** |

## A.15 Other Optional Schedules — ITR-1

| Schedule | Status |
|---|---|
| `Schedule80GGA` (5 fields: `DonationDtlsSciRsrchRuralDev[]`, `TotalDonationAmtCash80GGA`, `TotalDonationAmtOtherMode80GGA`, `TotalDonationsUs80GGA`, `TotalEligibleDonationAmt80GGA`) | MATCH (all zero defaults) |
| `Schedule80GGC` (5 fields) | MATCH (all zero defaults) |
| `Schedule80E` (`Schedule80EDtls[]` + `TotalInterest80E`) | MATCH (empty details, 0 total) |
| `Schedule80EE` (`Schedule80EEDtls[]` + `TotalInterest80EE`) | MATCH |
| `Schedule80EEA` (`PropStmpDtyVal` + `Schedule80EEADtls[]` + `TotalInterest80EEA`) | MATCH |
| `Schedule80EEB` (`Schedule80EEBDtls[]` + `TotalInterest80EEB`) | MATCH |
| `Schedule80C` (`Schedule80CDtls[]` + `TotalAmt`) | MATCH (empty details, 0 total) |
| `ScheduleEA10_13A` (9 fields: `Placeofwork`, `ActlHRARecv`, `ActlRentPaid`, `DtlsSalUsSec171`, `BasicSalary`, `DearnessAllwnc`, `ActlRentPaid10Per`, `Sal40Or50Per`, `EligbleExmpAllwncUs13A`) | MATCH |
| `TDSonSalaries` (`TDSonSalary[]` + `TotalTDSonSalaries`) | MATCH |
| `TDSonOthThanSals` (`TDSonOthThanSal[]` + `TotalTDSonOthThanSals`) | MATCH |
| `ScheduleTDS3Dtls` (`TDS3Details[]` + `TotalTDS3Details`) | MATCH |
| `ScheduleTCS` (`TCS[]` + `TotalSchTCS`) | MATCH |
| `TaxPayments` (`TaxPayment[]` + `TotalTaxPayments`) | WARNING: always empty — should be populated from challan data |
| `LTCG112A` (`TotSaleCnsdrn`, `TotCstAcqisn`, `LongCap112A`) | MATCH (conditional) |

---

# PART B: ITR-2 COMPLETE SCHEDULE AUDIT

**STATUS: ITR-2 ITD JSON BUILDER NOT IMPLEMENTED.** The file `app/engine/itd_json.py` explicitly states `build_itr2_json()` is not implemented. Taxify cannot produce ITD-compliant JSON for ITR-2.

## B.1 ITR-2 CBDT Required Top-Level Schedules vs Taxify Readiness

| CBDT Required Schedule | Taxify Input Schema | Taxify Calculator | ITD JSON Builder |
|---|---|---|---|
| `CreationInfo` | N/A | N/A | Would reuse `_creation_info()` |
| `Form_ITR2` | N/A | N/A | Would need `_form_itr("ITR-2")` |
| `PartA_GEN1` (PersonalInfo + FilingStatus) | `PartAGEN1` in `itr2.py` | N/A | Missing |
| `ScheduleS` (Salary — 14 fields, multi-employer array) | `SalaryIncome` (imported) | `salary.py` | Missing |
| `ScheduleHP` (House Property — 20+ fields) | `HousePropertyIncome` (imported) | `house_property.py` | Missing |
| `ScheduleCGFor23` (Capital Gains — 100+ fields) | `CGTransaction` | `capital_gains.py` (12,935 lines) | Missing |
| `Schedule112A` | `CG112AScrip` | Present | Missing (conditional) |
| `Schedule115AD` | **MISSING** | **MISSING** | Missing |
| `ScheduleVDA` | `VDATransaction` | `compute_vda` | Missing (conditional) |
| `ScheduleOS` (Other Sources — 10+ fields) | `OtherSourcesIncome` (imported) | `other_sources.py` | Missing |
| `ScheduleCYLA` | CYLA logic | `cyla.py` | Missing |
| `ScheduleBFLA` | `BFLossItem` | `bfla.py` | Missing |
| `ScheduleCFL` | `CFLLossItem` | `cfl.py` | Missing (conditional) |
| `ScheduleVIA` | `Chapter6ADeductions` | `deductions/` | Missing |
| `ScheduleSI` | `ScheduleSIEntry` | `special_rates.py` | Missing (conditional) |
| `ScheduleSPI` | `SPIEntry` | **MISSING in calculator** | Missing (conditional) |
| `ScheduleEI` | `AgriculturalIncome` + `ExemptIncome` | `agricultural.py` | Missing (conditional) |
| `SchedulePTI` | **MISSING** | **MISSING** | Missing (conditional) |
| `ScheduleFSI` | `FSICountryEntry` | **MISSING** | Missing (conditional) |
| `ScheduleTR1` | `TR1Entry` | **MISSING** | Missing (conditional) |
| `ScheduleFA` | **MISSING** | **MISSING** | Missing (conditional) |
| `ScheduleAL` (if TI > 50L) | **MISSING** | **MISSING** | Missing (conditional) |
| `Schedule5A2014` | **MISSING** | **MISSING** | Missing (conditional) |
| `ScheduleAMT` | `AMTInput` | `amt.py` | Missing (conditional) |
| `ScheduleAMTC` | **MISSING** | **MISSING** | Missing (conditional) |
| `ScheduleESOP` | **MISSING** | **MISSING** | Missing (conditional) |
| `ScheduleIT` | **MISSING** | **MISSING** | Missing |
| `ScheduleTDS1` | `TDS1Entry` | `tds_salary.py` | Missing |
| `ScheduleTDS2` | `TDS2Entry` | `tds_other.py` | Missing |
| `ScheduleTDS3` | **MISSING** | **MISSING** | Missing |
| `ScheduleTCS` | `TCSEntry` | `tcs.py` | Missing |
| `ScheduleTPSA` | **MISSING** | **MISSING** | Missing |
| `Schedule80G/80GGA/80GGC/80D-80EEB` | In `Chapter6ADeductions` | `deductions/*.py` | Missing |
| `PartB-TI` (17 fields) | Stored in `ITR2Result` | `itr2.py` | Missing |
| `PartB_TTI` (12+ fields) | Stored in `ITR2Result` | `itr2.py` | Missing |
| `Verification` (Capacity enum: S/R/K/A) | N/A | N/A | Missing |
| `TaxReturnPreparer` | N/A | N/A | Missing |

## B.2 ITR-2 `PartA_GEN1` — Missing CBDT Fields

The CBDT ITR-2 `PartA_GEN1.PersonalInfo` contains significantly more fields than Taxify's `itr2.py:PartAGEN1`:

| CBDT Field | In `itr2.py`? | Required For |
|---|---|---|
| `CompDirectorPrvYrDtls` (NameOfCompany, CompanyType, PAN, SharesTypes, DIN) | **MISSING** | Directors |
| `HeldUnlistedEqShrPrYrDtls` (14 fields: opening/closing balances, costs, dates, face values) | **MISSING** | Unlisted share holders |
| `PartnerInFirmDtls` (NameOfFirm, PAN) | **MISSING** | Partners in firms |
| `NriPEinIndia` / `NriSEpinIndia` | **MISSING** | NRIs |
| `AggrPaymentTransac` | **MISSING** | Cash > 1cr threshold |
| `NumberOfUsers` | **MISSING** | Required count |
| `ForeignExchangeFlag` | **MISSING** | Schedule FA connector |
| `LEIDtls` (Legal Entity Identifier) | **MISSING** | LE holders |
| `PortugueseCC5A` flag | **MISSING** | Portuguese Civil Code |
| `ConditionsResStatus` (R+ROR, R+RNOR, NR, NOR) | **MISSING** | Different from simple RES/NRI/NOR |
| `DateOfFormationOrIncorporation` | **MISSING** | HUF |
| `ReturnFileDate` | **MISSING** | Filing date |
| All Form10IEA fields (13+ fields) | **MISSING** | Same as ITR-4 FilingStatus |
| Address fields (ResidenceNo, Locality, City, State, Country, PinCode) | **MISSING** | No address at all in `PartAGEN1` |

---

# PART C: ITR-3 COMPLETE SCHEDULE AUDIT

**STATUS: ITR-3 ITD JSON BUILDER NOT IMPLEMENTED.** Same as ITR-2 — both `build_itr2_json()` and `build_itr3_json()` are stubs.

## C.1 ITR-3 CBDT Required Schedules (12 mandatory top-level)

| CBDT Required Schedule | Taxify Readiness |
|---|---|
| `CreationInfo` | Would reuse `_creation_info()` |
| `Form_ITR3` | Would use `_form_itr("ITR-3")` |
| `PartA_GEN1` | No dedicated ITR-3 builder |
| `PartA_GEN2` (AuditInfo: 44AA/44AB/92E audit flags, auditor details, dates, ARN) | **MISSING from input schema and calculator** |
| `PARTA_BS` (Balance Sheet: 20 fields — capital, reserves, secured/unsecured loans, current liab, other liab, total liab; fixed assets gross/depn/net, investments, loans/adv, debtors, cash, inventories, other assets, total assets) | `BalanceSheet` schema exists in `itr3.py` |
| `PARTA_PL` (PLDebits: opening stock, purchases, direct/employee/finance/depn/admin/selling expenses, closing stock + PLCredits: sales, other biz income, interest, rent, commission, dividend, CG, other credits) | `PLDebits` + `PLCredits` + `PLDisallowances` in `itr3.py` |
| `ITR3ScheduleBP` (Business Income: 30+ fields with P&L adjustments, depreciation, disallowances, ICDS effects, partner salary/interest, CG u/s 50, recovery u/s 41) | **MISSING from input schema entirely** |
| `ScheduleCYLA` | `cyla.py` exists |
| `ScheduleBFLA` | `bfla.py` exists |
| `PartB-TI` (17 fields) | `ITR3Result` has core fields |
| `PartB_TTI` (Tax computation + TaxPaid + Refund + `AssetOutIndiaFlag`) | `ITR3Result` has core fields |
| `Verification` | Would reuse `_verification()` |

## C.2 ITR-3 Conditional Schedules (24 additional) — Coverage Audit

| CBDT Schedule | Taxify Input Schema | Taxify Calculator | Summary |
|---|---|---|---|
| `ManufacturingAccount` | **MISSING** | **MISSING** | Raw materials consumed, direct expenses, WIP, cost of production |
| `TradingAccount` | **MISSING** | **MISSING** | Opening/closing stock, purchases, sales, gross profit |
| `PARTA_OI` (Other Information) | **MISSING** | **MISSING** | Method of accounting, stock valuation, partnership details |
| `PARTA_QD` (Quantitative Details — 44AB audit) | **MISSING** | **MISSING** | Quantitative details of principal items |
| `ScheduleDPM` (Depreciation on Plant & Machinery) | Generic `DepreciationBlock15/30/40/45` | Partial `_compute_block()` | Blocks exist but not mapped to CBDT DPM structure (rate categories 15/30/40/45/50) |
| `ScheduleDOA` (Depreciation on Other Assets) | `DOABuildingResidential`, `DOABuildingOther`, `DOAFurniture`, `DOAIntangible` | Partial | Blocks exist but not mapped to CBDT DOA field names |
| `ScheduleDEP` (Depreciation Summary) | Not separate | Not separate output | Needs aggregated summary |
| `ScheduleDCG` (Deemed CG u/s 50) | **MISSING** | Partial in `_compute_block` `deemed_cg` | Deemed CG from negative WDV blocks |
| `ScheduleESR` (Scientific Research u/s 35) | **MISSING** | **MISSING** | Revenue + capital expenditure, weighted deductions |
| `ITR3ScheduleUD` (Unabsorbed Depreciation) | **MISSING** | **MISSING** | Opening, additions, set-off, carried forward |
| `ScheduleICDS` | `ICDSAdjustment` (net effect only) | **MISSING** | CBDT has full multi-section ICDS schedule |
| `Schedule10AA` (SEZ Deduction) | **MISSING** | Caller computes `business_10aa` | Unit-wise SEZ deduction |
| `Schedule80_IA` | **MISSING** | Caller computes `business_80ia` | Infrastructure/industrial undertaking |
| `Schedule80_IB` | **MISSING** | Caller computes `business_80ib` | Specific industries |
| `Schedule80_IC` | **MISSING** | **MISSING** | Special category states |
| `Schedule80RA` | **MISSING** | Caller computes `business_80ra` | Royalty/FTS from foreign sources |
| `ScheduleGST` | `GSTINEntry` | **MISSING** | GSTIN-wise turnover |
| `ScheduleIF` (Income from Firm/LLP) | `FirmIncome` | **MISSING** | Share of profit, CG, interest, salary from firm |
| `ScheduleTPSA` | **MISSING** | **MISSING** | Tax paid by employer on behalf of assessee |
| `ScheduleESOP` | **MISSING** | **MISSING** | ESOP deferral perquisite tracking across years |

---

# PART D: ITR-4 COMPLETE FIELD AUDIT

## D.1 ITR-4 Root Object — Required Schedules

| CBDT Required Schedule | In `build_itr4_json()`? | Status |
|---|---|---|
| `CreationInfo` | YES | MATCH |
| `Form_ITR4` | YES (`FormName="ITR-4"`) | MATCH |
| `PersonalInfo` | YES but **MISSING `Status` field** | **ERROR: Status (enum I/H/F) is REQUIRED in CBDT ITR-4 schema** |
| `FilingStatus` | YES but **MISSING 13 Form10IEA fields** | **ERROR** (see D.2) |
| `IncomeDeductions` | YES but **wrong exempt income schedule** | **ERROR** (see D.4) |
| `TaxComputation` | YES | MATCH |
| `TaxPaid` | YES but **AdvanceTax always 0** | **ERROR** (see D.1 sub) |
| `Refund` | YES | MATCH |
| `Verification` | YES | MATCH (but Verification.Date missing) |

## D.2 ITR-4 `FilingStatus` — CRITICAL: 13 Form10IEA Fields Missing

Taxify's `_filing_status()` outputs only 5 fields. The CBDT ITR-4 FilingStatus has these additional conditionally required fields:

| CBDT ITR-4 Field | Type/Enum | Taxify Status |
|---|---|---|
| `Form10IEAEarlierAYOldRegime` | Y/N/NA | **MISSING** |
| `Form10IEAAssYear` | 2024-25 or 2025-26 | **MISSING** |
| `Form10IEAEarlierAYAckOldRegime` | 15-digit integer | **MISSING** |
| `F10IEAEarlierAYNewRegime` | Y/N | **MISSING** |
| `AssYrF10IEANewTaxReg` | 2025-26 | **MISSING** |
| `Form10IEAEarlierAYAckNewRegime` | 15-digit integer | **MISSING** |
| `F10IEACurrAYNewRegime` | Y/N | **MISSING** |
| `F10IEADateCurrAYNewTax` | YYYY-MM-DD | **MISSING** |
| `F10IEAAckNoCurrAYNewTax` | 15-digit integer | **MISSING** |
| `F10IEACurrAYOldRegime` | Y/N | **MISSING** |
| `F10IEADateCurrAYOldTax` | YYYY-MM-DD | **MISSING** |
| `F10IEAAckNoCurrAYOldTax` | 15-digit integer | **MISSING** |
| **Also:** ITR-4 FilingStatus does NOT have `OptOutNewTaxRegime` as a simple Y/N — it uses the Form10IEA cascade instead. Taxify's `OptOutNewTaxRegime` field is an ITR-1 concept. | | **ERROR** |

## D.3 ITR-4 `PersonalInfo` — CRITICAL MISSING FIELDS

| CBDT ITR-4 Field | Type | Taxify | Status |
|---|---|---|---|
| `Status` | enum I/H/F (Individual/HUF/Firm) | **MISSING** | **ERROR: Required field. ITD portal will reject.** |
| `Address.Phone` (sub-object: `STDcode` + `PhoneNo`) | Object with 2 required properties | **MISSING** | **ERROR: Taxify Address has no Phone sub-object.** |

Taxify's `_personal_info()` was written for ITR-1 and doesn't include ITR-4-specific fields. ITR-4 can be filed by Individuals, HUFs, and Firms.

## D.4 ITR-4 `IncomeDeductions` — Wrong Schedules

| Issue | Detail | Status |
|---|---|---|
| `IncomeFromBusinessProf` | Present — correctly added from `presumptive_income` | MATCH |
| `ExemptIncAgriOthUs10` | **Taxify inherited this from ITR-1 builder. ITR-4 CBDT schema does NOT have this property.** | **ERROR** |
| `TaxExmpIntIncDtls` | **MISSING. ITR-4 CBDT schema has `TaxExmpIntIncDtls` as a property for exempt interest income.** Taxify omits this entirely. | **ERROR** |
| `UserDeductUndChapVIA` vs `UsrDeductUndChapVIA` | CBDT ITR-4 schema uses `UserDeductUndChapVIA` (full "User"). Taxify uses `UsrDeductUndChapVIA` (abbreviated "Usr") from ITR-1 naming. Need to verify which ITR-4 actually uses. | **ERROR** (likely) |
| All `ITR1_` field prefixes | ITR-4 IncomeDeductions does NOT use `ITR1_` prefixes — Taxify's builder uses ITR-1 naming internally but outputs to the right keys. | MATCH |

## D.5 ITR-4 `ScheduleBP` — Field-by-Field

| CBDT Field | Taxify Source | Status |
|---|---|---|
| `NatOfBus44AD[]` | Populated with `[CodeAD, NameOfBusiness, Description]` when scheme=44AD | MATCH |
| `PersumptiveInc44AD.GrsTotalTrnOver` | `bp_gross_turnover` | MATCH |
| `.GrsTrnOverBank` | `bp_digital_turnover` | MATCH |
| `.GrsTotalTrnOverInCash` | `bp_cash_turnover` | MATCH |
| `.GrsTrnOverAnyOthMode` | `bp_other_turnover` | MATCH |
| `.PersumptiveInc44AD6Per` | Set when cash <= 5% of turnover | MATCH |
| `.PersumptiveInc44AD8Per` | Set when cash > 5% of turnover | MATCH |
| `.TotPersumptiveInc44AD` | `presumptive_income` | MATCH |
| `NatOfBus44ADA[]` | Populated with `[CodeADA, NameOfBusiness]` when scheme=44ADA | MATCH |
| `PersumptiveInc44ADA.GrsReceipt` | `bp_gross_turnover` | MATCH |
| `.GrsTrnOverBank44ADA` | `bp_digital_turnover` | MATCH |
| `.GrsTotalTrnOverInCash44ADA` | `bp_cash_turnover` | MATCH |
| `.GrsTrnOverAnyOthMode44ADA` | `bp_other_turnover` | MATCH |
| `.TotPersumptiveInc44ADA` | `presumptive_income` | MATCH |
| `NatOfBus44AE[]` | Empty `[]` **— should be populated per vehicle** | WARNING |
| `GoodsDtlsUs44AE[]` | Empty `[]` **— should have vehicle reg numbers, tonnage, months** | WARNING |
| `PersumptiveInc44AE.TotPersumInc44AE` | `presumptive_income` when 44AE | MATCH |
| `.SalInterestByFirm` | Hardcoded 0 | WARNING: should accept firm-specific input |
| `.TotalPersumptiveInc` | `presumptive_income` | MATCH |
| `.IncChargeableUnderBus` | `presumptive_income` | MATCH |
| `TurnoverGrsRcptForGSTIN[]` | Empty `[]` **— should accept GSTIN-wise data** | WARNING |
| `TotalTurnoverGrsRcptGSTIN` | Hardcoded 0 | WARNING |
| `FinanclPartclrOfBusiness` (12 fields: `PartnerMemberOwnCapital`, `SecuredLoans`, `UnSecuredLoans`, `Advances`, `SundryCreditors`, `OthrCurrLiab`, `TotCapLiabilities`, `FixedAssets`, `Investments`, `Inventories`, `SundryDebtors`, `BalWithBanks`, `CashInHand`, `LoansAndAdvances`, `OtherAssets`, `TotalAssets`) | All present as 0 | WARNING: always 0, should accept input |

## D.6 ITR-4 `ScheduleIT`

| CBDT Field | Taxify | Status |
|---|---|---|
| `TotalTurnoverGrsRcptUs44AD` | `bp_gross_turnover` | MATCH |
| `TotPresumIncUs44AD` | `result.presumptive_income` | MATCH |

## D.7 ITR-4 `TaxExmpIntIncDtls` — COMPLETELY MISSING

CBDT ITR-4 schema includes `TaxExmpIntIncDtls` (Tax Exempt Interest Income Details) as a property of the ITR4 object. Taxify's ITR-4 builder does not include this schedule at all.

## D.8 ITR-4 `Schedule80G` — SAME 11 ERRORS AS ITR-1

ITR-4 reuses the identical `_schedule_80g()` helper, inheriting all field name errors. CBDT ITR-4 schema uses the same Schedule80G field names as ITR-1.

## D.9 ITR-4 `TDSonOthThanSals` — Needs Richer Structure

CBDT ITR-4 TDS detail entry (`TDSonOthThanSalDtls`) uses: `TANOfDeductor`, `DeductedYr`, `BroughtFwdTDSAmt`, `TDSDeducted`, `TDSSection` (60+ code enum), `TDSClaimed`, `GrossAmount`, `HeadOfIncome` (BP/HP/OS/EI/NA), `TDSCreditCarriedFwd`. Taxify's TDS entries use `EmployerOrDeductorOrCollectDetl.TAN` pattern plus limited fields — need to align with ITR-4's richer structure.

---

# PART E: CALCULATOR ENGINE AUDIT

## E.1 Salary Schedule (`salary.py`) — Computes Correctly, But JSON Ignores Values

```python
# salary.py CORRECTLY computes:
gross = salary + perquisites + profits_in_lieu
old_regime: gross - HRA - LTA - std_ded(50000) - prof_tax(capped 5000) - ent_allowance(5000 if govt)
new_regime: gross - std_ded(75000)
```

**ISSUE:** The ITD JSON builders (`build_itr1_json()`, `build_itr4_json()`) hardcode these fields to 0:
- `DeductionUs16` = 0 (should = `salary_result.deductions_u16`)
- `DeductionUs16ia` = 0 (should = `salary_result.standard_deduction`)
- `EntertainmentAlw16ii` = 0 (should = `salary_result.entertainment_allowance`)
- `ProfessionalTaxUs16iii` = 0 (should = `salary_result.professional_tax`)

The calculator computes correctly but the JSON builder discards the values.

## E.2 House Property (`house_property.py`) — Correct

- Self-occupied: `-min(interest, 200000)` old regime / `0` new regime
- Let-out: `GAV - taxes - 30% std_ded - interest + arrears`
- Negative HP under new regime correctly disallowed (loss disallowed)
- Arrears rent with 30% deduction per Section 25A

## E.3 80D Deduction (`section_80d.py`) — INCORRECT PARENT AGE LOGIC

```python
# Current Taxify code:
is_senior = age_bracket in (SIXTY_TO_80, ABOVE_80)
cap_self = SECTION_80D_SELF_FAMILY_SENIOR_LIMIT if is_senior else SECTION_80D_SELF_FAMILY_LIMIT
ded_parents = min(ded.amount_80d_parents, SECTION_80D_PARENTS_SENIOR_LIMIT)  # ALWAYS 50000
```

**ERROR:** The parent cap is always `SECTION_80D_PARENTS_SENIOR_LIMIT` (50000), regardless of whether the assessee's parents are actually senior citizens. CBDT rules require:
- Self/family cap: depends on whether SELF or family member is senior citizen
- Parents cap: depends on whether PARENTS are senior citizens

The `Chapter6ADeductions` schema has no `parent_senior_citizen` flag. This must be added.

## E.4 80G Donations (`section_80g.py`) — Logic Correct, Missing Validation Rules

The compute function correctly:
- Caps cash per entry at Rs 2,000 (Section 80G(5D))
- Computes qualifying amount = total_donation * factor (100% or 50%)
- Applies 10% adjusted GTI limit for "with limit" donations

**MISSING enforcement** (required by CBDT validation rules):
- Cash donations > Rs 2,000 across entries with same PAN: entire amount disallowed
- Single entry > Rs 2,000 in cash: eligible amount = 0
- Donee PAN cannot appear in multiple Schedule80G blocks (except AAAAR1077P)
- ARN numbers must be unique within a block
- IFSC code mandatory for non-cash donations

## E.5 80C/80CCC/80CCD(1) (`section_80c.py`) — Basic Cap Correct, Missing Sub-Limits

- Combined pool of Rs 1,50,000 (Section 80CCE) — CORRECT

**MISSING enforcement:**
- 80CCD(1): Max 10% of salary (non-govt, non-pensioner employees) — CBDT Rule #3
- 80CCD(1): Max 20% of GTI (pensioners) — CBDT Rule #2
- 80CCD(2): Max 10% of salary (non-CG/SG employer) — CBDT Rule #4
- 80CCD(2): Max 14% of salary (CG/SG employer) — CBDT Rule #120
- 80CCH: Max 46.2% of salary u/s 17(1) — CBDT Rule #186

## E.6 Interest — Missing 234B and 234C

- `compute_234a()` — implemented (default of tax for late filing)
- `compute_234f()` — implemented (late fee Rs 1,000/5,000)
- **234B (advance tax shortfall)** — NOT IMPLEMENTED (always 0)
- **234C (advance tax deferment)** — NOT IMPLEMENTED (always 0)
- **234I (revised return fee)** — NOT IMPLEMENTED (hardcoded 0); CBDT requires Rs 1,000 if TI <= 5L, Rs 5,000 if TI > 5L for revised returns filed after 31/12

## E.7 87A Rebate — Basic Logic Present

- Old regime: max Rs 12,500 for TI <= 5,00,000
- New regime: max Rs 25,000 for TI <= 7,00,000 with marginal relief up to Rs 7,27,770
- Correctly applied after special rate tax

---

# PART F: VALIDATION RULES COVERAGE

| ITR | Category A (Blocking) | Category B (139(9) Defect) | Category D (Docs) | Taxify Rules | Coverage |
|---|---|---|---|---|---|
| **ITR-1** | 339 rules | 9 rules | 1 rule | 13 rules | **3.8%** |
| **ITR-2** | 200+ (est.) | 50+ (est.) | Several | 4 rules | **<2%** |
| **ITR-3** | 300+ (est.) | 50+ (est.) | Several | 0 rules | **0%** |
| **ITR-4** | 365+ rules | Many | Several | 5 rules | **<2%** |

A return that passes Taxify validation will almost certainly be rejected by the ITD portal's own Category A validations.

---

# PART G: SUMMARY OF ALL CRITICAL FIXES REQUIRED

## Must-Fix for ITD Upload (ITR-1 + ITR-4)

| # | Issue | Affects | Severity |
|---|---|---|---|
| 1 | `Schedule80G`: Fix 11 field names (`AppReq` -> `ApprReqd`, `NoAppReq` -> `NoApprReqd`) | ITR-1, ITR-4 | **BLOCKING** |
| 2 | `Schedule80D`: Fix 4 subtitle typos (`HlthInsPrem` -> `HealthInsPrem`) | ITR-1, ITR-4 | **BLOCKING** |
| 3 | `IncomeDeductions`: Wire `DeductionUs16`, `DeductionUs16ia`, `EntertainmentAlw16ii`, `ProfessionalTaxUs16iii` from salary result | ITR-1, ITR-4 | **BLOCKING** |
| 4 | `IncomeDeductions`: Wire `PerquisitesValue`, `ProfitsInSalary` from salary input | ITR-1, ITR-4 | **BLOCKING** |
| 5 | `TaxPaid`: Wire `AdvanceTax` and `SelfAssessmentTax` from input data | ITR-1, ITR-4 | **BLOCKING** |
| 6 | `Schedule80DD`: Add `DependentPan`, `DependentAadhaar` | ITR-1, ITR-4 | **BLOCKING** |
| 7 | `Schedule80U`: Add `Form10IAAckNum`, `UDIDNum` | ITR-1, ITR-4 | **BLOCKING** |

## Must-Fix for ITD Upload (ITR-4 Only)

| # | Issue | Severity |
|---|---|---|
| 8 | `PersonalInfo`: Add `Status` field (enum I/H/F) | **BLOCKING** |
| 9 | `PersonalInfo.Address`: Add `Phone` sub-object (`STDcode` + `PhoneNo`) | **BLOCKING** |
| 10 | `FilingStatus`: Add all 13 Form10IEA cascade fields | **BLOCKING** |
| 11 | `IncomeDeductions`: Replace `ExemptIncAgriOthUs10` with `TaxExmpIntIncDtls` | **BLOCKING** |
| 12 | `IncomeDeductions`: Fix `UsrDeductUndChapVIA` to `UserDeductUndChapVIA` if ITR-4 schema differs | **BLOCKING** |
| 13 | Add `TaxExmpIntIncDtls` schedule to ITR-4 output | **BLOCKING** |
| 14 | `ScheduleBP`: Populate `NatOfBus44AE[]`, `GoodsDtlsUs44AE[]` for 44AE filers | WARNING |
| 15 | `ScheduleBP.FinanclPartclrOfBusiness`: Wire actual values from input | WARNING |

## Must-Fix for System Completeness

| # | Issue |
|---|---|
| 16 | Implement `build_itr2_json()` with all 50+ schedules per CBDT ITR-2 schema |
| 17 | Implement `build_itr3_json()` with all 36 schedules per CBDT ITR-3 schema |
| 18 | Expand validation engine from ~20 rules to 500+ covering ALL Category A blocking rules |
| 19 | Fix `section_80d.py`: Add separate `parent_senior` flag parameter |
| 20 | Fix `section_80c.py`: Add 80CCD(1) salary%/GTI% caps, 80CCD(2) employer limits, 80CCH 46.2% cap |
| 21 | Implement 234B (advance tax interest) and 234C (deferment interest) |
| 22 | Add `PartA_GEN2` (AuditInfo) for ITR-3 |
| 23 | Add `ITR3ScheduleBP`, `ScheduleDPM`, `ScheduleDOA`, `ScheduleDEP` builders |
| 24 | Add `ScheduleIF`, `ScheduleICDS`, `ScheduleGST` builders |
| 25 | Add `SchedulePTI`, `ScheduleTPSA`, `ScheduleFA`, `ScheduleAL`, `Schedule5A2014` builders |
| 26 | Add `ScheduleAMTC`, `ScheduleESOP`, `ScheduleDCG`, `ScheduleESR`, `ScheduleUD` builders |
