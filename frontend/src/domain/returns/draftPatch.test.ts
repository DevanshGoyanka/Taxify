import { describe, expect, it } from 'vitest';
import { createEmptyReturnDraft } from './factory';
import { mergeDraft, type ReturnDraftPatch } from './draftPatch';

describe('mergeDraft', () => {
  it('merges identified arrays by id and appends new ids', () => {
    const base = createEmptyReturnDraft();
    base.bankAccounts = [{ id: 'a', bankName: 'Old', accountNumber: '1', ifscCode: 'AAAA0123456', accountType: 'SB', useForRefund: false }];
    const merged = mergeDraft(base, { bankAccounts: [{ id: 'a', bankName: 'New' }, { id: 'b', bankName: 'Other', accountNumber: '2', ifscCode: 'BBBB0123456', accountType: 'CA', useForRefund: true }] });
    expect(merged.bankAccounts).toEqual([
      { id: 'a', bankName: 'New', accountNumber: '1', ifscCode: 'AAAA0123456', accountType: 'SB', useForRefund: false },
      { id: 'b', bankName: 'Other', accountNumber: '2', ifscCode: 'BBBB0123456', accountType: 'CA', useForRefund: true },
    ]);
  });

  it('preserves values for empty scalars but replaces with zero and false', () => {
    const base = createEmptyReturnDraft();
    base.personal.name = 'Existing';
    base.verification.declarationAccepted = true;
    base.housePropertyPassThroughIncome = 100;
    const merged = mergeDraft(base, { personal: { name: '' }, verification: { declarationAccepted: false }, housePropertyPassThroughIncome: 0 });
    expect(merged.personal.name).toBe('Existing');
    expect(merged.verification.declarationAccepted).toBe(false);
    expect(merged.housePropertyPassThroughIncome).toBe(0);
  });

  it('replaces non-identified arrays and preserves them for an empty patch array', () => {
    const base = createEmptyReturnDraft();
    base.provenance = [{ source: 'MANUAL', importedAt: null, reference: 'old' }];
    expect(mergeDraft(base, { provenance: [] }).provenance).toEqual(base.provenance);
    expect(mergeDraft(base, { provenance: [{ source: 'AIS', importedAt: null, reference: 'new' }] }).provenance[0].source).toBe('AIS');
  });

  it('does not mutate base or patch and is deterministic', () => {
    const base = createEmptyReturnDraft('2026-27');
    const patch: ReturnDraftPatch = { personal: { pan: 'ABCDE1234F', name: 'A' } };
    const beforeBase = structuredClone(base);
    const beforePatch = structuredClone(patch);
    const first = mergeDraft(base, patch);
    const second = mergeDraft(base, patch);
    expect(first).toEqual(second);
    expect(base).toEqual(beforeBase);
    expect(patch).toEqual(beforePatch);
    expect(first).not.toBe(base);
  });
});
