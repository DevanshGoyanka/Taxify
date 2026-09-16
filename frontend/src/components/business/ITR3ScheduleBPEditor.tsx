import React from 'react';
import type { CanonicalObject, CanonicalValue } from './ITR3BusinessCoreManager';
import { SCHEDULE_BP_FIELDS, readScheduleBPValue, updateScheduleBPValue, type ScheduleBPDisposition, type ScheduleBPGroup } from '../../domain/itr3ScheduleBP';

/** Props for the explicit official Schedule BP editor. */
export interface ITR3ScheduleBPEditorProps {
  value?: CanonicalObject;
  onChange: (value: CanonicalObject) => void;
  disabled?: boolean;
}

const GROUP_LABELS: Record<ScheduleBPGroup, string> = {
  'p-and-l-bridge': 'P&L bridge',
  depreciation: 'Depreciation',
  'disallowances-add-backs': 'Disallowances and add-backs',
  'exempt-other-head-income': 'Exempt and other-head income',
  icds: 'ICDS adjustments',
  'presumptive-income': 'Presumptive income',
  'speculative-specified-business': 'Speculative and specified business',
  'current-year-setoff': 'Current-year set-off',
  'final-business-totals': 'Final business totals',
};

function displayValue(value: CanonicalValue | undefined): string {
  return typeof value === 'number' || typeof value === 'string' ? String(value) : '';
}

function isEditable(disposition: ScheduleBPDisposition): boolean {
  return disposition === 'editable-source' || disposition === 'imported';
}

/** Renders all 131 official Schedule BP paths with protected computed outputs. */
export default function ITR3ScheduleBPEditor({ value = {}, onChange, disabled = false }: ITR3ScheduleBPEditorProps): React.JSX.Element {
  const groups = [...new Set(SCHEDULE_BP_FIELDS.map((field) => field.group))];
  return <div aria-label="Schedule BP editor">
    {groups.map((group) => <section key={group} style={{ marginBottom: 18, padding: 16, border: '1px solid var(--border)', borderRadius: 6, background: '#fff' }}>
      <h3 style={{ margin: '0 0 14px', fontSize: 14, color: 'var(--text-secondary)' }}>{GROUP_LABELS[group]}</h3>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 12 }}>
        {SCHEDULE_BP_FIELDS.filter((field) => field.group === group).map((field) => {
          const current = readScheduleBPValue(value, field.path);
          const editable = isEditable(field.disposition) && !disabled;
          const computed = field.disposition === 'backend-computed';
          return <label key={field.path} htmlFor={`schedule-bp-${field.path}`} style={{ display: 'block' }}>
            <span style={{ display: 'block', marginBottom: 5, fontSize: 11, color: 'var(--text-secondary)' }}>{field.label}{field.required ? ' *' : ''}{computed ? ' (computed)' : field.disposition === 'backend-only' ? ' (backend)' : ''}</span>
            <input id={`schedule-bp-${field.path}`} aria-label={field.path} type={field.type === 'integer' || field.type === 'number' ? 'number' : 'text'} value={displayValue(current)} disabled={!editable} readOnly={!editable} style={{ width: '100%', boxSizing: 'border-box', padding: '8px 10px', border: '1px solid var(--border)', borderRadius: 5, background: editable ? '#fff' : 'var(--gold-pale)', color: 'var(--text-primary)' }} onChange={(event) => onChange(updateScheduleBPValue(value, field.path, field.type === 'integer' || field.type === 'number' ? (event.target.value === '' ? 0 : Number(event.target.value)) : event.target.value))} />
          </label>;
        })}
      </div>
    </section>)}
  </div>;
}
