import { describe, expect, it } from 'vitest';
import { createEmptyReturnDraft } from './returns/factory';
import { addItr3PartAQDRow, readItr3PartAQD, removeItr3PartAQDRow, updateItr3PartAQD } from './itr3PartAQD';

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

  it('can add and remove rows -- a fresh schedule has no way to reach any data without this', () => {
    const draft = createEmptyReturnDraft('2026-27', 'ITR-3', 'new');
    expect(readItr3PartAQD(draft.itr3BusinessWorkspace).TradingConcern).toBeUndefined();
    const withRow = addItr3PartAQDRow(draft.itr3BusinessWorkspace, 'TradingConcern');
    expect(readItr3PartAQD(withRow).TradingConcern).toHaveLength(1);
    expect(readItr3PartAQD(withRow).TradingConcern?.[0]).toEqual({ ItemName: '', UnitOfMeasure: '', OpeningStock: 0, PurchaseQty: 0, SaleQty: 0, ClgStock: 0, AnyShortExces: 0 });
    const withTwoRows = addItr3PartAQDRow(withRow, 'TradingConcern');
    expect(readItr3PartAQD(withTwoRows).TradingConcern).toHaveLength(2);
    const withOneRemoved = removeItr3PartAQDRow(withTwoRows, 'TradingConcern', 0);
    expect(readItr3PartAQD(withOneRemoved).TradingConcern).toHaveLength(1);
  });

  it('adds rows independently to RawMaterial and FinishrByProd branches', () => {
    const draft = createEmptyReturnDraft('2026-27', 'ITR-3', 'new');
    const withRawMaterial = addItr3PartAQDRow(draft.itr3BusinessWorkspace, 'RawMaterial');
    expect(readItr3PartAQD(withRawMaterial).ManfactrConcern?.RawMaterial).toHaveLength(1);
    expect(readItr3PartAQD(withRawMaterial).ManfactrConcern?.FinishrByProd).toBeUndefined();
    const withBoth = addItr3PartAQDRow(withRawMaterial, 'FinishrByProd');
    expect(readItr3PartAQD(withBoth).ManfactrConcern?.RawMaterial).toHaveLength(1);
    expect(readItr3PartAQD(withBoth).ManfactrConcern?.FinishrByProd).toHaveLength(1);
  });

  it('caps a branch at 20 rows and rejects an out-of-range removal', () => {
    let workspace = createEmptyReturnDraft('2026-27', 'ITR-3', 'new').itr3BusinessWorkspace;
    for (let i = 0; i < 20; i += 1) workspace = addItr3PartAQDRow(workspace, 'TradingConcern');
    expect(readItr3PartAQD(workspace).TradingConcern).toHaveLength(20);
    expect(addItr3PartAQDRow(workspace, 'TradingConcern')).toBe(workspace);
    expect(removeItr3PartAQDRow(workspace, 'TradingConcern', 20)).toBe(workspace);
  });
});
