import React, { useMemo } from 'react';
import { BankAccountManager, type BankAccountData } from './BankAccountManager';
import { ITD_COUNTRY_CODES } from '../constants/itdCountryCodes';

export type SupportedItrForm = 'ITR-1' | 'ITR-2' | 'ITR-3' | 'ITR-4';
type FormData = Record<string, unknown>;

interface PersonalInfoTabProps {
  formData: FormData;
  itrForm: SupportedItrForm;
  onChange: (next: FormData) => void;
  onBanksChange: (data: BankAccountData) => void;
  onRegimeChange: (regime: 'old' | 'new') => void;
}

interface FieldProps {
  label: string;
  value: string | number | undefined | null;
  onChange: (value: string) => void;
  type?: React.HTMLInputTypeAttribute;
  required?: boolean;
  pattern?: string;
  maxLength?: number;
  inputMode?: React.HTMLAttributes<HTMLInputElement>['inputMode'];
  help?: string;
  disabled?: boolean;
}

interface AddressData {
  residenceNo: string;
  residenceName: string;
  roadOrStreet: string;
  localityOrArea: string;
  cityOrTownOrDistrict: string;
  stateCode: string;
  countryCode: string;
  pinCode: string;
  zipCode: string;
}

interface DirectorDetail {
  companyName: string;
  companyType: 'D' | 'F' | '';
  companyPan: string;
  din: string;
  shareType: 'L' | 'U' | '';
}

interface PartnerFirmDetail {
  firmName: string;
  firmPan: string;
}

interface UnlistedShareHolding {
  companyName: string;
  companyType: 'D' | 'F' | '';
  companyPan: string;
  openingNumberOfShares: string;
  openingCostOfAcquisition: string;
  acquiredDuringYear: string;
  acquisitionDate: string;
  faceValuePerShare: string;
  issuePricePerShare: string;
  purchasePricePerShare: string;
  transferredDuringYear: string;
  transferSaleConsideration: string;
  closingNumberOfShares: string;
  closingCostOfAcquisition: string;
}

const CARD_STYLE: React.CSSProperties = { background: '#fff', border: '1px solid var(--border)', borderRadius: 8, padding: 18, marginBottom: 16 };
const LABEL_STYLE: React.CSSProperties = { display: 'block', marginBottom: 6, fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)' };
const INPUT_STYLE: React.CSSProperties = { width: '100%', boxSizing: 'border-box', padding: '8px 10px', border: '1px solid var(--border)', borderRadius: 6, fontSize: 13, background: '#fff' };
const GRID_STYLE: React.CSSProperties = { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', gap: 14 };
const PAN_PATTERN = '[A-Z]{5}[0-9]{4}[A-Z]';
const IFSC_PATTERN = '[A-Z]{4}0[A-Z0-9]{6}';
const PIN_PATTERN = '[1-9][0-9]{5}';
const ACK_PATTERN = '[0-9]{15}';

const INDIAN_STATES = [
  ['01', 'Andaman & Nicobar Islands'], ['02', 'Andhra Pradesh'], ['03', 'Arunachal Pradesh'], ['04', 'Assam'], ['05', 'Bihar'], ['06', 'Chandigarh'], ['07', 'Dadra & Nagar Haveli'], ['08', 'Daman & Diu'], ['09', 'Delhi'], ['10', 'Goa'], ['11', 'Gujarat'], ['12', 'Haryana'], ['13', 'Himachal Pradesh'], ['14', 'Jammu & Kashmir'], ['15', 'Karnataka'], ['16', 'Kerala'], ['17', 'Lakshadweep'], ['18', 'Madhya Pradesh'], ['19', 'Maharashtra'], ['20', 'Manipur'], ['21', 'Meghalaya'], ['22', 'Mizoram'], ['23', 'Nagaland'], ['24', 'Odisha'], ['25', 'Puducherry'], ['26', 'Punjab'], ['27', 'Rajasthan'], ['28', 'Sikkim'], ['29', 'Tamil Nadu'], ['30', 'Tripura'], ['31', 'Uttar Pradesh'], ['32', 'West Bengal'], ['33', 'Chhattisgarh'], ['34', 'Uttarakhand'], ['35', 'Jharkhand'], ['36', 'Telangana'], ['37', 'Ladakh'], ['99', 'Outside India'],
] as const;

function text(value: unknown): string {
  return typeof value === 'string' || typeof value === 'number' ? String(value) : '';
}

function bool(value: unknown): boolean {
  return value === true || value === 'Y';
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function Field({ label, value, onChange, type = 'text', required = false, pattern, maxLength, inputMode, help, disabled = false }: FieldProps): React.JSX.Element {
  const id = `personal-${label.replace(/[^a-z0-9]+/gi, '-').toLowerCase()}`;
  return <div>
    <label htmlFor={id} style={LABEL_STYLE}>{label}{required ? ' *' : ''}</label>
    <input id={id} type={type} value={value ?? ''} onChange={(event) => onChange(event.target.value)} required={required} pattern={pattern} maxLength={maxLength} inputMode={inputMode} disabled={disabled} aria-describedby={help ? `${id}-help` : undefined} style={{ ...INPUT_STYLE, textTransform: pattern === PAN_PATTERN || pattern === IFSC_PATTERN ? 'uppercase' : undefined }} />
    {help && <div id={`${id}-help`} style={{ marginTop: 4, color: 'var(--text-muted)', fontSize: 11 }}>{help}</div>}
  </div>;
}

function SelectField({ label, value, onChange, children, required = false }: { label: string; value: string; onChange: (value: string) => void; children: React.ReactNode; required?: boolean }): React.JSX.Element {
  const id = `personal-${label.replace(/[^a-z0-9]+/gi, '-').toLowerCase()}`;
  return <div><label htmlFor={id} style={LABEL_STYLE}>{label}{required ? ' *' : ''}</label><select id={id} value={value} required={required} onChange={(event) => onChange(event.target.value)} style={INPUT_STYLE}>{children}</select></div>;
}

function SectionHeading({ title, description }: { title: string; description: string }): React.JSX.Element {
  return <div style={{ marginBottom: 16 }}><h3 style={{ margin: 0, fontSize: 16, color: 'var(--text-primary)' }}>{title}</h3><p style={{ margin: '5px 0 0', fontSize: 12, color: 'var(--text-muted)' }}>{description}</p></div>;
}

function BlankAddress(): AddressData {
  return { residenceNo: '', residenceName: '', roadOrStreet: '', localityOrArea: '', cityOrTownOrDistrict: '', stateCode: '', countryCode: '91', pinCode: '', zipCode: '' };
}

/**
 * Renders the schema-oriented personal-information workflow for ITR returns.
 *
 * The component keeps legacy flat payload fields synchronized for the current
 * backend while storing new conditional data in structured objects. A return
 * may remain a draft with incomplete values; native field constraints provide
 * immediate feedback and server validation remains authoritative.
 */
export function PersonalInfoTab({ formData, itrForm, onChange, onBanksChange, onRegimeChange }: PersonalInfoTabProps): React.JSX.Element {
  const advancedForm = itrForm === 'ITR-2' || itrForm === 'ITR-3';
  const filingSection = text(formData.filingSection || '139(1)');
  const itr1FilingSections = new Set(['139(1)', '139(4)']);
  const selectedRegime = text(formData.regime || formData.taxRegime || (text(formData.optOutNewTaxRegime) === 'Y' ? 'old' : 'new')).toLowerCase() === 'old' ? 'OLD' : 'NEW';
  const primaryAddress = useMemo<AddressData>(() => ({
    residenceNo: text(formData.flatNo), residenceName: text(formData.premises), roadOrStreet: text(formData.road), localityOrArea: text(formData.area), cityOrTownOrDistrict: text(formData.city), stateCode: text(formData.state), countryCode: text(formData.country || '91'), pinCode: text(formData.pincode), zipCode: text(formData.zipCode),
  }), [formData]);
  const alternateAddress = (formData.alternateAddress && typeof formData.alternateAddress === 'object' ? formData.alternateAddress : BlankAddress()) as AddressData;
  const directors = Array.isArray(formData.directorDetails) ? formData.directorDetails as DirectorDetail[] : [];
  const partnerFirms = Array.isArray(formData.partnerFirmDetails) ? formData.partnerFirmDetails as PartnerFirmDetail[] : [];
  const holdings = Array.isArray(formData.unlistedShareHoldings) ? formData.unlistedShareHoldings as UnlistedShareHolding[] : [];
  const patch = (values: FormData): void => onChange({ ...formData, ...values });
  const updatePrimaryAddress = (key: keyof AddressData, value: string): void => {
    const next = { ...primaryAddress, [key]: value };
    patch({
      flatNo: next.residenceNo, premises: next.residenceName, road: next.roadOrStreet, area: next.localityOrArea,
      city: next.cityOrTownOrDistrict, state: next.stateCode, country: next.countryCode, pincode: next.pinCode, zipCode: next.zipCode,
    });
  };
  const updateAlternateAddress = (key: keyof AddressData, value: string): void => patch({ alternateAddress: { ...alternateAddress, [key]: value } });
  const setDob = (dob: string): void => {
    const date = new Date(`${dob}T00:00:00`);
    const reference = new Date('2026-03-31T00:00:00');
    let age = reference.getFullYear() - date.getFullYear();
    if (date > reference || (reference.getMonth() < date.getMonth()) || (reference.getMonth() === date.getMonth() && reference.getDate() < date.getDate())) age -= 1;
    patch({ dob, age: Number.isFinite(age) && age >= 0 ? age : 0 });
  };
  const renderAddressFields = (address: AddressData, update: (key: keyof AddressData, value: string) => void, prefix: string): React.JSX.Element => {
    const india = address.countryCode === '91';
    return <div style={GRID_STYLE}>
      <Field label={`${prefix} Flat / Door / Block No.`} value={address.residenceNo} onChange={(value) => update('residenceNo', value)} required maxLength={50} />
      <Field label={`${prefix} Premises / Building / Village`} value={address.residenceName} onChange={(value) => update('residenceName', value)} maxLength={50} />
      <Field label={`${prefix} Road / Street / Post Office`} value={address.roadOrStreet} onChange={(value) => update('roadOrStreet', value)} maxLength={50} />
      <Field label={`${prefix} Area / Locality`} value={address.localityOrArea} onChange={(value) => update('localityOrArea', value)} required maxLength={50} />
      <Field label={`${prefix} Town / City / District`} value={address.cityOrTownOrDistrict} onChange={(value) => update('cityOrTownOrDistrict', value)} required maxLength={50} />
      <SelectField label={`${prefix} Country`} value={address.countryCode} onChange={(value) => update('countryCode', value)} required>{ITD_COUNTRY_CODES.map((country) => <option key={country.value} value={country.value}>{country.value} — {country.label}</option>)}</SelectField>
      <SelectField label={`${prefix} State`} value={address.stateCode} onChange={(value) => update('stateCode', value)} required={india}><option value="">-- Select state --</option>{INDIAN_STATES.map(([code, label]) => <option key={code} value={code}>{code} — {label}</option>)}</SelectField>
      {india ? <Field label={`${prefix} PIN Code`} value={address.pinCode} onChange={(value) => update('pinCode', value.replace(/\D/g, '').slice(0, 6))} required pattern={PIN_PATTERN} maxLength={6} inputMode="numeric" help="Six digits; cannot start with zero." /> : <Field label={`${prefix} ZIP / Postal Code`} value={address.zipCode} onChange={(value) => update('zipCode', value)} required maxLength={20} />}
    </div>;
  };

  return <div>
    <SectionHeading title="Identity and contact" description="Enter the identity, communication and statutory profile exactly as registered. PAN and date of birth are used for validation and age-based tax rules." />
      <div style={CARD_STYLE}><div style={GRID_STYLE}>
        <Field label="First Name" value={text(formData.firstName)} onChange={(value) => patch({ firstName: value, name: [value, text(formData.middleName), text(formData.surnameOrOrgName)].filter(Boolean).join(' ') })} maxLength={25} />
        <Field label="Middle Name" value={text(formData.middleName)} onChange={(value) => patch({ middleName: value, name: [text(formData.firstName), value, text(formData.surnameOrOrgName)].filter(Boolean).join(' ') })} maxLength={25} />
        <Field label="Surname / Organisation Name" value={text(formData.surnameOrOrgName || formData.name)} onChange={(value) => patch({ surnameOrOrgName: value, name: [text(formData.firstName), text(formData.middleName), value].filter(Boolean).join(' ') || value })} required maxLength={75} />
        <Field label="PAN" value={text(formData.pan)} onChange={(value) => patch({ pan: value.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 10) })} required pattern={PAN_PATTERN} maxLength={10} help="Format: ABCDE1234F." />
        <Field label="Aadhaar Number" value={text(formData.aadhaar)} onChange={(value) => patch({ aadhaar: value.replace(/\D/g, '').slice(0, 12) })} pattern="[0-9]{12}" maxLength={12} inputMode="numeric" help="Enter 12 digits when Aadhaar is available." />
        <Field label="Date of Birth / Formation" value={text(formData.dob)} onChange={setDob} type="date" required maxLength={10} />
        <Field label="Age as on 31 March 2026" value={text(formData.age)} onChange={() => undefined} disabled help="Calculated from date of birth; this field cannot be edited." />
        <SelectField label="Assessee Status" value={text(formData.status || 'Individual')} onChange={(value) => patch({ status: value })} required><option value="Individual">Individual</option><option value="HUF">HUF</option><option value="Firm">Firm</option><option value="AOP">AOP/BOI</option><option value="Company">Company</option></SelectField>
        <Field label="Father's Name" value={text(formData.fatherName)} onChange={(value) => patch({ fatherName: value })} required maxLength={125} />
        <SelectField label="Gender" value={text(formData.gender || 'M')} onChange={(value) => patch({ gender: value })} required><option value="M">Male</option><option value="F">Female</option><option value="T">Transgender</option></SelectField>
        <SelectField label="Marital Status" value={text(formData.maritalStatus || 'SINGLE')} onChange={(value) => patch({ maritalStatus: value })} required><option value="SINGLE">Single</option><option value="MARRIED">Married</option><option value="DIVORCED">Divorced</option><option value="WIDOWED">Widowed</option></SelectField>
        <Field label="Nationality" value={text(formData.nationality || 'INDIA')} onChange={(value) => patch({ nationality: value.toUpperCase() })} required maxLength={50} />
      </div></div>
      <div style={CARD_STYLE}><h4 style={{ marginTop: 0, fontSize: 14 }}>Contact details</h4><div style={GRID_STYLE}>
        <SelectField label="Mobile Country Code" value={text(formData.mobileCountryCode || '91')} onChange={(value) => patch({ mobileCountryCode: value })} required>{ITD_COUNTRY_CODES.map((country) => <option key={country.value} value={country.value}>+{country.value} — {country.label}</option>)}</SelectField>
        <Field label="Mobile Number" value={text(formData.mobile)} onChange={(value) => patch({ mobile: value.replace(/\D/g, '').slice(0, 15) })} required pattern="[0-9]{6,15}" maxLength={15} inputMode="tel" />
        <Field label="Primary Email Address" value={text(formData.email)} onChange={(value) => patch({ email: value.trim() })} type="email" required maxLength={125} />
        <SelectField label="Secondary Mobile Country Code" value={text(formData.secondaryMobileCountryCode || formData.mobileCountryCode || '91')} onChange={(value) => patch({ secondaryMobileCountryCode: value })}>{ITD_COUNTRY_CODES.map((country) => <option key={country.value} value={country.value}>+{country.value} — {country.label}</option>)}</SelectField>
        <Field label="Secondary Mobile Number" value={text(formData.secondaryMobile)} onChange={(value) => patch({ secondaryMobile: value.replace(/\D/g, '').slice(0, 15) })} pattern="[0-9]{5,10}" maxLength={10} inputMode="tel" />
        <Field label="Secondary Email Address" value={text(formData.secondaryEmail)} onChange={(value) => patch({ secondaryEmail: value.trim() })} type="email" maxLength={125} />
        <Field label="Telephone (STD-Number)" value={text(formData.telephone)} onChange={(value) => patch({ telephone: value.replace(/[^0-9-]/g, '').slice(0, 20) })} maxLength={20} inputMode="tel" />
      </div></div>
    <SectionHeading title="Primary and alternate address" description="Use the address at which statutory communication should be received. Postal-code rules change when the selected country is outside India." />
      <div style={CARD_STYLE}><h4 style={{ marginTop: 0, fontSize: 14 }}>Primary address for communication</h4>{renderAddressFields(primaryAddress, updatePrimaryAddress, 'Primary')}</div>
      <div style={CARD_STYLE}>
        <SelectField label="Is the correspondence address different from the primary address?" value={bool(formData.secondaryAddressDifferent) ? 'Y' : 'N'} onChange={(value) => patch({ secondaryAddressDifferent: value === 'Y', alternateAddress: value === 'Y' ? alternateAddress : BlankAddress() })} required><option value="N">No</option><option value="Y">Yes</option></SelectField>
        {bool(formData.secondaryAddressDifferent) && <div style={{ marginTop: 16 }}><h4 style={{ marginTop: 0, fontSize: 14 }}>Alternate correspondence address</h4>{renderAddressFields(alternateAddress, updateAlternateAddress, 'Alternate')}</div>}
      </div>
    <SectionHeading title="Filing status and return history" description="The selected filing section activates the original-return and notice details required to prevent invalid return metadata." />
      <div style={CARD_STYLE}><div style={GRID_STYLE}>
        <SelectField label="Return filed under section" value={filingSection} onChange={(value) => patch({ filingSection: value, returnFileSectionCode: value === '139(4)' ? 12 : 11, returnType: 'ORIGINAL' })} required><option value="139(1)">139(1) — On or before due date</option><option value="139(4)">139(4) — Belated return</option>{itrForm === 'ITR-1' && !itr1FilingSections.has(filingSection) && <option value={filingSection}>{filingSection} — unsupported for ITR-1 JSON generation</option>}{itrForm !== 'ITR-1' && <><option value="142(1)">142(1) — Notice response</option><option value="148">148 — Reassessment return</option><option value="153C">153C — Search-related return</option><option value="139(5)">139(5) — Revised return</option><option value="139(9)">139(9) — Defective-return response</option><option value="119(2)(b)">119(2)(b) — Condonation of delay</option></>}</SelectField>
        <Field label="ITR Filing Due Date" value={text(formData.itrFilingDueDate)} onChange={() => undefined} disabled help="System-calculated due date; administrative rules determine this value." />
        {(filingSection === '139(5)' || filingSection === '139(9)') && <><Field label="Original Return Acknowledgement Number" value={text(formData.originalAcknowledgementNumber)} onChange={(value) => patch({ originalAcknowledgementNumber: value.replace(/\D/g, '').slice(0, 15) })} required pattern={ACK_PATTERN} maxLength={15} inputMode="numeric" help="15-digit acknowledgement number." /><Field label="Original Return Filing Date" value={text(formData.originalFilingDate)} onChange={(value) => patch({ originalFilingDate: value })} type="date" required /></>}
        {['142(1)', '148', '153C', '139(9)'].includes(filingSection) && <><Field label="Notice / Order Number" value={text(formData.noticeNumber)} onChange={(value) => patch({ noticeNumber: value })} required maxLength={50} /><Field label="Notice / Order Date" value={text(formData.noticeDate)} onChange={(value) => patch({ noticeDate: value })} type="date" required /></>}
        <SelectField label="Employer Category" value={text(formData.employerCategory || 'OTH')} onChange={(value) => patch({ employerCategory: value })} required><option value="CGOV">Central Government</option><option value="SGOV">State Government</option><option value="PSU">Public Sector Undertaking</option><option value="PE">Pensioner</option><option value="PESG">State Government Pensioner</option><option value="PEPS">PSU Pensioner</option><option value="PEO">Other Pensioner</option><option value="OTH">Others</option><option value="NA">Not Applicable</option></SelectField>
        <SelectField label="Tax Regime Election" value={selectedRegime} onChange={(value) => { const nextRegime = value === 'OLD' ? 'old' : 'new'; patch({ regime: nextRegime, taxRegime: nextRegime, optOutNewTaxRegime: value === 'OLD' ? 'Y' : 'N' }); onRegimeChange(nextRegime); }} required><option value="NEW">New tax regime</option><option value="OLD">Old tax regime / opt out</option></SelectField>
        {selectedRegime === 'OLD' && <><Field label="Form 10-IEA Acknowledgement Number" value={text(formData.form10IEAAcknowledgementNumber)} onChange={(value) => patch({ form10IEAAcknowledgementNumber: value })} maxLength={50} /><Field label="Form 10-IEA Filing Date" value={text(formData.form10IEAFilingDate)} onChange={(value) => patch({ form10IEAFilingDate: value })} type="date" /></>}
      </div></div>
      <div style={CARD_STYLE}><h4 style={{ marginTop: 0, fontSize: 14 }}>Seventh proviso to section 139</h4><SelectField label="Is filing required because of a seventh-proviso condition?" value={bool(formData.seventhProviso139) ? 'Y' : 'N'} onChange={(value) => patch({ seventhProviso139: value === 'Y' })} required><option value="N">No</option><option value="Y">Yes</option></SelectField>{bool(formData.seventhProviso139) && <div style={{ ...GRID_STYLE, marginTop: 16 }}><Field label="Foreign Travel Expenditure" value={text(formData.foreignTravelExpenditure)} onChange={(value) => patch({ foreignTravelExpenditure: value.replace(/\D/g, '') })} inputMode="numeric" help="Enter aggregate expenditure; ₹2,00,000 or more is a statutory trigger." /><Field label="Electricity Expenditure" value={text(formData.electricityExpenditure)} onChange={(value) => patch({ electricityExpenditure: value.replace(/\D/g, '') })} inputMode="numeric" help="Enter aggregate expenditure; ₹1,00,000 or more is a statutory trigger." /><Field label="Other Applicable Clause Details" value={text(formData.seventhProvisoDetails)} onChange={(value) => patch({ seventhProvisoDetails: value })} maxLength={500} /></div>}</div>
      <div style={CARD_STYLE}><SelectField label="Representative assessee filing this return?" value={bool(formData.assesseRepFlg) ? 'Y' : 'N'} onChange={(value) => patch({ assesseRepFlg: value === 'Y', representativeAssessee: value === 'Y' ? formData.representativeAssessee || { countryCode: '91' } : {} })} required><option value="N">No</option><option value="Y">Yes</option></SelectField>{bool(formData.assesseRepFlg) && <div style={{ ...GRID_STYLE, marginTop: 16 }}><Field label="Representative Name" value={text((formData.representativeAssessee as Record<string, unknown>)?.name)} onChange={(value) => patch({ representativeAssessee: { ...(formData.representativeAssessee as Record<string, unknown>), name: value } })} required maxLength={125} /><Field label="Representative PAN" value={text((formData.representativeAssessee as Record<string, unknown>)?.pan)} onChange={(value) => patch({ representativeAssessee: { ...(formData.representativeAssessee as Record<string, unknown>), pan: value.toUpperCase().slice(0, 10) } })} required pattern={PAN_PATTERN} maxLength={10} /><Field label="Representative Email" value={text((formData.representativeAssessee as Record<string, unknown>)?.email)} onChange={(value) => patch({ representativeAssessee: { ...(formData.representativeAssessee as Record<string, unknown>), email: value } })} type="email" required /><SelectField label="Representative Mobile Country Code" value={text((formData.representativeAssessee as Record<string, unknown>)?.countryCode || '91')} onChange={(value) => patch({ representativeAssessee: { ...(formData.representativeAssessee as Record<string, unknown>), countryCode: value } })} required>{ITD_COUNTRY_CODES.map((country) => <option key={country.value} value={country.value}>+{country.value} — {country.label}</option>)}</SelectField><Field label="Representative Mobile" value={text((formData.representativeAssessee as Record<string, unknown>)?.mobile)} onChange={(value) => patch({ representativeAssessee: { ...(formData.representativeAssessee as Record<string, unknown>), mobile: value.replace(/\D/g, '').slice(0, 10) } })} required pattern="[1-9][0-9]{4,9}" maxLength={10} inputMode="tel" /></div>}</div>
    <SectionHeading title="Verification" description="Confirm the statutory declaration before generating official CBDT JSON. ITR-1 representative verification is intentionally blocked until the full representative filing contract is implemented." />
      <div style={CARD_STYLE}>
        <div style={GRID_STYLE}>
          <SelectField label="Verification capacity" value={text((formData.verification as Record<string, unknown>)?.capacity || 'SELF')} onChange={(value) => patch({ verification: { ...(formData.verification as Record<string, unknown>), capacity: value } })} required><option value="SELF">Self</option><option value="REPRESENTATIVE">Representative assessee</option></SelectField>
          <Field label="Place of verification" value={text((formData.verification as Record<string, unknown>)?.place)} onChange={(value) => patch({ verification: { ...(formData.verification as Record<string, unknown>), place: value } })} required maxLength={50} help="Enter the city/place from which the return is verified." />
          <Field label="Verification date" value={text((formData.verification as Record<string, unknown>)?.date || todayIso())} onChange={(value) => patch({ verification: { ...(formData.verification as Record<string, unknown>), date: value || null } })} type="date" required />
        </div>
        <label style={{ display: 'flex', alignItems: 'flex-start', gap: 8, marginTop: 16, fontSize: 13, color: 'var(--text-primary)' }}><input type="checkbox" checked={bool((formData.verification as Record<string, unknown>)?.declarationAccepted)} onChange={(event) => patch({ verification: { ...(formData.verification as Record<string, unknown>), declarationAccepted: event.target.checked } })} />I declare that the information given in this return and its schedules is correct and complete to the best of my knowledge and belief.</label>
        {text((formData.verification as Record<string, unknown>)?.capacity || 'SELF') === 'REPRESENTATIVE' && <div style={{ marginTop: 10, padding: 10, borderRadius: 6, background: 'var(--warning-bg)', color: 'var(--warning)', fontSize: 12 }}>Representative verification details are collected above, but official ITR-1 JSON generation is blocked until representative verification is fully supported by the canonical filing mapper.</div>}
      </div>
    <SectionHeading title="Tax Return Preparer (TRP)" description="Optional. Fill only if a Tax Return Preparer prepared this return and is eligible for government reimbursement under section 288B." />
      <div style={CARD_STYLE}>
        <SelectField label="Was this return prepared by a TRP?" value={bool((formData.taxReturnPreparer as Record<string, unknown>)?.used) ? 'Y' : 'N'} onChange={(value) => patch({ taxReturnPreparer: { ...(formData.taxReturnPreparer as Record<string, unknown>), used: value === 'Y' } })} required><option value="N">No</option><option value="Y">Yes</option></SelectField>
        {bool((formData.taxReturnPreparer as Record<string, unknown>)?.used) && <div style={{ ...GRID_STYLE, marginTop: 16 }}>
          <Field label="TRP identification number" value={text((formData.taxReturnPreparer as Record<string, unknown>)?.identificationNumber)} onChange={(value) => patch({ taxReturnPreparer: { ...(formData.taxReturnPreparer as Record<string, unknown>), identificationNumber: value.toUpperCase() } })} required maxLength={10} pattern="^(T[0-9]{9}|[0-9]{6})$" help="T-number (T + 9 digits) or 6-digit TRP registration number." />
          <Field label="TRP name" value={text((formData.taxReturnPreparer as Record<string, unknown>)?.name)} onChange={(value) => patch({ taxReturnPreparer: { ...(formData.taxReturnPreparer as Record<string, unknown>), name: value } })} required maxLength={125} />
          <Field label="Reimbursement from government (₹)" value={text((formData.taxReturnPreparer as Record<string, unknown>)?.reimbursementFromGovernment)} onChange={(value) => patch({ taxReturnPreparer: { ...(formData.taxReturnPreparer as Record<string, unknown>), reimbursementFromGovernment: value.replace(/\D/g, '') } })} inputMode="numeric" help="Section 288B reimbursement claimed via the TRP." />
        </div>}
      </div>
    <SectionHeading title="Residential status and special declarations" description={advancedForm ? 'These declarations activate ITR-2/ITR-3 schedules and must contain supporting detail when answered Yes.' : 'Some declarations make this form ineligible. Taxify will show an eligibility blocker when a higher form is required.'} />
      <div style={CARD_STYLE}><div style={GRID_STYLE}>
        <SelectField label="Residential Status" value={text(formData.residentialStatus || 'ROR')} onChange={(value) => patch({ residentialStatus: value })} required><option value="ROR">Resident and Ordinarily Resident (ROR)</option><option value="RNOR">Resident but Not Ordinarily Resident (RNOR)</option><option value="NR">Non-Resident (NR)</option></SelectField>
        {advancedForm && <><Field label="Days stayed in India in previous year" value={text(formData.daysInIndiaCurrentYear)} onChange={(value) => patch({ daysInIndiaCurrentYear: value.replace(/\D/g, '').slice(0, 3) })} inputMode="numeric" /><Field label="Days stayed in India in preceding four years" value={text(formData.daysInIndiaPreviousFourYears)} onChange={(value) => patch({ daysInIndiaPreviousFourYears: value.replace(/\D/g, '').slice(0, 4) })} inputMode="numeric" /></>}
        <SelectField label="Director in a company?" value={bool(formData.isDirector) ? 'Y' : 'N'} onChange={(value) => patch({ isDirector: value === 'Y', directorDetails: value === 'Y' ? directors : [] })} required><option value="N">No</option><option value="Y">Yes</option></SelectField>
        <SelectField label="Held unlisted equity shares?" value={bool(formData.holdsUnlistedShares) ? 'Y' : 'N'} onChange={(value) => patch({ holdsUnlistedShares: value === 'Y', unlistedShareHoldings: value === 'Y' ? holdings : [] })} required><option value="N">No</option><option value="Y">Yes</option></SelectField>
        <SelectField label="FII / FPI?" value={bool(formData.isFiiFpi) ? 'Y' : 'N'} onChange={(value) => patch({ isFiiFpi: value === 'Y' })} required><option value="N">No</option><option value="Y">Yes</option></SelectField>
        {bool(formData.isFiiFpi) && <Field label="SEBI Registration Number" value={text(formData.sebiRegistrationNumber)} onChange={(value) => patch({ sebiRegistrationNumber: value.toUpperCase() })} required pattern="IN[a-zA-Z]{2}FP[0-9]{6}" maxLength={12} help="Format: INxxFP123456." />}
        {advancedForm && <><SelectField label="Portuguese Civil Code (Schedule 5A) applicable?" value={bool(formData.portugueseCivilCode5A) ? 'Y' : 'N'} onChange={(value) => patch({ portugueseCivilCode5A: value === 'Y' })}><option value="N">No</option><option value="Y">Yes</option></SelectField><Field label="LEI Number" value={text(formData.leiNumber)} onChange={(value) => patch({ leiNumber: value.toUpperCase().slice(0, 20) })} pattern="[A-Z0-9]{20}" maxLength={20} help="Enter only when an LEI is applicable." /><Field label="LEI Valid Up To" value={text(formData.leiValidUptoDate)} onChange={(value) => patch({ leiValidUptoDate: value })} type="date" /></>}
        {itrForm === 'ITR-3' && <><SelectField label="Partner in a firm?" value={bool(formData.partnerInFirm) ? 'Y' : 'N'} onChange={(value) => patch({ partnerInFirm: value === 'Y', partnerFirmDetails: value === 'Y' ? formData.partnerFirmDetails || [] : [] })}><option value="N">No</option><option value="Y">Yes</option></SelectField><SelectField label="Non-resident has PE in India?" value={bool(formData.nriPEinIndia) ? 'Y' : 'N'} onChange={(value) => patch({ nriPEinIndia: value === 'Y' })}><option value="N">No</option><option value="Y">Yes</option></SelectField><SelectField label="Non-resident has SEP in India?" value={text(formData.nriSEPinIndia || 'NA')} onChange={(value) => patch({ nriSEPinIndia: value })}><option value="NA">Not Applicable</option><option value="N">No</option><option value="Y">Yes</option></SelectField><SelectField label="Foreign exchange involved?" value={bool(formData.foreignExchangeFlag) ? 'Y' : 'N'} onChange={(value) => patch({ foreignExchangeFlag: value === 'Y' })} required><option value="N">No</option><option value="Y">Yes</option></SelectField></>}
      </div></div>
      {bool(formData.isDirector) && <RepeatableDetails title="Director details" addLabel="Add company" rows={directors} blank={{ companyName: '', companyType: '', companyPan: '', din: '', shareType: '' }} columns={[['Company Name', 'companyName'], ['Company Type (D / F)', 'companyType'], ['Company PAN', 'companyPan'], ['DIN', 'din'], ['Share Type (L / U)', 'shareType']]} onChange={(next) => patch({ directorDetails: next })} />}
      {itrForm === 'ITR-3' && bool(formData.partnerInFirm) && <RepeatableDetails title="Partnership-firm details" addLabel="Add firm" rows={partnerFirms} blank={{ firmName: '', firmPan: '' }} columns={[['Firm Name', 'firmName'], ['Firm PAN', 'firmPan']]} onChange={(next) => patch({ partnerFirmDetails: next })} />}
      {bool(formData.holdsUnlistedShares) && <RepeatableDetails title="Unlisted equity share holdings" addLabel="Add holding" rows={holdings} blank={{ companyName: '', companyType: '', companyPan: '', openingNumberOfShares: '', openingCostOfAcquisition: '', acquiredDuringYear: '', acquisitionDate: '', faceValuePerShare: '', issuePricePerShare: '', purchasePricePerShare: '', transferredDuringYear: '', transferSaleConsideration: '', closingNumberOfShares: '', closingCostOfAcquisition: '' }} columns={[['Company Name', 'companyName'], ['Company Type (D / F)', 'companyType'], ['Company PAN', 'companyPan'], ['Opening Number of Shares', 'openingNumberOfShares'], ['Opening Cost of Acquisition', 'openingCostOfAcquisition'], ['Shares Acquired During Year', 'acquiredDuringYear'], ['Acquisition Date', 'acquisitionDate'], ['Face Value per Share', 'faceValuePerShare'], ['Issue Price per Share', 'issuePricePerShare'], ['Purchase Price per Share', 'purchasePricePerShare'], ['Shares Transferred During Year', 'transferredDuringYear'], ['Transfer Sale Consideration', 'transferSaleConsideration'], ['Closing Number of Shares', 'closingNumberOfShares'], ['Closing Cost of Acquisition', 'closingCostOfAcquisition']]} onChange={(next) => patch({ unlistedShareHoldings: next })} />}
    <SectionHeading title="Bank accounts and refund" description="Add all reportable accounts. The account manager guarantees that no more than one account is selected for refund; the legacy global refund checkbox has been removed." />
      <div style={CARD_STYLE}><BankAccountManager data={(formData.bankAccountData as BankAccountData) || { accounts: [] }} onChange={onBanksChange} /></div>
      <div style={{ padding: 12, borderRadius: 6, background: 'var(--info-bg)', color: 'var(--info)', fontSize: 12 }}>For every account, provide the bank name, account number, official account type and a valid IFSC matching <code>{IFSC_PATTERN}</code>. Select exactly one refund account whenever a refund account is required.</div>
  </div>;
}

function RepeatableDetails<T extends Record<string, string>>({ title, addLabel, rows, blank, columns, onChange }: { title: string; addLabel: string; rows: T[]; blank: T; columns: Array<[string, keyof T]>; onChange: (rows: T[]) => void }): React.JSX.Element {
  const update = (index: number, key: keyof T, value: string): void => onChange(rows.map((row, rowIndex) => rowIndex === index ? { ...row, [key]: value } : row));
  return <div style={CARD_STYLE}><div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center', marginBottom: 12 }}><h4 style={{ margin: 0, fontSize: 14 }}>{title}</h4><button type="button" onClick={() => onChange([...rows, { ...blank }])} style={{ background: 'var(--primary)', color: '#fff', border: 0, borderRadius: 5, padding: '7px 10px', fontSize: 12, cursor: 'pointer' }}>+ {addLabel}</button></div>{rows.length === 0 && <div style={{ color: 'var(--text-muted)', fontSize: 12 }}>At least one detailed row is required because this declaration is Yes.</div>}{rows.map((row, index) => <div key={index} style={{ borderTop: index > 0 ? '1px solid var(--border)' : undefined, paddingTop: index > 0 ? 14 : 0, marginTop: index > 0 ? 14 : 0 }}><div style={GRID_STYLE}>{columns.map(([label, key]) => { const keyName = String(key).toLowerCase(); const isPan = keyName.includes('pan'); return <Field key={String(key)} label={label} value={row[key]} onChange={(value) => update(index, key, isPan ? value.toUpperCase().slice(0, 10) : value)} pattern={isPan ? PAN_PATTERN : undefined} maxLength={isPan ? 10 : 125} />; })}</div><button type="button" onClick={() => onChange(rows.filter((_, rowIndex) => rowIndex !== index))} style={{ marginTop: 10, border: 0, background: 'transparent', color: '#c62828', fontSize: 12, cursor: 'pointer' }}>Remove row</button></div>)}</div>;
}
