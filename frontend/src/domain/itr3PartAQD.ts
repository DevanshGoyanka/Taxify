import type { ITR3BusinessWorkspace } from './returns/types';

/** Official AY 2026-27 PARTA_QD quantitative-detail row. */
export interface ITR3PartAQDRow {
  ItemName: string;
  UnitOfMeasure: string;
  OpeningStock: number;
  PurchaseQty: number;
  SaleQty: number;
  ClgStock: number;
  AnyShortExces: number;
  PrevYrConsum?: number;
  yldFinisProd?: number;
  PercentYld?: number;
  PrevyrManfact?: number;
}

/** Canonical PARTA_QD branches; arrays are owned by the backend serializer. */
export interface ITR3PartAQDWorkspace {
  TradingConcern?: ITR3PartAQDRow[];
  ManfactrConcern?: { RawMaterial?: ITR3PartAQDRow[]; FinishrByProd?: ITR3PartAQDRow[] };
}

const UNITS = new Set(['101','102','103','104','105','106','107','108','109','110','111','112','113','114','115','116','117','118','119','120','121','122','999']);
const nonNegative = (value: unknown): number => { const n = Number(value); return Number.isFinite(n) && n >= 0 ? Math.floor(n) : 0; };
const row = (value: unknown): ITR3PartAQDRow => { const source = value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}; return { ItemName: typeof source.ItemName === 'string' ? source.ItemName : '', UnitOfMeasure: typeof source.UnitOfMeasure === 'string' && UNITS.has(source.UnitOfMeasure) ? source.UnitOfMeasure : '', OpeningStock: nonNegative(source.OpeningStock), PurchaseQty: nonNegative(source.PurchaseQty), SaleQty: nonNegative(source.SaleQty), ClgStock: nonNegative(source.ClgStock), AnyShortExces: nonNegative(source.AnyShortExces), ...(source.PrevYrConsum !== undefined ? { PrevYrConsum: nonNegative(source.PrevYrConsum) } : {}), ...(source.yldFinisProd !== undefined ? { yldFinisProd: nonNegative(source.yldFinisProd) } : {}), ...(source.PercentYld !== undefined ? { PercentYld: nonNegative(source.PercentYld) } : {}), ...(source.PrevyrManfact !== undefined ? { PrevyrManfact: nonNegative(source.PrevyrManfact) } : {}) }; };
const rows = (value: unknown): ITR3PartAQDRow[] | undefined => Array.isArray(value) ? value.slice(0, 20).map(row) : undefined;

/** Reads PARTA_QD without inventing absent quantitative disclosures. */
export function readItr3PartAQD(workspace: ITR3BusinessWorkspace): ITR3PartAQDWorkspace {
  const source = workspace.auxiliary.PARTA_QD;
  if (!source || typeof source !== 'object' || Array.isArray(source)) return {};
  const value = source as Record<string, unknown>;
  const manufacturing = value.ManfactrConcern as Record<string, unknown> | undefined;
  return { TradingConcern: rows(value.TradingConcern), ManfactrConcern: manufacturing && typeof manufacturing === 'object' ? { RawMaterial: rows(manufacturing.RawMaterial), FinishrByProd: rows(manufacturing.FinishrByProd) } : undefined };
}

/** Updates one PARTA_QD scalar immutably; structural paths and unknown fields are rejected. */
export function updateItr3PartAQD(workspace: ITR3BusinessWorkspace, branch: 'TradingConcern' | 'RawMaterial' | 'FinishrByProd', index: number, field: keyof ITR3PartAQDRow, value: unknown): ITR3BusinessWorkspace {
  if (!Number.isInteger(index) || index < 0 || !['ItemName','UnitOfMeasure','OpeningStock','PurchaseQty','SaleQty','ClgStock','AnyShortExces','PrevYrConsum','yldFinisProd','PercentYld','PrevyrManfact'].includes(field)) return workspace;
  const current = readItr3PartAQD(workspace); const list = branchRows(current, branch);
  if (index >= list.length) return workspace;
  const nextRows = list.map((item, rowIndex) => rowIndex === index ? { ...item, [field]: field === 'ItemName' ? String(value ?? '') : field === 'UnitOfMeasure' ? (UNITS.has(String(value)) ? String(value) : '') : nonNegative(value) } : item);
  return writeBranchRows(workspace, current, branch, nextRows);
}

const EMPTY_QD_ROW: ITR3PartAQDRow = { ItemName: '', UnitOfMeasure: '', OpeningStock: 0, PurchaseQty: 0, SaleQty: 0, ClgStock: 0, AnyShortExces: 0 };
const MAX_QD_ROWS = 20;

function branchRows(data: ITR3PartAQDWorkspace, branch: 'TradingConcern' | 'RawMaterial' | 'FinishrByProd'): ITR3PartAQDRow[] {
  return branch === 'TradingConcern' ? data.TradingConcern ?? [] : branch === 'RawMaterial' ? data.ManfactrConcern?.RawMaterial ?? [] : data.ManfactrConcern?.FinishrByProd ?? [];
}

function writeBranchRows(workspace: ITR3BusinessWorkspace, current: ITR3PartAQDWorkspace, branch: 'TradingConcern' | 'RawMaterial' | 'FinishrByProd', rowsNext: ITR3PartAQDRow[]): ITR3BusinessWorkspace {
  const next: ITR3PartAQDWorkspace = { ...current, ...(branch === 'TradingConcern' ? { TradingConcern: rowsNext } : { ManfactrConcern: { ...(current.ManfactrConcern ?? {}), ...(branch === 'RawMaterial' ? { RawMaterial: rowsNext } : { FinishrByProd: rowsNext }) } }) };
  return { ...workspace, auxiliary: { ...workspace.auxiliary, PARTA_QD: next as never } };
}

/** Appends a blank quantitative-detail row to a branch (official schema caps every QuantitDet array at 20 rows). */
export function addItr3PartAQDRow(workspace: ITR3BusinessWorkspace, branch: 'TradingConcern' | 'RawMaterial' | 'FinishrByProd'): ITR3BusinessWorkspace {
  const current = readItr3PartAQD(workspace); const list = branchRows(current, branch);
  if (list.length >= MAX_QD_ROWS) return workspace;
  return writeBranchRows(workspace, current, branch, [...list, { ...EMPTY_QD_ROW }]);
}

/** Removes one quantitative-detail row from a branch. */
export function removeItr3PartAQDRow(workspace: ITR3BusinessWorkspace, branch: 'TradingConcern' | 'RawMaterial' | 'FinishrByProd', index: number): ITR3BusinessWorkspace {
  const current = readItr3PartAQD(workspace); const list = branchRows(current, branch);
  if (!Number.isInteger(index) || index < 0 || index >= list.length) return workspace;
  return writeBranchRows(workspace, current, branch, list.filter((_, rowIndex) => rowIndex !== index));
}
