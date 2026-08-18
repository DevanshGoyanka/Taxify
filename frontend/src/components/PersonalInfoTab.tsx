import React, { useEffect, useMemo } from 'react';
import { BankAccountManager, type BankAccountData } from './BankAccountManager';
import { ITD_COUNTRY_CODES } from '../constants/itdCountryCodes';
import { calculateAgeFromDob } from '../utils/age';
import type { ReturnDraft } from '../domain/returns/types';

export type SupportedItrForm = 'ITR-1' | 'ITR-2' | 'ITR-3' | 'ITR-4';

type Personal = ReturnDraft['personal'];
type Filing = ReturnDraft['filing'];
type Verification = ReturnDraft['verification'];
type TaxReturnPreparer = ReturnDraft['taxReturnPreparer'];

type DraftPatch = {
  personal?: Partial<Personal>;
  filing?: Partial<Filing>;
  verification?: Partial<Verification>;
  taxReturnPreparer?: Partial<TaxReturnPreparer>;
  regime?: ReturnDraft['regime'];
};

interface PersonalInfoTabProps {
  draft: ReturnDraft;
  itrForm: SupportedItrForm;
  onChange: (patch: DraftPatch) => void;
  onBanksChange: (data: BankAccountData) => void;
  onRegimeChange: (regime: 'old' | 'new') => void;
}

interface AddressData {
  residenceNo: string;
  residenceName: string;
  roadOrStreet: string;
  localityOrArea: string;
  city: string;
  stateCode: string;
  countryCode: string;
  pinCode: string;
  zipCode: string;
}

const CARD_STYLE: React.CSSProperties = { background: '#fff', border: '1px solid var(--border)', borderRadius: 8, padding: 18, marginBottom: 16 };
const LABEL_STYLE: React.CSSProperties = { display: 'block', marginBottom: 6, fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)' };
const INPUT_STYLE: React.CSSProperties = { width: '100%', boxSizing: 'border-box', padding: '8px 10px', border: '1px solid var(--border)', borderRadius: 6, fontSize: 13, background: '#fff' };
const GRID_STYLE: React.CSSProperties = { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', gap: 14 };
const PAN_PATTERN = '[A-Z]{5}[0-9]{4}[A-Z]';
const PIN_PATTERN = '[1-9][0-9]{5}';

const INDIAN_STATES = [
  ['01', 'Andaman & Nicobar Islands'], ['02', 'Andhra Pradesh'], ['03', 'Arunachal Pradesh'], ['04', 'Assam'], ['05', 'Bihar'], ['06', 'Chandigarh'], ['07', 'Dadra & Nagar Haveli'], ['08', 'Daman & Diu'], ['09', 'Delhi'], ['10', 'Goa'], ['11', 'Gujarat'], ['12', 'Haryana'], ['13', 'Himachal Pradesh'], ['14', 'Jammu & Kashmir'], ['15', 'Karnataka'], ['16', 'Kerala'], ['17', 'Lakshadweep'], ['18', 'Madhya Pradesh'], ['19', 'Maharashtra'], ['20', 'Manipur'], ['21', 'Meghalaya'], ['22', 'Mizoram'], ['23', 'Nagaland'], ['24', 'Odisha'], ['25', 'Puducherry'], ['26', 'Punjab'], ['27', 'Rajasthan'], ['28', 'Sikkim'], ['29', 'Tamil Nadu'], ['30', 'Tripura'], ['31', 'Uttar Pradesh'], ['32', 'West Bengal'], ['33', 'Chhattisgarh'], ['34', 'Uttarakhand'], ['35', 'Jharkhand'], ['36', 'Telangana'], ['37', 'Ladakh'], ['99', 'Outside India'],
] as const;

function text(value: unknown): string { return value == null ? '' : String(value); }
function bool(value: unknown): boolean { return value === true; }
function todayIso(): string { return new Date().toISOString().slice(0, 10); }
function dueDate(form: SupportedItrForm): string { return form === 'ITR-1' || form === 'ITR-2' ? '2026-07-31' : '2026-08-31'; }
function blankAddress(): AddressData { return { residenceNo: '', residenceName: '', roadOrStreet: '', localityOrArea: '', city: '', stateCode: '', countryCode: '91', pinCode: '', zipCode: '' }; }

function Field({ label, value, onChange, type = 'text', required = false, pattern, maxLength, inputMode, help, disabled = false }: { label: string; value: string | number | undefined | null; onChange: (value: string) => void; type?: React.HTMLInputTypeAttribute; required?: boolean; pattern?: string; maxLength?: number; inputMode?: React.HTMLAttributes<HTMLInputElement>['inputMode']; help?: string; disabled?: boolean }): React.JSX.Element {
  const id = `personal-${label.replace(/[^a-z0-9]+/gi, '-').toLowerCase()}`;
  return <div>
    <label htmlFor={id} style={LABEL_STYLE}>{label}{required ? ' *' : ''}</label>
    <input id={id} type={type} value={value ?? ''} onChange={(event) => onChange(event.target.value)} required={required} pattern={pattern} maxLength={maxLength} inputMode={inputMode} disabled={disabled} style={INPUT_STYLE} />
    {help && <div style={{ marginTop: 4, color: 'var(--text-muted)', fontSize: 11 }}>{help}</div>}
  </div>;
}

function SelectField({ label, value, onChange, children, required = false }: { label: string; value: string; onChange: (value: string) => void; children: React.ReactNode; required?: boolean }): React.JSX.Element {
  const id = `personal-${label.replace(/[^a-z0-9]+/gi, '-').toLowerCase()}`;
  return <div><label htmlFor={id} style={LABEL_STYLE}>{label}{required ? ' *' : ''}</label><select id={id} value={value} required={required} onChange={(event) => onChange(event.target.value)} style={INPUT_STYLE}>{children}</select></div>;
}

function SectionHeading({ title, description }: { title: string; description: string }): React.JSX.Element {
  return <div style={{ marginBottom: 16 }}><h3 style={{ margin: 0, fontSize: 16, color: 'var(--text-primary)' }}>{title}</h3><p style={{ margin: '5px 0 0', fontSize: 12, color: 'var(--text-muted)' }}>{description}</p></div>;
}

/**
 * Canonical ITR-1 identity and filing editor.
 *
 * This component intentionally accepts a ReturnDraft rather than a flat
 * compatibility payload. Every editable value below is persisted in the
 * canonical personal, filing, verification, TRP, or bank-account section.
 */
export function PersonalInfoTab({ draft, itrForm, onChange, onBanksChange, onRegimeChange }: PersonalInfoTabProps): React.JSX.Element {
  const { personal, filing, verification, taxReturnPreparer } = draft;
  const filingDueDate = dueDate(itrForm);
  const age = useMemo(() => calculateAgeFromDob(personal.dateOfBirth, draft.assessmentYear || '2026-27'), [personal.dateOfBirth, draft.assessmentYear]);
  const primaryAddress: AddressData = {
    residenceNo: personal.flatNo, residenceName: personal.residenceName, roadOrStreet: personal.roadOrStreet,
    localityOrArea: personal.localityOrArea, city: personal.city, stateCode: personal.stateCode,
    countryCode: personal.countryCode || '91', pinCode: personal.pinCode, zipCode: personal.zipCode,
  };
  const alternateAddress = blankAddress();
  const updatePersonal = (patch: Partial<Personal>): void => onChange({ personal: patch });
  const updateFiling = (patch: Partial<Filing>): void => onChange({ filing: patch });
  const updateVerification = (patch: Partial<Verification>): void => onChange({ verification: patch });
  const updatePrimaryAddress = (key: keyof AddressData, value: string): void => {
    const next = { ...primaryAddress, [key]: value };
    updatePersonal({ flatNo: next.residenceNo, residenceName: next.residenceName, roadOrStreet: next.roadOrStreet, localityOrArea: next.localityOrArea, city: next.city, stateCode: next.stateCode, countryCode: next.countryCode, pinCode: next.pinCode, zipCode: next.zipCode });
  };
  const renderAddress = (address: AddressData, update: (key: keyof AddressData, value: string) => void, prefix: string): React.JSX.Element => {
    const india = address.countryCode === '91';
    return <div style={GRID_STYLE}>
      <Field label={`${prefix} Flat / Door / Block No.`} value={address.residenceNo} onChange={(value) => update('residenceNo', value)} required maxLength={50} />
      <Field label={`${prefix} Premises / Building / Village`} value={address.residenceName} onChange={(value) => update('residenceName', value)} maxLength={50} />
      <Field label={`${prefix} Road / Street / Post Office`} value={address.roadOrStreet} onChange={(value) => update('roadOrStreet', value)} maxLength={50} />
      <Field label={`${prefix} Area / Locality`} value={address.localityOrArea} onChange={(value) => update('localityOrArea', value)} required maxLength={50} />
      <Field label={`${prefix} Town / City / District`} value={address.city} onChange={(value) => update('city', value)} required maxLength={50} />
      <SelectField label={`${prefix} Country`} value={address.countryCode} onChange={(value) => update('countryCode', value)} required>{ITD_COUNTRY_CODES.map((country) => <option key={country.value} value={country.value}>{country.value} — {country.label}</option>)}</SelectField>
      <SelectField label={`${prefix} State`} value={address.stateCode} onChange={(value) => update('stateCode', value)} required={india}><option value="">-- Select state --</option>{INDIAN_STATES.map(([code, label]) => <option key={code} value={code}>{code} — {label}</option>)}</SelectField>
      {india ? <Field label={`${prefix} PIN Code`} value={address.pinCode} onChange={(value) => update('pinCode', value.replace(/\D/g, '').slice(0, 6))} required pattern={PIN_PATTERN} maxLength={6} inputMode="numeric" /> : <Field label={`${prefix} ZIP / Postal Code`} value={address.zipCode} onChange={(value) => update('zipCode', value)} required maxLength={20} />}
    </div>;
  };

  useEffect(() => {
    if (!filing.originalFilingDate && !verification.date) updateVerification({ date: todayIso() });
  }, [filing.originalFilingDate, verification.date]);

  return <div>
    <SectionHeading title="Identity and contact" description="Enter the identity, communication and statutory profile exactly as registered. PAN and date of birth are used for validation and age-based tax rules." />
    <div style={CARD_STYLE}><div style={GRID_STYLE}>
      <Field label="First Name" value={personal.firstName} onChange={(value) => updatePersonal({ firstName: value, name: [value, personal.middleName, personal.surnameOrOrgName].filter(Boolean).join(' ') })} maxLength={25} />
      <Field label="Middle Name" value={personal.middleName} onChange={(value) => updatePersonal({ middleName: value, name: [personal.firstName, value, personal.surnameOrOrgName].filter(Boolean).join(' ') })} maxLength={25} />
      <Field label="Surname / Organisation Name" value={personal.surnameOrOrgName} onChange={(value) => updatePersonal({ surnameOrOrgName: value, name: [personal.firstName, personal.middleName, value].filter(Boolean).join(' ') || value })} required maxLength={75} />
      <Field label="PAN" value={personal.pan} onChange={(value) => updatePersonal({ pan: value.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 10) })} required pattern={PAN_PATTERN} maxLength={10} help="Format: ABCDE1234F." />
      <Field label="Aadhaar Number" value={personal.aadhaar} onChange={(value) => updatePersonal({ aadhaar: value.replace(/\D/g, '').slice(0, 12) })} pattern="[0-9]{12}" maxLength={12} inputMode="numeric" />
      <Field label="Date of Birth / Formation" value={personal.dateOfBirth || ''} onChange={(value) => updatePersonal({ dateOfBirth: value || null })} type="date" required />
      <Field label="Age as on 31 March 2026" value={age} onChange={() => undefined} disabled />
      <Field label="Father's Name" value={personal.fatherName} onChange={(value) => updatePersonal({ fatherName: value })} required maxLength={125} />
    </div></div>
    <div style={CARD_STYLE}><h4 style={{ marginTop: 0, fontSize: 14 }}>Contact details</h4><div style={GRID_STYLE}>
      <Field label="Mobile Number" value={personal.mobile} onChange={(value) => updatePersonal({ mobile: value.replace(/\D/g, '').slice(0, 15) })} required pattern="[0-9]{6,15}" maxLength={15} inputMode="tel" />
      <Field label="Primary Email Address" value={personal.email} onChange={(value) => updatePersonal({ email: value.trim() })} type="email" required maxLength={125} />
      <Field label="Secondary Mobile Number" value={personal.secondaryMobile} onChange={(value) => updatePersonal({ secondaryMobile: value.replace(/\D/g, '').slice(0, 15), secondaryMobileCountryCode: personal.secondaryMobileCountryCode || '91' })} pattern="[0-9]{5,15}" maxLength={15} inputMode="tel" />
      <Field label="Secondary Email Address" value={personal.secondaryEmail} onChange={(value) => updatePersonal({ secondaryEmail: value.trim() })} type="email" maxLength={125} />
    </div></div>
    <SectionHeading title="Primary address" description="Use the address at which statutory communication should be received. Postal-code rules change when the selected country is outside India." />
    <div style={CARD_STYLE}>{renderAddress(primaryAddress, updatePrimaryAddress, 'Primary')}</div>
    <div style={CARD_STYLE}><h4 style={{ marginTop: 0, fontSize: 14 }}>Filing status</h4><div style={GRID_STYLE}>
      <SelectField label="Return filed under section" value={filing.filingSection} onChange={(value) => updateFiling({ filingSection: value as Filing['filingSection'], returnType: value === '139(5)' ? 'REVISED' : 'ORIGINAL' })} required><option value="139(1)">139(1) — On or before due date</option><option value="139(4)">139(4) — Belated return</option><option value="139(5)">139(5) — Revised return</option><option value="119(2)(b)">119(2)(b) — Condonation of delay</option></SelectField>
      <Field label="ITR Filing Due Date" value={filingDueDate} onChange={() => undefined} type="date" disabled />
      <Field label="Original Acknowledgement Number" value={filing.originalAcknowledgementNumber} onChange={(value) => updateFiling({ originalAcknowledgementNumber: value.replace(/\D/g, '').slice(0, 15) })} maxLength={15} inputMode="numeric" />
      <Field label="Original Return Filing Date" value={filing.originalFilingDate || ''} onChange={(value) => updateFiling({ originalFilingDate: value || null })} type="date" />
      <Field label="Notice / Order Number" value={filing.noticeNumber} onChange={(value) => updateFiling({ noticeNumber: value })} maxLength={100} />
      <SelectField label="Tax Regime Election" value={draft.regime === 'old' ? 'OLD' : 'NEW'} onChange={(value) => { const next = value === 'OLD' ? 'old' : 'new'; onChange({ regime: next }); onRegimeChange(next); }} required><option value="NEW">New tax regime</option><option value="OLD">Old tax regime / opt out</option></SelectField>
    </div></div>
    <SectionHeading title="Verification" description="The declaration must be accepted before official CBDT JSON generation." />
    <div style={CARD_STYLE}><div style={GRID_STYLE}>
      <SelectField label="Verification capacity" value={verification.capacity} onChange={(value) => updateVerification({ capacity: value as Verification['capacity'] })} required><option value="SELF">Self</option><option value="REPRESENTATIVE">Representative assessee</option></SelectField>
      <Field label="Place of verification" value={verification.place} onChange={(value) => updateVerification({ place: value })} required maxLength={50} />
      <Field label="Verification date" value={verification.date || ''} onChange={(value) => updateVerification({ date: value || null })} type="date" required />
    </div><label style={{ display: 'flex', alignItems: 'flex-start', gap: 8, marginTop: 16, fontSize: 13 }}><input type="checkbox" checked={bool(verification.declarationAccepted)} onChange={(event) => updateVerification({ declarationAccepted: event.target.checked })} />I declare that the information given in this return and its schedules is correct and complete.</label></div>
    <SectionHeading title="Tax Return Preparer (TRP)" description="Optional. Fill only if a Tax Return Preparer prepared this return." />
    <div style={CARD_STYLE}><SelectField label="Was this return prepared by a TRP?" value={taxReturnPreparer.used ? 'Y' : 'N'} onChange={(value) => onChange({ taxReturnPreparer: { used: value === 'Y' } })} required><option value="N">No</option><option value="Y">Yes</option></SelectField>{taxReturnPreparer.used && <div style={{ ...GRID_STYLE, marginTop: 16 }}><Field label="TRP identification number" value={taxReturnPreparer.identificationNumber} onChange={(value) => onChange({ taxReturnPreparer: { identificationNumber: value.toUpperCase() } })} required maxLength={10} /><Field label="TRP name" value={taxReturnPreparer.name} onChange={(value) => onChange({ taxReturnPreparer: { name: value } })} required maxLength={125} /><Field label="Reimbursement from government (₹)" value={taxReturnPreparer.reimbursementFromGovernment} onChange={(value) => onChange({ taxReturnPreparer: { reimbursementFromGovernment: Number(value.replace(/\D/g, '')) || 0 } })} inputMode="numeric" /></div>}</div>
    <SectionHeading title="Bank accounts and refund" description="Add all reportable accounts. Select exactly one refund account whenever a refund account is required." />
    <div style={CARD_STYLE}><BankAccountManager data={{ accounts: draft.bankAccounts }} onChange={onBanksChange} /></div>
    <div style={{ padding: 12, borderRadius: 6, background: 'var(--info-bg)', color: 'var(--info)', fontSize: 12 }}>Bank accounts are stored in the canonical draft and sent directly to the v2 repository.</div>
  </div>;
}
