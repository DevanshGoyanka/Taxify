# Taxify Frontend vs CBDT/ITD AY 2026-27 — Complete Field Audit

**Audit date:** 8 August 2026  
**Project:** `C:\Users\Devansh\Desktop\Taxify`  
**Scope:** Current implemented **frontend only** (`frontend/src`)  
**Authority:** Four official AY 2026-27 V1.1 JSON schemas and four official validation-rule PDFs in `Reference Docs by CBDT & ITD`  
**Companion field matrix:** `CBDT_FRONTEND_FIELD_MATRIX_AY2026_27.csv` (6,894 schema nodes)

---

## 1. Executive verdict

The present frontend is **not field-complete for any of ITR-1, ITR-2, ITR-3, or ITR-4**.

It is a useful common-income draft/computation interface with good work around salary, house property, ordinary other-source income, common deductions, TDS/challans, bank accounts, and restricted section 112A transactions. It is not yet a form-specific implementation of every mandatory and optional field in the official schemas.

### Form readiness

| Form | Top-level nodes | Required top-level nodes | Frontend conclusion |
|---|---:|---:|---|
| ITR-1 | 28 | 9 | Broad ordinary-case coverage, but filing status, verification, Schedule 80GGA/80GGC, TDS3 and many nested optional/conditional fields are incomplete. |
| ITR-2 | 46 | 8 | Common editor only. Major schedules including FA, FSI, TR, SPI, PTI, AL, AMT/AMTC, ESOP and much of full CG are absent. |
| ITR-3 | 69 | 12 | No operational ITR-3 frontend. Required Part A business, balance sheet, P&L and full Schedule BP are absent; official export is explicitly unavailable. |
| ITR-4 | 29 | 9 | Partial ordinary-income interface, but Schedule BP is materially incomplete: no 44AE, no 44AD 6%/8% receipt split, no proper 44ADA split, business identity/GST/financial particulars absent. |

### Schedule-level status counts

| Form | Present | Partial | Missing | Incorrect | Derived/System |
|---|---:|---:|---:|---:|---:|
| ITR-1 | 3 | 16 | 3 | 1 | 5 |
| ITR-2 | 2 | 16 | 20 | 1 | 7 |
| ITR-3 | 0 | 24 | 38 | 2 | 5 |
| ITR-4 | 0 | 19 | 5 | 1 | 4 |

> These are schedule-level classifications. The companion CSV accounts for every expanded schema node, including nested optional fields, array rows, constraints, and inherited schedule status.

---

## 2. Audit method

Every official property was assessed for:

1. Official schema path.
2. Required/optional status in its parent.
3. Type and constraints: enum, pattern, minimum/maximum, length, cardinality and date restrictions.
4. Whether the value is taxpayer-entered or legitimately generated/calculated.
5. Presence of an active frontend control—not merely a TypeScript interface, registry label, or backend field.
6. Conditional visibility and repeatable-row support.
7. Frontend validation and relevant official validation-PDF rules.

### Status definitions

- **Present:** material taxpayer inputs are available with substantially correct semantics/cardinality.
- **Partial:** only a subset exists, or conditions, rows, constraints, enum mapping, or details are incomplete.
- **Missing:** no active taxpayer-facing control.
- **Incorrect:** current UI/model materially conflicts with the official schema or rule.
- **Derived/System:** manual entry is not normally appropriate; the value should be computed/generated.

---

## 3. Frontend architecture findings

### 3.1 One shared editor is used for all forms

The frontend always renders the same ten tabs:

1. Personal Info
2. Salary Income
3. House Property
4. Capital Gains
5. Business or Profession
6. Other Sources
7. Exempt Income
8. Deductions
9. TDS & Advance Tax
10. Tax Computation

Evidence: `frontend/src/pages/ITRComputationPage.tsx:1472-1483,2026-2038`.

There is no separate full schedule workflow for ITR-2, ITR-3, or ITR-4. The schedule checklist is informational and does not render the missing editors.

### 3.2 Schedule registry is not implementation

`frontend/src/domain/scheduleRegistry.ts` identifies many schedules as partial or missing, but it only drives badges/checklists. It does not create taxpayer controls or block incompatible forms.

### 3.3 Canonical interfaces are richer than rendered UI

Several fields exist in `domain/returns/types.ts` or component interfaces but are not rendered. Interface presence was not counted as frontend implementation. Important examples:

- Business identities, GST turnover, financial particulars and 44AE vehicles.
- TCS canonical credits.
- Filing verification fields.
- House-property country, owner details, co-owner Aadhaar, multiple home loans and tenant Aadhaar.
- Dividend quarterly breakup and company PAN/TAN.
- Interest account/institution details.

### 3.4 Form blockers are advisory

Users can select a form despite blockers, and the selected form is saved. Evidence: `ITRComputationPage.tsx:1522-1538,578-580`.

### 3.5 ITR-3 is selectable but not exportable

The frontend explicitly blocks ITR-3 draft/official CBDT JSON generation. Evidence: `ITRComputationPage.tsx:656-667`.

---

## 4. Cross-form critical defects

### C-01 — Generic `Field` ignores semantic input type

The helper receives `type="date"`, `email`, `tel`, etc., but emits `input type="text"`. Evidence: `ITRComputationPage.tsx:2201-2257`.

Impact:

- No browser date/email/tel validation.
- Required markers are cosmetic.
- No reusable schema min/max, pattern, maxLength, enum or date-bound support.

### C-02 — Local Save validation is very narrow

`validatePhase1Payload()` validates selected donation, 80C, 80D, loan, bank and advance-tax fields, but not the complete core return. Missing local checks include:

- Taxpayer name/PAN/mobile/email/DOB/Aadhaar.
- Employer rows and salary evidence.
- House-property shares, PAN relationships, unrealized rent and date rules.
- Capital-gain dates/asset-specific schedules.
- Business presumptive thresholds.
- TDS/SAT/TCS relationships.
- Filing status, notices, representative assessee and verification.
- Form-specific mandatory/conditional schedules.

Evidence: `ITRComputationPage.tsx:56-98`.

### C-03 — Save and Validate have different gates

Save runs only narrow local validation. The separate Validate action calls the backend validator. Therefore a draft can be saved with official Category-A violations.

### C-04 — Agricultural income uses inconsistent keys

- Eligibility/default data uses `agriculturalIncome`.
- Schedule EI edits `agricultureIncome` and `agricultureExpenses`.

Evidence: `ITRComputationPage.tsx:179,1281,2070-2072`.

This can split eligibility from Schedule EI reporting and can double count/omit values.

### C-05 — Form leakage

- Business fields appear on ITR-1/2.
- VDA/winnings/gifts and multiple properties remain available regardless of form eligibility.
- Missing schedules do not block editing or form selection.
- ITR-1 property UI allows two properties while eligibility blocks more than one.

### C-06 — Validation can be stricter than the official schema for the wrong reasons

Local validation requires extra evidence fields not required by the relevant official JSON rows, for example institution PAN/date on 80C and lender PAN on deduction loans. Extra internal evidence is acceptable, but it should not make a schema-valid return impossible.

---

# 5. ITR-1 detailed audit

## 5.1 Top-level reconciliation

| Official node | Required | Status | Detailed finding |
|---|---:|---|---|
| `CreationInfo` | Yes | Derived/System | Correctly system-owned. |
| `Form_ITR1` | Yes | Derived/System | Form/AY/version should be fixed metadata. |
| `PersonalInfo` | Yes | Partial | Basic identity/contact/address exists; split name, secondary/alternate address, secondary contacts and strict constraints are incomplete. |
| `FilingStatus` | Yes | Partial | Only four filing sections and basic regime/status fields. Seventh-proviso, notice, revised-return and representative branches absent. |
| `ITR1_IncomeDeductions` | Yes | Partial | Common heads exist; official nested salary, exempt-income, OS and deduction details incomplete. |
| `ITR1_TaxComputation` | Yes | Derived/System | Backend-calculated display is appropriate. |
| `TaxPaid` | Yes | Derived/System | Aggregate totals can be derived from credit schedules. |
| `Refund` | Yes | Partial | Structured bank manager exists; duplicate legacy refund state and incomplete constraints remain. |
| `Schedule80G` | No | Partial | Detailed rows exist, but all conditional fields and reconciliation rules are not enforced. |
| `Schedule80GGA` | No | Missing | No qualifying-clause/scientific-rural donation editor. |
| `Schedule80GGC` | No | Missing | No political-party donation editor. |
| `Schedule80D` | No | Present | Four health categories and policy rows are available; statutory validation still depends on backend. |
| `Schedule80DD` | No | Partial | Core selectors exist; dependent/certificate/UDID conditionality incomplete. |
| `Schedule80U` | No | Partial | Core selectors exist; certificate/UDID conditionality incomplete. |
| `Schedule80E` | No | Partial | Repeatable loan editor, but exact official requirements and conditions are incomplete. |
| `Schedule80EE` | No | Partial | Loan editor exists; eligibility constraints incomplete. |
| `Schedule80EEA` | No | Partial | Loans and stamp value exist; qualifying conditions incomplete. |
| `Schedule80EEB` | No | Partial | Vehicle registration exists; remaining conditions incomplete. |
| `Schedule80C` | No | Present | Repeating identification and amount rows exist. |
| `ScheduleEA10_13A` | No | Partial | HRA facts exist per employer, not as complete official schedule rows. |
| `TDSonSalaries` | No | Partial | Salary TDS capture/import exists; official row contract is indirect. |
| `TDSonOthThanSals` | No | Partial | General TDS abstraction; exact enums/year/claim rules incomplete. |
| `ScheduleTDS3Dtls` | No | Missing | No dedicated Form 16C/tenant-TDS schedule. |
| `ScheduleTCS` | No | Partial | Canonical model/import possible; no complete dedicated editor. |
| `TaxPayments` | No | Present | BSR/date/challan/amount rows exist. |
| `LTCG112A` | No | Partial | Restricted transaction capture exists; full official row/aggregate semantics incomplete. |
| `Verification` | Yes | Incorrect | Father name exists; verifier name/PAN/capacity/place/declaration workflow absent. |
| `TaxReturnPreparer` | No | Missing | No TRP identification/name/reimbursement UI. |

## 5.2 Personal information gaps

Official fields not fully supported:

- `AssesseeName.FirstName`, `MiddleName`, `SurNameOrOrgName` are collapsed into one `name` field.
- `SecondaryAdd` flag is absent.
- `AlternateAddress.*` is absent.
- Secondary email/mobile fields are absent.
- State code `99` (foreign) is omitted from the state selector.
- PIN versus foreign ZIP conditional behavior is absent.
- PAN, Aadhaar, DOB, email and mobile patterns are not generally enforced.
- DOB maximum `2026-03-31` is not blocked.

## 5.3 Filing status gaps

Missing or incomplete taxpayer inputs:

- Filing sections 142(1), 148, 153C and 139(9).
- `SeventhProvisio139`.
- Foreign travel flag and amount (minimum ₹2 lakh when applicable).
- Electricity flag and amount (minimum ₹1 lakh when applicable).
- Clause-(iv) repeating nature/amount rows.
- Original return 15-digit acknowledgment and filing date.
- Notice/DIN and notice date.
- Representative flag and representative name/email/mobile.

## 5.4 Salary

Strengths:

- Repeatable employers.
- Employer/TAN/nature.
- Section 17(1), 17(2), 17(3) values.
- HRA, LTA, retirement receipts, section 10(14), section 16, TDS and employer NPS.

Gaps/defects:

- Official allowance-nature enumeration is represented by bespoke fields rather than complete repeatable official rows.
- No full detailed perquisite schedule.
- TAN and field maxima are weakly enforced.
- UI hint says professional-tax maximum ₹2,500, while the official schema field permits up to ₹5,000.

Evidence: `components/EmployerEntryManager.tsx:243-344`.

## 5.5 House property

Strengths:

- Property type/address/ownership/share/co-owners.
- Rent and municipal values.
- Tenant name/PAN.
- Interest and basic loan evidence.
- Backend computation display.

Missing/incomplete:

- Co-owner Aadhaar and serial number.
- Tenant Aadhaar and PAN/TAN alternative.
- Official state/country behavior.
- Property-owner “other” details.
- Full Section 24(b) repeatable rows with source, total loan and outstanding amount.
- Share sum = 100 validation.
- Assessee PAN must differ from co-owner PAN.
- Co-owned/not-co-owned share conditions.
- Unrealized rent limits.

## 5.6 Other sources and exempt income

Missing/incomplete:

- Official taxable provident-fund-interest categories.
- Dividend quarterly breakup.
- Duplicate income-tax-refund-interest prevention.
- Official repeatable Schedule EI category/subcategory rows.
- Agricultural income limit for ITR-1 must be enforced.
- Shared editor permits ITR-1-ineligible winnings/gifts instead of form-specific suppression/blocking.

## 5.7 Deductions and donations

- 80C and 80D are the strongest detailed schedules.
- 80DD/80U require positive-claim conditional validation for Form 10-IA, UDID and identity details.
- 80DDB disease/category details are not conditionally required locally.
- PRAN is not required when 80CCD(1B) is positive.
- 80GG/Form 10BA is absent.
- 80CCC identifier rows are absent.
- 80G donee PAN is not compared with taxpayer/verifier PAN.
- 80GGA and 80GGC are entirely absent.

## 5.8 Verification

Official required facts include verifier name, father name, verifier PAN, capacity and place. Only father name is directly captured. This is a blocking gap.

---

# 6. ITR-2 detailed audit

## 6.1 Top-level reconciliation

| Official node | Status | Key finding |
|---|---|---|
| `CreationInfo`, `Form_ITR2` | Derived/System | Correctly generated in principle. |
| `PartA_GEN1` | Partial | Basic personal fields only; ITR-2-specific residence, director, shares, representative, FII and filing branches missing. |
| `ScheduleS` | Partial | Strong common salary editor; official detailed allowance, 89A/ESOP and other branches incomplete. |
| `ScheduleHP` | Partial | Detailed common property editor; official row fields/constraints incomplete. |
| `ScheduleCGFor23` | Partial | Restricted generic transaction editor is far smaller than full Schedule CG. |
| `Schedule112A` | Partial | Some scrip evidence exists; full official row/totals incomplete. |
| `Schedule115AD` | Missing | No FII/FPI capital-gain schedule. |
| `ScheduleVDA` | Partial | Aggregate `vdaGains`, not per-transfer Schedule VDA. |
| `ScheduleOS` | Partial | Common categories only; many statutory branches absent. |
| `ScheduleCYLA`, `ScheduleBFLA` | Derived/System | Calculation is appropriate, but source facts are incomplete. |
| `ScheduleCFL` | Partial | Aggregate losses only; no AY-wise ledger. |
| `ScheduleVIA` | Partial | Common deductions only. |
| `Schedule80C`, `Schedule80D` | Present | Main repeatable entry exists. |
| `Schedule80G` | Partial | Complete statutory validation not enforced. |
| `Schedule80GGA`, `Schedule80GGC` | Missing | No editors. |
| `Schedule80DD`, `80U`, `80E`, `80EE`, `80EEA`, `80EEB` | Partial | Common details exist, conditions incomplete. |
| `ScheduleAMT`, `ScheduleAMTC` | Missing | No AMT/credit editor. |
| `ScheduleSPI` | Missing | No clubbing editor. |
| `ScheduleSI` | Derived/System | Totals can be derived only after missing source schedules are implemented. |
| `ScheduleEI` | Incorrect | Fixed amount fields do not match full rows; agricultural key mismatch. |
| `SchedulePTI` | Missing | No pass-through income editor. |
| `ScheduleFSI`, `ScheduleTR1`, `ScheduleFA` | Missing | No foreign income, tax relief or asset schedules. |
| `Schedule5A2014` | Missing | No Portuguese Civil Code schedule. |
| `ScheduleAL` | Missing | No assets/liabilities schedule. |
| `PartB-TI`, `PartB_TTI` | Derived/System | Calculated, but source schedules incomplete. |
| `ScheduleIT` | Present | Challan rows exist. |
| `ScheduleTDS1`, `ScheduleTDS2`, `ScheduleTCS` | Partial | Generic abstraction, not exact official schedules. |
| `ScheduleTDS3` | Missing | No dedicated editor. |
| `Verification` | Incorrect | No complete declaration/capacity/place workflow. |
| `TaxReturnPreparer` | Missing | No editor. |
| `ScheduleESOP` | Missing | No deferred startup ESOP schedule. |

## 6.2 Part A critical omissions

Missing ITR-2-specific inputs include:

- Status enum `I|H` as a controlled value.
- Filing section 92CD.
- ₹1 crore deposit/seventh-proviso branch.
- Exact residential enum and condition code.
- Stay days in current year and preceding four years.
- Section 115H benefit flag.
- Prior foreign tax jurisdictions.
- Portuguese Civil Code flag.
- FII/FPI flag and SEBI registration.
- Director company/DIN/share rows.
- Unlisted-equity opening/acquisition/transfer/closing rows.
- LEI and validity date.

The frontend asks only Yes/No for director and unlisted shares, but official validation makes detailed rows mandatory when Yes.

## 6.3 Residential-status value mismatch

Official values are `RES`, `NRI`, `NOR`; frontend uses `ROR`, `RNOR`, `NR`. Unless explicitly transformed before official serialization, these are invalid schema values.

## 6.4 Capital gains

The official Schedule CG includes many branches absent from the current restricted 112A-oriented editor:

- Land/building and stamp-duty value.
- Unlisted shares and valuation rules.
- Bonds/debentures, debt funds, jewellery and other assets.
- Depreciable assets.
- Nonresident and FII calculations.
- DTAA country/article/rate details.
- Section 54-series exemption rows with dates/amounts.
- Rate buckets and quarterly accrual tables.

Schedule VDA requires acquisition date, transfer date, income head, cost, consideration and gain per transfer; one aggregate is insufficient.

## 6.5 Other Sources

Missing branches include:

- Machinery/building letting.
- Full gifts/property valuation facts.
- Race-horse schedules.
- Unexplained income sections.
- Section 89A notified accounts.
- DTAA rows.
- Complete section 57/58/59 adjustments.
- Quarterly dividend details.

## 6.6 Loss schedules

Current aggregate `bfLossHP`, `bfLossBusiness`, `bfLossSTCG`, `bfLossLTCG` and speculation fields do not satisfy AY-wise CFL requirements. The UI must capture assessment year, category/head, original filing date/eligibility, amount brought forward, amount set off and balance.

## 6.7 Major entirely missing schedules

- SPI: specified person, PAN, relationship, head and clubbed amount.
- PTI: entity/PAN/section/head/rate income/loss/TDS.
- FSI: country/TIN/head/source/foreign income/tax paid.
- TR1: country/TIN/treaty article/relief section/amount.
- FA: foreign accounts, interests, property, trusts, signing authority and income.
- 5A: spouse and head-wise apportionment.
- AL: immovable/movable/financial assets and liabilities.
- AMT/AMTC.
- ESOP deferred-tax details.

---

# 7. ITR-3 detailed audit

## 7.1 Required top-level blocks

| Required block | Status | Finding |
|---|---|---|
| `CreationInfo` | Derived/System | Appropriate system metadata. |
| `Form_ITR3` | Derived/System | Appropriate fixed metadata. |
| `PartA_GEN1` | Partial | Shared personal/filer subset only. |
| `PartA_GEN2` | Missing | No business nature, audit liability, accountant/report editor. |
| `PARTA_BS` | Missing | No balance-sheet editor. |
| `PARTA_PL` | Partial | One net-profit scalar is not the official P&L. |
| `ITR3ScheduleBP` | Partial | Scheme/turnover/declared income only; full adjustment schedule absent. |
| `ScheduleCYLA` | Incorrect | UI labels aggregate brought-forward losses, not current-year head-wise adjustment. |
| `ScheduleBFLA` | Partial | No AY/head/category ledger. |
| `PartB-TI` | Derived/System | Calculated from incomplete inputs. |
| `PartB_TTI` | Derived/System | Calculated from incomplete inputs. |
| `Verification` | Partial | No complete visible workflow. |

No ITR-3 top-level schedule is fully present end-to-end.

## 7.2 Mandatory business/accounting gaps

### Part A GEN2

Missing:

- Nature-of-business codes and rows.
- Audit applicability and clause.
- Accountant name/address/membership/firm registration.
- Audit report date and acknowledgment.
- Other audit report details.
- Presumptive-only declaration.
- Filing due-date conditions and Form 10-IEA cascade.

### Balance Sheet

No editor for:

- Capital/reserves.
- Secured/unsecured loans.
- Deferred tax.
- Current liabilities/provisions.
- Fixed assets/investments.
- Current assets, loans/advances.
- Cash/bank.
- Miscellaneous expenditure.
- Totals and cross-footing.

### P&L / Manufacturing / Trading

No complete editor for revenue, stock, purchases, direct expenses, employee/finance/depreciation/admin expenses, taxes and appropriations. Manufacturing and trading accounts are absent.

### Schedule BP

Only scheme, total turnover, declared income/net-profit and two aggregate losses are captured. Missing adjustment families include sections 28–44, other-head credits, exempt credits, depreciation reconciliation, sections 36/37/40/40A/41/43B, ICDS, 35AD, speculation/specified business and Rule 7/7A/7B/8.

## 7.3 Other missing ITR-3 schedules

- Part A Other Information and Quantitative Details.
- DPM, DOA, depreciation source blocks and deemed CG source evidence.
- ESR, unabsorbed depreciation and ICDS.
- 10AA, 80-IA, 80-IB, 80-IC, 80RA.
- Investment-fund/partnership details and TPSA.
- GSTIN-wise turnover.
- SI, SPI, PTI.
- FSI, TR and FA.
- Schedule AL, 5A and ESOP.
- AMT/AMTC.
- AY-wise CFL.

## 7.4 Incorrect presumptive guidance

The frontend broadly says presumptive income should use ITR-4, but official ITR-3 includes 44AD/44ADA/44AE situations. The recommendation must account for taxpayer eligibility rather than categorically rejecting presumptive ITR-3.

## 7.5 Export readiness

ITR-3 official export is explicitly disabled. Until all required source schedules exist, this is the correct safety behavior and should remain disabled.

---

# 8. ITR-4 detailed audit

## 8.1 Top-level reconciliation

| Official node | Status | Finding |
|---|---|---|
| `CreationInfo`, `Form_ITR4` | Derived/System | Appropriate system metadata. |
| `PersonalInfo` | Partial | Common identity/address only. |
| `FilingStatus` | Partial | Form 10-IEA, seventh-proviso, representative and notice branches incomplete. |
| `IncomeDeductions` | Partial | Common heads exist; nested official rows incomplete. |
| `TaxComputation`, `TaxPaid` | Derived/System | Appropriately calculated. |
| `Refund` | Partial | Bank manager exists, exact official behavior incomplete. |
| `Schedule80G` | Partial | Main donation rows, incomplete official rule coverage. |
| `Schedule80GGC` | Missing | No political contribution editor. |
| `Schedule80DD`, `80U`, `80E`, `80EE`, `80EEA`, `80EEB`, `80C`, `80D` | Partial | Common detail exists; conditions/serialization/validation incomplete. |
| `ScheduleEA10_13A` | Missing | HRA facts are not a full official schedule editor. |
| `TaxExmpIntIncDtls` | Partial | Fixed exempt amounts, not full official details. |
| `LTCG112A` | Partial | Restricted evidence only. |
| `Verification` | Missing | No complete visible declaration workflow. |
| `TaxReturnPreparer` | Missing | No editor. |
| `ScheduleBP` | Incorrect | Materially incomplete and omits 44AE. |
| `ScheduleIT`, `ScheduleTCS`, salary/non-salary TDS | Partial | Generic credit/challan support only. |
| `ScheduleTDS3Dtls` | Missing | No dedicated editor. |

## 8.2 Schedule BP — 44AD

Required material facts missing from active UI:

- Business name.
- Nature/business code.
- Digital/account-payee/electronic receipts.
- Cash/other-mode receipts.
- Income at 6%.
- Income at 8%.
- GSTIN-wise turnover.
- Financial particulars.

Current active fields are only total turnover and declared income. This cannot enforce the official 6%/8% rules.

## 8.3 Schedule BP — 44ADA

Missing:

- Profession name/code/description.
- Digital receipt split.
- Cash/other receipt split.
- GST rows.
- Required financial particulars.

The current declared-income field does not enforce minimum 50% of gross receipts.

## 8.4 Schedule BP — 44AE

There is no active 44AE option or goods-carriage editor. Required facts include:

- Vehicle registration.
- Owned/leased/hired state.
- Heavy/other vehicle type.
- Tonnage.
- Months held.
- Per-vehicle presumptive income.
- Duplicate registration prevention.
- Partner salary/interest reconciliation where applicable.

A dormant model uses a boolean `leasedOrHired`, which cannot represent the official three-way state.

## 8.5 Financial particulars

The official validation rules require financial particulars with turnover. No active UI captures them, despite dormant TypeScript structures.

---

# 9. Validation-rule audit

## 9.1 What is currently enforced locally

- Country/state/PIN presence/syntax.
- Selected 80G donee identity/address/PAN syntax.
- Selected 80C evidence.
- 80D policy evidence.
- Deduction-loan evidence.
- One refund bank and IFSC syntax.
- Advance-tax BSR/date/serial/positive amount.
- Some component normalization and warning messages.

## 9.2 Official rule classes impossible with current UI

### All forms

- Complete representative assessee and verification.
- Secondary/alternate address requirements.
- Donee PAN vs taxpayer/verifier PAN comparison.
- Conditional supporting forms such as 10E, 10BA, 10-IA and 67 where their source schedules are absent.
- Complete new/old-regime stale-value prevention.

### ITR-1

- All filing-status cascades.
- 80GGA/80GGC.
- TDS3.
- Complete 80DD/80U/80DDB conditional requirements.

### ITR-2

- Director/unlisted-share details.
- Full CG rate and quarter reconciliation.
- AY-wise CFL.
- FSI/TR/FA.
- SPI/PTI/AL/AMT/ESOP.

### ITR-3

- Audit applicability/report details.
- BS/P&L/trading/manufacturing arithmetic.
- 44AD/44ADA mode-specific tests and 44AE vehicle tests.
- Form 3CD comparisons.
- Depreciation, ICDS, GST and quantitative-detail reconciliation.

### ITR-4

- 44AD 6%/8% tests.
- 44ADA 50% test with complete receipt evidence.
- All 44AE tests.
- Financial-particulars requirement.

## 9.3 Contradicted states currently allowed

- Empty/invalid core identity can be saved.
- Co-owned shares need not total 100.
- Co-owner PAN can equal taxpayer PAN.
- Co-owned/no-co-owned share conditions can conflict.
- Unrealized rent can exceed gross rent.
- Positive disability deductions can coexist with missing certificates/details.
- PRAN can be absent for a positive 80CCD(1B) claim.
- New-regime hidden deduction values may remain in state.
- Presumptive declared income can be below statutory percentage.
- TDS section choices are not form-specific.

---

# 10. Highest-priority gap list

## Critical

1. Build form-specific schedule routing instead of using only ten shared tabs.
2. Add complete Verification for all forms.
3. Add complete Part A filing-status conditional flows.
4. Implement ITR-2 full CG/112A/115AD/VDA and foreign schedules.
5. Implement ITR-3 Part A GEN2, BS, P&L and full Schedule BP before enabling export.
6. Replace ITR-4 scalar business input with complete 44AD/44ADA/44AE editors.
7. Make form blockers prevent filing/generation, not draft editing.
8. Validate the official artifact against schema and official rules before generation.

## High

9. Add director and unlisted-share detail tables.
10. Add AY-wise loss ledgers.
11. Add 80GGA, 80GGC, 80GG/Form 10BA and 80CCC details.
12. Add TDS3 and dedicated TCS editor.
13. Add FSI/TR/FA/SPI/PTI/AL/AMT/AMTC/ESOP.
14. Fix schema enum/value normalization, especially ITR-2 residential status.
15. Resolve agricultural-income key duplication.
16. Add complete conditional validation for 80DD/80U/80DDB/PRAN.

## Medium

17. Add alternate/secondary address and contacts.
18. Add complete house-property owner/co-owner/tenant/loan rows.
19. Add quarterly dividends and full other-source branches.
20. Remove misleading “CBDT compliant” claims until the corresponding field/rule matrix is green.

---

# 11. Recommended implementation sequence

## Phase 1 — Schema-aware frontend foundation

- Introduce a form/schedule router.
- Create reusable schema-aware controls supporting actual HTML type, required, enum, pattern, lengths, number bounds, date bounds and conditional requiredness.
- Use exact official enums internally or guarantee explicit boundary mapping.
- Add field-path error reporting.

## Phase 2 — Shared mandatory schedules

- Personal information with alternate/secondary address.
- Complete Filing Status.
- Verification and TRP.
- Exact TDS/TCS/IT/Bank schedules.
- Correct form eligibility and blocking behavior.

## Phase 3 — ITR-1 and ITR-4 completion

- Complete ordinary income nested rows.
- 80GGA/80GGC/TDS3.
- Full ITR-4 BP, including 44AE and financial particulars.

## Phase 4 — ITR-2 completion

- Full CG/112A/115AD/VDA.
- CYLA/BFLA/CFL source ledgers.
- SPI/PTI/FSI/TR/FA/AL/5A/AMT/ESOP.

## Phase 5 — ITR-3 completion

- Part A GEN2 and audit details.
- Manufacturing/trading/P&L/BS/OI/QD.
- Full BP adjustment schedules.
- Depreciation, ICDS, GST, partnership and incentive schedules.
- Enable official export only after mandatory-block validation passes.

## Phase 6 — Validation closure

- Map every official Category-A and Category-D rule to frontend, backend or external verification.
- Add automated tests per rule ID.
- Generate official JSON, validate it against V1.1, run rule checks, and block filing on errors.

---

# 12. Companion exhaustive matrix

`CBDT_FRONTEND_FIELD_MATRIX_AY2026_27.csv` contains **6,894 rows**:

| Form | Expanded schema nodes in matrix |
|---|---:|
| ITR-1 | 573 |
| ITR-2 | 2,078 |
| ITR-3 | 3,607 |
| ITR-4 | 636 |

Columns:

- `form`
- `top_level_schedule`
- `schema_path`
- `required_in_parent`
- `schema_type`
- `constraints`
- `description`
- `frontend_status`
- `frontend_evidence`
- `audit_note`

This matrix is the field-by-field accounting artifact. It includes nested arrays and optional fields and should be used as the implementation backlog. A schedule should be promoted from Partial/Missing to Present only after each taxpayer-entered descendant has a correct control, condition, validation, persistence path and official serialization mapping.

---

## 13. Final conclusion

The current frontend is best described as a **backend-assisted tax draft and computation UI**, not a complete AY 2026-27 CBDT return-preparation frontend.

The most mature frontend areas are ordinary salary, house property, basic other sources, 80C/80D, ordinary 80G, TDS/challans, bank accounts and restricted 112A evidence. The principal blockers are form-specific Part A flows, verification, complete capital gains/loss schedules, foreign schedules, ITR-3 accounting/business schedules, and ITR-4 presumptive business details.

**No source code was changed during this audit.** Only this report and the companion CSV audit matrix were created.
