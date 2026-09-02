import React, { useMemo } from 'react';
import type {
  AMTDetails, AssetLiabilityDetails, BroughtForwardLossEntry,
  ClubbedIncomeEntry, ESOPDeferralEntry, ForeignAssetEntry, ForeignSourceIncomeEntry,
  ForeignTaxReliefEntry, PassThroughIncomeEntry, PortugueseCivilCodeDetails, ReturnDraft,
  ScheduleSIEntry,
} from '../../domain/returns/types';

export type Row = Record<string, unknown> & { id: string };
type ListCallback<T> = (value: T[]) => void;

export interface ITR2SchedulesWorkspaceProps {
  assessmentYear: string;
  broughtForwardLossEntries: BroughtForwardLossEntry[]; onBroughtForwardLossEntriesChange: ListCallback<BroughtForwardLossEntry>;
  scheduleSIEntries: ScheduleSIEntry[]; onScheduleSIEntriesChange: ListCallback<ScheduleSIEntry>;
  foreignSourceIncome: ForeignSourceIncomeEntry[]; onForeignSourceIncomeChange: ListCallback<ForeignSourceIncomeEntry>;
  foreignTaxRelief: ForeignTaxReliefEntry[]; onForeignTaxReliefChange: ListCallback<ForeignTaxReliefEntry>;
  foreignAssets: ForeignAssetEntry[]; onForeignAssetsChange: ListCallback<ForeignAssetEntry>;
  clubbedIncome: ClubbedIncomeEntry[]; onClubbedIncomeChange: ListCallback<ClubbedIncomeEntry>;
  passThroughIncomeEntries: PassThroughIncomeEntry[]; onPassThroughIncomeEntriesChange: ListCallback<PassThroughIncomeEntry>;
  amt: AMTDetails | null; onAmtChange: (value: AMTDetails | null) => void;
  assetLiability: AssetLiabilityDetails | null; onAssetLiabilityChange: (value: AssetLiabilityDetails | null) => void;
  portugueseCivilCode: PortugueseCivilCodeDetails | null; onPortugueseCivilCodeChange: (value: PortugueseCivilCodeDetails | null) => void;
  esopDeferrals: ESOPDeferralEntry[]; onEsopDeferralsChange: ListCallback<ESOPDeferralEntry>;
}

const uid = (prefix: string): string => {
  const random = globalThis.crypto?.randomUUID;
  return random ? random.call(globalThis.crypto) : `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2)}`;
};
const money = (value: unknown): number => typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : 0;
const text = (value: unknown): string => value == null ? '' : String(value);

export const createBroughtForwardLossEntry = (): BroughtForwardLossEntry => ({ id: uid('bfla'), assessmentYear: '', head: 'HP', subCategory: '', originalLoss: 0, broughtForward: 0, dateOfFiling: null });
export const createScheduleSIEntry = (): ScheduleSIEntry => ({ id: uid('si'), section: '115BB', description: '', grossIncome: 0, deductions: 0, taxRatePct: null });
export const createForeignSourceIncomeEntry = (): ForeignSourceIncomeEntry => ({ id: uid('fsi'), countryCode: '', taxIdentificationNo: '', salaryIncome: 0, hpIncome: 0, cgIncome: 0, osIncome: 0, taxPaidOutsideIndia: 0, taxPayableInIndia: 0, reliefSection: '90' });
export const createForeignTaxReliefEntry = (): ForeignTaxReliefEntry => ({ id: uid('tr'), countryCode: '', taxIdentificationNo: '', incomeIncludedInThisReturn: 0, taxPaidOutsideIndia: 0, indianTaxPayable: 0, reliefClaimed: 0, reliefSection: '90', form67Filed: false });
export const createForeignAssetEntry = (): ForeignAssetEntry => ({ id: uid('fa'), assetType: 'BANK_ACCOUNT', countryCode: '', institutionOrEntityName: '', address: '', accountOrAssetIdentifier: '', ownershipStatus: '', openingOrAcquisitionDate: '', peakValue: 0, closingValue: 0, grossIncome: 0, incomeOffered: 0, incomeHead: null });
export const createClubbedIncomeEntry = (): ClubbedIncomeEntry => ({ id: uid('spi'), specifiedPersonName: '', pan: '', relationship: '', amountIncluded: 0, headOfIncome: 'OS' });
export const createPassThroughIncomeEntry = (): PassThroughIncomeEntry => ({ id: uid('pti'), entityName: '', entityPAN: '', incomeHead: 'OS', section: '', incomeAmount: 0, tdsCredit: 0 });
export const createAmtDetails = (): AMTDetails => ({ deduction10AA: 0, deduction80IAto80RRBExcept80P: 0, deduction35ADNetDepreciation: 0, creditsBroughtForward: [] });
export const createAssetLiabilityDetails = (): AssetLiabilityDetails => ({ immovableProperty: 0, cashInHand: 0, bankDeposits: 0, sharesAndSecurities: 0, insurancePolicies: 0, loansAndAdvances: 0, jewellery: 0, art: 0, vehiclesBoatsAircraft: 0, relatedLiabilities: 0 });
export const createPortugueseCivilCodeDetails = (): PortugueseCivilCodeDetails => ({ spouseName: '', spousePAN: '', spouseAadhaar: '', hpAmountApportioned: 0, cgAmountApportioned: 0, osAmountApportioned: 0, tdsApportioned: 0 });
export const createESOPDeferralEntry = (): ESOPDeferralEntry => ({ id: uid('esop'), employerPAN: '', dpiitRegistrationNumber: '', assessmentYear: '', taxDeferredBroughtForward: 0, taxPayableCurrentYear: 0, balanceTaxCarriedForward: 0 });

const PAN = /^[A-Z]{5}[0-9]{4}[A-Z]$/;
const AY = /^\d{4}-\d{2}$/;
const DIPP = /^DIPP[0-9]{3,5}$/;
const label = (key: string): string => key.replace(/([A-Z])/g, ' $1').replace(/^./, (c) => c.toUpperCase());
const isMoney = (key: string): boolean => /amount|income|loss|value|tax|deduction|credit|relief|salary|hp|cg|os|paid|payable|expenses|deferred|balance|jewellery|art|vehicles|shares|cash|bank|insurance|loans|property/i.test(key);

export function validationFor(section: string, row: Row, assessmentYear: string): string[] {
  const errors: string[] = [];
  if (section === 'BFLA' && row.assessmentYear && !AY.test(String(row.assessmentYear))) errors.push('Assessment year must use YYYY-YY format.');
  for (const [key, value] of Object.entries(row)) if (isMoney(key) && typeof value === 'number' && value < 0) errors.push(`${label(key)} cannot be negative.`);
  if (section === 'BFLA' && money(row.broughtForward) > money(row.originalLoss)) errors.push('Brought-forward loss cannot exceed original loss.');
  if (section === 'SI' && ['115BB', '115BBE', '115BBJ'].includes(String(row.section)) && money(row.deductions) > 0) errors.push('Deductions are not permitted for this special-rate section.');
  if (section === 'SI' && row.taxRatePct != null && (Number(row.taxRatePct) < 0 || Number(row.taxRatePct) > 100)) errors.push('Tax rate must be between 0 and 100.');
  if ((section === 'FSI' || section === 'TR') && (!text(row.countryCode) || !text(row.taxIdentificationNo))) errors.push('Country and tax identification number are required.');
  if (section === 'FA' && (!text(row.countryCode) || !text(row.institutionOrEntityName) || !text(row.address) || !text(row.accountOrAssetIdentifier) || !text(row.ownershipStatus) || !text(row.openingOrAcquisitionDate))) errors.push('Country, institution, address, identifier, ownership, and opening date are required.');
  if (section === 'SPI' && (!text(row.specifiedPersonName) || !text(row.relationship))) errors.push('Specified person name and relationship are required.');
  if (section === 'PTI' && (!text(row.entityName) || !text(row.entityPAN) || !PAN.test(text(row.entityPAN).toUpperCase()) || !text(row.incomeHead) || !text(row.section))) errors.push('Entity name, valid PAN, income head, and section are required.');
  if (section === 'TR' && (money(row.reliefClaimed) > money(row.taxPaidOutsideIndia) || money(row.reliefClaimed) > money(row.indianTaxPayable))) errors.push('Relief cannot exceed foreign tax paid or Indian tax payable.');
  if (section === '5A' && (!text(row.spouseName) || !text(row.spousePAN))) errors.push('Spouse name and PAN are required.');
  if (section === '5A' && text(row.spousePAN) && !PAN.test(text(row.spousePAN).toUpperCase())) errors.push('Spouse PAN must be valid.');
  if (section === '5A' && text(row.spouseAadhaar) && !/^\d{12}$/.test(text(row.spouseAadhaar))) errors.push('Spouse Aadhaar must contain 12 digits when supplied.');
  if (section === 'ESOP' && row.assessmentYear && !AY.test(text(row.assessmentYear))) errors.push('Assessment year must use YYYY-YY format.');
  if (section === 'ESOP' && (!text(row.employerPAN) || !PAN.test(text(row.employerPAN).toUpperCase()))) errors.push('A valid employer PAN is required.');
  if (section === 'ESOP' && text(row.dpiitRegistrationNumber) && !DIPP.test(text(row.dpiitRegistrationNumber).toUpperCase())) errors.push('DPIIT registration number must match DIPP followed by 3-5 digits (e.g. DIPP12345).');
  if (assessmentYear && !AY.test(assessmentYear)) errors.push('Assessment year must use YYYY-YY format.');
  return [...new Set(errors)];
}

function controlFor(section: string, key: string, row: Row, onValue: (value: unknown) => void): React.ReactElement {
  const value = row[key];
  const options: Record<string, string[]> = {
    head: ['HP', 'STCG', 'LTCG', 'RaceHorse'],
    reliefSection: ['90', '90A', '91'],
    assetType: ['BANK_ACCOUNT', 'CUSTODIAL_ACCOUNT', 'EQUITY_DEBT_INTEREST', 'CASH_VALUE_INSURANCE', 'FINANCIAL_INTEREST', 'IMMOVABLE_PROPERTY', 'SIGNING_AUTHORITY', 'TRUST', 'OTHER_FOREIGN_INCOME', 'OTHER_ASSET'],
    incomeHead: ['', 'SAL', 'HP', 'CG', 'OS', 'STCG', 'LTCG'],
  };
  if (section === 'SI' && key === 'section') options.section = ['115BB', '115BBE', '115BBF', '115BBG', '115BBJ', '115BBA', '111'];
  if (key === 'form67Filed') {
    return <input type="checkbox" checked={Boolean(value)} onChange={(event) => onValue(event.target.checked)} />;
  }
  if (options[key]) {
    return <select value={value == null ? '' : String(value)} onChange={(event) => onValue(event.target.value)}>
      {options[key].map((option) => <option key={option} value={option}>{option || 'None'}</option>)}
    </select>;
  }
  return <input
    type={isMoney(key) ? 'number' : key.toLowerCase().includes('date') ? 'date' : 'text'}
    min={isMoney(key) ? 0 : undefined}
    value={value == null ? '' : String(value)}
    onChange={(event) => onValue(isMoney(key) ? Number(event.target.value) || 0 : event.target.value)}
  />;
}

interface ListSectionProps<T extends Row> { title: string; code: string; rows: T[]; onChange: ListCallback<T>; factory: () => T; fields: string[]; assessmentYear: string; }
function ListSection<T extends Row>({ title, code, rows, onChange, factory, fields, assessmentYear }: ListSectionProps<T>): React.ReactElement {
  const update = (id: string, key: string, value: unknown): void => onChange(rows.map((row) => row.id === id ? { ...row, [key]: value } as T : row));
  return <section style={sectionStyle}><div style={headingStyle}><h3 style={{ margin: 0 }}>{title}</h3><button type="button" onClick={() => onChange([...rows, factory()])}>＋ Add</button></div>
    {rows.length === 0 && <p style={muted}>No entries. Add one if applicable; blank optional schedules are not errors.</p>}
    {rows.map((row, index) => <div key={row.id} style={rowStyle}><strong>{index + 1}</strong><div style={gridStyle}>{fields.map((key) => <label key={key}>{label(key)}{controlFor(code, key, row, (value) => update(row.id, key, value))}</label>)}</div><div style={{ display: 'flex', justifyContent: 'space-between' }}><small style={{ color: validationFor(code, row, assessmentYear).length ? '#b42318' : '#667085' }}>{validationFor(code, row, assessmentYear).join(' ') || 'Review values before filing; backend remains authoritative.'}</small><button type="button" onClick={() => onChange(rows.filter((item) => item.id !== row.id))}>Remove</button></div></div>)}</section>;
}

function NullableSection<T extends object>({ title, value, onChange, factory, fields, code, assessmentYear }: { title: string; value: T | null; onChange: (value: T | null) => void; factory: () => T; fields: string[]; code: string; assessmentYear: string }): React.ReactElement {
  const row = value as Row | null;
  return <section style={sectionStyle}><div style={headingStyle}><h3 style={{ margin: 0 }}>{title}</h3><label style={{ display: 'inline-flex', gap: 8, alignItems: 'center' }}><input type="checkbox" checked={value !== null} onChange={(event) => onChange(event.target.checked ? factory() : null)} /> Enable schedule</label></div>{row && <div style={rowStyle}><div style={gridStyle}>{fields.map((key) => <label key={key}>{label(key)}{controlFor(code, key, row, (next) => onChange({ ...value, [key]: next } as T))}</label>)}</div><small style={{ color: validationFor(code, row, assessmentYear).length ? '#b42318' : '#667085' }}>{validationFor(code, row, assessmentYear).join(' ') || 'No obvious issues detected.'}</small></div>}</section>;
}

export function ITR2SchedulesWorkspace(props: ITR2SchedulesWorkspaceProps): React.ReactElement {
  const ayWarning = useMemo(() => AY.test(props.assessmentYear) ? '' : 'Assessment year must use YYYY-YY format.', [props.assessmentYear]);
  return <div style={{ display: 'grid', gap: 16 }}><header><h2 style={{ marginBottom: 4 }}>ITR-2 Schedules</h2><p style={muted}>Capture schedule facts only. Tax, set-off, relief utilization, and applicability are calculated and validated by the backend.</p>{ayWarning && <div role="alert" style={{ color: '#b42318' }}>{ayWarning}</div>}</header>
    <ListSection title="Schedule BFLA — Brought-forward losses" code="BFLA" rows={props.broughtForwardLossEntries as unknown as Row[]} onChange={props.onBroughtForwardLossEntriesChange as unknown as ListCallback<Row>} factory={createBroughtForwardLossEntry as unknown as () => Row} fields={['assessmentYear', 'head', 'subCategory', 'originalLoss', 'broughtForward', 'dateOfFiling']} assessmentYear={props.assessmentYear} />
    <p style={muted}>Schedule CFL (losses carried forward to future years) is computed by the backend from the figures above and current-year set-off — there is nothing to enter here.</p>
    <ListSection title="Schedule SI — Special-rate income" code="SI" rows={props.scheduleSIEntries as unknown as Row[]} onChange={props.onScheduleSIEntriesChange as unknown as ListCallback<Row>} factory={createScheduleSIEntry as unknown as () => Row} fields={['section', 'description', 'grossIncome', 'deductions', 'taxRatePct']} assessmentYear={props.assessmentYear} />
    <ListSection title="Schedule FSI — Foreign source income" code="FSI" rows={props.foreignSourceIncome as unknown as Row[]} onChange={props.onForeignSourceIncomeChange as unknown as ListCallback<Row>} factory={createForeignSourceIncomeEntry as unknown as () => Row} fields={['countryCode', 'taxIdentificationNo', 'salaryIncome', 'hpIncome', 'cgIncome', 'osIncome', 'taxPaidOutsideIndia', 'taxPayableInIndia', 'reliefSection']} assessmentYear={props.assessmentYear} />
    <ListSection title="Schedule TR — Foreign tax relief" code="TR" rows={props.foreignTaxRelief as unknown as Row[]} onChange={props.onForeignTaxReliefChange as unknown as ListCallback<Row>} factory={createForeignTaxReliefEntry as unknown as () => Row} fields={['countryCode', 'taxIdentificationNo', 'incomeIncludedInThisReturn', 'taxPaidOutsideIndia', 'indianTaxPayable', 'reliefClaimed', 'reliefSection', 'form67Filed']} assessmentYear={props.assessmentYear} />
    <ListSection title="Schedule FA — Foreign assets" code="FA" rows={props.foreignAssets as unknown as Row[]} onChange={props.onForeignAssetsChange as unknown as ListCallback<Row>} factory={createForeignAssetEntry as unknown as () => Row} fields={['assetType', 'countryCode', 'institutionOrEntityName', 'address', 'accountOrAssetIdentifier', 'ownershipStatus', 'openingOrAcquisitionDate', 'peakValue', 'closingValue', 'grossIncome', 'incomeOffered', 'incomeHead']} assessmentYear={props.assessmentYear} />
    <ListSection title="Schedule SPI — Clubbed income" code="SPI" rows={props.clubbedIncome as unknown as Row[]} onChange={props.onClubbedIncomeChange as unknown as ListCallback<Row>} factory={createClubbedIncomeEntry as unknown as () => Row} fields={['specifiedPersonName', 'pan', 'relationship', 'amountIncluded', 'headOfIncome']} assessmentYear={props.assessmentYear} />
    <ListSection title="Schedule PTI — Pass-through income" code="PTI" rows={props.passThroughIncomeEntries as unknown as Row[]} onChange={props.onPassThroughIncomeEntriesChange as unknown as ListCallback<Row>} factory={createPassThroughIncomeEntry as unknown as () => Row} fields={['entityName', 'entityPAN', 'incomeHead', 'section', 'incomeAmount', 'tdsCredit']} assessmentYear={props.assessmentYear} />
    <NullableSection title="Schedule AMT / AMTC" code="AMT" value={props.amt} onChange={props.onAmtChange} factory={createAmtDetails} fields={['deduction10AA', 'deduction80IAto80RRBExcept80P', 'deduction35ADNetDepreciation']} assessmentYear={props.assessmentYear} />
    <NullableSection title="Schedule AL — Assets and liabilities" code="AL" value={props.assetLiability} onChange={props.onAssetLiabilityChange} factory={createAssetLiabilityDetails} fields={['immovableProperty', 'cashInHand', 'bankDeposits', 'sharesAndSecurities', 'insurancePolicies', 'loansAndAdvances', 'jewellery', 'art', 'vehiclesBoatsAircraft', 'relatedLiabilities']} assessmentYear={props.assessmentYear} />
    <NullableSection title="Schedule 5A — Portuguese Civil Code" code="5A" value={props.portugueseCivilCode} onChange={props.onPortugueseCivilCodeChange} factory={createPortugueseCivilCodeDetails} fields={['spouseName', 'spousePAN', 'spouseAadhaar', 'hpAmountApportioned', 'cgAmountApportioned', 'osAmountApportioned', 'tdsApportioned']} assessmentYear={props.assessmentYear} />
    <ListSection title="Schedule ESOP — Tax deferrals" code="ESOP" rows={props.esopDeferrals as unknown as Row[]} onChange={props.onEsopDeferralsChange as unknown as ListCallback<Row>} factory={createESOPDeferralEntry as unknown as () => Row} fields={['employerPAN', 'dpiitRegistrationNumber', 'assessmentYear', 'taxDeferredBroughtForward', 'taxPayableCurrentYear', 'balanceTaxCarriedForward']} assessmentYear={props.assessmentYear} />
  </div>;
}

const sectionStyle: React.CSSProperties = { border: '1px solid var(--border, #eaecf0)', borderRadius: 8, padding: 16, display: 'grid', gap: 12 };
const headingStyle: React.CSSProperties = { display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 };
const rowStyle: React.CSSProperties = { border: '1px solid #eaecf0', borderRadius: 6, padding: 12, display: 'grid', gap: 10 };
const gridStyle: React.CSSProperties = { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: 10 };
const muted: React.CSSProperties = { color: 'var(--text-muted, #667085)', margin: 0 };

export default ITR2SchedulesWorkspace;

export type ITR2ScheduleDraftFields = Pick<ReturnDraft, 'broughtForwardLossEntries' | 'scheduleSIEntries' | 'foreignSourceIncome' | 'foreignTaxRelief' | 'foreignAssets' | 'clubbedIncome' | 'passThroughIncomeEntries' | 'amt' | 'assetLiability' | 'portugueseCivilCode' | 'esopDeferrals'>;

