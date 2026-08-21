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
  tds_deducted_from_salary?: number;
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

// ── Presumptive business (44AD/44ADA/44AE) — prior-year + current-year ────

/** One prior-year business/profession row from lastFiledITR. */
export interface PrefillPresumptiveBusiness {
  /** Which scheme the row came from: '44AD' | '44ADA' | '44AE'. */
  scheme: string;
  /** Business/profession code (codeAD / codeADA / codeAE). */
  code: string;
  /** Business name as filed last year. */
  name_of_business: string;
  /** Optional description. */
  description: string;
}

/** One GSTIN turnover row from form26as.scheduleBP. */
export interface PrefillGstinTurnover {
  gstin: string;
  amount: number;
}

/** One 44AE goods-carriage row from lastFiledITR.goodsDtlsUs44AE. */
export interface PrefillGoodsCarriage44AE {
  reg_number: string;
  tonnage: number;
  /** Months owned/leased/hired. */
  holding_period: number;
  /** 'OWN' | 'LEASE' | 'HIRED'. */
  owned_leased_hired: string;
}

/** Presumptive income details (44AD/44ADA/44AE) from the prefill. */
export interface PrefillPresumptiveIncome {
  /** Current-year 44ADA gross receipts (form26as.persumptiveInc44ADA.grsReceipt). */
  gross_receipt_44ada: number;
  /** Current-year 44ADA total presumptive income declared. */
  declared_income_44ada: number;
  /** Prior-year business rows (code + name), tagged by scheme. */
  business_nature_codes: Array<{ code: string; name: string }>;
  // ── Full 44AD/44ADA/44AE extraction ──────────────────────────────────
  total_presumptive_income_44ad: number;
  total_presumptive_income_44ada: number;
  presumptive_income_44ad_6pct: number;
  presumptive_income_44ad_8pct: number;
  /** Prior-year businesses, tagged with the originating scheme. */
  businesses: PrefillPresumptiveBusiness[];
  /** GSTIN-wise turnover rows (shared by all schemes). */
  gstin_turnovers: PrefillGstinTurnover[];
  /** Prior-year 44AE vehicle details. */
  goods_carriages_44ae: PrefillGoodsCarriage44AE[];
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
  /** Presumptive business income (44AD/44ADA/44AE) — prior-year + current-year. */
  presumptive_income: PrefillPresumptiveIncome;
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


