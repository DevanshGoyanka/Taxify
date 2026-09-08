import { describe, expect, it } from 'vitest';
import type { CapitalGainPurchase, CapitalGainSale } from '../api/itrAutomation';
import { mapCapitalGains } from './mapCapitalGainsToDraftPatch';

function sale(overrides: Partial<CapitalGainSale> = {}): CapitalGainSale {
  return {
    id: 'sale-1',
    information_code: 'SFT-18-EMF',
    reporting_source: 'CAMS',
    reporting_entity_pan: 'AAACC3035G',
    security_name: 'Bandhan Financial Services Fund-Regular Plan-Growth',
    security_identifier: 'INF194KB1GE6',
    quantity: 1169.15,
    sale_price_per_unit: 12.83,
    total_sale_value: 15000,
    acquisition_cost: 16044.20,
    fair_market_value: 0,
    unit_fmv: 0,
    transaction_date: '30/03/2026',
    asset_type: 'Long term',
    security_class: 'Unit of Equity Oriented Mutual Fund',
    status: 'Active',
    is_summary: false,
    ...overrides,
  };
}

function purchase(overrides: Partial<CapitalGainPurchase> = {}): CapitalGainPurchase {
  return {
    id: 'pur-1',
    information_code: 'SFT-18(Pur)',
    reporting_source: 'CAMS',
    reporting_entity_pan: 'AAACC3035G',
    security_name: 'HDFC Asset Management Company Limited(H)',
    account_id: '85102941',
    period: 'Q4(Jan-Mar)',
    purchase_amount: 5000,
    status: 'Active',
    is_summary: false,
    ...overrides,
  };
}

describe('mapCapitalGains', () => {
  it('returns an empty patch for null/undefined/empty inputs', () => {
    expect(mapCapitalGains(null, null)).toEqual({});
    expect(mapCapitalGains(undefined, undefined)).toEqual({});
    expect(mapCapitalGains([], [])).toEqual({});
  });

  it('maps a long-term listed-equity sale → schedule112A scrip', () => {
    const patch = mapCapitalGains([sale()], []);
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
    expect(row?.id).toContain('INF194KB1GE6');
  });

  it('aggregates LTCG sales into simplified112A quick-entry totals', () => {
    const patch = mapCapitalGains([
      sale({ total_sale_value: 15000, acquisition_cost: 16000 }),
      sale({ id: 'sale-2', total_sale_value: 50000, acquisition_cost: 40000 }),
    ], []);
    expect(patch.capitalGainsSchedule?.simplified112A).toEqual({
      totalSaleConsideration: 65000,
      totalCostAcquisition: 56000,
    });
    expect(patch.capitalGainsSchedule?.schedule112A).toHaveLength(2);
  });

  it('routes short-term listed-equity sales → stEquity (not 112A)', () => {
    const patch = mapCapitalGains([sale({ asset_type: 'Short term' })], []);
    expect(patch.capitalGainsSchedule?.schedule112A).toBeUndefined();
    expect(patch.capitalGainsSchedule?.stEquity).toHaveLength(1);
    expect(patch.capitalGainsSchedule?.stEquity?.[0]).toMatchObject({
      isin: 'INF194KB1GE6',
      fullConsideration: 15000,
      acquisitionCost: 16044.20,
    });
    expect(patch.capitalGainsSchedule?.simplified112A).toBeUndefined();
  });

  it('maps property-sale (SFT-012) rows → ltImmovable with stamp duty', () => {
    const patch = mapCapitalGains([
      sale({
        id: 'prop-1',
        information_code: 'SFT-012',
        security_name: 'Survey Number 63/1',
        security_identifier: '',
        transaction_date: '05/07/2025',
        total_sale_value: 3725000,
        acquisition_cost: null,
        asset_type: 'Immovable Property',
        property_address: 'Survey Number 63/1',
        stamp_duty_value: 0,
        transaction_amount_assigned: 3725000,
      }),
    ], []);
    expect(patch.capitalGainsSchedule?.ltImmovable).toHaveLength(1);
    expect(patch.capitalGainsSchedule?.ltImmovable?.[0]).toMatchObject({
      dateOfSale: '05/07/2025',
      fullConsideration: 3725000,
      propertyAddress: 'Survey Number 63/1',
    });
    expect(patch.capitalGainsSchedule?.stImmovable).toBeUndefined();
  });

  it('maps VDA sales → vda[]', () => {
    const patch = mapCapitalGains([
      sale({
        id: 'vda-1',
        information_code: '194S',
        security_name: 'Bitcoin',
        security_identifier: '',
        total_sale_value: 100000,
        acquisition_cost: 30000,
        transaction_date: '20/03/2026',
        asset_type: '',
      }),
    ], []);
    expect(patch.capitalGainsSchedule?.vda).toHaveLength(1);
    expect(patch.capitalGainsSchedule?.vda?.[0]).toMatchObject({
      dateOfTransfer: '20/03/2026',
      head: 'CG',
      acquisitionCost: 30000,
      consideration: 100000,
    });
  });

  it('routes FII/FPI scrips → schedule115AD', () => {
    const patch = mapCapitalGains([
      sale({ security_class: 'FII units' }),
      sale({ id: 'sale-2', security_class: 'Unit of Equity Oriented Mutual Fund' }),
    ], []);
    expect(patch.capitalGainsSchedule?.schedule115AD).toHaveLength(1);
    expect(patch.capitalGainsSchedule?.schedule112A).toHaveLength(1);
  });

  it('does not double-count when re-imported: ids are deterministic', () => {
    const s = [sale()];
    const a = mapCapitalGains(s, []);
    const b = mapCapitalGains(s, []);
    expect(a.capitalGainsSchedule?.schedule112A?.[0].id).toBe(
      b.capitalGainsSchedule?.schedule112A?.[0].id,
    );
  });

  it('handles null/undefined numeric fields gracefully (zero, not NaN)', () => {
    const patch = mapCapitalGains([
      sale({ quantity: null, acquisition_cost: null, unit_fmv: null, fair_market_value: null, sale_price_per_unit: null }),
    ], []);
    const row = patch.capitalGainsSchedule?.schedule112A?.[0];
    expect(row?.quantity).toBe(0);
    expect(row?.acquisitionCost).toBe(0);
    expect(row?.fmvPerUnit).toBe(0);
    expect(row?.totalFmv).toBe(0);
    expect(row?.salePricePerUnit).toBe(0);
  });

  it('does NOT create a phantom scrip from a summary-only sale', () => {
    const summarySale = sale({
      id: 'summary-1',
      is_summary: true,
      security_identifier: '',
      security_name: '',
      quantity: null,
      sale_price_per_unit: null,
      acquisition_cost: null,
      total_sale_value: 496301,
      asset_type: '',
      security_class: '',
    });
    const patch = mapCapitalGains([summarySale], []);
    expect(patch.capitalGainsSchedule?.schedule112A ?? []).toHaveLength(0);
    expect(patch.capitalGainsSchedule?.schedule115AD ?? []).toHaveLength(0);
    expect(patch.capitalGainsSchedule?.stEquity ?? []).toHaveLength(0);
  });

  it('maps purchase rows → purchases[] (read-only reference)', () => {
    const patch = mapCapitalGains([], [purchase(), purchase({ id: 'pur-2', purchase_amount: 3000 })]);
    expect(patch.capitalGainsSchedule?.purchases).toHaveLength(2);
    const p = patch.capitalGainsSchedule?.purchases?.[0];
    expect(p).toMatchObject({
      informationCode: 'SFT-18(Pur)',
      securityName: 'HDFC Asset Management Company Limited(H)',
      accountId: '85102941',
      period: 'Q4(Jan-Mar)',
      purchaseAmount: 5000,
    });
  });
});
