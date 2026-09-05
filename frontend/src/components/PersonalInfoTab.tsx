import React, { useEffect, useMemo } from 'react';
import { BankAccountManager, type BankAccountData } from './BankAccountManager';
import { ITD_COUNTRY_CODES } from '../constants/itdCountryCodes';
import { calculateAgeFromDob } from '../utils/age';
import type { CompanyDirectorEntry, CompanyType, ReturnDraft, UnlistedEquityEntry } from '../domain/returns/types';
import {
  EMPLOYER_CATEGORY_OPTIONS,
  STATE_CODE_OPTIONS,
  type EmployerCategory,
  type StateCode,
} from '../domain/returns/cbdtEnums';
import { getDueDate, isDueDatePassed, todayIso } from '../domain/returns/dueDates';

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

function moneyValue(value: string | number | null | undefined): string {
  if (value === null || value === undefined) return '';
  return String(value);
}

function parseMoney(value: string): number {
  return value === '' ? 0 : Number(value);
}

function bool(value: unknown): boolean { return value === true; }
function blankAddress(): AddressData { return { residenceNo: '', residenceName: '', roadOrStreet: '', localityOrArea: '', city: '', stateCode: '', countryCode: '91', pinCode: '', zipCode: '' }; }

function Field({ label, value, onChange, type = 'text', required = false, pattern, maxLength, min, max, inputMode, help, disabled = false }: { label: string; value: string | number | undefined | null; onChange: (value: string) => void; type?: React.HTMLInputTypeAttribute; required?: boolean; pattern?: string; maxLength?: number; min?: number | string; max?: number | string; inputMode?: React.HTMLAttributes<HTMLInputElement>['inputMode']; help?: string; disabled?: boolean }): React.JSX.Element {
  const id = `personal-${label.replace(/[^a-z0-9]+/gi, '-').toLowerCase()}`;
  return <div>
    <label htmlFor={id} style={LABEL_STYLE}>{label}{required ? ' *' : ''}</label>
    <input id={id} type={type} value={value ?? ''} onChange={(event) => onChange(event.target.value)} required={required} pattern={pattern} maxLength={maxLength} min={min} max={max} inputMode={inputMode} disabled={disabled} style={INPUT_STYLE} />
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

function CheckField({ label, checked, onChange }: { label: string; checked: boolean; onChange: (value: boolean) => void }): React.JSX.Element {
  return <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}>
    <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
    {label}
  </label>;
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
  const assessmentYear = draft.assessmentYear || '2026-27';
  const filingDueDate = getDueDate(itrForm, assessmentYear);
  // Once the 139(1) due date has gone, an unfiled return is belated under
  // 139(4) and a filed one can only be corrected as revised under 139(5).
  const dueDatePassed = isDueDatePassed(itrForm, assessmentYear, verification.date || todayIso());
  const age = useMemo(() => calculateAgeFromDob(personal.dateOfBirth, draft.assessmentYear || '2026-27'), [personal.dateOfBirth, draft.assessmentYear]);
  const primaryAddress: AddressData = {
    residenceNo: personal.flatNo, residenceName: personal.residenceName, roadOrStreet: personal.roadOrStreet,
    localityOrArea: personal.localityOrArea, city: personal.city, stateCode: personal.stateCode,
    countryCode: personal.countryCode || '91', pinCode: personal.pinCode, zipCode: personal.zipCode,
  };
  const alternateAddress: AddressData = personal.alternateAddress
    ? {
        residenceNo: personal.alternateAddress.residenceNo,
        residenceName: personal.alternateAddress.residenceName,
        roadOrStreet: personal.alternateAddress.roadOrStreet,
        localityOrArea: personal.alternateAddress.localityOrArea,
        city: personal.alternateAddress.cityOrTownOrDistrict,
        stateCode: personal.alternateAddress.stateCode,
        countryCode: personal.alternateAddress.countryCode,
        pinCode: personal.alternateAddress.pinCode,
        zipCode: personal.alternateAddress.zipCode,
      }
    : blankAddress();
  const updatePersonal = (patch: Partial<Personal>): void => onChange({ personal: patch });
  const updateFiling = (patch: Partial<Filing>): void => onChange({ filing: patch });
  const updateVerification = (patch: Partial<Verification>): void => onChange({ verification: patch });
  const updatePrimaryAddress = (key: keyof AddressData, value: string): void => {
    const next = { ...primaryAddress, [key]: value };
    if (key === 'countryCode') {
      next.stateCode = value === '91' ? (next.stateCode === '99' ? '' : next.stateCode) : '99';
    }
    updatePersonal({ flatNo: next.residenceNo, residenceName: next.residenceName, roadOrStreet: next.roadOrStreet, localityOrArea: next.localityOrArea, city: next.city, stateCode: next.stateCode as StateCode | '', countryCode: next.countryCode, pinCode: next.pinCode, zipCode: next.zipCode });
  };
  const updateAlternateAddress = (key: keyof AddressData, value: string): void => {
    const next = { ...alternateAddress, [key]: value };
    if (key === 'countryCode') {
      next.stateCode = value === '91' ? (next.stateCode === '99' ? '' : next.stateCode) : '99';
    }
    updatePersonal({
      alternateAddress: {
        residenceNo: next.residenceNo,
        residenceName: next.residenceName,
        roadOrStreet: next.roadOrStreet,
        localityOrArea: next.localityOrArea,
        cityOrTownOrDistrict: next.city,
        stateCode: next.stateCode as StateCode | '',
        countryCode: next.countryCode,
        pinCode: next.pinCode,
        zipCode: next.zipCode,
      },
    });
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
      <SelectField label={`${prefix} State`} value={address.stateCode} onChange={(value) => update('stateCode', value)} required><option value="">-- Select state --</option>{STATE_CODE_OPTIONS.filter(({ code }) => india ? code !== '99' : code === '99').map(({ code, label }) => <option key={code} value={code}>{code} — {label}</option>)}</SelectField>
      {india ? <Field label={`${prefix} PIN Code`} value={address.pinCode} onChange={(value) => update('pinCode', value.replace(/\D/g, '').slice(0, 6))} required pattern={PIN_PATTERN} maxLength={6} inputMode="numeric" /> : <Field label={`${prefix} ZIP / Postal Code`} value={address.zipCode} onChange={(value) => update('zipCode', value)} required maxLength={8} />}
    </div>;
  };

  useEffect(() => {
    if (!filing.originalFilingDate && !verification.date) {
      onChange({ verification: { date: todayIso() } });
    }
  }, [filing.originalFilingDate, onChange, verification.date]);

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
      <SelectField label="Employer Category" value={personal.employerCategory} onChange={(value) => updatePersonal({ employerCategory: value as EmployerCategory })} required>
        <option value="">-- Select employer category --</option>
        {EMPLOYER_CATEGORY_OPTIONS.map(({ code, label }) => <option key={code} value={code}>{code} — {label}</option>)}
      </SelectField>
      {itrForm === 'ITR-2' && <SelectField label="ITR-2 assessee status" value={personal.assesseeStatus === 'H' ? 'H' : 'I'} onChange={(value) => updatePersonal({ assesseeStatus: value as Personal['assesseeStatus'] })} required>
        <option value="I">Individual</option><option value="H">HUF</option>
      </SelectField>}
      {itrForm === 'ITR-2' && <SelectField label="Residential Status" value={personal.residentialStatus || 'ROR'} onChange={(value) => updatePersonal({ residentialStatus: value as Personal['residentialStatus'] })} required>
        <option value="ROR">Resident and Ordinarily Resident</option>
        <option value="RNOR">Resident but Not Ordinarily Resident</option>
        <option value="NR">Non-Resident</option>
      </SelectField>}
    </div></div>
    <div style={CARD_STYLE}><h4 style={{ marginTop: 0, fontSize: 14 }}>Contact details</h4><div style={GRID_STYLE}>
      <Field label="Mobile Country Code" value={personal.mobileCountryCode} onChange={(value) => updatePersonal({ mobileCountryCode: value.replace(/\D/g, '').slice(0, 5) })} required pattern="[0-9]{1,5}" maxLength={5} inputMode="numeric" />
      <Field label="Mobile Number" value={personal.mobile} onChange={(value) => updatePersonal({ mobile: value.replace(/\D/g, '').slice(0, 10) })} required pattern="[1-9][0-9]{4,9}" maxLength={10} inputMode="tel" />
      <Field label="Primary Email Address" value={personal.email} onChange={(value) => updatePersonal({ email: value.trim() })} type="email" required maxLength={125} />
      <Field label="Secondary Mobile Country Code" value={personal.secondaryMobileCountryCode} onChange={(value) => updatePersonal({ secondaryMobileCountryCode: value.replace(/\D/g, '').slice(0, 5) })} pattern="[0-9]{1,5}" maxLength={5} inputMode="numeric" />
      <Field label="Secondary Mobile Number" value={personal.secondaryMobile} onChange={(value) => updatePersonal({ secondaryMobile: value.replace(/\D/g, '').slice(0, 10), secondaryMobileCountryCode: personal.secondaryMobileCountryCode || '91' })} pattern="[1-9][0-9]{4,9}" maxLength={10} inputMode="tel" />
      <Field label="Secondary Email Address" value={personal.secondaryEmail} onChange={(value) => updatePersonal({ secondaryEmail: value.trim() })} type="email" maxLength={125} />
      {itrForm === 'ITR-4' && <Field label="Landline STD Code" value={personal.landlineStdCode} onChange={(value) => updatePersonal({ landlineStdCode: value.replace(/\D/g, '').slice(0, 5) || '0' })} pattern="[0-9]{1,5}" maxLength={5} inputMode="numeric" />}
      {itrForm === 'ITR-4' && <Field label="Landline Phone Number" value={personal.landlinePhoneNo} onChange={(value) => updatePersonal({ landlinePhoneNo: value.replace(/\D/g, '').slice(0, 12) || '0' })} pattern="[0-9]{1,12}" maxLength={12} inputMode="tel" />}
    </div></div>
    {itrForm === 'ITR-4' && <div style={CARD_STYLE}><h4 style={{ marginTop: 0, fontSize: 14 }}>ITR-4 assessee status</h4><div style={GRID_STYLE}>
      <SelectField label="Status" value={personal.assesseeStatus} onChange={(value) => updatePersonal({ assesseeStatus: value as Personal['assesseeStatus'] })} required>
        <option value="I">Individual</option><option value="H">HUF</option><option value="F">Firm (other than LLP)</option>
      </SelectField>
    </div></div>}
    <SectionHeading title="Primary address" description="Use the address at which statutory communication should be received. Postal-code rules change when the selected country is outside India." />
    <div style={CARD_STYLE}>{renderAddress(primaryAddress, updatePrimaryAddress, 'Primary')}</div>
    <div style={CARD_STYLE}>
      <CheckField label="Use a different correspondence / alternate address" checked={personal.secondaryAddressDifferent} onChange={(checked) => updatePersonal({ secondaryAddressDifferent: checked, alternateAddress: checked ? (personal.alternateAddress ?? { residenceNo: '', residenceName: '', roadOrStreet: '', localityOrArea: '', cityOrTownOrDistrict: '', stateCode: '', countryCode: '91', pinCode: '', zipCode: '' }) : null })} />
      {personal.secondaryAddressDifferent && <div style={{ marginTop: 16 }}>{renderAddress(alternateAddress, updateAlternateAddress, 'Alternate')}</div>}
    </div>
    <div style={CARD_STYLE}><h4 style={{ marginTop: 0, fontSize: 14 }}>Filing status</h4><div style={GRID_STYLE}>
      <SelectField label="Return filed under section" value={filing.filingSection} onChange={(value) => updateFiling({ filingSection: value as Filing['filingSection'], returnType: value === '139(5)' ? 'REVISED' : 'ORIGINAL' })} required><option value="139(1)" disabled={dueDatePassed}>139(1) — On or before due date{dueDatePassed ? ' (due date passed)' : ''}</option><option value="139(4)">139(4) — Belated return</option><option value="142(1)">142(1) — Notice</option><option value="148">148 — Reassessment notice</option><option value="153C">153C — Notice</option><option value="139(5)">139(5) — Revised return</option><option value="139(9)">139(9) — Defective return</option><option value="92CD">92CD — Modified return</option><option value="119(2)(b)">119(2)(b) — Condonation of delay</option></SelectField>
      <Field label="ITR Filing Due Date" value={filingDueDate} onChange={() => undefined} type="date" disabled />
      {dueDatePassed && filing.filingSection === '139(1)' && <div style={{ gridColumn: '1 / -1', padding: '8px 10px', borderRadius: 6, border: '1px solid #f0c36d', background: '#fdf6e3', fontSize: 12, color: '#7a5b00' }}>The {itrForm} due date for AY {assessmentYear} ({filingDueDate}) has passed, so this return cannot be filed under 139(1). Choose 139(4) if it has not been filed yet, or 139(5) with the original acknowledgement details if it has. Filing and validation are blocked until this is changed.</div>}
      {filing.filingSection === '139(5)' && <Field label="Original Acknowledgement Number" value={filing.originalAcknowledgementNumber} onChange={(value) => updateFiling({ originalAcknowledgementNumber: value.replace(/\D/g, '').slice(0, 15) })} required pattern="[0-9]{15}" maxLength={15} inputMode="numeric" />}
      {filing.filingSection === '139(5)' && <Field label="Original Return Filing Date" value={filing.originalFilingDate || ''} onChange={(value) => updateFiling({ originalFilingDate: value || null })} type="date" required />}
      {['142(1)', '148', '153C', '139(9)', '119(2)(b)'].includes(filing.filingSection) && <Field label="Notice / Order Number" value={filing.noticeNumber} onChange={(value) => updateFiling({ noticeNumber: value })} required maxLength={100} />}
      {['142(1)', '148', '153C', '139(9)', '119(2)(b)'].includes(filing.filingSection) && <Field label="Notice / Order Date" value={filing.noticeDate || ''} onChange={(value) => updateFiling({ noticeDate: value || null })} type="date" required />}
      <SelectField label="Tax Regime Election" value={draft.regime === 'old' ? 'OLD' : 'NEW'} onChange={(value) => { const next = value === 'OLD' ? 'old' : 'new'; onChange({ regime: next }); onRegimeChange(next); }} required><option value="NEW">New tax regime</option><option value="OLD">Old tax regime / opt out</option></SelectField>
    </div></div>
    <SectionHeading title="Seventh proviso to section 139(1)" description="Complete only when filing is triggered by expenditure, deposits, turnover, receipts, or TDS/TCS thresholds despite otherwise being below the income threshold." />
    <div style={CARD_STYLE}>
      {(itrForm === 'ITR-4' || itrForm === 'ITR-2') && <><CheckField label="Deposits in current accounts exceeded ₹1 crore" checked={filing.seventhProviso.depositExceedsOneCrore} onChange={(checked) => updateFiling({ seventhProviso: { ...filing.seventhProviso, depositExceedsOneCrore: checked } })} />{filing.seventhProviso.depositExceedsOneCrore && <Field label="Aggregate current-account deposits (₹)" value={moneyValue(filing.seventhProviso.depositAmount)} onChange={(value) => updateFiling({ seventhProviso: { ...filing.seventhProviso, depositAmount: parseMoney(value) } })} type="number" required />}</>}
      <CheckField label="Foreign-travel expenditure exceeded ₹2 lakh" checked={filing.seventhProviso.foreignTravel} onChange={(checked) => updateFiling({ seventhProviso: { ...filing.seventhProviso, foreignTravel: checked } })} />
      {filing.seventhProviso.foreignTravel && <Field label="Foreign-travel expenditure (₹)" value={moneyValue(filing.seventhProviso.foreignTravelAmount)} onChange={(value) => updateFiling({ seventhProviso: { ...filing.seventhProviso, foreignTravelAmount: parseMoney(value) } })} type="number" required />}
      <CheckField label="Electricity expenditure exceeded ₹1 lakh" checked={filing.seventhProviso.electricityExpenditure} onChange={(checked) => updateFiling({ seventhProviso: { ...filing.seventhProviso, electricityExpenditure: checked } })} />
      {filing.seventhProviso.electricityExpenditure && <Field label="Electricity expenditure (₹)" value={moneyValue(filing.seventhProviso.electricityExpenditureAmount)} onChange={(value) => updateFiling({ seventhProviso: { ...filing.seventhProviso, electricityExpenditureAmount: parseMoney(value) } })} type="number" required />}
      <CheckField label="Other clause-(iv) threshold applies" checked={filing.seventhProviso.otherClauseIV} onChange={(checked) => updateFiling({ seventhProviso: { ...filing.seventhProviso, otherClauseIV: checked } })} />
      {filing.seventhProviso.otherClauseIV && <div style={{ marginTop: 12 }}>
        {filing.seventhProviso.clauseIVDetails.map((row, index) => <div key={row.id} style={{ ...GRID_STYLE, marginBottom: 10 }}>
          <SelectField label={`Clause ${index + 1} nature`} value={row.nature} onChange={(value) => updateFiling({ seventhProviso: { ...filing.seventhProviso, clauseIVDetails: filing.seventhProviso.clauseIVDetails.map((item) => item.id === row.id ? { ...item, nature: value as typeof row.nature } : item) } })} required>
            {(itrForm === 'ITR-4' ? ['1', '2', '3', '4'] : ['1', '2']).map((code) => <option key={code} value={code}>Nature {code}</option>)}
          </SelectField>
          <Field label={`Clause ${index + 1} amount (₹)`} value={moneyValue(row.amount)} onChange={(value) => updateFiling({ seventhProviso: { ...filing.seventhProviso, clauseIVDetails: filing.seventhProviso.clauseIVDetails.map((item) => item.id === row.id ? { ...item, amount: parseMoney(value) } : item) } })} type="number" required />
          <button type="button" onClick={() => updateFiling({ seventhProviso: { ...filing.seventhProviso, clauseIVDetails: filing.seventhProviso.clauseIVDetails.filter((item) => item.id !== row.id) } })}>Remove</button>
        </div>)}
        <button type="button" onClick={() => updateFiling({ seventhProviso: { ...filing.seventhProviso, clauseIVDetails: [...filing.seventhProviso.clauseIVDetails, { id: `seventh-${Date.now()}`, nature: '1', amount: 0 }] } })}>Add clause detail</button>
      </div>}
    </div>
    {itrForm === 'ITR-4' && <><SectionHeading title="Form 10-IEA" description="Enter the exact prior-year and current-year regime-election filing history." /><div style={CARD_STYLE}><div style={GRID_STYLE}>
      <SelectField label="Earlier AY old-regime Form 10-IEA" value={filing.form10IEAEarlierAYOldRegime} onChange={(value) => updateFiling({ form10IEAEarlierAYOldRegime: value as Filing['form10IEAEarlierAYOldRegime'] })}><option value="NA">Not applicable</option><option value="Y">Yes</option><option value="N">No</option></SelectField>
      {filing.form10IEAEarlierAYOldRegime === 'Y' && <SelectField label="Old-regime Form 10-IEA AY" value={filing.form10IEAAssessmentYear} onChange={(value) => updateFiling({ form10IEAAssessmentYear: value as Filing['form10IEAAssessmentYear'] })} required><option value="">Select AY</option><option value="2024-25">2024-25</option><option value="2025-26">2025-26</option></SelectField>}
      {filing.form10IEAEarlierAYOldRegime === 'Y' && <Field label="Earlier old-regime acknowledgement" value={filing.form10IEAEarlierAYAckOldRegime} onChange={(value) => updateFiling({ form10IEAEarlierAYAckOldRegime: value.replace(/\D/g, '').slice(0, 15) })} pattern="[0-9]{15}" maxLength={15} required />}
      <SelectField label="Earlier AY new-regime withdrawal" value={filing.form10IEAEarlierAYNewRegime} onChange={(value) => updateFiling({ form10IEAEarlierAYNewRegime: value as Filing['form10IEAEarlierAYNewRegime'] })}><option value="N">No</option><option value="Y">Yes</option></SelectField>
      {filing.form10IEAEarlierAYNewRegime === 'Y' && <SelectField label="New-regime withdrawal AY" value={filing.form10IEANewRegimeAssessmentYear} onChange={(value) => updateFiling({ form10IEANewRegimeAssessmentYear: value as Filing['form10IEANewRegimeAssessmentYear'] })} required><option value="">Select AY</option><option value="2025-26">2025-26</option></SelectField>}
      {filing.form10IEAEarlierAYNewRegime === 'Y' && <Field label="Earlier new-regime acknowledgement" value={filing.form10IEAEarlierAYAckNewRegime} onChange={(value) => updateFiling({ form10IEAEarlierAYAckNewRegime: value.replace(/\D/g, '').slice(0, 15) })} pattern="[0-9]{15}" maxLength={15} required />}
      <CheckField label="Filed Form 10-IEA for current AY new regime" checked={filing.form10IEACurrentAYNewRegime} onChange={(checked) => updateFiling({ form10IEACurrentAYNewRegime: checked })} />
      {filing.form10IEACurrentAYNewRegime && <Field label="Current AY new-regime filing date" value={filing.form10IEACurrentAYNewRegimeDate || ''} onChange={(value) => updateFiling({ form10IEACurrentAYNewRegimeDate: value || null })} type="date" required />}
      {filing.form10IEACurrentAYNewRegime && <Field label="Current AY new-regime acknowledgement" value={filing.form10IEACurrentAYNewRegimeAck} onChange={(value) => updateFiling({ form10IEACurrentAYNewRegimeAck: value.replace(/\D/g, '').slice(0, 15) })} pattern="[0-9]{15}" maxLength={15} required />}
      <CheckField label="Filed Form 10-IEA for current AY old regime" checked={filing.form10IEACurrentAYOldRegime} onChange={(checked) => updateFiling({ form10IEACurrentAYOldRegime: checked })} />
      {filing.form10IEACurrentAYOldRegime && <Field label="Current AY old-regime filing date" value={filing.form10IEACurrentAYOldRegimeDate || ''} onChange={(value) => updateFiling({ form10IEACurrentAYOldRegimeDate: value || null })} type="date" required />}
      {filing.form10IEACurrentAYOldRegime && <Field label="Current AY old-regime acknowledgement" value={filing.form10IEACurrentAYOldRegimeAck} onChange={(value) => updateFiling({ form10IEACurrentAYOldRegimeAck: value.replace(/\D/g, '').slice(0, 15) })} pattern="[0-9]{15}" maxLength={15} required />}
    </div></div></>}
    {itrForm === 'ITR-2' && <><SectionHeading title="Other ITR-2 declarations" description="FII/FPI status, SEBI registration, and Legal Entity Identifier." /><div style={CARD_STYLE}><div style={GRID_STYLE}>
      <CheckField label="Assessee is a Foreign Institutional Investor / Foreign Portfolio Investor (FII/FPI)" checked={filing.isFiiFpi} onChange={(checked) => updateFiling({ isFiiFpi: checked })} />
      {filing.isFiiFpi && <Field label="SEBI registration number" value={filing.sebiRegistrationNumber} onChange={(value) => updateFiling({ sebiRegistrationNumber: value.toUpperCase() })} required pattern="IN[A-Z]{2}FP[0-9]{6}" maxLength={11} help="Format: IN followed by 2 letters, FP, then 6 digits." />}
      <Field label="Legal Entity Identifier (LEI)" value={filing.leiNumber} onChange={(value) => updateFiling({ leiNumber: value.toUpperCase().slice(0, 20) })} maxLength={20} help="Required by CBDT instructions only when the refund claimed is ₹50 crore or more." />
      <CheckField label="Governed by Portuguese Civil Code under Section 5A" checked={filing.portugueseCivilCodeApplies} onChange={(checked) => updateFiling({ portugueseCivilCodeApplies: checked })} />
      <Field label="LEI valid upto date" value={filing.leiValidUptoDate || ''} onChange={(value) => updateFiling({ leiValidUptoDate: value || null })} type="date" />
    </div></div></>}
    {itrForm === 'ITR-2' && (personal.residentialStatus || 'ROR') !== 'ROR' && <><SectionHeading title="Residential status details" description="Basis, day counts, and jurisdiction of residence supporting the NRI/RNOR classification above." /><div style={CARD_STYLE}><div style={GRID_STYLE}>
      <SelectField label="Basis for residential status (Section 6)" value={filing.conditionsResStatus} onChange={(value) => updateFiling({ conditionsResStatus: value as Filing['conditionsResStatus'] })}>
        <option value="">-- Select basis --</option>
        <option value="1">1 — 182 days or more in India this year [6(1)(a)]</option>
        <option value="2">2 — 60+ days this year and 365+ days in preceding 4 years [6(1)(c)]</option>
        <option value="3">3 — Non-resident in 9 of the preceding 10 years [6(6)(a)]</option>
        <option value="4">4 — In India 729 days or less in preceding 7 years [6(6)(a)]</option>
        <option value="5">5 — Non-resident during the previous year</option>
        <option value="6">6 — Citizen/PIO visiting India, income &gt;₹15L, 120-181 days [6(6)(c)]</option>
        <option value="7">7 — Citizen, income &gt;₹15L, not liable to tax elsewhere [6(6)(d)/6(1A)]</option>
        <option value="8">8 — Citizen, crew member of Indian ship [Expl. 1(a) of 6(1)(c)]</option>
        <option value="9">9 — Citizen/PIO visiting India [Expl. 1(b) of 6(1)(c)]</option>
      </SelectField>
      <Field label="Total days stayed in India this previous year" value={filing.totalStayIndiaPrevYr ?? ''} onChange={(value) => updateFiling({ totalStayIndiaPrevYr: value === '' ? null : Math.max(0, Math.min(365, Number(value) || 0)) })} type="number" min={0} max={365} inputMode="numeric" />
      <Field label="Total days stayed in India in preceding 4 years" value={filing.totalStayIndia4PrecYr ?? ''} onChange={(value) => updateFiling({ totalStayIndia4PrecYr: value === '' ? null : Math.max(0, Math.min(1461, Number(value) || 0)) })} type="number" min={0} max={1461} inputMode="numeric" />
      {(personal.residentialStatus || 'ROR') === 'RNOR' && <CheckField label="Claiming Section 115H benefit (continued special-rate treatment for an NRI who becomes resident)" checked={filing.benefitUs115H} onChange={(checked) => updateFiling({ benefitUs115H: checked })} />}
      {filing.benefitUs115H && <div style={{ marginTop: 4, color: 'var(--text-muted)', fontSize: 11 }}>Available only for a resident taxpayer who was formerly non-resident.</div>}
    </div>
    <div style={{ marginTop: 16 }}>
      <h4 style={{ margin: '0 0 10px', fontSize: 13 }}>Jurisdiction(s) of residence</h4>
      {filing.jurisdictionResidenceEntries.map((row, index) => <div key={row.id} style={{ ...GRID_STYLE, marginBottom: 10 }}>
        <SelectField label={`Jurisdiction ${index + 1} country`} value={row.jurisdictionCode} onChange={(value) => updateFiling({ jurisdictionResidenceEntries: filing.jurisdictionResidenceEntries.map((item) => item.id === row.id ? { ...item, jurisdictionCode: value } : item) })} required>
          <option value="">-- Select country --</option>
          {ITD_COUNTRY_CODES.map((country) => <option key={country.value} value={country.value}>{country.value} — {country.label}</option>)}
        </SelectField>
        <Field label={`Jurisdiction ${index + 1} TIN`} value={row.tin} onChange={(value) => updateFiling({ jurisdictionResidenceEntries: filing.jurisdictionResidenceEntries.map((item) => item.id === row.id ? { ...item, tin: value } : item) })} required maxLength={75} />
        <button type="button" onClick={() => updateFiling({ jurisdictionResidenceEntries: filing.jurisdictionResidenceEntries.filter((item) => item.id !== row.id) })}>Remove</button>
      </div>)}
      <button type="button" onClick={() => updateFiling({ jurisdictionResidenceEntries: [...filing.jurisdictionResidenceEntries, { id: `jurisdiction-${Date.now()}`, jurisdictionCode: '', tin: '' }] })}>Add jurisdiction</button>
    </div></div></>}
    {itrForm === 'ITR-2' && <><SectionHeading title="Director and unlisted-equity disclosures" description="Company directorships held and unlisted equity shares held at any time during the year." /><div style={CARD_STYLE}>
      <CheckField label="Assessee was a director in a company at any time during the year" checked={bool(personal.isDirector)} onChange={(checked) => updatePersonal({ isDirector: checked, companyDirectorEntries: checked ? personal.companyDirectorEntries : [] })} />
      {bool(personal.isDirector) && <div style={{ marginTop: 12 }}>
        {personal.companyDirectorEntries.map((row, index) => <div key={row.id} style={{ ...GRID_STYLE, marginBottom: 10 }}>
          <Field label={`Company ${index + 1} name`} value={row.companyName} onChange={(value) => updatePersonal({ companyDirectorEntries: personal.companyDirectorEntries.map((item) => item.id === row.id ? { ...item, companyName: value } : item) })} required maxLength={125} />
          <SelectField label={`Company ${index + 1} type`} value={row.companyType} onChange={(value) => updatePersonal({ companyDirectorEntries: personal.companyDirectorEntries.map((item) => item.id === row.id ? { ...item, companyType: value as CompanyDirectorEntry['companyType'] } : item) })} required>
            <option value="D">Domestic</option>
            <option value="F">Foreign</option>
          </SelectField>
          <Field label={`Company ${index + 1} PAN`} value={row.pan} onChange={(value) => updatePersonal({ companyDirectorEntries: personal.companyDirectorEntries.map((item) => item.id === row.id ? { ...item, pan: value.toUpperCase() } : item) })} pattern={PAN_PATTERN} maxLength={10} />
          <SelectField label={`Company ${index + 1} shares`} value={row.sharesType} onChange={(value) => updatePersonal({ companyDirectorEntries: personal.companyDirectorEntries.map((item) => item.id === row.id ? { ...item, sharesType: value as CompanyDirectorEntry['sharesType'] } : item) })} required>
            <option value="L">Listed</option>
            <option value="U">Unlisted</option>
          </SelectField>
          <Field label={`Company ${index + 1} DIN`} value={row.din} onChange={(value) => updatePersonal({ companyDirectorEntries: personal.companyDirectorEntries.map((item) => item.id === row.id ? { ...item, din: value.replace(/\D/g, '').slice(0, 8) } : item) })} pattern="[0-9]{8}" maxLength={8} inputMode="numeric" />
          <button type="button" onClick={() => updatePersonal({ companyDirectorEntries: personal.companyDirectorEntries.filter((item) => item.id !== row.id) })}>Remove</button>
        </div>)}
        <button type="button" onClick={() => updatePersonal({ companyDirectorEntries: [...personal.companyDirectorEntries, { id: `director-${Date.now()}`, companyName: '', companyType: 'D', pan: '', sharesType: 'L', din: '' }] })}>Add company</button>
      </div>}
      <div style={{ marginTop: 20, paddingTop: 16, borderTop: '1px solid var(--border)' }}>
        <CheckField label="Assessee held unlisted equity shares at any time during the year" checked={bool(personal.holdsUnlistedShares)} onChange={(checked) => updatePersonal({ holdsUnlistedShares: checked, unlistedEquityEntries: checked ? personal.unlistedEquityEntries : [] })} />
        {bool(personal.holdsUnlistedShares) && <div style={{ marginTop: 12 }}>
          {personal.unlistedEquityEntries.map((row, index) => {
            const updateRow = (patch: Partial<UnlistedEquityEntry>): void => updatePersonal({ unlistedEquityEntries: personal.unlistedEquityEntries.map((item) => item.id === row.id ? { ...item, ...patch } : item) });
            return <div key={row.id} style={{ ...GRID_STYLE, marginBottom: 16, paddingBottom: 16, borderBottom: '1px solid var(--border)' }}>
              <Field label={`Company ${index + 1} name`} value={row.companyName} onChange={(value) => updateRow({ companyName: value })} required maxLength={125} />
              <SelectField label={`Company ${index + 1} type`} value={row.companyType} onChange={(value) => updateRow({ companyType: value as CompanyType })} required>
                <option value="D">Domestic</option>
                <option value="F">Foreign</option>
              </SelectField>
              <Field label={`Company ${index + 1} PAN`} value={row.pan} onChange={(value) => updateRow({ pan: value.toUpperCase() })} pattern={PAN_PATTERN} maxLength={10} />
              <Field label="Opening balance — shares" value={moneyValue(row.openingShares)} onChange={(value) => updateRow({ openingShares: parseMoney(value) })} type="number" min={0} required />
              <Field label="Opening balance — cost (₹)" value={moneyValue(row.openingCost)} onChange={(value) => updateRow({ openingCost: parseMoney(value) })} type="number" min={0} required />
              <Field label="Acquired during year — shares" value={moneyValue(row.acquiredShares)} onChange={(value) => updateRow({ acquiredShares: parseMoney(value) })} type="number" min={0} />
              <Field label="Date of subscription / purchase" value={row.dateOfAcquisition || ''} onChange={(value) => updateRow({ dateOfAcquisition: value || null })} type="date" />
              <Field label="Face value per share (₹)" value={moneyValue(row.faceValuePerShare)} onChange={(value) => updateRow({ faceValuePerShare: parseMoney(value) })} type="number" min={0} />
              <Field label="Issue price per share (₹)" value={moneyValue(row.issuePricePerShare)} onChange={(value) => updateRow({ issuePricePerShare: parseMoney(value) })} type="number" min={0} />
              <Field label="Purchase price per share (₹)" value={moneyValue(row.purchasePricePerShare)} onChange={(value) => updateRow({ purchasePricePerShare: parseMoney(value) })} type="number" min={0} />
              <Field label="Transferred during year — shares" value={moneyValue(row.transferredShares)} onChange={(value) => updateRow({ transferredShares: parseMoney(value) })} type="number" min={0} />
              <Field label="Sale consideration on transfer (₹)" value={moneyValue(row.transferSaleConsideration)} onChange={(value) => updateRow({ transferSaleConsideration: parseMoney(value) })} type="number" min={0} />
              <Field label="Closing balance — shares" value={moneyValue(row.closingShares)} onChange={(value) => updateRow({ closingShares: parseMoney(value) })} type="number" min={0} required />
              <Field label="Closing balance — cost (₹)" value={moneyValue(row.closingCost)} onChange={(value) => updateRow({ closingCost: parseMoney(value) })} type="number" min={0} required />
              <button type="button" onClick={() => updatePersonal({ unlistedEquityEntries: personal.unlistedEquityEntries.filter((item) => item.id !== row.id) })}>Remove</button>
            </div>;
          })}
          <button type="button" onClick={() => updatePersonal({ unlistedEquityEntries: [...personal.unlistedEquityEntries, { id: `equity-${Date.now()}`, companyName: '', companyType: 'D', pan: '', openingShares: 0, openingCost: 0, acquiredShares: 0, dateOfAcquisition: null, faceValuePerShare: 0, issuePricePerShare: 0, purchasePricePerShare: 0, transferredShares: 0, transferSaleConsideration: 0, closingShares: 0, closingCost: 0 }] })}>Add company</button>
        </div>}
      </div>
    </div></>}
    <SectionHeading title="Verification" description="The declaration must be accepted before official CBDT JSON generation." />
    <div style={CARD_STYLE}><div style={GRID_STYLE}>
      <SelectField label="Verification capacity" value={verification.capacity} onChange={(value) => updateVerification({ capacity: value as Verification['capacity'] })} required><option value="SELF">Self</option><option value="REPRESENTATIVE">Representative assessee</option>{itrForm === 'ITR-2' && personal.assesseeStatus === 'H' && <option value="KARTA">Karta</option>}{itrForm === 'ITR-4' && <option value="KARTA">Karta</option>}{itrForm === 'ITR-4' && <option value="PARTNER">Partner</option>}</SelectField>
      <Field label="Place of verification" value={verification.place} onChange={(value) => updateVerification({ place: value })} required maxLength={50} />
      <Field label="Verification date" value={verification.date || ''} onChange={(value) => updateVerification({ date: value || null })} type="date" required />
    </div>{verification.capacity === 'REPRESENTATIVE' && <div style={{ ...GRID_STYLE, marginTop: 16 }}>
      <Field label="Representative name" value={filing.representative?.name || ''} onChange={(value) => updateFiling({ representative: { name: value, email: filing.representative?.email || '', mobileCountryCode: filing.representative?.mobileCountryCode || '91', mobile: filing.representative?.mobile || '' } })} required maxLength={125} />
      <Field label="Representative email" value={filing.representative?.email || ''} onChange={(value) => updateFiling({ representative: { name: filing.representative?.name || '', email: value, mobileCountryCode: filing.representative?.mobileCountryCode || '91', mobile: filing.representative?.mobile || '' } })} required type="email" maxLength={125} />
      <Field label="Representative mobile country code" value={filing.representative?.mobileCountryCode || '91'} onChange={(value) => updateFiling({ representative: { name: filing.representative?.name || '', email: filing.representative?.email || '', mobileCountryCode: value.replace(/\D/g, '').slice(0, 5), mobile: filing.representative?.mobile || '' } })} required pattern="[0-9]{1,5}" maxLength={5} />
      <Field label="Representative mobile number" value={filing.representative?.mobile || ''} onChange={(value) => updateFiling({ representative: { name: filing.representative?.name || '', email: filing.representative?.email || '', mobileCountryCode: filing.representative?.mobileCountryCode || '91', mobile: value.replace(/\D/g, '').slice(0, 10) } })} required pattern="[1-9][0-9]{4,9}" maxLength={10} />
    </div>}<label style={{ display: 'flex', alignItems: 'flex-start', gap: 8, marginTop: 16, fontSize: 13 }}><input type="checkbox" checked={bool(verification.declarationAccepted)} onChange={(event) => updateVerification({ declarationAccepted: event.target.checked })} />I declare that the information given in this return and its schedules is correct and complete.</label></div>
    <SectionHeading title="Tax Return Preparer (TRP)" description="Optional. Fill only if a Tax Return Preparer prepared this return." />
    <div style={CARD_STYLE}><SelectField label="Was this return prepared by a TRP?" value={taxReturnPreparer.used ? 'Y' : 'N'} onChange={(value) => onChange({ taxReturnPreparer: { used: value === 'Y' } })} required><option value="N">No</option><option value="Y">Yes</option></SelectField>{taxReturnPreparer.used && <div style={{ ...GRID_STYLE, marginTop: 16 }}><Field label="TRP identification number" value={taxReturnPreparer.identificationNumber} onChange={(value) => onChange({ taxReturnPreparer: { identificationNumber: value.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 10) } })} required pattern="(T[0-9]{9}|[0-9]{6})" maxLength={10} help="Enter T followed by 9 digits, or a 6-digit legacy identifier." /><Field label="TRP name" value={taxReturnPreparer.name} onChange={(value) => onChange({ taxReturnPreparer: { name: value } })} required maxLength={125} /><Field label="Reimbursement from government (₹)" value={moneyValue(taxReturnPreparer.reimbursementFromGovernment)} onChange={(value) => onChange({ taxReturnPreparer: { reimbursementFromGovernment: parseMoney(value) } })} type="number" min={0} max={99999999999999} inputMode="numeric" /></div>}</div>
    <SectionHeading title="Bank accounts and refund" description="Add all reportable accounts. Select exactly one refund account whenever a refund account is required." />
    <div style={CARD_STYLE}><BankAccountManager data={{ accounts: draft.bankAccounts }} onChange={onBanksChange} /></div>
    <div style={{ padding: 12, borderRadius: 6, background: 'var(--info-bg)', color: 'var(--info)', fontSize: 12 }}>Bank accounts are stored in the canonical draft and sent directly to the v2 repository.</div>
  </div>;
}
