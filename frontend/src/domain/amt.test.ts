import { describe, expect, it } from 'vitest';
import { AMT_COMPUTED_FIELDS, AMT_FIELD_PATHS, createEmptyAMTDetails, isValidAMTAssessmentYear, updateAMTInputs } from './amt';

describe('Schedule AMT/AMTC editor contract', () => {
  it('registers official AMT and AMTC paths', () => {
    expect(AMT_FIELD_PATHS).toContain('ScheduleAMTC.ScheduleAMTCDtls[].AssYr');
    expect(AMT_FIELD_PATHS).toContain('ScheduleAMT.TaxPayableUnderSec115JC');
  });
  it('validates prior assessment years and rejects current/future values', () => {
    expect(isValidAMTAssessmentYear('2025-26')).toBe(true);
    expect(isValidAMTAssessmentYear('2026-27')).toBe(false);
    expect(isValidAMTAssessmentYear('2027-28')).toBe(false);
    expect(isValidAMTAssessmentYear('bad')).toBe(false);
  });
  it('updates only exact editable draft fields', () => {
    const initial = createEmptyAMTDetails();
    const result = updateAMTInputs(initial, { deduction10AA: 100, creditsBroughtForward: [{ id: 'x', assessmentYear: '2025-26', creditBroughtForward: 50 }] });
    expect(result.deduction10AA).toBe(100);
    expect(result.creditsBroughtForward[0]?.creditBroughtForward).toBe(50);
    expect(result).not.toHaveProperty('adjustedTotalIncome');
  });
  it('keeps all computed field names outside editable input contract', () => {
    expect(AMT_COMPUTED_FIELDS).toContain('amtTax');
    expect(AMT_COMPUTED_FIELDS).toContain('carryForwardCredit');
  });
});
