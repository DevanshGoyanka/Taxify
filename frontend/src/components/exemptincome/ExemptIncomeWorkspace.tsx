import React, { useMemo, useState } from 'react';
import type {
  AgriculturalLandParcel, DtaaExemptIncomeEntry, ExemptIncomeCategory,
  ExemptIncomeEntry, ExemptIncomeSchedule, ExemptIncomeSubCategory,
} from '../../domain/returns/types';
import type { ItrForm } from '../../domain/eligibility';

interface ExemptIncomeWorkspaceProps {
  form: ItrForm;
  schedule: ExemptIncomeSchedule;
  onChange: (next: ExemptIncomeSchedule) => void;
  disabled?: boolean;
}

interface CodeOption<T extends string> { value: T; label: string; }

const MAX_MONEY = 99_999_999_999_999;
const id = (prefix: string): string => `${prefix}-${crypto.randomUUID()}`;
const money = (value: unknown): number => typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : 0;
const inr = (value: number): string => `₹${money(value).toLocaleString('en-IN')}`;

const CATEGORY_OPTIONS: readonly CodeOption<ExemptIncomeCategory>[] = [
  { value: 'AGRI', label: 'AGRI — Agricultural income' },
  { value: 'GOVC', label: 'GOVC — Government compensation / specified receipt' },
  { value: 'ISI', label: 'ISI — Income from specified investments' },
  { value: 'SSRA', label: 'SSRA — Statutory / specified retirement amount' },
  { value: 'SRSC', label: 'SRSC — Specified compensation / receipt' },
  { value: 'SRST', label: 'SRST — Share / specified trust income' },
  { value: 'SRPC', label: 'SRPC — Specified provident / pension contribution' },
  { value: 'OTH', label: 'OTH — Other exempt income' },
  { value: 'OTHN', label: 'OTHN — Other exempt income of non-resident' },
];

const SUBCATEGORY_OPTIONS: readonly CodeOption<ExemptIncomeSubCategory>[] = [
  ['10(1)','Agricultural income'], ['10(2)','Share from HUF / specified share'], ['10(2A)','Share of profit from firm or LLP'],
  ['10(4)(i)','Interest / income specified under section 10(4)(i)'], ['10(4)(ii)','NRE-account interest u/s 10(4)(ii)'],
  ['10(4B)','Specified savings-certificate income'], ['10(4C)','Specified non-resident income'], ['10(4E)','Specified non-resident account income'],
  ['10(4F)','Specified fund income'], ['10(4G)','Specified non-resident income'], ['10(4H)','Specified IFSC income'],
  ['10(6B)','Tax paid by Government / Indian concern'], ['10(6BB)','Tax paid on specified income'], ['10(6D)','Specified foreign-company income'],
  ['10(8)','Foreign-government remuneration'], ['10(8A)','Consultant remuneration'], ['10(8B)','Employee remuneration of consultant'], ['10(9)','Family-member income'],
  ['10(10BB)','Bhopal gas-leak compensation'], ['10(10BC)','Disaster compensation'], ['10(10D)','Life-insurance proceeds'],
  ['10(11)','PPF / statutory provident-fund payment'], ['10(11A)','Sukanya Samriddhi payment'], ['10(12)','Recognised provident-fund accumulated balance'],
  ['10(12A)','NPS partial withdrawal'], ['10(12AA)','NPS closure / opt-out payment'], ['10(12AB)','Specified pension-scheme payment'],
  ['10(12B)','Agniveer Corpus Fund payment'], ['10(12BA)','Agniveer contribution / payment'], ['10(12C)','Specified provident-fund payment'],
  ['10(13)','Approved superannuation-fund payment'], ['10(15)','Interest on specified securities / investments'], ['10(16)','Scholarship'],
  ['10(17A)','Approved award or reward'], ['10(18)','Gallantry-award pension'], ['10(19)','Family pension of armed-forces member'], ['10(19A)','Specified family pension'],
  ['10(23AA)','Regimental-fund income'], ['10(23FBB)','Investment-fund income'], ['10(23FBC)','Securitisation-trust income'],
  ['10(23FD)','Business-trust pass-through income'], ['10(23FF)','Specified sovereign / pension-fund income'], ['10(25)','Provident-fund income'],
  ['10(26)','Income of Scheduled Tribe member'], ['10(26AAA)','Sikkimese individual income'], ['10(30)','Subsidy from Tea Board'], ['10(31)','Subsidy from Rubber / Coffee / Cardamom Board'],
  ['10(32)','Minor-child income exemption'], ['10(33)','Transfer of Unit Scheme 1964 units'], ['10(35)','Income from specified units'], ['10(35A)','Specified unit income'],
  ['10(36)','Eligible equity-share transfer income'], ['10(37)','Compulsory-acquisition capital gain'], ['10(37A)','Specified land / building capital gain'],
  ['10(43)','Reversal of deemed capital gain'], ['10(44)','Agniveer Corpus Fund income'], ['DMD','Dividend / distribution exempt under specified provision'],
  ['Incmexmptcircular','Income exempt by CBDT circular'], ['Incmexmptnotification','Income exempt by notification'], ['Receiptnotincme','Receipt not constituting income'],
  ['Anyother1','Any other exempt income — item 1'], ['Anyother2','Any other exempt income — item 2'], ['Anyother3','Any other exempt income — item 3'], ['Anyother4','Any other exempt income — item 4'],
].map(([value, description]) => ({ value: value as ExemptIncomeSubCategory, label: `${value} — ${description}` }));

const ITR1_SUBCATEGORIES = new Set<ExemptIncomeSubCategory>([
  '10(1)','10(2)','10(10BB)','10(10BC)','10(10D)','10(11)','10(11A)','10(12)','10(12A)','10(12AA)','10(12AB)','10(12B)','10(12BA)','10(12C)','10(13)','10(15)','10(16)','10(17A)','10(18)','10(19)','10(19A)','10(23AA)','10(23FBB)','10(23FD)','10(25)','10(26)','10(26AAA)','10(30)','10(31)','10(32)','10(35)','10(35A)','10(43)','10(44)','DMD','Incmexmptcircular','Incmexmptnotification','Receiptnotincme',
]);
const ITR4_SUBCATEGORIES = new Set<ExemptIncomeSubCategory>([
  '10(1)','10(2)','10(10BB)','10(10BC)','10(10D)','10(11)','10(11A)','10(12)','10(12A)','10(12AA)','10(12AB)','10(12B)','10(12BA)','10(12C)','10(13)','10(15)','10(16)','10(17A)','10(18)','10(19)','10(19A)','10(23AA)','10(23FBB)','10(23FD)','10(25)','10(26)','10(26AAA)','10(30)','10(31)','10(32)','10(35)','10(35A)','10(43)','10(44)','DMD','Incmexmptcircular','Incmexmptnotification','Receiptnotincme',
]);
const ITR2_SUBCATEGORIES = new Set<ExemptIncomeSubCategory>([
  '10(2)','10(4)(i)','10(4)(ii)','10(4B)','10(4C)','10(4E)','10(4F)','10(4G)','10(6B)','10(6D)','10(8)','10(8A)','10(8B)','10(9)','10(10BB)','10(10BC)','10(10D)','10(11)','10(11A)','10(12)','10(12A)','10(12AA)','10(12AB)','10(12B)','10(12BA)','10(12C)','10(13)','10(15)','10(16)','10(17A)','10(18)','10(19)','10(19A)','10(23FBB)','10(23FBC)','10(23FD)','10(26)','10(26AAA)','10(30)','10(31)','10(32)','10(33)','10(35)','10(35A)','10(36)','10(37)','10(37A)','10(43)','DMD','Incmexmptcircular','Incmexmptnotification','Receiptnotincme',
]);
const ITR3_SUBCATEGORIES = new Set(SUBCATEGORY_OPTIONS.map((option) => option.value).filter((value) => value !== '10(1)'));

const styles = {
  sectionHeader: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 } as React.CSSProperties,
  title: { margin: 0, fontSize: 14, fontWeight: 600, color: 'var(--text-secondary)' } as React.CSSProperties,
  subtitle: { marginTop: 4, fontSize: 12, color: 'var(--text-muted)' } as React.CSSProperties,
  panel: { marginBottom: 24, padding: 16, background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 6 } as React.CSSProperties,
  panelHeader: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 } as React.CSSProperties,
  panelTitle: { margin: 0, fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)' } as React.CSSProperties,
  grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 16 } as React.CSSProperties,
  primaryRow: { display: 'grid', gridTemplateColumns: 'minmax(180px, .8fr) minmax(280px, 1.6fr) minmax(150px, .65fr)', gap: 16, alignItems: 'end' } as React.CSSProperties,
  label: { display: 'block', marginBottom: 6, fontSize: 12, fontWeight: 500, color: 'var(--text-secondary)' } as React.CSSProperties,
  input: { width: '100%', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6, fontSize: 13, background: 'white' } as React.CSSProperties,
  add: { padding: '6px 12px', background: 'var(--gold)', color: 'white', border: 'none', borderRadius: 6, fontSize: 12, cursor: 'pointer' } as React.CSSProperties,
  remove: { padding: '4px 8px', background: 'var(--danger)', color: 'white', border: 'none', borderRadius: 4, fontSize: 11, cursor: 'pointer' } as React.CSSProperties,
  empty: { padding: 24, textAlign: 'center', color: 'var(--text-muted)', background: 'var(--bg)', borderRadius: 6, marginBottom: 24 } as React.CSSProperties,
};

function Field({ label, value, onChange, readOnly = false, type = 'number', maxLength, placeholder, disabled }: { label: string; value: string | number; onChange?: (value: string) => void; readOnly?: boolean; type?: 'number' | 'text'; maxLength?: number; placeholder?: string; disabled?: boolean }): React.JSX.Element {
  return <div><label style={styles.label}>{label}</label><input style={styles.input} type={type} value={value} readOnly={readOnly} disabled={disabled} max={type === 'number' ? MAX_MONEY : undefined} min={type === 'number' ? 0 : undefined} maxLength={maxLength} placeholder={placeholder} onChange={(event) => onChange?.(event.target.value)} /></div>;
}

function Collapsible({ title, subtitle, defaultOpen, summary, children }: { title: string; subtitle: string; defaultOpen: boolean; summary?: string; children: React.ReactNode }): React.JSX.Element {
  const [open, setOpen] = useState(defaultOpen);
  return <section style={{ marginBottom: 24 }}>
    <div style={{ ...styles.sectionHeader, cursor: 'pointer', userSelect: 'none' }} onClick={() => setOpen(!open)}>
      <div><h3 style={styles.title}><span style={{ marginRight: 6, fontSize: 11, color: 'var(--text-muted)' }}>{open ? '▼' : '▶'}</span>{title}</h3><div style={styles.subtitle}>{subtitle}</div></div>
      {summary && <strong style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{summary}</strong>}
    </div>
    {open && children}
  </section>;
}

export default function ExemptIncomeWorkspace({ form, schedule, onChange, disabled = false }: ExemptIncomeWorkspaceProps): React.JSX.Element {
  const patch = (next: Partial<ExemptIncomeSchedule>): void => onChange({ ...schedule, ...next });
  const isFull = form === 'ITR-2' || form === 'ITR-3';
  const isItr1 = form === 'ITR-1';
  const allowedCategories = form === 'ITR-1' || form === 'ITR-4' ? CATEGORY_OPTIONS.filter((option) => option.value !== 'OTHN') : CATEGORY_OPTIONS;
  const allowedSubcategories = useMemo(() => {
    const allowed = form === 'ITR-1' ? ITR1_SUBCATEGORIES : form === 'ITR-4' ? ITR4_SUBCATEGORIES : form === 'ITR-2' ? ITR2_SUBCATEGORIES : ITR3_SUBCATEGORIES;
    return SUBCATEGORY_OPTIONS.filter((option) => allowed.has(option.value));
  }, [form]);
  const netAgriculture = Math.max(0, money(schedule.grossAgriculturalReceipts) - money(schedule.agriculturalExpenses) - money(schedule.unabsorbedAgriculturalLossPreviousEightYears) + (form === 'ITR-3' ? money(schedule.agriculturalIncomeRule7And8) : 0));
  const othersTotal = schedule.otherExemptIncome.reduce((total, entry) => total + money(entry.grossAmount), 0);
  const dtaaTotal = schedule.dtaaExemptIncome.reduce((total, entry) => total + money(entry.amountOfIncome), 0);
  const total = money(schedule.interestIncome) + netAgriculture + othersTotal + dtaaTotal + money(schedule.incomeNotChargeableToTax) + money(schedule.passThroughIncomeNotChargeableToTax);
  const incompatible = schedule.otherExemptIncome.filter((entry) => !allowedSubcategories.some((option) => option.value === entry.subCategory) || !allowedCategories.some((option) => option.value === entry.category));

  const addEntry = (): void => patch({ otherExemptIncome: [...schedule.otherExemptIncome, { id: id('ei'), category: 'SRPC', subCategory: allowedSubcategories.find((option) => option.value === '10(11)')?.value ?? allowedSubcategories[0]?.value ?? 'Incmexmptnotification', description: '', grossAmount: 0 }] });
  const updateEntry = (entryId: string, updates: Partial<ExemptIncomeEntry>): void => patch({ otherExemptIncome: schedule.otherExemptIncome.map((entry) => entry.id === entryId ? { ...entry, ...updates } : entry) });
  const removeEntry = (entryId: string): void => patch({ otherExemptIncome: schedule.otherExemptIncome.filter((entry) => entry.id !== entryId) });
  const addLand = (): void => patch({ agriculturalLandParcels: [...schedule.agriculturalLandParcels, { id: id('agri-land'), nameOfDistrict: '', pinCode: '', measurementOfLand: 0, ownedFlag: 'O', irrigatedFlag: 'IRG' }] });
  const updateLand = (entryId: string, updates: Partial<AgriculturalLandParcel>): void => patch({ agriculturalLandParcels: schedule.agriculturalLandParcels.map((entry) => entry.id === entryId ? { ...entry, ...updates } : entry) });
  const removeLand = (entryId: string): void => patch({ agriculturalLandParcels: schedule.agriculturalLandParcels.filter((entry) => entry.id !== entryId) });
  const addDtaa = (): void => patch({ dtaaExemptIncome: [...schedule.dtaaExemptIncome, { id: id('ei-dtaa'), amountOfIncome: 0, natureOfIncome: '', countryName: '', countryCode: '', articleOfDtaa: '', headOfIncome: 'OS', trcFlag: 'N' }] });
  const updateDtaa = (entryId: string, updates: Partial<DtaaExemptIncomeEntry>): void => patch({ dtaaExemptIncome: schedule.dtaaExemptIncome.map((entry) => entry.id === entryId ? { ...entry, ...updates } : entry) });
  const removeDtaa = (entryId: string): void => patch({ dtaaExemptIncome: schedule.dtaaExemptIncome.filter((entry) => entry.id !== entryId) });

  if (isItr1) return <div>
    <div style={{ marginBottom: 16 }}><h3 style={styles.title}>Exempt Income (ExemptIncAgriOthUs10)</h3><div style={styles.subtitle}>AY 2026-27 · non-salary exempt income only; salary exemptions remain in Schedule S</div></div>
    <div style={{ marginBottom: 16, padding: 12, background: 'var(--info-bg)', color: 'var(--info)', border: '1px solid var(--info)', borderRadius: 6, fontSize: 12 }}>ITR-1 reports agricultural and other section-10 exempt income here. Agricultural income under section 10(1) is allowed only up to ₹5,000 — exceeding that requires ITR-2. Equity LTCG up to the section 112A threshold belongs in Capital Gains.</div>
    {incompatible.length > 0 && <div style={{ marginBottom: 16, padding: 12, background: 'var(--warning-bg)', color: 'var(--warning)', border: '1px solid var(--warning)', borderRadius: 6, fontSize: 12 }}>⚠ {incompatible.length} saved entr{incompatible.length === 1 ? 'y is' : 'ies are'} unsupported by ITR-1. Data is preserved; change form or classification before filing.</div>}
    <div style={styles.sectionHeader}><h4 style={styles.panelTitle}>Exempt Income Entries</h4><button style={styles.add} disabled={disabled} onClick={addEntry}>+ Add Exempt Income</button></div>
    {schedule.otherExemptIncome.length === 0 && <div style={styles.empty}>No non-salary exempt-income entries.</div>}
    {schedule.otherExemptIncome.map((entry, index) => <div key={entry.id} style={styles.panel}>
      <div style={styles.panelHeader}><h4 style={styles.panelTitle}>Exempt Entry #{index + 1}</h4><button style={styles.remove} disabled={disabled} onClick={() => removeEntry(entry.id)}>Remove</button></div>
      <div style={styles.primaryRow}>
        <div><label style={styles.label}>Category *</label><select style={styles.input} value={entry.category} disabled={disabled} onChange={(event) => updateEntry(entry.id, { category: event.target.value as ExemptIncomeCategory })}>{allowedCategories.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></div>
        <div><label style={styles.label}>Sub-category / section *</label><select style={styles.input} value={entry.subCategory} disabled={disabled} onChange={(event) => updateEntry(entry.id, { subCategory: event.target.value as ExemptIncomeSubCategory })}>{!allowedSubcategories.some((option) => option.value === entry.subCategory) && <option value={entry.subCategory}>Unsupported on ITR-1: {entry.subCategory}</option>}{allowedSubcategories.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></div>
        <Field label="Amount (₹) *" value={entry.grossAmount || ''} disabled={disabled} onChange={(value) => updateEntry(entry.id, { grossAmount: money(Number(value)) })} />
      </div>
      <div style={{ marginTop: 16 }}><Field label="Description / source *" type="text" maxLength={125} value={entry.description} disabled={disabled} onChange={(value) => updateEntry(entry.id, { description: value })} /></div>
    </div>)}
    <div style={styles.panel}><div style={styles.panelHeader}><h4 style={styles.panelTitle}>Exempt Income Review</h4><span style={{ padding: '2px 7px', borderRadius: 3, background: 'var(--info)', color: 'white', fontSize: 10, fontWeight: 600 }}>ExemptIncAgriOthUs10</span></div><div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}><span>Total exempt income</span><strong>{inr(othersTotal)}</strong></div></div>
  </div>;

  return <div>
    <div style={{ marginBottom: 16 }}><h3 style={styles.title}>{form === 'ITR-4' ? 'Tax-Exempt Income Details' : 'Schedule EI — Exempt Income'}</h3><div style={styles.subtitle}>AY 2026-27 · non-salary exempt income only; salary exemptions remain in Schedule S</div></div>
    {incompatible.length > 0 && <div style={{ marginBottom: 16, padding: 12, background: 'var(--warning-bg)', color: 'var(--warning)', border: '1px solid var(--warning)', borderRadius: 6, fontSize: 12 }}>⚠ {incompatible.length} saved entr{incompatible.length === 1 ? 'y is' : 'ies are'} unsupported by {form}. Data is preserved; change form or classification before filing.</div>}

    {isFull && <Collapsible title="Agricultural income" subtitle="Schedule EI gross receipts, expenses, Rule 7/8 and mandatory land details above ₹5,000" defaultOpen summary={inr(netAgriculture)}>
      <div style={styles.grid}>
        <Field label="Gross agricultural receipts (₹)" value={schedule.grossAgriculturalReceipts || ''} disabled={disabled} onChange={(value) => patch({ grossAgriculturalReceipts: money(Number(value)) })} />
        <Field label="Agricultural expenses (₹)" value={schedule.agriculturalExpenses || ''} disabled={disabled} onChange={(value) => patch({ agriculturalExpenses: money(Number(value)) })} />
        <Field label="Unabsorbed agricultural loss — previous 8 years (₹)" value={schedule.unabsorbedAgriculturalLossPreviousEightYears || ''} disabled={disabled} onChange={(value) => patch({ unabsorbedAgriculturalLossPreviousEightYears: money(Number(value)) })} />
        {form === 'ITR-3' && <Field label="Agricultural income under Rules 7 and 8 (₹)" value={schedule.agriculturalIncomeRule7And8 || ''} disabled={disabled} onChange={(value) => patch({ agriculturalIncomeRule7And8: money(Number(value)) })} />}
        <Field label="Net agricultural / Rule 7 income (₹)" value={netAgriculture} readOnly />
      </div>
      <div style={{ ...styles.sectionHeader, marginTop: 24 }}><h4 style={styles.panelTitle}>Agricultural land details</h4><button style={styles.add} disabled={disabled} onClick={addLand}>+ Add Land Parcel</button></div>
      {schedule.agriculturalLandParcels.length === 0 && <div style={styles.empty}>No land details. Add every agricultural land parcel when net agricultural income exceeds ₹5,000.</div>}
      {schedule.agriculturalLandParcels.map((entry, index) => <div key={entry.id} style={styles.panel}>
        <div style={styles.panelHeader}><h4 style={styles.panelTitle}>Land Parcel #{index + 1}</h4><button style={styles.remove} disabled={disabled} onClick={() => removeLand(entry.id)}>Remove</button></div>
        <div style={styles.grid}>
          <Field label="District *" type="text" maxLength={125} value={entry.nameOfDistrict} disabled={disabled} onChange={(value) => updateLand(entry.id, { nameOfDistrict: value })} />
          <Field label="PIN code *" type="text" maxLength={6} value={entry.pinCode} disabled={disabled} onChange={(value) => updateLand(entry.id, { pinCode: value.replace(/\D/g, '').slice(0, 6) })} />
          <Field label="Land measurement *" value={entry.measurementOfLand || ''} disabled={disabled} onChange={(value) => updateLand(entry.id, { measurementOfLand: money(Number(value)) })} />
          <div><label style={styles.label}>Ownership *</label><select style={styles.input} value={entry.ownedFlag} disabled={disabled} onChange={(event) => updateLand(entry.id, { ownedFlag: event.target.value as 'O' | 'H' })}><option value="O">O — Owned</option><option value="H">H — Held on lease</option></select></div>
          <div><label style={styles.label}>Irrigation *</label><select style={styles.input} value={entry.irrigatedFlag} disabled={disabled} onChange={(event) => updateLand(entry.id, { irrigatedFlag: event.target.value as 'IRG' | 'RF' })}><option value="IRG">IRG — Irrigated</option><option value="RF">RF — Rain-fed</option></select></div>
        </div>
      </div>)}
    </Collapsible>}

    <Collapsible title="Other non-salary exempt income" subtitle={`${form} Category / SubCategory enumerations from the official CBDT schema`} defaultOpen summary={inr(othersTotal)}>
      <div style={styles.sectionHeader}><h4 style={styles.panelTitle}>Exempt Income Entries</h4><button style={styles.add} disabled={disabled} onClick={addEntry}>+ Add Exempt Income</button></div>
      {schedule.otherExemptIncome.length === 0 && <div style={styles.empty}>No non-salary exempt-income entries.</div>}
      {schedule.otherExemptIncome.map((entry, index) => <div key={entry.id} style={styles.panel}>
        <div style={styles.panelHeader}><h4 style={styles.panelTitle}>Exempt Entry #{index + 1}</h4><button style={styles.remove} disabled={disabled} onClick={() => removeEntry(entry.id)}>Remove</button></div>
        <div style={styles.primaryRow}>
          <div><label style={styles.label}>Category *</label><select style={styles.input} value={entry.category} disabled={disabled} onChange={(event) => updateEntry(entry.id, { category: event.target.value as ExemptIncomeCategory })}>{allowedCategories.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></div>
          <div><label style={styles.label}>Sub-category / section *</label><select style={styles.input} value={entry.subCategory} disabled={disabled} onChange={(event) => updateEntry(entry.id, { subCategory: event.target.value as ExemptIncomeSubCategory })}>{!allowedSubcategories.some((option) => option.value === entry.subCategory) && <option value={entry.subCategory}>Unsupported on {form}: {entry.subCategory}</option>}{allowedSubcategories.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></div>
          <Field label="Amount (₹) *" value={entry.grossAmount || ''} disabled={disabled} onChange={(value) => updateEntry(entry.id, { grossAmount: money(Number(value)) })} />
        </div>
        <div style={{ marginTop: 16 }}><Field label="Description / source *" type="text" maxLength={125} value={entry.description} disabled={disabled} onChange={(value) => updateEntry(entry.id, { description: value })} /></div>
      </div>)}
    </Collapsible>

    {isFull && <Collapsible title="Income not chargeable under DTAA" subtitle="Schedule EI treaty-exempt income; distinct from taxable DTAA income in Schedule OS" defaultOpen={false} summary={inr(dtaaTotal)}>
      <div style={styles.sectionHeader}><h4 style={styles.panelTitle}>DTAA-Exempt Entries</h4><button style={styles.add} disabled={disabled} onClick={addDtaa}>+ Add DTAA-Exempt Entry</button></div>
      {schedule.dtaaExemptIncome.length === 0 && <div style={styles.empty}>No treaty-exempt income entries.</div>}
      {schedule.dtaaExemptIncome.map((entry, index) => <div key={entry.id} style={styles.panel}>
        <div style={styles.panelHeader}><h4 style={styles.panelTitle}>DTAA-Exempt Entry #{index + 1}</h4><button style={styles.remove} disabled={disabled} onClick={() => removeDtaa(entry.id)}>Remove</button></div>
        <div style={styles.grid}>
          <Field label="Amount of income (₹) *" value={entry.amountOfIncome || ''} disabled={disabled} onChange={(value) => updateDtaa(entry.id, { amountOfIncome: money(Number(value)) })} />
          <Field label="Nature of income *" type="text" maxLength={75} value={entry.natureOfIncome} disabled={disabled} onChange={(value) => updateDtaa(entry.id, { natureOfIncome: value })} />
          <Field label="Country name *" type="text" maxLength={55} value={entry.countryName} disabled={disabled} onChange={(value) => updateDtaa(entry.id, { countryName: value })} />
          <Field label="Country code excluding India *" type="text" value={entry.countryCode} disabled={disabled} onChange={(value) => updateDtaa(entry.id, { countryCode: value })} />
          <Field label="DTAA article *" type="text" maxLength={16} value={entry.articleOfDtaa} disabled={disabled} onChange={(value) => updateDtaa(entry.id, { articleOfDtaa: value })} />
          <div><label style={styles.label}>Head of income *</label><select style={styles.input} value={entry.headOfIncome} disabled={disabled} onChange={(event) => updateDtaa(entry.id, { headOfIncome: event.target.value as DtaaExemptIncomeEntry['headOfIncome'] })}><option value="SA">SA — Salary</option><option value="HP">HP — House property</option>{form === 'ITR-3' && <option value="PG">PG — Business / profession</option>}<option value="CG">CG — Capital gains</option><option value="OS">OS — Other sources</option></select></div>
          <div><label style={styles.label}>Tax residency certificate *</label><select style={styles.input} value={entry.trcFlag} disabled={disabled} onChange={(event) => updateDtaa(entry.id, { trcFlag: event.target.value as 'Y' | 'N' })}><option value="Y">Y — Yes</option><option value="N">N — No</option></select></div>
        </div>
      </div>)}
    </Collapsible>}

    {isFull && <Collapsible title="Additional Schedule EI disclosures" subtitle="Pass-through, not-chargeable and required totals" defaultOpen={false} summary={inr(total)}>
      <div style={styles.grid}>
        <Field label="Exempt interest income (₹)" value={schedule.interestIncome || ''} disabled={disabled} onChange={(value) => patch({ interestIncome: money(Number(value)) })} />
        <Field label="Pass-through income not chargeable to tax (₹)" value={schedule.passThroughIncomeNotChargeableToTax || ''} disabled={disabled} onChange={(value) => patch({ passThroughIncomeNotChargeableToTax: money(Number(value)) })} />
        <Field label="Income not chargeable to tax (₹)" value={schedule.incomeNotChargeableToTax || ''} disabled={disabled} onChange={(value) => patch({ incomeNotChargeableToTax: money(Number(value)) })} />
        {form === 'ITR-3' && <Field label="Income chargeable as per DTAA (₹)" value={schedule.incomeChargeableAsPerDtaa || ''} disabled={disabled} onChange={(value) => patch({ incomeChargeableAsPerDtaa: money(Number(value)) })} />}
        <Field label="Other exempt-income total (₹)" value={othersTotal} readOnly />
        <Field label="Total exempt income (₹)" value={total} readOnly />
      </div>
    </Collapsible>}

    <div style={styles.panel}><div style={styles.panelHeader}><h4 style={styles.panelTitle}>Exempt Income Review</h4><span style={{ padding: '2px 7px', borderRadius: 3, background: form === 'ITR-4' ? 'var(--info)' : 'var(--success)', color: 'white', fontSize: 10, fontWeight: 600 }}>{form === 'ITR-4' ? 'Compact TaxExmpIntIncDtls' : 'Full Schedule EI'}</span></div><div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}><span>Total exempt income</span><strong>{inr(form === 'ITR-4' ? othersTotal : total)}</strong></div></div>
  </div>;
}
