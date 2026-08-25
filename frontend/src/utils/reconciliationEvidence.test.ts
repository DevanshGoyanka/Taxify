import { describe, expect, it } from 'vitest';
import { mapAisToDraftPatch } from './mapAisToDraftPatch';
import { mapTisToDraftPatch } from './mapTisToDraftPatch';
import { map26asToDraftPatch } from './map26asToDraftPatch';
import { mergeDraft } from '../domain/returns/draftPatch';
import { createEmptyReturnDraft } from '../domain/returns/factory';
import { reconcileImportedEvidence } from '../domain/returns/reconciliation';

const realAis = {
  metadata: { pan: 'EPPPG3078Q', financial_year: '2025-26' },
  income_heads: {
    'Income from Other Sources': {
      income_head: 'Income from Other Sources', total_amount: 157.0, entries: [
        { sr_no: 1, information_code: 'SFT-016(SB)', information_description: 'Interest from savings bank', information_source: 'BANK LIMITED (AAACS8577K.AB703)', amount: 157.0, category: 'interest from savings bank', section: 'B2', detail_header: ['SR. NO.', 'INTEREST AMOUNT', 'STATUS'], details: [{ sr_no: 1, data: { col_0: '1', col_1: '157', col_2: 'Active' } }] },
        { sr_no: 2, information_code: 'TDS-999-UNKNOWN', information_description: 'Unknown code', information_source: 'UNKNOWN PARTY (PQR1234X)', amount: 999.0, category: 'unknown', section: 'B1', detail_header: ['SR. NO.', 'AMOUNT PAID', 'TDS DEDUCTED', 'STATUS'], details: [{ sr_no: 1, data: { col_0: '1', col_1: '999', col_2: '0', col_3: 'Active' } }] },
      ],
    },
  },
};

const realTis = {
  metadata: { pan: 'EPPPG3078Q', financial_year: '2025-26' },
  income_heads: {
    'Income from Other Sources': {
      income_head: 'Income from Other Sources', total_processed: 157.0, total_accepted: 157.0, entries: [
        { sr_no: 1, category: 'Interest from savings bank', accepted_by_taxpayer: 90.0, details: [{ sr_no: 1, information_source: 'BANK LIMITED (AAACS8577K.AB703)', institution_pan: 'AAACS8577K', reported_by_source: '157', accepted_by_taxpayer: '90' }] },
      ],
    },
  },
};

describe('evidence producers', () => {
  it('preserves raw source fields and flags unknowns requiring review', () => {
    const patch = mapAisToDraftPatch(realAis as never);
    const evidence = patch.reconciliation!.evidence!;
    expect(evidence).toHaveLength(2);
    expect(evidence[0].raw).toHaveProperty('information_code', 'SFT-016(SB)');
    expect(evidence[0].raw).toHaveProperty('details');
    expect(evidence[0].requiresReview).toBe(false);
    expect(evidence[1].role).toBe('PARSER_WARNING');
    expect(evidence[1].requiresReview).toBe(true);
    expect(evidence[1].relatedTab).toBe('RECONCILIATION');
  });

  it('26AS → AIS → TIS sequential merge retains all evidence', () => {
    let draft = createEmptyReturnDraft();
    draft = mergeDraft(draft, map26asToDraftPatch({ financialYear: '2025-26', tdsEntries: [{ sectionCode: '194A', employerName: 'Bank', employerTAN: 'TAN001', totalAmount: 1000, totalTDS: 100 }] }));
    expect(draft.reconciliation.evidence).toHaveLength(1);
    draft = mergeDraft(draft, mapAisToDraftPatch(realAis as never));
    expect(draft.reconciliation.evidence).toHaveLength(3);
    draft = mergeDraft(draft, mapTisToDraftPatch(realTis as never));
    expect(draft.reconciliation.evidence.length).toBeGreaterThanOrEqual(4);

    const reconciled = reconcileImportedEvidence(draft);
    const mismatch = reconciled.reconciliation.discrepancies.find((item) => item.category === 'interest from savings bank');
    expect(mismatch).toBeDefined();
    expect(mismatch!.aisAmount).toBe(157);
    expect(mismatch!.tisAcceptedAmount).toBe(90);
    expect(mismatch!.status).toBe('PENDING');
  });
});
