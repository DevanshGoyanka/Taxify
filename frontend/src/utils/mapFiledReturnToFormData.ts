/**
 * mapFiledReturnToFormData — convert the form-agnostic filed-return
 * extraction to a flat formData update patch.
 *
 * The filed-return JSON is the CBDT's official ITR JSON for the previous
 * year (or, for revision, the current year).  It carries:
 *
 * - Personal info (name, address, DOB, PAN, Aadhaar) — only populate if
 *   the Prefill didn't already provide them (Prefill is more recent).
 * - Employer details — only populate if the Prefill didn't (the filed
 *   return has prior-AY employer data which may not match the current AY).
 * - Bank accounts — only populate if the Prefill didn't.
 * - Carry-forward losses — ALWAYS populate (the filed return is the only
 *   source for brought-forward losses).
 * - Filing status (return section, residential status) — only populate
 *   if the Prefill didn't.
 *
 * Precedence: Prefill (most recent) > filed-return > reconciled (income/TDS
 * from AIS/TIS/26AS).  The caller should merge:
 *   { ...filedReturnUpdate, ...prefillUpdate, ...reconciledUpdate }
 *
 * For a revised-return flow (current AY already filed), the caller should
 * ONLY call this mapper after the user has explicitly confirmed the
 * revised-return flow (checked via the filing_advisory flag).
 */

export interface FiledReturnName {
  first_name: string;
  middle_name: string;
  surname_or_org_name: string;
}

export interface FiledReturnAddress {
  residence_no: string;
  residence_name: string;
  road_or_street: string;
  locality_or_area: string;
  city_or_town_or_district: string;
  state_code: string;
  country_code: string;
  pin_code: string;
  country_code_mobile: number;
  mobile_no: number;
  email_address: string;
  alternate_address: Record<string, any>;
  secondary_add: string;
}

export interface FiledReturnPersonalInfo {
  pan: string;
  aadhaar_card_no: string;
  name: FiledReturnName;
  dob: string;
  status: string;
  address: FiledReturnAddress;
}

export interface FiledReturnFilingStatus {
  return_file_sec: number;
  residential_status: string;
  seventh_provisio_139: string;
  opt_out_new_tax_regime: string;
  itr_filing_due_date: string;
}

export interface FiledReturnEmployerEntry {
  employer_name: string;
  nature_of_employment: string;
  tan: string;
  gross_salary: number;
  salary: number;
  value_of_perquisites: number;
  profits_in_lieu_of_salary: number;
  employer_address: string;
  employer_city: string;
  employer_state_code: string;
  employer_pin_code: string;
}

export interface FiledReturnBankAccount {
  bank_account_no: string;
  bank_name: string;
  ifsc_code: string;
  account_type: string;
  use_for_refund: string;
}

export interface FiledReturnTDSEntry {
  deductor_name: string;
  tan: string;
  section: string;
  income_amount: number;
  tds_deducted: number;
  tds_claimed: number;
  gross_amount: number;
  head_of_income: string;
}

export interface FiledReturnDeductions {
  section_80c: number;
  section_80d: number;
  section_80ttb: number;
  total_chap_via_deductions: number;
  [key: string]: number;
}

export interface FiledReturnCarryForwardLoss {
  assessment_year: string;
  brought_fwd_bus_loss: number;
  hp_loss_cf: number;
  ltcg_loss_cf: number;
  stcg_loss_cf: number;
  oth_src_loss_race_horse_cf: number;
}

export interface FiledReturnVerification {
  assessee_ver_name: string;
  assessee_ver_pan: string;
  father_name: string;
  capacity: string;
  place: string;
  date: string;
}

export interface FiledReturnExtraction {
  form_name: string;
  assessment_year: string;
  personal_info: FiledReturnPersonalInfo;
  filing_status: FiledReturnFilingStatus;
  employer_entries: FiledReturnEmployerEntry[];
  bank_accounts: FiledReturnBankAccount[];
  tds_salary_entries: FiledReturnTDSEntry[];
  tds_other_entries: FiledReturnTDSEntry[];
  deductions: FiledReturnDeductions;
  carry_forward_losses: FiledReturnCarryForwardLoss[];
  verification: FiledReturnVerification;
  total_tax_payments: number;
  bal_tax_payable: number;
  refund_due: number;
}

// ── Helpers ────────────────────────────────────────────────────────────────

function stableEntryId(prefix: string, entry: { employer_name?: string; tan?: string; bank_account_no?: string }): string {
  const identity = entry.employer_name || entry.bank_account_no || entry.tan || '';
  let hash = 2166136261;
  for (let i = 0; i < identity.length; i++) {
    hash ^= identity.charCodeAt(i);
    hash = Math.imul(hash, 16777619);
  }
  return `${prefix}-${(hash >>> 0).toString(36)}`;
}

// ── Main mapper ──────────────────────────────────────────────────────────────

export interface MapFiledReturnResult {
  formDataUpdate: Record<string, any>;
  summary: {
    personalInfo: boolean;
    employerEntries: number;
    bankAccounts: number;
    tdsSalaryEntries: number;
    tdsOtherEntries: number;
    carryForwardLosses: number;
    isPriorYear: boolean;
  };
}

export function mapFiledReturnToFormData(
  filedReturn: FiledReturnExtraction | null | undefined,
): MapFiledReturnResult {
  if (!filedReturn || !filedReturn.personal_info) {
    return {
      formDataUpdate: {},
      summary: {
        personalInfo: false,
        employerEntries: 0,
        bankAccounts: 0,
        tdsSalaryEntries: 0,
        tdsOtherEntries: 0,
        carryForwardLosses: 0,
        isPriorYear: false,
      },
    };
  }

  const pi = filedReturn.personal_info;
  const addr = pi.address || ({} as FiledReturnAddress);
  const name = pi.name || ({} as FiledReturnName);
  const fs = filedReturn.filing_status || ({} as FiledReturnFilingStatus);
  const ver = filedReturn.verification || ({} as FiledReturnVerification);

  const update: Record<string, any> = {};

  // ── Personal Info (only set non-empty values) ──
  if (pi.pan) update.pan = pi.pan;
  if (pi.aadhaar_card_no) update.aadhaar = pi.aadhaar_card_no;
  if (name.first_name) update.firstName = name.first_name;
  if (name.middle_name) update.middleName = name.middle_name;
  if (name.surname_or_org_name) update.surnameOrOrgName = name.surname_or_org_name;
  if (pi.dob) update.dob = pi.dob;
  if (pi.status) update.status = pi.status;

  // ── Address ──
  if (addr.residence_no) update.flatNo = addr.residence_no;
  if (addr.residence_name) update.premises = addr.residence_name;
  if (addr.road_or_street) update.road = addr.road_or_street;
  if (addr.locality_or_area) update.area = addr.locality_or_area;
  if (addr.city_or_town_or_district) update.city = addr.city_or_town_or_district;
  if (addr.state_code) update.state = addr.state_code;
  if (addr.country_code) update.country = addr.country_code;
  if (addr.pin_code) update.pincode = String(addr.pin_code);
  if (addr.country_code_mobile) update.mobileCountryCode = String(addr.country_code_mobile);
  if (addr.mobile_no) update.mobile = String(addr.mobile_no);
  if (addr.email_address) update.email = addr.email_address;

  // ── Filing Status ──
  if (fs.return_file_sec) update.filingSection = String(fs.return_file_sec);
  if (fs.residential_status) update.residentialStatus = fs.residential_status;

  // ── Employer Entries (prior-AY data — may not match current AY) ──
  if (filedReturn.employer_entries && filedReturn.employer_entries.length > 0) {
    update.employerEntries = filedReturn.employer_entries.map((emp) => ({
      id: stableEntryId('fr-employer', emp),
      employerName: emp.employer_name || 'Employer from filed return',
      employerTAN: emp.tan || '',
      employerPAN: '',
      basic: emp.salary || 0,
      da: 0,
      hra: 0,
      bonus: 0,
      allowances: 0,
      perquisites: emp.value_of_perquisites || 0,
      professionalTax: 0,
      tdsDeducted: 0,
      grossSalary: emp.gross_salary || 0,
      netSalary: emp.salary || 0,
      financialYear: '',
      verified26AS: false,
    }));
  }

  // ── Bank Accounts (prior-AY — may not match current AY) ──
  if (filedReturn.bank_accounts && filedReturn.bank_accounts.length > 0) {
    const rawType = (filedReturn.bank_accounts[0]?.account_type || '').toUpperCase();
    const validTypes = ['SB', 'CA', 'CC', 'OD', 'NRO', 'OTH'];
    const defaultType = validTypes.includes(rawType) ? rawType : 'SB';
    update.bankAccountData = {
      accounts: filedReturn.bank_accounts.map((acct) => {
        const acctType = (acct.account_type || '').toUpperCase();
        const accountType = validTypes.includes(acctType) ? acctType : defaultType;
        return {
          id: stableEntryId('fr-bank', acct as any),
          bankName: acct.bank_name || '',
          accountNumber: acct.bank_account_no || '',
          ifscCode: acct.ifsc_code || '',
          accountType: accountType as 'SB' | 'CA' | 'CC' | 'OD' | 'NRO' | 'OTH',
          useForRefund: acct.use_for_refund === 'true',
        };
      }),
    };
  }

  // ── Carry-forward losses (ALWAYS populate — filed return is the only source) ──
  if (filedReturn.carry_forward_losses && filedReturn.carry_forward_losses.length > 0) {
    update.carryForwardLosses = filedReturn.carry_forward_losses.map((loss) => ({
      assessmentYear: loss.assessment_year || '',
      businessLoss: loss.brought_fwd_bus_loss || 0,
      hpLoss: loss.hp_loss_cf || 0,
      ltcgLoss: loss.ltcg_loss_cf || 0,
      stcgLoss: loss.stcg_loss_cf || 0,
      otherSourceLoss: loss.oth_src_loss_race_horse_cf || 0,
    }));
    // Also set the flat bfLoss* fields used by the form.
    const totalBfHp = filedReturn.carry_forward_losses.reduce((s, l) => s + (l.hp_loss_cf || 0), 0);
    const totalBfLtcg = filedReturn.carry_forward_losses.reduce((s, l) => s + (l.ltcg_loss_cf || 0), 0);
    const totalBfStcg = filedReturn.carry_forward_losses.reduce((s, l) => s + (l.stcg_loss_cf || 0), 0);
    const totalBfBus = filedReturn.carry_forward_losses.reduce((s, l) => s + (l.brought_fwd_bus_loss || 0), 0);
    if (totalBfHp > 0) update.bfLossHP = totalBfHp;
    if (totalBfLtcg > 0) update.bfLossLTCG = totalBfLtcg;
    if (totalBfStcg > 0) update.bfLossSTCG = totalBfStcg;
    if (totalBfBus > 0) update.bfLossBusiness = totalBfBus;
  }

  // ── Verification ──
  if (ver.assessee_ver_name) update.assesseeVerName = ver.assessee_ver_name;
  if (ver.assessee_ver_pan) update.assesseeVerPAN = ver.assessee_ver_pan;
  if (ver.father_name) update.fatherName = ver.father_name;
  if (ver.capacity) update.capacity = ver.capacity;
  if (ver.place) update.place = ver.place;

  // ── Metadata ──
  update.importedFromFiledReturn = {
    form_name: filedReturn.form_name,
    assessment_year: filedReturn.assessment_year,
    imported_at: new Date().toISOString(),
    employer_count: filedReturn.employer_entries?.length || 0,
    bank_account_count: filedReturn.bank_accounts?.length || 0,
    carry_forward_loss_count: filedReturn.carry_forward_losses?.length || 0,
  };

  return {
    formDataUpdate: update,
    summary: {
      personalInfo: !!pi.pan,
      employerEntries: filedReturn.employer_entries?.length || 0,
      bankAccounts: filedReturn.bank_accounts?.length || 0,
      tdsSalaryEntries: filedReturn.tds_salary_entries?.length || 0,
      tdsOtherEntries: filedReturn.tds_other_entries?.length || 0,
      carryForwardLosses: filedReturn.carry_forward_losses?.length || 0,
      isPriorYear: true,  // The filed return is always for a prior AY (or current AY for revision)
    },
  };
}
