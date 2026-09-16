import React from 'react';
import type { CanonicalObject, CanonicalValue } from './business/ITR3BusinessCoreManager';
import { ITR3_PARTA_BS_FIELDS, ITR3_PARTA_PL_FIELDS, isFinancialFieldEditable, readCanonicalPath, updateCanonicalPath, type ITR3FinancialField, type ITR3FinancialFieldGroup } from '../domain/itr3PartAFinancials';

interface Props { schedule: 'PARTA_PL' | 'PARTA_BS'; value?: CanonicalObject; onChange: (value: CanonicalObject) => void; disabled?: boolean; }

const labels: Record<ITR3FinancialFieldGroup, string> = {
  'official-credits': 'Official credits', expenses: 'Expenses', 'interest-depreciation': 'Interest and depreciation', 'tax-and-profit-after-tax': 'Tax and profit after tax', appropriations: 'Appropriations', 'presumptive-rows': 'Presumptive rows', funds: 'Funds', loans: 'Loans and advances', 'fixed-assets': 'Fixed assets', investments: 'Investments', 'current-assets-liabilities': 'Current assets and liabilities', provisions: 'Provisions', 'totals-and-no-books': 'Totals and no-books disclosures',
};

const display = (value: CanonicalValue | undefined): string => value === undefined || value === null ? '' : typeof value === 'object' ? JSON.stringify(value) : String(value);

/** Dedicated field-by-field editor for official Part A Profit & Loss and Balance Sheet paths. */
export default function ITR3PartAFinancialEditor({ schedule, value = {}, onChange, disabled = false }: Props): React.JSX.Element {
  const fields = schedule === 'PARTA_PL' ? ITR3_PARTA_PL_FIELDS : ITR3_PARTA_BS_FIELDS;
  const groups = [...new Set(fields.map((field) => field.group))];
  const change = (field: ITR3FinancialField, raw: string): void => {
    if (!isFinancialFieldEditable(field) || disabled) return;
    const next: CanonicalValue = field.type === 'integer' || field.type === 'number' ? (raw === '' ? 0 : Number(raw)) : raw;
    onChange(updateCanonicalPath(value, field.path, next));
  };
  return <div aria-label={`${schedule} dedicated editor`}>
    <div style={{ marginBottom: 14, padding: 14, background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 6 }}><strong>{schedule === 'PARTA_PL' ? 'Part A-P&L — Profit and Loss Account' : 'Part A-BS — Balance Sheet'}</strong><div style={{ marginTop: 4, fontSize: 11, color: 'var(--text-muted)' }}>AY 2026-27 official fields. Computed, backend-only, imported and unsupported fields are protected.</div></div>
    {groups.map((group) => <section key={group} style={{ marginBottom: 16, padding: 15, border: '1px solid var(--border)', borderRadius: 6, background: '#fff' }}><h3 style={{ margin: '0 0 12px', fontSize: 14, color: 'var(--text-secondary)' }}>{labels[group]}</h3><div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 11 }}>{fields.filter((field) => field.group === group).map((field) => { const editable = isFinancialFieldEditable(field) && !disabled; const current = readCanonicalPath(value, field.path); return <label key={field.path} htmlFor={`${schedule}-${field.path}`} style={{ display: 'block' }}><span style={{ display: 'block', marginBottom: 4, fontSize: 11, color: 'var(--text-secondary)' }}>{field.label}{field.required ? ' *' : ''}<small style={{ display: 'block', color: 'var(--text-muted)' }}>{field.disposition}</small></span><input id={`${schedule}-${field.path}`} aria-label={field.path} type={field.type === 'integer' || field.type === 'number' ? 'number' : 'text'} value={display(current)} disabled={!editable} readOnly={!editable} onChange={(event) => change(field, event.target.value)} style={{ width: '100%', boxSizing: 'border-box', padding: '8px 10px', border: '1px solid var(--border)', borderRadius: 5, background: editable ? '#fff' : 'var(--gold-pale)' }} /></label>; })}</div></section>)}
  </div>;
}
