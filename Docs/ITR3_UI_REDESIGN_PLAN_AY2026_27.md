# ITR-3 UI Redesign and Implementation Plan — AY 2026-27

**Status:** Phase 1 implementation in progress: Personal Information.

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

### Phase 1 — Personal Information (A1–A18) — current implementation

Schema blocks: `PartA_GEN1.PersonalInfo`, `PartA_GEN1.FilingStatus` foundations, `Verification` foundations.

UI sections:

- **Return profile:** ITR-3, AY 2026-27, taxpayer type Individual/HUF, name components, PAN, Aadhaar, DOB/date of formation, father’s name where applicable.
- **Primary address:** residence/door, premises, road, locality, city/district, state, country, PIN/ZIP.
- **Secondary address:** explicit Yes/No matching `SecondaryAdd`; alternate address fields only when Yes.
- **Communication:** country code, mobile, email, secondary mobile/email.
- **Filing identity:** filing section, original/revised/notice details, due date, tax regime.
- **Representative/Karta:** capacity and representative details only when applicable.
- **Verification:** capacity, declarant place/date, declaration acceptance.
- **Professional usability:** completion summary, official field labels, required markers, inline format help, and no generic JSON editor.

Schema requirements implemented by this page: required `AssesseeName`, `PAN`, `Address`, `SecondaryAdd`, `DOB`, `Status`; required communication fields; PAN/mobile/email/PIN formats; `Verification.Declaration`, `Capacity`, `Date`, and `Place` foundations.

### Phase 2 — Filing Status (A19)

Schema paths: `PartA_GEN1.FilingStatus` and related `PartA_GEN2` flags.

Add explicit ITR-3 controls for return section, residential status (`RES`/`NRI`/`NOR`), business/profession income indicator, seventh-proviso triggers, unlisted equity, foreign exchange/foreign income indicators, Form 10-IEA history, director/partner status, representative assessee, PE/SEP/IFSC/FPI/LEI disclosures, and original return references. Rules must enforce mutually exclusive regime branches and conditional acknowledgements.

### Phase 3 — Audit Information (A20)

Schema path: `PartA_GEN2.AuditInfo`.

Guided questionnaire for sections 44AA, 44AB, and 92E; turnover band; cash-receipt/payment percentages; audit-accountant details; audit report date and acknowledgement; accounting/audit applicability. The UI reveals only the fields triggered by previous answers and validates the official dependencies.

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
