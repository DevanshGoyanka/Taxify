import React from 'react';
import type { ClubbedIncomeEntry, ScheduleSIEntry } from '../domain/returns/types';
import {
  ITR3_SI_SECTIONS, ITR3_SPI_HEADS, validateITR3SIEntry, validateITR3SPIEntry,
  updateITR3SIEntry, updateITR3SPIEntry,
} from '../domain/itr3SpecialSchedules';

export interface ITR3SpecialSchedulesEditorProps {
  scheduleSIEntries: ScheduleSIEntry[];
  onScheduleSIEntriesChange: (entries: ScheduleSIEntry[]) => void;
  clubbedIncome: ClubbedIncomeEntry[];
  onClubbedIncomeChange: (entries: ClubbedIncomeEntry[]) => void;
  computed?: ReadonlyArray<{ taxableIncome: number; taxAmount: number | null }>;
}

const uid = (prefix: string): string => globalThis.crypto?.randomUUID?.() ?? `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2)}`;
const money = (value: unknown): number => Math.max(0, Number.isFinite(Number(value)) ? Number(value) : 0);

/** Dedicated ITR-3 editor for official Schedule SI and Schedule SPI. */
export function ITR3SpecialSchedulesEditor(props: ITR3SpecialSchedulesEditorProps): React.ReactElement {
  const addSI = (): void => props.onScheduleSIEntriesChange([...props.scheduleSIEntries, { id: uid('si'), section: '115BB', description: '', grossIncome: 0, deductions: 0, taxRatePct: null }]);
  const addSPI = (): void => props.onClubbedIncomeChange([...props.clubbedIncome, { id: uid('spi'), specifiedPersonName: '', pan: '', relationship: '', amountIncluded: 0, headOfIncome: 'OS' }]);
  return <div style={{ display: 'grid', gap: 16 }}>
    <header><h2>ITR-3 Schedule SI &amp; SPI</h2><p style={muted}>Enter official source facts only. Taxable income, rates, and tax are backend-computed and read-only.</p></header>
    <section style={sectionStyle}><div style={headingStyle}><h3>Schedule SI — Special-rate income</h3><button type="button" onClick={addSI}>＋ Add</button></div>
      {props.scheduleSIEntries.map((entry, index) => { const errors = validateITR3SIEntry(entry); return <div style={rowStyle} key={entry.id}><strong>{index + 1}</strong><div style={gridStyle}>
        <label>Section<select value={entry.section} onChange={(event) => props.onScheduleSIEntriesChange(props.scheduleSIEntries.map((item) => item.id === entry.id ? updateITR3SIEntry(item, { section: event.target.value as ScheduleSIEntry['section'] }) : item))}>{ITR3_SI_SECTIONS.map((section) => <option key={section}>{section}</option>)}</select></label>
        <label>Description<input value={entry.description} onChange={(event) => props.onScheduleSIEntriesChange(props.scheduleSIEntries.map((item) => item.id === entry.id ? updateITR3SIEntry(item, { description: event.target.value }) : item))} /></label>
        <label>Gross income<input type="number" min={0} value={money(entry.grossIncome)} onChange={(event) => props.onScheduleSIEntriesChange(props.scheduleSIEntries.map((item) => item.id === entry.id ? updateITR3SIEntry(item, { grossIncome: money(event.target.value) }) : item))} /></label>
        <label>Deductions<input type="number" min={0} value={money(entry.deductions)} onChange={(event) => props.onScheduleSIEntriesChange(props.scheduleSIEntries.map((item) => item.id === entry.id ? updateITR3SIEntry(item, { deductions: money(event.target.value) }) : item))} /></label>
        <label>Taxable income (computed)<input readOnly value={props.computed?.[index]?.taxableIncome ?? 'Backend computed'} /></label><label>Tax (computed)<input readOnly value={props.computed?.[index]?.taxAmount ?? 'Backend computed'} /></label>
      </div><small style={{ color: errors.length ? '#b42318' : '#667085' }}>{errors.join(' ') || 'Backend computes rate and tax.'}</small><button type="button" onClick={() => props.onScheduleSIEntriesChange(props.scheduleSIEntries.filter((item) => item.id !== entry.id))}>Remove</button></div>; })}
      {!props.scheduleSIEntries.length && <p style={muted}>No Schedule SI entries.</p>}
    </section>
    <section style={sectionStyle}><div style={headingStyle}><h3>Schedule SPI — Specified-person income</h3><button type="button" onClick={addSPI}>＋ Add</button></div>
      {props.clubbedIncome.map((entry, index) => { const errors = validateITR3SPIEntry(entry); return <div style={rowStyle} key={entry.id}><strong>{index + 1}</strong><div style={gridStyle}>
        {(['specifiedPersonName', 'pan', 'relationship'] as const).map((key) => <label key={key}>{key === 'specifiedPersonName' ? 'Specified person name' : key.toUpperCase()}<input value={entry[key]} onChange={(event) => props.onClubbedIncomeChange(props.clubbedIncome.map((item) => item.id === entry.id ? updateITR3SPIEntry(item, { [key]: event.target.value }) : item))} /></label>)}
        <label>Income included<input type="number" min={0} value={money(entry.amountIncluded)} onChange={(event) => props.onClubbedIncomeChange(props.clubbedIncome.map((item) => item.id === entry.id ? updateITR3SPIEntry(item, { amountIncluded: money(event.target.value) }) : item))} /></label>
        <label>Head of income<select value={entry.headOfIncome} onChange={(event) => props.onClubbedIncomeChange(props.clubbedIncome.map((item) => item.id === entry.id ? updateITR3SPIEntry(item, { headOfIncome: event.target.value as ClubbedIncomeEntry['headOfIncome'] }) : item))}>{ITR3_SPI_HEADS.map((head) => <option key={head}>{head}</option>)}</select></label>
      </div><small style={{ color: errors.length ? '#b42318' : '#667085' }}>{errors.join(' ') || 'Ready for backend computation.'}</small><button type="button" onClick={() => props.onClubbedIncomeChange(props.clubbedIncome.filter((item) => item.id !== entry.id))}>Remove</button></div>; })}
      {!props.clubbedIncome.length && <p style={muted}>No Schedule SPI entries.</p>}
    </section>
  </div>;
}
const sectionStyle: React.CSSProperties = { border: '1px solid var(--border, #eaecf0)', borderRadius: 8, padding: 16, display: 'grid', gap: 12 };
const headingStyle: React.CSSProperties = { display: 'flex', justifyContent: 'space-between', alignItems: 'center' };
const rowStyle: React.CSSProperties = { border: '1px solid #eaecf0', borderRadius: 6, padding: 12, display: 'grid', gap: 10 };
const gridStyle: React.CSSProperties = { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: 10 };
const muted: React.CSSProperties = { color: 'var(--text-muted, #667085)', margin: 0 };
export default ITR3SpecialSchedulesEditor;
