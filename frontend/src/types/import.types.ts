// TypeScript type definitions for Part 2 - PDF Import
// Section 11 of FIXES_PART2_PDF_IMPORT_CLEANUP.md

export interface TDSEntry26AS {
  deductorName: string;
  tan: string;
  section: string;
  amountPaid: number;
  taxDeducted: number;
  taxDeposited: number;
}

export interface PropertyTDS26AS {
  acknowledgementNo: string;
  buyerName: string;
  buyerPAN: string;
  transactionDate: string;
  transactionAmount: number;
  tdsDeposited: number;
}

export interface RefundEntry26AS {
  assessmentYear: string;
  refundAmount: number;
  interestAmount: number;
  refundDate: string;
}

export interface Form26ASData {
  partIEntries: TDSEntry26AS[];
  partIVEntries: PropertyTDS26AS[];
  partVIIEntries: RefundEntry26AS[];
}

export interface AISTDSEntry {
  section: string;
  deductorName: string;
  deductorTAN: string;
  totalAmountPaid: number;
  totalTDSDeducted: number;
}

export interface SFTSaleEntry {
  transferDate: string;
  securityName: string;
  assetType: 'STCG' | 'LTCG';
  quantity: number;
  salePricePerUnit: number;
  salesConsideration: number;
  costOfAcquisition: number;
  fmvPerUnit: number;
  indexedCostOfAcquisition: number;
}

export interface MFPurchase {
  amcName: string;
  totalPurchase: number;
  totalSales: number;
}

export interface TaxPaymentAIS {
  financialYear: string;
  minorHead: string;
  taxAmount: number;
  surcharge: number;
  educationCess: number;
  totalAmount: number;
  bsrCode: string;
  depositDate: string;
  challanSerialNo: string;
}

export interface AISGeneralInfo {
  pan: string;
  aadhaar: string;
  name: string;
  dob: string;
  mobile: string;
  email: string;
  address: string;
}

export interface AISPartB1Data {
  tdsEntries: AISTDSEntry[];
}

export interface AISPartB2Data {
  dividendIncome: number;
  securitiesSale: SFTSaleEntry[];
  securitiesPurchaseAmount: number;
  mutualFundPurchase: MFPurchase[];
  interestOnSecurities: number;
}

export interface AISData {
  generalInfo: AISGeneralInfo;
  partB1: AISPartB1Data;
  partB2: AISPartB2Data;
  partB3: TaxPaymentAIS[];
}

export interface TISData {
  dividendIncome: number;
  interestFromDeposit: number;
  securitiesSaleConsideration: number;
  securitiesPurchaseAmount: number;
  interestOnSecurities: number;
  salaryAmount: number;
  rentIncome: number;
}

export interface ReconciliationItem {
  deductorName: string;
  tan: string;
  income26AS: number;
  incomeAIS: number;
  tds26AS: number;
  tdsAIS: number;
  incomeDiff: number;
  tdsDiff: number;
  recommendedAction: 'USE_26AS' | 'USE_AIS' | 'MANUAL';
}

export interface ReconciliationReport {
  hasDiscrepancies: boolean;
  items: ReconciliationItem[];
}
