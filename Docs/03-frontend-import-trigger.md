# 03 — Frontend Import Trigger

**Date:** 2026-07-23  
**Status:** Complete (pending Playwright event-loop fix)  
**Depends on:** docs/design/01-pipeline-architecture.md, docs/02-backend-automation-job.md

---

## 1. What Was Built

Added an "Import from Portal" option to the existing Import dropdown on `ITRComputationPage.tsx`. When clicked, it kicks off a background ITD portal automation job on the backend, then polls for progress and displays live status to the user.

---

## 2. Files Touched

| File | Change |
|---|---|
| `frontend/src/api/itrAutomation.ts` | Already existed — defines `itrAutomationApi.startImport()` and `itrAutomationApi.getJobStatus()` using `axiosInstance` |
| `frontend/src/pages/ITRComputationPage.tsx` | Added 4 new state hooks, import-from-portal handler, setInterval-based polling, cleanup on unmount, disable-in-flight logic, and a live status indicator bar |
| `run.py` | **New** — standalone entry point that sets `WindowsSelectorEventLoopPolicy` before uvicorn imports asyncio (required for Playwright on Windows) |

---

## 3. How Each Requirement Was Met

### 3.1 — "Import from Portal" in the existing dropdown (same UI pattern)

A new `<div>` entry was added as the **first child** of the dropdown menu, before the existing "ITD Prefill JSON" label. It uses the same styling (padding, font-size, borderTop) as the other entries so it blends natively.

```tsx
<div
  onClick={handleImportFromPortal}
  style={{
    display: 'block',
    padding: '8px 12px',
    fontSize: 12,
    cursor: automationJobId && (automationStatus === 'running' || automationStatus === 'queued')
      ? 'not-allowed' : 'pointer',
    opacity: automationJobId && (automationStatus === 'running' || automationStatus === 'queued')
      ? 0.5 : 1,
    pointerEvents: automationJobId && (automationStatus === 'running' || automationStatus === 'queued')
      ? 'none' : 'auto',
  }}
>
  Import from Portal
</div>
```

### 3.2 — Calls POST /clients/{id}/automation/import via existing axios pattern

The `itrAutomationApi` module (at `frontend/src/api/itrAutomation.ts`) was already present. It uses the existing `axiosInstance` with automatic JWT auth injection:

```typescript
const res = await itrAutomationApi.startImport(Number(clientId), ayParam || '2025-26');
```

That calls `POST /clients/{clientId}/automation/import` with `assessment_year` and `job_type=DOWNLOAD_ALL` query params.

### 3.3 — Status indicator via setInterval polling

Four state variables track the job:

```typescript
const [automationJobId, setAutomationJobId] = useState<number | null>(null);
const [automationStatus, setAutomationStatus] = useState<string | null>(null);
const [automationMessage, setAutomationMessage] = useState<string | null>(null);
const automationPollRef = useRef<ReturnType<typeof setInterval> | null>(null);
```

The polling logic (inside `handleImportFromPortal`):

1. Sets `automationStatus = 'queued'` immediately
2. Calls `startImport(…)` → gets `job_id`
3. Sets `automationJobId` and `automationStatus = 'running'`
4. Creates a `setInterval` that calls `getJobStatus(job_id)` every 2 seconds
5. On each poll, sets `automationStatus` + `automationMessage` from the response
6. On `completed` or `failed`: clears the interval, updates final message
7. Cleanup on unmount via a separate `useEffect`:

```typescript
useEffect(() => {
  return () => {
    if (automationPollRef.current) {
      clearInterval(automationPollRef.current);
    }
  };
}, []);
```

**Status messages the user sees:**

| State | Display |
|---|---|
| Post-click, pre-API | "Starting automation…" |
| API responded, job queued | `[Spinner] Running — Downloading Form 26AS…` |
| …continues up to… | `[Spinner] Running — All downloads complete` |
| Success | Green toast: "Portal import complete — 26AS, AIS, and TIS downloaded." |
| Failure | Red text under header: "Failed — PAN does not exist on the ITD portal…" |

A thin status bar renders **between the header and the tab bar** while a job is in-flight:

```tsx
{automationStatus && automationStatus !== 'completed' && (
  <div style={{
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    padding: '0 0 8px 34px',
    fontSize: 12,
    color: automationStatus === 'failed' ? 'var(--danger)' : 'var(--text-secondary)',
  }}>
    {(automationStatus === 'running' || automationStatus === 'queued') && <Spinner size={14} />}
    {automationStatus === 'running' && 'Running — '}
    {automationStatus === 'queued' && 'Queued — '}
    {automationStatus === 'failed' && 'Failed — '}
    {automationMessage || automationStatus}
  </div>
)}
```

### 3.4 — Disable during flight (no double-fire)

Two guards prevent duplicate jobs:

1. **Early return** in the handler if a job is already active:
   ```typescript
   if (!clientId || automationJobId) return;
   ```

2. **CSS-based disable** on the dropdown option — cursor becomes `not-allowed`, opacity drops to 0.5, and `pointerEvents: 'none'` blocks clicks:
   ```typescript
   cursor: automationJobId && (automationStatus === 'running' || automationStatus === 'queued') ? 'not-allowed' : 'pointer',
   opacity: automationJobId && (automationStatus === 'running' || automationStatus === 'queued') ? 0.5 : 1,
   pointerEvents: automationJobId && (automationStatus === 'running' || automationStatus === 'queued') ? 'none' : 'auto',
   ```

---

## 4. Data Flow Diagram

```
 User clicks "Import from Portal"
          │
          ▼
 handleImportFromPortal()
   ├── Sets status: 'queued', message: 'Starting automation...'
   ├── Closes dropdown
   ├── POST /clients/{id}/automation/import?assessment_year=2025-26&job_type=DOWNLOAD_ALL
   │     │
   │     └── Backend creates AutomationJob row (status: 'queued')
   │         Enqueues in asyncio.Queue
   │         Worker picks up → status: 'running'
   │           → login → download_26as → request_ais → download_tis → logout
   │           → status: 'completed' | 'failed'
   │
   ├── setInterval (every 2s):
   │     GET /automation/jobs/{job_id}
   │     │
   │     ├── status: 'running' → show spinner + status_message
   │     ├── status: 'completed' → clearInterval, toast success
   │     └── status: 'failed'   → clearInterval, show error
   │
   └── setAutomationJobId(jobId)
```

---

## 5. Critical Windows Fix: Playwright + ProactorEventLoop

### The Problem

On Windows, Python's default `ProactorEventLoop` does not implement `create_subprocess_exec`. Playwright (used by the automation worker) calls this internally to spawn Chromium. The result is a fatal `NotImplementedError`.

The error in `main.py` can't fix it because uvicorn creates its event loop **before importing `app.main`**:

```
uvicorn app.main:app
  → uvicorn creates event loop (ProactorEventLoop — locked)
  → uvicorn imports app.main
  → main.py: asyncio.set_event_loop_policy(…)  ← TOO LATE
```

### The Fix

`run.py` sets the policy **before uvicorn is imported**:

```python
import sys
if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
```

**Always start the server with `python run.py`, never `uvicorn app.main:app` directly.**

---

## 6. Verification Checklist

- [ ] Server started with `python run.py` (not `uvicorn app.main:app`)
- [ ] "Import from Portal" appears as the first option in the Import dropdown
- [ ] Clicking starts the job, shows "Starting automation…" → spinner + live status
- [ ] Dropdown option is disabled (greyed out, unclickable) while job is running
- [ ] On `completed`, toast: "Portal import complete — 26AS, AIS, and TIS downloaded."
- [ ] On `failed`, red error text with the reason from the backend
- [ ] No `NotImplementedError` in the server console
- [ ] No double-click spawning two jobs

---

## 7. Next Chunks (DO NOT BUILD AHEAD)

- Chunk 4: Parse downloaded PDFs (call extractors) and store parsed data
- Chunk 5: Auto-trigger reconciliation on the parsed data
- Chunk 6: Auto-populate `formData` from reconciliation result + trigger tax computation
- Chunk 7: Download progress bar / richer status UI
