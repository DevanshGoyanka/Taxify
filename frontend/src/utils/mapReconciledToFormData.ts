/**
 * mapReconciledToFormData — convert ReconciledResults → flat formData update.
 *
 * Maps reconciled income heads to the existing formData shape used by
 * ITRComputationPage. Follows the same entry-structure patterns as the
 * 26AS import path (e.g., employerEntries, bankInterestEntries, etc.).
 *
 * Category→IncomeHead mapping mirrors reconciliation.py's CATEGORY_TO_INCOME_HEAD.
 */

import type { ReconciledResults, ReconciledEntry } from '../api/itrAutomation';

// ── Category helpers ─────────────────────────────────────────────────────────

function isSalaryCat(entry: ReconciledEntry): boolean {
  // ONLY actual salary (Section 192 TDS). Do NOT match business receipts
  // (194H/194C/194J) or professional fees — those go to Business/Profession.
  const c = entry.category.toLowerCase();
  return c === 'salary';
}

function isBusinessCat(entry: ReconciledEntry): boolean {
  // Entries that belong under "Profits and Gains of Business or Profession"
  // or should be routed to bizTurnover/bpNetProfit form fields.
  // These include: 194C (contracts), 194J (professional),
  // 194M (certain payments), and any other business-like receipts.
  // Note: 194H (commission/brokerage) is classified as Other Sources.
  return entry.income_head === 'Profits and Gains of Business or Profession';
}

const PROFESSIONAL_SECTIONS = new Set(['194J']);
const BUSINESS_SECTIONS = new Set([
  '194C', '194I', '194M', '194N', '194O', '194Q', '194S',
  '194D', '206C', '206CE', '206CF',
]);

function detectPresumptiveScheme(entries: ReconciledEntry[]): '44AD' | '44ADA' | 'Regular' {
  let hasProfessional = false;
  let hasBusiness = false;

  for (const entry of entries) {
    const sec = (entry.section || '').replace(/\s+/g, '').toUpperCase();
    if (PROFESSIONAL_SECTIONS.has(sec)) hasProfessional = true;
    if (BUSINESS_SECTIONS.has(sec)) hasBusiness = true;
  }

  // If all entries are professional (194J), classify as 44ADA
  if (hasProfessional && !hasBusiness) return '44ADA';
  // If entries have business sections, classify as 44AD
  if (hasBusiness) return '44AD';
  // Default: 44AD for generic business receipts
  return '44AD';
}

function computeStatutoryMinimum(turnover: number, scheme: '44AD' | '44ADA' | 'Regular'): number {
  if (scheme === '44ADA') return Math.round(turnover * 0.50);
  if (scheme === '44AD') return Math.round(turnover * 0.06);
  return turnover;
}

function isDividendCat(entry: ReconciledEntry): boolean {
  return entry.category.toLowerCase() === 'dividend';
}

function isInterestCat(entry: ReconciledEntry): boolean {
  const c = entry.category.toLowerCase();
  return c.includes('interest') && !c.includes('from securities');
}

function isCapitalGainsCat(entry: ReconciledEntry): boolean {
  return entry.income_head === 'Capital Gains' ||
    entry.category.toLowerCase().includes('sale of') ||
    entry.category.toLowerCase().includes('purchase of') ||
    entry.category.toLowerCase().includes('property');
}

function isRefundCat(entry: ReconciledEntry): boolean {
  return entry.category.toLowerCase() === 'refund';
}

// ── Entry builders ───────────────────────────────────────────────────────────

function buildEmployerEntry(entry: ReconciledEntry) {
  return {
    employerName: entry.source || 'Employer from Portal',
    employerTAN: '',
    employerPAN: entry.present_in?.as26 ? String(entry.as26_tds || '') : '',
    basic: entry.final_amount,
    da: 0,
    hra: 0,
    bonus: 0,
    allowances: 0,
    perquisites: 0,
    professionalTax: 0,
    tdsDeducted: entry.as26_tds || 0,
    grossSalary: entry.final_amount,
    netSalary: entry.final_amount - (entry.as26_tds || 0),
    verified26AS: entry.present_in?.as26 || false,
  };
}

function buildDividendEntry(entry: ReconciledEntry) {
  return {
    id: `div-${entry.source.replace(/[^a-zA-Z0-9]/g, '').slice(0, 8)}-${Date.now().toString(36)}`,
    section: '194' as const,
    grossAmount: entry.final_amount,
    tdsDeducted: entry.as26_tds || 0,
    companyName: entry.source || 'Company from Portal',
    companyPAN: entry.present_in?.as26 ? '' : '',
    deductorTAN: '',
    isin: '',
    category: 'EQUITY' as const,
    // Legacy fields for backward compatibility with BankInterestEntryManager
    dividendAmount: entry.final_amount,
  };
}

/**
 * Build a CBDT-compliant InterestEntry from a reconciled entry.
 * Maps reconciliation categories to ITD Schedule OS tags (17A-17H).
 */
function buildInterestEntry(entry: ReconciledEntry) {
  const cat = entry.category.toLowerCase();
  let itdTag: string;
  if (cat === 'interest from savings bank') {
    itdTag = 'SAVINGS_BANK';     // 17A
  } else if (cat === 'interest from deposit') {
    itdTag = 'TERM_DEPOSIT';     // 17B
  } else {
    itdTag = 'OTHER';            // 17G/17H
  }

  return {
    id: `int-${entry.source.replace(/[^a-zA-Z0-9]/g, '').slice(0, 8)}-${Date.now().toString(36)}`,
    itdTag,
    grossAmount: entry.final_amount,
    tdsDeducted: entry.as26_tds || 0,
    bankName: entry.source || 'Bank from Portal',
    accountType: itdTag === 'TERM_DEPOSIT' ? 'FD' as const : 'SAVINGS' as const,
    accountNumber: '',
    ifscCode: '',
    deductorName: entry.source || '',
    deductorTAN: '',
    section: entry.section || (itdTag === 'SAVINGS_BANK' ? '194A' : '194A'),
  };
}

function buildBankInterestEntry(entry: ReconciledEntry) {
  return {
    bankName: entry.source || 'Bank from Portal',
    accountNumber: '',
    accountType: 'SAVINGS' as const,
    interestEarned: entry.final_amount,
    tdsDeducted: entry.as26_tds || 0,
    deductorTAN: '',
    section: entry.section || '',
  };
}

function buildCapitalGainsEntry(entry: ReconciledEntry) {
  const cat = entry.category.toLowerCase();
  const isProperty = cat.includes('property') || cat.includes('land');
  return {
    assetType: isProperty ? 'PROPERTY' : 'SECURITIES',
    assetDescription: entry.source || entry.description || '',
    saleConsideration: entry.final_amount,
    costOfAcquisition: 0,
    costOfImprovement: 0,
    expenditureOnTransfer: 0,
    indexedCostAcquisition: 0,
    indexedCostImprovement: 0,
    shortTerm: false, // default; can be refined per section
    section: entry.section || '',
    verified26AS: entry.present_in?.as26 || false,
  };
}

function buildTdsEntry(entry: ReconciledEntry) {
  return {
    section: entry.section || '192',
    deductorName: entry.source || 'Deductor from Portal',
    deductorTAN: '',
    deductorPAN: '',
    incomeAmount: entry.final_amount,
    tdsDeducted: entry.as26_tds || 0,
    certificateNo: '',
    deductionDate: '',
    uniqueTransactionNo: '',
    financialYear: '',
    verified26AS: entry.present_in?.as26 || false,
    claimedInReturn: true,
  };
}

// ── Main mapper ──────────────────────────────────────────────────────────────

export interface MapReconciledResult {
  formDataUpdate: Record<string, any>;
  discrepancies: ReconciledEntry[];
  summary: {
    salaryEntries: number;
    businessEntries: number;
    dividendEntries: number;
    interestEntries: number;
    capitalGainsEntries: number;
    tdsEntries: number;
    totalIncome: number;
    totalTds: number;
  };
}

export function mapReconciledToFormData(results: ReconciledResults): MapReconciledResult {
  const allEntries: ReconciledEntry[] = [];
  for (const head of Object.values(results.income_heads)) {
    allEntries.push(...head.entries);
  }

  // Group by category type
  const salaryEntries = allEntries.filter(isSalaryCat);
  const businessEntries = allEntries.filter(isBusinessCat);
  const dividendEntries = allEntries.filter(isDividendCat);
  const interestEntries = allEntries.filter(isInterestCat);
  const capitalGainsEntries = allEntries.filter(isCapitalGainsCat);
  const tdsEntries = allEntries.filter(e => (e.as26_tds || 0) > 0);
  const discrepancies = allEntries.filter(e => e.has_discrepancy);

  // ── Interest: split by sub-category ────────────────────────────────────────
  // Taxify's formData has separate fields: interestSB, interestFD, interestRD,
  // nscInterest, scssInterest, postOfficeInterest, otherInterest.
  // In the tax.py compute endpoint these are SUMMED:
  //   savings_bank = interestSB + postOfficeInterest
  //   fixed_deposit = interestFD + interestRD + nscInterest + scssInterest + otherInterest
  //   income_chargeable = savings_bank + fixed_deposit + fp + div
  //
  // If we set both interestSB = totalInterest AND interestFD = totalInterest,
  // the engine adds them → 2×. So we MUST split by the actual category.
  //
  // Known interest sub-categories from reconciliation:
  //   "interest from savings bank" → interestSB
  //   "interest from deposit"      → interestFD
  //   everything else             → interestSB (default)

  let interestSB = 0;
  let interestFD = 0;

  for (const entry of interestEntries) {
    const cat = entry.category.toLowerCase();
    if (cat === 'interest from savings bank') {
      interestSB += entry.final_amount;
    } else if (cat === 'interest from deposit') {
      interestFD += entry.final_amount;
    } else {
      // Unknown interest category → default to savings bank (interestSB)
      interestSB += entry.final_amount;
    }
  }
  const totalInterest = interestSB + interestFD;

  // ── Dividends: only set dividendShares, never dividends ────────────────────
  // "dividends" is a legacy field that tax.py also sums into total_dividend.
  // Setting both dividendShares=X and dividends=X → total_dividend=2X.
  const totalDividend = dividendEntries.reduce((s, e) => s + e.final_amount, 0);

  const totalSalary = salaryEntries.reduce((s, e) => s + e.final_amount, 0);
  const totalBusiness = businessEntries.reduce((s, e) => s + e.final_amount, 0);
  const totalCapitalGains = capitalGainsEntries.reduce((s, e) => s + e.final_amount, 0);
  const totalTds = allEntries.reduce((s, e) => s + (e.as26_tds || 0), 0);

  const formDataUpdate: Record<string, any> = {
    // ── Salary ──
    employerEntries: salaryEntries.length > 0
      ? salaryEntries.map(buildEmployerEntry)
      : [],
    basic: totalSalary, // primary salary field

    // ── Dividends ──
    dividendEntries: dividendEntries.length > 0
      ? dividendEntries.map(buildDividendEntry)
      : [],
    dividendShares: totalDividend,

    // ── Interest ──
    // New CBDT-compliant InterestEntry[] (used by InterestEntryManager in OS tab)
    interestEntries: interestEntries.length > 0
      ? interestEntries.map(buildInterestEntry)
      : [],
    // Legacy bankInterestEntries (used by BankInterestEntryManager in old layout)
    bankInterestEntries: interestEntries.length > 0
      ? interestEntries.map(buildBankInterestEntry)
      : [],
    interestSB,
    interestFD,

    // ── Business / Profession ──
    // Detect the correct presumptive scheme from TDS section codes:
    // 194J → professional income (44ADA), 194H/194C/194M → business (44AD).
    // Declared income defaults to the statutory minimum, not full turnover.
    bizTurnover: totalBusiness > 0 ? totalBusiness : undefined,
    bpNetProfit: totalBusiness > 0
      ? computeStatutoryMinimum(totalBusiness, detectPresumptiveScheme(businessEntries))
      : undefined,
    bizDeclared: totalBusiness > 0
      ? computeStatutoryMinimum(totalBusiness, detectPresumptiveScheme(businessEntries))
      : undefined,
    bizPresumptive: totalBusiness > 0 ? detectPresumptiveScheme(businessEntries) : undefined,

    // ── Capital Gains ──
    capitalGainTransactions: capitalGainsEntries.length > 0
      ? capitalGainsEntries.map(buildCapitalGainsEntry)
      : [],
    ltcg112APre: totalCapitalGains > 0 ? totalCapitalGains : 0,

    // ── TDS ──
    tdsEntries: tdsEntries.length > 0
      ? tdsEntries.map(buildTdsEntry)
      : [],
    tdsS192: totalSalary > 0 ? totalTds : 0,
    tds194A: totalInterest > 0 ? totalTds : 0,
    tdsOther: (!totalSalary && !totalInterest) ? totalTds : 0,

    // ── Store reconciliation metadata for warning banner ──
    importedFromRecon: {
      pan: results.metadata.pan,
      name: results.metadata.name,
      financialYear: results.metadata.financial_year,
      totalIncome: results.summary.total_final_income,
      totalDiscrepancies: results.summary.total_discrepancies,
      matchedAllThree: results.summary.matched_all_three,
      matchedTwo: results.summary.matched_two,
      importedAt: new Date().toISOString(),
    },
  };

  // Preserve existing entries if new ones are empty (don't erase user data)
  // Note: caller uses spread-merge, so empty arrays will overwrite. We handle
  // this by only setting multi-entry arrays when there's data.
  const cleanUpdate: Record<string, any> = {};
  for (const [key, val] of Object.entries(formDataUpdate)) {
    if (val === undefined) {
      // Skip undefined — don't overwrite existing form data
      continue;
    }
    if (Array.isArray(val) && val.length === 0 && key !== 'employerEntries') {
      // Skip empty arrays (caller will use ?? to preserve existing)
      continue;
    }
    cleanUpdate[key] = val;
  }

  return {
    formDataUpdate: cleanUpdate,
    discrepancies,
    summary: {
      salaryEntries: salaryEntries.length,
      businessEntries: businessEntries.length,
      dividendEntries: dividendEntries.length,
      interestEntries: interestEntries.length,
      capitalGainsEntries: capitalGainsEntries.length,
      tdsEntries: tdsEntries.length,
      totalIncome: results.summary.total_final_income,
      totalTds,
    },
  };
}
