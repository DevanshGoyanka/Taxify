/**
 * Schedule Registry – CBDT AY 2026-27
 *
 * Every official schedule across all four ITR forms is declared here.
 * The UI reads this registry to decide which sections to show, which
 * facts to collect, and which blockers to surface for the selected form.
 *
 * CONVENTIONS
 *   • A schedule marked ``always`` means the official schema requires it
 *     unconditionally (e.g. PartA_GEN1, Verification).
 *   • ``conditional`` schedules activate when their ``applies`` predicate
 *     returns true given the current EligibilityFacts.
 *   • ``derived`` schedules are filled by the backend builder and are never
 *     displayed as editable sections.
 *   • ``unavailable`` schedules have no frontend capture at all.
 */

import type { ItrForm, EligibilityFacts } from './eligibility';

// ── Types ────────────────────────────────────────────────────────────────────

export type ScheduleStatus =
  | 'not-applicable'   // form doesn't support it
  | 'available'        // form supports it with capture UI
  | 'partial'          // form supports some fields, not all
  | 'missing'          // form requires it, no UI yet
  | 'derived'          // computed by backend, no input needed
  | 'unavailable';     // not yet implemented for any form

export interface ScheduleDefinition {
  /** Official CBDT schema name. */
  id: string;
  /** Human-readable label. */
  label: string;
  /** Which forms include this schedule at all. */
  forms: readonly ItrForm[];
  /** Is this schedule always required (true), conditional (function), optional (false), or derived? */
  required: boolean | 'derived' | ((facts: EligibilityFacts) => boolean);
  /** Current implementation status per form. */
  status: Record<ItrForm, ScheduleStatus>;
  /** Description shown in the checklist. */
  description: string;
}

// ── Form lists ───────────────────────────────────────────────────────────────

const ALL: readonly ItrForm[] = ['ITR-1', 'ITR-2', 'ITR-3', 'ITR-4'];
const ITR1_4: readonly ItrForm[] = ['ITR-1', 'ITR-4'];
const ITR2_3: readonly ItrForm[] = ['ITR-2', 'ITR-3'];
const ITR3_ONLY: readonly ItrForm[] = ['ITR-3'];

// ── Status helpers ───────────────────────────────────────────────────────────

function statusRecord(
  availableOn: readonly ItrForm[],
  status: ScheduleStatus = 'available',
  overrides?: Partial<Record<ItrForm, ScheduleStatus>>,
): Record<ItrForm, ScheduleStatus> {
  const base: Record<ItrForm, ScheduleStatus> = {
    'ITR-1': 'not-applicable', 'ITR-2': 'not-applicable',
    'ITR-3': 'not-applicable', 'ITR-4': 'not-applicable',
  };
  for (const f of availableOn) base[f] = status;
  if (overrides) Object.assign(base, overrides);
  return base;
}

// ── Applicability predicates ─────────────────────────────────────────────────

const hasBusinessIncome = (f: EligibilityFacts): boolean =>
  f.hasBusinessIncome || f.presumptiveScheme !== undefined;

const isNotItr1Or4 = (_f: EligibilityFacts): boolean => true; // always applies for ITR-2/3

// ── Registry ─────────────────────────────────────────────────────────────────

export const SCHEDULE_REGISTRY: readonly ScheduleDefinition[] = [
  // ── Always‑required schedules (every form) ──
  {
    id: 'CreationInfo',
    label: 'Creation Info',
    forms: ALL,
    required: 'derived',
    status: statusRecord(ALL, 'derived'),
    description: 'Software‑generated metadata — not editable.',
  },
  {
    id: 'Verification',
    label: 'Verification',
    forms: ALL,
    required: true,
    status: statusRecord(ALL, 'missing'),
    description: 'Declaration accepted by the taxpayer — mandatory before filing.',
  },
  {
    id: 'TaxReturnPreparer',
    label: 'Tax Return Preparer',
    forms: ALL,
    required: false,
    status: statusRecord(ALL, 'not-applicable'),
    description: 'Only required when prepared by a TRP.',
  },

  // ── Personal & Filing ──
  {
    id: 'PersonalInfo',
    label: 'Personal Information',
    forms: ALL,
    required: true,
    status: statusRecord(ALL, 'available'),
    description: 'Name, PAN, Aadhaar, DOB, contact, and address.',
  },
  {
    id: 'FilingStatus',
    label: 'Filing Status',
    forms: ALL,
    required: true,
    status: statusRecord(ALL, 'partial'),
    description: 'Return type, due date, revised-return evidence, Form 10‑IEA elections.',
  },

  // ── Income schedules ──
  {
    id: 'ScheduleS',
    label: 'Salary Income',
    forms: ['ITR-1', 'ITR-2', 'ITR-3', 'ITR-4'],
    required: (f) => f.hasSalary,
    status: statusRecord(ALL, 'available'),
    description: 'Section 17(1/2/3) salary, allowances, perquisites, and employer details.',
  },
  {
    id: 'ScheduleHP',
    label: 'House Property',
    forms: ALL,
    required: false,
    status: statusRecord(ALL, 'available'),
    description: 'Income / loss from house property — self‑occupied, let‑out, or deemed let‑out.',
  },
  {
    id: 'ScheduleOS',
    label: 'Other Sources',
    forms: ALL,
    required: false,
    status: statusRecord(ALL, 'available'),
    description: 'Interest, dividends, family pension, gifts, and winnings.',
  },
  {
    id: 'ScheduleEI',
    label: 'Exempt Income',
    forms: ALL,
    required: false,
    status: statusRecord(ALL, 'partial'),
    description: 'Agricultural income, PPF interest, gratuity, VRS, and other exempt categories.',
  },
  {
    id: 'ScheduleBP',
    label: 'Business / Profession',
    forms: ['ITR-3', 'ITR-4'],
    required: hasBusinessIncome,
    status: statusRecord(['ITR-3', 'ITR-4'], 'partial'),
    description: 'Presumptive 44AD / 44ADA / 44AE, regular business, GST turnover, financial particulars.',
  },

  // ── Capital Gains ──
  {
    id: 'LTCG112A',
    label: 'LTCG u/s 112A',
    forms: ['ITR-1', 'ITR-4'],
    required: false,
    status: statusRecord(['ITR-1', 'ITR-4'], 'available', { 'ITR-2': 'not-applicable', 'ITR-3': 'not-applicable' }),
    description: 'Restricted long‑term capital gains on listed equity / equity MF / business trust units.',
  },
  {
    id: 'Schedule112A',
    label: 'Schedule 112A',
    forms: ITR2_3,
    required: (f) => f.hasCapitalGains,
    status: statusRecord(ITR2_3, 'partial'),
    description: 'Full Schedule 112A scrip‑level detail for ITR‑2 and ITR‑3.',
  },
  {
    id: 'ScheduleCGFor23',
    label: 'Capital Gains',
    forms: ITR2_3,
    required: (f) => f.hasCapitalGains,
    status: statusRecord(ITR2_3, 'partial'),
    description: 'Land, building, unlisted shares, debt MF, jewellery — full capital‑gains schedule.',
  },
  {
    id: 'Schedule115AD',
    label: 'FII Capital Gains (115AD)',
    forms: ITR2_3,
    required: false,
    status: statusRecord(ITR2_3, 'missing'),
    description: 'Capital gains for Foreign Institutional Investors.',
  },
  {
    id: 'ScheduleVDA',
    label: 'Virtual Digital Assets',
    forms: ITR2_3,
    required: (f) => f.hasVdaIncome,
    status: statusRecord(ITR2_3, 'partial'),
    description: 'Gains / loss on cryptocurrency, NFTs, and other VDAs.',
  },

  // ── Loss set‑off ──
  {
    id: 'ScheduleCYLA',
    label: 'Current Year Loss Adjustment',
    forms: ITR2_3,
    required: true,
    status: statusRecord(ITR2_3, 'derived'),
    description: 'Set‑off of current‑year losses across heads — derived by the backend.',
  },
  {
    id: 'ScheduleBFLA',
    label: 'Brought Forward Losses',
    forms: ITR2_3,
    required: true,
    status: statusRecord(ITR2_3, 'partial'),
    description: 'Brought‑forward loss detail and set‑off from prior years.',
  },
  {
    id: 'ScheduleCFL',
    label: 'Carried Forward Losses',
    forms: ITR2_3,
    required: false,
    status: statusRecord(ITR2_3, 'derived'),
    description: 'Losses carried forward to future years — derived by the backend.',
  },

  // ── Special income / rates ──
  {
    id: 'ScheduleSI',
    label: 'Special Rate Income',
    forms: ITR2_3,
    required: false,
    status: statusRecord(ITR2_3, 'missing'),
    description: 'Income taxable at special rates under Sections 115BB / 115BBE / etc.',
  },
  {
    id: 'ScheduleSPI',
    label: 'Clubbing of Income',
    forms: ITR2_3,
    required: false,
    status: statusRecord(ITR2_3, 'missing'),
    description: 'Income of specified persons clubbed with the assessee.',
  },
  {
    id: 'SchedulePTI',
    label: 'Pass‑Through Income',
    forms: ITR2_3,
    required: false,
    status: statusRecord(ITR2_3, 'missing'),
    description: 'Income from business trust / investment fund pass‑through.',
  },

  // ── Foreign ──
  {
    id: 'ScheduleFSI',
    label: 'Foreign Source Income',
    forms: ITR2_3,
    required: (f) => f.hasForeignIncomeOrAssets,
    status: statusRecord(ITR2_3, 'missing'),
    description: 'Income accrued / arising outside India.',
  },
  {
    id: 'ScheduleTR1',
    label: 'Foreign Tax Credit (TR)',
    forms: ITR2_3,
    required: (f) => f.hasForeignIncomeOrAssets,
    status: statusRecord(ITR2_3, 'missing'),
    description: 'Relief under DTAA / Section 90 / 91 for taxes paid abroad.',
  },
  {
    id: 'ScheduleFA',
    label: 'Foreign Assets',
    forms: ITR2_3,
    required: (f) => f.hasForeignIncomeOrAssets,
    status: statusRecord(ITR2_3, 'missing'),
    description: 'Details of foreign bank accounts, property, trusts, and signing authority.',
  },

  // ── AMT ──
  {
    id: 'ScheduleAMT',
    label: 'Alternate Minimum Tax',
    forms: ITR2_3,
    required: hasBusinessIncome,
    status: statusRecord(ITR2_3, 'missing'),
    description: 'AMT computation under Section 115JC.',
  },
  {
    id: 'ScheduleAMTC',
    label: 'AMT Credit',
    forms: ITR2_3,
    required: hasBusinessIncome,
    status: statusRecord(ITR2_3, 'missing'),
    description: 'AMT credit brought forward and utilised.',
  },

  // ── Miscellaneous ITR‑2 / ITR‑3 ──
  {
    id: 'ScheduleAL',
    label: 'Asset‑Liability Schedule',
    forms: ITR2_3,
    required: (f) => f.totalIncome > 50_000_000,
    status: statusRecord(ITR2_3, 'missing'),
    description: 'Statement of assets and liabilities — mandatory when income exceeds ₹50 lakh.',
  },
  {
    id: 'Schedule5A2014',
    label: 'Portuguese Civil Code',
    forms: ITR2_3,
    required: false,
    status: statusRecord(ITR2_3, 'missing'),
    description: 'Income apportionment under Portuguese Civil Code — Goa, Daman, and Diu.',
  },
  {
    id: 'ScheduleESOP',
    label: 'ESOP Tax Deferral',
    forms: ITR2_3,
    required: false,
    status: statusRecord(ITR2_3, 'missing'),
    description: 'Eligible startup ESOP tax deferral under Section 192(1C).',
  },

  // ── ITR‑3 Business schedules (REQUIRED) ──
  {
    id: 'PartA_GEN2',
    label: 'Business Profile',
    forms: ITR3_ONLY,
    required: true,
    status: statusRecord(ITR3_ONLY, 'missing'),
    description: 'Audit information, nature of business codes, and Section 44AA / 44AB applicability.',
  },
  {
    id: 'ITR3ScheduleBP',
    label: 'PGBP Computation',
    forms: ITR3_ONLY,
    required: true,
    status: statusRecord(ITR3_ONLY, 'missing'),
    description: 'Profit and gains of business or profession — the core ITR‑3 schedule.',
  },
  {
    id: 'PARTA_BS',
    label: 'Balance Sheet',
    forms: ITR3_ONLY,
    required: true,
    status: statusRecord(ITR3_ONLY, 'missing'),
    description: 'Full balance sheet — capital, liabilities, assets.',
  },
  {
    id: 'PARTA_PL',
    label: 'Profit & Loss Account',
    forms: ITR3_ONLY,
    required: true,
    status: statusRecord(ITR3_ONLY, 'missing'),
    description: 'Detailed profit and loss statement with expenditure classification.',
  },

  // ── ITR‑3 conditional business schedules ──
  {
    id: 'ManufacturingAccount',
    label: 'Manufacturing Account',
    forms: ITR3_ONLY,
    required: false,
    status: statusRecord(ITR3_ONLY, 'missing'),
    description: 'Manufacturing account — raw materials, WIP, finished goods.',
  },
  {
    id: 'TradingAccount',
    label: 'Trading Account',
    forms: ITR3_ONLY,
    required: false,
    status: statusRecord(ITR3_ONLY, 'missing'),
    description: 'Trading account — purchases, sales, opening / closing stock.',
  },
  {
    id: 'ScheduleDPM',
    label: 'Depreciation — Plant & Machinery',
    forms: ITR3_ONLY,
    required: false,
    status: statusRecord(ITR3_ONLY, 'missing'),
    description: 'Depreciation block schedule for plant and machinery under Section 32.',
  },
  {
    id: 'ScheduleDOA',
    label: 'Depreciation — Other Assets',
    forms: ITR3_ONLY,
    required: false,
    status: statusRecord(ITR3_ONLY, 'missing'),
    description: 'Depreciation on buildings, furniture, intangibles, and other assets.',
  },
  {
    id: 'ScheduleDEP',
    label: 'Depreciation Summary',
    forms: ITR3_ONLY,
    required: false,
    status: statusRecord(ITR3_ONLY, 'missing'),
    description: 'Aggregate depreciation summary as per the IT Act.',
  },
  {
    id: 'ScheduleDCG',
    label: 'Deemed Capital Gains',
    forms: ITR3_ONLY,
    required: false,
    status: statusRecord(ITR3_ONLY, 'missing'),
    description: 'Capital gains on sale of depreciable assets under Section 50.',
  },
  {
    id: 'ScheduleESR',
    label: 'ESR (Employer‑Employee)',
    forms: ITR3_ONLY,
    required: false,
    status: statusRecord(ITR3_ONLY, 'missing'),
    description: 'Employer‑employee relationship disclosure.',
  },
  {
    id: 'ITR3ScheduleUD',
    label: 'Unabsorbed Depreciation',
    forms: ITR3_ONLY,
    required: false,
    status: statusRecord(ITR3_ONLY, 'missing'),
    description: 'Unabsorbed depreciation brought forward and set‑off.',
  },
  {
    id: 'ScheduleICDS',
    label: 'ICDS Adjustments',
    forms: ITR3_ONLY,
    required: false,
    status: statusRecord(ITR3_ONLY, 'missing'),
    description: 'Income Computation and Disclosure Standards adjustments.',
  },
  {
    id: 'Schedule10AA',
    label: 'Section 10AA — SEZ',
    forms: ITR3_ONLY,
    required: false,
    status: statusRecord(ITR3_ONLY, 'missing'),
    description: 'Deduction for units in Special Economic Zones.',
  },
  {
    id: 'Schedule80_IA',
    label: 'Section 80‑IA',
    forms: ITR3_ONLY,
    required: false,
    status: statusRecord(ITR3_ONLY, 'missing'),
    description: 'Infrastructure / power / telecom deduction.',
  },
  {
    id: 'Schedule80_IB',
    label: 'Section 80‑IB',
    forms: ITR3_ONLY,
    required: false,
    status: statusRecord(ITR3_ONLY, 'missing'),
    description: 'Industrial undertaking / housing project deduction.',
  },
  {
    id: 'Schedule80_IC',
    label: 'Section 80‑IC',
    forms: ITR3_ONLY,
    required: false,
    status: statusRecord(ITR3_ONLY, 'missing'),
    description: 'Special category states undertaking deduction.',
  },
  {
    id: 'Schedule80RA',
    label: 'Section 80R / 80RRA',
    forms: ITR3_ONLY,
    required: false,
    status: statusRecord(ITR3_ONLY, 'missing'),
    description: 'Royalty / patent / remuneration from foreign sources.',
  },
  {
    id: 'ScheduleIF',
    label: 'Investment Fund Income',
    forms: ITR3_ONLY,
    required: false,
    status: statusRecord(ITR3_ONLY, 'missing'),
    description: 'Income from investment fund under Section 115UB.',
  },
  {
    id: 'ScheduleTPSA',
    label: 'Section 115TD (Accreted Income)',
    forms: ITR3_ONLY,
    required: false,
    status: statusRecord(ITR3_ONLY, 'missing'),
    description: 'Accreted income of a trust under Section 115TD.',
  },
  {
    id: 'ScheduleGST',
    label: 'GST Turnover',
    forms: ITR3_ONLY,
    required: false,
    status: statusRecord(ITR3_ONLY, 'missing'),
    description: 'GSTIN‑wise turnover detail.',
  },
];

// ── Derived immutable maps ───────────────────────────────────────────────────

const BY_ID = new Map<string, ScheduleDefinition>();
for (const s of SCHEDULE_REGISTRY) BY_ID.set(s.id, s);

/** Look up a single schedule by its CBDT identifier. */
export function getSchedule(id: string): ScheduleDefinition | undefined {
  return BY_ID.get(id);
}

/** All schedules applicable to a given form. */
export function schedulesForForm(form: ItrForm): readonly ScheduleDefinition[] {
  return SCHEDULE_REGISTRY.filter((s) => (s.forms as readonly ItrForm[]).includes(form));
}

/** Schedules that are currently blocking for the selected form. */
export function blockingSchedules(
  form: ItrForm,
  facts: EligibilityFacts,
): readonly ScheduleDefinition[] {
  return schedulesForForm(form).filter((s) => {
    if (s.required === 'derived') return false;
    if (s.required === false) return false;
    if (typeof s.required === 'function' && !s.required(facts)) return false;
    const st = s.status[form];
    return st === 'missing' || st === 'partial';
  });
}

/**
 * Active (visible) schedule statuses for a form, driven by applicability.
 * Returns only schedules that are:
 *   - always required, or
 *   - conditionally required AND activated, or
 *   - optional but with `available` / `partial` / `missing` status.
 */
export function activeSchedules(
  form: ItrForm,
  facts: EligibilityFacts,
): { schedule: ScheduleDefinition; status: ScheduleStatus; required: boolean }[] {
  return schedulesForForm(form)
    .map((s) => {
      const isRequired =
        s.required === true ||
        (typeof s.required === 'function' && s.required(facts));
      return {
        schedule: s,
        status: s.status[form],
        required: isRequired,
      };
    })
    .filter(({ status, required, schedule }) => {
      if (schedule.required === 'derived') return false;
      if (status === 'not-applicable') return false;
      if (!required && status !== 'missing' && status !== 'partial') return status === 'available';
      return true; // required OR missing OR partial
    });
}
