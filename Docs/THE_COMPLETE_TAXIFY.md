# THE COMPLETE TAXIFY — Final Implementation Plan

**Version:** 1.0
**Status:** Approved scope baseline
**Scope rule:** Taxify is the single most complete Income Tax Suite ever built — one product, complete and deep, not a bundle of shallow modules. GST is deferred. Employee screen-monitoring, retail ERP, and a standalone HR/payroll product are explicitly excluded.
**Guard rule:** This plan does not modify any existing Taxify source file. Each phase below is implemented only when explicitly started and approved.

---

## 0. Product Definition and Positioning

### 0.1 What Taxify is

Taxify is the world's first Income Tax Suite that combines, in one product:

1. A live-verified ITR-1 to ITR-7 + ITR-U computation, CBDT-JSON, and ERI Type-2/Type-3 filing engine.
2. A complete **double-entry Client Accounting engine** (the books of each client's business).
3. A complete **double-entry Firm Accounting engine** (the practitioner's own firm books).
4. A tax-audit engine (44AB, 3CA/3CB/3CD, 3CE/3CEB/3CEAA, 29B/29C, 10B/10BB-series, 56FF).
5. A statutory-forms engine (10-IEA, 10E, 67, 15CA/15CB, 26QB/26QC/26QD/26QE, 16/16A-series, 27D, 35/36/246A, 49A/49B).
6. A post-filing portal-automation layer (processing status, refund, demand, intimation 143(1), rectification 154, challan download, challan e-payment).
7. A TDS/TRACES module (24Q/26Q/27Q/27EQ, conso, justification, defaults, Form 16/16A, LDC).
8. An MCA/ROC module (company/LLP master, AOC-4/MGT-7/DIR-3-KYC/LLP-8/11, DPT-3, MSME-1, BEN-2, SRN tracking).
9. A CA practice-management platform (clients, family-head contacts, tasks, compliance calendar, notices, email, client portal, DMS, DSC register, licence register, billing, timesheets, team, analytics, engagement letters, conflict checks, ready-reckoner, mobile apps).
10. A WhatsApp self-service portal where clients self-serve status, documents, and **e-verify their own filed returns via OTP relay** — a feature no competitor has.
11. A controlled, guard-railed AI layer (document intelligence, capital-gains mapping, trial-balance mapping, drafting, assistant, audit trail).

### 0.2 What Taxify is NOT

- Not a GST product. GST return filing (GSTR-1/3B/9/9C, e-invoice, e-way-bill) is deferred. Output-GST/input-ITC ledgers exist inside Firm Accounting only because the firm raises GST-compliant invoices; filing those returns is out of scope.
- Not an employee screen-monitoring tool (CompuWatch-style webcam/screen-watch excluded).
- Not a retail ERP / inventory / POS product (Marg-ERP-style multi-branch retail excluded).
- Not a standalone HR/payroll product. Payroll is kept only to the extent needed to feed TDS-on-salary (24Q) for the firm's own staff and for client-staff TDS returns.

### 0.3 The two accounting domains (corrected)

Taxify has **two separate, first-class double-entry books**:

| Domain | Whose books | Purpose | Drives |
|---|---|---|---|
| **Client Accounting** | Each client's business | Trial balance → P&L → Balance Sheet → Schedule III → ITR/3CD/computation | ITR, audit, statutory forms |
| **Firm Accounting** | The practitioner's own CA firm | Firm P&L, firm Balance Sheet, partner capital/current accounts, fees receivable, firm ITR-5/3/6, firm TDS receivable, firm-as-deductor | Firm billing, partner-wise profitability, firm's own compliance |

Both share the same double-entry engine (chart of accounts, vouchers, trial balance, financial statements) but operate on separate books scoped by a `book_owner` dimension (client_id for client books; organization_id for the firm book).

---

## 1. Architecture Baseline (existing Taxify conventions)

Every phase must follow these conventions:

- **Backend:** FastAPI, Python 3.10, SQLAlchemy, SQLite (`app.db`), run via `run.py` (Windows Proactor event loop mandatory for Playwright).
- **Monetary values:** `decimal.Decimal` end-to-end — never float.
- **Tax engine pipeline:** `app/schemas` (Pydantic v2) → `app/engine/calculators` (dataclass) → `app/engine/itd` (CBDT JSON) → `app/engine/validators` (rules) → `app/eri` (Type-2/3 filing).
- **Routers:** `app/routers/`, mounted in `app/main.py` lifespan.
- **Background workers:** `app/automation/job_worker.py` (portal downloads), `app/filing_automation/worker.py` (filing). New workers register alongside.
- **Audit:** `app/db/models.py::AuditLog` is the tamper-evident trail; every consequential action appends a row.
- **Live verification:** No CBDT/ITD, ERI, TRACES, or MCA flow is marked "production-ready" until it has passed one live call against the real portal (UAT first, then production). This is the existing Taxify convention documented in `Docs/ERI_UAT_AND_PRODUCTION_REFERENCE.md`.
- **Frontend:** React 19 + TypeScript + Vite, React Router. `.editorconfig` is authoritative: 4 spaces Python, 2 spaces TS/JS/JSON/CSS, LF endings.

---

## 2. Phase Catalog (at a glance)

| Phase | Name | Priority | Depends on |
|---|---|---|---|
| A | Platform Foundation | P0 | — |
| B | Client Accounting Engine | P0 | A |
| C | Firm Accounting Engine | P0 | A, B |
| D | Income Tax Engine Completion (ITR-5/6/7 + ITR-U) | P1 | A |
| E | Post-Filing Portal Automation | P1 | A |
| F | Tax Audit Engine | P1 | B, C, D |
| G | Statutory Forms Engine | P1 | A |
| H | TDS / TRACES Module | P2 | A, E |
| I | MCA / ROC Module | P2 | A |
| J | Assessment-Order Checking Engine | P2 | E |
| K | Practice Management Layer | P1 (core) / P2 (breadth) | A |
| L | Portal Automation Hardening | P2 (ongoing) | E, F, H, I |
| M | WhatsApp Self-Service + E-Verify | P0 (e-verify) / P2 (rest) | A, K |
| N | AI Layer | P4 | all data phases |
| O | Production Hardening + Release | P4 | all |

---

# PHASE A — Platform Foundation

## A.0 Objective

Make Taxify a multi-user, multi-role, multi-tenant platform with a versioned form registry and a family-head contact model. Right now `User` is single-org and `Client` is flat; everything downstream depends on this phase.

## A.1 Work to be done

### A.1.1 Organization, team, role, permission model
- New tables: `organization`, `team`, `role`, `permission`, `user_organization`, `user_role`.
- Extend `Client.user_id` with a nullable `organization_id`; keep `user_id` as owner for backward compatibility.
- JWT carries org + role; middleware resolves and enforces per-request permission checks.
- Seed roles: Partner, Manager, Reviewer, Senior, Executive, Article, Billing, Read-only, Admin.
- Permission scopes: `clients`, `credentials`, `documents`, `filings`, `everify`, `billing`, `reports`, `team`, `config`.

### A.1.2 Contact / family-head model (WhatsApp prerequisite)
- New tables: `contact` (whatsapp_number E.164-normalized, email, name, active), `client_contact` (contact_id, client_id, relationship, is_primary, can_check_status, can_download, can_everify, can_receive_docs).
- Migration: every existing `Client` with email/mobile → default `Contact` + link.
- Unique constraint on `contact.whatsapp_number` per org.

### A.1.3 Assessment-year versioned form registry
- `form_registry` (AY → list of forms + schema version + due dates + enabled flags).
- Single source of truth for ITR, audit, TDS, MCA, statutory forms.
- Seed for AY 2026-27, 2025-26, 2024-25.

### A.1.4 Excel/CSV client import + competitor migration
- Port AayDocCapio PAN/DOB/duplicate-PAN logic into Taxify conventions.
- Columns: WhatsApp Number (→ contact), Group, Entity Type, TAN, CIN/LLPIN.
- Competitor migration: parse Winman/KDK/GenIT/CompuTax ITR-JSON into `ReturnDraft`.
- Branded template: Instructions + Groups + dropdown validation.

### A.1.5 Credential vault hardening
- Extend `app/vault.py` to hold ITR-portal + TRACES + MCA + bank credentials.
- Per-org encryption keys (not the AayDocCapio fixed key).
- Rotation reminders → link to DSC/licence register (Phase K).

## A.2 Deliverables (end of Phase A)

1. Migration script creating all new tables, reversible.
2. `app/auth/permissions.py`, `app/auth/org_context.py` middleware.
3. `app/routers/contacts.py`, `app/routers/imports.py`, `app/routers/forms.py`.
4. `app/engine/form_registry/` with seeded AY JSON.
5. `app/services/client_import_service.py`, `app/services/migration_import_service.py`.
6. `frontend/src/pages/ImportPage.tsx` wired into `App.tsx`.
7. Existing 950+ tests still green.

## A.3 Testing to confirm Phase A complete

- **Permission tests:** for each role, assert allowed vs denied on each scope.
- **Contact tests:** migrate existing clients → every client resolves to exactly one primary contact; duplicate WhatsApp number rejected.
- **Form-registry test:** every form referenced by `app/engine/itd/itr*.py` exists in registry for its AY.
- **Import round-trip:** export clients → re-import → identical clients; per-row errors reported.
- **Migration test:** sample Winman/KDK ITR JSON → `ReturnDraft` → re-export JSON → structurally equal.
- **Regression:** `pytest` full suite green (known baseline ~177 failures/13 collection errors predating this work must not increase).

---

# PHASE B — Client Accounting Engine

## B.0 Objective

Build the complete double-entry accounting engine for each client's books: chart of accounts, vouchers, trial balance, financial statements, depreciation, Tally import, and the one-click accounting→ITR/3CD/computation transfer. This is the corrected gap — Winman, CompuBal, KDK, and Marg all have this; Taxify currently has only a stub `AccountingPage.tsx`.

## B.1 Work to be done

### B.1.1 Chart of accounts + ledger architecture
- Tables: `chart_of_account` (code, name, group, sub-group, nature), `ledger_account` (per client/entity), `voucher`, `voucher_line` (debit/credit, Decimal), `cost_center`, `book_owner` (client_id for client books).
- Double-entry integrity: every voucher balances (sum debits == sum credits), enforced at DB layer.

### B.1.2 Journal / voucher entry
- Voucher types: Journal, Payment, Receipt, Contra, Sales, Purchase, Credit Note, Debit Note, Cash, Bank.
- Auto-numbering per voucher type per financial year.
- Recurring journals (rent, depreciation, monthly provisions).
- Reverse-charge and TDS-tag linkage for future.

### B.1.3 Trial balance
- Generate from posted vouchers for any date range.
- Previous-year + current-year columns + variance.
- Drill-down: TB → ledger → voucher → source document.

### B.1.4 Financial statements generation
- Profit & Loss (trading + P&L, vertical + horizontal).
- Balance Sheet (Schedule III Companies Act + IT-Act vertical/horizontal for non-company).
- Cash Flow Statement (indirect method, Companies Act).
- Income & Expenditure / Receipt & Payment (trusts, AOPs — ties to ITR-7).
- Auto Schedule-III notes generation.
- Prior-year comparison columns.

### B.1.5 Tally / Busy / Excel import
- Tally XML/JSON import (daybook, ledgers, vouchers).
- Busy export import.
- Excel paste-import with auto-ledger-mapping.
- Smart re-import (dedup by voucher number + amount + date).

### B.1.6 Depreciation engine (dual: IT Act + Companies Act)
- IT Act block-wise (Sec 32, Schedule II rates, additional depreciation).
- Companies Act (useful life + residual, component accounting).
- Reconciling-difference schedule (IT vs Co. Act) — the 3CD Clause 34/35 bridge.
- Fixed-asset register with addition/disposal/improvement tracking.

### B.1.7 Merge multiple businesses / branches for one client
- One client with multiple trading books → consolidated financials → consolidated ITR.

### B.1.8 Accounting → ITR/3CD/Computation transfer
- One-click: trial balance → computation → ITR schedules → 3CD clause mapping.
- Reuses Taxify's existing `flat_to_draft.py` + `draft_to_itr*_input.py` pipelines.

## B.2 Deliverables (end of Phase B)

1. `app/engine/accounting/` modules: `coa.py`, `voucher.py`, `trial_balance.py`, `financials.py`, `depreciation.py`, `tally_import.py`, `merge.py`, `to_itr_transfer.py`.
2. `app/routers/accounting.py` with CRUD for vouchers, ledger, TB, financials.
3. `app/schemas/accounting.py` Pydantic models.
4. `frontend/src/pages/AccountingPage.tsx` (real, not stub) + ledger/voucher/TB/P&L/BS editors.
5. Tally importer + Excel importer.
6. Dual depreciation calculator.
7. Accounting→ITR transfer endpoint.

## B.3 Testing to confirm Phase B complete

- **Double-entry integrity:** random voucher generation with unbalanced lines → rejected at DB layer.
- **TB correctness:** TB closing equity == retained + profit; P&L net ties to Balance Sheet.
- **Tally round-trip:** import sample Tally XML → reproduce identical TB → export → re-import → no drift.
- **Depreciation:** known-asset case → IT-Act and Co-Act depreciation match manual computation; reconciling difference schedule ties to 3CD Clause 34/35.
- **Transfer:** TB → computation → ITR-4 presumptive schedule → CBDT JSON → passes official schema validation.
- **Golden suite:** fixtures for trading, P&L, BS, Schedule III, cash flow.

---

# PHASE C — Firm Accounting Engine (the corrected addition)

## C.0 Objective

Build the complete double-entry accounting engine for the practitioner's **own CA firm** as a business entity. This is distinct from Client Accounting: here the firm itself is the assessee. This drives firm billing, partner-wise profitability, the firm's own ITR-5/3/6, firm TDS receivable on professional fees, and the firm as a deductor for staff/outside-professionals. Without this, Taxify cannot be a complete CA-practice product.

## C.1 Work to be done

### C.1.1 Firm book + chart of accounts
- `book_owner` dimension set to `organization_id` (vs `client_id` for client books).
- Firm chart of accounts seeded for a CA practice: Professional Fees, Consultancy Fees, Audit Fees, Return-Filing Fees, TDS-Return Fees, ROC Fees, Reimbursable Expenses, Staff Salaries, Partner Remuneration, Partner Interest, Rent, Utilities, Depreciation, Office Equipment, Bank, Cash, Output GST, Input GST, TDS Receivable, TDS Payable, Partner Capital, Partner Current.

### C.1.2 Professional-fee income ledgers
- Per-client fee ledgers (fees receivable per client, per service, per period).
- Auto-generated from billing invoices (Phase K-I8) — invoice posted → firm voucher auto-created.
- Fees-receivable aging report per client.

### C.1.3 Partner capital & current accounts
- Tables: `partner` (name, pan, capital_share_pct, current_balance), `partner_capital_account`, `partner_current_account`.
- Partner capital introduction/withdrawal vouchers.
- Partner remuneration per firm decision + section 40(b) reasonableness check.
- Partner interest on capital (Section 40(b) ceiling: 12% of remuneration+interest, computed).
- Profit-&-Loss appropriation: net profit → partners per capital ratio.

### C.1.4 Firm P&L + Balance Sheet + appropriation
- Firm trading/P&L (professional income − expenses).
- P&L appropriation: remuneration + interest + residual profit → partner current accounts.
- Firm Balance Sheet: partners' capital + current accounts on the liability side; office assets + receivables + bank on assets.

### C.1.5 Firm's own ITR (ITR-5/3/6)
- The firm is an assessee. Generate its ReturnDraft and file via the existing ERI pipeline.
- Partner remuneration/interest auto-flows to each partner's individual ITR-3 (mirrors CompuTax "Transfer of Allowable Remuneration & Other details of partner in Firm to Partner's Individual ITR").
- Section 44ADA presumptive option for individual professionals where applicable.

### C.1.6 Firm TDS receivable (on professional fees)
- The firm earns professional fees → clients deduct TDS u/s 194J.
- Reconcile firm's own 26AS/AIS → TDS receivable ledger → claimed in firm's ITR.
- Reuses `ais_extractor/reconciliation.py` on the firm-as-assessee side.

### C.1.7 Firm as deductor (staff + outside professionals)
- Firm deducts TDS on staff salaries (24Q) and outside-professional fees (26Q).
- Uses Phase H TDS module scoped to the firm's own TAN.
- Firm pays TDS challans via Phase E-D6 e-payment.

### C.1.8 GST-compliant invoicing ledgers (filing still deferred)
- Output-GST ledger (GST collected on firm invoices by HSN/SAC).
- Input-GST ledger (GST paid on expenses).
- GST-register reconciliation (not return filing — out of scope).

### C.1.9 Bank reconciliation
- Bank-ledger vs bank-statement import → reconciliation → unmatched list.
- Auto-suggest matches by amount + date + narration.

### C.1.10 Partner/client-wise profitability
- Revenue per partner (by clients assigned to that partner).
- Revenue per client, per service, per period.
- Realization rate (collected / billed) per client.
- WIP valuation per client.

## C.2 Deliverables (end of Phase C)

1. Firm-scoped accounting tables + seeded CA-practice chart of accounts.
2. `app/engine/accounting/firm/` modules: `partner_accounts.py`, `appropriation.py`, `firm_itr.py`, `firm_tds_recon.py`, `firm_as_deductor.py`, `gst_ledgers.py`, `bank_recon.py`, `profitability.py`.
3. `app/routers/firm_accounting.py`.
4. Firm ITR-5/3/6 generation path (reuses Phase D engine once built; stub-able before then).
5. Partner remuneration → partner individual ITR transfer.
6. Firm fees-receivable aging + partner/client profitability reports.
7. Frontend `FirmAccountingPage.tsx` with partner capital/current, appropriation, profitability dashboards.

## C.3 Testing to confirm Phase C complete

- **P&L appropriation:** net profit → remuneration + interest + residual → partner current accounts sum to net profit.
- **40(b) ceiling:** remuneration+interest exceeds statutory ceiling → excess disallowed and reported correctly in firm ITR.
- **Partner transfer:** firm remuneration+interest appears in each partner's ITR-3 Schedule BP/Salary exactly.
- **Firm TDS recon:** firm 26AS TDS credits == firm TDS receivable ledger == claimed in firm ITR.
- **GST ledger:** invoice GST amount == output-GST ledger entry; no return filing attempted.
- **Bank recon:** sample bank statement → unmatched count zero after auto-match.
- **Profitability:** revenue per partner + per client matches manually computed figures from a known dataset.

---

# PHASE D — Income Tax Engine Completion (ITR-5/6/7 + ITR-U)

## D.0 Objective

Complete the ITR form coverage so Taxify is a true end-to-end Income Tax Suite: ITR-1 through ITR-7 plus ITR-U. Taxify currently has 1-4 production-grade.

## D.1 Work to be done

### D.1.1 ITR-5 (firms, LLPs, AOPs, BOIs, estates)
- Schema + calculator + ITD builder + validator + frontend editor.
- Partnership profit/share, partner remuneration/interest, firm depreciation, presumptive (44AD/ADA/AE for firms), AMT.

### D.1.2 ITR-6 (companies)
- MAT + MAT credit (extend `app/engine/schedules/amt.py`), 115BAA/115BAB, foreign income + FTC, Schedule 3CL, Schedule SI special rates.
- DSC-only filing enforced (companies cannot use EVC).

### D.1.3 ITR-7 (trusts, institutions, political parties)
- 10A/10B/10BB exemption, 115BBC special rate, corpus/anonymous-donation handling, 12A registration.
- Flag needs-legal-review before filing.

### D.1.4 ITR-U (updated return u/s 139(8A))
- Additional-tax computation (25%/50%/100% surcharge tiers by year-gap).
- `FilingRecord.itr_type="ITR-U"`; select original return to update.
- Form-registry availability windows per AY.

### D.1.5 Rectification u/s 154
- New router `POST /returns/{client}/{ay}/rectification`.
- Reuse JSON path; portal worker posts rectification.
- Track separately from original filing.

## D.2 Deliverables (end of Phase D)

1. `app/schemas/itr5.py`, `itr6.py`, `itr7.py`, `itr_u.py`.
2. `app/engine/calculators/itr5.py`, `itr6.py`, `itr7.py`, `itr_u.py`.
3. `app/engine/itd/itr5.py`, `itr6.py`, `itr7.py`, `itr_u.py` + matching `_schema.py`.
4. `app/engine/validators/itr5/`, `itr6/`, `itr7/`, `itr_u/`.
5. Frontend editors for each form.
6. Rectification router + worker path.

## D.3 Testing to confirm Phase D complete

- **Golden suite per form** (mirror `test_itr1_golden_suite.py`).
- **Official JSON-schema validation** against `Reference Docs by CBDT & ITD/Official JSON Schema/`.
- **Official-rule coverage** mirroring the ITR-2 790-rule buildout methodology in `Docs/ITR2_VALIDATOR_GAP_MAPPING_AY2026_27.md`.
- **Live Type-2 UAT call** per form (1-7 + ITR-U) before "production-ready" tag.
- **Rectification** end-to-end against a known defective-return case.

---

# PHASE E — Post-Filing Portal Automation

## E.0 Objective

Everything that happens after the return is filed: processing status, refund, demand, intimation, challan download, challan e-payment, and the mass MIS report.

## E.1 Work to be done

### E.1.1 Return processing status
- Port AayDocCapio `return_status.py` → `app/automation/return_status.py`.
- Reuse Taxify's `downloader_filed_return.py` navigation helpers.
- Table `return_status_record` (client_id, ay, status, status_date, filing_date, ack_no, checked_at).

### E.1.2 Refund status
- New `app/automation/refund_status.py` — portal refund-status extraction.
- Store refund amount, status, failure reason (bank mismatch etc.).

### E.1.3 Outstanding demand status
- New `app/automation/demand_status.py`.
- Demand-notice capture + response-due tracking → feeds Phase K-I3 notice management.

### E.1.4 Intimation order download (143(1))
- Extend `downloader_filed_return.py` or new `downloader_intimation.py`.
- Parse intimation PDF → structured comparison (computed vs processed) → flag mismatches.

### E.1.5 Challan download (e-Pay Tax Payment History)
- Port AayDocCapio `downloader_challans.py` → `app/automation/downloader_challans.py`.
- Add to `job_worker.py` dispatch.
- Store under `downloads/<PAN>-<Name>/AY_YYYY_YY/Tax Challans/`.

### E.1.6 Challan e-payment (280/281/282 via NSDL gateway)
- New `app/automation/challan_payment.py` — generate challan, redirect to bank/gateway, stop before payment (mirror AayDocCapio `challan_generator.py` Pay-Later boundary).
- Hard safety boundary: detect and refuse any "Pay Now"/"Proceed to Pay" button; only generate CRN + save.

### E.1.7 Mass processing-status + intimation report
- Batch job: loop all clients for an AY → fetch processing status → produce a "filed / processed / refund / demand / notice" summary Excel.
- This is Winman's headline MIS feature — replicate it.

## E.2 Deliverables (end of Phase E)

1. `app/automation/return_status.py`, `refund_status.py`, `demand_status.py`, `downloader_intimation.py`, `downloader_challans.py`, `challan_payment.py`.
2. New tables: `return_status_record`, `refund_record`, `demand_record`, `challan_record`.
3. New routers under `app/routers/` for status/refund/demand/challan.
4. Mass-MIS batch job endpoint.
5. Frontend status dashboard extensions.

## E.3 Testing to confirm Phase E complete

- **Recorded-HTML fixture test** per worker (no live portal needed for regression).
- **One live run** per worker before sign-off (Taxify live-verification convention).
- **Intimation parse:** sample 143(1) PDF → mismatch report flags the known differences.
- **Challan safety:** any "Pay Now"/"Proceed to Pay" selector detected → hard stop, no payment triggered.
- **Mass MIS:** 20-client batch → Excel output matches per-client statuses.

---

# PHASE F — Tax Audit Engine

## F.0 Objective

Complete tax-audit (44AB) workflow from engagement to filed 3CD and related forms, fed by Client Accounting (Phase B).

## F.1 Work to be done

### F.1.1 Audit engagement + applicability
- Table `audit_engagement` (client_id, ay, audit_type, applicable_under, due_date, auditor, partner, status).
- 44AB applicability rule engine (turnover/gross-receipts thresholds, presumptive exceptions, 44AD/ADA/AE special cases).
- Due-date computation (audit cases: 31 Oct / 30 Nov for TP).

### F.1.2 Financial-statement ingestion (from Phase B)
- Trial balance → ledger mapping → Schedule III + 3CD clauses.
- Depreciation bridge (IT vs Co. Act from Phase B-B1.6).

### F.1.3 Audit forms (form-registry driven)
- Form 3CA + 3CB (report) + 3CD (particulars) — JSON + DSC + e-filing.
- Form 3CE (non-residents), 3CEB (international TP/SDT), 3CEAA (domestic TP/SDT).
- Form 29B (MAT), 29C (section 105A credits).
- Form 10B/10BB/10CCB/10CCBC/10CCBD/56FF — exemption/audit certificates.
- Each: schema + builder + validator + filing path, AY-versioned.

### F.1.4 Audit working papers + review workflow
- Audit checklist per audit type (SOP-driven).
- Client document requests (links Phase K-I6 DMS).
- Observations/adjustments ledger.
- Maker-checker review (article → senior → partner) — links Phase K-I1 tasks.
- UDIN generation + linkage (Phase K-I7 DSC register).

### F.1.5 CA registration + "Add CA" + report approval
- Register CA on assessee's IT portal profile, track approval, attach audit report — automated.
- Mirrors CompuBal "register CA + Add CA" and Winman "audit report filing fully automated from Add CA to approval."

## F.2 Deliverables (end of Phase F)

1. `app/engine/audit/` modules: `engagement.py`, `applicability.py`, `workingpapers.py`, `forms/` (3ca.py, 3cb.py, 3cd.py, 3ce.py, 3ceb.py, 3ceaa.py, 29b.py, 29c.py, 10b.py, 10bb.py, 10ccb.py, 10ccbc.py, 10ccbd.py, 56ff.py).
2. `app/routers/audit.py`.
3. `frontend/src/pages/AuditWorkspacePage.tsx`.
4. CA-registration automation in `app/automation/audit_portal.py`.

## F.3 Testing to confirm Phase F complete

- **Applicability:** threshold boundary cases (just under / just over 1 crore / 50 lakh / 2 crore presumptive) → correct applicability verdict.
- **Golden suite per audit form** against official JSON schema.
- **Depreciation bridge:** 3CD Clause 34/35 figures match Phase B reconciling-difference schedule exactly.
- **One live Type-2 UAT 3CD submission** before "production-ready" tag.

---

# PHASE G — Statutory Forms Engine

## G.0 Objective

Every applicable Income Tax form outside the ITR family, driven by the form registry, via a generic `StatutoryForm` base so each form is a small plugin — no per-form special snowflakes.

## G.1 Work to be done

### G.1.1 Regime / relief / deduction forms
- Form 10-IEA (regime), 10E (89 relief), 67 (FTC), 10-IA/10-BA/10-DA, 10-IC/10-ID.

### G.1.2 Withholding / TDS-as-payer forms (section 194- series payer side)
- Form 26QB (property), 26QC (rent), 26QD (contractor), 26QE.
- Forms 16/16A/16B/16C/16D/16E + 27D certificate generation.
- Overlaps Phase H (TDS): payer-side TDS lives here, deductor-side TDS returns live in Phase H.

### G.1.3 Foreign-remittance forms
- Form 15CA + 15CB (CA certification).

### G.1.4 PAN / taxpayer-service forms
- Form 49A/49B (PAN application/correction) — extend existing `app/routers/pan.py`.
- Aadhaar-status check, bank-account validation, refund-bank validation, authorized-signatory updates.

### G.1.5 Appeal / post-order forms
- Form 35 (CIT(A) appeal), 36 (Tribunal), 246A (objection), Form 67.
- Linked to Phase K-I3 notice management for response workflows.

## G.2 Deliverables (end of Phase G)

1. `app/engine/forms/` plugin directory, one file per form key.
2. Generic `StatutoryForm` base class (`app/engine/forms/base.py`).
3. `app/routers/statutory_forms.py`.
4. PAN-portal extensions in `app/routers/pan.py`.

## G.3 Testing to confirm Phase G complete

- **Plugin contract test:** every form implements schema + builder + filing path; base-class assertions pass.
- **One live UAT submission** per form category (one from 10-series, one 26Q-series, one 15CA/15CB pair, one 49A) before "production-ready."
- **Integration:** 15CB certificate pulls firm-CA data from Phase C partner master.

---

# PHASE H — TDS / TRACES Module

## H.0 Objective

Full TDS compliance lifecycle for deductor clients (and for the firm itself via Phase C).

## H.1 Work to be done

### H.1.1 Deductor master
- Tables: `deductor` (tan, type, status, responsible_person, authorized_signatory, branch), `deductor_contact`.
- Multiple TANs per org; link `Client` ↔ `Deductor`.
- TRACES credentials in vault (Phase A-A1.5).

### H.1.2 TDS return preparation
- Forms 24Q (salary), 26Q (non-salary), 27Q (non-resident), 27EQ (TCS).
- Deductee data import (Excel/CSV), challan mapping, salary-detail import.
- Return validation against TRACES FVU rules.

### H.1.3 TRACES automation worker
- New `app/automation/traces_worker.py`: login → select TAN → download conso → justification report → defaults → Form 16/16A batch → store.
- Reuse `BrowserManager` singleton patterns from `downloader_26as.py`.

### H.1.4 Defaults, corrections, LDC
- Short-deduction / short-payment / late-fee defaults → correction statement prep + filing.
- Lower-deduction / nil-deduction certificate tracking (Form 13 / section 197).

### H.1.5 TDS reconciliation
- TDS credits per deductee vs 26AS/AIS → mismatch report (extend `ais_extractor/reconciliation.py` to deductor side).

### H.1.6 TRACES notices
- Section 200A intimation, 201/271H penalty, 234E late-fee → feed Phase K-I3 notice management.

## H.2 Deliverables (end of Phase H)

1. `app/db/models_tds.py` (or extension of `models.py`).
2. `app/engine/tds/` (deductee validation, FVU rules, correction logic).
3. `app/automation/traces_worker.py`.
4. `app/routers/tds.py`.
5. Frontend `TdsWorkspacePage.tsx`.

## H.3 Testing to confirm Phase H complete

- **FVU validation:** sample 24Q/26Q returns pass FVU rules; known-defective cases rejected with correct error codes.
- **One live TRACES conso download + Form 16A batch per quarter** before sign-off.
- **Reconciliation:** deductee-side TDS vs 26AS mismatch report flags a planted discrepancy.

---

# PHASE I — MCA / ROC Module

## I.0 Objective

Company/LLP master + annual + event-based MCA filings.

## I.1 Work to be done

### I.1.1 Entity master
- Tables: `company` (cin, llpin, type, status, incorporation_date, fy, registered_office, capital), `director` (din, name, designation, appointment_date, din_kyc_due), `charge` (number, date, amount, status).
- Link `Client` ↔ `Company`/`LLP` (one client can have multiple entities).

### I.1.2 Annual filings
- AOC-4 / AOC-4 XBRL (financial statements), MGT-7 / MGT-7A (annual return), ADT-1 (auditor appointment), LLP Form 8 / Form 11.

### I.1.3 Event-based filings
- Director appointment/resignation (DIR-12), registered-office change (INC-22), share transfer, charge creation/modification/satisfaction (CHG-1/CHG-4/CHG-9), DIR-3 KYC / DIR-3 KYC Web.

### I.1.4 DPT-3, MSME-1, BEN-2, PAS-6, FC-4
- All as form-registry plugins with their own due-date + applicability rules.

### I.1.5 SRN + challan + resubmission tracking
- `mca_filing` table (entity, form, srn, challan, status, resubmission_due).
- MCA portal automation worker (login → check SRN status → download approval/challan).

### I.1.6 MCA notice management
- Resubmission notices, penalty notices → Phase K-I3 notice management.

## I.2 Deliverables (end of Phase I)

1. `app/db/models_mca.py`.
2. `app/engine/mca/` (form plugins).
3. `app/automation/mca_worker.py`.
4. `app/routers/mca.py`.
5. Frontend `McaWorkspacePage.tsx`.

## I.3 Testing to confirm Phase I complete

- **One live MCA filing** per major form (AOC-4, MGT-7, DIR-3 KYC) before sign-off.
- **SRN tracking:** sample SRN → status + approval/challan downloaded.
- **Event-based applicability:** director-resignation event triggers DIR-12 + MGT-14 applicability correctly.

---

# PHASE J — Assessment-Order Checking Engine

## J.0 Objective

Independent verification of Income-Tax assessment-order calculations (CompuChk equivalent).

## J.1 Work to be done

### J.1.1 Order calculation verification
- Import order details (143(1)/143(3)/147/153A/154, appeal-effects).
- Recompute tax + interest (234B/C/D, 220(2), 244A) independently.
- Flag discrepancies (department's calc vs correct calc).
- Printable discrepancy report.

### J.1.2 Interest calculator suite
- 234A, 234B, 234C, 234D, 220(2), 244A, 201(1A) — with date-wise breakdown.

## J.2 Deliverables (end of Phase J)

1. `app/engine/order_check/` modules: `verifier.py`, `interest/` (234a.py, 234b.py, 234c.py, 234d.py, 220.py, 244a.py, 201_1a.py).
2. `app/routers/order_check.py`.
3. Frontend `OrderCheckPage.tsx`.

## J.3 Testing to confirm Phase J complete

- **Known-order cases:** sample 143(1)/154 orders → discrepancy report matches manual recomputation.
- **Interest:** date-wise breakdown for each section matches manual calculation on a planted case.

---

# PHASE K — Practice Management Layer

## K.0 Objective

The practice-operations tier (Turia/QwikCA equivalent) integrated around the ITR engine. Split into core (P1) and breadth (P2).

## K.1 Work to be done — Core (P1)

### K.1.1 Task management
- Tables: `task`, `subtask`, `task_checklist`, `task_comment`, `task_attachment`, `task_working_user`, `task_template`, `task_recurrence_rule`.
- Lifecycle: Not Started → Assigned → In Progress → Waiting for Client → Ready for Review → Changes Required → Approved → Completed → Archived.
- Views: Kanban, list, table, week, calendar; custom statuses; maker-checker; working users; comments+files; bulk reassign.
- Wire `TasksPage.tsx` into `App.tsx`.

### K.1.2 Income Tax + TDS + MCA compliance calendar
- Templates: advance-tax 15/45/75/100% (234C), ITR due dates, 44AB, 10-IEA/10-E, 234A/B/F, TDS quarterly, MCA annual, event-based.
- Recurring-task generator: template → per-client per-period task instances.
- Calendar + sprint planner. Wire `CalendarPage.tsx`.

### K.1.3 Notice management (IT + TDS + MCA unified)
- Table `notice` (client_id, department, type, issued_date, response_due, assignee, status, pdf_path, related_task_id).
- Manual entry + upload now; auto-fetch from portal workers later.
- Lifecycle: Received → Classified → Assigned → Documents Requested → Drafting → Under Review → Submitted → Resolved → Closed.
- AI OCR + classification hook (Phase N).
- Wire `NoticesPage.tsx`.

### K.1.4 Email delivery (fix + extend)
- Rewrite `app/automation/emailer.py` — remove broken `from config import _app_dir` import and AayDocCapio branding.
- Tables: `email_template`, `email_message`, `email_broadcast`.
- SMTP/Gmail/Outlook, templates, email-to-task, reply-from-app, broadcast + reminder broadcasts, delivery + read tracking, address validation, PII-redacted logs.
- Wire `CommunicationPage.tsx`.

## K.2 Work to be done — Breadth (P2)

### K.2.1 Client portal
- Separate client-side auth (OTP/password), distinct from staff.
- Document upload/download, task status, pending requests, Q&A, filing status, invoice visibility, payment link, e-verify action (bridges Phase M or standalone).

### K.2.2 Document management system (real DMS)
- Tables: `document`, `document_version`, `document_movement`, `document_request`, `document_category`.
- AES-256 at rest (extend `portal_crypto.py`), version history, categories, expiry, mobile access via portal.

### K.2.3 DSC register + licence register
- `dsc_register` (holder, custodian, expiry, movement log, token type).
- `licence_register` (GST/MSME/IEC/prof-tax/portal-password renewal dates).
- Expiry alerts → calendar.

### K.2.4 Billing + client ledger (ties to Phase C Firm Accounting)
- Tables: `service`, `rate_card`, `quotation`, `proforma`, `invoice`, `invoice_line`, `payment`, `expense`, `billable_time`, `client_ledger_entry`.
- GST-compliant invoicing (HSN/SAC), sequential numbering, firm branding.
- Razorpay/UPI links, auto-reconcile.
- Task-linked invoicing (task complete → invoice).
- 50+ collection/outstanding reports.
- Wire `BillingPage.tsx`.

### K.2.5 Timesheets + WIP
- Time logs against task + client; weekly timesheets; manager approval; billable vs non-billable; WIP roll-forward.

### K.2.6 Team management
- Attendance (IP/geo), shifts, leave, leave-balance, reimbursements, approvals inbox (one queue for leave/task-review/invoice/expense), resource planner, sprint planner.

### K.2.7 Analytics + custom report builder
- Dashboards: tasks due/overdue, compliance status, open notices, revenue, collections, outstanding, team workload, filing completion, WhatsApp results, e-verify completion, WIP aging, revenue leakage.
- Custom report builder (Excel/PDF export). Wire `ReportsPage.tsx`; extend `DashboardPage.tsx`.

### K.2.8 Engagement letters + conflict-of-interest
- `engagement_letter` (client, scope, services, period, fees, signed_at, status).
- `conflict_check` (related-party detection across client base before engagement).
- ICAI compliance that none of the practice tools surface prominently.

### K.2.9 Ready-reckoner + reference tools
- Capital-gain cost-inflation index, gold/silver rates, tax-rate tables, IFSC/BSR/PAN-TAN AO codes, interest calculators (234A/B/C/D, 220(2), 244A).

### K.2.10 Birthday reminders + client greetings
- From `Client.dob` → scheduled greeting.

### K.2.11 Mobile apps (staff + client)
- Staff: GPS attendance, expense receipts, tasks on the go.
- Client: portal + WhatsApp-style messaging + document capture.

## K.3 Deliverables (end of Phase K)

1. All practice-management routers + tables.
2. Every stubbed frontend page (`TasksPage`, `NoticesPage`, `BillingPage`, `CalendarPage`, `CommunicationPage`, `ReportsPage`) wired into `App.tsx` with live data; "Backend integration coming soon" banners removed.
3. Rewritten `emailer.py` without broken imports.
4. Mobile app scaffolds (React Native or PWA).

## K.4 Testing to confirm Phase K complete

- **Task lifecycle:** full Not-Started→Archived round-trip with maker-checker rejection path.
- **Compliance calendar:** template → per-client task instances generated for a full year.
- **Notice workflow:** manual upload → classify → assign → submit → close.
- **Email:** rewritten emailer sends a test email via SMTP without `config` import error; broken AayDocCapio branding gone.
- **Billing:** invoice posted → firm-voucher auto-created (Phase C) → client-ledger updated → outstanding report accurate.
- **DMS:** AES-256 encryption verified at rest; version history restored.
- **Mobile:** staff check-in with GPS; client uploads a document via portal.

---

# PHASE L — Portal Automation Hardening

## L.0 Objective

A single, resilient portal-automation layer shared by ITR, audit, TDS, MCA, status, and challan workers.

## L.1 Work to be done

### L.1.1 Centralized selector registry
- Move all hardcoded portal selectors into `app/automation/selectors/` (page-object pattern), per portal (ITD, TRACES, MCA).
- Selector fallback groups + role-based preference.

### L.1.2 State-based waits (replace fixed sleeps)
- Replace `asyncio.sleep` with `wait_for_url` / `wait_for_selector` / `wait_for_load_state` / loading-overlay state.

### L.1.3 Redacted failure diagnostics
- Extend `capture_failure` to redact PAN, Aadhaar, tokens, cookies before screenshot/DOM save.
- Per-failure screenshot + DOM snapshot + selector-trace log.

### L.1.4 Portal-contract fixtures
- Record live HTML per critical flow; CI runs against fixtures (no live portal needed for regression).

### L.1.5 Portal-version compatibility matrix
- Document which selectors are live-verified vs best-effort; surface "unverified" in UI for operators.

### L.1.6 Worker concurrency + recovery
- `BrowserManager` lifecycle under `asyncio.Lock`; coordinated restart; stale-context detection.

## L.2 Deliverables (end of Phase L)

1. `app/automation/selectors/` page-object registry.
2. Refactored workers using state-based waits.
3. Redacting diagnostics layer.
4. CI fixture suite.
5. Compatibility-matrix doc.

## L.3 Testing to confirm Phase L complete

- **No fixed sleeps:** grep `asyncio.sleep(` in `app/automation/` returns only explicitly-justified stabilization waits.
- **Fixture CI:** all fixture-based tests pass without network access.
- **Concurrency:** two parallel workers do not race `BrowserManager` initialization.
- **Diagnostics redaction:** a planted failure capture contains no PAN/Aadhaar/token strings.

---

# PHASE M — WhatsApp Self-Service + E-Verify (unique differentiator)

## M.0 Objective

Clients self-serve status, documents, and e-verify via WhatsApp, eliminating the 1800-2000 phone-call workload.

## M.1 Work to be done

### M.1.1 WhatsApp Cloud API integration
- Webhook endpoint `POST /whatsapp/webhook` + Meta signature verification + message-ID deduplication.
- Outbound message service: text, button, list, document.
- Tables: `whatsapp_session`, `whatsapp_message`, `whatsapp_template`.

### M.1.2 Session state machine
- States: idle → showing_clients → client_selected → showing_menu → selecting_year → confirming_action → job_running → awaiting_otp → completed → expired → cancelled.
- Timeout (3 min for OTP, 15 min idle) → session reset.
- Access always resolved: `incoming_phone → contact → linked_client → allowed_action`. Never trust a PAN typed by the user.

### M.1.3 Self-service document delivery
- Job queue (reuse existing worker pattern): "download 26AS for client X, AY Y, send via WhatsApp document message."
- Each action = create job → portal worker runs → WhatsApp document message back.
- Actions: check ITR filed status, refund status, computation (current/last/last-to-last AY), 26AS, AIS, TIS, filed ITR, ITR-V, challan, return-processing status.

### M.1.4 E-verification OTP relay (the killer feature)
- Bridge between WhatsApp session and `app/eri/type2/everify.py` (which already exists).
- Flow: client picks E-Verify + AY → bot calls `generate_evc` → portal sends OTP to client's registered mobile/email → bot asks client for 6 digits → client types in WhatsApp → bot calls `verify_evc` → audit record saved → client notified.
- Controls: explicit confirmation before starting, masked ack number, one active e-verify per client/AY, OTP never logged, OTP expiry, human fallback after repeated failures, never auto-retry with a different client/year.
- Audit record: contact, client, AY, ack no, OTP requested/submitted timestamps, final portal result, worker id.

### M.1.5 WhatsApp-to-task
- Non-self-service messages (document requests, "I got a notice", "call me") → classify → create task → assign → acknowledge to client.
- AI classification hook (Phase N).

### M.1.6 WhatsApp broadcast + reminders
- Templated compliance reminders (advance-tax due, ITR due, document pending), delivery + read tracking, skip-if-already-filed.
- Segments by service type, group, city.

## M.2 Deliverables (end of Phase M)

1. `app/whatsapp/` modules: `webhook.py`, `session.py`, `outbound.py`, `everify_bridge.py`, `broadcast.py`.
2. Tables: `whatsapp_session`, `whatsapp_message`, `whatsapp_template`, `whatsapp_job`, `everify_attempt`.
3. `app/routers/whatsapp.py`.
4. Frontend WhatsApp-monitoring dashboard.
5. E-verify audit record wired into `AuditLog`.

## M.3 Testing to confirm Phase M complete

- **Pilot:** one internal account → one family head with 3 PANs → each PAN self-serves one document.
- **E-verify negative paths:** wrong OTP → clear failure message; expired OTP → re-prompt; already-verified return → block re-attempt; portal timeout → human fallback.
- **Concurrency:** two family heads requesting the same client → access-denied for the unauthorized one.
- **Worker restart mid-OTP:** session resumes or cleanly expires, never strands.
- **WhatsApp retry:** duplicate message IDs deduplicated, no double-e-verify.
- **Rollout gate:** internal → 100 → full 1800-2000 base, e-verify enabled last.

---

# PHASE N — AI Layer

## N.0 Objective

AI as a controlled layer over structured data, never auto-taking legal actions.

## N.1 Work to be done

### N.1.1 Document intelligence
- OCR (notice PDFs, Form 16, bank statements, broker statements, Tally exports).
- PAN/client matching + field extraction → structured data → ITR schedules / audit working papers.

### N.1.2 Capital-gains mapping
- Broker Excel → CG schedule (matches KDK's "auto capital gain mapping"), with 112A grandfathering + indexation.

### N.1.3 Trial-balance + accounting-policy prep
- TB import → schedule-mapping suggestions → draft accounting policies.

### N.1.4 Workflow classification
- Incoming WhatsApp/email → suggest client, task type, due date, assignee (human confirms).

### N.1.5 Drafting (human-approved)
- Notice responses, client replies, payment reminders, engagement letters.

### N.1.6 Assistant (natural-language practice queries)
- Guard-railed read-only queries over structured data: "which clients have unverified ITRs for AY 2025-26?", "overdue advance-tax payers?", "notices needing action this week?".
- Never auto-submits filings, notice responses, legal opinions, or client comms.

### N.1.7 Audit trail
- Every AI output stores: generated text, source records, model/version, approving user, approval timestamp, final action.

## N.2 Deliverables (end of Phase N)

1. `app/ai/` modules: `document_intelligence.py`, `capital_gains_mapper.py`, `tb_mapper.py`, `classifier.py`, `drafter.py`, `assistant.py`, `audit_trail.py`, `safety_guard.py`.
2. `app/routers/ai.py` (read-only assistant + drafting endpoints).
3. `SafetyGuard` enforcing the prohibited-actions list at framework level.

## N.3 Testing to confirm Phase N complete

- **Safety guard:** every prohibited action (e-verify, filing submit, notice submit, delete, credential change) is blocked with an audit-log entry; zero exceptions.
- **OCR accuracy:** sample notice → extracted type, department, deadline match manual read on a planted fixture.
- **Assistant:** natural-language query returns correct client list; cannot mutate any data.
- **Audit trail:** every AI output has all required fields; an output without approval cannot be sent.

---

# PHASE O — Production Hardening + Release

## O.0 Objective

Everything live-verified, signed, monitored, and gradually rolled out.

## O.1 Work to be done

### O.1.1 Live-verification gate
- One live ERI Type-2 UAT call per ITR form (1-7) + ITR-U, per audit form, per statutory form, per TDS form, per MCA form — before "production-ready" tag.

### O.1.2 Security hardening
- VAPT pass, penetration test on WhatsApp webhook + client portal auth.
- Rotate any secrets that touched staging.
- Confirm `.env`, `app.db`, DSC certs/keystores never committed.

### O.1.3 Installer + packaging
- Windows installer, macOS app, cloud deployment (`Docs/AWS_FREE_TIER_DEPLOYMENT.md`).
- Cloud backup (CompuSpace equivalent) — automated daily/weekly/monthly.

### O.1.4 Monitoring + on-call
- Uptime, job-queue depth, portal-automation failure-rate alerts.

### O.1.5 Gradual rollout
- Internal → 100 clients → 500 → full 1800-2000 base, with e-verify enabled last.

## O.2 Deliverables (end of Phase O)

1. Live-verification matrix (one row per form/flow, signed-off with live-call evidence).
2. VAPT report + remediation.
3. Windows/macOS installers + cloud deployment runbook.
4. Monitoring dashboards + alert routing.
5. Rollout runbook with go/no-go gates per cohort.

## O.3 Testing to confirm Phase O complete

- **Live gate:** every form/flow in the matrix has a passed live call.
- **VAPT:** no Critical/High findings open.
- **Installer:** clean-machine install succeeds; `app.db` and `.env` not in package.
- **Rollout:** each cohort passes its go/no-go gate before the next starts; e-verify cohort gate is the final one.

---

# 3. Priority Sequencing Summary

| Priority | Phase | Rationale |
|---|---|---|
| **P0** | A (foundation) | Everything depends on org/roles/contacts/form-registry |
| **P0** | B (client accounting) | ITR-5/6/7 + audit + 3CD need real financials |
| **P0** | C (firm accounting) | Corrected addition; firm is an assessee too; drives billing |
| **P0** | M1.4 (WhatsApp e-verify) | Unique differentiator; depends only on A2 + existing everify API |
| **P1** | D (ITR-5/6/7 + ITR-U) | Completes the "Income Tax Suite" core claim |
| **P1** | E (post-filing automation) | Status/refund/demand/challan — every competitor has these |
| **P1** | F (tax audit) | Needs B + C; large scope but core to "complete" |
| **P1** | K.1.x (tasks + calendar + notices + email core) | Practice-ops backbone; unblocks WhatsApp-to-task + notice workflows |
| **P2** | G (statutory forms) | Form-registry-driven, parallelizable |
| **P2** | H (TDS/TRACES) | Separate portal; can run parallel |
| **P2** | I (MCA/ROC) | Separate portal; parallel |
| **P2** | J (assessment-order checking) | Standalone engine; high CA value |
| **P2** | K.2.x (portal, DMS, DSC/licence, billing, timesheets, team, analytics, engagement, ready-reckoner, birthday, mobile) | Practice-ops breadth |
| **P3** | L (automation hardening) | Cross-cutting; ongoing |
| **P4** | N (AI) | Depends on data from everything above |
| **P4** | O (release) | Final gate |

---

# 4. Dependency Graph

```
A (foundation) ──┬─→ B (client accounting) ──→ C (firm accounting)
                 │
                 ├─→ D (ITR-5/6/7 + ITR-U)
                 │
                 ├─→ E (post-filing) ──→ J (order checking)
                 │
                 ├─→ F (tax audit) ←── B, C, D
                 │
                 ├─→ G (statutory forms)
                 │
                 ├─→ H (TDS/TRACES) ←── E
                 │
                 ├─→ I (MCA/ROC)
                 │
                 ├─→ K (practice mgmt) ──→ M (WhatsApp)
                 │
                 └─→ M.1.4 (WhatsApp e-verify) ←── A2 + existing everify API

L (automation hardening) ──→ all portal workers (E, F, H, I)
N (AI) ──→ all data phases
O (release) ──→ all phases
```

---

# 5. Two-Accounting-Domain Boundary (the corrected split)

| Question | Client Accounting (Phase B) | Firm Accounting (Phase C) |
|---|---|---|
| Whose books? | The client's business | The practitioner's own CA firm |
| `book_owner` scope | `client_id` | `organization_id` |
| Drives | ITR, audit, statutory forms | Firm billing, partner profitability, firm's own ITR-5/3/6 |
| Seed chart of accounts | General business COA | CA-practice COA (Professional Fees, Partner Capital, etc.) |
| Partner accounts? | No | Yes (capital + current + 40(b) ceiling) |
| Fees receivable? | No (client is not the firm) | Yes (per client, per service) |
| TDS receivable on fees? | No | Yes (firm's 26AS recon) |
| Firm as deductor? | No | Yes (staff 24Q + outside-professional 26Q) |
| GST ledgers? | No | Yes (output/input; filing deferred) |
| Bank reconciliation? | Client bank | Firm bank |
| Profitability reports? | Per client | Per partner + per client |

Both share the same double-entry engine but never cross books. A voucher in the firm book never touches a client's ledger, and vice versa.

---

# 6. Explicit Exclusions (to keep focus on "best Income Tax Suite")

- **GST return filing** (GSTR-1/3B/9/9C, e-invoice, e-way-bill) — deferred. Output/input-GST ledgers exist in Firm Accounting only because the firm raises GST-compliant invoices.
- **Employee screen monitoring / webcam watch / internet-surf logging** (CompuWatch) — privacy-hostile, out of scope.
- **Retail ERP / inventory / POS / multi-branch retail** (Marg ERP) — out of scope.
- **Standalone HR/payroll product** — only kept as a TDS-on-salary data source for 24Q, not a full HR suite.

---

# 7. The One-Line Positioning

> **Taxify — the world's first Income Tax Suite that combines a live-verified ITR-1-to-7 + ITR-U engine, a complete double-entry Client Accounting engine, a complete double-entry Firm Accounting engine, a tax-audit engine, full TDS/TRACES and MCA/ROC coverage, a CA practice-management platform, and a WhatsApp self-service portal where clients e-verify their own returns — built to be the best, not the broadest.**

---

# 8. Phase Completion Checklist (generic template)

For every phase, a phase is marked **completed** only when all of the following are true:

1. **Objective met** — the stated objective is fully implemented, not partially.
2. **Deliverables produced** — every item in the Deliverables section exists and is wired.
3. **Testing passed** — every test in the phase's Testing section passes, including any live-verification gate.
4. **Regression green** — the existing `pytest` suite does not have new failures attributable to this phase (baseline ~177 failures / 13 collection errors predating current work).
5. **No broken imports** — the undeclared-imports audit (from `CLAUDE.md`) reports no missing modules.
6. **Audit logging** — every consequential action appends to `AuditLog` where applicable.
7. **Documentation** — the phase's runbook updated in `Docs/` with live-call evidence or fixture evidence.
8. **Sign-off** — the phase owner explicitly marks it completed; for filing/audit/everify flows, a live UAT call's evidence is attached.

A phase is **not** completed by code existing alone; it is completed only when its verification bar is met.

---

*End of THE COMPLETE TAXIFY plan. This document is the scope baseline; any deviation requires an explicit scope-change approval. No existing Taxify source file was modified to produce this document.*
