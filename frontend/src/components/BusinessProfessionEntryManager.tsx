import React from 'react';
import ITR4ScheduleBPManager, { type ITR4ScheduleBPData } from './business/ITR4ScheduleBPManager';
import type { ITR3BusinessCoreData } from './business/ITR3BusinessCoreManager';
import type { ITR3AuxiliaryData } from './business/ITR3BusinessAuxiliaryManager';
import ITR3BusinessWorkspace from './business/ITR3BusinessWorkspace';

/** Canonical frontend-only Business/Profession state for AY 2026-27. */
export interface BusinessProfessionScheduleData {
  ITR4ScheduleBP?: ITR4ScheduleBPData;
  ITR3Core?: Partial<ITR3BusinessCoreData>;
  ITR3Auxiliary?: Partial<ITR3AuxiliaryData>;
}

interface Props {
  data?: BusinessProfessionScheduleData;
  onChange: (data: BusinessProfessionScheduleData) => void;
  selectedForm: string;
  taxResult?: { bizIncome?: number } | null;
}

const cardStyle: React.CSSProperties = { marginBottom: 20, padding: 16, background: 'var(--bg)', borderRadius: 6, border: '1px solid var(--border)' };

/** Routes Business/Profession capture to the exact official schema for the selected ITR form. */
export function BusinessProfessionEntryManager({ data = {}, onChange, selectedForm, taxResult }: Props): React.ReactElement {
  const normalizedForm = selectedForm.replace('-', '').toUpperCase();
  const itr3 = normalizedForm === 'ITR3';
  const itr4 = normalizedForm === 'ITR4';

  if (!itr3 && !itr4) {
    return <div>
      <Header selectedForm={selectedForm} detail="Business income is not reportable in the selected form." />
      <div style={{ marginBottom: 16, padding: '14px 16px', background: '#fef3c7', border: '2px solid #f59e0b', borderRadius: 8, fontSize: 13, color: '#92400e' }}>
        <strong style={{ fontSize: 14, display: 'block', marginBottom: 4 }}>⚠ Switch to ITR-3 or ITR-4</strong>
        <div>{selectedForm} does not contain a Business or Profession schedule. Use ITR-3 for full PGBP/accounts or ITR-4 for eligible presumptive income under sections 44AD, 44ADA, or 44AE.</div>
      </div>
    </div>;
  }

  if (itr4) {
    return <div>
      <Header selectedForm={selectedForm} detail="Official Schedule BP: 44AD, 44ADA, 44AE, GST turnover and financial particulars." />
      <ITR4ScheduleBPManager
        data={data.ITR4ScheduleBP}
        onChange={(ITR4ScheduleBP) => onChange({ ...data, ITR4ScheduleBP })}
      />
      <ComputedIncome value={Number(taxResult?.bizIncome || 0)} />
    </div>;
  }

  return <div>
    <ITR3BusinessWorkspace
      core={data.ITR3Core}
      auxiliary={data.ITR3Auxiliary}
      onCoreChange={(ITR3Core: ITR3BusinessCoreData) => onChange({ ...data, ITR3Core })}
      onAuxiliaryChange={(ITR3Auxiliary: ITR3AuxiliaryData) => onChange({ ...data, ITR3Auxiliary })}
      computedIncome={Number(taxResult?.bizIncome || 0)}
    />
  </div>;
}

function Header({ selectedForm, detail }: { selectedForm: string; detail: string }): React.ReactElement {
  return <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
    <div>
      <h3 style={{ margin: 0, fontSize: 14, color: 'var(--text-secondary)' }}>Business or Profession — {selectedForm}</h3>
      <div style={{ marginTop: 4, fontSize: 12, color: 'var(--text-muted)' }}>{detail}</div>
    </div>
  </div>;
}

function ComputedIncome({ value }: { value: number }): React.ReactElement {
  return <div style={cardStyle}>
    <label style={{ display: 'block', marginBottom: 5, fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)' }}>Computed business income</label>
    <input readOnly value={`₹${Number(value || 0).toLocaleString('en-IN')}`} style={{ width: '100%', maxWidth: 320, padding: '8px 10px', border: '1px solid var(--border)', borderRadius: 6, fontSize: 13, background: '#f8fafc', color: 'var(--text-primary)', boxSizing: 'border-box' }} />
  </div>;
}
