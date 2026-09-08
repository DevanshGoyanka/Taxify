# 🎯 TAXIFY ROADMAP — RESTRUCTURED BY BUILD FLOW

> This is the definitive, build-sequenced master list for Taxify.
> It restructures all features (original list + audit gaps + beat-the-incumbents additions) into the **exact delivery order** the founder expects:

> **Phase 0** → ITR-1–7 computation end-to-end (imports → compliant JSON)
> → **Phase 1** → Practice management for ITR-1–7
> → **Phase 2** → Backup / Restore / Switch-from-existing-software
> → **Phase 3** → Billing & accounting for the firm/practitioner
> → **Phase 4** → WhatsApp/email automation (everify, send, communicate)
> → **Phase 5** → Notice handling
> → **Phase 6** → TDS
> → **Phase 7** → GST (full plan — decision to implement later)

> Convention: `[CORE]` = must ship for the product to be credible · `[MOAT]` = differentiator that beats incumbents · `[SUITE]` = adjacent-domain module.
> Phase 7 (GST) is fully planned but gated on a later go/no-go decision, as instructed.
> GST is laid out completely so that if the decision is "yes", it can be built without rework.

---

# PHASE 0 — ITR-1–7 COMPUTATION ENGINE, END-TO-END

> **Goal:** The core. A user imports data and gets a fully computed, officially-validated, compliant JSON return file for ITR-1 through ITR-7 — with nothing else needed.
> Success criterion: **any return generated must clear the official ITD schema validation and be e-file-ready.**
> This is the product's foundation; nothing ships before it is rock-solid.

## 0.1 ITR FORM SUPPORT (all 7 + updated)
- [CORE] ITR-1 (SAHAJ) — salaried individuals — full computation + JSON
- [CORE] ITR-2 — individuals/HUFs, no business income — full computation + JSON
- [CORE] ITR-3 — individuals/HUFs with business/profession income — full computation + JSON
- [CORE] ITR-4 (SUGAM) — presumptive — full computation + JSON
- [CORE] ITR-5 — firms, LLPs, AOPs, BOIs — full computation + JSON
- [CORE] ITR-6 — companies (except u/s 11) — full computation + JSON
- [CORE] ITR-7 — trusts, political parties, institutions — full computation + JSON
- [CORE] ITR-U — updated return (within 24 months)
- [CORE] **Official ITD-schema validation** (JSON against the CBDT-published schema) — hard-wired into every form's route, not just internal rules
- [CORE] Form-specific validations, mandatory fields, cappings per ITD rules
- [CORE] Automatic ITR form selection based on income sources (with readout of the deciding factors)
- [MOAT] **Year-locked builds** — each compute instance locked to one assessment year; cross-year field mixing is structurally impossible
- [MOAT] **Per-figure provenance** — every field on the return shows its source (imported doc / AIS / prefill / manual), clickable and auditable
- [SUITE] ITR-7 component/trust-type matrix (10A/10AB/12AB/80G/35/11 accumulation variants)

> **Sub-sections 0.2–0.11 are computed inside every applicable ITR form.** (ITR-1 has no CG/business/HP-schedule; ITR-2/3/4/5/6/7 each open the relevant sub-engines.) A single shared engine, rendered per-form.

## 0.2 SALARY INCOME (`[CORE]`)
- Multiple employers (auto-merge + duplicate-merge)
- Allowances (HRA, LTA, special allowances) with correct sub-heading split
- Perquisites valuation (car, accommodation, concessional loans, ESOP/RSU at vesting)
- Profit in lieu of salary
- Section 16 deductions (Standard, Professional tax)
- Relief u/s 89 for arrears/advance salary + Form 10E generation
- Leave encashment + gratuity calculation/exemption
- [MOAT] **Accurate salary-head mapping** — basic/HRA/perquisites/exemptions land in the correct ITR field (fixes the lossy "everything into basic" gap)

## 0.3 HOUSE PROPERTY (`[CORE]`)
- Multiple-property support (correct per-form floor iteration)
- Self-occupied vs let-out classification
- Deemed let-out for 3rd+ self-occupied property
- Annual value (GAV/NAV, municipal-tax deduction, 30% std., 24(b) interest)
- Loss from HP (−₹2L limit, carry-forward)
- [MOAT] Single-vs-multiple property gating (ITR-1 single only; ITR-2 full HP schedule)

## 0.4 BUSINESS & PROFESSIONAL INCOME (`[CORE]`)
- Books-of-accounts integration (P&L, BS mapping)
- Depreciation engine (see 0.4a)
- Business-expense validation; speculative/non-speculative split
- Presumptive: 44AD (6%/8%), 44ADA (50%), 44AE (goods carriages, per-vehicle tonnage split)
- 44AB audit-requirement check + threshold watch (₹1cr/₹10cr; 44AD ₹2cr; 44ADA ₹75L alerts)
- MAT for companies (book profit), AMT for individuals/LLPs (adjusted total income)
- [MOAT] Trial-balance → ITR mapping engine (GL→ITR head map, editable rules)
- [MOAT] Balance Sheet → Schedule BS / P&L → Schedule BP/PBP auto-mapping (ITR-3/5/6)
- [MOAT] Closing-stock valuation (Section 145A, GST inclusion)
- Related-party / 40A(2)/(3) / cash>₹10k checks

### 0.4a DEPRECIATION ENGINE `[MOAT]`
- Block-wise WDV computation (all 100%/40% etc. blocks)
- Additions/deletions per year; pro-rata (180-day rule) + 50% cap
- Additional depreciation 32(1)(iia)
- Section 50 slip rule; Section 43(6) WDV definition
- Audited WDV carry-forward year-over-year
- ITR-3/3CD depreciation schedule (Part A–B) auto-generation

## 0.5 CAPITAL GAINS (`[CORE]`)
- ST/LT classification (asset-wise holding period)
- Equity/MF listed: STCG/LTCG incl. Section 112A grandfathering (FMV @ 31-01-2018) + STT confirmation both sides
- [MOAT] Rate-change auto-split for transactions straddling 23-07-2024 (15%→20% STCG)
- Debt MF: LTCG with indexation
- Real estate: LTCG with indexation + Section 50C stamp-duty-vs-consideration
- Gold/jewellery/bonds, unlisted shares (50CA / section 56(2)(x) off-market & gift rules)
- Indexed cost-of-acquisition (CII table); cost-of-improvement tracking
- Sections 54, 54F, 54EC, 54EE, 54GB, 54G with reinvestment-compliance tracking (sale-in-3-years → taxable)
- Broker statement import (Zerodha, Groww, Upstox, Angel) with cost basis + grandfathering
- [MOAT] ESOP/RSU flow (perquisite at vesting + CG at sale, employer-TDS reconciliation)
- [MOAT] Corporate actions (bonus: cost ₹0 / retained period; rights; splits)
- [MOAT] JDA / land-pooling deemed transfer

## 0.6 OTHER SOURCES INCOME (`[CORE]`)
- Interest (banks/PO/FD/Savings), dividend (TDS-tracked)
- Family pension (₹15,000 / 1/3rd std.; new-regime ₹25,000)
- Lottery/races/crossword (flat 30%), machinery/equipment rental, royalty/patent
- Agricultural income (rate purposes, partial integration)
- [MOAT] Crypto/VDA (30% + 1% TDS u/s 194S, cost basis, schedule)
- [MOAT] Deemed-income items (2(24)(xii), 41(1), 28 deemed entries, 56(2)(x) gifts)
- [MOAT] Slump sale (Section 50B)

## 0.7 NEW TAX REGIME / 115BAC (`[CORE]`)
- Automatic old-vs-new comparison + recommendation engine (with reason)
- Side-by-side computation + visual chart
- Regime-wise allowed/disallowed breakup; marginal relief near threshold
- TDS regime intimation to employer
- Historical regime-choice per client
- Form 10-IEA generation (business opt-out)
- One-time (business, non-reversible) vs annual (salaried) opt-out tracking
- Investment-planning suggestions per regime

## 0.8 TAX CALCULATION (`[CORE]`)
- Age-wise slabs (old + new)
- Surcharge (10/15/25/37%) + marginal relief on surcharge
- Health & Education Cess (4%)
- Rebate u/s 87A with marginal relief (correct cap per regime/year)
- AMT / MAT; tax after TDS/TCS/advance/self-assessment
- Refund/demand; rounding to ₹10
- Residential-status impact on rates; agricultural-income rate impact

## 0.9 INTEREST & PENALTY (`[CORE]`)
- 234A, 234B, 234C (accurate installment-wise deferment), 234F, 244A
- [MOAT] Compound-interest calculator for notice demands
- 270A, 271H, 272A; penalty-waiver request + reasonable-cause template

## 0.10 LOSS SET-OFF & CARRY-FORWARD (`[CORE]`)
- Intra-head + inter-head current-year set-off
- Business (8y), speculation (4y), capital (8y), HP (8y), unabsorbed depreciation (indefinite), 35AD (15y, no set-off)
- Set-off order enforcement; auto-track brought-forward losses
- Form 10-IEA carry-forward reporting
- New-regime loss restrictions (no HP loss, BF restrictions)

## 0.11 DATA IMPORT & RECONCILIATION (`[CORE]` — the spine)
> The engine is only as good as the data it fills. This is the accuracy lever.
- [CORE] **ITD Prefill import** (authoritative populator — the spine, not AIS)
- [CORE] Form 26AS import (TDS + TCS ledger)
- [CORE] AIS import (all information categories)
- [CORE] TIS import
- [MOAT] **AIS/TIS as diff, NOT auto-populator** — compute "prefill vs AIS vs entered" 3-way variance for the user
- SFT (from AIS), 15CA/15CB import
- OLTAS challan-status verification; defaults download (bulk pre-filled)
- Form 16 (salary) PDF parse; Form 16A/16B/16C; bank statement; MF statements (CAMS/KFintech)
- [MOAT] **PAN-mismatch gate** — hard-block commit/filing if client PAN mismatches imported data
- [MOAT] **No-silent-zeros** — auto-flag plausibly-non-zero fields sitting at 0
- [MOAT] **Duplicate-merge** — dedupe identical transactions across bank + AIS + broker + 26AS
- [MOAT] **Import-preview-before-commit** with side-by-side diff + accept/reject per row
- Digital-signature verification of imported documents

## 0.12 COMPLIANT JSON GENERATION (`[CORE]` — the end goal)
- [CORE] Generate ITD-schema JSON for every form
- [CORE] **Pre-upload official-schema validation** with field-level error locator
- [CORE] Deterministic, repeatable output (same input → same JSON hash — HMAC digest)
- [CORE] JSON roundtrip: import JSON → validate → recompute → verify identity
- [MOAT] Audit-trail of every computed figure (full calculator chain traceable)
- [MOAT] JSON preview + human-readable draft side-by-side

> **PHASE 0 DONE = every ITR-1–7 can be imported, computed, validated, and emitted as schema-clean JSON.** This is the hard, defensible core. Do not advance until this is solid.

---

# PHASE 1 — PRACTICE MANAGEMENT (for ITR-1–7)

> **Goal:** Rely on the Phase-0 core across many clients. This is the professional-workbench layer.

## 1.1 CLIENT MASTER & CASES
- Client master (PAN, Aadhaar, contact), categorization (individual/HUF/firm/company...)
- Multi-year data retention; family grouping; tags (VIP/urgent/dormant); doc storage
- Case creation, task assignment, due-date tracking, status, priority, comments/notes
- Multi-user, role-based (view/edit/admin), client assignment, audit trail, 2FA

## 1.2 FILING WORKFLOW (per return)
- Draft → validate → review → e-verify → file → acknowledge status pipeline
- Status tracking per client/r̥eturn; batch/bulk return dashboard
- Bulk filling: upload (JSON/Excel), queue, per-return status, error logs, retry, progress, completion report
- Original-vs-revised version control; lock/unlock; side-by-side diff
- 139(5) revised, 139(8A) ITR-U, 139(9) defective, 154 rectification, 155 amendment

## 1.3 E-FILING & SUBMISSION
- ERI licence integration (Type-2 API) + [MOAT] Type-3 offline bundle dual-mode
- DSC, eSign (Aadhaar), EVC; ITR-V download/storage
- Acknowledgment tracking; one-click ITD login (secure credential store); auto-email ITR-V
- Pre-upload validation wired into route

## 1.4 REPORTS & MIS
- Client tax summary, ITR status, refund/demand, YoY comparison
- E-return error locator, validation summary, scrutiny-trigger warnings
- Mismatch reports (26AS/AIS/TRACES vs ITR)
- One-page computation, tax-saving suggestions, refund/demand client report
- MIS dashboards (income-source pie, monthly-filing bar, pending/completed, real-time)

## 1.5 CALENDAR & DUE DATES
- Compliance calendar (ITR due dates), custom per-client due dates, extension tracking
- Google/Outlook sync; push/SMS/email reminders; color-coded view; auto-prioritization

## 1.6 CALCULATORS & UTILITIES
- HRA, capital-gains, depreciation, gratuity, leave-encashment, commuted pension, 89 relief
- Advance-tax, slab finder, surcharge/cess, marginal relief, refund-interest, loan-interest
- CII index table; grandfathering NAV lookup

## 1.7 KNOWLEDGE BASE & TRAINING
- Contextual help, user manual, FAQ, live chat, tickets, knowledge base
- Tax library: IT Act text, CBDT circulars (auto-update), case laws, due-date calendar, forms/annexures

---

# PHASE 2 — BACKUP / RESTORE / SWITCH-FROM-EXISTING-SOFTWARE

> **Goal:** Painless continuity. Backup safety + one-click migration from the incumbents (Winman/KDK/SAG/CompuTax/Clear).

## 2.1 BACKUP & RESTORE
- Automatic daily backups; offsite cloud backup; one-click restore; point-in-time recovery
- Complete DB export; disaster-recovery plan; data archival (old years)
- Backup hardening: encrypted, retention policy, restore dry-run verification
- Versioned schema-safe backup (survives software upgrades)

## 2.2 SWITCH / MIGRATION `[MOAT]`
- **One-click migration from Winman / KDK / SAG / CompuTax / ClearTax**
- Import client master, prior-year returns, losses carried forward, depreciation WDV opening balances
- Guided onboarding wizard (data mapping, field-level review, dry-run before commit)
- Migration validation report (what came over, what needs manual entry)
- **Winman-equivalent keyboard map** + **concurrent-tool mode** (run alongside incumbents during transition, keep in sync)
- [MOAT] Legacy-data continuity: 10+ years of prior returns + BF-loss/depreciation carried correctly into the new AY
- Rollback after migration if issues found

---

# PHASE 3 — BILLING & ACCOUNTING (for the firm / practitioner)

> **Goal:** The CA firm runs its own books + client billing in one place.

## 3.1 FIRM ACCOUNTING (double-entry)
- Chart of accounts, journal entries, ledgers, trial balance, P&L, balance sheet, cash flow
- Bank reconciliation
- Expense management: entry, vendors, bill booking, vendor payment, TDS on payment, reports

## 3.2 BILLING & INVOICING
- Automated fee calculation (ITR complexity-based); service-wise & client-wise billing
- Final invoice on service completion; credit/debit notes; recurring billing (retainers)
- Invoice customization (firm branding)
- Payment: receipts, multiple modes, aging analysis, auto-reminders, advance tracking, refunds
- Bank integration (statement import), auto-reconciliation (payments vs invoices), UPI QR

## 3.3 FIRM FINANCIAL REPORTS
- Revenue (month/year-wise), client profitability, expense analysis, receivables aging, cash-flow forecast, budget-vs-actual

---

# PHASE 4 — WHATSAPP / EMAIL AUTOMATION (everify, send, communicate)

> **Goal:** Close the loop with clients. Automated collection, notification, and e-verification — the productivity/experience moat.

## 4.1 OTP / EVERIFY AUTOMATION
- Bulk SMS / WhatsApp / email OTP requests; follow-ups; templates; multi-language
- OTP-status dashboard; auto-populate OTP in filing; validity tracking; resend; client notify on success
- One-click filing once OTP received; queue-based auto-filing; invalid-OTP error handling
- E2E OTP encryption; OTP audit log; device tracking; SMS fallback; IVR; help-desk

## 4.2 AUTOMATED DOCUMENT SHARING
- Auto-generate computation PDF; WhatsApp (Business API) / email / SMS send
- Branding templates; auto-send ITR-V + acknowledgment; filing-success notification; e-verification instructions
- Client approval workflow (approve/reject, comments, auto-notify CA, status tracking)
- Password-protected PDFs, watermarking, view-only, 30-day expiry links, read-receipts, download tracking, acknowledgment button

## 4.3 COMMUNICATION & COLLABORATION
- Internal chat, task assignment + notifications, shared notes, @mentions, file sharing
- Client comms log: email, WhatsApp, SMS, phone, meeting logs; searchable; timeline view
- E-payment gateway; Google Drive; Slack; Google Calendar/Meet integrations

---

# PHASE 5 — NOTICE HANDLING `[MOAT — biggest untapped post-filing pain]`

> **Goal:** Respond to notices & demand efficiently, end-to-end. Faceless-assessment readiness.

## 5.1 NOTICE INTAKE & CLASSIFICATION
- Auto-fetch notices from ITD **e-Proceeding portal**
- Auto-classify: 143(1), 143(2), 148, 147, 131 summon, 133(6), 263, 270A, 271AAB
- Severity scoring + statutory-deadline computation; 7-day deadline alerts
- Firm-wide notice register (client + year view)
- **Notice-defense packet** — one-click bundle (return + source docs + computation + import trail)

## 5.2 FACELESS ASSESSMENT (144B)
- Structured response drafting (grounds, submissions, attachments)
- Auto-draft submission from return + source docs
- Digital upload to e-Proceeding portal; submission/ack tracking
- Virtual-hearing scheduler + video-conferencing

## 5.3 DEMAND MANAGEMENT
- Outstanding-demand register (all clients/years)
- Demand-vs-return reconciliation (CPC computed vs filed)
- One-click demand payment (Challan 280 pre-filled)
- Section 220(6) installment request; 220(7) stay application; demand-waiver/appeal-effect tracking

## 5.4 APPEALS
- Forms 35 (CIT(A)), 36 (ITAT), 36A (cross-objections); grounds-of-appeal library
- Appeal-fee calculator; cause-list status; hearing reminders
- Order receipt + **appeal-effect computation** (recompute refund/demand after order)

## 5.5 SETTLEMENT & 264
- Form 34B settlement commission; Section 264 Commissioner revision

## 5.6 REFUND MANAGEMENT
- Refund-failure reason tracking (IFSC, Aadhaar-PAN, bank validation)
- Refund re-issue (237/239); refund-banker tracking (CMP/NSDL)
- Section 244A interest auto-computation; auto-refund-status polling + client notify on credit

---

# PHASE 6 — TDS COMPLIANCE `[SUITE — highest-frequency, most-sticky]`

> **Goal:** The monthly retention module. If it's built well, CAs don't leave.

## 6.1 TDS RETURNS
- Form 24Q (salary), 26Q (non-salary), 27Q (non-resident), 27EQ (TCS), 27A (control chart)
- Form 26QB (property 194IA), 26QC (rent 194IB), 26QD (contractor 194M), 26QE (VDA 194S)

## 6.2 TDS COMPUTATION
- Employee-wise 24Q: salary TDS, perquisites, exemptions, deductions, projection, quarterly shortfall
- Deductee-wise 26Q: section-wise rates (194A/C/D/H/I/J/M/N...), thresholds, PAN-not-available 20%, higher-rate tracking
- Section 197 lower-deduction certificate (apply + track); Section 195 nil-deduction (foreign)
- 15G/15H validation; TDS-liability vs payment reconciliation

## 6.3 CHALLAN & TRACES
- Challan 281 booking per deductee+quarter; auto-match challan↔deductees (CPC's top error source)
- Unmatched-challan resolution; short-payment identification (→234E); excess carry-forward
- TRACES login, justification report, conso-file download, defaults report
- Form 16 / 16A / 16B / 16C / 27D generation (bulk, DSC, email); AIS-TDS-26AS mismatch report

## 6.4 TDS CORRECTIONS
- C1 (deductor), C2 (challan), C3 (deductee), C4 (24Q annex II), C5 (PAN update), C9 (add challan)
- Cascade-order enforcement (C2 before C3)

## 6.5 TDS COMPLIANCE TRACKING
- Deposition due dates (7th; Mar=30 Apr); quarterly return dates
- 234E (₹200/day capped) + 271H penalty auto-computation
- 26QB/26QC 30-day deadline tracker

---

# PHASE 7 — GST COMPLIANCE `[SUITE — full plan; go/no-go decided later]`

> **Status:** Fully planned. **Decision deferred.** If greenlit, build in this order (self-holding sub-phases so partial builds still deliver value).

## 7.1 GST RETURNS
- GSTR-1 (monthly/QRMP, HSN, B2B/B2C/export/nil split), GSTR-1A
- GSTR-3B (monthly summary + payment), GSTR-2B (auto-ITC anchor)
- GSTR-9, GSTR-9C (reconciliation statement), GSTR-4 (composition), CMP-08
- GSTR-7 (TDS on GST), GSTR-8 (TCS on GST)

## 7.2 GST RECONCILIATION
- **2B vs purchase-register reconciliation** (the monthly nightmare)
- GSTR-1 vs 3B liability match; ITC-utilization tracker (CGST/SGST/IGST order)
- E-way-bill vs GSTR-1; GSTR-9 vs 3B annual
- **[MOAT] GSTR-vs-ITR turnover triple-match** (GSTR-1 vs PGBP vs 26AS) with reason capture

## 7.3 E-INVOICING & E-WAY BILL
- E-invoice (IRP, IRN, QR), cancellation/credit-note
- E-way-bill generation (bulk), distance calculator

## 7.4 GST NOTICES
- DRC-01 (SCN response), DRC-06 (reply), DRC-03 (voluntary payment), APL-01 appeal tracking

> **GST decision gate:** at the end of Phase 6, review build capacity + client demand. If GO → build 7.1→7.2→7.3→7.4. If NO-GO → GST stays a planned epic, not started.

---

# PHASE 8 — PENDING MODULES (scoped but not in the core flow)

> These exist in the full product vision but are **not** in the founder's build flow. Keep as backlog; revisit after Phase 7.

- **Payroll / PF / ESI / labour** — salary structure, monthly payroll, 12BB, PF+ECR+UAN, ESI, PT, F&F, gratuity, bonus
- **Company law / MCA** — AOC-4, MGT-7/7A, ADT-1, DIR-12, MGT-14, INC-20A, XBRL, SPICe+ incorporation
- **Trust & institution full suite** — this is partially in Phase 0 (ITR-7); full Form 10A/10AB/10AC, 12AB, DARPAN, FCRA, 80G receipts = Phase 8
- **NRI / international** — resident/RNOR engine, 183-day tracker, deemed residency, Form 67, Schedule FA, DTAAs
- **Advanced analytics** — refund prediction, notice-probability scoring, revenue forecast, churn, profitability, LTV
- **Multi-firm / white-label hosting** — one install, many firms, data isolation, master console, module metering

---

# SYSTEM & TECHNICAL (spans all phases)

> These are cross-cutting and land in every phase, not a distinct delivery step.

## S.1 SECURITY
- AES-256 at rest; SSL/TLS in transit; India data residency; DPDP
- RBAC, 2FA, session mgmt, IP whitelist, password policy, hashed storage
- Audit trail (who/what/when, immutable, export)
- Right-to-erasure, data portability, consent management, ToS, privacy policy, AI liability waiver, CA professional-liability tracking
- [MOAT] Client-consent gating for ITD representation
- [MOAT] SOC 2 Type II / ISO 27001 readiness
- [MOAT] Client data deletion on engagement-end; per-client export; instant staff-exit access revocation; DSC key security/renewal

## S.2 UPDATES & MAINTENANCE
- Auto-update per AY; Budget update (Finance Act, 48h); ITD-schema update; FVU sync
- Multi-year (10+), backward compatibility, release notes, notifications, beta program, rollback, staged rollout

## S.3 UX
- Dark/light, font size, high-contrast, keyboard shortcuts
- [MOAT] Excel-fidelity bulk grid (Excel keyboard nav, paste-from-Excel, bulk ops, smart templates, print formats)
- Wizard, tutorials, contextual help, smart next-action, progress indicators, tooltips, notifications, welcome tour
- Fast load, lazy loading, caching; customizable dashboard; drag-drop widgets

## S.4 INTEGRATIONS & API
- Tally; WhatsApp Business API; Twilio, MSG91, SendGrid, AWS SES; Razorpay; Google Drive/Slack/Calendar/Meet
- REST API, webhooks, API docs, key management, rate limiting, versioning, sandbox
- [MOAT] Broker APIs (Zerodha/Groww/Upstox/Angel) for auto CG cost basis

## S.5 DATA IMPORT/EXPORT
- Legacy import; export Excel/CSV/PDF (any report); bulk + selective export; data masking; import validation + error handling + preview-before-commit + history

---

## ✅ SUMMARY OF THE BUILD FLOW

| Phase | Focus | Core deliverable |
|---|---|---|
| **0** | ITR-1–7 computation end-to-end | **Every form: import → compute → validate → compliant JSON** |
| **1** | Practice management | Multi-client workbench on the core |
| **2** | Backup / Restore / Switch | Data safety + one-click migration from incumbents |
| **3** | Billing & accounting | Firm runs its own books + client billing |
| **4** | WhatsApp/email automation | everify, send, communicate |
| **5** | Notice handling | Faceless-assessment response end-to-end |
| **6** | TDS | Monthly retention module |
| **7** | GST (decide later) | Full plan ready; gated |
| **8** | Pending modules | Backlog: payroll/MCA/trust/NRI/analytics/white-label |
| **S** | System/technical | Cross-cutting, lands in every phase |

---

# APPENDIX — ORIGINAL COMPLETE & FINAL TAX ERP FEATURE LIST

> The founder's original feature list, appended verbatim for completeness and cross-reference. Every item below is already mapped into the phased build flow above; this section preserves the original grouping as a reference index.

---

## PART A: CORE TAX COMPUTATION FEATURES (230+ Features)

### 1. ITR FILING & COMPUTATION

#### 1.1 ITR Form Support (10 Features)
- ITR-1 (SAHAJ) - Salaried individuals
- ITR-2 - Individuals/HUFs without business income
- ITR-3 - Individuals/HUFs with business/profession income
- ITR-4 (SUGAM) - Presumptive taxation
- ITR-5 - Firms, LLPs, AOPs, BOIs
- ITR-6 - Companies (except exempt u/s 11)
- ITR-7 - Trusts, political parties, institutions
- ITR-U - Updated Return (within 24 months)
- Automatic ITR form selection based on income sources
- Form-specific validations as per ITD rules

#### 1.2 Salary Income Computation (8 Features)
- Salary from multiple employers
- Allowances (HRA, LTA, Special Allowances)
- Perquisites valuation (car, accommodation, loans, etc.)
- Profit in lieu of salary
- Deduction u/s 16 (Standard deduction, Professional tax)
- Relief u/s 89 for arrears/advance salary
- Leave encashment calculation
- Gratuity calculation & exemption

#### 1.3 House Property Income (7 Features)
- Multiple properties support
- Self-occupied vs Let-out classification
- Deemed let-out for 3rd property onwards
- Annual value computation
- Municipal taxes deduction
- Interest on home loan (u/s 24b)
- Standard deduction 30%
- Loss from house property (-₹2 lakh limit)

#### 1.4 Business & Professional Income (12 Features)
- Books of accounts integration (P&L, Balance Sheet)
- Depreciation as per IT Act (Block-wise, WDV method)
- Business expenses validation
- Presumptive taxation u/s 44AD (6%/8% of turnover)
- Presumptive taxation u/s 44ADA (50% for professionals)
- Presumptive taxation u/s 44AE (goods carriages)
- Speculative/non-speculative business classification
- Section 44AB audit requirement check
- MAT (Minimum Alternate Tax) for companies
- AMT (Alternate Minimum Tax) for certain individuals
- Book profit calculation (for MAT)
- Adjusted total income calculation (for AMT)

#### 1.5 Capital Gains (12 Features)
- Short-term vs Long-term classification (asset-wise holding period)
- Equity shares/mutual funds (listed) - LTCG/STCG computation
- Debt mutual funds - LTCG with indexation
- Real estate/property - LTCG with indexation
- Gold, jewelry, bonds - LTCG computation
- Unlisted shares computation
- Indexed cost of acquisition calculator
- Section 54 exemption (residential property reinvestment)
- Section 54F exemption (non-residential to residential)
- Section 54EC exemption (NHAI/REC bonds)
- Cost of improvement tracking
- Broker statement import (Zerodha, Groww, Upstox, etc.)

#### 1.6 Other Sources Income (8 Features)
- Interest from banks, post office, bonds
- Dividend income (with TDS tracking)
- Family pension (with standard deduction ₹15,000 or 1/3rd)
- Lottery, race horses, crossword puzzles (flat 30% tax)
- Rental income from machinery/equipment
- Royalty/patent income
- Agricultural income (exempt but shown for rate purposes)
- Cryptocurrency/Virtual Digital Assets (30% tax)

### 2. DEDUCTIONS & EXEMPTIONS

#### 2.1 Chapter VIA Deductions - 80C to 80U (35 Features)
- 80C - LIC premium (max ₹1.5 lakh)
- 80C - PPF contribution
- 80C - ELSS mutual funds
- 80C - NSC (National Savings Certificate)
- 80C - Home loan principal repayment
- 80C - Tuition fees (2 children)
- 80C - SSY (Sukanya Samriddhi Yojana)
- 80C - Tax-saver FDs
- 80CCC - Pension funds
- 80CCD(1) - NPS employee contribution
- 80CCD(1B) - Additional NPS ₹50,000
- 80CCD(2) - Employer NPS contribution (14% for govt, 10% for private)
- 80CCH(2) - Agniveer Corpus Fund
- 80D - Medical insurance (self, family, parents)
- 80D - Preventive health check-up (₹5,000)
- 80DD - Disabled dependent maintenance
- 80DDB - Medical treatment of specified diseases
- 80E - Education loan interest (no limit)
- 80EE - First-time home buyer (interest up to ₹50,000)
- 80EEA - Affordable housing (interest up to ₹1.5 lakh)
- 80EEB - Electric vehicle loan interest
- 80G - Donations (50%/100%, with/without limit)
- 80GG - Rent paid (for non-HRA recipients)
- 80GGA - Scientific research donations
- 80GGB - Political party donations (companies)
- 80GGC - Political party donations (individuals)
- 80IA to 80IE - Infrastructure/industrial undertakings
- 80JJAA - Employment generation
- 80LA - Offshore banking units
- 80P - Cooperative societies
- 80QQB - Royalty income (authors/artists)
- 80RRB - Patent royalty
- 80TTA - Interest on savings (individuals - ₹10,000)
- 80TTB - Interest on deposits (senior citizens - ₹50,000)
- 80U - Disabled individuals

#### 2.2 Section 10 Exemptions (8 Features)
- 10(13A) - HRA (House Rent Allowance)
- 10(5) - LTA (Leave Travel Allowance)
- 10(10) - Gratuity exemption
- 10(10AA) - VRS (Voluntary Retirement Scheme) exemption
- 10(10C) - Commuted pension
- 10(1) - Agricultural income (fully exempt)
- 10(14) - Other allowances (conveyance, etc.)
- 10(23C) - Trust/institution income

### 3. NEW TAX REGIME (SECTION 115BAC) - 20 Features

#### 3.1 Old vs New Regime Comparison
- Automatic regime comparison calculator
- Side-by-side tax computation display
- Visual comparison chart/graph
- Regime-wise breakup of allowed/disallowed deductions
- Marginal relief calculation (income near ₹12 lakh threshold)
- Recommendation engine (suggests beneficial regime)
- TDS regime selection intimation to employer
- Historical regime choice tracking per client

#### 3.2 New Regime Specific Features
- Enhanced standard deduction (₹75,000 for FY 2024-25)
- Enhanced rebate u/s 87A (up to ₹60,000 for income ≤₹12L)
- Employer NPS contribution allowed (80CCD(2) - 14%)
- Agniveer Corpus Fund deduction allowed (80CCH(2))
- Additional employee cost deduction allowed (80JJAA)
- Family pension deduction allowed (₹25,000 limit)
- Loss set-off restrictions (no house property loss in new regime)
- Brought forward loss restrictions
- Form 10-IEA generation (opt-out for business income)
- One-time opt-out tracking (non-reversible for business)
- Annual opt-in/opt-out for salaried
- Investment planning suggestions based on regime

### 4. TAX CALCULATION (15 Features)
- Slab-based tax computation (age-wise slabs)
- Old regime slab rates
- New regime slab rates
- Surcharge calculation (10%/15%/25%/37% based on income)
- Marginal relief on surcharge
- Health & Education Cess (4%)
- Rebate u/s 87A (old regime: ₹12,500; new regime: ₹25,000)
- AMT (Alternate Minimum Tax) for LLP/individuals
- MAT (Minimum Alternate Tax) for companies
- Tax payable after TDS/TCS/advance tax/self-assessment
- Total tax liability summary
- Refund/demand calculation
- Rounded off tax (to nearest ₹10)
- Residential status impact on tax rates
- Agricultural income rate impact calculation

### 5. INTEREST & PENALTY CALCULATIONS (12 Features)

#### 5.1 Interest
- 234A - Interest for default in furnishing return
- 234B - Interest for default in payment of advance tax
- 234C - Interest for deferment of advance tax
- 234F - Late filing fee (₹5,000 or ₹1,000)
- 244A - Interest on refund (if ITD delays)
- Automatic calculation based on due dates
- Interest calculator for notice demands (compound interest)

#### 5.2 Penalty
- 270A - Under-reporting/misreporting penalty
- 271H - Failure to file AIR/SFT
- 272A - TDS penalty calculator
- Penalty waiver request generator
- Reasonable cause explanation template

### 6. LOSS SET-OFF & CARRY FORWARD (10 Features)
- Current year intra-head set-off
- Current year inter-head set-off
- Business loss carry forward (8 years)
- Speculation loss carry forward (4 years)
- Capital loss carry forward (8 years)
- House property loss carry forward (8 years)
- Unabsorbed depreciation (indefinite carry forward)
- Set-off order validation as per IT Act
- Automatic tracking of brought forward losses
- Section 35AD specified business loss (15-year c/f, no set-off)

### 7. DATA IMPORT & INTEGRATION (25 Features)

#### 7.1 ITD Portal Integration
- Form 26AS import (TDS details)
- AIS (Annual Information Statement) import
- TIS (Tax Information Statement) import
- Pre-filled data auto-population
- Auto-download ITR-V after filing
- Challan status verification from OLTAS
- Form 15CA/15CB import (foreign remittances)
- SFT (Statement of Financial Transactions) import
- Processing status check (all clients)
- Intimation order download (Section 143(1))
- Defaults download (bulk pre-filled data)

#### 7.2 Accounting Software Integration
- Tally import (Trial Balance, P&L, Balance Sheet)
- Excel/CSV bulk import
- JSON/XML import/export

#### 7.3 Broker & Financial Statements
- Mutual fund statement (CAMS, Karvy)
- Bank statement import (interest income)
- Form 16 PDF parsing (auto-populate)
- Form 16A/16B/16C parsing
- Digital signature verification

### 8. E-FILING & SUBMISSION (20 Features)

#### 8.1 Direct Filing
- Direct API integration with ITD portal (ERI license)
- JSON generation with validation
- Pre-upload validation (error checking)
- Digital Signature Certificate (DSC) integration
- eSign via Aadhaar support
- EVC (Electronic Verification Code) generation
- ITR-V download and storage
- Acknowledgment number tracking
- One-click login to ITD portal (secure credentials)
- Auto-email ITR-V to client

#### 8.2 Bulk Filing
- Bulk client data upload (JSON/Excel)
- Queue management for bulk filing
- Status tracking per return
- Error logs for failed filings
- Retry mechanism
- Progress indicator dashboard
- Completion report
- Success/failure summary

### 9. REVISED RETURN & RECTIFICATION (10 Features)
- Section 139(5) - Revised return filing
- Section 139(8A) - Updated return (ITR-U)
- Section 139(9) - Defective return rectification
- Section 154 - Rectification application
- Section 155 - Other amendments
- Automatic change tracking (original vs revised)
- Version control (track all versions)
- File comparison tool (side-by-side view)
- Lock/unlock file feature
- Intimation error analysis

### 10. AUDIT REPORTS & STATUTORY FORMS (15 Features)

#### 10.1 Tax Audit Reports
- Form 3CA - Audit report (accounts audited u/s 44AB)
- Form 3CB - Audit report (no mandatory audit)
- Form 3CD - Statement of particulars (44 clauses)
- Form 3CEB - Transfer pricing audit
- Auto-population from books
- Clause-by-clause guidance

#### 10.2 Other Statutory Forms
- Form 10E - Relief u/s 89
- Form 67 - Foreign tax credit
- Form 10-IEA - Carry forward losses
- Form 12BB - Salary deduction declaration
- Form 15G/15H - No TDS deduction request
- Form 10 - Accumulation of income (trusts)
- Form 10B/10BB - Trust audit report
- Form 15CA/15CB - Foreign remittance certificate
- Form 49A/49AA - PAN application

### 11. TRUST & INSTITUTION FEATURES (20 Features)

#### 11.1 Trust Registration
- Form 10A - Initial registration application
- Form 10AB - Re-registration/renewal
- Form 10AC - Registration order tracking
- Form 10AD - Rejection/cancellation order
- URN (16-digit Unique Registration Number) tracking
- Section 12AB registration (charitable trusts)
- Section 10(23C) approval tracking
- Section 80G approval (for donation eligibility)
- Section 35 approval (scientific research)
- Provisional registration (3 years) tracking
- Permanent registration (5 years) tracking
- Renewal reminder (6 months before expiry)

#### 11.2 Trust Compliance
- Form 10 - Declaration for accumulation (85% application)
- Form 10B/10BB - Trust audit report
- Activity commencement tracking
- DARPAN portal integration (NGO details)
- FCRA registration tracking
- 80G donation receipt generator
- Statement of donations received
- Anonymous donation tracking (>5% limit)

### 12. ADVANCE TAX & CHALLAN MANAGEMENT (20 Features)

#### 12.1 Advance Tax
- Quarterly advance tax calculation
- Due date reminders (15 June, Sept, Dec, 15 March)
- Interest calculator for short payment (234B/234C)
- Installment-wise computation
- Automatic 234B/234C computation

#### 12.2 Challans
- Challan 280 - Income tax payment
- Challan 281 - Securities Transaction Tax (STT)
- Challan 282 - Equalization Levy
- Challan for 234E/234F fees
- Auto-filled e-challan (pre-populated)
- Auto-filled paper challan (printable)
- Net banking/UPI/card payment
- Challan status verification (OLTAS)
- Challan download from TRACES
- CIN (Challan Identification Number) tracking
- BSR code validation
- Challan/PAN correction request (online via TRACES)
- Payment history per client
- Outstanding tax alerts

### 14. INTERNATIONAL TAXATION (12 Features)
- DTAA (Double Tax Avoidance Agreement) relief computation
- Form 67 - Foreign tax credit
- Transfer pricing documentation support
- Form 3CEB - TP audit report
- Section 195 - TDS on foreign remittances
- Form 15CA/15CB generation
- Residential status determination (Resident/NRI/RNOR)
- Tax treaty benefits calculator
- Foreign asset disclosure (Schedule FA)
- FEMA compliance check
- Foreign income computation
- Foreign tax paid tracking

### 15. CLIENT & CASE MANAGEMENT (12 Features)

#### 15.1 Client Database
- Client master (PAN, Aadhaar, contact)
- Client categorization (individual/HUF/firm/company)
- Multi-year data retention
- Family grouping (link related clients)
- Client tags (VIP, urgent, dormant)
- Client-wise document storage

#### 15.2 Case Management
- Case creation per client
- Task assignment to team members
- Due date tracking
- Status updates (pending/in-progress/completed)
- Priority flagging
- Comments/notes on cases

### 16. REPORTS & MIS (25 Features)

#### 16.1 Tax Reports
- Client-wise tax summary
- ITR filing status report
- TDS summary report
- Advance tax liability report
- Refund/demand summary
- Year-on-year tax comparison

#### 16.2 Error & Validation Reports
- E-return error locator
- Validation summary report
- Warning report (scrutiny triggers)
- Mismatch report (26AS vs ITR, AIS vs ITR)

#### 16.3 Client Communication Reports
- Tax computation summary (1-page)
- Tax-saving suggestions report
- Refund/demand client report

#### 16.4 Practice Management Reports
- Revenue report (month/year-wise)
- Outstanding dues report
- Client categorization (by income slab/ITR type)
- VIP client report
- Dormant client report
- Client retention analysis
- Service-wise revenue breakdown
- Team productivity report
- Time-tracking report
- Notice summary report

#### 16.5 MIS Dashboards
- Visual dashboard with charts/graphs
- Pie charts (income sources)
- Bar graphs (month-wise filing)
- Pending vs completed tracking
- Real-time updates

### 17. CALCULATORS & UTILITIES (15 Features)
- HRA calculator
- Capital gains calculator
- Depreciation calculator (IT Act rates)
- Gratuity calculator
- Leave encashment calculator
- Commuted pension calculator
- Salary arrears calculator (Section 89 relief)
- Advance tax calculator (quarterly)
- Income tax slab rate finder
- Surcharge & cess calculator
- Marginal relief calculator
- GSTR vs ITR comparison tool
- Wealth Tax computation (legacy)
- Interest on refund calculator
- Loan interest calculator (home/education)

### 18. CALENDAR & DUE DATE MANAGEMENT (12 Features)
- Government compliance calendar
- ITR filing due dates
- TDS return due dates
- Advance tax due dates
- Custom due dates per client
- Extension tracking (auto-update)
- Google/Outlook Calendar sync
- Mobile push notifications
- SMS/Email reminders (configurable)
- Color-coded calendar view
- Auto-prioritization by deadline
- Risk/revenue-based prioritization

### 19. E-SERVICES & QUICK TOOLS (10 Features)
- E-payment gateway integration
- PAN validation (NSDL/ITD API)
- TAN validation
- PAN application (Form 49A/49AA)
- TAN application (Form 49B)
- PAN correction
- Check PAN/TAN application status
- Aadhaar-PAN linking
- Representative registration (on client's e-filing account)
- Auto-fill name as per PAN database

### 20. MULTI-USER & ACCESS CONTROL (10 Features)
- Multi-user access (partners/managers/staff)
- Role-based permissions (view/edit/admin)
- User activity logs
- Simultaneous login support
- Client assignment to users
- Password protection
- Session timeout
- Two-factor authentication (2FA)
- Audit trail of changes
- IP whitelisting (optional)

---

## PART B: YOUR INNOVATIVE FEATURES (135+ Features)

### 21. OTP AUTOMATION SYSTEM (23 Features)

#### 21.2 Automated OTP Requests
- Bulk SMS trigger to all clients
- WhatsApp message with submission link
- Email reminder with portal link
- Automated follow-ups
- Customizable message templates
- Multi-language support (English/Hindi)

#### 21.3 OTP Workflow
- Dashboard showing OTP status (collected/pending)
- Auto-populate OTP in filing workflow
- OTP validity tracking
- Resend OTP trigger
- Client notification on successful submission
- One-click filing once OTP received
- Queue-based auto-filing
- Error handling (invalid OTP notifications)

#### 21.4 OTP Security
- End-to-end OTP encryption
- OTP audit log
- Client device tracking
- SMS fallback (if WhatsApp fails)
- IVR system (phone-based OTP entry)
- Help desk for OTP issues

### 22. AUTOMATED DOCUMENT SHARING (18 Features)

#### 22.1 Auto-Share Tax Documents
- Auto-generate PDF of computation
- WhatsApp auto-send (Business API)
- Email auto-send with PDF
- SMS notification with download link
- Customizable templates (firm branding)
- Auto-send ITR-V
- Auto-send acknowledgment number
- Filing success notification
- E-verification instructions

#### 22.2 Client Approval Workflow
- Approve/Reject buttons
- Comment/query section
- Auto-notify CA on approval
- Approval status tracking

#### 22.3 Document Security
- Password-protected PDFs
- Watermarking (firm branding)
- View-only mode
- Expiry links (30-day validity)
- Read receipts (email/WhatsApp)
- Download tracking
- Client acknowledgment button

### 23. INTEGRATED ACCOUNTING & BILLING (37 Features)

#### 23.1 Full Double-Entry Accounting
- Chart of accounts setup
- Journal entries (manual + auto)
- Ledger accounts (client-wise/expense-wise)
- Trial balance generation
- Profit & Loss statement (firm's own)
- Balance Sheet (firm's own)
- Cash flow statement
- Bank reconciliation

#### 23.2 Billing & Invoicing
- Automated fee calculation (ITR complexity-based)
- Service-wise billing (ITR/audit/notice/consultancy)
- Client-wise billing (consolidated/itemized)
- Final invoice after service completion
- Credit note/debit note
- Recurring billing (retainer clients)
- Invoice customization (firm branding)

#### 23.3 Payment Tracking
- Payment receipt generation
- Multiple payment modes (cash/cheque/UPI/NEFT/card)
- Outstanding management (aging analysis)
- Automated payment reminders
- Advance payment tracking
- Refund processing
- Bank integration (statement import)
- Auto-reconciliation (payments vs invoices)
- UPI QR code generation

#### 23.4 Expense Management
- Expense entry (software/salaries/rent)
- Vendor management
- Bill booking
- Payment to vendors
- TDS on payments
- Expense reports (category/month-wise)

#### 23.5 Financial Reports (Firm's Own)
- Revenue report (month/year-wise)
- Client-wise profitability
- Expense analysis
- Outstanding receivables aging
- Cash flow forecast
- Budget vs actual

### 26. ADVANCED ANALYTICS & INSIGHTS (25 Features)

#### 26.1 Practice Performance
- Revenue trends (YoY growth)
- Client acquisition (new vs repeat)
- Service mix analysis
- Team productivity metrics
- Seasonality analysis
- Client retention rate

#### 26.2 Client Analytics
- Client profitability (fees vs effort)
- Tax-saving opportunities per client
- Client risk profile
- Payment behavior tracking
- Client lifetime value

#### 26.3 Predictive Analytics (AI)
- Refund prediction (amount & timeline)
- Notice probability scoring
- Revenue forecast (next FY)
- Churn prediction (clients at risk)

#### 26.4 Visual Analytics
- Interactive dashboards
- Heat maps (filing timeline)
- Trend charts
- Comparative analysis
- Drill-down reports
- Custom report builder
- Export to Excel/PDF
- Scheduled report delivery
- Real-time data updates

### 28. COMMUNICATION & COLLABORATION (11 Features)

#### 28.1 Internal Team
- Internal chat (team discussions)
- Task assignment with notifications
- Shared notes on client files
- @mentions to tag team members
- File sharing (internal)

#### 28.2 Client Communication Log
- Email tracking (sent/received)
- WhatsApp message log
- SMS log
- Phone call logging (manual)
- Meeting logs
- Searchable history
- Timeline view (chronological)

---

## PART C: SYSTEM & TECHNICAL FEATURES (121+ Features)

### 29. DATA SECURITY & COMPLIANCE (27 Features)

#### 29.1 Encryption & Security
- AES-256 encryption (data at rest)
- SSL/TLS encryption (data in transit)
- Data residency (servers in India)
- DPDP Act compliance (India's Data Protection)
- GDPR compliance (if applicable)
- Role-based access control (RBAC)
- Two-factor authentication (2FA)
- Session management (auto-logout)
- IP whitelisting
- Password policies (complexity requirements)
- Password encryption (hashed storage)

#### 29.2 Audit Trail
- Complete activity logging
- Who accessed which file
- What changes were made
- When actions occurred
- Immutable logs (cannot delete)
- Export logs for audit

#### 29.3 Data Privacy
- Right to erasure (GDPR/DPDP)
- Data portability
- Consent management
- Terms of Service acceptance
- Privacy policy display
- Liability waiver (for AI suggestions)
- CA professional liability insurance tracking

#### 29.4 Backup & Recovery
- Automatic daily backups
- Cloud backup (offsite)
- One-click restore
- Point-in-time recovery
- Complete database export
- Disaster recovery plan
- Data archival (old years)

### 30. SOFTWARE UPDATES & MAINTENANCE (12 Features)
- Auto-update for new Assessment Year
- Budget update (Finance Act changes - 48hrs)
- ITD schema update (JSON/XML)
- FVU utility sync (TDS versions)
- Multi-year data support (10+ years)
- Legacy data migration support
- Backward compatibility
- Version release notes
- Update notifications
- Optional beta program
- Rollback capability
- Staged rollout (phased updates)

### 31. USER EXPERIENCE & INTERFACE (20 Features)

#### 31.1 Interface Customization
- Dark mode / Light mode
- Font size adjustment
- High contrast mode (accessibility)
- Keyboard shortcuts
- Customizable dashboard (drag-drop widgets)
- Layout preferences (saved per user)
- Quick access toolbar
- Recently used items
- Bookmarks/favorites

#### 31.2 Guided Workflows
- Step-by-step wizard (first-time users)
- Interactive tutorials
- Contextual help (? icon on screens)
- Smart suggestions (AI next-action)
- Progress indicators (% completion)
- Tooltips and hover hints
- In-app notifications
- Welcome tour (new users)

#### 31.3 Performance
- Fast loading times (<2 seconds)
- Lazy loading (optimize large datasets)
- Caching strategy

### 32. INTEGRATION & API (25 Features)

#### 32.1 Third-Party Integrations
- Tally integration
- WhatsApp Business API (official)
- Twilio (SMS gateway)
- MSG91 (SMS gateway)
- SendGrid (email service)
- AWS SES (email service)
- Razorpay (payment gateway)
- Google Drive (document storage)
- Slack integration
- Google Calendar sync
- Google meet integration (for client meetings)

#### 32.2 Developer API
- REST API (for custom integrations)
- Webhooks (real-time notifications)
- API documentation (comprehensive)
- API keys management
- Rate limiting
- API versioning
- Sandbox environment (testing)

### 33. MULTI-LOCATION & BRANCH SUPPORT (8 Features)
- Multiple office locations
- Branch-wise data segregation
- Centralized reporting
- Inter-branch client transfer
- Franchise management
- White-label option
- Revenue sharing calculations
- Branch performance comparison

### 34. KNOWLEDGE BASE & TRAINING (15 Features)

#### 34.1 Help System
- Contextual help (every screen)
- User manual (searchable PDF)
- FAQ section
- Live chat support
- Support ticket system
- Knowledge base articles
- Community forum

#### 34.2 Tax Library
- IT Act full text (searchable)
- CBDT circulars (auto-updated)
- Case laws (important judgments)
- Tax updates (recent changes)
- Due date calendar
- Forms & annexures library
- Notifications & press releases

### 35. CUSTOMIZATION & FLEXIBILITY (14 Features)

#### 35.1 Templates
- Invoice design (firm branding)
- Email templates
- WhatsApp message templates
- Notice reply format (letterhead)
- Report templates

#### 35.2 Workflows
- Custom approval workflows
- Custom task templates
- Custom fields (firm-specific)
- Conditional logic (if-then rules)
- Automation rules (trigger-based)
- Business rules engine
- Workflow version control
- Import/export workflows

### 36. DATA IMPORT/EXPORT (10 Features)
- Import from legacy systems
- Export to Excel/CSV (any report)
- Export to PDF (print-ready)
- Bulk data export
- Selective data export
- Data masking (for privacy)
- Import validation
- Error handling (import failures)
- Import preview (before commit)
- Import history tracking

---

# APPENDIX B — ADDITIONAL FEATURES (Suggested Additions)

> The features **NOT** in the founder's original list, appended here in full. These were identified across the NRITAX/Taxify audits, the incumbent teardowns (Winman/KDK/Relyon/SAG/ClearTax/CompuTax), and the "beat-the-incumbents" spec.
> All of these are already mapped into their phases in the build flow above (Phase 0–8 + System); this appendix preserves them as a complete reference, in the same `✅`-format as the original list.

---

## PART D — NOTICE, SCRUTINY & APPEALS  `[MOAT — biggest untapped post-filing pain]`

### D1. NOTICE INTAKE & CLASSIFICATION
- Auto-fetch notices from ITD **e-Proceeding portal** (all clients, one click, via ITD API)
- Auto-classify notice type: 143(1) intimation / 143(2) scrutiny / 148 reassessment / 147 income escaped / 131 summons / 133(6) third-party info / 263 revision by PCIT / 270A penalty / 271AAB search-seizure
- Notice severity scoring (high/medium/low) based on type + amount demanded
- Statutory-deadline computation per notice type (30/60/90/120 days)
- Deadline alert (7 days before)
- Firm-wide notice register (client + year + type view)
- Notice-defense packet — one-click bundle (return + source docs + computation + import trail)

### D2. FACELESS ASSESSMENT (Section 144B) RESPONSE SYSTEM
- Structured response drafting (grounds of appeal, submissions, attachments)
- Auto-generate submission from return data + source documents
- Digital submission via ITD e-Proceeding portal (direct upload)
- Submission history + acknowledgement tracking
- Hearing scheduling (virtual hearing requests)
- Video-conferencing integration for faceless hearings

### D3. DEMAND MANAGEMENT
- Outstanding-demand register (all clients, all years)
- Demand-vs-return reconciliation (CPC computed vs filed)
- One-click demand payment (Challan 280 pre-filled)
- Installment request (Section 220(6) application)
- Stay of demand application (Section 220(6) / 220(7))
- Demand-waiver / appeal-effect tracking

### D4. APPEALS (CIT(A) / ITAT)
- Form 35 — Appeal to CIT(A), auto-populated from return + notice data
- Form 36 — Appeal to ITAT
- Form 36A — Memorandum of cross-objections
- Grounds-of-appeal template library (pre-written, editable)
- Appeal-fee calculator (based on assessed income)
- Appeal status tracking (CIT(A)/ITAT cause-list check)
- Hearing-date reminder
- Order receipt + **appeal-effect computation** (refund/demand recomputation after order)

### D5. SETTLEMENT & REVISION
- Form 34B — Application to Settlement Commission
- Section 264 — revision by Commissioner
- Immunity-from-penalty / prosecution tracking

### D6. REFUND MANAGEMENT (detailed)
- Refund-failure reason tracking (wrong IFSC, Aadhaar-PAN mismatch, bank-validation failure)
- Refund re-issue application (Section 237/239)
- Refund-banker tracking (SBI CMP / NSDL)
- Section 244A — interest on delayed refund auto-computation
- Refund-status auto-polling (daily) + client notify on credit

---

## PART E — TDS COMPLIANCE  `[SUITE — highest-frequency, most-sticky]`

### E1. TDS RETURNS
- Form 24Q — TDS on salary (quarterly, 4 statements/year)
- Form 26Q — TDS other than salary (quarterly)
- Form 27Q — TDS on payments to non-residents
- Form 27EQ — TCS returns
- Form 27A — control chart (filed with each TDS return)
- Form 26QB — TDS on property purchase (u/s 194IA, by buyer)
- Form 26QC — TDS on rent by individual (u/s 194IB)
- Form 26QD — TDS on contractor payment by individual (u/s 194M)
- Form 26QE — TDS on VDA transfer (u/s 194S)

### E2. TDS COMPUTATION ENGINE
- Employee-wise TDS (24Q): salary, perquisites, exemptions, deductions, tax projection, quarterly shortfall/excess
- Deductee-wise TDS (26Q): section-wise rates (194A/C/D/H/I/J/M/N...), thresholds, PAN-not-available 20%, higher-rate tracking
- Section 197 — lower-deduction certificate (apply + track + apply reduced rate)
- Section 195 — nil-deduction certificate (foreign payments)
- Form 15G/15H validation before nil deduction
- TDS-liability vs payment reconciliation (monthly)

### E3. CHALLAN & TRACES RECONCILIATION
- Challan 281 booking per deductee + quarter
- Auto-match challan-to-deductees (CPC's biggest TDS-error source)
- Unmatched-challan identification + resolution
- Short-payment identification (challan < deducted TDS) → 234E trigger
- Excess-challan carry-forward
- TRACES login, justification report, conso-file download, defaults report, correction support

### E4. TDS CERTIFICATES
- Form 16 generation (Part A from TRACES + Part B from computation)
- Form 16 bulk generation + digital signature + email to employees
- Form 16A (non-salary), Form 16B (194IA), Form 16C (194IB), Form 27D (TCS)
- TDS-credit mismatch report (TRACES vs AIS vs 26AS)

### E5. TDS CORRECTION RETURNS
- C1 (deductor personal details), C2 (challan details), C3 (deductee details)
- C4 (24Q Annex II salary detail), C5 (PAN update for invalid PAN), C9 (add challan rows)
- Cascade-correction logic (C2 before C3)

### E6. TDS COMPLIANCE TRACKER
- TDS-deposition due dates (7th of next month; March = 30 April)
- Return-filing due dates (quarterly: 31 Jul / 31 Oct / 31 Jan / 31 May)
- 234E — late-filing fee (₹200/day, capped at TDS) auto-computation
- 271H — penalty for late/wrong return
- 26QB/26QC 30-day payment-deadline tracker

---

## PART F — GST COMPLIANCE  `[SUITE — full plan; go/no-go decided later]`

### F1. GST RETURNS
- GSTR-1 (outward supplies, monthly/QRMP) — HSN summary, B2B/B2C/export/nil split
- GSTR-1A (amendment to GSTR-1)
- GSTR-3B (monthly summary + tax payment)
- GSTR-2B (auto-drafted ITC statement — reconciliation anchor)
- GSTR-9 (annual return)
- GSTR-9C (reconciliation statement, audit filers)
- GSTR-4 (quarterly return, composition) + CMP-08 (quarterly challan)
- GSTR-7 (TDS on GST — government deductors)
- GSTR-8 (TCS on GST — e-commerce operators)

### F2. GST RECONCILIATION
- GSTR-2B vs purchase-register reconciliation (the monthly nightmare)
- GSTR-1 vs GSTR-3B liability match
- ITC-utilization tracker (CGST/SGST/IGST, correct utilization order)
- E-way-bill vs GSTR-1 reconciliation
- GSTR-9 vs GSTR-3B annual reconciliation
- **GSTR-vs-ITR turnover triple-match** (GSTR-1 vs PGBP vs 26AS) with reason capture

### F3. E-INVOICING & E-WAY BILL
- E-invoice generation (IRP integration, IRN + QR code)
- E-invoice cancellation + credit note
- E-way-bill generation (transport >₹50,000), distance calculator
- Bulk e-way-bill + e-invoice

### F4. GST NOTICES & APPEALS
- DRC-01 — show-cause-notice response
- DRC-06 — reply to demand
- DRC-03 — voluntary payment
- APL-01 — appeal to GST Appellate Authority

---

## PART G — EMPLOYEE / PAYROLL / LABOUR COMPLIANCE  `[SUITE]`

- Salary-structure setup (CTC-to-take-home: basic, HRA, DA, allowances, perquisites)
- Monthly payroll processing (gross to net)
- TDS on salary (Form 24Q integration — monthly projection vs actual)
- Investment declaration (Form 12BB): collect, verify, apply
- Provisional vs final TDS (April→Feb projection, March actualization)
- Branded salary slips (emailable)
- Full & final settlement (F&F): leave encashment, gratuity, bonus, notice recovery
- Payroll register (month + employee wise)
- PF computation (12% employer + 12% employee, EPS split)
- EPFO ECR upload (monthly PF filing); UAN management; Forms 5/10/12A
- ESI computation (3.25% employer + 0.75% employee); Form 5; monthly return
- Professional Tax (state-wise) deduction + annual return
- Gratuity actuarial estimate; leave tracking (EL/CL/SL); bonus computation (8.33–20%)
- LWF (Labour Welfare Fund) deduction + remittance

---

## PART H — COMPANY LAW / MCA COMPLIANCE  `[SUITE]`

- Form AOC-4 (financial statements with MCA)
- Form MGT-7 / MGT-7A (annual return)
- Form ADT-1 (auditor appointment), DIR-12 (director changes), MGT-14 (resolutions), INC-20A (commencement)
- Board-meeting minutes drafting; AGM notice + minutes
- Register of directors + shareholders; share-certificate generation
- DIN (Director Identification Number) tracking; DSC registration tracking
- XBRL tagging + validation (companies required in XBRL format)
- SPICe+ incorporation; name reservation (RUN); DIN application; MoA/AoA templates

---

## PART I — AUDIT-DEPTH & STATUTORY FORMS (hardened)  `[MOAT depth]`

### I1. FORM 3CD CLAUSE-BY-CLAUSE CAPTURE (all 44 clauses)
- Clause 4 — nature of business/profession (auto from ITR)
- Clause 11 — capital-expenditure amounts debited
- Clause 12 — non-deductible amounts u/s 40A(3) (cash >₹10,000)
- Clause 13 — method of accounting (prior-year consistency check)
- Clause 16 — amounts u/s 28 (deemed income)
- Clause 17 — u/s 41 (remission of liability)
- Clause 19 — bad debts u/s 36(1)(vii)
- Clause 20 — gratuity provision u/s 40A(7)
- Clause 21 — u/s 43B disallowances (until actual payment)
- Clause 26 — hundi borrowings/re-payments
- Clause 30A/30B/30C — international/domestic transactions
- Clause 34 — TDS/TCS default reporting
- Clause 36 — share premium > FMV u/s 56(2)(viib)
- Clause 40 — unapplied income of trusts
- Clause 41 — speculation loss disallowed
- Clause 42 — deemed dividend u/s 2(22)(e)
- Clause 44 — GST break-up of expenditure (mandatory FY 2021-22+)
- Auto cross-reference Clause 34 ↔ TRACES TDS defaults

### I2. AUDIT WORKFLOW
- Standard audit checklist (ICAI guidance notes)
- Working-paper management (link evidence to each clause)
- Review/sign-off workflow (assistant → senior → partner)
- Audit-query management (raised → replied → closed)
- Audit-evidence storage (bank statements, ledgers, contracts per clause)

### I3. UDIN (Unique Document Identification Number)
- UDIN generation for every audit certificate (ICAI-mandated)
- UDIN tracking + renewal (3-month validity)
- Bulk UDIN verification
- UDIN revocation (if return revised post-UDIN)

---

## PART J — CAPITAL GAINS DEPTH (hardened)  `[MOAT]`

- Section 112A grandfathering — FMV as on 31-01-2018 (ISIN-wise NSE/BSE lookup)
- STCG/LTCG split for transactions straddling the 23-07-2024 rate change (15%→20%)
- STT confirmation at acquisition + transfer (111A/112A eligibility)
- ESOP/RSU: perquisite at vesting (89A) + CG at sale, employer-TDS reconciliation
- Bonus shares (cost ₹0, original holding period)
- Rights issue (cost at rights price, original period)
- Stock split / reverse split (cost + quantity adjustment)
- Off-market transfers — Section 50CA confirmation value / deemed FMV
- Gift taxation u/s 56(2)(x) (>₹50,000, FMV rules)
- Section 54GB (SME shares), Section 112A STT with Form 31 both sides
- JDA / land-pooling deemed-transfer computation
- Section 50C — stamp-duty-value vs consideration rule
- Section 50D — deemed full value where unimplementable
- Section 54 / 54F multiple-property rule enforcement
- Stamp duty + registration + brokerage in cost; indexed improvement cost

---

## PART K — DEPRECIATION ENGINE (dedicated)  `[MOAT]`

- Block-wise WDV computation (all blocks, additions/deletions per year)
- Audited WDV carry-forward year-over-year
- Pro-rata depreciation (first/later half of year — 50% cap)
- Additional depreciation u/s 32(1)(iia) (20% new plant/machinery)
- Assets put to use <180 days → 50% depreciation
- Sale-of-asset block reduction; STCG/LTCG on shortfall; Section 50 slip rule
- Section 43(6) WDV definition
- ITR-3/3CD block-wise depreciation Schedule Part A–B auto-generation

---

## PART L — BOOKS-TO-RETURN BRIDGE  `[MOAT]`

- Trial balance → ITR mapping engine (GL→ITR head map, editable rules)
- Balance Sheet → Schedule BS for ITR-3/4/5/6 (partner capital, loans, fixed assets, current liabilities)
- P&L → Schedule BP/PBP mapping
- Reconciling register (books vs ITR per head, variance reason)
- Audited-vs-unaudited flag driving 3CA vs 3CB vs 3CD
- Bank statement → 26AS → P&L receipt reconciliation (turnover verification)
- Turnover threshold-watch (44AD ₹2cr, 44ADA ₹75L, 44AB ₹1cr/₹10cr alerts)

---

## PART M — NRI / RESIDENTIAL-STATUS & INTERNATIONAL ENGINE  `[MOAT]`

- 183-day residence tracker (day-counting, exit/entry dates)
- RNOR rule application (−300/−182 day tests, 10-year/7-year lookback)
- Deemed residency u/s 6(1A) (600-day test; 120-day citizen rule FY 2020-21+)
- RNOR → Resident conversion alerts
- Foreign-income taxability by status (RNOR exempt vs Resident global)
- Form 67 auto-fill from foreign-asset + income data
- FEMA Schedule FA JSON lump-sum vs itemized auto-decide
- US-India / Canada-India treaty-specific items
- DTAA relief, treaty-benefit calculator, foreign-tax-paid tracking
- Foreign-asset disclosure thresholds auto-check

---

## PART N — ACCOUNTING-SOFTWARE & BROKER INTEGRATION (extended)

- Multi-accounting (Tally, Zoho, Marg, Busy, QuickBooks, Tally Prime) — planned
- Broker APIs (Zerodha, Groww, Upstox, Angel) — automatic CG cost basis + grandfathering
- Mutual-fund CAMS/KFintech statement parse
- Bank-statement parse (interest + transactions)

---

## PART O — CORRECTNESS / TRUST LEVERS  `[MOAT — the differentiator]`

- **Official ITD-schema validation hard-wired into every route** (not just internal rules)
- **Year-locked builds** — one assessment year per compute instance; cross-year mixing structurally impossible
- **Per-figure provenance** — every return field shows its source (document/import/manual), clickable
- **AIS/TIS as diff, NOT auto-populator** — 3-way variance (prefill vs AIS vs entered) for the user
- **PAN-mismatch gate** — hard-block commit/filing on PAN mismatch
- **No-silent-zeros** — auto-flag plausibly-non-zero fields at 0
- **Duplicate-merge** — dedupe identical transactions across bank + AIS + broker + 26AS
- **Import-preview-before-commit** with side-by-side diff + accept/reject per row
- **Hard-return computation depth** — full audit-trail of every calculator (not just final liability)
- **Interest-section self-check** — 234A/234B default computed so ITD penalty can't supersede
- **Statutory-ceiling enforcement** (deduction limits auto-cap)
- **Assessment-year consistency** — no mixture of FY/AY
- **HMAC-JSON digest** — deterministic, verifiable output identity

---

## PART P — MIGRATION & SWITCHING-COST KILLERS  `[MOAT]`

- One-click migration from Winman / KDK / SAG / CompuTax / ClearTax
- Import client master, prior-year returns, brought-forward losses, depreciation WDV opening
- Guided onboarding wizard (data mapping, field-level review, dry-run before commit)
- Migration validation report (what came over, what needs manual entry)
- Winman-equivalent keyboard map
- Concurrent-tool mode (run alongside incumbents during transition, keep in sync)
- 10+ years legacy-data continuity + rollback after migration

---

## PART Q — PRACTICE-MANAGEMENT & WHITE-LABEL DEPTH  `[MOAT]`

- Multi-firm hosting (one install, many independent CA firms)
- Per-firm data isolation + branding + fee schedule + form list
- Master-admin console (for the software operator)
- Module metering / licensing (which firm licenses ITR vs ITR+TDS vs ITR+TDS+GST)
- Client-consent gating for ITD representation (paper-trail)
- SOC 2 Type II / ISO 27001 readiness (win enterprise clients)
- Client data deletion on engagement-end; per-client data export (departure/portability)
- Instant staff-exit access revocation; DSC key security/renewal/expiry alerts
- Excel-fidelity bulk power (grid with Excel keyboard nav, paste-from-Excel, bulk ops, smart templates, print formats)

---

## PART R — PREDICTIVE & RISK ANALYTICS (AI)  `[MOAT]`

- Refund prediction (amount + timeline)
- Notice-probability scoring (per return, pre-filing)
- Scrutiny-risk heatmap (which schedules attract attention)
- Revenue forecast (next FY)
- Churn prediction (clients at risk)
- Tax-saving-opportunity detection per client
- Client risk profile (from filing history + income patterns)
