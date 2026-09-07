import { describe, expect, it } from 'vitest';
import { createEmptyReturnDraft } from './factory';

describe('createEmptyReturnDraft', () => {
  it('defaults the verification declaration to accepted, per the preparer-workflow default', () => {
    // The taxpayer/preparer can still uncheck this in the UI at any time --
    // this only changes the starting state of a brand-new draft, not a
    // reactively-enforced value (a reactive "always true" default would
    // make the checkbox impossible to leave unchecked).
    const draft = createEmptyReturnDraft('2026-27');
    expect(draft.verification.declarationAccepted).toBe(true);
  });

  it('leaves place of verification blank for a brand-new draft (filled reactively from city in the UI)', () => {
    const draft = createEmptyReturnDraft('2026-27');
    expect(draft.verification.place).toBe('');
  });
});
