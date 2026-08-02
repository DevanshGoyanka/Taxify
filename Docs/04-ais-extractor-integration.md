# 04 — AIS Extractor Integration into Backend Pipeline

**Date:** 2026-07-29  
**Status:** Complete  
**Depends on:** docs/04-downloads-and-status-ui.md (Chunk 2.2 job worker)

---

## 1. What Was Built

Integrated `ais_extractor/` into the backend job pipeline so that after the automation worker downloads 26AS, AIS, and TIS PDFs (and unlocks them), each PDF is automatically parsed and the structured results are stored on the `AutomationJob` record for consumption by downstream steps (reconciliation, form population).

---

## 2. PDF-to-Extractor Mapping

| PDF Type | Extractor Module | Function | Dependency |
|---|---|---|---|
| **Form 26AS** | `ais_extractor.as26_extractor` | `extract_26as(pdf_path) -> dict` | `pdfplumber` |
| **AIS** | `ais_extractor.extractor` | `extract_ais(pdf_path) -> AISDocument` | `fitz` (PyMuPDF) |
| **TIS** | `ais_extractor.tis_extractor` | `extract_tis(pdf_path) -> TISDocument` | `fitz` (PyMuPDF) |

All three PDF types have existing parsers — no new parsers were needed.

---

## 3. Files Changed / Created

| File | Change |
|---|---|
| `ais_extractor/__init__.py` | **New** — package init exposing `extract_26as`, `extract_ais`, `extract_tis` and JSON helpers |
| `app/db/models.py` | Added `parsed_results: Mapped[str]` column (JSON text, default `"{}"`) to `AutomationJob` |
| `app/automation/job_worker.py` | Added `ais_extractor` imports, `"extract"` step in `_STEP_PROGRESS`, extraction logic in `_run_job()` (Step 4.5), and `parsed_results` in `_get_job_dict()` |
| `app.db` (SQLite) | `ALTER TABLE automation_job ADD COLUMN parsed_results TEXT NOT NULL DEFAULT "{}"` |

---

## 4. Extraction Step Details

### Location in pipeline

Inserted as **Step 4.5** between unlock (Step 4) and logout (Step 5):

```
Step 1: login
Step 2: download_26as (+ unlock)
Step 3: request_ais / download_tis
Step 4: unlock AIS + TIS PDFs
Step 4.5: extract ← NEW — call ais_extractor on all 3 PDFs
Step 5: logout
```

### Pseudocode

```
for each of {26as, ais, tis}:
    if pdf_path exists:
        try:
            result = extractor(pdf_path)
            store result in parsed dict
            log summary (row counts, section counts)
        except Exception:
            capture error, continue to next PDF

if any_errors:
    parsed["_extraction_errors"] = [errors...]

update_job(parsed_results = json.dumps(parsed))
```

### Key design decisions

- **Errors are non-fatal**: If one extractor fails (e.g., corrupted PDF), the other two results are still stored. Errors go in `_extraction_errors` list within the parsed output.
- **PDFs are already unlocked** at this point (unlock in Steps 2 and 4). If unlock failed, the PDF won't exist/won't be readable and extraction logs a friendly skip.
- **26AS `_details` key is stripped** before storage to keep JSON clean. The raw extractor includes an internal `_details` key on each row that's used during parsing but not needed downstream.
- **AIS and TIS** use their respective `*_to_frontend_json()` helpers to produce a consistent JSON structure (`metadata`, `income_heads`, `summary`).
- **No changes to ais_extractor logic itself** — only an `__init__.py` added to make it importable as a package. The extractors already accepted `pdf_path` as a parameter and return structured data; they were already callable, just not importable as a clean package.

---

## 5. Parsed Results Shape

### `parsed_results` in job response

```json
{
  "26as": {
    "header": { "Permanent Account Number (PAN)": "...", "Financial Year": "...", ... },
    "parts": { "I": { "empty": false, "title": "...", "rows": [...] }, ... }
  },
  "ais": {
    "metadata": { "pan": "...", "name": "...", ... },
    "income_heads": { "Income from Other Sources": { "entries": [...], ... } },
    "summary": { "total_interest": 0.0, "total_dividend": 0.0, ... }
  },
  "tis": {
    "metadata": { "pan": "...", "name": "...", ... },
    "overview": [{ "sr_no": 1, "category": "...", "processed_by_system": 130.0, ... }],
    "income_heads": { "Income from Other Sources": { "entries": [...], ... } },
    "reconciliation": { "Dividend": { "processed_matches": true, ... } }
  },
  "_extraction_errors": []  // only present if errors occurred
}
```

### `parsed_results` exposed in GET `/automation/jobs/{job_id}`

The field is returned in the `_get_job_dict()` response under `parsed_results`.

---

## 6. Test Results

Tested against 3 real PDFs from `downloads/1/2025-26/` (client PAN: EPPPG3078Q, FY: 2025-26):

### 26AS (`EPPPG3078Q-26AS-2025_26.pdf`)
- **Metadata extracted**: PAN=EPPPG3078Q, FY=2024-25, Name=DEVANSH SUNIT GOYANKA
- **All parts present**: I-X, all empty (no TDS/TCS/refunds for this PAN — expected for young assessee)
- **Rows**: 0 total across all parts

### AIS (`EPPPG3078Q-AIS-2025_26.pdf`)
- **Metadata extracted**: PAN, Name, FY=2025-26
- **B2 entries**: 3 (Dividend SFT-015, Interest SFT-005, Interest SFT-005)
- **Income heads**: "Income from Other Sources" — 3 entries, total_amount=₹1,126
- **Tax payments**: 0, **Refunds**: 0
- Sample first entry: sr=1, code=SFT-015, desc="Dividend income", amount=₹130, details=1

### TIS (`EPPPG3078Q-TIS-2025_26.pdf`)
- **Metadata extracted**: PAN, Name, FY=2025-26
- **Overview**: 3 categories (Dividend ₹130, Interest from savings bank ₹157, Interest from deposit ₹839)
- **Annexure entries**: 3 (each with 1 detail row)
- **Reconciliation**: All 3 categories match — `processed_matches=true, accepted_matches=true`
- This means the Page 1 overview totals equal the sum of Annexure detail rows (reconciliation already verified internally)

### Final `parsed_json` size: 9,957 characters (all 3 PDFs combined)

---

## 7. Minimal Changes to `ais_extractor/`

The only change to `ais_extractor/` itself was adding `__init__.py` for clean imports. No internal logic was modified. The extractor functions already:

- Took `pdf_path: str` as their sole required argument
- Returned structured data (dict / dataclass)
- Had no hardcoded paths or script-level assumptions

---

## 8. Open Questions / Next Chunks

- **Reconciliation (Chunk 5)**: The next chunk should compare AIS vs TIS income figures and flag discrepancies. TIS already includes internal reconciliation (overview vs detail sums). The next layer reconciles AIS vs TIS at the income-head level.
- **Form population (Chunk 6)**: After reconciliation, the parsed data should auto-populate form fields in the ITR computation page.
- **DOB format**: Client DOB is stored as YYYY-MM-DD in the DB, but `pdf_unlocker` expects DD-MM-YYYY. Currently working because the unlocker splits by `-` and constructs DDMMYYYY. This is fragile — consider normalizing DOB handling in a future chunk.
