import { describe, expect, it } from 'vitest';
import type { CapitalGainEvidence } from '../api/itrAutomation';
import { mapCapitalGainsEvidence } from './mapCapitalGainsToDraftPatch';

function scrip(overrides: Partial<CapitalGainEvidence> = {}): CapitalGainEvidence {
  return {
    evidence_id: 'ev-1',
    granularity: 'TRANSACTION_DETAIL',
    side: 'SALE',
    category: 'sale of securities and units of mutual fund',
    information_code: 'SFT-18-EMF',
    summary_sr_no: 1,
    detail_sr_no: 1,
    reporting_source: 'CAMS',
    reporting_entity_pan: 'AAACC3035G',
    transaction_date: '30/03/2026',
    security_name: 'Bandhan Financial Services Fund-Regular Plan-Growth',
    security_identifier: 'INF194KB1GE6',
    security_class: 'Unit of Equity Oriented Mutual Fund',
    asset_type: 'Long term',
    quantity: 1169.15,
    amount: 15000,
    acquisition_cost: 16044.20,
    sale_price_per_unit: 12.83,
    unit_fmv: 0,
    fair_market_value: 0,
    stt_amount: 0.15,
    parser_confidence: 'HIGH',
    ...overrides,
  };
}

describe('mapCapitalGainsEvidence', () => {
  it('returns an empty patch for null/undefined/empty evidence', () => {
    expect(mapCapitalGainsEvidence(null)).toEqual({});
    expect(mapCapitalGainsEvidence(undefined)).toEqual({});
    expect(mapCapitalGainsEvidence([])).toEqual({});
  });

  it('maps a long-term listed-equity SALE row → schedule112A scrip', () => {
    const patch = mapCapitalGainsEvidence([scrip()]);
    const sched = patch.capitalGainsSchedule;
    expect(sched?.schedule112A).toHaveLength(1);
    const row = sched?.schedule112A?.[0];
    expect(row).toMatchObject({
      isin: 'INF194KB1GE6',
      name: 'Bandhan Financial Services Fund-Regular Plan-Growth',
      quantity: 1169.15,
      salePricePerUnit: 12.83,
      totalSaleValue: 15000,
      acquisitionCost: 16044.20,
      fmvPerUnit: 0,
      totalFmv: 0,
      shareOnOrBefore: '',
    });
    // Deterministic id for id-merge dedup
    expect(row?.id).toContain('INF194KB1GE6');
  });

  it('aggregates SALE scrips into simplified112A quick-entry totals', () => {
    const patch = mapCapitalGainsEvidence([
      scrip({ amount: 15000, acquisition_cost: 16000 }),
      scrip({ evidence_id: 'ev-2', detail_sr_no: 2, amount: 50000, acquisition_cost: 40000 }),
    ]);
    expect(patch.capitalGainsSchedule?.simplified112A).toEqual({
      totalSaleConsideration: 65000,
      totalCostAcquisition: 56000,
    });
    expect(patch.capitalGainsSchedule?.schedule112A).toHaveLength(2);
  });

  it('routes short-term listed-equity SALE rows → stEquity (not 112A)', () => {
    const patch = mapCapitalGainsEvidence([scrip({ asset_type: 'Short term' })]);
    // schedule112A key is absent (no LTCG scrips) — mergeDraft preserves base
    expect(patch.capitalGainsSchedule?.schedule112A).toBeUndefined();
    expect(patch.capitalGainsSchedule?.stEquity).toHaveLength(1);
    expect(patch.capitalGainsSchedule?.stEquity?.[0]).toMatchObject({
      isin: 'INF194KB1GE6',
      fullConsideration: 15000,
      acquisitionCost: 16044.20,
    });
    // Short-term rows don't aggregate into simplified112A (112A is LTCG-only)
    expect(patch.capitalGainsSchedule?.simplified112A).toBeUndefined();
  });

  it('skips PURCHASE-side rows (they are evidence only, not gains)', () => {
    const patch = mapCapitalGainsEvidence([scrip({ side: 'PURCHASE' })]);
    expect(patch.capitalGainsSchedule?.schedule112A).toBeUndefined();
    expect(patch.capitalGainsSchedule?.stEquity).toBeUndefined();
    expect(patch.capitalGainsSchedule?.simplified112A).toBeUndefined();
  });

  it('maps property-sale (194IA/SFT-012) rows → ltImmovable by default', () => {
    const patch = mapCapitalGainsEvidence([
      scrip({
        category: 'sale of land or building',
        information_code: 'SFT-012',
        security_identifier: '',
        security_name: '',
        transaction_date: '15/02/2026',
        amount: 5000000,
        acquisition_cost: 2000000,
        asset_type: '',
      }),
    ]);
    expect(patch.capitalGainsSchedule?.ltImmovable).toHaveLength(1);
    expect(patch.capitalGainsSchedule?.ltImmovable?.[0]).toMatchObject({
      dateOfSale: '15/02/2026',
      fullConsideration: 5000000,
      acquisitionCost: 2000000,
    });
    // stImmovable key absent (no short-term property)
    expect(patch.capitalGainsSchedule?.stImmovable).toBeUndefined();
  });

  it('maps VDA rows → vda[]', () => {
    const patch = mapCapitalGainsEvidence([
      scrip({
        category: 'receipts on transfer of virtual digital asset',
        information_code: 'SFT-128',
        security_identifier: '',
        security_name: '',
        amount: 100000,
        acquisition_cost: 30000,
        transaction_date: '20/03/2026',
        asset_type: '',
      }),
    ]);
    expect(patch.capitalGainsSchedule?.vda).toHaveLength(1);
    expect(patch.capitalGainsSchedule?.vda?.[0]).toMatchObject({
      dateOfTransfer: '20/03/2026',
      head: 'CG',
      acquisitionCost: 30000,
      consideration: 100000,
    });
  });

  it('routes FII/FPI scrips → schedule115AD', () => {
    const patch = mapCapitalGainsEvidence([
      scrip({ security_class: 'FII units' }),
      scrip({ security_class: 'Unit of Equity Oriented Mutual Fund' }),
    ]);
    expect(patch.capitalGainsSchedule?.schedule115AD).toHaveLength(1);
    expect(patch.capitalGainsSchedule?.schedule112A).toHaveLength(1);
  });

  it('does not double-count when re-imported: ids are deterministic', () => {
    const evidence = [scrip()];
    const a = mapCapitalGainsEvidence(evidence);
    const b = mapCapitalGainsEvidence(evidence);
    expect(a.capitalGainsSchedule?.schedule112A?.[0].id).toBe(
      b.capitalGainsSchedule?.schedule112A?.[0].id,
    );
  });

  it('handles null/undefined numeric fields gracefully (zero, not NaN)', () => {
    const patch = mapCapitalGainsEvidence([
      scrip({ quantity: null, acquisition_cost: null, unit_fmv: null, fair_market_value: null, sale_price_per_unit: null }),
    ]);
    const row = patch.capitalGainsSchedule?.schedule112A?.[0];
    expect(row?.quantity).toBe(0);
    expect(row?.acquisitionCost).toBe(0);
    expect(row?.fmvPerUnit).toBe(0);
    expect(row?.totalFmv).toBe(0);
    expect(row?.salePricePerUnit).toBe(0);
  });
});
