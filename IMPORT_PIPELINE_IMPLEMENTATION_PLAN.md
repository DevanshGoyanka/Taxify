# Import Pipeline Implementation Plan

**Document created:** 2026-08-15
**Last updated:** 2026-08-15 (after Phase 1 completion)
**Status:** Phase 1 complete, Phase 2 next

This document tracks the complete implementation plan for fixing the
import pipeline as identified in `IMPORT_FLOW_AUDIT_REPORT.md`.  It is
updated after every commit and before moving to the next phase.

---

## Table of Contents

1. [Phase 1: Form-agnostic Prefill JSON Parser ✅ COMPLETE](#phase-1-form-agnostic-prefill-json-parser--complete)
2. [Phase 2: Last Filed ITR JSON Parser](#phase-2-last-filed-itr-json-parser)
3. [Phase 3: Fix Individual Upload Endpoints + Document Persistence](#phase-3-fix-individual-upload-endpoints--document-persistence)
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

## Phase 2: Last Filed ITR JSON Parser

**Status:** Not started
**Estimated effort:** 1-2 days

### Goal

The last filed ITR JSON contains the taxpayer's previous-year return —
useful for:
- Pre-populating personal info (name, address, DOB, father's name)
- Pre-populating employer details (if same employer)
- Pre-populating bank accounts
- Providing a baseline for year-over-year comparison
- Carrying forward capital gains losses, brought-forward losses

Currently `downloader_filed_return.py` downloads it, but
`job_worker.py` never parses it.  The JSON is deleted after the job.

### Steps

#### Step 2.1: Study the filed-return JSON structure

The filed-return JSON is the CBDT's official ITR JSON for the previous
year.  It follows the same schema as the current-year ITR JSON (see
`PreFillSchemaJSON_V6.5.json` for the type library).  The top-level
keys differ by ITR form (ITR-1, ITR-2, ITR-3, ITR-4, etc.).

**Action:** Run a portal automation import with diagnostic logging to
dump the filed-return JSON structure (similar to how we dumped the
Prefill JSON in Phase 1).

#### Step 2.2: Create `app/engine/importers/filed_return_parser.py`

A form-agnostic parser that extracts:
- Personal info (name, address, DOB, PAN, Aadhaar, father's name)
- Employer details (if same employer — name, TAN, salary)
- Bank accounts (account no, bank name, IFSC, refund flag)
- Brought-forward losses (capital gains, house property, business)
- Section 80C cumulative deductions (for pension/PPF continuation)
- Carry-forward capital gains losses (for setoff against current-year
  gains)
- Filing status (return section, residential status)
- Verification details

#### Step 2.3: Wire into `job_worker.py`

After downloading the filed-return JSON, call the parser and attach
the extraction to the reconciled output under the `filed_return` key.

#### Step 2.4: Create `frontend/src/utils/mapFiledReturnToFormData.ts`

Maps the filed-return extraction to the flat formData shape.  Only
populate fields that are carry-forward (brought-forward losses,
personal info if empty, bank accounts if empty).

#### Step 2.5: Merge in `ITRComputationPage`

In `handleConfirmImport`, after `mapPrefillToFormData` and
`mapReconciledToFormData`, also run `mapFiledReturnToFormData` and
merge.  Prefill and reconciled take precedence; filed-return fills
gaps.

### Deliverables

- `app/engine/importers/filed_return_parser.py`
- `frontend/src/utils/mapFiledReturnToFormData.ts`
- Updated `app/automation/job_worker.py`
- Updated `frontend/src/pages/ITRComputationPage.tsx`

### What you can test

1. Run a portal automation import
2. Check the backend log — should say `Filed return extraction OK —
   personal_info=Yes, banks=N, losses=N`
3. Confirm the import — brought-forward losses should appear in the
   capital gains / house property tabs
4. Personal info should be pre-populated (if not already from Prefill)

---

## Phase 3: Fix Individual Upload Endpoints + Document Persistence

**Status:** Not started
**Estimated effort:** 3-4 days

### Goal

Every endpoint in `app/routers/integration.py` returns hardcoded mock
data.  The real parsers (`ais_extractor/extractor.py`,
`ais_extractor/as26_extractor.py`, `ais_extractor/tis_extractor.py`)
are only called by `job_worker.py`.  Individual uploads of AIS/TIS/
26AS/Prefill/Form 16 all get mock data.

This phase rewires the individual upload endpoints to use the real
parsers and adds a new `ImportedDocument` DB table for persistence.

### Steps

#### Step 3.1: Create `ImportedDocument` DB model

**New table:** `imported_document`

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | Auto-increment |
| `client_id` | Integer FK → `client.id` | ON DELETE CASCADE, indexed |
| `user_id` | Integer FK → `user.id` | ON DELETE CASCADE, indexed |
| `assessment_year` | String(10) | e.g. "2026-27" |
| `document_type` | String(20) | prefill, ais, tis, 26as, form16, filed_return |
| `source` | String(20) | portal, upload |
| `raw_content` | Text | Raw file content (JSON or base64 PDF) |
| `parsed_content` | Text | Parsed JSON (default "{}") |
| `created_at` | DateTime | Default UTC now |
| | | Unique constraint: (client_id, assessment_year, document_type) |

#### Step 3.2: Rewrite `app/routers/integration.py`

For each endpoint:
1. Read uploaded file
2. If PDF, write to temp and call the real extractor
3. If JSON, parse directly
4. Store raw + parsed content in `ImportedDocument` table
5. Return parsed content

**Endpoints to fix:**
- `POST /integration/form16/extract` — needs a Form 16 PDF parser
- `POST /api/v1/imports/ais` — use `ais_extractor.extractor.extract_ais`
- `POST /integration/ais-json/import` — use `ais_extractor.extractor`
- `POST /integration/tis/import` — use `ais_extractor.tis_extractor.extract_tis`
- `POST /integration/26as/import` — use `ais_extractor.as26_extractor.extract_26as`
- `POST /integration/prefill/import` — use `app.engine.importers.prefill_parser.parse_prefill_json`
- `POST /integration/autopopulate/form16` — merge Form 16 data into formData
- `POST /integration/autopopulate/ais` — merge AIS data into formData
- `POST /prefill/autoPopulateAll` — combine 26AS + AIS + TIS → form data
- `POST /integration/reconciliation` — call `ais_extractor.reconciliation.reconcile`
- `POST /prefill/autopopulate` — merge Prefill into formData

#### Step 3.3: Wire real reconciliation into upload path

Replace the mock `reconciliation()` endpoint with a call to
`ais_extractor.reconciliation.reconcile()`:

```python
@router.post("/integration/reconciliation")
def reconciliation(payload: dict, ...):
    ais = payload.get("aisData", {})
    tis = payload.get("tisData", {})
    as26 = payload.get("data26AS", {})
    result = reconcile(ais, tis, as26)
    return result
```

#### Step 3.4: Delete dead code

- Delete `app/services/prefill_service.py` (dead code, wrong AY)
- Delete `frontend/src/api/reconciliation.ts` stub (or wire it to the
  real endpoint)
- Remove mock data from every `integration.py` endpoint

### Deliverables

- New `ImportedDocument` DB model + migration
- Rewritten `app/routers/integration.py` with real parsers
- Deleted dead code (`prefill_service.py`, `reconciliation.ts` stub)

### What you can test

1. Upload an AIS PDF via the individual upload UI
2. Check the backend log — should call the real `extract_ais` parser
3. Verify the parsed AIS data is stored in the `ImportedDocument` table
4. Upload a 26AS text file — should call the real `extract_26as` parser
5. Upload a Prefill JSON — should call `parse_prefill_json` and store
6. Trigger reconciliation from the UI — should return real
   discrepancies (not `{"hasDiscrepancies": False}`)

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
| 2 | — | *Not started* | — |

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

### Phase 2 (pending)

- [ ] Filed-return parser extracts personal info
- [ ] Filed-return parser extracts bank accounts
- [ ] Filed-return parser extracts brought-forward losses
- [ ] Filed-return data merged into formData
- [ ] Brought-forward losses appear in capital gains / house property tabs

### Phase 3 (pending)

- [ ] Individual upload of AIS PDF calls real `extract_ais`
- [ ] Individual upload of 26AS text calls real `extract_26as`
- [ ] Individual upload of Prefill JSON calls `parse_prefill_json`
- [ ] Uploaded documents stored in `ImportedDocument` table
- [ ] Reconciliation endpoint returns real discrepancies
- [ ] Dead code (`prefill_service.py`) deleted

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
