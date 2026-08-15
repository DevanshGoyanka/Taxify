/**
 * mapPrefillToFormData — convert the form-agnostic Prefill extraction to a
 * flat formData update patch.
 *
 * The Prefill JSON from ITD carries the CBDT's own pre-filled data:
 * personal info, salary break-up, deductions, bank accounts, employer TDS,
 * tax payments, and carry-forward losses.  This mapper converts the
 * backend PrefillExtraction dict to the same flat formData shape used by
 * ITRComputationPage, so it can be merged with the reconciled update.
 *
 * Precedence rule: Prefill provides salary break-up, deductions, bank
 * accounts, and personal info that AIS/TIS/26AS don't carry.  The
 * reconciled update (from mapReconciledToFormData) provides income and
 * TDS entries from AIS/TIS/26AS.  When both set the same field, the
 * reconciled update takes precedence (it's more recent and authoritative
 * for the current AY).  So the caller should merge:
 *   { ...prefillUpdate, ...reconciledUpdate }
 *
 * Only non-empty values are included in the patch — undefined keys are
 * omitted so existing user-entered data is not overwritten with blanks.
 */

// ── Prefill extraction types (mirror app/engine/importers/prefill_parser.py) ──

export interface PrefillName {
  first_name: string;
  middle_name: string;
  surname_or_org_name: string;
}

export interface PrefillAddress {
  residence_no: string;
  residence_name: string;
  road_or_street: string;
  locality_or_area: string;
  city_or_town_or_district: string;
  state_code: string;
  country_code: string;
  pin_code: string;
  zip_code: string;
  country_code_mobile: number;
  mobile_no: number;
  country_code_mobile_sec: number;
  mobile_no_sec: number;
  email_address: string;
  email_address_secondary: string;
}

export interface PrefillPersonalInfo {
  pan: string;
  aadhaar_card_no: string;
  name: PrefillName;
  assessee_ver_name: string;
  father_name: string;
  dob: string;
  status: string;
  employer_category: string;
  address: PrefillAddress;
  residential_status: string;
}

export interface PrefillFilingStatus {
  return_file_sec: number;
  residential_status: string;
  section_115ba: string;
  assessee_rep_flg: string;
}

export interface PrefillEmployerEntry {
  employer_name: string;
  tan: string;
  gross_salary: number;
  salary: number;
  value_of_perquisites: number;
  profits_in_lieu_of_salary: number;
  nature_of_employment: string;
  employer_address: string;
  employer_city: string;
  employer_state_code: string;
  employer_pin_code: string;
  employer_zip_code: string;
}

export interface PrefillSalaryInsights {
  salary: number;
  perquisites_value: number;
  profits_in_salary: number;
}

export interface PrefillHouseProperty {
  address: string;
  city: string;
  state_code: string;
  pin_code: number;
  country_code: string;
  zip_code: string;
  if_let_out: string;
  type_of_hp: string;
  gross_rent: number;
}

export interface PrefillOtherSourcesIncome {
  dividend_gross: number;
  interest_from_savings_bank: number;
  interest_from_term_deposit: number;
  interest_from_others: number;
  rent_from_mach_plant_bldgs: number;
  lottery_puzzle_income: number;
  other_income_details: Array<{ nature: string; amount: number }>;
}

export interface PrefillBankAccount {
  bank_account_no: string;
  bank_name: string;
  ifsc_code: string;
  account_type: string;
  use_for_refund: string;
}

export interface PrefillTDSEntry {
  deductor_name: string;
  tan: string;
  section: string;
  income_amount: number;
  tds_deducted: number;
  tds_claimed: number;
  gross_amount: number;
  head_of_income: string;
  deducted_year: string;
}

export interface PrefillDeductions {
  section_80c: number;
  section_80d: number;
  section_80e: number;
  section_80g: number;
  section_80ccd_1b: number;
  section_80tta: number;
  section_80ttb: number;
  section_80ccch: number;
  total_chap_via_deductions: number;
  [key: string]: number;
}

export interface PrefillVerification {
  assessee_ver_name: string;
  assessee_ver_pan: string;
  father_name: string;
  capacity: string;
  place: string;
}

export interface PrefillExtraction {
  personal_info: PrefillPersonalInfo;
  filing_status: PrefillFilingStatus;
  employer_entries: PrefillEmployerEntry[];
  salary_insights: PrefillSalaryInsights;
  house_property: PrefillHouseProperty[];
  other_sources: PrefillOtherSourcesIncome;
  bank_accounts: PrefillBankAccount[];
  tds_salary_entries: PrefillTDSEntry[];
  tds_other_entries: PrefillTDSEntry[];
  deductions: PrefillDeductions;
  verification: PrefillVerification;
  assessment_year: string;
  pan: string;
}

// ── Helpers ────────────────────────────────────────────────────────────────

function stableEntryId(prefix: string, entry: { employer_name?: string; tan?: string; deductor_name?: string; bank_account_no?: string }): string {
  const identity = entry.employer_name || entry.deductor_name || entry.bank_account_no || entry.tan || '';
  let hash = 2166136261;
  for (let i = 0; i < identity.length; i++) {
    hash ^= identity.charCodeAt(i);
    hash = Math.imul(hash, 16777619);
  }
  return `${prefix}-${(hash >>> 0).toString(36)}`;
}

// ── Entry builders ──────────────────────────────────────────────────────────

function buildEmployerEntry(emp: PrefillEmployerEntry) {
  return {
    id: stableEntryId('employer', emp),
    employerName: emp.employer_name || 'Employer from Prefill',
    employerTAN: emp.tan || '',
    employerPAN: '',
    basic: emp.salary || 0,
    da: 0,
    hra: 0,
    bonus: 0,
    allowances: 0,
    perquisites: emp.value_of_perquisites || 0,
    professionalTax: 0,
    tdsDeducted: 0,  // TDS comes from tds_salary_entries, not the employer entry
    grossSalary: emp.gross_salary || 0,
    netSalary: emp.salary || 0,
    financialYear: '',
    verified26AS: false,
  };
}

function buildBankAccount(acct: PrefillBankAccount) {
  // Normalize the account type from the prefill (e.g. "SB", "CA", "CC",
  // "OD", "NRO", "OTH").  The BankAccountManager accepts exactly these
  // enum values.  Default to "SB" if missing or unrecognized.
  const rawType = (acct.account_type || '').toUpperCase();
  const validTypes = ['SB', 'CA', 'CC', 'OD', 'NRO', 'OTH'];
  const accountType = validTypes.includes(rawType) ? rawType : 'SB';
  return {
    id: stableEntryId('bank', acct as any),
    bankName: acct.bank_name || '',
    accountNumber: acct.bank_account_no || '',
    ifscCode: acct.ifsc_code || '',
    accountType: accountType as 'SB' | 'CA' | 'CC' | 'OD' | 'NRO' | 'OTH',
    useForRefund: acct.use_for_refund === 'true',
  };
}

function buildTdsSalaryEntry(entry: PrefillTDSEntry) {
  return {
    id: stableEntryId('tds-sal', entry),
    section: '192',
    deductorName: entry.deductor_name || '',
    deductorTAN: entry.tan || '',
    deductorPAN: '',
    incomeAmount: entry.income_amount || 0,
    tdsDeducted: entry.tds_deducted || 0,
    certificateNo: '',
    deductionDate: '',
    uniqueTransactionNo: '',
    financialYear: '',
    verified26AS: true,
    claimedInReturn: true,
    _isSalaryTds: true,
  };
}

function buildTdsOtherEntry(entry: PrefillTDSEntry) {
  return {
    id: stableEntryId('tds-oth', entry),
    section: entry.section || '',
    deductorName: entry.deductor_name || '',
    deductorTAN: entry.tan || '',
    deductorPAN: '',
    incomeAmount: entry.income_amount || entry.gross_amount || 0,
    tdsDeducted: entry.tds_deducted || 0,
    certificateNo: '',
    deductionDate: '',
    uniqueTransactionNo: '',
    financialYear: entry.deducted_year || '',
    verified26AS: true,
    claimedInReturn: true,
    _isSalaryTds: false,
  };
}

// ── Main mapper ──────────────────────────────────────────────────────────────

export interface MapPrefillResult {
  formDataUpdate: Record<string, any>;
  summary: {
    personalInfo: boolean;
    employerEntries: number;
    bankAccounts: number;
    tdsSalaryEntries: number;
    tdsOtherEntries: number;
    deductionsTotal: number;
    housePropertyEntries: number;
  };
}

export function mapPrefillToFormData(prefill: PrefillExtraction | null | undefined): MapPrefillResult {
  if (!prefill || !prefill.personal_info) {
    return {
      formDataUpdate: {},
      summary: {
        personalInfo: false,
        employerEntries: 0,
        bankAccounts: 0,
        tdsSalaryEntries: 0,
        tdsOtherEntries: 0,
        deductionsTotal: 0,
        housePropertyEntries: 0,
      },
    };
  }

  const pi = prefill.personal_info;
  const addr = pi.address || ({} as PrefillAddress);
  const name = pi.name || ({} as PrefillName);
  const fs = prefill.filing_status || ({} as PrefillFilingStatus);
  const ded = prefill.deductions || ({} as PrefillDeductions);
  const os = prefill.other_sources || ({} as PrefillOtherSourcesIncome);
  const ver = prefill.verification || ({} as PrefillVerification);

  const update: Record<string, any> = {};

  // ── Personal Info ──
  // Only set non-empty values so existing user data is not overwritten.
  if (pi.pan) update.pan = pi.pan;
  if (pi.aadhaar_card_no) update.aadhaar = pi.aadhaar_card_no;
  if (name.first_name) update.firstName = name.first_name;
  if (name.middle_name) update.middleName = name.middle_name;
  if (name.surname_or_org_name) update.surnameOrOrgName = name.surname_or_org_name;
  if (name.first_name || name.middle_name || name.surname_or_org_name) {
    update.name = [name.first_name, name.middle_name, name.surname_or_org_name].filter(Boolean).join(' ');
  }
  if (pi.dob) update.dob = pi.dob;
  if (pi.father_name) update.fatherName = pi.father_name;
  if (pi.status) update.status = pi.status;
  if (pi.employer_category) update.employerCategory = pi.employer_category;

  // ── Address ──
  if (addr.residence_no) update.flatNo = addr.residence_no;
  if (addr.residence_name) update.premises = addr.residence_name;
  if (addr.road_or_street) update.road = addr.road_or_street;
  if (addr.locality_or_area) update.area = addr.locality_or_area;
  if (addr.city_or_town_or_district) update.city = addr.city_or_town_or_district;
  if (addr.state_code) update.state = addr.state_code;
  if (addr.country_code) update.country = addr.country_code;
  if (addr.pin_code) update.pincode = String(addr.pin_code);
  if (addr.zip_code) update.zipCode = addr.zip_code;

  // ── Contact ──
  if (addr.country_code_mobile) update.mobileCountryCode = String(addr.country_code_mobile);
  if (addr.mobile_no) update.mobile = String(addr.mobile_no);
  if (addr.country_code_mobile_sec) update.secondaryMobileCountryCode = String(addr.country_code_mobile_sec);
  if (addr.mobile_no_sec) update.secondaryMobile = String(addr.mobile_no_sec);
  if (addr.email_address) update.email = addr.email_address;
  if (addr.email_address_secondary) update.secondaryEmail = addr.email_address_secondary;

  // ── Filing Status ──
  if (fs.return_file_sec) update.filingSection = String(fs.return_file_sec);
  if (fs.residential_status) update.residentialStatus = fs.residential_status;

  // ── Salary (from employer entries) ──
  // The Prefill employer entries carry gross_salary and salary (basic).
  // These are the CBDT's own pre-filled values — more authoritative than
  // AIS/TIS for salary break-up.  Set them only when the Prefill has data.
  if (prefill.employer_entries && prefill.employer_entries.length > 0) {
    update.employerEntries = prefill.employer_entries.map(buildEmployerEntry);
    const totalSalary = prefill.employer_entries.reduce((s, e) => s + (e.salary || 0), 0);
    const totalGross = prefill.employer_entries.reduce((s, e) => s + (e.gross_salary || 0), 0);
    if (totalGross > 0) update.grossSalary = totalGross;
    if (totalSalary > 0) update.basic = totalSalary;
  }

  // ── Salary insights (cumulative from CBDT) ──
  // Only set if employer entries didn't provide salary — insights is the
  // CBDT's cumulative figure which may differ from employer entries.
  const si = prefill.salary_insights;
  if (si && si.salary > 0 && !update.basic) {
    update.basic = si.salary;
  }

  // ── Bank Accounts ──
  if (prefill.bank_accounts && prefill.bank_accounts.length > 0) {
    update.bankAccountData = {
      accounts: prefill.bank_accounts.map(buildBankAccount),
    };
  }

  // ── TDS on Salary ──
  if (prefill.tds_salary_entries && prefill.tds_salary_entries.length > 0) {
    const tdsSalTotal = prefill.tds_salary_entries.reduce((s, e) => s + (e.tds_deducted || 0), 0);
    update.tdsS192 = tdsSalTotal;
  }

  // ── TDS on Other than Salary ──
  if (prefill.tds_other_entries && prefill.tds_other_entries.length > 0) {
    const tdsOthTotal = prefill.tds_other_entries.reduce((s, e) => s + (e.tds_deducted || 0), 0);
    update.tds194A = tdsOthTotal;  // Simplified — real mapping needs section logic
  }

  // ── Deductions (Chapter VI-A) ──
  // Map the Prefill deductions to the flat s80* keys used by the form.
  if (ded.section_80c) update.s80C = ded.section_80c;
  if (ded.section_80d) update.s80D = ded.section_80d;
  if (ded.section_80e) update.s80E = ded.section_80e;
  if (ded.section_80g) update.s80G = ded.section_80g;
  if (ded.section_80ccd_1b) update.s80CCD1B = ded.section_80ccd_1b;
  if (ded.section_80tta) update.s80TTA = ded.section_80tta;
  if (ded.section_80ttb) update.s80TTB = ded.section_80ttb;
  if (ded.section_80ccch) update.s80CCH = ded.section_80ccch;

  // ── Other Sources Income ──
  if (os.interest_from_savings_bank) update.interestSB = os.interest_from_savings_bank;
  if (os.interest_from_term_deposit) update.interestFD = os.interest_from_term_deposit;
  if (os.dividend_gross) update.dividendShares = os.dividend_gross;

  // ── House Property ──
  // Only set house property if the Prefill has entries and the form
  // supports it (ITR-1, ITR-2, ITR-3, ITR-4 all support HP).
  if (prefill.house_property && prefill.house_property.length > 0) {
    // The flat formData uses propertyDetails array for HP entries.
    // We set it only when there are entries — don't erase existing data.
    update.propertyDetails = prefill.house_property.map((hp) => ({
      address: hp.address || '',
      city: hp.city || '',
      state: hp.state_code || '',
      countryCode: hp.country_code || '91',
      pincode: hp.pin_code ? String(hp.pin_code) : '',
      zipCode: hp.zip_code || '',
      ifLetOut: hp.if_let_out || '',
      typeOfHP: hp.type_of_hp || '',
      grossRent: hp.gross_rent || 0,
    }));
  }

  // ── Verification ──
  if (ver.assessee_ver_name) update.assesseeVerName = ver.assessee_ver_name;
  if (ver.assessee_ver_pan) update.assesseeVerPAN = ver.assessee_ver_pan;
  if (ver.father_name && !update.fatherName) update.fatherName = ver.father_name;
  if (ver.capacity) update.capacity = ver.capacity;
  if (ver.place) update.place = ver.place;

  // ── Metadata ──
  update.importedFromPrefill = {
    pan: prefill.pan,
    assessmentYear: prefill.assessment_year,
    importedAt: new Date().toISOString(),
    employerCount: prefill.employer_entries?.length || 0,
    bankAccountCount: prefill.bank_accounts?.length || 0,
    tdsSalaryCount: prefill.tds_salary_entries?.length || 0,
    tdsOtherCount: prefill.tds_other_entries?.length || 0,
    deductionsTotal: ded.total_chap_via_deductions || 0,
  };

  return {
    formDataUpdate: update,
    summary: {
      personalInfo: !!pi.pan,
      employerEntries: prefill.employer_entries?.length || 0,
      bankAccounts: prefill.bank_accounts?.length || 0,
      tdsSalaryEntries: prefill.tds_salary_entries?.length || 0,
      tdsOtherEntries: prefill.tds_other_entries?.length || 0,
      deductionsTotal: ded.total_chap_via_deductions || 0,
      housePropertyEntries: prefill.house_property?.length || 0,
    },
  };
}
