import type { ReturnDraft, BroughtForwardLosses, Money } from './types';
import { ITR3_COVERAGE_MANIFEST, type ITR3CoverageEntry } from '../itr3CoverageManifest';

/** Official income heads represented by Schedule CYLA/BFLA. */
export type ITR3LossIncomeHead = 'Salary' | 'House property' | 'Business or profession' | 'Short-term capital gains' | 'Long-term capital gains' | 'Other sources';

/** Canonical editable B/F loss field. These values seed the official schedules; set-off is backend-owned. */
export interface ITR3LossInputField {
  readonly key: keyof BroughtForwardLosses;
  readonly path: string;
  readonly label: string;
  readonly head: ITR3LossIncomeHead;
}

/** Backend-computed official CYLA/BFLA field projection. */
export interface ITR3LossComputedField {
  readonly path: string;
  readonly label: string;
  readonly head: ITR3LossIncomeHead;
  readonly value: Money;
}

/** Official user-entered loss inputs supported by the canonical draft. */
export const ITR3_LOSS_INPUT_FIELDS: readonly ITR3LossInputField[] = [
  { key: 'bfLossHP', path: 'ScheduleCYLA.HP.IncCYLA.IncOfCurYrUnderThatHead', label: 'House property loss brought forward', head: 'House property' },
  { key: 'bfLossBusiness', path: 'ScheduleCYLA.BusProfExclSpecProf.IncCYLA.IncOfCurYrUnderThatHead', label: 'Business/profession loss brought forward', head: 'Business or profession' },
  { key: 'bfLossSTCG', path: 'ScheduleCYLA.STCG20Per.IncCYLA.IncOfCurYrUnderThatHead', label: 'Short-term capital loss brought forward', head: 'Short-term capital gains' },
  { key: 'bfLossLTCG', path: 'ScheduleCYLA.LTCG12_5Per.IncCYLA.IncOfCurYrUnderThatHead', label: 'Long-term capital loss brought forward', head: 'Long-term capital gains' },
  { key: 'bfLossSpeculation', path: 'ScheduleCYLA.SpeculativeInc.IncCYLA.IncOfCurYrUnderThatHead', label: 'Speculation loss brought forward', head: 'Business or profession' },
];

/** Returns all official CYLA/BFLA fields and their explicit disposition. */
export function itr3LossCoverage(): readonly ITR3CoverageEntry[] {
  return ITR3_COVERAGE_MANIFEST.filter((entry) => entry.schedule === 'ScheduleCYLA' || entry.schedule === 'ScheduleBFLA');
}

/** Safely updates one editable brought-forward loss amount. */
export function updateItr3LossInput(losses: BroughtForwardLosses, key: keyof BroughtForwardLosses, value: unknown): BroughtForwardLosses {
  const numeric = typeof value === 'number' ? value : Number(value);
  return { ...losses, [key]: Number.isFinite(numeric) && numeric >= 0 ? numeric : 0 };
}

/** Applies one editable loss input to a detached canonical return draft. */
export function applyItr3LossInput(draft: ReturnDraft, key: keyof BroughtForwardLosses, value: unknown): ReturnDraft {
  return { ...draft, lossesBroughtForward: updateItr3LossInput(draft.lossesBroughtForward, key, value) };
}
