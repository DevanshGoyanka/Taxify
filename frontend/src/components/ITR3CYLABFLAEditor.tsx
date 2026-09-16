import type { ReactElement } from 'react';
import type { BroughtForwardLosses, ReturnDraft } from '../domain/returns/types';
import { ITR3_LOSS_INPUT_FIELDS, itr3LossCoverage, updateItr3LossInput } from '../domain/returns/itr3LossSetoff';

interface Props {
  draft: ReturnDraft;
  taxResult?: Record<string, unknown> | null;
  onChange: (losses: BroughtForwardLosses) => void;
}

const money = (value: unknown): number => {
  const result = Number(value);
  return Number.isFinite(result) ? result : 0;
};

/** Dedicated ITR-3 Schedule CYLA/BFLA editor. */
export function ITR3CYLABFLAEditor({ draft, taxResult, onChange }: Props): ReactElement {
  const losses = draft.lossesBroughtForward;
  const computed = itr3LossCoverage().filter((entry) => entry.disposition === 'computed');
  const setInput = (key: keyof BroughtForwardLosses, value: unknown): void => onChange(updateItr3LossInput(losses, key, value));
  return (
    <section aria-label="Schedule CYLA and BFLA" style={{ display: 'grid', gap: 16 }}>
      <div>
        <h3 style={{ margin: 0 }}>Schedule CYLA &amp; BFLA</h3>
        <p style={{ color: 'var(--text-secondary)', fontSize: 12, margin: '6px 0 0' }}>
          Current-year and brought-forward loss set-off is calculated by the backend. Enter only opening loss balances below.
        </p>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(220px, 1fr))', gap: 12 }}>
        {ITR3_LOSS_INPUT_FIELDS.map((field) => (
          <label key={field.key} style={{ display: 'grid', gap: 5, fontSize: 12 }}>
            <span>{field.label} <small style={{ color: 'var(--text-secondary)' }}>({field.head})</small></span>
            <input
              aria-label={field.label}
              type="number"
              min={0}
              value={losses[field.key] ?? 0}
              onChange={(event) => setInput(field.key, event.target.value)}
            />
            <small style={{ color: 'var(--text-secondary)' }}>{field.path}</small>
          </label>
        ))}
      </div>
      <div style={{ border: '1px solid var(--border)', borderRadius: 6, padding: 12 }}>
        <strong style={{ fontSize: 13 }}>Backend-computed set-off and remaining balances</strong>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(180px, 1fr))', gap: 10, marginTop: 10 }}>
          {computed.slice(0, 12).map((field) => (
            <label key={field.path} style={{ display: 'grid', gap: 4, fontSize: 11 }}>
              <span>{field.fieldName}</span>
              <input aria-label={`${field.path} (computed)`} value={money(taxResult?.[field.fieldName])} readOnly disabled />
              <small>{field.path}</small>
            </label>
          ))}
        </div>
        <small style={{ display: 'block', marginTop: 10, color: 'var(--text-secondary)' }}>
          Read-only fields are never written into the draft; they refresh from the tax computation response.
        </small>
      </div>
    </section>
  );
}

export default ITR3CYLABFLAEditor;
