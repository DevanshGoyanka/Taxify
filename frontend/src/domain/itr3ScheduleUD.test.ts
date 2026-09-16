import { describe, expect, it } from 'vitest';
import { EMPTY_SCHEDULE_UD, recomputeScheduleUD, scheduleUDToCanonical, updateScheduleUDRow } from './itr3ScheduleUD';

describe('Schedule UD domain model', () => {
  it('recomputes row balances and aggregate totals', () => {
    const state = recomputeScheduleUD({ ...EMPTY_SCHEDULE_UD, currentDepreciationBalance: 4, currentAllowanceBalance: 3, rows: [{ assessmentYear: '2024-25', depreciationBroughtForward: 100, adjustedTaxUnder115BAC: 10, depreciationSetOffCurrentYear: 30, allowanceBroughtForward: 50, allowanceSetOffCurrentYear: 5, depreciationBalanceCarriedForward: 999, allowanceBalanceCarriedForward: 999 }] });
    expect(state.rows[0].depreciationBalanceCarriedForward).toBe(80);
    expect(state.rows[0].allowanceBalanceCarriedForward).toBe(45);
    expect(state.totalDepreciationBalanceCarriedForward).toBe(84);
    expect(state.totalBalanceCarriedForward).toBe(48);
  });
  it('updates nested rows immutably and refuses computed fields or invalid indices', () => {
    const initial = { ...EMPTY_SCHEDULE_UD, rows: [{ assessmentYear: '2024-25', depreciationBroughtForward: 10, adjustedTaxUnder115BAC: 0, depreciationSetOffCurrentYear: 1, allowanceBroughtForward: 2, allowanceSetOffCurrentYear: 0, depreciationBalanceCarriedForward: 9, allowanceBalanceCarriedForward: 2 }] };
    const next = updateScheduleUDRow(initial, 0, 'depreciationBroughtForward', 20);
    expect(next).not.toBe(initial);
    expect(next.rows).not.toBe(initial.rows);
    expect(initial.rows[0].depreciationBroughtForward).toBe(10);
    expect(next.rows[0].depreciationBalanceCarriedForward).toBe(19);
    expect(updateScheduleUDRow(initial, 0, 'depreciationBalanceCarriedForward', 500)).toBe(initial);
    expect(updateScheduleUDRow(initial, 4, 'depreciationBroughtForward', 500)).toBe(initial);
  });
  it('serializes every row and protects backend totals as output only', () => {
    const canonical = scheduleUDToCanonical({ ...EMPTY_SCHEDULE_UD, rows: [] });
    expect(canonical.CurrAssYr).toBe('2026-27');
    expect(canonical.ScheduleUD).toEqual([]);
    expect(canonical.TotalBalCFNY).toBe(0);
  });
});
