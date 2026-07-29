# 06 — Form Population from Reconciled Data

**Date:** 2026-07-29  
**Status:** Complete  
**Depends on:** docs/05-reconciliation-and-confirmation.md

---

## 1. What Was Built

When the user clicks "Confirm & Import" in the `ImportConfirmationModal`, the reconciled data is mapped to the existing `formData` shape used by `ITRComputationPage`. Form fields update immediately — same visual effect as if the user had filled them manually. A discrepancy warning banner appears above the tab bar when the reconciliation flagged mismatches or unmatched entries.

---

## 2. Approach: Frontend-Only Mapper

After inspecting the existing prefill infrastructure (`app/services/prefill_service.py`, `app/routers/integration.py`, `prefill_to_itr1_input()`), the existing `autoPopulateAll` endpoint expects flat schemas with hardcoded employer names — it cannot handle `ReconciledResults` (which has `income_heads[head_name].entries[]` with `source, final_amount, present_in, has_discrepancy`).

**Decision**: Write a frontend-only mapper (`mapReconciledToFormData`) rather than adding a new backend endpoint. Reasons:
1. The mapping logic is 150 lines of straightforward category→field routing — no business logic that needs to live server-side
2. The existing `handleFileImport` for 26AS already does frontend mapping as precedent (lines 492–632 of ITRComputationPage.tsx)
3. Avoids adding a new API endpoint for a single-use mapping

---

## 3. Files Created / Changed

| File | Change |
|---|---|
| `frontend/src/utils/mapReconciledToFormData.ts` | **New** — mapping function that converts `ReconciledResults` → flat `formData` update object |
| `frontend/src/pages/ITRComputationPage.tsx` | Added `mapReconciledToFormData` import, `reconDiscrepancies` state, real `handleConfirmImport` body, and discrepancy warning banner |
| `Docs/06-form-population.md` | This file |

---

## 4. Mapping Logic

### `mapReconciledToFormData(results: ReconciledResults)` → `MapReconciledResult`

Returns `{ formDataUpdate, discrepancies, summary }`.

#### Category → Form Field Routing

| ReconciledEntry category | → formData field | → Entry array type |
|---|---|---|
| `salary`, `business receipts`, `professional fees`, `commission or brokerage` | `basic`, `tdsS192` | `employerEntries[]` |
| `dividend` | `dividends`, `dividendShares` | `dividendEntries[]` |
| `interest from *` | `interestSB`, `interestFD`, `tds194A` | `bankInterestEntries[]` |
| `sale of *`, `purchase of *`, `*property*`, `*Capital Gains*` | `ltcg112APre` | `capitalGainTransactions[]` |
| Any with `as26_tds > 0` | — | `tdsEntries[]` |

#### Entry Structure Builders

Each builder follows the same pattern as the 26AS import path:

```typescript
// Example: dividend entry
function buildDividendEntry(entry: ReconciledEntry) {
  return {
    companyName: entry.source || 'Company from Portal',
    companyPAN: '',
    dividendAmount: entry.final_amount,
    tdsDeducted: entry.as26_tds || 0,
    deductorTAN: '',
    isin: '',
    category: 'SHARES',
    section: entry.section || '',
  };
}
```

#### Safe Merge: Preserve Existing Entries

When the reconciled data has no entries for a particular category (e.g., no salary), the mapper **skips** the array field rather than overwriting with `[]`. This prevents wiping out entries the user may have added manually before running the import:

```typescript
const EMPTY_KEEP_KEYS = ['employerEntries', 'dividendEntries', 
  'bankInterestEntries', 'capitalGainTransactions', 'tdsEntries'];
for (const key of EMPTY_KEEP_KEYS) {
  if (Array.isArray(safeUpdate[key]) && safeUpdate[key].length === 0 
      && prev[key]?.length > 0) {
    delete safeUpdate[key];
  }
}
```

---

## 5. Discrepancy Handling

### Warning Banner

A yellow warning banner appears **above the tab bar** when `reconDiscrepancies` is non-empty. It shows:

- **Discrepancy message**: e.g. *"2 discrepancies found between AIS, TIS, and 26AS. The higher amount has been used. Review highlighted entries in Salary, Interest, Dividends, and Capital Gains tabs."*
- **Unmatched entries message**: e.g. *"3 entries from TIS could not be matched and were skipped."*
- **Dismiss button**: Clears the banner for the session

### Design Decision

I opted for **non-blocking warnings** rather than a reconciliation modal because:
1. The `ImportConfirmationModal` already showed the discrepancy summary before confirm
2. Per-entry discrepancy detail is available via `ReconciledEntry.has_discrepancy` and `discrepancy_detail`
3. The user already chose "Confirm & Import" despite seeing the discrepancy count

If you want per-entry resolution (like the `EmployerReconciliationModal` pattern), that can be a follow-up chunk.

---

## 6. `handleConfirmImport` Flow

```
User clicks "Confirm & Import"
  │
  ├── mapReconciledToFormData(reconciledImportData)
  │     └── returns { formDataUpdate, discrepancies, summary }
  │
  ├── setFormData(prev => { ...prev, ...safeUpdate })
  │     └── form fields populate immediately (dividendEntries, bankInterestEntries, 
  │         basic, interestSB, dividends, tdsEntries, etc.)
  │
  ├── Build discrepancy messages from:
  │     ├── discrepancies.length > 0
  │     └── summary.unmatched_* > 0
  │
  ├── setReconDiscrepancies(messages) → warning banner renders
  │
  ├── toast.success("Import complete: ₹1,126 income, 0 salary, 2 interest, 1 dividend...")
  │
  ├── itrApi.saveFormData(...) — background save to backend
  │
  └── Dismiss modal + cleanup state
```

---

## 7. Test Results

### Reconciled → Mapper verification (real data)

Tested with `EPPPG3078Q` (FY 2025-26):

| Reconciled Entry | Category | Amount | → Mapped to |
|---|---|---|---|
| INDIAN RAILWAY FINANCE CORP | dividend | ₹130 | `dividendEntries[0]`, `dividendShares: 130` |
| SBI | interest from deposit | ₹839 | `bankInterestEntries[0]`, `interestSB: 996` (sum) |
| SBI | interest from savings bank | ₹157 | `bankInterestEntries[1]`, `interestFD: 996` (sum) |

Expected form result after confirm:
```
dividendEntries: [{ companyName: "INDIAN RAILWAY FINANCE...", dividendAmount: 130 }]
bankInterestEntries: [
  { bankName: "STATE BANK OF INDIA...", interestEarned: 839 },
  { bankName: "STATE BANK OF INDIA...", interestEarned: 157 }
]
dividends: 130, dividendShares: 130
interestSB: 996, interestFD: 996
employerEntries: [] (preserved existing, if any)
tdsEntries: [] (preserved existing, if any)
```

### Build verification
- TypeScript: `npx tsc --noEmit` passes clean (121 modules)
- Vite production build: succeeds in 513ms, no warnings

---

## 8. Decisions Made

1. **Frontend-only mapper** — The existing backend prefill expects flat dicts with hardcoded names and can't consume `ReconciledResults` directly. A backend adapter would be a pass-through with no business logic. Keeping it in the frontend follows the precedent of the 26AS import path.

2. **Safe array merge** — Multi-entry arrays (`employerEntries`, `bankInterestEntries`, etc.) are only overwritten when the reconciled data has at least one entry for that category. This prevents the importer from erasing data the user added before running the portal import.

3. **Non-blocking discrepancy warnings** — The confirmation modal already showed discrepancy details. The post-import banner serves as a persistent reminder without blocking the user's workflow.

---

## 9. Open Questions / Next Chunk

- **Per-entry discrepancy resolution**: Currently discrepancies are flagged in the banner but individual entries don't show visual markers in the form. A future chunk could add orange highlight/badge on `EmployerEntryManager` / `BankInterestEntryManager` entries that have `has_discrepancy: true`.
- **Deduplication with existing entries**: If the user already has manual entries and imports duplicates (same bank name, same dividend company), they'll appear twice. A future chunk could add fuzzy-name dedup before merging.
- **TDS population**: The current test PAN has no TDS entries. Test with a PAN that has 26AS TDS data to verify `tdsEntries[]` populate correctly.
