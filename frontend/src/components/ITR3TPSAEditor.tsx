import React from 'react';
import type { ITR3TPSA } from '../domain/itr3TPSA';
import { emptyITR3TPSADeposit, updateITR3TPSADeposit, validateITR3TPSADeposit } from '../domain/itr3TPSA';

export interface ITR3TPSAEditorProps { value: ITR3TPSA; computed?: Readonly<Record<string, number | null>>; onChange: (value: ITR3TPSA) => void; }
const num = (value: string): number => Number.isFinite(Number(value)) && Number(value) >= 0 ? Math.trunc(Number(value)) : 0;

/** Dedicated Schedule TPSA editor for supporting tax-deposit references. */
export default function ITR3TPSAEditor({ value, computed, onChange }: ITR3TPSAEditorProps): React.ReactElement {
  const update = (id: string, patch: Parameters<typeof updateITR3TPSADeposit>[1]): void => onChange({ details: value.details.map((row) => row.id === id ? updateITR3TPSADeposit(row, patch) : row) });
  return <div style={shell}><h2>Schedule TPSA — secondary adjustment</h2><p>Enter only supporting tax-deposit facts. Primary adjustment, additional tax, surcharge, cess, totals, and net payable are computed by the backend and cannot be edited.</p>
    <section style={section}><h3>Computed Schedule TPSA values</h3><div style={computedGrid}>{['AmtPrimaryAdjUs92CE_2A','AdditionalIncTax18PercAbove','Surcharge12Perc','HealthEducationCess','TotalAdditionalTax','TaxesPaid','NetTaxPayable','TotalAmountDeposited'].map((key) => <label key={key}>{key}<input readOnly value={computed?.[key] ?? 'Backend computed'} /></label>)}</div></section>
    <section style={section}><div style={heading}><h3>Taxes paid — DtlsTaxesPaid</h3><button type="button" onClick={() => onChange({ details: [...value.details, emptyITR3TPSADeposit(`tpsa-${Date.now()}`)] })}>＋ Add deposit</button></div>
      {value.details.map((row, index) => { const errors = validateITR3TPSADeposit(row); return <div style={rowStyle} key={row.id}><strong>{index + 1}</strong><div style={grid}>{field('BSRCode', row.bsrCode, (v) => update(row.id, { bsrCode: v.toUpperCase() } ))}{field('BankBranchName', row.bankBranchName, (v) => update(row.id, { bankBranchName: v }))}{field('DateDep', row.dateDep, (v) => update(row.id, { dateDep: v }), 'date')}{field('SrlNoOfChaln', row.srlNoOfChaln, (v) => update(row.id, { srlNoOfChaln: num(v) }), 'number')}{field('Amount', row.amount, (v) => update(row.id, { amount: num(v) }), 'number')}<button type="button" onClick={() => onChange({ details: value.details.filter((item) => item.id !== row.id) })}>Remove</button></div><small style={{ color: errors.length ? '#b42318' : '#667085' }}>{errors.join(' ') || 'Ready for backend mapping.'}</small></div>; })}
      {!value.details.length && <p>No deposit references entered; no related-party or transfer-pricing values are fabricated.</p>}
    </section></div>;
}
function field(label: string, value: string | number, onChange: (value: string) => void, type = 'text'): React.ReactElement { return <label>{label}<input type={type} value={value} min={type === 'number' ? 0 : undefined} onChange={(event) => onChange(event.target.value)} /></label>; }
const shell: React.CSSProperties = { display: 'grid', gap: 16 };
const section: React.CSSProperties = { border: '1px solid #eaecf0', borderRadius: 8, padding: 16, display: 'grid', gap: 12 };
const heading: React.CSSProperties = { display: 'flex', justifyContent: 'space-between', alignItems: 'center' };
const grid: React.CSSProperties = { display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(170px,1fr))', gap: 10, alignItems: 'end' };
const computedGrid: React.CSSProperties = { ...grid, gridTemplateColumns: 'repeat(auto-fit,minmax(210px,1fr))' };
const rowStyle: React.CSSProperties = { border: '1px solid #eaecf0', borderRadius: 6, padding: 12, display: 'grid', gap: 10 };
