import React from 'react';
import { ITD_COUNTRY_CODES } from '../constants/itdCountryCodes';
import type { HomeLoan, HouseProperty, TenantDetail } from '../domain/returns/types';
import { STATE_CODE_OPTIONS, type StateCode } from '../domain/returns/cbdtEnums';
const MONEY_MAX = 99999999999999;
const PAN_PATTERN = '[A-Z]{5}[0-9]{4}[A-Z]';
const PAN_TAN_PATTERN = '(?:[A-Z]{5}[0-9]{4}[A-Z]|[A-Z]{4}[0-9]{5}[A-Z])';
const inputStyle: React.CSSProperties = { width: '100%', padding: '8px 10px', border: '1px solid var(--border)', borderRadius: 6, fontSize: 13, background: '#fff', color: 'var(--text-primary)' };
const gridStyle: React.CSSProperties = { display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 12, marginBottom: 16 };
const labelStyle: React.CSSProperties = { display: 'block', marginBottom: 5, fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)' };

interface TaxSummary { hpIncome?: number; totalIncChargeHP?: number; }
interface Props { entries: HouseProperty[]; passThroughIncome: number; onChange: (entries: HouseProperty[], passThroughIncome: number) => void; itrForm: string; taxResult?: TaxSummary | null; }
interface FieldProps extends React.InputHTMLAttributes<HTMLInputElement> { label: string; value: string | number; onValue: (value: string | number) => void; }

/** Captures CBDT Schedule HP details while displaying only backend-computed tax results. */
export function HousePropertyEntryManager({ entries, passThroughIncome, onChange, itrForm, taxResult }: Props): React.ReactElement {
  const normalizedForm = itrForm.replace('-', '').toUpperCase();
  const maxProperties = normalizedForm === 'ITR1' ? 2 : normalizedForm === 'ITR4' ? 1 : Number.POSITIVE_INFINITY;
  const addressMax = maxProperties === 2 ? 50 : 200;
  const isItr2 = normalizedForm === 'ITR2';
  const supportsPassThrough = isItr2 || normalizedForm === 'ITR3';

  const commit = (next: HouseProperty[]): void => onChange(next, passThroughIncome);
  const patch = (index: number, values: Partial<HouseProperty>): void => commit(entries.map((entry, i) => i === index ? { ...entry, ...values } : entry));
  const patchNested = <T extends 'coOwners' | 'tenantDetails' | 'homeLoans'>(propertyIndex: number, key: T, rowIndex: number, values: Partial<HouseProperty[T][number]>): void => {
    const entry = entries[propertyIndex];
    const rows = entry[key].map((row, index) => index === rowIndex ? { ...row, ...values } : row) as HouseProperty[T];
    patch(propertyIndex, { [key]: rows } as Pick<HouseProperty, T>);
  };
  const removeNested = (propertyIndex: number, key: 'coOwners' | 'tenantDetails' | 'homeLoans', rowIndex: number): void => patch(propertyIndex, { [key]: entries[propertyIndex][key].filter((_, index) => index !== rowIndex) });

  const addProperty = (): void => {
    if (entries.length >= maxProperties) return;
    const property: HouseProperty = { id: `hp_${Date.now()}`, name: '', propertySequenceNo: entries.length + 1, propertyType: 'SELF_OCCUPIED',
      address: '', premisesName: '', roadOrStreet: '', area: '', city: '', state: '', pinCode: '', zipCode: '', countryCode: '91', propertyIdentificationNo: '',
      propertyOwnerType: 'SE', propertyOwnerOther: '', ownershipType: 'SOLE', ownershipShare: 100, isCoOwned: false, isPropertyInJointOwnership: false, coOwners: [],
      annualRent: 0, municipalRateableValue: 0, fairRentValue: 0, standardRent: 0, annualLettingValue: 0, unrealizedRent: 0, arrearsOfRent: 0,
      vacancyPeriodMonths: 0, municipalTaxesPaid: 0, interestOnLoan: 0, preConstructionInterest: 0, lenderName: '', lenderPAN: '', lenderType: 'B',
      loanAccountNo: '', loanSanctionDate: '', constructionCompletionDate: '', principalRepayment: 0, totalLoanAmount: 0, loanOutstandingAmount: 0,
      completedWithin5Years: false, homeLoans: [], tenantDetails: [], tenantName: '', tenantPAN: '', tenantAadhaar: '', passThroughIncome: 0,
      grossAnnualValue: 0, netAnnualValue: 0, standardDeduction30Pct: 0, incomeFromHP: 0, maxRent: 0, preConstructionInterestClaimed: 0 };
    commit([...entries, property]);
  };

  const updatePassThroughIncome = (value: number): void => onChange(entries, value);
  const hasBackendResult = taxResult !== null && taxResult !== undefined;
  const totalIncome = Number(taxResult?.totalIncChargeHP ?? taxResult?.hpIncome ?? 0);
  return <div style={{ marginBottom: 24 }}>
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}><h3 style={{ fontSize: 14, color: 'var(--text-secondary)' }}>House Property Entries ({entries.length}/{Number.isFinite(maxProperties) ? maxProperties : '∞'})</h3><button type="button" onClick={addProperty} disabled={entries.length >= maxProperties} style={{ padding: '6px 12px', background: 'var(--gold)', color: '#fff', border: 0, borderRadius: 6 }}>+ Add Property</button></div>
    {entries.length === 0 && <div style={{ padding: 24, textAlign: 'center', background: 'var(--bg)', color: 'var(--text-muted)' }}>No house property entries.</div>}
    {entries.map((entry, index) => {
      return <div key={entry.id} style={{ padding: 16, marginBottom: 24, background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 6 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 14 }}><strong style={{ fontSize: 13 }}>House Property — HPSNo {entry.propertySequenceNo}</strong><button type="button" onClick={() => commit(entries.filter((_, i) => i !== index))} style={{ background: 'var(--danger)', color: '#fff', border: 0, borderRadius: 4, padding: '4px 8px' }}>Remove</button></div>
        <Section title="Property details"><div style={gridStyle}>
          <NumberReadout label="House Property Serial Number (HPSNo) *" value={entry.propertySequenceNo} />
          <Select label="Property type *" value={entry.propertyType} required onChange={(value) => patch(index, { propertyType: value as HouseProperty['propertyType'] })} options={[['SELF_OCCUPIED','Self occupied'],['LET_OUT','Let out'],['DEEMED_LET_OUT','Deemed let out']]} />
          <Field label="Address *" type="text" value={entry.address} required maxLength={addressMax} onValue={(value) => patch(index, { address: String(value) })} />
          <Field label="City / Town / District *" type="text" value={entry.city} required maxLength={50} onValue={(value) => patch(index, { city: String(value) })} />
          <Select label="State code *" value={entry.state} required onChange={(value) => patch(index, { state: value as StateCode | '', pinCode: value === '99' ? '' : entry.pinCode, zipCode: value === '99' ? entry.zipCode : '' })} options={[["", "Select state"], ...STATE_CODE_OPTIONS.map(({ code, label }) => [code, `${code} — ${label}`] as [string,string])]} />
          <Select label="Country code *" value={entry.countryCode} required onChange={(value) => patch(index, { countryCode: value, state: value === '91' ? (entry.state === '99' ? '' : entry.state) : '99', pinCode: value === '91' ? entry.pinCode : '', zipCode: value === '91' ? '' : entry.zipCode })} options={[['','Select'], ...ITD_COUNTRY_CODES.map((country) => [country.value, `${country.value} — ${country.label}`] as [string,string])]} />
          {entry.state === '99' ? <Field label="ZIP / Postal code *" type="text" value={entry.zipCode} required maxLength={8} onValue={(value) => patch(index, { zipCode: String(value) })} /> : <Field label="PIN code *" type="text" value={entry.pinCode} required inputMode="numeric" pattern="[1-9][0-9]{5}" maxLength={6} onValue={(value) => patch(index, { pinCode: String(value) })} />}
        </div></Section>
        <Section title="Ownership"><div style={gridStyle}>
          <Select label="Property owner type *" value={entry.propertyOwnerType} required onChange={(value) => patch(index, { propertyOwnerType: value as HouseProperty['propertyOwnerType'], propertyOwnerOther: value === 'OT' ? entry.propertyOwnerOther : '' })} options={[['SE','Self'],['MI','Minor'],['SP','Self and spouse'],['OT','Other']]} />
          {entry.propertyOwnerType === 'OT' && <Field label="Other owner description *" type="text" value={entry.propertyOwnerOther} required maxLength={50} onValue={(value) => patch(index, { propertyOwnerOther: String(value) })} />}
          <Select label="Is property co-owned? *" value={entry.isCoOwned ? 'Y' : 'N'} required onChange={(value) => patch(index, { isCoOwned: value === 'Y', ownershipType: value === 'Y' ? 'JOINT' : 'SOLE', isPropertyInJointOwnership: value === 'Y', ownershipShare: value === 'Y' ? entry.ownershipShare : 100, coOwners: value === 'Y' ? entry.coOwners : [] })} options={[['N','No'],['Y','Yes']]} />
          {(isItr2 || entry.isCoOwned) && <Field label={`Your ownership share %${isItr2 ? " *" : ""}`} value={entry.ownershipShare} required={isItr2} readOnly={!entry.isCoOwned} min={0} max={100} step="0.01" onValue={(value) => patch(index, { ownershipShare: Number(value) })} />}
        </div>
        {entry.isCoOwned && <Rows title="Co-owner details" add={() => patch(index, { coOwners: [...entry.coOwners, { coOwnerSNo: entry.coOwners.length + 1, name: '', pan: '', aadhaar: '', share: 0 }] })}>{entry.coOwners.map((owner, row) => <div key={row} style={gridStyle}><Field label={`Serial ${row + 1} — Name *`} type="text" value={owner.name} required maxLength={125} onValue={(value) => patchNested(index, 'coOwners', row, { name: String(value) })} /><Field label="PAN" type="text" value={owner.pan} pattern={PAN_PATTERN} maxLength={10} onValue={(value) => patchNested(index, 'coOwners', row, { pan: String(value).toUpperCase() })} /><Field label="Aadhaar" type="text" value={owner.aadhaar} inputMode="numeric" pattern="[0-9]{12}" maxLength={12} onValue={(value) => patchNested(index, 'coOwners', row, { aadhaar: String(value) })} /><Field label="Share %" value={owner.share} min={0} max={100} step="0.01" onValue={(value) => patchNested(index, 'coOwners', row, { share: Number(value) })} /><Remove onClick={() => removeNested(index, 'coOwners', row)} /></div>)}</Rows>}
        </Section>
        {(isItr2 || entry.propertyType !== 'SELF_OCCUPIED') && <Section title="Rent details"><div style={gridStyle}>
          <Money label="Annual Lettable Value *" required value={entry.annualLettingValue} onValue={(value) => patch(index, { annualLettingValue: Number(value) })} />
          <Money label="Rent not realized" value={entry.unrealizedRent} onValue={(value) => patch(index, { unrealizedRent: Number(value) })} />
          <Money label="Local taxes" value={entry.municipalTaxesPaid} onValue={(value) => patch(index, { municipalTaxesPaid: Number(value) })} />
          <Money label="Arrears / unrealized rent received" value={entry.arrearsOfRent} onValue={(value) => patch(index, { arrearsOfRent: Number(value) })} />
        </div></Section>}
        <Rows title="Tenant details (optional)" add={() => patch(index, { tenantDetails: [...entry.tenantDetails, { tenantSNo: entry.tenantDetails.length + 1, name: '', pan: '', aadhaar: '', panOrTan: '' }] })}>{entry.tenantDetails.map((tenant: TenantDetail, row) => <div key={row} style={gridStyle}><Field label={`Serial ${row + 1} — Name *`} type="text" value={tenant.name} required maxLength={125} onValue={(value) => patchNested(index, 'tenantDetails', row, { name: String(value) })} /><Field label="PAN" type="text" value={tenant.pan} pattern={PAN_PATTERN} maxLength={10} onValue={(value) => patchNested(index, 'tenantDetails', row, { pan: String(value).toUpperCase() })} /><Field label="Aadhaar" type="text" value={tenant.aadhaar} pattern="[0-9]{12}" inputMode="numeric" maxLength={12} onValue={(value) => patchNested(index, 'tenantDetails', row, { aadhaar: String(value) })} /><Field label="PAN / TAN" type="text" value={tenant.panOrTan} pattern={PAN_TAN_PATTERN} maxLength={10} onValue={(value) => patchNested(index, 'tenantDetails', row, { panOrTan: String(value).toUpperCase() })} /><Remove onClick={() => removeNested(index, 'tenantDetails', row)} /></div>)}</Rows>
        <Section title="Section 24(b) home loans"><Rows title="Loan details" add={() => patch(index, { homeLoans: [...entry.homeLoans, { lenderType: 'B', lenderName: '', lenderPAN: '', loanAccountNo: '', dateOfLoan: '', totalLoanAmount: 0, loanOutstandingAmount: 0, interestUs24B: 0, constructionCompletionDate: '', completedWithin5Years: false, preConstructionInterest: 0 }] })}>{entry.homeLoans.map((loan: HomeLoan, row) => <div key={row} style={gridStyle}><Select label="Lender source *" value={loan.lenderType} required onChange={(value) => patchNested(index, 'homeLoans', row, { lenderType: value as HomeLoan['lenderType'] })} options={[['B','Bank'],['I','Institution']]} /><Field label="Lender name *" type="text" value={loan.lenderName} required maxLength={125} onValue={(value) => patchNested(index, 'homeLoans', row, { lenderName: String(value) })} /><Field label="Account / reference *" type="text" value={loan.loanAccountNo} required maxLength={20} pattern="[A-Za-z0-9 /-]+" onValue={(value) => patchNested(index, 'homeLoans', row, { loanAccountNo: String(value) })} /><Field label="Date of loan *" type="date" value={loan.dateOfLoan} required onValue={(value) => patchNested(index, 'homeLoans', row, { dateOfLoan: String(value) })} /><Money label="Total loan amount *" required value={loan.totalLoanAmount} onValue={(value) => patchNested(index, 'homeLoans', row, { totalLoanAmount: Number(value) })} /><Money label="Outstanding amount *" required value={loan.loanOutstandingAmount} onValue={(value) => patchNested(index, 'homeLoans', row, { loanOutstandingAmount: Number(value) })} /><Money label="Interest u/s 24(b) *" required value={loan.interestUs24B} onValue={(value) => patchNested(index, 'homeLoans', row, { interestUs24B: Number(value) })} /><Remove onClick={() => removeNested(index, 'homeLoans', row)} /></div>)}</Rows></Section>
        <Section title="Computed Schedule HP result"><div style={gridStyle}><Readout label="Income chargeable under house property (tax engine)" value={hasBackendResult ? totalIncome : null} /></div><p style={{ margin: '0 0 16px', fontSize: 11, color: 'var(--text-muted)' }}>{hasBackendResult ? 'The tax engine computes this amount across all house-property entries.' : 'Run computation to view the tax-engine result.'}</p></Section>
      </div>;
    })}
    {supportsPassThrough && <Section title="Schedule HP pass-through income"><div style={gridStyle}><Field label="Pass-through income" value={passThroughIncome} type="number" min={isItr2 ? -MONEY_MAX : undefined} max={MONEY_MAX} step="1" onValue={(value) => updatePassThroughIncome(Number(value))} /></div></Section>}
    <div style={{ padding: 16, background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 6, display: 'flex', justifyContent: 'space-between' }}><strong>Total Income Chargeable under House Property *</strong><strong>{hasBackendResult ? `₹${totalIncome.toLocaleString('en-IN')}` : '—'}</strong></div>
  </div>;
}

function Section({ title, children }: { title: string; children: React.ReactNode }): React.ReactElement { return <section><h4 style={{ fontSize: 13, color: 'var(--text-secondary)', margin: '20px 0 12px' }}>{title}</h4>{children}</section>; }
function Rows({ title, add, children }: { title: string; add: () => void; children: React.ReactNode }): React.ReactElement { return <div style={{ padding: 12, border: '1px solid var(--border)', borderRadius: 6, marginBottom: 16 }}><div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}><strong style={{ fontSize: 12 }}>{title}</strong><button type="button" onClick={add} style={{ background: 'var(--gold)', color: '#fff', border: 0, borderRadius: 5, padding: '5px 9px' }}>+ Add</button></div>{children}</div>; }
function Field({ label, value, onValue, type = 'number', ...props }: FieldProps): React.ReactElement { return <div><label style={labelStyle}>{label}</label><input {...props} type={type} value={value ?? ''} onChange={(event) => onValue(type === 'number' ? Number(event.target.value) : event.target.value)} style={inputStyle} /></div>; }
function Money(props: Omit<FieldProps, 'type'>): React.ReactElement { return <Field {...props} type="number" min={0} max={MONEY_MAX} step="1" inputMode="numeric" />; }
function Select({ label, value, options, onChange, required }: { label: string; value: string; options: Array<[string,string]>; onChange: (value: string) => void; required?: boolean }): React.ReactElement { return <div><label style={labelStyle}>{label}</label><select value={value} required={required} onChange={(event) => onChange(event.target.value)} style={inputStyle}>{options.map(([key, text]) => <option key={key} value={key}>{text}</option>)}</select></div>; }
function Remove({ onClick }: { onClick: () => void }): React.ReactElement { return <div><button type="button" onClick={onClick} style={{ background: 'var(--danger)', color: '#fff', border: 0, borderRadius: 4, padding: '7px 9px' }}>Remove</button></div>; }
function NumberReadout({ label, value }: { label: string; value: number }): React.ReactElement { return <div><label style={labelStyle}>{label}</label><input readOnly type="number" value={value} style={{ ...inputStyle, background: '#f8fafc' }} /></div>; }
function Readout({ label, value }: { label: string; value: number | null }): React.ReactElement { return <div><label style={labelStyle}>{label}</label><input readOnly value={value === null ? '—' : `₹${Number(value).toLocaleString('en-IN')}`} style={{ ...inputStyle, background: '#f8fafc' }} /></div>; }
