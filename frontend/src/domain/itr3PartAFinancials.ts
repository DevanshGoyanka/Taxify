import type { CanonicalObject, CanonicalValue } from '../components/business/ITR3BusinessCoreManager';
import { ITR3_COVERAGE_MANIFEST, type ITR3CoverageEntry } from './itr3CoverageManifest';

/** User-facing classification for an official ITR-3 financial-statement field. */
export type ITR3FinancialFieldDisposition = 'editable-source' | 'backend-computed' | 'imported' | 'backend-only' | 'missing';

/** Official form grouping used by the dedicated Part A editors. */
export type ITR3FinancialFieldGroup =
  | 'official-credits' | 'expenses' | 'interest-depreciation' | 'tax-and-profit-after-tax'
  | 'appropriations' | 'presumptive-rows' | 'funds' | 'loans' | 'fixed-assets'
  | 'investments' | 'current-assets-liabilities' | 'provisions' | 'totals-and-no-books';

export interface ITR3FinancialField {
  path: string;
  label: string;
  schedule: 'PARTA_PL' | 'PARTA_BS';
  group: ITR3FinancialFieldGroup;
  disposition: ITR3FinancialFieldDisposition;
  type: string;
  required: boolean;
}

const mapDisposition = (entry: ITR3CoverageEntry): ITR3FinancialFieldDisposition => {
  if (entry.disposition === 'dedicated-input' || entry.disposition === 'generic-input') return 'editable-source';
  if (entry.disposition === 'computed') return 'backend-computed';
  if (entry.disposition === 'imported') return 'imported';
  if (entry.disposition === 'backend-only' || entry.disposition === 'metadata') return 'backend-only';
  return 'missing';
};

function groupFor(path: string, schedule: 'PARTA_PL' | 'PARTA_BS'): ITR3FinancialFieldGroup {
  if (schedule === 'PARTA_PL') {
    if (path.includes('CreditsToPL')) return 'official-credits';
    if (path.includes('Interest') || path.includes('Depreciation') || path.includes('Depreciation') || path.includes('PBIDTA')) return 'interest-depreciation';
    if (path.includes('TaxProvAppr.')) return path.includes('Prov') || path.includes('Tax') || path.includes('ProfitAfterTax') ? 'tax-and-profit-after-tax' : 'appropriations';
    if (path.includes('Persumptive') || path.includes('GoodsDtlsUs44AE') || path.includes('NatOfBus44')) return 'presumptive-rows';
    return 'expenses';
  }
  if (path.includes('FundSrc')) return 'funds';
  if (path.includes('Loan') || path.includes('Adv')) return 'loans';
  if (path.includes('FixedAsset')) return 'fixed-assets';
  if (path.includes('Invest')) return 'investments';
  if (path.includes('Provisions')) return 'provisions';
  if (path.includes('CurrAsset') || path.includes('CurrLiabilities')) return 'current-assets-liabilities';
  return 'totals-and-no-books';
}

const labelFor = (path: string): string => path.split('.').at(-1)?.replace(/([a-z])([A-Z])/g, '$1 $2') ?? path;

/** The complete official AY 2026-27 Part A field inventory (176 PL + 70 BS). */
export const ITR3_PARTA_FINANCIAL_FIELDS: readonly ITR3FinancialField[] = ITR3_COVERAGE_MANIFEST
  .filter((entry) => entry.schedule === 'PARTA_PL' || entry.schedule === 'PARTA_BS')
  .map((entry) => { const schedule = entry.schedule as 'PARTA_PL' | 'PARTA_BS'; return ({ path: entry.path, label: labelFor(entry.path), schedule, group: groupFor(entry.path, schedule), disposition: mapDisposition(entry), type: entry.type, required: entry.required }); });

export const ITR3_PARTA_PL_FIELDS = ITR3_PARTA_FINANCIAL_FIELDS.filter((field) => field.schedule === 'PARTA_PL');
export const ITR3_PARTA_BS_FIELDS = ITR3_PARTA_FINANCIAL_FIELDS.filter((field) => field.schedule === 'PARTA_BS');

/** Reads a dotted canonical workspace path; array markers resolve to the first row. */
export function readCanonicalPath(value: CanonicalObject, path: string): CanonicalValue | undefined {
  let current: CanonicalValue | undefined = value;
  for (const segment of path.split('.').slice(1)) {
    if (segment.endsWith('[]')) {
      const array: CanonicalValue | undefined = current && typeof current === 'object' && !Array.isArray(current) ? (current as CanonicalObject)[segment.slice(0, -2)] : undefined;
      current = Array.isArray(array) ? array[0] : undefined;
    } else {
      current = current && typeof current === 'object' && !Array.isArray(current) ? (current as CanonicalObject)[segment] : undefined;
    }
  }
  return current;
}

/** Immutably updates a scalar dotted canonical path and never mutates the caller's draft. */
export function updateCanonicalPath(value: CanonicalObject, path: string, next: CanonicalValue): CanonicalObject {
  const segments = path.split('.').slice(1);
  const result: CanonicalObject = structuredClone(value) as CanonicalObject;
  let cursor: CanonicalValue = result;
  segments.forEach((rawSegment, index) => {
    const isArray = rawSegment.endsWith('[]');
    const segment = isArray ? rawSegment.slice(0, -2) : rawSegment;
    if (!cursor || typeof cursor !== 'object' || Array.isArray(cursor)) return;
    const objectCursor = cursor as CanonicalObject;
    if (index === segments.length - 1) {
      objectCursor[segment] = next;
      return;
    }
    if (isArray) {
      const existing = objectCursor[segment];
      const rows: CanonicalValue[] = Array.isArray(existing) ? existing : [];
      if (!rows[0] || typeof rows[0] !== 'object' || Array.isArray(rows[0])) rows[0] = {};
      objectCursor[segment] = rows;
      cursor = rows[0];
    } else {
      const child = objectCursor[segment];
      objectCursor[segment] = child && typeof child === 'object' && !Array.isArray(child) ? child : {};
      cursor = objectCursor[segment];
    }
  });
  return result;
}

/** Returns whether an official field can be edited from this frontend workspace. */
export function isFinancialFieldEditable(field: ITR3FinancialField): boolean {
  return field.disposition === 'editable-source';
}
