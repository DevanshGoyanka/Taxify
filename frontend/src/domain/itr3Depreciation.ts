import type { CanonicalJsonValue, ReturnDraft } from './returns/types';

/** Official depreciation block rates in AY 2026-27 Schedule DPM/DOA. */
export type DepreciationRate = 5 | 10 | 15 | 30 | 40 | 45;

/** Taxpayer-supplied facts for one official depreciation block. */
export interface DepreciationBlockInput {
  id: string;
  assetCategory: string;
  rate: DepreciationRate;
  openingWDV: number;
  additionsGreaterThan180Days: number;
  additionsLessThan180Days: number;
  disposals: number;
  transferSaleExpenditure: number;
  specialRate: number | null;
  businessUsePercent: number;
  openingDate: string | null;
  additionDates: string[];
}

/** Backend-computed statutory outputs for one depreciation block. */
export interface DepreciationBlockComputed {
  depreciationAtFullRate: number;
  depreciationAtHalfRate: number;
  totalDepreciation: number;
  wdvLastDay: number;
  netAggregateDepreciation: number;
  capitalGainUnderSection50: number;
  disallowanceUnderSection38_2: number;
}

/** Canonical depreciation workspace owned by an ITR-3 ReturnDraft. */
export interface DepreciationSchedule {
  dpm: DepreciationBlockInput[];
  doa: DepreciationBlockInput[];
  computed: {
    dpmTotal: number;
    doaTotal: number;
    totalDepreciation: number;
  };
}

/** Creates a safe empty depreciation schedule without fabricated asset rows. */
export function createEmptyDepreciationSchedule(): DepreciationSchedule {
  return { dpm: [], doa: [], computed: { dpmTotal: 0, doaTotal: 0, totalDepreciation: 0 } };
}

/** Returns a detached schedule with one validated taxpayer-input block appended. */
export function addDepreciationBlock(schedule: DepreciationSchedule, block: DepreciationBlockInput, kind: 'dpm' | 'doa'): DepreciationSchedule {
  if (!block.id.trim()) throw new Error('Depreciation block id is required');
  if (!Number.isFinite(block.rate) || block.rate <= 0) throw new Error('Depreciation rate must be positive');
  if (block.businessUsePercent < 0 || block.businessUsePercent > 100) throw new Error('Business use must be between 0 and 100');
  const copy = { ...block, additionDates: [...block.additionDates] };
  return { ...schedule, [kind]: [...schedule[kind], copy] };
}

/** Updates only taxpayer-input fields and preserves computed backend outputs. */
export function updateDepreciationBlock(schedule: DepreciationSchedule, kind: 'dpm' | 'doa', id: string, patch: Partial<DepreciationBlockInput>): DepreciationSchedule {
  const rows = schedule[kind].map((row) => row.id === id ? { ...row, ...patch, id: row.id, additionDates: patch.additionDates ? [...patch.additionDates] : [...row.additionDates] } : { ...row, additionDates: [...row.additionDates] });
  return { ...schedule, [kind]: rows };
}

/** Applies the typed depreciation schedule to a canonical ReturnDraft immutably. */
export function withDepreciationSchedule(draft: ReturnDraft, depreciation: DepreciationSchedule): ReturnDraft {
  return { ...draft, itr3BusinessWorkspace: { ...draft.itr3BusinessWorkspace, core: { ...draft.itr3BusinessWorkspace.core, depreciation: depreciation as unknown as CanonicalJsonValue } } };
}
