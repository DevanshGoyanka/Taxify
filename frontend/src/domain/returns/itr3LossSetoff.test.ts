import { describe, expect, it } from 'vitest';
import { ITR3_COVERAGE_MANIFEST } from '../itr3CoverageManifest';
import { applyItr3LossInput, ITR3_LOSS_INPUT_FIELDS, itr3LossCoverage } from './itr3LossSetoff';
import { createEmptyReturnDraft } from './factory';

describe('ITR-3 CYLA/BFLA editor model', () => {
  it('registers every official CYLA/BFLA path with an explicit disposition', () => {
    const official = ITR3_COVERAGE_MANIFEST.filter((entry) => entry.schedule === 'ScheduleCYLA' || entry.schedule === 'ScheduleBFLA');
    expect(itr3LossCoverage()).toHaveLength(official.length);
    expect(official.every((entry) => entry.disposition !== 'missing')).toBe(true);
  });

  it('writes editable fields to canonical draft paths without changing computed fields', () => {
    const draft = createEmptyReturnDraft('2026-27', 'ITR-3', 'new');
    const updated = applyItr3LossInput(draft, 'bfLossBusiness', '125000');
    expect(updated.lossesBroughtForward.bfLossBusiness).toBe(125000);
    expect(updated.lossesBroughtForward.bfLossHP).toBe(0);
    expect(updated).not.toHaveProperty('ScheduleCYLA');
    expect(ITR3_LOSS_INPUT_FIELDS.map((field) => field.path)).toContain('ScheduleCYLA.BusProfExclSpecProf.IncCYLA.IncOfCurYrUnderThatHead');
  });
});
