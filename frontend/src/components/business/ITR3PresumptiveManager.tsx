import React, { useMemo } from 'react';
import type { CanonicalObject, CanonicalValue } from './ITR3BusinessCoreManager';
import { NATURE_CODES_44AD, NATURE_CODES_44ADA, NATURE_CODES_44AE, type OfficialCodeOption } from './ITR4ScheduleBPData';

const MONEY_MAX = 99_999_999_999_999;
const AD_MAX = 30_000_000;
const ADA_MAX = 7_500_000;
const VEHICLE_LIMIT = 10;

interface NatureRow extends CanonicalObject {
  NameOfBusiness: string;
  Description: string;
}

interface GoodsCarriageRow extends CanonicalObject {
  RegNumberGoodsCarriage: string;
  OwnedLeasedHiredFlag: 'OWN' | 'LEASE' | 'HIRED';
  TonnageCapacity: number;
  HoldingPeriod: number;
  PresumptiveIncome: number;
}

/** Props for the dedicated ITR-3 presumptive-income editor. */
export interface ITR3PresumptiveManagerProps {
  data?: CanonicalObject | null;
  disabled?: boolean;
  onChange: (data: CanonicalObject) => void;
}

type NatureArrayKey = 'NatOfBus44AD' | 'NatOfBus44ADA' | 'NatOfBus44AE';
type CodeKey = 'CodeAD' | 'CodeADA' | 'CodeAE';

const styles: Record<string, React.CSSProperties> = {
  wrapper: { padding: 18, background: '#fff', border: '1px solid var(--border)', borderRadius: 6 },
  card: { marginBottom: 24, padding: 16, background: 'var(--bg)', borderRadius: 6, border: '1px solid var(--border)' },
  head: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, marginBottom: 12 },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 16 },
  label: { display: 'block', marginBottom: 6, fontSize: 12, fontWeight: 500, color: 'var(--text-secondary)' },
  input: { width: '100%', boxSizing: 'border-box', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6, fontSize: 13, color: 'var(--text-primary)', background: '#fff' },
  readOnly: { width: '100%', boxSizing: 'border-box', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6, fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', background: 'var(--gold-pale)' },
  row: { marginBottom: 16, padding: 16, background: '#fff', borderRadius: 6, border: '1px solid var(--border)' },
  button: { padding: '6px 12px', background: 'var(--gold)', color: '#fff', border: 'none', borderRadius: 6, fontSize: 12, cursor: 'pointer' },
  remove: { padding: '4px 8px', background: 'var(--danger)', color: '#fff', border: 'none', borderRadius: 4, fontSize: 11, cursor: 'pointer' },
  empty: { padding: 24, textAlign: 'center', color: 'var(--text-muted)', background: '#fff', borderRadius: 6, border: '1px solid var(--border)' },
  sectionHeader: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, marginBottom: 16 },
};

function asObject(value: CanonicalValue | undefined): CanonicalObject {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as CanonicalObject : {};
}

function asArray(value: CanonicalValue | undefined): CanonicalObject[] {
  return Array.isArray(value) ? value.filter((item): item is CanonicalObject => Boolean(item) && typeof item === 'object' && !Array.isArray(item)) : [];
}

function asNumber(value: CanonicalValue | undefined): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : 0;
}

function asString(value: CanonicalValue | undefined): string {
  return typeof value === 'string' ? value : '';
}

function toAmount(value: string, maximum: number = MONEY_MAX, minimum = 0): number {
  if (value.trim() === '') return 0;
  const parsed = Math.trunc(Number(value));
  if (!Number.isFinite(parsed)) return 0;
  return Math.min(maximum, Math.max(minimum, parsed));
}

function amount(value: number): string {
  return value === 0 ? '' : String(value);
}

function sum(values: number[], maximum: number = MONEY_MAX): number {
  return Math.min(maximum, values.reduce((total, value) => total + value, 0));
}

function derive(input?: CanonicalObject | null): CanonicalObject {
  const source = input ?? {};
  const ad = { ...asObject(source.PersumptiveInc44AD) };
  const ada = { ...asObject(source.PersumptiveInc44ADA) };
  const vehicles = asArray(source.GoodsDtlsUs44AE).slice(0, VEHICLE_LIMIT);

  if (source.PersumptiveInc44AD !== undefined || asArray(source.NatOfBus44AD).length > 0) {
    ad.GrsTrnOverOrReceipt = sum([
      asNumber(ad.GrsTrnOverBank),
      asNumber(ad.GrsTotalTrnOverInCash),
      asNumber(ad.GrsTrnOverAnyOthMode),
    ], AD_MAX);
    ad.TotPersumptiveInc44AD = sum([
      asNumber(ad.PersumptiveInc44AD6Per),
      asNumber(ad.PersumptiveInc44AD8Per),
    ]);
  }
  if (source.PersumptiveInc44ADA !== undefined || asArray(source.NatOfBus44ADA).length > 0) {
    ada.GrsReceipt = sum([
      asNumber(ada.GrsTrnOverBank44ADA),
      asNumber(ada.GrsTotalTrnOverInCash44ADA),
      asNumber(ada.GrsTrnOverAnyOthMode44ADA),
    ], ADA_MAX);
  }

  return {
    ...source,
    NatOfBus44AD: asArray(source.NatOfBus44AD),
    PersumptiveInc44AD: ad,
    NatOfBus44ADA: asArray(source.NatOfBus44ADA),
    PersumptiveInc44ADA: ada,
    NatOfBus44AE: asArray(source.NatOfBus44AE),
    GoodsDtlsUs44AE: vehicles,
    TotalNumOfMonths: sum(vehicles.map((row) => asNumber(row.HoldingPeriod)), 120),
    TotalPrsumptvIncUs44EGoods: sum(vehicles.map((row) => asNumber(row.PresumptiveIncome))),
    TotalPrsumptvIncUs44E: sum(vehicles.map((row) => asNumber(row.PresumptiveIncome))),
  };
}

function Field({ label, value, onChange, max = MONEY_MAX, min = 0, readOnly = false, disabled = false }: { label: string; value: number; onChange?: (value: number) => void; max?: number; min?: number; readOnly?: boolean; disabled?: boolean }): React.JSX.Element {
  return <label><span style={styles.label}>{label}</span><input aria-label={label} type="number" min={min} max={max} step="1" value={amount(value)} readOnly={readOnly} disabled={disabled && !readOnly} onChange={(event) => onChange?.(toAmount(event.target.value, max, min))} style={readOnly ? styles.readOnly : styles.input} /></label>;
}

function NatureEditor({ title, arrayKey, codeKey, rows, options, disabled, emit, details }: { title: string; arrayKey: NatureArrayKey; codeKey: CodeKey; rows: CanonicalObject[]; options: readonly OfficialCodeOption[]; disabled: boolean; emit: (patch: CanonicalObject) => void; details: React.ReactNode }): React.JSX.Element {
  const update = (index: number, key: string, value: string): void => emit({ [arrayKey]: rows.map((row, rowIndex) => rowIndex === index ? { ...row, [key]: value } : row) });
  const add = (): void => emit({ [arrayKey]: [...rows, { NameOfBusiness: '', [codeKey]: '' }] });
  const remove = (index: number): void => emit({ [arrayKey]: rows.filter((_, rowIndex) => rowIndex !== index) });

  return <section style={{ marginBottom: 28 }}>
    <div style={styles.sectionHeader}>
      <div><h3 style={{ margin: 0, fontSize: 14, fontWeight: 600, color: 'var(--text-secondary)' }}>{title}</h3><div style={{ marginTop: 4, fontSize: 11, color: 'var(--text-muted)' }}>Official AY 2026-27 business/profession codes</div></div>
      <button type="button" style={{ ...styles.button, opacity: disabled ? 0.5 : 1 }} disabled={disabled} onClick={add}>+ Add entry</button>
    </div>
    {rows.length === 0 && <div style={styles.empty}>No entries. Click &ldquo;Add entry&rdquo; to add one.</div>}
    {rows.map((rawRow, index) => {
      const row = rawRow as NatureRow;
      return <div style={styles.row} key={`${arrayKey}-${index}`}>
        <div style={styles.head}><h4 style={{ margin: 0, fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)' }}>Entry #{index + 1}{asString(row.NameOfBusiness) ? ` — ${asString(row.NameOfBusiness)}` : ''}</h4><button type="button" style={{ ...styles.remove, opacity: disabled ? 0.5 : 1 }} disabled={disabled} onClick={() => remove(index)}>Remove</button></div>
        <div style={styles.grid}>
          <label><span style={styles.label}>Name of business *</span><input aria-label={`${title} name ${index + 1}`} style={styles.input} maxLength={75} disabled={disabled} value={asString(row.NameOfBusiness)} onChange={(event) => update(index, 'NameOfBusiness', event.target.value)} /></label>
          <label><span style={styles.label}>Nature code *</span><select aria-label={`${title} nature code ${index + 1}`} style={styles.input} disabled={disabled} value={asString(row[codeKey])} onChange={(event) => update(index, codeKey, event.target.value)}><option value="">Select official code</option>{options.map(([code, description]) => <option key={code} value={code}>{code} - {description}</option>)}</select></label>
          <label><span style={styles.label}>Description</span><input aria-label={`${title} description ${index + 1}`} style={styles.input} maxLength={75} disabled={disabled} value={asString(row.Description)} onChange={(event) => update(index, 'Description', event.target.value)} /></label>
        </div>
        {index === 0 && <div style={{ marginTop: 20, paddingTop: 16, borderTop: '1px solid var(--border)' }}>{details}</div>}
      </div>;
    })}
  </section>;
}

/** Edits ITR-3 PARTA_PL presumptive fields using the proven ITR-4 interaction pattern. */
export default function ITR3PresumptiveManager({ data, disabled = false, onChange }: ITR3PresumptiveManagerProps): React.JSX.Element {
  const current = useMemo(() => derive(data), [data]);

  const emit = (patch: CanonicalObject): void => onChange(derive({ ...current, ...patch }));
  const updateObject = (key: 'PersumptiveInc44AD' | 'PersumptiveInc44ADA', patch: CanonicalObject): void => emit({ [key]: { ...asObject(current[key]), ...patch } });
  const ad = asObject(current.PersumptiveInc44AD);
  const ada = asObject(current.PersumptiveInc44ADA);
  const vehicles = asArray(current.GoodsDtlsUs44AE);
  const setVehicle = (index: number, patch: CanonicalObject): void => emit({ GoodsDtlsUs44AE: vehicles.map((row, rowIndex) => rowIndex === index ? { ...row, ...patch } : row) });
  const addVehicle = (): void => {
    if (!disabled && vehicles.length < VEHICLE_LIMIT) emit({ GoodsDtlsUs44AE: [...vehicles, { RegNumberGoodsCarriage: '', OwnedLeasedHiredFlag: 'OWN', TonnageCapacity: 0, HoldingPeriod: 1, PresumptiveIncome: 7500 }] });
  };

  const adDetails = <div><div style={{ marginBottom: 12 }}><h4 style={{ margin: 0, fontSize: 13, color: 'var(--text-secondary)' }}>Section 44AD - Presumptive income</h4><div style={{ marginTop: 4, fontSize: 11, color: 'var(--text-muted)' }}>Gross turnover and total presumptive income are calculated automatically.</div></div><div style={styles.grid}>
    <Field label="Turnover through banking modes" value={asNumber(ad.GrsTrnOverBank)} max={AD_MAX} disabled={disabled} onChange={(value) => updateObject('PersumptiveInc44AD', { GrsTrnOverBank: value })} />
    <Field label="Turnover in cash" value={asNumber(ad.GrsTotalTrnOverInCash)} max={AD_MAX} disabled={disabled} onChange={(value) => updateObject('PersumptiveInc44AD', { GrsTotalTrnOverInCash: value })} />
    <Field label="Turnover through any other mode" value={asNumber(ad.GrsTrnOverAnyOthMode)} max={AD_MAX} disabled={disabled} onChange={(value) => updateObject('PersumptiveInc44AD', { GrsTrnOverAnyOthMode: value })} />
    <Field label="Gross total turnover" value={asNumber(ad.GrsTrnOverOrReceipt)} max={AD_MAX} readOnly />
    <Field label="Presumptive income @ 6%" value={asNumber(ad.PersumptiveInc44AD6Per)} disabled={disabled} onChange={(value) => updateObject('PersumptiveInc44AD', { PersumptiveInc44AD6Per: value })} />
    <Field label="Presumptive income @ 8%" value={asNumber(ad.PersumptiveInc44AD8Per)} disabled={disabled} onChange={(value) => updateObject('PersumptiveInc44AD', { PersumptiveInc44AD8Per: value })} />
    <Field label="Total presumptive income u/s 44AD" value={asNumber(ad.TotPersumptiveInc44AD)} readOnly />
  </div></div>;

  const adaDetails = <div><div style={{ marginBottom: 12 }}><h4 style={{ margin: 0, fontSize: 13, color: 'var(--text-secondary)' }}>Section 44ADA - Presumptive income</h4><div style={{ marginTop: 4, fontSize: 11, color: 'var(--text-muted)' }}>Gross receipts are calculated automatically.</div></div><div style={styles.grid}>
    <Field label="Receipts through banking modes" value={asNumber(ada.GrsTrnOverBank44ADA)} max={ADA_MAX} disabled={disabled} onChange={(value) => updateObject('PersumptiveInc44ADA', { GrsTrnOverBank44ADA: value })} />
    <Field label="Receipts in cash" value={asNumber(ada.GrsTotalTrnOverInCash44ADA)} max={ADA_MAX} disabled={disabled} onChange={(value) => updateObject('PersumptiveInc44ADA', { GrsTotalTrnOverInCash44ADA: value })} />
    <Field label="Receipts through any other mode" value={asNumber(ada.GrsTrnOverAnyOthMode44ADA)} max={ADA_MAX} disabled={disabled} onChange={(value) => updateObject('PersumptiveInc44ADA', { GrsTrnOverAnyOthMode44ADA: value })} />
    <Field label="Gross receipts" value={asNumber(ada.GrsReceipt)} max={ADA_MAX} readOnly />
    <Field label="Total presumptive income u/s 44ADA" value={asNumber(ada.TotPersumptiveInc44ADA)} max={9_999_999} disabled={disabled} onChange={(value) => updateObject('PersumptiveInc44ADA', { TotPersumptiveInc44ADA: value })} />
  </div></div>;

  const aeDetails = <div><div style={styles.head}><div><h4 style={{ margin: 0, fontSize: 13, color: 'var(--text-secondary)' }}>Section 44AE - Goods carriages</h4><div style={{ marginTop: 4, fontSize: 11, color: 'var(--text-muted)' }}>{vehicles.length}/{VEHICLE_LIMIT} vehicles</div></div><button type="button" style={{ ...styles.button, opacity: disabled || vehicles.length >= VEHICLE_LIMIT ? 0.5 : 1 }} disabled={disabled || vehicles.length >= VEHICLE_LIMIT} onClick={addVehicle}>+ Add vehicle</button></div>
    {vehicles.length === 0 && <div style={styles.empty}>No goods carriage entries. Click &ldquo;Add vehicle&rdquo; to add one.</div>}
    {vehicles.map((rawRow, index) => {
      const row = rawRow as GoodsCarriageRow;
      return <div style={styles.row} key={`vehicle-${index}`}><div style={styles.head}><h4 style={{ margin: 0, fontSize: 13, color: 'var(--text-secondary)' }}>Vehicle #{index + 1}{asString(row.RegNumberGoodsCarriage) ? ` — ${asString(row.RegNumberGoodsCarriage)}` : ''}</h4><button type="button" style={{ ...styles.remove, opacity: disabled ? 0.5 : 1 }} disabled={disabled} onClick={() => emit({ GoodsDtlsUs44AE: vehicles.filter((_, rowIndex) => rowIndex !== index) })}>Remove</button></div><div style={styles.grid}>
        <label><span style={styles.label}>Registration number *</span><input aria-label={`Vehicle registration number ${index + 1}`} style={styles.input} maxLength={11} disabled={disabled} value={asString(row.RegNumberGoodsCarriage)} onChange={(event) => setVehicle(index, { RegNumberGoodsCarriage: event.target.value.toUpperCase() })} /></label>
        <label><span style={styles.label}>Owned / leased / hired *</span><select aria-label={`Vehicle ownership ${index + 1}`} style={styles.input} disabled={disabled} value={asString(row.OwnedLeasedHiredFlag) || 'OWN'} onChange={(event) => setVehicle(index, { OwnedLeasedHiredFlag: event.target.value })}><option value="OWN">Owned</option><option value="LEASE">Leased</option><option value="HIRED">Hired</option></select></label>
        <Field label="Tonnage capacity (0-100) *" value={asNumber(row.TonnageCapacity)} max={100} disabled={disabled} onChange={(value) => setVehicle(index, { TonnageCapacity: value })} />
        <Field label="Holding period in months *" value={asNumber(row.HoldingPeriod)} min={1} max={12} disabled={disabled} onChange={(value) => setVehicle(index, { HoldingPeriod: value })} />
        <Field label="Presumptive income *" value={asNumber(row.PresumptiveIncome)} min={7500} disabled={disabled} onChange={(value) => setVehicle(index, { PresumptiveIncome: value })} />
      </div></div>;
    })}
    <div style={{ marginTop: 20, paddingTop: 16, borderTop: '1px solid var(--border)' }}><div style={{ marginBottom: 12 }}><h4 style={{ margin: 0, fontSize: 13, color: 'var(--text-secondary)' }}>Section 44AE - Income summary</h4><div style={{ marginTop: 4, fontSize: 11, color: 'var(--text-muted)' }}>Calculated from goods-carriage entries.</div></div><div style={styles.grid}>
      <Field label="Total number of vehicle-months" value={asNumber(current.TotalNumOfMonths)} max={120} readOnly />
      <Field label="Total presumptive income from goods carriages" value={asNumber(current.TotalPrsumptvIncUs44EGoods)} readOnly />
      <Field label="Total presumptive income u/s 44AE" value={asNumber(current.TotalPrsumptvIncUs44E)} readOnly />
    </div></div>
  </div>;

  return <section aria-label="ITR-3 presumptive income" style={styles.wrapper}>
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 24 }}><span style={{ background: 'var(--gold)', color: '#fff', padding: '4px 10px', borderRadius: 4, fontSize: 12, fontWeight: 600 }}>PRESUMPTIVE</span><div><h3 style={{ margin: 0, fontSize: 14, color: 'var(--text-secondary)' }}>Presumptive business or profession</h3><div style={{ marginTop: 3, fontSize: 11, color: 'var(--text-muted)' }}>Sections 44AD, 44ADA and 44AE — AY 2026-27</div></div></div>
    <NatureEditor title="Section 44AD - Nature of business" arrayKey="NatOfBus44AD" codeKey="CodeAD" rows={asArray(current.NatOfBus44AD)} options={NATURE_CODES_44AD} disabled={disabled} emit={emit} details={adDetails} />
    <NatureEditor title="Section 44ADA - Nature of profession" arrayKey="NatOfBus44ADA" codeKey="CodeADA" rows={asArray(current.NatOfBus44ADA)} options={NATURE_CODES_44ADA} disabled={disabled} emit={emit} details={adaDetails} />
    <NatureEditor title="Section 44AE - Nature of business" arrayKey="NatOfBus44AE" codeKey="CodeAE" rows={asArray(current.NatOfBus44AE)} options={NATURE_CODES_44AE} disabled={disabled} emit={emit} details={aeDetails} />
  </section>;
}
