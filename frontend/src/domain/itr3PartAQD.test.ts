import { describe, expect, it } from 'vitest';
import { createEmptyReturnDraft } from './returns/factory';
import { readItr3PartAQD, updateItr3PartAQD } from './itr3PartAQD';

describe('PARTA_QD editor model', () => {
  it('updates scalar source facts immutably and normalizes invalid quantities', () => {
    const draft = createEmptyReturnDraft('2026-27', 'ITR-3', 'new');
    const workspace = { ...draft.itr3BusinessWorkspace, auxiliary: { ...draft.itr3BusinessWorkspace.auxiliary, PARTA_QD: { TradingConcern: [{ ItemName: 'Rice', UnitOfMeasure: '101', OpeningStock: 1, PurchaseQty: 2, SaleQty: 3, ClgStock: 0, AnyShortExces: 0 }] } } };
    const updated = updateItr3PartAQD(workspace, 'TradingConcern', 0, 'OpeningStock', '-5');
    expect(readItr3PartAQD(updated).TradingConcern?.[0].OpeningStock).toBe(0);
    expect(updated).not.toBe(workspace);
    expect(workspace.auxiliary.PARTA_QD).not.toBe(updated.auxiliary.PARTA_QD);
  });

  it('protects unknown, structural, and out-of-range updates', () => {
    const draft = createEmptyReturnDraft('2026-27', 'ITR-3', 'new');
    expect(updateItr3PartAQD(draft.itr3BusinessWorkspace, 'TradingConcern', 0, 'ClgStock', 4)).toBe(draft.itr3BusinessWorkspace);
    expect(updateItr3PartAQD(draft.itr3BusinessWorkspace, 'TradingConcern', -1, 'ClgStock', 4)).toBe(draft.itr3BusinessWorkspace);
  });
});
