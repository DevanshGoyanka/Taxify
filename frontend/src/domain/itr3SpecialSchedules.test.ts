import { describe, expect, it } from 'vitest';
import type { ClubbedIncomeEntry, ScheduleSIEntry } from './returns/types';
import {
  ITR3_COMPUTED_PATHS, ITR3_SI_INPUT_PATHS, ITR3_SPI_INPUT_PATHS,
  validateITR3SIEntry, validateITR3SPIEntry, updateITR3SIEntry,
} from './itr3SpecialSchedules';

describe('ITR-3 SI/SPI coverage', () => {
  it('registers official editable and computed paths explicitly', () => {
    expect(ITR3_SI_INPUT_PATHS).toContain('ScheduleSI.SplCodeRateTax[].SecCode');
    expect(ITR3_SI_INPUT_PATHS).toContain('ScheduleSI.SplCodeRateTax[].SplRateInc');
    expect(ITR3_SPI_INPUT_PATHS).toContain('ScheduleSPI.SpecifiedPerson[].AmtIncluded');
    expect(ITR3_COMPUTED_PATHS).toContain('ScheduleSI.SplCodeRateTax[].SplRateIncTax');
    expect(ITR3_COMPUTED_PATHS).toContain('ScheduleSI.TotSplRateIncTax');
  });

  it('validates official SI categories and prohibited deductions', () => {
    const entry: ScheduleSIEntry = { id: 'si-1', section: '115BB', description: 'Lottery', grossIncome: 1000, deductions: 1, taxRatePct: null };
    expect(validateITR3SIEntry(entry)).toContain('Deductions are not permitted for Section 115BB.');
    expect(validateITR3SIEntry({ ...entry, deductions: 0 })).toEqual([]);
  });

  it('validates SPI relationship, PAN, source amount, and head', () => {
    const entry: ClubbedIncomeEntry = { id: 'spi-1', specifiedPersonName: '', pan: 'BAD', relationship: '', amountIncluded: -1, headOfIncome: 'OS' };
    expect(validateITR3SPIEntry(entry).length).toBeGreaterThan(2);
  });

  it('protects backend-computed SI fields from draft updates', () => {
    const entry: ScheduleSIEntry = { id: 'si-1', section: '115BB', description: 'Lottery', grossIncome: 1000, deductions: 0, taxRatePct: null };
    const updated = updateITR3SIEntry(entry, { grossIncome: 2000, taxableIncome: 1, taxAmount: 999 });
    expect(updated.grossIncome).toBe(2000);
    expect(updated).not.toHaveProperty('taxableIncome');
    expect(updated).not.toHaveProperty('taxAmount');
  });
});
