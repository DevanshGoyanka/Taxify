import { describe, expect, it } from 'vitest';
import { createEmptyReturnDraft } from './factory';
import {
  replaceDraft,
  updateCapitalGainsSchedule,
  updateDraft,
  updateEmployers,
  updateSection80C,
  type ReturnEditorModelV2,
} from './editorModelV2';
import type { CapitalGainsSchedule, Employer, Investment80C } from './types';

function employer(): Employer {
  return {
    id: 'employer-1', customEmployerName: '', employerName: 'Acme', employerTAN: '', natureOfEmployment: 'OTH',
    employerAddress: '', employerCity: '', employerStateCode: '', employerPinCode: '', employerZipCode: '',
    salaryNatureRows: [], perquisiteNatureRows: [], section10ExemptionRows: [],
    basic: 100, da: 0, commission: 0, hra: 0, bonus: 0, allowances: 0, lta: 0,
    otherAllowance: 0, arrearSalary: 0, perquisites: 0, profitsInLieu: 0, rentPaid: 0,
    city: '', isMetroCity: false, isGovernmentEmployee: false, isDisabledEmployee: false,
    commutedPension: 0, gratuity: 0, leaveEncashment: 0, averageMonthlySalary: 0, yearsOfService: 0,
    unavailedLeaveDays: 0, actualLtaFare: 0, isDomesticTravel: true, journeysInBlock: 0, ltaExempt: 0,
    numberOfChildren: 0, gratuityAlsoReceived: false, transportAllowance: 0, childrenEducationAllowance: 0,
    hostelExpenditureAllowance: 0, uniformAllowance: 0, entertainmentAllowance: 0, professionalTax: 0,
    vrsCompensation: 0, retrenchmentCompensation: 0, otherExempt: 0, tdsDeducted: 0, employerNPS: 0,
  };
}

function investment(): Investment80C {
  return { id: '80c-1', investmentType: 'PPF', identificationNo: '', accountOrPolicyNo: 'A', amount: 100, dateOfInvestment: '2026-01-01', institutionName: 'Bank', institutionPAN: 'ABCDE1234F' };
}

describe('ReturnEditorModelV2', () => {
  it('performs detached immutable updates without mutating model or inputs', () => {
    const original: ReturnEditorModelV2 = { draft: createEmptyReturnDraft('2026-27') };
    const entries = [employer()];
    const updated = updateEmployers(original, entries);
    entries[0].employerName = 'Mutated input';
    updated.draft.employers[0].employerName = 'Mutated result';

    expect(original.draft.employers).toEqual([]);
    expect(updated).not.toBe(original);
    expect(updated.draft).not.toBe(original.draft);
    expect(entries[0].employerName).toBe('Mutated input');
  });

  it('supports idempotent draft transformations', () => {
    const model = replaceDraft(createEmptyReturnDraft('2026-27'));
    const setOldRegime = (draft: ReturnEditorModelV2['draft']): ReturnEditorModelV2['draft'] => ({ ...draft, regime: 'old' });
    const once = updateDraft(model, setOldRegime);
    const twice = updateDraft(once, setOldRegime);

    expect(twice).toEqual(once);
    expect(twice).not.toBe(once);
    expect(twice.draft).not.toBe(once.draft);
  });

  it('never produces an extras or compatibility envelope', () => {
    const draft = createEmptyReturnDraft('2026-27');
    draft.compatibility = { source: 'legacy-flat-v1', unknownFields: { future: true } };
    const model = replaceDraft(draft);
    const updated = updateSection80C(model, [investment()]);

    expect(Object.keys(updated)).toEqual(['draft']);
    expect(updated).not.toHaveProperty('extras');
    expect(updated.draft).not.toHaveProperty('compatibility');
    expect(updated.draft.deductions.section80C).toHaveLength(1);
  });

  it('seeds the capital gains schedule as the typed EMPTY_CAPITAL_GAINS_SCHEDULE', () => {
    const draft = createEmptyReturnDraft('2026-27');
    const schedule = draft.capitalGainsSchedule as CapitalGainsSchedule;
    expect(schedule.simplified112A).toEqual({ totalSaleConsideration: 0, totalCostAcquisition: 0 });
    expect(schedule.schedule112A).toEqual([]);
    expect(schedule.schedule115AD).toEqual([]);
    expect(schedule.vda).toEqual([]);
    expect(schedule.stImmovable).toEqual([]);
    expect(schedule.ltImmovable).toEqual([]);
    expect(schedule.stUnutilizedFlag).toBe('N');
    expect(schedule.ltUnutilizedFlag).toBe('N');
    expect(schedule.aggregates).toEqual({
      stPassThrough: 0, stPassThrough20: 0, stPassThrough30: 0, stPassThroughApplicable: 0,
      ltPassThrough: 0, ltPassThrough112A: 0, ltPassThrough125: 0,
    });
  });

  it('replaces the capital gains schedule immutably via updateCapitalGainsSchedule', () => {
    const model = replaceDraft(createEmptyReturnDraft('2026-27'));
    const newSchedule: CapitalGainsSchedule = {
      ...model.draft.capitalGainsSchedule,
      simplified112A: { totalSaleConsideration: 250000, totalCostAcquisition: 180000 },
      schedule112A: [{
        id: 'scrip-1', shareOnOrBefore: 'AE', isin: 'INE123456789', name: 'Reliance',
        quantity: 100, salePricePerUnit: 2500, totalSaleValue: 250000,
        costWithoutIndexation: 180000, acquisitionCost: 175000, fmvPerUnit: 2400,
        totalFmv: 240000, transferExpenses: 5000,
      }],
    };
    const updated = updateCapitalGainsSchedule(model, newSchedule);

    // Immutable: original unchanged
    expect(model.draft.capitalGainsSchedule.simplified112A.totalSaleConsideration).toBe(0);
    expect(model.draft.capitalGainsSchedule.schedule112A).toEqual([]);

    // Updated: new values
    expect(updated).not.toBe(model);
    expect(updated.draft).not.toBe(model.draft);
    expect(updated.draft.capitalGainsSchedule).not.toBe(model.draft.capitalGainsSchedule);
    expect(updated.draft.capitalGainsSchedule.simplified112A.totalSaleConsideration).toBe(250000);
    expect(updated.draft.capitalGainsSchedule.schedule112A).toHaveLength(1);
    expect(updated.draft.capitalGainsSchedule.schedule112A[0].isin).toBe('INE123456789');

    // Detached: mutating the input after the call does not affect the model
    newSchedule.schedule112A[0].isin = 'MUTATED';
    expect(updated.draft.capitalGainsSchedule.schedule112A[0].isin).toBe('INE123456789');
  });
});
