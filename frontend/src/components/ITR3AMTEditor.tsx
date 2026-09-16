import type { ReactElement } from 'react';
import { IndianNumberInput } from './IndianNumberInput';
import type { AMTDetails, AMTComputedValues, AMTCreditEntry } from '../domain/amt';
import { isValidAMTAssessmentYear, sanitizeAMTMoney, updateAMTInputs } from '../domain/amt';

type Props = { amt: AMTDetails | null; computed?: AMTComputedValues | null; onChange: (value: AMTDetails | null) => void };
const inputStyle: React.CSSProperties = { width: '100%', padding: '8px', border: '1px solid var(--border)', borderRadius: 4 };
const cardStyle: React.CSSProperties = { background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 8, padding: 16, marginBottom: 16 };

/** Dedicated editor for official ITR-3 Schedule AMT and Schedule AMTC. */
export default function ITR3AMTEditor({ amt, computed, onChange }: Props): ReactElement {
  const value = amt ?? { deduction10AA: 0, deduction80IAto80RRBExcept80P: 0, deduction35ADNetDepreciation: 0, creditsBroughtForward: [] };
  const update = (patch: Partial<AMTDetails>): void => onChange(updateAMTInputs(value, patch));
  const addCredit = (): void => update({ creditsBroughtForward: [...value.creditsBroughtForward, { id: `amt-credit-${Date.now()}`, assessmentYear: '', creditBroughtForward: 0 }] });
  const removeCredit = (id: string): void => update({ creditsBroughtForward: value.creditsBroughtForward.filter((entry) => entry.id !== id) });
  return <section aria-label="Schedule AMT and AMTC">
    <h2>Schedule AMT &amp; AMTC</h2>
    <p style={{ color: 'var(--text-secondary)' }}>Enter only statutory adjustments and brought-forward credits. AMT tax and credit utilization are computed by the backend.</p>
    <div style={cardStyle}>
      <h3>Schedule AMT — Section 115JC inputs</h3>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
        <label>Deduction under section 10AA<IndianNumberInput style={inputStyle} value={value.deduction10AA} onChange={(next) => update({ deduction10AA: sanitizeAMTMoney(next) })} /></label>
        <label>80-IA to 80-RRB (except 80P)<IndianNumberInput style={inputStyle} value={value.deduction80IAto80RRBExcept80P} onChange={(next) => update({ deduction80IAto80RRBExcept80P: sanitizeAMTMoney(next) })} /></label>
        <label>35AD net depreciation<IndianNumberInput style={inputStyle} value={value.deduction35ADNetDepreciation} onChange={(next) => update({ deduction35ADNetDepreciation: sanitizeAMTMoney(next) })} /></label>
      </div>
    </div>
    <div style={cardStyle}>
      <h3>Schedule AMTC — brought-forward credit</h3>
      {value.creditsBroughtForward.map((entry: AMTCreditEntry) => <div key={entry.id} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr auto', gap: 12, alignItems: 'end', marginBottom: 10 }}>
        <label>Assessment year (AssYr)<input style={inputStyle} placeholder="2025-26" value={entry.assessmentYear} onChange={(event) => update({ creditsBroughtForward: value.creditsBroughtForward.map((row) => row.id === entry.id ? { ...row, assessmentYear: event.target.value } : row) })} />{entry.assessmentYear && !isValidAMTAssessmentYear(entry.assessmentYear) && <small style={{ color: 'crimson' }}>Enter an eligible prior AY (YYYY-YY).</small>}</label>
        <label>Credit brought forward<IndianNumberInput style={inputStyle} value={entry.creditBroughtForward} onChange={(next) => update({ creditsBroughtForward: value.creditsBroughtForward.map((row) => row.id === entry.id ? { ...row, creditBroughtForward: sanitizeAMTMoney(next) } : row) })} /></label>
        <button type="button" onClick={() => removeCredit(entry.id)}>Remove</button>
      </div>)}
      <button type="button" onClick={addCredit}>Add brought-forward credit</button>
    </div>
    <div style={cardStyle} aria-label="Backend computed AMT values">
      <h3>Backend-computed values (read-only)</h3>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
        {([['Adjusted total income', computed?.adjustedTotalIncome], ['AMT tax', computed?.amtTax], ['Available AMT credit', computed?.availableCredit], ['Credit utilized', computed?.utilizedCredit], ['Remaining credit', computed?.remainingCredit], ['Credit carried forward', computed?.carryForwardCredit]] as const).map(([label, field]) => <label key={label}>{label}<input style={{ ...inputStyle, background: '#eee' }} readOnly value={field ?? 0} /></label>)}
      </div>
    </div>
  </section>;
}
