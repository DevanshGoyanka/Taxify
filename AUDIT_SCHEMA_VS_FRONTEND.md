# ITR-1 & ITR-4 Schema vs Frontend Audit
## AY 2026-27 | Generated 2026-07-29

**Reference:** Official ITD JSON Schema (`ITR-1_2026_Main_V1.1`, `ITR-4_2026_Main_V1.1`)  
**Frontend files:** `test_itr1_e2e.py`, `test_itr4_e2e.py`  
**Pydantic schemas:** `app/schemas/itr1.py`, `app/schemas/itr4.py`, `app/schemas/itr2.py`, `app/schemas/itr3.py`

**Legend:**
- ✅ Present & correct
- ⚠️ Present but incomplete (missing validation, sub-fields, or regime handling)
- ❌ Missing entirely
- 🔶 Optional field — nice-to-have
- 🔴 Mandatory field — must fix

---

## ITR-1 — FIELD-BY-FIELD AUDIT

### 1. CreationInfo (Mandatory)

| Official Schema Field | Mandatory? | Frontend Status | Notes |
|---|---|---|---|
| `SWVersionNo` | 🔴 Yes | ✅ `build_itr1_json` generates | Fixed "1.0" |
| `SWCreatedBy` | 🔴 Yes | ✅ `build_itr1_json` generates | Pattern `SW[0-9]{8}` |
| `JSONCreatedBy` | 🔴 Yes | ✅ `build_itr1_json` generates | Pattern `SW[0-9]{8}` |
| `JSONCreationDate` | 🔴 Yes | ✅ `build_itr1_json` generates | YYYY-MM-DD |
| `IntermediaryCity` | 🔴 Yes | ✅ `build_itr1_json` generates | Default "Delhi" |
| `Digest` | 🔴 Yes | ✅ `build_itr1_json` generates | 44-char digest |

### 2. Form_ITR1 (Mandatory)

| Official Schema Field | Mandatory? | Frontend Status | Notes |
|---|---|---|---|
| `FormName` | 🔴 Yes | ✅ `build_itr1_json` generates | Literal "ITR-1" |
| `Description` | 🔴 Yes | ✅ `build_itr1_json` generates | Hardcoded description |
| `AssessmentYear` | 🔴 Yes | ✅ `build_itr1_json` generates | Literal "2026" |
| `SchemaVer` | 🔴 Yes | ✅ `build_itr1_json` generates | Literal "Ver1.0" |
| `FormVer` | 🔴 Yes | ✅ `build_itr1_json` generates | Literal "Ver1.0" |

### 3. PersonalInfo (Mandatory)

| Official Schema Field | Mandatory? | Frontend Status | Notes |
|---|---|---|---|
| `AssesseeName.SurNameOrOrgName` | 🔴 Yes | ✅ `last_name` collected | |
| `AssesseeName.FirstName` | 🔶 Optional | ✅ `first_name` collected | |
| `AssesseeName.MiddleName` | 🔶 Optional | ✅ `middle_name` collected | |
| `PAN` | 🔴 Yes | ✅ Collected + validated | Pattern `[A-Z]{5}[0-9]{4}[A-Z]` |
| `Address.ResidenceNo` | 🔴 Yes | ✅ `residence_no` collected | |
| `Address.ResidenceName` | 🔶 Optional | ❌ Missing | Not asked |
| `Address.RoadOrStreet` | 🔶 Optional | ❌ Missing | Not asked |
| `Address.LocalityOrArea` | 🔴 Yes | ✅ `locality` collected | |
| `Address.CityOrTownOrDistrict` | 🔴 Yes | ✅ `city` collected | |
| `Address.StateCode` | 🔴 Yes | ✅ `state_code` collected | No enum validation |
| `Address.CountryCode` | 🔴 Yes | ✅ `country_code` collected | No enum validation |
| `Address.PinCode` | 🔶 Optional | ✅ `pin_code` collected | |
| `Address.ZipCode` | 🔶 Optional | ❌ Missing | |
| `Address.CountryCodeMobile` | 🔴 Yes | ⚠️ Hardcoded "91" in JSON builder | Not collected from user |
| `Address.MobileNo` | 🔴 Yes | ✅ `mobile_no` collected | |
| `Address.CountryCodeMobileNoSec` | 🔶 Optional | ❌ Missing | Secondary mobile |
| `Address.MobileNoSec` | 🔶 Optional | ❌ Missing | Secondary mobile |
| `Address.EmailAddress` | 🔴 Yes | ✅ `email` collected | No email regex validation |
| `Address.EmailAddressSec` | 🔶 Optional | ❌ Missing | Secondary email |
| `SecondaryAdd` | 🔴 Yes | ✅ Hardcoded "N" in JSON builder | Not asked from user |
| `AlternateAddress.*` | 🔶 Optional | ❌ Missing | Entire alternate address block |
| `DOB` | 🔴 Yes | ✅ Collected + validated | YYYY-MM-DD, max 2026-03-31 |
| `EmployerCategory` | 🔴 Yes | ✅ Collected | Enum: CGOV/SGOV/PSU/PE/PESG/PEPS/PEO/OTH/NA — **frontend has 6 options but schema has 9** |
| `AadhaarCardNo` | 🔶 Optional | ✅ Collected | Pattern `[0-9]{12}` |

**Gaps:**
- ❌ `Address.ResidenceName`, `Address.RoadOrStreet`, `Address.ZipCode` — missing
- ❌ `Address.CountryCodeMobile` — hardcoded, not collected
- ❌ `Address.CountryCodeMobileNoSec`, `Address.MobileNoSec`, `Address.EmailAddressSec` — secondary contact missing
- ❌ `AlternateAddress` — entire section missing
- ⚠️ `EmployerCategory` — frontend enum is incomplete (6 vs 9 values in official schema)

### 4. FilingStatus (Mandatory)

| Official Schema Field | Mandatory? | Frontend Status | Notes |
|---|---|---|---|
| `ReturnFileSec` | 🔴 Yes | ✅ Collected | Enum validated |
| `OptOutNewTaxRegime` | 🔴 Yes | ✅ Derived from `tax_regime` | Set to "Y" for new, "N" for old |
| `SeventhProvisio139` | 🔶 Optional | ❌ Missing | High-value spending flag |
| `IncrExpAggAmt2LkTrvFrgnCntryFlg` | 🔶 Optional | ❌ Missing | Foreign travel > ₹2L |
| `AmtSeventhProvisio139ii` | 🔶 Optional | ❌ Missing | Foreign travel amount |
| `IncrExpAggAmt1LkElctrctyPrYrFlg` | 🔶 Optional | ❌ Missing | Electricity > ₹1L |
| `AmtSeventhProvisio139iii` | 🔶 Optional | ❌ Missing | Electricity amount |
| `clauseiv7provisio139i` | 🔶 Optional | ❌ Missing | TDS/TCS ≥ ₹25K or bank deposits ≥ ₹50L |
| `clauseiv7provisio139iDtls` | 🔶 Optional | ❌ Missing | Array — mandatory filings trigger |
| `ReceiptNo` | 🔶 Optional (required for revised) | ❌ Missing | 15-digit ack number |
| `NoticeNo` | 🔶 Optional | ❌ Missing | |
| `OrigRetFiledDate` | 🔶 Optional | ❌ Missing | |
| `NoticeDateUnderSec` | 🔶 Optional | ❌ Missing | |
| `AsseseeRepFlg` | 🔴 Yes | ⚠️ Hardcoded "N" in JSON builder | Not asked from user |
| `AssesseeRep.*` | 🔶 Conditional | ❌ Missing | Representative details |
| `ItrFilingDueDate` | 🔴 Yes | ✅ Collected | Pattern `2026-07-31` |

**Gaps:**
- ❌ `SeventhProvisio139` — entire section missing (mandatory filing triggers)
- ❌ `clauseiv7provisio139iDtls` — critical for mandatory filers
- ❌ `ReceiptNo`, `OrigRetFiledDate` — needed for revised returns
- ❌ `AssesseeRep.*` — representative details block missing

### 5. ITR1_IncomeDeductions — SALARY (Mandatory section)

| Official Schema Field | Mandatory? | Frontend Status | Notes |
|---|---|---|---|
| `GrossSalary` | 🔴 Yes | ✅ `gross_salary` collected | |
| `Salary` | 🔶 Optional | ⚠️ Computed but not separately input | |
| `PerquisitesValue` | 🔶 Optional | ✅ `perquisites_value` collected | |
| `ProfitsInSalary` | 🔶 Optional | ✅ `profits_in_lieu_of_salary` collected | |
| `AllwncExemptUs10.TotalAllwncExemptUs10` | 🔴 Yes | ❌ Missing | Exempt allowances total |
| `AllwncExemptUs10.AllwncExemptUs10Dtls[]` | 🔶 Optional | ❌ Missing | Array of allowance breakdowns |
| `NetSalary` | 🔴 Yes | ✅ Computed from inputs | |
| `DeductionUs16` | 🔴 Yes | ✅ Computed | |
| `DeductionUs16ia` | 🔶 Optional | ✅ `standard_deduction_claimed` collected | Max 75000 |
| `EntertainmentAlw16ii` | 🔶 Optional | ✅ Collected | Max 5000 |
| `ProfessionalTaxUs16iii` | 🔶 Optional | ✅ Collected | Max 5000 |
| `IncomeFromSal` | 🔴 Yes | ✅ Computed | |

**Gaps:**
- ❌ `AllwncExemptUs10` — entire section missing (HRA exemption should go here)

### 6. ITR1_IncomeDeductions — HOUSE PROPERTY

| Official Schema Field | Mandatory? | Frontend Status | Notes |
|---|---|---|---|
| `PropertyDetails[]` | 🔶 Optional | ✅ Collected | Array, maxItems 2 |
| `PropertyDetails[].HPSNo` | 🔴 Yes (per item) | ❌ Missing | Property serial number |
| `PropertyDetails[].AddressDetailWithZipCode.*` | 🔴 Yes (per item) | ❌ Missing | Property address block |
| `PropertyDetails[].PropertyOwner` | 🔴 Yes (per item) | ❌ Missing | SE/MI/SP/OT |
| `PropertyDetails[].PropertyOwnerOther` | 🔶 Optional | ❌ Missing | |
| `PropertyDetails[].PropCoOwnedFlg` | 🔴 Yes | ❌ Missing | YES/NO |
| `PropertyDetails[].AsseseeShareProperty` | 🔶 Optional | ❌ Missing | 0-100% |
| `PropertyDetails[].CoOwners[]` | 🔶 Optional | ❌ Missing | Co-owner array |
| `PropertyDetails[].ifLetOut` | 🔴 Yes | ✅ `hp_type` mapped | L/D/S |
| `PropertyDetails[].TenantDetails[]` | 🔶 Optional | ❌ Missing | Tenant array |
| `PropertyDetails[].Rentdetails.AnnualLetableValue` | 🔴 Yes | ⚠️ `municipal_value` collected | Partial |
| `PropertyDetails[].Rentdetails.RentNotRealized` | 🔶 Optional | ❌ Missing | |
| `PropertyDetails[].Rentdetails.LocalTaxes` | 🔶 Optional | ✅ `municipal_tax` collected | |
| `PropertyDetails[].Rentdetails.TotalUnrealizedAndTax` | 🔴 Yes | ⚠️ Computed, not input | |
| `PropertyDetails[].Rentdetails.BalanceALV` | 🔴 Yes | ❌ Missing | |
| `PropertyDetails[].Rentdetails.AnnualOfPropOwned` | 🔴 Yes | ❌ Missing | |
| `PropertyDetails[].Rentdetails.ThirtyPercentOfBalance` | 🔴 Yes | ⚠️ Computed, not input | |
| `PropertyDetails[].Rentdetails.IntOnBorwCap` | 🔴 Yes | ✅ `home_loan_interest` collected | |
| `PropertyDetails[].Rentdetails.Section24B.*` | 🔶 Optional | ❌ Missing | Loan detail array |
| `PropertyDetails[].Rentdetails.TotalDeduct` | 🔴 Yes | ⚠️ Computed | |
| `PropertyDetails[].Rentdetails.ArrearsUnrealizedRentRcvd` | 🔶 Optional | ❌ Missing | |
| `PropertyDetails[].Rentdetails.IncomeOfHP` | 🔴 Yes | ⚠️ Computed | Can be negative |
| `TotalIncomeChargeableUnHP` | 🔶 Optional | ✅ Computed | |

**Gaps:**
- ❌ `PropertyDetails[].AddressDetailWithZipCode` — entire address per property missing
- ❌ `PropertyDetails[].PropertyOwner`, `PropCoOwnedFlg`, `CoOwners[]` — ownership details missing
- ❌ `PropertyDetails[].TenantDetails[]` — tenant array missing
- ❌ `PropertyDetails[].Rentdetails` — many computed/derived fields not surfaced
- ❌ `PropertyDetails[].Rentdetails.Section24B` — per-loan detail array missing

### 7. ITR1_IncomeDeductions — OTHER SOURCES

| Official Schema Field | Mandatory? | Frontend Status | Notes |
|---|---|---|---|
| `IncomeOthSrc` | 🔴 Yes | ✅ Computed | |
| `OthersInc.OthersIncDtlsOthSrc[]` | 🔶 Optional | ❌ Missing | Nature-of-income breakdown |
| `DeductionUs57iia` | 🔶 Optional | ❌ Missing | Family pension deduction (max ₹25K) |
| `GrossTotIncome` | 🔴 Yes | ✅ Computed | |
| `GrossTotIncomeIncLTCG112A` | 🔴 Yes | ✅ Computed | |
| `TotalIncome` | 🔴 Yes | ✅ Computed | Max ₹51,25,000 for ITR-1 |

**Gaps:**
- ❌ `OthersInc.OthersIncDtlsOthSrc` — frontend collects flat amounts but doesn't map to official nature codes (SAV/IFD/TAX/FAP/DIV)
- ❌ `DeductionUs57iia` — family pension ₹15K/₹25K deduction not asked

### 8. ITR1_IncomeDeductions — USR DEDUCTIONS (User Claimed, Mandatory)

| Official Schema Field | Mandatory? | Frontend Status | Notes |
|---|---|---|---|
| `Section80C` | 🔴 Yes | ✅ Collected `amount_80c` | |
| `Section80CCC` | 🔴 Yes | ✅ Collected `amount_80ccc` | |
| `Section80CCDEmployeeOrSE` | 🔴 Yes | ✅ Collected `amount_80ccd1` | |
| `Section80CCD1B` | 🔴 Yes | ✅ Collected `amount_80ccd1b` | |
| `Section80CCDEmployer` | 🔴 Yes | ✅ Collected `amount_80ccd2` | |
| `Section80D` | 🔴 Yes | ✅ Collected via 80D inputs | |
| `Section80DD` | 🔴 Yes | ✅ Collected `amount_80dd` | |
| `Section80DDBUsrType` | 🔴 Yes | ❌ Missing | "1" or "2" — taxpayer/senior type |
| `NameOfSpecDisease80DDB` | 🔴 Yes | ❌ Missing | Enum a-n (14 disease codes) |
| `Section80DDB` | 🔴 Yes | ✅ Collected `amount_80ddb` | |
| `Section80E` | 🔴 Yes | ✅ Collected `amount_80e` | |
| `Section80EE` | 🔴 Yes | ✅ Collected `amount_80ee` | |
| `Section80EEA` | 🔴 Yes | ✅ Collected `amount_80eea` | |
| `Section80EEB` | 🔴 Yes | ✅ Collected `amount_80eeb` | |
| `Section80G` | 🔴 Yes | ✅ Collected `amount_80g` | |
| `Section80GG` | 🔴 Yes | ✅ Collected `amount_80gg` | |
| `Form10BAAckNum` | 🔴 Yes | ❌ Missing | Form 10BA for 80GG |
| `Section80GGA` | 🔴 Yes | ⚠️ Not collected (ITR-1 only) | Hardcoded 0 |
| `Section80GGC` | 🔴 Yes | ⚠️ Not collected | Hardcoded 0 |
| `Section80U` | 🔴 Yes | ✅ Collected `amount_80u` | |
| `Section80TTA` | 🔴 Yes | ✅ Collected `amount_80tta` | |
| `Section80TTB` | 🔴 Yes | ✅ Collected `amount_80ttb` | |
| `AnyOthSec80CCH` | 🔴 Yes | ✅ Collected `amount_80cch` | |
| `TotalChapVIADeductions` | 🔴 Yes | ✅ Computed | |
| `PRANDtls[]` | 🔶 Optional | ❌ Missing | PRAN array |
| `PensionContributionFund[]` | 🔶 Optional | ❌ Missing | Pension fund array |

**Gaps:**
- ❌ `Section80DDBUsrType`, `NameOfSpecDisease80DDB` — needed for 80DDB
- ❌ `Form10BAAckNum` — needed if 80GG claimed
- ❌ `PRANDtls[]`, `PensionContributionFund[]` — NPS detail arrays

### 9. ITR1_IncomeDeductions — DEDUCT UND CHAP VIA (Allowed, Mandatory)

This mirrors the UsrDeductUndChapVIA but with statutory caps applied. The engine computes this correctly. All fields are covered via the engine's deduction result.

**Status:** ✅ All fields computed by engine with correct caps.

### 10. ITR1_IncomeDeductions — EXEMPT INCOME

| Official Schema Field | Mandatory? | Frontend Status | Notes |
|---|---|---|---|
| `ExemptIncAgriOthUs10.ExemptIncAgriOthUs10Total` | 🔴 Yes | ⚠️ Only agricultural asked | No other exempt income |
| `ExemptIncAgriOthUs10Dtls[].Category` | 🔶 Optional | ❌ Missing | AGRI/GOVC/ISI/SSRA/SRSC/SRST/SRPC/OTH |
| `ExemptIncAgriOthUs10Dtls[].SubCategory` | 🔶 Optional | ❌ Missing | 37 sub-category codes |
| `ExemptIncAgriOthUs10Dtls[].OthAmount` | 🔴 Yes | ❌ Missing | |

**Gaps:**
- ❌ Non-agricultural exempt income not collected (PPF interest, Sukanya, tax-free bonds, etc.)

### 11. ITR1_TaxComputation (Mandatory) ✅

All fields computed by the engine. No frontend gaps.

### 12. TaxPaid (Mandatory) ✅

All fields computed by the engine. No frontend gaps.

### 13. Refund (Mandatory) ✅

| Official Schema Field | Mandatory? | Frontend Status | Notes |
|---|---|---|---|
| `RefundDue` | 🔴 Yes | ✅ Computed | |
| `BankAccountDtls.AddtnlBankDetails[]` | 🔴 Yes | ✅ Collected | Bank name, account, IFSC |
| `BankAccountDtls.AddtnlBankDetails[].AccountType` | 🔴 Yes | ❌ Missing | SB/CA/CC/OD/NRO/OTH |
| `BankAccountDtls.AddtnlBankDetails[].UseForRefund` | 🔴 Yes | ❌ Missing | "true"/"false" |

### 14. Schedule80G (Optional)

| Official Schema Field | Mandatory? | Frontend Status | Notes |
|---|---|---|---|
| `TotalDonationsUs80GCash` | 🔴 Yes | ❌ Missing | |
| `TotalDonationsUs80GOtherMode` | 🔴 Yes | ❌ Missing | |
| `TotalDonationsUs80G` | 🔴 Yes | ❌ Missing | |
| `TotalEligibleDonationsUs80G` | 🔴 Yes | ❌ Missing | |
| `Don100Percent.*` | 🔶 Optional | ❌ Missing | 4 category sub-objects |
| `Don50PercentNoApprReqd.*` | 🔶 Optional | ❌ Missing | |
| `Don100PercentApprReqd.*` | 🔶 Optional | ❌ Missing | |
| `Don50PercentApprReqd.*` | 🔶 Optional | ❌ Missing | |
| `DoneeWithPan[]` (per category) | 🔶 Optional | ❌ Missing | Donee name, PAN, address, amounts |

**CRITICAL GAP:** The frontend collects a single ₹ amount for 80G (amount_80g) but the official schema requires a 4-category breakdown with per-donee arrays including PAN, address, cash vs other mode split, and eligible amounts. The JSON builder must populate the full Schedule80G structure.

### 15. Schedule80GGA (Optional) — ITR-1 specific

| Official Schema Field | Mandatory? | Frontend Status | Notes |
|---|---|---|---|
| `TotalDonationAmtCash80GGA` | 🔴 Yes | ❌ Missing | |
| `TotalDonationAmtOtherMode80GGA` | 🔴 Yes | ❌ Missing | |
| `TotalDonationsUs80GGA` | 🔴 Yes | ❌ Missing | |
| `TotalEligibleDonationAmt80GGA` | 🔴 Yes | ❌ Missing | |
| `DonationDtlsSciRsrchRuralDev[]` | 🔶 Optional | ❌ Missing | Per-donee entries with clause codes |

### 16. Schedule80GGC (Optional)

Same pattern — ❌ entirely missing from frontend.

### 17. Schedule80D (Mandatory)

| Official Schema Field | Mandatory? | Frontend Status | Notes |
|---|---|---|---|
| `Sec80DSelfFamSrCtznHealth.SeniorCitizenFlag` | 🔴 Yes | ⚠️ Derived from age | Set to Y/N/S but not exposed |
| `Sec80DSelfFamSrCtznHealth.SelfAndFamily` | 🔶 Optional | ⚠️ Computed but not separately surfaced | |
| `Sec80DSelfFamSrCtznHealth.HealthInsPremSlfFam` | 🔶 Optional | ⚠️ Collected `80d_self_family` | |
| `Sec80DSelfFamSrCtznHealth.PrevHlthChckUpSlfFam` | 🔶 Optional | ✅ Collected `80d_preventive_self` | |
| `Sec80DSelfFamSrCtznHealth.SelfAndFamilySeniorCitizen` | 🔶 Optional | ⚠️ Computed | |
| `Sec80DSelfFamSrCtznHealth.HlthInsPremSlfFamSrCtzn` | 🔶 Optional | ⚠️ Computed | |
| `Sec80DSelfFamSrCtznHealth.PrevHlthChckUpSlfFamSrCtzn` | 🔶 Optional | ⚠️ Computed | |
| `Sec80DSelfFamSrCtznHealth.MedicalExpSlfFamSrCtzn` | 🔶 Optional | ❌ Missing | Medical expense for non-insured seniors |
| `Sec80DSelfFamSrCtznHealth.ParentsSeniorCitizenFlag` | 🔴 Yes | ⚠️ Derived | |
| `Sec80DSelfFamSrCtznHealth.Parents` | 🔶 Optional | ⚠️ Computed | |
| `Sec80DSelfFamSrCtznHealth.HlthInsPremParents` | 🔶 Optional | ✅ Collected `80d_parents` | |
| `Sec80DSelfFamSrCtznHealth.PrevHlthChckUpParents` | 🔶 Optional | ✅ Collected `80d_preventive_parents` | |
| `Sec80DSelfFamSrCtznHealth.ParentsSeniorCitizen` | 🔶 Optional | ⚠️ Computed | |
| `Sec80DSelfFamSrCtznHealth.HlthInsPremParentsSrCtzn` | 🔶 Optional | ⚠️ Computed | |
| `Sec80DSelfFamSrCtznHealth.PrevHlthChckUpParentsSrCtzn` | 🔶 Optional | ⚠️ Computed | |
| `Sec80DSelfFamSrCtznHealth.MedicalExpParentsSrCtzn` | 🔶 Optional | ❌ Missing | Medical expense for non-insured senior parents |
| `Sec80DSelfFamSrCtznHealth.EligibleAmountOfDedn` | 🔴 Yes | ⚠️ Computed | |
| `Sch80DInsDtls[]` (4 sub-objects) | 🔶 Optional | ❌ Missing | Per-policy insurer name, policy no, amount |

**Gaps:**
- ❌ `MedicalExpSlfFamSrCtzn`, `MedicalExpParentsSrCtzn` — medical expense for seniors without insurance
- ❌ `Sch80DInsDtls[]` — policy-level detail arrays (4 categories: self, self-senior, parents, parents-senior)

### 18. Schedule80DD (Optional)

| Official Schema Field | Mandatory? | Frontend Status | Notes |
|---|---|---|---|
| `NatureOfDisability` | 🔴 Yes | ❌ Missing | "1" or "2" |
| `TypeOfDisability` | 🔴 Yes | ⚠️ `dd_severe` maps partially | "1" or "2" |
| `DeductionAmount` | 🔴 Yes | ✅ Computed | |
| `DependentType` | 🔴 Yes | ❌ Missing | "1" through "7" |
| `DependentPan` | 🔶 Optional | ❌ Missing | |
| `DependentAadhaar` | 🔶 Optional | ❌ Missing | |
| `Form10IAAckNum` | 🔶 Optional | ❌ Missing | |
| `UDIDNum` | 🔶 Optional | ❌ Missing | |

### 19. Schedule80U (Optional)

| Official Schema Field | Mandatory? | Frontend Status | Notes |
|---|---|---|---|
| `NatureOfDisability` | 🔴 Yes | ❌ Missing | "1" or "2" |
| `TypeOfDisability` | 🔴 Yes | ⚠️ `u_severe` maps partially | "1" or "2" |
| `DeductionAmount` | 🔴 Yes | ✅ Computed | |
| `Form10IAAckNum` | 🔶 Optional | ❌ Missing | |
| `UDIDNum` | 🔶 Optional | ❌ Missing | |

### 20. Schedule80E, 80EE, 80EEA, 80EEB (Optional)

| Official Schema Field | Mandatory? | Frontend Status | Notes |
|---|---|---|---|
| `Schedule80E.Schedule80EDtls[]` | 🔴 Yes (if claimed) | ❌ Missing | Per-loan details: bank, loan account, date, amounts |
| `Schedule80E.TotalInterest80E` | 🔴 Yes | ✅ Collected as flat amount | |
| `Schedule80EE.Schedule80EEDtls[]` | 🔴 Yes (if claimed) | ❌ Missing | Per-loan details |
| `Schedule80EE.TotalInterest80EE` | 🔴 Yes | ✅ Collected as flat amount | |
| `Schedule80EEA.PropStmpDtyVal` | 🔴 Yes | ❌ Missing | Stamp duty value (max ₹45L) |
| `Schedule80EEA.Schedule80EEADtls[]` | 🔴 Yes (if claimed) | ❌ Missing | Per-loan details |
| `Schedule80EEB.Schedule80EEBDtls[]` | 🔴 Yes (if claimed) | ❌ Missing | Per-loan + vehicle reg |
| `Schedule80EEB.VehicleRegNo` | 🔴 Yes | ❌ Missing | Vehicle registration number |

### 21. Schedule80C (Optional)

| Official Schema Field | Mandatory? | Frontend Status | Notes |
|---|---|---|---|
| `Schedule80CDtls[]` | 🔴 Yes (if claimed) | ❌ Missing | Per-investment details |
| `TotalAmt` | 🔴 Yes | ✅ Collected as flat `amount_80c` | |

### 22. ScheduleEA10_13A (HRA) — Optional

| Official Schema Field | Mandatory? | Frontend Status | Notes |
|---|---|---|---|
| `Placeofwork` | 🔴 Yes | ✅ `hra_metro` collected | Maps to "1" (metro) or "2" (non-metro) |
| `ActlHRARecv` | 🔴 Yes | ✅ `hra_received` collected | |
| `ActlRentPaid` | 🔴 Yes | ✅ `rent_paid` collected | |
| `DtlsSalUsSec171` | 🔴 Yes | ❌ Missing | Salary details u/s 17(1) |
| `BasicSalary` | 🔴 Yes | ❌ Missing | Basic salary for HRA |
| `DearnessAllwnc` | 🔶 Optional | ❌ Missing | |
| `ActlRentPaid10Per` | 🔴 Yes | ⚠️ Computed but not separately input | |
| `Sal40Or50Per` | 🔴 Yes | ⚠️ Computed but not separately input | |
| `EligbleExmpAllwncUs13A` | 🔴 Yes | ⚠️ Computed but not separately input | |

**Gaps:**
- ❌ `DtlsSalUsSec171`, `BasicSalary` — HRA computation inputs not collected separately

### 23. TDSonSalaries (Optional)

| Official Schema Field | Mandatory? | Frontend Status | Notes |
|---|---|---|---|
| `TotalTDSonSalaries` | 🔴 Yes (if present) | ✅ Computed | |
| `TDSonSalary[].EmployerOrDeductorOrCollectDetl.TAN` | 🔴 Yes (per entry) | ⚠️ Hardcoded "DELA00001A" | Not collected |
| `TDSonSalary[].EmployerOrDeductorOrCollectDetl.EmployerOrDeductorOrCollecterName` | 🔴 Yes (per entry) | ⚠️ Hardcoded "ABC Corp" | Not collected |
| `TDSonSalary[].IncChrgSal` | 🔴 Yes (per entry) | ✅ Populated | |
| `TDSonSalary[].TotalTDSSal` | 🔴 Yes (per entry) | ✅ Populated | |

### 24. TDSonOthThanSals (Optional)

Same issues — TAN/deductor name hardcoded, and `TDSSection` is hardcoded "194A".

### 25. TaxPayments (Optional)

| Official Schema Field | Mandatory? | Frontend Status | Notes |
|---|---|---|---|
| `TotalTaxPayments` | 🔴 Yes (if present) | ⚠️ Not populated | |
| `TaxPayment[].BSRCode` | 🔴 Yes (per entry) | ❌ Missing | |
| `TaxPayment[].DateDep` | 🔴 Yes (per entry) | ❌ Missing | |
| `TaxPayment[].SrlNoOfChaln` | 🔴 Yes (per entry) | ❌ Missing | |
| `TaxPayment[].Amt` | 🔴 Yes (per entry) | ❌ Missing | |

**Gap:** Advance tax and self-assessment tax are collected as flat amounts but the official schema requires per-challan detail (BSR code, date, serial number).

### 26. LTCG112A (Optional)

| Official Schema Field | Mandatory? | Frontend Status | Notes |
|---|---|---|---|
| `TotSaleCnsdrn` | 🔴 Yes (if present) | ✅ `cg_sale` collected | |
| `TotCstAcqisn` | 🔴 Yes (if present) | ✅ `cg_cost` collected | |
| `LongCap112A` | 🔴 Yes (if present) | ✅ `ltcg_112a` collected | Capped at ₹1,25,000 |

### 27. Verification (Mandatory) ✅

All fields populated correctly.

### 28. TaxReturnPreparer (Optional) ❌ Missing entirely

---

## ITR-4 — KEY ADDITIONAL SECTIONS

### ScheduleBP (Mandatory for ITR-4)

The ITR-4 frontend correctly collects:
- 44AD: turnover, digital/cash split, declared income ✅
- 44ADA: gross receipts, digital/cash split, declared income ✅
- 44AE: vehicles, heavy/light, GVW, months, declared income ✅

**Gap:** `ScheduleBPFinancial` (18 fields — capital, creditors, assets etc.) not collected.

### ITR-4 JSON Field Gaps

| Official Schema Field | Mandatory? | Frontend Status |
|---|---|---|
| `PersonalInfo.Status` | 🔴 Yes | ⚠️ Hardcoded "I" — should reflect assessee type |
| `FilingStatus.NatureOfEmpl` | 🔶 Optional | ❌ Not collected |
| `FilingStatus.ItrFilingDueDate` | 🔴 Yes | ✅ Collected |
| `ScheduleIT.TaxPayment[]` | 🔴 Yes | ❌ Missing per-challan breakdown |
| `TDS3 entries` | 🔶 Optional | ❌ Missing |

---

## CROSS-CUTTING GAPS (ITR-2/ITR-3 Field Dependencies)

The ITR-1/ITR-4 frontend shares models with ITR-2/ITR-3. These fields exist in the shared Pydantic schemas but are never collected:

### Capital Gains (ITR-2 full CG)
- `CGTransaction` model (16 fields) — only 112A simplified version collected
- `CG112AScrip` (12 fields) — per-scrip ISIN, FMV, shares
- `VDATransaction` — virtual digital assets
- `BFLossItem`, `CFLLossItem` — carry-forward losses
- `ScheduleSIEntry` — special rate incomes

### Foreign Assets/Income (ITR-2)
- `FSICountryEntry` (8 fields)
- `TR1Entry` (6 fields)

### Clubbing of Income (ITR-2)
- `SPIEntry` (4 fields)

### AMT (ITR-2)
- `AMTInput` (5 fields)

### Agricultural Income (ITR-2 detailed)
- `AgriculturalIncome` (3 fields) — gross, deductions, share from firm

### Exempt Income (ITR-2)
- `ExemptIncome` (5 fields) — PPF, Sukanya, tax-free bonds, NRE, other

### Business Income (ITR-3)
- `BusinessIncome` (30+ fields) — PGBP full computation
- `BalanceSheet` (12 fields)
- `NatureOfBusiness`, `AuditInfo`
- `PartnerInFirm`, `UDEntry`
- Business-specific deductions: 80-IA, 80-IB, 80-IC, 80RA, 10AA

---

## NEW REGIME vs OLD REGIME FIELD HANDLING

### Old Regime
Frontend correctly shows all Chapter VI-A deductions ✅

### New Regime
Frontend correctly hides most deductions, shows only 80CCD(2) + 80CCH ✅

**Regime validation gaps:**
- No check that `DeductionUs16ia` (standard deduction) is capped at ₹50K (old) vs ₹75K (new)
- No validation that `Rebate87A` threshold differs: ₹5L TI / ₹12,500 tax (old) vs ₹12L TI / ₹60,000 tax (new)

---

## VALIDATION GAPS SUMMARY

| Validation | Status | Notes |
|---|---|---|
| PAN format `[A-Z]{5}[0-9]{4}[A-Z]` | ✅ | |
| IFSC format `[A-Z]{4}0[A-Z0-9]{6}` | ✅ | |
| Date format YYYY-MM-DD | ✅ | |
| Aadhaar 12 digits | ✅ | Format check only |
| Mobile 10 digits | ✅ | |
| Email regex | ❌ | No format validation |
| StateCode enum (01-37, 99) | ❌ | No enum restriction |
| CountryCode enum (~240 values) | ❌ | No enum restriction |
| EmployerCategory full enum (9 values) | ⚠️ | Only 6 of 9 |
| PIN code regex `[1-9][0-9]{5}` | ❌ | No format check |
| Account type enum (SB/CA/CC/OD/NRO/OTH) | ❌ | Not collected |
| TDSSection enum (57 values) | ❌ | Hardcoded "194A" |
| Disease code enum (a-n, 14 values) for 80DDB | ❌ | Not collected |
| Form10IAAckNum format for 80DD/80U | ❌ | Not collected |
| TotalIncome max ₹51,25,000 for ITR-1 | ✅ | Engine enforced |
| GTI > ₹50L gate for ITR-4 | ✅ | Engine enforced |
| 112A LTCG max ₹1,25,000 | ✅ | Enforced |
| Agricultural income > ₹5,000 → ITR-2 | ✅ | Enforced |
| Section 80GGA only for ITR-1 | ✅ | ITR-4 excludes it |

---

## SEVERITY PRIORITIZATION

### 🔴 CRITICAL (JSON will be rejected by ITD)
1. **Schedule80G missing** — flat amount vs full 4-category + DoneeWithPan array
2. **Schedule80D missing policy-level detail** — Sch80DInsDtls arrays
3. **Schedule80E/80EE/80EEA/80EEB missing loan-level detail** — per-loan arrays
4. **Schedule80C missing investment detail** — Schedule80CDtls array
5. **Bank AccountType + UseForRefund** — mandatory but not collected
6. **TaxPayment per-challan details** — BSR code, date, serial number missing

### 🟠 HIGH (functionally needed)
7. **DeductUndChapVIA.Section80DDBUsrType + NameOfSpecDisease** — mandatory for 80DDB
8. **Schedule80DD dependent type + nature of disability** — mandatory
9. **Schedule80U nature of disability** — mandatory
10. **ScheduleEA10_13A (HRA)** DtlsSalUsSec171, BasicSalary — needed for proper HRA

### 🟡 MEDIUM (optional but good practice)
11. **AlternateAddress** — complete secondary address block
12. **Secondary mobile/email**
13. **EmployerCategory full enum** (9 values vs 6)
14. **Email regex validation**
15. **StateCode/CountryCode enum validation**
16. **PropertyDetails address per property**
17. **Co-owner/Tenant arrays**
18. **SeventhProvisio139 fields** (mandatory filing triggers)

### 🔵 NICE-TO-HAVE
19. **TaxReturnPreparer**
20. **AssesseeRep details**
21. **PRAN/Pension fund arrays**
22. **Exempt income breakdown (non-agri)**

---

## ITR-2 / ITR-3 SHARED-FIELD NOTES

When the frontend expands to ITR-2 and ITR-3, these additional fields will need collection:

### ITR-2 requires:
- `CGTransaction[]` — full capital gains with indexation, 54/54B/54EC/54F deductions
- `CG112AScrip[]` — per-scrip 112A detail
- `BF/CF Loss Items` — carry-forward/brought-forward losses
- `AgriculturalIncome` — gross, deductions, share from firm
- `ExemptIncome` — PPF, Sukanya, tax-free bonds, NRE
- `FSICountryEntry[]` — foreign income by country
- `TR1Entry[]` — DTAA relief by country
- `SPIEntry[]` — clubbing of income
- `AMTInput` — alternate minimum tax
- `ResidentialStatus` — RES/NRI/NOR

### ITR-3 additionally requires:
- `BusinessIncome` — full PGBP with disallowances, depreciation, ICDS
- `BalanceSheet` — 12 fields
- `PartA_GEN2` — audit info, nature of business
- `PartnerInFirm[]` — Schedule IF
- `UDEntry[]` — unabsorbed depreciation
- `ScheduleBPFinancial` — financial particulars



---

---

# ITR-2 — COMPLETE SECTION-BY-SECTION FIELD AUDIT

**Official Schema:** ITR-2_2026_Main_V1.1 (14,421 lines, 46 top-level sections)
**8 mandatory** + **38 optional** sections

## ITR-2 TOP-LEVEL SECTIONS

| # | Section | Mandatory | Description |
|---|---|---|---|
| 1 | CreationInfo | Yes | SW/JSON metadata (6 fields) |
| 2 | Form_ITR2 | Yes | Form identity |
| 3 | PartA_GEN1 | Yes | PersonalInfo + FilingStatus |
| 4 | ScheduleS | Opt | Salary - per-employer array with TAN |
| 5 | ScheduleHP | Opt | House Property (can be negative) |
| 6 | **ScheduleCGFor23** | Opt | **Full Capital Gains** - STCG + LTCG with indexation |
| 7 | **Schedule112A** | Opt | LTCG on listed equity - per-scrip ISIN |
| 8 | Schedule115AD | Opt | FII capital gains |
| 9 | **ScheduleVDA** | Opt | Virtual Digital Assets |
| 10 | **ScheduleOS** | Opt | Other Sources (85+ fields) |
| 11 | ScheduleCYLA | Yes | Current Year Loss (11 heads) |
| 12 | ScheduleBFLA | Yes | Brought Forward Loss (11 heads) |
| 13 | ScheduleCFL | Opt | Carry Forward Loss (8 AYs) |
| 14 | ScheduleVIA | Opt | Chapter VI-A deductions |
| 15-25 | 80C/80D/80G/80GGC/80DD/80U/80E/80EE/80EEA/80EEB/80GGA | Opt | All deduction schedules |
| 26 | **ScheduleAMT** | Opt | AMT computation |
| 27 | **ScheduleAMTC** | Opt | AMT Credit (13 AY array) |
| 28 | **ScheduleSPI** | Opt | Clubbing of Income |
| 29 | **ScheduleSI** | Opt | Special Rate Income (68 codes x 12 rates) |
| 30 | **ScheduleEI** | Opt | Exempt Income (51 sub-categories) |
| 31 | SchedulePTI | Opt | Pass Through Income |
| 32 | **ScheduleFSI** | Opt | Foreign Source Income per country |
| 33 | **ScheduleTR1** | Opt | Tax Relief DTAA |
| 34 | **ScheduleFA** | Opt | **Foreign Assets - 10 sub-arrays** |
| 35 | Schedule5A2014 | Opt | Clubbing with spouse |
| 36 | **ScheduleAL** | Opt | Assets & Liabilities (>50L trigger) |
| 37 | PartB-TI | Yes | Total Income (17 fields) |
| 38 | PartB_TTI | Yes | Tax + TaxPaid + Refund |
| 39 | ScheduleIT | Opt | Per-challan tax payments |
| 40-43 | TDS1/2/3 + TCS | Opt | TDS schedules |
| 44 | Verification | Yes | |
| 45 | TaxReturnPreparer | Opt | TRP |
| 46 | **ScheduleESOP** | Opt | ESOP deferred tax (6 AYs) |

## CRITICAL ITR-2 SECTIONS - FIELD INVENTORY

### ScheduleCGFor23 - Full Capital Gains (CORE)

**ShortTermCapGainFor23:** SaleofLandBuild (FullValConsid, DeductUS48->CostOfAcquisition, CostOfImprov, ExpOnTranfer, Balance), DeductUS54B, DeductUS54F, SaleofLandBuildDtls[] array, SaleofMF, IncChrgblSTCG_DTAA_115AD, TOT_STCG_For23.

**LongTermCapGain23 WITH INDEXATION:** SaleofLandBuild (FullValConsid, CostOfAcquisition, **IndexedCostOfAcq**, CostOfImprov, **IndexedcostOfImp**, ExpOnTranfer, Balance CAN BE NEGATIVE). **6 deduction trackers:** DeductionUs54, 54B, 54EC, 54F, 54G, 54GA - each with Dtls[] per-transaction array.

**Other sub-sections:** CurrYrLosses (6 CG sub-types x setoff types, 42+ tracking fields), AccruOrRecOfCG (quarterly Q1-Q4), DeducClaimInfo.

### Schedule112A - Per-Scrip LTCG Detail

| Field | Type | Constraint |
|---|---|---|
| Schedule112ADtls[].ISINCode | string | [A-Z0-9]{12} |
| Schedule112ADtls[].NameOfShareUnit | string | Max 125 |
| Schedule112ADtls[].NumberOfSharesUnits | integer | |
| Schedule112ADtls[].SaleValuePerShareUnit | integer | |
| Schedule112ADtls[].CostAcqPerShareUnit | integer | |
| Schedule112ADtls[].FMVPerShareUnit | integer | Grandfathered |
| Balance112A, TotalBalance112A | integer | **Can be negative** |

### ScheduleVDA - Virtual Digital Assets

Per-transaction array: DateofAcquisition, DateofTransfer (both YYYY-MM-DD), HeadUndIncTaxed (enum: [CG]), AcquisitionCost, ConsidReceived, IncomeFromVDA. TotIncCapGain.

### ScheduleFA - Foreign Assets (10 Arrays)

All 10 share: CountryName, CountryCodeExcludingIndia (2-char ISO).

| # | Sub-section | Per-Item Unique Fields |
|---|---|---|
| A | DetailsForiegnBank | NameOfBank, AddressOfBank, AccountNumber, **AccountType**(1-6), StatusOfAccount, PeakBalance, ClosingBalance, GrossInterest, GrossAmountOther |
| B | DtlsForeignCustodialAcc | NameOfFinancialInstitution + same bank fields |
| C | DtlsForeignEquityDebtInterest | **NatureOfEntity**(1-9), DateOfAcquisition, DateOfSale, InvestmentValue |
| D | DtlsForeignCashValueInsurance | NameOfFinancialInstitution, CashSurrenderValue, DateOfPolicy |
| E | DetailsFinancialInterest | Any other financial interest |
| F | DetailsImmovableProperty | Address, value, acquisition date |
| G | DetailsOthAssets | Any other capital asset |
| H | DetailsOfAccntsHvngSigningAuth | Signing authority accounts |
| I | DetailsOfTrustOutIndiaTrustee | Trust + trustee |
| J | DetailsOfOthSourcesIncOutsideIndia | Other foreign income |

### ScheduleSI - Special Rate Income

SplCodeRateTax[].SecCode: **68 enum values**. SplCodeRateTax[].SplRatePercent: **12 enum values** (1,5,10,15,12.5,20,25,30,50,60,4,9). SplRateInc, SplRateIncTax.

### ScheduleEI - Exempt Income

ExcNetAgriIncDtls[] array. OthersIncDtls[] array with **51 SubCategory codes** (10(1) through Receiptnotincme). IncNotChrgblAsPerDTAADtls[] array.

### ScheduleAL - Assets & Liabilities

MovableAsset has 8 categories: DepositsInBank, SharesAndSecurities, InsurancePolicies, LoansAndAdvancesGiven, CashInHand, JewelleryBullionEtc, VehiclesYachtsBoatsAircrafts, Others. ImmovableDetails[] array. LiabilityInRelatAssets.

### ScheduleESOP - Deferred Tax (6 AYs)

6 assessment year sub-sections (2021-22 through 2026-27), each with: TaxDeferredBFEarlierAY, ScheduleESOPEventDtls[] (per-event: allotment date, exercise date, FMV), TotalTaxAttributedAmt, TaxPayableCurrentAY, BalanceTaxCF.

---

---

# ITR-3 - COMPLETE SECTION-BY-SECTION FIELD AUDIT

**Official Schema:** ITR-3_2026_Main_V1.1 (1,060,874 bytes, 69 sections, 287 definitions)
**12 mandatory** + **57 optional** sections
**This is the MOST complex form** - full business income with PGBP, depreciation, balance sheet

## ITR-3 MANDATORY SECTIONS (12)

CreationInfo, Form_ITR3, PartA_GEN1, **PartA_GEN2**, **PARTA_BS**, **PARTA_PL**, **ITR3ScheduleBP**, ScheduleCYLA, ScheduleBFLA, PartB-TI, PartB_TTI, Verification

## ITR-3 UNIQUE BUSINESS SECTIONS (21)

ManufacturingAccount, TradingAccount, PARTA_OI, PARTA_QD, **ScheduleDPM**, **ScheduleDOA**, ScheduleDEP, ScheduleDCG, ScheduleESR, **ITR3ScheduleUD**, ScheduleICDS, Schedule10AA, **ScheduleIF**, ScheduleGST, ScheduleTPSA, Schedule80_IA, Schedule80_IB, Schedule80_IC, Schedule80RA

Plus ALL 36 ITR-2 schedules inherited (S, HP, CGFor23, 112A, 115AD, VDA, OS, CFL, VIA, deductions, AMT, SPI, SI, EI, PTI, FSI, TR1, FA, AL, 5A2014, ESOP, TDS/TCS, IT)

## ITR-3 BUSINESS-SPECIFIC FIELD INVENTORY

### A. PartA_GEN2 - Audit Info (Mandatory)

| Field | Type | Constraint |
|---|---|---|
| LiableSec44AAflg, LiableSec44ABflg, AuditAccountantFlg | string | Y/N pattern |
| TotalSalesExcOneCr | enum | Upto1CR/Upto10CR/MoreThan10CR |
| AgrOFAllAmtsRcvd, AgrOFAllPayMade | enum | Upto5Per/MoreThan5Per |
| Cndnfor44AB | enum | bi/bii/biii |
| BiiDetails | object | 44AD/44ADA/44AE/44BB Y/N flags |
| AuditDetails92E | object | TP audit: AuditorName, AuditorPAN, AuditDate |
| AuditDetails | object | AuditorName, AuditorPAN, AuditDate, AcknowledgementNum |
| AuditReportDetails[] | Array | Multiple auditor entries |
| NatOfBus[] | Array | NatureOfBusiness + BusinessCode |

### B. PARTA_BS - Balance Sheet (Mandatory, 30+ fields)

**FundSrc:** PropFund.PropCap, ResrNSurp(RevResr, CapResr, StatResr, OthResr, TotResrNSurp), TotPropFund. LoanFunds.SecrLoan(ForeignCurrLoan, RupeeLoan:FrmBank, FrmOthrs, TotRupeeLoan, TotSecrLoan), LoanFunds.UnsecrLoan(FrmBank, FrmOthrs, TotUnSecrLoan), TotLoanFund, TotFundSrc.

**AppOfFunds:** FixedAssets, NonCurrentInvst, CurrentAssets(Inventories, SundryDebtors, CashBank, LoansAdvances, OtherCA), CurrentLiabilities(SundryCreditors, Provisions, OtherCL), NetCurrentAssets, TotAppOfFunds. All integer 0-99999999999999.

### C. PARTA_PL - Profit & Loss (Mandatory, 40+ fields)

**CreditsToPL:** GrossProfitFromTrading, OthIncome(RentInc, Comissions, Dividends, InterestInc, ProfitOnSaleFixedAsset, ProfitOnInvChrSTT, ProfitOnOthInv, ProfitOnCurrFluct, ProfitOnCnvInvntryToCapAsst, ProfitOnAgriIncome, LiabilityWrittenBack, AmtofInterest, AmtofRem, MiscOthIncome, TotOthIncome), OtherIncDtls[] array{NatureOfIncome, Amount}, TotCreditsToPL.

**DebitsToPL (24 expense heads):** Freight, ConsumptionOfStores, PowerFuel, RentRatesTaxes, Repairs, Insurance, TravelExpenses, Advertisement, BadDebts, InterestPaid, Depreciation, AmortizationOfPreliminaryExpenses, DirectorsRemuneration, EmployeesRemuneration, AuditorsRemuneration, LegalExpenses, PostageTelephone, PrintingStationery, BankCharges, SundryExpenses, OtherExpenses, PenaltyPaid, DonationPaid, TotDebitsToPL.

### D. ITR3ScheduleBP - PGBP Core Computation

25+ sub-sections: ProfBfrTaxPL, NetPLFromSpecBus, NetPLFromSpecifiedBus, IncRecCredPLOthHeadDtls[] array, IncDebitedPLNotDeductible, IncNotCredPLButTaxable, PLUs44sChapXIIG(44AD/44ADA/44AE/44B/44BB/44BBA/44BBC/44BBD/44DA presumptives), ProfitLossInclRefrdSec, ProfitFrmActCvrd(Rule7/7A/7B/7B1A/8), IncCredPL(firm share, AOP/BOI, CG, dividends 115-O), **8 Disallowance sections**(40(a)(i), 40(a)(ia), 40A(2), 40A(3), 40(b), 43B, 36(1)(va), 14A), Depreciation adjustments(books vs IT Act), ICDS adjustments(increase/decrease), DeductionUs32_1_iii, TotalBusinessIncome.

### E. ScheduleDPM - Depreciation on Plant & Machinery

4 rate blocks (15%, 30%, 40%, 45%). **Per-block 14 fields:** WDVFirstDay, AdjustmentSec115BAC, AdditionsGrThan180Days(full rate), AdditionsLessThan180Days(half rate), FullRateDeprAmt, HalfRateDeprAmt, AddlnDeprOnGT180DayAdditions, AddlnDeprOnLessThan180DayAdditions, TotalDepreciation, DepDisAllowUs38_2, NetAggregateDepreciation, ProportionateAggDepreciation, ExpdrOnTrforSaleAsset, CapGainUs50.

### F. ScheduleDOA - Depreciation on Other Assets

7 blocks: Land(N/A rate), Building(5%), Building(10%), Building(40%), Furniture(10%), Intangible(25%), Ships(20%). Each uses same 14-field structure as DPM.

### G. PARTA_QD - Quantitative Details (Conditional on 44AB)

3 arrays x max 20 items: Trading items, Raw materials, Finished goods. Per item: ItemName(max25), **UnitOfMeasure**(23-value enum: 101=Bags, 102=Boxes, 103=Gms, 104=Kgs, 105=K.Ltr, 106=Ltr, 107=Metres, 108=Nos, 109=Pairs, 110=Pcs, 111=Quintals, 112=Sets, 113=SqFt, 114=SqMtr, 115=Tonnes, 116=Units, 117=Acre, 118=Bales, 119=Barrels, 120=Cartons, 121=Grs, 122=Prs, 999=Others), OpeningStock, PurchaseQty, SaleQty, ClosingStock(integer 0-99999999999999).

### H. ScheduleIF - Partner in Firm

Per-partner: FirmName(1-125), FirmPAN([A-Z]{5}[0-9]{4}[A-Z]), IsLiableToAudit(Y/N), Sec92EFirmFlag(Y/N), ProfitSharePercent(0-100, multipleOf0.01), ProfitShareAmt, IntrstAmtDueOrRecv, RemunernAmtDueOrRecv, FirmCapBalOn31Mar.

### I. Other ITR-3 Schedules

| Schedule | Content |
|---|---|
| ScheduleGST | GSTIN array: GSTINNo([a-zA-Z0-9]{15}), AmtTurnGrossRcptGSTIN |
| ITR3ScheduleUD | Unabsorbed depreciation per AY |
| ScheduleICDS | ICDS I-X per-standard deviations |
| ScheduleESR | Scientific research: 35(1)(i)/(ii)/(iia)/(iii)/(iv), 35(2AA), 35(2AB) |
| Schedule10AA | SEZ: DateOfCommencement, ExportTurnover, TotalTurnover, ProfitDerived, DeductionAmt |
| Schedule80_IA/IB/IC | Per-unit business deduction tracking |
| ManufacturingAccount | 15+ fields: raw material, WIP, direct/indirect expenses |
| TradingAccount | 15+ fields: sales, services, other revenue, excise/VAT, stock |
| PARTA_OI | Accounting method(MERC/CASH), stock valuation(1/2/3 for RM+FG) |

---

## VALIDATION REQUIREMENTS - ALL FORMS

### Regex Patterns Needed

| Pattern | Usage | Forms |
|---|---|---|
| [A-Z]{5}[0-9]{4}[A-Z] | PAN | All |
| [0-9]{12} | Aadhaar | All |
| YYYY-MM-DD regex | All dates | All |
| [A-Z]{4}[0-9]{5}[A-Z] | TAN | All |
| [A-Z]{4}[0][A-Z0-9]{6} | IFSC | All |
| [A-Z0-9]{12} | ISIN | 2/3 |
| [a-zA-Z0-9]{15} | GSTIN | 3 |
| [1-9][0-9]{9} | Mobile | All |
| [1-9][0-9]{5} | PIN | All |
| [0-9]{15} | Ack number | All |
| [0-9]{3}[0-9A-Z]{4} | BSR | All |
| [S][W][0-9]{8} | SW ID | All |
| [T][0-9]{9}|[0-9]{6} | TRP ID | All |
| DIPP[0-9]{3,5} | DPIIT Reg | 2/3 |

### Key Enums (Dropdowns Required)

| Enum | Count | Key Values |
|---|---|---|
| StateCode | 38 | 01-37 + 99(Foreign) |
| CountryCode | ~240 | ISO calling codes |
| EmployerCategory | 9 | CGOV/SGOV/PSU/PE/PESG/PEPS/PEO/OTH/NA |
| ReturnFileSec | 8 | 11-20 |
| Capacity(Verification) | 4 | S/R/K/A |
| Status | 2 | I(Individual)/H(HUF) |
| SecCode(ScheduleSI) | 68 | Section codes for special rates |
| SplRatePercent | 12 | 1,5,10,15,12.5,20,25,30,50,60,4,9 |
| NatureOfDisability | 2 | 1(normal)/2(severe) |
| TypeOfDisability | 2 | 1/2 |
| DependentType(80DD) | 8 | 1-8 |
| Disease codes(80DDB) | 14 | a-n (neurological, cancer, AIDS etc) |
| LoanType | 2 | B(Bank)/I(Other) |
| AccountType(Bank) | 6 | SB/CA/CC/OD/NRO/OTH |
| PropertyOwner | 4 | SE/MI/SP/OT |
| ifLetOut | 3 | L/D/S |
| UnitOfMeasure(QD) | 23 | 101-122 + 999 |
| 80GGA clauses | 8 | 80GGA2a-2e |
| TDSSection | 59 | Section codes |
| AccountType(FA) | 6 | 1-6 |
| NatureOfEntity(FA) | 9 | 1-9 |
| Allowance codes | 17 | 10(5)-10(17) |
| Exempt sub-categories | 51 | Various |
| DeductedYr | 18 | 2025-2008 |
| Donation categories(80G) | 4 | 100%/50% x with/without approval |

### Negative-Allowed Fields

| Field | Forms |
|---|---|
| IncomeOfHP / TotalIncomeChargeableUnHP | 1/2/3 |
| Balance112A / TotalBalance112A | 2/3 |
| Balance115AD / TotalBalance115AD | 2/3 |
| AmtNotDeductibleUs58(OS) | 2/3 |
| ProfitChargTaxUs59(OS) | 2/3 |
| BalanceNoRaceHorse / BalanceOwnRaceHorse(OS) | 2/3 |
| GrossIncChrgblTaxAtAppRate(OS) | 2/3 |
| InterestGross(OS) | 2/3 |
| NatofPassThrghIncome(OS) | 2/3 |
| TotalIncItemPartBTI(AMT) | 2/3 |
| DeductionClaimUndrAnySec(AMT) | 2/3 |
| AmtTaxRefunded(TR) | 2/3 |

---

## FRONTEND IMPLEMENTATION ROADMAP

### Phase 1 - ITR-1/ITR-4 Critical Fixes
1. Schedule80G/80D/80E/80EE/80EEA/80EEB/80C detail arrays
2. Bank AccountType + UseForRefund
3. TaxPayment per-challan (BSR, date, serial)
4. Full EmployerCategory enum (9 values)
5. 80DDB user type + 14 disease codes
6. 80DD/80U disability nature/type/UDID/Form10IA

### Phase 2 - ITR-2 New Build
1. **ScheduleCGFor23** - STCG/LTCG with indexation, 54-series deductions
2. **Schedule112A** - Per-scrip ISIN detail
3. **ScheduleVDA** - Virtual digital assets
4. **ScheduleFA** - All 10 foreign asset arrays
5. **ScheduleFSI + ScheduleTR1** - Foreign income + DTAA
6. **ScheduleSI** - 68 special rate codes
7. **ScheduleEI** - Full exempt income with 51 sub-categories
8. **ScheduleSPI** - Clubbing of income
9. **ScheduleAL** - Assets & liabilities
10. **ScheduleESOP** - 6-AY ESOP deferred tax

### Phase 3 - ITR-3 Business Sections
1. **PartA_GEN2** - Audit info + NatureOfBusiness
2. **PARTA_BS** - Balance sheet (30+ fields)
3. **PARTA_PL** - Profit & Loss (40+ fields)
4. **ITR3ScheduleBP** - Full PGBP computation
5. **ScheduleDPM + ScheduleDOA** - Depreciation (11 blocks x 14 fields each)
6. **ManufacturingAccount + TradingAccount** (30+ fields total)
7. **PARTA_QD** - Quantitative details with 23-unit dropdown
8. **ScheduleIF** - Partnership firm details
9. **ScheduleGST** - GST turnover
10. Business deductions: 80-IA, 80-IB, 80-IC, 10AA
11. **ScheduleICDS + ITR3ScheduleUD**
