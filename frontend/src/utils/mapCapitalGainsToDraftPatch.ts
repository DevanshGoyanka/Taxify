/**
 * Capital Gains auto-population mapper.
 *
 * Consumes `capital_gain_evidence` rows from a reconciled import payload
 * (AIS/TIS/26AS) and projects them into the typed `CapitalGainsSchedule`
 * on the canonical draft.
 *
 * Routing (header-driven, mirrors `ais_extractor/reconciliation.py`):
 *   - AIS SFT-17-LES / SFT-18-EMF sale-detail rows (asset_type "Long term")
 *     → `schedule112A[]` (listed equity / equity-MF LTCG scrips)
 *   - Same codes, asset_type "Short term"
 *     → `stEquity[]` (STCG equity/STT, JSON rows — engine computes later)
 *   - FII/FPI scrips (security_class contains "FII" or "FPI" / code SFT-18-EMF
 *     with AMC source matching FPI patterns)
 *     → `schedule115AD[]` (currently routed to 112A; refined in Phase 5)
 *   - SFT-012 / 26AS 194IA (sale of land/building)
 *     → `stImmovable[]` / `ltImmovable[]` stubs (dateOfSale, fullConsideration,
 *       acquisitionCost; holding period derived from transaction_date when
 *       available; long-term if > 24 months)
 *   - VDA rows (category contains "virtual digital asset")
 *     → `vda[]`
 *   - SALE-side aggregate totals (summary-only evidence)
 *     → `simplified112A` quick-entry aggregate (sale consideration + cost)
 *
 * The merge is id-based (`mergeDraft` handles id-merge for arrays), so
 * re-importing the same AIS appends no duplicates.
 *
 * @module mapCapitalGainsToDraftPatch
 */

import type { CapitalGainEvidence } from '../api/itrAutomation';
import type { CapitalGainsSchedule, ImmovableAssetGain, JsonRow, Scrip112A, VdaEntry } from '../domain/returns/types';
import type { ReturnDraftPatch } from '../domain/returns/draftPatch';

// ── Helpers ─────────────────────────────────────────────────────────────────

/** Parse a possibly-null/undefined/string number to a non-negative number. */
function toNum(value: number | null | undefined | string): number {
  if (value === null || value === undefined) return 0;
  const n = typeof value === 'string' ? Number(value.replace(/,/g, '')) : Number(value);
  return Number.isFinite(n) && n >= 0 ? n : 0;
}

/** Build a stable evidence-derived id (deterministic — supports id-merge). */
function evidenceId(evidence: CapitalGainEvidence, suffix = ''): string {
  const parts = [
    'cg',
    evidence.information_code || 'unknown',
    evidence.security_identifier || `${evidence.summary_sr_no}-${evidence.detail_sr_no ?? 'x'}`,
    String(evidence.transaction_date || evidence.quarter || ''),
    suffix,
  ].filter(Boolean);
  return parts.join('-').replace(/\s+/g, '_').toUpperCase();
}

/** Determine the long-term holding period from a transaction date.
 * Returns true when the asset was held > 24 months (land/building) or
 * > 12 months (listed securities — handled by asset_type directly). */
function isLongTermImmovable(transactionDate: string | undefined, acquisitionDate?: string): boolean {
  // AIS/26AS property-sale rows don't reliably carry the purchase date, so
  // we conservatively treat property sales as long-term unless the asset_type
  // explicitly says "Short term" (the evidence field is for securities; for
  // property it's usually empty). Phase 5 will refine this once corpus 194IA
  // rows are inspected for purchase-date columns.
  if (acquisitionDate && transactionDate) {
    const acq = new Date(acquisitionDate);
    const sale = new Date(transactionDate);
    if (!Number.isNaN(acq.getTime()) && !Number.isNaN(sale.getTime())) {
      const months = (sale.getFullYear() - acq.getFullYear()) * 12 + (sale.getMonth() - acq.getMonth());
      return months > 24;
    }
  }
  return true;
}

// ── Scrip mappers (112A / 115AD) ───────────────────────────────────────────

/** Map a SALE-side, long-term listed-equity/MF evidence row → Scrip112A. */
function toScrip112A(evidence: CapitalGainEvidence): Scrip112A {
  const isin = (evidence.security_identifier || '').trim();
  return {
    id: evidenceId(evidence),
    // AIS carries "BE"/"AE" semantics via the `acquired_before_31_jan_2018`
    // boolean; if unset, we default to 'AE' (after 31-Jan-2018) — the engine
    // applies grandfathering only when 'BE' is set.
    shareOnOrBefore: evidence.acquired_before_31_jan_2018 === true ? 'BE' : evidence.acquired_before_31_jan_2018 === false ? 'AE' : '',
    isin,
    name: (evidence.security_name || '').trim(),
    quantity: toNum(evidence.quantity),
    salePricePerUnit: toNum(evidence.sale_price_per_unit),
    totalSaleValue: toNum(evidence.amount),
    costWithoutIndexation: toNum(evidence.acquisition_cost),
    acquisitionCost: toNum(evidence.acquisition_cost),
    fmvPerUnit: toNum(evidence.unit_fmv),
    totalFmv: toNum(evidence.fair_market_value),
    transferExpenses: 0, // STT is not a transfer expense; engine handles it separately
  };
}

// ── VDA mapper ──────────────────────────────────────────────────────────────

/** Map a VDA evidence row → VdaEntry. */
function toVdaEntry(evidence: CapitalGainEvidence): VdaEntry {
  return {
    id: evidenceId(evidence, 'vda'),
    dateOfAcquisition: '',
    dateOfTransfer: evidence.transaction_date || '',
    head: 'CG',
    acquisitionCost: toNum(evidence.acquisition_cost),
    consideration: toNum(evidence.amount),
  };
}

// ── Immovable property mapper (194IA / SFT-012) ────────────────────────────

/** Map a property-sale evidence row → ImmovableAssetGain stub. */
function toImmovableGain(evidence: CapitalGainEvidence, longTerm: boolean): ImmovableAssetGain {
  return {
    id: evidenceId(evidence, longTerm ? 'lt' : 'st'),
    dateOfSale: evidence.transaction_date || '',
    fullConsideration: toNum(evidence.amount),
    acquisitionCost: toNum(evidence.acquisition_cost),
    transferExpenses: 0,
  };
}

// ── Category detection ─────────────────────────────────────────────────────

function isVdaCategory(category: string): boolean {
  return /virtual digital asset/i.test(category);
}

function isPropertyCategory(category: string): boolean {
  return /immovable|land or building|land or building or both/i.test(category);
}

function isListedEquityCategory(category: string): boolean {
  return /sale of securities|securities and units of mutual fund/i.test(category);
}

/** ST equity rows (asset_type "Short term" on a listed-equity sale). */
function toStEquityRow(evidence: CapitalGainEvidence): JsonRow {
  return {
    id: evidenceId(evidence, 'steq'),
    fullConsideration: toNum(evidence.amount),
    acquisitionCost: toNum(evidence.acquisition_cost),
    improvementCost: 0,
    transferExpenses: 0,
    isin: evidence.security_identifier || '',
    securityName: evidence.security_name || '',
    quantity: toNum(evidence.quantity),
    salePricePerUnit: toNum(evidence.sale_price_per_unit),
  };
}

// ── Main mapper ─────────────────────────────────────────────────────────────

/**
 * Project capital-gain evidence rows into a typed CG schedule patch.
 *
 * @param evidence  The `capital_gain_evidence` array from a reconciled import
 *                  payload (AIS/TIS/26AS via `reconcile()`).
 * @returns A `ReturnDraftPatch` whose `capitalGainsSchedule` sub-keys are
 *          populated for consumption by `mergeDraft`.
 */
export function mapCapitalGainsEvidence(
  evidence: CapitalGainEvidence[] | null | undefined,
): ReturnDraftPatch {
  if (!evidence || evidence.length === 0) return {};

  const schedule112A: Scrip112A[] = [];
  const schedule115AD: Scrip112A[] = [];
  const stEquity: JsonRow[] = [];
  const ltImmovable: ImmovableAssetGain[] = [];
  const stImmovable: ImmovableAssetGain[] = [];
  const vda: VdaEntry[] = [];

  // Simplified 112A aggregate (for ITR-1/4 quick-entry): sale + cost totals
  // from SALE-side, TRANSACTION_DETAIL listed-equity rows.
  let simplifiedSale = 0;
  let simplifiedCost = 0;

  for (const row of evidence) {
    const category = row.category || '';
    const side = row.side || 'UNKNOWN';
    const assetType = (row.asset_type || '').toLowerCase();
    const isLongTerm = assetType.includes('long');
    const isShortTerm = assetType.includes('short');
    // A REPORTING_SOURCE_AGGREGATE row is a category total — it has no scrip
    // identity (no ISIN, no per-scrip cost, no quantity).  It must NOT become
    // a Schedule 112A scrip, an stEquity row, an immovable stub, or a VDA
    // entry: doing so produces phantom rows whose sale value is the category
    // aggregate and whose cost/ISIN are zero.  Only TRANSACTION_DETAIL rows
    // carry per-scrip facts.  A SALE-side aggregate may still contribute its
    // amount to the simplified112A quick-entry aggregate below.
    const isDetail = row.granularity === 'TRANSACTION_DETAIL';

    // VDA — any side, but only transaction-detail rows (aggregates have no
    // per-asset acquisition cost / consideration split).
    if (isVdaCategory(category)) {
      if (isDetail) vda.push(toVdaEntry(row));
      continue;
    }

    // Immovable property (land/building) — SFT-012 / 26AS 194IA.  Only
    // transaction-detail rows become property stubs; an aggregate has no
    // purchase date / per-property consideration.
    if (isPropertyCategory(category)) {
      if (!isDetail) continue;
      const longTerm = isLongTermImmovable(row.transaction_date);
      if (longTerm) ltImmovable.push(toImmovableGain(row, true));
      else stImmovable.push(toImmovableGain(row, false));
      continue;
    }

    // Listed equity / equity-MF sale — route by term + side
    if (isListedEquityCategory(category)) {
      // Purchase-side rows don't create gains; they're evidence only.
      if (side === 'PURCHASE') continue;

      // Aggregate into simplified112A for ITR-1/4 quick-entry.  Both
      // transaction-detail and SALE-side aggregate rows contribute their
      // sale amount (and cost, where present) to the simplified totals —
      // for a client whose AIS carries only a summary sale (no per-scrip
      // detail), the aggregate is the only sale figure available.
      if (isLongTerm) {
        simplifiedSale += toNum(row.amount);
        simplifiedCost += toNum(row.acquisition_cost);
      }

      // Only transaction-detail rows become scrips.  A summary aggregate
      // has no ISIN / per-scrip cost and would be a phantom scrip.
      if (!isDetail) continue;

      if (isShortTerm) {
        // STCG listed equity → stEquity (engine computes 111A/115AD(1)(b)(ii) proviso)
        stEquity.push(toStEquityRow(row));
      } else {
        // LTCG listed equity → Schedule 112A scrips (or 115AD for FII/FPI)
        // Heuristic: 115AD applies to FII/FPI — detect via security_class or
        // reporting source.  Refined in Phase 5 once corpus confirms the
        // FII/FPI marker.
        const securityClass = (row.security_class || '').toLowerCase();
        const isFii = securityClass.includes('fii') || securityClass.includes('fpi');
        if (isFii) schedule115AD.push(toScrip112A(row));
        else schedule112A.push(toScrip112A(row));
      }
      continue;
    }
    // Non-CG categories are ignored here; they're handled by the other mappers.
  }

  // Build the patch — only emit keys that have data so `mergeDraft` preserves
  // existing schedule contents untouched for empty keys.
  const schedule: Partial<CapitalGainsSchedule> = {};
  if (schedule112A.length) schedule.schedule112A = schedule112A;
  if (schedule115AD.length) schedule.schedule115AD = schedule115AD;
  if (stEquity.length) schedule.stEquity = stEquity;
  if (ltImmovable.length) schedule.ltImmovable = ltImmovable;
  if (stImmovable.length) schedule.stImmovable = stImmovable;
  if (vda.length) schedule.vda = vda;
  if (simplifiedSale > 0 || simplifiedCost > 0) {
    schedule.simplified112A = { totalSaleConsideration: simplifiedSale, totalCostAcquisition: simplifiedCost };
  }

  if (Object.keys(schedule).length === 0) return {};
  return { capitalGainsSchedule: schedule };
}
