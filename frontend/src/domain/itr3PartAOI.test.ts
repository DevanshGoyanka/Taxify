import { describe, expect, it } from 'vitest';
import { EMPTY_ITR3_PART_A_OI, ITR3_PART_A_OI_FIELDS, readItr3PartAOI, updateItr3PartAOI } from './itr3PartAOI';
import { createEmptyReturnDraft } from './returns/factory';

describe('ITR-3 Part A-OI', () => {
  it('covers official adjustment paths without exposing computed totals', () => {
    expect(ITR3_PART_A_OI_FIELDS.some((field) => field.path.includes('14A'))).toBe(true);
    expect(ITR3_PART_A_OI_FIELDS.some((field) => field.path.includes('AmtDisall43B'))).toBe(true);
    expect(ITR3_PART_A_OI_FIELDS.some((field) => field.path.includes('InterestDisAllowUs23SMEAct'))).toBe(true);
    expect(ITR3_PART_A_OI_FIELDS.some((field) => field.label.includes('Schedule BP'))).toBe(false);
  });
  it('updates the canonical workspace exactly and normalizes invalid amounts', () => {
    const draft = createEmptyReturnDraft('2026-27', 'ITR-3', 'new');
    const workspace = updateItr3PartAOI(draft.itr3BusinessWorkspace, 'EmpBonusCommSum', '-9');
    expect(readItr3PartAOI(workspace).amountDisallUs36.EmpBonusCommSum).toBe(0);
    const updated = updateItr3PartAOI(workspace, 'AmountOfExpDisAllwUs14A', '1250.8');
    expect(readItr3PartAOI(updated).amountOfExpDisallwUs14A).toBe(1250);
    expect(updated.auxiliary).toEqual({});
  });
  it('does not accept unknown or computed fields', () => {
    const draft = createEmptyReturnDraft('2026-27', 'ITR-3', 'new');
    expect(updateItr3PartAOI(draft.itr3BusinessWorkspace, 'TotAmtDisallUs36', 99)).toBe(draft.itr3BusinessWorkspace);
    expect(EMPTY_ITR3_PART_A_OI.scheduleTPSAFlg).toBe('N');
  });
  it('writes the accounting-method and stock-valuation fields to their real official paths, not a corrupted nested key', () => {
    const draft = createEmptyReturnDraft('2026-27', 'ITR-3', 'new');
    const withMethod = updateItr3PartAOI(draft.itr3BusinessWorkspace, 'MethodOfAcct', 'CASH');
    expect(readItr3PartAOI(withMethod).methodOfAcct).toBe('CASH');
    const withStockFlag = updateItr3PartAOI(withMethod, 'ValRawMaterial', '2');
    expect(readItr3PartAOI(withStockFlag).methodOfValClgStk.ValRawMaterial).toBe('2');
    const withEffect = updateItr3PartAOI(withStockFlag, 'EffectOnPL', '1500');
    expect(readItr3PartAOI(withEffect).methodOfValClgStk.EffectOnPL).toBe(1500);
    // Section 5 (NoCredToPLAmt) writes only its own real sub-fields, never a
    // bogus self-named key -- the pre-fix duplicate field entry corrupted
    // this exact object with a `NoCredToPLAmt.NoCredToPLAmt` key.
    const withNoCredit = updateItr3PartAOI(withEffect, 'Section28Items', '250');
    expect(readItr3PartAOI(withNoCredit).noCredToPLAmt).toEqual({ Section28Items: 250 });
  });
});
