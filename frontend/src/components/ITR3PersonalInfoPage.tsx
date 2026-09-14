import React, { useEffect } from 'react';
import { BankAccountManager, type BankAccountData } from './BankAccountManager';
import { ITD_COUNTRY_CODES } from '../constants/itdCountryCodes';
import { STATE_CODE_OPTIONS, type StateCode } from '../domain/returns/cbdtEnums';
import { getDueDate, todayIso } from '../domain/returns/dueDates';
import type { ReturnDraft } from '../domain/returns/types';

interface Props {
  draft: ReturnDraft;
  onChange: (patch: DraftPatch) => void;
  onBanksChange: (data: BankAccountData) => void;
  onRegimeChange: (regime: 'old' | 'new') => void;
}

type DraftPatch = {
  personal?: Partial<ReturnDraft['personal']>;
  filing?: Partial<ReturnDraft['filing']>;
  verification?: Partial<ReturnDraft['verification']>;
  regime?: ReturnDraft['regime'];
};

type Address = {
  residenceNo: string;
  residenceName: string;
  roadOrStreet: string;
  localityOrArea: string;
  city: string;
  stateCode: string;
  countryCode: string;
  pinCode: string;
  zipCode: string;
};

const card: React.CSSProperties = { background: '#fff', border: '1px solid var(--border)', borderRadius: 8, padding: 16, marginBottom: 14 };
const grid: React.CSSProperties = { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 12 };
const label: React.CSSProperties = { display: 'block', marginBottom: 4, fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)' };
const input: React.CSSProperties = { width: '100%', boxSizing: 'border-box', padding: '8px 10px', border: '1px solid var(--border)', borderRadius: 6, fontSize: 13 };
const PAN = '[A-Z]{5}[0-9]{4}[A-Z]';
const PIN = '[1-9][0-9]{5}';

function Field({ label: text, value, onChange, type = 'text', required = false, pattern, maxLength, min, max, help }: { label: string; value: string | number | null | undefined; onChange: (value: string) => void; type?: React.HTMLInputTypeAttribute; required?: boolean; pattern?: string; maxLength?: number; min?: number; max?: number; help?: string }): React.JSX.Element {
  const id = `itr3-${text.replace(/[^a-z0-9]+/gi, '-').toLowerCase()}`;
  return <div><label htmlFor={id} style={label}>{text}{required && <span style={{ color: 'var(--danger)' }}> *</span>}</label><input id={id} style={input} value={value ?? ''} onChange={(event) => onChange(event.target.value)} type={type} required={required} pattern={pattern} maxLength={maxLength} min={min} max={max} />{help && <div style={{ marginTop: 4, color: 'var(--text-muted)', fontSize: 11 }}>{help}</div>}</div>;
}

function Select({ label: text, value, onChange, children, required = false }: { label: string; value: string; onChange: (value: string) => void; children: React.ReactNode; required?: boolean }): React.JSX.Element {
  return <div><label style={label}>{text}{required && <span style={{ color: 'var(--danger)' }}> *</span>}</label><select style={input} value={value} onChange={(event) => onChange(event.target.value)} required={required}>{children}</select></div>;
}

function Section({ title, description, children }: { title: string; description: string; children: React.ReactNode }): React.JSX.Element {
  return <section style={card}><h3 style={{ margin: '0 0 4px', fontSize: 16, color: 'var(--text-primary)' }}>{title}</h3><p style={{ margin: '0 0 14px', fontSize: 12, lineHeight: 1.5, color: 'var(--text-muted)' }}>{description}</p>{children}</section>;
}

function addressFromPersonal(personal: ReturnDraft['personal']): Address {
  return { residenceNo: personal.flatNo, residenceName: personal.residenceName, roadOrStreet: personal.roadOrStreet, localityOrArea: personal.localityOrArea, city: personal.city, stateCode: personal.stateCode, countryCode: personal.countryCode || '91', pinCode: personal.pinCode, zipCode: personal.zipCode };
}

function addressFromAlternate(personal: ReturnDraft['personal']): Address {
  const address = personal.alternateAddress;
  return address ? { residenceNo: address.residenceNo, residenceName: address.residenceName, roadOrStreet: address.roadOrStreet, localityOrArea: address.localityOrArea, city: address.cityOrTownOrDistrict, stateCode: address.stateCode, countryCode: address.countryCode || '91', pinCode: address.pinCode, zipCode: address.zipCode } : { residenceNo: '', residenceName: '', roadOrStreet: '', localityOrArea: '', city: '', stateCode: '', countryCode: '91', pinCode: '', zipCode: '' };
}

function AddressFields({ prefix, value, onChange }: { prefix: string; value: Address; onChange: (key: keyof Address, value: string) => void }): React.JSX.Element {
  const india = value.countryCode === '91';
  return <div style={grid}>
    <Field label={`${prefix} flat / door / block no.`} value={value.residenceNo} onChange={(next) => onChange('residenceNo', next)} required maxLength={50} />
    <Field label={`${prefix} premises / building / village`} value={value.residenceName} onChange={(next) => onChange('residenceName', next)} maxLength={50} />
    <Field label={`${prefix} road / street / post office`} value={value.roadOrStreet} onChange={(next) => onChange('roadOrStreet', next)} maxLength={50} />
    <Field label={`${prefix} area / locality`} value={value.localityOrArea} onChange={(next) => onChange('localityOrArea', next)} required maxLength={50} />
    <Field label={`${prefix} town / city / district`} value={value.city} onChange={(next) => onChange('city', next)} required maxLength={50} />
    <Select label={`${prefix} country`} value={value.countryCode} onChange={(next) => onChange('countryCode', next)} required>{ITD_COUNTRY_CODES.map((country) => <option key={country.value} value={country.value}>{country.value} — {country.label}</option>)}</Select>
    <Select label={`${prefix} state`} value={value.stateCode} onChange={(next) => onChange('stateCode', next)} required><option value="">-- Select state --</option>{STATE_CODE_OPTIONS.filter(({ code }) => india ? code !== '99' : code === '99').map(({ code, label: stateLabel }) => <option key={code} value={code}>{code} — {stateLabel}</option>)}</Select>
    {india ? <Field label={`${prefix} PIN code`} value={value.pinCode} onChange={(next) => onChange('pinCode', next.replace(/\D/g, '').slice(0, 6))} required pattern={PIN} maxLength={6} /> : <Field label={`${prefix} ZIP / postal code`} value={value.zipCode} onChange={(next) => onChange('zipCode', next)} required maxLength={8} />}
  </div>;
}

/**
 * Tax-professional ITR-3 Personal Information page for AY 2026-27.
 *
 * This page is intentionally isolated from PersonalInfoTab so ITR-1, ITR-2,
 * and ITR-4 retain their existing UI and behavior.
 */
export function ITR3PersonalInfoPage({ draft, onChange, onBanksChange, onRegimeChange }: Props): React.JSX.Element {
  const { personal, filing, verification } = draft;
  const primary = addressFromPersonal(personal);
  const alternate = addressFromAlternate(personal);
  const updatePersonal = (patch: Partial<ReturnDraft['personal']>): void => onChange({ personal: patch });
  const updateFiling = (patch: Partial<ReturnDraft['filing']>): void => onChange({ filing: patch });
  const updateVerification = (patch: Partial<ReturnDraft['verification']>): void => onChange({ verification: patch });
  const updateAddress = (which: 'primary' | 'alternate', key: keyof Address, value: string): void => {
    const next = { ...(which === 'primary' ? primary : alternate), [key]: value };
    if (key === 'countryCode') next.stateCode = value === '91' && next.stateCode === '99' ? '' : value === '91' ? next.stateCode : '99';
    if (which === 'primary') updatePersonal({ flatNo: next.residenceNo, residenceName: next.residenceName, roadOrStreet: next.roadOrStreet, localityOrArea: next.localityOrArea, city: next.city, stateCode: next.stateCode as StateCode | '', countryCode: next.countryCode, pinCode: next.pinCode, zipCode: next.zipCode });
    else updatePersonal({ alternateAddress: { residenceNo: next.residenceNo, residenceName: next.residenceName, roadOrStreet: next.roadOrStreet, localityOrArea: next.localityOrArea, cityOrTownOrDistrict: next.city, stateCode: next.stateCode as StateCode | '', countryCode: next.countryCode, pinCode: next.pinCode, zipCode: next.zipCode } });
  };

  useEffect(() => {
    if (!verification.date) updateVerification({ date: todayIso() });
  }, [verification.date]);

  return <div>
    <div style={{ ...card, background: 'var(--gold-pale)' }}><strong style={{ color: 'var(--text-primary)' }}>ITR-3 · Part A — Personal Information</strong><div style={{ marginTop: 5, fontSize: 12, color: 'var(--text-muted)' }}>Complete this profile first. Your answers determine the filing-status, audit, business, and supporting schedules shown later.</div></div>
    <Section title="Assessee identity" description="Part A A1–A4 and A14–A16. These fields map to PartA_GEN1.PersonalInfo and are used throughout the return."><div style={grid}>
      <Field label="First name" value={personal.firstName} onChange={(value) => updatePersonal({ firstName: value, name: [value, personal.middleName, personal.surnameOrOrgName].filter(Boolean).join(' ') })} maxLength={25} />
      <Field label="Middle name" value={personal.middleName} onChange={(value) => updatePersonal({ middleName: value, name: [personal.firstName, value, personal.surnameOrOrgName].filter(Boolean).join(' ') })} maxLength={25} />
      <Field label="Surname / organisation name" value={personal.surnameOrOrgName} onChange={(value) => updatePersonal({ surnameOrOrgName: value, name: [personal.firstName, personal.middleName, value].filter(Boolean).join(' ') || value })} required maxLength={75} />
      <Field label="PAN" value={personal.pan} onChange={(value) => updatePersonal({ pan: value.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 10) })} required pattern={PAN} maxLength={10} help="Format: ABCDE1234F." />
      <Select label="Status" value={personal.assesseeStatus === 'H' ? 'H' : 'I'} onChange={(value) => updatePersonal({ assesseeStatus: value as 'I' | 'H' | 'F' })} required><option value="I">Individual</option><option value="H">HUF</option></Select>
      <Field label="Date of birth / formation" value={personal.dateOfBirth || ''} onChange={(value) => updatePersonal({ dateOfBirth: value || null })} type="date" required />
      <Field label="Father's name" value={personal.fatherName} onChange={(value) => updatePersonal({ fatherName: value })} required maxLength={125} />
      <Field label="Aadhaar number" value={personal.aadhaar} onChange={(value) => updatePersonal({ aadhaar: value.replace(/\D/g, '').slice(0, 12) })} pattern="[0-9]{12}" maxLength={12} />
    </div></Section>
    <Section title="Primary address" description="Part A A5a–A13a. The country controls whether the form requires an Indian PIN or foreign ZIP/postal code."><AddressFields prefix="Primary" value={primary} onChange={(key, value) => updateAddress('primary', key, value)} /></Section>
    <Section title="Communication details" description="Part A communication fields. Enter the taxpayer’s active mobile and email used for filing communication."><div style={grid}>
      <Field label="Mobile country code" value={personal.mobileCountryCode} onChange={(value) => updatePersonal({ mobileCountryCode: value.replace(/\D/g, '').slice(0, 5) })} required pattern="[0-9]{1,5}" maxLength={5} />
      <Field label="Mobile number" value={personal.mobile} onChange={(value) => updatePersonal({ mobile: value.replace(/\D/g, '').slice(0, 10) })} required pattern="[1-9][0-9]{4,9}" maxLength={10} />
      <Field label="Primary email" value={personal.email} onChange={(value) => updatePersonal({ email: value.trim() })} type="email" required maxLength={125} />
      <Field label="Secondary mobile country code" value={personal.secondaryMobileCountryCode} onChange={(value) => updatePersonal({ secondaryMobileCountryCode: value.replace(/\D/g, '').slice(0, 5) })} pattern="[0-9]{1,5}" maxLength={5} />
      <Field label="Secondary mobile number" value={personal.secondaryMobile} onChange={(value) => updatePersonal({ secondaryMobile: value.replace(/\D/g, '').slice(0, 10), secondaryMobileCountryCode: personal.secondaryMobileCountryCode || '91' })} pattern="[1-9][0-9]{4,9}" maxLength={10} />
      <Field label="Secondary email" value={personal.secondaryEmail} onChange={(value) => updatePersonal({ secondaryEmail: value.trim() })} type="email" maxLength={125} />
    </div></Section>
    <Section title="Secondary / alternate address" description="Part A secondary-address indicator and A5b–A13b. Select Yes only when a distinct correspondence address must be reported."><label style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: 13 }}><input type="checkbox" checked={personal.secondaryAddressDifferent} onChange={(event) => updatePersonal({ secondaryAddressDifferent: event.target.checked, alternateAddress: event.target.checked ? (personal.alternateAddress ?? { residenceNo: '', residenceName: '', roadOrStreet: '', localityOrArea: '', cityOrTownOrDistrict: '', stateCode: '', countryCode: '91', pinCode: '', zipCode: '' }) : null })} />A different secondary address is applicable</label>{personal.secondaryAddressDifferent && <div style={{ marginTop: 14 }}><AddressFields prefix="Secondary" value={alternate} onChange={(key, value) => updateAddress('alternate', key, value)} /></div>}</Section>
    <Section title="Filing status and regime" description="Start with the return section and tax regime. Conditional notice, revised-return, and Form 10-IEA workflows will be expanded in the Filing Status phase."><div style={grid}>
      <Select label="Return filed under section" value={filing.filingSection} onChange={(value) => updateFiling({ filingSection: value as ReturnDraft['filing']['filingSection'], returnType: value === '139(5)' ? 'REVISED' : 'ORIGINAL' })} required><option value="139(1)">139(1) — On or before due date</option><option value="139(4)">139(4) — Belated</option><option value="139(5)">139(5) — Revised</option><option value="142(1)">142(1) — Notice</option><option value="148">148 — Reassessment notice</option><option value="139(9)">139(9) — Defective return</option><option value="119(2)(b)">119(2)(b) — Condonation</option></Select>
      <Field label="ITR filing due date" value={getDueDate('ITR-3', draft.assessmentYear || '2026-27')} onChange={() => undefined} type="date" />
      <Select label="Tax regime election" value={draft.regime === 'old' ? 'old' : 'new'} onChange={(value) => { const regime = value as 'old' | 'new'; onChange({ regime }); onRegimeChange(regime); }} required><option value="new">New tax regime</option><option value="old">Old tax regime / opt out</option></Select>
      {filing.filingSection === '139(5)' && <><Field label="Original acknowledgement number" value={filing.originalAcknowledgementNumber} onChange={(value) => updateFiling({ originalAcknowledgementNumber: value.replace(/\D/g, '').slice(0, 15) })} required pattern="[0-9]{15}" maxLength={15} /><Field label="Original return filing date" value={filing.originalFilingDate || ''} onChange={(value) => updateFiling({ originalFilingDate: value || null })} type="date" required /></>}
    </div></Section>
    <Section title="Verification" description="The final declaration is required before CBDT JSON generation. Representative details and capacity-specific fields will be expanded with the official filing-status phase."><div style={grid}>
      <Select label="Verification capacity" value={verification.capacity} onChange={(value) => updateVerification({ capacity: value as ReturnDraft['verification']['capacity'] })} required><option value="SELF">Self</option><option value="REPRESENTATIVE">Representative assessee</option><option value="KARTA">Karta</option><option value="PARTNER">Authorised partner</option></Select>
      <Field label="Place" value={verification.place} onChange={(value) => updateVerification({ place: value })} required maxLength={50} />
      <Field label="Verification date" value={verification.date || ''} onChange={(value) => updateVerification({ date: value || null })} type="date" required />
    </div><label style={{ display: 'flex', gap: 8, alignItems: 'flex-start', marginTop: 14, fontSize: 13 }}><input type="checkbox" checked={verification.declarationAccepted} onChange={(event) => updateVerification({ declarationAccepted: event.target.checked })} />I declare that the information given in this return and its schedules is correct and complete.</label></Section>
    <Section title="Bank accounts and refund" description="Add reportable bank accounts in the canonical draft. Select the refund account in the account manager."><BankAccountManager data={{ accounts: draft.bankAccounts }} onChange={onBanksChange} /></Section>
  </div>;
}

export default ITR3PersonalInfoPage;
