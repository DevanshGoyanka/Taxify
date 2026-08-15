# Filed-Return Integration — Reactivation Guide

**Document created:** 2026-08-15
**Status:** Filed-return integration temporarily disabled for Phase 2 testing
**Related plan:** `IMPORT_PIPELINE_IMPLEMENTATION_PLAN.md` (Phase 2)

This document describes how to reactivate the filed-return integration
after Phase 2 testing is complete.  The filed-return integration was
temporarily disabled so the portal automation import doesn't surface the
"already filed" blocking error during testing.

---

## Why it was disabled

When the portal automation detects that the current AY (2026-27) already
has a filed return, the filed-return integration shows a blocking error:

> ⚠️ ITR for AY 2026-27 is already filed (section 139(1)). To file a
> revised return, explicitly confirm the revised-return flow.

This is **correct behavior** for production — the user must explicitly
confirm a revised-return flow before the current-AY filed-ITR data is
populated.  But during testing, the blocking error prevents smooth
testing of the other import features (Prefill, reconciliation, AIS/TIS/
26AS).

The filed-return integration was **not** populating any data that the
Prefill doesn't already provide (both provide personal info, bank
accounts, and TDS).  The only unique data the filed-return provides is:
- **Carry-forward losses** (brought-forward HP/business/LTCG/STCG losses)
- **Prior-AY employer details** (may differ from current-AY employers)
- **Prior-AY bank accounts** (may differ from current-AY accounts)

Commenting it out for testing has minimal impact on the import flow.

---

## What was disabled

### Backend — `app/automation/job_worker.py`

Three blocks were commented out (search for `REACTIVATE`):

1. **Step 4.2 — Filed-return download** (lines ~620-645)
   - The `download_filed_return_json()` call that downloads the prior-
     year return JSON from the portal.
   - Replaced with a log line: `[FILED RETURN DL] SKIPPED (Phase 2
     testing) — prior_ref_ay=...`

2. **Step 4.6.1 — Filed-return parsing** (lines ~919-970)
   - The `_parse_filed_return_file()` call that parses the downloaded
     JSON into a `FiledReturnExtraction`.
   - Replaced with a log line: `[Worker] Filed-return parsing SKIPPED
     (Phase 2 testing).`

3. **Step 4.7 — Reconciled output attachment** (lines ~960-970)
   - The `reconciled["filed_return"] = parsed["filed_return"]` line that
     attaches the extraction to the reconciled output.

### Frontend — `frontend/src/pages/ITRComputationPage.tsx`

Four blocks were commented out (search for `REACTIVATE`):

1. **Import** (line ~9)
   - `import { mapFiledReturnToFormData } from '../utils/mapFiledReturnToFormData';`

2. **Merge block** (lines ~920-935)
   - The `mapFiledReturnToFormData()` call and the filed-return data
     extraction.
   - Replaced with stubs: `const advisory = null;` and
     `const filedReturnResult = { ... };`

3. **Tertiary toast + advisory error toast** (lines ~985-1020)
   - The `toast` for filed-return imports and the `toast.error` for the
     "already filed" advisory.

4. **Advisory banner** (lines ~990-1010)
   - The `advisoryBanner` block in the discrepancy messages that adds
     the advisory message to the warning banner.

---

## How to reactivate

### Step 1: Uncomment the filed-return download (backend)

**File:** `app/automation/job_worker.py`
**Location:** Step 4.2 (search for `REACTIVATE: _update_job(`)

Uncomment the entire download block:

```python
# Before (disabled):
if prior_ref_ay and advisory.download_row_identity:
    # REACTIVATE: _update_job(
    # REACTIVATE:     job_id,
    # ...
    log(f"[FILED RETURN DL] SKIPPED (Phase 2 testing) — prior_ref_ay={prior_ref_ay}")

# After (reactivated):
if prior_ref_ay and advisory.download_row_identity:
    _update_job(
        job_id,
        current_step="filed_return_download",
        status_message="Downloading prior-year reference JSON...",
        progress_pct=84,
    )
    log(f"[FILED RETURN DL] Downloading prior-year reference JSON for AY {prior_ref_ay}.")
    prior_dl = await download_filed_return_json(
        page=page,
        assessment_year=prior_ref_ay,
        target_row_identity=advisory.download_row_identity,
        download_dir=dldir,
        timeout_ms=60_000,
        log=log,
    )
    page = await resolve_itd_anchor(page)
    artifact_outcomes["prior_year_return"] = prior_dl.to_dict()
    if prior_dl.state is FiledReturnDownloadState.DOWNLOADED:
        files["prior_year_return"] = prior_dl.path
        steps.append("prior_year_return_downloaded")
        log(f"[FILED RETURN DL] Prior-year reference JSON saved for AY {prior_ref_ay}.")
    else:
        log(f"[FILED RETURN DL] Prior-year reference download: {prior_dl.state.value}")
```

### Step 2: Uncomment the filed-return parsing (backend)

**File:** `app/automation/job_worker.py`
**Location:** Step 4.6.1 (search for `REACTIVATE: path_filed =`)

Uncomment the entire parsing block:

```python
# Before (disabled):
# REACTIVATE: path_filed = files.get("prior_year_return")
# REACTIVATE: if path_filed and os.path.exists(path_filed):
# REACTIVATE:     try:
# ...
log("[Worker] Filed-return parsing SKIPPED (Phase 2 testing).")

# After (reactivated):
path_filed = files.get("prior_year_return")
if path_filed and os.path.exists(path_filed):
    try:
        filed_extracted = _parse_filed_return_file(path_filed)
        parsed["filed_return"] = _filed_return_to_dict(filed_extracted)
        log(
            f"[Worker] Filed return parsed: "
            f"form={filed_extracted.form_name}, "
            f"employers={len(filed_extracted.employer_entries)}, "
            f"banks={len(filed_extracted.bank_accounts)}, "
            f"tds_sal={len(filed_extracted.tds_salary_entries)}, "
            f"tds_oth={len(filed_extracted.tds_other_entries)}, "
            f"losses={len(filed_extracted.carry_forward_losses)}"
        )
        logger.info(
            "Job %d: Filed-return extraction OK — form=%s, employers=%d, "
            "banks=%d, tds_sal=%d, tds_oth=%d, losses=%d",
            job_id,
            filed_extracted.form_name,
            len(filed_extracted.employer_entries),
            len(filed_extracted.bank_accounts),
            len(filed_extracted.tds_salary_entries),
            len(filed_extracted.tds_other_entries),
            len(filed_extracted.carry_forward_losses),
        )
    except Exception as e:
        err = f"Filed-return extraction failed: {type(e).__name__}: {e}"
        extract_errors.append(err)
        log(f"[Worker] {err}")
        logger.exception("Job %d: Filed-return extraction error", job_id)
else:
    logger.info("Job %d: Filed-return file not found at %s — skipping", job_id, path_filed)
```

### Step 3: Uncomment the reconciled output attachment (backend)

**File:** `app/automation/job_worker.py`
**Location:** Step 4.7 (search for `REACTIVATE: if "filed_return" in parsed:`)

Uncomment the attachment line:

```python
# Before (disabled):
# REACTIVATE: if "filed_return" in parsed:
# REACTIVATE:     reconciled["filed_return"] = parsed["filed_return"]

# After (reactivated):
if "filed_return" in parsed:
    reconciled["filed_return"] = parsed["filed_return"]
```

### Step 4: Uncomment the frontend import

**File:** `frontend/src/pages/ITRComputationPage.tsx`
**Location:** Line ~9 (search for `REACTIVATE: import`)

Uncomment the import:

```typescript
// Before (disabled):
// REACTIVATE: import { mapFiledReturnToFormData } from '../utils/mapFiledReturnToFormData';

// After (reactivated):
import { mapFiledReturnToFormData } from '../utils/mapFiledReturnToFormData';
```

### Step 5: Uncomment the frontend merge block

**File:** `frontend/src/pages/ITRComputationPage.tsx`
**Location:** `handleConfirmImport` (search for `REACTIVATE: const advisory =`)

Uncomment the merge block and remove the stubs:

```typescript
// Before (disabled):
// REACTIVATE: const advisory = (reconciledImportData as any).filing_advisory;
// REACTIVATE: const filedReturnData = (reconciledImportData as any).filed_return || null;
// REACTIVATE: const filedReturnResult = mapFiledReturnToFormData(filedReturnData);
const advisory = null as any;
const filedReturnResult = { formDataUpdate: {}, summary: { carryForwardLosses: 0, bankAccounts: 0, employerEntries: 0 } } as any;

// After (reactivated):
const advisory = (reconciledImportData as any).filing_advisory;
const filedReturnData = (reconciledImportData as any).filed_return || null;
const filedReturnResult = mapFiledReturnToFormData(filedReturnData);
```

### Step 6: Uncomment the tertiary toast + advisory error toast

**File:** `frontend/src/pages/ITRComputationPage.tsx`
**Location:** `handleConfirmImport` (search for `REACTIVATE: if (filedReturnResult.summary`)

Uncomment the entire toast block:

```typescript
// Before (disabled):
// REACTIVATE: if (filedReturnResult.summary.carryForwardLosses > 0 || ...) {
// ...
// REACTIVATE: }

// After (reactivated):
if (filedReturnResult.summary.carryForwardLosses > 0 || filedReturnResult.summary.bankAccounts > 0) {
  const frParts: string[] = [];
  if (filedReturnResult.summary.carryForwardLosses > 0) frParts.push(`${filedReturnResult.summary.carryForwardLosses} brought-fwd loss(es)`);
  if (filedReturnResult.summary.bankAccounts > 0) frParts.push(`${filedReturnResult.summary.bankAccounts} bank account(s)`);
  if (filedReturnResult.summary.employerEntries > 0) frParts.push(`${filedReturnResult.summary.employerEntries} employer(s)`);
  toast(`Filed return: ${frParts.join(', ')}`, { icon: '📄' });
}

if (advisory && advisory.current_ay_already_filed) {
  if (advisory.current_ay_is_revised) {
    toast.error(
      `ITR for AY ${advisory.download_assessment_year || ''} is already filed as a REVISED return. ` +
      'The last filed ITR was a revised return. To file another revised return, explicitly confirm the revised-return flow.',
      { duration: 8000 }
    );
  } else {
    toast.error(
      `ITR for AY ${advisory.download_assessment_year || ''} is already filed. ` +
      'To file a revised return, explicitly confirm the revised-return flow.',
      { duration: 8000 }
    );
  }
}
```

### Step 7: Uncomment the advisory banner

**File:** `frontend/src/pages/ITRComputationPage.tsx`
**Location:** `handleConfirmImport` (search for `REACTIVATE: const advisoryBanner =`)

Uncomment the entire banner block:

```typescript
// Before (disabled):
// REACTIVATE: const advisoryBanner = (reconciledImportData as any).filing_advisory;
// ...
// REACTIVATE: }

// After (reactivated):
const advisoryBanner = (reconciledImportData as any).filing_advisory;
if (advisoryBanner && advisoryBanner.current_ay_already_filed) {
  if (advisoryBanner.current_ay_is_revised) {
    msgs.push(
      `⚠️ ITR for AY ${advisoryBanner.download_assessment_year || ''} is already filed as a REVISED return ` +
      `(section ${advisoryBanner.current_ay_filing_section || '139(5)'}). ` +
      'The last filed ITR was a revised return. To file another revised return, ' +
      'explicitly confirm the revised-return flow.'
    );
  } else {
    msgs.push(
      `⚠️ ITR for AY ${advisoryBanner.download_assessment_year || ''} is already filed ` +
      `(section ${advisoryBanner.current_ay_filing_section || '139(1)'}). ` +
      'To file a revised return, explicitly confirm the revised-return flow.'
    );
  }
}
```

### Step 8: Verify

After reactivating all blocks:

1. Run `npx tsc --noEmit` in the frontend — should compile clean.
2. Run `py -c "from app.automation.job_worker import _parse_prefill_file"` in the backend — should print `OK`.
3. Run a portal automation import — the backend log should show:
   - `[FILED RETURN DL] Downloading prior-year reference JSON for AY ...`
   - `Filed-return extraction OK — form=ITR2, employers=2, banks=1, ...`
4. The frontend should show:
   - Tertiary toast: "Filed return: N bank account(s), N employer(s)"
   - If current-AY already filed: error toast + warning banner

---

## How to search for all disabled blocks

All disabled blocks are marked with `REACTIVATE:` prefix comments.  To
find all of them:

```bash
# Backend
grep -n "REACTIVATE:" app/automation/job_worker.py

# Frontend
grep -n "REACTIVATE:" frontend/src/pages/ITRComputationPage.tsx
```

Each `REACTIVATE:` line is a commented-out line that should be
uncommented to reactivate the filed-return integration.

---

## What is NOT disabled (still active)

The following filed-return-related features remain active during testing:

1. **Filing-mode classification** — `app/automation/filing_mode_classifier.py`
   - Still detects `current_ay_already_filed`, `current_ay_is_revised`,
     `current_ay_filing_section` from the filed-return inventory.
   - The classification is based on the **inventory** (not the downloaded
     JSON), so it works even with the download disabled.

2. **Filing advisory** — `app/automation/filing_advisory.py`
   - Still generates the advisory with
     `requires_user_confirmation_for_revision=True` when the current-AY
     return exists.
   - The advisory is still logged: `Job NN: Advisory — already_filed=...`

3. **Advisory surface in reconciled output** — `job_worker.py`
   - Still attaches `reconciled["filing_advisory"]` and
     `reconciled["filing_mode_classification"]` to the reconciled output.
   - The frontend just doesn't show the blocking error because the
     merge block is disabled.

4. **Filed-return parser** — `app/engine/importers/filed_return_parser.py`
   - Still exists and is fully functional.
   - Just not called by the job worker during testing.

5. **Frontend mapper** — `frontend/src/utils/mapFiledReturnToFormData.ts`
   - Still exists and is fully functional.
   - Just not imported by `ITRComputationPage.tsx` during testing.

---

## Reactivation checklist

- [ ] Step 1: Uncomment filed-return download in `job_worker.py` (Step 4.2)
- [ ] Step 2: Uncomment filed-return parsing in `job_worker.py` (Step 4.6.1)
- [ ] Step 3: Uncomment reconciled output attachment in `job_worker.py` (Step 4.7)
- [ ] Step 4: Uncomment frontend import in `ITRComputationPage.tsx` (line 9)
- [ ] Step 5: Uncomment frontend merge block in `ITRComputationPage.tsx` (handleConfirmImport)
- [ ] Step 6: Uncomment tertiary toast + advisory error toast in `ITRComputationPage.tsx`
- [ ] Step 7: Uncomment advisory banner in `ITRComputationPage.tsx`
- [ ] Step 8: Verify backend compiles (`py -c "from app.automation.job_worker import _parse_prefill_file"`)
- [ ] Step 9: Verify frontend compiles (`npx tsc --noEmit`)
- [ ] Step 10: Run portal automation import — verify filed-return extraction + advisory toast/banner

---

## What the advisory flags mean

The advisory log line shows:

```
Job NN: Advisory — already_filed=True, is_revised=False, 
       filing_section=139(1), requires_confirmation=True, 
       download_ay=2025-26
```

| Flag | Meaning |
|---|---|
| `already_filed=True` | The current AY (2026-27) already has a filed return. |
| `is_revised=False` | The last filed ITR was an **original** return (section 139(1)), not a revised return (139(5)). |
| `filing_section=139(1)` | The filing section of the effective current-AY return. "139(1)" = original, "139(5)" = revised, "139(9)" = defective. |
| `requires_confirmation=True` | The user must explicitly confirm the revised-return flow before the current-AY filed-ITR data is populated. |
| `download_ay=2025-26` | The prior-year return (2025-26) was targeted for download as a read-only reference. |

### Business rules

| Scenario | Advisory flag | What happens |
|---|---|---|
| Current AY already filed (original) | `already_filed=True`, `is_revised=False` | Error toast: "ITR for AY X is already filed. To file a revised return, explicitly confirm..." |
| Current AY already filed (revised) | `already_filed=True`, `is_revised=True` | Error toast: "ITR for AY X is already filed as a REVISED return. The last filed ITR was a revised return." |
| Prior AY (normal filing) | `already_filed=False` | No blocking error — proceed normally |
