/**
 * Capital Gains auto-population mapper.
 *
 * Consumes the flat `capital_gain_sales` and `capital_gain_purchases` lists
 * from a reconciled import payload (AIS/TIS/26AS via `reconcile()`) and
 * projects them into the typed `CapitalGainsSchedule` on the canonical draft.
 *
 * Routing (mirrors `ais_extractor/reconciliation.py`):
 *   - AIS SFT-17-LES / SFT-18-EMF / SFT-18-OTU sale-detail rows (asset_type
 *     "Long term") → `schedule112A[]` (listed equity / equity-MF LTCG scrips)
 *   - Same codes, asset_type "Short term"
 *     → `stEquity[]` (STCG equity/STT, JSON rows — engine computes later)
 *   - SFT-012 sale of immovable property
 *     → `stImmovable[]` / `ltImmovable[]` (dateOfSale, fullConsideration,
 *       stampDutyValue; long-term if > 24 months, conservatively true)
 *   - VDA rows (information_code 194S or asset_type/property indicating VDA)
 *     → `vda[]`
 *   - Summary-only sales (no per-scrip detail) → `simplified112A` aggregate
 *
 * Purchases (SFT-17-Pur / SFT-18-Pur / SFT-012(P)) are read-only reference
 * rows in the `purchases[]` list — they surface cost-base evidence but
 * produce no gain.
 *
 * The merge is id-based (`mergeDraft` handles id-merge for arrays), so
 * re-importing the same AIS appends no duplicates.
 *
 * @module mapCapitalGainsToDraftPatch
 */

import type { CapitalGainPurchase as SchedulePurchase, CapitalGainSale, CapitalGainsSchedule, ImmovableAssetGain, JsonRow, Scrip112A, VdaEntry } from '../domain/returns/types';
import type { ReturnDraftPatch } from '../domain/returns/draftPatch';

// ── Helpers ─────────────────────────────────────────────────────────────────

/** Parse a possibly-null/undefined/string number to a non-negative number. */
function toNum(value: number | null | undefined | string): number {
  if (value === null || value === undefined) return 0;
  const n = typeof value === 'string' ? Number(value.replace(/,/g, '')) : Number(value);
  return Number.isFinite(n) && n >= 0 ? n : 0;
}

/** Build a stable sale-derived id (deterministic — supports id-merge). */
function saleId(sale: CapitalGainSale, suffix = ''): string {
  const parts = [
    'cg',
    sale.information_code || 'unknown',
    sale.security_identifier || sale.id,
    String(sale.transaction_date || ''),
    suffix,
  ].filter(Boolean);
  return parts.join('-').replace(/\s+/g, '_').toUpperCase();
}

/** Build a stable purchase-derived id (deterministic — supports id-merge). */
function purchaseId(purchase: CapitalGainPurchase, suffix = 'pur'): string {
  const parts = [
    'cg',
    purchase.information_code || 'unknown',
    purchase.account_id || purchase.id,
    String(purchase.period || ''),
    suffix,
  ].filter(Boolean);
  return parts.join('-').replace(/\s+/g, '_').toUpperCase();
}

// ── Scrip mappers (112A / 115AD) ───────────────────────────────────────────

/** Map a SALE-side, long-term listed-equity/MF sale row → Scrip112A. */
function toScrip112A(sale: CapitalGainSale): Scrip112A {
  const isin = (sale.security_identifier || '').trim();
  return {
    id: saleId(sale),
    shareOnOrBefore: '',
    isin,
    name: (sale.security_name || '').trim(),
    quantity: toNum(sale.quantity),
    salePricePerUnit: toNum(sale.sale_price_per_unit),
    totalSaleValue: toNum(sale.total_sale_value),
    costWithoutIndexation: toNum(sale.acquisition_cost),
    acquisitionCost: toNum(sale.acquisition_cost),
    fmvPerUnit: toNum(sale.unit_fmv),
    totalFmv: toNum(sale.fair_market_value),
    transferExpenses: 0,
  };
}

/** ST equity rows (asset_type "Short term" on a listed-equity sale). */
function toStEquityRow(sale: CapitalGainSale): JsonRow {
  return {
    id: saleId(sale, 'steq'),
    fullConsideration: toNum(sale.total_sale_value),
    acquisitionCost: toNum(sale.acquisition_cost),
    improvementCost: 0,
    transferExpenses: 0,
    isin: sale.security_identifier || '',
    securityName: sale.security_name || '',
    quantity: toNum(sale.quantity),
    salePricePerUnit: toNum(sale.sale_price_per_unit),
  };
}

// ── VDA mapper ──────────────────────────────────────────────────────────────

/** Map a VDA sale row → VdaEntry. */
function toVdaEntry(sale: CapitalGainSale): VdaEntry {
  return {
    id: saleId(sale, 'vda'),
    dateOfAcquisition: '',
    dateOfTransfer: sale.transaction_date || '',
    head: 'CG',
    acquisitionCost: toNum(sale.acquisition_cost),
    consideration: toNum(sale.total_sale_value),
  };
}

// ── Immovable property mapper (SFT-012) ─────────────────────────────────────

/** Map a property-sale row → ImmovableAssetGain stub. */
function toImmovableGain(sale: CapitalGainSale, longTerm: boolean): ImmovableAssetGain {
  return {
    id: saleId(sale, longTerm ? 'lt' : 'st'),
    dateOfSale: sale.transaction_date || sale.reported_on || '',
    fullConsideration: toNum(sale.transaction_amount_assigned || sale.total_sale_value),
    acquisitionCost: 0,
    transferExpenses: 0,
    // Stamp duty value is the FMV for CG computation on immovable property.
    stampDutyValue: toNum(sale.stamp_duty_value),
    propertyAddress: sale.property_address || '',
  };
}

// ── Purchase reference mapper (informational, read-only) ──────────────────

/** Map a flat purchase row → a read-only SchedulePurchase. */
function toSchedulePurchase(p: CapitalGainPurchase): SchedulePurchase {
  return {
    id: purchaseId(p),
    informationCode: p.information_code || '',
    reportingSource: (p.reporting_source || '').trim(),
    securityName: (p.security_name || '').trim(),
    isin: '',
    period: p.period || p.reported_on || '',
    purchaseAmount: toNum(p.purchase_amount),
    accountId: (p.account_id || '').trim(),
    status: (p.status || '').trim(),
  };
}

// ── Category detection ─────────────────────────────────────────────────────

function isImmovableSale(sale: CapitalGainSale): boolean {
  const code = (sale.information_code || '').toUpperCase();
  const asset = (sale.asset_type || '').toLowerCase();
  return code.startsWith('SFT-012') || asset === 'immovable property';
}

function isVdaSale(sale: CapitalGainSale): boolean {
  const code = (sale.information_code || '').toUpperCase();
  return code.includes('194S') || /virtual digital asset/i.test(sale.security_name || '');
}

// ── Main mapper ─────────────────────────────────────────────────────────────

/**
 * Project flat capital-gain sale + purchase lists into a typed CG schedule patch.
 *
 * @param sales     The `capital_gain_sales` array from a reconciled import.
 * @param purchases The `capital_gain_purchases` array from a reconciled import.
 * @returns A `ReturnDraftPatch` whose `capitalGainsSchedule` sub-keys are
 *          populated for consumption by `mergeDraft`.
 */
export function mapCapitalGains(
  sales: CapitalGainSale[] | null | undefined,
  purchases: CapitalGainPurchase[] | null | undefined,
): ReturnDraftPatch {
  if ((!sales || sales.length === 0) && (!purchases || purchases.length === 0)) return {};

  const schedule112A: Scrip112A[] = [];
  const schedule115AD: Scrip112A[] = [];
  const purchaseList: SchedulePurchase[] = [];
  const stEquity: JsonRow[] = [];
  const ltImmovable: ImmovableAssetGain[] = [];
  const stImmovable: ImmovableAssetGain[] = [];
  const vda: VdaEntry[] = [];

  let simplifiedSale = 0;
  let simplifiedCost = 0;

  // ── Sales ──
  for (const sale of sales || []) {
    // Immovable property (SFT-012 sale of land/building)
    if (isImmovableSale(sale)) {
      // Conservatively long-term unless a short-term marker is present.
      const assetLower = (sale.asset_type || '').toLowerCase();
      const longTerm = !assetLower.includes('short');
      if (longTerm) ltImmovable.push(toImmovableGain(sale, true));
      else stImmovable.push(toImmovableGain(sale, false));
      continue;
    }

    // VDA (virtual digital asset — 194S)
    if (isVdaSale(sale)) {
      vda.push(toVdaEntry(sale));
      continue;
    }

    // Listed equity / equity-MF sale — route by term
    const assetType = (sale.asset_type || '').toLowerCase();
    const isLongTerm = assetType.includes('long');
    const isShortTerm = assetType.includes('short');

    // Aggregate into simplified112A for ITR-1/4 quick-entry.  Both detail
    // and summary-only rows contribute their sale amount and cost.
    if (isLongTerm || (!assetType && !isShortTerm)) {
      simplifiedSale += toNum(sale.total_sale_value);
      simplifiedCost += toNum(sale.acquisition_cost);
    }

    // Summary-only rows have no per-scrip detail — don't create scrips.
    if (sale.is_summary) continue;

    if (isShortTerm) {
      stEquity.push(toStEquityRow(sale));
    } else {
      const securityClass = (sale.security_class || '').toLowerCase();
      const isFii = securityClass.includes('fii') || securityClass.includes('fpi');
      if (isFii) schedule115AD.push(toScrip112A(sale));
      else schedule112A.push(toScrip112A(sale));
    }
  }

  // ── Purchases (read-only reference) ──
  for (const p of purchases || []) {
    purchaseList.push(toSchedulePurchase(p));
  }

  const schedule: Partial<CapitalGainsSchedule> = {};
  if (schedule112A.length) schedule.schedule112A = schedule112A;
  if (schedule115AD.length) schedule.schedule115AD = schedule115AD;
  if (purchaseList.length) schedule.purchases = purchaseList;
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
