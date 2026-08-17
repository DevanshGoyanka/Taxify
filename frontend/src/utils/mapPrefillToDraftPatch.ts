import { EMPTY_TDS_CREDIT, type Employer, type InterestIncome, type DividendIncome, type TdsCredit } from '../domain/returns/types';
import type { DeepPartial, ReturnDraftPatch } from '../domain/returns/draftPatch';
import { createReconciliationEvidence } from '../domain/returns/evidence';
import type { PrefillEmployerEntry, PrefillExtraction, PrefillTDSEntry } from './mapPrefillToFormData';
import { normalizeNatureOfEmployment } from './normalizeNatureOfEmployment';

function id(prefix: string, ...parts: unknown[]): string {
  const text = parts.map((part) => String(part ?? '')).join('|');
  let hash = 2166136261;
  for (let index = 0; index < text.length; index += 1) {
    hash ^= text.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return `${prefix}-${(hash >>> 0).toString(36)}`;
}

function employer(entry: PrefillEmployerEntry): DeepPartial<Employer> {
  const identity = (entry.tan || entry.employer_name || 'unknown').trim().toUpperCase();
  return {
    id: `employer-${identity}`, customEmployerName: entry.employer_name || '',
    employerName: entry.employer_name || 'Employer from Prefill', employerTAN: entry.tan || '',
    natureOfEmployment: normalizeNatureOfEmployment(entry.nature_of_employment), employerAddress: entry.employer_address || '',
    employerCity: entry.employer_city || '', employerStateCode: entry.employer_state_code || '', employerPinCode: entry.employer_pin_code || '', employerZipCode: entry.employer_zip_code || '',
    salaryNatureRows: [], perquisiteNatureRows: [], section10ExemptionRows: [], basic: entry.salary || 0, da: 0, commission: 0, hra: 0, bonus: 0, allowances: 0, lta: 0,
    otherAllowance: 0, arrearSalary: 0, perquisites: entry.value_of_perquisites || 0, profitsInLieu: entry.profits_in_lieu_of_salary || 0, rentPaid: 0,
    city: entry.employer_city || '', isMetroCity: false, isGovernmentEmployee: false, isDisabledEmployee: false, commutedPension: 0, gratuity: 0, leaveEncashment: 0,
    averageMonthlySalary: 0, yearsOfService: 0, unavailedLeaveDays: 0, actualLtaFare: 0, isDomesticTravel: true, journeysInBlock: 0, ltaExempt: 0,
    numberOfChildren: 0, gratuityAlsoReceived: false, transportAllowance: 0, childrenEducationAllowance: 0, hostelExpenditureAllowance: 0, uniformAllowance: 0,
    entertainmentAllowance: 0, professionalTax: 0, vrsCompensation: 0, retrenchmentCompensation: 0, otherExempt: 0, tdsDeducted: entry.tds_deducted_from_salary || 0, employerNPS: 0,
  };
}

function tds(entry: PrefillTDSEntry, salary: boolean): TdsCredit {
  const gross = entry.income_amount || entry.gross_amount || 0;
  const tax = entry.tds_deducted || 0;
  return {
    ...structuredClone(EMPTY_TDS_CREDIT), id: id('prefill-tds', entry.tan, entry.section, gross),
    section: salary ? '192' : entry.section || '194A', deductorName: entry.deductor_name || '', deductorTAN: entry.tan || '',
    grossAmount: gross, taxDeducted: tax, financialYear: entry.deducted_year || '2025-26', verified26AS: true,
    schedule: salary ? 'TDS1' : 'TDS2', headOfIncome: salary ? 'NA' : 'OS', claimOutOfTotTDSOnAmtPaid: entry.tds_claimed || tax,
  };
}

function interest(kind: InterestIncome['kind'], amount: number, index: number): InterestIncome {
  return { id: id('prefill-interest', kind, index, amount), kind, grossAmount: amount, tdsDeducted: 0, bankName: '', accountType: kind === 'SAVINGS_BANK' ? 'SAVINGS' : 'FD', accountNumber: '', ifscCode: '', postOfficeName: '', accountNumberPO: '', nscCertificateNumber: '', yearOfPurchase: 0, scssAccountNumber: '', dateOfOpening: '', deductorName: '', deductorTAN: '', remarks: '' };
}

function dividend(amount: number, index: number): DividendIncome {
  return { id: id('prefill-dividend', index, amount), section: '194', grossAmount: amount, tdsDeducted: 0, companyName: 'Dividend income', companyPAN: '', deductorTAN: '', isin: '', category: 'EQUITY', q1: 0, q2: 0, q3: 0, q4: 0, q5: 0 };
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

/** Maps an ITD prefill extraction directly into canonical draft fields. */
export function mapPrefillToDraftPatch(prefill: PrefillExtraction | null | undefined): ReturnDraftPatch {
  if (!prefill) return {};
  const pi = prefill.personal_info;
  const name = pi?.name;
  const address = pi?.address;
  const other = prefill.other_sources;
  const interests: InterestIncome[] = [];
  if (other?.interest_from_savings_bank) interests.push(interest('SAVINGS_BANK', other.interest_from_savings_bank, interests.length));
  if (other?.interest_from_term_deposit) interests.push(interest('TERM_DEPOSIT', other.interest_from_term_deposit, interests.length));
  if (other?.interest_from_others) interests.push(interest('OTHER', other.interest_from_others, interests.length));
  for (const detail of other?.other_income_details || []) {
    const nature = detail.nature?.toUpperCase();
    if (nature === 'SAV' || nature === 'IFD' || nature === 'IDP' || nature === 'INT') interests.push(interest(nature === 'SAV' ? 'SAVINGS_BANK' : nature === 'INT' ? 'OTHER' : 'TERM_DEPOSIT', detail.amount || 0, interests.length));
  }
  const dividends = (other?.other_income_details || []).filter((item) => ['DIV', 'DVD'].includes(item.nature?.toUpperCase())).map((item, index) => dividend(item.amount || 0, index));
  if (dividends.length === 0 && other?.dividend_gross) dividends.push(dividend(other.dividend_gross, 0));
  const ded = prefill.deductions;
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
    employers: (prefill.employer_entries || []).map(employer),
    bankAccounts: (prefill.bank_accounts || []).map((account) => ({ id: id('prefill-bank', account.bank_account_no, account.ifsc_code), bankName: account.bank_name || '', accountNumber: account.bank_account_no || '', ifscCode: account.ifsc_code || '', accountType: ['SB', 'CA', 'CC', 'OD', 'NRO', 'OTH'].includes(account.account_type?.toUpperCase()) ? account.account_type.toUpperCase() as 'SB' | 'CA' | 'CC' | 'OD' | 'NRO' | 'OTH' : 'SB', useForRefund: String(account.use_for_refund).toLowerCase() === 'true' })),
    taxes: { tds: [...(prefill.tds_salary_entries || []).map((entry) => tds(entry, true)), ...(prefill.tds_other_entries || []).map((entry) => tds(entry, false))] },
    deductions: { chapterVIA: { section80C: ded?.section_80c, section80D: ded?.section_80d, section80E: ded?.section_80e, section80G: ded?.section_80g, section80CCD1B: ded?.section_80ccd_1b, section80TTA: ded?.section_80tta, section80TTB: ded?.section_80ttb, anyOtherSection80CCH: ded?.section_80ccch, totalChapterVIADeductions: ded?.total_chap_via_deductions } },
    otherSources: { interest: interests, dividends, otherIncome: (other?.other_income_details || []).filter((item) => !['SAV', 'IFD', 'IDP', 'INT', 'DIV', 'DVD'].includes(item.nature?.toUpperCase())).map((item, index) => ({ id: id('prefill-other', item.nature, index), nature: item.nature || 'OTHER', description: item.nature || '', amount: item.amount || 0 })) },
    verification: { place: prefill.verification?.place, capacity: prefill.verification?.capacity?.toUpperCase().includes('REP') ? 'REPRESENTATIVE' : undefined },
    provenance: [{ source: 'ITD_PREFILL', importedAt: new Date().toISOString(), reference: prefill.pan || pi?.pan || '' }],
    reconciliation: { evidence, discrepancies: [] },
  };
}
