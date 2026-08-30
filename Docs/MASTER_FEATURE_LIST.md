# 🎯 COMPLETE TAX ERP — MASTER IMPLEMENTATION FEATURE LIST

> This is the single consolidated, build-ready feature list. It merges:
> (1) the original "COMPLETE & FINAL TAX ERP FEATURE LIST", plus
> (2) every gap identified across the NRITAX/Taxify audits, the incumbent teardowns, and the "12-pillar beat-the-incumbents" spec.
>
> Features are numbered so they can map 1:1 to backlog tickets / epic IDs.
> Legend: [CORE] = must-have for a credible ITR product · [MOAT] = differentiator that beats incumbents · [SUITE] = adjacent-domain module that locks clients in.

---

## PART A — CORE COMPUTATION ENGINE

### A1. ITR FORM SUPPORT
- [CORE] ITR-1 (SAHAJ) — salaried individuals
- [CORE] ITR-2 — individuals/HUFs without business income
- [CORE] ITR-3 — individuals/HUFs with business/profession income
- [CORE] ITR-4 (SUGAM) — presumptive taxation
- [SUITE] ITR-5 — firms, LLPs, AOPs, BOIs
- [SUITE] ITR-6 — companies (except u/s 11)
- [SUITE] ITR-7 — trusts, political parties, institutions
- [SUITE] ITR-U — updated return (within 24 months)
- [CORE] Automatic ITR form selection based on income sources (with reason display)
- [CORE] Form-specific validation as per official ITD schema (JSON, not just internal rules)
- [MOAT] **Year-locked builds** — each compute instance locked to one assessment year; impossible to mix FY/AY
- [MOAT] **Per-figure provenance** — every field on the return shows its source (imported doc / AIS / manual), clickable

### A2. SALARY INCOME
- Salary from multiple employers (auto-merge + duplicate-merge)
- Allowances (HRA, LTA, Special Allowances) with correct sub-heading split
- [MOAT] **Perquisites valuation** (car, accommodation, concessional loans, ESOP/RSU at vesting)
- Profit in lieu of salary
- Section 16 deductions (Standard, Professional tax)
- Relief u/s 89 for arrears/advance salary + **Form 10E generation**
- Leave encashment calculation
- Gratuity calculation & exemption (incl. private-sector 15-day rule)
- [MOAT] **Accurate salary-head mapping** — basic/HRA/perquisites/exemptions each land in the correct ITR field (fixes the "everything into basic" lossy-bug found in the audit)

### A3. HOUSE PROPERTY
- Multiple-property support (correctly iterating scheduled floors)
- Self-occupied vs let-out classification
- Deemed let-out for 3rd+ self-occupied property
- Annual value (GAV/NAV deduction: municipal taxes, 30% std., 24B interest)
- Municipal taxes deduction
- Interest on home loan u/s 24(b)
- Standard deduction 30%
- Loss from HP (`-₹2L` limit, carried forward per schedule)
- [MOAT] **Single-vs-multiple property handling** — correctly gate ITR-1 (single only) vs ITR-2 (full HP schedule)

### A4. BUSINESS & PROFESSIONAL INCOME
- Books-of-accounts integration (P&L, Balance Sheet mapping)
- [MOAT] **Full block-wise depreciation engine (IT Act rates)**: WDV, additions/deletions, pro-rata (180-day rule), 50% cap, additional dep 32(1)(iia), Section 50 slip rule, Section 43(6) definition, audited WDV carry-forward — with ITR-3/3CD depreciation schedule auto-generation
- Business expenses validation
- Presumptive 44AD (6%/8%), 44ADA (50%), 44AE (goods carriages, per-vehicle tonnage split)
- Speculative/non-speculative classification
- 44AB audit-requirement check + **threshold watch** (₹1cr/₹10cr, 44AD ₹2cr, 44ADA ₹75L alerts)
- MAT for companies (book profit calc)
- AMT for individuals/LLPs (adjusted total income calc)
- Book profit / adjusted total income schedules
- [MOAT] **Trial-balance → ITR mapping engine** (GL-code mapping to ITR heads, editable mapping rules)
- [MOAT] **Balance Sheet → Schedule BS / P&L → Schedule BP/PBP** auto-mapping for ITR-3/ITR-4
- [MOAT] **Valuation of closing stock (Section 145A)** with GST inclusion
- Key-man insurance / Section 40A(2)/(3) related-party / cash>₹10k checks

### A5. CAPITAL GAINS
- ST/LT classification (asset-wise holding period)
- Equity/MF listed: STCG/LTCG incl. **Section 112A grandfathering (FMV as on 31-01-2018)** + STT confirmation both sides
- [MOAT] **Rate-change auto-split** for transactions straddling the 23-07-2024 rate change (15%→20% STCG)
- Debt MF: LTCG with indexation
- Real estate: LTCG with indexation + **Section 50C stamp-duty-vs-consideration rule**
- Gold/jewellery/bonds, unlisted shares (with **50CA/Section 56(2)(x) off-market & gift rules**)
- Indexed cost-of-acquisition calculator (CII year table)
- Section 54, 54F, 54EC, 54EE, 54GB, 54G exemptions with **reinvestment compliance tracking** (sale-within-3-years → taxable)
- Cost-of-improvement tracking
- Broker statement import (Zerodha, Groww, Upstox, Angel, etc.) with cost-basis + grandfathering
- [MOAT] **ESOP/RSU flow**: perquisite at vesting (salary 89A) + CG at sale, employer-TDS reconciliation
- [MOAT] **Corporate-action handling**: bonus (cost ₹0, original period), rights, splits/reverse-splits
- [MOAT] **JDA/land-pooling** deemed-transfer computation

### A6. OTHER SOURCES INCOME
- Interest from banks/PO/bonds (with the savings-interest vs FD split)
- Dividend income (with TDS tracking)
- Family pension (₹15,000 / 1/3rd std. deduction; new-regime ₹25,000)
- Lottery/races/crossword (flat 30% + 234E-related handling)
- Rental from machinery/equipment, royalty/patent
- Agricultural income (shown for rate purposes, partial integration)
- [MOAT] Cryptocurrency/VDA (30% + 1% TDS u/s 194S, transfer cost basis, schedule)
- [MOAT] **Deemed income items**: rewards/awards u/s 2(24)(xii), 41(1) remission, 28 deemed income entries, 56(2)(x) gifts
- [MOAT] **Slump sale (Section 50B)** computation

### A7. NEW TAX REGIME (115BAC) — 20
- [CORE] Automatic old-vs-new comparison + recommendation engine (with reason)
- Side-by-side computation + visual chart
- Regime-wise allowed/disallowed deduction breakup
- Marginal relief near threshold
- TDS regime intimation to employer
- Historical regime-choice tracking per client
- Form 10-IEA generation (business opt-out)
- One-time (business, non-reversible) vs annual (salaried) opt-out tracking
- Investment-planning suggestions per regime

### A8. TAX CALCULATION
- Age-wise slabs (old + new)
- Surcharge (10/15/25/37%) + **marginal relief on surcharge**
- Health & Education Cess 4%
- Rebate u/s 87A with marginal relief (correct 87A cap in each regime/year)
- AMT/MAT
- Tax after TDS/TCS/advance/self-assessment; refund/demand; rounding to ₹10
- Residential-status impact on rates
- Agricultural-income rate impact

### A9. INTEREST & PENALTY
- 234A, 234B, 234C (with accurate installment-wise deferment), 234F, 244A
- [MOAT] **Compound interest calculator for notice demands**
- 270A (under/misreporting), 271H, 272A
- Penalty-waiver request + reasonable-cause template

### A10. LOSS SET-OFF & CARRY-FORWARD
- Intra-head + inter-head current-year set-off
- Business (8y), speculation (4y), capital (8y), HP (8y), unabsorbed depreciation (indefinite), 35AD specified-business (15y, no set-off)
- Set-off order enforcement per IT Act
- Auto-track brought-forward losses + **Form 10-IEA carryforward reporting**
- New-regime loss restrictions (no HP loss, BF loss restrictions)

---

## PART B — IMPORT / RECONCILIATION / POPULATION  [MOAT]

> This is the "how the return gets filled correctly" layer — the #1 win against incumbents.

### B1. ITD DATA SPINE
- [CORE] ITD Prefill import (authoritative populator — the spine, not AIS)
- Form 26AS import (TDS + TCS ledger)
- AIS import (all 20+ information categories: TDS, SFT, bank interest, share transactions, etc.)
- TIS import (tax information statement)
- **AIS/TIS as diff, NOT auto-populator**: compute "in AIS vs entered vs prefill" 3-way variance for the user
- SFT (from AIS), 15CA/15CB import
- OLTAS challan-status verification
- Defaults download (bulk pre-filled)
- Intimation u/s 143(1) download
- [MOAT] **PAN-mismatch gate** — hard-block filing/commit if client PAN mismatches imported data
- [MOAT] **No-silent-zeros** — auto-flag any field that's plausibly-non-zero but sits at 0 (from prefill/AIS)
- [MOAT] **Duplicate-merge** — dedupe identical transactions appearing in bank + AIS + broker + 26AS
- [MOAT] **Import-preview-before-commit** with side-by-side diff + accept/reject per row

### B2. DOCUMENT PARSING
- Form 16 (salary) PDF parse → salary schedule
- Form 16A/16B/16C parse
- Bank statement parse (interest + transactions)
- Mutual fund statements (CAMS, KFintech)
- Broker statements (per-broker templates)
- [MOAT] **Accurate salary field mapping** (basic/allowance/perquisite/exemption split) — no lossy dump-into-basic
- [MOAT] Digital-signature verification of imported documents

### B3. ACCOUNTING SOFTWARE
- Tally (Trial Balance, P&L, BS) — the "books-to-return" bridge
- Excel/CSV / JSON/XML bulk import-export
- [MOAT] **Multi-accounting** (Zoho, Marg, Busy, QuickBooks) — planned
- [MOAT] **Bank statement → 26AS → P&L receipt reconciliation** (turnover verification for 44AD/44ADA eligibility)

---

## PART C — E-FILING & SUBMISSION

### C1. DIRECT FILING
- ERI licence integration (Type-2 API)
- ITD-schema JSON generation with **official-schema validation hard-wired into the route** (fix the ITR-1 gap found in audit)
- Pre-upload validation + error locator
- DSC + eSign (Aadhaar) + EVC
- ITR-V download/storage, acknowledgment tracking
- One-click ITD login (secure credential store)
- Auto-email ITR-V to client
- [MOAT] **Type-2 + Type-3 dual-mode** (API auto-filing AND manual-bundle for offline/difficult cases)

### C2. BULK FILING
- Bulk upload (JSON/Excel), queue management, per-return status, error logs, retry, progress dashboard, completion report, summary

### C3. REVISED / UPDATED / RECTIFICATION
- 139(5) revised, 139(8A) ITR-U, 139(9) defective, 154 rectification, 155 amendment
- Original-vs-revised change tracking (side-by-side diff)
- Version control (all versions), lock/unlock
- Intimation-error analysis

---

## PART D — NOTICE, SCRUTINY & APPEALS  [MOAT — biggest untapped pain]

### D1. NOTICE INTAKE & CLASSIFICATION
- Auto-fetch notices from ITD **e-Proceeding portal**
- Auto-classify: 143(1), 143(2), 148, 147, 131 summons, 133(6), 263, 270A, 271AAB
- Severity scoring + statutory-deadline computation
- Deadline alerts (7-day), firm-wide notice register
- Notice-defense packet (one-click bundle: return + source docs + computation + import trail)

### D2. FACELESS ASSESSMENT (144B)
- Structured response drafting (grounds, submissions, attachments)
- Auto-draft submission from return + source docs
- Digital upload to e-Proceeding portal
- Submission/ack tracking, virtual-hearing scheduler, video-conferencing

### D3. DEMAND MANAGEMENT
- Outstanding-demand register (all clients/years)
- Demand-vs-return reconciliation (CPC computed vs filed)
- One-click demand payment (Challan 280 pre-filled)
- Section 220(6) installment request + 220(7) stay application
- Demand-waiver / appeal-effect tracking

### D4. APPEALS
- Form 35 (CIT(A)), Form 36 (ITAT), Form 36A (cross-objections)
- Grounds-of-appeal template library
- Appeal-fee calculator, cause-list status, hearing reminders
- Order receipt + **appeal-effect computation** (refund/demand recomputation after order)

### D5. SETTLEMENT & 264
- Form 34B settlement commission + immunity-from-penalty tracking
- Section 264 revision by Commissioner

### D6. REFUND MANAGEMENT
- Refund-failure reason tracking (IFSC, Aadhaar-PAN, bank validation)
- Refund re-issue (237/239), refund banker tracking (CMP NSDL)
- **Section 244A interest on delayed refund auto-computation**
- Auto-refund-status polling (daily) + client notify on credit

---

## PART E — TDS COMPLIANCE  [SUITE — highest-frequency, most-sticky]

> If you add ONE adjacent module, make it TDS. It is monthly, painful, and what KDK/SAG lock clients in with.

### E1. TDS RETURNS
- Form 24Q (salary), 26Q (non-salary), 27Q (non-resident), 27EQ (TCS), 27A (control chart)
- Form 26QB (property 194IA), 26QC (rent 194IB), 26QD (contractor 194M), 26QE (VDA 194S)

### E2. TDS COMPUTATION
- Employee-wise 24Q: salary TDS, perquisites, exemptions, deductions, projection, quarterly shortfall
- Deductee-wise 26Q: section-wise rates (194A/C/D/H/I/J/M/N...), thresholds, PAN-not-available 20%, higher-rate tracking
- Section 197 lower-deduction certificate (apply + track)
- Section 195 nil-deduction certificate (foreign payments)
- 15G/15H validation, TDS-liability vs payment reconciliation

### E3. CHALLAN & TRACES
- Challan 281 booking per deductee+quarter
- Auto-match challan↔deductees (CPC's top error source); unmatched-challan resolution
- Short-payment identification (→234E), excess carry-forward
- TRACES login, justification report, conso-file download, defaults report
- Form 16 / 16A / 16B / 16C / 27D generation (bulk, DSC, email)
- TDS-credit mismatch report (TRACES vs AIS vs 26AS)

### E4. TDS CORRECTIONS
- C1 (deductor details), C2 (challan), C3 (deductee), C4 (24Q annex II), C5 (PAN update), C9 (add challan)
- Correct cascade order enforcement (C2 before C3)

### E5. TDS COMPLIANCE TRACKING
- Deposition due dates (7th; Mar=30 Apr), quarterly return dates
- 234E (₹200/day capped) + 271H penalty auto-computation
- 26QB/26QC 30-day deadline tracker

---

## PART F — GST COMPLIANCE  [SUITE]

### F1. GST RETURNS
- GSTR-1 (monthly/QRMP, HSN, B2B/B2C/export/nil split), GSTR-1A
- GSTR-3B (monthly summary + payment), GSTR-2B (auto-ITC anchor)
- GSTR-9, GSTR-9C (reconciliation statement), GSTR-4 (composition), CMP-08
- GSTR-7 (TDS), GSTR-8 (TCS)

### F2. GST RECONCILIATION
- **2B vs purchase-register reconciliation** (the monthly nightmare)
- GSTR-1 vs 3B liability match; ITC-utilization tracker (CGST/SGST/IGST order)
- E-way-bill vs GSTR-1; GSTR-9 vs 3B annual
- **GSTR vs ITR turnover triple-match** (GSTR-1 vs PGBP vs 26AS) with reason capture (exempt/zero-rated/composition)

### F3. E-INVOICING & E-WAY BILL
- E-invoice (IRP, IRN, QR), cancellation/credit-note
- E-way-bill generation (bulk), distance calculator

### F4. GST NOTICES
- DRC-01 (SCN response), DRC-06 (reply), DRC-03 (voluntary payment), APL-01 appeal-tracking

---

## PART G — EMPLOYEE / PAYROLL / LABOUR  [SUITE]

- Salary-structure setup (CTC→take-home), monthly payroll
- Investment declaration (12BB) collect/verify/apply; provisional vs final TDS
- Branded salary slips; full & final settlement (leave encashment, gratuity, bonus, notice recovery)
- PF (12%+12%, EPS split), EPFO ECR upload, UAN management, Forms 5/10/12A
- ESI (3.25%+0.75%), ESI Form 5
- PT (state-wise) + annual return
- Gratuity actuarial estimate, leave tracking, bonus computation, LWF
- Labour compliance reminders

---

## PART H — COMPANY LAW / MCA  [SUITE]

- Form AOC-4, MGT-7/MGT-7A, ADT-1, DIR-12, MGT-14, INC-20A
- Board/AGM minutes, registers, share-certificate gen, DIN/DSC tracking
- XBRL tagging + validation
- SPICe+ incorporation, RUN name reservation, DIN application, MoA/AoA templates

---

## PART I — AUDIT REPORTS & STATUTORY FORMS  [MOAT depth]

- Forms 3CA/3CB/3CD with **all 44 clauses structured as input fields** (not a shell), incl. Clause 43B, 40A(2)/(3)/(7), 41, 56(2)(viib), 36(1)(vii), 30A/B/C, 34, 42 (deemed dividend), 44 (GST expense split), speculation-loss clause
- Auto cross-reference Clause 34 ↔ TRACES TDS defaults
- **Audit checklist + working-paper management** (link evidence per clause)
- Review/sign-off workflow (assistant→senior→partner); audit-query management
- **UDIN generation/renewal/revocation** (ICAI-mandated — high-anxiety)
- Form 10E, 67, 10-IEA, 12BB, 15G/15H, 10/10B/10BB, 15CA/15CB, 3CEB, 49A/49AA

---

## PART J — TRUST & INSTITUTION  [SUITE]

- Forms 10A/10AB/10AC/10AD; URN tracking
- Sections 12AB / 10(23C) / 80G / 35 approvals
- Provisional/permanent registration + renewal reminders
- Form 10 (85% accumulation), 10B/10BB audit
- DARPAN + FCRA tracking
- 80G donation-receipt generator, donation statement, anonymous-donation (>5%) tracking

---

## PART K — ADVANCE TAX & CHALLANS

- Quarterly calculation + due-date reminders; 234B/234C interest
- Installment-wise computation; Challans 280/281/282/234E
- E-challan auto-fill + paper-challan print
- Net-banking/UPI/card payment
- OLTAS verification, TRACES challan download, CIN tracking, BSR validation
- Challan/PAN correction via TRACES; payment history; outstanding alerts

---

## PART L — INTERNATIONAL TAXATION & NRI  [MOAT — underserved niche]

- DTAA relief, Form 67 (auto-fill from foreign data)
- TP documentation, Form 3CEB; Section 195 TDS; 15CA/15CB
- **Resident/NRI/RNOR engine**: 183-day tracker, RNOR −300/−182 day tests, deemed-residency 6(1A) test, citizen 120-day rule, RNOR→Resident conversion alerts
- Treaty-benefit calculator; Schedule FA (foreign assets, JSON lump-sum); FEMA checks
- Foreign income + foreign-tax-paid tracking
- US/CA-India-specific reportable-account items

---

## PART M — CLIENT & CASE / PRACTICE MANAGEMENT
- Client master (PAN, Aadhaar, contact), categorization, multi-year retention, family grouping, tags, doc storage
- Case creation/assignment/due-dates/status/priority/comments

---

## PART N — REPORTS & MIS
- Client tax summary, ITR status, TDS summary, advance-tax, refund/demand, YoY comparison
- E-return error locator, validation summary, scrutiny triggers, **mismatch reports (26AS/AIS vs ITR)**
- One-page computation, tax-saving suggestions, refund/demand client report
- Practice: revenue, outstanding, client categorization, VIP, dormant, retention, service-wise revenue, team productivity, time-tracking, notice summary
- MIS dashboards (charts, pie income-sources, bar monthly-filing, pending/completed, real-time)

---

## PART O — CALCULATORS & UTILITIES
- HRA, capital-gains, depreciation, gratuity, leave-encashment, commuted-pension, 89 relief
- Advance-tax, slab finder, surcharge/cess, marginal-relief, GSTR-vs-ITR, wealth-tax (legacy), refund-interest, loan-interest
- **[MOAT]** **Compound interest on demands**, **CII index table**, **grandfathering NAV lookup**

---

## PART P — CALENDAR & DUE DATES
- Compliance calendar (ITR, TDS, advance-tax dates)
- Custom per-client due dates, extension tracking, Google/Outlook sync
- Push/SMS/email reminders, color-coded view, auto-prioritization, risk/revenue prioritization

---

## PART Q — E-SERVICES & QUICK TOOLS
- E-payment gateway, PAN validation (NSDL/ITD API), TAN validation
- PAN application (49A/49AA), TAN application (49B), PAN correction, status checks
- Aadhaar-PAN linking, representative registration, auto-fill name per PAN DB

---

## PART R — MULTI-USER & ACCESS CONTROL
- Multi-user, role-based (view/edit/admin), activity logs, simultaneous login, client assignment, password policy, session timeout, 2FA, audit trail, IP whitelist

---

## PART S — OTP AUTOMATION  [MOAT]
- Bulk SMS/WhatsApp/email OTP requests, follow-ups, templates, multi-language
- OTP-status dashboard, auto-populate in filing, validity tracking, resend, client notification, one-click filing, queue-based auto-filing, invalid-OTP error handling
- E2E OTP encryption, OTP audit log, device tracking, SMS fallback, IVR, help-desk

---

## PART T — AUTOMATED DOCUMENT SHARING  [MOAT]
- Auto-PDF computation, WhatsApp/email/SMS send, branding templates, auto-send ITR-V/ack, filing-success notification, e-verification instructions
- Client approval workflow (approve/reject, comments, auto-notify CA, status)
- Password-protected PDFs, watermarking, view-only, 30-day expiry links, read-receipts, download tracking, acknowledgment button

---

## PART U — INTEGRATED ACCOUNTING & BILLING
- Double-entry: chart of accounts, journal, ledgers, trial balance, P&L, BS, cash-flow, bank reconciliation
- Automated fee calc (complexity-based), service/client-wise billing, final invoice, credit/debit notes, recurring billing, branding
- Payments: receipts, modes, aging analysis, auto-reminders, advance tracking, refunds, bank import, auto-reconcile, UPI QR
- Expenses: entry, vendors, bill booking, vendor payment, TDS on payment, reports
- Firm reports: revenue, client profitability, expense analysis, receivables aging, cash-flow forecast, budget-vs-actual

---

## PART V — ADVANCED ANALYTICS & INSIGHTS  [MOAT]
- Practice: revenue YoY, client acquisition, service mix, productivity, seasonality, retention
- Client: profitability (fees vs effort), **tax-saving opportunities**, risk profile, payment behavior, LTV
- Predictive AI: refund prediction, **notice-probability scoring**, revenue forecast, churn prediction
- Visual: interactive dashboards, heat maps, trend charts, comparative analysis, drill-down, custom report builder, export Excel/PDF, scheduled delivery, real-time

---

## PART W — COMMUNICATION & COLLABORATION
- Internal chat, task assignment + notifications, shared notes, @mentions, file sharing
- Client comms log: email, WhatsApp, SMS, phone, meeting logs; searchable history; timeline view

---

## PART X — DATA SECURITY & COMPLIANCE
- AES-256 at rest, SSL/TLS in transit, India data residency, DPDP, RBAC, 2FA, session mgmt, IP whitelist, password policy, hashed storage
- Audit trail (who/what/when, immutable, export)
- Right to erasure, data portability, consent management, ToS, privacy policy, AI liability waiver, CA professional-liability tracking
- Daily backups, offsite, one-click restore, point-in-time, DB export, DR plan, archival
- **[MOAT]** **Client-consent gating for ITD representation** (paper-trail)
- **[MOAT]** **SOC 2 Type II / ISO 27001 readiness** (win enterprise clients)
- **[MOAT]** Client data deletion on engagement-end; per-client export; instant staff-exit access revocation; DSC key security/renewal; client view-only portal access

---

## PART Y — UPDATES & MAINTENANCE
- Auto-update per AY; Budget update (Finance Act, 48h); ITD-schema update; FVU sync
- Multi-year (10+), migration, backward compatibility, release notes, notifications, beta program, rollback, staged rollout

---

## PART Z — UX & INTERFACE
- Dark/light, font-size, high-contrast, keyboard shortcuts (Excel-layout navigation), customizable dashboard, layout prefs, quick toolbar, recent items, bookmarks
- Wizard, tutorials, contextual help, smart next-action, progress indicators, tooltips, in-app notifications, welcome tour
- Fast load, lazy loading, caching
- **[MOAT]** **Excel-fidelity bulk power**: grid editor w/ Excel keyboard nav, paste-from-Excel, bulk ops, smart templates, print formats

---

## PART AA — INTEGRATIONS & API
- Tally, WhatsApp Business API, Twilio, MSG91, SendGrid, AWS SES, Razorpay, Google Drive, Slack, Google Calendar, Google Meet
- **REST API, webhooks, API docs, key management, rate limiting, versioning, sandbox**
- **[MOAT]** **Broker APIs** (Zerodha/Groww/Upstox/Angel for auto CG cost basis)

---

## PART AB — MULTI-LOCATION & WHITE-LABEL
- Multiple offices, branch segregation, centralized reporting, inter-branch transfer, franchise, white-label, revenue sharing, branch comparison
- **[MOAT]** **Multi-firm hosting** (one install, many independent firms w/ data isolation + branding)
- **[MOAT]** **Master-admin console + module metering** (per-firm licence of ITR / ITR+TDS / ITR+TDS+GST)

---

## PART AC — KNOWLEDGE BASE & TRAINING
- Contextual help, user manual, FAQ, live chat, tickets, knowledge base, community forum
- Tax library: IT Act full text, CBDT circulars (auto-update), case laws, tax updates, due-date calendar, forms/annexures, notifications/press releases

---

## PART AD — CUSTOMIZATION & FLEXIBILITY
- Templates (invoice, email, WhatsApp, notice-reply letterhead, reports)
- Custom approval workflows, task templates, custom fields, conditional logic, automation rules, business rules engine, workflow versioning, import/export workflows

---

## PART AE — DATA IMPORT/EXPORT
- Legacy import, export Excel/CSV/PDF (any report), bulk + selective export, data masking, import validation, error handling, preview-before-commit, import history

---

### IMPLEMENTATION PRIORITY (recommended order)

| Phase | Focus | Why |
|---|---|---|
| **P1** | Hard-return accuracy engine (A1–A10) + official-schema validation wired into every route + per-figure provenance + year-lock | Foundation; differentiates on correctness |
| **P2** | Import/reconciliation spine (B) + filing (C) | Fills returns correctly; KDK-class import accuracy |
| **P3** | **Notice/Scrutiny (D)** | Biggest untapped post-filing pain; beats incumbents |
| **P4** | **TDS suite (E)** | Highest-frequency, most-sticky retention module |
| **P5** | Depreciation engine (A4) + audit 3CD depth (I) + UDIN | Audit-grade quality; CA trust |
| **P6** | NRI engine (L) | Underserved, high willingness to pay |
| **P7** | GST suite (F) → Payroll (G) → MCA (H) | Adjacent-domain suite expansion |
| **P8** | Practice mgmt, billing, analytics, OTP, sharing, white-label multi-firm (M–AE) | Moats & monetization |
