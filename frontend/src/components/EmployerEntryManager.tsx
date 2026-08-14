import React from 'react';

interface EmployerEntry {
  id: string;
  employerName?: string;
  employerTAN?: string;
  natureOfEmployment?: 'CGOV' | 'SGOV' | 'PSU' | 'PE' | 'PESG' | 'PEPS' | 'PEO' | 'OTH';
  employerAddress?: string;
  employerCity?: string;
  employerStateCode?: string;
  employerPinCode?: string;
  employerZipCode?: string;
  basic?: number;
  da?: number;
  commission?: number;
  hra?: number;
  bonus?: number;
  allowances?: number;
  lta?: number;
  otherAllowance?: number;
  arrearSalary?: number;
  perquisites?: number;
  profitsInLieu?: number;
  rentPaid?: number;
  city?: string;
  isMetroCity?: boolean;
  isDisabledEmployee?: boolean;
  commutedPension?: number;
  gratuity?: number;
  leaveEncashment?: number;
  averageMonthlySalary?: number;
  yearsOfService?: number;
  unavailedLeaveDays?: number;
  actualLtaFare?: number;
  isDomesticTravel?: boolean;
  journeysInBlock?: number;
  numberOfChildren?: number;
  gratuityAlsoReceived?: boolean;
  transportAllowance?: number;
  childrenEducationAllowance?: number;
  hostelExpenditureAllowance?: number;
  uniformAllowance?: number;
  entertainmentAllowance?: number;
  professionalTax?: number;
  vrsCompensation?: number;
  retrenchmentCompensation?: number;
  section10ExemptionRows?: Section10ExemptionRow[];
}

interface Section10ExemptionRow {
  id: string;
  natureCode: string;
  otherDescription: string;
  amount: number;
}

/** A TDS entry from the TDS and Advance Tax tab */
interface TDSEntry {
  id?: string;
  section?: string;
  deductorName?: string;
  deductorTAN?: string;
  incomeAmount?: number;
  tdsDeducted?: number;
  certificateNo?: string;
  deductionDate?: string;
  financialYear?: string;
  verified26AS?: boolean;
  claimedInReturn?: boolean;
}

interface BackendResult {
  grossSalary?: number;
  incomeFromSal?: number;
  hraExempt?: number;
  ltaExempt?: number;
  gratuityExempt?: number;
  leaveEncashmentExempt?: number;
  pensionCommutationExempt?: number;
  transportAllowanceExempt?: number;
  childrenEducationExempt?: number;
  hostelExpenditureExempt?: number;
  uniformAllowanceExempt?: number;
  totalSection10Exempt?: number;
  standardDeduction?: number;
  entertainmentAllowanceDed?: number;
  professionalTaxDed?: number;
  totalSection16Deductions?: number;
  totalTDSDeducted?: number;
}

interface Props {
  entries: EmployerEntry[];
  onChange: (entries: EmployerEntry[]) => void;
  assessmentYear: string;
  taxRegime?: string;
  backendResult?: BackendResult;
  /** Live TDS entries from the TDS and Advance Tax tab -- read-only here */
  tdsEntries?: TDSEntry[];
}

const INPUT_STYLE: React.CSSProperties = {
  width: '100%', boxSizing: 'border-box', padding: '8px 10px',
  border: '1px solid var(--border-strong)', borderRadius: 6, fontSize: 13,
  background: '#fff', color: 'var(--text-primary)',
};
const GRID_STYLE: React.CSSProperties = {
  display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', gap: 14,
};
const CARD_STYLE: React.CSSProperties = {
  background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 10,
  padding: 18, marginBottom: 16, boxShadow: '0 1px 2px rgba(11, 25, 41, 0.04)',
};

const SECTION_10_OTHER_EXEMPTIONS = [
  ['10(6)', 'Foreign diplomatic remuneration'],
  ['10(7)', 'Government service outside India'],
  ['10(10CC)', 'Employer-paid tax on non-monetary perquisite'],
  ['10(14)(i)', 'Official-duty allowance not otherwise entered'],
  ['10(14)(ii)', 'Personal / cost-of-living allowance not otherwise entered'],
  ['10(14)(i)(115BAC)', 'Rule 2BB allowance under new regime'],
  ['10(14)(ii)(115BAC)', 'Disabled-person transport allowance under new regime'],
  ['EIC', "Judges' exempt income"],
  ['10(17)', 'MP / MLA / MLC allowance'],
  ['OTH', 'Other salary-origin section 10 exemption'],
] as const;

function generateId(): string {
  return 'salary-' + Date.now() + '-' + Math.random().toString(36).slice(2, 10);
}

function money(value: number | undefined): number {
  return typeof value === 'number' && Number.isFinite(value) && value > 0 ? value : 0;
}

function formatINR(value: number | undefined): string {
  return Math.round(money(value)).toLocaleString('en-IN');
}

function Field({
  label, required = false, help, children,
}: {
  label: string; required?: boolean; help?: string; children: React.ReactNode;
}): React.JSX.Element {
  return (
    <div>
      <label style={{ display: 'block', marginBottom: 5, fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)' }}>
        {label}
        {required ? <span style={{ color: 'var(--danger)' }}> *</span> : ''}
      </label>
      {children}
      {help && <div style={{ marginTop: 4, color: 'var(--text-muted)', fontSize: 11 }}>{help}</div>}
    </div>
  );
}

function AmountInput({ value, onChange }: { value: number | undefined; onChange: (v: number) => void }): React.JSX.Element {
  return (
    <input
      type="text"
      inputMode="numeric"
      value={value ? String(value) : ''}
      onChange={(e) => onChange(Number(e.target.value.replace(/\D/g, '')) || 0)}
      style={INPUT_STYLE}
    />
  );
}

function TextInput({ value, onChange, maxLength }: { value: string | undefined; onChange: (v: string) => void; maxLength?: number }): React.JSX.Element {
  return (
    <input
      type="text"
      value={value || ''}
      onChange={(e) => onChange(e.target.value)}
      maxLength={maxLength}
      style={INPUT_STYLE}
    />
  );
}

function SectionHeading({ n, title, description }: { n: number; title: string; description?: string }): React.JSX.Element {
  return (
    <div style={{ margin: '24px 0 12px', padding: '10px 12px', borderLeft: '4px solid var(--gold)', borderRadius: '0 6px 6px 0', background: 'var(--gold-pale)' }}>
      <h4 style={{ margin: 0, color: 'var(--navy)', fontSize: 15 }}>{n}. {title}</h4>
      {description && <p style={{ margin: '4px 0 0', color: 'var(--text-secondary)', fontSize: 12 }}>{description}</p>}
    </div>
  );
}

function Section10Rows({ rows, onChange }: { rows: Section10ExemptionRow[]; onChange: (rows: Section10ExemptionRow[]) => void }): React.JSX.Element {
  const addRow = (): void => onChange([...rows, { id: generateId(), natureCode: '10(6)', otherDescription: '', amount: 0 }]);
  const update = (id: string, patch: Partial<Section10ExemptionRow>): void =>
    onChange(rows.map((row) => (row.id === id ? { ...row, ...patch } : row)));

  return (
    <div style={CARD_STYLE}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, marginBottom: 12 }}>
        <div>
          <strong style={{ fontSize: 13, color: 'var(--navy)' }}>Other salary-origin section 10 exemptions</strong>
          <div style={{ color: 'var(--text-secondary)', fontSize: 11, marginTop: 3 }}>
            HRA, LTA, retirement benefits and section 10(14) allowances are entered in their dedicated sections above.
          </div>
        </div>
        <button
          type="button"
          onClick={addRow}
          style={{ border: 0, borderRadius: 5, padding: '7px 10px', color: '#fff', background: 'var(--navy-light)', cursor: 'pointer', fontWeight: 600 }}
        >
          + Add exemption
        </button>
      </div>
      {rows.length === 0 && <div style={{ color: 'var(--text-muted)', fontSize: 12 }}>No other salary-origin section 10 exemptions added.</div>}
      {rows.map((row) => (
        <div
          key={row.id}
          style={{ display: 'grid', gridTemplateColumns: 'minmax(220px, 2fr) minmax(160px, 1.5fr) minmax(120px, 1fr) 34px', gap: 10, alignItems: 'end', marginTop: 10 }}
        >
          <Field label="Exemption" required>
            <select value={row.natureCode} onChange={(e) => update(row.id, { natureCode: e.target.value })} style={INPUT_STYLE}>
              {SECTION_10_OTHER_EXEMPTIONS.map(([code, desc]) => (
                <option key={code} value={code}>{code} -- {desc}</option>
              ))}
            </select>
          </Field>
          <Field label="Description" required={row.natureCode === 'OTH'}>
            {row.natureCode === 'OTH'
              ? <TextInput value={row.otherDescription} onChange={(v) => update(row.id, { otherDescription: v.slice(0, 125) })} maxLength={125} />
              : <input value="" disabled style={{ ...INPUT_STYLE, background: 'var(--bg)' }} />}
          </Field>
          <Field label="Exempt amount" required>
            <AmountInput value={row.amount} onChange={(v) => update(row.id, { amount: v })} />
          </Field>
          <button
            type="button"
            onClick={() => onChange(rows.filter((r) => r.id !== row.id))}
            aria-label="Remove exemption"
            style={{ height: 36, border: '1px solid #fecaca', borderRadius: 5, color: 'var(--danger)', background: 'var(--danger-bg)', cursor: 'pointer' }}
          >
            &#215;
          </button>
        </div>
      ))}
    </div>
  );
}

/** Read-only TDS panel -- matches TDS tab entries by TAN and section 192/192A */
function EmployerTDSPanel({ employerTAN, allTdsEntries }: {
  employerTAN?: string;
  allTdsEntries: TDSEntry[];
}): React.JSX.Element {
  const tan = (employerTAN || '').trim().toUpperCase();
  const salary192 = allTdsEntries.filter((e) => e.section === '192' || e.section === '192A');

  const matched: TDSEntry[] = salary192.length === 0
    ? []
    : tan.length === 10
      ? salary192.filter((e) => (e.deductorTAN || '').trim().toUpperCase() === tan)
      : salary192; // no TAN yet -- show all as a hint

  const claimedTotal = matched
    .filter((e) => e.claimedInReturn !== false)
    .reduce((s, e) => s + money(e.tdsDeducted), 0);

  const bannerBase: React.CSSProperties = {
    padding: '12px 14px', borderRadius: 8,
    background: 'var(--info-bg)', border: '1px solid #bfdbfe',
    fontSize: 12, color: 'var(--info)',
  };

  if (salary192.length === 0) {
    return (
      <div style={bannerBase}>
        <strong>No section 192 TDS entries found.</strong>
        <div style={{ marginTop: 6, color: 'var(--text-secondary)' }}>
          Go to the <strong>TDS &amp; Advance Tax</strong> tab to add salary TDS deducted under section 192.
          Any changes made there will automatically appear here.
        </div>
      </div>
    );
  }

  if (matched.length === 0) {
    return (
      <div style={bannerBase}>
        <strong>No TDS entries matched TAN <span style={{ fontFamily: 'monospace' }}>{tan || '(not entered)'}</span>.</strong>
        <div style={{ marginTop: 6, color: 'var(--text-secondary)' }}>
          Enter this employer&apos;s TAN in the Employer details section above, or add a section 192 entry in the{' '}
          <strong>TDS &amp; Advance Tax</strong> tab using this TAN.
        </div>
      </div>
    );
  }

  return (
    <div style={{ ...CARD_STYLE, padding: 0, overflow: 'hidden' }}>
      <div style={{ padding: '10px 14px', background: 'var(--info-bg)', borderBottom: '1px solid #bfdbfe', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <strong style={{ fontSize: 13, color: 'var(--info)' }}>Section 192 TDS -- read only</strong>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>
            Sourced from the TDS &amp; Advance Tax tab. Edit entries there; changes reflect here automatically.
            {!tan && ' (Showing all section 192 entries -- enter employer TAN to filter to this employer.)'}
          </div>
        </div>
        <div style={{ textAlign: 'right', whiteSpace: 'nowrap', paddingLeft: 12 }}>
          <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 2 }}>TOTAL CLAIMED TDS</div>
          <strong style={{ fontSize: 18, color: 'var(--navy)' }}>&#x20B9;{formatINR(claimedTotal)}</strong>
        </div>
      </div>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, minWidth: 640 }}>
          <thead>
            <tr style={{ background: 'var(--bg)' }}>
              {['Deductor name', 'TAN', 'Cert. No.', 'Income (Rs)', 'TDS (Rs)', 'Date', 'Verified', 'Claimed'].map((h) => (
                <th key={h} style={{ padding: '7px 10px', textAlign: 'left', fontWeight: 600, color: 'var(--text-muted)', borderBottom: '1px solid var(--border)', whiteSpace: 'nowrap' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {matched.map((e, i) => (
              <tr key={e.id || i} style={{ borderBottom: '1px solid var(--border)' }}>
                <td style={{ padding: '7px 10px', color: 'var(--text-primary)' }}>{e.deductorName || <span style={{ color: 'var(--text-muted)' }}>--</span>}</td>
                <td style={{ padding: '7px 10px', fontFamily: 'monospace', color: 'var(--text-secondary)', fontSize: 11 }}>{e.deductorTAN || '--'}</td>
                <td style={{ padding: '7px 10px', color: 'var(--text-secondary)' }}>{e.certificateNo || '--'}</td>
                <td style={{ padding: '7px 10px', textAlign: 'right', color: 'var(--text-primary)' }}>&#x20B9;{formatINR(e.incomeAmount)}</td>
                <td style={{ padding: '7px 10px', textAlign: 'right', fontWeight: 700, color: 'var(--navy)' }}>&#x20B9;{formatINR(e.tdsDeducted)}</td>
                <td style={{ padding: '7px 10px', color: 'var(--text-muted)', fontSize: 11 }}>{e.deductionDate || '--'}</td>
                <td style={{ padding: '7px 10px', textAlign: 'center' }}>{e.verified26AS ? '✓' : '--'}</td>
                <td style={{ padding: '7px 10px', textAlign: 'center' }}>
                  <span style={{
                    display: 'inline-block', padding: '2px 7px', borderRadius: 10, fontSize: 11, fontWeight: 600,
                    background: e.claimedInReturn !== false ? 'var(--success-bg)' : 'var(--bg)',
                    color: e.claimedInReturn !== false ? 'var(--success)' : 'var(--text-muted)',
                  }}>
                    {e.claimedInReturn !== false ? 'Yes' : 'No'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function EmployerForm({
  entry, onChange, onRemove, taxRegime, allTdsEntries,
}: {
  entry: EmployerEntry;
  onChange: (patch: Partial<EmployerEntry>) => void;
  onRemove: () => void;
  taxRegime: string;
  allTdsEntries: TDSEntry[];
}): React.JSX.Element {
  const hraClaimed = money(entry.hra) > 0;
  const ltaClaimed = money(entry.lta) > 0;
  const retirementReceived =
    money(entry.commutedPension) > 0 || money(entry.gratuity) > 0 ||
    money(entry.leaveEncashment) > 0 || money(entry.vrsCompensation) > 0 ||
    money(entry.retrenchmentCompensation) > 0;
  const section10Rows = entry.section10ExemptionRows || [];

  const gross =
    money(entry.basic) + money(entry.da) + money(entry.hra) + money(entry.lta) +
    money(entry.bonus) + money(entry.commission) + money(entry.allowances) +
    money(entry.otherAllowance) + money(entry.arrearSalary) + money(entry.perquisites) +
    money(entry.profitsInLieu) + money(entry.commutedPension) + money(entry.gratuity) +
    money(entry.leaveEncashment) + money(entry.vrsCompensation) + money(entry.retrenchmentCompensation);

  // Sequential section numbers -- only visible sections get a number
  let seq = 0;
  const next = (): number => { seq += 1; return seq; };
  const nDetails = next();
  const nSalary = next();
  const nHRA = hraClaimed ? next() : 0;
  const nLTA = ltaClaimed ? next() : 0;
  const nAllowances = next();
  const nRetirement = retirementReceived ? next() : 0;
  const nOtherExempt = next();
  const nSection16 = next();
  const nTDS = next();

  return (
    <div style={{ ...CARD_STYLE, padding: 20, marginBottom: 22, borderTop: '3px solid var(--gold)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '4px 0 14px', borderBottom: '1px solid var(--border)' }}>
        <div>
          <h3 style={{ margin: 0, fontSize: 17, color: 'var(--navy)' }}>{entry.employerName?.trim() || 'Employer'}</h3>
          <div style={{ marginTop: 3, fontSize: 12, color: 'var(--text-secondary)' }}>One continuous Schedule S entry. Each fact appears once only.</div>
        </div>
        <button
          type="button"
          onClick={onRemove}
          aria-label={'Remove ' + (entry.employerName?.trim() || 'employer')}
          style={{ border: '1px solid #fecaca', borderRadius: 5, padding: '7px 10px', background: 'var(--danger-bg)', color: 'var(--danger)', cursor: 'pointer' }}
        >
          Remove
        </button>
      </div>

      <SectionHeading n={nDetails} title="Employer details" description="Required employer identity and address for this salary source." />
      <div style={GRID_STYLE}>
        <Field label="Employer Name" required>
          <TextInput value={entry.employerName} onChange={(v) => onChange({ employerName: v.slice(0, 125) })} maxLength={125} />
        </Field>
        <Field label="Nature of Employment" required>
          <select value={entry.natureOfEmployment || 'OTH'} onChange={(e) => onChange({ natureOfEmployment: e.target.value as EmployerEntry['natureOfEmployment'] })} style={INPUT_STYLE}>
            <option value="CGOV">Central Government</option>
            <option value="SGOV">State Government</option>
            <option value="PSU">Public Sector Unit</option>
            <option value="PE">Pensioner -- Central Government</option>
            <option value="PESG">Pensioner -- State Government</option>
            <option value="PEPS">Pensioner -- PSU</option>
            <option value="PEO">Pensioner -- Others</option>
            <option value="OTH">Others</option>
          </select>
        </Field>
        <Field label="Employer TAN" help="Optional when unavailable; format ABCD12345E.">
          <TextInput value={entry.employerTAN} onChange={(v) => onChange({ employerTAN: v.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 10) })} maxLength={10} />
        </Field>
        <Field label="Employer Address" required>
          <TextInput value={entry.employerAddress} onChange={(v) => onChange({ employerAddress: v.slice(0, 200) })} maxLength={200} />
        </Field>
        <Field label="Employer City / District" required>
          <TextInput value={entry.employerCity} onChange={(v) => onChange({ employerCity: v.slice(0, 50) })} maxLength={50} />
        </Field>
        <Field label="Employer State Code" required>
          <TextInput value={entry.employerStateCode} onChange={(v) => onChange({ employerStateCode: v.replace(/\D/g, '').slice(0, 2) })} maxLength={2} />
        </Field>
        <Field label="Employer PIN Code">
          <TextInput value={entry.employerPinCode} onChange={(v) => onChange({ employerPinCode: v.replace(/\D/g, '').slice(0, 6) })} maxLength={6} />
        </Field>
        <Field label="Employer Foreign ZIP">
          <TextInput value={entry.employerZipCode} onChange={(v) => onChange({ employerZipCode: v.slice(0, 8) })} maxLength={8} />
        </Field>
      </div>

      <SectionHeading n={nSalary} title="Taxable salary received" description="Enter each salary amount once. HRA, LTA and retirement amounts reveal evidence fields below when non-zero." />
      <div style={GRID_STYLE}>
        <Field label="Basic Salary"><AmountInput value={entry.basic} onChange={(v) => onChange({ basic: v })} /></Field>
        <Field label="Dearness Allowance"><AmountInput value={entry.da} onChange={(v) => onChange({ da: v })} /></Field>
        <Field label="HRA Received"><AmountInput value={entry.hra} onChange={(v) => onChange({ hra: v })} /></Field>
        <Field label="LTA / LTC Received"><AmountInput value={entry.lta} onChange={(v) => onChange({ lta: v })} /></Field>
        <Field label="Bonus / Performance Pay"><AmountInput value={entry.bonus} onChange={(v) => onChange({ bonus: v })} /></Field>
        <Field label="Commission / Fees"><AmountInput value={entry.commission} onChange={(v) => onChange({ commission: v })} /></Field>
        <Field label="Other Taxable Allowances"><AmountInput value={entry.allowances} onChange={(v) => onChange({ allowances: v })} /></Field>
        <Field label="Other Taxable Salary"><AmountInput value={entry.otherAllowance} onChange={(v) => onChange({ otherAllowance: v })} /></Field>
        <Field label="Arrears / Advance Salary"><AmountInput value={entry.arrearSalary} onChange={(v) => onChange({ arrearSalary: v })} /></Field>
        <Field label="Taxable Perquisites -- Section 17(2)"><AmountInput value={entry.perquisites} onChange={(v) => onChange({ perquisites: v })} /></Field>
        <Field label="Profits in Lieu -- Section 17(3)"><AmountInput value={entry.profitsInLieu} onChange={(v) => onChange({ profitsInLieu: v })} /></Field>
      </div>

      {hraClaimed && (
        <>
          <SectionHeading n={nHRA} title="HRA claim -- Section 10(13A)" description="Required because HRA received is greater than zero." />
          <div style={GRID_STYLE}>
            <Field label="Annual Rent Paid" required><AmountInput value={entry.rentPaid} onChange={(v) => onChange({ rentPaid: v })} /></Field>
            <Field label="City of Employment" required><TextInput value={entry.city} onChange={(v) => onChange({ city: v.slice(0, 50) })} maxLength={50} /></Field>
            <Field label="Place of Work" required>
              <select value={entry.isMetroCity ? 'METRO' : 'NON_METRO'} onChange={(e) => onChange({ isMetroCity: e.target.value === 'METRO' })} style={INPUT_STYLE}>
                <option value="NON_METRO">Non-metro (40%)</option>
                <option value="METRO">Metro (50%)</option>
              </select>
            </Field>
          </div>
        </>
      )}

      {ltaClaimed && (
        <>
          <SectionHeading n={nLTA} title="LTA / LTC claim -- Section 10(5)" description="Required because LTA/LTC received is greater than zero." />
          <div style={GRID_STYLE}>
            <Field label="Actual Eligible Fare" required><AmountInput value={entry.actualLtaFare} onChange={(v) => onChange({ actualLtaFare: v })} /></Field>
            <Field label="Journeys Used in Current Block" required><AmountInput value={entry.journeysInBlock} onChange={(v) => onChange({ journeysInBlock: v })} /></Field>
            <Field label="Domestic Travel Only" required>
              <select value={entry.isDomesticTravel === false ? 'N' : 'Y'} onChange={(e) => onChange({ isDomesticTravel: e.target.value === 'Y' })} style={INPUT_STYLE}>
                <option value="Y">Yes</option>
                <option value="N">No</option>
              </select>
            </Field>
          </div>
        </>
      )}

      <SectionHeading n={nAllowances} title="Section 10(14) allowances" description="Enter only allowances received from this employer. Do not repeat these in the Other Section 10 table." />
      <div style={GRID_STYLE}>
        <Field label="Transport Allowance"><AmountInput value={entry.transportAllowance} onChange={(v) => onChange({ transportAllowance: v })} /></Field>
        <Field label="Children Education Allowance"><AmountInput value={entry.childrenEducationAllowance} onChange={(v) => onChange({ childrenEducationAllowance: v })} /></Field>
        <Field label="Hostel Expenditure Allowance"><AmountInput value={entry.hostelExpenditureAllowance} onChange={(v) => onChange({ hostelExpenditureAllowance: v })} /></Field>
        <Field label="Uniform Allowance"><AmountInput value={entry.uniformAllowance} onChange={(v) => onChange({ uniformAllowance: v })} /></Field>
        <Field label="Eligible Children Count" help="Maximum two children for CEA / hostel allowance.">
          <AmountInput value={entry.numberOfChildren} onChange={(v) => onChange({ numberOfChildren: v })} />
        </Field>
        <Field label="Employee with disability?" help="Relevant for permitted transport allowance.">
          <select value={entry.isDisabledEmployee ? 'Y' : 'N'} onChange={(e) => onChange({ isDisabledEmployee: e.target.value === 'Y' })} style={INPUT_STYLE}>
            <option value="N">No</option>
            <option value="Y">Yes</option>
          </select>
        </Field>
      </div>

      {retirementReceived && (
        <>
          <SectionHeading n={nRetirement} title="Retirement / termination receipts" description="Provide supporting facts for receipts entered above. Exemption is calculated under the applicable section." />
          <div style={GRID_STYLE}>
            <Field label="Commuted Pension"><AmountInput value={entry.commutedPension} onChange={(v) => onChange({ commutedPension: v })} /></Field>
            <Field label="Gratuity"><AmountInput value={entry.gratuity} onChange={(v) => onChange({ gratuity: v })} /></Field>
            <Field label="Leave Encashment"><AmountInput value={entry.leaveEncashment} onChange={(v) => onChange({ leaveEncashment: v })} /></Field>
            <Field label="VRS Compensation"><AmountInput value={entry.vrsCompensation} onChange={(v) => onChange({ vrsCompensation: v })} /></Field>
            <Field label="Retrenchment Compensation"><AmountInput value={entry.retrenchmentCompensation} onChange={(v) => onChange({ retrenchmentCompensation: v })} /></Field>
            <Field label="Average Monthly Salary"><AmountInput value={entry.averageMonthlySalary} onChange={(v) => onChange({ averageMonthlySalary: v })} /></Field>
            <Field label="Years of Service"><AmountInput value={entry.yearsOfService} onChange={(v) => onChange({ yearsOfService: v })} /></Field>
            <Field label="Unavailed Leave Days"><AmountInput value={entry.unavailedLeaveDays} onChange={(v) => onChange({ unavailedLeaveDays: v })} /></Field>
            {money(entry.commutedPension) > 0 && (
              <Field label="Was gratuity also received?" required>
                <select value={entry.gratuityAlsoReceived ? 'Y' : 'N'} onChange={(e) => onChange({ gratuityAlsoReceived: e.target.value === 'Y' })} style={INPUT_STYLE}>
                  <option value="N">No</option>
                  <option value="Y">Yes</option>
                </select>
              </Field>
            )}
          </div>
        </>
      )}

      <SectionHeading n={nOtherExempt} title="Other salary-origin section 10 exemptions" description="Use only for exemptions not covered by the dedicated sections above (not HRA, LTA, retirement, or 10(14))." />
      <Section10Rows rows={section10Rows} onChange={(rows) => onChange({ section10ExemptionRows: rows })} />

      <SectionHeading n={nSection16} title="Salary deductions -- Section 16" description="These reduce salary income directly and are not Chapter VI-A deductions." />
      <div style={GRID_STYLE}>
        <Field label="Entertainment Allowance -- Section 16(ii)" help="Government employees only; capped by law.">
          <AmountInput value={entry.entertainmentAllowance} onChange={(v) => onChange({ entertainmentAllowance: v })} />
        </Field>
        <Field label="Professional Tax -- Section 16(iii)" help="Salary deduction; capped at Rs 2,500.">
          <AmountInput value={entry.professionalTax} onChange={(v) => onChange({ professionalTax: v })} />
        </Field>
      </div>
      <div style={{ marginTop: 12, padding: 11, borderRadius: 6, color: 'var(--info)', background: 'var(--info-bg)', fontSize: 12 }}>
        Employer NPS under section 80CCD(2) belongs in the Deductions tab. Non-salary exempt income belongs in the Exempt Income tab.
      </div>

      <SectionHeading
        n={nTDS}
        title="Salary TDS deducted -- Section 192 (view only)"
        description="Pulled from the TDS & Advance Tax tab, matched by employer TAN. Go to that tab to add or edit entries -- changes appear here immediately."
      />
      <EmployerTDSPanel employerTAN={entry.employerTAN} allTdsEntries={allTdsEntries} />

      <div style={{ marginTop: 16, padding: 12, borderRadius: 6, background: 'var(--gold-pale)', border: '1px solid var(--gold-light)', fontSize: 12, color: '#7c530e' }}>
        Locally entered gross salary for this employer: <strong>&#x20B9;{formatINR(gross)}</strong>.
        Final exemptions and net taxable salary are calculated by the tax engine after computation.
      </div>
    </div>
  );
}

export function EmployerEntryManager({
  entries = [], onChange, assessmentYear, taxRegime = 'OLD', backendResult, tdsEntries = [],
}: Props): React.JSX.Element {
  const addEmployer = (): void =>
    onChange([...entries, { id: generateId(), natureOfEmployment: 'OTH', isDomesticTravel: true }]);

  const updateEmployer = (id: string, patch: Partial<EmployerEntry>): void =>
    onChange(entries.map((e) => (e.id === id ? { ...e, ...patch } : e)));

  const hasBackendResult = backendResult !== null && backendResult !== undefined;
  const finalGross = money(backendResult?.grossSalary);
  const finalExemptions = money(backendResult?.totalSection10Exempt) + money(backendResult?.totalSection16Deductions);

  const totalSalaryTDS = tdsEntries
    .filter((e) => (e.section === '192' || e.section === '192A') && e.claimedInReturn !== false)
    .reduce((s, e) => s + money(e.tdsDeducted), 0);

  return (
    <div style={{ marginBottom: 24 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, marginBottom: 16 }}>
        <div>
          <h3 style={{ margin: 0, fontSize: 17, color: 'var(--navy)' }}>Salary Income -- Schedule S</h3>
          <p style={{ margin: '4px 0 0', color: 'var(--text-secondary)', fontSize: 12 }}>
            Assessment Year {assessmentYear} &middot; {taxRegime} regime.
            Add one continuous entry for each employer or pension source.
          </p>
        </div>
        <button
          type="button"
          onClick={addEmployer}
          style={{ padding: '9px 14px', background: 'var(--gold)', color: '#fff', border: 0, borderRadius: 6, cursor: 'pointer', fontWeight: 600, fontSize: 13 }}
        >
          + Add employer
        </button>
      </div>

      {entries.length === 0 && (
        <div style={{ ...CARD_STYLE, textAlign: 'center', padding: 40, color: 'var(--text-muted)', borderStyle: 'dashed' }}>
          No salary source added yet. Click <strong style={{ color: 'var(--gold)' }}>+ Add employer</strong> to begin Schedule S.
        </div>
      )}

      {entries.map((entry) => (
        <EmployerForm
          key={entry.id}
          entry={entry}
          onChange={(patch) => updateEmployer(entry.id, patch)}
          onRemove={() => onChange(entries.filter((e) => e.id !== entry.id))}
          taxRegime={taxRegime}
          allTdsEntries={tdsEntries}
        />
      ))}

      {entries.length > 0 && (
        <div style={{ background: 'linear-gradient(135deg, var(--navy), var(--navy-light))', borderRadius: 10, padding: 20, color: '#fff' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <h4 style={{ margin: 0, fontSize: 14, color: 'var(--gold-light)' }}>Schedule S -- Salary Summary</h4>
            <span style={{ fontSize: 11, padding: '2px 8px', background: hasBackendResult ? 'var(--success)' : '#4a5568', borderRadius: 4, color: '#fff' }}>
              {hasBackendResult ? 'Live' : 'Awaiting computation'}
            </span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 16 }}>
            <div>
              <div style={{ opacity: 0.7, fontSize: 11, marginBottom: 4 }}>GROSS SALARY</div>
              <strong style={{ fontSize: 22 }}>{hasBackendResult ? `₹${formatINR(finalGross)}` : '—'}</strong>
            </div>
            <div>
              <div style={{ opacity: 0.7, fontSize: 11, marginBottom: 4 }}>SECTION 10 + 16</div>
              <strong style={{ fontSize: 22, color: '#86efac' }}>{hasBackendResult ? `₹${formatINR(finalExemptions)}` : '—'}</strong>
            </div>
            <div>
              <div style={{ opacity: 0.7, fontSize: 11, marginBottom: 4 }}>NET TAXABLE SALARY</div>
              <strong style={{ fontSize: 22, color: 'var(--gold-light)' }}>{hasBackendResult ? `₹${formatINR(money(backendResult?.incomeFromSal))}` : '—'}</strong>
            </div>
          </div>
          <div style={{ marginTop: 14, opacity: 0.65, fontSize: 11 }}>
            {hasBackendResult
              ? 'Values are from the tax engine computation.'
              : 'Run computation to view the tax-engine result.'}
          </div>
        </div>
      )}
    </div>
  );
}
