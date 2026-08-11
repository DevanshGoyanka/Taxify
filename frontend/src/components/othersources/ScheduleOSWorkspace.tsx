import React, { useMemo, useState } from 'react';
import type {
  AccumulatedPfEntry, DividendIncome, DividendSection, DtaaIncomeEntry, DtaaNatureOfIncome, GiftIncome, InterestIncome, InterestKind,
  OtherIncomeEntry, PfAssessmentYear, ReturnDraft, Section89AEntry, SpecialRateIncomeEntry,
  SpecialRateSourceDescription, WinningIncome, WinningIncomeType,
} from '../../domain/returns/types';
import type { ItrForm } from '../../domain/eligibility';

const INV = 99_999_999_999_999;

interface ScheduleOSWorkspaceProps {
  form: ItrForm;
  regime: 'old' | 'new';
  otherSources: ReturnDraft['otherSources'];
  onChange: (next: ReturnDraft['otherSources']) => void;
  disabled?: boolean;
}

const genId = (prefix: string): string => `${prefix}-${crypto.randomUUID()}`;
const money = (value: unknown): number => (typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : 0);
const inr = (value: number): string => `₹${Number(value || 0).toLocaleString('en-IN')}`;
const sum = (values: readonly { grossAmount?: number; value?: number; amount?: number; sourceAmount?: number }[]): number => values.reduce((total, entry) => total + money(entry.grossAmount ?? entry.value ?? entry.amount ?? entry.sourceAmount), 0);

// ── Interest taxonomy ─────────────────────────────────────────────────────────
interface InterestOption { kind: InterestKind; label: string; }
const INTEREST_OPTIONS: readonly InterestOption[] = [
  { kind: 'SAVINGS_BANK', label: 'Savings-account interest' },
  { kind: 'TERM_DEPOSIT', label: 'Deposit interest (bank/post office/co-op)' },
  { kind: 'IT_REFUND', label: 'Income-tax refund interest' },
  { kind: 'BONDS', label: 'Bonds or debentures' },
  { kind: 'SECURITIES', label: 'Interest on securities' },
  { kind: 'PF_10_11_FIRST', label: 'Taxable PF interest — first proviso to 10(11)' },
  { kind: 'PF_10_11_SECOND', label: 'Taxable PF interest — second proviso to 10(11)' },
  { kind: 'PF_10_12_FIRST', label: 'Taxable PF interest — first proviso to 10(12)' },
  { kind: 'PF_10_12_SECOND', label: 'Taxable PF interest — second proviso to 10(12)' },
  { kind: 'OTHER', label: 'Other interest' },
];
const interestLabel = (kind: InterestKind): string => INTEREST_OPTIONS.find((option) => option.kind === kind)?.label ?? kind;

// ── Dividend taxonomy ─────────────────────────────────────────────────────────
interface DividendOption { section: DividendSection; label: string; }
const DIVIDEND_OPTIONS: readonly DividendOption[] = [
  { section: '194', label: 'Dividend other than 2(22)(e)' },
  { section: '10(22e)', label: 'Deemed dividend u/s 2(22)(e)' },
  { section: '10(22f)', label: 'Dividend u/s 2(22)(f)' },
  { section: '115BBDA', label: 'Dividend u/s 115BBDA' },
  { section: '115BBDAaiii', label: 'Dividend u/s 115BBDA(a)(iii)' },
  { section: '115A1ai', label: 'Dividend u/s 115A(1)(a)(i)' },
  { section: '115A1aA', label: 'Dividend u/s 115A(1)(a)(A) — proviso' },
  { section: '115AC', label: 'Dividend u/s 115AC' },
  { section: '115ACA', label: 'Dividend u/s 115ACA' },
  { section: '115AD1i', label: 'Dividend u/s 115AD(1)(i)' },
  { section: 'DTAA', label: 'DTAA dividend' },
];
const dividendLabel = (section: DividendSection): string => DIVIDEND_OPTIONS.find((option) => option.section === section)?.label ?? section;

// ── Winnings taxonomy ─────────────────────────────────────────────────────────
interface WinningOption { type: WinningIncomeType; label: string; }
const WINNING_OPTIONS: readonly WinningOption[] = [
  { type: 'LOTTERY', label: 'Lottery, crossword, card game, betting or gambling' },
  { type: 'ONLINE_GAMING', label: 'Online games' },
  { type: 'HORSE_RACE', label: 'Winnings from horse races' },
  { type: 'UNEXPLAINED_115BBE', label: 'Unexplained income u/s 115BBE' },
  { type: 'RACE_HORSE_ACTIVITY', label: 'Owning and maintaining race horses' },
];
const winningLabel = (type: WinningIncomeType): string => WINNING_OPTIONS.find((option) => option.type === type)?.label ?? type;

// ── DTAA nature-of-income enum ───────────────────────────────────────────────
const DTAA_NATURE_OPTIONS: readonly { value: DtaaNatureOfIncome; label: string }[] = [
  { value: '1ai', label: '115A(1)(a)(i) — dividend' },
  { value: '1aiii', label: '115A(1)(a)(iii) — interest' },
  { value: '1b', label: '115A(1)(b) — royalty' },
  { value: '1c', label: '115A(1)(c) — technical service fees' },
  { value: '1d', label: '115A(1)(d) — other income' },
  { value: '2ai', label: '115A(2)(a)(i)' },
  { value: '2aii', label: '115A(2)(a)(ii)' },
  { value: '2d', label: '115A(2)(d)' },
  { value: '2e', label: '115A(2)(e)' },
];

// ── Special-rate source description enum ──────────────────────────────────────
const SPECIAL_RATE_OPTIONS: readonly { value: SpecialRateSourceDescription; label: string }[] = [
  { value: '5A1ai', label: '115A(1)(a)(i) — dividend' },
  { value: '5A1aA', label: '115A(1)(a)(A) — proviso' },
  { value: '5A1aii', label: '115A(1)(a)(ii) — interest' },
  { value: '5A1aiia', label: '115A(1)(a)(ii)(a)' },
  { value: '5A1aiiaa', label: '115A(1)(a)(ii)(aa)' },
  { value: '5A1aiiab', label: '115A(1)(a)(ii)(ab)' },
  { value: '5A1aiiac', label: '115A(1)(a)(ii)(ac)' },
  { value: '5A1aiii', label: '115A(1)(a)(iii)' },
  { value: '5A1bA', label: '115A(1)(b)(A) — royalty' },
  { value: '5AC1ab', label: '115AC(1)(a)(b)' },
  { value: '5AC1abD', label: '115AC(1)(a)(b)(D)' },
  { value: '5ACA1a', label: '115ACA(1)(a)' },
  { value: '5AD1i', label: '115AD(1)(i)' },
  { value: '5AD1iP', label: '115AD(1)(i) — proviso' },
  { value: '5BBA', label: '115BBA' },
  { value: '5BBF', label: '115BBF' },
  { value: '5BBG', label: '115BBG' },
  { value: '5Ea', label: '115E(a)' },
  { value: '5A1aiiaaP', label: '115A(1)(a)(ii)(aa) — proviso' },
  { value: '5A1aiiaa2P', label: '115A(1)(a)(ii)(aa) — 2nd proviso' },
  { value: '5AD1iDiv', label: '115AD(1)(i) — dividend' },
];
const specialRateLabel = (value: SpecialRateSourceDescription): string => SPECIAL_RATE_OPTIONS.find((option) => option.value === value)?.label ?? value;

// ── PF assessment-year enum ──────────────────────────────────────────────────
const PF_ASSESSMENT_YEARS: readonly PfAssessmentYear[] = ['2005-06','2006-07','2007-08','2008-09','2009-10','2010-11','2011-12','2012-13','2013-14','2014-15','2015-16','2016-17','2017-18','2018-19','2019-20','2020-21','2021-22','2022-23','2023-24','2024-25','2025-26'];

// ── Form compatibility ────────────────────────────────────────────────────────
type Category = 'interest' | 'dividend' | 'familyPension' | 'machineryRent' | 'otherIncome' | 'gifts' | 'lottery' | 'onlineGaming' | 'horseRace' | 'raceHorseActivity' | 'unexplained115BBE' | 'unexplained' | 'dtaa' | 'section89A' | 'accumulatedPf' | 'deductions' | 'passThrough' | 'specialRate';
const COMPACT_FORMS: ReadonlySet<ItrForm> = new Set(['ITR-1', 'ITR-4']);
const requiresFullSchedule: readonly Category[] = ['lottery', 'onlineGaming', 'horseRace', 'raceHorseActivity', 'unexplained115BBE', 'unexplained', 'dtaa', 'section89A', 'accumulatedPf', 'specialRate'];

function isCategoryPopulated(category: Category, os: ReturnDraft['otherSources']): boolean {
  switch (category) {
    case 'interest': return os.interest.length > 0;
    case 'dividend': return os.dividends.length > 0;
    case 'familyPension': return money(os.familyPension.grossAmount) > 0;
    case 'machineryRent': return os.otherIncome.some((entry) => entry.nature === 'MACHINERY_RENT');
    case 'otherIncome': return os.otherIncome.some((entry) => entry.nature !== 'MACHINERY_RENT');
    case 'gifts': return os.gifts.length > 0;
    case 'lottery': return os.winnings.some((w) => w.type === 'LOTTERY' || w.type === 'BETTING' || w.type === 'CARD_GAME');
    case 'onlineGaming': return os.winnings.some((w) => w.type === 'ONLINE_GAMING');
    case 'horseRace': return os.winnings.some((w) => w.type === 'HORSE_RACE');
    case 'raceHorseActivity': return os.winnings.some((w) => w.type === 'RACE_HORSE_ACTIVITY');
    case 'unexplained115BBE': return os.winnings.some((w) => w.type === 'UNEXPLAINED_115BBE');
    case 'unexplained': return Object.values(os.unexplainedIncome).some((v) => money(v) > 0);
    case 'dtaa': return os.dtaaIncome.length > 0;
    case 'section89A': return os.section89A.length > 0;
    case 'accumulatedPf': return os.accumulatedPf.length > 0;
    case 'deductions': return Object.values(os.deductions).some((v) => money(v) > 0);
    case 'passThrough': return os.otherIncome.some((entry) => entry.nature === 'PASS_THROUGH');
    case 'specialRate': return os.specialRateIncome.length > 0;
    default: return false;
  }
}

function compactFormIncompatibilities(os: ReturnDraft['otherSources']): Category[] {
  return requiresFullSchedule.filter((category) => isCategoryPopulated(category, os));
}

// ── Shared UI primitives (TDS-tab visual language) ───────────────────────────
const sectionHeaderStyle: React.CSSProperties = { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16, cursor: 'pointer', userSelect: 'none' };
const sectionTitleStyle: React.CSSProperties = { fontSize: 14, fontWeight: 600, color: 'var(--text-secondary)', margin: 0 };
const sectionSubtitleStyle: React.CSSProperties = { fontSize: 12, color: 'var(--text-muted)', marginTop: 4 };
const entryPanelStyle: React.CSSProperties = { marginBottom: 24, padding: 16, background: 'var(--bg)', borderRadius: 6, border: '1px solid var(--border)' };
const entryHeaderStyle: React.CSSProperties = { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 };
const entryTitleStyle: React.CSSProperties = { fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)', margin: 0 };
const gridStyle: React.CSSProperties = { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 16 };
const wideFieldStyle: React.CSSProperties = { gridColumn: 'span 2' };
const labelStyle: React.CSSProperties = { display: 'block', marginBottom: 6, fontSize: 12, fontWeight: 500, color: 'var(--text-secondary)' };
const inputStyle: React.CSSProperties = { width: '100%', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6, fontSize: 13 };
const selectStyle: React.CSSProperties = { width: '100%', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6, fontSize: 13, background: 'white' };
const addButtonStyle: React.CSSProperties = { padding: '6px 12px', background: 'var(--gold)', color: 'white', border: 'none', borderRadius: 6, fontSize: 12, cursor: 'pointer' };
const removeButtonStyle: React.CSSProperties = { padding: '4px 8px', background: 'var(--danger)', color: 'white', border: 'none', borderRadius: 4, fontSize: 11, cursor: 'pointer' };
const removeCircleButtonStyle: React.CSSProperties = { background: 'var(--danger)', color: 'white', border: 'none', width: 24, height: 24, borderRadius: '50%', cursor: 'pointer', fontSize: 14, padding: 0 };
const emptyStyle: React.CSSProperties = { padding: 24, textAlign: 'center', color: 'var(--text-muted)', background: 'var(--bg)', borderRadius: 6, marginBottom: 24 };
const summaryPanelStyle: React.CSSProperties = { marginTop: 32, padding: 16, background: 'var(--bg)', borderRadius: 6, border: '1px solid var(--border)' };
const summaryRowStyle: React.CSSProperties = { display: 'flex', justifyContent: 'space-between', padding: '4px 0', fontSize: 12 };
const badgeStyle: React.CSSProperties = { padding: '2px 6px', fontSize: 10, fontWeight: 600, borderRadius: 3, color: 'white' };
const subSectionHeaderStyle: React.CSSProperties = { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 };

function Field({ label, value, onChange, type = 'text', readOnly = false, max, min, disabled, wide = false }: { label: string; value: string | number; onChange?: (value: string) => void; type?: 'text' | 'number' | 'date'; readOnly?: boolean; max?: number; min?: number; disabled?: boolean; wide?: boolean }): React.JSX.Element {
  return <div style={wide ? wideFieldStyle : undefined}><label style={labelStyle}>{label}</label><input style={inputStyle} type={type} value={value ?? ''} readOnly={readOnly} disabled={disabled} max={max} min={min} onChange={(event) => onChange?.(type === 'number' ? event.target.value : event.target.value)} /></div>;
}

function ApplicabilityBadge({ form }: { form: ItrForm }): React.JSX.Element {
  const isCompact = COMPACT_FORMS.has(form);
  const label = isCompact ? `Compact model (${form})` : `Full Schedule OS (${form})`;
  const color = isCompact ? 'var(--accent-blue)' : 'var(--success)';
  return <span style={{ ...badgeStyle, background: color }}>{label}</span>;
}

function FormWarning({ form, categories }: { form: ItrForm; categories: Category[] }): React.JSX.Element | null {
  if (categories.length === 0) return null;
  const isCompact = COMPACT_FORMS.has(form);
  if (!isCompact) return null;
  return <div style={{ marginBottom: 16, padding: 12, background: 'var(--warning-bg)', border: '1px solid var(--warning)', borderRadius: 6, fontSize: 12, color: 'var(--warning)' }}>
    ⚠ The following income categories are not supported by {form}: {categories.join(', ')}. Use ITR-2 or ITR-3 to report this income. The data is preserved but the form cannot be filed as-is.
  </div>;
}

// Collapsible section — entire header is clickable to toggle. No explicit button.
function Section({ title, subtitle, badge, badgeColor, defaultOpen, summary, children }: { title: string; subtitle?: string; badge?: string; badgeColor?: string; defaultOpen: boolean; summary?: string; children?: React.ReactNode }): React.JSX.Element {
  const [open, setOpen] = useState(defaultOpen);
  return <section style={{ marginBottom: 24 }}>
    <div style={sectionHeaderStyle} onClick={() => setOpen(!open)}>
      <div>
        <h3 style={sectionTitleStyle}>
          <span style={{ fontSize: 11, color: 'var(--text-muted)', marginRight: 6 }}>{open ? '▼' : '▶'}</span>
          {title}
          {badge && <span style={{ ...badgeStyle, background: badgeColor ?? 'var(--gold)', marginLeft: 8 }}>{badge}</span>}
        </h3>
        {subtitle && <div style={sectionSubtitleStyle}>{subtitle}</div>}
      </div>
      {summary && <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)' }}>{summary}</span>}
    </div>
    {open && children}
  </section>;
}

// Reusable five-period breakup block (CBDT DateRangeType).
function FivePeriodBreakup({ q1, q2, q3, q4, q5, disabled, onChange }: { q1: number; q2: number; q3: number; q4: number; q5: number; disabled?: boolean; onChange: (field: 'q1' | 'q2' | 'q3' | 'q4' | 'q5', value: number) => void }): React.JSX.Element {
  return <details style={{ marginTop: 16 }}>
    <summary style={{ fontSize: 12, cursor: 'pointer', color: 'var(--text-secondary)', fontWeight: 500 }}>Five-period breakup (CBDT DateRange)</summary>
    <div style={{ ...gridStyle, marginTop: 12 }}>
      <Field label="Up to 15 Jun (₹)" type="number" value={q1 || ''} disabled={disabled} max={INV} onChange={(value) => onChange('q1', money(Number(value)))} />
      <Field label="16 Jun – 15 Sep (₹)" type="number" value={q2 || ''} disabled={disabled} max={INV} onChange={(value) => onChange('q2', money(Number(value)))} />
      <Field label="16 Sep – 15 Dec (₹)" type="number" value={q3 || ''} disabled={disabled} max={INV} onChange={(value) => onChange('q3', money(Number(value)))} />
      <Field label="16 Dec – 15 Mar (₹)" type="number" value={q4 || ''} disabled={disabled} max={INV} onChange={(value) => onChange('q4', money(Number(value)))} />
      <Field label="16 Mar – 31 Mar (₹)" type="number" value={q5 || ''} disabled={disabled} max={INV} onChange={(value) => onChange('q5', money(Number(value)))} />
    </div>
  </details>;
}

// ── Main workspace component ──────────────────────────────────────────────────
export default function ScheduleOSWorkspace({ form, regime, otherSources, onChange, disabled = false }: ScheduleOSWorkspaceProps): React.JSX.Element {
  const os = otherSources;

  const patch = (next: Partial<ReturnDraft['otherSources']>): void => onChange({ ...os, ...next });
  const patchInterest = (interest: InterestIncome[]): void => patch({ interest });
  const patchDividends = (dividends: DividendIncome[]): void => patch({ dividends });
  const patchWinnings = (winnings: WinningIncome[]): void => patch({ winnings });
  const patchGifts = (gifts: GiftIncome[]): void => patch({ gifts });
  const patchOtherIncome = (otherIncome: OtherIncomeEntry[]): void => patch({ otherIncome });
  const patchDtaa = (dtaaIncome: DtaaIncomeEntry[]): void => patch({ dtaaIncome });
  const patch89A = (section89A: Section89AEntry[]): void => patch({ section89A });
  const patchPf = (accumulatedPf: AccumulatedPfEntry[]): void => patch({ accumulatedPf });
  const patchSpecialRate = (specialRateIncome: SpecialRateIncomeEntry[]): void => patch({ specialRateIncome });

  const incompatibilities = useMemo(() => compactFormIncompatibilities(os), [os]);
  const interestTotal = sum(os.interest);
  const dividendTotal = sum(os.dividends);
  // CBDT AY 2026-27: DeductionUs57iia cap is ₹25,000 universally — no regime distinction.
  const familyPensionDeduction = Math.min(money(os.familyPension.grossAmount) / 3, 25000);

  // ── Interest ──
  const addInterest = (): void => { if (disabled) return; patchInterest([...os.interest, { id: genId('interest'), kind: 'SAVINGS_BANK', grossAmount: 0, tdsDeducted: 0, bankName: '', accountType: '', accountNumber: '', ifscCode: '', postOfficeName: '', accountNumberPO: '', nscCertificateNumber: '', yearOfPurchase: 0, scssAccountNumber: '', dateOfOpening: '', deductorName: '', deductorTAN: '', remarks: '' }]); };
  const updateInterest = (id: string, updates: Partial<InterestIncome>): void => patchInterest(os.interest.map((entry) => entry.id === id ? { ...entry, ...updates } : entry));
  const removeInterest = (id: string): void => patchInterest(os.interest.filter((entry) => entry.id !== id));

  // ── Dividends ──
  const addDividend = (): void => { if (disabled) return; patchDividends([...os.dividends, { id: genId('dividend'), section: '194', grossAmount: 0, tdsDeducted: 0, companyName: '', companyPAN: '', deductorTAN: '', isin: '', category: '', q1: 0, q2: 0, q3: 0, q4: 0, q5: 0 }]); };
  const updateDividend = (id: string, updates: Partial<DividendIncome>): void => patchDividends(os.dividends.map((entry) => entry.id === id ? { ...entry, ...updates } : entry));
  const removeDividend = (id: string): void => patchDividends(os.dividends.filter((entry) => entry.id !== id));

  // ── Ordinary income ──
  const addOtherIncome = (): void => { if (disabled) return; patchOtherIncome([...os.otherIncome, { id: genId('osOther'), nature: 'OTHER', description: '', amount: 0 }]); };
  const updateOtherIncome = (id: string, updates: Partial<OtherIncomeEntry>): void => patchOtherIncome(os.otherIncome.map((entry) => entry.id === id ? { ...entry, ...updates } : entry));
  const removeOtherIncome = (id: string): void => patchOtherIncome(os.otherIncome.filter((entry) => entry.id !== id));

  // ── Gifts ──
  const addGift = (): void => { if (disabled) return; patchGifts([...os.gifts, { id: genId('gift'), propertyType: 'CASH', value: 0, donorName: '', donorRelation: '', dateOfReceipt: '', description: '', fromRelative: false, receivedOnMarriage: false, considerationKind: 'WITHOUT_CONSIDERATION' }]); };
  const updateGift = (id: string, updates: Partial<GiftIncome>): void => patchGifts(os.gifts.map((entry) => entry.id === id ? { ...entry, ...updates } : entry));
  const removeGift = (id: string): void => patchGifts(os.gifts.filter((entry) => entry.id !== id));

  // ── Winnings ──
  const addWinning = (): void => { if (disabled) return; patchWinnings([...os.winnings, { id: genId('winning'), type: 'LOTTERY', grossAmount: 0, tdsDeducted: 0, payerName: '', payerTAN: '', dateOfWinning: '', q1: 0, q2: 0, q3: 0, q4: 0, q5: 0 }]); };
  const addRaceHorseActivity = (): void => { if (disabled) return; patchWinnings([...os.winnings, { id: genId('winning'), type: 'RACE_HORSE_ACTIVITY', grossAmount: 0, tdsDeducted: 0, payerName: '', payerTAN: '', dateOfWinning: '', receipts: 0, deductionUs57: 0, amountNotDeductibleUs58: 0, profitChargeableUs59: 0, balance: 0 }]); };
  const updateWinning = (id: string, updates: Partial<WinningIncome>): void => patchWinnings(os.winnings.map((entry) => entry.id === id ? { ...entry, ...updates } : entry));
  const removeWinning = (id: string): void => patchWinnings(os.winnings.filter((entry) => entry.id !== id));

  // ── DTAA ──
  const addDtaa = (): void => { if (disabled) return; patchDtaa([...os.dtaaIncome, { id: genId('osDtaa'), amount: 0, natureOfIncome: '1ai', countryName: '', countryCode: '', dtaaArticle: '', rateAsPerTreaty: 0, rateAsPerITAct: 0, taxResidencyCertificate: 'N', itemNoIncl: '', applicableRate: 0, q1: 0, q2: 0, q3: 0, q4: 0, q5: 0 }]); };
  const updateDtaa = (id: string, updates: Partial<DtaaIncomeEntry>): void => patchDtaa(os.dtaaIncome.map((entry) => entry.id === id ? { ...entry, ...updates } : entry));
  const removeDtaa = (id: string): void => patchDtaa(os.dtaaIncome.filter((entry) => entry.id !== id));

  // ── 89A ──
  const add89A = (): void => { if (disabled) return; patch89A([...os.section89A, { id: genId('os89a'), countryCode: 'US', amount: 0 }]); };
  const update89A = (id: string, updates: Partial<Section89AEntry>): void => patch89A(os.section89A.map((entry) => entry.id === id ? { ...entry, ...updates } : entry));
  const remove89A = (id: string): void => patch89A(os.section89A.filter((entry) => entry.id !== id));
  const update89AAgg = (field: keyof ReturnDraft['otherSources']['section89AAggregates'], value: number): void => { if (disabled) return; patch({ section89AAggregates: { ...os.section89AAggregates, [field]: value } }); };

  // ── Accumulated PF ──
  const addPf = (): void => { if (disabled) return; patchPf([...os.accumulatedPf, { id: genId('osPf'), assessmentYear: '2025-26', incomeBenefit: 0, taxBenefit: 0 }]); };
  const updatePf = (id: string, updates: Partial<AccumulatedPfEntry>): void => patchPf(os.accumulatedPf.map((entry) => entry.id === id ? { ...entry, ...updates } : entry));
  const removePf = (id: string): void => patchPf(os.accumulatedPf.filter((entry) => entry.id !== id));
  const updatePfAgg = (field: keyof ReturnDraft['otherSources']['accumulatedPfAggregates'], value: number): void => { if (disabled) return; patch({ accumulatedPfAggregates: { ...os.accumulatedPfAggregates, [field]: value } }); };

  // ── Special-rate income ──
  const addSpecialRate = (): void => { if (disabled) return; patchSpecialRate([...os.specialRateIncome, { id: genId('osSpecRate'), sourceDescription: '5A1ai', sourceAmount: 0 }]); };
  const updateSpecialRate = (id: string, updates: Partial<SpecialRateIncomeEntry>): void => patchSpecialRate(os.specialRateIncome.map((entry) => entry.id === id ? { ...entry, ...updates } : entry));
  const removeSpecialRate = (id: string): void => patchSpecialRate(os.specialRateIncome.filter((entry) => entry.id !== id));

  // ── Deductions ──
  const updateDeduction = (key: keyof ReturnDraft['otherSources']['deductions'], value: number): void => { if (disabled) return; patch({ deductions: { ...os.deductions, [key]: value } }); };
  const totalDeductions = money(os.deductions.expenses) + money(os.deductions.interestExpenseEligibleUs57) + money(os.deductions.familyPensionDeductionUs57iia) + money(os.deductions.depreciation);

  // ── Unexplained ──
  const updateUnexplained = (key: keyof ReturnDraft['otherSources']['unexplainedIncome'], value: number): void => { if (disabled) return; patch({ unexplainedIncome: { ...os.unexplainedIncome, [key]: value } }); };

  // ── DTAA aggregates ──
  const updateDtaaAgg = (value: number): void => { if (disabled) return; patch({ dtaaAggregates: { ...os.dtaaAggregates, totalAmountTaxUsDtaa: value } }); };

  return <div>
    <div style={{ marginBottom: 16 }}>
      <h3 style={sectionTitleStyle}>Income from Other Sources (Schedule OS)</h3>
      <div style={sectionSubtitleStyle}>Sections 56–59 · AY 2026-27 · CBDT-compliant</div>
    </div>

    <FormWarning form={form} categories={incompatibilities} />

    {/* ═══ Section 1: Interest income (open) ═══ */}
    <Section title="Interest income" subtitle="Sections 194A, 194K, 244A, 10(11)/10(12) provisos" badge={COMPACT_FORMS.has(form) ? form : undefined} defaultOpen={true} summary={inr(interestTotal)}>
      <div style={subSectionHeaderStyle}>
        <h3 style={sectionTitleStyle}>Interest Entries (CBDT Compliant)</h3>
        <button type="button" style={addButtonStyle} disabled={disabled} onClick={addInterest}>+ Add Interest Entry</button>
      </div>
      {os.interest.length === 0 && <div style={emptyStyle}>No interest entries. Click "+ Add Interest Entry" to add an entry.</div>}
      {os.interest.map((entry, index) => <div key={entry.id} style={entryPanelStyle}>
        <div style={entryHeaderStyle}>
          <h4 style={entryTitleStyle}>Interest Entry #{index + 1} · {interestLabel(entry.kind)}</h4>
          <button type="button" style={removeButtonStyle} disabled={disabled} onClick={() => removeInterest(entry.id)}>Remove</button>
        </div>
        <div style={gridStyle}>
          <div style={wideFieldStyle}>
            <label style={labelStyle}>Nature of interest *</label>
            <select style={selectStyle} value={entry.kind} disabled={disabled} onChange={(event) => updateInterest(entry.id, { kind: event.target.value as InterestKind })}>
              {INTEREST_OPTIONS.map((option) => <option key={option.kind} value={option.kind}>{option.label}</option>)}
            </select>
          </div>
          <Field label="Gross interest (₹) *" type="number" value={entry.grossAmount || ''} disabled={disabled} max={INV} onChange={(value) => updateInterest(entry.id, { grossAmount: money(Number(value)) })} />
          <Field label="TDS deducted (₹)" type="number" value={entry.tdsDeducted || ''} disabled={disabled} max={INV} onChange={(value) => updateInterest(entry.id, { tdsDeducted: money(Number(value)) })} />
        </div>
        <div style={{ ...gridStyle, marginTop: 16 }}>
          <div style={wideFieldStyle}><label style={labelStyle}>Source / institution</label><input style={inputStyle} type="text" value={entry.bankName || entry.deductorName} disabled={disabled} onChange={(event) => updateInterest(entry.id, { bankName: event.target.value })} /></div>
          <div style={wideFieldStyle}><label style={labelStyle}>Deductor TAN</label><input style={inputStyle} type="text" value={entry.deductorTAN} disabled={disabled} onChange={(event) => updateInterest(entry.id, { deductorTAN: event.target.value })} /></div>
        </div>
      </div>)}
    </Section>

    {/* ═══ Section 2: Dividend income (open) ═══ */}
    <Section title="Dividend income" subtitle="Sections 2(22)(e), 2(22)(f), 194, 115BBDA, 115A, 115AC/ACA/AD, DTAA" defaultOpen={true} summary={inr(dividendTotal)}>
      <div style={subSectionHeaderStyle}>
        <h3 style={sectionTitleStyle}>Dividend Entries (CBDT Compliant)</h3>
        <button type="button" style={addButtonStyle} disabled={disabled} onClick={addDividend}>+ Add Dividend Entry</button>
      </div>
      {os.dividends.length === 0 && <div style={emptyStyle}>No dividend entries. Click "+ Add Dividend Entry" to add an entry.</div>}
      {os.dividends.map((entry, index) => <div key={entry.id} style={entryPanelStyle}>
        <div style={entryHeaderStyle}>
          <h4 style={entryTitleStyle}>Dividend Entry #{index + 1} · {dividendLabel(entry.section)}</h4>
          <button type="button" style={removeButtonStyle} disabled={disabled} onClick={() => removeDividend(entry.id)}>Remove</button>
        </div>
        <div style={gridStyle}>
          <div style={wideFieldStyle}>
            <label style={labelStyle}>Section *</label>
            <select style={selectStyle} value={entry.section} disabled={disabled} onChange={(event) => updateDividend(entry.id, { section: event.target.value as DividendSection })}>
              {DIVIDEND_OPTIONS.map((option) => <option key={option.section} value={option.section}>{option.label}</option>)}
            </select>
          </div>
          <Field label="Gross dividend (₹) *" type="number" value={entry.grossAmount || ''} disabled={disabled} max={INV} onChange={(value) => updateDividend(entry.id, { grossAmount: money(Number(value)) })} />
          <Field label="TDS deducted (₹)" type="number" value={entry.tdsDeducted || ''} disabled={disabled} max={INV} onChange={(value) => updateDividend(entry.id, { tdsDeducted: money(Number(value)) })} />
        </div>
        <div style={{ ...gridStyle, marginTop: 16 }}>
          <div style={wideFieldStyle}><label style={labelStyle}>Company / source *</label><input style={inputStyle} type="text" value={entry.companyName} disabled={disabled} onChange={(event) => updateDividend(entry.id, { companyName: event.target.value })} /></div>
          <div style={wideFieldStyle}><label style={labelStyle}>Company PAN</label><input style={inputStyle} type="text" value={entry.companyPAN} disabled={disabled} onChange={(event) => updateDividend(entry.id, { companyPAN: event.target.value })} /></div>
          <div style={wideFieldStyle}><label style={labelStyle}>Deductor TAN</label><input style={inputStyle} type="text" value={entry.deductorTAN} disabled={disabled} onChange={(event) => updateDividend(entry.id, { deductorTAN: event.target.value })} /></div>
          <div style={wideFieldStyle}><label style={labelStyle}>ISIN</label><input style={inputStyle} type="text" value={entry.isin} disabled={disabled} onChange={(event) => updateDividend(entry.id, { isin: event.target.value })} /></div>
          <div>
            <label style={labelStyle}>Category *</label>
            <select style={selectStyle} value={entry.category} disabled={disabled} onChange={(event) => updateDividend(entry.id, { category: event.target.value as DividendIncome['category'] })}>
              <option value="">—</option>
              <option value="EQUITY">Equity</option>
              <option value="PREFERENCE">Preference</option>
              <option value="MUTUAL_FUND">Mutual fund</option>
            </select>
          </div>
        </div>
        <FivePeriodBreakup q1={entry.q1} q2={entry.q2} q3={entry.q3} q4={entry.q4} q5={entry.q5} disabled={disabled} onChange={(field, value) => updateDividend(entry.id, { [field]: value })} />
      </div>)}
    </Section>

    {/* ═══ Section 3: Family pension and ordinary income (collapsed) ═══ */}
    <Section title="Family pension and other ordinary income" subtitle="Family pension (57(iia) ₹25,000 cap), machinery rent, pass-through, other" defaultOpen={false} summary={inr(sum(os.otherIncome) + money(os.familyPension.grossAmount))}>
      <div style={subSectionHeaderStyle}>
        <h3 style={sectionTitleStyle}>Ordinary Income Entries</h3>
        <button type="button" style={addButtonStyle} disabled={disabled} onClick={addOtherIncome}>+ Add Income Entry</button>
      </div>
      {os.otherIncome.length === 0 && money(os.familyPension.grossAmount) === 0 && <div style={emptyStyle}>No entries. Click "+ Add Income Entry" to add an entry.</div>}

      {money(os.familyPension.grossAmount) > 0 && <div style={entryPanelStyle}>
        <div style={entryHeaderStyle}>
          <h4 style={entryTitleStyle}>Family pension</h4>
        </div>
        <div style={gridStyle}>
          <div style={wideFieldStyle}><label style={labelStyle}>Payer name *</label><input style={inputStyle} type="text" value={os.familyPension.payerName} disabled={disabled} onChange={(event) => patch({ familyPension: { ...os.familyPension, payerName: event.target.value } })} /></div>
          <div style={wideFieldStyle}><label style={labelStyle}>Relation to pensioner</label><input style={inputStyle} type="text" value={os.familyPension.relationToPensioner} disabled={disabled} onChange={(event) => patch({ familyPension: { ...os.familyPension, relationToPensioner: event.target.value } })} /></div>
          <Field label="Gross family pension (₹) *" type="number" value={os.familyPension.grossAmount || ''} disabled={disabled} max={INV} onChange={(value) => patch({ familyPension: { ...os.familyPension, grossAmount: money(Number(value)) } })} />
        </div>
        <div style={{ ...gridStyle, marginTop: 16 }}>
          <Field label="Deduction u/s 57(iia) — ₹25,000 cap" type="number" value={familyPensionDeduction} readOnly />
          <Field label="Net family pension (₹)" type="number" value={money(os.familyPension.grossAmount) - familyPensionDeduction} readOnly />
        </div>
      </div>}

      {os.otherIncome.map((entry, index) => <div key={entry.id} style={entryPanelStyle}>
        <div style={entryHeaderStyle}>
          <h4 style={entryTitleStyle}>Income Entry #{index + 1}</h4>
          <button type="button" style={removeButtonStyle} disabled={disabled} onClick={() => removeOtherIncome(entry.id)}>Remove</button>
        </div>
        <div style={gridStyle}>
          <div style={wideFieldStyle}>
            <label style={labelStyle}>Nature of income *</label>
            <select style={selectStyle} value={entry.nature} disabled={disabled} onChange={(event) => updateOtherIncome(entry.id, { nature: event.target.value as 'FAMILY_PENSION' | 'MACHINERY_RENT' | 'OTHER' | 'PASS_THROUGH' })}>
              <option value="FAMILY_PENSION">Family pension</option>
              <option value="MACHINERY_RENT">Rent from machinery, plant or building</option>
              <option value="PASS_THROUGH">Pass-through income (normal rate)</option>
              <option value="OTHER">Any other normal-rate income</option>
            </select>
          </div>
          <Field label="Amount (₹) *" type="number" value={entry.amount || ''} disabled={disabled} max={INV} onChange={(value) => updateOtherIncome(entry.id, { amount: money(Number(value)) })} />
        </div>
        <div style={{ ...gridStyle, marginTop: 16 }}>
          <div style={wideFieldStyle}><label style={labelStyle}>Description</label><input style={inputStyle} type="text" maxLength={125} value={entry.description} disabled={disabled} onChange={(event) => updateOtherIncome(entry.id, { description: event.target.value })} /></div>
        </div>
      </div>)}
    </Section>

    {/* ═══ Section 4: Gifts (collapsed) ═══ */}
    <Section title="Gifts and property — section 56(2)(x)" subtitle="Money, immovable property, other specified property" defaultOpen={false} summary={inr(sum(os.gifts))}>
      <div style={subSectionHeaderStyle}>
        <h3 style={sectionTitleStyle}>Gift Entries (CBDT Compliant)</h3>
        <button type="button" style={addButtonStyle} disabled={disabled} onClick={addGift}>+ Add Gift Entry</button>
      </div>
      {os.gifts.length === 0 && <div style={emptyStyle}>No gifts. Aggregate value above ₹50,000 from non-relatives is taxable.</div>}
      {os.gifts.map((entry, index) => <div key={entry.id} style={entryPanelStyle}>
        <div style={entryHeaderStyle}>
          <h4 style={entryTitleStyle}>Gift Entry #{index + 1} · {entry.propertyType}</h4>
          <button type="button" style={removeButtonStyle} disabled={disabled} onClick={() => removeGift(entry.id)}>Remove</button>
        </div>
        <div style={gridStyle}>
          <div style={wideFieldStyle}>
            <label style={labelStyle}>Property type *</label>
            <select style={selectStyle} value={entry.propertyType} disabled={disabled} onChange={(event) => updateGift(entry.id, { propertyType: event.target.value as GiftIncome['propertyType'] })}>
              <option value="CASH">Money received without consideration</option>
              <option value="IMMOVABLE">Immovable property</option>
              <option value="MOVABLE">Other specified property</option>
            </select>
          </div>
          {entry.propertyType !== 'CASH' && <div style={wideFieldStyle}>
            <label style={labelStyle}>Consideration kind *</label>
            <select style={selectStyle} value={entry.considerationKind} disabled={disabled} onChange={(event) => updateGift(entry.id, { considerationKind: event.target.value as GiftIncome['considerationKind'] })}>
              <option value="WITHOUT_CONSIDERATION">Without consideration</option>
              <option value="INADEQUATE_CONSIDERATION">Inadequate consideration</option>
            </select>
          </div>}
          <div style={wideFieldStyle}><label style={labelStyle}>Donor name *</label><input style={inputStyle} type="text" value={entry.donorName} disabled={disabled} onChange={(event) => updateGift(entry.id, { donorName: event.target.value })} /></div>
          <div style={wideFieldStyle}><label style={labelStyle}>Donor relation</label><input style={inputStyle} type="text" value={entry.donorRelation} disabled={disabled} onChange={(event) => updateGift(entry.id, { donorRelation: event.target.value })} /></div>
          {entry.propertyType === 'IMMOVABLE'
            ? <Field label="Stamp duty value (₹)" type="number" value={entry.stampDutyValue || ''} disabled={disabled} max={INV} onChange={(value) => updateGift(entry.id, { stampDutyValue: money(Number(value)) })} />
            : <Field label="Fair market value (₹)" type="number" value={entry.fairMarketValue || ''} disabled={disabled} max={INV} onChange={(value) => updateGift(entry.id, { fairMarketValue: money(Number(value)) })} />}
          <Field label="Consideration paid (₹)" type="number" value={entry.considerationPaid || ''} disabled={disabled} max={INV} onChange={(value) => updateGift(entry.id, { considerationPaid: money(Number(value)) })} />
          <Field label="Taxable value (₹)" type="number" value={entry.value || ''} readOnly />
          <div><label style={labelStyle}>Date received</label><input style={inputStyle} type="date" value={entry.dateOfReceipt} disabled={disabled} onChange={(event) => updateGift(entry.id, { dateOfReceipt: event.target.value })} /></div>
        </div>
        <div style={{ ...gridStyle, marginTop: 16 }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, marginTop: 24 }}><input type="checkbox" checked={entry.fromRelative} disabled={disabled} onChange={(event) => updateGift(entry.id, { fromRelative: event.target.checked })} /> From relative (exempt)</label>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, marginTop: 24 }}><input type="checkbox" checked={entry.receivedOnMarriage} disabled={disabled} onChange={(event) => updateGift(entry.id, { receivedOnMarriage: event.target.checked })} /> Received on marriage (exempt)</label>
        </div>
      </div>)}
    </Section>

    {/* ═══ Section 5: Winnings (collapsed) ═══ */}
    <Section title="Winnings, online games, unexplained income and race-horse income" subtitle="Sections 115BB, 115BBE, 115BBJ, IncFromOwnHorse" defaultOpen={false} summary={inr(sum(os.winnings))}>
      <FormWarning form={form} categories={['lottery', 'onlineGaming', 'horseRace', 'raceHorseActivity', 'unexplained115BBE'].filter((c) => isCategoryPopulated(c as Category, os)) as Category[]} />
      <div style={subSectionHeaderStyle}>
        <h3 style={sectionTitleStyle}>Winnings Entries (CBDT Compliant)</h3>
        <div style={{ display: 'flex', gap: 8 }}>
          <button type="button" style={addButtonStyle} disabled={disabled} onClick={addWinning}>+ Add Winnings Entry</button>
          <button type="button" style={addButtonStyle} disabled={disabled} onClick={addRaceHorseActivity}>+ Add Race-Horse Activity</button>
        </div>
      </div>
      {os.winnings.length === 0 && <div style={emptyStyle}>No winnings. Lottery, gaming, 115BBE and race-horse income require ITR-2 or ITR-3.</div>}
      {os.winnings.map((entry, index) => <div key={entry.id} style={entryPanelStyle}>
        <div style={entryHeaderStyle}>
          <h4 style={entryTitleStyle}>Entry #{index + 1} · {winningLabel(entry.type)}</h4>
          <button type="button" style={removeButtonStyle} disabled={disabled} onClick={() => removeWinning(entry.id)}>Remove</button>
        </div>
        {entry.type === 'RACE_HORSE_ACTIVITY'
          ? <div style={gridStyle}>
            <Field label="Gross receipts (₹) *" type="number" value={entry.receipts || ''} disabled={disabled} max={INV} onChange={(value) => updateWinning(entry.id, { receipts: money(Number(value)) })} />
            <Field label="Deduction u/s 57 (₹)" type="number" value={entry.deductionUs57 || ''} disabled={disabled} max={INV} onChange={(value) => updateWinning(entry.id, { deductionUs57: money(Number(value)) })} />
            <Field label="Amount not deductible u/s 58 (₹)" type="number" value={entry.amountNotDeductibleUs58 || ''} disabled={disabled} max={INV} onChange={(value) => updateWinning(entry.id, { amountNotDeductibleUs58: money(Number(value)) })} />
            <Field label="Profit chargeable u/s 59 (₹)" type="number" value={entry.profitChargeableUs59 || ''} disabled={disabled} max={INV} onChange={(value) => updateWinning(entry.id, { profitChargeableUs59: money(Number(value)) })} />
            <Field label="Balance (₹)" type="number" value={entry.balance || ''} readOnly />
          </div>
          : <div style={gridStyle}>
            <div style={wideFieldStyle}>
              <label style={labelStyle}>Income type *</label>
              <select style={selectStyle} value={entry.type} disabled={disabled} onChange={(event) => updateWinning(entry.id, { type: event.target.value as WinningIncomeType })}>
                {WINNING_OPTIONS.filter((option) => option.type !== 'RACE_HORSE_ACTIVITY').map((option) => <option key={option.type} value={option.type}>{option.label}</option>)}
              </select>
            </div>
            <Field label="Gross winnings (₹) *" type="number" value={entry.grossAmount || ''} disabled={disabled} max={INV} onChange={(value) => updateWinning(entry.id, { grossAmount: money(Number(value)) })} />
            <Field label="TDS deducted (₹)" type="number" value={entry.tdsDeducted || ''} disabled={disabled} max={INV} onChange={(value) => updateWinning(entry.id, { tdsDeducted: money(Number(value)) })} />
          </div>}
        {entry.type !== 'RACE_HORSE_ACTIVITY' && (
          <div style={{ ...gridStyle, marginTop: 16 }}>
            <div style={wideFieldStyle}><label style={labelStyle}>Payer / source</label><input style={inputStyle} type="text" value={entry.payerName} disabled={disabled} onChange={(event) => updateWinning(entry.id, { payerName: event.target.value })} /></div>
            <div style={wideFieldStyle}><label style={labelStyle}>Payer TAN</label><input style={inputStyle} type="text" value={entry.payerTAN} disabled={disabled} onChange={(event) => updateWinning(entry.id, { payerTAN: event.target.value })} /></div>
            <Field label="Date received" type="date" value={entry.dateOfWinning} disabled={disabled} onChange={(value) => updateWinning(entry.id, { dateOfWinning: value })} />
          </div>
        )}
        {entry.type !== 'RACE_HORSE_ACTIVITY' && (
          <FivePeriodBreakup q1={entry.q1 ?? 0} q2={entry.q2 ?? 0} q3={entry.q3 ?? 0} q4={entry.q4 ?? 0} q5={entry.q5 ?? 0} disabled={disabled} onChange={(field, value) => updateWinning(entry.id, { [field]: value })} />
        )}
      </div>)}
    </Section>

    {/* ═══ Section 6: Deductions (collapsed) ═══ */}
    <Section title="Deductions and adjustments — sections 57–59" subtitle="Expenses, interest, depreciation, 58/59 adjustments" defaultOpen={false} summary={inr(totalDeductions)}>
      <div style={gridStyle}>
        <Field label="Other allowable expenses u/s 57 (₹)" type="number" value={os.deductions.expenses || ''} disabled={disabled} max={INV} onChange={(value) => updateDeduction('expenses', money(Number(value)))} />
        <Field label="Interest expense against dividend (₹)" type="number" value={os.deductions.interestExpenseUs57 || ''} disabled={disabled} max={INV} onChange={(value) => updateDeduction('interestExpenseUs57', money(Number(value)))} />
        <Field label="Eligible interest expense u/s 57 (₹)" type="number" value={os.deductions.interestExpenseEligibleUs57 || ''} disabled={disabled} max={INV} onChange={(value) => updateDeduction('interestExpenseEligibleUs57', money(Number(value)))} />
        <Field label="Family pension deduction u/s 57(iia) (₹)" type="number" value={familyPensionDeduction} readOnly />
        <Field label="Depreciation (₹)" type="number" value={os.deductions.depreciation || ''} disabled={disabled} max={INV} onChange={(value) => updateDeduction('depreciation', money(Number(value)))} />
        <Field label="Total deductions (₹)" type="number" value={totalDeductions} readOnly />
        <Field label="Amount not deductible u/s 58 (₹)" type="number" value={os.deductions.amountNotDeductibleUs58 || ''} disabled={disabled} max={INV} onChange={(value) => updateDeduction('amountNotDeductibleUs58', money(Number(value)))} />
        <Field label="Profit chargeable u/s 59 (₹)" type="number" value={os.deductions.profitChargeableUs59 || ''} disabled={disabled} max={INV} onChange={(value) => updateDeduction('profitChargeableUs59', money(Number(value)))} />
      </div>
    </Section>

    {/* ═══ Section 7: Advanced disclosures (collapsed) ═══ */}
    <Section title="Advanced Other Sources disclosures" subtitle="Sections 68–69D, 89A, accumulated PF, DTAA, special-rate income" defaultOpen={false} badge={COMPACT_FORMS.has(form) ? 'ITR-2/3 only' : undefined} badgeColor="var(--accent-rose)">
      <FormWarning form={form} categories={['unexplained', 'dtaa', 'section89A', 'accumulatedPf', 'specialRate'].filter((c) => isCategoryPopulated(c as Category, os)) as Category[]} />

      {/* Unexplained income — sections 68–69D */}
      <div style={{ marginBottom: 24 }}>
        <h4 style={entryTitleStyle}>Unexplained income — sections 68–69D</h4>
        <div style={{ ...gridStyle, marginTop: 12 }}>
          <Field label="Cash credits u/s 68 (₹)" type="number" value={os.unexplainedIncome.cashCreditsUs68 || ''} disabled={disabled} max={INV} onChange={(value) => updateUnexplained('cashCreditsUs68', money(Number(value)))} />
          <Field label="Unexplained investments u/s 69 (₹)" type="number" value={os.unexplainedIncome.unexplainedInvestmentsUs69 || ''} disabled={disabled} max={INV} onChange={(value) => updateUnexplained('unexplainedInvestmentsUs69', money(Number(value)))} />
          <Field label="Unexplained money u/s 69A (₹)" type="number" value={os.unexplainedIncome.unexplainedMoneyUs69A || ''} disabled={disabled} max={INV} onChange={(value) => updateUnexplained('unexplainedMoneyUs69A', money(Number(value)))} />
          <Field label="Undisclosed investments u/s 69B (₹)" type="number" value={os.unexplainedIncome.undisclosedInvestmentsUs69B || ''} disabled={disabled} max={INV} onChange={(value) => updateUnexplained('undisclosedInvestmentsUs69B', money(Number(value)))} />
          <Field label="Unexplained expenditure u/s 69C (₹)" type="number" value={os.unexplainedIncome.unexplainedExpenditureUs69C || ''} disabled={disabled} max={INV} onChange={(value) => updateUnexplained('unexplainedExpenditureUs69C', money(Number(value)))} />
          <Field label="Hundi borrowing u/s 69D (₹)" type="number" value={os.unexplainedIncome.hundiBorrowingUs69D || ''} disabled={disabled} max={INV} onChange={(value) => updateUnexplained('hundiBorrowingUs69D', money(Number(value)))} />
          <Field label="Prior-year business trust receipt u/s 56(2)(xii) (₹)" type="number" value={os.unexplainedIncome.priorYearBusinessTrust562xii || ''} disabled={disabled} max={INV} onChange={(value) => updateUnexplained('priorYearBusinessTrust562xii', money(Number(value)))} />
          <Field label="Prior-year life insurance receipt u/s 56(2)(xiii) (₹)" type="number" value={os.unexplainedIncome.priorYearLifeInsurance562xiii || ''} disabled={disabled} max={INV} onChange={(value) => updateUnexplained('priorYearLifeInsurance562xiii', money(Number(value)))} />
        </div>
      </div>

      {/* Section 89A — vertical entries + aggregates */}
      <div style={{ marginBottom: 24 }}>
        <div style={subSectionHeaderStyle}>
          <h3 style={sectionTitleStyle}>Section 89A Entries (CBDT Compliant)</h3>
          <button type="button" style={addButtonStyle} disabled={disabled} onClick={add89A}>+ Add 89A Entry</button>
        </div>
        {os.section89A.length === 0 && <div style={emptyStyle}>No 89A entries. Click "+ Add 89A Entry" to add.</div>}
        {os.section89A.map((entry, index) => <div key={entry.id} style={entryPanelStyle}>
          <div style={entryHeaderStyle}>
            <h4 style={entryTitleStyle}>89A Entry #{index + 1}</h4>
            <button type="button" style={removeCircleButtonStyle} disabled={disabled} onClick={() => remove89A(entry.id)}>×</button>
          </div>
          <div style={gridStyle}>
            <div>
              <label style={labelStyle}>Country code *</label>
              <select style={selectStyle} value={entry.countryCode} disabled={disabled} onChange={(event) => update89A(entry.id, { countryCode: event.target.value as 'US' | 'UK' | 'CA' })}>
                <option value="US">US</option>
                <option value="UK">UK</option>
                <option value="CA">CA</option>
              </select>
            </div>
            <Field label="Amount (₹) *" type="number" value={entry.amount || ''} disabled={disabled} max={INV} onChange={(value) => update89A(entry.id, { amount: money(Number(value)) })} />
          </div>
        </div>)}
        <div style={{ ...gridStyle, marginTop: 16 }}>
          <Field label="Income notified u/s 89A (aggregate) (₹)" type="number" value={os.section89AAggregates.incomeNotified89AOS || ''} disabled={disabled} max={INV} onChange={(value) => update89AAgg('incomeNotified89AOS', money(Number(value)))} />
          <Field label="Income notified other u/s 89A (₹)" type="number" value={os.section89AAggregates.incomeNotifiedOther89AOS || ''} disabled={disabled} max={INV} onChange={(value) => update89AAgg('incomeNotifiedOther89AOS', money(Number(value)))} />
          <Field label="Income notified prior year u/s 89A (₹)" type="number" value={os.section89AAggregates.incomeNotifiedPriorYear89AOS || ''} disabled={disabled} max={INV} onChange={(value) => update89AAgg('incomeNotifiedPriorYear89AOS', money(Number(value)))} />
          <Field label="Income relief u/s 89A (₹)" type="number" value={os.section89AAggregates.incomeReliefUs89AOS || ''} disabled={disabled} max={INV} onChange={(value) => update89AAgg('incomeReliefUs89AOS', money(Number(value)))} />
        </div>
      </div>

      {/* Accumulated PF — vertical entries + aggregates */}
      <div style={{ marginBottom: 24 }}>
        <div style={subSectionHeaderStyle}>
          <h3 style={sectionTitleStyle}>Accumulated PF Entries (CBDT Compliant)</h3>
          <button type="button" style={addButtonStyle} disabled={disabled} onClick={addPf}>+ Add PF Entry</button>
        </div>
        {os.accumulatedPf.length === 0 && <div style={emptyStyle}>No PF entries. Click "+ Add PF Entry" to add.</div>}
        {os.accumulatedPf.map((entry, index) => <div key={entry.id} style={entryPanelStyle}>
          <div style={entryHeaderStyle}>
            <h4 style={entryTitleStyle}>PF Entry #{index + 1}</h4>
            <button type="button" style={removeCircleButtonStyle} disabled={disabled} onClick={() => removePf(entry.id)}>×</button>
          </div>
          <div style={gridStyle}>
            <div>
              <label style={labelStyle}>Assessment year *</label>
              <select style={selectStyle} value={entry.assessmentYear} disabled={disabled} onChange={(event) => updatePf(entry.id, { assessmentYear: event.target.value as PfAssessmentYear })}>
                {PF_ASSESSMENT_YEARS.map((year) => <option key={year} value={year}>{year}</option>)}
              </select>
            </div>
            <Field label="Income benefit (₹)" type="number" value={entry.incomeBenefit || ''} disabled={disabled} max={INV} onChange={(value) => updatePf(entry.id, { incomeBenefit: money(Number(value)) })} />
            <Field label="Tax benefit (₹)" type="number" value={entry.taxBenefit || ''} disabled={disabled} max={INV} onChange={(value) => updatePf(entry.id, { taxBenefit: money(Number(value)) })} />
          </div>
        </div>)}
        <div style={{ ...gridStyle, marginTop: 16 }}>
          <Field label="Total income benefit (aggregate) (₹)" type="number" value={os.accumulatedPfAggregates.totalIncomeBenefit || ''} disabled={disabled} max={INV} onChange={(value) => updatePfAgg('totalIncomeBenefit', money(Number(value)))} />
          <Field label="Total tax benefit (aggregate) (₹)" type="number" value={os.accumulatedPfAggregates.totalTaxBenefit || ''} disabled={disabled} max={INV} onChange={(value) => updatePfAgg('totalTaxBenefit', money(Number(value)))} />
        </div>
      </div>

      {/* DTAA income — vertical entries + 5-period breakup + aggregates */}
      <div style={{ marginBottom: 24 }}>
        <div style={subSectionHeaderStyle}>
          <h3 style={sectionTitleStyle}>DTAA Income Entries (CBDT Compliant)</h3>
          <button type="button" style={addButtonStyle} disabled={disabled} onClick={addDtaa}>+ Add DTAA Entry</button>
        </div>
        {os.dtaaIncome.length === 0 && <div style={emptyStyle}>No DTAA entries. Click "+ Add DTAA Entry" to add.</div>}
        {os.dtaaIncome.map((entry, index) => <div key={entry.id} style={entryPanelStyle}>
          <div style={entryHeaderStyle}>
            <h4 style={entryTitleStyle}>DTAA Entry #{index + 1}</h4>
            <button type="button" style={removeButtonStyle} disabled={disabled} onClick={() => removeDtaa(entry.id)}>Remove</button>
          </div>
          <div style={gridStyle}>
            <div style={wideFieldStyle}>
              <label style={labelStyle}>Nature of income *</label>
              <select style={selectStyle} value={entry.natureOfIncome} disabled={disabled} onChange={(event) => updateDtaa(entry.id, { natureOfIncome: event.target.value as DtaaIncomeEntry['natureOfIncome'] })}>
                {DTAA_NATURE_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
              </select>
            </div>
            <div style={wideFieldStyle}><label style={labelStyle}>Item no. (incl.)</label><input style={inputStyle} type="text" value={entry.itemNoIncl} disabled={disabled} onChange={(event) => updateDtaa(entry.id, { itemNoIncl: event.target.value })} /></div>
            <div style={wideFieldStyle}><label style={labelStyle}>Country name</label><input style={inputStyle} type="text" value={entry.countryName} disabled={disabled} onChange={(event) => updateDtaa(entry.id, { countryName: event.target.value })} /></div>
            <div style={wideFieldStyle}><label style={labelStyle}>Country code</label><input style={inputStyle} type="text" value={entry.countryCode} disabled={disabled} onChange={(event) => updateDtaa(entry.id, { countryCode: event.target.value })} /></div>
            <div style={wideFieldStyle}><label style={labelStyle}>DTAA article</label><input style={inputStyle} type="text" value={entry.dtaaArticle} disabled={disabled} onChange={(event) => updateDtaa(entry.id, { dtaaArticle: event.target.value })} /></div>
            <Field label="Amount (₹) *" type="number" value={entry.amount || ''} disabled={disabled} max={INV} onChange={(value) => updateDtaa(entry.id, { amount: money(Number(value)) })} />
            <Field label="Rate as per treaty (%)" type="number" value={entry.rateAsPerTreaty || ''} disabled={disabled} max={100} onChange={(value) => updateDtaa(entry.id, { rateAsPerTreaty: money(Number(value)) })} />
            <Field label="Rate as per IT Act (%)" type="number" value={entry.rateAsPerITAct || ''} disabled={disabled} max={100} onChange={(value) => updateDtaa(entry.id, { rateAsPerITAct: money(Number(value)) })} />
            <Field label="Applicable rate (%)" type="number" value={entry.applicableRate || ''} disabled={disabled} max={100} onChange={(value) => updateDtaa(entry.id, { applicableRate: money(Number(value)) })} />
            <div>
              <label style={labelStyle}>Tax residency certificate *</label>
              <select style={selectStyle} value={entry.taxResidencyCertificate} disabled={disabled} onChange={(event) => updateDtaa(entry.id, { taxResidencyCertificate: event.target.value as 'Y' | 'N' })}>
                <option value="Y">Yes</option>
                <option value="N">No</option>
              </select>
            </div>
          </div>
          <FivePeriodBreakup q1={entry.q1} q2={entry.q2} q3={entry.q3} q4={entry.q4} q5={entry.q5} disabled={disabled} onChange={(field, value) => updateDtaa(entry.id, { [field]: value })} />
        </div>)}
        <div style={{ ...gridStyle, marginTop: 16 }}>
          <Field label="Total amount taxable u/s DTAA (aggregate) (₹)" type="number" value={os.dtaaAggregates.totalAmountTaxUsDtaa || ''} disabled={disabled} max={INV} onChange={(value) => updateDtaaAgg(money(Number(value)))} />
        </div>
      </div>

      {/* Special-rate income — OthersGrossDtls (21-value enum) */}
      <div>
        <div style={subSectionHeaderStyle}>
          <h3 style={sectionTitleStyle}>Special-Rate Income Entries (CBDT Compliant)</h3>
          <button type="button" style={addButtonStyle} disabled={disabled} onClick={addSpecialRate}>+ Add Special-Rate Entry</button>
        </div>
        {os.specialRateIncome.length === 0 && <div style={emptyStyle}>No special-rate entries. Click "+ Add Special-Rate Entry" to add income chargeable at special rates (115A, 115AC, 115ACA, 115AD, 115BBA, 115BBF, 115BBG, 115E, etc.).</div>}
        {os.specialRateIncome.map((entry, index) => <div key={entry.id} style={entryPanelStyle}>
          <div style={entryHeaderStyle}>
            <h4 style={entryTitleStyle}>Special-Rate Entry #{index + 1} · {specialRateLabel(entry.sourceDescription)}</h4>
            <button type="button" style={removeButtonStyle} disabled={disabled} onClick={() => removeSpecialRate(entry.id)}>Remove</button>
          </div>
          <div style={gridStyle}>
            <div style={wideFieldStyle}>
              <label style={labelStyle}>Source description *</label>
              <select style={selectStyle} value={entry.sourceDescription} disabled={disabled} onChange={(event) => updateSpecialRate(entry.id, { sourceDescription: event.target.value as SpecialRateSourceDescription })}>
                {SPECIAL_RATE_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
              </select>
            </div>
            <Field label="Source amount (₹) *" type="number" value={entry.sourceAmount || ''} disabled={disabled} max={INV} onChange={(value) => updateSpecialRate(entry.id, { sourceAmount: money(Number(value)) })} />
          </div>
        </div>)}
      </div>
    </Section>

    {/* ═══ Review summary ═══ */}
    <div style={summaryPanelStyle}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <ApplicabilityBadge form={form} />
        <h4 style={{ ...entryTitleStyle, fontSize: 14 }}>Schedule OS review</h4>
      </div>
      <div style={summaryRowStyle}><span>Interest income</span><span>{inr(interestTotal)}</span></div>
      <div style={summaryRowStyle}><span>Dividend income</span><span>{inr(dividendTotal)}</span></div>
      <div style={summaryRowStyle}><span>Family pension (gross)</span><span>{inr(money(os.familyPension.grossAmount))}</span></div>
      <div style={summaryRowStyle}><span>Other ordinary income</span><span>{inr(sum(os.otherIncome))}</span></div>
      <div style={summaryRowStyle}><span>Gifts / section 56(2)(x)</span><span>{inr(sum(os.gifts))}</span></div>
      <div style={summaryRowStyle}><span>Winnings and race-horse activity</span><span>{inr(sum(os.winnings))}</span></div>
      <div style={summaryRowStyle}><span>Special-rate income</span><span>{inr(sum(os.specialRateIncome))}</span></div>
      <div style={{ ...summaryRowStyle, borderTop: '1px solid var(--border)', marginTop: 8, paddingTop: 8, fontWeight: 600 }}><span>Gross other sources</span><span>{inr(interestTotal + dividendTotal + money(os.familyPension.grossAmount) + sum(os.otherIncome) + sum(os.gifts) + sum(os.winnings) + sum(os.specialRateIncome))}</span></div>
      <div style={summaryRowStyle}><span>Less: deductions u/s 57</span><span>-{inr(totalDeductions)}</span></div>
      {incompatibilities.length > 0 && <div style={{ ...summaryRowStyle, color: 'var(--warning)' }}><span>Form compatibility</span><span>⚠ {incompatibilities.length} incompatible categor{incompatibilities.length === 1 ? 'y' : 'ies'}</span></div>}
    </div>
  </div>;
}
