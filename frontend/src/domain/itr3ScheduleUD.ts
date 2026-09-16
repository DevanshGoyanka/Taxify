import type { CanonicalJsonValue } from './returns/types';

/** A taxpayer-supplied brought-forward unabsorbed depreciation / allowance row. */
export interface ScheduleUDRow {
  /** Assessment year from which the balance was brought forward. */
  assessmentYear: string;
  /** Unabsorbed depreciation brought forward. */
  depreciationBroughtForward: number;
  /** Section 115BAC adjustment to the brought-forward depreciation. */
  adjustedTaxUnder115BAC: number;
  /** Current-year depreciation set off against current-year income. */
  depreciationSetOffCurrentYear: number;
  /** Unabsorbed allowance brought forward. */
  allowanceBroughtForward: number;
  /** Current-year allowance set off against current-year income. */
  allowanceSetOffCurrentYear: number;
  /** Backend-computed depreciation balance carried forward. */
  depreciationBalanceCarriedForward: number;
  /** Backend-computed allowance balance carried forward. */
  allowanceBalanceCarriedForward: number;
}

/** Canonical typed Schedule UD state for AY 2026-27. */
export interface ScheduleUD {
  currentAssessmentYear: '2026-27';
  /** Current-year depreciation balance supplied by the backend calculation. */
  currentDepreciationBalance: number;
  /** Current-year allowance balance supplied by the backend calculation. */
  currentAllowanceBalance: number;
  rows: ScheduleUDRow[];
  totalBroughtForwardDepreciation: number;
  total115BACAdjustment: number;
  totalCurrentYearDepreciationSetOff: number;
  totalDepreciationBalanceCarriedForward: number;
  totalBroughtForwardAllowance: number;
  totalCurrentYearAllowanceSetOff: number;
  totalBalanceCarriedForward: number;
}

/** Empty typed Schedule UD state. */
export const EMPTY_SCHEDULE_UD: ScheduleUD = {
  currentAssessmentYear: '2026-27', currentDepreciationBalance: 0, currentAllowanceBalance: 0, rows: [],
  totalBroughtForwardDepreciation: 0, total115BACAdjustment: 0, totalCurrentYearDepreciationSetOff: 0,
  totalDepreciationBalanceCarriedForward: 0, totalBroughtForwardAllowance: 0, totalCurrentYearAllowanceSetOff: 0,
  totalBalanceCarriedForward: 0,
};

/** Official Schedule UD path and ownership disposition. */
export type ScheduleUDDisposition = 'editable-source' | 'backend-computed' | 'backend-only';
export interface ScheduleUDField { path: string; disposition: ScheduleUDDisposition; required: boolean; array: boolean; }

/** Complete official AY 2026-27 Schedule UD path catalog. */
export const SCHEDULE_UD_FIELDS: readonly ScheduleUDField[] = [
  { path: 'ITR3ScheduleUD.CurAllowBalCFNY', disposition: 'editable-source', required: true, array: false },
  { path: 'ITR3ScheduleUD.CurBalCFNY', disposition: 'editable-source', required: true, array: false },
  { path: 'ITR3ScheduleUD.CurrAssYr', disposition: 'backend-only', required: true, array: false },
  { path: 'ITR3ScheduleUD.ScheduleUD', disposition: 'backend-only', required: false, array: true },
  { path: 'ITR3ScheduleUD.ScheduleUD[].AdjustAccTax115BACAmt', disposition: 'editable-source', required: false, array: false },
  { path: 'ITR3ScheduleUD.ScheduleUD[].AllowBalCFNY', disposition: 'backend-computed', required: true, array: false },
  { path: 'ITR3ScheduleUD.ScheduleUD[].AmtAllowSOCY', disposition: 'editable-source', required: true, array: false },
  { path: 'ITR3ScheduleUD.ScheduleUD[].AmtBFUAllow', disposition: 'editable-source', required: true, array: false },
  { path: 'ITR3ScheduleUD.ScheduleUD[].AmtBFUD', disposition: 'editable-source', required: true, array: false },
  { path: 'ITR3ScheduleUD.ScheduleUD[].AmtDeprSOCY', disposition: 'editable-source', required: true, array: false },
  { path: 'ITR3ScheduleUD.ScheduleUD[].AssYr', disposition: 'editable-source', required: true, array: false },
  { path: 'ITR3ScheduleUD.ScheduleUD[].BalCFNY', disposition: 'backend-computed', required: true, array: false },
  { path: 'ITR3ScheduleUD.TotAdjustAccTax115BACAmt', disposition: 'backend-computed', required: false, array: false },
  { path: 'ITR3ScheduleUD.TotBFUAllowAmt', disposition: 'backend-computed', required: true, array: false },
  { path: 'ITR3ScheduleUD.TotBFUDepritAmt', disposition: 'backend-computed', required: true, array: false },
  { path: 'ITR3ScheduleUD.TotCurYrAllowSetoffInc', disposition: 'backend-computed', required: true, array: false },
  { path: 'ITR3ScheduleUD.TotCurYrdepritSetoffInc', disposition: 'backend-computed', required: true, array: false },
  { path: 'ITR3ScheduleUD.TotDepritBalCFNY', disposition: 'backend-computed', required: true, array: false },
  { path: 'ITR3ScheduleUD.TotalBalCFNY', disposition: 'backend-computed', required: true, array: false },
];

/** Read a Schedule UD field without exposing mutable nested references. */
export function readScheduleUDValue(state: ScheduleUD, path: string): CanonicalJsonValue | undefined {
  const parts = path.replace(/^ITR3ScheduleUD\./, '').split('.');
  if (parts.length === 1) return (state as unknown as Record<string, CanonicalJsonValue>)[parts[0]];
  return undefined;
}

/** Recalculate backend-owned Schedule UD balances while preserving source inputs. */
export function recomputeScheduleUD(input: ScheduleUD): ScheduleUD {
  const rows = input.rows.map((row) => ({ ...row,
    depreciationBalanceCarriedForward: Math.max(0, row.depreciationBroughtForward + row.adjustedTaxUnder115BAC - row.depreciationSetOffCurrentYear),
    allowanceBalanceCarriedForward: Math.max(0, row.allowanceBroughtForward - row.allowanceSetOffCurrentYear),
  }));
  return { ...input, currentAssessmentYear: '2026-27', rows,
    totalBroughtForwardDepreciation: rows.reduce((s, r) => s + r.depreciationBroughtForward, 0),
    total115BACAdjustment: rows.reduce((s, r) => s + r.adjustedTaxUnder115BAC, 0),
    totalCurrentYearDepreciationSetOff: rows.reduce((s, r) => s + r.depreciationSetOffCurrentYear, 0),
    totalDepreciationBalanceCarriedForward: rows.reduce((s, r) => s + r.depreciationBalanceCarriedForward, 0) + input.currentDepreciationBalance,
    totalBroughtForwardAllowance: rows.reduce((s, r) => s + r.allowanceBroughtForward, 0),
    totalCurrentYearAllowanceSetOff: rows.reduce((s, r) => s + r.allowanceSetOffCurrentYear, 0),
    totalBalanceCarriedForward: rows.reduce((s, r) => s + r.allowanceBalanceCarriedForward, 0) + input.currentAllowanceBalance,
  };
}

/** Apply an editable row update immutably; computed paths are ignored. */
export function updateScheduleUDRow(state: ScheduleUD, index: number, field: keyof ScheduleUDRow, value: string | number): ScheduleUD {
  const editable = new Set<keyof ScheduleUDRow>(['assessmentYear', 'depreciationBroughtForward', 'adjustedTaxUnder115BAC', 'depreciationSetOffCurrentYear', 'allowanceBroughtForward', 'allowanceSetOffCurrentYear']);
  if (!Number.isInteger(index) || index < 0 || index >= state.rows.length || !editable.has(field)) return state;
  const rows = state.rows.map((row, i) => i === index ? { ...row, [field]: field === 'assessmentYear' ? String(value) : Math.max(0, Number(value) || 0) } : row);
  return recomputeScheduleUD({ ...state, rows });
}

/** Convert the typed model to the canonical auxiliary object used by ReturnDraft. */
export function scheduleUDToCanonical(state: ScheduleUD): Record<string, CanonicalJsonValue> {
  return { CurrAssYr: state.currentAssessmentYear, CurBalCFNY: state.currentDepreciationBalance, CurAllowBalCFNY: state.currentAllowanceBalance,
    ScheduleUD: state.rows.map((row) => ({ AssYr: row.assessmentYear, AmtBFUD: row.depreciationBroughtForward, AdjustAccTax115BACAmt: row.adjustedTaxUnder115BAC, AmtDeprSOCY: row.depreciationSetOffCurrentYear, BalCFNY: row.depreciationBalanceCarriedForward, AmtBFUAllow: row.allowanceBroughtForward, AmtAllowSOCY: row.allowanceSetOffCurrentYear, AllowBalCFNY: row.allowanceBalanceCarriedForward })),
    TotBFUDepritAmt: state.totalBroughtForwardDepreciation, TotAdjustAccTax115BACAmt: state.total115BACAdjustment, TotCurYrdepritSetoffInc: state.totalCurrentYearDepreciationSetOff, TotDepritBalCFNY: state.totalDepreciationBalanceCarriedForward, TotBFUAllowAmt: state.totalBroughtForwardAllowance, TotCurYrAllowSetoffInc: state.totalCurrentYearAllowanceSetOff, TotalBalCFNY: state.totalBalanceCarriedForward };
}
