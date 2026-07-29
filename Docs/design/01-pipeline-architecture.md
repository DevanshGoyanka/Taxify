# Automation Pipeline Architecture

**Status:** Approved  
**Date:** 2025-07-19  
**Author:** Codebase discovery pass

---

## 1. Current State (What Exists)

### 1.1 Browser Automation (`app/automation/`)

| Module | Responsibility | Entry Point | Wired to API? |
|---|---|---|---|
| `browser.py` | Chromium lifecycle (singleton `BrowserManager`), proxy detection, anti-detection init scripts | `browser_manager.get_context()` | **No** |
| `auth.py` | ITD login: PAN → SAM checkbox → password → dashboard | `login_itd(user_id, password, log_callback, context)` | **No** |
| `downloader_ais_tis.py` | Phase 1 (request AIS generation) + Phase 2 (poll Activity History → download) | `run_request_ais()`, `run_download_ais_tis()` | **No** |
| `downloader_26as.py` | TRACES portal: 26AS PDF + TXT (ZIP) download | `download_26as(page, ay, download_dir, log, pan, dob)` | **No** |
| `pdf_unlocker.py` | Strip ITD password from AIS/TIS/26AS PDFs using PAN+DOB | `unlock_pdf(file_path, pan, dob)` | Import endpoints use it |
| `errors.py` | Friendly error messages from Playwright exceptions | `_friendly_error(raw)` | **No** |

**Key finding:** The browser automation is a fully-built but **unconnected subsystem**. `run_request_ais()` and `run_download_ais_tis()` take a logged-in Playwright `Page`, click through the AIS portal, handle the "large file queued" vs "instant download" path, and return structured result dicts. But nothing in `app/routers/` calls them.

### 1.2 Document Extraction (`ais_extractor/`)

| Module | Input | Output | Used By |
|---|---|---|---|
| `extractor.py` | AIS PDF (unlocked) | Nested JSON: `{income_heads: {Salary: {entries: [...]}, ...}}` | `POST /api/v1/imports/ais` |
| `tis_extractor.py` | TIS PDF (unlocked) | Nested JSON: `{income_heads: {...}}` with `accepted_by_taxpayer` amounts | `POST /integration/tis/import` |
| `as26_extractor.py` | 26AS PDF (unlocked) | JSON: `{parts: {I: {rows: [...]}, VI: {...}, ...}}` | `POST /integration/26as/import` (PDF path) |
| `reconciliation.py` | AIS JSON + TIS JSON + 26AS JSON | `{income_heads: {Salary: {entries: [ReconciledEntry], total_final, discrepancies}}}` | `POST /integration/reconciliation` |

### 1.3 Tax Engine (`app/engine/`)

- **ITR-1**: `app/engine/calculators/itr1.py::compute(ITR1Input) → ITR1Result` — full salary, HP, OS, 112A CG, deductions, slab tax, rebate, surcharge, cess, interest, TDS credit
- **ITR-4**: `app/engine/calculators/itr4.py::compute(ITR4Input) → ITR4Result` — adds presumptive business income
- **ITR-3**: `app/engine/calculators/itr3.py::compute(ITR3Input) → ITR3Result` — full business + capital gains
- **Schedules**: `salary.py`, `house_property.py`, `other_sources.py`, `presumptive.py`, `special_rates.py`, `deductions/`, `loss_setoff/`, `tds_tcs/`

### 1.4 Frontend Import Flow (Current)

The Import dropdown on `ITRComputationPage.tsx` has 6 file type options:
1. **ITD Prefill JSON** → `POST /integration/prefill/import`
2. **Form 26AS (TXT/ZIP)** → `POST /integration/26as/import`
3. **Form 26AS (PDF)** → `POST /integration/26as/import`
4. **AIS (PDF)** → `POST /api/v1/imports/ais`
5. **AIS (JSON)** → `POST /integration/ais-json/import`
6. **TIS (PDF)** → `POST /integration/tis/import`

Each import returns parsed JSON → frontend merges into `formData` state → calls `POST /tax-summary/compute` for tax computation.

### 1.5 What's NOT Wired

| Capability | Backend Exists? | Frontend Exists? | Connected? |
|---|---|---|---|
| Login to ITD portal | ✅ `auth.py::login_itd()` | ❌ No UI | ❌ |
| Download AIS from ITD portal | ✅ `downloader_ais_tis.py` | ❌ No UI | ❌ |
| Download TIS from ITD portal | ✅ `downloader_ais_tis.py` | ❌ No UI | ❌ |
| Download 26AS from TRACES | ✅ `downloader_26as.py` | ❌ No UI | ❌ |
| Request AIS generation (large file) | ✅ `run_request_ais()` | ❌ No UI | ❌ |
| Poll Activity History for completed AIS | ✅ `download_ais_from_activity_history()` | ❌ No UI | ❌ |
| Unlock downloaded PDFs | ✅ `pdf_unlocker.py` | N/A | ⚠️ Only from import endpoints, not from automation |
| Run reconciliation | ✅ `reconciliation.py` | ⚠️ Called from `handleFileImport` for AIS+26AS | ⚠️ Only works when both files manually imported |
| Form 16 extraction | ❌ **MOCK ONLY** (`POST /integration/form16/extract` returns hardcoded TCS data) | ✅ Menu entry exists | ❌ |

---

## 2. Design Decisions

### 2.1 Concurrency Model: Serial Background Worker

**Decision:** Single in-process asyncio task processing automation jobs sequentially.

One browser context = one ITD login session. After each client's downloads complete, the session is logged out and the context is disposed. A new context is created for the next job.

**Rationale:**
- ITD portal enforces one active session per PAN; multiple browser contexts could trigger account locks
- Browser resource contention (Playwright + Chromium memory) is avoided
- Simplified error handling — no concurrent session management

**Future upgrade path:** If parallel processing becomes necessary, upgrade to a bounded semaphore (e.g., 3 concurrent browser contexts for 3 different PANs). Start with 1.

### 2.2 Job State Storage: DB Table + In-Memory Queue

**Decision:** New `automation_jobs` DB table for persistent state + in-memory `asyncio.Queue` for the worker.

Jobs lost on server restart is acceptable for v1. The DB table records job progress for the frontend to poll and serves as an audit trail. On startup, the worker starts with an empty in-memory queue — any `queued` jobs from before the restart remain in the DB as orphaned and the frontend shows them as stale.

**Proposed schema:**

```python
# app/db/models/automation_job.py
class AutomationJob(Base):
    __tablename__ = "automation_jobs"

    id: int (PK, auto)
    client_id: int (FK → clients)
    user_id: int (FK → users)
    job_type: str          # "DOWNLOAD_ALL" | "DOWNLOAD_AIS_TIS" | "DOWNLOAD_26AS" | "REQUEST_AIS"
    status: str            # "queued" | "running" | "completed" | "failed" | "cancelled"
    fiscal_year: str       # "2024-25"
    
    # Progress tracking
    steps_completed: list[str]   # JSON: ["login", "26as_downloaded", "ais_requested"]
    current_step: str | None     # "downloading_tis"
    status_message: str | None   # human-readable, shown in UI
    
    # Results
    files_downloaded: dict       # JSON: {"26as": "/path/...", "ais": None, "tis": "/path/..."}
    ais_ref_id: str | None       # For large-file AIS: reference ID from Activity History
    error_message: str | None
    
    # Timestamps
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    
    # Retry
    attempt_count: int (default 0)
    max_attempts: int (default 3)
```

### 2.3 Download Directory

**Decision:** `downloads/{client_id}/{fy}/` — no configurable prefix for v1.

Files go under the project root in a `downloads/` directory, organized by client ID and fiscal year. The worker creates directories as needed.

### 2.4 ITD Portal Password

**Decision:** Per-client, stored encrypted on the `Client` model.

The `app/security/portal_crypto.py` module provides `encrypt_portal_password()` / `decrypt_portal_password()`. The `Client` model needs a `portal_password` column (encrypted text). The worker decrypts it at job start time.

---

## 3. Full Pipeline Sequence

### Phase 0 — Client Setup
1. User creates client via UI → `POST /clients` → stores PAN, DOB, ITD password in DB
2. User navigates to client's ITR page for a specific AY

### Phase 1 — Initiate Automation (user clicks "Auto-Download from ITD")

1. Frontend calls `POST /automation/jobs {client_id, fiscal_year, job_type: "DOWNLOAD_ALL"}`
2. Backend creates `AutomationJob` row (status="queued"), enqueues job in asyncio queue
3. Worker picks up job → sets status="running"
4. Worker calls `BrowserManager.get_context()` → launches Chromium
5. Worker decrypts `client.portal_password`, calls `login_itd(client.pan, password, log, context)` → returns `Page`
6. Worker calls `download_26as(page, ay, download_dir, log, client.pan, client.dob)` → saves 26AS PDF + TXT to `downloads/{client_id}/{fy}/`
7. Worker calls `pdf_unlocker.unlock_pdf(26as_pdf_path, ...)` → unlocks PDF
8. Worker calls `run_request_ais(page, fy, download_dir, log, client.pan, client.dob)` → either:
   - **Small AIS:** instant download + unlock → `ais: {status: "downloaded"}`
   - **Large AIS:** queued on ITD servers → `ais: {status: "requested", ref_id: "REF123"}`
9. If AIS was downloaded: worker calls `ais_extractor.extractor.extract_ais_pdf(ais_pdf_path)` → stores parsed JSON
10. Worker calls `download_tis()` (inside `run_request_ais`) → TIS always instant → unlock → parse
11. Worker calls `logout_itd(page)` → closes browser context
12. Updates `AutomationJob`: status="completed", files_downloaded, etc.

### Phase 1b — Poll for Large AIS (if AIS was queued)

1. Worker checks if `ais_ref_id` is set and AIS not yet downloaded
2. Worker waits (polling interval: 30s, max 10min)
3. Worker re-logins, calls `download_ais_from_activity_history(page, fy, download_dir, log, pan, dob, ref_id=ref_id, should_continue=...)`
4. On success: unlock + parse + update job

### Phase 2 — Parse & Reconcile (automatically after Phase 1)

1. Backend parses all downloaded files:
   - `ais_extractor.extractor.extract_ais_pdf(ais_pdf_path)` → AIS JSON
   - `ais_extractor.tis_extractor.extract_tis_pdf(tis_pdf_path)` → TIS JSON
   - `ais_extractor.as26_extractor.extract_26as_pdf(26as_pdf_path)` → 26AS JSON
2. Backend calls `reconciliation.reconcile(ais_json, tis_json, as26_json)` → unified view
3. Stores reconciliation result on the job
4. Frontend polls `GET /automation/jobs/{id}` → receives reconciliation data

### Phase 3 — Auto-Populate Form (triggered by frontend)

1. Frontend receives reconciliation result
2. Transforms entries into `formData` (same logic as existing `handleFileImport` lines 419–600)
3. Calls `itrApi.saveFormData(clientId, year, populatedFormData)`
4. Calls `itrApi.computeTaxSummary(formData, ay, regime)` → tax computation displayed

---

## 4. Component Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                        FRONTEND                                   │
│  ITRComputationPage                                               │
│  ┌─────────────┐   ┌──────────────────┐   ┌──────────────────┐  │
│  │ Auto-Download│   │ Import (manual)  │   │ Job Status Card  │  │
│  │   Button     │   │   Dropdown       │   │  (polling)       │  │
│  └──────┬───────┘   └────────┬─────────┘   └────────┬─────────┘  │
│         │                    │                      │             │
└─────────┼────────────────────┼──────────────────────┼────────────┘
          │                    │                      │
          ▼                    ▼                      ▼
┌──────────────────────────────────────────────────────────────────┐
│                        API LAYER (FastAPI)                        │
│                                                                    │
│  POST /automation/jobs          (create + enqueue)                │
│  GET  /automation/jobs/{id}     (poll status)                     │
│  GET  /automation/jobs          (list by client)                  │
│  POST /automation/jobs/{id}/cancel                                │
│                                                                    │
│  Existing:                                                        │
│  POST /api/v1/imports/ais       (upload AIS JSON)                 │
│  POST /integration/26as/import  (upload 26AS TXT/PDF)             │
│  POST /integration/tis/import   (upload TIS PDF)                  │
│  POST /integration/reconciliation (reconcile 3 docs)              │
│  POST /tax-summary/compute      (tax computation)                 │
└──────────────────────────────────────────────────────────────────┘
          │
          ▼
┌──────────────────────────────────────────────────────────────────┐
│                    JOB WORKER (asyncio task)                      │
│                                                                    │
│  while True:                                                      │
│      job = queue.get()                                            │
│      try:                                                         │
│          ctx = await browser_manager.get_context()                │
│          page = await login_itd(pan, pwd, log, ctx)               │
│          await download_26as(page, ay, dir, log, pan, dob)        │
│          await run_request_ais(page, fy, dir, log, pan, dob)      │
│          if ais_queued:                                           │
│              await poll_activity_history(...)                      │
│          await logout_itd(page)                                   │
│          await parse + reconcile all files                        │
│          mark job completed                                        │
│      except Exception:                                            │
│          mark job failed, schedule retry if attempts < max        │
└──────────────────────────────────────────────────────────────────┘
          │                    │                    │
          ▼                    ▼                    ▼
┌──────────────┐  ┌──────────────────┐  ┌──────────────────────┐
│ automation/  │  │ ais_extractor/   │  │ app/engine/          │
│ browser.py   │  │ extractor.py     │  │ calculators/itr1.py  │
│ auth.py      │  │ as26_extractor.py│  │ schedules/           │
│ downloader*.py│ │ tis_extractor.py │  │ slab_tax.py          │
│ pdf_unlocker │  │ reconciliation.py│  │ rebate.py etc.       │
└──────────────┘  └──────────────────┘  └──────────────────────┘
```

---

## 5. What's Missing (Gap Analysis)

| # | Gap | Priority | Effort |
|---|---|---|---|
| 1 | **No API endpoints for automation** — `POST /automation/jobs`, `GET /automation/jobs/{id}`, `GET /automation/jobs?client_id=X` | **P0** | 2 days |
| 2 | **No job queue/worker** — Need in-process asyncio queue + worker that owns browser lifecycle | **P0** | 2 days |
| 3 | **No `AutomationJob` DB model** — Need migration + model + CRUD | **P0** | 1 day |
| 4 | **`portal_password` on Client model** — `Client` needs encrypted password column; `portal_crypto.py` already exists | **P0** | 0.5 day |
| 5 | **No frontend "Auto-Download" button** — ITRComputationPage has manual Import dropdown but no automated download trigger | **P0** | 1 day |
| 6 | **No job status polling on frontend** — Need a progress card/panel that polls `GET /automation/jobs/{id}` | **P0** | 1.5 days |
| 7 | **Form 16 extraction is a MOCK** — Returns hardcoded TCS data, not real PDF parsing | P1 | 3 days |
| 8 | **No error recovery / retry** — Browser crash mid-download loses all progress. Need resume from last completed step | P1 | 2 days |
| 9 | **No file lifecycle management** — Downloaded files need cleanup, deduplication, and organization. Currently ad-hoc. | P2 | 1 day |
| 10 | **No notification when download completes** — User has to manually refresh. Need toast/websocket on job completion. | P1 | 1 day |

---

## 6. Implementation Sequence

### Milestone 1 — Core Plumbing (3 days)
1. Add `portal_password` column to `Client` model + migration
2. Create `AutomationJob` DB model + migration
3. Create `POST /automation/jobs` + `GET /automation/jobs/{id}` + `GET /automation/jobs` endpoints
4. Implement in-process asyncio job queue + worker
5. Wire worker to call existing `login_itd` → `download_26as` → `run_request_ais` → `run_download_ais_tis`
6. Store results in AutomationJob

### Milestone 2 — Frontend Integration (2 days)
1. Add "Auto-Download" button to ITRComputationPage (near Import dropdown)
2. Add job status card with progress polling (interval: 2s)
3. On completion: auto-trigger parse → reconcile → populate form → compute tax

### Milestone 3 — Polish (2 days)
1. Handle large-file AIS polling in background
2. Error recovery / retry
3. Form 16 extraction (real implementation)

---

## 7. New API Endpoints

### `POST /automation/jobs`

Create and enqueue an automation job.

```
Request:
{
    "client_id": int,
    "fiscal_year": str,        // "2024-25"
    "job_type": str            // "DOWNLOAD_ALL" | "DOWNLOAD_AIS_TIS" | "DOWNLOAD_26AS"
}

Response: 201
{
    "id": int,
    "client_id": int,
    "status": "queued",
    "fiscal_year": "2024-25",
    "job_type": "DOWNLOAD_ALL",
    "created_at": "2025-07-19T..."
}
```

### `GET /automation/jobs/{id}`

Poll job status.

```
Response: 200
{
    "id": int,
    "status": "running" | "completed" | "failed" | "cancelled",
    "steps_completed": ["login", "26as_downloaded"],
    "current_step": "downloading_tis",
    "status_message": "Downloading TIS PDF...",
    "files_downloaded": {"26as": "/path/...", "ais": null, "tis": null},
    "result": { ... reconciliation JSON, only when completed },
    "error_message": null,
    "created_at": "...",
    "started_at": "...",
    "completed_at": null
}
```

### `GET /automation/jobs`

List jobs for a client.

```
Query params: ?client_id=X&status=completed&limit=10

Response: 200
{
    "jobs": [ { ... job summary ... } ]
}
```

### `POST /automation/jobs/{id}/cancel`

Cancel a queued or running job.

```
Response: 200
{
    "id": int,
    "status": "cancelled"
}
```
