import React, { useEffect, useRef, useState } from 'react';
import { NATURE_CODES_44AD, NATURE_CODES_44ADA, NATURE_CODES_44AE, type OfficialCodeOption } from './ITR4ScheduleBPData';

const MONEY_MAX = 99_999_999_999_999;
const AD_MAX = 30_000_000;
const ADA_MAX = 7_500_000;

/** One business reported under section 44AD. */
export interface NatOfBus44AD {
  NameOfBusiness: string;
  CodeAD: string;
  Description?: string;
}

/** Presumptive-income particulars under section 44AD. */
export interface PersumptiveInc44AD {
  GrsTotalTrnOver: number;
  GrsTrnOverBank?: number;
  GrsTotalTrnOverInCash?: number;
  GrsTrnOverAnyOthMode?: number;
  PersumptiveInc44AD6Per?: number;
  PersumptiveInc44AD8Per?: number;
  TotPersumptiveInc44AD: number;
}

/** One profession reported under section 44ADA. */
export interface NatOfBus44ADA {
  NameOfBusiness: string;
  CodeADA: string;
  Description?: string;
}

/** Presumptive-income particulars under section 44ADA. */
export interface PersumptiveInc44ADA {
  GrsReceipt: number;
  GrsTrnOverBank44ADA?: number;
  GrsTotalTrnOverInCash44ADA?: number;
  GrsTrnOverAnyOthMode44ADA?: number;
  TotPersumptiveInc44ADA: number;
}

/** One transport business reported under section 44AE. */
export interface NatOfBus44AE {
  NameOfBusiness: string;
  CodeAE: string;
  Description?: string;
}

/** Goods-carriage particulars under section 44AE. */
export interface GoodsDtlsUs44AE {
  RegNumberGoodsCarriage: string;
  OwnedLeasedHiredFlag: 'OWN' | 'LEASE' | 'HIRED';
  TonnageCapacity: number;
  HoldingPeriod: number;
  PresumptiveIncome: number;
}

/** Presumptive-income totals under section 44AE. */
export interface PersumptiveInc44AE {
  TotPersumInc44AE: number;
  SalInterestByFirm?: number;
  TotalPersumptiveInc: number;
  IncChargeableUnderBus: number;
}

/** Turnover or gross receipts attributed to one GSTIN. */
export interface TurnoverGrsRcptForGSTIN {
  GSTINNo: string;
  AmtTurnGrossRcptGSTIN: number;
}

/** Financial particulars of the presumptive business. */
export interface FinanclPartclrOfBusiness {
  PartnerMemberOwnCapital?: number;
  SecuredLoans?: number;
  UnSecuredLoans?: number;
  Advances?: number;
  SundryCreditors?: number;
  OthrCurrLiab?: number;
  TotCapLiabilities?: number;
  FixedAssets?: number;
  Investments?: number;
  Inventories?: number;
  SundryDebtors?: number;
  BalWithBanks?: number;
  CashInHand?: number;
  LoansAndAdvances?: number;
  OtherAssets?: number;
  TotalAssets?: number;
}

/** Exact AY 2026-27 ITR-4 ScheduleBP data shape. */
export interface ITR4ScheduleBPData {
  NatOfBus44AD?: NatOfBus44AD[];
  PersumptiveInc44AD?: PersumptiveInc44AD;
  NatOfBus44ADA?: NatOfBus44ADA[];
  PersumptiveInc44ADA?: PersumptiveInc44ADA;
  NatOfBus44AE?: NatOfBus44AE[];
  GoodsDtlsUs44AE?: GoodsDtlsUs44AE[];
  PersumptiveInc44AE?: PersumptiveInc44AE;
  TurnoverGrsRcptForGSTIN?: TurnoverGrsRcptForGSTIN[];
  TotalTurnoverGrsRcptGSTIN?: number;
  FinanclPartclrOfBusiness?: FinanclPartclrOfBusiness;
}

/** Props for the official ITR-4 Schedule BP editor. */
export interface ITR4ScheduleBPManagerProps {
  data?: ITR4ScheduleBPData | null;
  onChange: (data: ITR4ScheduleBPData) => void;
  /** Prior-year (lastFiledITR) figures shown as read-only reference labels
   *  above each input field, so the user can see last year's filed values
   *  while entering this year's figures. */
  priorYearData?: ITR4ScheduleBPData | null;
}

type NatureRow = NatOfBus44AD | NatOfBus44ADA | NatOfBus44AE;
type NatureArrayKey = 'NatOfBus44AD' | 'NatOfBus44ADA' | 'NatOfBus44AE';
type CodeKey = 'CodeAD' | 'CodeADA' | 'CodeAE';
type NumberRecord = Record<string, number | undefined>;

const styles: Record<string, React.CSSProperties> = {
  card: { marginBottom: 24, padding: 16, background: 'var(--bg)', borderRadius: 6, border: '1px solid var(--border)' },
  head: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, marginBottom: 12 },
  body: {},
  grid: { display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 16 },
  label: { display: 'block', marginBottom: 6, fontSize: 12, fontWeight: 500, color: 'var(--text-secondary)' },
  input: { width: '100%', boxSizing: 'border-box', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6, fontSize: 13, color: 'var(--text-primary)', background: '#fff' },
  readOnly: { width: '100%', boxSizing: 'border-box', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6, fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', background: 'var(--gold-pale)' },
  row: { marginBottom: 24, padding: 16, background: 'var(--bg)', borderRadius: 6, border: '1px solid var(--border)' },
  button: { padding: '6px 12px', background: 'var(--gold)', color: '#fff', border: 'none', borderRadius: 6, fontSize: 12, cursor: 'pointer' },
  remove: { padding: '4px 8px', background: 'var(--danger)', color: '#fff', border: 'none', borderRadius: 4, fontSize: 11, cursor: 'pointer' },
  empty: { padding: 24, textAlign: 'center', color: 'var(--text-muted)', background: 'var(--bg)', borderRadius: 6, marginBottom: 24 },
  sectionHeader: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 },
  priorLabel: { display: 'block', marginBottom: 2, fontSize: 10, color: 'var(--text-muted)', fontStyle: 'italic' },
  priorValue: { display: 'block', marginBottom: 4, fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)', background: 'var(--gold-pale)', padding: '2px 6px', borderRadius: 4, border: '1px solid var(--border)' },
  priorBanner: { marginBottom: 16, padding: '10px 14px', background: 'var(--gold-pale)', border: '1px solid var(--border)', borderRadius: 6, fontSize: 12, color: 'var(--text-secondary)' },
};

const toAmount = (value: string, maximum: number = MONEY_MAX, minimum = 0): number => {
  if (value.trim() === '') return 0;
  const parsed = Math.trunc(Number(value));
  if (!Number.isFinite(parsed)) return 0;
  return Math.min(maximum, Math.max(minimum, parsed));
};

const toNum = (value: number | string | undefined | null): number => {
  // Coerce every value to a finite number. A numeric string (e.g. "215420"
  // arriving from a backend/prior-year load) would otherwise trigger JS
  // string concatenation inside reduce (0 + "215420" = "0215420"),
  // inflating the turnover 10x and cascading into the presumptive income.
  if (typeof value === 'number') return Number.isFinite(value) ? value : 0;
  if (value == null) return 0;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
};
const sum = (values: Array<number | undefined>): number => Math.min(MONEY_MAX, values.reduce<number>((total, value) => total + toNum(value), 0));
const amount = (value: number | string | undefined): string => {
  // Coerce to a number before stringifying so a persisted garbage string
  // (e.g. "0000...215420" from a prior string-concat bug) never renders
  // literally in the numeric input. NaN/undefined -> ''.
  const n = toNum(value);
  return n ? String(n) : '';
};
const formatRupee = (value: number | undefined): string => value ? `₹${Number(value).toLocaleString('en-IN')} (last year)` : '';

const derive = (input?: ITR4ScheduleBPData | null): ITR4ScheduleBPData => {
  const result: ITR4ScheduleBPData = {
    ...(input ?? {}),
    NatOfBus44AD: [...(input?.NatOfBus44AD ?? [])],
    NatOfBus44ADA: [...(input?.NatOfBus44ADA ?? [])],
    NatOfBus44AE: [...(input?.NatOfBus44AE ?? [])],
    GoodsDtlsUs44AE: [...(input?.GoodsDtlsUs44AE ?? [])].slice(0, 10),
    TurnoverGrsRcptForGSTIN: [...(input?.TurnoverGrsRcptForGSTIN ?? [])],
    FinanclPartclrOfBusiness: { ...(input?.FinanclPartclrOfBusiness ?? {}) },
  };
  if (input?.PersumptiveInc44AD) {
    const p = { ...input.PersumptiveInc44AD } as PersumptiveInc44AD & { _override6Per?: boolean; _override8Per?: boolean };
    p.GrsTotalTrnOver = sum([p.GrsTrnOverBank, p.GrsTotalTrnOverInCash, p.GrsTrnOverAnyOthMode]);
    // Section 44AD statutory split: 6% applies ONLY to turnover received
    // through banking/digital modes; the balance (cash + any other non-
    // banking mode) attracts 8%. "Any other mode" is a non-banking receipt
    // so it goes in the 8% bucket, NOT 6%.
    const sixBase = toNum(p.GrsTrnOverBank);
    const eightBase = sum([p.GrsTotalTrnOverInCash, p.GrsTrnOverAnyOthMode]);
    // Half-up rounding to the nearest rupee matches the statutory CBDT
    // convention (app/engine/itd/common._to_rupees) so the frontend preview
    // reconciles exactly with the generated JSON.
    const statutorySix = Math.round(sixBase * 0.06);
    const statutoryEight = Math.round(eightBase * 0.08);
    // The taxpayer may offer MORE than the presumptive minimum (Section 44AD
    // lets the assessee declare higher income). When the override flag is
    // off, the field auto-computes to the statutory minimum and is read-only.
    // When on, the user-entered value is preserved (clamped to >= minimum so
    // it can never fall below the statutory floor).
    if (!p._override6Per) p.PersumptiveInc44AD6Per = statutorySix;
    else p.PersumptiveInc44AD6Per = Math.max(statutorySix, toNum(p.PersumptiveInc44AD6Per));
    if (!p._override8Per) p.PersumptiveInc44AD8Per = statutoryEight;
    else p.PersumptiveInc44AD8Per = Math.max(statutoryEight, toNum(p.PersumptiveInc44AD8Per));
    p.TotPersumptiveInc44AD = sum([p.PersumptiveInc44AD6Per, p.PersumptiveInc44AD8Per]);
    result.PersumptiveInc44AD = p;
  }
  if (input?.PersumptiveInc44ADA) {
    const p = { ...input.PersumptiveInc44ADA };
    p.GrsReceipt = sum([p.GrsTrnOverBank44ADA, p.GrsTotalTrnOverInCash44ADA, p.GrsTrnOverAnyOthMode44ADA]);
    result.PersumptiveInc44ADA = p;
  }
  const normalizedVehicles = result.GoodsDtlsUs44AE ?? [];
  if (input?.PersumptiveInc44AE || normalizedVehicles.length > 0) {
    const salary = input?.PersumptiveInc44AE?.SalInterestByFirm ?? 0;
    const vehicleIncome = sum(normalizedVehicles.map((row) => row.PresumptiveIncome));
    const businessIncome = sum([
      result.PersumptiveInc44AD?.TotPersumptiveInc44AD,
      result.PersumptiveInc44ADA?.TotPersumptiveInc44ADA,
      Math.max(0, vehicleIncome - salary),
    ]);
    result.PersumptiveInc44AE = {
      SalInterestByFirm: salary,
      TotPersumInc44AE: vehicleIncome,
      TotalPersumptiveInc: Math.max(0, vehicleIncome - salary),
      IncChargeableUnderBus: businessIncome,
    };
  }
  result.TotalTurnoverGrsRcptGSTIN = sum((result.TurnoverGrsRcptForGSTIN ?? []).map((row) => row.AmtTurnGrossRcptGSTIN));
  const f = result.FinanclPartclrOfBusiness ?? {};
  f.TotCapLiabilities = sum([f.PartnerMemberOwnCapital, f.SecuredLoans, f.UnSecuredLoans, f.Advances, f.SundryCreditors, f.OthrCurrLiab]);
  f.TotalAssets = sum([f.FixedAssets, f.Investments, f.Inventories, f.SundryDebtors, f.BalWithBanks, f.CashInHand, f.LoansAndAdvances, f.OtherAssets]);
  result.FinanclPartclrOfBusiness = f;
  return result;
};

function Field({ label, value, onChange, max = MONEY_MAX, min = 0, readOnly = false, priorValue, overrideFlag, onToggleOverride }: { label: string; value?: number; onChange?: (value: number) => void; max?: number; min?: number; readOnly?: boolean; priorValue?: number; overrideFlag?: boolean; onToggleOverride?: () => void; }): React.JSX.Element {
  return <label>
    <span style={styles.label}>{label}{onToggleOverride && <span style={{ marginLeft: 8, fontSize: 10, color: 'var(--text-muted)' }}>[{overrideFlag ? 'declared higher' : 'auto: statutory minimum'}]</span>}</span>
    {onToggleOverride && <label style={{ display: 'flex', alignItems: 'center', gap: 4, marginTop: 2, fontSize: 10, color: 'var(--text-muted)' }}><input type="checkbox" checked={Boolean(overrideFlag)} onChange={onToggleOverride} style={{ margin: 0 }} />Declare higher than minimum</label>}
    {priorValue !== undefined && priorValue !== 0 && <>
      <span style={styles.priorLabel}>Last year filed</span>
      <span style={styles.priorValue}>{formatRupee(priorValue)}</span>
    </>}
    <input aria-label={label} type="number" min={min} max={max} step="1" value={amount(value)} readOnly={readOnly} onChange={(event) => onChange?.(toAmount(event.target.value, max, min))} style={readOnly ? styles.readOnly : styles.input} />
  </label>;
}

function Card({ title, subtitle, action, children }: { title: string; subtitle?: string; action?: React.ReactNode; children: React.ReactNode }): React.JSX.Element {
  return <section style={styles.card}><div style={styles.head}><div><h4 style={{ margin: 0, fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)' }}>{title}</h4>{subtitle && <div style={{ marginTop: 4, color: 'var(--text-muted)', fontSize: 11 }}>{subtitle}</div>}</div>{action}</div><div style={styles.body}>{children}</div></section>;
}

function NatureEditor({ title, arrayKey, codeKey, rows, options, emit, details }: { title: string; arrayKey: NatureArrayKey; codeKey: CodeKey; rows: NatureRow[]; options: readonly OfficialCodeOption[]; emit: (patch: Partial<ITR4ScheduleBPData>) => void; details?: React.ReactNode }): React.JSX.Element {
  const update = (index: number, key: string, value: string): void => {
    const next = rows.map((row, i) => i === index ? { ...row, [key]: value } : row);
    emit({ [arrayKey]: next } as Partial<ITR4ScheduleBPData>);
  };
  const add = (): void => emit({ [arrayKey]: [...rows, { NameOfBusiness: '', [codeKey]: '' }] } as Partial<ITR4ScheduleBPData>);
  const remove = (index: number): void => emit({ [arrayKey]: rows.filter((_, i) => i !== index) } as Partial<ITR4ScheduleBPData>);
  return <div style={{ marginBottom: 28 }}>
    <div style={styles.sectionHeader}>
      <div><h3 style={{ margin: 0, fontSize: 14, fontWeight: 600, color: 'var(--text-secondary)' }}>{title}</h3><div style={{ marginTop: 4, fontSize: 11, color: 'var(--text-muted)' }}>Official AY 2026-27 business/profession codes</div></div>
      <button type="button" style={styles.button} onClick={add}>+ Add entry</button>
    </div>
    {rows.length === 0 && <div style={styles.empty}>No entries. Click “Add entry” to add one.</div>}
    {rows.map((row, index) => <div style={styles.row} key={`${arrayKey}-${index}`}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}><h4 style={{ margin: 0, fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)' }}>Entry #{index + 1}{row.NameOfBusiness ? ` — ${row.NameOfBusiness}` : ''}</h4><button type="button" style={styles.remove} onClick={() => remove(index)}>Remove</button></div>
      <div style={styles.grid}>
        <label><span style={styles.label}>Name of business *</span><input style={styles.input} maxLength={75} value={row.NameOfBusiness} onChange={(e) => update(index, 'NameOfBusiness', e.target.value)} /></label>
        <label><span style={styles.label}>Nature code *</span><select style={styles.input} value={(row as unknown as Record<string, string>)[codeKey] ?? ''} onChange={(e) => update(index, codeKey, e.target.value)}><option value="">Select official code</option>{options.map(([code, text]) => <option key={code} value={code}>{code} - {text}</option>)}</select></label>
        <label><span style={styles.label}>Description</span><input style={styles.input} maxLength={75} value={row.Description ?? ''} onChange={(e) => update(index, 'Description', e.target.value)} /></label>
      </div>
      {index === 0 && details && <div style={{ marginTop: 20, paddingTop: 16, borderTop: '1px solid var(--border)' }}>{details}</div>}
    </div>)}
  </div>;
}

/** Edits the exact official AY 2026-27 ITR-4 ScheduleBP structure. */
export default function ITR4ScheduleBPManager({ data, onChange, priorYearData }: ITR4ScheduleBPManagerProps): React.JSX.Element {
  const current = derive(data);
  const prior = priorYearData ? derive(priorYearData) : null;
  const lastNormalized = useRef<string>('');
  // "Declare higher" override flags for the 6%/8% presumptive fields.
  // Persisted on the data object as _override6Per/_override8Per (prefixed so
  // they never leak into the official CBDT JSON, which serializes only the
  // official ScheduleBP keys). Off = auto-compute the statutory minimum
  // (read-only); On = let the taxpayer declare a higher income (>= minimum).
  const [override6, setOverride6] = useState<boolean>(Boolean((current.PersumptiveInc44AD as never as { _override6Per?: boolean } | undefined)?._override6Per));
  const [override8, setOverride8] = useState<boolean>(Boolean((current.PersumptiveInc44AD as never as { _override8Per?: boolean } | undefined)?._override8Per));
  const toggleOverride6 = (): void => {
    const next = !override6;
    setOverride6(next);
    emit({ PersumptiveInc44AD: { ...((current.PersumptiveInc44AD as object | undefined) ?? {}), _override6Per: next } as never } as Partial<ITR4ScheduleBPData>);
  };
  const toggleOverride8 = (): void => {
    const next = !override8;
    setOverride8(next);
    emit({ PersumptiveInc44AD: { ...((current.PersumptiveInc44AD as object | undefined) ?? {}), _override8Per: next } as never } as Partial<ITR4ScheduleBPData>);
  };
  useEffect(() => {
    const incoming = JSON.stringify(data ?? {});
    const normalized = JSON.stringify(current);
    if (incoming !== normalized && lastNormalized.current !== normalized) {
      lastNormalized.current = normalized;
      onChange(current);
    }
  }, [data, current, onChange]);

  const emit = (patch: Partial<ITR4ScheduleBPData>): void => onChange(derive({ ...current, ...patch }));
  const updateObject = <K extends keyof ITR4ScheduleBPData>(key: K, patch: Record<string, number>): void => emit({ [key]: { ...((current[key] as object | undefined) ?? {}), ...patch } } as Partial<ITR4ScheduleBPData>);
  const ad = current.PersumptiveInc44AD ?? { GrsTotalTrnOver: 0, TotPersumptiveInc44AD: 0 };
  const ada = current.PersumptiveInc44ADA ?? { GrsReceipt: 0, TotPersumptiveInc44ADA: 0 };
  const ae = current.PersumptiveInc44AE ?? { TotPersumInc44AE: 0, TotalPersumptiveInc: 0, IncChargeableUnderBus: 0 };
  const vehicles = current.GoodsDtlsUs44AE ?? [];
  const gstRows = current.TurnoverGrsRcptForGSTIN ?? [];
  const financial = current.FinanclPartclrOfBusiness ?? {};
  const priorAd = prior?.PersumptiveInc44AD;
  const priorAda = prior?.PersumptiveInc44ADA;
  const priorAe = prior?.PersumptiveInc44AE;
  const priorFinancial = prior?.FinanclPartclrOfBusiness;
  const hasPrior = prior !== null && (
    (priorAd && (priorAd.GrsTotalTrnOver || priorAd.TotPersumptiveInc44AD)) !== undefined
    || (priorAda && (priorAda.GrsReceipt || priorAda.TotPersumptiveInc44ADA))
    || (priorAe && priorAe.TotPersumInc44AE)
    || (priorFinancial && (priorFinancial.TotalAssets || priorFinancial.TotCapLiabilities))
  );

  const setVehicle = (index: number, patch: Partial<GoodsDtlsUs44AE>): void => emit({ GoodsDtlsUs44AE: vehicles.map((row, i) => i === index ? { ...row, ...patch } : row) });
  const addVehicle = (): void => { if (vehicles.length < 10) emit({ GoodsDtlsUs44AE: [...vehicles, { RegNumberGoodsCarriage: '', OwnedLeasedHiredFlag: 'OWN', TonnageCapacity: 0, HoldingPeriod: 1, PresumptiveIncome: 7500 }] }); };
  const setGstin = (index: number, patch: Partial<TurnoverGrsRcptForGSTIN>): void => emit({ TurnoverGrsRcptForGSTIN: gstRows.map((row, i) => i === index ? { ...row, ...patch } : row) });

  return <div>
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 24 }}>
      <span style={{ background: 'var(--gold)', color: '#fff', padding: '4px 10px', borderRadius: 4, fontSize: 12, fontWeight: 600 }}>BP</span>
      <div><h3 style={{ margin: 0, fontSize: 14, fontWeight: 600, color: 'var(--text-secondary)' }}>Presumptive Business or Profession</h3><div style={{ marginTop: 3, fontSize: 11, color: 'var(--text-muted)' }}>Schedule BP — sections 44AD, 44ADA and 44AE — AY 2026-27</div></div>
    </div>
    {hasPrior && <div style={styles.priorBanner}>
      <strong>Last year's filed figures shown above each field</strong> — small read-only reference labels (gold) display the prior-year values from your previously filed ITR, so you can compare while entering this year's figures.
    </div>}
    <NatureEditor title="Section 44AD - Nature of business" arrayKey="NatOfBus44AD" codeKey="CodeAD" rows={current.NatOfBus44AD ?? []} options={NATURE_CODES_44AD} emit={emit} details={<div>
      <div style={{ marginBottom: 12 }}><h4 style={{ margin: 0, fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)' }}>Section 44AD - Presumptive income</h4><div style={{ marginTop: 4, color: 'var(--text-muted)', fontSize: 11 }}>Gross turnover and total income are derived</div></div>
      <div style={styles.grid}>
        <Field label="Turnover through banking modes" value={ad.GrsTrnOverBank} max={AD_MAX} priorValue={priorAd?.GrsTrnOverBank} onChange={(v) => updateObject('PersumptiveInc44AD', { GrsTrnOverBank: v })} />
        <Field label="Turnover in cash" value={ad.GrsTotalTrnOverInCash} max={AD_MAX} priorValue={priorAd?.GrsTotalTrnOverInCash} onChange={(v) => updateObject('PersumptiveInc44AD', { GrsTotalTrnOverInCash: v })} />
        <Field label="Turnover through any other mode" value={ad.GrsTrnOverAnyOthMode} max={AD_MAX} priorValue={priorAd?.GrsTrnOverAnyOthMode} onChange={(v) => updateObject('PersumptiveInc44AD', { GrsTrnOverAnyOthMode: v })} />
        <Field label="Gross total turnover" value={ad.GrsTotalTrnOver} max={AD_MAX} priorValue={priorAd?.GrsTotalTrnOver} readOnly />
        <Field label="Presumptive income @ 6%" value={ad.PersumptiveInc44AD6Per} max={AD_MAX} priorValue={priorAd?.PersumptiveInc44AD6Per} readOnly={!override6} onChange={(v) => updateObject('PersumptiveInc44AD', { PersumptiveInc44AD6Per: v } as Record<string, number>)} overrideFlag={override6} onToggleOverride={toggleOverride6} />
        <Field label="Presumptive income @ 8%" value={ad.PersumptiveInc44AD8Per} max={AD_MAX} priorValue={priorAd?.PersumptiveInc44AD8Per} readOnly={!override8} onChange={(v) => updateObject('PersumptiveInc44AD', { PersumptiveInc44AD8Per: v } as Record<string, number>)} overrideFlag={override8} onToggleOverride={toggleOverride8} />
        <Field label="Total presumptive income u/s 44AD" value={ad.TotPersumptiveInc44AD} max={AD_MAX} priorValue={priorAd?.TotPersumptiveInc44AD} readOnly />
      </div>
    </div>} />

    <NatureEditor title="Section 44ADA - Nature of profession" arrayKey="NatOfBus44ADA" codeKey="CodeADA" rows={current.NatOfBus44ADA ?? []} options={NATURE_CODES_44ADA} emit={emit} details={<div>
      <div style={{ marginBottom: 12 }}><h4 style={{ margin: 0, fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)' }}>Section 44ADA - Presumptive income</h4><div style={{ marginTop: 4, color: 'var(--text-muted)', fontSize: 11 }}>Gross receipts are derived</div></div>
      <div style={styles.grid}>
        <Field label="Receipts through banking modes" value={ada.GrsTrnOverBank44ADA} max={ADA_MAX} priorValue={priorAda?.GrsTrnOverBank44ADA} onChange={(v) => updateObject('PersumptiveInc44ADA', { GrsTrnOverBank44ADA: v })} />
        <Field label="Receipts in cash" value={ada.GrsTotalTrnOverInCash44ADA} max={ADA_MAX} priorValue={priorAda?.GrsTotalTrnOverInCash44ADA} onChange={(v) => updateObject('PersumptiveInc44ADA', { GrsTotalTrnOverInCash44ADA: v })} />
        <Field label="Receipts through any other mode" value={ada.GrsTrnOverAnyOthMode44ADA} max={ADA_MAX} priorValue={priorAda?.GrsTrnOverAnyOthMode44ADA} onChange={(v) => updateObject('PersumptiveInc44ADA', { GrsTrnOverAnyOthMode44ADA: v })} />
        <Field label="Gross receipt" value={ada.GrsReceipt} max={ADA_MAX} priorValue={priorAda?.GrsReceipt} readOnly />
        <Field label="Total presumptive income u/s 44ADA" value={ada.TotPersumptiveInc44ADA} max={ADA_MAX} priorValue={priorAda?.TotPersumptiveInc44ADA} onChange={(v) => updateObject('PersumptiveInc44ADA', { TotPersumptiveInc44ADA: v })} />
      </div>
    </div>} />

    <NatureEditor title="Section 44AE - Nature of business" arrayKey="NatOfBus44AE" codeKey="CodeAE" rows={current.NatOfBus44AE ?? []} options={NATURE_CODES_44AE} emit={emit} details={<div>
      <div style={{ ...styles.head, marginBottom: 12 }}><div><h4 style={{ margin: 0, fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)' }}>Section 44AE - Goods carriages</h4><div style={{ marginTop: 4, color: 'var(--text-muted)', fontSize: 11 }}>{vehicles.length}/10 vehicles</div></div><button type="button" style={{ ...styles.button, opacity: vehicles.length >= 10 ? 0.5 : 1 }} disabled={vehicles.length >= 10} onClick={addVehicle}>+ Add vehicle</button></div>
      {vehicles.length === 0 && <div style={styles.empty}>No goods carriage entries. Click “Add vehicle” to add one.</div>}
      {vehicles.map((row, index) => <div style={styles.row} key={`vehicle-${index}`}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}><h4 style={{ margin: 0, fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)' }}>Vehicle #{index + 1}{row.RegNumberGoodsCarriage ? ` — ${row.RegNumberGoodsCarriage}` : ''}</h4><button type="button" style={styles.remove} onClick={() => emit({ GoodsDtlsUs44AE: vehicles.filter((_, i) => i !== index) })}>Remove</button></div>
        <div style={styles.grid}>
          <label><span style={styles.label}>Registration number *</span><input style={styles.input} minLength={1} maxLength={11} value={row.RegNumberGoodsCarriage} onChange={(e) => setVehicle(index, { RegNumberGoodsCarriage: e.target.value.toUpperCase() })} /></label>
          <label><span style={styles.label}>Owned / leased / hired *</span><select style={styles.input} value={row.OwnedLeasedHiredFlag} onChange={(e) => setVehicle(index, { OwnedLeasedHiredFlag: e.target.value as GoodsDtlsUs44AE['OwnedLeasedHiredFlag'] })}><option value="OWN">Owned</option><option value="LEASE">Leased</option><option value="HIRED">Hired</option></select></label>
          <Field label="Tonnage capacity (0-100) *" value={row.TonnageCapacity} max={100} onChange={(v) => setVehicle(index, { TonnageCapacity: v })} />
          <Field label="Holding period in months *" value={row.HoldingPeriod} min={1} max={12} onChange={(v) => setVehicle(index, { HoldingPeriod: v })} />
          <Field label="Presumptive income *" value={row.PresumptiveIncome} min={7500} onChange={(v) => setVehicle(index, { PresumptiveIncome: v })} />
        </div>
      </div>)}
      <div style={{ marginTop: 20, paddingTop: 16, borderTop: '1px solid var(--border)' }}>
        <div style={{ marginBottom: 12 }}><h4 style={{ margin: 0, fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)' }}>Section 44AE - Income summary</h4><div style={{ marginTop: 4, color: 'var(--text-muted)', fontSize: 11 }}>Computed from goods-carriage entries</div></div>
        <div style={styles.grid}>
          <Field label="Total presumptive income u/s 44AE" value={ae.TotPersumInc44AE} priorValue={priorAe?.TotPersumInc44AE} readOnly />
          <Field label="Salary / interest from firm" value={ae.SalInterestByFirm} priorValue={priorAe?.SalInterestByFirm} onChange={(v) => updateObject('PersumptiveInc44AE', { SalInterestByFirm: v })} />
          <Field label="Total presumptive income" value={ae.TotalPersumptiveInc} priorValue={priorAe?.TotalPersumptiveInc} readOnly />
          <Field label="Income chargeable under business" value={ae.IncChargeableUnderBus} priorValue={priorAe?.IncChargeableUnderBus} readOnly />
        </div>
      </div>
    </div>} />

    <Card title="Turnover / gross receipts for GSTIN" subtitle="Schedule-level GSTIN reporting" action={<button type="button" style={styles.button} onClick={() => emit({ TurnoverGrsRcptForGSTIN: [...gstRows, { GSTINNo: '', AmtTurnGrossRcptGSTIN: 0 }] })}>+ Add GSTIN</button>}>
      {gstRows.length === 0 && <div style={styles.empty}>No GSTIN entries. Click “Add GSTIN” to add one.</div>}
      {gstRows.map((row, index) => <div style={styles.row} key={`gst-${index}`}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}><h4 style={{ margin: 0, fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)' }}>GSTIN Entry #{index + 1}{row.GSTINNo ? ` — ${row.GSTINNo}` : ''}</h4><button type="button" style={styles.remove} onClick={() => emit({ TurnoverGrsRcptForGSTIN: gstRows.filter((_, i) => i !== index) })}>Remove</button></div>
        <div style={styles.grid}>
          <label><span style={styles.label}>GSTIN *</span><input style={styles.input} maxLength={15} pattern="[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]" value={row.GSTINNo} onChange={(e) => setGstin(index, { GSTINNo: e.target.value.toUpperCase() })} /></label>
          <Field label="Turnover / gross receipt *" value={row.AmtTurnGrossRcptGSTIN} onChange={(v) => setGstin(index, { AmtTurnGrossRcptGSTIN: v })} />
        </div>
      </div>)}
      <div style={{ maxWidth: 360, marginLeft: 'auto' }}><Field label="Total turnover / gross receipts for GSTIN" value={current.TotalTurnoverGrsRcptGSTIN} readOnly /></div>
    </Card>

    <Card title="Financial particulars of business" subtitle="As on 31 March 2026; totals are derived"><div style={styles.grid}>
      {([
        ['PartnerMemberOwnCapital', 'Partners / members own capital'], ['SecuredLoans', 'Secured loans'], ['UnSecuredLoans', 'Unsecured loans'], ['Advances', 'Advances'], ['SundryCreditors', 'Sundry creditors'], ['OthrCurrLiab', 'Other current liabilities'],
      ] as Array<[keyof FinanclPartclrOfBusiness, string]>).map(([key, label]) => <Field key={key} label={label} value={financial[key]} priorValue={priorFinancial?.[key]} onChange={(v) => updateObject('FinanclPartclrOfBusiness', { [key]: v })} />)}
      <Field label="Total capital and liabilities" value={financial.TotCapLiabilities} priorValue={priorFinancial?.TotCapLiabilities} readOnly />
      {([
        ['FixedAssets', 'Fixed assets'], ['Investments', 'Investments'], ['Inventories', 'Inventories'], ['SundryDebtors', 'Sundry debtors'], ['BalWithBanks', 'Balance with banks'], ['CashInHand', 'Cash in hand'], ['LoansAndAdvances', 'Loans and advances'], ['OtherAssets', 'Other assets'],
      ] as Array<[keyof FinanclPartclrOfBusiness, string]>).map(([key, label]) => <Field key={key} label={label} value={financial[key]} priorValue={priorFinancial?.[key]} onChange={(v) => updateObject('FinanclPartclrOfBusiness', { [key]: v })} />)}
      <Field label="Total assets" value={financial.TotalAssets} priorValue={priorFinancial?.TotalAssets} readOnly />
    </div></Card>
  </div>;
}
