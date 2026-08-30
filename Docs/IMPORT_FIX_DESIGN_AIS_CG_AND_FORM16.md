# Import Fix — Design Document (AIS Capital Gains + Form 16 Parser)

**Created:** 2026-08-30
**Status:** DRAFT — for review before implementation
**Scope (confirmed by product owner):**
1. **Improve AIS-side capital-gains handling** (no broker-file import)
2. **Build a Form 16 PDF/Excel parser** (salary schedule)
**Explicitly OUT of scope (per decision):**
3. Broker-file (Zerodha/Groww/Upstox/...) capital-gains import — **not** this pass
4. Filed-return reactor (`# REACTIVATE` blocks) — **remains dormant**
5. Isolated AIS regex dead-code cleanup — housekeeping only, noted

---

## Context — what already works

The import/reconciliation core is built and mostly wired. Verified against current code:

- **Extractors (100% corpus-tested as parsers):** AIS (65/65), TIS (64/64) via pdfplumber; 26AS (PDF/TXT/ZIP); Prefill JSON (form-agnostic, 82KB).
- **Reconciliation engine** (`ais_extractor/reconciliation.py::reconcile`) — 3-way TIS>AIS>26AS merge, CBDT category→income-head map, discrepancy detection, capital-gains evidence ledger, prefill-TDS↔26AS cross-check by TAN.
- **Persistence:** `imported_document` table + shared `imported_document_service`; server-side reconcile endpoint `GET /integration/reconciliation/client/{id}`; single dedup key (client × AY × doc_type). (P1–P6, R1, R2 resolved.)
- **Frontend population:** `mapReconciledToDraftPatch.ts`, `mapCapitalGainsToDraftPatch.ts`, `mapPrefillToDraftPatch.ts`, `mapAis/Tis/26asToDraftPatch.ts` consume the reconciled payload into `ReturnDraftPatch`.
- **Official-schema validation** (ITR-1/2/4) wired into gateways.

---

## Part A — AIS-side capital-gains handling (improvement, no broker import)

### A.1 Current behaviour (verified in `_extract_capital_gain_ledger`, reconciliation.py:571)

The extractor reads the AIS detail tables and emits flat per-transaction rows:

- **Sales** from `SFT-17-LES` / `SFT-18-EMF` sale tables, `SFT-012` immovable-property sale, and summary-only entries.
- **Purchases** from `SFT-17(Pur)` / `SFT-18(Pur)` and `SFT-012(P)`.
- Each sale row captures: `information_code`, `reporting_source`, `reporting_entity_pan`, `security_name`, `security_identifier` (ISIN extracted via regex from the name cell), `transaction_date`, `quantity`, `sale_price_per_unit`, `total_sale_value`, `acquisition_cost` (from the AIS `COST ACQUISITION` column via `_first_amount`), `fair_market_value`, `unit_fmv`, `asset_type` (Long/Short term), `security_class`, `status`, `is_summary`.
- Immovable rows capture property address/type, transaction/assigned amount (per-party share), stamp-duty value, party count.

The frontend `mapCapitalGainsToDraftPatch.ts` maps these onto the CG schedule; `restricted_112a.py` consumes the reconciled **purchase** totals for the restricted-112A cost computation.

### A.2 Gap analysis (what's wrong with the AIS-only path)

1. **Cost basis is 100% AIS-supplied.** `acquisition_cost` comes from whatever the ITD emits in the `COST ACQUISITION` cell. The ITD does **not** populate cost for every transaction (many SFT rows carry only the consideration side). Where absent, cost is `None` → the CG row can't complete the gain, or falls back to FMV-only.
2. **No 31-Jan-2018 (112A) grandfathering cost.** The AIS carries an `acquired_before_31_jan_2018` signal in some rows but no computed pre-2018 FMV cost basis. `restricted_112a.py` computes the restricted-112A cost from reconciled **purchase** totals — but if the taxpayer's purchase predates the AIS window (or the AIS purchase table is empty for that scrip), the 112A cost is missing. **This is the single biggest correctness hole in the AIS-only CG path.**
3. **No corporate-action adjustment.** Bonus/rights/split shares have a structural cost (bonus = ₹0, retained holding period; rights = rights price, original period). The AIS is raw sale-side and does not supply this; without it, per-unit cost for a scrip with a corporate action is wrong, and the holding period (ST vs LT) can be misclassified.
4. **No intra-AIS sale↔Rise cross-foot for cost.** Sales and purchases are extracted independently; the restricted-112A cost pulls purchase totals but there's no per-scrip reconciliation that matching a sale to the most recent purchase (lot) — so average-cost vs specific-share handling is unresolved.
5. **`asset_type` is taken verbatim from the AIS** (`Long term` / `Short term`) — trusted without an independent holding-period check against purchase date.

### A.3 Proposed design — improvements within the AIS source only

> Design principle: **stay within the AIS as the sole CG source** (per decision), but make the AIS path *computationally complete and honest* rather than pass-through. Where the AIS cannot supply a cost, expose it explicitly and flag for manual review instead of silently producing a wrong gain.

**A.3.1 A schema-level CG row extension** (backward-compatible — additive fields):

Add to each sale row in `_extract_capital_gain_ledger`:
- `cost_source`: enum `AIS` | `FMV_31JAN2018` | `COMPUTED_112A` | `NOT_SUPPLIED`
- `cost_confidence`: `high` | `low` | `missing`
- `acquisition_date` (when the AIS carries it) — needed for holding-period check
- `stt_eligible`: bool derived from `debit_type`/`credit_type`/status + recognized-exchange signal already in row
- `grandfathering_fmv` (the AIS `unit_fmv` / `fair_market_value` where present) — retained for the 112A check
- `holding_period_days` / `is_long_term` — **computed**, not verbatim, where acquisition date is available
- `corporate_action_flag`: set when a sale quantity appears inconsistent with a single-lot purchase (heuristic; surfaces for review)

**A.3.2 A 112A/grandfathering cost-resolution layer** (new small module, e.g. `app/engine/schedules/cg_cost_resolution.py` or extend `restricted_112a.py`):

Given a sale row + the reconciled purchase ledger, resolve the cost by priority:
1. If AIS supplies `acquisition_cost` → use it (`cost_source=AIS`).
2. Else if `acquired_before_31_jan_2018` and an FMV basis exists (AIS `unit_fmv`/`fair_market_value`, or the ₹0-cost / FMV-as-on-31-01-2018 rule) → compute the **Section 112A cost** (`cost_source=COMPUTED_112A`) and flag `cost_confidence=low`.
3. Else if a matching purchase row exists (by ISIN, lot) → average cost per unit (or explicit lot matching) → `cost_source=COMPUTED_112A`.
4. Else → `cost_source=NOT_SUPPLIED`, `cost_confidence=missing`, and **emit a `cost_unsupplied[]` advisory entry** so the UI lists "these CG rows need cost entered manually" rather than surfacing a silent ₹0 gain.

**A.3.3 A per-scrip gain reconciliation** (additive):

For each scrip, cross-foot `sales consideration ↔ purchase cost + gain` so the CG schedule is internally consistent, and push any unexplained gap to `capital_gain_control_discrepancies[]` (already an output channel).

**A.3.4 UI/reporting:**

- Extend `mapCapitalGainsToDraftPatch.ts` to carry `cost_source`/`cost_confidence` into the draft patch so the CG tab badges each row with its provenance and highlights rows awaiting manual cost entry (the "no-silent-zeros" principle, applied to cost).
- Add an import-time advisory listing CG rows with missing cost so the CA can complete them before filing.

### A.4 Deliverables

- `reconciliation.py::_extract_capital_gain_ledger` — additive row fields (A.3.1)
- New CG-cost-resolution module (A.3.2) + unit tests (fixtures: cost-supplied, pre-2018 → 112A FMV, purchase-lot average, missing-cost)
- Per-scrip control cross-foot (A.3.3)
- Frontend mapper extension + badge/advisory UI (A.3.4)
- Tests: keep 145-pass import-contract suite green; add CG-specific cases.

---

## Part B — Form 16 parser (PDF + Excel → salary schedule)

### B.1 Current state (verified)
- `POST /integration/form16/extract` returns **HTTP 501** (`integration.py:157`).
- No parser file exists in `ais_extractor/` or `app/engine/importers/`.
- No frontend `mapForm16ToDraftPatch.ts` (only incidental references in pages/eligibility/api).
- Today salary is entered manually.

### B.2 Goal
Parse Form 16 (Part A + Part B) into a **salary-schedule extraction** that the existing `mapReconciledToDraftPatch`-style flow can consume, and that populates `employerEntries[]` + the salary/TDS fields the same way Prefill does.

### B.3 Design
**B.3.1 New parser: `ais_extractor/form16_extractor.py`**
- Input: `bytes` (PDF) and/or Excel/CSV template.
- Output: a `Form16Extraction` dataclass + `form16_to_frontend_json()`, matching the shape convention used by the other extractors.

**Fields to extract:**
- **Part A (employer/TDS certificate):** TAN, employer name; per-quarter TDS deposited (Q1–Q4); total TDS on salary; (used for 26AS↔Form16 TDS cross-check).
- **Part B (salary break-up):** gross salary (salary u/s 17(1)); value of perquisites 17(2); profits in lieu 17(3); **income chargeable under "Salaries"** (the net figure); **Standard deduction u/s 16(ia);** professional tax 16(iii); income u/s 17(2) perquisites; income u/s 17(1); total; **Chapter VI-A deductions claimed** (80C, 80CCD(1), 80CCD(1B), 80D, 80E, 80TTA/TTB, 80G, etc.); tax payable; TDS deductible u/s 192; relief u/s 89; surcharge+cess; total tax.
- Note 2025 scheme changes: standard deduction ₹75,000 (new regime) — field must be version-tolerant.

**Parsing approach:**
- **PDF:** Form 16 is a form, not free text (values are in labelled field/value rows across 1–2 pages). Use pdfplumber `extract_words`/`extract_text` with **label-anchored keying** (find the label, take the following numeric token) — the same label-anchoring discipline as the AIS/TIS extractors. Tolerance for the label/value whitespace variation that the AIS extractor already solved with `\s+` collapsing.
- **Excel/CSV:** the CA working sheet (many firms use a standard Form 16 Excel template). Parse via column headers. Support the common template shapes; document the supported header set.
- **PDF decryption:** Form 16s are sometimes password-protected; reuse the existing `pdf_unlocker.py` + `verify_pdf_decryptable()` (DOB-based) path rather than a new one.

**B.3.2 Endpoint** — replace the 501 in `integration.py:157`:
- `POST /integration/form16/extract` (multipart file: `file` + `pdf_password` optional) → `extract_form16(...)` returns `Form16Extraction` (or 422 on parse failure).
- Persist to `imported_document` with `document_type='form16'` via the shared `imported_document_service` (mirrors AIS/TIS/26AS).
- Keep it symmetric with the other docs (parse + persist + return).

**B.3.3 Frontend mapper** — new `frontend/src/utils/mapForm16ToDraftPatch.ts`:
- Consumes `Form16Extraction` → produces `ReturnDraftPatch` populating `employerEntries[]` (TAN, gross, perquisites, profits-in-lieu, nature-of-employment), the salary computation fields, and TDS-salary rows.
- Precedence to match the existing merge order in `ITRComputationPage.handleConfirmImport` (filed-return < Prefill < reconciled). Decide where Form 16 sits: **proposal — Form 16 supplies the salary-head break-up that Prefill/AIS don't fully carry, so merge it at the same precedence as Prefill for salary fields.** Confirm in review.

**B.3.4 Reconciliation touch (small):**
- `reconcile()` already cross-checks prefill-TDS vs 26AS-TDS by TAN. Add an optional `form16_data` param to cross-check **Form-16 total TDS vs 26AS TDS**, and flag discrepancies (same pattern as `prefill_tds_discrepancies[]`). *(Optional stretch — flag if it adds risk; can be a follow-up.)*

### B.4 Deliverables
- `ais_extractor/form16_extractor.py` (pdfplumber label-anchored + Excel/CSV)
- 501→real endpoint in `integration.py` + persistence
- `mapForm16ToDraftPatch.ts` + tests
- Corpus test set: 8–10 real Form 16 PDFs (salary + perquisite + relief variants) — target 100% like the AIS/TIS parsers
- Optional: form16-TDS↔26AS cross-check in `reconcile()`

---

## Out of scope this pass (confirmed)

- **Broker capital-gains import** — deferred. The AIS improvements above (especially the 112A cost-resolution + cost-unsupplied advisory) are the correct foundation; a broker import can plug in later as a *second cost source* feeding the same `cost_source` enum (`BROKER`).
- **Filed-return `# REACTIVATE` blocks** — remain dormant, untouched.
- **AIS legacy regex dead path** (`_parse_listed_equity_sale_rows`) — leave for a separate housekeeping pass; noted here only so it's tracked.

---

## Risks / open questions for review

1. **AIS scope limit:** Without a broker file, the 112A cost and corporate actions depend entirely on what the AIS emits + our computation. Some rows will still end up `cost_source=NOT_SUPPLIED` and need manual entry. Is that acceptable for this pass (my recommendation: yes — honesty over false auto-fill), or should we fast-track broker import?
2. **Form 16 merge precedence** — where should Form-16 salary sit relative to Prefill/reconciled in `handleConfirmImport`? (Proposal: Prefill-level for salary fields.)
3. **Form 16 TDS↔26AS cross-check** — include in this pass (small) or defer to follow-up to reduce risk?
4. **Auto or manual AY** — Form 16 extraction should read the AY from the certificate and validate it matches the active assessment year (same guard the downloaders use).

---

*Review this before implementation begins. Once approved, I'll implement Part A then Part B, keeping the existing 145-pass import-contract + 1137-pass backend + 135-pass frontend suites green.*
