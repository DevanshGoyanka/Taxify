import type { ReconciledEntry, ReconciledResults } from '../api/itrAutomation';
import { EMPTY_TDS_CREDIT, type DividendIncome, type Employer, type InterestIncome, type Presumptive44AD, type Presumptive44ADA, type TdsCredit } from '../domain/returns/types';
import { createEmptyFinancialParticulars } from '../domain/returns/factory';
import type { ReturnDraftPatch } from '../domain/returns/draftPatch';
import { mapCapitalGainsEvidence } from './mapCapitalGainsToDraftPatch';

function id(prefix: string, entry: ReconciledEntry): string {
  const text = entry.source_id || `${entry.source}|${entry.section}|${entry.final_amount}`;
  let hash = 2166136261;
  for (let index = 0; index < text.length; index += 1) { hash ^= text.charCodeAt(index); hash = Math.imul(hash, 16777619); }
  return `${prefix}-${(hash >>> 0).toString(36)}`;
}

function allEntries(results: ReconciledResults): ReconciledEntry[] {
  return Object.values(results.income_heads || {}).flatMap((head) => head.entries || []);
}

function employer(entry: ReconciledEntry): Employer {
  const identity = (entry.tan || entry.source || 'unknown').trim().toUpperCase();
  return {
    id: `employer-${identity}`,
    customEmployerName: entry.source || '',
    employerName: entry.source || 'Employer from Portal',
    employerTAN: entry.tan || '',
    natureOfEmployment: 'OTH',
    employerAddress: '', employerCity: '', employerStateCode: '', employerPinCode: '', employerZipCode: '',
    salaryNatureRows: [], perquisiteNatureRows: [], section10ExemptionRows: [],
    basic: entry.final_amount || 0, da: 0, commission: 0, hra: 0, bonus: 0,
    allowances: 0, lta: 0, otherAllowance: 0, arrearSalary: 0, perquisites: 0,
    profitsInLieu: 0, rentPaid: 0, city: '', isMetroCity: false,
    isGovernmentEmployee: false, isDisabledEmployee: false, commutedPension: 0,
    gratuity: 0, leaveEncashment: 0, averageMonthlySalary: 0, yearsOfService: 0,
    unavailedLeaveDays: 0, actualLtaFare: 0, isDomesticTravel: true,
    journeysInBlock: 0, ltaExempt: 0, numberOfChildren: 0,
    gratuityAlsoReceived: false, transportAllowance: 0,
    childrenEducationAllowance: 0, hostelExpenditureAllowance: 0,
    uniformAllowance: 0, entertainmentAllowance: 0, professionalTax: 0,
    vrsCompensation: 0, retrenchmentCompensation: 0, otherExempt: 0,
    tdsDeducted: entry.as26_tds || 0, employerNPS: 0,
  };
}

function tds(entry: ReconciledEntry): TdsCredit {
  const section = (entry.section || '192').replace(/\s+/g, '').toUpperCase();
  const tax = entry.as26_tds || 0;
  return { ...structuredClone(EMPTY_TDS_CREDIT), id: id('recon-tds', entry), section, deductorName: entry.source || 'Deductor from Portal', deductorTAN: entry.tan || '', deductorPAN: entry.pan || '', grossAmount: entry.final_amount || 0, taxDeducted: tax, verified26AS: Boolean(entry.present_in?.as26), schedule: section === '192' || section === 'S192' ? 'TDS1' : 'TDS2', headOfIncome: section === '192' || section === 'S192' ? 'NA' : 'OS', claimOutOfTotTDSOnAmtPaid: tax };
}

function interest(entry: ReconciledEntry): InterestIncome {
  const category = (entry.category || '').toLowerCase();
  const kind = category === 'interest from savings bank' ? 'SAVINGS_BANK' : category === 'interest from deposit' ? 'TERM_DEPOSIT' : 'OTHER';
  return { id: id('recon-interest', entry), kind, grossAmount: entry.final_amount || 0, tdsDeducted: entry.as26_tds || 0, bankName: entry.source || '', accountType: kind === 'SAVINGS_BANK' ? 'SAVINGS' : 'FD', accountNumber: '', ifscCode: '', postOfficeName: '', accountNumberPO: '', nscCertificateNumber: '', yearOfPurchase: 0, scssAccountNumber: '', dateOfOpening: '', deductorName: entry.source || '', deductorTAN: entry.tan || '', remarks: '' };
}

function dividend(entry: ReconciledEntry): DividendIncome {
  return { id: id('recon-dividend', entry), section: '194', grossAmount: entry.final_amount || 0, tdsDeducted: entry.as26_tds || 0, companyName: entry.source || 'Company from Portal', companyPAN: entry.pan || '', deductorTAN: entry.tan || '', isin: '', category: 'EQUITY', q1: 0, q2: 0, q3: 0, q4: 0, q5: 0 };
}

function business(entries: ReconciledEntry[]): Presumptive44AD | Presumptive44ADA {
  const professional = entries.every((entry) => (entry.section || '').replace(/\s/g, '').toUpperCase() === '194J');
  const turnover = entries.reduce((sum, entry) => sum + (entry.final_amount || 0), 0);
  const common = { id: `recon-business-${professional ? '44ada' : '44ad'}`, businessName: entries[0]?.source || 'Imported business', natureCode: '', description: 'Imported from reconciled portal data', declaredIncome: Math.round(turnover * (professional ? 0.5 : 0.06)), gstinTurnovers: [], financialParticulars: createEmptyFinancialParticulars() };
  return professional ? { ...common, scheme: '44ADA', grossReceipts: turnover, digitalReceipts: turnover, nonDigitalReceipts: 0 } : { ...common, scheme: '44AD', digitalReceipts: turnover, nonDigitalReceipts: 0, digitalPresumptiveIncome: Math.round(turnover * 0.06), nonDigitalPresumptiveIncome: 0 };
}

/** Maps reconciled AIS/TIS/26AS results directly into canonical draft fields. */
export function mapReconciledToDraftPatch(results: ReconciledResults | null | undefined): ReturnDraftPatch {
  if (!results) return {};
  const entries = allEntries(results);
  const salaries = entries.filter((entry) => (entry.category || '').toLowerCase() === 'salary');
  const interests = entries.filter((entry) => (entry.category || '').toLowerCase().includes('interest') && !(entry.category || '').toLowerCase().includes('from securities'));
  const dividends = entries.filter((entry) => (entry.category || '').toLowerCase() === 'dividend');
  const businesses = entries.filter((entry) => entry.income_head === 'Profits and Gains of Business or Profession');
  const tdsRows = entries.filter((entry) => entry.credit_type !== 'TCS' && (entry.as26_tds || 0) > 0);
  const cgPatch = mapCapitalGainsEvidence(results.capital_gain_evidence);
  return {
    employers: salaries.map(employer),
    otherSources: { interest: interests.map(interest), dividends: dividends.map(dividend) },
    taxes: { tds: tdsRows.map(tds) },
    businesses: businesses.length ? [business(businesses)] : undefined,
    capitalGainsSchedule: cgPatch.capitalGainsSchedule,
    provenance: [{ source: 'AIS', importedAt: new Date().toISOString(), reference: results.metadata.pan || results.metadata.financial_year || '' }],
  };
}
