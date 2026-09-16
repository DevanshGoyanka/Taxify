import { describe, expect, it } from 'vitest';
import {
  SCHEDULE_BP_COMPUTED_FIELDS,
  SCHEDULE_BP_FIELDS,
  SCHEDULE_BP_PATH_COUNT,
  readScheduleBPValue,
  updateScheduleBPValue,
} from './itr3ScheduleBP';

describe('AY 2026-27 Schedule BP editor model', () => {
  it('classifies every official Schedule BP path exactly once', () => {
    expect(SCHEDULE_BP_FIELDS).toHaveLength(SCHEDULE_BP_PATH_COUNT);
    expect(new Set(SCHEDULE_BP_FIELDS.map((field) => field.path)).size).toBe(SCHEDULE_BP_PATH_COUNT);
    expect(SCHEDULE_BP_FIELDS.every((field) => ['editable-source', 'backend-computed', 'imported', 'backend-only'].includes(field.disposition))).toBe(true);
  });

  it('groups official rows across the complete business computation', () => {
    const groups = new Set(SCHEDULE_BP_FIELDS.map((field) => field.group));
    expect(groups).toEqual(new Set(['p-and-l-bridge', 'depreciation', 'disallowances-add-backs', 'exempt-other-head-income', 'icds', 'presumptive-income', 'speculative-specified-business', 'current-year-setoff', 'final-business-totals']));
    expect(SCHEDULE_BP_FIELDS.find((field) => field.path.endsWith('DepreciationAllowUs32_1_i'))?.label).toContain('Depreciation');
  });

  it('updates exact editable paths in canonical Schedule BP state', () => {
    const next = updateScheduleBPValue({}, 'ITR3ScheduleBP.BusinessIncOthThanSpec.AmtDebPLDisallowUs37', 1250);
    expect(readScheduleBPValue(next, 'ITR3ScheduleBP.BusinessIncOthThanSpec.AmtDebPLDisallowUs37')).toBe(1250);
  });

  it('does not allow UI updates to overwrite backend-computed totals', () => {
    const field = SCHEDULE_BP_COMPUTED_FIELDS.find((candidate) => candidate.path.endsWith('TotLossSetOffOnBus'));
    expect(field).toBeDefined();
    const path = field?.path ?? '';
    const original = updateScheduleBPValue({}, path, 999);
    expect(readScheduleBPValue(original, path)).toBeUndefined();
  });
});
