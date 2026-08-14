/**
 * CBDT Form Eligibility Engine – AY 2026-27
 *
 * Single authority for which ITR forms a taxpayer may file.  Driven by
 * facts from user imports, explicit questionnaire answers, and computed
 * tax results.  Never auto-switches the form silently; returns a
 * recommendation the UI presents for user confirmation.
 *
 * All rules reference the official IT Master Circular and the CBDT
 * AY 2026-27 notification for ITR-1 / ITR-2 / ITR-3 / ITR-4.
 */

// ── Types ────────────────────────────────────────────────────────────────────

export type ItrForm = 'ITR-1' | 'ITR-2' | 'ITR-3' | 'ITR-4';

export interface EligibilityFacts {
  // ── Import‑derived facts ──
  hasSalary: boolean;
  hasCapitalGains: boolean;
  hasBusinessIncome: boolean;
  hasProfessionalIncome: boolean;
  hasLotteryOrGamingIncome: boolean;
  hasVdaIncome: boolean;
  hasForeignIncomeOrAssets: boolean;
  hasMultipleHouseProperties: boolean;

  // ── Questionnaire / explicit facts ──
  residentialStatus: 'ROR' | 'RNOR' | 'NR';
  isDirector: boolean;
  hasUnlistedShares: boolean;
  agriculturalIncome: number;
  isAudited: boolean;
  hasBroughtForwardLosses: boolean;

  // ── Computed / derived ──
  totalIncome: number;
  presumptiveScheme?: '44AD' | '44ADA' | '44AE' | 'Regular';
}

export interface FormRecommendation {
  /** The single best-guess recommended form. */
  recommendedForm: ItrForm;
  /** Every form the taxpayer could elect, with eligibility verdicts. */
  eligibleForms: Record<ItrForm, boolean>;
  /** Human-readable reason for the recommendation. */
  reason: string;
  /** If the recommended form is ineligible, why.  Empty when eligible. */
  blockers: string[];
  /** Facts that are still missing and affect eligibility. */
  missingFacts: string[];
  /** Per-form list of blockers — used by the manual-switch UI. */
  blockersByForm: Record<ItrForm, string[]>;
}

// ── Fact collectors ──────────────────────────────────────────────────────────

/**
 * Derives a rich EligibilityFacts object from the current form data,
 * the latest tax result, and any explicitly set questionnaire fields.
 */
export function collectEligibilityFacts(
  formData: Record<string, unknown>,
  taxResult?: Record<string, unknown> | null,
): EligibilityFacts {
  const m = (key: string): number => Number(formData[key] ?? 0) || 0;

  // ── Import‑derived facts ──
  const hasSalary =
    m('basic') > 0 ||
    (Array.isArray(formData.employerEntries) && formData.employerEntries.length > 0);
  const hasCapitalGains =
    m('stcgPre') > 0 || m('stcgPost') > 0 || m('stcgOther') > 0 ||
    m('ltcgPre') > 0 || m('ltcgPost') > 0 || m('ltcgOther') > 0 ||
    (Array.isArray(formData.capitalGainTransactions) && formData.capitalGainTransactions.length > 0);
  const hasBusinessIncome = m('bizTurnover') > 0 || m('bpNetProfit') > 0;
  const hasLotteryOrGamingIncome =
    m('lotteryIncome') > 0 || m('onlineGamingIncome') > 0 ||
    m('cardGameIncome') > 0 || m('horseRaceIncome') > 0 || m('raceWinnings') > 0;
  const hasVdaIncome = m('vdaGains') > 0;
  const hasForeignIncomeOrAssets = m('foreignIncome') > 0 || m('foreignAssets') > 0;
  // Official AY 2026-27 ITR-1 V1.1 schema permits PropertyDetails.maxItems = 2.
  const hasMultipleHouseProperties =
    (Array.isArray(formData.housePropertyEntries) && formData.housePropertyEntries.length > 2) ||
    (formData.hpType === 'letout' && m('grossRent') > 0 && (formData.hpType2 !== undefined));

  // ── Questionnaire / explicit ──
  const residentialStatus = (String(formData.residentialStatus ?? 'ROR')) as EligibilityFacts['residentialStatus'];
  const isDirector = Boolean(formData.isDirector);
  const hasUnlistedShares = Boolean(formData.holdsUnlistedShares);
  const agriculturalIncome = m('agriculturalIncome') + m('agricultureIncome');
  const hasBroughtForwardLosses =
    m('bfLossHP') > 0 || m('bfLossBusiness') > 0 || m('bfLossSTCG') > 0 || m('bfLossLTCG') > 0;

  // ── Computed ──
  const totalIncome = Number(taxResult?.totalIncome ?? 0) || 0;
  const bizPresumptive = String(formData.bizPresumptive ?? 'Regular');
  const presumptiveScheme = hasBusinessIncome
    ? (['44AD', '44ADA', '44AE'].includes(bizPresumptive) ? bizPresumptive as '44AD' | '44ADA' | '44AE' : undefined)
    : undefined;

  return {
    hasSalary, hasCapitalGains, hasBusinessIncome,
    hasProfessionalIncome: m('professionalIncome') > 0, hasLotteryOrGamingIncome,
    hasVdaIncome, hasForeignIncomeOrAssets, hasMultipleHouseProperties,
    residentialStatus, isDirector, hasUnlistedShares, agriculturalIncome,
    isAudited: Boolean(formData.isAudited), hasBroughtForwardLosses,
    totalIncome, presumptiveScheme,
  };
}

// ── Rule helpers ─────────────────────────────────────────────────────────────

const ITR_FORMS: readonly ItrForm[] = ['ITR-1', 'ITR-2', 'ITR-3', 'ITR-4'] as const;

/**
 * Returns every eligible form with blockers, plus a single recommendation.
 *
 * ITR‑3 and ITR‑4 are considered “future” forms that need explicit user
 * acknowledgement before filing.  The eligibility engine allows them, but
 * the UI may show a compatibility note until those workflows ship.
 */
export function evaluateEligibility(facts: EligibilityFacts): FormRecommendation {
  const blockers: Record<ItrForm, string[]> = { 'ITR-1': [], 'ITR-2': [], 'ITR-3': [], 'ITR-4': [] };

  // ── ITR-1 rules (most restrictive) ──────────────────────────────────────
  if (facts.totalIncome > 5_000_000)
    blockers['ITR-1'].push('Total income exceeds ₹50 lakh');
  if (facts.hasCapitalGains)
    blockers['ITR-1'].push('Capital gains require ITR-2 or higher');
  if (facts.hasBusinessIncome)
    blockers['ITR-1'].push('Business income requires ITR-3 or ITR-4');
  if (facts.agriculturalIncome > 5_000)
    blockers['ITR-1'].push('Agricultural income exceeds ₹5,000 (requires ITR-2)');
  if (facts.isDirector)
    blockers['ITR-1'].push('Directors must file ITR-2 or ITR-3');
  if (facts.hasUnlistedShares)
    blockers['ITR-1'].push('Unlisted equity shares require ITR-2');
  if (facts.residentialStatus !== 'ROR')
    blockers['ITR-1'].push('Non-resident / RNOR must file ITR-2');
  if (facts.hasBroughtForwardLosses)
    blockers['ITR-1'].push('Brought-forward losses require ITR-2');
  if (facts.hasLotteryOrGamingIncome)
    blockers['ITR-1'].push('Lottery / gaming income requires ITR-2');
  if (facts.hasForeignIncomeOrAssets)
    blockers['ITR-1'].push('Foreign income / assets require ITR-2');
  if (facts.hasMultipleHouseProperties)
    blockers['ITR-1'].push('More than one house property requires ITR-2');
  if (facts.hasVdaIncome)
    blockers['ITR-1'].push('VDA income requires ITR-2');

  // ── ITR-4 rules (presumptive only) ──────────────────────────────────────
  if (!facts.hasBusinessIncome)
    blockers['ITR-4'].push('ITR-4 is only for presumptive business income');
  if (facts.hasBusinessIncome && !facts.presumptiveScheme)
    blockers['ITR-4'].push('Regular (non-presumptive) business income requires ITR-3');
  if (facts.totalIncome > 50_000_000)
    blockers['ITR-4'].push('Total income exceeds ₹50 lakh (requires ITR-3)');
  if (facts.isDirector)
    blockers['ITR-4'].push('Directors cannot file ITR-4');
  if (facts.residentialStatus !== 'ROR')
    blockers['ITR-4'].push('Non-residents cannot file ITR-4');
  if (facts.hasUnlistedShares)
    blockers['ITR-4'].push('Unlisted equity holders cannot file ITR-4');
  if (facts.hasForeignIncomeOrAssets)
    blockers['ITR-4'].push('Foreign income / assets are outside ITR-4');
  // Capital gains outside restricted 112A also block ITR-4.
  if (facts.hasCapitalGains)
    blockers['ITR-4'].push('Capital gains outside restricted Section 112A are outside ITR-4');

  // ── ITR-3 rules (business, but not presumptive-only) ────────────────────
  if (!facts.hasBusinessIncome)
    blockers['ITR-3'].push('ITR-3 is only for business / professional income');
  if (facts.hasBusinessIncome && facts.presumptiveScheme)
    blockers['ITR-3'].push('Presumptive business should use ITR-4');
  // ITR-3 can handle everything ITR-2 can, so no ITR-2‑style blockers apply.

  // ── ITR-2 rules ─────────────────────────────────────────────────────────
  // ITR-2 cannot have business income of any kind (that's ITR-3 or ITR-4).
  if (facts.hasBusinessIncome)
    blockers['ITR-2'].push('Business / professional income requires ITR-3 or ITR-4');

  // ── Determine recommendation ────────────────────────────────────────────
  const eligible = (form: ItrForm): boolean => blockers[form].length === 0;

  let recommendedForm: ItrForm = 'ITR-1';
  let reason = 'Salary and simple income — ITR-1 is sufficient.';
  let primaryBlockers: string[] = [];

  if (eligible('ITR-1')) {
    recommendedForm = 'ITR-1';
    reason = 'Salary, one house property, and interest / dividends — ITR-1 eligible.';
  } else if (facts.hasBusinessIncome && facts.presumptiveScheme && eligible('ITR-4')) {
    recommendedForm = 'ITR-4';
    reason = `Presumptive business under Section ${facts.presumptiveScheme} — ITR-4 is the correct form.`;
  } else if (facts.hasBusinessIncome && eligible('ITR-3')) {
    recommendedForm = 'ITR-3';
    reason = 'Business / professional income — ITR-3 is required.';
  } else if (eligible('ITR-2')) {
    recommendedForm = 'ITR-2';
    reason = 'Capital gains, foreign assets, or special income — ITR-2 is required.';
  } else {
    // Pick the form with the fewest blockers as a best-effort recommendation.
    const ranked = (ITR_FORMS as ItrForm[])
      .map((f) => ({ form: f, count: blockers[f].length }))
      .sort((a, b) => a.count - b.count);
    recommendedForm = ranked[0].form;
    primaryBlockers = blockers[recommendedForm];
    reason = `${recommendedForm} has the fewest blockers (${primaryBlockers.length}) but may not be fileable. Resolve the issues below.`;
  }

  return {
    recommendedForm,
    eligibleForms: Object.fromEntries(ITR_FORMS.map((f) => [f, eligible(f)])) as Record<ItrForm, boolean>,
    reason,
    blockers: primaryBlockers,
    missingFacts: collectMissingFacts(facts),
    blockersByForm: { ...blockers },
  };
}

// ── Missing-fact detection ───────────────────────────────────────────────────

function collectMissingFacts(facts: EligibilityFacts): string[] {
  const missing: string[] = [];
  // Residential status is essential for ITR form routing.
  if (!facts.residentialStatus || facts.residentialStatus === 'ROR') {
    // ROR is the default; only flag when it's truly unset.
    // We don't flag this unless the form data is completely empty of any
    // residential status field — the UI sets ROR by default.
  }
  // If there are no income facts at all, the taxpayer hasn't provided data.
  const hasAnyIncome =
    facts.hasSalary || facts.hasCapitalGains || facts.hasBusinessIncome ||
    facts.hasLotteryOrGamingIncome || facts.hasVdaIncome || facts.agriculturalIncome > 0;
  if (!hasAnyIncome && facts.totalIncome === 0) {
    missing.push('No income data has been provided yet. Import AIS / 26AS, or enter income manually.');
  }
  return missing;
}

// ── Convenience ──────────────────────────────────────────────────────────────

/**
 * One-call helper: given form data and optional tax result, returns the
 * full eligibility recommendation.
 */
export function assessFormEligibility(
  formData: Record<string, unknown>,
  taxResult?: Record<string, unknown> | null,
): FormRecommendation {
  return evaluateEligibility(collectEligibilityFacts(formData, taxResult));
}
