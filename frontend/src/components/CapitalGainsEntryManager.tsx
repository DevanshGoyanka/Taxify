import React, { useCallback } from 'react';

export const RESTRICTED_ASSET_TYPES = [
  'LISTED_EQUITY',
  'EQUITY_ORIENTED_MUTUAL_FUND',
  'BUSINESS_TRUST_UNIT',
] as const;

export type RestrictedAssetType = (typeof RESTRICTED_ASSET_TYPES)[number];

export interface CapitalGainTransaction {
  id?: string;
  transactionId?: string;
  recordKind?: 'EVIDENCE' | 'TRANSACTION';
  assetType?: string;
  description?: string;
  assetDescription?: string;
  acquisitionDate?: string;
  purchaseDate?: string;
  transferDate?: string;
  saleDate?: string;
  actualCost?: number;
  purchaseCost?: number;
  saleValue?: number;
  saleCost?: number;
  transferExpenses?: number;
  expenses?: number;
  sttPaidOnAcquisition?: boolean;
  sttPaidOnTransfer?: boolean;
  recognizedExchange?: boolean;
  acquiredBefore31Jan2018?: boolean;
  fmv31Jan2018?: number;
  fmvJan2018?: number;
  isin?: string;
  quantity?: number;
  /** AIS source description (AMC name, depository, etc.) */
  importSource?: string;
  accountId?: string;
  section?: string;
  /** "PURCHASE" or "SALE" — set by AIS importer */
  evidenceSide?: string;
  [key: string]: unknown;
}

export interface CapitalGainsIssue {
  code?: string;
  message?: string;
  row?: number;
  field?: string;
  severity?: string;
  [key: string]: unknown;
}

export interface CapitalGainsSummary {
  status?: string;
  gross112AGain?: number;
  fullValueOfConsideration?: number;
  costOfAcquisition?: number;
  transferExpenses?: number;
  evidenceCount?: number;
  evidencePurchaseTotal?: number;
  evidenceSaleTotal?: number;
  transactionCount?: number;
  issues?: CapitalGainsIssue[];
  eligibility?: Record<string, boolean>;
  recommendedForm?: string;
  [key: string]: unknown;
}

interface CapitalGainsEntryManagerProps {
  entries: CapitalGainTransaction[];
  onChange: (entries: CapitalGainTransaction[]) => void;
  selectedForm: string;
  summary?: CapitalGainsSummary | null;
  issues?: CapitalGainsIssue[];
  status?: string | null;
  eligibility?: Record<string, boolean> | null;
}

const ASSET_OPTIONS: ReadonlyArray<{ value: RestrictedAssetType; label: string }> = [
  { value: 'LISTED_EQUITY', label: 'Listed equity share' },
  { value: 'EQUITY_ORIENTED_MUTUAL_FUND', label: 'Equity-oriented mutual fund' },
  { value: 'BUSINESS_TRUST_UNIT', label: 'Business trust unit' },
];

function valueOf<T>(entry: CapitalGainTransaction, canonical: keyof CapitalGainTransaction, legacy: keyof CapitalGainTransaction, fallback: T): T {
  const c = entry[canonical];
  if (c !== undefined && c !== null) return c as T;
  const l = entry[legacy];
  return l !== undefined && l !== null ? l as T : fallback;
}

function makeId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') return crypto.randomUUID();
  return `cg-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function parseNumber(value: string): number | undefined {
  if (value.trim() === '') return undefined;
  const n = Number(value);
  return Number.isFinite(n) ? n : undefined;
}

function formatINR(value: unknown): string {
  const n = Number(value);
  return Number.isFinite(n) ? `\u20b9${n.toLocaleString('en-IN', { maximumFractionDigits: 0 })}` : '\u2014';
}

function isRestrictedAsset(assetType: unknown): boolean {
  return RESTRICTED_ASSET_TYPES.includes(String(assetType || '') as RestrictedAssetType);
}

/**
 * True for purchase-only AIS evidence rows (no sale consideration).
 * Per CBDT ITR-1/ITR-4 Schedule 112A rules, only disposal rows with a
 * sale consideration are reported as taxable events. Purchase-only rows
 * are AIS reference data showing what was acquired, used to fill cost of
 * acquisition in the matching sale entry.
 */
function isPurchaseOnlyRow(entry: CapitalGainTransaction): boolean {
  const saleVal = Number(entry.saleValue ?? entry.saleCost ?? 0);
  const side = (entry.evidenceSide ?? '').toUpperCase();
  return saleVal === 0 && side !== 'SALE';
}

export const CapitalGainsEntryManager: React.FC<CapitalGainsEntryManagerProps> = ({
  entries,
  onChange,
  selectedForm,
  summary,
  issues = [],
  status,
  eligibility,
}) => {
  const backendIssues = summary?.issues ?? issues;
  const effectiveStatus = summary?.status ?? status ?? (entries.length ? 'PENDING' : 'EMPTY');
  const effectiveEligibility = summary?.eligibility ?? eligibility ?? {};
  const selectedEligible = effectiveEligibility[selectedForm];

  // Split into disposal rows (sale consideration > 0, go through 112A engine)
  // and purchase-only reference rows (AIS purchase evidence, not a taxable event).
  const disposalEntries = entries.filter((e) => !isPurchaseOnlyRow(e));
  const purchaseRefEntries = entries.filter(isPurchaseOnlyRow);

  const purchaseCount = purchaseRefEntries.length;
  const saleCount = disposalEntries.length;

  const update = useCallback((disposalIndex: number, patch: Partial<CapitalGainTransaction>): void => {
    const disposalEntry = disposalEntries[disposalIndex];
    const fullIndex = entries.indexOf(disposalEntry);
    if (fullIndex === -1) return;
    const transactionPatch = disposalEntry.evidenceSide?.toUpperCase() === 'SALE'
      ? { recordKind: 'TRANSACTION' as const }
      : {};
    onChange(entries.map((entry, row) => row === fullIndex
      ? { ...entry, ...transactionPatch, ...patch }
      : entry));
  }, [entries, disposalEntries, onChange]);

  const updateBoth = useCallback((index: number, canonical: keyof CapitalGainTransaction, legacy: keyof CapitalGainTransaction, value: unknown): void => {
    update(index, { [canonical]: value, [legacy]: value });
  }, [update]);

  const addEntry = useCallback((): void => {
    const id = makeId();
    onChange([...entries, {
      id,
      transactionId: id,
      recordKind: 'TRANSACTION',
      assetType: 'EQUITY_ORIENTED_MUTUAL_FUND',
      description: '',
      assetDescription: '',
      acquisitionDate: '',
      purchaseDate: '',
      transferDate: '',
      saleDate: '',
      actualCost: undefined,
      purchaseCost: undefined,
      saleValue: undefined,
      saleCost: undefined,
      transferExpenses: 0,
      expenses: 0,
      sttPaidOnAcquisition: undefined,
      sttPaidOnTransfer: undefined,
      recognizedExchange: undefined,
      acquiredBefore31Jan2018: false,
      evidenceSide: 'SALE',
    }]);
  }, [entries, onChange]);

  const removeEntry = useCallback((entry: CapitalGainTransaction): void => {
    onChange(entries.filter((e) => e !== entry));
  }, [entries, onChange]);

  const s: React.CSSProperties = { display: 'grid', gap: 4, fontSize: 12, color: '#374151' };
  const inp: React.CSSProperties = { width: '100%', boxSizing: 'border-box', padding: '7px 8px', border: '1px solid #d1d5db', borderRadius: 5, background: 'white' };

  // Summary metrics: evidenceCount is a plain count, not a money value.
  const evidenceMetrics = effectiveStatus === 'EVIDENCE_ONLY'
    ? [
        { label: 'AIS purchase evidence', value: formatINR(summary?.evidencePurchaseTotal ?? 0) },
        { label: 'AIS sale evidence', value: formatINR(summary?.evidenceSaleTotal ?? 0) },
        { label: 'Evidence entries', value: String(summary?.evidenceCount ?? 0) },
        { label: '112A gain / (loss)', value: formatINR(summary?.gross112AGain ?? 0) },
      ]
    : [
        { label: '112A gain / (loss)', value: formatINR(summary?.gross112AGain) },
        { label: 'Sale consideration', value: formatINR(summary?.fullValueOfConsideration) },
        { label: 'Cost accepted', value: formatINR(summary?.costOfAcquisition) },
        { label: 'Transfer expenses', value: formatINR(summary?.transferExpenses) },
      ];

  return (
    <section style={{ display: 'grid', gap: 14 }}>
      {/* Header */}
      <header style={{ padding: 16, borderRadius: 8, color: 'white', background: '#1a1a2e', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
        <div>
          <div style={{ fontWeight: 700 }}>Capital gains</div>
          <div style={{ fontSize: 12, opacity: 0.82, marginTop: 3 }}>
            {entries.length > 0
              ? `${entries.length} AIS entries imported (${purchaseCount} purchase reference${purchaseCount !== 1 ? 's' : ''}, ${saleCount} disposal lot${saleCount !== 1 ? 's' : ''}). AIS-provided dates, costs, quantities, ISINs, STT, and holding classifications are prefilled when available.`
              : `No AIS capital-gain entries imported yet. Use "Import" to download from the ITD portal, or "Add entry" to enter manually.`}
          </div>
        </div>
        <button type="button" onClick={addEntry} style={{ border: 0, borderRadius: 5, padding: '8px 13px', color: 'white', background: '#16a34a', cursor: 'pointer', whiteSpace: 'nowrap' }}>+ Add entry</button>
      </header>

      {/* Summary banner */}
      {summary && (
        <div style={{ padding: 14, border: `1px solid ${effectiveStatus === 'VALID' ? '#86efac' : '#fcd34d'}`, borderRadius: 8, background: effectiveStatus === 'VALID' ? '#f0fdf4' : '#fffbeb' }}>
          <div style={{ fontWeight: 700, color: effectiveStatus === 'VALID' ? '#166534' : '#92400e' }}>
            {effectiveStatus === 'VALID'
              ? '\u2705 Eligible for ITR-1/ITR-4'
              : effectiveStatus === 'BLOCKED'
              ? '\u26a0\ufe0f Issues need resolution before computation'
              : effectiveStatus === 'EVIDENCE_ONLY'
              ? '\ud83d\udccb AIS evidence imported \u2014 detailed disposal fields are prefilled where AIS provides them'
              : 'Review entries below'}
          </div>
          {selectedEligible === false && (
            <div style={{ marginTop: 4, fontSize: 12, color: '#b91c1c' }}>{selectedForm} is not eligible. Use ITR-2 or ITR-3.</div>
          )}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(130px, 1fr))', gap: 8, marginTop: 10 }}>
            {evidenceMetrics.map(({ label, value }) => (
              <div key={label} style={{ padding: 10, border: '1px solid #e5e7eb', borderRadius: 6, background: 'white' }}>
                <div style={{ fontSize: 11, color: '#6b7280' }}>{label}</div>
                <div style={{ marginTop: 2, fontWeight: 700 }}>{value}</div>
              </div>
            ))}
          </div>

          {/* CBDT note: purchase-only rows are reference, not reportable events */}
          {purchaseRefEntries.length > 0 && (
            <div style={{ marginTop: 10, fontSize: 12, color: '#92400e', background: '#fef3c7', borderRadius: 5, padding: '8px 10px' }}>
              <strong>CBDT note:</strong> {purchaseRefEntries.length} AIS purchase record{purchaseRefEntries.length > 1 ? 's' : ''} (shown collapsed below) are <em>not</em> taxable events and are <em>not</em> reported in ITR-1 Schedule 112A.
              Only disposals (rows with a sale consideration) are reported. Use the purchase amounts as cost of acquisition when filling in the matching sale entry above.
            </div>
          )}
        </div>
      )}

      {/* Backend issues */}
      {backendIssues.length > 0 && (
        <div role="alert" style={{ padding: 12, borderRadius: 7, color: '#b91c1c', background: '#fef2f2' }}>
          <strong>Computation issues</strong>
          <ul style={{ margin: '6px 0 0', paddingLeft: 20 }}>
            {backendIssues.map((issue, idx) => (
              <li key={`${issue.code || 'i'}-${idx}`}>
                {issue.row ? `Row ${issue.row}: ` : ''}{issue.message || issue.code || 'Review required'}
              </li>
            ))}
          </ul>
        </div>
      )}

      {entries.length === 0 && (
        <div style={{ padding: 28, textAlign: 'center', border: '1px dashed #cbd5e1', borderRadius: 8, color: '#64748b' }}>
          No entries. Click "Import" or "Add entry".
        </div>
      )}

      {/* ── DISPOSAL ENTRIES (taxable events — Schedule 112A) ── */}
      {disposalEntries.length > 0 && (
        <div>
          <div style={{ fontSize: 12, fontWeight: 600, color: '#1e40af', marginBottom: 8, padding: '6px 10px', background: '#eff6ff', borderRadius: 6, borderLeft: '3px solid #3b82f6' }}>
            Schedule 112A disposal entries ({saleCount}) \u2014 review AIS-prefilled disposal details
          </div>
          {disposalEntries.map((entry, index) => {
            const assetType = String(entry.assetType || '');
            const isRestricted = isRestrictedAsset(assetType);
            const acqDate = valueOf(entry, 'acquisitionDate', 'purchaseDate', '');
            const saleDate = valueOf(entry, 'transferDate', 'saleDate', '');
            const desc = valueOf(entry, 'description', 'assetDescription', '');
            const cost = valueOf<number | undefined>(entry, 'actualCost', 'purchaseCost', undefined);
            const saleVal = valueOf<number | undefined>(entry, 'saleValue', 'saleCost', undefined);
            const exp = valueOf<number | undefined>(entry, 'transferExpenses', 'expenses', 0);
            const fmv = valueOf<number | undefined>(entry, 'fmv31Jan2018', 'fmvJan2018', undefined);
            const rowIssues = backendIssues.filter((issue) => issue.row === index + 1);

            return (
              <article key={entry.id || entry.transactionId || index} style={{ padding: 16, border: '1px solid #bfdbfe', borderRadius: 8, background: 'white', marginBottom: 10 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, marginBottom: 12 }}>
                  <div>
                    <strong>Entry {index + 1}</strong>
                    {entry.section && <span style={{ marginLeft: 8, fontSize: 11, color: '#6b7280', background: '#f3f4f6', padding: '1px 5px', borderRadius: 3 }}>{entry.section}</span>}
                    {!isRestricted && <span style={{ marginLeft: 8, color: '#92400e', fontSize: 12 }}>Only 112A assets supported in {selectedForm}</span>}
                  </div>
                  <button type="button" aria-label={`Remove entry ${index + 1}`} onClick={() => removeEntry(entry)} style={{ border: 0, background: 'transparent', color: '#dc2626', cursor: 'pointer' }}>Remove</button>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(150px, 1fr))', gap: 12 }}>
                  <label style={s}>Asset type<select value={assetType} onChange={(e) => update(index, { assetType: e.target.value })} style={inp}>{!isRestricted && assetType && <option value={assetType}>{assetType.replaceAll('_', ' ')}</option>}{ASSET_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</select></label>
                  <label style={{ ...s, gridColumn: 'span 2' }}>Description / scheme name<input value={String(desc)} onChange={(e) => updateBoth(index, 'description', 'assetDescription', e.target.value)} style={inp} placeholder="Fund name / security / trust" /></label>
                  <label style={s}>ISIN<input value={String(entry.isin || '')} onChange={(e) => update(index, { isin: e.target.value.toUpperCase() })} style={inp} /></label>
                  <label style={s}>Purchase date<input type="date" value={String(acqDate)} onChange={(e) => updateBoth(index, 'acquisitionDate', 'purchaseDate', e.target.value)} style={inp} /></label>
                  <label style={s}>Sale date<input type="date" value={String(saleDate)} onChange={(e) => updateBoth(index, 'transferDate', 'saleDate', e.target.value)} style={inp} /></label>
                  <NumberField label="Cost of acquisition" value={cost} onChange={(v) => updateBoth(index, 'actualCost', 'purchaseCost', v)} style={inp} />
                  <NumberField label="Sale consideration" value={saleVal} onChange={(v) => updateBoth(index, 'saleValue', 'saleCost', v)} style={inp} />
                  <NumberField label="Transfer expenses" value={exp} onChange={(v) => updateBoth(index, 'transferExpenses', 'expenses', v)} style={inp} />
                  <NumberField label="Quantity" value={typeof entry.quantity === 'number' ? entry.quantity : undefined} onChange={(v) => update(index, { quantity: v })} style={inp} />
                  {assetType === 'LISTED_EQUITY' && <BooleanField label="STT on acquisition" value={entry.sttPaidOnAcquisition} onChange={(v) => update(index, { sttPaidOnAcquisition: v })} style={inp} />}
                  <BooleanField label="STT on transfer" value={entry.sttPaidOnTransfer} onChange={(v) => update(index, { sttPaidOnTransfer: v })} style={inp} />
                  {assetType === 'LISTED_EQUITY' && <BooleanField label="Recognized exchange" value={entry.recognizedExchange} onChange={(v) => update(index, { recognizedExchange: v })} style={inp} />}
                  <label style={s}>Acquired on/before 31-Jan-2018<select value={entry.acquiredBefore31Jan2018 === true ? 'yes' : 'no'} onChange={(e) => update(index, { acquiredBefore31Jan2018: e.target.value === 'yes' })} style={inp}><option value="no">No</option><option value="yes">Yes</option></select></label>
                  {entry.acquiredBefore31Jan2018 === true && <NumberField label="FMV on 31-Jan-2018" value={fmv} onChange={(v) => updateBoth(index, 'fmv31Jan2018', 'fmvJan2018', v)} style={inp} />}
                </div>

                {rowIssues.length > 0 && <ul style={{ margin: '10px 0 0', paddingLeft: 20, color: '#b45309', fontSize: 12 }}>{rowIssues.map((issue, ii) => <li key={`${issue.code || 'i'}-${ii}`}>{issue.message || issue.code || 'Review'}</li>)}</ul>}
              </article>
            );
          })}
        </div>
      )}

      {/* ── PURCHASE REFERENCE ROWS (AIS evidence, not ITR reportable events) ── */}
      {purchaseRefEntries.length > 0 && (
        <details style={{ border: '1px solid #e5e7eb', borderRadius: 8 }}>
          <summary style={{
            padding: '10px 14px', cursor: 'pointer', fontWeight: 600, fontSize: 13,
            color: '#374151', background: '#f9fafb', borderRadius: 8,
            listStyle: 'none', display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          }}>
            <span>
              AIS purchase reference &mdash; {purchaseRefEntries.length} record{purchaseRefEntries.length !== 1 ? 's' : ''},{' '}
              total \u20b9{purchaseRefEntries.reduce((sum, e) => sum + Number(e.actualCost ?? e.purchaseCost ?? 0), 0).toLocaleString('en-IN')}
            </span>
            <span style={{ fontSize: 11, color: '#6b7280', fontWeight: 400 }}>Not reported in ITR &mdash; reference only \u25be</span>
          </summary>
          <div style={{ padding: '10px 14px', display: 'grid', gap: 6 }}>
            <p style={{ fontSize: 12, color: '#6b7280', margin: '0 0 6px' }}>
              These AIS rows show what was <strong>purchased</strong> during the year.
              Per CBDT Schedule 112A (ITR-1/ITR-4), only sales (disposals) are reported as taxable events.
              Use these amounts as the <em>cost of acquisition</em> when completing the disposal entries above.
            </p>
            {purchaseRefEntries.map((entry, idx) => {
              const cost = Number(entry.actualCost ?? entry.purchaseCost ?? 0);
              const desc = String(entry.description ?? entry.assetDescription ?? '');
              const sec = String(entry.section ?? '');
              return (
                <div key={entry.id ?? idx} style={{
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  padding: '8px 10px', background: 'white', border: '1px solid #e5e7eb',
                  borderRadius: 6, fontSize: 12,
                }}>
                  <div>
                    {sec && <span style={{ marginRight: 8, fontSize: 10, color: '#6b7280', background: '#f3f4f6', padding: '1px 4px', borderRadius: 3 }}>{sec}</span>}
                    <span style={{ fontWeight: 500 }}>{desc || 'Unnamed fund'}</span>
                  </div>
                  <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
                    <span style={{ color: '#374151' }}>Cost: <strong>\u20b9{cost.toLocaleString('en-IN')}</strong></span>
                    <button type="button" onClick={() => removeEntry(entry)} style={{ border: 0, background: 'transparent', color: '#dc2626', cursor: 'pointer', fontSize: 11 }}>Remove</button>
                  </div>
                </div>
              );
            })}
          </div>
        </details>
      )}
    </section>
  );
};

function NumberField({ label, value, onChange, style }: { label: string; value: number | undefined; onChange: (value: number | undefined) => void; style: React.CSSProperties }): React.ReactElement {
  return <label style={{ display: 'grid', gap: 4, fontSize: 12, color: '#374151' }}>{label}<input type="number" min="0" step="any" value={value ?? ''} onChange={(e) => onChange(parseNumber(e.target.value))} style={style} /></label>;
}

function BooleanField({ label, value, onChange, style }: { label: string; value: boolean | undefined; onChange: (value: boolean | undefined) => void; style: React.CSSProperties }): React.ReactElement {
  return <label style={{ display: 'grid', gap: 4, fontSize: 12, color: '#374151' }}>{label}<select value={value === true ? 'yes' : value === false ? 'no' : ''} onChange={(e) => onChange(e.target.value === '' ? undefined : e.target.value === 'yes')} style={style}><option value="">Select</option><option value="yes">Yes</option><option value="no">No</option></select></label>;
}
