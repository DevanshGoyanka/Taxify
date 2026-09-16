import React from 'react';
import type { ForeignSourceIncomeEntry, ForeignTaxReliefEntry } from '../domain/returns/types';
import { computedRelief, foreignIncomeTotal, foreignReliefTotals, validateForeignSourceIncome, validateForeignTaxRelief } from '../domain/itr3ForeignSchedules';

export interface ITR3ForeignSchedulesEditorProps {
  foreignSourceIncome: ForeignSourceIncomeEntry[];
  onForeignSourceIncomeChange: (entries: ForeignSourceIncomeEntry[]) => void;
  foreignTaxRelief: ForeignTaxReliefEntry[];
  onForeignTaxReliefChange: (entries: ForeignTaxReliefEntry[]) => void;
}

const uid = (prefix: string): string => globalThis.crypto?.randomUUID?.() ?? `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2)}`;
const money = (value: unknown): number => Math.max(0, Number.isFinite(Number(value)) ? Number(value) : 0);
const sections = ['90', '90A', '91'] as const;
const field = (label: string, value: string | number, onChange: (value: string) => void, numeric = false): React.ReactElement => <label>{label}<input type={numeric ? 'number' : 'text'} min={numeric ? 0 : undefined} value={value} onChange={(event) => onChange(event.target.value)} /></label>;

/** Dedicated ITR-3 editor for official Schedule FSI and Schedule TR1. */
export function ITR3ForeignSchedulesEditor(props: ITR3ForeignSchedulesEditorProps): React.ReactElement {
  const updateFsi = (id: string, patch: Partial<ForeignSourceIncomeEntry>): void => props.onForeignSourceIncomeChange(props.foreignSourceIncome.map((item) => item.id === id ? { ...item, ...patch } : item));
  const updateTr = (id: string, patch: Partial<ForeignTaxReliefEntry>): void => props.onForeignTaxReliefChange(props.foreignTaxRelief.map((item) => item.id === id ? { ...item, ...patch } : item));
  const totals = foreignReliefTotals(props.foreignTaxRelief);
  const newFsi = (): ForeignSourceIncomeEntry => ({ id: uid('fsi'), countryName: '', countryCode: '', taxIdentificationNo: '', salaryIncome: 0, hpIncome: 0, businessIncome: 0, cgIncome: 0, osIncome: 0, taxPaidOutsideIndia: 0, taxPayableInIndia: 0, reliefSection: '90', treatyArticle: '' });
  const newTr = (): ForeignTaxReliefEntry => ({ id: uid('tr1'), countryCode: '', taxIdentificationNo: '', incomeIncludedInThisReturn: 0, taxPaidOutsideIndia: 0, indianTaxPayable: 0, reliefClaimed: 0, reliefSection: '90', form67Filed: false, form10FFiled: false });
  return <div style={{ display: 'grid', gap: 16 }}>
    <header><h2>ITR-3 Schedule FSI &amp; TR1</h2><p style={muted}>Enter country-wise source facts and statutory documentation. Totals and relief calculations are backend-owned.</p></header>
    <section style={sectionStyle}><div style={headingStyle}><h3>Schedule FSI — Foreign Source Income</h3><button type="button" onClick={() => props.onForeignSourceIncomeChange([...props.foreignSourceIncome, newFsi()])}>＋ Add country</button></div>
      {props.foreignSourceIncome.map((entry, index) => { const errors = validateForeignSourceIncome(entry); return <div style={rowStyle} key={entry.id}><strong>{index + 1}</strong><div style={gridStyle}>
        {field('Country name', entry.countryName, (value) => updateFsi(entry.id, { countryName: value }))}{field('Country code', entry.countryCode, (value) => updateFsi(entry.id, { countryCode: value.toUpperCase() }))}{field('Foreign TIN', entry.taxIdentificationNo, (value) => updateFsi(entry.id, { taxIdentificationNo: value }))}{field('Treaty article', entry.treatyArticle, (value) => updateFsi(entry.id, { treatyArticle: value }))}
        {field('Salary income', entry.salaryIncome, (value) => updateFsi(entry.id, { salaryIncome: money(value) }), true)}{field('House-property income', entry.hpIncome, (value) => updateFsi(entry.id, { hpIncome: money(value) }), true)}{field('Business income', entry.businessIncome, (value) => updateFsi(entry.id, { businessIncome: money(value) }), true)}{field('Capital gains', entry.cgIncome, (value) => updateFsi(entry.id, { cgIncome: money(value) }), true)}{field('Other-source income', entry.osIncome, (value) => updateFsi(entry.id, { osIncome: money(value) }), true)}
        {field('Foreign tax paid', entry.taxPaidOutsideIndia, (value) => updateFsi(entry.id, { taxPaidOutsideIndia: money(value) }), true)}{field('Indian tax payable', entry.taxPayableInIndia, (value) => updateFsi(entry.id, { taxPayableInIndia: money(value) }), true)}
        <label>Relief section<select value={entry.reliefSection} onChange={(event) => updateFsi(entry.id, { reliefSection: event.target.value as ForeignSourceIncomeEntry['reliefSection'] })}>{sections.map((section) => <option key={section} value={section}>Section {section}</option>)}</select></label>
        <label>Total income (computed)<input readOnly value={foreignIncomeTotal(entry)} /></label><label>Relief (computed)<input readOnly value={computedRelief(entry.taxPaidOutsideIndia, entry.taxPayableInIndia)} /></label>
      </div><small style={{ color: errors.length ? '#b42318' : '#667085' }}>{errors.join(' ') || 'Ready for backend computation.'}</small><button type="button" onClick={() => props.onForeignSourceIncomeChange(props.foreignSourceIncome.filter((item) => item.id !== entry.id))}>Remove</button></div>; })}
      {!props.foreignSourceIncome.length && <p style={muted}>No foreign-source income rows.</p>}
    </section>
    <section style={sectionStyle}><div style={headingStyle}><h3>Schedule TR1 — Foreign Tax Relief</h3><button type="button" onClick={() => props.onForeignTaxReliefChange([...props.foreignTaxRelief, newTr()])}>＋ Add claim</button></div>
      {props.foreignTaxRelief.map((entry, index) => { const errors = validateForeignTaxRelief(entry); return <div style={rowStyle} key={entry.id}><strong>{index + 1}</strong><div style={gridStyle}>
        {field('Country code', entry.countryCode, (value) => updateTr(entry.id, { countryCode: value.toUpperCase() }))}{field('Foreign TIN', entry.taxIdentificationNo, (value) => updateTr(entry.id, { taxIdentificationNo: value }))}{field('Income included', entry.incomeIncludedInThisReturn, (value) => updateTr(entry.id, { incomeIncludedInThisReturn: money(value) }), true)}{field('Foreign tax paid', entry.taxPaidOutsideIndia, (value) => updateTr(entry.id, { taxPaidOutsideIndia: money(value) }), true)}{field('Indian tax payable', entry.indianTaxPayable, (value) => updateTr(entry.id, { indianTaxPayable: money(value) }), true)}
        <label>Relief section<select value={entry.reliefSection} onChange={(event) => updateTr(entry.id, { reliefSection: event.target.value as ForeignTaxReliefEntry['reliefSection'] })}>{sections.map((section) => <option key={section} value={section}>Section {section}</option>)}</select></label>
        <label>Relief claimed<input type="number" min={0} value={entry.reliefClaimed} onChange={(event) => updateTr(entry.id, { reliefClaimed: money(event.target.value) })} /></label><label>Form 67 filed<select value={entry.form67Filed ? 'Y' : 'N'} onChange={(event) => updateTr(entry.id, { form67Filed: event.target.value === 'Y' })}><option value="Y">Yes</option><option value="N">No</option></select></label><label>Form 10F filed<select value={entry.form10FFiled ? 'Y' : 'N'} onChange={(event) => updateTr(entry.id, { form10FFiled: event.target.value === 'Y' })}><option value="Y">Yes</option><option value="N">No</option></select></label>
      </div><small style={{ color: errors.length ? '#b42318' : '#667085' }}>{errors.join(' ') || 'Ready for backend computation.'}</small><button type="button" onClick={() => props.onForeignTaxReliefChange(props.foreignTaxRelief.filter((item) => item.id !== entry.id))}>Remove</button></div>; })}
      <aside aria-label="Schedule TR1 computed totals" style={summaryStyle}><span>Total foreign tax paid (computed): ₹{totals.taxPaid}</span><span>Total relief (computed): ₹{totals.relief}</span><span>DTAA relief (computed): ₹{totals.dtaaRelief}</span><span>Section 91 relief (computed): ₹{totals.nonDtaaRelief}</span></aside>
      {!props.foreignTaxRelief.length && <p style={muted}>No foreign tax relief claims.</p>}
    </section>
  </div>;
}
const sectionStyle: React.CSSProperties = { border: '1px solid var(--border, #eaecf0)', borderRadius: 8, padding: 16, display: 'grid', gap: 12 };
const headingStyle: React.CSSProperties = { display: 'flex', justifyContent: 'space-between', alignItems: 'center' };
const rowStyle: React.CSSProperties = { border: '1px solid #eaecf0', borderRadius: 6, padding: 12, display: 'grid', gap: 10 };
const gridStyle: React.CSSProperties = { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: 10 };
const summaryStyle: React.CSSProperties = { display: 'flex', gap: 16, flexWrap: 'wrap', background: '#f8fafc', padding: 12 };
const muted: React.CSSProperties = { color: 'var(--text-muted, #667085)', margin: 0 };
export default ITR3ForeignSchedulesEditor;
