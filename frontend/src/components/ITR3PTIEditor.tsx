import React from 'react';
import type { PassThroughIncomeEntry, PTIIncomeHead } from '../domain/returns/types';
import { aggregateITR3PTI, createITR3PTIEntry, ITR3_PTI_SECTIONS, validateITR3PTIEntry } from '../domain/itr3Pti';

export interface ITR3PTIEditorProps { entries: PassThroughIncomeEntry[]; onChange: (entries: PassThroughIncomeEntry[]) => void; }
const heads: readonly PTIIncomeHead[] = ['HP', 'STCG', 'LTCG', 'OS'];
const uid = (): string => globalThis.crypto?.randomUUID?.() ?? `pti-${Date.now()}`;

/** Dedicated official ITR-3 Schedule PTI editor. */
export function ITR3PTIEditor({ entries, onChange }: ITR3PTIEditorProps): React.ReactElement {
  const totals = aggregateITR3PTI(entries);
  const update = (id: string, patch: Partial<PassThroughIncomeEntry>): void => onChange(entries.map((entry) => entry.id === id ? { ...entry, ...patch } : entry));
  return <div style={{ display: 'grid', gap: 16 }}>
    <header><h2>ITR-3 Schedule PTI — Pass-through income</h2><p style={muted}>Enter only official business trust / investment fund facts. Tax, exempt components, and aggregated totals are computed by the backend.</p></header>
    <section style={sectionStyle}><div style={headingStyle}><h3>PTI entities and income heads</h3><button type="button" onClick={() => onChange([...entries, createITR3PTIEntry(uid())])}>＋ Add entity</button></div>
      {entries.map((entry, index) => { const errors = validateITR3PTIEntry(entry); return <div key={entry.id} style={rowStyle}><strong>{index + 1}</strong><div style={gridStyle}>
        <label>Entity / fund type<select value={entry.investmentType} onChange={(e) => update(entry.id, { investmentType: e.target.value as PassThroughIncomeEntry['investmentType'] })}><option value="A">Business trust (115UA)</option><option value="B">Investment fund (115UB)</option><option value="C">Other trust (115U)</option></select></label>
        <label>Trust / fund name<input value={entry.entityName} onChange={(e) => update(entry.id, { entityName: e.target.value })} /></label>
        <label>Trust / fund PAN<input value={entry.entityPAN} maxLength={10} onChange={(e) => update(entry.id, { entityPAN: e.target.value.toUpperCase() })} /></label>
        <label>Income head<select value={entry.incomeHead} onChange={(e) => update(entry.id, { incomeHead: e.target.value as PTIIncomeHead })}>{heads.map((head) => <option key={head}>{head}</option>)}</select></label>
        <label>Applicable section<select value={entry.section} onChange={(e) => update(entry.id, { section: e.target.value, investmentType: e.target.value === '115UA' ? 'A' : e.target.value === '115UB' ? 'B' : 'C' })}>{ITR3_PTI_SECTIONS.map((section) => <option key={section}>{section}</option>)}</select></label>
        <label>Income amount<input type="number" min={0} value={entry.incomeAmount} onChange={(e) => update(entry.id, { incomeAmount: Math.max(0, Number(e.target.value) || 0) })} /></label>
        <label>TDS credit<input type="number" min={0} value={entry.tdsCredit} onChange={(e) => update(entry.id, { tdsCredit: Math.max(0, Number(e.target.value) || 0) })} /></label>
      </div><small style={{ color: errors.length ? '#b42318' : '#667085' }}>{errors.join(' ') || 'Ready for backend computation.'}</small><button type="button" onClick={() => onChange(entries.filter((item) => item.id !== entry.id))}>Remove</button></div>; })}
      {!entries.length && <p style={muted}>No PTI entities.</p>}
    </section>
    <section style={sectionStyle}><h3>Computed PTI totals (read-only)</h3><div style={gridStyle}>{heads.map((head) => <label key={head}>{head} total<input readOnly value={totals[head]} /></label>)}</div></section>
  </div>;
}
const sectionStyle: React.CSSProperties = { border: '1px solid var(--border, #eaecf0)', borderRadius: 8, padding: 16, display: 'grid', gap: 12 };
const headingStyle: React.CSSProperties = { display: 'flex', justifyContent: 'space-between', alignItems: 'center' };
const rowStyle: React.CSSProperties = { border: '1px solid #eaecf0', borderRadius: 6, padding: 12, display: 'grid', gap: 10 };
const gridStyle: React.CSSProperties = { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: 10 };
const muted: React.CSSProperties = { color: 'var(--text-muted, #667085)', margin: 0 };
export default ITR3PTIEditor;
