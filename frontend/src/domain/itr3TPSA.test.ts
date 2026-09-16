import { describe, expect, it } from 'vitest';
import { ITR3_TPSA_COMPUTED_PATHS, ITR3_TPSA_INPUT_PATHS, emptyITR3TPSADeposit, updateITR3TPSADeposit, validateITR3TPSADeposit } from './itr3TPSA';
import { ITR3_COVERAGE_BY_PATH } from './itr3CoverageManifest';

describe('Schedule TPSA coverage', () => {
  it('covers all official TPSA paths with explicit dispositions', () => {
    const paths = [...ITR3_TPSA_COMPUTED_PATHS, ...ITR3_TPSA_INPUT_PATHS];
    expect(paths).toHaveLength(13);
    for (const path of paths) expect(ITR3_COVERAGE_BY_PATH.get(path)?.disposition).not.toBe('missing');
  });
  it('validates official deposit constraints and enum-free source facts', () => {
    const row = emptyITR3TPSADeposit('1');
    expect(validateITR3TPSADeposit(row)).toContain('BSRCode must contain 3 digits followed by 4 alphanumeric characters.');
    const valid = updateITR3TPSADeposit(row, { bsrCode: '1234ABC', bankBranchName: 'Main', dateDep: '2025-04-01', srlNoOfChaln: 1, amount: 2500 });
    expect(validateITR3TPSADeposit(valid)).toEqual([]);
  });
  it('immutably updates editable facts and clamps invalid monetary values', () => {
    const original = emptyITR3TPSADeposit('1');
    const updated = updateITR3TPSADeposit(original, { amount: -10, srlNoOfChaln: 100000 });
    expect(updated).not.toBe(original);
    expect(original.amount).toBe(0);
    expect(updated.amount).toBe(0);
    expect(updated.srlNoOfChaln).toBe(99999);
  });
});
