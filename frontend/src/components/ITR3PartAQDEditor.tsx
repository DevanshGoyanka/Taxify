import React from 'react';
import { readItr3PartAQD, updateItr3PartAQD, type ITR3PartAQDRow } from '../domain/itr3PartAQD';
import type { ITR3BusinessWorkspace } from '../domain/returns/types';

interface Props { workspace: ITR3BusinessWorkspace; onChange: (workspace: ITR3BusinessWorkspace) => void; }
const branches: readonly ['TradingConcern' | 'RawMaterial' | 'FinishrByProd', string][] = [['TradingConcern','Trading concern'],['RawMaterial','Raw materials'],['FinishrByProd','Finished products / by-products']];
const fields: readonly (keyof ITR3PartAQDRow)[] = ['ItemName','UnitOfMeasure','OpeningStock','PurchaseQty','SaleQty','ClgStock','AnyShortExces','PrevYrConsum','yldFinisProd','PercentYld','PrevyrManfact'];
const numeric = new Set<keyof ITR3PartAQDRow>(fields.slice(2));
function listFor(data: ReturnType<typeof readItr3PartAQD>, branch: string): ITR3PartAQDRow[] { return branch === 'TradingConcern' ? data.TradingConcern ?? [] : branch === 'RawMaterial' ? data.ManfactrConcern?.RawMaterial ?? [] : data.ManfactrConcern?.FinishrByProd ?? []; }
/** Dedicated official PARTA_QD editor; only scalar source facts are editable. */
export default function ITR3PartAQDEditor({ workspace, onChange }: Props): React.JSX.Element {
  const data = readItr3PartAQD(workspace);
  const change = (branch: 'TradingConcern' | 'RawMaterial' | 'FinishrByProd', index: number, field: keyof ITR3PartAQDRow, value: string): void => onChange(updateItr3PartAQD(workspace, branch, index, field, value));
  return <section aria-label="PARTA_QD dedicated editor"><h3>Part A-QD — Quantitative details</h3><p>Enter source quantities only. The official QuantitDet arrays and all JSON nesting are serialized by the backend.</p>{branches.map(([branch, label]) => <div key={branch} style={{ marginBottom: 16, padding: 12, border: '1px solid var(--border)', borderRadius: 6 }}><h4>{label}</h4>{listFor(data, branch).map((item, index) => <div key={index} style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, marginBottom: 10 }}>{fields.map((field) => <label key={field}><span>{String(field)}</span><input aria-label={`${branch} ${index + 1} ${String(field)}`} type={numeric.has(field) ? 'number' : 'text'} min={numeric.has(field) ? 0 : undefined} value={item[field] ?? ''} onChange={(event) => change(branch, index, field, event.target.value)} /></label>)}</div>)}</div>)}</section>;
}
