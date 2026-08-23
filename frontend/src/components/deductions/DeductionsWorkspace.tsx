// Deductions Workspace — CBDT AY 2026-27 compliant, form-aware (ITR-1 to ITR-4).
// Mirrors the official UsrDeductUndChapVIAType / DeductUndChapVIA schema.
// Renders the existing sub-managers (80C, 80D, 80G, loans) plus every scalar
// Chapter VI-A section, gated per ITR form. New regime restricts to 80CCD(2).

import React, { useMemo, useState } from 'react';
import type { ChapterVIA, BusinessDeductions, Donation80G, Investment80C, PensionContribution80CCC, Schedule80GGAEntry, Schedule80GGCEntry, Section80D, Section80GGAClause } from '../../domain/returns/types';
import type { DeductionLoanManagerData } from '../../domain/returns';
import type { ItrForm } from '../../domain/eligibility';
import { Section80CManager } from '../Section80CManager';
import { Section80DManager } from '../Section80DManager';
import { DonationEntryManager } from '../DonationEntryManager';
import { DeductionLoanManager } from '../DeductionLoanManager';
import { INDIAN_STATE_CODE_OPTIONS, type StateCode } from '../../domain/returns/cbdtEnums';

interface SubManagers {
  section80C: (data: { investments: Investment80C[] }) => void;
  section80D: (data: Section80D) => void;
  donations: (entries: Donation80G[]) => void;
  deductionLoans: (data: DeductionLoanManagerData) => void;
}

interface DeductionsWorkspaceProps {
  form: ItrForm;
  regime: 'old' | 'new';
  section80C: Investment80C[];
  pensionContribution80CCC: PensionContribution80CCC[];
  section80D: Section80D;
  section80G: Donation80G[];
  loans: DeductionLoanManagerData;
  chapterVIA: ChapterVIA;
  onChangeChapterVIA: (next: ChapterVIA) => void;
  onChangePensionContribution80CCC: (entries: PensionContribution80CCC[]) => void;
  schedule80GGA: Schedule80GGAEntry[];
  schedule80GGC: Schedule80GGCEntry[];
  onChangeSchedule80GGA: (entries: Schedule80GGAEntry[]) => void;
  onChangeSchedule80GGC: (entries: Schedule80GGCEntry[]) => void;
  managers: SubManagers;
  totalDeductions?: number;
  deductionBreakdown?: Record<string, number> | null;
}

const MAX_MONEY = 99_999_999_999_999;
const money = (value: unknown): number => typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : 0;
const inr = (value: number): string => `₹${money(value).toLocaleString('en-IN')}`;

// Per-form capability matrix (from the official UsrDeductUndChapVIAType enums).
const FORM_CAPS = {
  'ITR-1': { gga: true, ggc: true, qqb: false, rrb: false, business: false },
  'ITR-2': { gga: true, ggc: true, qqb: true, rrb: true, business: false },
  'ITR-3': { gga: true, ggc: true, qqb: true, rrb: true, business: true },
  'ITR-4': { gga: false, ggc: true, qqb: false, rrb: false, business: false },
} as const;

const styles = {
  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 } as React.CSSProperties,
  title: { margin: 0, fontSize: 14, fontWeight: 600, color: 'var(--text-secondary)' } as React.CSSProperties,
  subtitle: { marginTop: 4, fontSize: 12, color: 'var(--text-muted)' } as React.CSSProperties,
  panel: { marginBottom: 24, padding: 16, background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 6 } as React.CSSProperties,
  panelHeader: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 } as React.CSSProperties,
  panelTitle: { margin: 0, fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)' } as React.CSSProperties,
  grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16 } as React.CSSProperties,
  label: { display: 'block', marginBottom: 6, fontSize: 12, fontWeight: 500, color: 'var(--text-secondary)' } as React.CSSProperties,
  input: { width: '100%', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6, fontSize: 13, background: 'white', boxSizing: 'border-box' as const } as React.CSSProperties,
  hint: { marginTop: 4, fontSize: 11, color: 'var(--text-muted)' } as React.CSSProperties,
  badge: { padding: '2px 7px', borderRadius: 3, color: 'white', fontSize: 10, fontWeight: 600 } as React.CSSProperties,
  unsupported: { marginBottom: 16, padding: 12, background: 'var(--warning-bg)', color: 'var(--warning)', border: '1px solid var(--warning)', borderRadius: 6, fontSize: 12 } as React.CSSProperties,
};

function Collapsible({ title, subtitle, defaultOpen, summary, badge, children }: { title: string; subtitle: string; defaultOpen: boolean; summary?: string; badge?: React.ReactNode; children: React.ReactNode }): React.JSX.Element {
  const [open, setOpen] = useState(defaultOpen);
  return <section style={{ marginBottom: 24 }}>
    <div style={{ ...styles.header, cursor: 'pointer', userSelect: 'none' }} onClick={() => setOpen(!open)}>
      <div>
        <h3 style={styles.title}><span style={{ marginRight: 6, fontSize: 11, color: 'var(--text-muted)' }}>{open ? '▼' : '▶'}</span>{title}</h3>
        <div style={styles.subtitle}>{subtitle}</div>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>{badge}{summary && <strong style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{summary}</strong>}</div>
    </div>
    {open && children}
  </section>;
}

function NumberField({ label, value, onChange, disabled, hint, placeholder }: { label: string; value: number; onChange: (value: number) => void; disabled?: boolean; hint?: string; placeholder?: string }): React.JSX.Element {
  return <div><label style={styles.label}>{label}</label><input style={styles.input} type="number" value={value || ''} disabled={disabled} min={0} max={MAX_MONEY} placeholder={placeholder ?? '0'} onChange={(event) => onChange(money(Number(event.target.value)))} />{hint && <div style={styles.hint}>{hint}</div>}</div>;
}
function TextField({ label, value, onChange, disabled, maxLength, placeholder, hint, type = 'text', required, pattern }: { label: string; value: string; onChange: (value: string) => void; disabled?: boolean; maxLength?: number; placeholder?: string; hint?: string; type?: React.HTMLInputTypeAttribute; required?: boolean; pattern?: string }): React.JSX.Element {
  return <div><label style={styles.label}>{label}{required ? ' *' : ''}</label><input style={styles.input} type={type} value={value} disabled={disabled} required={required} pattern={pattern} maxLength={maxLength} placeholder={placeholder} onChange={(event) => onChange(event.target.value)} />{hint && <div style={styles.hint}>{hint}</div>}</div>;
}
function SelectField<T extends string>({ label, value, onChange, disabled, options, hint }: { label: string; value: T; onChange: (value: T) => void; disabled?: boolean; options: readonly { value: T; label: string }[]; hint?: string }): React.JSX.Element {
  return <div><label style={styles.label}>{label}</label><select style={styles.input} value={value} disabled={disabled} onChange={(event) => onChange(event.target.value as T)}>{options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select>{hint && <div style={styles.hint}>{hint}</div>}</div>;
}

const DISEASE_OPTIONS = [
  { value: 'a', label: 'a — Dementia' }, { value: 'b', label: 'b — Dystonia Musculorum Deformans' }, { value: 'c', label: 'c — Motor Neuron Disease' }, { value: 'd', label: 'd — Ataxia' }, { value: 'e', label: 'e — Chorea' }, { value: 'f', label: 'f — Hemiballismus' }, { value: 'g', label: 'g — Aphasia' }, { value: 'h', label: "h — Parkinson's Disease" }, { value: 'i', label: 'i — Malignant Cancers' }, { value: 'j', label: 'j — Full Blown AIDS' }, { value: 'k', label: 'k — Chronic Renal Failure' }, { value: 'l', label: 'l — Hematological Disorders' }, { value: 'm', label: 'm — Hemophilia' }, { value: 'n', label: 'n — Thalassaemia' },
] as const;
const NATURE_OPTIONS = [{ value: '1', label: '1 — Disability' }, { value: '2', label: '2 — Severe disability' }] as const;
const TYPE_OPTIONS = [{ value: '1', label: '1 — Autism, cerebral palsy or multiple disabilities' }, { value: '2', label: '2 — Other disability' }] as const;
const USERTYPE_OPTIONS = [{ value: '', label: '-- Select --' }, { value: '1', label: '1 — Self / Dependent' }, { value: '2', label: '2 — Senior Citizen (Self)' }] as const;
const DEPENDENT_BASE = [{ value: '', label: '-- Select --' }, { value: '1', label: '1 — Spouse' }, { value: '2', label: '2 — Son' }, { value: '3', label: '3 — Daughter' }, { value: '4', label: '4 — Father' }, { value: '5', label: '5 — Mother' }, { value: '6', label: '6 — Brother' }, { value: '7', label: '7 — Sister' }] as const;
const HUF_MEMBER_OPTION = { value: '8', label: '8 — Member of the HUF (HUF filer only)' } as const;
const YN_OPTIONS = [{ value: 'Y', label: 'Y — Yes' }, { value: 'N', label: 'N — No' }] as const;

/** Per-form DependentType options; ITR-2/3 include the HUF-member value 8. */
function dependentOptions(form: ItrForm) {
  return form === 'ITR-2' || form === 'ITR-3' ? [...DEPENDENT_BASE, HUF_MEMBER_OPTION] : DEPENDENT_BASE;
}

const GGA_CLAUSE_OPTIONS: ReadonlyArray<{ value: Section80GGAClause; label: string }> = [
  { value: '80GGA2a', label: '80GGA(2)(a) — scientific research association' },
  { value: '80GGA2aa', label: '80GGA(2)(aa) — social science/statistical research' },
  { value: '80GGA2b', label: '80GGA(2)(b) — rural development association' },
  { value: '80GGA2bb', label: '80GGA(2)(bb) — approved eligible project' },
  { value: '80GGA2c', label: '80GGA(2)(c) — conservation/afforestation' },
  { value: '80GGA2cc', label: '80GGA(2)(cc) — notified afforestation fund' },
  { value: '80GGA2d', label: '80GGA(2)(d) — rural development fund' },
  { value: '80GGA2e', label: '80GGA(2)(e) — urban poverty eradication fund' },
];

let rowIdCounter = 0;
function nextRowId(prefix: string): string {
  rowIdCounter += 1;
  return `${prefix}-${Date.now().toString(36)}-${rowIdCounter}`;
}

function empty80GGAEntry(): Schedule80GGAEntry {
  return { id: nextRowId('80gga'), relevantClause: '80GGA2a', doneeName: '', doneePAN: '', addressLine: '', city: '', stateCode: '', pinCode: '', cashAmount: 0, otherModeAmount: 0 };
}
function empty80GGCEntry(): Schedule80GGCEntry {
  return { id: nextRowId('80ggc'), cashAmount: 0, otherModeAmount: 0, contributionDate: '', transactionRef: '', ifscCode: '', politicalPartyName: '', politicalPartyPAN: '' };
}

function empty80CCCEntry(): PensionContribution80CCC {
  return { id: nextRowId('80ccc'), identifierType: 'OTHPRAN', identifierName: '', amount: 0 };
}

function Schedule80CCCEditor({ entries, onChange }: { entries: PensionContribution80CCC[]; onChange: (entries: PensionContribution80CCC[]) => void }): React.JSX.Element {
  const update = (id: string, patch: Partial<PensionContribution80CCC>): void => onChange(entries.map((entry) => entry.id === id ? { ...entry, ...patch } : entry));
  const remove = (id: string): void => onChange(entries.filter((entry) => entry.id !== id));
  return <div style={{ marginTop: 16 }}>
    <h4 style={{ ...styles.panelTitle, marginBottom: 10 }}>Section 80CCC pension contributions</h4>
    {entries.map((entry, index) => <div key={entry.id} style={{ marginBottom: 12, padding: 12, border: '1px solid var(--border)', borderRadius: 6 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
        <strong style={{ fontSize: 12 }}>Contribution #{index + 1}</strong>
        <button type="button" onClick={() => remove(entry.id)} style={{ border: '1px solid var(--border)', background: 'white', padding: '2px 8px', fontSize: 11, borderRadius: 4, cursor: 'pointer' }}>Remove</button>
      </div>
      <div style={styles.grid}>
        <SelectField label="Identifier type" value={entry.identifierType} options={[{ value: 'PRAN', label: 'PRAN' }, { value: 'OTHPRAN', label: 'Other policy / identifier' }]} onChange={(value) => update(entry.id, { identifierType: value })} />
        <TextField label="Identifier / policy number" value={entry.identifierName} maxLength={125} placeholder="Policy number or PRAN" onChange={(value) => update(entry.id, { identifierName: value })} />
        <NumberField label="Contribution amount (₹)" value={entry.amount} onChange={(value) => update(entry.id, { amount: value })} />
      </div>
    </div>)}
    <button type="button" onClick={() => onChange([...entries, empty80CCCEntry()])} style={{ border: '1px solid var(--border)', background: 'var(--bg)', padding: '6px 12px', fontSize: 12, borderRadius: 6, cursor: 'pointer' }}>+ Add pension contribution</button>
  </div>;
}

function Schedule80GGAEditor({ entries, onChange }: { entries: Schedule80GGAEntry[]; onChange: (entries: Schedule80GGAEntry[]) => void }): React.JSX.Element {
  const update = (id: string, patch: Partial<Schedule80GGAEntry>): void => onChange(entries.map((e) => e.id === id ? { ...e, ...patch } : e));
  const remove = (id: string): void => onChange(entries.filter((e) => e.id !== id));
  const add = (): void => onChange([...entries, empty80GGAEntry()]);
  const total = entries.reduce((sum, e) => sum + money(e.cashAmount) + money(e.otherModeAmount), 0);
  return <div>
    {entries.length === 0 && <div style={{ ...styles.hint, marginBottom: 8 }}>No 80GGA donation rows yet. Click “Add donation” to add the first row.</div>}
    {entries.map((entry, index) => (
      <div key={entry.id} style={{ marginBottom: 16, padding: 12, border: '1px solid var(--border)', borderRadius: 6 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
          <strong style={{ fontSize: 12 }}>Donation #{index + 1}</strong>
          <button type="button" onClick={() => remove(entry.id)} style={{ border: '1px solid var(--border)', background: 'white', padding: '2px 8px', fontSize: 11, borderRadius: 4, cursor: 'pointer' }}>Remove</button>
        </div>
        <div style={styles.grid}>
          <SelectField label="Relevant clause" value={entry.relevantClause} options={GGA_CLAUSE_OPTIONS} onChange={(value) => update(entry.id, { relevantClause: value })} />
          <TextField label="Donee name" value={entry.doneeName} maxLength={125} placeholder="Research association / fund name" onChange={(value) => update(entry.id, { doneeName: value })} />
          <TextField label="Donee PAN" value={entry.doneePAN} maxLength={10} placeholder="ABCDE1234F" onChange={(value) => update(entry.id, { doneePAN: value.toUpperCase() })} />
          <TextField label="Address line" value={entry.addressLine} maxLength={200} placeholder="Donee address" onChange={(value) => update(entry.id, { addressLine: value })} />
          <TextField label="City / District" value={entry.city} maxLength={50} placeholder="City" onChange={(value) => update(entry.id, { city: value })} />
          <SelectField label="State code" value={entry.stateCode} options={[{ value: '' as const, label: '-- Select state --' }, ...INDIAN_STATE_CODE_OPTIONS.map(({ code, label }) => ({ value: code, label: `${code} — ${label}` }))]} onChange={(value) => update(entry.id, { stateCode: value as StateCode | '' })} hint="CBDT Indian state code (01-37)" />
          <TextField label="Pin code" value={entry.pinCode} maxLength={6} placeholder="6-digit PIN" onChange={(value) => update(entry.id, { pinCode: value.replace(/\D/g, '').slice(0, 6) })} />
          <NumberField label="Cash donation (₹)" value={entry.cashAmount} hint="Cash not allowed for 80GGA — keep 0" onChange={(value) => update(entry.id, { cashAmount: value })} />
          <NumberField label="Non-cash donation (₹)" value={entry.otherModeAmount} onChange={(value) => update(entry.id, { otherModeAmount: value })} />
        </div>
      </div>
    ))}
    <button type="button" onClick={add} style={{ border: '1px solid var(--border)', background: 'var(--bg)', padding: '6px 12px', fontSize: 12, borderRadius: 6, cursor: 'pointer' }}>+ Add donation</button>
    <div style={{ ...styles.hint, marginTop: 8 }}>Total claimed: <strong>{inr(total)}</strong></div>
  </div>;
}

function Schedule80GGCEditor({ entries, onChange }: { entries: Schedule80GGCEntry[]; onChange: (entries: Schedule80GGCEntry[]) => void }): React.JSX.Element {
  const update = (id: string, patch: Partial<Schedule80GGCEntry>): void => onChange(entries.map((e) => e.id === id ? { ...e, ...patch } : e));
  const remove = (id: string): void => onChange(entries.filter((e) => e.id !== id));
  const add = (): void => onChange([...entries, empty80GGCEntry()]);
  const total = entries.reduce((sum, e) => sum + money(e.cashAmount) + money(e.otherModeAmount), 0);
  return <div>
    {entries.length === 0 && <div style={{ ...styles.hint, marginBottom: 8 }}>No 80GGC contribution rows yet. Click “Add contribution” to add the first row.</div>}
    {entries.map((entry, index) => (
      <div key={entry.id} style={{ marginBottom: 16, padding: 12, border: '1px solid var(--border)', borderRadius: 6 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
          <strong style={{ fontSize: 12 }}>Contribution #{index + 1}</strong>
          <button type="button" onClick={() => remove(entry.id)} style={{ border: '1px solid var(--border)', background: 'white', padding: '2px 8px', fontSize: 11, borderRadius: 4, cursor: 'pointer' }}>Remove</button>
        </div>
        <div style={styles.grid}>
          <TextField label="Political party name" value={entry.politicalPartyName} maxLength={125} placeholder="Registered political party" required onChange={(value) => update(entry.id, { politicalPartyName: value })} />
          <TextField label="Political party PAN" value={entry.politicalPartyPAN} maxLength={10} pattern="[A-Z]{5}[0-9]{4}[A-Z]" placeholder="ABCDE1234F" required onChange={(value) => update(entry.id, { politicalPartyPAN: value.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 10) })} />
          <NumberField label="Cash contribution (₹)" value={entry.cashAmount} hint="Cash not allowed for 80GGC — keep 0" onChange={(value) => update(entry.id, { cashAmount: value })} />
          <NumberField label="Non-cash contribution (₹)" value={entry.otherModeAmount} onChange={(value) => update(entry.id, { otherModeAmount: value })} />
          <TextField label="Contribution date" value={entry.contributionDate} type="date" required onChange={(value) => update(entry.id, { contributionDate: value })} />
          <TextField label="Transaction reference" value={entry.transactionRef} maxLength={50} placeholder="Cheque / UTR no." required onChange={(value) => update(entry.id, { transactionRef: value })} />
          <TextField label="IFSC code" value={entry.ifscCode} maxLength={11} pattern="[A-Z]{4}0[A-Z0-9]{6}" placeholder="AAAA0XXXXXX" required onChange={(value) => update(entry.id, { ifscCode: value.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 11) })} />
        </div>
      </div>
    ))}
    <button type="button" onClick={add} style={{ border: '1px solid var(--border)', background: 'var(--bg)', padding: '6px 12px', fontSize: 12, borderRadius: 6, cursor: 'pointer' }}>+ Add contribution</button>
    <div style={{ ...styles.hint, marginTop: 8 }}>Total claimed: <strong>{inr(total)}</strong></div>
  </div>;
}

export default function DeductionsWorkspace({ form, regime, section80C, pensionContribution80CCC, section80D, section80G, loans, chapterVIA, onChangeChapterVIA, onChangePensionContribution80CCC, schedule80GGA, schedule80GGC, onChangeSchedule80GGA, onChangeSchedule80GGC, managers, totalDeductions, deductionBreakdown }: DeductionsWorkspaceProps): React.JSX.Element {
  const caps = FORM_CAPS[form];
  const isNew = regime === 'new';
  // ITR-2/3 Schedule80DD/80U also collect Form10IAFilingDate and FormAckNum11A; ITR-1/4 only Form10IAAckNum.
  const fullForm10IA = form === 'ITR-2' || form === 'ITR-3';
  const dependentOpts = dependentOptions(form);
  const patch = (next: Partial<ChapterVIA>): void => onChangeChapterVIA({ ...chapterVIA, ...next });
  const patchBusiness = (next: Partial<BusinessDeductions>): void => onChangeChapterVIA({ ...chapterVIA, businessDeductions: { ...chapterVIA.businessDeductions, ...next } });

  // Sum of scalar Chapter VI-A fields the user entered (display only; backend owns statutory caps).
  const viaTotal = useMemo(() => {
    const v = chapterVIA;
    return money(v.section80CCC) + money(v.section80CCDEmployeeOrSE) + money(v.section80CCD1B) + money(v.section80CCDEmployer)
      + money(v.section80D) + money(v.section80DD) + money(v.section80DDB) + money(v.section80E) + money(v.section80EE) + money(v.section80EEA) + money(v.section80EEB)
      + money(v.section80G) + money(v.section80GG) + money(v.section80GGA) + money(v.section80GGC) + money(v.section80U) + money(v.section80QQB) + money(v.section80RRB)
      + money(v.section80TTA) + money(v.section80TTB) + money(v.anyOtherSection80CCH)
      + (caps.business ? money(chapterVIA.businessDeductions.section80IA) + money(chapterVIA.businessDeductions.section80IAB) + money(chapterVIA.businessDeductions.section80IB) + money(chapterVIA.businessDeductions.section80IBA) + money(chapterVIA.businessDeductions.section80IC) + money(chapterVIA.businessDeductions.section80JJA) + money(chapterVIA.businessDeductions.section80JJAA) : 0);
  }, [chapterVIA, caps.business]);

  const eligible = (section: string): number | null => (deductionBreakdown && typeof deductionBreakdown[section] === 'number') ? deductionBreakdown[section] : null;

  if (isNew) return <div>
    <div style={{ marginBottom: 16, padding: 12, background: 'var(--info-bg)', color: 'var(--info)', border: '1px solid var(--info)', borderRadius: 6, fontSize: 12 }}>
      New tax regime disallows most Chapter VI-A deductions. Only <strong>80CCD(2)</strong> (employer NPS contribution) remains deductible. Switch to the old regime to claim 80C, 80D, 80G, 80E and other sections.
    </div>
    <div style={styles.panel}>
      <div style={styles.panelHeader}><h4 style={styles.panelTitle}>Employer NPS — Section 80CCD(2)</h4><span style={{ ...styles.badge, background: 'var(--info)' }}>New regime</span></div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 16 }}>
        <NumberField label="Employer NPS contribution (₹)" value={chapterVIA.section80CCDEmployer} disabled={false} hint="10% of (basic + DA) for non-govt; 14% for govt employees" onChange={(value) => patch({ section80CCDEmployer: value })} />
        <TextField label="PRAN" value={chapterVIA.pranNumber} maxLength={12} placeholder="12-digit PRAN" onChange={(value) => patch({ pranNumber: value.replace(/\D/g, '').slice(0, 12) })} />
      </div>
    </div>
    <div style={styles.panel}><div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}><span>Total deductions</span><strong>{inr(totalDeductions ?? chapterVIA.section80CCDEmployer)}</strong></div></div>
  </div>;

  return <div>
    <div style={{ marginBottom: 16 }}><h3 style={styles.title}>Deductions under Chapter VI-A (Schedule VIA)</h3><div style={styles.subtitle}>AY 2026-27 · {form} · backend applies statutory ceilings; enter gross eligible amounts</div></div>

    <Collapsible title="Section 80C / 80CCC / 80CCD — savings & pension" subtitle="PF, PPF, ELSS, LIC, NSC, NPS; aggregate ceiling ₹1.5L under 80CCE" defaultOpen summary={inr(chapterVIA.section80C + chapterVIA.section80CCC + chapterVIA.section80CCDEmployeeOrSE + chapterVIA.section80CCD1B)} badge={<span style={{ ...styles.badge, background: 'var(--success)' }}>80CCE ₹1.5L</span>}>
      <Section80CManager data={{ investments: section80C }} onChange={managers.section80C} backendEligible={eligible('80C')} />
      <Schedule80CCCEditor entries={pensionContribution80CCC} onChange={(entries) => {
        const total = entries.reduce((sum, entry) => sum + money(entry.amount), 0);
        onChangePensionContribution80CCC(entries);
        patch({ section80CCC: total, pensionContribution80CCC: total });
      }} />
      <div style={{ ...styles.grid, marginTop: 16 }}>
        <NumberField label="80CCC total from detail rows (₹)" value={chapterVIA.section80CCC} hint="Auto-derived from required identifier rows; part of the 80CCE ₹1.5L pool" disabled onChange={() => undefined} />
        <NumberField label="80CCD(1) — self NPS contribution (₹)" value={chapterVIA.section80CCDEmployeeOrSE} hint="Employee/Self-employed; 10% of salary / 20% of gross income" onChange={(value) => patch({ section80CCDEmployeeOrSE: value })} />
        <NumberField label="80CCD(1B) — additional NPS (₹)" value={chapterVIA.section80CCD1B} hint="Max ₹50,000 over and above 80CCE ceiling" onChange={(value) => patch({ section80CCD1B: value })} />
        <NumberField label="80CCD(2) — employer NPS (₹)" value={chapterVIA.section80CCDEmployer} hint="10% non-govt / 14% govt; excluded from 80CCE ceiling" onChange={(value) => patch({ section80CCDEmployer: value })} />
        <TextField label="PRAN" value={chapterVIA.pranNumber} maxLength={12} placeholder="12-digit PRAN" onChange={(value) => patch({ pranNumber: value.replace(/\D/g, '').slice(0, 12) })} />
      </div>
    </Collapsible>

    <Collapsible title="Section 80D — health insurance & preventive checkup" subtitle="Self/family and parents; senior-citizen ceilings apply" defaultOpen summary={inr(chapterVIA.section80D)} badge={<span style={{ ...styles.badge, background: 'var(--success)' }}>80D</span>}>
      <Section80DManager data={section80D} onChange={managers.section80D} backendEligible={eligible('80D')} />
    </Collapsible>

    <Collapsible title="Section 80DD / 80DDB / 80U — disability & medical treatment" subtitle="Disabled dependent (80DD), specified disease (80DDB), self disability (80U)" defaultOpen={false} summary={inr(chapterVIA.section80DD + chapterVIA.section80DDB + chapterVIA.section80U)} badge={<span style={{ ...styles.badge, background: 'var(--info)' }}>Medical</span>}>
      <h4 style={{ ...styles.panelTitle, marginBottom: 10 }}>Section 80DD — disabled dependent</h4>
      <div style={styles.grid}>
        <NumberField label="80DD deduction amount (₹)" value={chapterVIA.section80DD} hint="Flat ₹75,000 (disability) / ₹1,25,000 (severe)" onChange={(value) => patch({ section80DD: value })} />
        <SelectField label="Nature of disability" value={chapterVIA.section80DDNatureOfDisability} options={NATURE_OPTIONS} onChange={(value) => patch({ section80DDNatureOfDisability: value })} />
        <SelectField label="Type of disability" value={chapterVIA.section80DDTypeOfDisability} options={TYPE_OPTIONS} onChange={(value) => patch({ section80DDTypeOfDisability: value })} />
        <SelectField label="Dependent type" value={chapterVIA.section80DDDependentType} options={dependentOpts} onChange={(value) => patch({ section80DDDependentType: value })} hint={fullForm10IA ? 'Includes HUF member for HUF filers' : undefined} />
        <TextField label="Dependent PAN" value={chapterVIA.section80DDDependentPAN} maxLength={10} placeholder="ABCDE1234F" onChange={(value) => patch({ section80DDDependentPAN: value.toUpperCase() })} />
        <TextField label="Dependent Aadhaar" value={chapterVIA.section80DDDependentAadhaar} maxLength={12} placeholder="12-digit Aadhaar" onChange={(value) => patch({ section80DDDependentAadhaar: value.replace(/\D/g, '').slice(0, 12) })} />
        <TextField label="UDID number" value={chapterVIA.section80DDUDIDNumber} maxLength={18} placeholder="Unique Disability ID" onChange={(value) => patch({ section80DDUDIDNumber: value })} />
        <SelectField label="Form 10-IA filed?" value={chapterVIA.section80DDForm10IA.filed} options={YN_OPTIONS} onChange={(value) => patch({ section80DDForm10IA: { ...chapterVIA.section80DDForm10IA, filed: value } })} />
        <TextField label="Form 10-IA acknowledgement no." value={chapterVIA.section80DDForm10IA.acknowledgementNumber} maxLength={15} placeholder="Form 10-IA ack number" onChange={(value) => patch({ section80DDForm10IA: { ...chapterVIA.section80DDForm10IA, acknowledgementNumber: value } })} />
        {fullForm10IA && <TextField label="Form 10-IA filing date" value={chapterVIA.section80DDForm10IA.filingDate ?? ''} placeholder="YYYY-MM-DD" onChange={(value) => patch({ section80DDForm10IA: { ...chapterVIA.section80DDForm10IA, filingDate: value } })} hint="ITR-2/3 only" />}
        {fullForm10IA && <TextField label="Form 10-IA / 11A ack. no." value={chapterVIA.section80DDForm10IA.formAckNum11A} maxLength={15} placeholder="FormAckNum11A" onChange={(value) => patch({ section80DDForm10IA: { ...chapterVIA.section80DDForm10IA, formAckNum11A: value } })} hint="ITR-2/3 only" />}
      </div>
      <h4 style={{ ...styles.panelTitle, marginTop: 20, marginBottom: 10 }}>Section 80DDB — specified disease treatment</h4>
      <div style={styles.grid}>
        <NumberField label="80DDB amount (₹)" value={chapterVIA.section80DDB} hint="Max ₹40,000 (₹1,00,000 senior citizen)" onChange={(value) => patch({ section80DDB: value })} />
        <SelectField label="User type" value={chapterVIA.section80DDBUserType} options={USERTYPE_OPTIONS} onChange={(value) => patch({ section80DDBUserType: value })} />
        <SelectField label="Disease code" value={chapterVIA.section80DDBNameOfSpecDisease} options={DISEASE_OPTIONS} onChange={(value) => patch({ section80DDBNameOfSpecDisease: value })} hint="Specified disease under Rule 3D" />
      </div>
      <h4 style={{ ...styles.panelTitle, marginTop: 20, marginBottom: 10 }}>Section 80U — self disability</h4>
      <div style={styles.grid}>
        <NumberField label="80U deduction amount (₹)" value={chapterVIA.section80U} hint="Flat ₹75,000 (disability) / ₹1,25,000 (severe)" onChange={(value) => patch({ section80U: value })} />
        <SelectField label="Nature of disability" value={chapterVIA.section80UNatureOfDisability} options={NATURE_OPTIONS} onChange={(value) => patch({ section80UNatureOfDisability: value })} />
        <SelectField label="Type of disability" value={chapterVIA.section80UTypeOfDisability} options={TYPE_OPTIONS} onChange={(value) => patch({ section80UTypeOfDisability: value })} />
        <TextField label="UDID number" value={chapterVIA.section80UUDIDNumber} maxLength={18} placeholder="Unique Disability ID" onChange={(value) => patch({ section80UUDIDNumber: value })} />
        <SelectField label="Form 10-IA filed?" value={chapterVIA.section80UForm10IA.filed} options={YN_OPTIONS} onChange={(value) => patch({ section80UForm10IA: { ...chapterVIA.section80UForm10IA, filed: value } })} />
        <TextField label="Form 10-IA acknowledgement no." value={chapterVIA.section80UForm10IA.acknowledgementNumber} maxLength={15} placeholder="Form 10-IA ack number" onChange={(value) => patch({ section80UForm10IA: { ...chapterVIA.section80UForm10IA, acknowledgementNumber: value } })} />
        {fullForm10IA && <TextField label="Form 10-IA filing date" value={chapterVIA.section80UForm10IA.filingDate ?? ''} placeholder="YYYY-MM-DD" onChange={(value) => patch({ section80UForm10IA: { ...chapterVIA.section80UForm10IA, filingDate: value } })} hint="ITR-2/3 only" />}
        {fullForm10IA && <TextField label="Form 10-IA / 11A ack. no." value={chapterVIA.section80UForm10IA.formAckNum11A} maxLength={15} placeholder="FormAckNum11A" onChange={(value) => patch({ section80UForm10IA: { ...chapterVIA.section80UForm10IA, formAckNum11A: value } })} hint="ITR-2/3 only" />}
      </div>
    </Collapsible>

    <Collapsible title="Section 80G — donations" subtitle="Cash donations capped at ₹2,000; PAN-required donees for 100%/50% approval categories" defaultOpen={false} summary={inr(chapterVIA.section80G)} badge={<span style={{ ...styles.badge, background: 'var(--gold)' }}>80G</span>}>
      <DonationEntryManager entries={section80G} onChange={managers.donations} backendEligible={eligible('80G')} />
    </Collapsible>

    <Collapsible title="Section 80GGA / 80GGC — scientific research & political contributions" subtitle="Donations for scientific research/rural development (80GGA) and political parties/electoral trusts (80GGC)" defaultOpen={false} summary={inr(chapterVIA.section80GGA + chapterVIA.section80GGC)} badge={<span style={{ ...styles.badge, background: 'var(--gold)' }}>{caps.gga ? 'Research/Political' : 'Political only'}</span>}>
      {!caps.gga && <div style={styles.unsupported}>Section 80GGA is not available on {form}. Only 80GGC applies.</div>}
      {caps.gga && <>
        <h4 style={{ ...styles.panelTitle, marginBottom: 10 }}>Section 80GGA — scientific research / rural development donations</h4>
        <Schedule80GGAEditor entries={schedule80GGA} onChange={onChangeSchedule80GGA} />
        <NumberField label="80GGA aggregate (₹)" value={chapterVIA.section80GGA} hint="Auto-derived from detail rows; 100% deductible, cash not allowed" disabled onChange={() => undefined} />
      </>}
      <h4 style={{ ...styles.panelTitle, marginTop: 20, marginBottom: 10 }}>Section 80GGC — political party / electoral trust contributions</h4>
      <Schedule80GGCEditor entries={schedule80GGC} onChange={onChangeSchedule80GGC} />
      <NumberField label="80GGC aggregate (₹)" value={chapterVIA.section80GGC} hint="Auto-derived from detail rows; 100% deductible, cash not allowed" disabled onChange={() => undefined} />
    </Collapsible>

    <Collapsible title="Section 80E / 80EE / 80EEA / 80EEB — education & home/EV loans" subtitle="Education loan interest (80E), first-home loan interest (80EE/80EEA), electric vehicle loan interest (80EEB)" defaultOpen={false} summary={inr(chapterVIA.section80E + chapterVIA.section80EE + chapterVIA.section80EEA + chapterVIA.section80EEB)} badge={<span style={{ ...styles.badge, background: 'var(--info)' }}>Loans</span>}>
      <DeductionLoanManager data={loans} onChange={managers.deductionLoans} />
    </Collapsible>

    <Collapsible title="Section 80GG — rent paid (no HRA received)" subtitle="Least of: rent − 10% income, ₹2,000/month, 25% of income" defaultOpen={false} summary={inr(chapterVIA.section80GG)}>
      <div style={styles.grid}>
        <NumberField label="80GG deduction amount (₹)" value={chapterVIA.section80GG} hint="Only when HRA is not received u/s 10(13A)" onChange={(value) => patch({ section80GG: value })} />
        <NumberField label="Total rent paid (₹)" value={chapterVIA.section80GGRentPaid} hint="Annual rent paid for the computation reference" onChange={(value) => patch({ section80GGRentPaid: value })} />
      </div>
    </Collapsible>

    {(caps.qqb || caps.rrb) && <Collapsible title="Section 80QQB / 80RRB — royalty & patent income" subtitle="Author royalty (80QQB) and patent royalties (80RRB); ITR-2/3 only" defaultOpen={false} summary={inr(chapterVIA.section80QQB + chapterVIA.section80RRB)} badge={<span style={{ ...styles.badge, background: 'var(--info)' }}>Royalty</span>}>
      <div style={styles.grid}>
        <NumberField label="80QQB — royalty income (₹)" value={chapterVIA.section80QQB} hint="Max ₹3,00,000" onChange={(value) => patch({ section80QQB: value })} />
        <TextField label="Form 10-CD acknowledgement no. (80QQB)" value={chapterVIA.section80QQBForm10CCDAckNum} maxLength={15} placeholder="Form 10-CD ack number" onChange={(value) => patch({ section80QQBForm10CCDAckNum: value })} />
        <NumberField label="80RRB — patent royalty income (₹)" value={chapterVIA.section80RRB} hint="Max ₹3,00,000 for resident patentees" onChange={(value) => patch({ section80RRB: value })} />
        <TextField label="Form 10-CCE acknowledgement no. (80RRB)" value={chapterVIA.section80RRBForm10CCEAckNum} maxLength={15} placeholder="Form 10-CCE ack number" onChange={(value) => patch({ section80RRBForm10CCEAckNum: value })} />
      </div>
    </Collapsible>}

    <Collapsible title="Section 80TTA / 80TTB — savings account interest" subtitle="80TTA: ₹10,000 (non-senior); 80TTB: ₹50,000 (senior citizen, incl. FD/RD)" defaultOpen={false} summary={inr(chapterVIA.section80TTA + chapterVIA.section80TTB)} badge={<span style={{ ...styles.badge, background: 'var(--info)' }}>Interest</span>}>
      <div style={styles.grid}>
        <NumberField label="80TTA — savings account interest (₹)" value={chapterVIA.section80TTA} hint="Max ₹10,000; non-senior individuals/HUF" onChange={(value) => patch({ section80TTA: value })} />
        <NumberField label="80TTB — senior citizen deposit interest (₹)" value={chapterVIA.section80TTB} hint="Max ₹50,000; FD/RD/savings for senior citizens" onChange={(value) => patch({ section80TTB: value })} />
      </div>
    </Collapsible>

    {caps.business && <Collapsible title="Part B/C — business-linked deductions (80IA family)" subtitle="ITR-3 only: infrastructure, power, SEZ, employment, etc." defaultOpen={false} summary={inr(chapterVIA.businessDeductions.totalPartBChapterVIA + chapterVIA.businessDeductions.totalPartCChapterVIA)} badge={<span style={{ ...styles.badge, background: 'var(--gold)' }}>ITR-3</span>}>
      <div style={styles.grid}>
        <NumberField label="80IA — infra / power / telecom profits (₹)" value={chapterVIA.businessDeductions.section80IA} onChange={(value) => patchBusiness({ section80IA: value })} />
        <NumberField label="80IAB — SEZ developer profits (₹)" value={chapterVIA.businessDeductions.section80IAB} onChange={(value) => patchBusiness({ section80IAB: value })} />
        <NumberField label="80IB — other industrial undertakings (₹)" value={chapterVIA.businessDeductions.section80IB} onChange={(value) => patchBusiness({ section80IB: value })} />
        <NumberField label="80IBA — 100% affordable housing (₹)" value={chapterVIA.businessDeductions.section80IBA} onChange={(value) => patchBusiness({ section80IBA: value })} />
        <NumberField label="80IC — special category state undertakings (₹)" value={chapterVIA.businessDeductions.section80IC} onChange={(value) => patchBusiness({ section80IC: value })} />
        <NumberField label="80JJA — business of collecting biodegradable waste (₹)" value={chapterVIA.businessDeductions.section80JJA} onChange={(value) => patchBusiness({ section80JJA: value })} />
        <NumberField label="80JJAA — additional employee cost (₹)" value={chapterVIA.businessDeductions.section80JJAA} hint="30% of additional employee salary for 3 years" onChange={(value) => patchBusiness({ section80JJAA: value })} />
      </div>
    </Collapsible>}

    <Collapsible title="Other disclosures — Form 10-BA & Any other section 80CCH" subtitle="Form 10-BA for 80GG; any other Chapter VI-A deduction not listed above" defaultOpen={false}>
      <div style={styles.grid}>
        <TextField label="Form 10-BA acknowledgement no." value={chapterVIA.form10BAAckNum} maxLength={15} placeholder="Required when claiming 80GG" onChange={(value) => patch({ form10BAAckNum: value })} />
        <NumberField label="Any other section 80CCH deduction (₹)" value={chapterVIA.anyOtherSection80CCH} onChange={(value) => patch({ anyOtherSection80CCH: value })} />
        <TextField label="Description of other 80CCH deduction" value={chapterVIA.anyOtherSection80CCHDescription} maxLength={125} placeholder="Nature of the other deduction" onChange={(value) => patch({ anyOtherSection80CCHDescription: value })} />
      </div>
    </Collapsible>

    <div style={styles.panel}>
      <div style={styles.panelHeader}><h4 style={styles.panelTitle}>Deductions review</h4><span style={{ ...styles.badge, background: 'var(--success)' }}>{form}</span></div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 6 }}><span>Chapter VI-A aggregate (user-entered)</span><strong>{inr(viaTotal)}</strong></div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}><span>Total deductions (backend)</span><strong>{inr(totalDeductions ?? viaTotal)}</strong></div>
    </div>
  </div>;
}
