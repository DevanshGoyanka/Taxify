# Import Flow End-to-End Audit Report

**Date:** 2026-08-15
**Scope:** Complete audit of the import pipeline — Prefill JSON, Form 26AS, AIS, TIS, last-filed ITR JSON — from import button click through parsing, storage, reconciliation, and form auto-population. Includes individual document imports and portal automation.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Architecture Overview: The Two Import Paths](#2-architecture-overview-the-two-import-paths)
3. [Path A: Portal Automation Import (The Production Path)](#3-path-a-portal-automation-import-the-production-path)
4. [Path B: Individual Document Import (The Mock/Stub Path)](#4-path-b-individual-document-import-the-mockstub-path)
5. [Document-by-Document Deep Dive](#5-document-by-document-deep-dive)
6. [Reconciliation Engine Deep Dive](#6-reconciliation-engine-deep-dive)
7. [Form Auto-Population Deep Dive](#7-form-auto-population-deep-dive)
8. [Storage Audit](#8-storage-audit)
9. [Critical Gaps and Broken Parts](#9-critical-gaps-and-broken-parts)
10. [Year-Adaptive Architecture Impact on Imports](#10-year-adaptive-architecture-impact-on-imports)
11. [Implementation Plan: Fixing the Import Pipeline](#11-implementation-plan-fixing-the-import-pipeline)

---

## 1. Executive Summary

The import pipeline has **two completely separate paths** that share almost no code:

| Path | Status | Used in production? |
|---|---|---|
| **Path A: Portal Automation** (ITD portal → Playwright → PDF download → PDF extraction → reconciliation → form population) | ✅ Mostly working — real parsers, real reconciliation engine, real form mapper | Yes — this is what the "Import from Portal" button does |
| **Path B: Individual Document Upload** (user uploads AIS/TIS/26AS/Prefill/Form 16 files) | ❌ Almost entirely mock data and stubs | No — every endpoint returns hardcoded fake data |

**The reconciliation engine (`ais_extractor/reconciliation.py`) is genuinely production-quality** — it handles cross-document matching, PAN-based deduplication, TIS-accepted-amount priority, capital-gain evidence extraction, and discrepancy detection. But it only receives data from Path A. Path B feeds fake data into a dead endpoint.

**The Prefill JSON pipeline is completely broken** — the `/integration/prefill/import` endpoint returns `{"status": "imported", "message": "Prefill data imported successfully"}` without doing anything. The `prefill_service.py` has a `prefill_to_itr1_input()` function that hardcodes `"ay": 2025` (wrong year) and never gets called by any route.

**No imported document is persisted to the database.** Only the final reconciled result is stored in the `automation_job.parsed_results` column as a JSON blob. Raw AIS, TIS, 26AS, and Prefill artifacts are downloaded to disk and deleted on the next job. There is no `ImportedDocument` table.

---

## 2. Architecture Overview: The Two Import Paths

```
┌─────────────────────────────────────────────────────────────────────┐
│                         IMPORT FLOW MAP                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Path A: PORTAL AUTOMATION (working, production)                    │
│  ─────────────────────────────────────                               │
│  Frontend: "Import from Portal" button                              │
│     → itrAutomationApi.startImport(clientId, ay)                    │
│     → POST /clients/{id}/automation/import?assessment_year=2026-27  │
│                                                                     │
│  Backend: app/automation/job_worker.py                              │
│     1. Playwright browser session → ITD portal login                 │
│     2. download_26as() → 26AS PDF → disk                           │
│     3. downloader_ais_tis() → AIS PDF + TIS PDF → disk             │
│     4. downloader_prefill() → Prefill JSON → disk                  │
│     5. downloader_filed_return() → last ITR JSON → disk            │
│     6. _extract_26as() → ais_extractor.as26_extractor               │
│     7. _extract_ais() → ais_extractor.extractor                     │
│     8. _extract_tis() → ais_extractor.tis_extractor                │
│     9. reconcile() → ais_extractor.reconciliation                  │
│    10. Store reconciled JSON in automation_job.parsed_results      │
│    11. Frontend polls getJobStatus() → gets parsed_results        │
│    12. mapReconciledToFormData() → formData update                │
│    13. ImportConfirmationModal → user approves                    │
│    14. applyLegacyPatch() → editor model updated                   │
│                                                                     │
│  Path B: INDIVIDUAL UPLOAD (broken, mock/stub)                      │
│  ─────────────────────────────────────                               │
│  Frontend: "Import File" dropdown                                    │
│     → handleFileImport(type, file)                                  │
│     → integrationApi.importAIS/importTIS/import26AS/etc.           │
│     → POST /integration/ais-json/import                             │
│     → POST /integration/tis/import                                 │
│     → POST /integration/26as/import                                 │
│     → POST /integration/prefill/import                              │
│     → POST /integration/form16/extract                              │
│                                                                     │
│  Backend: app/routers/integration.py                                │
│     → Returns hardcoded mock data for every endpoint               │
│     → No persistence                                                │
│     → No reconciliation                                             │
│     → autoPopulateAll() returns mock employer/bank/dividend        │
│     → prefill_autopopulate() returns formData unchanged            │
│     → reconciliation() returns {"hasDiscrepancies": False}         │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. Path A: Portal Automation Import (The Production Path)

### 3.1 Frontend Trigger

**File:** `frontend/src/pages/ITRComputationPage.tsx` ~line 874

```typescript
const res = await itrAutomationApi.startImport(clientId, ayParam || '2026-27');
setAutomationJobId(res.job_id);
setShowStatusBox(true);
```

**API:** `POST /clients/{clientId}/automation/import?assessment_year=2026-27&job_type=DOWNLOAD_ALL`

### 3.2 Backend Job Worker

**File:** `app/automation/job_worker.py`

The worker runs these steps:

| Step | Action | Downloader | Output |
|---|---|---|---|
| 1 | Login to ITD portal | `app/automation/auth.py` | Playwright page |
| 2 | Download Form 26AS | `downloader_26as.py` | PDF on disk |
| 3 | Download AIS | `downloader_ais_tis.py` | PDF on disk |
| 4 | Download TIS | `downloader_ais_tis.py` | PDF on disk |
| 5 | Download Prefill JSON | `downloader_prefill.py` | JSON on disk |
| 6 | Download Filed Return (last ITR) | `downloader_filed_return.py` | JSON on disk |
| 7 | Verify PDF decryptable | `pdf_unlocker.py` | Unlocked PDF |
| 8 | Extract 26AS data | `ais_extractor/as26_extractor.py` | Structured JSON |
| 9 | Extract AIS data | `ais_extractor/extractor.py` | Structured JSON |
| 10 | Extract TIS data | `ais_extractor/tis_extractor.py` | Structured JSON |
| 11 | Reconcile all three | `ais_extractor/reconciliation.py` | Reconciled JSON |
| 12 | Store in DB | `automation_job.parsed_results` | JSON blob column |

### 3.3 What Works in Path A

| Component | Status | Notes |
|---|---|---|
| Playwright portal login + navigation | ✅ | `auth.py`, `navigation.py` handle session expiry |
| 26AS PDF download | ✅ | `downloader_26as.py` |
| AIS/TIS PDF download | ✅ | `downloader_ais_tis.py` |
| Prefill JSON download | ✅ | `downloader_prefill.py` — validates PAN + AY in downloaded JSON |
| Filed return JSON download | ✅ | `downloader_filed_return.py` — downloads last filed ITR |
| 26AS PDF → structured JSON | ✅ | `ais_extractor/as26_extractor.py` — parses Parts I, IV, VII |
| AIS PDF → structured JSON | ✅ | `ais_extractor/extractor.py` — state machine, 1246 lines |
| TIS PDF → structured JSON | ✅ | `ais_extractor/tis_extractor.py` |
| Reconciliation (AIS + TIS + 26AS → unified) | ✅ | `ais_extractor/reconciliation.py` — 1000+ lines, comprehensive |
| Reconciled data → formData mapping | ✅ | `mapReconciledToFormData.ts` — handles salary, interest, dividend, CG, TDS, TCS, business |
| Import confirmation modal | ✅ | Shows discrepancies, unmatched entries, category control issues |
| Job status polling | ✅ | `itrAutomationApi.getJobStatus(jobId)` |
| Progress UI | ✅ | StatusBox with progress %, status messages |

### 3.4 What's Broken in Path A

| Issue | Severity | Details |
|---|---|---|
| **Prefill JSON is never parsed into form data** | 🔴 Critical | `downloader_prefill.py` downloads and validates the Prefill JSON, but `job_worker.py` never calls any parser to extract fields from it. The Prefill JSON sits on disk and is deleted. The reconciled output only contains AIS/TIS/26AS data — no Prefill fields (salary break-up, deductions, bank accounts, employer details) ever reach the form. |
| **Last filed ITR JSON is never imported** | 🔴 Critical | `downloader_filed_return.py` downloads the last filed ITR JSON, but `job_worker.py` never parses it or feeds it into the reconciliation or form population. It's downloaded and discarded. |
| **Prefill JSON not fed into reconciliation** | 🟡 Major | The reconciliation engine only takes AIS, TIS, 26AS — it has no concept of Prefill data. Prefill should provide salary break-up, deductions, bank accounts, and employer details that AIS/TIS/26AS don't carry. |
| **No document persistence** | 🟡 Major | Raw PDFs and JSONs are downloaded to a temp directory and deleted. Only the final reconciled JSON is stored in `automation_job.parsed_results`. There's no way to re-parse or re-reconcile later without re-downloading. |
| **No Prefill-specific field extraction** | 🟡 Major | `prefill_service.py` has `map_26as_to_prefill()`, `map_ais_to_prefill()`, and `prefill_to_itr1_input()` — but none of these functions are called by any route. They're dead code. |
| **Assessment year hardcoded** | 🟡 Major | `downloader_prefill.py` line 20: `AY = "2026-27"`. The Prefill downloader rejects any AY ≠ "2026-27" outright. |
| **Double computation risk** | 🟡 Minor | `job_worker.py` doesn't call the tax engine, but the frontend's `mapReconciledToFormData` sets `basic`, `interestSB`, `interestFD`, `dividendShares` AND `employerEntries`, `interestEntries`, `dividendEntries` — the backend tax engine sums both the scalar and array fields, risking double-counting. The mapper has comments acknowledging this risk. |

---

## 4. Path B: Individual Document Import (The Mock/Stub Path)

### 4.1 Frontend Trigger

**File:** `frontend/src/pages/ITRComputationPage.tsx` ~line 1019

```typescript
if (type === 'ais-pdf' || type === 'ais-json' || type === 'tis-pdf' || '26as-pdf' || '26as-txt' || 'prefill') {
  if (typeStr === 'prefill') {
    data = await integrationApi.importITDPrefill(file, legacyClientId!, effectiveAssessmentYear);
  } else if (typeStr === 'ais-json') {
    data = await integrationApi.importAISJson(file, pan!, dob!);
  } else if (typeStr === 'ais-pdf') {
    data = await integrationApi.importAIS(file, legacyClientId!, effectiveAssessmentYear, pan!, dob!);
  }
  // ...
}
```

### 4.2 Backend Endpoints — What They Actually Return

**File:** `app/routers/integration.py`

Every endpoint in this file returns **hardcoded mock data**:

| Endpoint | What it should do | What it actually does |
|---|---|---|
| `POST /integration/form16/extract` | Parse Form 16 PDF, extract employer + salary + TDS | Returns hardcoded `{"employerName": "TATA CONSULTANCY SERVICES LTD", "grossSalary": 1250000.0, ...}` |
| `POST /api/v1/imports/ais` | Parse AIS PDF/JSON, extract income heads + TDS + SFT | Returns hardcoded mock AIS with TATA employer, Reliance securities, HDFC mutual fund |
| `POST /integration/ais-json/import` | Same as above for JSON input | Tries `decrypt_ais_json()`, falls back to hardcoded mock on any exception |
| `POST /integration/tis/import` | Parse TIS, extract accepted income totals | Returns hardcoded `{"dividendIncome": 12000.0, "salaryAmount": 1250000.0, ...}` |
| `POST /integration/26as/import` | Parse 26AS text/PDF, extract TDS entries | Tries `parse_26as_txt()`, falls back to hardcoded mock TATA + HDFC entries |
| `POST /integration/prefill/import` | Parse Prefill JSON, extract all fields | Returns `{"status": "imported", "message": "Prefill data imported successfully"}` — does nothing |
| `POST /integration/autopopulate/form16` | Merge Form 16 data into formData | Returns `{**form_data, **updates}` with 6 fields from the mock Form 16 |
| `POST /integration/autopopulate/ais` | Merge AIS data into formData | Returns `{**form_data}` — does nothing |
| `POST /prefill/autoPopulateAll` | Combine 26AS + AIS + TIS → form data | Returns hardcoded employer/bank/dividend entries using TATA/HDFC/Reliance mock names |
| `POST /integration/reconciliation` | Reconcile AIS + 26AS + TIS | Returns `{"hasDiscrepancies": False, "items": []}` — always |
| `POST /prefill/autopopulate` | Merge Prefill into formData | Returns `{**form_data}` — does nothing |

### 4.3 What's Broken in Path B

| Issue | Severity | Details |
|---|---|---|
| **Every endpoint returns mock data** | 🔴 Critical | The `integration.py` router is a mock. No real parsing happens for uploaded documents. |
| **No AIS PDF parsing for individual uploads** | 🔴 Critical | The real AIS parser (`ais_extractor/extractor.py`) is only called by `job_worker.py`. Individual AIS uploads go to `/integration/ais-json/import` which tries a decryptor and falls back to mock. |
| **No TIS parsing for individual uploads** | 🔴 Critical | TIS uploads always get hardcoded mock data. |
| **No 26AS text parsing for individual uploads** | 🟡 Major | The real 26AS parser (`ais_extractor/as26_extractor.py`) is only called by `job_worker.py`. Individual 26AS uploads try `parse_26as_txt()` from `app/automation/as26_converter.py` (a different, older parser), but fall back to mock on any error. |
| **No Prefill JSON parsing for individual uploads** | 🔴 Critical | `importITDPrefill()` calls `/integration/prefill/import` which returns a success message and does nothing. |
| **No reconciliation for individual uploads** | 🔴 Critical | `getReconciliationReport()` calls `/integration/reconciliation` which always returns `{"hasDiscrepancies": False, "items": []}`. |
| **No storage for individual uploads** | 🔴 Critical | Uploaded files are processed in-memory and discarded. No DB persistence. |
| **Dead code: `prefill_service.py`** | 🟡 Major | Contains `map_26as_to_prefill()`, `map_ais_to_prefill()`, `prefill_to_itr1_input()` — none called by any route. `prefill_to_itr1_input()` hardcodes `"ay": 2025` (wrong year). |

---

## 5. Document-by-Document Deep Dive

### 5.1 Prefill JSON (ITD Pre-filled Data)

**What it is:** The official CBDT pre-filled JSON downloaded from the ITD portal. Contains the taxpayer's personal info, salary details, house property, other sources income, deductions (Chapter VI-A), bank accounts, TDS/TCS schedules, and tax payments — essentially a pre-populated ITR.

#### Current State: BROKEN

| Stage | Status | Details |
|---|---|---|
| Download (portal automation) | ✅ Works | `downloader_prefill.py` downloads + validates PAN/AY in the JSON |
| Storage | ❌ Not stored | JSON sits on disk, deleted after job |
| Parsing | ❌ Never parsed | No parser exists in the active code path. `prefill_service.py` has mapper stubs but they're never called |
| Reconciliation | ❌ Not reconciled | Reconciliation engine doesn't accept Prefill data |
| Form population | ❌ Never populated | No field from Prefill JSON reaches the form |

**Gap:** The Prefill JSON is the single most valuable document for auto-population because it contains structured data the CBDT already validated. It should populate: personal info, employer entries (salary break-up), house property, other sources income, Chapter VI-A deductions, bank accounts, TDS/TCS schedules, and tax payments. Currently none of this reaches the form.

#### Prefill JSON Structure (from ITD portal):

```json
{
  "personalInfo": { "pan", "name", "dob", "address", "aadhaar", ... },
  "filingStatus": { "returnFileSec", "optOutNewTaxRegime", ... },
  "ITR1_IncomeDeductions": {
    "GrossSalary", "Salary", "NetSalary", "DeductionUs16",
    "IncomeFromSal", "IncomeOthSrc", "GrossTotIncome",
    "UsrDeductUndChapVIA": { "Section80C", "Section80D", ... }
  },
  "TDSonSalaries": { "TDSonSalary": [{ "EmployerOrDeductorOrCollectDetl", "IncChrgSal", "TotalTDSSal" }] },
  "TaxPaid": { "TaxesPaid": { "AdvanceTax", "TDS", "TCS", "SelfAssessmentTax" } },
  "Refund": { "RefundDue", "BankAccountDtls" },
  "Verification": { "Declaration", "Capacity", "Place" }
}
```

### 5.2 Form 26AS (Annual Tax Statement)

**What it is:** Annual Tax Statement under section 203AA. Shows TDS/TCS credits, particulars of advance tax/self-assessment tax, refund details.

#### Current State: PARTIALLY WORKING (Path A only)

| Stage | Path A (Portal) | Path B (Upload) |
|---|---|---|
| Download / Upload | ✅ Downloaded as PDF | ✅ Accepted as upload |
| Storage | ❌ Temp file, deleted | ❌ Not stored |
| Parsing | ✅ `as26_extractor.py` → structured JSON | ❌ Tries `as26_converter.py`, falls back to mock |
| Reconciliation | ✅ Fed into reconciliation engine | ❌ `reconciliation()` returns mock empty |
| Form population | ✅ Via reconciled → `mapReconciledToFormData` | ❌ Mock data populated |

**26AS Structure (from parser):**
```
parts:
  I:   TDS on salary (192, 192A) — deductor name, TAN, section, amount, TDS
  IV:  TDS on property (194IA) — buyer, seller, transaction amount, TDS
  VI:  TCS (206C) — collector name, TAN, section, amount, TCS
  VII: Refunds — AY, refund amount, interest, date
```

### 5.3 AIS (Annual Information Statement)

**What it is:** Comprehensive statement of all financial transactions reported to the ITD under SFT. Includes salary, dividends, interest, securities transactions, mutual fund transactions, property transactions, etc.

#### Current State: PARTIALLY WORKING (Path A only)

| Stage | Path A (Portal) | Path B (Upload) |
|---|---|---|
| Download / Upload | ✅ Downloaded as PDF | ✅ Accepted as upload |
| Storage | ❌ Temp file, deleted | ❌ Not stored |
| Parsing | ✅ `extractor.py` (1246 lines, state machine) → structured JSON with income_heads, entries, details | ❌ Tries `ais_json_decryptor`, falls back to mock |
| Reconciliation | ✅ Fed into reconciliation engine | ❌ Mock |
| Form population | ✅ Via reconciled → `mapReconciledToFormData` | ❌ Mock data populated |

**AIS Structure (from parser):**
```json
{
  "metadata": { "pan", "name", "financial_year", "download_id" },
  "income_heads": {
    "Salary": { "entries": [{ "category", "information_code", "information_source", "amount", "institution_pan", "details": [...] }] },
    "Capital Gains": { "entries": [...] },
    "Income from Other Sources": { "entries": [...] },
    ...
  }
}
```

### 5.4 TIS (Taxpayer Information Summary)

**What it is:** Summary of all financial information (from AIS) with the taxpayer's accepted/denied status for each item. Shows "accepted by taxpayer" amounts.

#### Current State: PARTIALLY WORKING (Path A only)

| Stage | Path A (Portal) | Path B (Upload) |
|---|---|---|
| Download / Upload | ✅ Downloaded as PDF | ✅ Accepted as upload |
| Storage | ❌ Temp file, deleted | ❌ Not stored |
| Parsing | ✅ `tis_extractor.py` → structured JSON with accepted_by_taxpayer amounts | ❌ Mock data |
| Reconciliation | ✅ Fed into reconciliation engine (TIS accepted amounts take priority) | ❌ Mock |
| Form population | ✅ Via reconciled → `mapReconciledToFormData` | ❌ Mock data populated |

**TIS Structure (from parser):**
```json
{
  "metadata": { "pan", "name", "financial_year" },
  "income_heads": {
    "Salary": { "entries": [{ "category", "accepted_by_taxpayer", "details": [...] }] },
    ...
  }
}
```

### 5.5 Last Filed ITR JSON

**What it is:** The JSON of the last filed return — contains all fields submitted in the previous year's return.

#### Current State: DOWNLOADED BUT NEVER USED

| Stage | Status | Details |
|---|---|---|
| Download (portal) | ✅ Works | `downloader_filed_return.py` downloads the JSON |
| Storage | ❌ Not stored | Downloaded to disk, deleted after job |
| Parsing | ❌ Never parsed | No parser exists for the filed return JSON |
| Reconciliation | ❌ Not reconciled | Not fed into reconciliation engine |
| Form population | ❌ Never populated | No field from the last ITR reaches the form |

**Gap:** The last filed ITR JSON should pre-populate personal info (name, address, DOB, PAN, Aadhaar), employer details, bank accounts, and provide a baseline for comparison. Currently it's downloaded and discarded.

### 5.6 Form 16

**What it is:** Employer-issued certificate showing salary, TDS, and deductions.

#### Current State: MOCK ONLY

| Stage | Status | Details |
|---|---|---|
| Upload | ✅ Accepted | Frontend handles file upload |
| Storage | ❌ Not stored | In-memory only |
| Parsing | ❌ Mock | `/integration/form16/extract` returns hardcoded TATA employer data |
| Reconciliation | ❌ N/A | No reconciliation for Form 16 |
| Form population | ❌ Mock | `autopopulate_form16` merges 6 mock fields into formData |

---

## 6. Reconciliation Engine Deep Dive

**File:** `ais_extractor/reconciliation.py` — 1000+ lines

### 6.1 Architecture

The reconciliation engine is the strongest part of the import pipeline. It:

1. **Extracts entries** from each document into a common `Entry` dataclass
2. **Builds a match key** per entry: `{category}|id:{tan_or_pan}` or `{category}|name:{normalized_name}` or `{category}|transaction:{identity}` for capital gains
3. **Cross-matches** across documents using:
   - Exact key match
   - PAN-based cross-match (same PAN, different name spelling)
   - Name-based cross-match (normalized name fallback)
4. **Selects the final amount** using priority: TIS (accepted by taxpayer) > AIS > 26AS
5. **Detects discrepancies** by comparing every available source pair
6. **Extracts capital gain evidence** at transaction-detail level with FMV, STT, acquisition cost, etc.
7. **Produces category controls** from TIS accepted totals (system-deduplicated)

### 6.2 Category → Income Head Mapping

```python
CATEGORY_TO_INCOME_HEAD = {
    "salary":                           "Salary",
    "business receipts":                "Profits and Gains of Business or Profession",
    "dividend":                         "Income from Other Sources",
    "interest from savings bank":       "Income from Other Sources",
    "interest from deposit":            "Income from Other Sources",
    "sale of securities and units of mutual fund": "Capital Gains",
    "purchase of immovable property":   "Capital Gains",
    "refund":                           "Refund",
    ...
}
```

### 6.3 Section → Category Mapping

```python
SECTION_TO_CATEGORY = {
    "192": "salary", "192A": "salary",
    "193": "interest from deposit",
    "194": "dividend", "194K": "dividend",
    "194A": "interest from deposit",
    "194C": "business receipts", "194J": "business receipts",
    "194IA": "sale of land or building",
    "206C": "business receipts",
    ...
}
```

### 6.4 Tax Credit Selection

Tax credits (TDS/TCS) **always come from 26AS** — never from AIS or TIS:
- `credit_selected_source` = `"26AS"`
- `credit_selection_reason` = `"26AS_TAX_CREDIT"`
- Income/transaction values use TIS > AIS > 26AS fallback

### 6.5 What the Reconciliation Engine Does NOT Do

| Gap | Severity | Details |
|---|---|---|
| **No Prefill input** | 🔴 Critical | The engine only takes `ais_data`, `tis_data`, `as26_data`. No Prefill JSON input. |
| **No last ITR input** | 🔴 Critical | No filed-return input for comparison or pre-population. |
| **No Form 16 input** | 🟡 Major | Form 16 salary break-up isn't reconciled against AIS/26AS salary. |
| **No deduplication of same employer across 26AS + Prefill** | 🟡 Major | Prefill carries employer TDS details; 26AS also carries them. Without reconciliation, they may double-count. |

---

## 7. Form Auto-Population Deep Dive

### 7.1 Path A: Portal Automation → `mapReconciledToFormData.ts`

**File:** `frontend/src/utils/mapReconciledToFormData.ts` — 400+ lines

This is the production form-population mapper. It handles:

| Income Head | Form Fields Populated | Notes |
|---|---|---|
| Salary | `employerEntries[]`, `basic`, `tdsS192` | Only Section 192 TDS — business receipts excluded |
| Business/Profession | `bizTurnover`, `bpNetProfit`, `bizDeclared`, `bizPresumptive` | Detects 44AD vs 44ADA from TDS sections |
| Dividend | `dividendEntries[]`, `dividendShares` | Only `dividendShares`, never `dividends` (avoids double-count) |
| Interest | `interestEntries[]`, `bankInterestEntries[]`, `interestSB`, `interestFD` | Splits by sub-category (savings bank vs deposit) to avoid double-count |
| Capital Gains | `capitalGainTransactions[]` | Each AIS CG entry → one row with FMV, STT, acquisition cost |
| TDS | `tdsEntries[]`, `tdsS192`, `tds194A`, `tdsOther` | Section 192 → TDS1 (no TAN); others require TAN |
| TCS | `tcsEntries[]` | From 26AS Part VI |
| Metadata | `importedFromRecon` | Stores PAN, name, FY, total income, discrepancy count |

**Double-counting safeguards:**
- Interest split into `interestSB` + `interestFD` (not both set to total)
- Dividends only set `dividendShares` (not `dividends`)
- Empty arrays don't erase existing user-entered data (except `employerEntries` and `capitalGainTransactions`)

### 7.2 Path B: Individual Upload → `autoPopulateAll` (Mock)

**File:** `app/routers/integration.py` — `autopopulate_all()`

Returns hardcoded mock data:
```python
employer_entries.append({
    "employerName": "TATA CONSULTANCY SERVICES LTD",
    "employerTAN": "MUMT01234F",
    "basic": salary,
    ...
})
```

Every employer is TATA, every bank is HDFC, every company is Reliance — regardless of what was actually uploaded.

### 7.3 ImportConfirmationModal

**File:** `frontend/src/components/ImportConfirmationModal.tsx`

Shows:
- Summary counts (salary, business, dividend, interest, CG, TDS, TCS entries)
- Total income and total TDS
- Discrepancy count
- Unmatched entries (TIS-only, AIS-only, 26AS-only)
- Category control discrepancies

User can:
- Approve → `mapReconciledToFormData()` patches the form
- Cancel → discards import

---

## 8. Storage Audit

### 8.1 What's Stored

| Data | Storage | Location | Persisted? |
|---|---|---|---|
| Automation job metadata | DB | `automation_job` table | ✅ |
| Reconciled results | DB (JSON blob) | `automation_job.parsed_results` | ✅ |
| Downloaded file paths | DB (JSON blob) | `automation_job.files_downloaded` | ✅ (paths only, files deleted) |
| Artifact outcomes | DB (JSON blob) | `automation_job.artifact_outcomes` | ✅ (metadata only) |
| Raw 26AS PDF | Disk (temp) | `downloads/{job_id}/26as.pdf` | ❌ Deleted after job |
| Raw AIS PDF | Disk (temp) | `downloads/{job_id}/ais.pdf` | ❌ Deleted after job |
| Raw TIS PDF | Disk (temp) | `downloads/{job_id}/tis.pdf` | ❌ Deleted after job |
| Raw Prefill JSON | Disk (temp) | `downloads/{job_id}/prefill.json` | ❌ Deleted after job |
| Raw filed ITR JSON | Disk (temp) | `downloads/{job_id}/filed_return.json` | ❌ Deleted after job |
| Individual upload files | In-memory | Not stored anywhere | ❌ |

### 8.2 Missing Storage

| Need | Current State | Required |
|---|---|---|
| `ImportedDocument` table | ❌ Does not exist | Store raw imported documents per client + AY for re-parsing and audit trail |
| Parsed AIS/TIS/26AS JSON | ❌ Not stored separately | Store parsed JSON alongside the reconciled result for debugging |
| Prefill JSON persistence | ❌ Not stored | Store the Prefill JSON per client + AY — it's the canonical CBDT pre-fill |
| Filed return JSON persistence | ❌ Not stored | Store the last filed ITR per client + AY for year-over-year carry-forward |

---

## 9. Critical Gaps and Broken Parts

### 9.1 Gap Summary by Severity

| # | Gap | Severity | Path | Fix Effort |
|---|---|---|---|---|
| 1 | Prefill JSON never parsed into form data | 🔴 Critical | A | Medium — build a Prefill parser |
| 2 | Last filed ITR JSON never imported | 🔴 Critical | A | Medium — build a filed-return parser |
| 3 | Individual upload endpoints all return mock data | 🔴 Critical | B | High — wire real parsers to upload routes |
| 4 | Prefill JSON not fed into reconciliation | 🟡 Major | A | Medium — extend reconciliation engine |
| 5 | No document persistence (ImportedDocument table) | 🟡 Major | A+B | Medium — new DB model + migration |
| 6 | `prefill_service.py` is dead code with wrong AY | 🟡 Major | B | Low — delete or rewrite |
| 7 | `reconciliation.ts` API client is a stub | 🟡 Major | B | Low — wire to real reconciliation |
| 8 | No Form 16 PDF parser | 🟡 Major | B | High — build PDF text extraction |
| 9 | Assessment year hardcoded in downloaders | 🟡 Major | A | Low (after Year-Adaptive plan) |
| 10 | No reconciliation between Prefill and 26AS employer TDS | 🟡 Minor | A | Medium — extend reconciliation |
| 11 | Double-counting risk in `mapReconciledToFormData` | 🟡 Minor | A | Low — remove legacy scalar fields |
| 12 | `as26_converter.py` duplicate parser | 🟡 Minor | B | Low — consolidate to `as26_extractor.py` |

### 9.2 Gap Details

#### Gap 1: Prefill JSON Never Parsed (CRITICAL)

The Prefill JSON is the most valuable import document. It contains the CBDT's own pre-filled data including:
- Personal info (name, address, PAN, Aadhaar, DOB)
- Salary break-up (gross, basic, perquisites, profits, allowances, exempt, deductions)
- House property details
- Other sources income (interest, dividends, etc.)
- Chapter VI-A deductions (80C, 80D, 80E, etc.)
- Bank accounts (for refund)
- TDS on salaries (employer TAN, name, income, TDS)
- Tax payments (advance tax, self-assessment tax, TDS, TCS totals)
- Verification details

**Currently:** `downloader_prefill.py` downloads and validates it. `job_worker.py` never calls any parser. The JSON is deleted.

**Fix:** Create `app/engine/importers/prefill_parser.py` that extracts every field from the Prefill JSON and maps it to the flat formData contract. Call it in `job_worker.py` after the download step. Feed the extracted data into `mapReconciledToFormData` or a new `mapPrefillToFormData`.

#### Gap 2: Last Filed ITR JSON Never Imported (CRITICAL)

The last filed ITR JSON contains the taxpayer's previous-year return — useful for:
- Pre-populating personal info (name, address, DOB, father's name)
- Pre-populating employer details (if same employer)
- Pre-populating bank accounts
- Providing a baseline for year-over-year comparison
- Carrying forward capital gains losses, brought-forward losses

**Currently:** `downloader_filed_return.py` downloads it. `job_worker.py` never parses it. The JSON is deleted.

**Fix:** Create `app/engine/importers/filed_return_parser.py` that extracts carry-forward fields and maps them to the flat formData contract.

#### Gap 3: Individual Upload Endpoints All Mock (CRITICAL)

Every endpoint in `app/routers/integration.py` returns hardcoded mock data. The real parsers (`ais_extractor/extractor.py`, `ais_extractor/as26_extractor.py`, `ais_extractor/tis_extractor.py`) are only called by `job_worker.py`.

**Fix:** Rewrite `integration.py` to call the real parsers:
```python
@router.post("/integration/26as/import")
def import_26as(file: UploadFile = File(...), ...):
    content = file.file.read()
    # If PDF, write to temp and call _extract_26as
    # If text, write to temp and call _parse_26as_txt
    # If JSON, parse directly
    # Store in ImportedDocument table
    # Return parsed result
```

---

## 10. Year-Adaptive Architecture Impact on Imports

When the `YEAR_ADAPTIVE_ARCHITECTURE_PLAN.md` is implemented, it will affect the import pipeline:

### 10.1 What Changes

| Component | Current | After Year-Adaptive | Impact |
|---|---|---|---|
| `downloader_prefill.py` AY | Hardcoded `"2026-27"` | `profile.assessment_year` | Prefill download works for any supported AY |
| `downloader_prefill.py` AY text regex | `re.compile(r"(?:AY\s*)?2026\s*[-–_/]\s*27")` | Dynamic from profile | Validates any AY format |
| `prefill_service.py` `"ay": 2025` | Wrong year hardcoded | Deleted or uses profile | Fix dead code |
| Reconciliation category mapping | Hardcoded section→category | Profile-driven (if sections change) | Future-proof |
| Form field mapping | Hardcoded field names | Profile-driven schema fields | Future-proof |
| Schema validation | `ITR-1_2026_Main_V1.1 (2).json` | `schema_loader.load_schema(profile, form)` | Per-AY schema |

### 10.2 What the Year-Adaptive Plan Enables for Imports

| Capability | Current | After |
|---|---|---|
| Import for AY 2027-28 | ❌ Hardcoded rejection | ✅ Profile-driven download + parse + reconcile |
| Schema-specific field mapping | ❌ Hardcoded to 2026-27 schema | ✅ Profile carries schema version, mapper branches on it |
| Section code changes (new sections added by Finance Act) | ❌ Hardcoded `SECTION_TO_CATEGORY` | ✅ Profile carries section→category map per AY |
| Capital gains rules (112A grandfathering, FMV date) | ❌ Hardcoded `31 Jan 2018` | ✅ Profile carries `grandfathering_date` |

---

## 11. Implementation Plan: Fixing the Import Pipeline

### Phase 1: Fix Prefill JSON Import (Critical, 2-3 days)

#### Step 1.1: Create Prefill Parser

**New file:** `app/engine/importers/prefill_parser.py`

```python
def parse_prefill_json(prefill_data: dict, assessment_year: str) -> PrefillExtraction:
    """Parse the ITD Prefill JSON into flat formData fields."""
    # Extract: personalInfo, filingStatus, ITR1_IncomeDeductions,
    # TDSonSalaries, TaxPaid, Refund (bank accounts), Verification
    # Map to the flat formData contract used by the frontend
```

Extract these fields from the Prefill JSON:
- `personalInfo.AssesseeName` → `firstName`, `middleName`, `surnameOrOrgName`
- `personalInfo.PAN` → `pan`
- `personalInfo.Address` → `flatNo`, `premises`, `road`, `area`, `city`, `state`, `country`, `pincode`
- `personalInfo.DOB` → `dob`
- `personalInfo.AadhaarCardNo` → `aadhaar`
- `filingStatus.ReturnFileSec` → `filingSection`
- `filingStatus.OptOutNewTaxRegime` → `regime` / `taxRegime`
- `ITR1_IncomeDeductions.GrossSalary` → `grossSalary`
- `ITR1_IncomeDeductions.NetSalary` → `netSalary`
- `ITR1_IncomeDeductions.IncomeFromSal` → `basic`
- `ITR1_IncomeDeductions.UsrDeductUndChapVIA.Section80C` → `s80C`
- `TDSonSalaries.TDSonSalary[]` → `employerEntries[]` (with TAN, name, IncChrgSal, TotalTDSSal)
- `TaxPaid.TaxesPaid` → `advanceTaxEntries`, `selfAssessmentTaxEntries`, `tdsS192`
- `Refund.BankAccountDtls` → `bankAccountData.accounts[]`
- `Verification` → `verification`

#### Step 1.2: Wire Prefill Parser into Job Worker

**File:** `app/automation/job_worker.py`

After the Prefill download step, call the parser:
```python
path_prefill = files.get("prefill")
if path_prefill and os.path.exists(path_prefill):
    prefill_raw = json.loads(Path(path_prefill).read_text(encoding="utf-8-sig"))
    prefill_extracted = parse_prefill_json(prefill_raw, assessment_year)
    parsed["prefill"] = prefill_extracted
```

#### Step 1.3: Create `mapPrefillToFormData`

**New file:** `frontend/src/utils/mapPrefillToFormData.ts`

Maps the extracted Prefill fields to the flat formData contract, merging with reconciled data (Prefill provides employer salary break-up + deductions that AIS/26AS don't carry).

#### Step 1.4: Merge Prefill + Reconciled Data

In `handleAutomationComplete`, after `mapReconciledToFormData`, also run `mapPrefillToFormData` and merge:
```typescript
const reconciledUpdate = mapReconciledToFormData(reconciledImportData);
const prefillUpdate = mapPrefillToFormData(job.parsed_results.prefill);
// Prefill provides salary break-up + deductions; reconciled provides TDS/TCS
const mergedUpdate = { ...prefillUpdate, ...reconciledUpdate };
```

### Phase 2: Fix Last Filed ITR Import (Critical, 1-2 days)

#### Step 2.1: Create Filed Return Parser

**New file:** `app/engine/importers/filed_return_parser.py`

Extract carry-forward fields:
- Personal info (name, address, DOB, PAN, Aadhaar, father's name)
- Employer details (if same employer)
- Bank accounts
- Brought-forward losses (capital gains, house property, business)
- Section 80C cumulative deductions (for pension/PPF continuation)

#### Step 2.2: Wire into Job Worker

Add filed return parsing after reconciliation:
```python
path_filed = files.get("filed_return")
if path_filed and os.path.exists(path_filed):
    filed_raw = json.loads(Path(path_filed).read_text(encoding="utf-8-sig"))
    filed_extracted = parse_filed_return_json(filed_raw, assessment_year)
    parsed["filed_return"] = filed_extracted
```

### Phase 3: Fix Individual Upload Endpoints (Critical, 3-4 days)

#### Step 3.1: Create `ImportedDocument` DB Model

**File:** `app/db/models.py`

```python
class ImportedDocument(Base):
    __tablename__ = "imported_document"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    client_id: Mapped[int] = mapped_column(Integer, ForeignKey("client.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    assessment_year: Mapped[str] = mapped_column(String(10), nullable=False)
    document_type: Mapped[str] = mapped_column(String(20), nullable=False)  # prefill, ais, tis, 26as, form16, filed_return
    source: Mapped[str] = mapped_column(String(20), nullable=False)  # portal, upload
    raw_content: Mapped[str] = mapped_column(Text, nullable=False)  # raw file content (JSON or base64 PDF)
    parsed_content: Mapped[str] = mapped_column(Text, nullable=False, default="{}")  # parsed JSON
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    # Unique constraint: one document per type per client per AY
    __table_args__ = (UniqueConstraint("client_id", "assessment_year", "document_type", name="uq_imported_doc"),)
```

#### Step 3.2: Rewrite `integration.py` to Use Real Parsers

**File:** `app/routers/integration.py`

For each endpoint:
1. Read uploaded file
2. If PDF, write to temp file and call the real extractor (`ais_extractor/extractor.py` etc.)
3. If JSON, parse directly
4. Store raw + parsed content in `ImportedDocument` table
5. Return parsed content

```python
@router.post("/integration/26as/import")
def import_26as(file: UploadFile = File(...), clientId: Optional[str] = Form(None), ...):
    content = file.file.read()
    if content.startswith(b"%PDF"):
        # PDF — write to temp and extract
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(content)
            parsed = _extract_26as(tmp.name)
            os.unlink(tmp.name)
    elif content.startswith(b"{"):
        # JSON — already structured
        parsed = json.loads(content)
    else:
        # Text — try the text parser
        parsed = parse_26as_txt_text(content.decode("utf-8"))
    # Store in DB
    _store_imported_document(client_id, assessment_year, "26as", "upload", content, parsed)
    return parsed
```

#### Step 3.3: Wire Real Reconciliation into Upload Path

Replace the mock `reconciliation()` endpoint with a call to `ais_extractor.reconciliation.reconcile()`:
```python
@router.post("/integration/reconciliation")
def reconciliation(payload: dict, ...):
    ais = payload.get("aisData", {})
    tis = payload.get("tisData", {})
    as26 = payload.get("data26AS", {})
    result = reconcile(ais, tis, as26)
    return result
```

#### Step 3.4: Delete Dead Code

- Delete `app/services/prefill_service.py` (dead code, wrong AY)
- Delete `frontend/src/api/reconciliation.ts` stub (or wire it to the real endpoint)
- Remove mock data from every `integration.py` endpoint

### Phase 4: Extend Reconciliation Engine (Medium, 2-3 days)

#### Step 4.1: Add Prefill Input to Reconciliation

Extend `reconcile()` to accept a `prefill_data` parameter:
```python
def reconcile(ais_data, tis_data, as26_data, prefill_data=None):
    # Extract Prefill employer TDS entries
    # Cross-match against 26AS employer TDS entries
    # Use Prefill salary break-up (basic, HRA, perquisites) when 26AS only has the total
```

#### Step 4.2: Add Filed Return Input for Comparison

Extend `reconcile()` to accept a `filed_return_data` parameter for year-over-year comparison:
```python
def reconcile(..., filed_return_data=None):
    # Compare current-year salary against previous-year salary
    # Flag if employer changed
    # Flag if bank accounts changed
```

### Phase 5: Document Persistence (Medium, 1-2 days)

#### Step 5.1: Persist Raw + Parsed Documents

Store every imported document in the `ImportedDocument` table:
- Raw content (JSON text or base64 PDF)
- Parsed content (structured JSON)
- Document type, source, client, AY
- Timestamp

#### Step 5.2: Add Re-parse / Re-reconcile Endpoint

```python
@router.post("/clients/{client_id}/itr/{year}/re-reconcile")
def re_reconcile(client_id, year, ...):
    # Load all ImportedDocuments for this client + AY
    # Re-run reconciliation
    # Return new reconciled result
```

#### Step 5.3: Add Import History View

Frontend: show imported documents per client + AY with timestamps, source (portal vs upload), and re-parse/re-reconcile buttons.

### Phase 6: Year-Adaptive Integration (After Year-Adaptive Plan, 1-2 days)

#### Step 6.1: Remove Hardcoded AY from Downloaders

Replace `AY = "2026-27"` with `profile = get_profile(assessment_year)` in:
- `downloader_prefill.py`
- `downloader_ais_tis.py`
- `downloader_26as.py`
- `downloader_filed_return.py`

#### Step 6.2: Profile-Driven Section→Category Mapping

Move `SECTION_TO_CATEGORY` and `CATEGORY_TO_INCOME_HEAD` from `reconciliation.py` into the `TaxYearProfile` so they can change per AY when the Finance Act adds new sections.

#### Step 6.3: Profile-Driven Field Mapping

`mapReconciledToFormData` should use the tax-year config to know which form fields exist for the current AY (field names may change when the CBDT schema changes).

---

## Implementation Priority

| Priority | Phase | What | Why |
|---|---|---|---|
| 🔴 P0 | Phase 1 | Fix Prefill JSON import | The single most valuable document is completely unused |
| 🔴 P0 | Phase 2 | Fix last filed ITR import | Carry-forward data is lost every year |
| 🔴 P0 | Phase 3.1-3.2 | Fix individual upload endpoints | Users can't upload documents — everything is mock |
| 🟡 P1 | Phase 3.3 | Wire real reconciliation to uploads | Uploaded documents can't be reconciled |
| 🟡 P1 | Phase 5 | Document persistence | No audit trail, no re-parse capability |
| 🟡 P1 | Phase 4 | Extend reconciliation engine | Prefill + filed return should be reconciled |
| 🟢 P2 | Phase 6 | Year-adaptive integration | After the Year-Adaptive plan is implemented |

---

## Appendix A: File Inventory

### Backend Import Files

| File | Purpose | Status |
|---|---|---|
| `app/routers/integration.py` | Individual upload endpoints | ❌ All mock |
| `app/services/prefill_service.py` | Prefill mapping service | ❌ Dead code, wrong AY |
| `app/automation/job_worker.py` | Portal automation worker | ✅ Working (but doesn't parse Prefill/filed return) |
| `app/automation/downloader_prefill.py` | Prefill JSON download | ✅ Working |
| `app/automation/downloader_ais_tis.py` | AIS + TIS PDF download | ✅ Working |
| `app/automation/downloader_26as.py` | 26AS PDF download | ✅ Working |
| `app/automation/downloader_filed_return.py` | Filed return JSON download | ✅ Working |
| `app/automation/ais_converter.py` | AIS converter | ⚠️ Unknown if used |
| `app/automation/ais_json_decryptor.py` | AIS JSON decryptor | ⚠️ Used by integration.py, falls back to mock |
| `app/automation/as26_converter.py` | 26AS text parser (older) | ⚠️ Used by integration.py, falls back to mock |
| `ais_extractor/extractor.py` | AIS PDF extractor (state machine) | ✅ Production-quality |
| `ais_extractor/as26_extractor.py` | 26AS PDF extractor | ✅ Production-quality |
| `ais_extractor/tis_extractor.py` | TIS PDF extractor | ✅ Production-quality |
| `ais_extractor/reconciliation.py` | Reconciliation engine | ✅ Production-quality |
| `app/eri/prefill.py` | ERI prefill helper | ⚠️ Unknown usage |

### Frontend Import Files

| File | Purpose | Status |
|---|---|---|
| `frontend/src/api/integration.ts` | Individual upload API client | ✅ Calls backend (backend is mock) |
| `frontend/src/api/reconciliation.ts` | Reconciliation API client | ❌ Stub (`stub('/api/reconciliation', {})`) |
| `frontend/src/api/itrAutomation.ts` | Portal automation API client | ✅ Working |
| `frontend/src/types/import.types.ts` | Import TypeScript types | ✅ Complete |
| `frontend/src/utils/mapReconciledToFormData.ts` | Reconciled → formData mapper | ✅ Production-quality |
| `frontend/src/components/ImportConfirmationModal.tsx` | Import confirmation UI | ✅ Working |
| `frontend/src/components/EmployerReconciliationModal.tsx` | Employer reconciliation UI | ✅ Working |
| `frontend/src/pages/ReconciliationPage.tsx` | Reconciliation page | ⚠️ Unknown if wired |

---

## Conclusion

The import pipeline has a solid foundation — the portal automation path (Path A) with the reconciliation engine and form mapper is genuinely production-quality. But it has two critical gaps: the Prefill JSON and last filed ITR JSON are downloaded but never parsed.

The individual upload path (Path B) is entirely mock data and needs a complete rewrite to use the real parsers.

The recommended fix order:
1. **Phase 1-2:** Build Prefill + filed return parsers (highest ROI — unlocks the most valuable data)
2. **Phase 3:** Rewrite individual upload endpoints to use real parsers + add document persistence
3. **Phase 4-5:** Extend reconciliation + add persistence
4. **Phase 6:** Year-adaptive integration (after the Year-Adaptive plan)
