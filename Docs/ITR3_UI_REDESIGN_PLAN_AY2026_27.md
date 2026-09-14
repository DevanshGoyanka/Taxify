# ITR-3 UI Redesign and Implementation Plan — AY 2026-27

**Status:** Phase 3 completed: Audit Information. Phase 4 — Nature of Business or Profession is next.

**Scope:** Redesign the ITR-3 experience for tax professionals against the notified form PDF and official CBDT JSON schema, without modifying ITR-1, ITR-2, or ITR-4 behavior. Every phase must persist through the canonical `ReturnDraft`; browser-only `localStorage` is not an acceptable source of filing data.

## 1. Official source authority

- Form: `Reference Docs by CBDT & ITD/Official ITR FORMS/ITR-3-2026-Eng.pdf`
- Schema: `Reference Docs by CBDT & ITD/Official JSON Schema/ITR-3_2026_Main_V1.1 (2).json`
- Validation rules: `Reference Docs by CBDT & ITD/Official Validations/CBDT_e-filing_ITR-3_Validation Rules_V1.0_AY 26-27 (1).pdf`

The PDF controls user-facing order and arithmetic context. The JSON schema controls exact field names, types, required blocks, enums, and conditional structures. The validation rules control cross-field blocking behavior.

## 2. Design principles for tax professionals

1. **Follow the notified form order**, but present it as a guided workflow rather than a wall of generic fields.
2. **Show applicability before data entry.** Audit status, books, business nature, residence, foreign income/assets, deductions, and filing thresholds determine which schedules appear.
3. **Separate user-entered, imported, and calculated values.** Calculated totals are read-only and show their source schedule.
4. **Use official terminology with plain-language help.** Every field should expose the PDF item/section and the schema path in developer metadata.
5. **Never silently fabricate zeros.** An inapplicable schedule is omitted; a required unanswered field is visibly blocked.
6. **Persist every edit to `ReturnDraft`**, with typed models and round-trip tests.
7. **Preserve other forms.** ITR-1/2/4 components and routes remain unchanged unless a separately reviewed shared-model change is unavoidable.

## 3. Page and schedule roadmap in official PDF order

### Phase 1 — Personal Information (A1–A18) — ✅ COMPLETED

**Completed:** 2026-09-14
**Implementation:** `frontend/src/components/ITR3PersonalInfoPage.tsx`, wired through the ITR-3-only branch in `frontend/src/pages/ITRComputationPage.tsx`.
**Commit:** `16ee72a` (`Implement ITR-3 personal information foundation`)

Schema blocks: `PartA_GEN1.PersonalInfo`, `PartA_GEN1.FilingStatus` foundations, `Verification` foundations.

UI sections delivered:

- **Return profile:** ITR-3, AY 2026-27, Individual/HUF status, name components, PAN, Aadhaar, DOB/date of formation, and father’s name.
- **Primary address:** residence/door, premises, road, locality, city/district, state, country, PIN/ZIP.
- **Secondary address:** explicit Yes/No indicator matching `SecondaryAdd`; alternate address fields appear only when selected.
- **Communication:** country code, mobile, email, secondary mobile/email.
- **Filing identity:** filing section, revised-return details, due date, and tax regime.
- **Verification:** self, representative, Karta, or partner capacity; place/date; declaration acceptance.
- **Bank accounts:** canonical bank-account manager remains available within the ITR-3 page.
- **Professional usability:** official field labels, required markers, format constraints, inline help, and no generic JSON editor.

Isolation guarantee: the existing `PersonalInfoTab` remains the rendering path for ITR-1, ITR-2, and ITR-4. No ITR-1/2/4 component behavior was changed for this page.

Validation completed:

- Frontend production build: passed (`tsc -b && vite build`).
- Affected backend regression tests: **226 passed**.
- `git diff --check`: passed.
- Changes pushed to `origin/devansh-dev`.

Known Phase 1 follow-ups, intentionally deferred to later phases:

- Full ITR-3 filing-status conditional fields, including residential status, seventh-proviso details, Form 10-IEA history, director/partner/PE/SEP/IFSC/FPI/LEI disclosures.
- Typed canonical persistence for the full ITR-3 business workspace and all supporting schedules.
- Complete representative/Karta cross-field validation and backend ITR-3 mapper/schema-validator integration.

### Phase 2 — Filing Status (A19) — ✅ COMPLETED

**Completed:** 2026-09-14**Implementation:** Extended `frontend/src/components/ITR3PersonalInfoPage.tsx` only; ITR-1/2/4 personal-information rendering remains unchanged.

Schema paths: `PartA_GEN1.FilingStatus` and related filing-profile fields already present in the canonical `ReturnDraft`.

Delivered controls:

- Return section, revised-return acknowledgement/date, and notice/order number/date.
- Residential status (`ROR`, `RNOR`, `NR`) with non-resident basis, stay-day counts, foreign residence jurisdictions, and Section 115H Yes/No answer.
- FII/FPI status, SEBI registration number, LEI number, and LEI validity date.
- Seventh-proviso thresholds for current-account deposits, foreign travel, and electricity expenditure, with conditional amount fields and statutory minimums.
- Company-director disclosure rows with company name, domestic/foreign type, PAN, DIN, and removal controls.
- Explicit conditional visibility and canonical `ReturnDraft` updates for all fields.

Validation completed:

- Frontend production build: passed (`tsc -b && vite build`).
- Canonical draft and personal-information regressions: **33 passed**.
- `git diff --check`: passed.

Intentional deferrals to typed-model/backend phases:

- Full partner, PE/SEP, IFSC-unit, foreign-exchange, and other ITR-3-only fields not present in the current canonical frontend model.
- Full unlisted-equity detail rows; the existing canonical type is available but will be completed with the official schema-backed disclosure workflow.
- Form 10-IEA history and all CBDT cross-field validation in the backend mapper/validator.


### Phase 3 — Audit Information (A20) — ✅ COMPLETED

**Completed:** 2026-09-14
**Implementation:** Added canonical `itr3AuditInfo` to frontend/backend `ReturnDraft`, safe factory defaults, loaded-draft normalization, and an isolated ITR-3 Part A A20 audit editor in `frontend/src/components/ITR3PersonalInfoPage.tsx`.

Schema path: `PartA_GEN2.AuditInfo`.

Delivered controls:

- Sections 44AA, 44AB, 92E, and account-audit Yes/No answers.
- Income declared only under presumptive sections.
- Turnover/receipt band and cash-receipt/payment percentages when applicable.
- Section 44AB condition selection and audit-accountant appointment.
- Audit report date, acknowledgement number, auditor/firm name, PAN, and Aadhaar.
- Section 92E audit date and acknowledgement number.
- Conditional visibility and canonical persistence through `ReturnDraft`.

Validation completed:

- Frontend production build: passed (`tsc -b && vite build`).
- Backend canonical draft schema tests: **20 passed**.
- `git diff --check`: passed.

Intentional deferrals:

- Complete backend ITR-3 mapper/validator serialization into `PartA_GEN2`.
- Official audit-detail arrays and all Part A-OI/Part A-QD dependencies.
- Nature-of-business code entry, scheduled for Phase 4.


### Phase 4 — Nature of Business or Profession

Schema path: `PartA_GEN2.NatOfBus`.

A repeatable, searchable official nature-code table with up to the schema-supported number of activities, trade/profession description, primary activity marker, and duplicate-code prevention.

### Phase 5 — Part A-BS

Schema path: `PARTA_BS`.

Tax-professional balance-sheet workspace split into Sources of Funds, Application of Funds, and No-Account-Case. Each group shows subtotals and reconciliation status. Imported opening figures remain traceable; totals are computed and read-only.

### Phase 6 — Part A-Manufacturing Account

Schema path: `ManufacturingAccount`.

Manufacturing-specific opening stock, purchases, direct wages/expenses, factory overheads, closing stock, and cost of goods produced. Applicability is controlled by business nature and user answer.

### Phase 7 — Part A-Trading Account

Schema path: `TradingAccount`.

Revenue, duties/taxes, closing stock, opening stock, purchases, direct expenses, cost of goods produced, gross profit, intraday and F&O turnover/income. Reconciliation to P&L is visible.

### Phase 8 — Part A-P&L

Schema path: `PARTA_PL`.

Credits and debits in the PDF’s sequence, with section-specific disallowance links and separate presumptive tables for 44AD, 44ADA, and 44AE. Net profit before tax is calculated from entered lines and cannot be independently overwritten.

### Phase 9 — Part A-OI

Schema path: `PARTA_OI`.

Accounting method, stock valuation, ICDS deviations, disallowances under sections 14A, 36, 37, 40, 40A, 41, and 43B, and secondary-adjustment trigger. The page becomes mandatory when official audit applicability requires it.

### Phase 10 — Part A-QD

Schema path: `PARTA_QD`.

Separate trading and manufacturing quantitative-detail tables with opening stock, purchases/production, sales/consumption, closing stock, units, and reconciliation warnings.

### Phase 11 — Schedule transition

Display a completion checkpoint for Parts A and the supporting schedules. No JSON block is emitted for the printed banner.

### Phase 12 — Schedule S

Schema path: `ScheduleS`. Reuse typed salary rows, nature-of-salary breakdown, exemptions, section 16 deductions, and 89A relief with reconciliation to employer/Form 16 evidence.

### Phase 13 — Schedule HP

Schema path: `ScheduleHP`. Repeatable property cards, ownership/co-owner detail, rent and municipal values, interest, pass-through income, and computed annual value.

### Phase 14 — Schedule BP

Schema path: `ITR3ScheduleBP`. Replace generic field entry with a structured tax bridge: book profit → additions → deductions → presumptive/speculative/specified business → chargeable business income → intra-head set-off. Every line displays its P&L or supporting-schedule source.

### Phases 15–18 — DPM, DOA, DEP, DCG

Schema paths: `ScheduleDPM`, `ScheduleDOA`, `ScheduleDEP`, `ScheduleDCG`. Block-wise depreciation ledgers with additions by holding period, rates, WDV continuity, transfer rows, and derived summaries. DEP/DCG are computed from DPM/DOA.

### Phase 19 — Schedule ESR

Schema path: `ScheduleESR`. Scientific research expenditure rows, qualifying section, amount debited, eligible deduction, and excess/disallowance reconciliation.

### Phases 20–23 — Schedule CG, 112A, 115AD, VDA

Schema paths: `ScheduleCGFor23`, `Schedule112A`, `Schedule115AD`, `ScheduleVDA`. Typed transaction tables, dates, ISIN/security identifiers, cost basis, grandfathering, transfer expenses, exemptions, FII status, and separate VDA business-income versus capital-gain classification.

### Phase 24 — Schedule OS

Schema path: `ScheduleOS`. Interest, dividends, family pension, winnings, unexplained income, deductions, and section/rate classification with source evidence.

### Phases 25–29 — CYLA, BFLA, CFL, UD, ICDS

Schema paths: `ScheduleCYLA`, `ScheduleBFLA`, `ScheduleCFL`, `ITR3ScheduleUD`, `ScheduleICDS`. Present a read-only loss set-off waterfall driven by typed source inputs; allow only valid opening loss/UD facts to be entered; show carry-forward result and reconciliation.

### Phases 30–40 — 10AA, donations, disability, RA, 80-series, Chapter VI-A

Schema paths: `Schedule10AA`, `Schedule80G`, `Schedule80GGA`, `Schedule80GGC`, `Schedule80DD`, `Schedule80U`, `Schedule80RA`, `Schedule80_IA`, `Schedule80_IB`, `Schedule80_IC`, `ScheduleVIA` and its sub-blocks. Each deduction gets an applicability questionnaire, evidence fields, statutory caps, and a computed eligible amount.

### Phases 41–42 — AMT and AMTC

Schema paths: `ScheduleAMT`, `ScheduleAMTC`. Explain why AMT applies, show the adjustment bridge, tax comparison, and brought-forward credit ledger. All computed values are read-only.

### Phases 43–47 — SPI, SI, IF, EI, PTI

Schema paths: `ScheduleSPI`, `ScheduleSI`, `ScheduleIF`, `ScheduleEI`, `SchedulePTI`. Repeatable relationship/entity rows, special-rate classifications, partnership allocations, exempt-income categories, and pass-through certificates with head-of-income mapping.

### Phases 48–51 — TPSA, FSI, TR, FA

Schema paths: `ScheduleTPSA`, `ScheduleFSI`, `ScheduleTR1`, `ScheduleFA`. Applicability driven by transfer-pricing and foreign-income/residential facts. Foreign-asset entry must support account, custodial, equity/debt, insurance, financial interest, immovable property, signing authority, trust, and other-asset structures exactly as the schema requires.

### Phases 52–55 — 5A, AL, GST, ESOP

Schema paths: `Schedule5A2014`, `ScheduleAL`, `ScheduleGST`, `ScheduleESOP`. Use explicit section triggers: Portuguese Civil Code, income threshold for AL, GSTIN turnover disclosure, and eligible-startup ESOP deferral ledger.

### Phases 56–60 — Part B-TI, Part B-TTI, TRP, tax payments, verification

Schema paths: `PartB-TI`, `PartB_TTI`, `TaxReturnPreparer`, `ScheduleIT`, `ScheduleTDS1/2/3`, `ScheduleTCS`, `Verification`. Provide a read-only computation waterfall, reconcile all credits/payments, collect TRP details, and show final blocking issues before JSON generation.

## 4. Cross-cutting implementation gates

- Add typed ITR-3 fields to frontend and backend `ReturnDraft` with safe defaults and round-trip tests.
- Replace ITR-3 business `localStorage` state with canonical draft persistence.
- Create explicit applicability rules and stable schedule identifiers; remove placeholder/masked schedule keys.
- Add `draft_to_itr3_input`, canonical gateway dispatch, ITR-3 input/calculation validators, official schema validation, and typed builder serialization.
- Ensure generated JSON contains only applicable schedules and never fabricated values.
- Add cross-schedule reconciliation: BS balances, P&L/Trading links, BP bridge, depreciation summaries, losses, deductions, tax payments, and totals.
- Add persistence, accessibility, and form-regression tests. Every ITR-1/2/4 test must remain unchanged and green.

## 5. Known issues discovered but intentionally not modified

- Existing ITR-2 fixes are present in the working tree and are outside the ITR-3 UI scope.
- The current ITR-3 business workspace uses generic canonical objects, local-only schedule selection, and is not connected to `ReturnDraft`; this is addressed in the later typed business phases, not by silently changing ITR-1/2/4.
- Existing ITR-3 schedule-choice keys include masked/unstable identifiers in `ITR3BusinessWorkspace.tsx`; these must be corrected during the supporting-schedule persistence phase.
- ITR-3 backend canonical mapper/gateway/schema-validator/builder integration is not yet production-ready and must remain gated until frontend persistence is complete.
- Generated scratch files in the repository are audit artifacts and should not be included in a production commit.
