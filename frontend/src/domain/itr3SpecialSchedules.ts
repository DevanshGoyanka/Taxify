import type { ClubbedIncomeEntry, ScheduleSIEntry, ScheduleSISection } from './returns/types';

/** Official ITR-3 Schedule SI category codes accepted by the canonical backend. */
export const ITR3_SI_SECTIONS: readonly ScheduleSISection[] = [
  '115BB', '115BBE', '115BBF', '115BBG', '115BBJ', '115BBA', '111',
] as const;

/** Official ITR-3 Schedule SPI head-of-income codes. */
export const ITR3_SPI_HEADS = ['SAL', 'HP', 'CG', 'OS'] as const;
export type ITR3SPIHead = (typeof ITR3_SPI_HEADS)[number];

/** A display-only calculation projection; it is never accepted by draft updates. */
export interface ITR3ComputedSpecialRateRow {
  taxableIncome: number;
  taxAmount: number | null;
}

/** Official backend field paths exposed as editable Schedule SI inputs. */
export const ITR3_SI_INPUT_PATHS = [
  'ScheduleSI.SplCodeRateTax[].SecCode',
  'ScheduleSI.SplCodeRateTax[].SplRateInc',
] as const;

/** Official backend field paths exposed as editable Schedule SPI inputs. */
export const ITR3_SPI_INPUT_PATHS = [
  'ScheduleSPI.SpecifiedPerson[].SpecifiedPersonName',
  'ScheduleSPI.SpecifiedPerson[].PANofSpecPerson',
  'ScheduleSPI.SpecifiedPerson[].AaadhaarOfSpecPerson',
  'ScheduleSPI.SpecifiedPerson[].ReltnShip',
  'ScheduleSPI.SpecifiedPerson[].AmtIncluded',
  'ScheduleSPI.SpecifiedPerson[].HeadIncIncluded',
] as const;

/** Official computed/read-only paths; no editor control writes these fields. */
export const ITR3_COMPUTED_PATHS = [
  'ScheduleSI.EditAutopoulatedDetail',
  'ScheduleSI.SplCodeRateTax[].SplRateIncTax',
  'ScheduleSI.SplCodeRateTax[].SplRatePercent',
  'ScheduleSI.TotSplRateInc',
  'ScheduleSI.TotSplRateIncTax',
] as const;

export type ITR3SpecialSchedulePath =
  | (typeof ITR3_SI_INPUT_PATHS)[number]
  | (typeof ITR3_SPI_INPUT_PATHS)[number]
  | (typeof ITR3_COMPUTED_PATHS)[number];

/** Validates one editable SI row without validating backend-computed values. */
export function validateITR3SIEntry(entry: ScheduleSIEntry): string[] {
  const errors: string[] = [];
  if (!ITR3_SI_SECTIONS.includes(entry.section)) errors.push('Select an official special-rate section.');
  if (!entry.description.trim()) errors.push('Description is required.');
  if (!Number.isFinite(Number(entry.grossIncome)) || Number(entry.grossIncome) < 0) errors.push('Gross income cannot be negative.');
  if (!Number.isFinite(Number(entry.deductions)) || Number(entry.deductions) < 0) errors.push('Deductions cannot be negative.');
  if ((entry.section === '115BB' || entry.section === '115BBE' || entry.section === '115BBJ') && Number(entry.deductions) > 0) {
    errors.push(`Deductions are not permitted for Section ${entry.section}.`);
  }
  return errors;
}

/** Validates one editable SPI row against backend-supported fields. */
export function validateITR3SPIEntry(entry: ClubbedIncomeEntry): string[] {
  const errors: string[] = [];
  if (!entry.specifiedPersonName.trim()) errors.push('Specified person name is required.');
  if (entry.pan && !/^[A-Z]{5}[0-9]{4}[A-Z]$/.test(entry.pan.toUpperCase())) errors.push('PAN must be valid.');
  if (!entry.relationship.trim()) errors.push('Relationship is required.');
  if (!Number.isFinite(Number(entry.amountIncluded)) || Number(entry.amountIncluded) < 0) errors.push('Income included cannot be negative.');
  if (!ITR3_SPI_HEADS.includes(entry.headOfIncome as ITR3SPIHead)) errors.push('Select an official income head.');
  return errors;
}

/** Applies only editable SI fields; computed fields are intentionally discarded. */
export function updateITR3SIEntry(entry: ScheduleSIEntry, patch: Partial<ScheduleSIEntry> & Partial<ITR3ComputedSpecialRateRow>): ScheduleSIEntry {
  const { taxableIncome: _taxableIncome, taxAmount: _taxAmount, ...editable } = patch;
  return { ...entry, ...editable };
}

/** Applies only editable SPI fields; unknown/computed values cannot enter the draft. */
export function updateITR3SPIEntry(entry: ClubbedIncomeEntry, patch: Partial<ClubbedIncomeEntry>): ClubbedIncomeEntry {
  return {
    id: entry.id,
    specifiedPersonName: patch.specifiedPersonName ?? entry.specifiedPersonName,
    pan: patch.pan ?? entry.pan,
    relationship: patch.relationship ?? entry.relationship,
    amountIncluded: patch.amountIncluded ?? entry.amountIncluded,
    headOfIncome: patch.headOfIncome ?? entry.headOfIncome,
  };
}
