# TAXIFY FRONTEND CROSS-REFERENCE AUDIT
## Every Official Schema Field vs. Actual Frontend Implementation
### AY 2026-27 | Generated 2026-07-29

---

**Methodology:** 
- **Official Schema Source:** `C:\Users\Devansh\Desktop\Taxify\ITD OFFICAL REFERENCE DOCS\AY 2026-27 Offical Schema JSON\`
- **Validation Docs:** `C:\Users\Devansh\Desktop\Taxify\ITD OFFICAL REFERENCE DOCS\AY 2026-27 Offical Schema validatins txt\`
- **Frontend Source:** `C:\Users\Devansh\Desktop\Taxify\frontend\src\`
- **Key Pages:** `ITRComputationPage.tsx` (1850 lines), `ITRComputationTabs.tsx` (996 lines)
- **Key Components:** `EmployerEntryManager.tsx`, `HousePropertyEntryManager.tsx`, `CapitalGainsEntryManager.tsx`, `DonationEntryManager.tsx`, `BankInterestEntryManager.tsx`
- **Type Definitions:** `scheduleOS.ts`, `phase2.ts`, `import.types.ts`, `api.types.ts`

**Legend:**
| Icon | Meaning |
|---|---|
| ✅ | FULLY PRESENT — Field collected, validated, and mapped to schema correctly |
| ⚠️ | PARTIALLY PRESENT — Field exists but incomplete (missing validation, sub-fields, enum values, or regime handling) |
| ❌ | MISSING — Field required by schema but NOT collected anywhere in frontend |
| 🔵 | N/A — Not applicable for this form type |
| 🔴 | CRITICAL — JSON will be rejected by ITD if missing |

---

# PART 1: ITR-1 — COMPLETE FIELD-BY-FIELD CROSS-REFERENCE

## 1. CreationInfo (Mandatory — 6 fields)

| # | Schema Field | Mandatory | Frontend Variable | Status | Notes |
|---|---|---|---|---|---|
| 1.1 | `SWVersionNo` | 🔴 Yes | N/A (generated in `build_itr1_json`) | ✅ | Hardcoded "1.0" in backend JSON builder |
| 1.2 | `SWCreatedBy` | 🔴 Yes | N/A (generated) | ✅ | Pattern `SW[0-9]{8}` generated backend |
| 1.3 | `JSONCreatedBy` | 🔴 Yes | N/A (generated) | ✅ | Pattern `SW[0-9]{8}` generated backend |
| 1.4 | `JSONCreationDate` | 🔴 Yes | N/A (generated) | ✅ | YYYY-MM-DD generated backend |
| 1.5 | `IntermediaryCity` | 🔴 Yes | N/A (generated) | ✅ | Default "Delhi" in backend |
| 1.6 | `Digest` | 🔴 Yes | N/A (generated) | ✅ | 44-char digest computed backend |

**Section Status: ✅ All 6 fields handled by backend JSON builder. No frontend gaps.**

---

## 2. Form_ITR1 (Mandatory — 5 fields)

| # | Schema Field | Mandatory | Frontend Variable | Status | Notes |
|---|---|---|---|---|---|
| 2.1 | `FormName` | 🔴 Yes | `itrForm` state | ✅ | "ITR-1" set correctly |
| 2.2 | `Description` | 🔴 Yes | N/A (generated) | ✅ | Backend hardcodes description |
| 2.3 | `AssessmentYear` | 🔴 Yes | `ayParam` from context | ✅ | "2026" from AYContext |
| 2.4 | `SchemaVer` | 🔴 Yes | N/A (generated) | ✅ | "Ver1.0" |
| 2.5 | `FormVer` | 🔴 Yes | N/A (generated) | ✅ | "Ver1.0" |

**Section Status: ✅ All 5 fields handled.**

---

## 3. PersonalInfo (Mandatory — Comprehensive)

### 3A. AssesseeName

| # | Schema Field | Mandatory | Frontend Variable | Status | Notes |
|---|---|---|---|---|---|
| 3.1 | `AssesseeName.SurNameOrOrgName` | 🔴 Yes | `name` → split by backend | ✅ | Collected as full name, backend splits |
| 3.2 | `AssesseeName.FirstName` | Optional | `name` → split by backend | ✅ | From client master |
| 3.3 | `AssesseeName.MiddleName` | Optional | `name` → split by backend | ⚠️ | Backend may need explicit middle name if present |

### 3B. PAN

| # | Schema Field | Mandatory | Frontend Variable | Status | Notes |
|---|---|---|---|---|---|
| 3.4 | `PAN` | 🔴 Yes | `pan` | ✅ | From client master; backend validates regex `[A-Z]{5}[0-9]{4}[A-Z]` |

### 3C. Address

| # | Schema Field | Mandatory | Frontend Variable | Status | Notes |
|---|---|---|---|---|---|
| 3.5 | `Address.ResidenceNo` | 🔴 Yes | `flatNo` | ✅ | Collected in PersonalInfo tab |
| 3.6 | `Address.ResidenceName` | Optional | `premises` | ✅ | Collected as "Name of Premises" |
| 3.7 | `Address.RoadOrStreet` | Optional | `road` | ✅ | Collected as "Road/Street/Post Office" |
| 3.8 | `Address.LocalityOrArea` | 🔴 Yes | `area` | ✅ | Collected |
| 3.9 | `Address.CityOrTownOrDistrict` | 🔴 Yes | `city` | ✅ | Collected |
| 3.10 | `Address.StateCode` | 🔴 Yes | `state` | ⚠️ | Collected as TEXT INPUT — should be DROPDOWN with 38 state codes (01-37, 99). No enum validation. |
| 3.11 | `Address.CountryCode` | 🔴 Yes | `country` | ⚠️ | Collected as TEXT INPUT "India" — should be DROPDOWN with ~240 country codes. No enum validation. |
| 3.12 | `Address.PinCode` | Optional | `pincode` | ⚠️ | Collected but NO regex validation `[1-9][0-9]{5}` |
| 3.13 | `Address.ZipCode` | Optional | — | ❌ | Not collected anywhere |
| 3.14 | `Address.CountryCodeMobile` | 🔴 Yes | — | 🔴 **Hardcoded** | Hardcoded to "91" in backend JSON builder. NOT collected from user. |
| 3.15 | `Address.MobileNo` | 🔴 Yes | `mobile` | ✅ | Collected; backend validates 10 digits |
| 3.16 | `Address.EmailAddress` | 🔴 Yes | `email` | ⚠️ | Collected but NO email regex validation |
| 3.17 | `Address.CountryCodeMobileNoSec` | Optional | — | ❌ | Secondary mobile country code NOT collected |
| 3.18 | `Address.MobileNoSec` | Optional | — | ❌ | Secondary mobile NOT collected |
| 3.19 | `Address.EmailAddressSec` | Optional | — | ❌ | Secondary email NOT collected |

### 3D. Additional Personal Info

| # | Schema Field | Mandatory | Frontend Variable | Status | Notes |
|---|---|---|---|---|---|
| 3.20 | `SecondaryAdd` | 🔴 Yes | — | ⚠️ | Hardcoded "N" in backend. Not asked from user. |
| 3.21 | `AlternateAddress.*` (entire block) | Optional | — | ❌ | Entire alternate address section missing. Not collected. |
| 3.22 | `DOB` | 🔴 Yes | `dob` | ✅ | From client master; backend validates YYYY-MM-DD, max 2026-03-31 |
| 3.23 | `EmployerCategory` | 🔴 Yes | `employerCategory` | ⚠️ | **Dropdown exists but INCOMPLETE.** Frontend has CGOV, SGOV, PSU, PE, PESG, PEPS, PEO, OTH, NA (9 values) — Wait, subagent reports 9 values present. Let me verify: ✅ Actually present with all 9. |
| 3.24 | `AadhaarCardNo` | Optional | `aadhaar` | ⚠️ | Collected but only format check `[0-9]{12}` — no UIDAI checksum validation |

### 3E. Additional fields in PersonalInfo tab NOT in schema

| # | Frontend Variable | Label | Schema equivalent |
|---|---|---|---|
| — | `gender` | Gender (M/F/T) | Not in PersonalInfo directly; may be used for title/prefix |
| — | `fatherName` | Father's Name | Not directly in ITR-1; may go in AssesseeRep or be metadata |
| — | `maritalStatus` | Marital Status | Not in ITR-1 schema; used for ITR eligibility |
| — | `nationality` | Nationality | Not a separate ITR-1 field; used for residential status logic |
| — | `telephone` | Telephone (STD-Number) | Not in ITR-1 schema |

**Section Status: ⚠️ 7 gaps — StateCode/CountryCode no enum validation, PinCode no regex, CountryCodeMobile hardcoded, secondary contact missing, AlternateAddress missing, no email validation.**

---

## 4. FilingStatus (Mandatory)

| # | Schema Field | Mandatory | Frontend Variable | Status | Notes |
|---|---|---|---|---|---|
| 4.1 | `ReturnFileSec` | 🔴 Yes | `filingSection` | ✅ | Dropdown: 139(1)/139(4)/139(5)/119(2)(b) |
| 4.2 | `OptOutNewTaxRegime` | 🔴 Yes | `regime` | ✅ | "Y" for new, "N" for old — correctly derived |
| 4.3 | `SeventhProvisio139` | Optional | — | ❌ | High-value spending trigger flag NOT collected |
| 4.4 | `IncrExpAggAmt2LkTrvFrgnCntryFlg` | Optional | — | ❌ | Foreign travel > ₹2L flag NOT collected |
| 4.5 | `AmtSeventhProvisio139ii` | Optional | — | ❌ | Foreign travel amount NOT collected |
| 4.6 | `IncrExpAggAmt1LkElctrctyPrYrFlg` | Optional | — | ❌ | Electricity > ₹1L flag NOT collected |
| 4.7 | `AmtSeventhProvisio139iii` | Optional | — | ❌ | Electricity amount NOT collected |
| 4.8 | `clauseiv7provisio139i` | Optional | — | ❌ | TDS/TCS ≥ ₹25K or bank deposits ≥ ₹50L flag NOT collected |
| 4.9 | `clauseiv7provisio139iDtls` (array) | Optional | — | ❌ | Mandatory filings trigger details array NOT collected |
| 4.10 | `ReceiptNo` | Optional (required for revised) | — | ❌ | 15-digit ack number for revised returns NOT collected |
| 4.11 | `NoticeNo` | Optional | — | ❌ | NOT collected |
| 4.12 | `OrigRetFiledDate` | Optional | — | ❌ | NOT collected |
| 4.13 | `NoticeDateUnderSec` | Optional | — | ❌ | NOT collected |
| 4.14 | `AsseseeRepFlg` | 🔴 Yes | — | ⚠️ | Hardcoded "N" in backend. Not asked from user. |
| 4.15 | `AssesseeRep.*` (entire block) | Conditional | — | ❌ | Representative details block missing |
| 4.16 | `ItrFilingDueDate` | 🔴 Yes | Implicit in AY | ✅ | Pattern `2026-07-31`, derived from AY |

**Section Status: ⚠️ 10 gaps — SeventhProvisio139 entire section missing, ReceiptNo/revised return fields missing, AssesseeRep missing.**

---

## 5. Salary Income (Schedule S equivalent)

### 5A. Gross Salary Components (Sec 17(1))

| # | Schema Field | Mandatory | Frontend Variable | Status | Notes |
|---|---|---|---|---|---|
| 5.1 | `GrossSalary` | 🔴 Yes | Computed by backend | ✅ | From employer entries or legacy fields |
| 5.2 | `Salary` | Optional | `employerEntries[].basic + da + bonus + commission + hra + lta + allowances` | ✅ | All components collected in EmployerEntryManager |
| 5.3 | `PerquisitesValue` | Optional | `employerEntries[].perquisites` | ✅ | Perquisites u/s 17(2) |
| 5.4 | `ProfitsInSalary` | Optional | `employerEntries[].profitsInLieu` | ✅ | Profits in Lieu u/s 17(3) |
| 5.5 | `AllwncExemptUs10.TotalAllwncExemptUs10` | 🔴 Yes | Computed by backend | ⚠️ | Backend computes from components but frontend doesn't show per-allowance breakdown |
| 5.6 | `AllwncExemptUs10.AllwncExemptUs10Dtls[]` (array) | Optional | — | ❌ | **NOT collected.** Schema expects per-allowance detail with 17 allowance codes. |
| 5.7 | `NetSalary` | 🔴 Yes | Computed by backend | ✅ | |
| 5.8 | `DeductionUs16` | 🔴 Yes | Computed by backend | ✅ | |
| 5.9 | `DeductionUs16ia` (Standard Deduction) | Optional | Computed by backend | ✅ | ₹50K old / ₹75K new |
| 5.10 | `EntertainmentAlw16ii` | Optional | `employerEntries[].entertainmentAllowance` | ✅ | Collected, max ₹5,000 |
| 5.11 | `ProfessionalTaxUs16iii` | Optional | `employerEntries[].professionalTax` | ✅ | Collected, max ₹5,000 |
| 5.12 | `IncomeFromSal` | 🔴 Yes | Computed by backend | ✅ | |

### 5B. HRA Exemption (Schedule EA10_13A)

| # | Schema Field | Mandatory | Frontend Variable | Status | Notes |
|---|---|---|---|---|---|
| 5.13 | `Placeofwork` | 🔴 Yes | `employerEntries[].isMetroCity` | ✅ | Maps to "1" (metro) or "2" (non-metro) |
| 5.14 | `ActlHRARecv` | 🔴 Yes | `employerEntries[].hra` | ✅ | |
| 5.15 | `ActlRentPaid` | 🔴 Yes | `employerEntries[].rentPaid` | ✅ | |
| 5.16 | `DtlsSalUsSec171` | 🔴 Yes | — | ❌ | **NOT collected.** Salary details under section 17(1) for HRA computation — should be basic + DA |
| 5.17 | `BasicSalary` | 🔴 Yes | `employerEntries[].basic` | ⚠️ | Collected but not explicitly linked to HRA form; backend must extract this |
| 5.18 | `DearnessAllwnc` | Optional | `employerEntries[].da` | ⚠️ | Collected but not explicitly linked to HRA form |
| 5.19 | `ActlRentPaid10Per` | 🔴 Yes | Computed by backend | ✅ | Backend computes |
| 5.20 | `Sal40Or50Per` | 🔴 Yes | Computed by backend | ✅ | Backend computes |
| 5.21 | `EligbleExmpAllwncUs13A` | 🔴 Yes | Computed by backend | ✅ | Backend computes |

### 5C. Salary TDS

| # | Schema Field | Mandatory | Frontend Variable | Status | Notes |
|---|---|---|---|---|---|
| 5.22 | `TotalTDSonSalaries` | 🔴 Yes (if present) | Computed by backend | ✅ | Sum of all employer TDS |
| 5.23 | `TDSonSalary[].EmployerOrDeductorOrCollectDetl.TAN` | 🔴 Yes (per entry) | `employerEntries[].employerTAN` | ✅ | Collected in EmployerEntryManager |
| 5.24 | `TDSonSalary[].EmployerOrDeductorOrCollectDetl.EmployerOrDeductorOrCollecterName` | 🔴 Yes (per entry) | `employerEntries[].employerName` | ✅ | Collected |
| 5.25 | `TDSonSalary[].IncChrgSal` | 🔴 Yes (per entry) | Computed by backend | ✅ | Backend populates |
| 5.26 | `TDSonSalary[].TotalTDSSal` | 🔴 Yes (per entry) | `employerEntries[].tdsDeducted` | ✅ | Collected |

**Section Status: ⚠️ 2 gaps — AllwncExemptUs10Dtls[] array missing, DtlsSalUsSec171 not explicitly collected for HRA.**

---

## 6. House Property (Schedule HP)

### 6A. Property Header

| # | Schema Field | Mandatory | Frontend Variable | Status | Notes |
|---|---|---|---|---|---|
| 6.1 | `PropertyDetails[]` (array, max 2) | Optional | `housePropertyEntries[]` | ⚠️ | Array exists but maxItems=1 for ITR-1 frontend; schema allows 2 |
| 6.2 | `PropertyDetails[].HPSNo` | 🔴 Yes (per item) | `housePropertyEntries[].propertySequenceNo` | ⚠️ | **Interface field exists** but NOT rendered as input. Auto-numbered but not user-editable. |
| 6.3 | `PropertyDetails[].AddressDetailWithZipCode` | 🔴 Yes (per item) | address fields in manager | ⚠️ | Address collected but NOT as a separate structured object with `AddrDetail`, `CityOrTownOrDistrict`, `StateCode`, `PinCode` sub-fields |
| 6.4 | `PropertyDetails[].PropertyOwner` | 🔴 Yes (per item) | `housePropertyEntries[].propertyOwnerType` | ⚠️ | **Interface field exists** (SE/MI/SP/OT) but NOT rendered as dropdown in the UI |
| 6.5 | `PropertyDetails[].PropertyOwnerOther` | Optional | — | ❌ | NOT collected |
| 6.6 | `PropertyDetails[].PropCoOwnedFlg` | 🔴 Yes | `housePropertyEntries[].isCoOwned` | ✅ | Collected as YES/NO dropdown |
| 6.7 | `PropertyDetails[].AsseseeShareProperty` | Optional | `housePropertyEntries[].ownershipShare` | ✅ | Collected as percentage |
| 6.8 | `PropertyDetails[].CoOwners[]` (array) | Optional | `housePropertyEntries[].coOwners[]` | ⚠️ | Array exists but only name/PAN/share collected. **Missing: aadhaar, coOwnerSNo** |
| 6.9 | `PropertyDetails[].ifLetOut` | 🔴 Yes | `housePropertyEntries[].propertyType` | ✅ | SELF_OCCUPIED/LET_OUT/DEEMED_LET_OUT maps to L/D/S |

### 6B. Rent Details

| # | Schema Field | Mandatory | Frontend Variable | Status | Notes |
|---|---|---|---|---|---|
| 6.10 | `PropertyDetails[].Rentdetails.AnnualLetableValue` | 🔴 Yes | `housePropertyEntries[].annualRent` | ✅ | Only shown for LET_OUT |
| 6.11 | `PropertyDetails[].Rentdetails.RentNotRealized` | Optional | `housePropertyEntries[].unrealizedRent` | ✅ | Collected |
| 6.12 | `PropertyDetails[].Rentdetails.LocalTaxes` | Optional | `housePropertyEntries[].municipalTaxesPaid` | ✅ | Collected |
| 6.13 | `PropertyDetails[].Rentdetails.TotalUnrealizedAndTax` | 🔴 Yes | Computed by backend | ✅ | |
| 6.14 | `PropertyDetails[].Rentdetails.BalanceALV` | 🔴 Yes | Computed by backend | ⚠️ | Backend computes; frontend doesn't show intermediate |
| 6.15 | `PropertyDetails[].Rentdetails.AnnualOfPropOwned` | 🔴 Yes | Computed by backend | ⚠️ | Backend computes; frontend doesn't show intermediate |
| 6.16 | `PropertyDetails[].Rentdetails.ThirtyPercentOfBalance` | 🔴 Yes | Computed by backend | ⚠️ | Backend computes; frontend doesn't show intermediate |
| 6.17 | `PropertyDetails[].Rentdetails.IntOnBorwCap` | 🔴 Yes | `housePropertyEntries[].interestOnLoan` | ✅ | |
| 6.18 | `PropertyDetails[].Rentdetails.Section24B` (array) | Optional | `housePropertyEntries[].homeLoans[]` | ⚠️ | **Interface field exists** but NOT rendered. Should be per-loan detail array with lender PAN, loan account, date. |
| 6.19 | `PropertyDetails[].Rentdetails.TotalDeduct` | 🔴 Yes | Computed by backend | ✅ | |
| 6.20 | `PropertyDetails[].Rentdetails.ArrearsUnrealizedRentRcvd` | Optional | `housePropertyEntries[].arrearsOfRent` | ✅ | |
| 6.21 | `PropertyDetails[].Rentdetails.IncomeOfHP` | 🔴 Yes | Computed by backend | ✅ | Can be negative |

### 6C. Tenant Details

| # | Schema Field | Mandatory | Frontend Variable | Status | Notes |
|---|---|---|---|---|---|
| 6.22 | `PropertyDetails[].TenantDetails[]` (array) | Optional | tenant fields in manager | ⚠️ | Single tenant (name + PAN) collected but NOT as an array with full TenantPAN/TenantAadhaar |

**Section Status: ⚠️ 7 gaps — PropertyOwner dropdown not rendered, AddressDetailWithZipCode not structured, CoOwner aadhaar missing, Section24B homeLoans array not rendered, TenantDetails not a proper array, HPSNo not editable, intermediate rent computed fields not shown.**

---

## 7. Other Sources (Schedule OS)

### 7A. Interest Income (ITD Tags 17A-17H)

| # | Schema Field | Mandatory | Frontend Variable | Status | Notes |
|---|---|---|---|---|---|
| 7.1 | `IntrstFrmSavingBank` (17A) | Optional | `interestEntries[]` where accountType=SAVINGS | ✅ | InterestEntryManager collects per-bank |
| 7.2 | `IntrstFrmTermDeposit` (17B) | Optional | `interestEntries[]` where accountType=FD | ✅ | Per-term-deposit entries |
| 7.3 | `IntrstFrmIncmTaxRefund` (17C) | Optional | `incomeFromITRefund` (legacy) | ⚠️ | Collected as flat number; no per-refund detail with date/AY |
| 7.4 | `IntrstSec10XIFirstProviso` (17D) | Optional | `postOfficeInterest` (legacy) | ⚠️ | Flat amount; no per-account detail |
| 7.5 | `IntrstSec10XISecondProviso` (17E) | Optional | `nscInterest` (legacy) | ⚠️ | Flat amount; no per-certificate detail |
| 7.6 | `IntrstSec10XIIFirstProviso` (17F) | Optional | `scssInterest` (legacy) | ⚠️ | Flat amount; no per-account detail |
| 7.7 | `IntrstSec10XIISecondProviso` (17G) | Optional | `otherInterest` (legacy) | ⚠️ | Flat amount; no source detail |
| 7.8 | `IntrstFrmOthers` (17H) | Optional | Merged with above | ⚠️ | Not separately identified |

### 7B. Dividend Income

| # | Schema Field | Mandatory | Frontend Variable | Status | Notes |
|---|---|---|---|---|---|
| 7.9 | `DividendOthThan22e` | Optional | `dividendEntries[]` where section='194' | ✅ | DividendEntryManager collects per-company |
| 7.10 | `Dividend22e` | Optional | `dividendEntries[]` where section='10(22e)' | ✅ | EXEMPT — correctly handled |
| 7.11 | `Dividend22f` | Optional | `dividendEntries[]` where section='10(22f)' | ✅ | EXEMPT — correctly handled |

### 7C. Family Pension

| # | Schema Field | Mandatory | Frontend Variable | Status | Notes |
|---|---|---|---|---|---|
| 7.12 | `FamilyPension` | Optional | `familyPensionEntry.grossAmount` | ✅ | FamilyPensionManager collects |
| 7.13 | `DeductionUs57iia` | Optional | Computed by backend | ✅ | min(1/3rd, ₹15K old/₹25K new) |

### 7D. Winnings (Sec 115BB)

| # | Schema Field | Mandatory | Frontend Variable | Status | Notes |
|---|---|---|---|---|---|
| 7.14 | `WinningsLottery` | Optional | `winningsEntries[]` where type=LOTTERY | ✅ | WinningsManager collects per-type |
| 7.15 | `WinningsBetting` | Optional | `winningsEntries[]` where type=BETTING | ✅ | |
| 7.16 | `WinningsCardGame` | Optional | `winningsEntries[]` where type=CARD_GAME | ✅ | |
| 7.17 | `WinningsHorseRace` | Optional | `winningsEntries[]` where type=HORSE_RACE | ✅ | |

### 7E. Gifts (Sec 56(2)(x))

| # | Schema Field | Mandatory | Frontend Variable | Status | Notes |
|---|---|---|---|---|---|
| 7.18 | `ImmovpropWithoutCons562x` | Optional | `giftEntries[]` where propertyType=IMMOVABLE | ✅ | GiftPropertyManager collects |
| 7.19 | `AnyOtherPropWithoutCons562x` | Optional | `giftEntries[]` where propertyType=CASH/MOVABLE | ✅ | |

### 7F. Other Sources Fields

| # | Schema Field | Mandatory | Frontend Variable | Status | Notes |
|---|---|---|---|---|---|
| 7.20 | `OthersInc.OthersIncDtlsOthSrc[]` (array) | Optional | — | ❌ | **NOT collected.** Nature-of-income breakdown array with codes (SAV/IFD/TAX/FAP/DIV). Frontend collects flat amounts per category but not per-source detail. |
| 7.21 | `GrossTotIncome` | 🔴 Yes | Computed by backend | ✅ | |
| 7.22 | `GrossTotIncomeIncLTCG112A` | 🔴 Yes | Computed by backend | ✅ | |
| 7.23 | `TotalIncome` | 🔴 Yes | Computed by backend | ✅ | Max ₹51,25,000 for ITR-1 |

**Section Status: ⚠️ 7 gaps — Most interest categories collected as flat amounts not structured entries, OthersIncDtlsOthSrc array missing, IT refund interest lacks detail.**

---

## 8. Deductions (Chapter VI-A)

### 8A. Section 80C (CRITICAL)

| # | Schema Field | Mandatory | Frontend Variable | Status | Notes |
|---|---|---|---|---|---|
| 8.1 | `Section80C` | 🔴 Yes | Aggregated: `s80C_epf + s80C_ppf + s80C_elss + s80C_lic + s80C_home` | ⚠️ | Flat amounts per type collected |
| 8.2 | `Schedule80CDtls[]` (array) | 🔴 Yes (if claimed) | — | 🔴 **MISSING** | Per-investment detail array NOT collected. Schema requires: InvestmentType, InvestmentAmount, DateOfInvestment, InstitutionName, PAN, AccountNo. |

### 8B. Section 80CCC / 80CCD (NPS)

| # | Schema Field | Mandatory | Frontend Variable | Status | Notes |
|---|---|---|---|---|---|
| 8.3 | `Section80CCC` | 🔴 Yes | — | ❌ | Separate 80CCC not collected (merged into 80C) |
| 8.4 | `Section80CCDEmployeeOrSE` | 🔴 Yes | `s80CCD1B` | ⚠️ | 80CCD(1) vs 80CCD(1B) are different caps. Frontend only has 80CCD(1B). |
| 8.5 | `Section80CCD1B` | 🔴 Yes | `s80CCD1B` + `s80CCD1B_PRAN` | ⚠️ | PRAN collected but as single text field — schema expects `PRANDtls[]` array |
| 8.6 | `Section80CCDEmployer` | 🔴 Yes | `s80CCD2` + `employerEntries[].employerNPS` | ✅ | |
| 8.7 | `PRANDtls[]` (array) | Optional | — | ❌ | Per-PRAN detail array NOT collected |
| 8.8 | `PensionContributionFund[]` (array) | Optional | — | ❌ | Per-fund detail NOT collected |

### 8C. Section 80D (CRITICAL)

| # | Schema Field | Mandatory | Frontend Variable | Status | Notes |
|---|---|---|---|---|---|
| 8.9 | `Section80D` | 🔴 Yes | `s80D_self + s80D_parent` | ✅ | Aggregate collected |
| 8.10 | `Sec80DSelfFamSrCtznHealth.SeniorCitizenFlag` | 🔴 Yes | Derived from `age` | ⚠️ | Backend derives; frontend doesn't expose as checkbox |
| 8.11 | `Sec80DSelfFamSrCtznHealth.SelfAndFamily` | Optional | Computed by backend | ⚠️ | Not separately visible |
| 8.12 | `Sec80DSelfFamSrCtznHealth.HealthInsPremSlfFam` | Optional | `s80D_self` | ⚠️ | Flat amount — no per-policy detail |
| 8.13 | `Sec80DSelfFamSrCtznHealth.PrevHlthChckUpSlfFam` | Optional | — | ❌ | Preventive health checkup for self NOT separately collected |
| 8.14 | `Sec80DSelfFamSrCtznHealth.ParentsSeniorCitizenFlag` | 🔴 Yes | Derived from age | ⚠️ | Not explicitly collected |
| 8.15 | `Sec80DSelfFamSrCtznHealth.HealthInsPremParents` | Optional | `s80D_parent` | ⚠️ | Flat amount; no per-policy detail |
| 8.16 | `Sec80DSelfFamSrCtznHealth.PrevHlthChckUpParents` | Optional | — | ❌ | Preventive health checkup for parents NOT separately collected |
| 8.17 | `Sec80DSelfFamSrCtznHealth.MedicalExpSlfFamSrCtzn` | Optional | — | ❌ | Medical expense for non-insured seniors NOT collected |
| 8.18 | `Sec80DSelfFamSrCtznHealth.MedicalExpParentsSrCtzn` | Optional | — | ❌ | Medical expense for non-insured senior parents NOT collected |
| 8.19 | `Sch80DInsDtls[]` (4 sub-objects: self, self-senior, parents, parents-senior) | Optional | `s80D_selfInsurerName`, `s80D_selfPolicyNo`, `s80D_parentInsurerName`, `s80D_parentPolicyNo` | 🔴 **INCOMPLETE** | **CRITICAL:** Schema expects FULL per-policy arrays with: InsurerName, PolicyNo, PremiumAmount, PolicyType, DateOfCommencement. Frontend has single name/policy fields — NOT arrays. |

### 8D. Section 80DD (Optional)

| # | Schema Field | Mandatory | Frontend Variable | Status | Notes |
|---|---|---|---|---|---|
| 8.20 | `NatureOfDisability` | 🔴 Yes | — | ❌ | "1" or "2" NOT collected |
| 8.21 | `TypeOfDisability` | 🔴 Yes | `dd_severe` (legacy?!) | ⚠️ | Only severe flag — should be "1" or "2" |
| 8.22 | `DeductionAmount` | 🔴 Yes | Computed by backend | ✅ | ₹75K normal / ₹1.25L severe |
| 8.23 | `DependentType` | 🔴 Yes | — | ❌ | "1" through "7" dependent codes NOT collected |
| 8.24 | `DependentPan` | Optional | — | ❌ | NOT collected |
| 8.25 | `DependentAadhaar` | Optional | — | ❌ | NOT collected |
| 8.26 | `Form10IAAckNum` | Optional | — | ❌ | NOT collected |
| 8.27 | `UDIDNum` | Optional | — | ❌ | NOT collected |

### 8E. Section 80DDB (CRITICAL)

| # | Schema Field | Mandatory | Frontend Variable | Status | Notes |
|---|---|---|---|---|---|
| 8.28 | `Section80DDBUsrType` | 🔴 Yes | — | 🔴 **MISSING** | "1" (self/dependent) or "2" (senior). NOT collected. |
| 8.29 | `NameOfSpecDisease80DDB` | 🔴 Yes | — | 🔴 **MISSING** | 14 disease codes (a-n): Neurological, Cancer, AIDS, Chronic Renal Failure, Hemophilia, Thalassemia, etc. NOT collected. |
| 8.30 | `Section80DDB` | 🔴 Yes | Computed by backend | ⚠️ | Amount is collected but without the required fields above, it can't be correctly JSON'd |

### 8F. Section 80U (Optional)

| # | Schema Field | Mandatory | Frontend Variable | Status | Notes |
|---|---|---|---|---|---|
| 8.31 | `NatureOfDisability` | 🔴 Yes | — | ❌ | "1" or "2" NOT collected |
| 8.32 | `TypeOfDisability` | 🔴 Yes | `u_severe` (legacy?!) | ⚠️ | Only severe flag |
| 8.33 | `DeductionAmount` | 🔴 Yes | Computed by backend | ✅ | |
| 8.34 | `Form10IAAckNum` | Optional | — | ❌ | NOT collected |
| 8.35 | `UDIDNum` | Optional | — | ❌ | NOT collected |

### 8G. Section 80E/80EE/80EEA/80EEB (CRITICAL)

| # | Schema Field | Mandatory | Frontend Variable | Status | Notes |
|---|---|---|---|---|---|
| 8.36 | `Schedule80E.Schedule80EDtls[]` (per-loan array) | 🔴 Yes (if claimed) | — | 🔴 **MISSING** | Per-loan: bank name, loan account, sanction date, interest amount. Frontend only has flat `s80E` amount + `s80E_lenderName`. |
| 8.37 | `Schedule80E.TotalInterest80E` | 🔴 Yes | `s80E` | ⚠️ | Flat amount collected but no per-loan backing |
| 8.38 | `Schedule80EE.Schedule80EEDtls[]` (per-loan) | 🔴 Yes (if claimed) | — | 🔴 **MISSING** | NOT collected |
| 8.39 | `Schedule80EE.TotalInterest80EE` | 🔴 Yes | — | ❌ | 80EE not separately collected |
| 8.40 | `Schedule80EEA.PropStmpDtyVal` | 🔴 Yes | — | ❌ | Stamp duty value (max ₹45L) NOT collected |
| 8.41 | `Schedule80EEA.Schedule80EEADtls[]` (per-loan) | 🔴 Yes | — | 🔴 **MISSING** | NOT collected |
| 8.42 | `Schedule80EEB.Schedule80EEBDtls[]` (per-loan+vehicle) | 🔴 Yes | — | 🔴 **MISSING** | NOT collected |
| 8.43 | `Schedule80EEB.VehicleRegNo` | 🔴 Yes | — | ❌ | Vehicle registration NOT collected |

### 8H. Section 80G (CRITICAL)

| # | Schema Field | Mandatory | Frontend Variable | Status | Notes |
|---|---|---|---|---|---|
| 8.44 | `TotalDonationsUs80GCash` | 🔴 Yes | Computed by backend | ⚠️ | Backend must derive from donations array |
| 8.45 | `TotalDonationsUs80GOtherMode` | 🔴 Yes | Computed by backend | ⚠️ | Backend must derive from donations array |
| 8.46 | `TotalDonationsUs80G` | 🔴 Yes | Computed by backend | ✅ | Sum |
| 8.47 | `TotalEligibleDonationsUs80G` | 🔴 Yes | Computed by backend | ⚠️ | Must apply 50%/100% gating |
| 8.48 | `Don100Percent` (sub-object) | Optional | `donationEntries[]` where `eligiblePercentage=100` | ⚠️ | **Frontend collects per-donee entries** BUT doesn't separate into the 4 official categories (100% without approval, 50% without approval, 100% with approval, 50% with approval). Only has 100% vs 50% dropdown. |
| 8.49 | `Don50PercentNoApprReqd` | Optional | `donationEntries[]` where `eligiblePercentage=50` | ⚠️ | Same issue — no "approval required" distinction |
| 8.50 | `Don100PercentApprReqd` | Optional | Not separately collected | 🔴 **MISSING** | No "approval required" category |
| 8.51 | `Don50PercentApprReqd` | Optional | Not separately collected | 🔴 **MISSING** | No "approval required" category |
| 8.52 | `DoneeWithPan[]` (per category array) | Optional | `donationEntries[]` | ⚠️ | **FRONTEND HAS THIS** — per-donee entries with name, PAN, amount, date, mode. But: **Missing** donee address (AddrDetail, City, State, PinCode), donation date not mapped to schema field, cash vs other mode split not tracked per category level. |

### 8I. Section 80GG

| # | Schema Field | Mandatory | Frontend Variable | Status | Notes |
|---|---|---|---|---|---|
| 8.53 | `Section80GG` | 🔴 Yes | — | ❌ | NOT collected separately |
| 8.54 | `Form10BAAckNum` | 🔴 Yes (if claimed) | — | ❌ | Form 10BA acknowledgment number NOT collected |

### 8J. Section 80GGA (ITR-1 specific)

| # | Schema Field | Mandatory | Frontend Variable | Status | Notes |
|---|---|---|---|---|---|
| 8.55 | `TotalDonationAmtCash80GGA` | 🔴 Yes (if claimed) | — | ❌ | NOT collected |
| 8.56 | `TotalDonationAmtOtherMode80GGA` | 🔴 Yes (if claimed) | — | ❌ | NOT collected |
| 8.57 | `DonationDtlsSciRsrchRuralDev[]` (array) | Optional | — | ❌ | Per-donee with clause codes NOT collected |

### 8K. Section 80GGC

| # | Schema Field | Mandatory | Frontend Variable | Status | Notes |
|---|---|---|---|---|---|
| 8.58 | Entire 80GGC block | Optional | — | ❌ | NOT collected |

### 8L. Other Deductions

| # | Schema Field | Mandatory | Frontend Variable | Status | Notes |
|---|---|---|---|---|---|
| 8.59 | `Section80TTA` | 🔴 Yes | `s80TTA` | ✅ | Max ₹10K validated by backend |
| 8.60 | `Section80TTB` | 🔴 Yes | `s80TTB` | ✅ | Senior citizens only |
| 8.61 | `AnyOthSec80CCH` | 🔴 Yes | — | ❌ | Sukanya Samriddhi deduction not separately collected |
| 8.62 | `TotalChapVIADeductions` | 🔴 Yes | Computed by backend | ✅ | |

**Section Status: 🔴 18 CRITICAL gaps — Schedule80C details array, Schedule80D policy arrays, 80DDB user type + disease codes, 80DD/80U disability details, Schedule80E/80EE/80EEA/80EEB per-loan arrays, 80G 4-category split + donee address, Form10BA, 80GGA/80GGC, 80CCH.**

---

## 9. Exempt Income (Schedule EI equivalent)

| # | Schema Field | Mandatory | Frontend Variable | Status | Notes |
|---|---|---|---|---|---|
| 9.1 | `ExemptIncAgriOthUs10.ExemptIncAgriOthUs10Total` | 🔴 Yes | Computed by backend | ⚠️ | Only agricultural income collected; other exempt income from separate tab |
| 9.2 | `ExemptIncAgriOthUs10Dtls[].Category` | Optional | Implicit from field groupings | ❌ | Category codes (AGRI/GOVC/ISI/SSRA/SRSC/SRST/SRPC/OTH) NOT collected as structured array |
| 9.3 | `ExemptIncAgriOthUs10Dtls[].SubCategory` | Optional | — | ❌ | 37 sub-category codes NOT collected |
| 9.4 | `ExemptIncAgriOthUs10Dtls[].OthAmount` | 🔴 Yes | Scattered across `agricultureIncome`, `ppfInterest`, `sukanyaSamriddhiInterest`, etc. | ⚠️ | **Frontend has the fields** (`agricultureIncome`, `agricultureExpenses`, `ppfInterest`, `sukanyaSamriddhiInterest`, `otherExemptInterest`, `gratuityExempt`, `leaveEncashmentExempt`, etc.) but they are NOT structured as the `ExemptIncAgriOthUs10Dtls[]` array the schema expects. |

**Status: ⚠️ Fields exist but scattered across tabs instead of structured as the official `ExemptIncAgriOthUs10Dtls[]` array with Category/SubCategory/Amount tuples.**

---

## 10. Tax Payments (Schedule IT + TDS)

### 10A. TDS (Tax Deducted at Source)

| # | Schema Field | Mandatory | Frontend Variable | Status | Notes |
|---|---|---|---|---|---|
| 10.1 | `TDSonSalary[]` (per-employer TAN) | Conditional | Derived from `employerEntries[]` | ✅ | Backend maps to TAN-entry format |
| 10.2 | `TDSonOthThanSals[]` | Conditional | `tdsEntries[]` | ⚠️ | **Array EXISTS** with 12 fields per entry. BUT: `TDSSection` in schema has 59 enum values — frontend has dropdown but may not have all. Deductor details collected but `EmployerOrDeductorOrCollectDetl` structured object (with TAN, Name sub-fields) not generated by frontend — backend must build this. |

### 10B. Advance Tax & Self-Assessment Tax (CRITICAL)

| # | Schema Field | Mandatory | Frontend Variable | Status | Notes |
|---|---|---|---|---|---|
| 10.3 | `TaxPayment[].BSRCode` | 🔴 Yes (per entry) | `selfAssessmentTaxEntries[].bsrCode` | ⚠️ | SAT entries have BSR code. But ADVANCE TAX entries are legacy flat amounts (`adv15Jun`, `adv15Sep`, `adv15Dec`, `adv15Mar`) with NO BSR code, date, or challan serial. |
| 10.4 | `TaxPayment[].DateDep` | 🔴 Yes (per entry) | `selfAssessmentTaxEntries[].depositDate` | ⚠️ | Same — only SAT entries have dates. Advance tax entries DON'T. |
| 10.5 | `TaxPayment[].SrlNoOfChaln` | 🔴 Yes (per entry) | `selfAssessmentTaxEntries[].challanNo` | ⚠️ | Same — only SAT entries. Advance tax NO challan numbers. |
| 10.6 | `TaxPayment[].Amt` | 🔴 Yes (per entry) | `selfAssessmentTaxEntries[].amount` / `adv15Jun` etc. | ⚠️ | Amounts exist but advance tax lacks per-challan detail |
| 10.7 | `TotalTaxPayments` | 🔴 Yes (if present) | Computed by backend | ✅ | |

**CRITICAL: Advance tax entries (`adv15Jun`, `adv15Sep`, `adv15Dec`, `adv15Mar`) are collected as flat amounts WITHOUT BSR code, deposit date, and challan serial number. The official schema requires per-challan detail. The SAT entries (`selfAssessmentTaxEntries[]`) DO have all required fields.**

---

## 11. Bank Account Details (Refund)

| # | Schema Field | Mandatory | Frontend Variable | Status | Notes |
|---|---|---|---|---|---|
| 11.1 | `BankAccountDtls.AddtnlBankDetails[]` | 🔴 Yes | `bankAccountDetails[]` | ⚠️ | Array exists with `bankName`, `accountNumber`, `ifscCode`, `accountType` |
| 11.2 | `BankAccountDtls.AddtnlBankDetails[].AccountType` | 🔴 Yes | `bankAccountDetails[].accountType` | ⚠️ | Frontend has SAVINGS/CURRENT dropdown. Schema expects 6 values: SB/CA/CC/OD/NRO/OTH |
| 11.3 | `BankAccountDtls.AddtnlBankDetails[].UseForRefund` | 🔴 Yes | — | 🔴 **MISSING** | "true"/"false" flag NOT collected. Schema requires at least one account marked as refund account. |

**Status: 🔴 1 CRITICAL — UseForRefund missing. AccountType enum incomplete (2 vs 6 values).**

---

## 12. Verification (Mandatory)

| # | Schema Field | Mandatory | Frontend Variable | Status | Notes |
|---|---|---|---|---|---|
| 12.1 | `Verification.AssesseeVerName` | 🔴 Yes | `name` | ✅ | From form data |
| 12.2 | `Verification.AssesseeVerPAN` | 🔴 Yes | `pan` | ✅ | |
| 12.3 | `Verification.Capacity` | 🔴 Yes | Hardcoded | ⚠️ | Should be S(Self)/R(Rep)/K(Karta)/A(Attorney). Not collected. |
| 12.4 | `Verification.Place` | 🔴 Yes | Hardcoded | ⚠️ | Default to city from address |
| 12.5 | `Verification.Date` | 🔴 Yes | Generated at submission | ✅ | |

---

## 13. TaxReturnPreparer (Optional)

| # | Schema Field | Mandatory | Frontend Variable | Status | Notes |
|---|---|---|---|---|---|
| 13.1 | Entire TRP block (8+ fields) | Optional | — | ❌ | NOT collected. Includes TRP name, PAN, membership no, date, place. |

---

# PART 2: ITR-2 — FIELD-BY-FIELD CROSS-REFERENCE

> **Note:** ITR-2 frontend pages do NOT exist yet as dedicated pages. The `ITRComputationPage.tsx` auto-detects ITR form type and adjusts tabs. The Pydantic schemas in `app/schemas/itr2.py` exist. Frontend support is limited to what ITR-1 already covers plus CG transaction entries.

---

## ITR-2 Unique Sections — Frontend Status

| # | Schema Section | Description | Mandatory | Frontend Status | Gaps |
|---|---|---|---|---|---|
| 2.1 | **ScheduleCGFor23** | Full Capital Gains (STCG + LTCG with indexation, 54/54B/54EC/54F/54G/54GA deductions) | Optional | ⚠️ | `CapitalGainsEntryManager` collects 8 fields per transaction. **MISSING:** IndexedCostOfAcq, IndexedCostOfImp, 54-series deduction trackers (54, 54EC, 54F — only 3 of 6 in dropdown), CurrYrLosses (42+ tracking fields), AccruOrRecOfCG (quarterly Q1-Q4), DeducClaimInfo. CostInflationIndex NOT collected. |
| 2.2 | **Schedule112A** | Per-scrip LTCG on listed equity | Optional | ❌ | **NOT collected.** Requires per-scrip ISIN ([A-Z0-9]{12}), NameOfShareUnit, NumberOfSharesUnits, SaleValuePerShareUnit, CostAcqPerShareUnit, FMVPerShareUnit (grandfathered). Balance112A can be negative. |
| 2.3 | **Schedule115AD** | FII capital gains | Optional | ❌ | NOT collected |
| 2.4 | **ScheduleVDA** | Virtual Digital Assets (per-transaction) | Optional | ⚠️ | `vdaGains` collected as flat number. **MISSING:** DateofAcquisition, DateofTransfer, HeadUndIncTaxed enum, per-transaction array. |
| 2.5 | **ScheduleOS** | Other Sources (85+ fields) | Optional | ⚠️ | Covers what ITR-1 has plus: AmtNotDeductibleUs58, ProfitChargTaxUs59, BalanceNoRaceHorse, BalanceOwnRaceHorse, GrossIncChrgblTaxAtAppRate, InterestGross, NatofPassThrghIncome — **all missing** |
| 2.6 | **ScheduleCYLA** | Current Year Loss Adjustment (11 income heads × setoff types) | 🔴 Yes | ⚠️ | Frontend has `bfLossHP`, `bfLossBusiness`, `bfLossSTCG`, `bfLossLTCG`, `bfLossSpeculation` as flat amounts. **MISSING:** 11 income head breakdown, setoff type tracking per head. |
| 2.7 | **ScheduleBFLA** | Brought Forward Loss Adjustment (11 heads) | 🔴 Yes | ❌ | NOT collected — only flat B/F amounts |
| 2.8 | **ScheduleCFL** | Carry Forward Loss (8 AYs, 11 heads each) | Optional | ❌ | NOT collected |
| 2.9 | **ScheduleAMT** | Alternate Minimum Tax | Optional | ❌ | NOT collected |
| 2.10 | **ScheduleAMTC** | AMT Credit (13 AY array) | Optional | ❌ | NOT collected |
| 2.11 | **ScheduleSPI** | Clubbing of Income (per-person) | Optional | ❌ | NOT collected |
| 2.12 | **ScheduleSI** | Special Rate Income (68 codes × 12 rates) | Optional | ❌ | **NOT collected at all.** 68 section codes, 12 rate percentages. |
| 2.13 | **ScheduleEI** | Exempt Income (51 sub-categories) | Optional | ⚠️ | Basic exempt income fields exist. **MISSING:** 51 sub-category codes, ExcNetAgriIncDtls[] array, OthersIncDtls[] with sub-cat codes, IncNotChrgblAsPerDTAADtls[]. |
| 2.14 | **SchedulePTI** | Pass Through Income | Optional | ❌ | NOT collected |
| 2.15 | **ScheduleFSI** | Foreign Source Income (per country) | Optional | ❌ | **NOT collected.** CountryCode, TaxIdentificationNo, HeadOfIncome (11 heads), GrossAmount, TaxPaidOutsideIndia. |
| 2.16 | **ScheduleTR1** | DTAA Tax Relief (per country) | Optional | ❌ | **NOT collected.** CountryCode, TaxIdentificationNo, DTAAArticle, TaxPaidOutsideIndia, ReliefAvailable, ReliefClaimed. |
| 2.17 | **ScheduleFA** | Foreign Assets (10 sub-arrays) | Optional | ❌ | **NOT collected.** 10 sub-sections (A-J): ForeignBankAccounts, CustodialAccounts, EquityDebtInterest, CashValueInsurance, FinancialInterest, ImmovableProperty, OtherAssets, SigningAuthority, TrustOutsideIndia, OtherSourcesIncome. Each with 5-13 fields. |
| 2.18 | **Schedule5A2014** | Clubbing with spouse (pre-2014) | Optional | ❌ | NOT collected |
| 2.19 | **ScheduleAL** | Assets & Liabilities (>₹50L income trigger) | Optional | ❌ | **NOT collected.** Movable (8 categories), Immovable, Liabilities. |
| 2.20 | **ScheduleESOP** | ESOP deferred tax (6 AYs) | Optional | ❌ | **NOT collected.** 6 AYs (2021-2026), per-event arrays with allotment/exercise dates and FMV. |

**ITR-2 Summary: 15 of 24 unique sections are ❌ MISSING. Only ScheduleCGFor23 (partial), ScheduleOS (partial), ScheduleVDA (flat only), and the shared schedules (VIA, 80C, 80D, 80G, TDS) have any frontend coverage.**

---

# PART 3: ITR-3 — FIELD-BY-FIELD CROSS-REFERENCE

> **Note:** ITR-3 is the most complex form. No dedicated ITR-3 frontend pages exist. The `BusinessTab` in `ITRComputationTabs.tsx` has basic presumptive scheme fields. Pydantic schemas exist in `app/schemas/itr3.py`.

---

## ITR-3 Business-Specific Sections — Frontend Status

| # | Schema Section | Description | Mandatory | Frontend Status | Gaps |
|---|---|---|---|---|---|
| 3.1 | **PartA_GEN2** | Audit Info + Nature of Business | 🔴 Yes | ❌ | **NOT collected.** LiableSec44AAflg, LiableSec44ABflg, AuditAccountantFlg, TotalSalesExcOneCr, NatOfBus[] array with BusinessCode. |
| 3.2 | **PARTA_BS** | Balance Sheet (30+ fields) | 🔴 Yes | ❌ | **NOT collected.** FundSrc (PropFund, LoanFunds Secured/Unsecured), AppOfFunds (FixedAssets, NonCurrentInvst, CurrentAssets, CurrentLiabilities, NetCurrentAssets). All integers. |
| 3.3 | **PARTA_PL** | Profit & Loss (40+ fields) | 🔴 Yes | ❌ | **NOT collected.** CreditsToPL (24 income heads), DebitsToPL (23 expense heads: Freight, PowerFuel, RentRatesTaxes, Repairs, Insurance, Travel, Advertisement, BadDebts, InterestPaid, Depreciation, DirectorsRemuneration, EmployeesRemuneration, AuditorsRemuneration, LegalExpenses, etc.) |
| 3.4 | **ITR3ScheduleBP** | PGBP Full Computation | 🔴 Yes | ⚠️ | Only basic presumptive fields: `bizPresumptive` (44AD/44ADA/Regular), `bizTurnover`, `bizDeclared`, `bpNetProfit`. **MISSING:** 25+ sub-sections including NetPLFromSpecBus, netPLFromSpecifiedBus, 8 disallowance sections (40(a)(i), 40(a)(ia), 40A(2), 40A(3), 40(b), 43B, 36(1)(va), 14A), depreciation adjustments, ICDS adjustments, DeductionUs32_1_iii. |
| 3.5 | **ScheduleDPM** | Depreciation on P&M (4 rate blocks × 14 fields) | Optional | ❌ | **NOT collected.** 15%, 30%, 40%, 45% blocks with WDV, additions (>180 days / <180 days), full/half rate depreciation, additional depreciation, disallowance, proportionate depreciation, expenditure on transfer/sale, capital gain u/s 50. |
| 3.6 | **ScheduleDOA** | Depreciation on Other Assets (7 blocks × 14 fields) | Optional | ❌ | **NOT collected.** Land, Building (5%), Building (10%), Building (40%), Furniture (10%), Intangible (25%), Ships (20%). |
| 3.7 | **ScheduleDCG** | Deemed Capital Gains | Optional | ❌ | NOT collected |
| 3.8 | **ScheduleESR** | Scientific Research (35(1)(i)/(ii)/(iia)/(iii)/(iv), 35(2AA), 35(2AB)) | Optional | ❌ | NOT collected |
| 3.9 | **ITR3ScheduleUD** | Unabsorbed Depreciation per AY | Optional | ❌ | NOT collected |
| 3.10 | **ScheduleICDS** | ICDS I-X per-standard deviations | Optional | ❌ | NOT collected |
| 3.11 | **PARTA_QD** | Quantitative Details (3 arrays × 20 items) | Conditional (44AB) | ❌ | **NOT collected.** Trading items, Raw materials, Finished goods. Per-item: ItemName, UnitOfMeasure (23-value enum), OpeningStock, PurchaseQty, SaleQty, ClosingStock. |
| 3.12 | **ScheduleIF** | Partner in Firm | Optional | ❌ | **NOT collected.** Per-partner: FirmName, FirmPAN, IsLiableToAudit, ProfitSharePercent, ProfitShareAmt, IntrstAmtDueOrRecv, RemunernAmtDueOrRecv, FirmCapBalOn31Mar. |
| 3.13 | **ScheduleGST** | GST Turnover | Optional | ❌ | **NOT collected.** GSTIN array: GSTINNo (15-char regex), AmtTurnGrossRcptGSTIN. |
| 3.14 | **Schedule10AA** | SEZ Deduction | Optional | ❌ | NOT collected |
| 3.15 | **Schedule80_IA** | Infrastructure deduction | Optional | ❌ | NOT collected |
| 3.16 | **Schedule80_IB** | Industrial undertaking deduction | Optional | ❌ | NOT collected |
| 3.17 | **Schedule80_IC** | Special category states deduction | Optional | ❌ | NOT collected |
| 3.18 | **Schedule80RA** | Royalty/FTS deduction | Optional | ❌ | NOT collected |
| 3.19 | **ManufacturingAccount** | (15+ fields) | Optional | ❌ | NOT collected |
| 3.20 | **TradingAccount** | (15+ fields) | Optional | ❌ | NOT collected |
| 3.21 | **PARTA_OI** | Accounting Method + Stock Valuation | Optional | ❌ | NOT collected |

**ITR-3 Summary: 19 of 21 business-specific sections are ❌ MISSING. Only basic presumptive taxation fields exist in the BusinessTab. The full PGBP computation with depreciation, disallowances, balance sheet, P&L, quantitative details, and partnership schedules has NO frontend coverage.**

---

# PART 4: ITR-4 — FIELD-BY-FIELD CROSS-REFERENCE

ITR-4 shares most fields with ITR-1. The unique ITR-4 sections:

| # | Schema Section | Frontend Status | Notes |
|---|---|---|---|
| 4.1 | **ScheduleBP** (Presumptive Business) | ✅ | 44AD/44ADA correctly handled |
| 4.2 | **ScheduleBPFinancial** (18 fields: capital, creditors, assets) | ❌ | NOT collected |
| 4.3 | **PersonalInfo.Status** "I" vs "H" | ⚠️ | Hardcoded "I"; should reflect assessee type |
| 4.4 | **FilingStatus.NatureOfEmpl** | ❌ | NOT collected |
| 4.5 | **44AE Vehicle Details** | ⚠️ | AdvancedTaxPage has this but ITRComputationPage BusinessTab doesn't show vehicle-level detail |
| 4.6 | **ScheduleIT per-challan** | ⚠️ | Same advance tax issue as ITR-1 |

---

# PART 5: CROSS-CUTTING VALIDATION GAPS (ALL FORMS)

## 5A. Missing Regex Validations

| # | Validation | Schema Pattern | Frontend Status |
|---|---|---|---|
| V1 | PAN | `[A-Z]{5}[0-9]{4}[A-Z]` | ✅ Backend validates |
| V2 | Aadhaar | `[0-9]{12}` | ⚠️ Format check only; no Verhoeff checksum |
| V3 | TAN | `[A-Z]{4}[0-9]{5}[A-Z]` | ❌ No frontend validation on `employerTAN`, `deductorTAN` |
| V4 | IFSC | `[A-Z]{4}0[A-Z0-9]{6}` | ⚠️ `bankIFSC` collected but no format validation; `ifscCode` in BankInterest maxLength=11 only |
| V5 | ISIN | `[A-Z0-9]{12}` | ❌ No validation (only collected in dividend `isin` field) |
| V6 | GSTIN | `[a-zA-Z0-9]{15}` | ❌ No validation (ITR-3 not implemented) |
| V7 | Mobile | `[1-9][0-9]{9}` | ⚠️ Backend validates but no frontend format check |
| V8 | PIN Code | `[1-9][0-9]{5}` | ❌ No frontend validation |
| V9 | Email | Standard email regex | ❌ No frontend validation |
| V10 | BSR Code | `[0-9]{3}[0-9A-Z]{4}` | ❌ Collected in SAT entries but no format validation |
| V11 | SW ID | `SW[0-9]{8}` | ✅ Backend generates |
| V12 | Ack Number | `[0-9]{15}` | ❌ No validation on `ReceiptNo` (not even collected) |
| V13 | DPIIT Reg | `DIPP[0-9]{3,5}` | ❌ Not collected |
| V14 | TRP ID | `T[0-9]{9}\|[0-9]{6}` | ❌ Not collected |

## 5B. Missing Enum Validations (Dropdown vs Text Input)

| # | Enum Field | Required Values | Frontend Status |
|---|---|---|---|
| E1 | `StateCode` | 38 values (01-37 + 99) | ❌ Text input — no dropdown |
| E2 | `CountryCode` | ~240 ISO calling codes | ❌ Text input "India" |
| E3 | `EmployerCategory` | 9 values | ✅ Dropdown with all 9 values |
| E4 | `ReturnFileSec` | 8 values (11-20) | ⚠️ Frontend uses different labels: `139(1)`/`139(4)`/`139(5)`/`119(2)(b)` — should map to numeric codes |
| E5 | `AccountType` (Bank) | 6 values: SB/CA/CC/OD/NRO/OTH | ❌ Only SAVINGS/CURRENT |
| E6 | `ifLetOut` (Property) | 3 values: L/D/S | ✅ Maps correctly |
| E7 | `PropertyOwner` | 4 values: SE/MI/SP/OT | ❌ In interface but NOT rendered as dropdown |
| E8 | `LoanType` (Lender) | 3 values: B/I/L | ❌ Not collected |
| E9 | `Disease Code` (80DDB) | 14 values (a-n) | ❌ Not collected |
| E10 | `NatureOfDisability` (80DD/80U) | 2 values: 1/2 | ❌ Not collected as proper dropdown |
| E11 | `TypeOfDisability` (80DD/80U) | 2 values: 1/2 | ⚠️ Only severe checkbox |
| E12 | `DependentType` (80DD) | 8 values: 1-8 | ❌ Not collected |
| E13 | `TDSSection` | 59 values | ⚠️ TDS tab has dropdown with sections but completeness not verified |
| E14 | `SecCode` (ScheduleSI) | 68 values | ❌ Not collected |
| E15 | `SplRatePercent` | 12 values | ❌ Not collected |
| E16 | `UnitOfMeasure` (QD) | 23 values (101-122 + 999) | ❌ Not collected |
| E17 | `NatureOfEntity` (FA) | 9 values (1-9) | ❌ Not collected |
| E18 | `AccountType` (FA) | 6 values (1-6) | ❌ Not collected |
| E19 | `Exempt Sub-Categories` | 51 values | ❌ Not collected as structured enum |
| E20 | `Donation Category` (80G) | 4 categories | ⚠️ Only 100%/50% — no "approval required" distinction |
| E21 | `Capacity` (Verification) | 4 values: S/R/K/A | ❌ Not collected; hardcoded |
| E22 | `Allowance Codes` | 17 values (10(5)-10(17)) | ❌ Not collected |
| E23 | `80GGA Clauses` | 8 values | ❌ Not collected |
| E24 | `DeductedYr` | 18 values (2025-2008) | ❌ Not collected |

## 5C. Regime-Specific Validation Gaps

| # | Validation Rule | Old Regime | New Regime | Frontend Status |
|---|---|---|---|---|
| R1 | Standard Deduction cap | ₹50,000 | ₹75,000 | ✅ Backend handles |
| R2 | Rebate 87A threshold | TI ≤ ₹5L / rebate ₹12,500 | TI ≤ ₹12L / rebate ₹60,000 | ✅ Backend computes correctly |
| R3 | 80C to 80U deduction visibility | All shown | Only 80CCD(2) + 80CCH | ✅ Tab filters by `regime` |
| R4 | Set-off & carry forward loss rules differ per regime | Allowed | Restricted | ⚠️ No frontend warning |
| R5 | 115BAC depreciation rates differ | Normal rates | 115BAC adjusted rates | ❌ Not surfaced in frontend (ITR-3) |

---

# PART 6: COMPLETE GAP SUMMARY BY SEVERITY

## 🔴 CRITICAL — JSON Will Be Rejected by ITD (12 items)

| # | Gap | Forms Affected | Frontend Root Cause |
|---|---|---|---|
| C1 | **Schedule80G 4-category breakdown** + DoneeWithPan arrays with donee address | ITR-1, ITR-2, ITR-4 | DonationEntryManager has per-donee entries but no 4-category split (100/50% × with/without approval). Missing donee address fields. |
| C2 | **Schedule80D per-policy arrays** (Sch80DInsDtls) — 4 categories × per-policy with insurer name, policy no, premium, date | ITR-1, ITR-2, ITR-3, ITR-4 | Only single insurer name + policy number per self/parent. NOT arrays. Missing premium amount per policy, policy type, commencement date. |
| C3 | **Schedule80E per-loan array** (bank, loan account, sanction date, interest) | ITR-1, ITR-2, ITR-3, ITR-4 | Only flat `s80E` + one `s80E_lenderName`. No loan detail array. |
| C4 | **Schedule80EE/80EEA/80EEB** — per-loan arrays + stamp duty value + vehicle reg | ITR-1, ITR-2 | NOT collected at all. |
| C5 | **Schedule80C per-investment array** (Schedule80CDtls) | ITR-1, ITR-2, ITR-4 | Flat amounts per type (EPF, PPF, ELSS, LIC, Home). No per-investment detail with institution, date, account. |
| C6 | **Bank AccountType full enum** (6 values: SB/CA/CC/OD/NRO/OTH) | All | Only SAVINGS/CURRENT dropdown. |
| C7 | **Bank UseForRefund** flag | All | NOT collected. Schema requires at least 1 account marked for refund. |
| C8 | **Advance Tax per-challan details** (BSR code, date, challan serial) | All | `adv15Jun/Sep/Dec/Mar` are flat amounts. No BSR/date/challan per installment. Self-assessment tax entries DO have these fields. |
| C9 | **Section80DDBUsrType** + 14 disease codes | ITR-1, ITR-2 | NOT collected. |
| C10 | **CountryCodeMobile hardcoded "91"** | All | Not collected from user. |
| C11 | **TDS deductor structured objects** (EmployerOrDeductorOrCollectDetl with TAN + Name sub-objects) | All | Backend must rebuild from flat fields. |
| C12 | **Address.CountryCode** as text input instead of dropdown | All | No enum validation — could submit invalid country code. |

## 🟠 HIGH — Functionally Critical (14 items)

| # | Gap | Forms Affected |
|---|---|---|
| H1 | **Schedule80DD disability details** — NatureOfDisability, TypeOfDisability, DependentType (8 values), DependentPan, DependentAadhaar, Form10IAAckNum, UDIDNum | ITR-1, ITR-2 |
| H2 | **Schedule80U disability details** — NatureOfDisability, TypeOfDisability, Form10IAAckNum, UDIDNum | ITR-1, ITR-2 |
| H3 | **ScheduleEA10_13A HRA** — DtlsSalUsSec171, BasicSalary explicitly for HRA, DearnessAllwnc | ITR-1, ITR-2, ITR-4 |
| H4 | **Form10BAAckNum** for 80GG | ITR-1, ITR-2, ITR-4 |
| H5 | **Schedule80GGA** — Scientific Research/Rural Development donations with per-donee + clause codes | ITR-1 |
| H6 | **Schedule80GGC** — Political/other donations | ITR-1, ITR-2, ITR-3, ITR-4 |
| H7 | **AllwncExemptUs10Dtls[]** — Exempt allowance breakdown array with 17 allowance codes | ITR-1, ITR-2, ITR-3, ITR-4 |
| H8 | **PropertyDetails.AddressDetailWithZipCode** — Structured property address (not single text field) | ITR-1, ITR-2, ITR-4 |
| H9 | **PropertyDetails.PropertyOwner** — SE/MI/SP/OT dropdown NOT rendered | ITR-1, ITR-2, ITR-4 |
| H10 | **PropertyDetails.Section24B** — Per-loan detail array for home loans | ITR-1, ITR-2, ITR-4 |
| H11 | **PropertyDetails.TenantDetails[]** — Array with TenantPAN, TenantAadhaar (single flat fields collected) | ITR-1, ITR-2, ITR-4 |
| H12 | **PRANDtls[]** + **PensionContributionFund[]** — NPS detail arrays | ITR-1, ITR-2 |
| H13 | **Verification.Capacity** — S/R/K/A not collected | All |
| H14 | **MedicalExpSlfFamSrCtzn** + **MedicalExpParentsSrCtzn** — Medical expenses for non-insured senior parents | ITR-1, ITR-2, ITR-4 |

## 🟡 MEDIUM — Optional but Recommended (16 items)

| # | Gap | Forms Affected |
|---|---|---|
| M1 | **AlternateAddress** — Entire block missing | All |
| M2 | **Secondary mobile/email** (CountryCodeMobileNoSec, MobileNoSec, EmailAddressSec) | All |
| M3 | **SeventhProvisio139** — All 6 fields (mandatory filing triggers) | ITR-1, ITR-4 |
| M4 | **ReceiptNo** / **OrigRetFiledDate** — Revised return fields | All |
| M5 | **AssesseeRep** — Entire representative details block | All |
| M6 | **OthersIncDtlsOthSrc[]** — Nature-of-income breakdown with codes | ITR-1, ITR-2, ITR-4 |
| M7 | **ExemptIncAgriOthUs10Dtls[]** — Structured exempt income array with Category/SubCategory codes | All |
| M8 | **StateCode** dropdown — 38 values (currently text input) | All |
| M9 | **CountryCode** dropdown — ~240 values (currently text input "India") | All |
| M10 | **PinCode regex** validation `[1-9][0-9]{5}` | All |
| M11 | **Email regex** validation | All |
| M12 | **TAN format** validation on frontend | All |
| M13 | **Section80CCH** (Sukanya) — Not separately collected | ITR-1, ITR-2, ITR-4 |
| M14 | **Section80CCC** — Not separately collected (merged into 80C) | ITR-1, ITR-2, ITR-4 |
| M15 | **Section80CCD(1)** (employee NPS) — Only 80CCD(1B) collected | ITR-1, ITR-2, ITR-4 |
| M16 | **Preventive health checkup** (PrevHlthChckUpSlfFam + PrevHlthChckUpParents) — Not separately collected | ITR-1, ITR-2, ITR-4 |

## 🔵 NICE-TO-HAVE (4 items)

| # | Gap | Forms Affected |
|---|---|---|
| N1 | **TaxReturnPreparer** — 8+ fields (TRP name, PAN, membership, date, place) | All |
| N2 | **Address.ZipCode** | All |
| N3 | **Address.ResidenceName / RoadOrStreet** already collected but not mapped to schema sub-fields | ITR-1, ITR-2, ITR-4 |
| N4 | **IT Refund Interest** — Per-refund detail (date, AY) vs flat amount | ITR-1, ITR-2 |

---

# PART 7: IMPLEMENTATION PLAN

## Phase 1 — ITR-1/ITR-4 CRITICAL FIXES (Must ship before ITD submission)

### Step 1.1: Schedule80G Full Implementation
- **Current:** `DonationEntryManager` has per-donee entries (name, PAN, amount, date, mode, percentage).
- **Need:**
  1. Add 4-category dropdown: "100% Without Approval" / "50% Without Approval" / "100% With Approval" / "50% With Approval"
  2. Add donee address fields: AddrDetail, City, State, PinCode per entry
  3. Track cash vs other mode at category level
  4. Add eligible amount per donee (currently computed as `amount × percentage`)

### Step 1.2: Schedule80D Policy Arrays
- **Current:** Single insurer name + policy no per self/parent.
- **Need:**
  1. Convert to per-policy array (`Sch80DInsDtls[]`) for each of 4 categories
  2. Per policy: InsurerName, PolicyNo, PremiumAmount, PolicyType, DateOfCommencement
  3. Add `MedicalExpSlfFamSrCtzn` and `MedicalExpParentsSrCtzn` inputs
  4. Add `PrevHlthChckUpSlfFam` and `PrevHlthChckUpParents` inputs
  5. Add senior citizen flag checkboxes per category

### Step 1.3: Schedule80E/80EE/80EEA/80EEB Detail Arrays
- **Current:** Flat `s80E` + `s80E_lenderName`.
- **Need:**
  1. Create per-loan detail component with: LenderName, LenderPAN, LoanAccountNo, LoanSanctionDate, InterestAmount
  2. Add 80EE: per-loan + first-time home buyer eligibility
  3. Add 80EEA: stamp duty value (max ₹45L) + per-loan detail
  4. Add 80EEB: per-loan + vehicle registration number

### Step 1.4: Schedule80C Investment Detail Array
- **Current:** Flat amounts per type.
- **Need:**
  1. Create per-investment array: InvestmentType (dropdown: LIC, PPF, EPF, ELSS, NSC, HomeLoan, Tuition, FD, etc.), InvestmentAmount, DateOfInvestment, InstitutionName, InstitutionPAN, AccountNo/PolicyNo

### Step 1.5: Bank Account Fixes
- Add `UseForRefund` checkbox per bank account
- Expand `AccountType` dropdown from 2 values to 6: SB/CA/CC/OD/NRO/OTH

### Step 1.6: Advance Tax Per-Challan Detail
- Convert `adv15Jun/Sep/Dec/Mar` from flat amounts to array-based entries
- Add BSR Code, Deposit Date, Challan Serial No per entry
- Reuse `selfAssessmentTaxEntries[]` pattern

### Step 1.7: Critical Schema Field Additions
- Add `Section80DDBUsrType` dropdown (1=Self/Dependent, 2=Senior)
- Add `NameOfSpecDisease80DDB` dropdown (14 disease codes)
- Add `CountryCodeMobile` input (default "91")
- Add `StateCode` dropdown with 38 values
- Add `CountryCode` dropdown with ~240 values

### Step 1.8: Schedule80DD/80U Disability Details
- Add `NatureOfDisability` dropdown (1=Normal, 2=Severe)
- Add `TypeOfDisability` dropdown
- Add `DependentType` dropdown (1-7) for 80DD
- Add `DependentPan`, `DependentAadhaar`, `Form10IAAckNum`, `UDIDNum` fields

## Phase 2 — ITR-2 New Frontend Build (4-6 weeks)

### Step 2.1: Full ScheduleCGFor23 Page
- STCG section: SaleofLandBuild with FullValConsid, CostOfAcquisition, CostOfImprov, ExpOnTranfer, Balance
- LTCG section WITH INDEXATION: CostOfAcquisition, IndexedCostOfAcq, CostOfImprov, IndexedCostOfImp
- CII (Cost Inflation Index) table lookup
- 6 deduction trackers: 54, 54B, 54EC, 54F, 54G, 54GA — each with per-transaction Dtls[] array
- CurrYrLosses: 6 CG sub-types × setoff types
- AccruOrRecOfCG: quarterly Q1-Q4

### Step 2.2: Schedule112A Per-Scrip Page
- Per-scrip table: ISIN Code, Name of Share/Unit, Number of Shares, Sale Value per Share, Cost Acquisition per Share, FMV per Share (grandfathered)
- Balance112A can be negative

### Step 2.3: ScheduleFA Foreign Assets (10 Pages)
- A: Foreign Bank Accounts (7+ fields including peak balance, closing balance)
- B: Custodial Accounts
- C: Equity/Debt Interests (NatureOfEntity dropdown 1-9, investment value)
- D: Cash Value Insurance
- E: Other Financial Interests
- F: Immovable Property
- G: Other Capital Assets
- H: Signing Authority Accounts
- I: Trust Outside India
- J: Other Income Sources

### Step 2.4: ScheduleSI Special Rate Income
- 68 Section Code dropdown × 12 Rate Percentage
- SplRateInc field per entry

### Step 2.5: ScheduleEI Full Exempt Income
- 51 sub-category codes with structured arrays
- ExcNetAgriIncDtls[] with nature of agricultural activity

### Step 2.6: ScheduleFSI + ScheduleTR1
- Per-country foreign income (11 heads) + tax paid
- DTAA article + relief available/claimed

### Step 2.7: ScheduleSPI (Clubbing), ScheduleAL (Assets), ScheduleESOP (6 AY)
- Clubbing per person
- Assets & liabilities with 8 movable categories + immovable
- 6 AY ESOP deferred tax with per-event arrays

## Phase 3 — ITR-3 Business Sections (6-8 weeks)

### Step 3.1: PartA_GEN2 — Audit Info
- 44AA/44AB/92E audit flags
- TotalSalesExcOneCr dropdown
- NatureOfBusiness array (BusinessCode dropdown)

### Step 3.2: PARTA_BS — Balance Sheet
- 30+ fields: Proprietor's Capital, Reserves & Surplus, Secured/Unsecured Loans, Fixed Assets, Investments, Current Assets (Inventories, Sundry Debtors, Cash), Current Liabilities

### Step 3.3: PARTA_PL — Profit & Loss
- 40+ fields: Gross Profit, Other Income (13 sub-fields), Debits (24 expense heads)

### Step 3.4: ITR3ScheduleBP — Full PGBP
- Net profit from P&L
- Income credited to P&L but not taxable (disallowance)
- Income not in P&L but taxable
- 8 disallowance sections with per-item detail arrays
- Depreciation adjustments (books vs IT Act)
- ICDS adjustments

### Step 3.5: ScheduleDPM + ScheduleDOA — Depreciation
- 4 P&M blocks (15%, 30%, 40%, 45%) × 14 fields each
- 7 Other Asset blocks × 14 fields each
- WDV, additions >180 days, additions <180 days, full rate dep, half rate dep, additional dep, disallowance u/s 38(2)

### Step 3.6: Manufacturing + Trading Accounts
- 30+ fields total (raw material, WIP, direct/indirect expenses, sales, services)

### Step 3.7: PARTA_QD — Quantitative Details
- 3 arrays × 20 items: Trading, Raw Materials, Finished Goods
- 23-value UnitOfMeasure dropdown per item

### Step 3.8: ScheduleIF — Partnership
- Per-partner: Firm name, Firm PAN, audit flag, profit share %, amounts

---

# APPENDIX A: WHAT'S ALREADY CORRECT (Do NOT Touch)

These frontend areas are properly implemented:

1. ✅ **All computation fields** — IncomeDeductions, TaxComputation, TaxPaid, Refund, Verification — computed by backend engine
2. ✅ **New vs old regime deduction gating** — frontend correctly hides/shows deductions per regime
3. ✅ **ITR form auto-detection** — correct eligibility checks (agri > ₹5K, 112A > ₹1.25L, GTI > ₹50L, director/unlisted shares)
4. ✅ **EmployerEntryManager** — 42 fields covering full Sec 17(1)/(2)/(3), HRA, LTA, retirement benefits, 10(14) allowances, 16 deductions, TDS
5. ✅ **HousePropertyEntryManager** — 31 rendered fields covering property type, address, rental details, loan details, co-owners
6. ✅ **CapitalGainsEntryManager** — 8 editable + 14 computed fields per transaction with backend calculation
7. ✅ **InterestEntryManager / DividendEntryManager / WinningsManager / GiftPropertyManager / FamilyPensionManager** — per-source detail arrays
8. ✅ **26AS/AIS/TIS import pipeline** with auto-population and reconciliation
9. ✅ **Multi-entry TDS array** with 12 fields per entry + 60+ section dropdown
10. ✅ **Self-assessment tax entries** with BSR, challan, date, CIN
11. ✅ **Bank account details array** with name, account, IFSC (missing UseForRefund and full AccountType enum)
12. ✅ **ITR-4 presumptive schemes** (44AD/44ADA/44AE)
13. ✅ **TaxComputationTab** — display-only tab correctly rendered from backend taxResult
14. ✅ **Backend calculation engine** — SalaryScheduleComputer, HousePropertyCalculator, CapitalGainsCalculator producing correct values

---

# APPENDIX B: FIELD COUNT SUMMARY

| Form | Official Schema Sections | Fields in Schema (est.) | Frontend Fields Collected | Missing Fields | % Complete |
|---|---|---|---|---|---|
| ITR-1 | 29 | ~350 | ~255 | ~95 | 73% |
| ITR-4 | 29+ | ~380 | ~270 | ~110 | 71% |
| ITR-2 | 46 | ~900 | ~70 (shared only) | ~830 | 8% |
| ITR-3 | 69 | ~1,400 | ~80 (shared only) | ~1,320 | 6% |

**ITR-2/ITR-3 note:** The counts for ITR-2/ITR-3 indicate fields collected through the shared ITR-1 infrastructure. The unique ITR-2 (ScheduleCGFor23 full, 112A, FA, SI, EI, AL, ESOP, etc.) and ITR-3 (PGBP, BS, PL, DPM, DOA, QD, IF, etc.) sections have NO frontend collection pages.

---

*End of Audit. Next step: Begin Phase 1 implementation.*
