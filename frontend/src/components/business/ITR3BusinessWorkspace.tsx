import React, { useMemo, useState } from 'react';
import ITR3BusinessCoreManager, { type CanonicalValue, type ITR3BusinessCoreData } from './ITR3BusinessCoreManager';
import ITR3BusinessAuxiliaryManager, { type ITR3AuxiliaryData, type ITR3AuxiliaryValue } from './ITR3BusinessAuxiliaryManager';

/** Props for the guided AY 2026-27 ITR-3 business workspace. */
export interface ITR3BusinessWorkspaceProps {
  core?: Partial<ITR3BusinessCoreData>;
  auxiliary?: Partial<ITR3AuxiliaryData>;
  onCoreChange: (data: ITR3BusinessCoreData) => void;
  onAuxiliaryChange: (data: ITR3AuxiliaryData) => void;
  computedIncome?: number;
}

type StepKey = 'profile' | 'accounts' | 'bp' | 'supporting' | 'review';

interface StepDefinition {
  key: StepKey;
  number: number;
  title: string;
  subtitle: string;
}

interface ScheduleChoice {
  key: string;
  label: string;
  help: string;
  group: string;
}

const STEPS: readonly StepDefinition[] = [
  { key: 'profile', number: 1, title: 'Business & audit', subtitle: 'Books, audit and nature of business' },
  { key: 'accounts', number: 2, title: 'Financial statements', subtitle: 'Balance Sheet, Trading and P&L' },
  { key: 'bp', number: 3, title: 'Schedule BP', subtitle: 'Tax computation from book profit' },
  { key: 'supporting', number: 4, title: 'Supporting schedules', subtitle: 'Only schedules applicable to you' },
  { key: 'review', number: 5, title: 'Review', subtitle: 'Check completion and computed income' },
];

const SCHEDULE_CHOICES: readonly ScheduleChoice[] = [
  { key: 'ScheduleDPM', label: 'DPM — Plant and machinery depreciation', help: 'Select when depreciation is claimed on plant and machinery blocks.', group: 'Depreciation and assets' },
  { key: 'ScheduleDOA', label: 'DOA — Depreciation on other assets', help: 'Land, buildings, furniture, intangible assets and ships.', group: 'Depreciation and assets' },
  { key: 'ScheduleDEP', label: 'DEP — Depreciation summary', help: 'Summary of depreciation carried to Schedule BP.', group: 'Depreciation and assets' },
  { key: 'ScheduleDCG', label: 'DCG — Capital gains on depreciable assets', help: 'Select when a depreciable block gives rise to section 50 capital gains.', group: 'Depreciation and assets' },
  { key: 'ScheduleESR', label: 'ESR — Scientific research expenditure', help: 'Deductions claimed under section 35.', group: 'Adjustments and carried-forward amounts' },
  { key: 'ITR3ScheduleUD', label: 'UD — Unabsorbed depreciation', help: 'Brought-forward depreciation and allowance set-off.', group: 'Adjustments and carried-forward amounts' },
  { key: 'ScheduleICDS', label: 'ICDS adjustments', help: 'Increase or decrease in profit under the ten notified ICDS.', group: 'Adjustments and carried-forward amounts' },
  { key: 'ScheduleGST', label: 'GST turnover', help: 'Turnover or gross receipts reported for each GSTIN.', group: 'Business disclosures' },
  { key: 'ScheduleIF', label: 'IF — Partnership firms', help: 'Share of profit, interest, remuneration and capital in firms.', group: 'Business disclosures' },
  { key: 'PARTA_QD', label: 'Part A-QD — Quantitative details', help: 'Trading or manufacturing stock and quantity details, where applicable.', group: 'Business disclosures' },
  { key: 'Schedule10AA', label: '10AA — SEZ deduction', help: 'Deduction for eligible SEZ undertakings.', group: 'Profit-linked deductions' },
  { key: 'Schedule80_IA', label: '80-IA deduction', help: 'Eligible infrastructure or power undertakings.', group: 'Profit-linked deductions' },
  { key: 'Schedule80_IB', label: '80-IB deduction', help: 'Eligible mineral oil, housing, food and other undertakings.', group: 'Profit-linked deductions' },
  { key: 'Schedule80_IC', label: '80-IC / 80-IE deduction', help: 'Eligible undertakings in specified states and the North-East.', group: 'Profit-linked deductions' },
  { key: 'Schedule80RA', label: '80RA — Research donations', help: 'Eligible donations to research associations and institutions.', group: 'Profit-linked deductions' },
  { key: 'ScheduleTPSA', label: 'TPSA — Secondary adjustment tax', help: 'Additional tax arising from a transfer-pricing secondary adjustment.', group: 'Transfer pricing' },
];

const sectionCard: React.CSSProperties = { padding: 18, background: '#fff', border: '1px solid var(--border)', borderRadius: 6, marginBottom: 16 };

function hasMeaningfulValue(value: CanonicalValue | ITR3AuxiliaryValue | undefined): boolean {
  if (Array.isArray(value)) return value.length > 0 && value.some(hasMeaningfulValue);
  if (value && typeof value === 'object') return Object.values(value).some(hasMeaningfulValue);
  return value !== undefined && value !== null && value !== '' && value !== 0 && value !== false;
}

function countMeaningful(value: CanonicalValue | ITR3AuxiliaryValue | undefined): number {
  if (Array.isArray(value)) return value.reduce<number>((total, item) => total + countMeaningful(item), 0);
  if (value && typeof value === 'object') return Object.values(value).reduce<number>((total, item) => total + countMeaningful(item), 0);
  return hasMeaningfulValue(value) ? 1 : 0;
}

function initialSelectedSchedules(auxiliary?: Partial<ITR3AuxiliaryData>): Set<string> {
  return new Set(SCHEDULE_CHOICES.filter((choice) => hasMeaningfulValue(auxiliary?.[choice.key])).map((choice) => choice.key));
}

/** Renders a guided portal-style workflow over the canonical ITR-3 schedules. */
export default function ITR3BusinessWorkspace({ core, auxiliary, onCoreChange, onAuxiliaryChange, computedIncome = 0 }: ITR3BusinessWorkspaceProps): React.JSX.Element {
  const [activeStep, setActiveStep] = useState<StepKey>('profile');
  const [selectedSchedules, setSelectedSchedules] = useState<Set<string>>(() => initialSelectedSchedules(auxiliary));
  const activeIndex = STEPS.findIndex((step) => step.key === activeStep);
  const selectedKeys = useMemo(() => SCHEDULE_CHOICES.map((choice) => choice.key).filter((key) => selectedSchedules.has(key)), [selectedSchedules]);

  const toggleSchedule = (key: string): void => setSelectedSchedules((current) => {
    const next = new Set(current);
    if (next.has(key)) next.delete(key); else next.add(key);
    return next;
  });
  const go = (offset: number): void => setActiveStep(STEPS[Math.max(0, Math.min(STEPS.length - 1, activeIndex + offset))].key);

  return <div>
    <div style={{ marginBottom: 20, padding: 16, background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 6 }}>
      <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 4 }}>ITR-3 — Profits and gains from business or profession</div>
      <div style={{ fontSize: 12, lineHeight: 1.5, color: 'var(--text-muted)' }}>Complete the return in the same order as the notified CBDT form: establish applicability, prepare accounts, compute taxable business income, then complete only the supporting schedules that apply.</div>
    </div>

    <nav aria-label="ITR-3 business filing steps" style={{ display: 'grid', gridTemplateColumns: 'repeat(5, minmax(0, 1fr))', gap: 8, marginBottom: 22 }}>
      {STEPS.map((step) => {
        const active = step.key === activeStep;
        const completed = STEPS.findIndex((item) => item.key === step.key) < activeIndex;
        return <button key={step.key} type="button" onClick={() => setActiveStep(step.key)} style={{ padding: '12px 10px', textAlign: 'left', border: `1px solid ${active ? 'var(--gold)' : 'var(--border)'}`, borderRadius: 6, background: active ? 'var(--gold-pale)' : '#fff', cursor: 'pointer' }}>
          <span style={{ display: 'inline-flex', width: 22, height: 22, alignItems: 'center', justifyContent: 'center', borderRadius: '50%', background: active || completed ? 'var(--gold)' : 'var(--bg)', color: active || completed ? '#fff' : 'var(--text-muted)', fontSize: 11, fontWeight: 700 }}>{completed ? '✓' : step.number}</span>
          <span style={{ display: 'block', marginTop: 8, fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)' }}>{step.title}</span>
          <span style={{ display: 'block', marginTop: 3, fontSize: 10, lineHeight: 1.35, color: 'var(--text-muted)' }}>{step.subtitle}</span>
        </button>;
      })}
    </nav>

    {activeStep === 'profile' && <div>
      <div style={sectionCard}><h3 style={{ margin: '0 0 6px', fontSize: 15, color: 'var(--text-secondary)' }}>1. Establish your business reporting requirements</h3><p style={{ margin: 0, fontSize: 12, lineHeight: 1.55, color: 'var(--text-muted)' }}>Answer the books and audit questions first. These disclosures determine the accounts and supporting schedules required in the return. Add every business or profession using the official nature code.</p></div>
      <ITR3BusinessCoreManager value={core} onChange={onCoreChange} visibleSchedules={['PartA_GEN2']} showHeading={false} />
    </div>}

    {activeStep === 'accounts' && <div>
      <div style={sectionCard}><h3 style={{ margin: '0 0 6px', fontSize: 15, color: 'var(--text-secondary)' }}>2. Prepare financial statements</h3><p style={{ margin: 0, fontSize: 12, lineHeight: 1.55, color: 'var(--text-muted)' }}>Enter figures in accounting order. Manufacturers should complete the Manufacturing Account first; its cost of goods produced flows into the Trading Account, followed by the Profit and Loss Account and Balance Sheet.</p></div>
      <ITR3BusinessCoreManager value={core} onChange={onCoreChange} visibleSchedules={['ManufacturingAccount', 'TradingAccount', 'PARTA_PL', 'PARTA_BS']} showHeading={false} />
    </div>}

    {activeStep === 'bp' && <div>
      <div style={sectionCard}><h3 style={{ margin: '0 0 6px', fontSize: 15, color: 'var(--text-secondary)' }}>3. Compute income in Schedule BP</h3><div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 10, marginTop: 12 }}>
        {[['A', 'Regular business', 'Book profit, other-head items, disallowances, deductions and Rule 7 adjustments'], ['B', 'Speculative business', 'Profit or loss from speculative transactions'], ['C', 'Specified business', 'Section 35AD specified-business computation'], ['D', 'Chargeable income', 'Aggregate business income and current-year business-loss set-off']].map(([code, title, text]) => <div key={code} style={{ padding: 12, border: '1px solid var(--border)', borderRadius: 6, background: 'var(--bg)' }}><span style={{ display: 'inline-flex', width: 22, height: 22, alignItems: 'center', justifyContent: 'center', background: 'var(--gold)', color: '#fff', borderRadius: 4, fontSize: 11, fontWeight: 700 }}>{code}</span><strong style={{ display: 'block', marginTop: 8, fontSize: 12, color: 'var(--text-secondary)' }}>{title}</strong><span style={{ display: 'block', marginTop: 4, fontSize: 10, lineHeight: 1.4, color: 'var(--text-muted)' }}>{text}</span></div>)}
      </div></div>
      <ITR3BusinessCoreManager value={core} onChange={onCoreChange} visibleSchedules={['ITR3ScheduleBP']} showHeading={false} />
    </div>}

    {activeStep === 'supporting' && <div>
      <div style={sectionCard}><h3 style={{ margin: '0 0 6px', fontSize: 15, color: 'var(--text-secondary)' }}>4. Select applicable supporting schedules</h3><p style={{ margin: 0, fontSize: 12, lineHeight: 1.55, color: 'var(--text-muted)' }}>The ITD utility shows schedules based on applicability. Select only those relevant to this return. Hiding a schedule does not delete data already entered.</p></div>
      {[...new Set(SCHEDULE_CHOICES.map((choice) => choice.group))].map((group) => <div key={group} style={sectionCard}><h4 style={{ margin: '0 0 12px', fontSize: 13, color: 'var(--text-secondary)' }}>{group}</h4><div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 10 }}>{SCHEDULE_CHOICES.filter((choice) => choice.group === group).map((choice) => <label key={choice.key} style={{ display: 'flex', gap: 10, padding: 12, border: `1px solid ${selectedSchedules.has(choice.key) ? 'var(--gold)' : 'var(--border)'}`, borderRadius: 6, background: selectedSchedules.has(choice.key) ? 'var(--gold-pale)' : 'var(--bg)', cursor: 'pointer' }}><input type="checkbox" checked={selectedSchedules.has(choice.key)} onChange={() => toggleSchedule(choice.key)} style={{ marginTop: 2 }} /><span><strong style={{ display: 'block', fontSize: 12, color: 'var(--text-secondary)' }}>{choice.label}</strong><span style={{ display: 'block', marginTop: 4, fontSize: 10, lineHeight: 1.4, color: 'var(--text-muted)' }}>{choice.help}</span></span></label>)}</div></div>)}
      {selectedKeys.length === 0 ? <div style={{ padding: 24, textAlign: 'center', color: 'var(--text-muted)', background: 'var(--bg)', borderRadius: 6 }}>No supporting schedule selected. Choose an applicable schedule above to complete it.</div> : <ITR3BusinessAuxiliaryManager data={auxiliary} onChange={onAuxiliaryChange} visibleSchedules={selectedKeys} showHeading={false} />}
    </div>}

    {activeStep === 'review' && <div>
      <div style={sectionCard}><h3 style={{ margin: '0 0 6px', fontSize: 15, color: 'var(--text-secondary)' }}>5. Review business schedules</h3><p style={{ margin: 0, fontSize: 12, lineHeight: 1.55, color: 'var(--text-muted)' }}>Review the schedules below before moving to tax computation. Final CBDT validation remains authoritative; zero values can be valid where a mandatory schema field is not applicable.</p></div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 12, marginBottom: 16 }}>
        <ReviewMetric label="Core schedules" value="6" detail={`${countMeaningful(core as CanonicalValue)} populated values`} />
        <ReviewMetric label="Supporting schedules" value={String(selectedKeys.length)} detail={selectedKeys.length ? 'selected as applicable' : 'none selected'} />
        <ReviewMetric label="Computed business income" value={`₹${Number(computedIncome || 0).toLocaleString('en-IN')}`} detail="from current tax computation" />
      </div>
      <div style={sectionCard}><h4 style={{ margin: '0 0 12px', fontSize: 13, color: 'var(--text-secondary)' }}>Selected supporting schedules</h4>{selectedKeys.length ? <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>{SCHEDULE_CHOICES.filter((choice) => selectedSchedules.has(choice.key)).map((choice) => <span key={choice.key} style={{ padding: '5px 9px', borderRadius: 12, background: 'var(--gold-pale)', color: 'var(--text-secondary)', fontSize: 11 }}>{choice.label}</span>)}</div> : <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>No supporting schedules selected.</div>}</div>
    </div>}

    <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 20 }}><button type="button" disabled={activeIndex === 0} onClick={() => go(-1)} style={{ padding: '7px 14px', border: '1px solid var(--border)', background: '#fff', borderRadius: 6, fontSize: 12, cursor: activeIndex === 0 ? 'not-allowed' : 'pointer', opacity: activeIndex === 0 ? 0.5 : 1 }}>← Previous</button><button type="button" disabled={activeIndex === STEPS.length - 1} onClick={() => go(1)} style={{ padding: '7px 14px', border: 0, background: 'var(--gold)', color: '#fff', borderRadius: 6, fontSize: 12, cursor: activeIndex === STEPS.length - 1 ? 'not-allowed' : 'pointer', opacity: activeIndex === STEPS.length - 1 ? 0.5 : 1 }}>Save and continue →</button></div>
  </div>;
}

function ReviewMetric({ label, value, detail }: { label: string; value: string; detail: string }): React.JSX.Element {
  return <div style={{ padding: 16, background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 6 }}><div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{label}</div><div style={{ marginTop: 6, fontSize: 18, fontWeight: 700, color: 'var(--text-secondary)' }}>{value}</div><div style={{ marginTop: 4, fontSize: 10, color: 'var(--text-muted)' }}>{detail}</div></div>;
}
