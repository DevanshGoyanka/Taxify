import { describe, expect, it } from 'vitest';
import {
  assessFormEligibility,
  assessFormEligibilityFromDraft,
  collectEligibilityFacts,
  collectEligibilityFactsFromDraft,
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
    hasOutOfScopeTaxableEvidence: false,
    hasNon112ACapitalGainsEvidence: false,
    hasBusinessIncomeEvidence: false,
    hasForeignRemittanceEvidence: false,
    hasUnreviewedEvidence: false,
    restricted112AAmount: 0,
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

  it('keeps ITR-1 eligible for two official PropertyDetails rows', () => {
    const rec = assessFormEligibility({
      basic: 600_000,
      residentialStatus: 'ROR',
      housePropertyEntries: [{ propertyType: 'SELF_OCCUPIED' }, { propertyType: 'LET_OUT' }],
    }, { totalIncome: 600_000 });
    expect(rec.recommendedForm).toBe('ITR-1');
    expect(rec.eligibleForms['ITR-1']).toBe(true);
  });

  it('requires ITR-2 once PropertyDetails exceeds the official two-row limit', () => {
    const rec = assessFormEligibility({
      basic: 600_000,
      residentialStatus: 'ROR',
      housePropertyEntries: [{}, {}, {}],
    }, { totalIncome: 600_000 });
    expect(rec.recommendedForm).toBe('ITR-2');
    expect(rec.eligibleForms['ITR-1']).toBe(false);
  });
});

// ── Evidence-driven eligibility ──────────────────────────────────────────────

describe('collectEligibilityFactsFromDraft', () => {
  function draftWithEvidence(rows: Array<{ role: string; source?: string; sourceCode?: string; relatedTab?: string; acceptedAmount?: number; processedAmount?: number; reportedAmount?: number }>, formData: Record<string, unknown> = {}) {
    return {
      reconciliation: { evidence: rows, discrepancies: [] },
      employers: formData.basic ? [{ id: 'e', employerName: 'X', basic: Number(formData.basic) || 0 }] : [],
      personal: { residentialStatus: formData.residentialStatus as 'ROR' | 'RNOR' | 'NR' | undefined },
    } as unknown as Parameters<typeof assessFormEligibilityFromDraft>[0];
  }

  it('returns all-false for a draft with no evidence', () => {
    const facts = collectEligibilityFactsFromDraft(draftWithEvidence([]));
    expect(facts).toMatchObject({
      hasOutOfScopeTaxableEvidence: false,
      hasNon112ACapitalGainsEvidence: false,
      hasBusinessIncomeEvidence: false,
      hasForeignRemittanceEvidence: false,
      hasUnreviewedEvidence: false,
      restricted112AAmount: 0,
    });
  });

  it('detects non-112A capital-gains evidence (SFT-012, 194IA) and blocks ITR-1', () => {
    const facts = collectEligibilityFactsFromDraft(draftWithEvidence([
      { role: 'OUT_OF_SCOPE_TAXABLE', source: 'AIS', sourceCode: 'SFT-012', relatedTab: 'CAPITAL_GAINS' },
    ]));
    expect(facts.hasNon112ACapitalGainsEvidence).toBe(true);
    expect(facts.hasCapitalGains).toBe(true);
  });

  it('classifies 112A sale evidence (SFT-17-LES) as RESTRICTED_112A_TAXABLE, not OUT_OF_SCOPE', () => {
    const facts = collectEligibilityFactsFromDraft(draftWithEvidence([
      { role: 'RESTRICTED_112A_TAXABLE', source: 'AIS', sourceCode: 'SFT-17-LES(M)', relatedTab: 'CAPITAL_GAINS', acceptedAmount: 100_000 },
    ]));
    expect(facts.hasNon112ACapitalGainsEvidence).toBe(false);
    expect(facts.restricted112AAmount).toBe(100_000);
    // ₹1L is within the ₹1.25L ITR-1/4 exemption — does NOT block ITR-1.
    expect(facts.hasCapitalGains).toBe(false);
  });

  it('blocks ITR-1 when 112A proceeds exceed ₹1.25L', () => {
    const facts = collectEligibilityFactsFromDraft(draftWithEvidence([
      { role: 'RESTRICTED_112A_TAXABLE', source: 'AIS', sourceCode: 'SFT-17-LES(M)', relatedTab: 'CAPITAL_GAINS', acceptedAmount: 200_000 },
    ]));
    expect(facts.restricted112AAmount).toBe(200_000);
    expect(facts.hasCapitalGains).toBe(true);
  });

  it('detects business-income evidence (TDS-194C/194D/194H)', () => {
    const facts = collectEligibilityFactsFromDraft(draftWithEvidence([
      { role: 'OUT_OF_SCOPE_TAXABLE', source: 'AIS', sourceCode: 'TDS-194C', relatedTab: 'BUSINESS' },
    ]));
    expect(facts.hasBusinessIncomeEvidence).toBe(true);
  });

  it('detects foreign-remittance TCS evidence (206CQ)', () => {
    const facts = collectEligibilityFactsFromDraft(draftWithEvidence([
      { role: 'TAX_CREDIT', source: '26AS', sourceCode: '206CQ', relatedTab: 'TAXES' },
    ]));
    expect(facts.hasForeignRemittanceEvidence).toBe(true);
  });

  it('detects unclassified evidence (PARSER_WARNING)', () => {
    const facts = collectEligibilityFactsFromDraft(draftWithEvidence([
      { role: 'PARSER_WARNING', source: 'AIS', sourceCode: 'UNKNOWN', relatedTab: 'RECONCILIATION' },
    ]));
    expect(facts.hasUnreviewedEvidence).toBe(true);
  });
});

describe('assessFormEligibilityFromDraft', () => {
  function draftWithEvidence(rows: Array<{ role: string; source?: string; sourceCode?: string; relatedTab?: string; acceptedAmount?: number; processedAmount?: number; reportedAmount?: number }>, formData: Record<string, unknown> = {}) {
    return {
      reconciliation: { evidence: rows, discrepancies: [] },
      employers: formData.basic ? [{ id: 'e', employerName: 'X', basic: Number(formData.basic) || 0 }] : [],
      personal: { residentialStatus: formData.residentialStatus as 'ROR' | 'RNOR' | 'NR' | undefined },
    } as unknown as Parameters<typeof assessFormEligibilityFromDraft>[0];
  }

  it('keeps ITR-1 when evidence is only salary and interest', () => {
    const rec = assessFormEligibilityFromDraft(
      draftWithEvidence([
        { role: 'TAXABLE_ITR1', source: 'AIS', sourceCode: 'TDS-192', relatedTab: 'SALARY' },
        { role: 'TAXABLE_ITR1', source: 'AIS', sourceCode: 'SFT-016(SB)', relatedTab: 'OTHER_SOURCES' },
      ], { basic: 600_000, residentialStatus: 'ROR' }),
      { totalIncome: 600_000 },
    );
    expect(rec.recommendedForm).toBe('ITR-1');
    expect(rec.eligibleForms['ITR-1']).toBe(true);
  });

  it('keeps ITR-1 eligible when 112A sale proceeds are within ₹1.25L exemption', () => {
    const rec = assessFormEligibilityFromDraft(
      draftWithEvidence([
        { role: 'RESTRICTED_112A_TAXABLE', source: 'AIS', sourceCode: 'SFT-17-LES(M)', relatedTab: 'CAPITAL_GAINS', acceptedAmount: 100_000 },
        { role: 'RESTRICTED_112A_TAXABLE', source: 'AIS', sourceCode: 'SFT-18-EMF(M)', relatedTab: 'CAPITAL_GAINS', acceptedAmount: 25_000 },
      ], { basic: 600_000, residentialStatus: 'ROR' }),
      { totalIncome: 600_000 },
    );
    expect(rec.eligibleForms['ITR-1']).toBe(true);
    expect(rec.recommendedForm).toBe('ITR-1');
  });

  it('escalates to ITR-2 when 112A proceeds exceed ₹1.25L', () => {
    const rec = assessFormEligibilityFromDraft(
      draftWithEvidence([
        { role: 'RESTRICTED_112A_TAXABLE', source: 'AIS', sourceCode: 'SFT-17-LES(M)', relatedTab: 'CAPITAL_GAINS', acceptedAmount: 200_000 },
      ], { basic: 600_000, residentialStatus: 'ROR' }),
      { totalIncome: 600_000 },
    );
    expect(rec.eligibleForms['ITR-1']).toBe(false);
    expect(rec.blockersByForm['ITR-1'].some((b) => b.includes('112A'))).toBe(true);
  });

  it('escalates to ITR-2 when AIS has non-112A capital-gains evidence (property sale)', () => {
    const rec = assessFormEligibilityFromDraft(
      draftWithEvidence([
        { role: 'OUT_OF_SCOPE_TAXABLE', source: 'AIS', sourceCode: 'SFT-012', relatedTab: 'CAPITAL_GAINS' },
      ], { basic: 600_000, residentialStatus: 'ROR' }),
      { totalIncome: 600_000 },
    );
    expect(rec.eligibleForms['ITR-1']).toBe(false);
    expect(rec.blockersByForm['ITR-1'].some((b) => b.includes('non-112A'))).toBe(true);
  });

  it('does NOT treat purchase-only evidence as capital gains', () => {
    const rec = assessFormEligibilityFromDraft(
      draftWithEvidence([
        { role: 'ACQUISITION_ONLY', source: 'AIS', sourceCode: 'SFT-17(PUR)', relatedTab: 'RECONCILIATION' },
        { role: 'ACQUISITION_ONLY', source: 'AIS', sourceCode: 'SFT-012(P)', relatedTab: 'RECONCILIATION' },
      ], { basic: 600_000, residentialStatus: 'ROR' }),
      { totalIncome: 600_000 },
    );
    expect(rec.eligibleForms['ITR-1']).toBe(true);
    expect(rec.recommendedForm).toBe('ITR-1');
  });

  it('escalates away from ITR-1 when AIS has business receipts', () => {
    const rec = assessFormEligibilityFromDraft(
      draftWithEvidence([
        { role: 'OUT_OF_SCOPE_TAXABLE', source: 'AIS', sourceCode: 'TDS-194C', relatedTab: 'BUSINESS' },
      ], { basic: 600_000, residentialStatus: 'ROR' }),
      { totalIncome: 600_000 },
    );
    expect(rec.eligibleForms['ITR-1']).toBe(false);
    expect(rec.blockersByForm['ITR-1'].some((b) => b.includes('business'))).toBe(true);
  });

  it('blocks ITR-1 and ITR-4 when foreign-remittance TCS evidence is present', () => {
    const rec = assessFormEligibilityFromDraft(
      draftWithEvidence([
        { role: 'TAX_CREDIT', source: '26AS', sourceCode: '206CQ', relatedTab: 'TAXES' },
      ], { basic: 600_000, residentialStatus: 'ROR' }),
      { totalIncome: 600_000 },
    );
    expect(rec.eligibleForms['ITR-1']).toBe(false);
    expect(rec.eligibleForms['ITR-4']).toBe(false);
  });

  it('blocks ITR-1 when unclassified evidence requires review', () => {
    const rec = assessFormEligibilityFromDraft(
      draftWithEvidence([
        { role: 'PARSER_WARNING', source: 'AIS', sourceCode: 'UNKNOWN', relatedTab: 'RECONCILIATION' },
      ], { basic: 600_000, residentialStatus: 'ROR' }),
      { totalIncome: 600_000 },
    );
    expect(rec.eligibleForms['ITR-1']).toBe(false);
    expect(rec.blockersByForm['ITR-1'].some((b) => b.includes('review'))).toBe(true);
  });
});
