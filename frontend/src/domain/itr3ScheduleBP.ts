import { ITR3_COVERAGE_MANIFEST, type ITR3CoverageEntry } from './itr3CoverageManifest';
import type { CanonicalObject, CanonicalValue } from '../components/business/ITR3BusinessCoreManager';

/** Official Schedule BP field disposition. */
export type ScheduleBPDisposition = 'editable-source' | 'backend-computed' | 'imported' | 'backend-only';

/** Official Schedule BP UI grouping. */
export type ScheduleBPGroup = 'p-and-l-bridge' | 'depreciation' | 'disallowances-add-backs' | 'exempt-other-head-income' | 'icds' | 'presumptive-income' | 'speculative-specified-business' | 'current-year-setoff' | 'final-business-totals';

/** A field in the AY 2026-27 official Schedule BP model. */
export interface ScheduleBPField {
  path: string;
  fieldName: string;
  label: string;
  group: ScheduleBPGroup;
  disposition: ScheduleBPDisposition;
  type: string;
  required: boolean;
  array: boolean;
  official: ITR3CoverageEntry;
}

const COMPUTED_TERMINALS = new Set([
  'TotDeemedProfitBusUs', 'TotDeprAllowITAct', 'TotExmpInc', 'TotExpDebPL',
  'TotProfitFrmActCvrd', 'TotLossSetOffOnBus', 'TotIncomeOfBusProf',
  'TotIncomeOfSpecBus', 'TotIncomeOfSpecifiedBus', 'BalancePLOthThanSpecBus',
  'AdjustedPLOthThanSpecBus', 'AdjustPLAfterDeprOthSpecInc', 'TotAfterAddToPLDeprOthSpecInc',
  'TotDeductionAmts', 'TotProfitLossOfBusiness', 'IncOfCurYrAfterSetOff',
  'LossRemainSetOffOnBus', 'LossSetOffOnBusLoss', 'BusLossSetoff',
  'IncOfCurYrUnderThatHead', 'ProfitLossOfSpecBus', 'ProfitLossOfSpecifiedBus',
  'TotalProfitFrmActCvrd', 'TotExempIncPL', 'TotIncFromBusProf',
]);
const COMPUTED_PARTS = ['.Tot', '.Total', 'BalancePL', 'AdjustedPL', 'AfterSetOff', 'RemainSetOff', 'LossSetOffOnBus'];

function terminal(path: string): string {
  return path.slice(path.lastIndexOf('.') + 1);
}

function groupFor(path: string): ScheduleBPGroup {
  if (path.includes('BusSetoffCurrYr')) return 'current-year-setoff';
  if (path.includes('Speculative') || path.includes('Specified')) return 'speculative-specified-business';
  if (path.includes('DeemedProfit') || path.includes('ProfitLossInclRefrdSec') || path.includes('44AD') || path.includes('44ADA') || path.includes('44AE')) return 'presumptive-income';
  if (path.includes('ICDS') || path.includes('IncProfDecLossAcc')) return 'icds';
  if (path.includes('Depreciation') || path.includes('Depr')) return 'depreciation';
  if (path.includes('Exemp') || path.includes('OthHead') || path.includes('IncCredPL')) return 'exempt-other-head-income';
  if (path.includes('Disallow') || path.includes('Disall') || path.includes('DebPL') || path.includes('DeemInc')) return 'disallowances-add-backs';
  if (path.includes('Tot') || path.includes('Balance') || path.includes('IncomeOf')) return 'final-business-totals';
  return 'p-and-l-bridge';
}

function dispositionFor(entry: ITR3CoverageEntry): ScheduleBPDisposition {
  const name = terminal(entry.path);
  if (entry.array || entry.object) return 'backend-only';
  if (COMPUTED_TERMINALS.has(name) || COMPUTED_PARTS.some((part) => name.includes(part))) return 'backend-computed';
  return 'editable-source';
}

function labelFor(entry: ITR3CoverageEntry): string {
  return entry.fieldName.replace(/([a-z])([A-Z])/g, '$1 $2').replace(/_/g, ' ').replace(/^./, (value) => value.toUpperCase());
}

/** Complete official Schedule BP field catalog, with one disposition per path. */
export const SCHEDULE_BP_FIELDS: readonly ScheduleBPField[] = ITR3_COVERAGE_MANIFEST
  .filter((entry) => entry.schedule === 'ITR3ScheduleBP')
  .map((entry) => ({ path: entry.path, fieldName: entry.fieldName, label: labelFor(entry), group: groupFor(entry.path), disposition: dispositionFor(entry), type: entry.type, required: entry.required, array: entry.array, official: entry }));

/** The official Schedule BP path count for AY 2026-27. */
export const SCHEDULE_BP_PATH_COUNT = 131 as const;

/** Fields that may be edited by the user; computed and backend-only paths are excluded. */
export const SCHEDULE_BP_EDITABLE_FIELDS = SCHEDULE_BP_FIELDS.filter((field) => field.disposition === 'editable-source');

/** Fields whose values are owned by backend computation and must never be overwritten by UI input. */
export const SCHEDULE_BP_COMPUTED_FIELDS = SCHEDULE_BP_FIELDS.filter((field) => field.disposition === 'backend-computed');

/** Read a nested canonical Schedule BP value. */
export function readScheduleBPValue(source: CanonicalObject | undefined, path: string): CanonicalValue | undefined {
  if (!source) return undefined;
  let current: CanonicalValue = source;
  for (const part of path.replace(/^ITR3ScheduleBP\./, '').split('.')) {
    if (!current || typeof current !== 'object' || Array.isArray(current)) return undefined;
    current = (current as CanonicalObject)[part];
  }
  return current;
}

/** Update one editable Schedule BP source, refusing computed/backend-owned paths. */
export function updateScheduleBPValue(source: CanonicalObject, path: string, value: CanonicalValue): CanonicalObject {
  const field = SCHEDULE_BP_FIELDS.find((candidate) => candidate.path === path);
  if (!field || field.disposition !== 'editable-source') return source;
  const parts = path.replace(/^ITR3ScheduleBP\./, '').split('.');
  const update = (node: CanonicalObject, index: number): CanonicalObject => {
    const key = parts[index];
    if (index === parts.length - 1) return { ...node, [key]: value };
    const child = node[key];
    const childObject = child && typeof child === 'object' && !Array.isArray(child) ? child as CanonicalObject : {};
    return { ...node, [key]: update(childObject, index + 1) };
  };
  return update(source, 0);
}

/** Preserve backend-owned values while applying an imported Schedule BP object. */
export function mergeScheduleBPBackendValues(current: CanonicalObject, incoming: CanonicalObject): CanonicalObject {
  let result = current;
  for (const field of SCHEDULE_BP_FIELDS) {
    const incomingValue = readScheduleBPValue(incoming, field.path);
    if (incomingValue === undefined) continue;
    if (field.disposition === 'backend-computed' || field.disposition === 'backend-only') result = updateUnsafe(result, field.path, incomingValue);
  }
  return result;
}

function updateUnsafe(source: CanonicalObject, path: string, value: CanonicalValue): CanonicalObject {
  const parts = path.replace(/^ITR3ScheduleBP\./, '').split('.');
  const update = (node: CanonicalObject, index: number): CanonicalObject => index === parts.length - 1 ? { ...node, [parts[index]]: value } : { ...node, [parts[index]]: update((node[parts[index]] as CanonicalObject) ?? {}, index + 1) };
  return update(source, 0);
}
