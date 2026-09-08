# ITR-2 AY 2026-27 — Complete JSON Schema Field Catalog

> **Source:** `ITR-2_2026_Main_V1.1 (1).json` (14,421 lines)
> **Root:** `ITR.ITR2`

---

## Global Type Primitives

| Type | Definition |
|---|---|
| `nonEmptyString` | `string` with pattern: any string including whitespace |
| `nonZeroString` | `string` ending with a digit and containing at least one `[1-9]` |
| `endWithDigit` | `string` matching `.*[0-9]` |

---

## 1. CreationInfo
**JSON Path:** `ITR.ITR2.CreationInfo`
**Required:** ✅ Yes

| Field | Path | Type | Mandatory | Constraints |
|---|---|---|---|---|
| SWVersionNo | `CreationInfo.SWVersionNo` | string | ✅ | maxLength:10, minLength:1, default:`"1.0"` |
| SWCreatedBy | `CreationInfo.SWCreatedBy` | string | ✅ | pattern:`[S][W][0-9]{8}` |
| JSONCreatedBy | `CreationInfo.JSONCreatedBy` | string | ✅ | pattern:`[S][W][0-9]{8}` |
| JSONCreationDate | `CreationInfo.JSONCreationDate` | string | ✅ | pattern:YYYY-MM-DD, on/after 2026-04-01 |
| IntermediaryCity | `CreationInfo.IntermediaryCity` | string | ✅ | maxLength:25, minLength:1, default:`"Delhi"` |
| Digest | `CreationInfo.Digest` | string | ✅ | pattern:`"-"` or `.{44}` (44 chars or dash) |

---

## 2. Form_ITR2
**JSON Path:** `ITR.ITR2.Form_ITR2`
**Required:** ✅ Yes

| Field | Path | Type | Mandatory | Constraints |
|---|---|---|---|---|
| FormName | `Form_ITR2.FormName` | string | ✅ | pattern:`"ITR-2"` |
| Description | `Form_ITR2.Description` | string | ✅ | maxLength:100, minLength:1 |
| AssessmentYear | `Form_ITR2.AssessmentYear` | string | ✅ | pattern:`"2026"` |
| SchemaVer | `Form_ITR2.SchemaVer` | string | ✅ | pattern:`"Ver1.0"`, maxLength:10 |
| FormVer | `Form_ITR2.FormVer` | string | ✅ | pattern:`"Ver1.0"`, maxLength:10 |

---

## 3. PartA_GEN1 — Personal Information
**JSON Path:** `ITR.ITR2.PartA_GEN1`
**Required:** ✅ Yes

### 3a. PersonalInfo
**JSON Path:** `ITR.ITR2.PartA_GEN1.PersonalInfo`
**Required:** ✅ Yes

| Field | Path | Type | Mandatory | Constraints |
|---|---|---|---|---|
| AssesseeName | `PersonalInfo.AssesseeName` | object | ✅ | See AssesseeName sub-object |
| PAN | `PersonalInfo.PAN` | string | ✅ | pattern:`[A-Z]{5}[0-9]{4}[A-Z]` |
| Address | `PersonalInfo.Address` | object | ✅ | See Address sub-object |
| SecondaryAdd | `PersonalInfo.SecondaryAdd` | string (enum) | ✅ | `"Y"`, `"N"` |
| AlternateAddress | `PersonalInfo.AlternateAddress` | object | ❌ | See AlternateAddress sub-object |
| DOB | `PersonalInfo.DOB` | string | ✅ | pattern:YYYY-MM-DD, on/before 2026-03-31 |
| Status | `PersonalInfo.Status` | string (enum) | ✅ | `"I"` (Individual), `"H"` (HUF) |
| AadhaarCardNo | `PersonalInfo.AadhaarCardNo` | string | ❌ | pattern:`[0-9]{12}` |

### 3b. AssesseeName
**JSON Path:** `ITR.ITR2.PartA_GEN1.PersonalInfo.AssesseeName`
**Required:** ✅ Yes

| Field | Path | Type | Mandatory | Constraints |
|---|---|---|---|---|
| FirstName | `AssesseeName.FirstName` | string | ❌ | maxLength:25 |
| MiddleName | `AssesseeName.MiddleName` | string | ❌ | maxLength:25 |
| SurNameOrOrgName | `AssesseeName.SurNameOrOrgName` | string | ✅ | maxLength:75, minLength:1 |

### 3c. Address
**JSON Path:** `ITR.ITR2.PartA_GEN1.PersonalInfo.Address`
**Required:** ✅ Yes

| Field | Path | Type | Mandatory | Constraints |
|---|---|---|---|---|
| ResidenceNo | `Address.ResidenceNo` | string | ✅ | maxLength:50, minLength:1 |
| ResidenceName | `Address.ResidenceName` | string | ❌ | maxLength:50 |
| RoadOrStreet | `Address.RoadOrStreet` | string | ❌ | maxLength:50 |
| LocalityOrArea | `Address.LocalityOrArea` | string | ✅ | maxLength:50, minLength:1 |
| CityOrTownOrDistrict | `Address.CityOrTownOrDistrict` | string | ✅ | maxLength:50, minLength:1 |
| StateCode | `Address.StateCode` | string (enum) | ✅ | See StateCode enum below |
| CountryCode | `Address.CountryCode` | string (enum) | ✅ | See CountryCode enum (incl. `"91"` for India) |
| PinCode | `Address.PinCode` | integer | ❌ | range:100000–999999, pattern:`[1-9][0-9]{5}` |
| ZipCode | `Address.ZipCode` | string | ❌ | maxLength:8 |
| Phone (STDcode) | `Address.Phone.STDcode` | integer | ✅ | range:0–99999, default:0 |
| Phone (PhoneNo) | `Address.Phone.PhoneNo` | string | ✅ | pattern:`[0-9]{1,10}`, default:`"0"` |
| CountryCodeMobile | `Address.CountryCodeMobile` | integer | ✅ | pattern:`[0-9]{1,5}` |
| MobileNo | `Address.MobileNo` | integer | ✅ | pattern:`[1-9][0-9]{9}` or `[1-9][0-9]{4,9}` |
| CountryCodeMobileNoSec | `Address.CountryCodeMobileNoSec` | integer | ❌ | pattern:`[0-9]{1,5}` |
| MobileNoSec | `Address.MobileNoSec` | integer | ❌ | pattern:`[1-9][0-9]{9}` or `[1-9][0-9]{4,9}` |
| EmailAddress | `Address.EmailAddress` | string | ✅ | maxLength:125, minLength:1, email pattern |
| EmailAddressSec | `Address.EmailAddressSec` | string | ❌ | maxLength:125, email pattern |

### 3d. AlternateAddress
**JSON Path:** `ITR.ITR2.PartA_GEN1.PersonalInfo.AlternateAddress`

| Field | Path | Type | Mandatory | Constraints |
|---|---|---|---|---|
| ResidenceNo | `AlternateAddress.ResidenceNo` | string | ✅ | maxLength:50, minLength:1 |
| ResidenceName | `AlternateAddress.ResidenceName` | string | ❌ | maxLength:50 |
| RoadOrStreet | `AlternateAddress.RoadOrStreet` | string | ❌ | maxLength:50 |
| LocalityOrArea | `AlternateAddress.LocalityOrArea` | string | ✅ | maxLength:50, minLength:1 |
| CityOrTownOrDistrict | `AlternateAddress.CityOrTownOrDistrict` | string | ✅ | maxLength:50, minLength:1 |
| StateCode | `AlternateAddress.StateCode` | string (enum) | ✅ | State code list |
| CountryCode | `AlternateAddress.CountryCode` | string (enum) | ❌ | Country code list |
| PinCode | `AlternateAddress.PinCode` | integer | ❌ | 100000–999999 |
| ZipCode | `AlternateAddress.ZipCode` | string | ❌ | maxLength:8 |

### 3e. FilingStatus
**JSON Path:** `ITR.ITR2.PartA_GEN1.FilingStatus`
**Required:** ✅ Yes

| Field | Path | Type | Mandatory | Constraints |
|---|---|---|---|---|
| ReturnFileSec | `FilingStatus.ReturnFileSec` | integer (enum) | ✅ | `11`=139(1) due date, `12`=139(4) belated, `13`=142(1), `14`=148, `16`=153C, `17`=139(5) revised, `18`=139(9), `19`=92CD modified, `20`=119(2)(b) condonation; range:11–20, default:11 |
| OptOutNewTaxRegime | `FilingStatus.OptOutNewTaxRegime` | string | ✅ | pattern:`"Y"` or `"N"`, default:`"N"` |
| SeventhProvisio139 | `FilingStatus.SeventhProvisio139` | string | ✅ | pattern:`"Y"` or `"N"` |
| DepAmtAggAmtExcd1CrPrYrFlg | `FilingStatus.DepAmtAggAmtExcd1CrPrYrFlg` | string | ❌ | `"Y"`/`"N"` |
| AmtSeventhProvisio139i | `FilingStatus.AmtSeventhProvisio139i` | integer | ❌ | range:1,00,00,000–99,99,99,99,99,999 |
| IncrExpAggAmt2LkTrvFrgnCntryFlg | `FilingStatus.IncrExpAggAmt2LkTrvFrgnCntryFlg` | string | ❌ | `"Y"`/`"N"` |
| AmtSeventhProvisio139ii | `FilingStatus.AmtSeventhProvisio139ii` | integer | ❌ | range:2,00,000–99,99,99,99,99,999 |
| IncrExpAggAmt1LkElctrctyPrYrFlg | `FilingStatus.IncrExpAggAmt1LkElctrctyPrYrFlg` | string | ❌ | `"Y"`/`"N"` |
| AmtSeventhProvisio139iii | `FilingStatus.AmtSeventhProvisio139iii` | integer | ❌ | range:1,00,000–99,99,99,99,99,999 |
| clauseiv7provisio139i | `FilingStatus.clauseiv7provisio139i` | string | ❌ | `"Y"`/`"N"` |
| clauseiv7provisio139iDtls | `FilingStatus.clauseiv7provisio139iDtls` | array | ❌ | Array of clauseiv7provisio139iType |
| NoticeNo | `FilingStatus.NoticeNo` | string | ❌ | maxLength:100 |
| NoticeDate | `FilingStatus.NoticeDate` | string | ❌ | YYYY-MM-DD |
| ReceiptNo | `FilingStatus.ReceiptNo` | string | ❌ | pattern:`[0-9]{15}` |
| OrigRetFiledDate | `FilingStatus.OrigRetFiledDate` | string | ❌ | YYYY-MM-DD |
| ResidentialStatus | `FilingStatus.ResidentialStatus` | string (enum) | ✅ | `"RES"` (Resident), `"NRI"` (Non-Resident), `"NOR"` (Not Ordinarily Resident) |
| ConditionsResStatus | `FilingStatus.ConditionsResStatus` | string (enum) | ❌ | `"1"`–`"9"` |
| JurisdictionResPrevYr | `FilingStatus.JurisdictionResPrevYr` | object | ❌ | Contains array of JurisdictionResPrevYrDtls |
| TotalPrStayIndiaPrevYr | `FilingStatus.TotalPrStayIndiaPrevYr` | integer | ❌ | range:0–365 |
| TotalPrStayIndia4PrecYr | `FilingStatus.TotalPrStayIndia4PrecYr` | integer | ❌ | range:0–1461 |
| BenefitUs115HFlg | `FilingStatus.BenefitUs115HFlg` | string (enum) | ❌ | `"Y"`, `"N"` |
| AsseseeRepFlg | `FilingStatus.AsseseeRepFlg` | string (enum) | ❌ | `"Y"`, `"N"` |
| AssesseeRep (RepName) | `FilingStatus.AssesseeRep.RepName` | string | ✅* | maxLength:125, minLength:1 |
| AssesseeRep (RepEmailID) | `FilingStatus.AssesseeRep.RepEmailID` | string | ✅* | maxLength:125, email pattern |
| AssesseeRep (CountryCodeRepMobileNo) | `FilingStatus.AssesseeRep.CountryCodeRepMobileNo` | integer | ✅* | pattern:`[0-9]{1,5}` |
| AssesseeRep (RepMobileNo) | `FilingStatus.AssesseeRep.RepMobileNo` | integer | ✅* | pattern:`[1-9][0-9]{9}` or `[1-9][0-9]{4,9}` |
| PortugeseCC5A | `FilingStatus.PortugeseCC5A` | string (enum) | ❌ | `"Y"`, `"N"` |
| FiiFpiFlag | `FilingStatus.FiiFpiFlag` | string (enum) | ✅ | `"Y"`, `"N"` |
| SebiRegnNo | `FilingStatus.SebiRegnNo` | string | ❌ | pattern:`IN[a-zA-Z]{2}FP[0-9]{6}` |
| CompDirectorPrvYrFlg | `FilingStatus.CompDirectorPrvYrFlg` | string (enum) | ❌ | `"Y"`, `"N"` |
| CompDirectorPrvYr | `FilingStatus.CompDirectorPrvYr` | object | ❌ | See CompDirectorPrvYrDtls array |
| HeldUnlistedEqShrPrYrFlg | `FilingStatus.HeldUnlistedEqShrPrYrFlg` | string (enum) | ✅ | `"Y"`, `"N"` |
| HeldUnlistedEqShrPrYr | `FilingStatus.HeldUnlistedEqShrPrYr` | object | ❌ | See HeldUnlistedEqShrPrYrDtls |
| LEIDtls.LEINumber | `FilingStatus.LEIDtls.LEINumber` | string | ❌ | maxLength:20, minLength:20 |
| LEIDtls.ValidUptoDate | `FilingStatus.LEIDtls.ValidUptoDate` | string | ❌ | YYYY-MM-DD |
| ItrFilingDueDate | `FilingStatus.ItrFilingDueDate` | string | ✅ | maxLength:10, minLength:9, pattern:`"2026-07-31"` |

\* Required when AsseseeRepFlg is `"Y"`

#### clauseiv7provisio139iType (array item)
| Field | Type | Mandatory | Constraints |
|---|---|---|---|
| clauseiv7provisio139iNature | string (enum) | ✅ | `"1"`=TDS+TCS ≥₹25k/50k; `"2"`=Savings deposits ≥₹50L |
| clauseiv7provisio139iAmount | integer | ✅ | 0–99999999999999 |

#### JurisdictionResPrevYrDtls (array item)
| Field | Type | Mandatory | Constraints |
|---|---|---|---|
| JurisdictionResidence | string (enum) | ✅ | Country codes (93=AF, 1=CA, 2=US, 44=UK, 91=IN, etc.; 9998=Not Applicable, 9999=Others) |
| TIN | string | ✅ | maxLength:75, minLength:1 |

#### CompDirectorPrvYrDtls (array item)
| Field | Type | Mandatory | Constraints |
|---|---|---|---|
| NameOfCompany | string | ✅ | maxLength:125, minLength:1 |
| CompanyType | string (enum) | ✅ | `"D"`=Domestic, `"F"`=Foreign |
| PAN | string | ❌ | `[A-Z]{5}[0-9]{4}[A-Z]` |
| SharesTypes | string (enum) | ✅ | `"L"`=Listed, `"U"`=Unlisted |
| DIN | string | ❌ | `[0-9]{8}` |

#### HeldUnlistedEqShrPrYrDtls (array item)
| Field | Type | Mandatory | Constraints |
|---|---|---|---|
| NameOfCompany | string | ✅ | maxLength:125, minLength:1 |
| CompanyType | string (enum) | ✅ | `"D"`/`"F"` |
| PAN | string | ❌ | `[A-Z]{5}[0-9]{4}[A-Z]` |
| OpngBalNumberOfShares | integer | ✅ | 0–99999999999999 |
| OpngBalCostOfAcquisition | number | ✅ | ≥0, multipleOf:0.01 |
| ShrAcqDurYrNumberOfShares | integer | ❌ | 0–99999999999999 |
| DateOfSubscrPurchase | string | ❌ | YYYY-MM-DD |
| FaceValuePerShare | number | ❌ | ≥0, multipleOf:0.01 |
| IssuePricePerShare | integer | ❌ | 0–99999999999999 |
| PurchasePricePerShare | number | ❌ | ≥0, multipleOf:0.01 |
| ShrTrnfNumberOfShares | integer | ❌ | 0–99999999999999 |
| ShrTrnfSaleConsideration | number | ❌ | ≥0, multipleOf:0.01 |
| ClsngBalNumberOfShares | integer | ✅ | 0–99999999999999 |
| ClsngBalCostOfAcquisition | number | ✅ | ≥0, multipleOf:0.01 |

---

## 4. ScheduleS — Salary
**JSON Path:** `ITR.ITR2.ScheduleS`
**Required:** ❌ (optional as per JSON, but listed in ITR2 properties)

### Top-Level Fields

| Field | Path | Type | Mandatory | Constraints |
|---|---|---|---|---|
| Salaries | `ScheduleS.Salaries` | array | ❌ | minItems:1, of Salaries object |
| TotalGrossSalary | `ScheduleS.TotalGrossSalary` | integer | ✅ | 0–99999999999999, default:0 |
| AllwncExtentExemptUs10 | `ScheduleS.AllwncExtentExemptUs10` | integer | ✅ | 0–99999999999999, default:0 |
| AllwncExemptUs10 | `ScheduleS.AllwncExemptUs10` | object | ❌ | Contains array of AllwncExemptUs10DtlsType |
| Section10_13A | `ScheduleS.Section10_13A` | object | ❌ | HRA exemption details |
| Increliefus89A | `ScheduleS.Increliefus89A` | integer | ❌ | 0–99999999999999 |
| NetSalary | `ScheduleS.NetSalary` | integer | ✅ | 0–99999999999999, default:0 |
| DeductionUS16 | `ScheduleS.DeductionUS16` | integer | ✅ | 0–99999999999999, default:0 |
| DeductionUnderSection16ia | `ScheduleS.DeductionUnderSection16ia` | integer | ✅ | 0–75,000, default:0 |
| EntertainmntalwncUs16ii | `ScheduleS.EntertainmntalwncUs16ii` | integer | ✅ | 0–5,000, default:0 |
| ProfessionalTaxUs16iii | `ScheduleS.ProfessionalTaxUs16iii` | integer | ✅ | 0–5,000, default:0 |
| TotIncUnderHeadSalaries | `ScheduleS.TotIncUnderHeadSalaries` | integer | ✅ | 0–99999999999999, default:0 |

### Section10_13A (HRA) sub-object
| Field | Type | Mandatory | Constraints |
|---|---|---|---|
| Placeofwork | string (enum) | ✅ | `"1"`=Metro, `"2"`=Non-Metro |
| ActlHRARecv | integer | ✅ | 0–99999999999999 |
| ActlRentPaid | integer | ✅ | 0–99999999999999 |
| DtlsSalUsSec171 | integer | ✅ | 0–99999999999999 |
| ActlRentPaid10Per | integer | ✅ | 0–99999999999999 |
| Sal40Or50Per | integer | ✅ | 0–99999999999999 |
| EligbleExmpAllwncUs13A | integer | ✅ | 0–99999999999999 |

### Salaries (array item)
| Field | Path (within array) | Type | Mandatory | Constraints |
|---|---|---|---|---|
| NameOfEmployer | `Salaries[n].NameOfEmployer` | string | ✅ | maxLength:125 |
| NatureOfEmployment | `Salaries[n].NatureOfEmployment` | string (enum) | ✅ | `"CGOV"`, `"SGOV"`, `"PSU"`, `"PE"`, `"PESG"`, `"PEPS"`, `"PEO"`, `"OTH"` |
| TANofEmployer | `Salaries[n].TANofEmployer` | string | ❌ | pattern:`[A-Z]{4}[0-9]{5}[A-Z]` |
| AddressDetail | `Salaries[n].AddressDetail` | object | ✅ | (See AddressDetail — AddrDetail/City/State/PinCode/Zip) |
| **Salarys** | | | | |
| GrossSalary | `Salarys.GrossSalary` | integer | ✅ | 0–99999999999999 |
| Salary | `Salarys.Salary` | integer | ✅ | 0–99999999999999 |
| NatureOfSalary | `Salarys.NatureOfSalary` | object | ❌ | Contains OthersIncDtls array of NatureOfSalaryDtlsType |
| ValueOfPerquisites | `Salarys.ValueOfPerquisites` | integer | ✅ | 0–99999999999999 |
| NatureOfPerquisites | `Salarys.NatureOfPerquisites` | object | ❌ | Contains array of NatureOfPerquisitesType |
| ProfitsinLieuOfSalary | `Salarys.ProfitsinLieuOfSalary` | integer | ✅ | 0–99999999999999 |
| NatureOfProfitInLieuOfSalary | `Salarys.NatureOfProfitInLieuOfSalary` | object | ❌ | Contains array of NatureOfProfitInLieuOfSalaryType |
| IncomeNotified89A | `Salarys.IncomeNotified89A` | integer | ✅ | 0–99999999999999 |
| IncomeNotified89AType | `Salarys.IncomeNotified89AType` | array | ❌ | Array of NOT89AType |
| IncomeNotifiedOther89A | `Salarys.IncomeNotifiedOther89A` | integer | ✅ | 0–99999999999999 |
| IncomeNotifiedPrYr89A | `Salarys.IncomeNotifiedPrYr89A` | integer | ❌ | 0–99999999999999 |

#### NatureOfSalaryDtlsType (array item)
| Field | Type | Mandatory | Constraints |
|---|---|---|---|
| NatureDesc | string (enum) | ✅ | `"1"`=Basic, `"2"`=DA, `"3"`=Conveyance, `"4"`=HRA, `"5"`=LTA, `"6"`=ChildrenEducation, `"7"`=OtherAllowance, `"8"`=EmployerNPS, `"9"`=Rule6(4thSch), `"10"`=Rule11(4), `"11"`=Annuity/Pension, `"12"`=CommutedPension, `"13"`=Gratuity, `"14"`=Fees/Commission, `"15"`=AdvanceSalary, `"16"`=LeaveEncashment, `"17"`=Agnipath, `"OTH"`=Others |
| OthNatOfInc | string | ❌ | maxLength:50 |
| OthAmount | integer | ✅ | 0–99999999999999 |

#### NatureOfPerquisitesType (array item)
| Field | Type | Mandatory | Constraints |
|---|---|---|---|
| NatureDesc | string (enum) | ✅ | `"1"`–`"15"`=standard perks, `"16"`=ESOP-startup-deferred, `"17"`=Non-qualifiedESOP, `"18"`=Employer contribution 17(2)(vii), `"19"`=Accretion 17(2)(viia), `"21"`=ESOP-startup-not-deferred, `"OTH"` |
| OthNatOfInc | string | ❌ | maxLength:50 |
| OthAmount | integer | ✅ | 0–99999999999999 |

#### NatureOfProfitInLieuOfSalaryType
| Field | Type | Mandatory | Constraints |
|---|---|---|---|
| NatureDesc | string (enum) | ✅ | `"1"`=Termination compensation, `"2"`=PF/KeymanInsurance, `"3"`=Before-joining/after-cessation, `"OTH"` |
| OthNatOfInc | string | ❌ | maxLength:50 |
| OthAmount | integer | ✅ | 0–99999999999999 |

#### NOT89AType
| Field | Type | Mandatory | Constraints |
|---|---|---|---|
| NOT89ACountrycode | string (enum) | ✅ | `"US"`, `"UK"`, `"CA"` |
| NOT89AAmount | integer | ✅ | 0–99999999999999 |

#### AllwncExemptUs10DtlsType
| Field | Type | Mandatory | Constraints |
|---|---|---|---|
| SalNatureDesc | string (enum) | ✅ | `"10(5)"`=LTA, `"10(6)"`, `"10(7)"`, `"10(10)"`=Gratuity, `"10(10A)"`=CommutedPension, `"10(10AA)"`=LeaveEncashment, `"10(10B)(i)"`, `"10(10B)(ii)"`, `"10(10C)"`=VRS, `"10(10CC)"`, `"10(13A)"`=HRA, `"10(14)(i)"`, `"10(14)(ii)"`, `"10(14)(i)(115BAC)"`, `"10(14)(ii)(115BAC)"`, `"EIC"`=Judges, `"10(17)"`=MP/MLA |
| SalOthNatOfInc | string | ❌ | maxLength:125 |
| SalOthAmount | integer | ✅ | 0–99999999999999 |

---

## 5. ScheduleHP — House Property
**JSON Path:** `ITR.ITR2.ScheduleHP`
**Fields with NEGATIVE allowed:** `PassThroghIncome`, `TotalIncomeChargeableUnHP`, `HPSNo`, `IncomeOfHP`

| Field | Path | Type | Mandatory | Constraints |
|---|---|---|---|---|
| PropertyDetails | `ScheduleHP.PropertyDetails` | array | ❌ | Of PropertyDetails |
| PassThroghIncome | `ScheduleHP.PassThroghIncome` | integer | ❌ | **−99999999999999 to +99999999999999** |
| TotalIncomeChargeableUnHP | `ScheduleHP.TotalIncomeChargeableUnHP` | integer | ✅ | **−99999999999999 to +99999999999999**, default:0 |

### PropertyDetails (array item)
| Field | Type | Mandatory | Constraints |
|---|---|---|---|
| HPSNo | integer | ✅ | **−99999999999999 to +99999999999999** |
| AddressDetailWithZipCode | object | ✅ | AddrDetail/City/State/Country/PinCode/Zip |
| PropertyOwner | string (enum) | ✅ | `"SE"`=Self, `"MI"`=Minor, `"SP"`=Spouse, `"OT"`=Others |
| PropertyOwnerOther | string | ❌ | maxLength:50 |
| PropCoOwnedFlg | string (enum) | ✅ | `"YES"`, `"NO"` |
| AsseseeShareProperty | number | ✅ | 0–100, multipleOf:0.01, default:0 |
| CoOwners | array | ❌ | Array of CoOwners |
| ifLetOut | string (enum) | ✅ | `"L"`=LetOut, `"D"`=DeemedLetOut, `"S"`=SelfOccupied |
| TenantDetails | array | ❌ | Array of TenantDetails |
| Rentdetails | object | ✅ | See below |

### Rentdetails
| Field | Type | Mandatory | Constraints |
|---|---|---|---|
| AnnualLetableValue | integer | ✅ | 0–99999999999999 |
| RentNotRealized | integer | ❌ | 0–99999999999999 |
| LocalTaxes | integer | ❌ | 0–99999999999999 |
| TotalUnrealizedAndTax | integer | ✅ | 0–99999999999999 |
| BalanceALV | integer | ✅ | 0–99999999999999 |
| AnnualOfPropOwned | integer | ✅ | 0–99999999999999 |
| ThirtyPercentOfBalance | integer | ✅ | 0–99999999999999 |
| IntOnBorwCap | integer | ❌ | 0–99999999999999 |
| Section24B (object) | object | ❌ | Contains Section24BDtls array |
| TotalDeduct | integer | ✅ | 0–99999999999999 |
| ArrearsUnrealizedRentRcvd | integer | ❌ | 0–99999999999999 |
| **IncomeOfHP** | integer | ✅ | **−99999999999999 to +99999999999999** (supports losses) |

### Section24B sub-array item
| Field | Type | Mandatory | Constraints |
|---|---|---|---|
| LoanTknFrom | string (enum) | ✅ | `"B"`=Bank, `"I"`=OtherThanBank |
| BankOrInstnName | string | ✅ | maxLength:125 |
| LoanAccNoOfBankOrInstnRefNo | string (nonZeroString) | ✅ | maxLength:20 |
| DateofLoan | string | ✅ | YYYY-MM-DD |
| TotalLoanAmt | integer | ✅ | 0–99999999999999 |
| LoanOutstndngAmt | integer | ✅ | 0–99999999999999 |
| InterestUs24B | integer | ✅ | 0–99999999999999 |
| TotalInterestUs24B | integer | ✅ | 0–99999999999999 |

### CoOwners
| Field | Type | Mandatory | Constraints |
|---|---|---|---|
| CoOwnersSNo | integer | ✅ | −99999999999999 to +99999999999999 |
| NameCoOwner | string | ✅ | maxLength:125 |
| PAN_CoOwner | string | ❌ | `[A-Z]{5}[0-9]{4}[A-Z]` |
| Aadhaar_CoOwner | string | ❌ | `[0-9]{12}` |
| PercentShareProperty | number | ❌ | 0–100, multipleOf:0.01 |

### TenantDetails
| Field | Type | Mandatory | Constraints |
|---|---|---|---|
| TenantSNo | integer | ✅ | −99999999999999 to +99999999999999 |
| NameofTenant | string | ✅ | maxLength:125 |
| PANofTenant | string | ❌ | `[A-Z]{5}[0-9]{4}[A-Z]` |
| AadhaarofTenant | string | ❌ | `[0-9]{12}` |
| PANTANofTenant | string | ❌ | `[A-Z]{4}[0-9]{5}[A-Z]` or `[A-Z]{5}[0-9]{4}[A-Z]` |

---

## 6. ScheduleCGFor23 — Capital Gains (pre-23/7/2024)
**JSON Path:** `ITR.ITR2.ScheduleCGFor23`
**NEGATIVE allowed in:** Balance, STCGonImmvblPrprty, LTCGonImmvblPrprty, CapgainonAssets, NRITransaction amounts, PassThrInc, DTAA amounts, CapitalLossBuyBack, TotalSTCG, TotalLTCG

### Top-Level
| Field | Path | Type | Mandatory | Constraints |
|---|---|---|---|---|
| ShortTermCapGainFor23 | `ScheduleCGFor23.ShortTermCapGainFor23` | object | ✅ | See below |
| LongTermCapGain23 | `ScheduleCGFor23.LongTermCapGain23` | object | ✅ | See below |
| SumOfCGIncm | `ScheduleCGFor23.SumOfCGIncm` | integer | ✅ | 0–99999999999999 |
| IncmFromVDATrnsf | `ScheduleCGFor23.IncmFromVDATrnsf` | integer | ✅ | 0–99999999999999 |
| TotScheduleCGFor23 | `ScheduleCGFor23.TotScheduleCGFor23` | integer | ✅ | 0–99999999999999 |
| DeducClaimInfo | `ScheduleCGFor23.DeducClaimInfo` | object | ❌ | See deduction claims |
| CurrYrLosses | `ScheduleCGFor23.CurrYrLosses` | object | ✅ | Set-off of losses |
| AccruOrRecOfCG | `ScheduleCGFor23.AccruOrRecOfCG` | object | ✅ | Date-range breakup of CG |

### ShortTermCapGainFor23
| Sub-section | Type | Key Fields |
|---|---|---|
| SaleofLandBuild.SaleofLandBuildDtls | array | DateofPurchase, DateofSale, FullConsideration, PropertyValuation, FullConsideration50C (≥0), AquisitCost, ImproveCost, ExpOnTrans, TotalDedn, **Balance (− to +)**, DeductionUs54B, **STCGonImmvblPrprty (− to +)**, TrnsfImmblPrprtyDtls (buyer PAN/name/share/amount/address) |
| EquityMFonSTT | array (max 2) | MFSectionCode (enum:`"1A"` for 111A others, `"5AD1biip"` for FII), EquityOrUnitSec94TypeMFonSTT sub-object |
| NRITransacSec48Dtl | object | NRItaxSTTPaid (− to +), NRItaxSTTNotPaid (− to +) |
| NRISecur115AD | ref | EquityOrUnitSec94Type |
| SaleOnOtherAssets | ref | EquityOrUnitSec94Type |
| UnutilizedStcgFlag | string (enum) | `"Y"`, `"N"`, `"X"` |
| UnutilizedCg | object | UnutilizedCgPrvYrStcg (array) |
| AmtDeemedStcg | integer | 0–99999999999999 |
| TotalAmtDeemedStcg | integer | ✅ required | 0–99999999999999 |
| PassThrIncNatureSTCG | integer | ✅ | default:0 |
| PassThrIncNatureSTCG20Per | integer | ❌ | **− to +** |
| PassThrIncNatureSTCG30Per | integer | ❌ | **− to +** |
| PassThrIncNatureSTCGAppRate | integer | ❌ | **− to +** |
| NRICgDTAA | object | NRITaxUsDTAAStcgType (array of NRIDTAADtls) |
| TotalAmtNotTaxUsDTAAStcg | integer | ✅ | **− to +** |
| TotalAmtTaxUsDTAAStcg | integer | ✅ | **− to +** |
| CapitalLossBuyBackShares | object | TotalCapitalLossBuyBackShares (≤0, min:−), array of {Rate:STL20/STL30/STLAR, Amount:≤0} |
| TotalSTCG | integer | ✅ | **− to +** |

### LongTermCapGain23
Key sections mirror STCG but with LTCG specifics:
- **SaleofLandBuild**: with indexation (AquisitCostIndex, CostOfImprovements indexing), exemptions u/s 54/54B/54EC/54F
- **Proviso112Applicable** (max 2 entries): SectionCode `"22"` or `"5ACA1b"`, EquityOrUnitSec54TypeDebn112
- **SaleOfEquityShareUs112A**: EquityShareUs112A sub-object
- **NRIProvisoSec48**: LTCGWithoutBenefit, DeductionUs54F (max 1cr), BalanceCG
- **NRIOnSec112and115**: array of {SectionCode, FullValueConsd*, DeductSec48, BalanceCG, DeductionUs54F}
- **NRISaleOfEquityShareUs112A**
- **NRISaleofForeignAsset**: SaleonSpecAsset, DednSpecAssetus115, BalonSpeciAsset
- **SaleofAssetNADtls**
- **PassThrIncNatureLTCG**, **PassThrIncNatureLTCGUs112A12_5Per**, **PassThrIncNatureLTCG12_5Per** (all − to +)
- **NRICgDTAA** (NRITaxUsDTAALtcgType)
- **TotalAmtNotTaxUsDTAALtcg**, **TotalAmtTaxUsDTAALtcg** (− to +)
- **CapitalLossBuyBackShares** (LTCG)
- **TotalLTCG** (− to +)

### CurrYrLosses
Contains sub-objects for each CG category showing set-off:
- InLossSetOff, InStcg20Per, InStcg30Per, InStcgAppRate, InStcgDTAARate
- InLtcg12_5Per, InLtcgDTAARate
- TotLossSetOff, LossRemainSetOff

Each contains cross-category set-off fields like StclSetoff20Per, StclSetoff30Per, StclSetoffAppRate, StclSetoffDTAARate, LtclSetOff12_5Per, LtclSetOffDTAARate (all 0–max).

### AccruOrRecOfCG
Contains DateRangeType objects for each CG rate category:
- ShortTermUnder20Per, ShortTermUnder30Per, ShortTermUnderAppRate, ShortTermUnderDTAARate
- LongTermUnder12_5Per, LongTermUnderDTAARate
- VDATrnsfGainsUnder30Per

Each DateRangeType has DateRange with quarterly breakup: Upto15Of6, Upto15Of9, Up16Of9To15Of12, Up16Of12To15Of3, Up16Of3To31Of3 (all integers 0–max).

### DeducClaimInfo
Five deduction arrays:
- DeducClaimDtlsUs54 (array of DeducClaimDtls54n54F)
- DeducClaimDtlsUs54B (array of DeducClaimDtls54B)
- DeducClaimDtlsUs54EC (array of DeducClaimDtls54ECn115F)
- DeducClaimDtlsUs54F (array of DeducClaimDtls54n54F)
- DeducClaimDtlsUs115F (array of DeducClaimDtls115F)

Each has: DateofTransfer, cost/investment amount, DateofPurchase/Investment, AmtDeposited (for 54/54B), DepositDate, AccountNo, IFSC, AmtDeducted.

---

## 7. Schedule112A — LTCG on Equity (112A)
**JSON Path:** `ITR.ITR2.Schedule112A`

| Field | Path | Type | Mandatory | Constraints |
|---|---|---|---|---|
| Schedule112ADtls | `.Schedule112ADtls` | array | ❌ | Of Schedule112A115ADType |
| SaleValue112A | `.SaleValue112A` | integer | ✅ | 0–99999999999999 |
| CostAcqWithoutIndx112A | `.CostAcqWithoutIndx112A` | integer | ✅ | 0–99999999999999 |
| AcquisitionCost112A | `.AcquisitionCost112A` | integer | ✅ | 0–99999999999999 |
| LTCGBeforelowerB1B2112A | `.LTCGBeforelowerB1B2112A` | integer | ✅ | 0–99999999999999 |
| FairMktValueCapAst112A | `.FairMktValueCapAst112A` | integer | ✅ | 0–99999999999999 |
| ExpExclCnctTransfer112A | `.ExpExclCnctTransfer112A` | integer | ✅ | 0–99999999999999 |
| Deductions112A | `.Deductions112A` | integer | ✅ | 0–99999999999999 |
| Balance112A | `.Balance112A` | integer | ✅ | **−99999999999999 to +99999999999999** |
| TotalBalance112A | `.TotalBalance112A` | integer | ✅ | **−99999999999999 to +99999999999999** |

### Schedule112A115ADType (array item)
| Field | Type | Mandatory | Constraints |
|---|---|---|---|
| ShareOnOrBefore | string (enum) | ✅ | `"BE"`=Before 31-Jan-2018, `"AE"`=After 31-Jan-2018 |
| ISINCode | string | ✅ | pattern:`IN[0-9A-Z]{10}` or `"INNOTREQUIRD"` |
| ShareUnitName | string | ✅ | maxLength:125; `"CONSOLIDATED"` for AE |
| NumSharesUnits | number | ✅ | 0–100000000000000.0, multipleOf:0.0001 |
| SalePricePerShareUnit | number | ✅ | 0–100000000000000.0, multipleOf:0.0001 |
| TotSaleValue | integer | ✅ | 0–99999999999999 |
| CostAcqWithoutIndx | integer | ✅ | 0–99999999999999 |
| AcquisitionCost | number | ✅ | 0–100000000000000.0, multipleOf:0.0001 |
| LTCGBeforelowerB1B2 | integer | ✅ | 0–99999999999999 |
| FairMktValuePerShareunit | number | ✅ | 0–100000000000000.0, multipleOf:0.0001 |
| TotFairMktValueCapAst | integer | ✅ | 0–99999999999999 |
| ExpExclCnctTransfer | number | ✅ | 0–100000000000000.0, multipleOf:0.0001 |
| TotalDeductions | integer | ✅ | 0–99999999999999 |
| Balance | integer | ✅ | **−99999999999999 to +99999999999999** |

---

## 8. Schedule115AD — FII Capital Gains
**JSON Path:** `ITR.ITR2.Schedule115AD`

Identical structure to Schedule112A but with "115AD" suffix on all fields. Uses same Schedule112A115ADType for array items.

| Key Top-Level Fields | Type | Mandatory | Negative? |
|---|---|---|---|
| Schedule115ADDtls | array | ❌ | — |
| SaleValue115AD | integer | ✅ | No |
| CostAcqWithoutIndx115AD | integer | ✅ | No |
| AcquisitionCost115AD | integer | ✅ | No |
| LTCGBeforelowerB1B2115AD | integer | ✅ | No |
| FairMktValueCapAst115AD | integer | ✅ | No |
| ExpExclCnctTransfer115AD | integer | ✅ | No |
| Deductions115AD | integer | ✅ | No |
| Balance115AD | integer | ✅ | **YES (− to +)** |
| TotalBalance115AD | integer | ✅ | **YES (− to +)** |

---

## 9. ScheduleVDA — Virtual Digital Assets
**JSON Path:** `ITR.ITR2.ScheduleVDA`

| Field | Path | Type | Mandatory | Constraints |
|---|---|---|---|---|
| ScheduleVDADtls | `.ScheduleVDADtls` | array | ✅ | Array of VDA transaction objects |
| TotIncCapGain | `.TotIncCapGain` | integer | ✅ | 0–99999999999999 |

### ScheduleVDADtls (array item)
| Field | Type | Mandatory | Constraints |
|---|---|---|---|
| DateofAcquisition | string | ✅ | YYYY-MM-DD |
| DateofTransfer | string | ✅ | YYYY-MM-DD |
| HeadUndIncTaxed | string (enum) | ✅ | `"CG"` only |
| AcquisitionCost | integer | ✅ | 0–99999999999999 |
| ConsidReceived | integer | ✅ | 0–99999999999999 |
| IncomeFromVDA | integer | ✅ | 0–99999999999999 |

---

## 10. ScheduleOS — Other Sources
**JSON Path:** `ITR.ITR2.ScheduleOS`

### Top-Level
| Field | Path | Type | Mandatory | Constraints |
|---|---|---|---|---|
| IncOthThanOwnRaceHorse | `ScheduleOS.IncOthThanOwnRaceHorse` | object | ❌ (massive sub-object) | |
| TotOthSrcNoRaceHorse | `ScheduleOS.TotOthSrcNoRaceHorse` | integer | ❌ | 0–99999999999999 |
| IncFromOwnHorse | `ScheduleOS.IncFromOwnHorse` | object | ❌ | Race horse details |
| IncChargeable | `ScheduleOS.IncChargeable` | integer | ✅ | 0–99999999999999 |
| IncFrmLottery | `ScheduleOS.IncFrmLottery` | DateRangeType | ✅ | Quarterly breakup |
| IncFrmOnGames | `ScheduleOS.IncFrmOnGames` | DateRangeType | ❌ | Online games u/s 115BBJ |
| DividendIncUs115BBDA, DividendIncUs115BBDAaiii, DividendIncUs115A1ai, DividendIncUs115A1aA, DividendIncUs115AC, DividendIncUs115ACA, DividendIncUs115AD1i | | DateRangeType | ✅ (some) | Various dividend categories |
| DividendDTAA | | DateRangeType | ✅ | |
| NOT89A | | DateRangeType | ✅ | |

### IncOthThanOwnRaceHorse key fields
(All integers, many support negative)

| Field | Type | Range | Default | Negative? |
|---|---|---|---|---|
| GrossIncChrgblTaxAtAppRate | integer | − to + | 0 | YES |
| DividendGross | integer | 0–max | 0 | No |
| DividendOthThan22e, Dividend22e, Dividend22f | integer | 0–max | — | No |
| InterestGross | integer | − to + | 0 | YES |
| IntrstFrmSavingBank, IntrstFrmTermDeposit, IntrstFrmIncmTaxRefund | integer | 0–max | 0 | No |
| NatofPassThrghIncome | integer | − to + | 0 | YES |
| IntrstSec10XIFirstProviso, IntrstSec10XISecondProviso, IntrstSec10XIIFirstProviso, IntrstSec10XIISecondProviso | integer | 0–max | 0 | No |
| IntrstFrmOthers, RentFromMachPlantBldgs | integer | 0–max | 0 | No |
| Tot562x | integer | 0–max | 0 | No |
| Aggrtvaluewithoutcons562x, Immovpropwithoutcons562x, Immovpropinadeqcons562x, Anyotherpropwithoutcons562x, Anyotherpropinadeqcons562x | integer | 0–max | 0 | No |
| FamilyPension, AnyOtherIncome | integer | 0–max | 0 | No |
| IncChargeableSpecialRates, LtryPzzlChrgblUs115BB, IncChrgblUs115BBJ, IncChrgblUs115BBE | integer | 0–max | 0 | No |
| CashCreditsUs68, UnExplndInvstmntsUs69, UnExplndMoneyUs69A, UnDsclsdInvstmntsUs69B, UnExplndExpndtrUs69C, AmtBrwdRepaidOnHundiUs69D | integer | 0–max | 0 | No |
| OthersGross | integer | 0–max | 0 | No |
| OthersGrossDtls | array | — | — | Items:{SourceDescription (special-rates enum 22+ values), SourceAmount (0–max)} |
| PassThrIncOSChrgblSplRate | integer | 0–max | 0 | No |
| PTIOthersGrossDtls | array | — | — | Same enum prefixed "PTI_" |
| Deductions ( Expenses, UsrIntExp57, IntExp57, DeductionUs57iia ≤25000, Depreciation, TotDeductions) | object | 0–max | ✅ some | No |
| AmtNotDeductibleUs58, ProfitChargTaxUs59 | integer | − to + | — | YES |
| Increliefus89AOS | integer | 0–max | — | No |
| BalanceNoRaceHorse | integer | − to + | 0 | YES |
| TaxAccumulatedBalRecPF | object | — | — | Array of {AY, IncomeBenefit, TaxBenefit} + totals |
| IncChargblSplRateOS.TotalAmtTaxUsDTAASchOs | integer | 0–max | ✅ | No |
| NRIOsDTAA | object | — | — | NRIDTAADtlsSchOS array |

### IncFromOwnHorse
| Field | Type | Mandatory | Constraints |
|---|---|---|---|
| Receipts | integer | ✅ | 0–max |
| DeductSec57 | integer | ✅ | 0–max |
| AmtNotDeductibleUs58 | integer | ❌ | − to + |
| ProfitChargTaxUs59 | integer | ❌ | − to + |
| BalanceOwnRaceHorse | integer | ✅ | − to +, default:0 |

---

## 11. ScheduleCYLA — Current Year Loss Adjustment
**JSON Path:** `ITR.ITR2.ScheduleCYLA`
**Required:** ✅ Yes

| Field | Path | Type | Mandatory |
|---|---|---|---|
| Salary.IncCYLA | `ScheduleCYLA.Salary.IncCYLA` | ref IncCYLA | ❌ |
| HP.IncCYLA | `ScheduleCYLA.HP.IncCYLA` | ref HPIncCYLA | ❌ |
| STCG20Per.IncCYLA | `ScheduleCYLA.STCG20Per.IncCYLA` | ref IncCYLA | ✅ |
| STCG30Per.IncCYLA | `ScheduleCYLA.STCG30Per.IncCYLA` | ref IncCYLA | ✅ |
| STCGAppRate.IncCYLA | `ScheduleCYLA.STCGAppRate.IncCYLA` | ref IncCYLA | ✅ |
| STCGDTAARate.IncCYLA | `ScheduleCYLA.STCGDTAARate.IncCYLA` | ref IncCYLA | ✅ |
| LTCG12_5Per.IncCYLA | `ScheduleCYLA.LTCG12_5Per.IncCYLA` | ref IncCYLA | ✅ |
| LTCGDTAARate.IncCYLA | `ScheduleCYLA.LTCGDTAARate.IncCYLA` | ref IncCYLA | ✅ |
| OthSrcExclRaceHorse.IncCYLA | `ScheduleCYLA.OthSrcExclRaceHorse.IncCYLA` | ref OthSrcExclRaceHorseIncCYLA | ❌ |
| OthSrcRaceHorse.IncCYLA | `ScheduleCYLA.OthSrcRaceHorse.IncCYLA` | ref IncCYLA | ❌ |
| IncOSDTAA.IncCYLA | `ScheduleCYLA.IncOSDTAA.IncCYLA` | ref IncCYLA | ❌ |
| TotalCurYr | object | ✅ | TotHPlossCurYr, TotOthSrcLossNoRaceHorse (0–max) |
| TotalLossSetOff | object | ✅ | TotHPlossCurYrSetoff (max 2,00,000), TotOthSrcLossNoRaceHorseSetoff (0–max) |
| LossRemAftSetOff | object | ✅ | BalHPlossCurYrAftSetoff, BalOthSrcLossNoRaceHorseAftSetoff |

### IncCYLA (standard)
| Field | Type | Mandatory | Constraints |
|---|---|---|---|
| IncOfCurYrUnderThatHead | integer | ✅ | 0–99999999999999, default:0 |
| HPlossCurYrSetoff | integer | ❌ | 0–max |
| OthSrcLossNoRaceHorseSetoff | integer | ❌ | 0–max |
| IncOfCurYrAfterSetOff | integer | ✅ | 0–max |

### HPIncCYLA
| Field | Type | Mandatory |
|---|---|---|
| IncOfCurYrUnderThatHead | integer | ✅ (0–max) |
| OthSrcLossNoRaceHorseSetoff | integer | ❌ (0–max) |
| IncOfCurYrAfterSetOff | integer | ✅ |

### OthSrcExclRaceHorseIncCYLA
| Field | Type | Mandatory |
|---|---|---|
| IncOfCurYrUnderThatHead | integer | ✅ (0–max) |
| HPlossCurYrSetoff | integer | ❌ (0–max) |
| IncOfCurYrAfterSetOff | integer | ✅ |

---

## 12. ScheduleBFLA — Brought Forward Loss Adjustment
**JSON Path:** `ITR.ITR2.ScheduleBFLA`
**Required:** ✅ Yes

| Field | Type | Mandatory |
|---|---|---|
| Salary.IncBFLA | ref SalaryOthSrcIncBFLA | ✅ |
| HP.IncBFLA | ref IncBFLA | ❌ |
| STCG20Per.IncBFLA, STCG30Per.IncBFLA, STCGAppRate.IncBFLA, STCGDTAARate.IncBFLA | ref IncBFLA | ✅ each |
| LTCG12_5Per.IncBFLA, LTCGDTAARate.IncBFLA | ref IncBFLA | ✅ each |
| OthSrcExclRaceHorse.IncBFLA | ref SalaryOthSrcIncBFLA | ❌ |
| OthSrcRaceHorse.IncBFLA | ref IncBFLA | ❌ |
| IncOSDTAA.IncBFLA | ref SalaryOthSrcIncBFLA | ❌ |
| TotalBFLossSetOff.TotBFLossSetoff | integer | ✅ (0–max) |
| IncomeOfCurrYrAftCYLABFLA | integer | ✅ (0–max) |

### IncBFLA
| Field | Type | Mandatory |
|---|---|---|
| IncOfCurYrUndHeadFromCYLA | integer | ✅ (0–max) |
| BFlossPrevYrUndSameHeadSetoff | integer | ✅ (0–max) |
| IncOfCurYrAfterSetOffBFLosses | integer | ✅ (0–max) |

### SalaryOthSrcIncBFLA (simplified)
| Field | Type |
|---|---|
| IncOfCurYrUndHeadFromCYLA | integer |
| IncOfCurYrAfterSetOffBFLosses | integer |

---

## 13. ScheduleCFL — Carry Forward Loss
**JSON Path:** `ITR.ITR2.ScheduleCFL`

| Field | Description |
|---|---|
| LossCFFromPrev8thYearFromAY | AY 2018-19, ref CarryFwdWithoutLossDetail |
| LossCFFromPrev7thYearFromAY | AY 2019-20 |
| LossCFFromPrev6thYearFromAY | AY 2020-21 |
| LossCFFromPrev5thYearFromAY | AY 2021-22 |
| LossCFFromPrev4thYearFromAY | AY 2022-23, ref CarryFwdLossDetail (incl DateOfFiling) |
| LossCFFromPrev3rdYearFromAY | AY 2023-24 |
| LossCFFromPrev2ndYearFromAY | AY 2024-25 |
| LossCFFromPrevYrToAY | AY 2025-26 |
| TotalOfBFLossesEarlierYrs.LossSummaryDetail | Summary |
| AdjTotBFLossInBFLA.LossSummaryDetail | Adjusted |
| CurrentAYloss.LossSummaryDetail | Current year losses |
| TotalLossCFSummary.LossSummaryDetail | Total |

**LossSummaryDetail fields:** TotalHPPTILossCF, TotalSTCGPTILossCF, TotalLTCGPTILossCF, OthSrcLossRaceHorseCF (all 0–max).

**CarryFwdLossDetail:** DateOfFiling, TotalHPPTILossCF, TotalSTCGPTILossCF, TotalLTCGPTILossCF, OthSrcLossRaceHorseCF.

**CarryFwdWithoutLossDetail:** Same minus OthSrcLossRaceHorseCF.

---

## 14. ScheduleVIA — Chapter VI-A Deductions
**JSON Path:** `ITR.ITR2.ScheduleVIA`
**Required:** ✅ Yes
Contains two sub-objects: `UsrDeductUndChapVIA` (user-entered) and `DeductUndChapVIA` (actual allowed deduction).

### UsrDeductUndChapVIA
All fields integer 0–99999999999999 unless noted:

| Field | Constraints |
|---|---|
| Section80C | No cap |
| Section80CCC | No cap |
| PensionContribution80CCC | array of {TypeofIdentifier:`"PRAN"`/`"OTHPRAN"`, NameofIdentifier, Amount} |
| Section80CCDEmployeeOrSE | No cap |
| Section80CCD1B | No cap in Usr |
| Section80CCDEmployer | No cap |
| PRANDtls | array of {PRANNum: `[0-9]{12}`} |
| Section80D | No cap in Usr |
| Section80DD | No cap |
| Section80DDBUsrType | enum:`"1"`=Self/dependent, `"2"`=SeniorCitizen |
| Section80DDB | No cap |
| NameOfSpecDisease80DDB | enum:`"a"`–`"n"` (14 diseases) |
| Section80E, Section80EE, Section80EEA, Section80EEB, Section80G | No cap |
| Section80GG | No cap |
| Form10BAAckNum | string, maxLength:15 |
| Section80GGA, Section80GGC, Section80U | No cap |
| Section80QQB, Section80RRB | with Form ack num fields (maxLength:15) |
| Section80TTA, Section80TTB | No cap |
| AnyOthSec80CCH | No cap |
| TotalChapVIADeductions | Sum total |

### DeductUndChapVIA (actual allowed)
| Field | Max Limit |
|---|---|
| Section80C | no hard cap |
| Section80CCC | no hard cap |
| Section80CCDEmployeeOrSE | no hard cap |
| Section80CCD1B | **50,000** |
| Section80CCDEmployer | no hard cap |
| Section80D | **1,00,000** |
| Section80DD | **1,25,000** |
| Section80DDB | **1,00,000** |
| Section80E | no hard cap |
| Section80EE | **50,000** |
| Section80EEA | **1,50,000** |
| Section80EEB | **1,50,000** |
| Section80G | no hard cap |
| Section80GG | **60,000** |
| Section80GGA | no hard cap |
| Section80GGC | no hard cap |
| Section80U | **1,25,000** |
| Section80RRB | **3,00,000** |
| Section80QQB | **3,00,000** |
| Section80TTA | **10,000** |
| Section80TTB | **50,000** |
| AnyOthSec80CCH | **2,88,000** |
| TotalChapVIADeductions | sum total |

---

## 15. Schedule80C, 80D, 80G, 80GGC, 80DD, 80U, 80E, 80EE, 80EEA, 80EEB, 80GGA

### Schedule80C
| Field | Type | Mandatory | Constraints |
|---|---|---|---|
| Schedule80CDtls | array | ✅ | Items: {IdentificationNo (string maxLength:50), Amount (0–max)} |
| TotalAmt | integer | ✅ | 0–99999999999999 |

### Schedule80D
Complex nested object `Sec80DSelfFamSrCtznHealth` with four quadrants (Self+Family, Parents × SeniorCitizen/NonSenior):
| Key fields | Type |
|---|---|
| SeniorCitizenFlag / ParentsSeniorCitizenFlag | string pattern:`"Y"/"N"/"S"` or `"Y"/"N"/"P"` |
| HealthInsPrem, PrevHlthChckUp, MedicalExp | integers |
| SelfAndFamily / SelfAndFamilySeniorCitizen / Parents / ParentsSeniorCitizen | integers with caps (25000 or 50000) |
| EligibleAmountOfDedn | integer, max:100000 |
| Insurance detail sub-arrays (Sch80DInsDtls): {InsurerName, PolicyNo, HealthInsAmt} × 4 |

### Schedule80G
Four donation categories, each with:
| Category | Deduction % |
|---|---|
| Don100Percent | 100% without approval needed |
| Don50PercentNoApprReqd | 50% without approval needed |
| Don100PercentApprReqd | 100% with approval |
| Don50PercentApprReqd | 50% with approval |

Each category has:
- DoneeWithPan (array of DoneeWithPan)
- Totals: Cash, OtherMode, Total, EligibleAmount

**DoneeWithPan:**
| Field | Type | Mandatory | Constraints |
|---|---|---|---|
| DoneeWithPanName | string | ✅ | maxLength:125 |
| DoneePAN | string | ✅ | `[A-Z]{5}[0-9]{4}[A-Z]` |
| ArnNbr | string | ❌ | maxLength:25 |
| AddressDetail | ref AddressDetail80G | ✅ | |
| DonationAmtCash | integer | ✅ | 0–max |
| DonationAmtOtherMode | integer | ✅ | 0–max |
| TransactionRefNum | string | ❌ | maxLength:50 |
| IFSCCode | string | ❌ | `[A-Z]{4}[0][A-Z0-9]{6}` |
| DonationAmt | integer | ✅ | 0–max |
| EligibleDonationAmt | integer | ✅ | 0–max |

Global totals: TotalDonationsUs80GCash, TotalDonationsUs80GOtherMode, TotalDonationsUs80G, TotalEligibleDonationsUs80G.

### Schedule80GGC
| Field | Type | Mandatory | Constraints |
|---|---|---|---|
| Schedule80GGCDetails | array | ❌ | Items:{DonationDate, DonationAmtCash, DonationAmtOtherMode, TransactionRefNum, IFSCCode, DonationAmt, EligibleDonationAmt, PoliticalPartyName, PoliticalPartyPAN} |
| TotalDonationAmtCash80GGC, TotalDonationAmtOtherMode80GGC, TotalDonationsUs80GGC, TotalEligibleDonationAmt80GGC | integer | ✅ | 0–max |

### Schedule80DD
| Field | Type | Mandatory | Constraints |
|---|---|---|---|
| NatureOfDisability | string (enum) | ✅ | `"1"`=Disabled dependent, `"2"`=Severely disabled dependent |
| TypeOfDisability | string (enum) | ✅ | `"1"`=Autism/cerebralPalsy/multiple, `"2"`=Others |
| DeductionAmount | integer | ✅ | maxLength:14 |
| DependentType | string (enum) | ✅ | `"1"`=Spouse, `"2"`=Son, `"3"`=Daughter, `"4"`=Father, `"5"`=Mother, `"6"`=Brother, `"7"`=Sister, `"8"`=HUF member |
| DependentPan | string | ❌ | `[A-Z]{5}[0-9]{4}[A-Z]` |
| DependentAadhaar | string | ❌ | `[0-9]{12}` |
| Form10IAFilingDate | string | ❌ | YYYY-MM-DD |
| Form10IAAckNum | string | ❌ | maxLength:15 |
| FormAckNum11A | string | ❌ | maxLength:15 |
| UDIDNum | string | ❌ | maxLength:18 |

### Schedule80U
| Field | Type | Mandatory | Constraints |
|---|---|---|---|
| NatureOfDisability | string (enum) | ✅ | `"1"`=Self with disability, `"2"`=Self with severe disability |
| TypeOfDisability | string (enum) | ✅ | `"1"`/`"2"` (same as 80DD) |
| DeductionAmount | integer | ✅ | maxLength:14 |
| Form10IAFilingDate, Form10IAAckNum, FormAckNum11A, UDIDNum | | ❌ | Same as 80DD |

### Schedule80E, 80EE, 80EEA, 80EEB
All follow similar loan-detail patterns with:

| Common Fields | Specifics |
|---|---|
| LoanTknFrom | enum:`"B"`=Bank, `"I"`=Institution |
| BankOrInstnName | maxLength:125 |
| LoanAccNoOfBankOrInstnRefNo | maxLength:20, nonZeroString pattern |
| DateofLoan | YYYY-MM-DD |
| TotalLoanAmt | integer 0–max (80EE: max 35,00,000) |
| LoanOutstndngAmt | integer 0–max |
| Interest{Section} | integer 0–max |

80EEA adds: PropStmpDtyVal (max:45,00,000)
80EEB adds: VehicleRegNo (maxLength:11)

### Schedule80GGA
| Field | Type | Mandatory |
|---|---|---|
| DonationDtlsSciRsrchRuralDev | array | ❌ |
| Totals (Cash/Other/Total/Eligible) | integer | ✅ |

Array item fields:
| Field | Type | Mandatory | Constraints |
|---|---|---|---|
| RelevantClauseUndrDedClaimed | string (enum) | ✅ | `"80GGA2a"`–`"80GGA2e"` (8 values) |
| NameOfDonee, AddressDetail, DoneePAN | | ✅ | |
| DonationAmtCash, DonationAmtOtherMode, DonationAmt, EligibleDonationAmt | integer | ✅ | 0–max |

---

## 16. ScheduleAMT + ScheduleAMTC

### ScheduleAMT
| Field | Type | Mandatory | Constraints |
|---|---|---|---|
| TotalIncItemPartBTI | integer | ✅ | **− to +**, default:0 |
| DeductionClaimUndrAnySec | integer | ✅ | **− to +**, default:0 |
| AdjustedUnderSec115JC | integer | ✅ | 0–max, default:0 |
| TaxPayableUnderSec115JC | integer | ✅ | 0–max, default:0 |

### ScheduleAMTC
| Field | Type | Mandatory | Constraints |
|---|---|---|---|
| TaxSection115JC | integer | ✅ | 0–max |
| TaxOthProvisions | integer | ✅ | 0–max |
| AmtTaxCreditAvailable | integer | ✅ | 0–max |
| ScheduleAMTCDtls | array | ❌ | 1–13 items, each {AssYr (enum 2013-14 to 2025-26), Gross, AmtCreditSetOfEy, AmtCreditBalBroughtFwd, AmtCreditUtilized, BalAmtCreditCarryFwd} |
| CurrAssYr | string (enum) | ❌ | `"2026-27"` |
| CurrYrAmtCreditFwd | integer | ✅ | 0–max |
| CurrYrCreditCarryFwd | integer | ✅ | 0–max |
| TotAMTGross, TotSetOffEys, TotBalBF, TotAmtCreditUtilisedCY, TotBalAMTCreditCF | integer | ✅ | 0–max |
| TaxSection115JD, AmtLiabilityAvailable | integer | ✅ | 0–max |

---

## 17. ScheduleSPI — Clubbing of Income
**JSON Path:** `ITR.ITR2.ScheduleSPI`

| Field | Type | Mandatory |
|---|---|---|
| SpecifiedPerson | array (min 1) | ❌ |

**SpecifiedPerson (array item):**
| Field | Type | Mandatory | Constraints |
|---|---|---|---|
| SpecifiedPersonName | string | ✅ | maxLength:125 |
| PANofSpecPerson | string | ❌ | `[A-Z]{5}[0-9]{4}[A-Z]` |
| AaadhaarOfSpecPerson | string | ❌ | `[0-9]{12}` |
| ReltnShip | string | ✅ | maxLength:50 |
| **AmtIncluded** | integer | ✅ | **− to +** |
| HeadIncIncluded | string (enum) | ✅ | `"SA"`, `"HP"`, `"CG"`, `"OS"`, `"EI"` |

---

## 18. ScheduleSI — Special Rate Income
**JSON Path:** `ITR.ITR2.ScheduleSI`

| Field | Type | Mandatory |
|---|---|---|
| SplCodeRateTax | array (min 1) | ❌ |
| TotSplRateInc | integer | ✅ (0–max) |
| TotSplRateIncTax | integer | ✅ (0–max) |

**SplCodeRateTax array item:**
| Field | Type | Mandatory | Constraints |
|---|---|---|---|
| SecCode | string (enum) | ✅ | 68 possible values: `"1"`=111, `"1A"`=111A, `"21"`=112, `"22"`=112(1), `"21ciii"`, `"2A"`=112A, `"5A1ai"`–`"5ADiiiP"` (various 115A/115AC/115ACA/115AD), `"5BB"`, `"5BBJ"`, `"5BBA"`, `"5BBE"`, `"5BBF"`, `"5BBG"`, `"5BBH"`=VDA, `"5Ea"`, `"5Eb"`, `"DTAASTCG"`, `"DTAALTCG"`, `"DTAAOS"`, plus PTI_ variants |
| SplRatePercent | number (enum) | ✅ | `1, 4, 5, 9, 10, 12.5, 15, 20, 25, 30, 50, 60` |
| SplRateInc | integer | ✅ | 0–max |
| SplRateIncTax | integer | ✅ | 0–max |

---

## 19. ScheduleEI — Exempt Income
**JSON Path:** `ITR.ITR2.ScheduleEI`

| Field | Type | Mandatory | Constraints |
|---|---|---|---|
| InterestInc | integer | ❌ | 0–max |
| GrossAgriRecpt | integer | ❌ | 0–max |
| ExpIncAgri | integer | ❌ | 0–max |
| UnabAgriLossPrev8 | integer | ❌ | 0–max |
| NetAgriIncOrOthrIncRule7 | integer | ✅ | 0–max |
| ExcNetAgriInc.ExcNetAgriIncDtls | array | ❌ | {NameOfDistrict, PinCode, MeasurementOfLand (number×0.01), AgriLandOwnedFlag:`"O"`/`"H"`, AgriLandIrrigatedFlag:`"IRG"`/`"RF"`} |
| OthersInc.OthersIncDtls | array | ❌ | OthersIncDtlEI items |
| Others | integer | ✅ | 0–max |
| IncNotChrgblAsPerDTAA.IncNotChrgblAsPerDTAADtls | array | ❌ | {AmountOfIncome, NatureOfIncome, CountryName, CountryCodeExcludingIndia, ArticleOfDTAA, HeadOfIncome:`"SA"/"HP"/"CG"/"OS"`, TRCFlag:`"Y"/"N"`} |
| IncNotChrgblToTax | integer | ✅ | 0–max |
| PassThrIncNotChrgblTax | integer | ❌ | 0–max |
| TotalExemptInc | integer | ✅ | 0–max |

**OthersIncDtlEI array item:**
| Field | Type | Mandatory | Constraints |
|---|---|---|---|
| Category | string (enum) | ❌ | `"AGRI"`, `"GOVC"`, `"ISI"`, `"SSRA"`, `"SRSC"`, `"SRST"`, `"SRPC"`, `"OTH"`, `"OTHN"` |
| SubCategory | string (enum) | ❌ | 51 values: `"10(30)"`–`"10(9)"`, including `"DMD"`, `"Incmexmptcircular"`, `"Incmexmptnotification"`, `"Receiptnotincme"` |
| Description | string | ❌ | maxLength:125 |
| OthAmount | integer | ✅ | 0–max |

---

## 20. SchedulePTI — Pass Through Income
**JSON Path:** `ITR.ITR2.SchedulePTI`

| Field | Type |
|---|---|
| SchedulePTIDtls | array (min 1) |

**SchedulePTIDtls array item:**
| Field | Type | Mandatory | Constraints |
|---|---|---|---|
| InvstmntCvrdUs115UA115UB | string | ✅ | pattern:`"A"`/`"B"`/`"C"` (115UA/115UB/115U) |
| BusinessName, BusinessPAN | string | ✅ | |
| IncFromHP | SchedulePTIType | ✅ | {AmountOfInc, CurrYrLossShareByInvstFund, NetIncomeLoss (− to +), TDSAmount} |
| CapitalGainsPTI | object | ✅ | ShortTermCG, STCG_Sec111A, STCG_Others, LongTermCG, LTCG_Sec112A, LTCG_Others — all SchedulePTIType |
| IncClmdPTI | object | ✅ | TotalSec23FBB, Sec23FBB, SecBIncExmptDtl, SecCIncExmptDtl — various sub-types |
| IncOthSrc, OS_Dividend, OS_Others | SchedulePTITypeOS23FBB | ✅ | {AmountOfInc (− to +), NetIncomeLoss (− to +), TDSAmount (0–max)} |

---

## 21. ScheduleFSI — Foreign Source Income
**JSON Path:** `ITR.ITR2.ScheduleFSI`

| Field | Type |
|---|---|
| ScheduleFSIDtls | array (min 1) |

**ScheduleFSIDtls array item:**
| Field | Type | Mandatory | Constraints |
|---|---|---|---|
| CountryName | string | ✅ | maxLength:55 |
| CountryCodeExcludingIndia | string (enum) | ✅ | All countries except India |
| TaxIdentificationNo | string | ✅ | maxLength:75 |
| IncFromSal, IncFromHP, IncCapGain, IncOthSrc, TotalCountryWise | ScheduleFSIIncType | ✅ | Each: {IncFrmOutsideInd, TaxPaidOutsideInd, TaxPayableinInd, TaxReliefinInd (all 0–max), DTAAReliefUs90or90A (string, optional)} |

---

## 22. ScheduleTR1 — Tax Relief (DTAA)
**JSON Path:** `ITR.ITR2.ScheduleTR1`

| Field | Type | Mandatory | Constraints |
|---|---|---|---|
| ScheduleTR | array | ❌ | Items: {CountryName, CountryCodeExcludingIndia, TaxIdentificationNo, TaxPaidOutsideIndia, TaxReliefOutsideIndia, ReliefClaimedUsSection:`"90"/"90A"/"91"`} |
| TotalTaxPaidOutsideIndia | integer | ✅ | 0–max |
| TotalTaxReliefOutsideIndia | integer | ✅ | 0–max |
| TaxReliefOutsideIndiaDTAA | integer | ✅ | 0–max |
| TaxReliefOutsideIndiaNotDTAA | integer | ✅ | 0–max |
| TaxPaidOutsideIndFlg | string (enum) | ❌ | `"YES"`, `"NO"` |
| AmtTaxRefunded | integer | ❌ | **− to +** |
| AssmtYrTaxRelief | string | ❌ | Pattern:`YYYY-YY` |

---

## 23. ScheduleFA — Foreign Assets (ALL 10 sub-sections)
**JSON Path:** `ITR.ITR2.ScheduleFA`

### 23a. DetailsForiegnBank (Foreign Bank Accounts)
| Field | Type | Mandatory | Negative? |
|---|---|---|---|
| CountryName | string | ✅ | — |
| CountryCodeExcludingIndia | string (enum) | ✅ | — |
| Bankname | string | ✅ | — |
| AddressOfBank | string | ✅ | — |
| ZipCode | string | ✅ | — |
| ForeignAccountNumber | string | ✅ | maxLength:34 |
| OwnerStatus | string (enum) | ✅ | `"OWNER"`, `"BENEFICIAL_OWNER"`, `"BENIFICIARY"` |
| AccOpenDate | string | ✅ | YYYY-MM-DD |
| PeakBalanceDuringYear | integer | ✅ | **− to +** |
| ClosingBalance | integer | ✅ | **− to +** |
| IntrstAccured | integer | ✅ | **− to +** |

### 23b. DtlsForeignCustodialAcc (Custodial Accounts)
| Field | Type | Mandatory | Constraints |
|---|---|---|---|
| CountryName, CountryCodeExcludingIndia | | ✅ | |
| FinancialInstName, FinancialInstAddress | string | ✅ | |
| ZipCode | string | ✅ | |
| AccountNumber | string | ✅ | maxLength:34 |
| Status | string (enum) | ✅ | `"OWNER"/"BENEFICIAL_OWNER"/"BENIFICIARY"` |
| AccOpenDate | string | ✅ | YYYY-MM-DD |
| PeakBalanceDuringPeriod | integer | ✅ | **− to +** |
| ClosingBalance | integer | ✅ | **− to +** |
| GrossAmtPaidCredited | integer | ✅ | 0–max |
| NatureOfAmount | string (enum) | ✅ | `"I"`=Interest, `"D"`=Dividend, `"S"`=Sale/redemption, `"O"`=Other, `"N"`=NoAmount |

### 23c. DtlsForeignEquityDebtInterest (Equity/Debt)
| Field | Type | Mandatory | Negative? |
|---|---|---|---|
| CountryName, CountryCodeExcludingIndia | | ✅ | |
| NameOfEntity, AddressOfEntity, ZipCode | string | ✅ | |
| NatureOfEntity | string | ✅ | maxLength:34 |
| InterestAcquiringDate | string | ✅ | YYYY-MM-DD |
| InitialValOfInvstmnt | integer | ✅ | **YES (− to +)** |
| PeakBalanceDuringPeriod | integer | ✅ | **YES** |
| ClosingBalance | integer | ✅ | **YES** |
| TotGrossAmtPaidCredited | integer | ✅ | **YES** |
| TotGrossProceeds | integer | ✅ | **YES** |

### 23d. DtlsForeignCashValueInsurance
| Field | Type | Mandatory | Negative? |
|---|---|---|---|
| CountryName, CountryCodeExcludingIndia | | ✅ | |
| FinancialInstName, FinancialInstAddress, ZipCode | string | ✅ | |
| ContractDate | string | ✅ | YYYY-MM-DD |
| CashValOrSurrenderVal | integer | ✅ | **YES** |
| TotGrossAmtPaidCredited | integer | ✅ | **YES** |

### 23e. DetailsFinancialInterest
| Field | Type | Mandatory |
|---|---|---|
| CountryName, CountryCodeExcludingIndia, ZipCode | | ✅ |
| NatureOfEntity | string (maxLength:100) | ❌ |
| NameOfEntity, AddressOfEntity | string | ✅ |
| NatureOfInt | string (enum) | ✅ | `"DIRECT"`, `"BENEFICIAL_OWNER"`, `"BENIFICIARY"` |
| DateHeld | string | ✅ | YYYY-MM-DD |
| TotalInvestment | integer | ✅ | 0–max |
| IncFromInt | integer | ✅ | **− to +** |
| NatureOfInc | string | ✅ | maxLength:100 |
| IncTaxAmt | integer | ✅ | **− to +** |
| IncTaxSch | string (enum) | ✅ | `"SA"/"HP"/"CG"/"OS"/"EI"/"NI"` |
| IncTaxSchNo | string | ✅ | maxLength:50 |

### 23f. DetailsImmovableProperty
| Field | Type | Mandatory |
|---|---|---|
| CountryName, CountryCodeExcludingIndia, ZipCode | | ✅ |
| AddressOfProperty | string | ❌ | maxLength:200 |
| Ownership | string (enum) | ✅ | `"DIRECT"/"BENEFICIAL_OWNER"/"BENIFICIARY"` |
| DateOfAcq | string | ✅ | YYYY-MM-DD |
| TotalInvestment | integer | ✅ | 0–max |
| IncDrvProperty | integer | ✅ | **− to +** |
| NatureOfInc | string | ✅ | maxLength:100 |
| IncTaxAmt | integer | ✅ | **− to +** |
| IncTaxSch | string (enum) | ✅ | `"SA"/"HP"/"CG"/"OS"/"EI"/"NI"` |
| IncTaxSchNo | string | ✅ | maxLength:50 |

### 23g. DetailsOthAssets
Same structure as ImmovableProperty but:
- NatureOfAsset instead of AddressOfProperty
- IncDrvAsset instead of IncDrvProperty

### 23h. DetailsOfAccntsHvngSigningAuth
| Field | Type | Mandatory | Constraints |
|---|---|---|---|
| NameOfInstitution, AddressOfInstitution | string | ✅ | |
| CountryName, CountryCodeExcludingIndia, ZipCode | | ✅ | |
| NameMentionedInAccnt | string | ✅ | maxLength:125 |
| InstitutionAccountNumber | string | ✅ | maxLength:34 |
| PeakBalanceOrInvestment | integer | ✅ | **− to +** |
| IncAccuredTaxFlag | string (enum) | ✅ | `"Y"/"N"` |
| IncAccuredInAcc | integer | ❌ | **− to +** |
| IncOfferedAmt | integer | ❌ | **− to +** |
| IncOfferedSch | string (enum) | ❌ | `"SA"/"HP"/"CG"/"OS"/"EI"/"NI"` |
| IncOfferedSchNo | string | ❌ | maxLength:50 |

### 23i. DetailsOfTrustOutIndiaTrustee
| Field | Type | Mandatory |
|---|---|---|
| CountryName, CountryCodeExcludingIndia, ZipCode | | ✅ |
| NameOfTrust, AddressOfTrust | string | ✅ |
| NameOfOtherTrustees, AddressOfOtherTrustees | string | ✅ |
| NameOfSettlor, AddressOfSettlor | string | ✅ |
| NameOfBeneficiaries, AddressOfBeneficiaries | string | ✅ |
| DateHeld | string | ✅ | YYYY-MM-DD |
| IncDrvTaxFlag | string (enum) | ✅ | `"Y"/"N"` |
| IncDrvFromTrust | integer | ❌ | **− to +** |
| IncOfferedAmt | integer | ❌ | **− to +** |
| IncOfferedSch | string (enum) | ❌ | `"SA"/"HP"/"CG"/"OS"/"EI"/"NI"` |
| IncOfferedSchNo | string | ❌ | maxLength:50 |

### 23j. DetailsOfOthSourcesIncOutsideIndia
| Field | Type | Mandatory |
|---|---|---|
| CountryName, CountryCodeExcludingIndia, ZipCode | | ✅ |
| NameOfPerson, AddressOfPerson | string | ✅ |
| IncDerived | integer | ❌ | **− to +** |
| NatureOfInc | string | ✅ | maxLength:100 |
| IncDrvTaxFlag | string (enum) | ✅ | `"Y"/"N"` |
| IncOfferedAmt | integer | ❌ | **− to +** |
| IncOfferedSch | string (enum) | ❌ | `"SA"/"HP"/"CG"/"OS"/"EI"/"NI"` |
| IncOfferedSchNo | string | ❌ | maxLength:50 |

---

## 24. Schedule5A2014 — Portuguese Civil Code
**JSON Path:** `ITR.ITR2.Schedule5A2014`

| Field | Type | Mandatory | Constraints |
|---|---|---|---|
| NameOfSpouse | string | ✅ | maxLength:125 |
| PANOfSpouse | string | ✅ | `[A-Z]{5}[0-9]{4}[A-Z]` |
| AadhaarOfSpouse | string | ❌ | `[0-9]{12}` |
| HPHeadIncome, CapGainHeadIncome, OtherSourcesHeadIncome, TotalHeadIncome | Sch5AIncType | ✅ | Each: {IncRecvdUndHead (0–max), AmtApprndOfSpouse (− to +), AmtTDSDeducted (− to +), TDSApprndOfSpouse (− to +)} |

---

## 25. ScheduleAL — Assets & Liabilities (>₹50L)
**JSON Path:** `ITR.ITR2.ScheduleAL`

| Field | Type | Mandatory |
|---|---|---|
| ImmovableDetails | array | ❌ |
| MovableAsset | object | ✅ |
| LiabilityInRelatAssets | integer | ✅ (0–max) |

**ImmovableDetails array item:** {Description (maxLength:25), AddressAL, Amount (0–max)}

**MovableAsset:**
| Field | Type | Mandatory |
|---|---|---|
| DepositsInBank | integer | ✅ (0–max) |
| SharesAndSecurities | integer | ✅ |
| InsurancePolicies | integer | ✅ |
| LoansAndAdvancesGiven | integer | ✅ |
| CashInHand | integer | ✅ |
| JewelleryBullionEtc | integer | ✅ |
| ArchCollDrawPaintSulpArt | integer | ✅ |
| VehiclYachtsBoatsAircrafts | integer | ✅ |

---

## 26. PartB-TI — Computation of Total Income
**JSON Path:** `ITR.ITR2.PartB-TI`
**Required:** ✅ Yes

| Field | Type | Mandatory | Notes |
|---|---|---|---|
| Salaries | integer | ✅ | 0–max |
| IncomeFromHP | integer | ✅ | 0–max |
| CapGain | object | ✅ | ShortTerm, LongTerm, ShortTermLongTermTotal, CapGains30Per115BBH, TotalCapGains (all 0–max) |
| IncFromOS | object | ✅ | OtherSrcThanOwnRaceHorse, IncChargblSplRate, FromOwnRaceHorse, TotIncFromOS |
| TotalTI | integer | ✅ | 0–max |
| CurrentYearLoss | integer | ✅ | From CYLA, 0–max |
| BalanceAfterSetoffLosses | integer | ✅ | 0–max |
| BroughtFwdLossesSetoff | integer | ✅ | From BFLA, 0–max |
| GrossTotalIncome | integer | ✅ | 0–max |
| IncChargeTaxSplRate111A112 | integer | ✅ | 0–max |
| DeductionsUnderScheduleVIA | integer | ✅ | 0–max |
| TotalIncome | integer | ✅ | 0–max |
| IncChargeableTaxSplRates | integer | ✅ | From SI total(i), 0–max |
| NetAgricultureIncomeOrOtherIncomeForRate | integer | ✅ | From EI, 0–max |
| AggregateIncome | integer | ✅ | 0–max |
| LossesOfCurrentYearCarriedFwd | integer | ✅ | From CFL, 0–max |
| DeemedIncomeUs115JC | integer | ✅ | 0–max |

---

## 27. PartB_TTI — Computation of Tax Liability
**JSON Path:** `ITR.ITR2.PartB_TTI`
**Required:** ✅ Yes

| Field | Type | Mandatory | Notes |
|---|---|---|---|
| TaxPayDeemedTotIncUs115JC | integer | ✅ | 0–max |
| Surcharge | integer | ✅ | 0–max |
| HealthEduCess | integer | ✅ | 0–max |
| TotalTaxPayablDeemedTotInc | integer | ✅ | 0–max |
| ComputationOfTaxLiability | object | ✅ | See sub-objects |
| TaxPaid | object | ✅ | |
| Refund | object | ✅ | |
| AssetOutIndiaFlag | string (enum) | ✅ | `"YES"`, `"NO"` |

### ComputationOfTaxLiability
| Sub-object | Fields |
|---|---|
| TaxPayableOnTI | TaxAtNormalRatesOnAggrInc, TaxAtSpecialRates, RebateOnAgriInc, TaxPayableOnTotInc (all 0–max) |
| Rebate87A | integer 0–max |
| TaxPayableOnRebate | integer 0–max |
| Surcharge25ofSI, SurchargeOnAboveCrore (after marginal) | integer 0–max |
| Surcharge25ofSIBeforeMarginal, SurchargeOnAboveCroreBeforeMarginal | integer 0–max |
| TotalSurcharge, EducationCess | integer 0–max |
| GrossTaxLiability, GrossTaxPayable | integer 0–max |
| GrossTaxPay | TaxInc17, TaxDeferred17, TaxDeferredPayableCY (all 0–max) |
| CreditUS115JD, TaxPayAfterCreditUs115JD | integer 0–max |
| TaxRelief | Section89, Section90, Section91, TotTaxRelief (all 0–max) |
| NetTaxLiability | integer 0–max |
| IntrstPay | IntrstPayUs234A, IntrstPayUs234B, IntrstPayUs234C, LateFilingFee234F (max:5000), FeeFurnish234I (max:5000), TotalIntrstPay |
| AggregateTaxInterestLiability | integer 0–max |

### TaxPaid
| Field | Type |
|---|---|
| TaxesPaid | {AdvanceTax, TDS, TCS, SelfAssessmentTax, TotalTaxesPaid} all 0–max |
| BalTaxPayable | 0–max (optional) |

### Refund
| Field | Type |
|---|---|
| RefundDue | integer 0–max |
| BankAccountDtls | {BankDtlsFlag:`"Y"/"N"`, AddtnlBankDetails array of BankDetailType, ForeignBankDetails array of ForeignBankDtls} |

**BankDetailType:** {IFSCCode:`[A-Z]{4}[0][A-Z0-9]{6}`, BankName, BankAccountNo (nonZeroString, maxLength:20), AccountType:`"SB"/"CA"/"CC"/"OD"/"NRO"/"CGAS"/"OTH"`, UseForRefund:`"true"/"false"`}

**ForeignBankDtls:** {SWIFTCode (maxLength:30), BankName, IBAN (maxLength:40), CountryCode}

---

## 28. ScheduleIT — Tax Payments
**JSON Path:** `ITR.ITR2.ScheduleIT`

| Field | Type | Mandatory |
|---|---|---|
| TaxPayment | array (min 1) | ❌ |
| TotalTaxPayments | integer | ✅ (0–max) |

**TaxPayment array item:**
| Field | Type | Mandatory | Constraints |
|---|---|---|---|
| BSRCode | string | ✅ | pattern:`[0-9]{3}[0-9A-Z]{4}` |
| DateDep | string | ✅ | YYYY-MM-DD, on/after 2025-04-01 |
| SrlNoOfChaln | integer | ✅ | 0–99999 |
| Amt | integer | ✅ | 0–99999999999999 |

---

## 29. ScheduleTDS1, ScheduleTDS2, ScheduleTDS3, ScheduleTCS

### ScheduleTDS1 (TDS on Salary)
| Field | Type | Mandatory |
|---|---|---|
| TDSonSalary | array (min 1) | ❌ |
| TotalTDSonSalaries | integer | ✅ |

**TDSonSalary array item:** {EmployerOrDeductorOrCollectDetl {TAN, Name}, IncChrgSal (0–max), TotalTDSSal (0–max)}

### ScheduleTDS2 (TDS Other Than Salary)
| Field | Type | Mandatory |
|---|---|---|
| TDSOthThanSalaryDtls | array (min 1) | ❌ |
| TotalTDSonOthThanSals | integer | ✅ |

**TDSOthThanSalaryDtls array item:**
| Field | Type | Mandatory | Constraints |
|---|---|---|---|
| TDSCreditName | string (enum) | ✅ | `"S"`=Self, `"O"`=OtherPerson |
| PANofOtherPerson, AadhaarOfOtherPerson | string | ❌ | |
| TANOfDeductor | string | ✅ | TAN pattern |
| TDSSection | string (enum) | ✅ | 59 values: `"92A"`–`"96DA"`, `"94BA-P"` |
| DeductedYr | integer (enum) | ❌ | 2008–2024 |
| BroughtFwdTDSAmt | integer | ❌ | 0–max |
| TaxDeductCreditDtls | object | ✅ | TaxDeductedOwnHands/Income/TDS, TaxClaimedOwnHands/Income/TDS, TaxClaimedSpouseOthPrsnPAN, SpouseOthPrsnAadhaar |
| GrossAmount | integer | ❌ | 0–max |
| HeadOfIncome | string (enum) | ❌ | `"HP"/"CG"/"OS"/"EI"/"NA"` |
| AmtCarriedFwd | integer | ✅ | 0–max |

### ScheduleTDS3 (TDS by Buyer/Tenant)
| Field | Type | Mandatory |
|---|---|---|
| TDS3onOthThanSalDtls | array (min 1) | ❌ |
| TotalTDS3OnOthThanSal | integer | ✅ |

**TDS3onOthThanSalDtls array item:** Similar to TDS2 but with PANOfBuyerTenant, AadhaarOfBuyerTenant instead of TANOfDeductor, and HeadOfIncome only `"HP"/"CG"/"OS"/"EI"`.

### ScheduleTCS
| Field | Type | Mandatory |
|---|---|---|
| TCS | array (min 1) | ❌ |
| TotalSchTCS | integer | ✅ |

**TCS array item:**
| Field | Type | Mandatory | Constraints |
|---|---|---|---|
| TCSCreditOwner | string (enum) | ✅ | `"1"`=Self, `"2"`=Spouse/Other |
| PANOfSpouseOrOthrPrsn | string | ❌ | |
| EmployerOrDeductorOrCollectTAN | string | ✅ | TAN pattern, maxLength:10 |
| DeductedYr | integer (enum) | ❌ | 2008–2024 |
| BroughtFwdTDSAmt | integer | ❌ | 0–max |
| TCSCurrFYDtls | object | ❌ | TCSAmtCollOwnHand, TCSAmtCollSpouseOrOthrHand |
| TCSClaimedThisYearDtls | object | ❌ | TCSAmtCollOwnHand, TCSAmtCollSpouseOrOthrHand, PANOfSpouseOrOthrPrsn |
| AmtCarriedFwd | integer | ❌ | 0–max |

---

## 30. Verification
**JSON Path:** `ITR.ITR2.Verification`
**Required:** ✅ Yes

| Field | Type | Mandatory | Constraints |
|---|---|---|---|
| Declaration.AssesseeVerName | string | ✅ | maxLength:125, minLength:1 |
| Declaration.FatherName | string | ✅ | maxLength:125, minLength:1 |
| Declaration.AssesseeVerPAN | string | ✅ | pattern:`[A-Z]{3}[P][A-Z][0-9]{4}[A-Z]` |
| Capacity | string (enum) | ✅ | `"S"`=Self, `"R"`=Representative, `"K"`=Karta, `"A"`=Authorised Signatory |
| Date | string | ❌ | YYYY-MM-DD |
| Place | string | ❌ | maxLength:50 |

---

## 31. TaxReturnPreparer
**JSON Path:** `ITR.ITR2.TaxReturnPreparer`

| Field | Type | Mandatory | Constraints |
|---|---|---|---|
| IdentificationNoOfTRP | string | ✅ | pattern:`[T][0-9]{9}` or `[0-9]{6}` |
| NameOfTRP | string | ✅ | maxLength:125 |
| ReImbFrmGov | integer | ✅ | 0–max, default:0 |

---

## 32. ScheduleESOP — ESOP Tax Deferral
**JSON Path:** `ITR.ITR2.ScheduleESOP`

| Top-Level Field | Type | Mandatory | Constraints |
|---|---|---|---|
| PanofStartUp | string | ✅ | `[A-Z]{5}[0-9]{4}[A-Z]` |
| DPIITRegNo | string | ✅ | pattern:`DIPP[0-9]{3,5}` |
| ScheduleESOP2122_Type through ScheduleESOP2627_Type | object | each has required AssessmentYear | 6 year-specific sub-objects |
| TotalTaxAttributedAmt | integer | ✅ | 0–max |

**Each year sub-object (e.g., ScheduleESOP2122_Type):**
| Field | Type | Mandatory |
|---|---|---|
| AssessmentYear | string (pattern) | ✅ (e.g., `"2021-22"` to `"2026-27"`) |
| TaxDeferredBFEarlierAY | integer | ❌ (0–max) |
| ScheduleESOPEventDtls | object | ❌ |
| TotalTaxAttributedAmt{yr} | integer | ❌ (0–max) |
| TaxPayableCurrentAY | integer | ❌ (0–max) |
| BalanceTaxCF | integer | ❌ (0–max) |

**ScheduleESOPEventDtls:**
| Field | Type | Mandatory | Constraints |
|---|---|---|---|
| SecurityType | string (enum) | ❌ | `"FS"`=FullySold, `"PS"`=PartlySold, `"NS"`=NotSold |
| ScheduleESOPEventDtlsType | array | ❌ | Items:{Date, TaxAttributedAmt (0–max)} |
| CeasedEmployee | string (enum) | ❌ | `"Y"/"N"` |
| DateOfCeasing | string | ❌ | YYYY-MM-DD |

**Note:** ScheduleESOP2627_Type is simplified — only AssessmentYear (`"2026-27"`) and BalanceTaxCF.

---

## Key Enum Lookups

### State Codes
| Code | State | Code | State |
|---|---|---|---|
| 01 | Andaman & Nicobar | 20 | Manipur |
| 02 | Andhra Pradesh | 21 | Meghalaya |
| 03 | Arunachal Pradesh | 22 | Mizoram |
| 04 | Assam | 23 | Nagaland |
| 05 | Bihar | 24 | Odisha |
| 06 | Chandigarh | 25 | Puducherry |
| 07 | Dadra & Nagar Haveli | 26 | Punjab |
| 08 | Daman & Diu | 27 | Rajasthan |
| 09 | Delhi | 28 | Sikkim |
| 10 | Goa | 29 | Tamil Nadu |
| 11 | Gujarat | 30 | Tripura |
| 12 | Haryana | 31 | Uttar Pradesh |
| 13 | Himachal Pradesh | 32 | West Bengal |
| 14 | Jammu & Kashmir | 33 | Chhattisgarh |
| 15 | Karnataka | 34 | Uttarakhand |
| 16 | Kerala | 35 | Jharkhand |
| 17 | Lakshadweep | 36 | Telangana |
| 18 | Madhya Pradesh | 37 | Ladakh |
| 19 | Maharashtra | 99 | State outside India |

### Important Country Codes (for common reference)
1=Canada, 2=USA, 5=Italy, 14=Portugal, 20=Egypt, 28=South Africa, 30=Greece, 31=Netherlands, 32=Belgium, 33=France, 35=Spain, 40=Romania, 41=Switzerland, 43=Austria, 44=UK, 45=Denmark, 46=Sweden, 47=Norway, 48=Poland, 49=Germany, 52=Mexico, 55=Brazil, 57=Colombia, 60=Malaysia, 61=Australia, 63=Philippines, 64=New Zealand, 65=Singapore, 66=Thailand, 81=Japan, 82=South Korea, 84=Vietnam, 86=China, 90=Turkey, 91=India, 92=Pakistan, 94=Sri Lanka, 95=Myanmar, 98=Iran, 212=Morocco, 234=Nigeria, 351=Portugal*, 352=Luxembourg, 353=Ireland, 354=Iceland, 355=Albania, 357=Cyprus, 358=Finland, 359=Bulgaria, 370=Lithuania, 371=Latvia, 372=Estonia, 373=Moldova, 374=Armenia, 375=Belarus, 376=Andorra, 377=Monaco, 378=San Marino, 380=Ukraine, 381=Serbia, 382=Montenegro, 385=Croatia, 386=Slovenia, 389=North Macedonia, 420=Czechia, 421=Slovakia, 423=Liechtenstein, 880=Bangladesh, 886=Taiwan, 960=Maldives, 961=Lebanon, 962=Jordan, 963=Syria, 964=Iraq, 965=Kuwait, 966=Saudi Arabia, 967=Yemen, 968=Oman, 970=Palestine, 971=UAE, 972=Israel, 973=Bahrain, 974=Qatar, 975=Bhutan, 976=Mongolia, 977=Nepal, 992=Tajikistan, 993=Turkmenistan, 994=Azerbaijan, 995=Georgia, 996=Kyrgyzstan, 998=Uzbekistan, 9999=Others, 9998=Not Applicable
> *Note: 351 actually appears as 14 for Portugal in this schema (14 is the enum value)

---

## Negative Number Support Summary

Fields that can be **negative**:

| Schedule | Fields with Negative Range |
|---|---|
| ScheduleHP | PassThroghIncome, TotalIncomeChargeableUnHP, HPSNo, IncomeOfHP |
| ScheduleCGFor23 | Balance, STCGonImmvblPrprty, LTCGonImmvblPrprty, CapgainonAssets, NRITaxSTTPaid/NotPaid, PassThrInc*, TotalAmtNotTax/Tax DTAA, CapitalLossBuyBack, TotalSTCG/TotalLTCG, LTCGonImmvblPrprtyBE, TaxSec1121aiiB/TaxSec1121a/ExcessAmtSec1121a |
| Schedule112A/115AD | Balance, TotalBalance |
| ScheduleOS | GrossIncChrgblTaxAtAppRate, InterestGross, NatofPassThrghIncome, AmtNotDeductibleUs58, ProfitChargTaxUs59, BalanceNoRaceHorse, BalanceOwnRaceHorse |
| ScheduleSPI | AmtIncluded |
| SchedulePTI | NetIncomeLoss, AmountOfInc (in OS23FBB) |
| ScheduleFSI/TR1 | AmtTaxRefunded |
| ScheduleFA (all subsections) | PeakBalance, ClosingBalance, totals for equity/debt, IncFromInt/IncDrvProperty/IncDrvAsset, IncTaxAmt, IncAccuredInAcc, IncOfferedAmt, IncDrvFromTrust, IncDerived |
| Schedule5A2014 | AmtApprndOfSpouse, AmtTDSDeducted, TDSApprndOfSpouse |
| ScheduleAMT | TotalIncItemPartBTI, DeductionClaimUndrAnySec |
| PartB-TI | IncomeFromHP (0+ only), TotalIncome, AggregateIncome |
| DTAA amounts | DTAAamt, applicable rates |

---

## Common Patterns / Regex

| Pattern | Used For |
|---|---|
| `[A-Z]{5}[0-9]{4}[A-Z]` | PAN |
| `[A-Z]{3}[P][A-Z][0-9]{4}[A-Z]` | Verification PAN (4th char must be 'P') |
| `[A-Z]{4}[0-9]{5}[A-Z]` | TAN |
| `[0-9]{12}` | Aadhaar |
| `[1-9][0-9]{5}` / `[1-9]{1}[0-9]{5}` | Pin code |
| `([12]\d{3}-(0[1-9]\|1[0-2])-(0[1-9]\|[12]\d\|3[01]))` | Date YYYY-MM-DD |
| `[A-Z]{4}[0][A-Z0-9]{6}` | IFSC code |
| `IN[a-zA-Z]{2}FP[0-9]{6}` | SEBI FPI registration |
| `[S][W][0-9]{8}` | Software vendor ID |
| `[T][0-9]{9}\|[0-9]{6}` | TRP ID |
| `DIPP[0-9]{3,5}` | DPIIT registration |
| `[0-9]{15}` | Return receipt/acknowledgment number |
| `[0-9]{3}[0-9A-Z]{4}` | BSR code |
