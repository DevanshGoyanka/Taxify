import { describe, expect, it } from 'vitest';
import {
  assessFormEligibility,
  collectEligibilityFacts,
  evaluateEligibility,
  type EligibilityFacts,
  type FormRecommendation,
  type ItrForm,
} from './eligibility';

// ── Helpers ─────────────────────────────────────────────────────────────────

function makeFacts(overrides: Partial<EligibilityFacts> = {}): EligibilityFacts {
  return {
    hasSalary: true,
    hasCapitalGains: false,
    hasBusinessIncome: false,
    hasProfessionalIncome: false,
    hasLotteryOrGamingIncome: false,
    hasVdaIncome: false,
    hasForeignIncomeOrAssets: false,
    hasMultipleHouseProperties: false,
    residentialStatus: 'ROR',
    isDirector: false,
    hasUnlistedShares: false,
    agriculturalIncome: 0,
    isAudited: false,
    hasBroughtForwardLosses: false,
    totalIncome: 500_000,
    presumptiveScheme: undefined,
    ...overrides,
  };
}

function emptyFormData(): Record<string, unknown> {
  return {
    basic: 0, residentialStatus: 'ROR', bizTurnover: 0, bpNetProfit: 0,
    bizPresumptive: 'Regular',
    employerEntries: [],
    capitalGainTransactions: [],
    housePropertyEntries: [],
  };
}

// ── Fact Collection ──────────────────────────────────────────────────────────

describe('collectEligibilityFacts', () => {
  it('derives salary from basic or employer entries', () => {
    expect(collectEligibilityFacts({ basic: 1_000_000 })).toMatchObject({ hasSalary: true });
    expect(collectEligibilityFacts({ employerEntries: [{ basic: 500_000 }] })).toMatchObject({ hasSalary: true });
    expect(collectEligibilityFacts({ basic: 0, employerEntries: [] })).toMatchObject({ hasSalary: false });
  });

  it('derives capital gains from legacy scalars or structured transactions', () => {
    expect(collectEligibilityFacts({ stcgPre: 10_000 })).toMatchObject({ hasCapitalGains: true });
    expect(collectEligibilityFacts({ ltcgOther: 5_000 })).toMatchObject({ hasCapitalGains: true });
    expect(collectEligibilityFacts({ capitalGainTransactions: [{ assetType: 'LISTED_EQUITY' }] }))
      .toMatchObject({ hasCapitalGains: true });
    expect(collectEligibilityFacts(emptyFormData())).toMatchObject({ hasCapitalGains: false });
  });

  it('detects business income from turnover or net profit', () => {
    expect(collectEligibilityFacts({ bizTurnover: 5_000_000 })).toMatchObject({ hasBusinessIncome: true });
    expect(collectEligibilityFacts({ bpNetProfit: 50_000 })).toMatchObject({ hasBusinessIncome: true });
  });

  it('detects presumptive scheme', () => {
    expect(collectEligibilityFacts({ bizTurnover: 5_000_000, bizPresumptive: '44AD' }))
      .toMatchObject({ hasBusinessIncome: true, presumptiveScheme: '44AD' });
    expect(collectEligibilityFacts({ bizTurnover: 5_000_000, bizPresumptive: 'Regular' }))
      .toMatchObject({ presumptiveScheme: undefined });
  });

  it('captures questionnaire facts', () => {
    expect(collectEligibilityFacts({ isDirector: true })).toMatchObject({ isDirector: true });
    expect(collectEligibilityFacts({ holdsUnlistedShares: true })).toMatchObject({ hasUnlistedShares: true });
    expect(collectEligibilityFacts({ residentialStatus: 'NR' })).toMatchObject({ residentialStatus: 'NR' });
  });
});

// ── Eligibility Engine ───────────────────────────────────────────────────────

describe('evaluateEligibility', () => {
  it('recommends ITR-1 for simple salary cases', () => {
    const r = evaluateEligibility(makeFacts());
    expect(r.recommendedForm).toBe('ITR-1');
    expect(r.eligibleForms['ITR-1']).toBe(true);
    expect(r.blockers).toHaveLength(0);
  });

  it('blocks ITR-1 when total income exceeds 50 lakh', () => {
    const r = evaluateEligibility(makeFacts({ totalIncome: 6_000_000 }));
    expect(r.eligibleForms['ITR-1']).toBe(false);
    expect(r.blockersByForm['ITR-1']).toContainEqual(expect.stringContaining('50 lakh'));
  });

  it('blocks ITR-1 when capital gains present', () => {
    const r = evaluateEligibility(makeFacts({ hasCapitalGains: true }));
    expect(r.eligibleForms['ITR-1']).toBe(false);
    expect(r.blockersByForm['ITR-1']).toContainEqual(expect.stringContaining('Capital gains'));
  });

  it('blocks ITR-1 for directors', () => {
    const r = evaluateEligibility(makeFacts({ isDirector: true }));
    expect(r.eligibleForms['ITR-1']).toBe(false);
    expect(r.blockersByForm['ITR-1']).toContainEqual(expect.stringContaining('Director'));
  });

  it('blocks ITR-1 for non-residents', () => {
    const r = evaluateEligibility(makeFacts({ residentialStatus: 'NR' }));
    expect(r.eligibleForms['ITR-1']).toBe(false);
  });

  it('recommends ITR-4 for presumptive business', () => {
    const r = evaluateEligibility(makeFacts({
      hasBusinessIncome: true,
      presumptiveScheme: '44AD',
      hasCapitalGains: false,
    }));
    expect(r.recommendedForm).toBe('ITR-4');
    expect(r.eligibleForms['ITR-4']).toBe(true);
  });

  it('recommends ITR-3 for non-presumptive business income', () => {
    const r = evaluateEligibility(makeFacts({
      hasBusinessIncome: true,
      presumptiveScheme: undefined,
      hasCapitalGains: true,
    }));
    expect(r.recommendedForm).toBe('ITR-3');
  });

  it('blocks ITR-4 for directors', () => {
    const r = evaluateEligibility(makeFacts({
      hasBusinessIncome: true,
      presumptiveScheme: '44AD',
      isDirector: true,
    }));
    expect(r.eligibleForms['ITR-4']).toBe(false);
  });

  it('recommends ITR-2 when capital gains force it and no business income', () => {
    const r = evaluateEligibility(makeFacts({
      hasCapitalGains: true,
      hasBusinessIncome: false,
      totalIncome: 3_000_000,
    }));
    expect(r.recommendedForm).toBe('ITR-2');
  });

  it('identifies missing facts when no income data provided', () => {
    const r = evaluateEligibility(makeFacts({
      hasSalary: false,
      totalIncome: 0,
    }));
    expect(r.missingFacts.length).toBeGreaterThan(0);
  });
});

// ── assessFormEligibility convenience ────────────────────────────────────────

describe('assessFormEligibility', () => {
  it('returns a complete FormRecommendation from form data', () => {
    const data = { basic: 600_000, residentialStatus: 'ROR' };
    const rec = assessFormEligibility(data, { totalIncome: 600_000 });
    expect(rec).toHaveProperty('recommendedForm');
    expect(rec).toHaveProperty('eligibleForms');
    expect(rec).toHaveProperty('blockers');
    expect(rec).toHaveProperty('blockersByForm');
    expect(rec.recommendedForm).toBe('ITR-1');
  });

  it('detects directors correctly from form data', () => {
    const data = { basic: 600_000, isDirector: true };
    const rec = assessFormEligibility(data);
    expect(rec.recommendedForm).toBe('ITR-2');
  });
});
