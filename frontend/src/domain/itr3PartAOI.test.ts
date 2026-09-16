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
    const updated = updateItr3PartAOI(workspace, 'amountOfExpDisallwUs14A', '1250.8');
    expect(readItr3PartAOI(updated).amountOfExpDisallwUs14A).toBe(1250);
    expect(updated.auxiliary).toEqual({});
  });
  it('does not accept unknown or computed fields', () => {
    const draft = createEmptyReturnDraft('2026-27', 'ITR-3', 'new');
    expect(updateItr3PartAOI(draft.itr3BusinessWorkspace, 'TotAmtDisallUs36', 99)).toBe(draft.itr3BusinessWorkspace);
    expect(EMPTY_ITR3_PART_A_OI.otherAdditions).toBe(0);
  });
});
