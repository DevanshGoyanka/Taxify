/**
 * ITD Schema Compliant Types for Schedule OS (Income from Other Sources)
 * Based on ITR-2 AY 2026-27 JSON Schema
 * 
 * ITD Tags for Interest Income:
 * - 17A: IntrstFrmSavingBank - Bank Savings Account (194A)
 * - 17B: IntrstFrmTermDeposit - Term Deposit (194A)
 * - 17C: IntrstFrmIncmTaxRefund - IT Refund Interest (244A - No TDS)
 * - 17D: IntrstSec10XIFirstProviso - Post Office Savings (10(2)(xxi))
 * - 17E: IntrstSec10XISecondProviso - NSC Interest (10(2)(xxi)) - EXEMPT
 * - 17F: IntrstSec10XIIFirstProviso - SCSS Interest (10(2)(xii)) - EXEMPT
 * - 17G: IntrstSec10XIISecondProviso - Other Interest
 * - 17H: IntrstFrmOthers - Any other interest
 */

// ==================== INTEREST TYPES ====================

export type InterestITDTag = 
  | 'SAVINGS_BANK'      // 17A - Bank savings account
  | 'TERM_DEPOSIT'     // 17B - Fixed/Term deposit
  | 'IT_REFUND'         // 17C - IT Refund (no TDS)
  | 'POST_OFFICE'      // 17D - Post Office
  | 'NSC'              // 17E - NSC (TAXABLE)
  | 'SCSS'             // 17F - SCSS (TAXABLE)
  | 'OTHER'            // 17G/17H - Other
  | 'BONDS'            // Bonds/Debentures
  | 'SECURITIES';      // Securities

export interface InterestEntry {
  id: string;
  itdTag: InterestITDTag;
  grossAmount: number;
  tdsDeducted: number;
  
  // Bank-specific
  bankName?: string;
  accountType?: 'SAVINGS' | 'CURRENT' | 'FD';
  accountNumber?: string;
  ifscCode?: string;
  
  // Post Office specific
  postOfficeName?: string;
  accountNumberPO?: string;
  
  // NSC specific
  nscCertificateNumber?: string;
  yearOfPurchase?: number;
  
  // SCSS specific
  scssAccountNumber?: string;
  dateOfOpening?: string;
  
  // Common
  deductorName?: string;
  deductorTAN?: string;
  remarks?: string;
}

// ITD Tag display info
export const INTEREST_TAG_INFO: Record<InterestITDTag, { label: string; section: string; description: string; tdsRate: number; exempt: boolean }> = {
  SAVINGS_BANK: { label: 'Savings Account (17A)', section: '194A', description: 'Interest from bank savings account', tdsRate: 10, exempt: false },
  TERM_DEPOSIT: { label: 'Term Deposit (17B)', section: '194A', description: 'Interest from FD/RD', tdsRate: 10, exempt: false },
  IT_REFUND: { label: 'IT Refund Interest (17C)', section: '244A', description: 'Interest on income tax refund', tdsRate: 0, exempt: true },
  POST_OFFICE: { label: 'Post Office Savings (17D)', section: '194A', description: 'Interest from Post Office savings', tdsRate: 10, exempt: false },
  NSC: { label: 'NSC Interest (17E)', section: '194A', description: 'NSC accrued interest - TAXABLE', tdsRate: 10, exempt: false },
  SCSS: { label: 'SCSS Interest (17F)', section: '194A', description: 'Senior Citizen Savings Scheme - TAXABLE', tdsRate: 10, exempt: false },
  OTHER: { label: 'Other Interest (17H)', section: '194A', description: 'Any other interest income', tdsRate: 10, exempt: false },
  BONDS: { label: 'Bonds/Debentures', section: '193', description: 'Interest on bonds/securities', tdsRate: 10, exempt: false },
  SECURITIES: { label: 'Securities', section: '194A', description: 'Interest on securities', tdsRate: 10, exempt: false },
};

// ==================== DIVIDEND TYPES ====================

export type DividendSection = '10(22e)' | '10(22f)' | '194';

export interface DividendEntry {
  id: string;
  section: DividendSection;
  grossAmount: number;
  tdsDeducted: number;
  companyName: string;
  companyPAN?: string;
  deductorTAN?: string;
  isin?: string;
  category?: 'EQUITY' | 'PREFERENCE' | 'MUTUAL_FUND';
  // Quarterly breakup (Category A validation)
  q1?: number;
  q2?: number;
  q3?: number;
  q4?: number;
}

export const DIVIDEND_SECTION_INFO: Record<DividendSection, { label: string; description: string; exempt: boolean }> = {
  '10(22e)': { label: '2(22)(e) - Deemed Dividend', description: 'Deemed dividend from closely held companies (Sec 2(22)(e))', exempt: false },
  '10(22f)': { label: '2(22)(f) - Capital Reduction', description: 'Dividend on capital reduction - unlisted companies (Sec 2(22)(f))', exempt: false },
  '194': { label: '194 - Regular Dividends', description: 'Dividend taxable at normal rates (TDS u/s 194)', exempt: false },
};

// ==================== WINNINGS TYPES ====================

export type WinningsType = 'LOTTERY' | 'BETTING' | 'CARD_GAME' | 'HORSE_RACE';

export interface WinningsEntry {
  id: string;
  type: WinningsType;
  grossAmount: number;
  tdsDeducted: number;
  payerName?: string;
  payerTAN?: string;
  dateOfWinning?: string;
}

export const WINNINGS_INFO: Record<WinningsType, { label: string; section: string; taxRate: number; tdsThreshold: number }> = {
  LOTTERY: { label: 'Lottery/Betting', section: '194B', taxRate: 30, tdsThreshold: 10000 },
  BETTING: { label: 'Betting/Gambling', section: '194B', taxRate: 30, tdsThreshold: 10000 },
  CARD_GAME: { label: 'Card Game/Puzzle', section: '194B', taxRate: 30, tdsThreshold: 10000 },
  HORSE_RACE: { label: 'Horse Race', section: '194BB', taxRate: 30, tdsThreshold: 10000 },
};

// ==================== FAMILY PENSION ====================

export interface FamilyPensionEntry {
  grossAmount: number;
  payerName?: string;
  relationToPensioner?: string;
  // Deduction u/s 57(iia) = min(1/3rd, Rs 15,000 old / Rs 25,000 new) - calculated by backend
}

// ==================== GIFTS 56(2)(x) ====================

export type GiftPropertyType = 'IMMOVABLE' | 'CASH' | 'MOVABLE' | 'OTHER';

export interface GiftEntry {
  id: string;
  propertyType: GiftPropertyType;
  value: number;
  donorName?: string;
  donorRelation?: string;
  dateOfReceipt?: string;
  description?: string;
  fromRelative?: boolean;
  receivedOnMarriage?: boolean;
}

export const GIFT_INFO = {
  threshold: 50000,
  description: 'Gifts above ₹50,000 aggregate from non-relatives are taxable under Section 56(2)(x). Exempt: gifts on marriage, from relatives.',
};

// ==================== VDA ====================

export interface VDAEntry {
  grossGains: number;
  type: 'CRYPTO' | 'NFT' | 'OTHER';
  dateOfTransaction?: string;
  // Tax at 30% + 4% cess - calculated by backend
}

// ==================== SCHEDULE OS AGGREGATE ====================

export interface ScheduleOSResult {
  // Interest Income (ITD Tags)
  intrFrmSavingBank: number;      // 17A
  intrFrmTermDeposit: number;     // 17B
  intrFrmIncmTaxRefund: number;  // 17C
  intrSec10XIFirstProviso: number; // 17D
  intrSec10XISecondProviso: number; // 17E - EXEMPT
  intrSec10XIIFirstProviso: number; // 17F - EXEMPT
  
  // Dividend Income
  dividendGross: number;
  dividendOthThan22e: number;
  dividend22e: number; // EXEMPT
  dividend22f: number; // EXEMPT
  
  // Family Pension
  familyPension: number;
  familyPensionDed: number; // u/s 16(iv)
  
  // Winnings
  winningsGross: number;
  winningsTax: number;
  
  // Gifts
  immovpropwithoutcons562x: number;
  anyotherpropwithoutcons562x: number;
  
  // VDA
  vdaGains: number;
  
  // Other
  anyOtherIncome: number;
  
  // Totals
  grossOtherSources: number;
  taxableOtherSources: number;
  totalInterest: number;
  totalDividend: number;
  totalWinnings: number;
  totalGifts: number;
}
