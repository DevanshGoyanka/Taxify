# Backend Automation Job System

## Overview

The automation job system runs ITD (Income Tax Department) portal downloads in the background via Playwright. A **POST endpoint** enqueues a job; a **serial background worker** processes one job at a time; a **GET endpoint** polls for progress.

```
POST /clients/{id}/automation/import   -- enqueue
GET  /automation/jobs/{job_id}         -- poll
GET  /automation/jobs                  -- list
```

---

## System Design

### Architecture

```
┌─────────────┐     POST /clients/{id}/automation/import     ┌──────────────────┐
│  Frontend   │ ──────────────────────────────────────────> │  FastAPI Router  │
│  (Next.js)   │ <────────── { job_id, status:"queued" } ── │  automation.py   │
└─────────────┘                                              └────────┬─────────┘
                                                                     │
                                                           saves AutomationJob row
                                                           enqueues job_id
                                                                     │
                                                                     v
┌─────────────┐     GET /automation/jobs/{job_id}          ┌──────────────────┐
│  Frontend   │ ──────────────────────────────────────────> │  FastAPI Router  │
│  (polling)  │ <── { status, steps_completed, files, ... } │  automation.py   │
└─────────────┘                                              └────────┬─────────┘
                                                                     │
                                                                     │ reads AutomationJob
                                                                     v
                                                           ┌──────────────────┐
                                                           │   job_worker.py  │
                                                           │  (asyncio loop)  │
                                                           └────────┬─────────┘
                                                                    │
                                                             _run_job(job_id)
                                                                    │
                                                       ┌────────────┼────────────┐
                                                       v            v            v
                                                 login_itd  download_26as  run_request_ais
                                                       │            │            │
                                                       v            v            v
                                                   ITD Portal    TRACES     AIS/TIS Portal
                                                   (Playwright   (PDF+TXT)  (PDF)
                                                    Chromium)
```

### Key design decisions

| Decision | Rationale |
|---|---|
| **Serial execution** | One Playwright browser handles one job at a time. No concurrency — avoids race conditions with portal sessions and prevents rate-limiting/account locking. |
| **Async queue with `asyncio.Queue`** | Fits naturally into FastAPI's async event loop. Jobs wait in FIFO order. |
| **DB as state sink** | `AutomationJob` row is updated in real-time by the worker. The poll endpoint reads directly from it. No in-memory state to lose on restart. |
| **Fresh DB sessions per update** | The worker operates outside of request-scoped FastAPI sessions. Uses `SessionLocal()` for each read/write — avoids stale session issues. |
| **Shared navigation and ownership** | ITD menu navigation, overlay waits, popup/same-tab redirect races, and external-page cleanup use common deadline-bounded helpers. Only owned child tabs are closed; same-tab redirects restore the authenticated ITD anchor. |
| **Explicit AY/FY semantics** | Jobs persist both the requested assessment year and its derived financial year. TRACES receives AY; AIS/TIS and filenames use FY. |

---

## Database Schema

### `automation_job` table

| Column | Type | Purpose |
|---|---|---|
| `id` | INTEGER PK | Auto-increment job ID |
| `client_id` | INTEGER FK → client.id | Which client |
| `user_id` | INTEGER FK → user.id | Ownership for access control |
| `job_type` | VARCHAR(30) | `DOWNLOAD_ALL`, `DOWNLOAD_AIS_TIS`, `DOWNLOAD_26AS` |
| `status` | VARCHAR(20) | `queued` → `running` → `completed` / `failed` / `cancelled` |
| `assessment_year` | VARCHAR(10), nullable for migration compatibility | Requested AY used by TRACES (e.g. `2026-27`); legacy rows are additively backfilled from FY |
| `fiscal_year` | VARCHAR(10) | Derived FY used by AIS/TIS and filenames (e.g. `2025-26`) |
| `steps_completed` | TEXT (JSON list) | e.g. `["login", "26as_downloaded", "ais_downloaded", "tis_downloaded", "logout"]` |
| `current_step` | VARCHAR(100) | What the worker is doing right now |
| `status_message` | VARCHAR(500) | Live human-readable progress |
| `files_downloaded` | TEXT (JSON object) | Validated final artifact paths; Phase 2 adds `prefill` without auto-importing it |
| `artifact_outcomes` | TEXT (JSON object) | Structured per-artifact status such as Prefill `downloaded`, `no_data`, or `validation_failed` |
| `ais_ref_id` | VARCHAR(50) | AIS reference ID from the portal (used for Phase 2 polling) |
| `error_message` | VARCHAR(1000) | Friendly error + full traceback on failure |
| `created_at` | DATETIME | When the job was created |
| `started_at` | DATETIME | When the worker picked it up |
| `completed_at` | DATETIME | When it finished (success or failure) |
| `attempt_count` | INTEGER | How many times this job was attempted |
| `max_attempts` | INTEGER | Max retries allowed (default 3) |

---

## API Endpoints

### POST `/clients/{client_id}/automation/import`

Start an automation job.

**Query parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `assessment_year` | string | `2026-27` | Strict contiguous AY; persisted directly and converted to FY internally |
| `job_type` | string | `DOWNLOAD_ALL` | `DOWNLOAD_ALL` \| `DOWNLOAD_AIS_TIS` \| `DOWNLOAD_26AS` |

**Auth:** Bearer token (must own the client)

**Preconditions:**
- Client must exist and belong to the authenticated user
- Client must have `portal_password` set (AES-256-GCM encrypted)

**Response (200):**
```json
{
  "job_id": 42,
  "status": "queued",
  "assessment_year": "2026-27",
  "fiscal_year": "2025-26",
  "download_dir": "D:\\Taxify\\Taxify\\downloads\\2\\2024-25",
  "message": "Automation job created and queued. Poll GET /automation/jobs/{job_id} for progress."
}
```

**Errors:**
- `404` — Client not found
- `400` — Client missing portal_password

---

### GET `/automation/jobs/{job_id}`

Poll job status.

**Auth:** Bearer token (must own the job)

**Response for running job:**
```json
{
  "id": 42,
  "client_id": 2,
  "user_id": 1,
  "job_type": "DOWNLOAD_ALL",
  "status": "running",
  "assessment_year": "2026-27",
  "fiscal_year": "2025-26",
  "steps_completed": ["login"],
  "current_step": "download_26as",
  "status_message": "Downloading Form 26AS...",
  "files_downloaded": {},
  "ais_ref_id": null,
  "error_message": null,
  "created_at": "2026-07-23T16:00:00",
  "started_at": "2026-07-23T16:00:01",
  "completed_at": null,
  "attempt_count": 1,
  "max_attempts": 3
}
```

**Response for completed job:**
```json
{
  "status": "completed",
  "steps_completed": ["login", "26as_downloaded", "ais_downloaded", "tis_downloaded", "logout"],
  "current_step": null,
  "status_message": "All downloads complete",
  "files_downloaded": {
    "26as": "D:\\Taxify\\Taxify\\downloads\\2\\2024-25\\AAACT1234A-26AS-2024_25.pdf",
    "ais": "D:\\Taxify\\Taxify\\downloads\\2\\2024-25\\AAACT1234A-AIS-2024_25.pdf",
    "tis": "D:\\Taxify\\Taxify\\downloads\\2\\2024-25\\AAACT1234A-TIS-2024_25.pdf"
  }
}
```

**Response for failed job:**
```json
{
  "status": "failed",
  "current_step": null,
  "status_message": "Failed: PAN does not exist on the ITD portal...",
  "error_message": "PAN does not exist on the ITD portal...\n\n--- Full traceback ---\n..."
}
```

---

### GET `/automation/jobs`

List jobs for the authenticated user.

**Query parameters:**

| Parameter | Type | Description |
|---|---|---|
| `client_id` | int | Filter by client |
| `status` | string | Filter by status |
| `limit` | int | Max results (default 20, max 100) |

**Response:**
```json
{
  "jobs": [
    {
      "id": 42,
      "client_id": 2,
      "job_type": "DOWNLOAD_ALL",
      "status": "completed",
      "assessment_year": "2026-27",
  "fiscal_year": "2025-26",
      "current_step": null,
      "status_message": "All downloads complete",
      "error_message": null,
      "created_at": "2026-07-23T16:00:00",
      "started_at": "2026-07-23T16:00:01",
      "completed_at": "2026-07-23T16:02:30"
    }
  ]
}
```

---

## Job Lifecycle

```
           POST
            │
            v
        ┌────────┐
        │ queued │  <-- row inserted, job_id enqueued
        └───┬────┘
            │  worker picks up
            v
        ┌─────────┐
        │ running │  <-- started_at set, current_step updated live
        └────┬────┘
             │
      ┌──────┴──────┐
      v              v
  ┌───────────┐  ┌────────┐
  │ completed │  │ failed │  <-- completed_at set, files populated or error stored
  └───────────┘  └────────┘
```

**Download steps in order:**
1. `login` — Playwright login to ITD portal with PAN + decrypted portal password
2. `download_26as` — Navigate to TRACES, download PDF + TXT, unlock PDF with DOB
3. `request_ais` — Open AIS tab, request AIS PDF generation (+ download TIS)
4. (if AIS queued) `poll_ais` — Poll Activity History until AIS PDF ready, then download
5. `logout` — Clean ITD portal logout

**PDF unlock (post-download):**
Each downloaded PDF is unlocked via `pikepdf` using DOB-based password candidates (format: DDMMYYYY). If unlock fails, the PDF is kept encrypted but the job is still marked `completed` — a warning is logged.

---

## Frontend Integration

### How to trigger a job

```typescript
// POST to start, get job_id back
const res = await fetch(
  `/api/clients/${clientId}/automation/import?assessment_year=${ay}`,
  { method: 'POST', headers: { Authorization: `Bearer ${token}` } }
);
const { job_id } = await res.json();

// Poll every 2 seconds until done
const interval = setInterval(async () => {
  const pollRes = await fetch(`/api/automation/jobs/${job_id}`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  const job = await pollRes.json();
  
  if (job.status === 'completed' || job.status === 'failed') {
    clearInterval(interval);
    // Update UI with job.files_downloaded or job.error_message
  }
  // Show job.status_message in progress UI
  setStatusMessage(job.status_message);
}, 2000);
```

### Download directory

Files land in: `{project_root}/downloads/{client_id}/{fiscal_year}/`

Example: `D:\Taxify\Taxify\downloads\2\2024-25\AAACT1234A-26AS-2024_25.pdf`

---

## Files Created / Modified

| File | Change |
|---|---|
| `app/db/models.py` | Added `AutomationJob` model (rewrote entire file for cleanliness) |
| `app/automation/job_worker.py` | **New** — serial async queue worker |
| `app/routers/automation.py` | **New** — POST + GET endpoints |
| `app/main.py` | Added `automation_router`, `start_worker`/`stop_worker` in lifespan |
| `app/routers/clients.py` | Fixed import: `app.security.portal_crypto` → `app.schemas.security.portal_crypto` |

---

## Security Notes

- **Portal passwords** are stored AES-256-GCM encrypted (key from `PORTAL_ENCRYPTION_KEY` env var)
- **Access control**: Jobs are scoped to `user_id`. Polling a job you don't own returns 403.
- **No credentials in logs**: PAN is partially redacted in auth logs
- **Terminal diagnostics are value-free**: Input values and page URLs are omitted; only control metadata is recorded after terminal login failure.
- **Owned-page cleanup**: TRACES/AIS child tabs are closed only when opened by the downloader. Same-tab redirects restore the original ITD anchor in the same authenticated context.
- **Single elapsed navigation budgets**: frame scans and popup/same-tab races share global monotonic deadlines instead of multiplying full waits by selector, frame, or navigation outcome.
- **Explicit year validation**: malformed and non-contiguous AY values are rejected with HTTP 422 before a job is created.
- **Browser cleanup**: the worker closes its authoritative page and context in `finally` — no orphan Chromium processes.

---

## Phase 0 Runtime and Timing Baseline

Start the backend with the standard, GIL-enabled Python interpreter:

```powershell
py -3.14 run.py
```

The launcher rejects free-threaded Python and reports missing `PyMuPDF` or `pikepdf` dependencies before the server starts.

Automation logs now include credential-safe monotonic events:

```text
[Timing] context requested total=0.000s delta=0.000s
[Timing] context ready total=1.250s delta=1.250s
[Timing] login page requested total=1.251s delta=0.001s
[Timing] login page ready total=3.500s delta=2.249s
[Timing] PAN submitted total=6.000s delta=2.500s
[Timing] SAM ready total=7.200s delta=1.200s
[Timing] password submitted total=8.100s delta=0.900s
[Timing] dashboard ready total=12.400s delta=4.300s
```

Timing labels come from a fixed allowlist and never include PAN, password, taxpayer name, portal response body, dynamic URL, or document contents. Alternative semantic selectors share one total elapsed deadline, preventing timeout multiplication when controls are absent.
