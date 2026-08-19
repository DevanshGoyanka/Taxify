import type { ReturnDraftPatch } from '../domain/returns/draftPatch';
import { createReconciliationEvidence } from '../domain/returns/evidence';
import type { PrefillExtraction } from './prefillTypes';

function id(prefix: string, ...parts: unknown[]): string {
  const text = parts.map((part) => String(part ?? '')).join('|');
  let hash = 2166136261;
  for (let index = 0; index < text.length; index += 1) {
    hash ^= text.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return `${prefix}-${(hash >>> 0).toString(36)}`;
}

function filingSection(code: number | string | undefined): '139(1)' | '139(4)' | '139(5)' | '119(2)(b)' | undefined {
  const normalized = String(code ?? '').trim();
  const mapping: Record<string, '139(1)' | '139(4)' | '139(5)' | '119(2)(b)'> = {
    '11': '139(1)',
    '12': '139(4)',
    '13': '139(5)',
    '139(1)': '139(1)',
    '139(4)': '139(4)',
    '139(5)': '139(5)',
    '119(2)(b)': '119(2)(b)',
  };
  return mapping[normalized];
}

/** Maps an ITD prefill extraction directly into canonical draft fields.
 *
 * Per project decision, prefill contributes ONLY personal info + refund
 * bank account (filing section + verification + provenance metadata).
 * Income heads, employers, TDS, deductions, and capital gains are owned
 * by the reconciliation patch (built from 26AS/AIS/TIS); emitting them here
 * would duplicate when both patches merge.
 */
export function mapPrefillToDraftPatch(
  prefill: PrefillExtraction | null | undefined,
): ReturnDraftPatch {
  if (!prefill) return {};
  const pi = prefill.personal_info;
  const name = pi?.name;
  const address = pi?.address;
  const topLevelSections: Array<[keyof PrefillExtraction, unknown]> = [
    ['personal_info', prefill.personal_info], ['filing_status', prefill.filing_status], ['employer_entries', prefill.employer_entries],
    ['salary_insights', prefill.salary_insights], ['house_property', prefill.house_property], ['other_sources', prefill.other_sources],
    ['bank_accounts', prefill.bank_accounts], ['tds_salary_entries', prefill.tds_salary_entries], ['tds_other_entries', prefill.tds_other_entries],
    ['deductions', prefill.deductions], ['verification', prefill.verification], ['assessment_year', prefill.assessment_year], ['pan', prefill.pan],
  ];
  const evidence = topLevelSections.filter(([, value]) => value !== null && value !== undefined && value !== '' && (!Array.isArray(value) || value.length > 0)).map(([section, value]) => createReconciliationEvidence({
    source: 'ITD_PREFILL', code: String(section), section: String(section), category: String(section).replace(/_/g, ' '),
    description: `ITD prefill ${String(section)}`, raw: { value } as Record<string, unknown>, identity: [section],
  }));
  return {
    assessmentYear: prefill.assessment_year || undefined,
    personal: {
      name: [name?.first_name, name?.middle_name, name?.surname_or_org_name].filter(Boolean).join(' '), firstName: name?.first_name,
      middleName: name?.middle_name, surnameOrOrgName: name?.surname_or_org_name, fatherName: pi?.father_name, pan: pi?.pan || prefill.pan,
      aadhaar: pi?.aadhaar_card_no, email: address?.email_address, mobile: address?.mobile_no ? String(address.mobile_no) : undefined,
      secondaryEmail: address?.email_address_secondary, secondaryMobile: address?.mobile_no_sec ? String(address.mobile_no_sec) : undefined,
      secondaryMobileCountryCode: address?.country_code_mobile_sec ? String(address.country_code_mobile_sec) : undefined,
      dateOfBirth: pi?.dob || undefined, flatNo: address?.residence_no, residenceName: address?.residence_name, roadOrStreet: address?.road_or_street,
      localityOrArea: address?.locality_or_area, city: address?.city_or_town_or_district, stateCode: address?.state_code, countryCode: address?.country_code,
      pinCode: address?.pin_code ? String(address.pin_code) : undefined, zipCode: address?.zip_code,
    },
    filing: { filingSection: filingSection(prefill.filing_status?.return_file_sec) },
    bankAccounts: (prefill.bank_accounts || []).map((account) => ({ id: id('prefill-bank', account.bank_account_no, account.ifsc_code), bankName: account.bank_name || '', accountNumber: account.bank_account_no || '', ifscCode: account.ifsc_code || '', accountType: ['SB', 'CA', 'CC', 'OD', 'NRO', 'OTH'].includes(account.account_type?.toUpperCase()) ? account.account_type.toUpperCase() as 'SB' | 'CA' | 'CC' | 'OD' | 'NRO' | 'OTH' : 'SB', useForRefund: String(account.use_for_refund).toLowerCase() === 'true' })),
    verification: { place: prefill.verification?.place, capacity: prefill.verification?.capacity?.toUpperCase().includes('REP') ? 'REPRESENTATIVE' : undefined },
    provenance: [{ source: 'ITD_PREFILL', importedAt: new Date().toISOString(), reference: prefill.pan || pi?.pan || '' }],
    reconciliation: { evidence, discrepancies: [] },
  };
}
