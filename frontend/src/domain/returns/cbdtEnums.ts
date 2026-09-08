/**
 * Canonical CBDT enums for ITR-1 / ITR-4 (AY 2026-27).
 *
 * Source of truth: the official CBDT JSON schemas
 * (Reference Docs by CBDT & ITD/Official JSON Schema/
 *  ITR-1_2026_Main_V1.1 (2).json, ITR-4_2026_Main_V1.1 (2).json).
 *
 * These unions constrain frontend input at the type layer so invalid
 * values surface at entry time, not at CBDT-generation time.
 */

export type EmployerCategory =
  | 'CGOV' | 'SGOV' | 'PSU' | 'PE' | 'PESG' | 'PEPS' | 'PEO' | 'OTH' | 'NA';

/** CBDT PersonalInfo.EmployerCategory (ITR-1 & ITR-4 schema enum). */
export const EMPLOYER_CATEGORY_OPTIONS: ReadonlyArray<{ code: EmployerCategory; label: string }> = [
  { code: 'CGOV', label: 'Central Government' },
  { code: 'SGOV', label: 'State Government' },
  { code: 'PSU', label: 'Public Sector Undertaking' },
  { code: 'PE', label: 'Pensioner - Central Government' },
  { code: 'PESG', label: 'Pensioner - State Government' },
  { code: 'PEPS', label: 'Pensioner - Public Sector Undertaking' },
  { code: 'PEO', label: 'Pensioner - Others' },
  { code: 'OTH', label: 'Others' },
  { code: 'NA', label: 'Not Applicable' },
];

export type StateCode =
  | '01' | '02' | '03' | '04' | '05' | '06' | '07' | '08' | '09'
  | '10' | '11' | '12' | '13' | '14' | '15' | '16' | '17' | '18'
  | '19' | '20' | '21' | '22' | '23' | '24' | '25' | '26' | '27'
  | '28' | '29' | '30' | '31' | '32' | '33' | '34' | '35' | '36'
  | '37' | '99';

/** CBDT StateCode enum. Code 99 represents an address outside India. */
export const STATE_CODE_OPTIONS: ReadonlyArray<{ code: StateCode; label: string }> = [
  { code: '01', label: 'Andaman and Nicobar Islands' },
  { code: '02', label: 'Andhra Pradesh' },
  { code: '03', label: 'Arunachal Pradesh' },
  { code: '04', label: 'Assam' },
  { code: '05', label: 'Bihar' },
  { code: '06', label: 'Chandigarh' },
  { code: '07', label: 'Dadra and Nagar Haveli' },
  { code: '08', label: 'Daman and Diu' },
  { code: '09', label: 'Delhi' },
  { code: '10', label: 'Goa' },
  { code: '11', label: 'Gujarat' },
  { code: '12', label: 'Haryana' },
  { code: '13', label: 'Himachal Pradesh' },
  { code: '14', label: 'Jammu and Kashmir' },
  { code: '15', label: 'Karnataka' },
  { code: '16', label: 'Kerala' },
  { code: '17', label: 'Lakshadweep' },
  { code: '18', label: 'Madhya Pradesh' },
  { code: '19', label: 'Maharashtra' },
  { code: '20', label: 'Manipur' },
  { code: '21', label: 'Meghalaya' },
  { code: '22', label: 'Mizoram' },
  { code: '23', label: 'Nagaland' },
  { code: '24', label: 'Odisha' },
  { code: '25', label: 'Puducherry' },
  { code: '26', label: 'Punjab' },
  { code: '27', label: 'Rajasthan' },
  { code: '28', label: 'Sikkim' },
  { code: '29', label: 'Tamil Nadu' },
  { code: '30', label: 'Tripura' },
  { code: '31', label: 'Uttar Pradesh' },
  { code: '32', label: 'West Bengal' },
  { code: '33', label: 'Chhattisgarh' },
  { code: '34', label: 'Uttarakhand' },
  { code: '35', label: 'Jharkhand' },
  { code: '36', label: 'Telangana' },
  { code: '37', label: 'Ladakh' },
  { code: '99', label: 'Outside India' },
];

export const INDIAN_STATE_CODE_OPTIONS = STATE_CODE_OPTIONS.filter(({ code }) => code !== '99');

export type NatureOfEmployment =
  | 'CGOV' | 'SGOV' | 'PSU' | 'PE' | 'PESG' | 'PEPS' | 'PEO' | 'OTH';

/** CBDT Schedule S NatureOfEmployment enum, scoped to one employer row. */
export const NATURE_OF_EMPLOYMENT_OPTIONS: ReadonlyArray<{ code: NatureOfEmployment; label: string }> = [
  { code: 'CGOV', label: 'Central Government' },
  { code: 'SGOV', label: 'State Government' },
  { code: 'PSU', label: 'Public Sector Undertaking' },
  { code: 'PE', label: 'Pensioner - Central Government' },
  { code: 'PESG', label: 'Pensioner - State Government' },
  { code: 'PEPS', label: 'Pensioner - Public Sector Undertaking' },
  { code: 'PEO', label: 'Pensioner - Others' },
  { code: 'OTH', label: 'Others' },
];

const EMPLOYER_CATEGORIES = new Set<string>(EMPLOYER_CATEGORY_OPTIONS.map(({ code }) => code));
const STATE_CODES = new Set<string>(STATE_CODE_OPTIONS.map(({ code }) => code));
const EMPLOYMENT_NATURES = new Set<string>(NATURE_OF_EMPLOYMENT_OPTIONS.map(({ code }) => code));

export function normalizeEmployerCategory(value: unknown): EmployerCategory | '' {
  const code = String(value ?? '').trim().toUpperCase();
  return EMPLOYER_CATEGORIES.has(code) ? code as EmployerCategory : '';
}

export function normalizeStateCode(value: unknown): StateCode | '' {
  const code = String(value ?? '').trim().padStart(2, '0');
  return STATE_CODES.has(code) ? code as StateCode : '';
}

export function normalizeEmploymentNature(value: unknown): NatureOfEmployment | '' {
  const code = String(value ?? '').trim().toUpperCase();
  return EMPLOYMENT_NATURES.has(code) ? code as NatureOfEmployment : '';
}
