import { describe, expect, it } from 'vitest';
import { createReconciliationEvidence } from './evidence';

describe('createReconciliationEvidence', () => {
  it('preserves the complete raw source entry untouched', () => {
    const raw = { information_code: 'TDS-999', custom_field: 'keep me', nested: { deep: 7 }, amount: '1,234' };
    const evidence = createReconciliationEvidence({ source: 'AIS', code: 'TDS-999', raw, identity: ['TDS-999'] });
    expect(evidence.raw).toEqual(raw);
    expect(evidence.raw).not.toBe(raw);
  });

  it('flags unknown codes as requiring review (never taxable)', () => {
    const evidence = createReconciliationEvidence({ source: 'AIS', code: 'TDS-XYZ-UNKNOWN', raw: {}, identity: ['TDS-XYZ-UNKNOWN'] });
    expect(evidence.role).toBe('PARSER_WARNING');
    expect(evidence.requiresReview).toBe(true);
    expect(evidence.relatedTab).toBe('RECONCILIATION');
  });

  it('parses comma-formatted amounts into numbers', () => {
    const evidence = createReconciliationEvidence({
      source: 'AIS', code: 'SFT-016(SB)', category: 'interest from savings bank',
      reportedAmount: '1,234', processedAmount: '1,234', taxAmount: '0', raw: {}, identity: ['SFT-016(SB)'],
    });
    expect(evidence.reportedAmount).toBe(1234);
    expect(evidence.processedAmount).toBe(1234);
    expect(evidence.taxAmount).toBe(0);
    expect(evidence.role).toBe('TAXABLE_ITR1');
    expect(evidence.requiresReview).toBe(false);
  });

  it('produces stable deterministic ids for the same identity', () => {
    const a = createReconciliationEvidence({ source: 'AIS', code: 'TDS-192', raw: {}, identity: ['TDS-192', 'TAN'] });
    const b = createReconciliationEvidence({ source: 'AIS', code: 'TDS-192', raw: {}, identity: ['TDS-192', 'TAN'] });
    expect(a.id).toBe(b.id);
  });
});
