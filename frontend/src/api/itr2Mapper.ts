/**
 * Maps frontend form data to the canonical ITR-2 input payload expected by
 * the backend `/itr2/compute` and `/itr2/compute-json` endpoints.
 *
 * This mapper ensures the frontend never needs to know the full 656-line
 * Pydantic schema — it assembles the required fields from the flat form.
 */

import type { ITR2Result } from './itrCompute';

export interface ITR2FormPayload {
  // Filing profile
  pan: string;
  firstName: string;
  middleName?: string;
  surname: string;
  dateOfBirth: string;
  fatherName: string;
  verificationPlace: string;
  residentialStatus: 'RES' | 'NRI' | 'NOR';
  returnFileSection: number;
  // Address
  residenceNo: string;
  localityOrArea: string;
  cityOrTownOrDistrict: string;
  stateCode: string;
  pinCode: string;
  mobileNo: string;
  email: string;
  // Income
  ageBracket: 'below_60' | '60_to_80' | 'above_80';
  taxRegime: 'old' | 'new';
  grossSalary?: number;
  perquisitesValue?: number;
  profitsInLieuOfSalary?: number;
  hraExemptAmount?: number;
  houseProperties?: Array<{
    propertyType: 'S' | 'L' | 'D';
    annualRentReceived?: number;
    municipalTaxesPaid?: number;
    homeLoanInterestPaid?: number;
    addressDetail?: string;
    cityOrTownOrDistrict?: string;
    stateCode?: string;
    pinCode?: string;
  }>;
  savingsBankInterest?: number;
  fixedDepositInterest?: number;
  familyPensionReceived?: number;
  dividendIncome?: number;
  cgTransactions?: Array<{
    assetType: string;
    description?: string;
    dateOfAcquisition?: string;
    dateOfTransfer: string;
    fullConsideration: number;
    costOfAcquisition: number;
    indexedCost?: number;
    improvementCost?: number;
    indexedImprovement?: number;
    expenditureOnTransfer?: number;
    isSttPaidOnTransfer?: boolean;
    fairMarketValueJan2018?: number;
    exemptions?: Array<{
      section: '54' | '54B' | '54EC' | '54F' | '115F';
      investmentAmount: number;
      investmentDate?: string;
      cgasDepositAmount?: number;
    }>;
  }>;
  cg112aScrips?: Array<{
    isinCode: string;
    shareUnitName: string;
    isBefore31Jan2018?: boolean;
    dateOfAcquisition?: string;
    dateOfTransfer: string;
    numSharesUnits: number;
    salePricePerShare: number;
    totalSaleValue: number;
    costAcqWithoutIndex: number;
    fmvPerShare?: number;
    totalFmv?: number;
    expenditureOnTransfer?: number;
  }>;
  vdaTransactions?: Array<{
    dateOfAcquisition: string;
    dateOfTransfer: string;
    acquisitionCost: number;
    considerationReceived: number;
  }>;
  bfLosses?: Array<{
    assessmentYear: string;
    head: 'HP' | 'STCG' | 'LTCG' | 'RaceHorse';
    originalLoss?: number;
    broughtForward: number;
  }>;
  deductions?: {
    amount_80c?: number;
    amount_80d_self?: number;
    amount_80d_parents?: number;
    amount_80ccd1b?: number;
    amount_80ccd2?: number;
    amount_80e?: number;
    amount_80ee?: number;
    amount_80eea?: number;
    amount_80eeb?: number;
    amount_80g?: number;
    amount_80gg?: number;
    amount_80tta?: number;
    amount_80ttb?: number;
    amount_80dd?: number;
    amount_80ddb?: number;
    amount_80u?: number;
  };
  tds1Entries?: Array<{
    employerTan: string;
    employerName: string;
    incomeChargeable: number;
    tdsDeducted: number;
  }>;
  tds2Entries?: Array<{
    deductorTan: string;
    deductorName?: string;
    tdsSection: string;
    grossAmount: number;
    tdsDeducted: number;
    tdsClaimedThisYear: number;
    financialYear?: string;
  }>;
  tcsEntries?: Array<{
    collectorTan: string;
    tcsSection?: string;
    grossAmount: number;
    tcsCollected: number;
    tcsCreditClaimed: number;
    financialYear?: string;
  }>;
  taxPaymentEntries?: Array<{
    amount: number;
    paymentType: string;
    paymentDate: string;
    bsrCode?: string;
    challanSerialNumber?: string;
  }>;
  bankAccounts?: Array<{
    accountNumber: string;
    ifscCode: string;
    bankName: string;
    accountType: string;
    isPrimary?: boolean;
  }>;
  filingDate?: string;
  dueDate?: string;
  advanceTaxPaid?: number;
  selfAssessmentTaxPaid?: number;
  relief89?: number;
}

export function mapFormDataToITR2Input(form: ITR2FormPayload): Record<string, unknown> {
  const payload: Record<string, unknown> = {
    age_bracket: form.ageBracket,
    tax_regime: form.taxRegime,
    residential_status: form.residentialStatus,
    filing_section: form.returnFileSection,
  };

  // Filing profile
  if (form.pan) {
    payload.filing_profile = {
      pan: form.pan,
      first_name: form.firstName || '',
      middle_name: form.middleName || '',
      surname_or_org_name: form.surname,
      date_of_birth_or_formation: form.dateOfBirth,
      father_name: form.fatherName,
      verification_place: form.verificationPlace,
      residential_status: form.residentialStatus,
      return_file_section: form.returnFileSection,
      primary_address: {
        residence_no: form.residenceNo || '',
        locality_or_area: form.localityOrArea || '',
        city_or_town_or_district: form.cityOrTownOrDistrict || '',
        state_code: form.stateCode || '07',
        pin_code: form.pinCode || '',
        mobile_no: form.mobileNo || '',
        email: form.email || '',
      },
    };
  }

  // Salary income
  if (form.grossSalary !== undefined || form.perquisitesValue !== undefined) {
    payload.salary_income = {
      gross_salary: String(form.grossSalary || 0),
      perquisites_value: String(form.perquisitesValue || 0),
      profits_in_lieu_of_salary: String(form.profitsInLieuOfSalary || 0),
      hra_exempt_amount: String(form.hraExemptAmount || 0),
    };
  }

  // House properties
  if (form.houseProperties && form.houseProperties.length > 0) {
    payload.house_properties = form.houseProperties.map((p) => ({
      property_type: p.propertyType,
      annual_rent_received: String(p.annualRentReceived || 0),
      municipal_taxes_paid: String(p.municipalTaxesPaid || 0),
      home_loan_interest_paid: String(p.homeLoanInterestPaid || 0),
    }));
    payload.property_filing_details = form.houseProperties.map((p) => ({
      address_detail: p.addressDetail || 'Not provided',
      city_or_town_or_district: p.cityOrTownOrDistrict || 'Not provided',
      state_code: p.stateCode || '99',
      pin_code: p.pinCode || undefined,
    }));
  }

  // Other sources
  if (form.savingsBankInterest !== undefined || form.dividendIncome !== undefined) {
    payload.other_sources_income = {
      savings_bank_interest: String(form.savingsBankInterest || 0),
      fixed_deposit_interest: String(form.fixedDepositInterest || 0),
      family_pension_received: String(form.familyPensionReceived || 0),
      dividend_income: String(form.dividendIncome || 0),
    };
  }

  // Capital gains transactions
  if (form.cgTransactions && form.cgTransactions.length > 0) {
    payload.cg_transactions = form.cgTransactions.map((tx) => ({
      asset_type: tx.assetType,
      description: tx.description || '',
      date_of_acquisition: tx.dateOfAcquisition,
      date_of_transfer: tx.dateOfTransfer,
      full_consideration: String(tx.fullConsideration),
      cost_of_acquisition: String(tx.costOfAcquisition),
      indexed_cost: String(tx.indexedCost || 0),
      improvement_cost: String(tx.improvementCost || 0),
      indexed_improvement: String(tx.indexedImprovement || 0),
      expenditure_on_transfer: String(tx.expenditureOnTransfer || 0),
      is_stt_paid_on_transfer: tx.isSttPaidOnTransfer ?? true,
      fair_market_value_jan2018: tx.fairMarketValueJan2018 ? String(tx.fairMarketValueJan2018) : null,
      exemptions: (tx.exemptions || []).map((e) => ({
        section: e.section,
        transfer_date: tx.dateOfTransfer,
        eligible_gain: String(e.investmentAmount),
        investment_amount: String(e.investmentAmount),
        investment_date: e.investmentDate,
      })),
    }));
  }

  // 112A scrips
  if (form.cg112aScrips && form.cg112aScrips.length > 0) {
    payload.cg_112a_scrips = form.cg112aScrips.map((s) => ({
      isin_code: s.isinCode,
      share_unit_name: s.shareUnitName,
      is_before_31jan2018: s.isBefore31Jan2018 || false,
      date_of_acquisition: s.dateOfAcquisition,
      date_of_transfer: s.dateOfTransfer,
      num_shares_units: String(s.numSharesUnits),
      sale_price_per_share: String(s.salePricePerShare),
      total_sale_value: String(s.totalSaleValue),
      cost_acq_without_index: String(s.costAcqWithoutIndex),
      fmv_per_share: String(s.fmvPerShare || 0),
      total_fmv: String(s.totalFmv || 0),
      expenditure_on_transfer: String(s.expenditureOnTransfer || 0),
    }));
  }

  // VDA transactions
  if (form.vdaTransactions && form.vdaTransactions.length > 0) {
    payload.vda_transactions = form.vdaTransactions.map((v) => ({
      date_of_acquisition: v.dateOfAcquisition,
      date_of_transfer: v.dateOfTransfer,
      acquisition_cost: String(v.acquisitionCost),
      consideration_received: String(v.considerationReceived),
    }));
  }

  // Brought-forward losses
  if (form.bfLosses && form.bfLosses.length > 0) {
    payload.bf_losses = form.bfLosses.map((l) => ({
      assessment_year: l.assessmentYear,
      head: l.head,
      original_loss: String(l.originalLoss || 0),
      brought_forward: String(l.broughtForward),
    }));
  }

  // Deductions
  if (form.deductions) {
    payload.deductions_chapter6a = {
      amount_80c: String(form.deductions.amount_80c || 0),
      amount_80d_self: String(form.deductions.amount_80d_self || 0),
      amount_80d_parents: String(form.deductions.amount_80d_parents || 0),
      amount_80ccd1b: String(form.deductions.amount_80ccd1b || 0),
      amount_80ccd2: String(form.deductions.amount_80ccd2 || 0),
      amount_80e: String(form.deductions.amount_80e || 0),
      amount_80ee: String(form.deductions.amount_80ee || 0),
      amount_80eea: String(form.deductions.amount_80eea || 0),
      amount_80eeb: String(form.deductions.amount_80eeb || 0),
      amount_80g: String(form.deductions.amount_80g || 0),
      amount_80gg: String(form.deductions.amount_80gg || 0),
      amount_80tta: String(form.deductions.amount_80tta || 0),
      amount_80ttb: String(form.deductions.amount_80ttb || 0),
      amount_80dd: String(form.deductions.amount_80dd || 0),
      amount_80ddb: String(form.deductions.amount_80ddb || 0),
      amount_80u: String(form.deductions.amount_80u || 0),
    };
  }

  // TDS1 entries + employer filing details
  if (form.tds1Entries && form.tds1Entries.length > 0) {
    payload.tds1_entries = form.tds1Entries.map((e) => ({
      employer_tan: e.employerTan,
      employer_name: e.employerName,
      income_chargeable: String(e.incomeChargeable),
      tds_deducted: String(e.tdsDeducted),
    }));
    payload.employer_filing_details = form.tds1Entries.map((e) => ({
      employer_tan: e.employerTan,
      employer_name: e.employerName,
      address_detail: 'Not provided',
      city_or_town_or_district: 'Not provided',
      state_code: '99',
    }));
  }

  // TDS2 entries
  if (form.tds2Entries && form.tds2Entries.length > 0) {
    payload.tds2_entries = form.tds2Entries.map((e) => ({
      deductor_tan: e.deductorTan,
      deductor_name: e.deductorName || '',
      tds_section: e.tdsSection,
      gross_amount: String(e.grossAmount),
      tds_deducted: String(e.tdsDeducted),
      tds_claimed_this_year: String(e.tdsClaimedThisYear),
      financial_year: e.financialYear || '2024-25',
    }));
  }

  // TCS entries
  if (form.tcsEntries && form.tcsEntries.length > 0) {
    payload.tcs_entries = form.tcsEntries.map((e) => ({
      collector_tan: e.collectorTan,
      tcs_section: e.tcsSection || '206C',
      gross_amount: String(e.grossAmount),
      tcs_collected: String(e.tcsCollected),
      tcs_credit_claimed: String(e.tcsCreditClaimed),
      financial_year: e.financialYear || '2024-25',
    }));
  }

  // Tax payment entries
  if (form.taxPaymentEntries && form.taxPaymentEntries.length > 0) {
    payload.tax_payment_entries = form.taxPaymentEntries.map((e) => ({
      amount: String(e.amount),
      payment_type: e.paymentType,
      payment_date: e.paymentDate,
      bsr_code: e.bsrCode || '',
      challan_serial_number: e.challanSerialNumber || '',
    }));
  }

  // Bank accounts
  if (form.bankAccounts && form.bankAccounts.length > 0) {
    payload.bank_accounts = form.bankAccounts.map((a) => ({
      account_number: a.accountNumber,
      ifsc_code: a.ifscCode,
      bank_name: a.bankName,
      account_type: a.accountType,
      is_primary: a.isPrimary || false,
    }));
  }

  // Filing dates
  if (form.filingDate) payload.filing_date = form.filingDate;
  if (form.dueDate) payload.due_date = form.dueDate;
  payload.advance_tax_paid = String(form.advanceTaxPaid || 0);
  payload.self_assessment_tax_paid = String(form.selfAssessmentTaxPaid || 0);
  payload.relief_89 = String(form.relief89 || 0);

  return payload;
}

export type { ITR2Result };
