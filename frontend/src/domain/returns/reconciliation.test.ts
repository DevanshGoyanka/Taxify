import { describe, expect, it } from 'vitest';
import { createEmptyReturnDraft } from './factory';
import { reconcileImportedEvidence } from './reconciliation';
import { createReconciliationEvidence } from './evidence';

const ais = (amount: number) => createReconciliationEvidence({ source: 'AIS', code: 'SFT-016(SB)', category: 'interest from savings bank', reportedAmount: amount, processedAmount: amount, raw: { amount }, identity: ['ais-bank'] });
const tis = (amount: number) => createReconciliationEvidence({ source: 'TIS', category: 'Interest from savings bank', evidenceKind: 'CATEGORY_CONTROL', processedAmount: amount, acceptedAmount: amount, raw: { amount }, identity: ['tis-control'] });


describe('reconcileImportedEvidence', () => {
  it('creates a pending discrepancy for an AIS/TIS mismatch', () => {
    const draft = createEmptyReturnDraft();
    draft.reconciliation.evidence = [ais(100), tis(90)];
    const result = reconcileImportedEvidence(draft);
    expect(result.reconciliation.discrepancies).toHaveLength(1);
    expect(result.reconciliation.discrepancies[0]).toMatchObject({ category: 'interest from savings bank', aisAmount: 100, tisAcceptedAmount: 90, difference: 10, status: 'PENDING' });
  });

  it('preserves confirmation while amounts are unchanged and resets when changed', () => {
    const draft = reconcileImportedEvidence(Object.assign(createEmptyReturnDraft(), { reconciliation: { evidence: [ais(100), tis(90)], discrepancies: [] } }));
    draft.reconciliation.discrepancies[0].status = 'CONFIRMED_TIS';
    expect(reconcileImportedEvidence(draft).reconciliation.discrepancies[0].status).toBe('CONFIRMED_TIS');
    draft.reconciliation.evidence = [ais(101), tis(90)];
    expect(reconcileImportedEvidence(draft).reconciliation.discrepancies[0].status).toBe('PENDING');
  });

  it('does not compare acquisition-only rows', () => {
    const draft = createEmptyReturnDraft();
    draft.reconciliation.evidence = [
      createReconciliationEvidence({ source: 'AIS', code: 'SFT-18(Pur)', reportedAmount: 100, raw: {}, identity: ['purchase'] }),
      createReconciliationEvidence({ source: 'TIS', category: 'Purchase of securities and units of mutual funds', evidenceKind: 'CATEGORY_CONTROL', acceptedAmount: 80, raw: {}, identity: ['purchase-control'] }),
    ];
    expect(reconcileImportedEvidence(draft).reconciliation.discrepancies).toHaveLength(0);
  });
});
