import type { AMTCreditEntry, AMTDetails, AMTComputedValues } from './returns/types';

/** Canonical official Schedule AMT and AMTC paths exposed by this editor. */
export const AMT_FIELD_PATHS = [
  'ScheduleAMT.AdjustmentSec115JC.DeductClaimSec10AA',
  'ScheduleAMT.AdjustmentSec115JC.DeductClaimSec80IAto80RRBExcept80P',
  'ScheduleAMT.AdjustmentSec115JC.DeductClaimSec35AD',
  'ScheduleAMTC.ScheduleAMTCDtls[].AssYr',
  'ScheduleAMTC.ScheduleAMTCDtls[].AmtCreditBalBroughtFwd',
  'ScheduleAMT.TotalIncItem11',
  'ScheduleAMT.TaxPayableUnderSec115JC',
  'ScheduleAMTC.AmtTaxCreditAvailable',
  'ScheduleAMTC.TotAmtCreditUtilisedCY',
  'ScheduleAMTC.TotBalAMTCreditCF',
] as const;

/** Backend-owned fields that must never be accepted as editable draft data. */
export const AMT_COMPUTED_FIELDS = [
  'adjustedTotalIncome', 'amtTax', 'availableCredit', 'utilizedCredit',
  'remainingCredit', 'carryForwardCredit',
] as const;

const YEAR_PATTERN = /^20(\d{2})-(\d{2})$/;

/** Validates a CBDT assessment-year label and rejects future/current years. */
export function isValidAMTAssessmentYear(value: string, currentAssessmentYear = '2026-27'): boolean {
  if (!YEAR_PATTERN.test(value) || value === currentAssessmentYear) return false;
  const match = value.match(YEAR_PATTERN);
  const current = currentAssessmentYear.match(YEAR_PATTERN);
  if (!match || !current) return false;
  return Number(match[1]) >= 13 && Number(match[1]) < Number(current[1]);
}

/** Sanitizes non-negative monetary input without permitting NaN, infinity, or negatives. */
export function sanitizeAMTMoney(value: number): number {
  return Number.isFinite(value) && value >= 0 ? Math.trunc(value) : 0;
}

/** Creates a stable, editable AMT detail object without computed fields. */
export function createEmptyAMTDetails(): AMTDetails {
  return { deduction10AA: 0, deduction80IAto80RRBExcept80P: 0, deduction35ADNetDepreciation: 0, creditsBroughtForward: [] };
}

/** Applies only user-editable fields to AMT details; computed values are discarded. */
export function updateAMTInputs(current: AMTDetails, patch: Partial<Pick<AMTDetails, 'deduction10AA' | 'deduction80IAto80RRBExcept80P' | 'deduction35ADNetDepreciation' | 'creditsBroughtForward'>>): AMTDetails {
  return {
    deduction10AA: sanitizeAMTMoney(patch.deduction10AA ?? current.deduction10AA),
    deduction80IAto80RRBExcept80P: sanitizeAMTMoney(patch.deduction80IAto80RRBExcept80P ?? current.deduction80IAto80RRBExcept80P),
    deduction35ADNetDepreciation: sanitizeAMTMoney(patch.deduction35ADNetDepreciation ?? current.deduction35ADNetDepreciation),
    creditsBroughtForward: (patch.creditsBroughtForward ?? current.creditsBroughtForward).map((entry) => ({
      id: entry.id, assessmentYear: entry.assessmentYear, creditBroughtForward: sanitizeAMTMoney(entry.creditBroughtForward),
      ...(entry.expiryDate ? { expiryDate: entry.expiryDate } : {}), ...(entry.eligible === undefined ? {} : { eligible: entry.eligible }),
    })),
  };
}

/** Extracts backend computed AMT values while remaining safe for missing responses. */
export function readAMTComputed(result: unknown): AMTComputedValues | null {
  if (!result || typeof result !== 'object') return null;
  const source = result as Record<string, unknown>;
  const candidate = (source.amt ?? source.amtSummary ?? source) as Record<string, unknown>;
  const number = (key: string): number => typeof candidate[key] === 'number' && Number.isFinite(candidate[key]) ? candidate[key] as number : 0;
  return { adjustedTotalIncome: number('adjustedTotalIncome'), amtTax: number('amtTax'), availableCredit: number('availableCredit'), utilizedCredit: number('utilizedCredit'), remainingCredit: number('remainingCredit'), carryForwardCredit: number('carryForwardCredit') };
}

export type { AMTCreditEntry, AMTDetails, AMTComputedValues };
