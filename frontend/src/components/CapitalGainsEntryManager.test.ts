import { describe, expect, it } from 'vitest';
import { hasNonSimplifiedCapitalGains } from '../components/CapitalGainsEntryManager';

describe('hasNonSimplifiedCapitalGains', () => {
  it('returns false for undefined, null, or empty schedule', () => {
    expect(hasNonSimplifiedCapitalGains(undefined)).toBe(false);
    expect(hasNonSimplifiedCapitalGains({})).toBe(false);
  });

  it('returns false when only simplified 112A data is present', () => {
    expect(hasNonSimplifiedCapitalGains({ simplified112A: { totalSaleConsideration: 100000, totalCostAcquisition: 50000 } })).toBe(false);
  });

  it('returns true when any full Schedule CG array has rows', () => {
    expect(hasNonSimplifiedCapitalGains({ stImmovable: [{ id: '1' }] })).toBe(true);
    expect(hasNonSimplifiedCapitalGains({ schedule112A: [{ isin: 'INE123456789' }] })).toBe(true);
    expect(hasNonSimplifiedCapitalGains({ vda: [{ head: 'CG' }] })).toBe(true);
    expect(hasNonSimplifiedCapitalGains({ deductionClaims: [{ section: '54EC' }] })).toBe(true);
  });

  it('returns true when aggregate objects have keys', () => {
    expect(hasNonSimplifiedCapitalGains({ aggregates: { stPassThrough: 1000 } })).toBe(true);
    expect(hasNonSimplifiedCapitalGains({ lossSetOff: { lt125_income: 50000 } })).toBe(true);
    expect(hasNonSimplifiedCapitalGains({ quarterly: { lt125_1: 50000 } })).toBe(true);
    expect(hasNonSimplifiedCapitalGains({ stSection48: { nriSttPaid: 100 } })).toBe(true);
  });

  it('returns false for empty aggregate objects', () => {
    expect(hasNonSimplifiedCapitalGains({ aggregates: {} })).toBe(false);
    expect(hasNonSimplifiedCapitalGains({ lossSetOff: {} })).toBe(false);
  });

  it('returns true when unutilized flags are not N', () => {
    expect(hasNonSimplifiedCapitalGains({ stUnutilizedFlag: 'Y' })).toBe(true);
    expect(hasNonSimplifiedCapitalGains({ ltUnutilizedFlag: 'X' })).toBe(true);
    expect(hasNonSimplifiedCapitalGains({ stUnutilizedFlag: 'N', ltUnutilizedFlag: 'N' })).toBe(false);
  });

  it('returns true when multiple non-simplified sections have data', () => {
    const schedule = {
      simplified112A: { totalSaleConsideration: 200000, totalCostAcquisition: 150000 },
      stImmovable: [{ id: 'st1' }],
      ltImmovable: [{ id: 'lt1' }],
      schedule112A: [{ isin: 'INE123456789' }],
      deductionClaims: [{ section: '54' }],
    };
    expect(hasNonSimplifiedCapitalGains(schedule)).toBe(true);
  });
});
