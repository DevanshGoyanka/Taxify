import { describe, expect, it } from 'vitest';
import {
  SCHEDULE_OS_FIELDS,
  SCHEDULE_OS_OFFICIAL_PATH_COUNT,
  isScheduleOSComputed,
  scheduleOSCoverageByGroup,
  updateScheduleOSField,
} from './scheduleOSCoverage';

describe('Schedule OS official coverage', () => {
  it('classifies exactly all 143 official AY 2026-27 paths', () => {
    expect(SCHEDULE_OS_OFFICIAL_PATH_COUNT).toBe(143);
    expect(SCHEDULE_OS_FIELDS).toHaveLength(143);
    expect(new Set(SCHEDULE_OS_FIELDS.map((field) => field.path)).size).toBe(143);
    expect(Object.values(scheduleOSCoverageByGroup()).reduce((total, count) => total + count, 0)).toBe(143);
  });

  it('protects backend-computed totals from UI overwrite', () => {
    const root = { total: 10, input: 2 };
    const computed = SCHEDULE_OS_FIELDS.find((field) => field.path.endsWith('.TotDeductions'));
    expect(computed).toBeDefined();
    expect(isScheduleOSComputed(computed!.path)).toBe(true);
    const result = updateScheduleOSField(root, computed!.path, 99);
    expect(result.changed).toBe(false);
    expect(result.value).toBe(root);
    expect(result.error).toContain('read-only');
  });

  it('rejects unknown paths and updates exact editable scalar paths immutably', () => {
    const root = { IncOthThanOwnRaceHorse: { IntrstFrmSavingBank: 0 } };
    const path = 'ScheduleOS.IncOthThanOwnRaceHorse.IntrstFrmSavingBank';
    const result = updateScheduleOSField(root, path, 1250);
    expect(result.changed).toBe(true);
    expect(result.value).toEqual({ IncOthThanOwnRaceHorse: { IntrstFrmSavingBank: 1250 } });
    expect(root.IncOthThanOwnRaceHorse.IntrstFrmSavingBank).toBe(0);
    expect(updateScheduleOSField(root, 'ScheduleOS.NotOfficial', 1).changed).toBe(false);
  });
});
