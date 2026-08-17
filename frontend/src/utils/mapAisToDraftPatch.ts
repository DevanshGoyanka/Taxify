import {
  EMPTY_TDS_CREDIT,
  type DividendIncome,
  type Employer,
  type InterestIncome,
  type TdsCredit,
} from '../domain/returns/types';
import type { ReturnDraftPatch } from '../domain/returns/draftPatch';
import { createReconciliationEvidence } from '../domain/returns/evidence';
import { classifyAisEntry } from '../domain/returns/sourceClassification';
import { normalizeNatureOfEmployment } from './normalizeNatureOfEmployment';

interface PortalDetail {
  data?: Record<string, unknown>;
  sr_no?: string | number;
}
interface PortalEntry {
  sr_no?: string | number;
  information_code?: string;
  information_description?: string;
  information_source?: string;
  institution_pan?: string;
  amount?: number;
  category?: string;
  section?: string;
  income_head?: string;
  detail_header?: string[];
  details?: PortalDetail[];
}
export interface AisImportData {
  income_heads?: Record<string, { entries?: PortalEntry[] }>;
  summary?: { total_tds?: number };
}

function hashId(prefix: string, ...values: unknown[]): string {
  const text = values.map((value) => String(value ?? '')).join('|');
  let hash = 2166136261;
  for (let index = 0; index < text.length; index += 1) {
    hash ^= text.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return `${prefix}-${(hash >>> 0).toString(36)}`;
}

function originOf(entry: PortalEntry): { name: string; tan: string } {
  const raw = entry.information_source || '';
  const match = raw.match(/^(.+?)\s*\(([^)]+)\)\s*$/);
  return {
    name: match?.[1]?.trim() || raw.trim(),
    tan: match?.[2]?.split('.')[0]?.trim() || '',
  };
}

function numberValue(value: unknown): number {
  const parsed = Number.parseFloat(String(value ?? '0').replace(/,/g, ''));
  return Number.isFinite(parsed) ? parsed : 0;
}

/** Sums a detail-table column matching any of the matchers (ACTIVE rows only). */
function activeSum(entry: PortalEntry, ...matchers: string[]): number {
  const header = entry.detail_header || [];
  if (header.length === 0) return 0;
  const columnIndex = header.findIndex((item) =>
    matchers.some((matcher) => item.toUpperCase().includes(matcher)),
  );
  if (columnIndex < 0) return 0;
  const statusIndex = header.length - 1;
  return (entry.details || []).reduce((sum, detail) => {
    if (statusIndex >= 0
      && String(detail.data?.[`col_${statusIndex}`] || '').toUpperCase() !== 'ACTIVE') {
      return sum;
    }
    return sum + numberValue(detail.data?.[`col_${columnIndex}`]);
  }, 0);
}

/** Gross amount for an entry, preferring the ACTIVE detail rows then amount. */
function grossOf(entry: PortalEntry, ...matchers: string[]): number {
  return activeSum(entry, ...matchers) || entry.amount || 0;
}

function buildEmployer(entry: PortalEntry): Employer {
  const origin = originOf(entry);
  const basic = grossOf(entry, '17(1)', 'SALARY', 'GROSS SALARY');
  const perquisites = activeSum(entry, 'VALUE OF PERQUISITES', 'PERQUISITE');
  const profitsInLieu = activeSum(entry, 'PROFITS IN LIEU', 'PROFIT IN LIEU');
  const tds = activeSum(entry, 'TDS DEDUCTED');
  return {
    id: `employer-${(origin.tan || origin.name || 'unknown').trim().toUpperCase()}`,
    customEmployerName: origin.name,
    employerName: origin.name || 'Employer from AIS',
    employerTAN: origin.tan,
    natureOfEmployment: normalizeNatureOfEmployment('OTH'),
    employerAddress: '', employerCity: '', employerStateCode: '',
    employerPinCode: '', employerZipCode: '',
    salaryNatureRows: [], perquisiteNatureRows: [], section10ExemptionRows: [],
    basic, da: 0, commission: 0, hra: 0, bonus: 0, allowances: 0, lta: 0,
    otherAllowance: 0, arrearSalary: 0, perquisites, profitsInLieu, rentPaid: 0,
    city: '', isMetroCity: false, isGovernmentEmployee: false,
    isDisabledEmployee: false, commutedPension: 0, gratuity: 0,
    leaveEncashment: 0, averageMonthlySalary: 0, yearsOfService: 0,
    unavailedLeaveDays: 0, actualLtaFare: 0, isDomesticTravel: true,
    journeysInBlock: 0, ltaExempt: 0, numberOfChildren: 0,
    gratuityAlsoReceived: false, transportAllowance: 0,
    childrenEducationAllowance: 0, hostelExpenditureAllowance: 0,
    uniformAllowance: 0, entertainmentAllowance: 0, professionalTax: 0,
    vrsCompensation: 0, retrenchmentCompensation: 0, otherExempt: 0,
    tdsDeducted: tds, employerNPS: 0,
  };
}

function buildInterest(entry: PortalEntry, kind: InterestIncome['kind']): InterestIncome {
  const origin = originOf(entry);
  const gross = grossOf(entry, 'INTEREST AMOUNT', 'AMOUNT PAID', 'AMOUNT PAID/CREDITED');
  const tds = activeSum(entry, 'TDS DEDUCTED');
  return {
    id: hashId('ais-interest', entry.information_code, origin.tan, entry.amount),
    kind, grossAmount: gross, tdsDeducted: tds, bankName: origin.name,
    accountType: kind === 'SAVINGS_BANK' ? 'SAVINGS' : 'FD', accountNumber: '',
    ifscCode: '', postOfficeName: '', accountNumberPO: '', nscCertificateNumber: '',
    yearOfPurchase: 0, scssAccountNumber: '', dateOfOpening: '',
    deductorName: origin.name, deductorTAN: origin.tan, remarks: '',
  };
}

function buildDividend(entry: PortalEntry): DividendIncome {
  const origin = originOf(entry);
  const gross = grossOf(entry, 'DIVIDEND AMOUNT', 'AMOUNT');
  return {
    id: hashId('ais-dividend', origin.tan, entry.amount), section: '194',
    grossAmount: gross, tdsDeducted: 0,
    companyName: origin.name || 'Dividend from AIS',
    companyPAN: entry.institution_pan || '', deductorTAN: origin.tan, isin: '',
    category: entry.information_code?.includes('018') ? 'MUTUAL_FUND' : 'EQUITY',
    q1: 0, q2: 0, q3: 0, q4: 0, q5: 0,
  };
}

function buildTds(entry: PortalEntry): TdsCredit {
  const origin = originOf(entry);
  const code = (entry.information_code || '').toUpperCase();
  const section = code === 'TDS-ANN.II-SAL' ? '192' : code.replace('TDS-', '') || '194A';
  const gross = grossOf(entry, 'AMOUNT PAID', 'AMOUNT PAID/CREDITED', 'GROSS AMOUNT');
  const tax = activeSum(entry, 'TDS DEDUCTED');
  return {
    ...structuredClone(EMPTY_TDS_CREDIT),
    id: hashId('ais-tds', origin.tan, section, entry.amount),
    section, deductorName: origin.name, deductorTAN: origin.tan,
    deductorPAN: entry.institution_pan || '', grossAmount: gross, taxDeducted: tax,
    verified26AS: true, schedule: section === '192' ? 'TDS1' : 'TDS2',
    headOfIncome: section === '192' ? 'NA' : 'OS', claimOutOfTotTDSOnAmtPaid: tax,
  };
}

function hasDestination(entry: PortalEntry, destination: string): boolean {
  return classifyAisEntry(entry.information_code, entry.category).canonicalDestination === destination;
}

function isSavingsInterest(entry: PortalEntry): boolean {
  const code = (entry.information_code || '').toUpperCase();
  const category = (entry.category || '').toLowerCase();
  return code.includes('(SB)') || category.includes('savings');
}

function isTermDepositInterest(entry: PortalEntry): boolean {
  const code = (entry.information_code || '').toUpperCase();
  const category = (entry.category || '').toLowerCase();
  return code.includes('(TD)') || category.includes('deposit')
    || category.includes('term') || category.includes('fixed');
}

function isInterestEntry(entry: PortalEntry): boolean {
  return hasDestination(entry, 'otherSources.interest');
}

function isDividendEntry(entry: PortalEntry): boolean {
  return hasDestination(entry, 'otherSources.dividends');
}

function isSalaryEntry(entry: PortalEntry): boolean {
  return hasDestination(entry, 'employers');
}

function isTdsEntry(entry: PortalEntry): boolean {
  return hasDestination(entry, 'taxes.tds');
}

/** Maps raw AIS import data into canonical draft fields. */
export function mapAisToDraftPatch(data: AisImportData | null | undefined): ReturnDraftPatch {
  if (!data) return {};
  const entries = Object.values(data.income_heads || {}).flatMap((head) => head.entries || []);

  const salaryEntries = entries.filter(isSalaryEntry);
  const detailedSalaryEntries = salaryEntries.filter(
    (entry) => (entry.information_code || '').toUpperCase() === 'TDS-ANN.II-SAL',
  );
  const employerSource = detailedSalaryEntries.length > 0 ? detailedSalaryEntries : salaryEntries;
  const employersById = new Map<string, Employer>();
  for (const entry of employerSource) {
    const employer = buildEmployer(entry);
    employersById.set(employer.id, employer);
  }
  const employers = [...employersById.values()];

  const sftInterest = entries
    .filter((entry) => isInterestEntry(entry) && !isSalaryEntry(entry) && !isTdsEntry(entry))
    .map((entry) => buildInterest(
      entry,
      isSavingsInterest(entry) ? 'SAVINGS_BANK' : 'TERM_DEPOSIT',
    ));
  // Deduplicate B1 TDS-interest entries that duplicate a B2 SFT interest
  // entry from the same deductor — the same income is reported twice.
  const seenInterestNames = new Set(sftInterest.map((item) => item.deductorName.toLowerCase()));
  const b1Interest = entries
    .filter((entry) => isTdsEntry(entry) && isInterestEntry(entry) && !isSalaryEntry(entry))
    .map((entry) => buildInterest(
      entry,
      isSavingsInterest(entry) ? 'SAVINGS_BANK' : 'TERM_DEPOSIT',
    ))
    .filter((item) => !seenInterestNames.has(item.deductorName.toLowerCase()));

  const dividends = entries.filter(isDividendEntry).map(buildDividend);

  const tdsEntries = entries.filter(isTdsEntry).map(buildTds);

  const evidence = entries.map((entry, index) => {
    const origin = originOf(entry);
    return createReconciliationEvidence({
      source: 'AIS', code: entry.information_code, section: entry.section, incomeHead: entry.income_head,
      category: entry.category, description: entry.information_description, sourceName: origin.name, sourceIdentifier: origin.tan,
      reportedAmount: entry.amount, processedAmount: entry.amount, taxAmount: activeSum(entry, 'TDS DEDUCTED'), status: entry.information_code,
      raw: entry as unknown as Record<string, unknown>,
      identity: [entry.information_code, entry.section, entry.category, origin.tan, entry.amount, entry.sr_no, index],
    });
  });

  return {
    employers,
    otherSources: { interest: [...sftInterest, ...b1Interest], dividends },
    taxes: { tds: tdsEntries },
    provenance: [{ source: 'AIS', importedAt: new Date().toISOString(), reference: 'direct-import' }],
    reconciliation: { evidence, discrepancies: [] },
  };
}
