/**
 * mapReconciledToFormData — convert ReconciledResults → flat formData update.
 *
 * Maps reconciled income heads to the existing formData shape used by
 * ITRComputationPage. Follows the same entry-structure patterns as the
 * 26AS import path (e.g., employerEntries, bankInterestEntries, etc.).
 *
 * Category→IncomeHead mapping mirrors reconciliation.py's CATEGORY_TO_INCOME_HEAD.
 */

import type {
  CapitalGainEvidence,
  ReconciledResults,
  ReconciledEntry,
} from '../api/itrAutomation';

// ── Category helpers ─────────────────────────────────────────────────────────

function isSalaryCat(entry: ReconciledEntry): boolean {
  // ONLY actual salary (Section 192 TDS). Do NOT match business receipts
  // (194H/194C/194J) or professional fees — those go to Business/Profession.
  const c = (entry.category || '').toLowerCase();
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
  return (entry.category || '').toLowerCase() === 'dividend';
}

function isInterestCat(entry: ReconciledEntry): boolean {
  const c = (entry.category || '').toLowerCase();
  return c.includes('interest') && !c.includes('from securities');
}

function isCapitalGainsCat(entry: ReconciledEntry): boolean {
  return entry.income_head === 'Capital Gains' ||
    (entry.category || '').toLowerCase().includes('sale of') ||
    (entry.category || '').toLowerCase().includes('purchase of') ||
    (entry.category || '').toLowerCase().includes('property');
}

function isRefundCat(entry: ReconciledEntry): boolean {
  return (entry.category || '').toLowerCase() === 'refund';
}

// ── Entry builders ───────────────────────────────────────────────────────────

function stableEntryId(prefix: string, entry: ReconciledEntry): string {
  const identity = entry.source_id || `${entry.category || ''}|${entry.source}|${entry.final_amount}`;
  let hash = 2166136261;
  for (let index = 0; index < identity.length; index += 1) {
    hash ^= identity.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return `${prefix}-${(hash >>> 0).toString(36)}`;
}

function buildEmployerEntry(entry: ReconciledEntry) {
  return {
    id: stableEntryId('salary', entry),
    employerName: entry.source || 'Employer from Portal',
    employerTAN: entry.tan || '',
    employerPAN: entry.pan || '',
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
    id: stableEntryId('div', entry),
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
  const cat = (entry.category || '').toLowerCase();
  let itdTag: string;
  if (cat === 'interest from savings bank') {
    itdTag = 'SAVINGS_BANK';     // 17A
  } else if (cat === 'interest from deposit') {
    itdTag = 'TERM_DEPOSIT';     // 17B
  } else {
    itdTag = 'OTHER';            // 17G/17H
  }

  return {
    id: stableEntryId('int', entry),
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

function capitalGainAssetType(evidence: CapitalGainEvidence): string {
  const code = (evidence.information_code || '').toUpperCase();
  const cat  = (evidence.category || '').toLowerCase();
  // Information code is authoritative; broad category labels mention both
  // securities and mutual funds and cannot distinguish SFT-17 from SFT-18.
  if (code.includes('SFT-17')) return 'LISTED_EQUITY';
  if (code.includes('SFT-18')) return 'EQUITY_ORIENTED_MUTUAL_FUND';
  if (cat.includes('mutual fund')) return 'EQUITY_ORIENTED_MUTUAL_FUND';
  if (cat.includes('securities')) return 'LISTED_EQUITY';
  return 'EQUITY_ORIENTED_MUTUAL_FUND';
}

function buildCapitalGainEvidenceEntry(
  evidence: CapitalGainEvidence,
  allEvidence: CapitalGainEvidence[],
) {
  const isPurchase = evidence.side === 'PURCHASE';
  const isSale = evidence.side === 'SALE';
  const description = evidence.security_name || evidence.security_class || '';
  const isoDate = (raw: string | undefined): string => {
    if (!raw) return '';
    const trimmed = raw.trim();
    if (!trimmed) return '';
    // Convert DD/MM/YYYY to YYYY-MM-DD
    const m = trimmed.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
    if (m) return `${m[3]}-${m[2].padStart(2,'0')}-${m[1].padStart(2,'0')}`;
    // Accept already-ISO YYYY-MM-DD.  Reject anything else (e.g. quarters
    // like "Q2(Jul-Sep)" that the AIS reconciliation emits for SFT-18(Pur)
    // purchase aggregates — those are not real dates and must not be passed
    // through to the backend's strict ISO date parser.
    if (/^\d{4}-\d{2}-\d{2}$/.test(trimmed)) return trimmed;
    return '';
  };

  // For sale rows, attempt to derive the acquisition date by matching to
  // the corresponding purchase evidence. AIS reports disposals and purchases
  // as separate rows; the purchase row has the transaction_date we need.
  let derivedAcquisitionDate = '';
  if (isSale) {
    const isin = evidence.security_identifier || '';
    const name = (evidence.security_name || evidence.security_class || '').toLowerCase();
    // Find a purchase row matching by ISIN (preferred) or scheme name.
    const match = allEvidence.find(e => {
      if (e.side !== 'PURCHASE') return false;
      if (isin && e.security_identifier === isin) return true;
      const eName = (e.security_name || e.security_class || '').toLowerCase();
      if (name && eName === name) return true;
      return false;
    });
    if (match?.transaction_date) {
      derivedAcquisitionDate = isoDate(match.transaction_date);
    }
  }

  return {
    id: `cg-${evidence.evidence_id}`,
    transactionId: evidence.evidence_id,
    recordKind: (isSale && evidence.granularity === 'TRANSACTION_DETAIL'
      && evidence.transaction_date && evidence.acquisition_cost != null
      && evidence.asset_type?.toLowerCase().includes('long'))
      ? 'TRANSACTION' as const
      : 'EVIDENCE' as const,
    evidenceSide: evidence.side,  // 'PURCHASE' or 'SALE'
    quarter: evidence.quarter || '',
    assetType: capitalGainAssetType(evidence),
    description,
    assetDescription: description,
    // For purchases, the transaction_date IS the acquisition date.
    // For sales, use the derived date from the matching purchase evidence.
    acquisitionDate: isPurchase ? isoDate(evidence.transaction_date) : derivedAcquisitionDate,
    purchaseDate: isPurchase ? isoDate(evidence.transaction_date) : derivedAcquisitionDate,
    transferDate: isSale ? isoDate(evidence.transaction_date) : '',
    saleDate: isSale ? isoDate(evidence.transaction_date) : '',
    actualCost: isPurchase ? evidence.amount : (evidence.acquisition_cost ?? 0),
    purchaseCost: isPurchase ? evidence.amount : (evidence.acquisition_cost ?? 0),
    saleValue: isSale ? evidence.amount : 0,
    saleCost: isSale ? evidence.amount : 0,
    transferExpenses: 0,
    expenses: 0,
    acquiredBefore31Jan2018: evidence.acquired_before_31_jan_2018 ?? undefined,
    fmv31Jan2018: evidence.fair_market_value ?? undefined,
    fmvJan2018: evidence.fair_market_value ?? undefined,
    isin: evidence.security_identifier || '',
    quantity: evidence.quantity ?? undefined,
    section: evidence.information_code,
    importSource: evidence.reporting_source || '',
    accountId: evidence.account_id || '',
    acquisitionMode: evidence.acquisition_mode || evidence.debit_type || '',
    debitType: evidence.debit_type || '',
    creditType: evidence.credit_type || '',
    salePricePerUnit: evidence.sale_price_per_unit ?? undefined,
    sttAmount: evidence.stt_amount ?? undefined,
    aisHoldingPeriod: evidence.asset_type || undefined,
    unitFmv: evidence.unit_fmv ?? undefined,
    sttPaidOnAcquisition: evidence.stt_paid_on_acquisition ?? undefined,
    sttPaidOnTransfer: evidence.stt_paid_on_transfer ?? (isSale && (evidence.stt_amount ?? 0) > 0 ? true : undefined),
    recognizedExchange: evidence.recognized_exchange ?? undefined,
  };
}

function buildTdsEntry(entry: ReconciledEntry) {
  const sec = (entry.section || '').replace(/\s+/g, '').toUpperCase();
  // Section 192 is salary TDS — goes to TDS1 which doesn't require TAN.
  // All other sections require deductor TAN per CBDT rules.
  const isSalaryTds = sec === '192' || sec === 'S192';
  return {
    id: stableEntryId('tds', entry),
    section: sec || '192',
    deductorName: entry.source || 'Deductor from Portal',
    deductorTAN: entry.tan || '',
    deductorPAN: entry.pan || '',
    incomeAmount: entry.final_amount,
    tdsDeducted: entry.as26_tds || 0,
    certificateNo: '',
    deductionDate: '',
    uniqueTransactionNo: '',
    financialYear: '',
    verified26AS: entry.present_in?.as26 || false,
    claimedInReturn: true,
    _isSalaryTds: isSalaryTds,
  };
}

function buildTcsEntry(entry: ReconciledEntry) {
  return {
    id: stableEntryId('tcs', entry),
    collectorName: entry.source || 'Collector from Form 26AS',
    collectorTAN: entry.tan || '',
    grossAmount: entry.amounts?.as26 || 0,
    taxCollected: entry.as26_tcs || 0,
    tcsCollected: entry.as26_tcs || 0,
    section: (entry.section || '206C').replace(/\s+/g, '').toUpperCase(),
    financialYear: '',
    verified26AS: true,
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
    tcsEntries: number;
    totalIncome: number;
    totalTds: number;
    totalTcs: number;
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
  const tdsEntries = allEntries.filter(e => e.credit_type !== 'TCS' && (e.as26_tds || 0) > 0);
  const tcsEntries = allEntries.filter(e => e.credit_type === 'TCS' && (e.as26_tcs || 0) > 0);
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
    const cat = (entry.category || '').toLowerCase();
    if (cat === 'interest from savings bank') {
      interestSB += entry.final_amount;
    } else if (cat === 'interest from deposit') {
      interestFD += entry.final_amount;
    } else {
      // Unknown interest category → default to savings bank (interestSB)
      interestSB += entry.final_amount;
    }
  }
  const controlledSavingsInterest = results.category_controls?.['interest from savings bank'];
  const controlledDepositInterest = results.category_controls?.['interest from deposit'];
  if (controlledSavingsInterest !== undefined) interestSB = controlledSavingsInterest;
  if (controlledDepositInterest !== undefined) interestFD = controlledDepositInterest;
  const totalInterest = interestSB + interestFD;

  // ── Dividends: only set dividendShares, never dividends ────────────────────
  // "dividends" is a legacy field that tax.py also sums into total_dividend.
  // Setting both dividendShares=X and dividends=X → total_dividend=2X.
  const rawDividendTotal = dividendEntries.reduce((s, e) => s + e.final_amount, 0);
  const controlledDividendTotal = results.category_controls?.dividend;
  const totalDividend = controlledDividendTotal ?? rawDividendTotal;

  const rawSalaryTotal = salaryEntries.reduce((s, e) => s + e.final_amount, 0);
  const totalSalary = results.category_controls?.salary ?? rawSalaryTotal;
  const totalBusiness = businessEntries.reduce((s, e) => s + e.final_amount, 0);
  const presumptiveScheme = totalBusiness > 0 ? detectPresumptiveScheme(businessEntries) : undefined;
  const presumptiveIncome = presumptiveScheme
    ? computeStatutoryMinimum(totalBusiness, presumptiveScheme)
    : undefined;
  const tdsSalary = tdsEntries
    .filter(e => ['192', 'S192'].includes((e.section || '').replace(/\s+/g, '').toUpperCase()))
    .reduce((sum, entry) => sum + (entry.as26_tds || 0), 0);
  const tdsInterest = tdsEntries
    .filter(e => ['193', '194A'].includes((e.section || '').replace(/\s+/g, '').toUpperCase()))
    .reduce((sum, entry) => sum + (entry.as26_tds || 0), 0);
  const totalTds = tdsEntries.reduce((sum, entry) => sum + (entry.as26_tds || 0), 0);
  const totalTcs = tcsEntries.reduce((sum, entry) => sum + (entry.as26_tcs || 0), 0);
  const tdsOther = totalTds - tdsSalary - tdsInterest;

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
    importedCategoryControls: results.category_controls || {},
    importedCategoryControlDiscrepancies: results.category_control_discrepancies || [],

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
    bpNetProfit: presumptiveIncome,
    bizDeclared: presumptiveIncome,
    bizPresumptive: presumptiveScheme,

    // ── Capital Gains ──
    // One AIS CG entry → one row. TIS provides accepted controls for comparison.
    capitalGainTransactions: (results.capital_gain_evidence || []).map(
      (e) => buildCapitalGainEvidenceEntry(e, results.capital_gain_evidence || []),
    ),
    // Do not set ltcg112APre from reconciliation — the backend reads this
    // scalar as taxable 112A gain and will reject ITR-1 if it exceeds the
    // Rs 1,25,000 limit. The structured capitalGainTransactions rows are
    // preserved for the user to review and enter cost of acquisition manually.

    // ── TDS ──
    // Preserve every 26AS TDS row with its available provenance. Missing TAN,
    // certificate, or date remains an incomplete draft issue in the backend;
    // it must not cause the credit row to disappear.
    tdsEntries: tdsEntries.map(buildTdsEntry),
    tcsEntries: tcsEntries.map(buildTcsEntry),
    tdsS192: tdsSalary,
    tds194A: tdsInterest,
    tdsOther,

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
    if (Array.isArray(val) && val.length === 0 && key !== 'employerEntries' && key !== 'capitalGainTransactions') {
      // Most empty imports preserve prior edits. Capital-gain transactions are
      // intentionally cleared when the source contains controls but no details,
      // preventing an older aggregate-shaped import from surviving as a tax lot.
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
      capitalGainsEntries: results.capital_gain_evidence?.length || 0,
      tdsEntries: tdsEntries.length,
      tcsEntries: tcsEntries.length,
      totalIncome: results.summary.total_final_income,
      totalTds,
      totalTcs,
    },
  };
}
