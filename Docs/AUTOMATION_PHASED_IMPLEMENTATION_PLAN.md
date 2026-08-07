# Taxify Portal Automation — Phase-Gated Implementation Plan

**Target filing season:** AY 2026-27
**Prepared:** 8 August 2026
**Reference implementation:** `C:\Users\Devansh\Desktop\AayDocCapio`
**Implementation repository:** `C:\Users\Devansh\Desktop\Taxify`
**Status:** Plan only — no phase may begin without explicit user approval.

---

## 1. Objective

Build a fast, reliable, success-oriented Income Tax Portal automation workflow that logs in once per client and retrieves the complete evidence bundle needed for AY 2026-27 preparation:

1. Current-year ITD Prefill JSON for AY 2026-27.
2. Form 26AS PDF for AY 2026-27.
3. Form 26AS TXT/ZIP for AY 2026-27, using the existing decryption flow.
4. AIS PDF for FY 2025-26.
5. TIS PDF for FY 2025-26.
6. Latest valid prior filed ITR JSON for AY 2025-26.

The workflow must minimize elapsed time by removing artificial sleeps, duplicate navigation, duplicate login/logout, serial timeout multiplication, repeated portal opening, and worker-blocking AIS polling. It must **not** fail a client merely because the portal takes longer than a fixed whole-client duration. Slow but progressing portal operations must be allowed to complete.

---

## 2. Non-negotiable constraints

1. **No hard 30-second whole-client timeout.** Thirty seconds is an optimization target under normal portal conditions, not a correctness boundary.
2. **Success over arbitrary speed.** Continue waiting when the portal shows meaningful progress.
3. **One normal login and one logout per client workflow.**
4. **No extraction changes during the automation phases.** The following remain untouched unless a separately approved extraction phase is created:
   - `ais_extractor/**`
   - existing AIS/TIS/26AS extraction algorithms
   - reconciliation algorithms
   - tax calculators and CBDT builders
5. **No duplicate consequential portal actions.** In particular, do not blindly resubmit credentials, AIS-generation requests, or download clicks after ambiguous responses.
6. **Every artifact has an independent outcome.** A failed or unavailable document must not erase successfully downloaded artifacts.
7. **Explicit AY/FY semantics.** AY 2026-27 and FY 2025-26 must never be substituted for one another.
8. **No phase proceeds without user acceptance.** After each phase, implementation stops until the user confirms the manual acceptance checklist.
9. **Reference implementation behavior must be preserved where proven.** Improvements must be incremental, tested, and justified against AayDocCapio.
10. **Sensitive taxpayer files remain local.** No PAN, DOB, portal password, downloaded document, cookie, or session token may be committed or logged in clear text.

---

## 3. Current-state findings

### 3.1 Existing reusable functionality

Taxify already has AayDocCapio-derived implementations for:

- Browser launch/context creation.
- ITD PAN/SAM/password login.
- Dashboard detection and logout.
- TRACES navigation and Form 26AS PDF/TXT download.
- Compliance Portal navigation and AIS/TIS download.
- AIS Activity History polling.
- PDF unlocking.
- Backend job queue and frontend status polling.

### 3.2 Missing functionality

Neither Taxify nor AayDocCapio currently automates:

- ITD `Download Pre-filled Data` JSON.
- `View Filed Returns` / `View Filed Forms` prior ITR JSON download.

Taxify's manual `/integration/prefill/import` endpoint is currently a stub and is not portal browser automation.

### 3.3 Existing defects to address phasewise

- Current `job_type` values are accepted but ignored by the worker.
- Taxify chains all document phases unconditionally.
- AY is converted to FY and the FY is passed into the 26AS downloader as if it were AY.
- AIS queued generation can occupy the sole worker for approximately ten minutes.
- Compliance Portal may be opened twice in one job.
- Alternative selector waits and frame searches can multiply nominal timeouts.
- New-tab and same-tab outcomes are checked serially.
- `networkidle` can waste 40 seconds even though the workflow proceeds afterward.
- Fixed sleeps delay successful fast-path execution.
- External portal pages may replace the ITD anchor but are later closed unconditionally.
- Broad exception handling sometimes reduces document failures to booleans and permits misleading completion.
- Every detailed log line can trigger a separate SQLite write.

---

## 4. Target workflow

The optimized sequence is:

```text
Create isolated client browser context
  → Login once
  → Establish stable authenticated ITD anchor page
  → Download current AY Prefill JSON
  → Download latest prior AY filed ITR JSON
  → Open AIS portal
      → Check for existing ready/generating AIS
      → Request AIS only if no existing request exists
      → Download TIS
      → Retain queued AIS reference/state
  → Restore ITD anchor
  → Open TRACES
      → Download 26AS PDF
      → Download 26AS TXT/ZIP
      → Use existing unlock/decrypt behavior
      → Close only the owned TRACES child tab
  → Recheck queued AIS once after TRACES
      → Download if ready
      → Otherwise persist waiting-external state
  → Logout once
  → Close context in finally
```

The order intentionally starts AIS server-side generation before TRACES so that generation overlaps with useful work without unsafe simultaneous browser interaction.

---

# Phase 0 — Baseline Recovery, Safety, and Observability

## Goal

Restore a known-good automation baseline, prevent recurrence of the recent authentication regression, and add enough timing/state visibility to optimize based on evidence.

## Implementation scope

### Authentication baseline

- Keep `app/automation/auth.py` aligned with the committed/reference implementation initially.
- Add regression tests before changing selectors or waits.
- Prove that alternative selectors share one elapsed wait rather than one timeout each.
- Ensure diagnostics are captured only on terminal failure, not on every polling cycle.

### Runtime environment

- Retain standard Python runtime validation.
- Retain `PyMuPDF` and `pikepdf` as declared runtime dependencies.
- Document the supported launch command:

```powershell
py -3.14 run.py
```

### Timing instrumentation

Record monotonic phase timestamps without exposing credentials:

- context requested / ready;
- login page requested / ready;
- PAN submitted;
- SAM ready;
- password submitted;
- dashboard ready;
- each portal navigation started / ready;
- each download started / completed;
- logout started / completed.

### Test harness

Create mocked Playwright tests for:

- missing and present Continue controls;
- delayed SAM;
- account lock;
- invalid PAN;
- OTP/CAPTCHA state;
- dashboard readiness;
- selector alternatives under one shared wait.

## Files expected to change

- `app/automation/auth.py`
- `app/automation/browser.py`
- `app/automation/errors.py`
- `app/automation/job_worker.py`
- new automation test modules
- automation documentation

## Explicit exclusions

- No Prefill downloader.
- No prior ITR downloader.
- No extraction changes.
- No workflow reordering.

## Automated acceptance criteria

- Authentication unit tests pass.
- Existing automation tests pass.
- Missing-selector tests demonstrate no timeout multiplication.
- No secrets appear in logs or failure snapshots.
- `auth.py` still follows the proven portal sequence.

## User manual test gate

The user must manually verify:

1. Server starts with `py -3.14 run.py`.
2. One known-valid client reaches the ITD dashboard.
3. SAM checkbox and password login behave exactly as before.
4. Active-session popup, if encountered, is handled correctly.
5. Invalid password produces a clear failure and does not repeatedly submit credentials.
6. Timing logs show the real phase durations.

## Required approval

Implementation stops after Phase 0. The user must explicitly respond that Phase 0 login and diagnostics work correctly before Phase 1 begins.

---

# Phase 1 — Shared Navigation, Year Semantics, and Page Ownership

## Goal

Create reliable primitives that every document downloader can use without duplicating menus, confusing AY/FY, or closing the wrong page.

## Implementation scope

### Explicit tax-year model

Introduce a typed value object carrying:

- current assessment year: `2026-27`;
- current financial year: `2025-26`;
- prior assessment year: `2025-26`;
- normalized filename forms.

Validate year inputs at the API boundary.

### Shared ITD navigation

Create shared helpers for:

- locating/creating the authenticated ITD anchor page;
- restoring the dashboard;
- waiting for overlays to clear;
- opening hamburger navigation when needed;
- navigating `e-File → Income Tax Returns`;
- selecting a submenu item by normalized semantic label;
- detecting login/session expiry.

### Page ownership

Introduce a portal handle that records:

- origin page;
- target page;
- whether a child tab opened;
- whether the anchor was replaced;
- owning portal.

Cleanup must close only owned child pages. Same-tab navigation must restore or recreate the ITD anchor using the same authenticated context.

### Navigation race

Race concurrently:

- new child page;
- same-tab URL change;
- redirect confirmation;
- explicit error state.

Do not wait for a full new-tab timeout before checking same-tab navigation.

### Frame search

Replace per-frame full timeouts with one global adaptive frame search that repeatedly scans all current frames.

## Files expected to change

- new `app/automation/navigation.py`
- new `app/automation/years.py`
- `app/automation/downloader_26as.py`
- `app/automation/downloader_ais_tis.py`
- `app/automation/job_worker.py`
- `app/routers/automation.py`
- database model/migration for explicit AY if necessary
- navigation/year tests

## Automated acceptance criteria

- AY 2026-27 maps to FY 2025-26 and prior AY 2025-26.
- 26AS receives AY, AIS/TIS receives FY.
- New-tab and same-tab fixtures both pass.
- Closing TRACES/AIS never closes the only authenticated ITD page.
- Frame lookup elapsed time is bounded by one global operation wait, not frame count multiplied by timeout.

## User manual test gate

The user must manually verify:

1. Login reaches dashboard.
2. Shared navigation opens `e-File → Income Tax Returns`.
3. 26AS receives AY 2026-27 in the portal dropdown.
4. AIS receives FY 2025-26.
5. After closing TRACES, the ITD session remains authenticated.
6. After closing AIS, the ITD session remains authenticated.
7. Both popup-tab and same-tab behavior, if observable, recover correctly.

## Required approval

Implementation stops after Phase 1. The user must confirm year handling and page restoration before Phase 2 begins.

---

# Phase 2 — Current-Year Prefill JSON Download

## Goal

Download and validate the official current-year Prefill JSON through the existing authenticated browser session.

## Discovery requirement

Before implementation, capture the live portal DOM for:

- `Download Pre-filled Data` menu item;
- AY selector;
- download button;
- loading, no-data, and error states.

Do not guess a single brittle selector.

## Implementation scope

Create `app/automation/downloader_prefill.py`:

1. Restore ITD anchor.
2. Navigate to the Prefill page.
3. Select AY 2026-27.
4. Verify the selected year.
5. Arm the exact-page download listener.
6. Click Download once.
7. Save to a `.partial` path.
8. Validate non-zero size and JSON syntax.
9. Validate PAN/AY when present in the JSON.
10. Atomically rename to the final path.
11. Return a structured artifact outcome.

Proposed filename:

```text
<PAN>-PREFILL-AY-2026_27.json
```

## Artifact outcome states

- `downloaded`
- `no_data`
- `retryable_failure`
- `validation_failed`
- `session_expired`
- `permanent_failure`

## Automated acceptance criteria

- Correct AY is selected.
- Download click is not duplicated.
- Invalid/empty JSON never receives a successful status.
- PAN/AY mismatch is rejected safely.
- `.partial` files are cleaned or retained with an explicit failure status.
- Existing manual Prefill import behavior remains unchanged.

## User manual test gate

The user must manually verify:

1. Portal reaches Download Pre-filled Data.
2. AY 2026-27 is selected.
3. Official JSON downloads successfully.
4. File name and download directory are correct.
5. JSON opens and contains expected taxpayer/current-year metadata.
6. The ITD session remains active after download.
7. No extraction or form fields are changed automatically in this phase.

## Required approval

Implementation stops after Phase 2. The user must inspect the downloaded JSON and approve before Phase 3 begins.

---

# Phase 3 — Latest Prior Filed ITR JSON Download

## Goal

Download the latest valid filed-return JSON for prior AY 2025-26 and preserve sufficient metadata for later carry-forward analysis.

## Discovery requirement

Capture live DOM/fixtures for:

- `View Filed Returns` / `View Filed Forms` menu item;
- table rows and pagination;
- status and form columns;
- filing/revision dates;
- acknowledgement number;
- download action menu;
- JSON option;
- no-return state.

## Implementation scope

Create `app/automation/downloader_filed_returns.py`:

1. Restore ITD anchor.
2. Navigate to filed returns.
3. Locate all records for AY 2025-26, including paginated records.
4. Parse row metadata.
5. Exclude invalid/incomplete filings where status indicates they are not valid filed returns.
6. Select deterministically by:
   - target AY;
   - valid/completed status;
   - filing timestamp descending;
   - revised/latest version precedence;
   - acknowledgement number tie-breaker.
7. Download JSON from the selected row.
8. Validate JSON syntax, PAN, AY, form and acknowledgement where present.
9. Register metadata without extracting tax details.

Proposed filename:

```text
<PAN>-FILED-ITR-AY-2025_26-<ACK>.json
```

## Automated acceptance criteria

- Revised return is selected when it is the latest valid filing.
- DOM order alone does not determine selection.
- Pagination is handled.
- No prior filing returns `no_filed_return`, not workflow failure.
- Latest-row JSON unavailability is reported explicitly rather than silently downloading a different return.
- Downloaded JSON metadata matches the selected row.

## User manual test gate

The user must manually verify:

1. Filed Returns page opens.
2. Prior AY 2025-26 records are identified.
3. The latest valid filing is selected.
4. Correct ITR form, filing date and acknowledgement are displayed in status metadata.
5. The correct JSON downloads.
6. Original versus revised selection is correct for a client with revisions.
7. A client with no prior return gets a clear non-error outcome.

## Required approval

Implementation stops after Phase 3. The user must approve prior-return selection and file identity before Phase 4 begins.

---

# Phase 4 — 26AS Flow Hardening Without Extraction Changes

## Goal

Retain the reference TRACES process while removing artificial delays and fixing ownership/year/error behavior.

## Implementation scope

- Use shared ITD navigation and page ownership.
- Pass AY 2026-27 explicitly.
- Preserve existing agreement handling and TDS-default intermediate-page support.
- Replace fixed hover sleeps with submenu visibility.
- Replace fixed post-click sleeps with target-state waits.
- Race loader completion, PDF button, large-file message, no-data and error states.
- Download PDF and TXT/ZIP as independent artifacts.
- Preserve PDF success if TXT fails.
- Continue using existing decryption/unlock code unchanged.
- Verify file headers, sizes and ZIP structure before recording success.

## Automated acceptance criteria

- PDF and TXT both download under normal fixtures.
- PDF-only partial success is preserved.
- Wrong DOB preserves encrypted ZIP/PDF with a clear locked status.
- Multi-frame fixtures pass.
- TDS-default intermediate page passes.
- Large 26AS receives a structured outcome.
- No extraction module diff is introduced.

## User manual test gate

The user must manually verify:

1. TRACES opens successfully.
2. Agreement modal is handled.
3. AY 2026-27 is selected.
4. PDF downloads and opens.
5. TXT/ZIP downloads and decrypts with the stored DOB.
6. Wrong-DOB behavior is clear and non-destructive.
7. TRACES closes and the ITD anchor remains usable.

## Required approval

Implementation stops after Phase 4. The user must verify both 26AS artifacts before Phase 5 begins.

---

# Phase 5 — AIS/TIS Fast Path and Adaptive Queued AIS

## Goal

Make AIS/TIS faster without sacrificing slow-portal success or issuing duplicate AIS requests.

## Implementation scope

### Fast readiness

- Replace `networkidle` with route-specific readiness controls.
- Replace fixed hydration sleeps with FY dropdown/download-icon readiness.
- Scope all download listeners to the exact Compliance Portal page.

### Request safety

Before requesting AIS:

1. Check Activity History for a ready request.
2. Download if ready.
3. If generating, capture the existing reference ID.
4. Request only when no matching existing request is present.
5. Resolve ambiguous submissions through Activity History before another request.

### TIS

Download TIS during the same Compliance Portal session, independently of AIS result.

### Adaptive queue handling

- Start AIS generation before TRACES.
- Perform one recheck after TRACES.
- If still generating, persist `waiting_external` and release the browser worker.
- Schedule lightweight continuation checks.
- Use adaptive background intervals such as 5s, 10s, 20s, 30s, then 60s with jitter.
- Do not hold the sole worker sleeping for ten minutes.
- Continue waiting/retrying over time while the external request remains valid.

## Automated acceptance criteria

- Instant AIS downloads.
- Existing ready AIS downloads without submitting a new request.
- Existing generating AIS is not requested again.
- New request is submitted once.
- Queued AIS persists reference/state and releases the active worker.
- TIS success is preserved if AIS is queued or fails.
- No `networkidle` dependency remains in the critical path.

## User manual test gate

The user must manually verify:

1. Compliance Portal SSO works.
2. FY 2025-26 is selected.
3. TIS downloads.
4. Instant AIS downloads.
5. Queued AIS shows reference ID and waiting state.
6. Queued AIS does not freeze later clients.
7. A later continuation downloads the generated AIS.
8. No duplicate AIS request appears in Activity History.
9. Returning from AIS preserves the ITD session.

## Required approval

Implementation stops after Phase 5. The user must approve instant and queued AIS behavior before Phase 6 begins.

---

# Phase 6 — Single-Login Coordinator and Optimal Ordering

## Goal

Combine the individually proven phases into one success-oriented client workflow.

## Implementation scope

Create `app/automation/workflow.py` to coordinate:

1. Context creation.
2. One login.
3. Prefill JSON.
4. Prior filed ITR JSON.
5. AIS pre-check/request + TIS.
6. 26AS PDF/TXT.
7. AIS recheck.
8. One logout.
9. Guaranteed context cleanup.

Each artifact executes within an independent transaction boundary:

```text
prepare → navigate → download .partial → validate → atomic rename → record outcome → cleanup owned page/modal
```

Authentication loss is the only default condition that can stop all subsequent artifacts. Other artifact failures produce warnings and allow the workflow to continue where safe.

## Job statuses

- `queued`
- `running`
- `completed`
- `completed_with_warnings`
- `waiting_external`
- `failed_authentication`
- `failed`
- `cancelled`

## Automated acceptance criteria

- Normal workflow logs in exactly once.
- Normal workflow logs out exactly once.
- Artifact order matches the approved design.
- Queued AIS generation overlaps with TRACES work.
- One artifact failure does not erase others.
- No orphan page/context/listener remains.
- Slow progress continues rather than failing at an arbitrary whole-client duration.

## User manual test gate

The user must run the complete workflow for representative clients:

1. All artifacts immediately available.
2. Queued AIS.
3. No prior filed return.
4. Revised prior return.
5. Slow ITD or TRACES response.
6. Wrong DOB for protected documents.
7. One unavailable artifact with remaining artifacts successful.

The user must confirm artifact paths, status outcomes, one-login behavior, and absence of duplicate requests.

## Required approval

Implementation stops after Phase 6. The complete workflow does not proceed to persistence/UI refinements until the user approves live end-to-end behavior.

---

# Phase 7 — Durable Artifact Manifest and Job-State Persistence

## Goal

Persist every artifact and its provenance reliably without parsing its tax content.

## Implementation scope

Add a durable artifact model containing:

- job/client IDs;
- artifact type;
- AY/FY;
- path;
- status;
- source portal;
- reference ID;
- acknowledgement number;
- prior ITR form;
- filing date;
- size;
- SHA-256;
- download/validation timestamps;
- error code/message;
- metadata JSON.

Artifact types:

- `PREFILL_JSON`
- `PRIOR_ITR_JSON`
- `FORM26AS_PDF`
- `FORM26AS_TXT`
- `AIS_PDF`
- `TIS_PDF`

Use additive migrations only. Do not delete or rewrite prior jobs.

Throttle status persistence so detailed logs do not open and commit one SQLite session per message. Persist phase transitions immediately and batch diagnostic logs.

## Automated acceptance criteria

- Existing databases migrate additively.
- Each artifact can be queried independently.
- Checksums and metadata are recorded.
- Retried downloads do not create ambiguous duplicates.
- Existing job records remain readable.

## User manual test gate

The user must verify:

1. Job history shows every artifact independently.
2. Prior form, AY, acknowledgement and reference ID are visible where applicable.
3. Partial success persists after restart.
4. Waiting AIS resumes after restart.
5. No existing client/job data is lost.

## Required approval

Implementation stops after Phase 7. The user must approve persistence and restart behavior before Phase 8 begins.

---

# Phase 8 — Frontend Status, Controls, and Phase-Aware Recovery

## Goal

Expose the richer automation workflow clearly without implying false success.

## Implementation scope

- Display all six artifact outcomes independently.
- Show `waiting_external` separately from failure.
- Show current portal/action and elapsed phase time.
- Offer scoped retry actions:
  - retry Prefill;
  - retry prior ITR;
  - retry 26AS;
  - check queued AIS;
  - retry TIS.
- Continue supporting full `DOWNLOAD_ALL`.
- Make narrower job types operational.
- Prevent duplicate active jobs per client/PAN.
- Avoid overlapping frontend polling requests.
- Refresh form data only when a later approved import/parser phase actually applies data.

## Automated acceptance criteria

- Frontend types support all statuses/artifacts.
- Status UI accurately distinguishes complete, warning, queued and failed.
- Retry invokes the correct job type.
- No duplicate job starts.
- Frontend tests and build pass.

## User manual test gate

The user must verify:

1. Every artifact has a visible status.
2. Queued AIS is understandable and non-blocking.
3. Retry buttons target only the failed artifact.
4. Complete and partial-success messaging is accurate.
5. No downloaded-data import happens unexpectedly.
6. UI survives refresh and resumes current job display.

## Required approval

Implementation stops after Phase 8. The user must approve the complete automation UI before any extraction/reconciliation enhancement is proposed.

---

# Phase 9 — Separate Future Proposal: Prefill/Prior-ITR Interpretation

This phase is intentionally **not part of the automation implementation** and requires separate approval because the user explicitly requested no extraction changes now.

A future proposal may introduce schema-version-aware readers for downloaded Prefill and prior ITR JSON to produce reference evidence for:

- prior filed form and filing type;
- original/revised status;
- personal-information comparison;
- residential status;
- brought-forward capital/business/house-property losses;
- unabsorbed depreciation;
- AMT credit;
- carry-forward TDS/TCS;
- form-selection warnings and recommendations.

Prior-year form alone must never automatically force the current form. Recommendations must cite current eligibility facts and surviving carry-forward schedules.

---

## 5. Error and retry policy

### Permanent/user-action states

Do not retry blindly:

- invalid PAN;
- incorrect password;
- account locked;
- OTP/2FA required;
- CAPTCHA/human verification;
- no filed return;
- explicit no-data;
- AIS too large for PDF.

### Retryable states

Retry adaptively:

- connection reset;
- empty response;
- transient DNS failure;
- portal timeout with no terminal error;
- browser process crash;
- temporarily missing control after reload;
- session expiry, with controlled re-login when safe.

### Progress-aware waiting

Operations use:

1. A normal readiness interval for metrics only.
2. A no-progress interval that resets when URL, loader, modal, frame, control, row or download state changes.
3. A generous configurable safety cap for truly stuck operations.

No whole-client timeout is used.

---

## 6. Validation matrix

Every phase must run:

- focused unit tests;
- affected backend integration tests;
- affected frontend tests;
- Python compilation/static checks;
- frontend build when frontend code changes;
- Git diff review proving extraction files are untouched unless explicitly approved.

Live portal accounts should cover:

- normal fast response;
- slow progressing response;
- active session;
- popup and same-tab redirects;
- queued AIS;
- revised prior ITR;
- no prior ITR;
- protected PDF/ZIP;
- wrong DOB;
- partial artifact failure;
- browser restart/session recovery.

---

## 7. Mandatory phase-control protocol

For every implementation phase, the assistant must:

1. Implement **only** that phase.
2. Run its automated acceptance suite.
3. Provide a concise changed-file summary.
4. Provide exact automated test results.
5. Provide the phase's manual test checklist.
6. Explicitly state that implementation is paused.
7. Wait for the user's live-test report.
8. Fix defects found within the current phase.
9. Obtain explicit written acceptance such as:

```text
Phase N accepted. Proceed to Phase N+1.
```

10. Only then begin the next phase.

No phase may be silently combined with another. No downstream feature may be implemented “while already in the file.”

---

## 8. Definition of complete automation

The automation program is complete only when:

- one authenticated client run obtains all immediately available artifacts;
- slow but progressing portals are allowed to complete;
- queued AIS is resumed without blocking other clients;
- all AY/FY selections are correct;
- prior filed return selection is deterministic;
- each file is integrity-validated and registered;
- partial successes persist;
- no duplicate consequential action occurs;
- no orphan tabs, contexts or listeners remain;
- the user has manually accepted every phase;
- extraction code remains unchanged throughout the automation implementation unless separately approved.
