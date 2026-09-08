import { describe, expect, it } from 'vitest';
import {
  applicableFilingSection,
  filingSectionDueDateError,
  getDueDate,
  isDueDatePassed,
} from './dueDates';
import { createEmptyReturnDraft } from './factory';
import { validateCbdtFrontendFields } from './filingPreflight';

const ON_DUE_DATE = '2026-07-31';
const DAY_AFTER = '2026-08-01';

describe('filing due dates', () => {
  it('uses 31 July for ITR-1/ITR-2 and 31 August for ITR-3/ITR-4', () => {
    expect(getDueDate('ITR-1', '2026-27')).toBe('2026-07-31');
    expect(getDueDate('ITR-2', '2026-27')).toBe('2026-07-31');
    expect(getDueDate('ITR-3', '2026-27')).toBe('2026-08-31');
    expect(getDueDate('ITR-4', '2026-27')).toBe('2026-08-31');
  });

  it('treats the due date itself as on time', () => {
    expect(isDueDatePassed('ITR-1', '2026-27', ON_DUE_DATE)).toBe(false);
    expect(isDueDatePassed('ITR-1', '2026-27', DAY_AFTER)).toBe(true);
    // ITR-4 still has a month to run on the same date.
    expect(isDueDatePassed('ITR-4', '2026-27', DAY_AFTER)).toBe(false);
  });

  it('moves an unfiled return to belated and a filed one to revised', () => {
    expect(applicableFilingSection('ITR-1', '2026-27', { onDate: ON_DUE_DATE })).toBe('139(1)');
    expect(applicableFilingSection('ITR-1', '2026-27', { onDate: DAY_AFTER })).toBe('139(4)');
    expect(
      applicableFilingSection('ITR-1', '2026-27', { originalReturnFiled: true, onDate: ON_DUE_DATE }),
    ).toBe('139(5)');
  });

  it('only invalidates 139(1), and names both remedies when it does', () => {
    expect(filingSectionDueDateError('139(4)', 'ITR-1', '2026-27', DAY_AFTER)).toBeNull();
    expect(filingSectionDueDateError('139(5)', 'ITR-1', '2026-27', DAY_AFTER)).toBeNull();
    expect(filingSectionDueDateError('148', 'ITR-1', '2026-27', DAY_AFTER)).toBeNull();
    expect(filingSectionDueDateError('139(1)', 'ITR-1', '2026-27', ON_DUE_DATE)).toBeNull();

    const message = filingSectionDueDateError('139(1)', 'ITR-1', '2026-27', DAY_AFTER);
    expect(message).toContain('2026-07-31');
    expect(message).toContain('139(4)');
    expect(message).toContain('139(5)');
  });
});

describe('pre-flight enforcement of the due date', () => {
  const draftFiledOn = (filingSection: '139(1)' | '139(4)', date: string) => {
    const draft = createEmptyReturnDraft('2026-27', 'ITR-1', 'new');
    draft.personal.fatherName = 'Mohan Sharma';
    draft.personal.surnameOrOrgName = 'Sharma';
    draft.personal.pan = 'ABCDE1234F';
    draft.personal.employerCategory = 'OTH';
    draft.personal.stateCode = '09';
    draft.personal.pinCode = '110001';
    draft.bankAccounts = [{
      id: 'bank-1',
      bankName: 'State Bank of India',
      accountNumber: '1234567890',
      ifscCode: 'SBIN0001234',
      accountType: 'SB',
      useForRefund: true,
    }];
    draft.verification.place = 'Delhi';
    draft.verification.date = date;
    draft.verification.declarationAccepted = true;
    draft.filing.filingSection = filingSection;
    return draft;
  };

  it('blocks a 139(1) return declared after the due date', () => {
    const errors = validateCbdtFrontendFields(draftFiledOn('139(1)', DAY_AFTER));
    expect(errors.some((error) => error.includes('139(4)') && error.includes('139(5)'))).toBe(true);
  });

  it('accepts the same return once it is marked belated', () => {
    expect(validateCbdtFrontendFields(draftFiledOn('139(4)', DAY_AFTER))).toEqual([]);
  });

  it('accepts 139(1) on the due date itself', () => {
    expect(validateCbdtFrontendFields(draftFiledOn('139(1)', ON_DUE_DATE))).toEqual([]);
  });
});
