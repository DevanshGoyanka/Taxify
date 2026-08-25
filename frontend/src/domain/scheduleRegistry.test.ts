import { describe, expect, it } from 'vitest';
import {
  SCHEDULE_REGISTRY,
  activeSchedules,
  blockingSchedules,
  getSchedule,
  schedulesForForm,
  type ScheduleStatus,
} from './scheduleRegistry';
import { type EligibilityFacts, type ItrForm } from './eligibility';

function makeFacts(overrides: Partial<EligibilityFacts> = {}): EligibilityFacts {
  return {
    hasSalary: true, hasCapitalGains: false, hasBusinessIncome: false,
    hasProfessionalIncome: false, hasLotteryOrGamingIncome: false,
    hasVdaIncome: false, hasForeignIncomeOrAssets: false,
    hasMultipleHouseProperties: false, residentialStatus: 'ROR',
    isDirector: false, hasUnlistedShares: false, agriculturalIncome: 0,
    isAudited: false, hasBroughtForwardLosses: false, totalIncome: 500_000,
    presumptiveScheme: undefined,
    hasOutOfScopeTaxableEvidence: false, hasNon112ACapitalGainsEvidence: false,
    hasBusinessIncomeEvidence: false,
    hasForeignRemittanceEvidence: false, hasUnreviewedEvidence: false,
    restricted112AAmount: 0,
    ...overrides,
  };
}

describe('SCHEDULE_REGISTRY', () => {
  it('has every official schedule for ITR-1', () => {
    const ids = schedulesForForm('ITR-1').map(s => s.id);
    expect(ids).toContain('PersonalInfo');
    expect(ids).toContain('FilingStatus');
    expect(ids).toContain('ScheduleS');
    expect(ids).toContain('ScheduleHP');
    expect(ids).toContain('ScheduleOS');
    expect(ids).toContain('LTCG112A');
    expect(ids).toContain('Verification');
    // Should NOT contain ITR-2/3-only schedules
    expect(ids).not.toContain('ScheduleCGFor23');
    expect(ids).not.toContain('ITR3ScheduleBP');
  });

  it('has every official schedule for ITR-2', () => {
    const ids = schedulesForForm('ITR-2').map(s => s.id);
    expect(ids).toContain('ScheduleCGFor23');
    expect(ids).toContain('Schedule112A');
    expect(ids).toContain('ScheduleVDA');
    expect(ids).toContain('ScheduleCYLA');
    expect(ids).toContain('ScheduleBFLA');
    expect(ids).toContain('ScheduleFSI');
    expect(ids).toContain('ScheduleFA');
    expect(ids).toContain('ScheduleAL');
    // Should NOT contain ITR-3-only schedules
    expect(ids).not.toContain('ITR3ScheduleBP');
    expect(ids).not.toContain('PARTA_BS');
  });

  it('has every official schedule for ITR-3', () => {
    const ids = schedulesForForm('ITR-3').map(s => s.id);
    expect(ids).toContain('PartA_GEN2');
    expect(ids).toContain('ITR3ScheduleBP');
    expect(ids).toContain('PARTA_BS');
    expect(ids).toContain('PARTA_PL');
    expect(ids).toContain('ScheduleDPM');
    expect(ids).toContain('ScheduleGST');
  });

  it('has every official schedule for ITR-4', () => {
    const ids = schedulesForForm('ITR-4').map(s => s.id);
    expect(ids).toContain('ScheduleBP');
    expect(ids).toContain('LTCG112A');
    // Should NOT contain ITR-2/3-only schedules
    expect(ids).not.toContain('ScheduleCGFor23');
    expect(ids).not.toContain('ScheduleAL');
  });

  it('getSchedule returns a schedule by ID', () => {
    const s = getSchedule('ScheduleS');
    expect(s).toBeDefined();
    expect(s!.id).toBe('ScheduleS');
    expect(s!.forms).toContain('ITR-1');
  });

  it('getSchedule returns undefined for unknown IDs', () => {
    expect(getSchedule('NonExistent')).toBeUndefined();
  });
});

describe('activeSchedules', () => {
  it('returns required and available schedules for ITR-1 simple salary case', () => {
    const active = activeSchedules('ITR-1', makeFacts());
    const ids = active.map(a => a.schedule.id);
    expect(ids).toContain('PersonalInfo');
    expect(ids).toContain('FilingStatus');
    expect(ids).toContain('ScheduleS'); // salary is present
    expect(ids).toContain('Verification');
    // ScheduleBP should NOT appear for ITR-1
    expect(ids).not.toContain('ScheduleBP');
  });

  it('includes ScheduleBP for ITR-4 when business income is present', () => {
    const active = activeSchedules('ITR-4', makeFacts({
      hasBusinessIncome: true,
      presumptiveScheme: '44AD',
    }));
    const ids = active.map(a => a.schedule.id);
    expect(ids).toContain('ScheduleBP');
  });

  it('includes CG schedules for ITR-2 when capital gains present', () => {
    const active = activeSchedules('ITR-2', makeFacts({ hasCapitalGains: true }));
    const ids = active.map(a => a.schedule.id);
    expect(ids).toContain('Schedule112A');
    expect(ids).toContain('ScheduleCGFor23');
  });

  it('marks ITR-3 required business schedules as missing', () => {
    const active = activeSchedules('ITR-3', makeFacts({ hasBusinessIncome: true }));
    const bp = active.find(a => a.schedule.id === 'ITR3ScheduleBP');
    expect(bp).toBeDefined();
    expect(bp!.status).toBe('missing');
    expect(bp!.required).toBe(true);
  });
});

describe('blockingSchedules', () => {
  it('returns Verification and FilingStatus as blockers for ITR-1 (always required, missing/partial)', () => {
    const blocking = blockingSchedules('ITR-1', makeFacts());
    const ids = blocking.map(s => s.id);
    // Verification is always required and currently 'missing' — that's a blocker.
    expect(ids).toContain('Verification');
    // FilingStatus is always required and currently 'partial' — that's a blocker.
    expect(ids).toContain('FilingStatus');
    // ScheduleHP, ScheduleOS, LTCG112A are optional for ITR-1 — NOT blockers.
    expect(ids).not.toContain('ScheduleHP');
    expect(ids).not.toContain('ScheduleOS');
    expect(ids).not.toContain('LTCG112A');
  });

  it('returns missing required ITR-3 schedules as blockers', () => {
    const blocking = blockingSchedules('ITR-3', makeFacts({ hasBusinessIncome: true }));
    const ids = blocking.map(s => s.id);
    expect(ids).toContain('PartA_GEN2');
    expect(ids).toContain('ITR3ScheduleBP');
    expect(ids).toContain('PARTA_BS');
    expect(ids).toContain('PARTA_PL');
  });
});
