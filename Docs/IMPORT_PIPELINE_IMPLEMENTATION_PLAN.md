# Import Pipeline Implementation Plan

**Document created:** 2026-08-15
**Last updated:** 2026-08-15 (after Phase 3 completion)
**Status:** Phase 3 complete, Phase 4 next

This document tracks the complete implementation plan for fixing the
import pipeline as identified in `IMPORT_FLOW_AUDIT_REPORT.md`.  It is
updated after every commit and before moving to the next phase.

---

## Table of Contents

1. [Phase 1: Form-agnostic Prefill JSON Parser ✅ COMPLETE](#phase-1-form-agnostic-prefill-json-parser--complete)
2. [Phase 2: Last Filed ITR JSON Parser ✅ COMPLETE](#phase-2-last-filed-itr-json-parser--complete)
3. [Phase 3: Fix Individual Upload Endpoints + Document Persistence ✅ COMPLETE](#phase-3-fix-individual-upload-endpoints--document-persistence--complete)
4. [Phase 4: Extend Reconciliation Engine](#phase-4-extend-reconciliation-engine)
5. [Phase 5: Document Persistence + Re-parse/Re-reconcile](#phase-5-document-persistence--re-parsere-reconcile)
6. [Phase 6: Year-Adaptive Integration](#phase-6-year-adaptive-integration)
7. [Commit History](#commit-history)
8. [Testing Checklist](#testing-checklist)

---

## Phase 1: Form-agnostic Prefill JSON Parser ✅ COMPLETE

**Started:** 2026-08-15
**Completed:** 2026-08-15
**Commits:** 4 (all pushed to `origin/main`)

### Goal

The Prefill JSON from ITD is the single most valuable import document —
it carries the CBDT's own pre-filled data including salary break-up,
Chapter VI-A deductions, bank accounts, employer TDS, personal info,
and carry-forward losses.  Previously it was downloaded by the portal
automation but never parsed — it sat on disk and was deleted.

### What was built

#### Backend — `app/engine/importers/prefill_parser.py` (1700+ lines)

A form-agnostic parser that extracts **every section** from the real
ITD Prefill JSON payload.  The parser does NOT know which ITR form the
taxpayer will eventually file — it pulls all fields and lets the
form-specific mappers in the frontend pick what they need.

**Sections extracted:**

| Section | Source key | What it extracts |
|---|---|---|
| Personal info | `personalInfo` | PAN, Aadhaar (base64-decoded), name (3-part), DOB, father's name, status, address (residence/road/area/city/state/country/PIN), mobile, email, secondary mobile/email, employer category, residential status, Portuguese 5A flag |
| Org firm info | `personalInfo.orgFirmInfo` | Assessee name, date of formation, status/company type |
| Filing status | `filingStatus` (top-level) | Return section, residential status, 7th proviso, clause iv7 details, Form 10IF ack, receipt no, original filing date |
| Filing status ext | `filingStatus` | 7th-proviso clause details, Form 10IF ack, original-return filing date |
| Employer entries | `salaries.salary[]` + `lastFiledITR.natOfEmployment` + enriched from TDS-other | Employer name, TAN, gross salary, basic, perquisites, profits-in-lieu, nature of employment, address |
| Salary insights | `insights.cumulativeSalary` | Cumulative salary, perquisites, profits-in-lieu, update timestamp |
| House property | `lastFiledITR.scheduleHP.propertyDetails` + `insights.scheduleHP` | Address, city, state, PIN, country, if-let-out, type, gross rent, co-owners, tenants |
| Other sources income | `insights.scheduleOS` + `form26as.scheduleOS` + `form24q` | Dividend gross, dividend-oth-22e, SB interest, FD interest, others interest, rent from machinery, lottery income, other income details (nature + amount) |
| Bank accounts | `bankAccountDtls` (top-level) + `lastFiledITR.bankAccountDtls` | Bank name, account number, IFSC, account type, refund flag — **deduplicated by stripping leading zeros**, only ONE marked for refund |
| TDS on salary | `tdsOnSalaries.tdsOnSalary[]` | Deductor name, TAN, section 192, income, TDS, claimed |
| TDS other than salary | `form26as.tdsOnOthThanSals.tdSonOthThanSal[]` | Deductor name, TAN, section code, gross amount, TDS deducted, TDS claimed, head of income, deducted year, brought-forward TDS |
| TCS entries | `lastFiledITR.scheduleTCS.tcs[]` | Collector name, TAN, PAN, section, gross, TCS collected, TCS claimed, head of income, collected year |
| Deductions (Chapter VI-A) | `insights.UsrDeductUndChapVIAType` + `form24q.usrDeductUndChapVIAType` + `lastFiledITR.usrDeductUndChapVIAType` + `scheduleDeductions.usrDeductUndChapVIA` | All section 80* deductions (80C, 80D, 80CCD, 80TTA, 80TTB, etc.) — case-insensitive key matching, merged from all sources |
| 80D details | `lastFiledITR.schedule80D` | Senior citizen flags (self/family, parent) |
| Carry-forward losses | `scheduleCFL.CarryFwdLossDetail` | Business loss, HP loss, LTCG loss, STCG loss, speculative, specified, insurance, race-horse |
| Verification | `verification` | Assessee ver name, PAN, father name, capacity, place |
| Capital gains property | `insights.capitalGains.propertyDetails` | Address, buyers (name, PAN, Aadhaar, amount paid), stamp duty, transaction amount |
| Other income CPC | `incDeductionsOthIncCPC` | Assessment year, nature, amount |
| Presumptive income | `form26as.persumptiveInc44ADA` + `lastFiledITR.natOfBus44ADA` | 44ADA gross receipt, business nature codes |
| Depreciation | `lastFiledITR.scheduleDOA` + `lastFiledITR.scheduleDPM` | Recursive walker for all asset classes (ships, intangible, land, building, furniture, plant & machinery) with WDV first day |
| AMT credits | `lastFiledITR.scheduleAMTC.scheduleAMTCDtls` | Assessment year, gross, setoff earlier AY, forwarded |
| ESOP deferred tax | `ScheduleESOP` | All year sub-objects (2122, 2223, 2324, 2425, 2526) with assessment year + tax deferred BF |
| Audit info | `lastFiledITR.AuditInfo` | Income declared u/s, 44AA flag, audit report details |
| Form 10IF | `form10IF` + `Form10IFA` | New tax regime, ack no, filed 10IFA, return filing 115BAE |
| LastFiledITR flags | `lastFiledITR` | Income from bus/prof, 115H, foreign exchange, director, partner, unlisted shares, asset-outside-India, total months |
| LastFiledITR filing status | `lastFiledITR.filingStatus` | Residential status, FII/FPI, 115BAE yes/no, 24/25 |
| Form 3CD | `form3CD` | Raw pass-through for audit particulars |
| Schedule 5A2014 | `lastFiledITR.schedule5A2014` | Portuguese civil code |
| Schedule SPI | `lastFiledITR.scheduleSPI` | Specified persons |
| Schedule UD | `lastFiledITR.scheduleUD` | Unabsorbed depreciation |
| Manufacturing account | `lastFiledITR.manufacturingAccount` | Opening inventory |
| Schedule 80G | `Schedule80G` | Donations |
| Schedule EI | `ScheduleEI` | Exempt income |
| Schedule AL | `scheduleAL` | Assets and liabilities |

**Key design decisions:**

1. **Form-agnostic** — the parser extracts everything regardless of
   which ITR form the taxpayer will file.  The frontend mappers pick
   what they need.
2. **Three wrapper shapes** — handles flat root, `data`-wrapped, and
   `prefillData`-wrapped payloads.
3. **Case-insensitive key matching** — the real ITD prefill uses
   inconsistent casing (`Section80TTB` vs `section80TTA`); the parser
   normalizes everything to lowercase.
4. **Bank account deduplication** — the ITD emits the same account
   twice (real number + zero-padded); the parser strips leading zeros
   for comparison and keeps only the first occurrence.
5. **Single refund account** — only ONE bank account is marked for
   refund (the BankAccountManager requires exactly one).
6. **Employer enrichment** — when `salaries` is null (as in the real
   prefill), the parser fills stub employer entries from the TDS-other
   deductor names and deduplicates by TAN.

#### Frontend — `frontend/src/utils/mapPrefillToFormData.ts` (437 lines)

Converts the `PrefillExtraction` dict to the flat `formData` shape used
by `ITRComputationPage`.  Maps:
- Personal info → `firstName`, `middleName`, `surnameOrOrgName`, `pan`,
  `aadhaar`, `dob`, `fatherName`, `status`, `employerCategory`
- Address → `flatNo`, `premises`, `road`, `area`, `city`, `state`,
  `country`, `pincode`, `zipCode`
- Contact → `mobileCountryCode`, `mobile`, `secondaryMobile`,
  `secondaryMobileCountryCode`, `email`, `secondaryEmail`
- Filing status → `filingSection`, `residentialStatus`
- Employer entries → `employerEntries[]` (with stable IDs)
- Bank accounts → `bankAccountData.accounts[]` (with stable IDs,
  normalized account types SB/CA/CC/OD/NRO/OTH)
- TDS salary → `tdsS192`
- TDS other → `tds194A`
- Deductions → `s80C`, `s80D`, `s80E`, `s80G`, `s80CCD1B`, `s80TTA`,
  `s80TTB`, `s80CCH`
- Other sources → `interestSB`, `interestFD`, `dividendShares`
- House property → `propertyDetails[]`
- Verification → `assesseeVerName`, `assesseeVerPAN`, `fatherName`,
  `capacity`, `place`
- Metadata → `importedFromPrefill` (PAN, AY, timestamp, counts)

#### Job worker — `app/automation/job_worker.py`

- Imported `parse_prefill_file` and `prefill_extraction_to_dict`
- After downloading the Prefill JSON (Step 4.6), calls the parser and
  attaches the extraction to the reconciled output under the `prefill`
  key
- Logs extraction counts (employers, banks, TDS, deductions) for
  verification
- Logs the raw top-level keys for diagnostic purposes

#### ITRComputationPage — `frontend/src/pages/ITRComputationPage.tsx`

- Imported `mapPrefillToFormData`
- `handleConfirmImport` now merges Prefill data **first** (personal
  info, deductions, bank accounts, salary break-up), then the
  reconciled update overrides income/TDS fields (reconciled is more
  authoritative for the current AY)
- Added a secondary toast showing what Prefill-specific data was
  imported (personal info, employers, bank accounts, deductions,
  TDS-salary)

### Commits

| # | Commit | Description |
|---|---|---|
| 1 | `2b5f720` | feat(import): Phase 1 — form-agnostic Prefill JSON parser + mapper |
| 2 | `eabeaec` | fix(prefill-mapper): add id to bank account entries |
| 3 | `fb4ca8f` | fix(prefill-parser): match real ITD prefill JSON structure |
| 4 | `bcc0054` | feat(prefill-parser): extract ALL sections from ITD prefill + dedupe banks |

### Verification

Tested against the real ITD Prefill JSON for taxpayer SUNIT GOYANKA
(PAN ACUPG3482G).  All sections extracted correctly:
- ✅ 1 bank account (deduplicated from 2, 1 refund account)
- ✅ 2 employer entries (enriched from TDS deductor names)
- ✅ 2 TDS-other entries (Anand Agrawal + SBI, with TAN, section, gross, TDS, claimed)
- ✅ Deductions: 80TTA=6105, 80TTB=50000
- ✅ Other sources: dividend=215, SB=6105, FD=325458
- ✅ 11 depreciation blocks, 1 AMT credit, 5 ESOP entries
- ✅ Audit info, Form 10IF, all lastFiledITR flags
- ✅ Personal info, filing status, verification

### What you can test

1. Run a portal automation import (Import from Portal button)
2. Confirm the import
3. Check the Personal Info tab — should pre-populate with name,
   address, mobile, email, Aadhaar, DOB, father's name from the Prefill
4. Check the Bank Accounts section — should show 1 deduplicated account
   with the refund checkbox set
5. Check the backend log — should say `Prefill extraction OK —
   employers=2, banks=1, tds_sal=0, tds_oth=2, deductions=56105`
6. Look for the secondary toast — should say "Prefill: personal info,
   2 employer(s), 1 bank account(s), deductions ₹56,105, 2 TDS-salary"

---

## Phase 2: Last Filed ITR JSON Parser ✅ COMPLETE

**Started:** 2026-08-15
**Completed:** 2026-08-15
**Commits:** 1 (pending push)

### Goal

The last filed ITR JSON contains the taxpayer's previous-year return —
useful for:
- Pre-populating personal info (name, address, DOB, father's name)
- Pre-populating employer details (if same employer)
- Pre-populating bank accounts
- Providing a baseline for year-over-year comparison
- Carrying forward capital gains losses, brought-forward losses

Previously `downloader_filed_return.py` downloaded it, but
`job_worker.py` never parsed it.  The JSON was deleted after the job.

### Revised-return flagging

The download logic was extended to flag whether the current-AY return
is already filed (and whether it was a revised return).  This prevents
accidental overwriting of a filed return:

- If the current-AY return is **already filed** (original or revised),
  the advisory sets `current_ay_already_filed=True` and
  `requires_user_confirmation_for_revision=True`.  The user must
  explicitly confirm the revised-return flow before the filed-ITR data
  is populated.
- If the last filed ITR was a **revised return** (section 139(5)),
  the advisory sets `current_ay_is_revised=True` and shows a prominent
  warning: "The last filed ITR was a revised return."
- If the last filed ITR is for a **normal (prior) AY**, no issues —
  proceed normally.

### What was built

#### Backend — `app/engine/importers/filed_return_parser.py` (560+ lines)

A form-agnostic parser that extracts **every section** from the CBDT's
official ITR JSON payload.  The parser auto-detects the ITR form
(ITR1, ITR2, ITR3, ITR4, ITR5, ITR6, ITR7) and extracts:

| Section | Source key | What it extracts |
|---|---|---|
| Personal info | `PartA_GEN1.PersonalInfo` | PAN, Aadhaar, name (3-part), DOB, status, address (residence/road/area/city/state/country/PIN), mobile, email, alternate address |
| Filing status | `PartA_GEN1.FilingStatus` | Return section, residential status, 7th proviso, opt-out new regime, due date, director/partner/unlisted shares flags |
| Employer entries | `ScheduleS.Salaries[]` | Employer name, nature of employment, TAN, gross salary, basic, perquisites, profits-in-lieu, address |
| Bank accounts | `PartB_TTI.Refund.BankAccountDtls.AddtnlBankDetails[]` | Bank name, account number, IFSC, account type, refund flag — deduplicated, only ONE marked for refund |
| TDS on salary | `ScheduleTDS1.TDSonSalariesDtls[]` | Deductor name, TAN, section 192, income, TDS, claimed |
| TDS other | `ScheduleTDS2.TDSOthThanSalaryDtls[]` | Deductor name, TAN, section, gross, TDS deducted, TDS claimed, head of income, brought-forward TDS |
| Deductions | `ScheduleVIA.UsrDeductUndChapVIA` | All section 80* deductions (80C, 80D, 80CCD, 80TTA, 80TTB, etc.) |
| Other sources | `ScheduleOS` | Dividend, SB/FD interest, others, other income details |
| Carry-forward losses | `ScheduleCFL.CarryFwdLossDetail` | Business loss, HP loss, LTCG loss, STCG loss, insurance, specified, race-horse |
| Verification | `Verification` | Name, PAN, father name, capacity, place, date |
| Capital gains | `ScheduleCGFor23` | Raw dict for frontend mapper (ITR-2/3) |
| Schedule CYLA/BFLA/SI/IT/AMTC | raw dicts | Pass-through for form-specific mappers |
| Tax totals | `PartB_TTI` | Total tax payments, bal tax payable, refund due, asset-outside-India flag |

**Key design decisions:**

1. **Form-agnostic** — auto-detects the ITR form and extracts all
   fields regardless of form.
2. **PascalCase keys** — the filed-return JSON uses PascalCase (unlike
   the prefill's camelCase); the parser handles both via case-insensitive
   matching.
3. **Bank account deduplication** — same as the prefill parser.
4. **Single refund account** — same as the prefill parser.

#### Classifier — `app/automation/filing_mode_classifier.py`

Extended `FilingModeClassification` with three new fields:
- `current_ay_already_filed: bool`
- `current_ay_is_revised: bool`
- `current_ay_filing_section: Optional[str]`

The classifier detects revised returns by checking the effective
current-AY return's `filing_section` for "139(5)" and `filing_type`
for "revised".

#### Advisory — `app/automation/filing_advisory.py`

Extended `FilingAdvisory` with:
- `current_ay_already_filed: bool`
- `current_ay_is_revised: bool`
- `current_ay_filing_section: Optional[str]`
- `download_is_current_ay: bool`
- `requires_user_confirmation_for_revision: bool`

The advisory message is customized for revised returns: "ITR for AY
2026-27 is already filed as a REVISED return (section 139(5)). The last
filed ITR was a revised return."

The download logic was made conservative: the current-AY return is
**never** auto-downloaded for revision.  The advisory always surfaces
`requires_user_confirmation_for_revision=True` when the current-AY
return exists, and the user must explicitly confirm the revised-return
flow before the data is populated.

#### Job worker — `app/automation/job_worker.py`

- Imported `parse_filed_return_file` and `filed_return_extraction_to_dict`
- After downloading the filed-return JSON (Step 4.6.1), calls the parser
  and attaches the extraction to the reconciled output under the
  `filed_return` key
- Logs extraction counts (form, employers, banks, TDS, losses) for
  verification
- Surfaces the filing advisory and classification in the reconciled
  output so the frontend can show the flags

#### Frontend — `frontend/src/utils/mapFiledReturnToFormData.ts` (280 lines)

Converts the `FiledReturnExtraction` dict to the flat `formData` shape.
Maps:
- Personal info → `firstName`, `middleName`, `surnameOrOrgName`, `pan`,
  `aadhaar`, `dob`, `status`
- Address → `flatNo`, `premises`, `road`, `area`, `city`, `state`,
  `country`, `pincode`
- Contact → `mobileCountryCode`, `mobile`, `email`
- Filing status → `filingSection`, `residentialStatus`
- Employer entries → `employerEntries[]` (with stable IDs)
- Bank accounts → `bankAccountData.accounts[]` (with stable IDs,
  normalized account types)
- Carry-forward losses → `carryForwardLosses[]` + flat `bfLossHP`,
  `bfLossLTCG`, `bfLossSTCG`, `bfLossBusiness` fields
- Verification → `assesseeVerName`, `assesseeVerPAN`, `fatherName`,
  `capacity`, `place`
- Metadata → `importedFromFiledReturn`

#### ITRComputationPage — `frontend/src/pages/ITRComputationPage.tsx`

- Imported `mapFiledReturnToFormData`
- `handleConfirmImport` now merges filed-return data **first** (lowest
  precedence: filed-return < Prefill < reconciled), then Prefill, then
  reconciled
- Added a tertiary toast showing filed-return imports (brought-forward
  losses, bank accounts, employer details)
- Added a prominent `toast.error` when the current-AY return is already
  filed (with a different message for revised returns)
- The warning banner now shows the filing-advisory message when the
  current-AY return is already filed

### Verification

Tested against the real filed-return JSON for taxpayer SUNIT GOYANKA
(PAN ACUPG3482G, ITR-2, AY 2026-27).  All sections extracted correctly:
- ✅ Form: ITR-2, AY: 2026, Schema: Ver1.0
- ✅ Personal info (name, PAN, Aadhaar, DOB, address, mobile, email)
- ✅ 2 employer entries (ADV. RAVINDRA K. AGRAWAL, ADV. RAHUL R. AGRAWAL)
- ✅ 1 bank account (SBI, deduplicated, 1 refund)
- ✅ 2 TDS-other entries (with TAN, section, gross, TDS, claimed)
- ✅ Capital gains schedule keys
- ✅ Schedule CYLA, BFLA, AMTC, SI keys
- ✅ Verification (name, PAN, father, capacity, place, date)
- ✅ Refund due: 31890, Asset out India: NO

### Commits

| # | Commit | Description |
|---|---|---|
| 1 | (pending) | feat(import): Phase 2 — filed-return parser + revised-return flagging |

### What you can test

1. Run a portal automation import
2. Check the backend log — should say `Filed-return extraction OK —
   form=ITR2, employers=2, banks=1, tds_sal=0, tds_oth=2, losses=0`
3. Confirm the import — brought-forward losses should appear in the
   capital gains / house property tabs (if any)
4. Personal info should be pre-populated (if not already from Prefill)
5. If the current-AY return is already filed, a prominent error toast
   should appear warning the user to confirm the revised-return flow
6. The warning banner should show the advisory message

---

## Phase 3: Fix Individual Upload Endpoints + Document Persistence ✅ COMPLETE

**Started:** 2026-08-15
**Completed:** 2026-08-15
**Commits:** 1 (pending push)

### Goal

Every endpoint in `app/routers/integration.py` returned hardcoded mock
data.  The real parsers (`ais_extractor/extractor.py`,
`ais_extractor/as26_extractor.py`, `ais_extractor/tis_extractor.py`)
were only called by `job_worker.py`.  Individual uploads of AIS/TIS/
26AS/Prefill/Form 16 all got mock data.

This phase rewired the individual upload endpoints to use the real
parsers and added a new `ImportedDocument` DB table for persistence.

### What was built

#### New DB model — `app/db/models.py`

Added the `ImportedDocument` table:

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | Auto-increment |
| `client_id` | Integer FK → `client.id` | ON DELETE CASCADE, indexed |
| `user_id` | Integer FK → `user.id` | ON DELETE CASCADE, indexed |
| `assessment_year` | String(10) | e.g. "2026-27" |
| `document_type` | String(20) | prefill, ais, tis, 26as, form16, filed_return |
| `source` | String(20) | portal or upload |
| `raw_content` | Text | Raw file content (JSON text or base64 PDF) |
| `parsed_content` | Text | Parsed JSON (default "{}") |
| `created_at` | DateTime | Default UTC now |
| `updated_at` | DateTime | Default UTC now, onupdate now |
| | | Unique constraint: (client_id, assessment_year, document_type) |

The table is auto-created by `create_tables()` at startup (uses
`CREATE TABLE IF NOT EXISTS` semantics).

#### Rewritten `app/routers/integration.py`

Replaced all mock endpoints with real-parser implementations:

| Endpoint | Before | After |
|---|---|---|
| `POST /integration/form16/extract` | Mock TCS data | Returns 501 (no parser yet) |
| `POST /api/v1/imports/ais` | Mock AIS data | Calls `extract_ais` (PDF) or `decrypt_ais_json` (encrypted JSON) or `json.loads` (plain JSON); persists to ImportedDocument |
| `POST /integration/ais-json/import` | Mock AIS data | Same as above (alias) |
| `POST /integration/tis/import` | Mock TIS data | Calls `extract_tis` (PDF) or `json.loads` (JSON); persists to ImportedDocument |
| `POST /integration/26as/import` | Mock 26AS data (with real TXT parser) | Calls `extract_26as` (PDF) or `parse_26as_txt` (TXT) or `json.loads` (JSON); persists to ImportedDocument |
| `POST /integration/prefill/import` | Mock "imported" message | Calls `parse_prefill_json`; persists to ImportedDocument |
| `POST /integration/autopopulate/form16` | Merge mock | Merge whatever the frontend supplies (no parser yet) |
| `POST /integration/autopopulate/ais` | No merge | Merge AIS summary (interest/dividend) into formData |
| `POST /prefill/autoPopulateAll` | Mock employer "TATA" | Merge 26AS + AIS + TIS into formData (no hardcoded names) |
| `POST /integration/reconciliation` | `{"hasDiscrepancies": False}` | Calls real `reconcile()` from `ais_extractor.reconciliation` |
| `POST /prefill/autopopulate` | No merge | Calls `parse_prefill_json`, merges personal info + banks + deductions |

**Key design decisions:**

1. **Real parsers only** — no mock data anywhere.  If a parser is
   unavailable, the endpoint returns a 501 with a clear message.
2. **Persistence** — every upload endpoint persists the raw + parsed
   content to the `ImportedDocument` table via `_upsert_imported_document`.
3. **Client resolution** — `_resolve_client_id` accepts either a
   numeric id or a public_id (UUID) and verifies ownership.
4. **Three upload formats** — AIS/TIS/26AS endpoints handle PDF, TXT,
   and JSON uploads.
5. **Encrypted AIS JSON** — the AIS endpoint still decrypts encrypted
   JSON from the ITD portal using the supplied PAN + DOB.

#### Deleted dead code

- `app/services/prefill_service.py` — dead code (wrong schema shape,
  no imports anywhere).  Deleted.

#### Frontend — `frontend/src/api/reconciliation.ts`

Replaced the stub (`stub('/api/reconciliation', {})`) with a real
client that calls `POST /integration/reconciliation` with the AIS,
TIS, and 26AS data and returns a typed `ReconciliationResult`.

### Commits

| # | Commit | Description |
|---|---|---|
| 1 | (pending) | feat(import): Phase 3 — real parsers + document persistence |

### What you can test

1. Upload an AIS PDF via the individual upload UI — should call the
   real `extract_ais` parser and return real AIS data (not mock).
2. Upload a 26AS text file — should call the real `parse_26as_txt`.
3. Upload a Prefill JSON — should call `parse_prefill_json` and return
   the form-agnostic extraction.
4. Upload an AIS PDF with a `clientId` — check the `imported_document`
   table has a new row with `document_type='ais'`.
5. Trigger reconciliation from the UI — should return real
   discrepancies (not `{"hasDiscrepancies": False}`).
6. Upload a Form 16 PDF — should return a 501 with "Form 16 auto-
   extraction is not yet available" (not mock TCS data).

---

## Phase 4: Extend Reconciliation Engine

**Status:** Not started
**Estimated effort:** 2-3 days

### Goal

The reconciliation engine (`ais_extractor/reconciliation.py`) currently
only accepts AIS, TIS, and 26AS data.  It should also accept Prefill
and last-filed-ITR data for cross-document reconciliation.

### Steps

#### Step 4.1: Add Prefill input to reconciliation

Extend `reconcile()` to accept a `prefill_data` parameter:
```python
def reconcile(ais_data, tis_data, as26_data, prefill_data=None):
    # Extract Prefill employer TDS entries
    # Cross-match against 26AS employer TDS entries
    # Use Prefill salary break-up (basic, HRA, perquisites) when 26AS
    # only has the total
```

#### Step 4.2: Add filed-return input for comparison

Extend `reconcile()` to accept a `filed_return_data` parameter for
year-over-year comparison:
```python
def reconcile(..., filed_return_data=None):
    # Compare current-year salary against previous-year salary
    # Flag if employer changed
    # Flag if bank accounts changed
```

#### Step 4.3: Add Prefill-vs-26AS employer TDS reconciliation

Prefill carries employer TDS details; 26AS also carries them.  Without
reconciliation, they may double-count.  Add a cross-check that
deduplicates employer TDS entries across Prefill and 26AS.

### Deliverables

- Extended `ais_extractor/reconciliation.py` with `prefill_data` and
  `filed_return_data` parameters
- Updated `job_worker.py` to pass Prefill and filed-return data to
  `reconcile()`

### What you can test

1. Run a portal automation import
2. Check the reconciliation log — should show Prefill-vs-26AS
   employer TDS cross-checks
3. Verify no double-counting of employer TDS in the reconciled output

---

## Phase 5: Document Persistence + Re-parse/Re-reconcile

**Status:** Not started
**Estimated effort:** 1-2 days

### Goal

Store every imported document in the `ImportedDocument` table (created
in Phase 3) and add endpoints to re-parse or re-reconcile without
re-downloading from the portal.

### Steps

#### Step 5.1: Persist portal-automation downloads

In `job_worker.py`, after each download, store the raw + parsed
content in the `ImportedDocument` table:
- 26AS PDF → raw (base64) + parsed JSON
- AIS PDF → raw (base64) + parsed JSON
- TIS PDF → raw (base64) + parsed JSON
- Prefill JSON → raw text + parsed JSON
- Filed return JSON → raw text + parsed JSON

#### Step 5.2: Add re-parse endpoint

```python
@router.post("/clients/{client_id}/itr/{year}/re-parse/{doc_type}")
def re_parse(client_id, year, doc_type, ...):
    # Load ImportedDocument for this client + AY + doc_type
    # Re-run the parser
    # Update parsed_content
    # Return new parsed result
```

#### Step 5.3: Add re-reconcile endpoint

```python
@router.post("/clients/{client_id}/itr/{year}/re-reconcile")
def re_reconcile(client_id, year, ...):
    # Load all ImportedDocuments for this client + AY
    # Re-run reconciliation
    # Return new reconciled result
```

#### Step 5.4: Add import history view

Frontend: show imported documents per client + AY with timestamps,
source (portal vs upload), and re-parse/re-reconcile buttons.

### Deliverables

- Updated `job_worker.py` to persist downloads
- New re-parse endpoint
- New re-reconcile endpoint
- New import history frontend view

### What you can test

1. Run a portal automation import
2. Check the `ImportedDocument` table — should have 5 rows (26AS, AIS,
   TIS, Prefill, filed return)
3. Hit the re-reconcile endpoint — should return a new reconciled
   result without re-downloading
4. Open the import history view — should show 5 documents with
   timestamps

---

## Phase 6: Year-Adaptive Integration

**Status:** Not started (after Year-Adaptive plan)
**Estimated effort:** 1-2 days

### Goal

When the `YEAR_ADAPTIVE_ARCHITECTURE_PLAN.md` is implemented, remove
hardcoded assessment years from the import pipeline and make the
section/category mappings profile-driven.

### Steps

#### Step 6.1: Remove hardcoded AY from downloaders

Replace `AY = "2026-27"` with `profile = get_profile(assessment_year)`
in:
- `downloader_prefill.py`
- `downloader_ais_tis.py`
- `downloader_26as.py`
- `downloader_filed_return.py`

#### Step 6.2: Profile-driven section→category mapping

Move `SECTION_TO_CATEGORY` and `CATEGORY_TO_INCOME_HEAD` from
`reconciliation.py` into the `TaxYearProfile` so they can change per
AY when the Finance Act adds new sections.

#### Step 6.3: Profile-driven field mapping

`mapReconciledToFormData` and `mapPrefillToFormData` should use the
tax-year config to know which form fields exist for the current AY
(field names may change when the CBDT schema changes).

### Deliverables

- Updated downloaders (profile-driven AY)
- Profile-driven section/category mapping
- Profile-driven field mappers

### What you can test

1. Switch to a different assessment year (e.g. 2027-28)
2. Run a portal automation import — should download for the new AY
3. Verify the Prefill parser extracts correctly for the new AY
4. Verify reconciliation uses the new section/category mapping

---

## Commit History

| Phase | Commit | Description | Date |
|---|---|---|---|
| 1 | `2b5f720` | feat(import): Phase 1 — form-agnostic Prefill JSON parser + mapper | 2026-08-15 |
| 1 | `eabeaec` | fix(prefill-mapper): add id to bank account entries | 2026-08-15 |
| 1 | `fb4ca8f` | fix(prefill-parser): match real ITD prefill JSON structure | 2026-08-15 |
| 1 | `bcc0054` | feat(prefill-parser): extract ALL sections from ITD prefill + dedupe banks | 2026-08-15 |
| 1 | (pushed) | All 4 commits pushed to `origin/main` | 2026-08-15 |
| 2 | (pending) | feat(import): Phase 2 — filed-return parser + revised-return flagging | 2026-08-15 |
| 3 | (pending) | feat(import): Phase 3 — real parsers + document persistence | 2026-08-15 |
| 4 | — | *Not started* | — |

---

## Testing Checklist

### Phase 1 (complete)

- [x] Portal automation import downloads Prefill JSON
- [x] Prefill parser extracts personal info (PAN, Aadhaar, name, DOB, address)
- [x] Prefill parser extracts bank accounts (deduplicated, 1 refund)
- [x] Prefill parser extracts TDS-other entries
- [x] Prefill parser extracts deductions (80TTA, 80TTB)
- [x] Prefill parser extracts other sources income (dividend, SB, FD)
- [x] Prefill parser extracts all other sections (depreciation, AMT, ESOP, audit, 10IF, etc.)
- [x] Frontend mapper converts extraction to flat formData
- [x] ITRComputationPage merges Prefill data into the form
- [x] Bank accounts appear in Personal Info tab (1 account, 1 refund)
- [x] Secondary toast shows Prefill-specific imports
- [x] Backend log shows correct extraction counts

### Phase 2 (complete)

- [x] Filed-return parser auto-detects ITR form (ITR1-ITR7)
- [x] Filed-return parser extracts personal info (PAN, Aadhaar, name, DOB, address)
- [x] Filed-return parser extracts employer entries (name, TAN, salary)
- [x] Filed-return parser extracts bank accounts (deduplicated, 1 refund)
- [x] Filed-return parser extracts TDS-other entries
- [x] Filed-return parser extracts carry-forward losses
- [x] Filed-return parser extracts all other schedules (CYLA, BFLA, SI, AMTC, CG)
- [x] Classifier detects revised returns (section 139(5))
- [x] Advisory flags current_ay_already_filed and current_ay_is_revised
- [x] Advisory requires user confirmation for revision
- [x] Job worker parses filed-return JSON and attaches to reconciled output
- [x] Frontend mapper converts extraction to flat formData
- [x] ITRComputationPage merges filed-return data (lowest precedence)
- [x] Warning banner shows advisory message when current-AY already filed
- [x] Prominent error toast for revised-return scenarios

### Phase 3 (complete)

- [x] ImportedDocument DB model created with unique constraint
- [x] imported_document table auto-created on startup
- [x] AIS endpoint uses real `extract_ais` parser (PDF)
- [x] AIS endpoint decrypts encrypted JSON from portal
- [x] TIS endpoint uses real `extract_tis` parser
- [x] 26AS endpoint uses real `extract_26as` parser (PDF)
- [x] 26AS endpoint uses `parse_26as_txt` (TXT)
- [x] Prefill endpoint uses real `parse_prefill_json` parser
- [x] Form 16 endpoint returns 501 (no parser yet)
- [x] Reconciliation endpoint calls real `reconcile()`
- [x] All upload endpoints persist raw + parsed content to ImportedDocument
- [x] Dead code `prefill_service.py` deleted
- [x] Frontend `reconciliation.ts` stub replaced with real client

### Phase 4 (pending)

- [ ] Reconciliation engine accepts Prefill input
- [ ] Reconciliation engine accepts filed-return input
- [ ] Prefill-vs-26AS employer TDS cross-check works
- [ ] No double-counting of employer TDS

### Phase 5 (pending)

- [ ] Portal automation downloads persisted in `ImportedDocument` table
- [ ] Re-parse endpoint works without re-downloading
- [ ] Re-reconcile endpoint works without re-downloading
- [ ] Import history view shows documents with timestamps

### Phase 6 (pending — after Year-Adaptive plan)

- [ ] Downloaders use profile-driven AY (not hardcoded)
- [ ] Section/category mapping is profile-driven
- [ ] Field mappers use tax-year config
- [ ] Import works for any supported AY

---

## Notes

- **CBDT guidelines reference:** When stuck or confused, refer to the
  CBDT prefill schema at `Docs/PreFillSchemaJSON_V6.5/PreFillSchemaJSON_V6.5.json`
  and the official CBDT documentation in `Reference Docs by CBDT & ITD/`.
- **Real ITD prefill structure:** The real ITD prefill JSON uses a
  different structure than the schema's `$defs` suggest.  See the
  "match real ITD prefill JSON structure" commit (`fb4ca8f`) for
  details.
- **Form-agnostic principle:** All parsers in `app/engine/importers/`
  are form-agnostic — they extract every field and let the
  form-specific mappers in the frontend pick what they need.
