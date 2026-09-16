import { describe, expect, it } from 'vitest';
import {
  CG_ACCRUAL_BUCKETS,
  CG_ACCRUAL_DATE_RANGES,
  EMPTY_SCHEDULE_CG_ACCRUAL,
  normalizeScheduleCGAccrual,
  scheduleCGAccrualPaths,
  updateScheduleCGAccrual,
  validateScheduleCGAccrual,
} from './itr3CapitalGainsAccrual';

describe('Schedule CG quarterly accrual', () => {
  it('covers exactly seven buckets and five official paths each', () => {
    expect(CG_ACCRUAL_BUCKETS).toHaveLength(7);
    expect(CG_ACCRUAL_DATE_RANGES).toHaveLength(5);
    expect(scheduleCGAccrualPaths()).toHaveLength(35);
    expect(new Set(scheduleCGAccrualPaths()).size).toBe(35);
  });

  it('normalizes missing, negative, and non-finite values safely', () => {
    const value = normalizeScheduleCGAccrual({ ShortTermUnder20Per: { Upto15Of6: 10, Upto15Of9: -2, Up16Of9To15Of12: 'bad' } });
    expect(value.ShortTermUnder20Per.Upto15Of6).toBe(10);
    expect(value.ShortTermUnder20Per.Upto15Of9).toBe(0);
    expect(value.ShortTermUnder20Per.Up16Of9To15Of12).toBe(0);
    expect(validateScheduleCGAccrual(value)).toEqual([]);
  });

  it('updates exactly one canonical bucket path', () => {
    const next = updateScheduleCGAccrual(EMPTY_SCHEDULE_CG_ACCRUAL, 'VDATrnsfGainsUnder30Per', 'Up16Of3To31Of3', 99);
    expect(next.VDATrnsfGainsUnder30Per.Up16Of3To31Of3).toBe(99);
    expect(next.ShortTermUnder20Per).toEqual(EMPTY_SCHEDULE_CG_ACCRUAL.ShortTermUnder20Per);
    expect(EMPTY_SCHEDULE_CG_ACCRUAL.VDATrnsfGainsUnder30Per.Up16Of3To31Of3).toBe(0);
  });

  it('rejects invalid edits and preserves the computed/read-only surface', () => {
    const current = EMPTY_SCHEDULE_CG_ACCRUAL;
    expect(updateScheduleCGAccrual(current, 'ShortTermUnder20Per', 'Upto15Of6', -1)).toBe(current);
    expect(updateScheduleCGAccrual(current, 'ShortTermUnder20Per', 'Upto15Of6', 1.5)).toBe(current);
    expect(validateScheduleCGAccrual({})).toHaveLength(7);
  });
});
