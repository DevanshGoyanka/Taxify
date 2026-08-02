# 05 — Reconciliation & Import Confirmation

**Date:** 2026-07-29  
**Status:** Complete  
**Depends on:** docs/04-ais-extractor-integration.md

---

## 1. What Was Built

After all 3 PDFs are extracted, `ais_extractor/reconciliation.py` cross-matches entries across 26AS, AIS, and TIS, producing a unified reconciled view. The reconciled result replaces raw parsed PDFs as the job's final payload. On the frontend, a confirmation modal appears when the job completes, showing a summary before the user confirms or cancels the import.

---

## 2. Files Changed / Created

| File | Change |
|---|---|
| `app/automation/job_worker.py` | Added `reconcile` import. Removed `_details` stripping (reconciliation needs it). Added Step 4.6 reconciliation call after extraction, storing reconciled result in `parsed_results`. |
| `frontend/src/api/itrAutomation.ts` | Added `parsed_results: ReconciledResults \| null` to `AutomationJob`. Added full TypeScript types for reconciled data shape (`ReconciledResults`, `ReconciledIncomeHead`, `ReconciledEntry`, `ReconciledUnmatchedEntry`). |
| `frontend/src/components/ImportConfirmationModal.tsx` | **New** — modal with inline styles (no Tailwind) showing reconciled income summary with two visual states. Uses CSS custom properties from `index.css` design system. |
| `frontend/src/pages/ITRComputationPage.tsx` | Added `ImportConfirmationModal` import, `showImportConfirmModal` + `reconciledImportData` state. Changed `handleAutomationComplete` to show modal when `parsed_results` is present. Added `handleConfirmImport` (placeholder for next chunk) and `handleCancelImport`. Passes `clientName`, `pan`, `assessmentYear` props to modal. |
| `frontend/src/components/StatusBox.tsx` | Added `extract` step to `STEP_INFO` and `ALL_STEPS` so the timeline shows "Extracting & reconciling data". |

---

## 3. Backend: Reconciliation Step

### Position in pipeline

```
Step 4:   unlock AIS + TIS PDFs
Step 4.5: extract (ais_extractor: parse all 3 PDFs)
Step 4.6: reconcile ← NEW — cross-match, priority selection, discrepancy check
Step 5:   logout
```

### Reconciliation function

Called as:

```python
from ais_extractor.reconciliation import reconcile

reconciled = reconcile(
    ais_data=parsed["ais"],
    tis_data=parsed["tis"],
    as26_data=parsed["26as"],
)
```

The function signature is exactly what `reconciliation.py` exports — no adaptation was needed. The existing `reconcile()` already takes dicts matching the `*_to_frontend_json()` output shapes from the extractors.

### Data shape adaptation

**One adaptation was made**: in Chunk 04, we stripped `_details` from 26AS rows (`row.pop("_details", None)`). This broke reconciliation because `_extract_26as()` reads `row["_details"]` to extract section codes and TDS amounts. **Fix**: removed the `_details` stripping. The `_details` key stays in the raw parsed output. Reconciliation strips it when building its own entries.

### Reconciliation logic (existing, unchanged)

- **Entry extraction**: Each document's results are flattened to `Entry` objects keyed by `category|source`
- **Cross-matching**: PAN-based fuzzy matching handles different display names for the same institution across documents
- **Priority**: TIS (accepted_by_taxpayer) > AIS (amount) > 26AS — the highest-priority value wins as `final_amount`
- **Discrepancy flagging**: If amounts differ by >₹1 across documents, the entry is marked `has_discrepancy: true` with detail
- **Unmatched tracking**: Entries appearing in only one document are listed separately

---

## 4. Reconciled Payload Shape (stored in `parsed_results`)

```json
{
  "metadata": {
    "pan": "EPPPG3078Q",
    "name": "DEVANSH SUNIT GOYANKA",
    "financial_year": "2025-26"
  },
  "income_heads": {
    "Income from Other Sources": {
      "income_head": "Income from Other Sources",
      "total_final": 1126.00,
      "total_tis": 1126.00,
      "total_ais": 1126.00,
      "total_as26": 0.00,
      "total_as26_tds": 0.00,
      "discrepancy_count": 0,
      "entries": [
        {
          "source": "INDIAN RAILWAY FINANCE CORPORATION (AAACI0681C.AN555)",
          "final_amount": 130.00,
          "amounts": { "tis": 130.00, "ais": 130.00, "as26": 0.00 },
          "as26_tds": 0.00,
          "present_in": { "tis": true, "ais": true, "as26": false },
          "has_discrepancy": false,
          "income_head": "Income from Other Sources"
        }
      ]
    }
  },
  "unmatched": { "tis_only": [], "ais_only": [], "as26_only": [] },
  "summary": {
    "total_entries": 3,
    "total_final_income": 1126.00,
    "total_discrepancies": 0,
    "matched_all_three": 0,
    "matched_two": 3,
    "matched_one": 0,
    "unmatched_tis": 0,
    "unmatched_ais": 0,
    "unmatched_as26": 0
  },
  "_extraction_errors": []  // only if errors
}
```

---

## 5. Frontend: Import Confirmation Modal

### Design system

The modal uses **inline styles referencing CSS custom properties** from `index.css` — NOT Tailwind (Tailwind is not configured in this project). Colors, border-radius, and spacing match the existing Save/JSON/PDF button patterns and the `EmployerReconciliationModal`. The overlay uses `z-index: 2000` to sit above the import dropdown.

### Props

| Prop | Type | Required | Purpose |
|---|---|---|---|
| `show` | `boolean` | Yes | Controls visibility |
| `results` | `ReconciledResults \| null` | Yes | The reconciled data payload |
| `clientName` | `string` | No | Client display name (from parent page) |
| `pan` | `string` | No | PAN (from parent page) |
| `assessmentYear` | `string` | No | Assessment year (e.g. "2025-26") |
| `onConfirm` | `() => void` | Yes | Confirm & Import handler |
| `onCancel` | `() => void` | Yes | Cancel handler |
| `onRetry` | `() => void` | No | Retry handler (defaults to `onCancel` if not provided) |

### When it appears

After `StatusPill` signals `onComplete` (job status = "completed"), `handleAutomationComplete` checks for `job.parsed_results`. If present, it sets `showImportConfirmModal = true`.

### Modal layout (top to bottom)

1. **Title**: `"Import from Portal"` in Crimson Pro (site heading font), with client name / PAN / AY as a small muted-color subtitle below it. No "Ready" label — the status line conveys state.

2. **Status line**: One clear sentence, not redundant. Two patterns:
   - **Has data**: *"N income entries imported — total: ₹X — N discrepancies flagged"*
   - **Empty/failed**: *"No reportable income was found in the portal documents."* (rendered in warning amber, with ⚠ icon)

3. **Income Summary table** (only when data exists): Compact table with columns: Income Head | Amount | Entries | TDS. Discrepancy counts shown inline as `⚠ N` badges next to the head name. Individual entry sources are not shown — the table is an income-head-level roll-up.

4. **Discrepancies callout** (when `total_discrepancies > 0`): Amber-bordered box using `var(--warning)` / `var(--warning-bg)` — matching how validation errors are styled elsewhere. Explains amounts differ between documents and the higher value is used.

5. **Unmatched entries callout** (when `unmatchedTotal > 0`): Blue info box using `var(--info)` / `var(--info-bg)`. Notes unmatched entries will be skipped.

6. **Extraction errors callout** (when `_extraction_errors` has entries): Red-bordered callout using `var(--danger)` / `var(--danger-bg)` with a bullet list of each error in plain language.

7. **Data source footer**: Small muted text — `"Data source: ITD portal • 2024-25 • EPPPG3078Q"` — left-aligned in the footer bar.

8. **Action buttons**: Right-aligned in the footer bar.
   - **Cancel**: Secondary/outline style — white background, `var(--text-secondary)` text, `var(--border-strong)` border. Matches the page's dismiss button style.
   - **Confirm & Import**: Primary style — `var(--gold)` background, white text. Matches the Save button color on the same page.
   - **Retry** (empty/failed state only): `var(--danger)` background, white text. Closes the modal (calls `onRetry || onCancel`).

### Two visual states

#### State 1: Has data (success)

- Header has a bottom border separator
- Status line in normal `text-secondary` color
- Income summary table shown
- Discrepancies / unmatched callouts shown if applicable
- "Confirm & Import" button enabled
- Example: 3 income entries, ₹1,126 total, 0 discrepancies

#### State 2: Empty / failed (zero usable data)

- No header border separator
- Status line in warning amber with ⚠ icon
- No income table (no data to show)
- Extraction errors in a red callout if present; otherwise a centered empty-state message
- "Confirm & Import" replaced with "Retry" (danger red), which calls `onRetry` (if provided) or `onCancel` to simply close the modal
- Example: 0 entries, both AIS and TIS extraction failed with "document closed or encrypted"

---

## 6. Test Results

### Backend reconciliation (simulated _run_job Step 4.6)

Tested with 3 real PDFs from `downloads/1/2025-26/` (PAN: EPPPG3078Q, FY: 2025-26):

| Metric | Value |
|---|---|
| Total entries | 3 |
| Income heads | 1 (Income from Other Sources) |
| Total final income | ₹1,126.00 |
| Discrepancies | 0 |
| Matched in 2 docs (TIS+AIS) | 3 |
| Matched in all 3 docs | 0 (no TDS entries in 26AS for this PAN) |
| Unmatched | 0 for all documents |

Breakdown:
- Dividend (Indian Railway Finance): ₹130 (TIS+AIS)
- Interest from deposit (SBI): ₹839 (TIS+AIS)
- Interest from savings bank (SBI): ₹157 (TIS+AIS)

### Frontend

- TypeScript: `npx tsc --noEmit` passes clean
- Vite build: completes in ~710ms, no errors
- Modal renders with real data from reconciled results

---

## 7. Decisions Made

1. **`_details` stripping removed** — Originally added in Chunk 04 to keep JSON "clean", but reconciliation reads `_details` for section codes and TDS amounts. The field stays; it's a small internal detail not exposed to the UI.

2. **Reconciliation errors are non-fatal** — If `reconcile()` itself throws, the raw parsed PDF data is stored instead and an error is logged. The job still completes (status="completed") rather than failing, since the PDFs were downloaded successfully.

3. **One-line status message replaces redundant summary** — The original modal showed multiple overlapping sentences saying the same thing (entry count, total, zero discrepancies, "no entries found"). Collapsed into one clear line determined by whether usable data exists.

4. **Cancel discards client-side only** — The reconciled data stays in the DB (`AutomationJob.parsed_results`). Only client state is cleared. If the user re-triggers the import, the modal will show again with the same data.

5. **No Tailwind — inline styles only** — Tailwind is not configured in the project. The old modal used Tailwind classes that rendered as unstyled text. The redesign uses inline `style` objects referencing CSS custom properties (`var(--gold)`, `var(--border)`, `var(--text-secondary)`, etc.) from `index.css`, matching the existing button and card patterns across the app.

6. **Empty/failed state replaces "Confirm & Import" with "Retry"** — When zero reportable data is extracted (0 entries, ₹0.00 total), the modal visually indicates a failure/empty state: amber status line with warning icon, extraction errors in a red callout, and "Retry" (danger-red button) replaces "Confirm & Import". "Retry" simply closes the modal — the user manually clicks Import again.

7. **Income level roll-up instead of per-entry table** — Instead of listing individual entries (up to 15 with truncation), the modal shows a compact income-head-level summary table (Income Head | Amount | Entries | TDS), keeping the modal focused on the import decision rather than micro-level data review.

---

## 8. Open Questions / Next Chunk

- **Chunk 06**: Wire `handleConfirmImport` to auto-populate `formData` from reconciled income heads — map "Salary" entries to employer/salary fields, "Income from Other Sources" to interest/dividend managers, "Capital Gains" to capital gains entries, TDS to TDS tab, etc.
- **TDS population**: Currently this PAN has no 26AS entries (no TDS). Test with a PAN that has TDS to verify the TDS fields populate correctly in the form.
