import React from 'react';

const MONEY_MAX = 99999999999999;
const inputStyle: React.CSSProperties = { width: '100%', padding: '8px 10px', border: '1px solid var(--border)', borderRadius: 6, fontSize: 13, background: '#fff', color: 'var(--text-primary)', boxSizing: 'border-box' };
const labelStyle: React.CSSProperties = { display: 'block', marginBottom: 5, fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)' };
const gridStyle: React.CSSProperties = { display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 12, marginBottom: 16 };
const cardStyle: React.CSSProperties = { marginBottom: 20, padding: 16, background: 'var(--bg)', borderRadius: 6, border: '1px solid var(--border)' };

type JsonRow = Record<string, unknown>;
type SectionKey = keyof CapitalGainsScheduleData;
type FieldKind = 'text' | 'money' | 'signed' | 'decimal' | 'date' | 'select' | 'boolean' | 'readout';
interface FieldSpec { key: string; label: string; kind?: FieldKind; required?: boolean; options?: Array<[string, string]>; maxLength?: number; pattern?: string; }
interface NestedSpec { key: string; title: string; fields: FieldSpec[]; maxRows?: number; }

export interface CapitalGainTransaction extends JsonRow { id?: string; transactionId?: string; recordKind?: 'EVIDENCE' | 'TRANSACTION'; }
export interface CapitalGainsIssue extends JsonRow { code?: string; message?: string; row?: number; field?: string; severity?: string; }
export interface CapitalGainsSummary { issues?: CapitalGainsIssue[]; eligibility?: Record<string, boolean>; [key: string]: unknown; }

export interface CapitalGainsScheduleData {
  simplified112A: JsonRow;
  stImmovable: JsonRow[];
  stEquity: JsonRow[];
  stNriUnlisted: JsonRow[];
  stOtherAssets: JsonRow[];
  stSlumpSale: JsonRow[];
  ltImmovable: JsonRow[];
  ltProviso112: JsonRow[];
  ltNri112115: JsonRow[];
  ltForeignAssets: JsonRow[];
  ltOtherAssets: JsonRow[];
  ltSlumpSale: JsonRow[];
  schedule112A: JsonRow[];
  schedule115AD: JsonRow[];
  vda: JsonRow[];
  stUnutilized: JsonRow[];
  ltUnutilized: JsonRow[];
  stDtaa: JsonRow[];
  ltDtaa: JsonRow[];
  buyBackLosses: JsonRow[];
  deductionClaims: JsonRow[];
  stSection48: JsonRow;
  ltNriProviso48: JsonRow;
  ltNri112A: JsonRow;
  stUnutilizedFlag: string;
  ltUnutilizedFlag: string;
  quarterly: JsonRow;
  aggregates: JsonRow;
  lossSetOff: JsonRow;
}

interface Props {
  data?: Partial<CapitalGainsScheduleData>;
  entries?: CapitalGainTransaction[];
  onChange: (data: CapitalGainsScheduleData) => void;
  selectedForm: string;
  summary?: CapitalGainsSummary | null;
  issues?: CapitalGainsIssue[];
}

const emptyData = (): CapitalGainsScheduleData => ({
  simplified112A: { totalSaleConsideration: 0, totalCostAcquisition: 0 },
  stImmovable: [], stEquity: [], stNriUnlisted: [], stOtherAssets: [], stSlumpSale: [],
  ltImmovable: [], ltProviso112: [], ltNri112115: [], ltForeignAssets: [], ltOtherAssets: [], ltSlumpSale: [],
  schedule112A: [], schedule115AD: [], vda: [], stUnutilized: [], ltUnutilized: [], stDtaa: [], ltDtaa: [], buyBackLosses: [], deductionClaims: [],
  quarterly: {}, stSection48: { nriSttPaid: 0, nriSttNotPaid: 0 }, ltNriProviso48: { ltcgWithoutBenefit: 0, deduction54F: 0 }, ltNri112A: {}, stUnutilizedFlag: 'N', ltUnutilizedFlag: 'N', lossSetOff: {}, aggregates: { stPassThrough: 0, stPassThrough20: 0, stPassThrough30: 0, stPassThroughApplicable: 0, ltPassThrough: 0, ltPassThrough112A: 0, ltPassThrough125: 0 },
});

const normalizeData = (value?: Partial<CapitalGainsScheduleData>): CapitalGainsScheduleData => {
  const base = emptyData();
  if (!value) return base;
  const result = { ...base, ...value } as CapitalGainsScheduleData;
  for (const key of Object.keys(base) as SectionKey[]) {
    if (Array.isArray(base[key])) (result as unknown as Record<string, unknown>)[key] = Array.isArray(value[key]) ? value[key] : [];
  }
  result.simplified112A = { ...base.simplified112A, ...(value.simplified112A || {}) };
  result.quarterly = { ...(value.quarterly || {}) };
  result.aggregates = { ...base.aggregates, ...(value.aggregates || {}) };
  result.stSection48 = { ...base.stSection48, ...(value.stSection48 || {}) };
  result.ltNriProviso48 = { ...base.ltNriProviso48, ...(value.ltNriProviso48 || {}) };
  result.ltNri112A = { ...(value.ltNri112A || {}) };
  result.lossSetOff = { ...(value.lossSetOff || {}) };
  return result;
};

const ST_IMMOVABLE: FieldSpec[] = [
  { key: 'dateOfPurchase', label: 'Date of purchase', kind: 'date' }, { key: 'dateOfSale', label: 'Date of sale', kind: 'date' },
  { key: 'fullConsideration', label: 'Full value of consideration', kind: 'money' }, { key: 'stampDutyValue', label: 'Property valuation u/s 50C', kind: 'money' },
  { key: 'acquisitionCost', label: 'Cost of acquisition *', kind: 'money', required: true }, { key: 'improvementCost', label: 'Cost of improvement *', kind: 'money', required: true },
  { key: 'transferExpenses', label: 'Transfer expenses *', kind: 'money', required: true }, { key: 'deduction54B', label: 'Deduction u/s 54B *', kind: 'money', required: true },
  { key: 'consideration50C', label: 'Consideration adopted u/s 50C *', kind: 'readout', required: true }, { key: 'totalDeductions', label: 'Total deductions *', kind: 'readout', required: true },
  { key: 'balance', label: 'Balance *', kind: 'readout', required: true }, { key: 'capitalGain', label: 'STCG on immovable property *', kind: 'readout', required: true },
];
const COMMON_ASSET: FieldSpec[] = [
  { key: 'fullConsideration', label: 'Full value of consideration *', kind: 'money', required: true },
  { key: 'acquisitionCost', label: 'Cost of acquisition *', kind: 'money', required: true },
  { key: 'improvementCost', label: 'Cost of improvement *', kind: 'money', required: true },
  { key: 'transferExpenses', label: 'Transfer expenses *', kind: 'money', required: true },
  { key: 'loss94', label: 'Loss disallowed u/s 94(7)/94(8)', kind: 'money' },
  { key: 'totalDeductions', label: 'Total deductions *', kind: 'readout', required: true }, { key: 'balance', label: 'Balance *', kind: 'readout', required: true },
  { key: 'capitalGain', label: 'Capital gain / loss *', kind: 'readout', required: true },
];
const LT_IMMOVABLE: FieldSpec[] = [
  ...ST_IMMOVABLE.filter((field) => !['improvementCost', 'deduction54B'].includes(field.key)),
  { key: 'indexedAcquisitionCost', label: 'Indexed acquisition cost', kind: 'money' },
  { key: 'improvementFinancialYear', label: 'Improvement financial year' }, { key: 'improvementCost', label: 'Improvement cost', kind: 'money' },
  { key: 'indexedImprovementCost', label: 'Indexed improvement cost', kind: 'money' },
  { key: 'exemptionSection', label: 'Exemption section', kind: 'select', options: [['54','54'],['54B','54B'],['54F','54F'],['54EC','54EC']] },
  { key: 'exemptionAmount', label: 'Exemption amount', kind: 'money' },
];
const SCRIP_FIELDS: FieldSpec[] = [
  { key: 'shareOnOrBefore', label: 'Acquired before/after 31-Jan-2018 *', kind: 'select', required: true, options: [['BE','Before/on 31-Jan-2018'],['AE','After 31-Jan-2018']] },
  { key: 'isin', label: 'ISIN code *', required: true, maxLength: 12, pattern: '(?:IN[0-9A-Z]{10}|INNOTREQUIRD)' },
  { key: 'name', label: 'Share / unit name *', required: true, maxLength: 125 }, { key: 'quantity', label: 'Number of shares / units', kind: 'decimal' },
  { key: 'salePricePerUnit', label: 'Sale price per unit', kind: 'decimal' }, { key: 'totalSaleValue', label: 'Total sale value *', kind: 'money', required: true },
  { key: 'costWithoutIndexation', label: 'Cost without indexation *', kind: 'money', required: true }, { key: 'acquisitionCost', label: 'Acquisition cost *', kind: 'decimal', required: true },
  { key: 'fmvPerUnit', label: 'FMV per unit on 31-Jan-2018 *', kind: 'decimal', required: true }, { key: 'totalFmv', label: 'Total fair market value *', kind: 'money', required: true },
  { key: 'transferExpenses', label: 'Transfer expenses *', kind: 'decimal', required: true },
  { key: 'ltcgBeforeLower', label: 'LTCG before lower of B1/B2 *', kind: 'readout', required: true }, { key: 'totalDeductions', label: 'Total deductions *', kind: 'readout', required: true },
  { key: 'balance', label: 'Balance *', kind: 'readout', required: true },
];
const VDA_FIELDS: FieldSpec[] = [
  { key: 'dateOfAcquisition', label: 'Date of acquisition *', kind: 'date', required: true }, { key: 'dateOfTransfer', label: 'Date of transfer *', kind: 'date', required: true },
  { key: 'head', label: 'Head under which taxed *', kind: 'select', required: true, options: [['CG','Capital gains'],['BI','Business income']] },
  { key: 'acquisitionCost', label: 'Acquisition cost *', kind: 'money', required: true }, { key: 'consideration', label: 'Consideration received *', kind: 'money', required: true },
  { key: 'incomeFromVda', label: 'Income from VDA *', kind: 'readout', required: true },
];
const DTAA_FIELDS: FieldSpec[] = [
  { key: 'amount', label: 'DTAA amount *', kind: 'signed', required: true }, { key: 'itemNumber', label: 'Schedule CG item number *', required: true },
  { key: 'countryName', label: 'Country name *', required: true }, { key: 'countryCode', label: 'Country code excluding India *', required: true },
  { key: 'article', label: 'DTAA article *', required: true, maxLength: 16 }, { key: 'treatyRate', label: 'Treaty rate % *', kind: 'decimal', required: true },
  { key: 'trcAvailable', label: 'Tax residency certificate?', kind: 'boolean' }, { key: 'itActSection', label: 'Income-tax Act section *', required: true },
  { key: 'itActRate', label: 'Income-tax Act rate % *', kind: 'decimal', required: true }, { key: 'applicableRate', label: 'Applicable rate %', kind: 'decimal' },
];
const TRANSFEREE_FIELDS: FieldSpec[] = [
  { key: 'name', label: 'Buyer name *', required: true, maxLength: 125 }, { key: 'pan', label: 'Buyer PAN', maxLength: 10, pattern: '[A-Z]{5}[0-9]{4}[A-Z]' },
  { key: 'aadhaar', label: 'Buyer Aadhaar', maxLength: 12, pattern: '[0-9]{12}' }, { key: 'share', label: 'Percentage share *', kind: 'decimal', required: true },
  { key: 'amount', label: 'Amount *', kind: 'money', required: true }, { key: 'address', label: 'Property address *', required: true, maxLength: 250 },
  { key: 'stateCode', label: 'State code *', required: true }, { key: 'countryCode', label: 'Country code *', required: true },
  { key: 'pinCode', label: 'PIN code' }, { key: 'zipCode', label: 'ZIP code', maxLength: 8 },
];
const IMPROVEMENT_FIELDS: FieldSpec[] = [
  { key: 'serialNumber', label: 'Serial number *', kind: 'money', required: true }, { key: 'cost', label: 'Improvement cost *', kind: 'money', required: true },
  { key: 'financialYear', label: 'Financial year of improvement *', required: true }, { key: 'indexedCost', label: 'Indexed improvement cost *', kind: 'readout', required: true },
];
const EXEMPTION_FIELDS: FieldSpec[] = [
  { key: 'section', label: 'Exemption section *', kind: 'select', required: true, options: [['54','54'],['54B','54B'],['54F','54F'],['54EC','54EC']] },
  { key: 'amount', label: 'Exemption amount *', kind: 'money', required: true },
];
const UNUTILIZED_FIELDS: FieldSpec[] = [
  { key: 'transferPreviousYear', label: 'Previous year of original transfer *', required: true }, { key: 'sectionClaimed', label: 'Section claimed *', required: true },
  { key: 'yearAssetAcquired', label: 'Year in which asset acquired' }, { key: 'amountUtilized', label: 'Amount utilized', kind: 'money' },
  { key: 'amountUnutilized', label: 'Amount not utilized *', kind: 'money', required: true },
];
const CLAIM_FIELDS: FieldSpec[] = [
  { key: 'section', label: 'Deduction section *', kind: 'select', required: true, options: [['54','54'],['54B','54B'],['54EC','54EC'],['54F','54F'],['115F','115F'],['54D','54D'],['54G','54G'],['54GA','54GA']] },
  { key: 'dateOfTransfer', label: 'Date of transfer / acquisition *', kind: 'date', required: true }, { key: 'newAssetCost', label: 'Cost / amount invested', kind: 'money' },
  { key: 'dateOfPurchase', label: 'Purchase / investment date', kind: 'date' }, { key: 'amountDeposited', label: 'Amount deposited', kind: 'money' },
  { key: 'depositDate', label: 'Deposit date', kind: 'date' }, { key: 'accountNumber', label: 'Capital Gains Account number', maxLength: 20 },
  { key: 'ifsc', label: 'IFSC', pattern: '[A-Z]{4}0[A-Z0-9]{6}', maxLength: 11 }, { key: 'amountDeducted', label: 'Amount deducted *', kind: 'money', required: true },
];
const QUARTERS: FieldSpec[] = [
  { key: 'upto15June', label: 'Up to 15 June', kind: 'money' }, { key: 'upto15September', label: '16 June–15 September', kind: 'money' },
  { key: 'upto15December', label: '16 September–15 December', kind: 'money' }, { key: 'upto15March', label: '16 December–15 March', kind: 'money' },
  { key: 'upto31March', label: '16 March–31 March', kind: 'money' },
];

export function hasNonSimplifiedCapitalGains(schedule: Partial<CapitalGainsScheduleData> | undefined): boolean {
  if (!schedule) return false;
  const arrays: Array<keyof CapitalGainsScheduleData> = ['stImmovable','stEquity','stNriUnlisted','stOtherAssets','stSlumpSale','ltImmovable','ltProviso112','ltNri112115','ltForeignAssets','ltOtherAssets','ltSlumpSale','schedule112A','schedule115AD','vda','stUnutilized','ltUnutilized','stDtaa','ltDtaa','buyBackLosses','deductionClaims'];
  for (const key of arrays) { const rows = schedule[key]; if (Array.isArray(rows) && rows.length > 0) return true; }
  const sums: Array<keyof CapitalGainsScheduleData> = ['stSection48','ltNriProviso48','ltNri112A','aggregates','lossSetOff','quarterly'];
  for (const key of sums) { const obj = schedule[key]; if (obj && typeof obj === 'object' && !Array.isArray(obj) && Object.keys(obj as object).length > 0) return true; }
  if (schedule.stUnutilizedFlag && schedule.stUnutilizedFlag !== 'N') return true;
  if (schedule.ltUnutilizedFlag && schedule.ltUnutilizedFlag !== 'N') return true;
  return false;
}

/** Unified CBDT AY 2026-27 Capital Gains capture for ITR-1 through ITR-4. */
export function CapitalGainsEntryManager({ data: incoming, entries = [], onChange, selectedForm, summary, issues = [] }: Props): React.ReactElement {
  const data = normalizeData(incoming);
  const normalizedForm = selectedForm.replace('-', '').toUpperCase();
  const simple = normalizedForm === 'ITR1' || normalizedForm === 'ITR4';
  const itr3 = normalizedForm === 'ITR3';
  const patchObject = (key: 'simplified112A' | 'quarterly' | 'aggregates' | 'stSection48' | 'ltNriProviso48' | 'ltNri112A' | 'lossSetOff', patch: JsonRow): void => onChange({ ...data, [key]: { ...data[key], ...patch } });
  const patchFlag = (key: 'stUnutilizedFlag' | 'ltUnutilizedFlag', value: string): void => onChange({ ...data, [key]: value });
  const setRows = (key: SectionKey, rows: JsonRow[]): void => onChange({ ...data, [key]: rows });
  const importedSale = entries.reduce((sum, row) => sum + Number(row.saleValue ?? row.saleCost ?? 0), 0);
  const importedCost = entries.reduce((sum, row) => sum + Number(row.actualCost ?? row.purchaseCost ?? 0), 0);
  const simpleSale = Number(data.simplified112A.totalSaleConsideration || 0);
  const simpleCost = Number(data.simplified112A.totalCostAcquisition || 0);
  // Only derive the gain when the user has entered both sale and cost.
  // When cost is blank (0), we must NOT auto-cap sale to ₹1,25,000 — that
  // would mislead the user into thinking the gain is ₹1,25,000 when they
  // haven't actually provided the purchase value yet.
  const costEntered = Number(data.simplified112A.totalCostAcquisition) > 0;
  const simpleGain = costEntered
    ? Math.max(0, Math.min(125000, simpleSale - simpleCost))
    : 0;
  const allIssues = (summary?.issues || issues).filter(Boolean);

  const rows = (key: SectionKey): JsonRow[] => Array.isArray(data[key]) ? data[key] as JsonRow[] : [];
  const sumRows = (key: string, field: string): number => rows(key as SectionKey).reduce((acc, row) => acc + Number(row[field] || 0), 0);
  const countRows = (key: SectionKey): number => rows(key).length;
  const overviewCategories = [
    { key: 'stImmovable', label: 'A1. STCG land/building', count: countRows('stImmovable'), sale: sumRows('stImmovable','fullConsideration'), cost: sumRows('stImmovable','acquisitionCost') },
    { key: 'stEquity', label: 'A2. STCG equity/STT', count: countRows('stEquity'), sale: sumRows('stEquity','fullConsideration'), cost: sumRows('stEquity','acquisitionCost') },
    { key: 'stNriUnlisted', label: 'A3. STCG NRI unlisted', count: countRows('stNriUnlisted'), sale: sumRows('stNriUnlisted','unquotedConsideration'), cost: sumRows('stNriUnlisted','acquisitionCost') },
    { key: 'stOtherAssets', label: 'A4. STCG other assets', count: countRows('stOtherAssets'), sale: sumRows('stOtherAssets','fullConsideration'), cost: sumRows('stOtherAssets','acquisitionCost') },
    { key: 'stSlumpSale', label: 'A5. STCG slump sale (ITR-3)', count: countRows('stSlumpSale'), sale: 0, cost: 0 },
    { key: 'ltImmovable', label: 'B1. LTCG land/building', count: countRows('ltImmovable'), sale: sumRows('ltImmovable','fullConsideration'), cost: sumRows('ltImmovable','acquisitionCost') },
    { key: 'ltProviso112', label: 'B2. LTCG proviso 112', count: countRows('ltProviso112'), sale: sumRows('ltProviso112','fullConsideration'), cost: sumRows('ltProviso112','acquisitionCost') },
    { key: 'ltNri112115', label: 'B3. LTCG NRI 112/115', count: countRows('ltNri112115'), sale: sumRows('ltNri112115','fullConsideration'), cost: sumRows('ltNri112115','acquisitionCost') },
    { key: 'ltForeignAssets', label: 'B4. LTCG NRI foreign assets', count: countRows('ltForeignAssets'), sale: sumRows('ltForeignAssets','saleValue'), cost: 0 },
    { key: 'ltOtherAssets', label: 'B5. LTCG other assets', count: countRows('ltOtherAssets'), sale: sumRows('ltOtherAssets','fullConsideration'), cost: sumRows('ltOtherAssets','acquisitionCost') },
    { key: 'ltSlumpSale', label: 'B6. LTCG slump sale (ITR-3)', count: countRows('ltSlumpSale'), sale: 0, cost: 0 },
    { key: 'schedule112A', label: 'C. Schedule 112A scrips', count: countRows('schedule112A'), sale: sumRows('schedule112A','totalSaleValue'), cost: sumRows('schedule112A','costWithoutIndexation') },
    { key: 'schedule115AD', label: 'D. Schedule 115AD scrips', count: countRows('schedule115AD'), sale: sumRows('schedule115AD','totalSaleValue'), cost: sumRows('schedule115AD','costWithoutIndexation') },
    { key: 'vda', label: 'E. Schedule VDA', count: countRows('vda'), sale: sumRows('vda','consideration'), cost: sumRows('vda','acquisitionCost') },
    { key: 'deductionClaims', label: 'F. Deduction claims', count: countRows('deductionClaims'), sale: 0, cost: 0 },
    { key: 'stDtaa', label: 'STCG under DTAA', count: countRows('stDtaa'), sale: 0, cost: 0 },
    { key: 'ltDtaa', label: 'LTCG under DTAA', count: countRows('ltDtaa'), sale: 0, cost: 0 },
    { key: 'buyBackLosses', label: 'Buy-back losses', count: countRows('buyBackLosses'), sale: 0, cost: 0 },
  ].filter((cat) => cat.count > 0 || cat.sale > 0 || cat.cost > 0);
  const totalImportedSale = overviewCategories.reduce((sum, cat) => sum + cat.sale, 0);
  const totalImportedCost = overviewCategories.reduce((sum, cat) => sum + cat.cost, 0);

  return <div>
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
      <div><h3 style={{ margin: 0, fontSize: 14, color: 'var(--text-secondary)' }}>Capital Gains — {selectedForm}</h3><div style={{ marginTop: 4, fontSize: 12, color: 'var(--text-muted)' }}>Full Schedule CG capture. Sections not reportable under the selected form are locked read-only.</div></div>
    </div>
    {simple && <div style={{ marginBottom: 16, padding: '14px 16px', background: '#fef3c7', border: '2px solid #f59e0b', borderRadius: 8, fontSize: 13, color: '#92400e' }}><strong style={{ fontSize: 14, display: 'block', marginBottom: 4 }}>⚠ Switch to ITR-2 or ITR-3 to report these gains</strong><div>The selected form (ITR-1/ITR-4) only permits the simplified section 112A schedule. The full Schedule CG sections below are locked because they cannot be filed under this form. Switch to ITR-2 or ITR-3 using the form selector at the top of the page to unlock and report these transactions.</div></div>}
    {allIssues.length > 0 && <div style={{ padding: 12, marginBottom: 16, color: 'var(--danger)', background: '#fef2f2', borderRadius: 6 }}><strong>Review required</strong><ul>{allIssues.map((issue, index) => <li key={index}>{String(issue.message || issue.code || 'Capital-gains issue')}</li>)}</ul></div>}
    {entries.length > 0 && <div style={{ ...cardStyle, background: '#fffbeb' }}><strong style={{ fontSize: 13 }}>Imported AIS reference</strong><div style={{ fontSize: 12, marginTop: 5, color: 'var(--text-secondary)' }}>{entries.length} imported row(s); sale consideration ₹{importedSale.toLocaleString('en-IN')}; recorded cost ₹{importedCost.toLocaleString('en-IN')}. These are evidence only until entered in the applicable CBDT schedule below.</div></div>}
    {overviewCategories.length > 0 && <div style={{ ...cardStyle, background: '#f0fdf4', border: '1px solid #bbf7d0' }}><strong style={{ fontSize: 13 }}>Gains overview</strong><div style={{ fontSize: 12, marginTop: 4, color: 'var(--text-muted)' }}>Categorised by Schedule CG section. Use this to decide the correct ITR form before filing. Zero-entry categories are omitted.</div><div style={{ marginTop: 12 }}><table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}><thead><tr style={{ textAlign: 'left', color: 'var(--text-secondary)' }}><th style={{ padding: '6px 8px', borderBottom: '1px solid var(--border)' }}>Category</th><th style={{ padding: '6px 8px', borderBottom: '1px solid var(--border)', textAlign: 'right' }}>Rows</th><th style={{ padding: '6px 8px', borderBottom: '1px solid var(--border)', textAlign: 'right' }}>Sale ₹</th><th style={{ padding: '6px 8px', borderBottom: '1px solid var(--border)', textAlign: 'right' }}>Cost ₹</th></tr></thead><tbody>{overviewCategories.map((cat) => <tr key={cat.key}><td style={{ padding: '6px 8px', borderBottom: '1px solid var(--border)' }}>{cat.label}</td><td style={{ padding: '6px 8px', borderBottom: '1px solid var(--border)', textAlign: 'right' }}>{cat.count}</td><td style={{ padding: '6px 8px', borderBottom: '1px solid var(--border)', textAlign: 'right' }}>{cat.sale.toLocaleString('en-IN')}</td><td style={{ padding: '6px 8px', borderBottom: '1px solid var(--border)', textAlign: 'right' }}>{cat.cost.toLocaleString('en-IN')}</td></tr>)}</tbody><tfoot><tr style={{ fontWeight: 600 }}><td style={{ padding: '8px' }}>Total</td><td style={{ padding: '8px', textAlign: 'right' }}>{overviewCategories.reduce((s, c) => s + c.count, 0)}</td><td style={{ padding: '8px', textAlign: 'right' }}>₹{totalImportedSale.toLocaleString('en-IN')}</td><td style={{ padding: '8px', textAlign: 'right' }}>₹{totalImportedCost.toLocaleString('en-IN')}</td></tr></tfoot></table></div></div>}

    <SectionTitle title="Quick entry — section 112A (simplified)" />
    <ApplicabilityBadge form={normalizedForm} permitted={simple} />
    <div style={cardStyle}><div style={gridStyle}>
      <Field spec={{ key: 'totalSaleConsideration', label: 'Total sale consideration *', kind: 'money', required: true }} row={data.simplified112A} patch={(patch) => patchObject('simplified112A', patch)} />
      <Field spec={{ key: 'totalCostAcquisition', label: 'Total cost of acquisition *', kind: 'money', required: true }} row={data.simplified112A} patch={(patch) => patchObject('simplified112A', patch)} />
      <Readout label="Long-term capital gain u/s 112A *" value={simpleGain} />
    </div><div style={{ fontSize: 12, color: 'var(--text-muted)' }}>ITR-1/ITR-4 permit only this simplified 112A schedule and cap the reportable gain at ₹1,25,000. ITR-2/3 filers should use the full Schedule 112A in section C below for scrip-level detail.</div></div>

    <SectionTitle title="A. Short-term capital gains" />
    <ApplicabilityBadge form={normalizedForm} permitted={!simple} />
    <RowSection title="A1. Land or building" rows={data.stImmovable} fields={ST_IMMOVABLE} disabled={simple} nested={[{ key: 'transferees', title: 'Transferee / buyer details', fields: TRANSFEREE_FIELDS }]} onChange={(rows) => setRows('stImmovable', rows)} />
    <RowSection title="A2. Equity shares / equity-oriented funds with STT" rows={data.stEquity} disabled={simple} fields={[{ key: 'sectionCode', label: 'Section code *', kind: 'select', required: true, options: [['1A','111A'],['5AD1biip','115AD(1)(b)(ii) proviso']] }, ...COMMON_ASSET]} onChange={(rows) => setRows('stEquity', rows)} maxRows={2} />
    <AggregateCard fields={[{ key: 'nriSttPaid', label: 'NRI transactions — STT paid *', kind: 'signed', required: true }, { key: 'nriSttNotPaid', label: 'NRI transactions — STT not paid *', kind: 'signed', required: true }]} row={data.stSection48} disabled={simple} patch={(patch) => patchObject('stSection48', patch)} />
    <RowSection title="A3. NRI unlisted shares / securities u/s 115AD" rows={data.stNriUnlisted} fields={[{ key: 'unquotedConsideration', label: 'Consideration for unquoted shares', kind: 'money' }, { key: 'fairMarketValue', label: 'Fair market value u/s 50CA', kind: 'money' }, ...COMMON_ASSET]} disabled={simple} onChange={(rows) => setRows('stNriUnlisted', rows)} />
    <RowSection title="A4. Other short-term assets" disabled={simple} rows={data.stOtherAssets} fields={[...COMMON_ASSET, ...(itr3 ? [{ key: 'deemedGain', label: 'Deemed STCG', kind: 'money' } as FieldSpec, { key: 'exemptionSection', label: 'Exemption', kind: 'select', options: [['54G','54G'],['54GA','54GA']] } as FieldSpec, { key: 'exemptionAmount', label: 'Exemption amount', kind: 'money' } as FieldSpec] : [])]} onChange={(rows) => setRows('stOtherAssets', rows)} />
    {itr3 && <RowSection title="A5. Short-term slump sale" rows={data.stSlumpSale} fields={[{ key: 'fmv11uae2', label: 'FMV under Rule 11UAE(2) *', kind: 'money', required: true }, { key: 'fmv11uae3', label: 'FMV under Rule 11UAE(3) *', kind: 'money', required: true }, { key: 'netWorth', label: 'Net worth of division *', kind: 'signed', required: true }]} onChange={(rows) => setRows('stSlumpSale', rows)} />}
    <AggregateCard fields={[{ key: 'stPassThrough', label: 'Pass-through STCG *', kind: 'signed' }, { key: 'stPassThrough20', label: 'Pass-through STCG at 20%', kind: 'signed' }, { key: 'stPassThrough30', label: 'Pass-through STCG at 30%', kind: 'signed' }, { key: 'stPassThroughApplicable', label: 'Pass-through STCG at applicable rate', kind: 'signed' }]} row={data.aggregates} patch={(patch) => patchObject('aggregates', patch)} />
    <FlagField label="Unutilized STCG deposit exists? *" value={data.stUnutilizedFlag} disabled={simple} onChange={(value) => patchFlag('stUnutilizedFlag', value)} />
    <RowSection title="Prior-year unutilized STCG deposits" disabled={simple} rows={data.stUnutilized} fields={UNUTILIZED_FIELDS} onChange={(rows) => setRows('stUnutilized', rows)} />
    <RowSection title="STCG under DTAA" disabled={simple} rows={data.stDtaa} fields={DTAA_FIELDS} onChange={(rows) => setRows('stDtaa', rows)} />
    <RowSection title="Capital loss on buy-back of shares" disabled={simple} rows={data.buyBackLosses} fields={[{ key: 'rate', label: 'Rate bucket *', kind: 'select', required: true, options: [['STL20','STCG 20%'],['STL30','STCG 30%'],['STLAR','Applicable rate']] }, { key: 'amount', label: 'Loss amount *', kind: 'signed', required: true }]} onChange={(rows) => setRows('buyBackLosses', rows)} maxRows={3} />

    <SectionTitle title="B. Long-term capital gains" />
    <ApplicabilityBadge form={normalizedForm} permitted={!simple} />
    <RowSection title="B1. Land or building" rows={data.ltImmovable} disabled={simple} fields={LT_IMMOVABLE} nested={[{ key: 'transferees', title: 'Transferee / buyer details', fields: TRANSFEREE_FIELDS }, { key: 'improvements', title: 'Indexed cost of improvements', fields: IMPROVEMENT_FIELDS }, { key: 'exemptions', title: 'Exemptions under sections 54/54B/54F/54EC', fields: EXEMPTION_FIELDS, maxRows: 6 }]} onChange={(rows) => setRows('ltImmovable', rows)} />
    <RowSection title="B2. Securities where proviso to section 112 applies" disabled={simple} rows={data.ltProviso112} fields={[{ key: 'sectionCode', label: 'Section code *', kind: 'select', required: true, options: [['22','Section 112 proviso'],['5ACA1b','Section 115ACA(1)(b)']] }, ...COMMON_ASSET, { key: 'deduction54F', label: 'Deduction u/s 54F', kind: 'money' }]} onChange={(rows) => setRows('ltProviso112', rows)} maxRows={2} />
    <AggregateCard fields={[{ key: 'ltcgWithoutBenefit', label: 'NRI LTCG without indexation benefit *', kind: 'signed', required: true }, { key: 'deduction54F', label: 'Deduction u/s 54F *', kind: 'money', required: true }, { key: 'balance', label: 'Balance NRI LTCG *', kind: 'readout', required: true }]} row={data.ltNriProviso48} disabled={simple} patch={(patch) => patchObject('ltNriProviso48', patch)} />
    <RowSection title="B3. NRI gains under sections 112 / 115" disabled={simple} rows={data.ltNri112115} fields={[{ key: 'sectionCode', label: 'Section code *', kind: 'select', required: true, options: [['21ciii','Section 112(1)(c)(iii)'],['5AC1c','Section 115AC(1)(c)'],['5ADiii','Section 115AD(1)(iii)']] }, ...COMMON_ASSET, { key: 'deduction54F', label: 'Deduction u/s 54F', kind: 'money' }]} onChange={(rows) => setRows('ltNri112115', rows)} maxRows={3} />
    <RowSection title="B4. NRI specified foreign assets" disabled={simple} rows={data.ltForeignAssets} fields={[{ key: 'saleValue', label: 'Sale value of specified asset *', kind: 'money', required: true }, { key: 'deduction115F', label: 'Deduction u/s 115F *', kind: 'money', required: true }]} onChange={(rows) => setRows('ltForeignAssets', rows)} />
    <RowSection title="B5. Other long-term assets" disabled={simple} rows={data.ltOtherAssets} fields={[...COMMON_ASSET, { key: 'exemptionSection', label: 'Exemption section' }, { key: 'exemptionAmount', label: 'Exemption amount', kind: 'money' }]} onChange={(rows) => setRows('ltOtherAssets', rows)} />
    {itr3 && <RowSection title="B6. Long-term slump sale" rows={data.ltSlumpSale} fields={[{ key: 'fmv11uae2', label: 'FMV under Rule 11UAE(2) *', kind: 'money', required: true }, { key: 'fmv11uae3', label: 'FMV under Rule 11UAE(3) *', kind: 'money', required: true }, { key: 'netWorth', label: 'Net worth of division *', kind: 'signed', required: true }, { key: 'exemptionAmount', label: 'Exemption amount *', kind: 'money', required: true }]} onChange={(rows) => setRows('ltSlumpSale', rows)} />}
    <AggregateCard fields={[{ key: 'ltPassThrough', label: 'Pass-through LTCG *', kind: 'signed' }, { key: 'ltPassThrough112A', label: 'Pass-through LTCG u/s 112A at 12.5%', kind: 'signed' }, { key: 'ltPassThrough125', label: 'Pass-through other LTCG at 12.5%', kind: 'signed' }]} row={data.aggregates} patch={(patch) => patchObject('aggregates', patch)} />
    <FlagField label="Unutilized LTCG deposit exists? *" value={data.ltUnutilizedFlag} disabled={simple} onChange={(value) => patchFlag('ltUnutilizedFlag', value)} />
    <RowSection title="Prior-year unutilized LTCG deposits" disabled={simple} rows={data.ltUnutilized} fields={UNUTILIZED_FIELDS} onChange={(rows) => setRows('ltUnutilized', rows)} />
    <RowSection title="LTCG under DTAA" disabled={simple} rows={data.ltDtaa} fields={DTAA_FIELDS} onChange={(rows) => setRows('ltDtaa', rows)} />

    <SectionTitle title="C. Schedule 112A — equity shares, equity-oriented funds and business-trust units" />
    <ApplicabilityBadge form={normalizedForm} permitted={!simple} />
    <RowSection title="Schedule 112A scrip details" disabled={simple} rows={data.schedule112A} fields={SCRIP_FIELDS} onChange={(rows) => setRows('schedule112A', rows)} />
    <ScheduleTotals title="Schedule 112A totals" rows={data.schedule112A} />
    <AggregateCard fields={[{ key: 'balance', label: 'NRI / FII Schedule 112A balance', kind: 'signed' }, { key: 'deduction54F', label: 'NRI / FII deduction u/s 54F', kind: 'money' }]} row={data.ltNri112A} disabled={simple} patch={(patch) => patchObject('ltNri112A', patch)} />
    <SectionTitle title="D. Schedule 115AD — FII/FPI securities" />
    <RowSection title="Schedule 115AD scrip details" disabled={simple} rows={data.schedule115AD} fields={SCRIP_FIELDS} onChange={(rows) => setRows('schedule115AD', rows)} />
    <ScheduleTotals title="Schedule 115AD totals" rows={data.schedule115AD} />
    <SectionTitle title="E. Schedule VDA" />
    <RowSection title="Virtual digital asset transfers" disabled={simple} rows={data.vda} fields={VDA_FIELDS.map((field) => field.key === 'head' && !itr3 ? { ...field, options: [['CG','Capital gains']] } : field)} onChange={(rows) => setRows('vda', rows)} />
    <SectionTitle title="F. Capital-gain deduction claims" />
    <RowSection title="Sections 54 / 54B / 54EC / 54F / 115F deduction details" disabled={simple} rows={data.deductionClaims} fields={CLAIM_FIELDS.map((field) => field.key === 'section' && !itr3 ? { ...field, options: field.options?.filter(([value]) => !['54D','54G','54GA'].includes(value)) } : field)} onChange={(rows) => setRows('deductionClaims', rows)} />
    <SectionTitle title="G. Accrual or receipt of capital gains by instalment period" />
    <QuarterlyEditor row={data.quarterly} disabled={simple} patch={(patch) => patchObject('quarterly', patch)} />
    <SectionTitle title="H. Computed Schedule CG totals and current-year loss set-off" />
    <LossSetOffMatrix row={data.lossSetOff} disabled={simple} patch={(patch) => patchObject('lossSetOff', patch)} />
    <div style={cardStyle}><div style={gridStyle}><Readout label="Total short-term capital gain" value={Number(summary?.totalSTCG || 0)} /><Readout label="Total long-term capital gain" value={Number(summary?.totalLTCG || 0)} /><Readout label="Income from VDA transfers" value={Number(summary?.vdaIncome || 0)} /><Readout label="Total Schedule CG" value={Number(summary?.totalCapitalGains || 0)} /><Readout label="Current-year loss set off" value={Number(summary?.totalLossSetOff || 0)} /><Readout label="Loss remaining after set off" value={Number(summary?.lossRemaining || 0)} /></div></div>
  </div>;
}

function ApplicabilityBadge({ form, permitted }: { form: string; permitted: boolean }): React.ReactElement | null {
  if (permitted) return null;
  const target = form === 'ITR1' || form === 'ITR4' ? 'ITR-2 / ITR-3' : form === 'ITR2' ? 'ITR-3' : 'the selected form';
  return <div style={{ marginBottom: 12, padding: '8px 12px', background: '#fef3c7', border: '1px solid #fcd34d', borderRadius: 6, fontSize: 12, color: '#92400e' }}><strong>Not reportable under {form === 'ITR1' ? 'ITR-1' : form === 'ITR2' ? 'ITR-2' : form === 'ITR3' ? 'ITR-3' : 'ITR-4'}.</strong> Entries below are preserved but will not be filed. Switch to {target} to report these gains.</div>;
}
function SectionTitle({ title }: { title: string }): React.ReactElement { return <h3 style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-secondary)', margin: '24px 0 12px' }}>{title}</h3>; }
function RowSection({ title, rows, fields, nested = [], onChange, maxRows, disabled = false }: { title: string; rows: JsonRow[]; fields: FieldSpec[]; nested?: NestedSpec[]; onChange: (rows: JsonRow[]) => void; maxRows?: number; disabled?: boolean }): React.ReactElement {
  const add = (): void => { if (disabled || (maxRows !== undefined && rows.length >= maxRows)) return; onChange([...rows, { id: makeId() }]); };
  const patch = (index: number, values: JsonRow): void => { if (disabled) return; onChange(rows.map((row, rowIndex) => rowIndex === index ? { ...row, ...values } : row)); };
  const dimmed = disabled ? { opacity: 0.6, pointerEvents: 'none' as const } : {};
  return <div style={{ marginBottom: 18, ...dimmed }}><div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}><strong style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{title} ({rows.length}{maxRows ? `/${maxRows}` : ''})</strong><button type="button" onClick={add} disabled={disabled || (maxRows !== undefined && rows.length >= maxRows)} style={{ padding: '6px 12px', background: 'var(--gold)', color: '#fff', border: 0, borderRadius: 6, fontSize: 12 }}>+ Add entry</button></div>{rows.length === 0 && <div style={{ padding: 18, textAlign: 'center', color: 'var(--text-muted)', background: 'var(--bg)', borderRadius: 6 }}>No entries.</div>}{rows.map((row, index) => <div key={String(row.id || index)} style={cardStyle}><div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}><strong style={{ fontSize: 12 }}>Entry #{index + 1}</strong><button type="button" onClick={() => onChange(rows.filter((_, rowIndex) => rowIndex !== index))} disabled={disabled} style={{ padding: '4px 8px', background: 'var(--danger)', color: '#fff', border: 0, borderRadius: 4, fontSize: 11 }}>Remove</button></div><div style={gridStyle}>{fields.map((field) => <Field key={field.key} spec={field} row={row} patch={(values) => patch(index, values)} disabled={disabled} />)}</div>{nested.map((spec) => <NestedRows key={spec.key} spec={spec} rows={Array.isArray(row[spec.key]) ? row[spec.key] as JsonRow[] : []} onChange={(nestedRows) => patch(index, { [spec.key]: nestedRows })} disabled={disabled} />)}</div>)}</div>;
}
function AggregateCard({ fields, row, patch, disabled = false }: { fields: FieldSpec[]; row: JsonRow; patch: (values: JsonRow) => void; disabled?: boolean }): React.ReactElement { return <div style={{ ...cardStyle, ...(disabled ? { opacity: 0.6, pointerEvents: 'none' as const } : {}) }}><div style={gridStyle}>{fields.map((field) => <Field key={field.key} spec={field} row={row} patch={patch} disabled={disabled} />)}</div></div>; }
function Field({ spec, row, patch, disabled = false }: { spec: FieldSpec; row: JsonRow; patch: (values: JsonRow) => void; disabled?: boolean }): React.ReactElement {
  const value = row[spec.key] ?? '';
  if (spec.kind === 'readout') return <Readout label={spec.label} value={Number(value || 0)} />;
  if (spec.kind === 'select' || spec.kind === 'boolean') { const options = spec.kind === 'boolean' ? [['','Select'],['Y','Yes'],['N','No']] : [['','Select'], ...(spec.options || [])]; return <div><label style={labelStyle}>{spec.label}</label><select required={spec.required} value={String(value)} onChange={(event) => patch({ [spec.key]: event.target.value })} disabled={disabled} style={{ ...inputStyle, ...(disabled ? { background: '#f8fafc', color: 'var(--text-muted)', cursor: 'not-allowed' } : {}) }}>{options.map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></div>; }
  const numeric = ['money','signed','decimal'].includes(spec.kind || '');
  return <div><label style={labelStyle}>{spec.label}</label><input required={spec.required} type={spec.kind === 'date' ? 'date' : numeric ? 'number' : 'text'} min={spec.kind === 'money' ? 0 : spec.kind === 'signed' ? -MONEY_MAX : spec.kind === 'decimal' ? 0 : undefined} max={numeric ? MONEY_MAX : undefined} step={spec.kind === 'decimal' ? '0.0001' : numeric ? '1' : undefined} maxLength={spec.maxLength} pattern={spec.pattern} value={String(value)} onChange={(event) => patch({ [spec.key]: numeric ? numberValue(event.target.value) : event.target.value })} readOnly={disabled} style={{ ...inputStyle, ...(disabled ? { background: '#f8fafc', color: 'var(--text-muted)', cursor: 'not-allowed' } : {}) }} /></div>;
}
function QuarterlyEditor({ row, patch, disabled = false }: { row: JsonRow; patch: (values: JsonRow) => void; disabled?: boolean }): React.ReactElement {
  const categories = [['st20','STCG taxable at 20%'],['st30','STCG taxable at 30%'],['stApplicable','STCG at applicable rate'],['stDtaa','STCG under DTAA'],['lt125','LTCG taxable at 12.5%'],['ltDtaa','LTCG under DTAA'],['vda30','VDA gains taxable at 30%']];
  return <div style={disabled ? { opacity: 0.6, pointerEvents: 'none' } : {}}>{categories.map(([key, title]) => <div key={key} style={cardStyle}><strong style={{ fontSize: 12 }}>{title}</strong><div style={{ ...gridStyle, marginTop: 12 }}>{QUARTERS.map((field) => <Field key={field.key} spec={{ ...field, key: `${key}_${field.key}` }} row={row} patch={patch} disabled={disabled} />)}</div></div>)}</div>;
}
function NestedRows({ spec, rows, onChange, disabled = false }: { spec: NestedSpec; rows: JsonRow[]; onChange: (rows: JsonRow[]) => void; disabled?: boolean }): React.ReactElement {
  const add = (): void => { if (disabled || (spec.maxRows !== undefined && rows.length >= spec.maxRows)) return; onChange([...rows, { id: makeId() }]); };
  return <div style={{ padding: 12, border: '1px solid var(--border)', borderRadius: 6, marginTop: 12, ...(disabled ? { opacity: 0.6, pointerEvents: 'none' as const } : {}) }}><div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 10 }}><strong style={{ fontSize: 12 }}>{spec.title} ({rows.length})</strong><button type="button" onClick={add} disabled={disabled || (spec.maxRows !== undefined && rows.length >= spec.maxRows)} style={{ padding: '5px 9px', background: 'var(--gold)', color: '#fff', border: 0, borderRadius: 5 }}>+ Add</button></div>{rows.map((row, index) => <div key={String(row.id || index)} style={{ paddingTop: 10, marginTop: 10, borderTop: index ? '1px solid var(--border)' : undefined }}><div style={gridStyle}>{spec.fields.map((field) => <Field key={field.key} spec={field} row={row} patch={(values) => onChange(rows.map((item, rowIndex) => rowIndex === index ? { ...item, ...values } : item))} disabled={disabled} />)}</div><button type="button" onClick={() => onChange(rows.filter((_, rowIndex) => rowIndex !== index))} disabled={disabled} style={{ padding: '4px 8px', background: 'var(--danger)', color: '#fff', border: 0, borderRadius: 4 }}>Remove</button></div>)}</div>;
}
function FlagField({ label, value, onChange, disabled = false }: { label: string; value: string; onChange: (value: string) => void; disabled?: boolean }): React.ReactElement { return <div style={{ ...cardStyle, ...(disabled ? { opacity: 0.6, pointerEvents: 'none' as const } : {}) }}><label style={labelStyle}>{label}</label><select value={value} onChange={(event) => onChange(event.target.value)} disabled={disabled} style={{ ...inputStyle, ...(disabled ? { background: '#f8fafc', color: 'var(--text-muted)', cursor: 'not-allowed' } : {}) }}><option value="N">No</option><option value="Y">Yes</option><option value="X">Not applicable</option></select></div>; }
function ScheduleTotals({ title, rows }: { title: string; rows: JsonRow[] }): React.ReactElement {
  const total = (key: string): number => rows.reduce((sum, row) => sum + Number(row[key] || 0), 0);
  return <div style={cardStyle}><strong style={{ fontSize: 12 }}>{title}</strong><div style={{ ...gridStyle, marginTop: 12 }}><Readout label="Sale value" value={total('totalSaleValue')} /><Readout label="Cost without indexation" value={total('costWithoutIndexation')} /><Readout label="Acquisition cost" value={total('acquisitionCost')} /><Readout label="FMV of capital assets" value={total('totalFmv')} /><Readout label="Transfer expenses" value={total('transferExpenses')} /><Readout label="Balance" value={total('balance')} /></div></div>;
}
function LossSetOffMatrix({ row, patch, disabled = false }: { row: JsonRow; patch: (values: JsonRow) => void; disabled?: boolean }): React.ReactElement {
  const buckets = [['st20','STCG 20%'],['st30','STCG 30%'],['stApplicable','STCG applicable rate'],['stDtaa','STCG DTAA'],['lt125','LTCG 12.5%'],['ltDtaa','LTCG DTAA']];
  return <div style={{ ...cardStyle, ...(disabled ? { opacity: 0.6, pointerEvents: 'none' as const } : {}) }}><strong style={{ fontSize: 12 }}>Current-year capital-loss set-off matrix</strong>{buckets.map(([key, title]) => <div key={key} style={{ ...gridStyle, marginTop: 12 }}><Field spec={{ key: `${key}_income`, label: `${title} — current-year income`, kind: 'readout', required: true }} row={row} patch={patch} /><Field spec={{ key: `${key}_stcl`, label: 'Short-term loss set off', kind: 'readout', required: true }} row={row} patch={patch} /><Field spec={{ key: `${key}_ltcl`, label: 'Long-term loss set off', kind: 'readout', required: true }} row={row} patch={patch} /><Field spec={{ key: `${key}_balance`, label: 'Current-year capital gain', kind: 'readout', required: true }} row={row} patch={patch} /></div>)}</div>;
}
function Readout({ label, value }: { label: string; value: number }): React.ReactElement { return <div><label style={labelStyle}>{label}</label><input readOnly value={`₹${Number(value || 0).toLocaleString('en-IN')}`} style={{ ...inputStyle, background: '#f8fafc' }} /></div>; }
function numberValue(value: string): number | undefined { if (value === '') return undefined; const parsed = Number(value); return Number.isFinite(parsed) ? parsed : undefined; }
function makeId(): string { return typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function' ? crypto.randomUUID() : `cg-${Date.now()}-${Math.random().toString(36).slice(2)}`; }
