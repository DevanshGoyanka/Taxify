# Downloads Naming & Status UI

**Date:** 2026-07-24  
**Scope:** Standardised download file naming, abstracted backend logs into user-friendly frontend status, added step-by-step StatusBox component.

---

## 1. Problem Statement

Three issues existed before this change:

1. **Inconsistent file naming** — `downloader_26as.py` used `assessment_year` (e.g. `26AS-2026_27.pdf`) while AIS/TIS used `fiscal_year` (`AIS-2025_26.pdf`). All documents for the same financial year had different filename suffixes.
2. **Raw server logs leaked to frontend** — `status_message` exposed internal tags like `[Worker]`, `[26AS]`, `[Victory]`, making the UI confusing for end users.
3. **No visual progress feedback** — The frontend displayed a single line of monochrome text with no indication of which step was running or how much work remained.

---

## 2. Solution Overview

### 2.1 File Naming Convention

All three documents (26AS, AIS, TIS) now follow a consistent pattern:

```
{downloads}/{client_id}/{fiscal_year}/{PAN}-{DOCTYPE}-{fy_str}.{ext}
```

| Document | Filename | Example |
|---|---|---|
| Form 26AS | `{PAN}-26AS-{fy_str}.pdf` | `AAACT1234A-26AS-2024_25.pdf` |
| 26AS Text  | `{PAN}-26AS-{fy_str}.txt` | `AAACT1234A-26AS-2024_25.txt` |
| AIS        | `{PAN}-AIS-{fy_str}.pdf`  | `AAACT1234A-AIS-2024_25.pdf`  |
| TIS        | `{PAN}-TIS-{fy_str}.pdf`  | `AAACT1234A-TIS-2024_25.pdf`  |
| Form 168   | `{PAN}-168-{ty_str}.pdf`  | `AAACT1234A-168-2024_25.pdf`  |

- `fy_str` = financial year with hyphen replaced by underscore (`2024-25` → `2024_25`).
- All filenames use **financial year**, never assessment year.
- `downloader_26as.py` previously used assessment year — now unified.

### 2.2 Status Message Abstraction

Backend logs remain unchanged on the server (print/log to console), but the value stored in `AutomationJob.status_message` and the `progress_label` sent in the API response is now cleaned:

- `_friendly_status()` maps raw tags like `"Starting browser..."` → `"Launching secure browser…"`.
- `_STEP_PROGRESS` dict maps each `current_step` to a user-facing `label`/`icon`/`pct`.
- The API returns **both**:
  - `status_message` — cleaned, user-friendly
  - `raw_status_message` — original server log (for debugging only)

### 2.3 StatusBox Component

`frontend/src/components/StatusBox.tsx` replaces the old single-line status text with a dedicated progress panel:

- **Progress bar** — animated bar from 0% to 100%, driven by `progress_pct`.
- **Current action** — shows spinner + `progress_label` while running.
- **Step timeline** — dot+icon list of all 7 steps (`login` → `download_26as` → `request_ais` → `download_tis` → `poll_ais` → `unlock` → `logout`), with completed ✅ / current ● / pending ○ markers.
- **Error display** — red box with truncated error message on failure.
- **Elapsed time** — shows when the job started and total duration on completion.
- **✕ dismiss button** — clears the status box after the job finishes.
- Self-contained polling (every 2 s) — the parent page passes `jobId` and callback handlers; the component manages its own poll interval.

---

## 3. Files Changed

### Backend

| File | Change |
|---|---|
| `app/db/models.py` | Added `progress_pct: Mapped[int]` column on `AutomationJob` (default 0). |
| `app/automation/job_worker.py` | Added `_STEP_PROGRESS`, `_STATUS_CLEAN_MAP`, `_friendly_status()`, `_progress_for_step()` helpers. All `_update_job()` calls now include `progress_pct`. `_get_job_dict()` returns `progress_pct`, `progress_label`, `progress_icon`, plus `raw_status_message` for debugging. |
| `app/automation/downloader_26as.py` | Renamed `ay_str` → `fy_str` for consistent financial-year naming. |
| `app/routers/automation.py` | `list_jobs` now includes `progress_pct`. `get_job_status` delegates to updated `_get_job_dict()`. |

### Frontend

| File | Change |
|---|---|
| `frontend/src/api/itrAutomation.ts` | `AutomationJob` interface updated with `progress_pct`, `progress_label`, `progress_icon`, `raw_status_message`. |
| `frontend/src/components/StatusBox.tsx` | **New** — live step-by-step progress component with self-contained polling. |
| `frontend/src/pages/ITRComputationPage.tsx` | Replaced old automation state (`automationStatus`, `automationMessage`, `automationPollRef`) with `showStatusBox` + `StatusBox` component. Removed all manual polling logic. |

---

## 4. Status Progress Mapping

| Step | `current_step` | `progress_pct` | User-Facing Label |
|---|---|---|---|
| 1 | `login` | 5–9 | Signing into ITD portal |
| 2 | `download_26as` | 10–28 | Downloading Form 26AS |
| 3 | `request_ais` | 30–55 | Requesting AIS generation |
| 4 | `download_tis` | — (within request_ais) | Downloading TIS statement |
| 5 | `poll_ais` | 65 | Waiting for AIS generation |
| 6 | `unlock` | 85 | Decrypting PDFs |
| 7 | `logout` | 95 | Signing out |
| — | complete | 100 | All downloads complete |

---

## 5. Database Migration

A new column was added to `automation_job`:

```sql
ALTER TABLE automation_job ADD COLUMN progress_pct INTEGER NOT NULL DEFAULT 0;
```

If using Alembic:
```
alembic revision --autogenerate -m "add progress_pct to automation_job"
alembic upgrade head
```

If using SQLite with auto-create:
- Drop the `automation_job` table or the entire DB and restart (tables are auto-created on startup).

---

## 6. Future Improvements

- **Auto-refresh on completion** — when a job finishes, automatically trigger import of the downloaded files into the form.
- **Download link buttons** — show clickable links to each downloaded file in the StatusBox after completion.
- **Persist status box state** — remember dismissed state so re-opening the page doesn't show old completed jobs.
