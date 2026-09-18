import type { ReactElement } from 'react';
import type { ReturnDraft } from '../domain/returns/types';
import { ITR3_PART_A_OI_FIELDS, readItr3PartAOI, updateItr3PartAOI } from '../domain/itr3PartAOI';

interface Props { draft: ReturnDraft; taxResult?: Record<string, unknown> | null; onChange: (workspace: ReturnDraft['itr3BusinessWorkspace']) => void; }
const amount = (value: unknown): number => Number.isFinite(Number(value)) ? Math.max(0, Number(value)) : 0;

/** Dedicated official ITR-3 Part A-OI business-adjustment editor. */
export function ITR3PartAOIEditor({ draft, taxResult, onChange }: Props): ReactElement {
  const workspace = draft.itr3BusinessWorkspace;
  const part = readItr3PartAOI(workspace);
  const rawValue = (key: string, group: string): unknown => {
    const value = (part as unknown as Record<string, unknown>)[group];
    return typeof value === 'object' && value !== null ? (value as Record<string, unknown>)[key] : value;
  };
  const inputValue = (key: string, group: string): number => amount(rawValue(key, group));
  return <section aria-label="Part A-OI" style={{ display: 'grid', gap: 16 }}>
    <div><h3 style={{ margin: 0 }}>Part A-OI — Other Information</h3><p style={{ color: 'var(--text-secondary)', fontSize: 12 }}>Official ITR-3 business-profit adjustments. Enter source amounts only; Schedule BP totals and computed outputs are read-only.</p></div>
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(220px, 1fr))', gap: 12 }}>
      {ITR3_PART_A_OI_FIELDS.map((field) => <label key={field.path} style={{ display: 'grid', gap: 5, fontSize: 12 }}><span>{field.label}</span>
        {field.type === 'select'
          ? <select aria-label={field.label} value={String(rawValue(field.key, field.group) ?? field.options?.[0]?.value ?? '')} onChange={(event) => onChange(updateItr3PartAOI(workspace, field.key, event.target.value))}>
              {field.options?.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
            </select>
          : <input aria-label={field.label} type="number" min={0} step={1} value={inputValue(field.key, field.group)} onChange={(event) => onChange(updateItr3PartAOI(workspace, field.key, event.target.value))} />}
        <small style={{ color: 'var(--text-secondary)' }}>{field.path}</small></label>)}
    </div>
    <div style={{ border: '1px solid var(--border)', borderRadius: 6, padding: 12 }}><strong>Backend-computed business outputs</strong><label style={{ display: 'grid', gap: 5, marginTop: 10, fontSize: 12 }}><span>Schedule BP business income</span><input readOnly disabled aria-label="Schedule BP business income (computed)" value={amount(taxResult?.bizIncome)} /></label><small style={{ display: 'block', marginTop: 8, color: 'var(--text-secondary)' }}>Computed totals and Schedule BP outputs cannot be edited from Part A-OI.</small></div>
  </section>;
}
export default ITR3PartAOIEditor;
