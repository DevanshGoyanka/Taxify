# ITR-3 Frontend Comprehensive Field-by-Field Audit (AY 2026-27)

**Scope:** every one of the 60 official ITR-3 form Parts/Schedules (per the verified ordering in
`Docs/ITR3_V2_PIPELINE_PRODUCTION_PLAN.md` §0A), checked against the actual live frontend code —
not the backend, not the plan docs' own claims. Ground truth is the verbatim field-by-field
transcription of the actual PDF pages in `Docs/ITR3_FIELD_BY_FIELD_GUIDE_1..4*.md`, itself read
directly from `Reference Docs by CBDT & ITD/Official ITR FORMS/ITR-3-2026-Eng.pdf`.

**Method:** every live ITR-3 frontend component was identified by tracing the actual render tree
from `frontend/src/pages/ITRComputationPage.tsx`'s `activeTab` switch (9 tabs total, tabs 0-8) —
not by trusting `Docs/ITR3_UI_REDESIGN_PLAN_AY2026_27.md`'s own phase-completion claims, several
of which turned out to be wrong (see Part A-OI below). Components that are imported but never
actually rendered for ITR-3 (`LossesTab`, `VDATab`, and five standalone Other-Sources managers)
were identified and excluded from the "live" count, but noted where relevant. Every field-status
table below was produced by directly reading the component source and the corresponding guide
section side-by-side — not spot-checked.

**Status definitions:** `Implemented` = field exists, correctly labeled/structured, matches the
form. `Partially Implemented` = field exists but with reduced granularity, a missing sub-case, or
a documented/disclosed prototype gap. `Wrong` = field exists but produces incorrect data,
mislabels what it asks for, or computes an incorrect value. `Missing` = no field or component
exists at all.

---

## 1. Executive summary

- **9 of 60 form sections have any live frontend UI at all.** Those 9 tabs cover **32 of the 60**
  named Parts/Schedules (several tabs bundle multiple form sections — e.g. the Business tab alone
  covers 6). **28 of the 60 schedules have zero frontend implementation** — not partial, not a
  placeholder, nothing at all.
- **7 schedules have confirmed, real bugs** (wrong data, wrong labels, or wrong computed values),
  not just incompleteness: Part A-BS, Manufacturing Account, Trading Account, Schedule BP,
  Schedule CG, Schedule 80G, Schedule EI.
- **2 form sections claimed as "delivered" in `Docs/ITR3_UI_REDESIGN_PLAN_AY2026_27.md` turned
  out, on direct code inspection, to not match that claim**: Part A-OI is described in that plan's
  Phase 9 write-up as if it were in scope, but is **entirely absent from the codebase** — zero
  references anywhere. Schedule BP's "structured tax bridge" (per the same plan's Phase 14
  description) is in fact a generic raw-schema form with almost none of its own bridge/total
  formulas computed.
- **Two components are dead code**: `LossesTab` (the only thing that would have given Schedule
  CYLA any UI at all) and `VDATab` are both defined in `ITRComputationTabs.tsx` but never actually
  rendered anywhere in `ITRComputationPage.tsx`. Five other imported managers (Dividend/Interest/
  Winnings/FamilyPension/Gift) are likewise unused — `ScheduleOSWorkspace.tsx` built its own
  internal UI for all of these instead.

---

## 2. Master status table — all 60 schedules

| # | Schedule (as printed) | Live component | Status | Field detail |
|---:|---|---|---|---|
| 1 | Personal Information (A1-A18) | `ITR3PersonalInfoPage.tsx` | Partially Implemented | §3.1 |
| 2 | Filing Status (A19) | `ITR3PersonalInfoPage.tsx` | Partially Implemented | §3.1 |
| 3 | Audit Information (A20) | `ITR3PersonalInfoPage.tsx` | Partially Implemented | §3.1 |
| 4 | Nature of Business or Profession | `ITR3PersonalInfoPage.tsx` | Partially Implemented | §3.1 |
| 5 | Part A-BS (Balance Sheet) | `ITR3PersonalInfoPage.tsx` | **Wrong** | §3.1 |
| 6 | Part A-Manufacturing Account | `ITR3BusinessCoreManager.tsx` | **Wrong** | §3.2 |
| 7 | Part A-Trading Account | `ITR3BusinessCoreManager.tsx` | **Wrong** | §3.2 |
| 8 | Part A-P&L | `ITR3BusinessCoreManager.tsx` | Partially Implemented | §3.2 |
| 9 | Part A-OI (Other Information) | **none** | **Missing (0%)** | §3.2 |
| 10 | Part A-QD (Quantitative Details) | `ITR3BusinessAuxiliaryManager.tsx` | Partially Implemented | §3.2 |
| 11 | "SCHEDULES TO THE RETURN FORM" banner | n/a — not a real schedule | n/a | — |
| 12 | Schedule S — Salary | `EmployerEntryManager.tsx` | Partially Implemented | §3.3 |
| 13 | Schedule HP — House Property | `HousePropertyEntryManager.tsx` | Implemented | §3.4 |
| 14 | Schedule BP — Business/Profession | `ITR3BusinessCoreManager.tsx` | **Wrong** | §3.2 |
| 15 | Schedule DPM — Depreciation (P&M) | none | **Missing** | — |
| 16 | Schedule DOA — Depreciation (Other Assets) | none | **Missing** | — |
| 17 | Schedule DEP — Depreciation Summary | none | **Missing** | — |
| 18 | Schedule DCG — Deemed Capital Gains (depreciable assets) | none | **Missing** | — |
| 19 | Schedule ESR — Scientific Research Expenditure | none | **Missing** | — |
| 20 | Schedule CG — Capital Gains | `CapitalGainsEntryManager.tsx` | **Wrong** | §3.5 |
| 21 | Schedule 112A | `CapitalGainsEntryManager.tsx` | Implemented | §3.5 |
| 22 | Schedule 115AD(1)(b)(iii) | `CapitalGainsEntryManager.tsx` | Implemented | §3.5 |
| 23 | Schedule VDA | `CapitalGainsEntryManager.tsx` | Partially Implemented | §3.5 |
| 24 | Schedule OS — Other Sources | `ScheduleOSWorkspace.tsx` | Implemented | §3.6 |
| 25 | Schedule CYLA | `LossesTab` (dead code, not rendered) | **Missing (0% live)** | §3.7 |
| 26 | Schedule BFLA | none | **Missing** | — |
| 27 | Schedule CFL | none | **Missing** | — |
| 28 | Schedule UD | none | **Missing** | — |
| 29 | Schedule ICDS | none | **Missing** | — |
| 30 | Schedule 10AA | none | **Missing** | — |
| 31 | Schedule 80G — Donations | `DonationEntryManager.tsx` | **Wrong** | §3.8 |
| 32 | Schedule 80GGA | `DeductionsWorkspace.tsx` (flag only) | Partially Implemented | §3.9 |
| 33 | Schedule 80GGC | `DeductionsWorkspace.tsx` (flag only) | Partially Implemented | §3.9 |
| 34 | Schedule 80DD | `DeductionsWorkspace.tsx` | Partially Implemented | §3.9 |
| 35 | Schedule 80U | `DeductionsWorkspace.tsx` | Partially Implemented | §3.9 |
| 36 | Schedule RA | none | **Missing** | — |
| 37 | Schedule 80-IA | `DeductionsWorkspace.tsx` | Partially Implemented | §3.9 |
| 38 | Schedule 80-IB | `DeductionsWorkspace.tsx` | Partially Implemented | §3.9 |
| 39 | Schedule 80-IE (schema `Schedule80_IC`) | `DeductionsWorkspace.tsx` | Partially Implemented | §3.9 |
| 40 | Schedule VI-A (+80C/80CCC/80D/80E/80EE/80EEA/80EEB/80CCH) | `DeductionsWorkspace.tsx` + 4 sub-managers | Partially Implemented | §3.8/§3.9 |
| 41 | Schedule AMT | none | **Missing** | — |
| 42 | Schedule AMTC | none | **Missing** | — |
| 43 | Schedule SPI | none | **Missing** | — |
| 44 | Schedule SI | none | **Missing** | — |
| 45 | Schedule IF | none | **Missing** | — |
| 46 | Schedule EI — Exempt Income | `ExemptIncomeWorkspace.tsx` | **Wrong** | §3.10 |
| 47 | Schedule PTI | none | **Missing** | — |
| 48 | Schedule TPSA | none | **Missing** | — |
| 49 | Schedule FSI | none | **Missing** | — |
| 50 | Schedule TR | none | **Missing** | — |
| 51 | Schedule FA | none | **Missing** | — |
| 52 | Schedule 5A | none | **Missing** | — |
| 53 | Schedule AL | none | **Missing** | — |
| 54 | Schedule GST | none | **Missing** | — |
| 55 | Schedule ESOP | none | **Missing** | — |
| 56 | Part B-TI (Total Income) | `TaxComputationTab` | Partially Implemented (read-only display) | §3.11 |
| 57 | Part B-TTI (Tax Liability) | `TaxComputationTab` | Partially Implemented (read-only display) | §3.11 |
| 58 | Tax Return Preparer (TRP) | none | **Missing** | — |
| 59 | Section 17 — Tax Payments (A/B/C/D) | `TDSTab` | Partially Implemented | §3.12 |
| 60 | Verification | `ITR3PersonalInfoPage.tsx` | Partially Implemented | §3.1 |

**Tally:** 4 Implemented · 21 Partially Implemented · 7 Wrong · 28 Missing (27 real + 1 dead-code
schedule) · 1 N/A (banner).

---

## 3. Detailed per-schedule field tables

### 3.1 Personal Info, Filing Status, Audit Info, Nature of Business, Part A-BS, Verification
*(`ITR3PersonalInfoPage.tsx` — schedules 1-5, 60)*

**Confirmed real defects:**
1. **Wrong — "No books of account" checkbox is inert** (line 156). Checking it should switch
   Part A-BS to the form's simplified item-6 4-field disclosure. It doesn't — detailed
   Sources/Applications fields render regardless. A no-books preparer has no correct path.
2. **Wrong — Director-disclosure dropdown asks the wrong question** (line 155). Form's column (j)
   asks "listed or unlisted shares"; component offers "Domestic"/"Foreign" — a different
   classification entirely.
3. **Wrong — Part A-BS structural misplacement** (lines 96, 156). `creditors`/`provisions` sit
   under Sources of Funds; the form treats "current liabilities and provisions" as a deduction
   *within* Application of Funds. `otherLiabilities` has no Sources-side counterpart in the form
   at all.
4. Minor: A3 labeled "Surname/organisation name" vs. form's "Last name"; a "Father's name" field
   with no corresponding field anywhere on ITR-3's Personal Information page (confirmed directly
   against the PDF image — likely inherited from ITR-1/2); A15 (Date of Commencement of Business)
   silently missing despite the component's own description text claiming "A14-A16"; filing-section
   dropdown missing `92CD` and `153C`; residential-status dropdown shows only "Code 1"-"Code 9"
   with no descriptive text, so a preparer can't tell which applies without the form in hand;
   92E audit flow skips an intermediate "have accounts been audited u/s 92E" Yes/No the form has;
   nature-of-business section doesn't mention the form's own exclusion of 44AD/44ADA/44AE
   businesses from that table.
5. **Verification (schedule 60)**: Capacity (Self/Representative/Karta/Partner), Place, Date, and
   the declaration checkbox are present and correctly required. Missing: capacity-specific detail
   fields (representative's own identity when filing on someone else's behalf) and the section
   92CD "critical assumptions satisfied" declaration clause — both explicitly disclosed as
   deferred in the component's own description text, not a silent gap.
6. Partner-in-firm table (form field (k): Name of Firm + PAN) is entirely missing, but this is
   disclosed in `Docs/ITR3_UI_REDESIGN_PLAN_AY2026_27.md`'s own Phase 2 deferral list — noted for
   completeness, not a new finding.

### 3.2 Business workspace: Manufacturing, Trading, P&L, OI, QD, Schedule BP
*(`ITR3BusinessCoreManager.tsx`, `ITR3BusinessAuxiliaryManager.tsx`, `ITR3PresumptiveManager.tsx` — schedules 6-10, 14)*

**Rendering mechanism** (this governs how to read the findings below): Manufacturing/Trading
Account and Part A-QD have real hand-built field UIs. Part A-P&L and Schedule BP are rendered by a
**generic schema-driven form** (`SchemaEditor`/`CanonicalObject`, walking a raw embedded JSON-
schema blob) with only a partial `CALCULATED_FIELDS`/`FORMULAS` map computing some sub-totals —
this is a fundamentally different (much thinner) implementation than a purpose-built editor, even
where the raw fields technically exist.

**Confirmed real defects:**
1. **Wrong — Manufacturing Account total (1F) double-counts Direct Expenses** (line 78). Formula
   sums `DirectExpenses` *and* its own sub-components (`CarriageInward`+`PowerAndFuel`+
   `OthDirectExpenses`) in the same total — inflates cost of goods produced for any return with
   non-zero direct expenses.
2. **Wrong — Trading Account total shows the identical double-counting pattern** (line 87), and
   inconsistently omits `OthDirectExpenses` unlike the Manufacturing version. Two independent
   instances of the same bug pattern — worth a full pass over the entire formulas map.
3. **Wrong — 44AD/44ADA extended turnover caps (₹3cr/₹75L) applied unconditionally**
   (`ITR3PresumptiveManager.tsx:6-7`), never checking the 5%-cash-receipts condition that's
   supposed to gate the extension from the statutory ₹2cr/₹50L base.
4. **Wrong — 44AE presumptive default/floor is a flat ₹7,500** (lines 159, 189) when the statutory
   rate is ₹7,500 *per month* — under-reports for any vehicle held longer than one month.
5. **Part A-P&L: 6 of the schedule's own bridge/total lines have zero auto-computation**: item 46iii
   (other expenses total), 47iv (bad debts total), **50 (profit before interest/depreciation/tax —
   the schedule's single largest formula)**, 53 (net profit before tax), 56 (profit after tax),
   58/60 (appropriation/balance carried to BS). A preparer must hand-calculate these with no
   verification. ~15 other sub-totals (employee comp, insurance, commission, royalty, professional
   fees, rates/taxes, interest, and the full no-books-of-accounts simplified P&L) are correctly
   auto-computed. Roughly 40 of 60 printed line-items have some data-entry field, generically
   labeled via the raw schema (not matched to the form's own prose).
6. **Part A-OI: entirely absent.** Zero references to `PARTA_OI` anywhere in the codebase — not in
   `ITR3BusinessCoreManager.tsx`, not in the typed `ITR3BusinessCoreData` interface (only 6 fields:
   `PartA_GEN2`, `PARTA_BS`, `ManufacturingAccount`, `TradingAccount`, `PARTA_PL`,
   `ITR3ScheduleBP`), not in `ITR3BusinessWorkspace.tsx`'s schedule-choice list. This directly
   contradicts `Docs/ITR3_UI_REDESIGN_PLAN_AY2026_27.md`'s Phase 9 write-up, which describes this
   page as if it exists ("The page becomes mandatory when official audit applicability requires
   it"). Since Part A-OI is form-mandatory whenever 44AB audit applies, **any audited ITR-3 filer
   currently has no way to enter this data at all** — method of accounting, stock valuation, ICDS
   deviations, and all section 36/37/40/40A/41/43B disallowance disclosures (item 6 alone has 19
   lettered sub-items).
7. **Part A-QD: fields are genuinely well-built** (item name, unit, opening/closing stock,
   purchases/production, sales/consumption, shortage/excess reconciliation, manufacturing-specific
   yield percentages) — closely matches the guide. But it's reachable only via an opt-in checkbox
   in `ITR3BusinessWorkspace.tsx`'s 16-item schedule-choice list, with **no enforcement tying it to
   the form's own "mandatory if audited" rule** — an audited preparer can simply never check the
   box.
8. **Schedule BP: of ~40 line items, only 8 sub-totals are auto-computed, and at least 2 of those
   8 are themselves arithmetically wrong.** The 4a+4b combined total (`TotalProfitFrmActCvrd`)
   collapses two form items the downstream formula for item 38 needs kept separate. The exempt-
   income total (`TotExempIncPL`, item 5d) sums 4 terms when the form's formula is a 3-term sum —
   an extra `OperatingDividendAmt` addend inflates it. A third (item E-iv, loss-setoff total) is
   likely wrong pending schema confirmation (sums what may be an income figure alongside two
   setoff amounts). **Most critically: the schedule's actual output figures — items 6, 10, 13, 34
   ("Income" = 13+26-33, the single most consequential line in Schedule BP), 36, 37, 38, and D
   itself (income chargeable = A37+B42+C48) — have zero computation anywhere in the file.** A
   preparer must compute the entire BP bridge by hand with no verification whatsoever. Sections B
   (speculative income, items 39-42) and C (specified business u/s 35AD, items 43-49) have no
   formulas at all either. This is a larger gap than the Manufacturing/Trading bugs — those at
   least attempt a (wrong) computation; here, most of the bridge doesn't attempt one.

### 3.3 Schedule S — Salary
*(`EmployerEntryManager.tsx`)*

23 form line-items checked: **18 Implemented** (11 direct, 7 via reasonable decomposition/
backend-computation), **1 Partially Implemented**, **1 Wrong**, **3 Missing**.

- **Missing — items 1d, 1e, 1f: Section 89A retirement-account income has no capture path at
  all** (notified-country retirement income, non-notified-country retirement income, and
  previously-relieved income now taxable). Direct consequence: **item 2a (89A relief claimed) and
  therefore item 4 (Net Salary = 2 − 2a − 3) and item 6 (income chargeable) are structurally
  incapable of being correct** for any taxpayer with foreign retirement-account income — not a
  display bug, a missing-input bug with a wrong-output consequence.
- **Partially Implemented — employer TAN** (line 513): UI copy says "Optional when unavailable,"
  but the form requires it whenever tax was actually deducted; that conditional-mandatory rule
  isn't enforced.
- Gross salary, perquisites (17(2)), profit-in-lieu (17(3)), all Section 10 exemption sub-items
  (via dedicated HRA/LTA/retirement/10(14) sections), and Section 16 deductions (standard
  deduction, entertainment allowance, professional tax) are all correctly implemented.
- No ITR-3-specific gating exists in this component (identical for ITR-1/2/3/4) — Schedule S's
  structure doesn't materially differ across forms, so this isn't itself a finding.

### 3.4 Schedule HP — House Property
*(`HousePropertyEntryManager.tsx`)*

Core computation chain (1a→1k) maps cleanly field-for-field, including the home-loan interest
sub-table. Pass-through income correctly gated for ITR-3 (`supportsPassThrough`).

Minor only: label "Annual Lettable Value" is a shortened paraphrase of the form's longer "Gross
rent received or receivable or lettable value" (item 1a); co-owner rows are unbounded in the UI
while the form prints exactly 2 named rows (I, II) — likely harmless if the underlying schema
array isn't capped, not independently verified either way.

### 3.5 Schedule CG, 112A, 115AD, VDA
*(`CapitalGainsEntryManager.tsx`)*

**Schedule CG (schedule 20) — Wrong.** Every multi-item ST/LT category's on-screen letter is
mismatched against its own field content:

| Shown as | Actually is (per field content) |
|---|---|
| A5 "STCG slump sale" | **A2** |
| A2 "STCG equity/STT" | **A3** |
| A3 "STCG NRI unlisted" | **A5** |
| A4 "STCG other assets" | **A6** — the real **A4** (non-resident-non-FII item) has no field anywhere: a genuine coverage gap, not just mislabeling |
| B6 "LTCG slump sale" | **B2** |
| B2 "LTCG proviso 112" | **B3** |
| B3 "LTCG NRI 112/115" | **B6** |
| B4 "LTCG NRI foreign assets" | **B8** |
| B5 "LTCG other assets" | **B9** |

Underlying JSON field names look internally consistent (so this may be a labeling-only bug, not
necessarily a computation bug), but every category number a preparer sees is wrong. *Within* each
category, the field sets (dates, consideration, cost/improvement/transfer-expense, 94(7)/(8) loss,
deduction sections) are correct.

**Schedule 112A / 115AD (schedules 21-22) — Implemented.** All 13-14 logical columns present under
matching field names (Sl.No, acquired-before/after, ISIN, name, qty, sale price, full value, cost
w/o indexation, cost, FMV-31-Jan-2018, total FMV, transfer expenses, total deductions, balance),
correctly shared between both schedules per the guide's own "same column structure" note. The most
completely and correctly implemented sub-schedules found in this entire audit.

**Schedule VDA (schedule 23) — Partially Implemented.** All 7 columns present (Sl.No, dates,
head-of-income classification, cost, consideration, income), correctly restricted to Capital-Gains-
only for non-ITR-3 forms while ITR-3 keeps both Business/CG options. Gaps: the form's two gift
cost-basis sub-cases (56(2)(x) tax paid vs. cost to previous owner) collapse into one flat field;
the form's two separately-reported totals (A: business income → Schedule BP item A3g, B: capital
gain → Schedule CG item C2) never surface separately on screen, only as one combined figure —
underlying per-row data supports the split, the UI just doesn't show it. `VDATab`'s own comment
("VDA rows are edited inside CapitalGainsEntryManager") is confirmed true, but `VDATab` itself is
dead code, never rendered.

### 3.6 Schedule OS — Other Sources
*(`ScheduleOSWorkspace.tsx`)*

Interest sub-items (4 kinds incl. PF-proviso), race-horse activity (8a-8e), and the unexplained-
income 68-69D breakdown (all 6 sub-items) match the guide exactly.

Minor items, not confirmed as bugs: dividend option list includes `115BBDA`/`115BBDAaiii`, not
found anywhere in the guide's transcribed Schedule OS 2(d) sub-item list — could be a genuine
AY2026-27 form change or a transcription gap, worth a direct re-check either way; no distinct
"pass-through interest" option matching the form's dedicated sub-item (possibly intentionally fed
from Schedule PTI instead, PTI itself has no frontend — see §2 row 47); a separate flat
`UNEXPLAINED_115BBE` winnings-array option exists alongside the already-correct dedicated
`unexplainedIncome` object — risks double-entry, not confirmed whether the calculator dedupes it.

### 3.7 Schedule CYLA
*(`LossesTab` — defined in `ITRComputationTabs.tsx:236` but never rendered)*

**Missing (0% live).** The component exists and would present a reasonable, if simplified,
current/brought-forward loss set-off UI ("Brought Forward Losses (CBDT Schedule CYLA)") — but it
is dead code: no reference anywhere in `ITRComputationPage.tsx`'s render tree. A preparer using the
live app has zero UI for this schedule.

### 3.8 Schedule 80G — Donations
*(`DonationEntryManager.tsx`)*

**Wrong.** All 4 donation categories (A/B/C/D) present with correct 100%/50%,
approval-required/not labeling; donee name/address/PAN, cash/other-mode/total amounts, transaction
reference, and IFSC are all implemented, with eligible-amount correctly deferred to the backend
(not computed client-side). The one real defect: **the ARN (Donation Reference Number) field is
rendered unconditionally for every category**, when the guide's transcription shows it printed
**only** in category D's column structure — confirmed both in this component (line 40, no
category-based gating) and in the canonical `Donation80G` type itself (structural, not just a
display artifact). A preparer entering an A/B/C donation sees a field the form doesn't ask for
there. Section D's own "Total" row (row iii) couldn't be independently confirmed — the guide
itself flagged this row as falling on a page break during transcription; the component does
compute category-level running totals regardless.

### 3.9 Chapter VI-A: 80C/80CCC/80D/80DD/80U/80E-family/80CCH/80-IA/80-IB/80-IE/80GGA/80GGC
*(`Section80CManager.tsx`, `Section80DManager.tsx`, `DeductionLoanManager.tsx`, `DeductionsWorkspace.tsx`)*

- **80C — Implemented.** 11 typed investment categories, identification/account/date/institution
  detail fields, correctly deferred ₹1.5L cap. **80CCC — Missing from this file specifically**
  (the form's own separately-numbered line item has no field in `Section80CManager.tsx`; a
  `pensionContribution80CCC` prop is passed elsewhere in `DeductionsWorkspace`, not independently
  verified as complete since it lives outside this component).
- **80D — Implemented**, fully matching all 4 self/family/parents/senior-citizen combinations,
  insurer/policy detail, preventive-checkup and non-insured-senior medical-expense sub-fields, caps
  correctly deferred to backend.
- **80E/80EE/80EEA/80EEB (loan interest) — Implemented.** All four sections' lender/loan/interest
  fields present, 80EEA's stamp-duty-value field and 80EEB's vehicle-registration field correctly
  scoped to their own sections only.
- **80CCH (Agniveer Corpus Fund) — Missing entirely.** Confirmed absent from all of
  `Section80CManager.tsx`, `Section80DManager.tsx`, and `DeductionLoanManager.tsx`. Separately,
  `DeductionsWorkspace.tsx` has a field named `anyOtherSection80CCH` that's actually the form's
  generic "any other deduction" catch-all mislabeled with the specific 80CCH statutory name — a
  preparer with a genuine 80CCH claim may not recognize this as the right field.
- **80DD / 80U — Partially Implemented.** Full 8-option "type of dependent" list matches the guide
  exactly for 80DD. But the "type of disability" dropdown collapses the form's 10 named conditions
  down to 2 generic options (Autism/cerebral-palsy/multiple vs. "Other") — needs a JSON-schema
  check to determine whether the real schema field is genuinely a binary flag (fine) or expects one
  of the 10 named codes (real data loss); not resolved either way in this audit.
- **80-IA / 80-IB / 80-IE — Partially Implemented.** All three exist but each is collapsed to one
  flat number, when the form needs real per-undertaking breakdowns (2 rows for 80-IA, 8 cells for
  80-IB's 4 sub-clauses × 2 undertakings, 16 cells for 80-IE's 8 North-East states × 2
  undertakings) with Form 10CCB sourcing. A multi-undertaking filer has no way to enter the real
  detail. 80-IE is also user-facing-labeled "80IC" (the schema block name), not "80-IE" (the
  form's own printed name) — a preparer scanning the gazetted form for "80-IE" won't recognize it.
- **80GGA / 80GGC — Partially Implemented.** Both are enabled via boolean flags
  (`FORM_CAPS['ITR-3'].gga/ggc: true`) confirmed correct at that level, but the underlying field
  structures weren't independently field-verified in this audit (out of scope for the forks that
  covered VI-A). 80GGA's own form-printed applicability restriction ("applicable in the case of a
  partner of firm deriving only profit from the firm") isn't reflected as a conditional warning.
- **80QQB / 80RRB — Implemented, and confirmed genuinely correct** (not an ITR-2 copy-paste
  error) — both are real VI-A Part C line items on the ITR-3 form itself.
- **Schedule 10AA, Schedule RA — Missing entirely.** No representation anywhere in
  `DeductionsWorkspace.tsx` or its sub-managers.

### 3.10 Schedule EI — Exempt Income
*(`ExemptIncomeWorkspace.tsx`)*

**Wrong.**
1. **Agricultural-land-detail threshold is off by 100x.** UI text (lines 162, 171) says land-parcel
   detail is required above "₹5,000" net agricultural income; the form's actual printed text says
   "**₹5 lakh**" — confirmed by direct comparison. A different, correctly-stated ₹5,000 threshold
   (the real ITR-1-eligibility rule) exists elsewhere in the same file, so this isn't a copy-paste
   of the right number, it's simply wrong for this specific hint.
2. **The displayed EI total includes a field the form's formula doesn't have.** Form's own formula
   (item 6) is "1+2+3+4+5" — five components. The component (line 127) sums **six**, adding
   `incomeNotChargeableToTax`, which has no corresponding numbered line anywhere in the guide's
   Schedule EI transcription, yet is shown as its own line item and silently folded into the total.
3. **Item 2(iv) should be sourced from Schedule BP item 38** (the form prints this explicitly) but
   is a free-entry field instead, letting a preparer enter a figure that disagrees with BP.

### 3.11 Part B-TI, Part B-TTI
*(`TaxComputationTab` in `ITRComputationTabs.tsx:846`, confirmed rendered at `ITRComputationPage.tsx:2080`)*

**Partially Implemented — read-only display only.** All figures (gross salary, Section 10
exemptions, Section 16 deductions, GTI, deductions under Chapter VI-A, total income, etc.) are
backend-computed and shown correctly as read-only — appropriate, since these are computed totals,
not data-entry fields. What's absent: any of the schedule's own editable declarative content (e.g.
Part B-TTI's asset-outside-India flag, or anything requiring a preparer answer rather than a
computed figure) — not independently field-verified beyond confirming the summary display exists
and is wired to real backend figures, not placeholders.

### 3.12 Section 17 — Tax Payments
*(`TDSTab` in `ITRComputationTabs.tsx:322`)*

Of ~35 distinct form fields/columns across the four lettered sub-tables: **~20 Implemented**, **8
Partially Implemented**, **7 Missing**.

- **17-A (Advance/Self-Assessment Tax) — fully implemented**: BSR code, deposit date, challan
  serial, amount, all present and validated.
- **17-B (TDS on Salary) — mostly implemented**, one field genericized ("Income Amount" label
  isn't specifically "Income chargeable under Salaries").
- **17-C (TDS on Other Income) — the weakest section.** Missing entirely: the form's own/spouse
  claim-breakdown Income/TDS/PAN triplets (columns 7-9), the current-FY TDS own-vs-spouse-hands
  split (only one undifferentiated scalar exists), and the brought-forward TDS's paired
  "financial year" field (the amount field exists, the year doesn't). The TDS3 branch additionally
  has no owner-hands selector at all (present in the TDS2 branch, absent in TDS3 — an
  inconsistency within the same component).
- **17-D (TCS) — brought-forward/carried-forward TCS fields are entirely missing**, while the
  equivalent fields for TDS2/TDS3 do exist elsewhere in the same component — the same
  inconsistency pattern as above.
- **Section-code dropdown (17-C item 4a) is a separate, confirmed defect**: hand-maintained rather
  than generated from the codebase's own declared "single source of truth"
  (`frontend/src/domain/returns/tdsSections.ts`), causing it to both miss several schema-valid
  section-code variants (194J(a)/(b) split, 194I(a)/(b) split, 194LC/194LBA/194N sub-variants,
  presumptive-purpose variants) and to show every section for every form instead of filtering to
  what ITR-3 actually permits — despite a `tdsSectionsForForm('ITR-3')` scoping helper already
  existing, unused, in the same codebase.

---

## 4. If you fix nothing else — ranked worst-first

1. **Schedule BP's actual output figures (items 6, 10, 13, 34, 36, 37, 38, D) have zero
   computation.** This is the schedule computing business/profession income — the core of an
   ITR-3 return — and a preparer must hand-calculate its own bridge with no safety net.
2. **Part A-OI doesn't exist**, contradicting the redesign plan's own claim, and is form-mandatory
   for every audited filer.
3. **Schedule CG's category letters are systematically wrong** — every multi-item ST/LT category
   a preparer sees is shifted from its real form position, plus a genuine A4 coverage gap.
4. **Manufacturing/Trading Account double-count Direct Expenses** — a real, silent numeric error
   for any return with non-zero direct expenses, not just a UI gap.
5. **Part A-BS's "no books" checkbox does nothing**, and Sources/Applications are structurally
   misplaced.
6. **Schedule EI's ₹5 lakh threshold is displayed as ₹5,000** — a 100x error a preparer would
   directly act on.
7. **44AD/44ADA/44AE presumptive-income rules are wrong**: extended caps applied without checking
   eligibility, 44AE's floor off by a factor of "per month."
8. **Schedule S has no way to enter Section 89A retirement-account income**, which structurally
   breaks the Net Salary total for any taxpayer who has it.
9. **Schedule 80G shows the ARN field for every donation category** when the form only asks for it
   in category D.
10. **Section 17-C/17-D's claim-breakdown and TCS carry-forward fields are missing**, and the TDS
    section-code dropdown misses several valid codes while not filtering by form at all.

---

## 5. Complete list of schedules with zero frontend implementation (28)

Schedule DPM (15), Schedule DOA (16), Schedule DEP (17), Schedule DCG (18), Schedule ESR (19),
Schedule CYLA (25 — dead code only), Schedule BFLA (26), Schedule CFL (27), Schedule UD (28),
Schedule ICDS (29), Schedule 10AA (30), Schedule RA (36), Schedule AMT (41), Schedule AMTC (42),
Schedule SPI (43), Schedule SI (44), Schedule IF (45), Schedule PTI (47), Schedule TPSA (48),
Schedule FSI (49), Schedule TR (50), Schedule FA (51), Schedule 5A (52), Schedule AL (53),
Schedule GST (54), Schedule ESOP (55), Tax Return Preparer (58), Part A-OI (9 — counted separately
above as a confirmed contradiction of the plan doc's own claim, included here for completeness).
