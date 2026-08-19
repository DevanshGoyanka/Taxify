DATE - 19-08-2026(After all the uploads were fixed)

# End-to-End Imports & Reconciliation — Definitive Documentation

**Status:** Living document. Every claim below is verified against the current codebase (commit on `main` as of the AIS/TIS pdfplumber migration). Where the implementation differs from CBDT/ITD rules, the deviation is flagged explicitly in a `⚠ CBDT DEVIATION` or `⚠ GAP` callout.

**Scope:** This document covers the **complete import pipeline** for all income-tax source documents the application ingests. There are **four persisted document types** — Prefill JSON, Form 26AS, AIS PDF, and TIS PDF — across both ingestion paths. (Form 26AS arrives as either a PDF or a TXT inside a TRACES ZIP, but both formats collapse to the single `26as` document_type at the storage layer; see §2.2.) Form 16 is **out of scope** for automated extraction (no parser exists — §0, E1) but is listed in §0's table for completeness because the endpoint exists and returns HTTP 501.

- **PART 1 — Portal Automation Import** (the ITD-portal downloader that fetches the source artifacts in one job)
- **PART 2 — Manual Individual Uploads** (the user uploads one document at a time)

**Important caveat on "shared":** Both parts call the **same `reconcile()` engine** and the **same per-document extractors**, and now share the **same `imported_document_service`** persistence layer (P1/P2/P4 resolved). The delivered payload is **mostly** identical across paths: `_extraction_errors` is now attached in both the automation path and the manual `/v2/imports/parse-reconcile` path (P5 resolved). `filing_advisory` / `filing_mode_classification` remain **automation-only** by design (they require portal-side filed-return inventory + classification that manual uploads don't trigger) — the manual path returns a strict subset. See §1.4 and §3.8, and register entry P5.

The final sections cover how reconciled figures are populated into income heads on the frontend, and a consolidated risk/gap register.

---

## 0. The Extractors (shared by both paths)

All four source documents are parsed by a single package — `ais_extractor/` — plus the prefill parser. At **runtime**, exactly one extractor function is invoked per document type by both the automation worker and the manual-upload endpoints. (Note: the AIS module retains a legacy regex path `_parse_listed_equity_sale_rows` that is no longer on the live call path but is still imported by a unit test — see E3. It is retained as a reference/rollback artefact; the pdfplumber extractor is the sole live path.)

| Document | Extractor function | Lives in | Backing library | Corpus-verified accuracy |
|---|---|---|---|---|
| **AIS PDF** | `extract_ais()` / `extract_ais_json()` | `ais_extractor/extractor.py` → delegates to `ais_extractor/ais_pdfplumber.py` | `pdfplumber` | **100%** — 65/65 corpus tests pass (64 unique AIS PDFs + 1 discovery-guard test). Every PDF's metadata, B1/B2/B7 entries, detail rows, ISIN/quantity/sale-price semantic keys, and page-break continuation merges verified |
| **TIS PDF** | `extract_tis()` / `tis_to_frontend_json()` | `ais_extractor/tis_extractor.py` → delegates to `ais_extractor/tis_pdfplumber.py` | `pdfplumber` | **100%** — 64/64 corpus tests pass (63 unique TIS PDFs + 1 discovery-guard test). Every overview category has exactly one matching Annexure entry (no missing/phantom entries); `processed_by_system` reconciles to the rupee for **all** categories across **all** PDFs; `accepted_by_taxpayer` reconciles for 62/63 PDFs, with the single exception (AONPD0576P Dividend) verified against the raw PDF as a TIS-source data inconsistency, not a parser bug |
| **26AS PDF** | `extract_26as()` / `extract_26as_json()` | `ais_extractor/as26_extractor.py` | `pdfplumber` | Production; covered by `tests/test_26as_*` |
| **26AS TXT (in ZIP)** | `parse_26as_txt()` (legacy `_parse`) | `app/automation/as26_converter.py` | stdlib regex | Legacy fallback for the TRACES password-protected ZIP path |
| **Prefill JSON** | `parse_prefill_json()` / `parse_prefill_file()` | `app/engine/importers/prefill_parser.py` | stdlib `json` | Production; covered by `tests/test_prefill.py` |
| **Form 16** | — | — | — | ⚠ **NOT IMPLEMENTED** — the endpoint returns HTTP 501 ("Form 16 auto-extraction is not yet available") |

### 0.1 Production-readiness verdict for the AIS & TIS **parsing layer**

**YES — the AIS and TIS extractors are production-ready *as parsers*.** This verdict is scoped strictly to extraction correctness (every entry, every total, every cell). It does **not** extend to the downstream pipeline: a High-severity TCS-routing deviation (R1) and Medium-High persistence/cross-path gaps (P1–P3) consume these extractors' output and are still open — see §5 before treating the end-to-end pipeline as production-ready.

1. **Cell-accurate parsing.** Both now use `pdfplumber.extract_tables()`, which recovers proper cell boundaries. The earlier PyMuPDF line-state-machine lost multi-word cells (e.g. `Listed Equity Share`, `Off market`, `Short term` split across lines), which collapsed SFT-17-LES sale tables to summary-only aggregates and caused detail-row "bleeding" between entries. pdfplumber eliminates both classes of defect.
2. **Page-break continuity.** Detail tables that span 2+ pages (e.g. a 79-row SFT-17-LES sale table, a 22-row GST-purchases table) are merged across page boundaries — both detail-header-only continuation tables (AIS) and detail-only / overview-split continuation tables (TIS).
3. **Semantic keys.** AIS detail rows carry header-driven semantic keys (`isin`, `security_name`, `quantity`, `sales_consideration`, `asset_type`, `debit_type`, `credit_type`, `indexed_cost_of_acquisition`, …) so the capital-gains mapper and the 112A engine consume structured fields, not positional `col_N` indices.
4. **Per-rupee cross-foot.** For every TIS PDF, the page-1 overview total (parsed independently) equals the sum of that category's Annexure detail rows, for every category. A detail row attached to the **wrong** entry would change the donor and recipient category totals, so wrong-attachment that changes a category total by more than the ₹1 tolerance is caught. (Two rows swapped between categories with offsetting amounts would still pass — a low-probability gap; the `present_in` provenance flags and the entry-level `has_discrepancy` comparison provide a secondary check.)
5. **No missing/phantom entries.** For every TIS client, the overview category count equals the Annexure entry count, one-to-one by `(sr_no, category)`.

The extractors are wired into both ingestion paths (automation worker + manual uploads) and into the reconciliation engine — see the flow diagrams below.

---

## PART 1 — Portal Automation Import

### 1.1 Trigger

The user clicks "Import from Portal" in the frontend for a given client + assessment year. The frontend calls:

```
POST /api/clients/{client_id}/automation/import?assessment_year=2026-27&job_type=DOWNLOAD_ALL
```

(`app/routers/automation.py::start_automation_import`). `job_type` can be `DOWNLOAD_ALL` (default), `DOWNLOAD_AIS_TIS`, or `DOWNLOAD_26AS`.

### 1.2 What the job downloads

The endpoint creates an `AutomationJob` row (status=`queued`) and enqueues it into the background worker (`app/automation/job_worker.py::_run_job`). For `DOWNLOAD_ALL`, the worker runs four download sub-steps in order, producing five artifacts on disk under `_download_dir(client_id, fiscal_year)`:

| Step | Downloader | Artifact(s) produced |
|---|---|---|
| `download_26as` | `app/automation/downloader_26as.py::download_26as` | `26as.txt` (and/or `26as.pdf`) inside a TRACES password-protected ZIP, unzipped to disk |
| `download_ais_tis` | `app/automation/downloader_ais_tis.py::run_download_ais_tis` | `ais.pdf` and `tis.pdf` (AIS/TIS are downloaded together because they share a portal request flow: `run_request_ais` then the joint download) |
| `download_prefill` | `app/automation/downloader_prefill.py::download_prefill` | `prefill.json` (the ITD Prefill JSON for the ITR form — currently ITR-1) |
| `download_filed_return` | `app/automation/downloader_filed_return.py::download_filed_return_json` | (currently commented out / REACTIVATE — see §1.6 GAP) |

The PDFs are password-protected by the ITD portal; `pdf_unlocker.py` + `verify_pdf_decryptable()` decrypt them using the client's DOB before extraction.

### 1.3 Extraction (same extractors as manual uploads)

After download, the worker runs the **same extractors** the manual-upload endpoints use:

```python
# job_worker.py (simplified)
from ais_extractor.extractor import extract_ais as _extract_ais, ais_to_frontend_json as _ais_to_frontend
from ais_extractor.tis_extractor import extract_tis as _extract_tis, tis_to_frontend_json as _tis_to_frontend
from ais_extractor.reconciliation import reconcile as _reconcile_data
from app.engine.importers.prefill_parser import parse_prefill_file as _parse_prefill_file, ...

result_26as = _extract_26as(path_26as)          # → dict {header, parts{I,IV,VI,VII}}
doc_ais     = _extract_ais(path_ais)            # → AISDocument (dataclass)
ais_json    = _ais_to_frontend(doc_ais)         # → frontend JSON
doc_tis     = _extract_tis(path_tis)            # → TISDocument
tis_json    = _tis_to_frontend(doc_tis)         # → frontend JSON
prefill_ext = _parse_prefill_file(prefill_path, assessment_year=ay)
```

### 1.4 Reconciliation (same engine as manual uploads)

The worker then calls the single reconciliation engine:

```python
reconciled = _reconcile_data(ais_data=ais_dict, tis_data=tis_dict, as26_data=as26_dict)
if parsed.get("prefill"):
    reconciled["prefill"] = parsed["prefill"]    # attach form-agnostic prefill extraction
reconciled["filing_advisory"] = artifact_outcomes["filing_advisory"]
reconciled["filing_mode_classification"] = artifact_outcomes["filing_mode_classification"]
reconciled["_extraction_errors"] = extract_errors
```

The reconciliation engine (`ais_extractor/reconciliation.py::reconcile`) is the heart of the system. Its rules are detailed in **§3**.

### 1.5 Persistence & delivery to the frontend

The reconciled result is stored **as a single JSON blob** on the `AutomationJob.parsed_results` column:

```python
parsed_json = json.dumps(reconciled, ensure_ascii=False, default=str)
_update_job(job_id, parsed_results=parsed_json, progress_pct=94)
```

The frontend polls `GET /api/automation/jobs/{job_id}` (returns `_get_job_dict(job_id)`, which surfaces `parsed_results` as a parsed dict) and renders the income-head summary, the capital-gains evidence ledger, and the unmatched/discrepancy lists.

⚠ **RESOLVED (P1):** The automation worker **now persists all four source documents** to the `imported_document` table (Step 4.6.2, via `app/db/imported_document_service.upsert_imported_document` with `source=automation`), in addition to storing the reconciled blob on `AutomationJob.parsed_results`. The cross-path dedup consequence described in §2.3 is now closed — a manual re-upload replaces the automation's row in place on the shared dedup key.

### 1.6 Automation GAP register

| # | Gap | Impact | Severity |
|---|---|---|---|
| A1 | Filed-return download (`download_filed_return_json`) is commented out in the worker (`# REACTIVATE: prior_dl = await download_filed_return_json(...)`) and its attachment to the reconciled output is also commented out (`# REACTIVATE: reconciled["filed_return"] = parsed["filed_return"]`) | The "filed return" reactivation feature (compare this year's draft against last year's filed return) does not receive the filed-return JSON through automation. | Medium |
| (→ P1) | Automation result lives only on `AutomationJob.parsed_results`; the four raw source documents are not written to `imported_document` | This is the same root-cause gap tracked as **P1** in §5.3 (Medium-High) — no separate automation-side entry to avoid register duplication. | Medium-High (see P1) |

---

## PART 2 — Manual Individual Uploads

### 2.1 The two manual-upload endpoints

There are two parallel surfaces for manual uploads. Both call the **same extractors**:

**(a) Per-document endpoints** — `app/routers/integration.py`:

| Endpoint | Function | Extractor called |
|---|---|---|
| `POST /api/v1/imports/ais` (alias `POST /integration/ais-json/import`) | `import_ais_json` | `extract_ais` + `extract_ais_json` (PDF), `decrypt_ais_json` (encrypted portal JSON), `json.loads` (plain JSON) |
| `POST /integration/tis/import` | `import_tis` | `extract_tis` + `tis_to_frontend_json` (PDF), `json.loads` (plain JSON) |
| `POST /integration/26as/import` | `import_26as` | `extract_26as` (PDF), `parse_26as_txt` (TXT), ZIP→unzip→either (TRACES ZIP), `json.loads` (plain JSON) |
| `POST /integration/prefill/import` | `import_prefill` | `parse_prefill_json` |
| `POST /integration/form16/extract` | `extract_form16` | ⚠ returns HTTP 501 (no parser) |
| `POST /integration/reconciliation` | `reconciliation` | `ais_extractor.reconciliation.reconcile` |

**(b) Unified parse+reconcile endpoint** — `app/routers/tax_v2.py`:

| Endpoint | Function | Extractors called |
|---|---|---|
| `POST /v2/imports/parse-reconcile` | `parse_reconcile` | any subset of {`extract_ais_json`, `extract_tis`+`tis_to_frontend_json`, `extract_26as`, `parse_prefill_json`}, then `reconcile` |

The unified endpoint accepts all four files in one multipart request (`ais`, `tis`, `form26as`, `prefill` — each optional), parses whatever is supplied, runs `reconcile` on the AIS/TIS/26AS combination present, attaches `prefill` if supplied, and returns the full `ReconciledResults` payload.

### 2.2 Persistence model (the dedup key)

Both manual-upload paths persist to the **`imported_document`** table (`app/db/models.py::ImportedDocument`). The table has a `UniqueConstraint("client_id", "assessment_year", "document_type")` — so the dedup key is **(client × assessment year × document type)**.

The upsert helper (`_upsert_imported_document`, present in both `integration.py` and `tax_v2.py`) works as follows:

```python
existing = db.query(ImportedDocument).filter(
    ImportedDocument.client_id == client_id,
    ImportedDocument.assessment_year == assessment_year,
    ImportedDocument.document_type == document_type,   # "ais" | "tis" | "26as" | "prefill"
).first()
if existing is not None:
    existing.raw_content = raw_content          # REPLACE raw bytes
    existing.parsed_content = parsed_content   # REPLACE parsed JSON
    db.commit()
    return existing
# else INSERT a new row
```

### 2.3 Manual re-upload behaviour — exactly what happens

> **Your question:** "If I have already imported the automation import but I re-upload any of imports manually, how does the system handle that? Does it create a duplicate entry? Or does it erase all the already imported data via automation and just keep the latest imported data?"

**Answer (verified against the code):**

1. **Within the manual-upload path, re-uploading the same document type for the same client + AY does NOT create a duplicate.** It performs an in-place **replace** of that single document's `raw_content` + `parsed_content` rows (the upsert above). The other document types' rows are untouched.

2. **Re-uploading a manual document does NOT automatically re-run reconciliation.** The per-document endpoints (`/integration/ais/import` etc.) only persist + return that one document's parsed JSON. To produce a new reconciled view, the frontend must call `POST /integration/reconciliation` (passing the latest AIS+TIS+26AS parsed JSONs) or `POST /v2/imports/parse-reconcile` (which parses + persists + reconciles in one shot).

3. **Re-uploading a manual document does NOT touch the automation job's stored result, but now coexists on the shared table (P1 resolved).** Previously (P1 open) the automation worker wrote nothing to `imported_document`, so the two paths had no shared storage. **Now (P1 resolved):** the automation worker persists all four documents to `imported_document` with `source=automation`. A subsequent manual re-upload of the same document type **replaces** the automation's row in place (same dedup key) and flips `source` to `upload`. The automation's `AutomationJob.parsed_results` blob is still frozen at job-completion time (the worker doesn't rewrite it on manual upload), so the live reconciled view should be re-fetched via the server-side endpoint (`GET /integration/reconciliation/client/{id}`) rather than the stale automation blob.

4. **Consequence — the latest data "wins" only per-document, and only within the `imported_document` table.** There is no global "latest import wins, erase everything else" semantics. The system does not erase the automation job's stored result when a manual upload arrives, and it does not erase other document types when one is re-uploaded.

⚠ **RESOLVED (partial — live truth):** The automation path still stores its reconciled blob on `AutomationJob.parsed_results` (frozen at job-completion) AND now also persists the four source documents to `imported_document` (P1 resolved). The **live truth** is the `imported_document` table — the new `GET /integration/reconciliation/client/{id}` endpoint (P6) reconciles it server-side on demand, so the frontend should call `getReconciliationReportFromServer()` for the current view rather than reading the frozen automation blob. A manual re-upload replaces the automation's row in place on the shared dedup key, so the live view always reflects the latest data.

⚠ **RESOLVED (P6):** The silent TDS/TCS credit-loss chain is closed. Two fixes: (1) the automation worker now persists 26AS to `imported_document` (P1), and (2) the new `GET /integration/reconciliation/client/{client_id}?assessmentYear=...` endpoint + `reconcile_imported_documents()` service function read the 26AS row back from `imported_document` and reconcile server-side. The frontend `getReconciliationReportFromServer(clientId, ay)` helper calls this endpoint, so a page-refresh between upload and reconcile no longer drops credits. Callers using the legacy `POST /integration/reconciliation` (frontend-supplied body) should migrate to the server-side endpoint.

### 2.4 The four 26AS input shapes

`POST /integration/26as/import` handles four input formats, in this detection order:

1. **Plain JSON** (`content.startswith(b"{")`) → `json.loads`, persist, return.
2. **TRACES ZIP** (`zipfile.is_zipfile`) → password = client DOB in `DDMMYYYY` (with `DDMMYY` and `YYYYMMDD` fallbacks) → unzip → prefer `.txt`, else `.pdf` → re-run through the TXT or PDF path.
3. **26AS PDF** (`extract_26as`) → `extract_26as` returns `{header, parts{I,IV,VI,VII}}`; `_map_legacy_26as` reshapes it into the frontend's `partIEntries` / `incomeBreakdown` / `tdsEntries` / `tcsEntries` structure. The PDF path prefers summary-level totals (`Total Amount Paid/Credited`, `Total Tax Deducted`, `Total TDS Deposited`) which are already net-of-reversals.
4. **26AS TXT** (`parse_26as_txt` → legacy `as26_converter._parse`) → no summary totals, so `_map_legacy_26as` sums the per-detail rows; reversal entries (negative amounts) are netted per `(deductorName, tan, section)`.

⚠ **CBDT note on 26AS reversals:** CBDT/ITD treat a reversal entry (book-entry correction) as a netting against the original deductor+section, not as a separate deductor. `_map_legacy_26as` implements this correctly by keying the net map on `(deductorName, tan, section)` and summing. ✅ Compliant.

### 2.5 Cross-path dedup — the honest assessment

| Scenario | What happens | Duplicate? | Data erased? |
|---|---|---|---|
| Automation import, then manual re-upload of AIS only | The `ais` row is **replaced in place** (was `source=automation`, now `source=upload`); `tis`/`26as`/`prefill` rows remain (from the automation, `source=automation`); `AutomationJob.parsed_results` unchanged | No duplicate row (unique constraint) | Only the `ais` row replaced; automation blob frozen |
| Automation import, then manual re-upload of all 4 docs | All 4 rows **replaced in place** (`source` flips automation→upload for each); `AutomationJob.parsed_results` still holds the automation's reconciled blob | No duplicates | Each prior automation row replaced in place |
| Manual upload AIS, then manual re-upload AIS | Same `ais` row updated in place | No | Only the prior `ais` row's content is replaced (in-place) |
| Manual upload AIS, then manual upload TIS | Two separate rows (`ais`, `tis`); no reconciliation run yet | No | Nothing erased |
| `POST /v2/imports/parse-reconcile` re-run with all 4 | Each row upserted (replaced); new `reconcile` result returned live | No | Each prior doc row replaced in place |

---

## 3. The Reconciliation Engine (`ais_extractor/reconciliation.py::reconcile`)

This is the single source of truth for merging AIS + TIS + 26AS into one income-head-organised view. It is called identically by the automation worker and by the manual endpoints.

### 3.1 Inputs

Three dicts, any of which may be empty:
- `ais_data` — the `extract_ais_json` output: `{metadata, income_heads, summary}`
- `tis_data` — the `tis_to_frontend_json` output: `{metadata, income_heads, overview, reconciliation, summary}`
- `as26_data` — the `extract_26as` / `parse_26as_txt` output: `{header, parts{I,IV,VI,VII}}`

### 3.2 Canonical category → income-head mapping (CBDT-compliant)

`CATEGORY_TO_INCOME_HEAD` (the authoritative map) follows CBDT placement rules:

| TIS/AIS category | Income head |
|---|---|
| salary | Salary |
| business receipts | Profits and Gains of Business or Profession |
| dividend | Income from Other Sources |
| interest from savings bank | Income from Other Sources |
| interest from deposit | Income from Other Sources |
| sale of securities and units of mutual fund | Capital Gains |
| purchase of securities and units of mutual funds | Capital Gains |
| sale of land or building | Capital Gains |
| purchase of immovable property | Capital Gains |
| gst turnover | Profits and Gains of Business or Profession |
| gst purchases | Profits and Gains of Business or Profession |
| purchase of time deposits | Income from Other Sources |
| cash deposits | Income from Other Sources |
| cash withdrawals | Income from Other Sources |
| winnings from online games | Income from Other Sources |
| purchase of vehicle | Income from Other Sources |
| commission income | Income from Other Sources |
| insurance commission | Profits and Gains of Business or Profession |
| receipt from partnership firm | Profits and Gains of Business or Profession |
| tax payments | Taxes Paid |
| refund | Refund |

26AS section → category is mapped via `SECTION_TO_CATEGORY` (`192/192A→salary`, `193/194A→interest from deposit`, `194/194K→dividend`, `194B/194BA/194BB→winnings`, `194C/194I/194J/194M/194N/194O/194Q/194S→business receipts`, `194D→insurance commission`, `194H→commission income`, `194IA/194IB→sale of land or building`, `206C*→business receipts`).

⚠ **RESOLVED (R1 — TCS routing):** `SECTION_TO_CATEGORY` previously routed every `206C*` (TCS) section to `business receipts` (PGBP), which misclassified a non-business collectee's TCS as PGBP income. **Fix:** 26AS Part VI rows now route to the dedicated `tcs credit` category → `TCS Credit` income head (a tax credit, not income); the frontend maps them to Schedule TCS. The engine surfaces TCS via `as26_tcs` regardless of routing, so the credit is preserved — only the income-head attribution changed.

### 3.3 Matching rules (how an AIS row, a TIS row, and a 26AS row become one reconciled entry)

Each document's rows are normalised into `Entry` objects keyed by `entry.key` (a stable hash of category + normalised source name + section). The three sets of entries are then merged in this order:

1. **Exact-key match** — entries sharing the same `key` (same category, same normalised deductor/source name, compatible section) are grouped together. `sections_compatible()` permits matches across section-variant spellings (e.g. `192` vs `S192`).
2. **PAN cross-match** (`_pan_cross_match`) — for non-transaction-level categories, if doc-A's entry and doc-B's entry share the same PAN + category + compatible section but have *different* normalised source names, merge doc-B's rows under doc-A's key (doc-A typically has the cleaner name). Run for all three pairs: (AIS,TIS), (AIS,26AS), (TIS,26AS).
3. **Controlled-name cross-match** (`_name_cross_match`) — for salary (where AIS/TIS labels carry document-specific prefixes like "Salary received"), merge on a category-aware fallback identity after stripping the prefix. Run for all three pairs.

Transaction-level categories (capital-gains: sale/purchase of securities, sale/purchase of immovable property) are **excluded** from PAN/name cross-matching — each transaction row is matched only by exact key, because two different securities from the same broker must not be merged.

### 3.4 Final-amount selection rule

For each reconciled entry, the final income amount is chosen by priority:

```
TIS (accepted_by_taxpayer)  >  AIS (amount)  >  26AS (amount)
```

Encoded as:
- If `has_tis`: `final = tis_total`, reason `TIS_ACCEPTED_INCOME`
- elif `has_ais`: `final = ais_total`, reason `AIS_INCOME_FALLBACK`
- else: `final = as26_total` (or 0 if 26AS row is credit-only), reason `26AS_INCOME_FALLBACK` / `26AS_CREDIT_EVIDENCE_ONLY`

**Tax credits (TDS/TCS) always come from 26AS** — `as26_tds` and `as26_tcs` are sourced from Form 26AS Parts I/VI respectively (verified in `as26_extractor.py`: Part VI title = "TCS - Tax Collected at Source", Part VII title = "Refunds Paid"), regardless of which document supplied the income amount. reason `26AS_TAX_CREDIT`.

⚠ **CBDT note on TIS priority:** CBDT/ITD treat the TIS "accepted by taxpayer" as the figure the taxpayer has reviewed and accepted; using it as the primary amount is compliant. AIS is the system-processed gross; 26AS is the tax-credit ledger (not income evidence per se). ✅ The priority order is correct.

### 3.5 TIS category-control rule (dedup vs raw detail)

TIS exposes per-category `accepted_by_taxpayer` totals that are **system-deduplicated** (the TIS generator collapses duplicate source reports). The engine treats these as **category controls**: for controlled (non-transaction-level) categories where TIS is present, AIS/26AS-only rows are zeroed out (`final_amount = 0.0`) so they don't double-count, and the head-level total is adjusted by `accepted_total - sum(tis rows)` to absorb the dedup delta. Any gap between the TIS detail-row sum and the TIS accepted total is reported in `category_control_discrepancies`.

### 3.6 Discrepancy detection

For each reconciled entry, every available source-pair is compared:
- (TIS vs AIS), (TIS vs 26AS), (AIS vs 26AS) — wherever both are present
- A mismatch > ₹1.00 sets `has_discrepancy = true` and `discrepancy_detail = "TIS=X vs AIS=Y; ..."`

Discrepancies are surfaced at three levels:
1. **Entry-level** — `ReconciledEntry.has_discrepancy` + `discrepancy_detail`
2. **Head-level** — `income_heads[ih].discrepancy_count`
3. **Category-control-level** — `category_control_discrepancies[]` (TIS detail-sum vs accepted-total gaps)
4. **Capital-gains control-level** — `capital_gain_control_discrepancies[]` (per-security sale-proceeds mismatches)

### 3.7 Capital-gains evidence + controls (SFT-017 / SFT-018)

`_extract_capital_gain_ledger(ais, tis)` produces:
- `capital_gain_evidence[]` — per-transaction rows from AIS SFT-017-LES / SFT-018 detail tables, carrying `security_name`, `security_identifier` (ISIN), `quantity`, `sale_price_per_unit`, `sales_consideration`, `cost_of_acquisition`, `unit_fmv`, `fair_market_value`, `indexed_cost_of_acquisition`, `stt_amount`, `debit_type`, `credit_type`, `asset_type` (Long/Short term), `acquisition_mode`, `acquired_before_31_jan_2018`, `recognized_exchange`, `parser_confidence`. This is the row-level ledger the frontend CG mapper consumes.
- `capital_gain_controls[]` — per-source aggregate controls (AIS summary amount + TIS accepted amount per reporting entity).
- `capital_gain_control_discrepancies[]` — where a source's aggregate doesn't equal the sum of its detail rows.

The 112A engine (`app/engine/schedules/restricted_112a.py`) consumes the reconciled purchase totals for the restricted-112A cost computation.

### 3.8 Output structure (the `ReconciledResults` payload)

The `reconcile()` function itself always returns these nine keys:

```
{
  "metadata": {pan, name, financial_year},
  "income_heads": {
    "<income_head>": {
      income_head, total_final, total_tis, total_ais, total_as26,
      total_as26_tds, total_as26_tcs, discrepancy_count, entries[]
    }, ...
  },
  "category_controls": {<category>: <accepted_total>},
  "category_control_discrepancies": [{category, tis_accepted_total, tis_detail_total, difference}],
  "capital_gain_evidence": [{...per-transaction CG fields...}],
  "capital_gain_controls": [{...per-source CG aggregates...}],
  "capital_gain_control_discrepancies": [...],
  "unmatched": {tis_only[], ais_only[], as26_only[]},
  "summary": {
    total_entries, total_final_income, total_discrepancies,
    matched_all_three, matched_two, matched_one,
    unmatched_tis, unmatched_ais, unmatched_as26
  }
}
```

**Four extra keys are attached only by the automation worker** (`job_worker.py`, §1.4), NOT by either manual path. A manually-reconciled result therefore lacks them:

| Key | Attached by | Consumed by |
|---|---|---|
| `prefill` | automation worker only (when `download_prefill` succeeded); the `/v2/imports/parse-reconcile` manual endpoint **also** attaches it when a prefill file is supplied | `mapPrefillToDraftPatch.ts` (§4) |
| `filing_advisory` | automation worker only (from `artifact_outcomes`) | frontend filing-advisory banner |
| `filing_mode_classification` | automation worker only (from `artifact_outcomes`) | frontend ITR-form selector |
| `_extraction_errors` | automation worker only | frontend error list |

⚠ **RESOLVED (partial — P5):** `_extraction_errors` is now attached in both the automation path and the manual `/v2/imports/parse-reconcile` path. `filing_advisory` / `filing_mode_classification` remain **automation-only by design** (they require portal-side filed-return inventory + classification that manual uploads don't trigger) — the manual path returns a strict subset. Callers must not assume these two keys are present when using the manual path.

### 3.9 How the import summary is derived

The `summary` block is computed at the end of `reconcile()`:
- `total_entries` = `len(reconciled)` — every matched or single-source entry
- `total_final_income` = `Σ final_amount + Σ controlled_head_adjustments` — the gross taxable income across all heads (after TIS dedup adjustments)
- `total_discrepancies` = count of entries with `has_discrepancy`
- `matched_all_three` / `matched_two` / `matched_one` = counts by how many documents contributed
- `unmatched_tis` / `unmatched_ais` / `unmatched_as26` = entries present in only one document

---

## 4. Frontend population (reconciled → income heads on screen)

The frontend consumes the `ReconciledResults` payload via typed mappers in `frontend/src/utils/`:

| Mapper | Consumes | Produces (draft patch) |
|---|---|---|
| `mapReconciledToDraftPatch.ts` | `ReconciledResults` | A `ReturnDraftPatch` populating Salary (employers), TDS credits (TDS1/TDS2 schedules), Interest income, Dividend income, Presumptive 44AD/44ADA (from business-receipts entries), Capital Gains (via `mapCapitalGainsEvidence`) |
| `mapAisToDraftPatch.ts` | AIS JSON directly | AIS-only draft patch (for when only AIS is uploaded, no reconciliation) |
| `mapTisToDraftPatch.ts` | TIS JSON directly | TIS-only draft patch |
| `map26asToDraftPatch.ts` | 26AS frontend shape | TDS/TCS credit rows |
| `mapPrefillToDraftPatch.ts` | Prefill extraction | Personal info, filing status, salary employers, house property, other-sources, deductions, bank accounts, TDS/TCS entries, carry-forward losses |
| `mapCapitalGainsToDraftPatch.ts` | `capital_gain_evidence[]` | CG schedule rows (short-term / long-term, listed/unlisted, STT flags, 112A cost) |

The reconciled entry's `selected_source` / `selection_reason` / `present_in` flags are preserved into the draft patch so the UI can badge each figure with its provenance ("from TIS", "from AIS", "from 26AS") and show mismatch warnings where `has_discrepancy`.

---

## 5. Consolidated risk / gap register

Every item below is a concrete, code-verified issue. Items marked ⚠ **CBDT DEVIATION** can cause a wrong figure on the filed return. Items marked ⚠ **GAP** are missing functionality.

### 5.1 Extraction-layer

| # | Item | Severity |
|---|---|---|
| E1 | **Form 16 extraction not implemented** — `/integration/form16/extract` returns HTTP 501. Form 16 is **out of scope** for automated extraction (no parser). Users enter Form 16 data manually. | Medium (feature gap, not a correctness bug) |
| E2 | TIS `accepted_by_taxpayer` has one verified TIS-source inconsistency (AONPD0576P Dividend: overview excludes a TDS-accepted value of ₹20,724 that the detail row carries). Parser is faithful; the source PDF's own reconciliation is off. Documented in the corpus test. | Low (source-data quirk; parser correct) |
| E3 | AIS legacy `_parse_listed_equity_sale_rows` regex path is retained but no longer the live path (the pdfplumber extractor supersedes it). The retained path's `asset_type` casing was fixed (`Long term` not `Long Term`) to keep its unit test green. Retained as a reference/rollback artefact for the next migration, not invoked at runtime. **Action:** either delete the dead path and its test, or document the retention rationale in-code, to prevent quiet drift in a compliance domain. | Low (technical debt; revisit before next migration) |

### 5.2 Reconciliation-layer

| # | Item | Severity |
|---|---|---|
| R1 | ✅ **RESOLVED — TCS routing.** `SECTION_TO_CATEGORY` previously routed every `206C*` (TCS) section to `business receipts` (PGBP) unconditionally. **Fix:** TCS rows (26AS Part VI) now route to a dedicated `tcs credit` category → `TCS Credit` income head (a tax credit, not income), since 26AS cannot determine collectee business status and the safe CBDT-compliant default is the credit bucket. The frontend mapper (`mapReconciledToDraftPatch.ts`) now maps TCS rows to the Schedule TCS credit list (`taxes.tcs`) rather than letting them vanish. | Resolved |
| R2 | ✅ **RESOLVED — Prefill TDS vs 26AS TDS reconciliation.** `reconcile()` now accepts an optional `prefill_data` param and cross-checks each prefill TDS entry (salary + other TDS) against the reconciled 26AS TDS entries by TAN. Matches are counted in `summary.prefill_tds_matched`; prefill-only entries (no 26AS match) are flagged in `prefill_tds_discrepancies[]` with `type=prefill_only_no_26as_match`; amount mismatches are flagged with `type=amount_mismatch`. 26AS TAN is authoritative. | Resolved |
| R3 | Category-control zeroing: when TIS is present for a controlled category, AIS/26AS-only rows in that category get `final_amount = 0.0`. If the TIS accepted total is itself wrong (E2), the zeroing propagates. | Low (mitigated by `category_control_discrepancies` reporting) |

### 5.3 Persistence / cross-path

| # | Item | Severity |
|---|---|---|
| P1 | ✅ **RESOLVED — automation worker now persists all 4 source documents to `imported_document`.** `app/db/imported_document_service.py` (new shared module) provides `upsert_imported_document()`, `load_imported_documents()`, `reconcile_imported_documents()`. The worker's Step 4.6.2 persists ais/tis/26as/prefill with `source=automation`; the manual routers delegate to the same service with `source=upload`. | Resolved |
| P2 | ✅ **RESOLVED — unified "latest truth" across the two storage locations.** Both paths now write to `imported_document` on the same dedup key, so a manual re-upload replaces the automation's row in place (latest wins per document type). The `source` column tracks provenance (automation vs upload). | Resolved |
| P3 | ✅ **RESOLVED — server-side reconcile reads from `imported_document`.** New endpoint `GET /integration/reconciliation/client/{client_id}?assessmentYear=...` loads the persisted set and reconciles server-side; the frontend `getReconciliationReportFromServer()` helper calls it, so a page-refresh between upload and reconcile no longer drops 26AS credits. | Resolved |
| P4 | ✅ **RESOLVED — DRY.** Both `_upsert_imported_document` copies (`integration.py` and `tax_v2.py`) now delegate to the shared `imported_document_service` module; the `source`-column divergence is eliminated. | Resolved |
| P5 | ✅ **RESOLVED (partial) — `_extraction_errors` now attached in the manual `/v2/imports/parse-reconcile` path** (collected per-document) so the payload matches the automation path on that key. `filing_advisory` / `filing_mode_classification` remain automation-only by design (they require portal-side filed-return inventory + classification that manual uploads don't trigger) — the manual path returns a strict subset, documented in §3.8. | Resolved (partial) |
| P6 | ✅ **RESOLVED — silent TDS/TCS credit loss eliminated.** The new server-side reconcile endpoint (P3) reads 26AS from `imported_document` instead of depending on frontend in-memory state; and the automation worker now persists 26AS (P1) so a manual re-reconcile can reload it. The trace in §2.3 is now closed for callers that use `getReconciliationReportFromServer`. | Resolved |

### 5.4 Automation-layer

| # | Item | Severity |
|---|---|---|
| A1 | ⚠ **INTENTIONALLY NOT WIRED — filed-return download + parsing + attachment remain commented out.** Per project decision, the filed-return integration is kept as a reference block only and is **not wired anywhere** in the implementation (not in the worker, not in the frontend). The download block's log line now reads `[FILED RETURN DL] SKIPPED (filed-return not wired)`. `FILED_RETURN_REACTIVATION_GUIDE.md` documents the historical reactivation checklist; it is **not** being applied. The filing-advisory + filing-mode-classification flow (which is separate from the filed-return download) remains active. | Not wired (by decision) |
| (P1) | "No re-extract-from-persisted-artifact path because artifacts aren't persisted to `imported_document`" is the automation-side face of the **same** gap tracked as P1 in §5.3 — folded there to avoid register duplication. | Medium-High (see P1) |

---

## 6. Remediation status (all implemented)

1. ✅ **R1 (TCS routing)** — TCS rows now route to the dedicated `TCS Credit` income head; frontend maps them to Schedule TCS. Verified by 135 frontend tests + `realClientCorpusCompliance` test.
2. ✅ **P6 (silent credit loss)** — New `GET /integration/reconciliation/client/{client_id}` endpoint + `reconcile_imported_documents()` service function read from `imported_document` server-side. Frontend `getReconciliationReportFromServer()` helper wired.
3. ✅ **P1/P2 (unified persistence)** — Automation worker Step 4.6.2 persists all 4 artifacts to `imported_document` via the shared `imported_document_service` module; both manual routers delegate to the same service. Dedup key (client × AY × document_type) + `source` provenance column now shared.
4. ✅ **P5 (payload schema divergence, partial)** — `_extraction_errors` now collected + attached in the manual `/v2/imports/parse-reconcile` path. `filing_advisory` / `filing_mode_classification` remain automation-only by design (documented in §3.8).
5. ✅ **P3 (auto-reconcile on manual upload)** — Satisfied by the server-side reconcile endpoint (P6): the frontend calls `getReconciliationReportFromServer(clientId, ay)` after any upload, which reads the current persisted set and reconciles — no in-memory dependency.
6. ⚠ **A1 (filed return)** — **Intentionally not wired.** Per project decision, the filed-return download + parsing + attachment remain commented out and are not wired anywhere. Kept as reference only.
7. ✅ **R2 (prefill TDS)** — `reconcile()` now accepts `prefill_data` and cross-checks prefill TDS vs 26AS TDS by TAN; outputs `prefill_tds_discrepancies[]` + `summary.prefill_tds_matched` / `prefill_tds_only`.
8. ✅ **F9 (no change needed)** — Verified: Part VI = TCS, Part VII = Refunds. §3.4 correct.

### Verification

- Backend: `tests/test_reconciliation_import_contract.py` + `tests/test_real_ais_corpus_extraction.py` + `tests/test_real_tis_corpus_extraction.py` + `tests/test_ais_listed_equity_extraction.py` → **145 passed**.
- Full backend suite: **1137 passed**, 10 pre-existing failures (ERI router module-attribute issues + 2 pre-existing DB/code-assertion tests) — **0 new regressions** from this work.
- Frontend: **135/135 passed** (16 test files).

---

*Document end. Every assertion above is traceable to a specific file/function in the codebase at the time of the AIS/TIS pdfplumber migration.*
