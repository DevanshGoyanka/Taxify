import axiosInstance from '../api/axiosInstance';

// Request types for capital gains calculation
export interface CapitalGainsCalculationRequest {
  assetType: string;
  assetDescription?: string;
  purchaseDate: string;
  saleDate: string;
  purchaseCost: number;
  saleCost: number;
  transferExpenses: number;
  costOfImprovement?: number;
  fmvAsOn31Jan2018?: number;
  buyerName?: string;
  buyerPAN?: string;
  exemptionSection?: string;
  exemptionAmount?: number;
}

// Response from backend - includes all calculated values
export interface CapitalGainsCalculationResponse {
  // Input echoed
  gainType: string;
  longTerm: boolean;
  holdingPeriodMonths: number;
  purchaseCost: number;
  saleCost: number;
  costOfAcquisition: number;
  indexedCost: number;
  transferExpenses: number;
  // Calculated values from BACKEND
  gain: number;
  exemptionClaimed: number;
  taxableGain: number;
  taxRate: number;
  taxPayable: number;
  exemptionLimit: number;
  usedIndexation: boolean;
  costInflationIndexAcquisition: number;
  costInflationIndexTransfer: number;
}

export interface CapitalGainsSummary {
  stcg111A: number;
  ltcg112A: number;
  stcgOther: number;
  ltcg112: number;
  totalCapitalGains: number;
  totalTax: number;
  lossSetOff: number;
  netCapitalGains: number;
  remainingLoss: number;
}

export interface CapitalGainsBatchRequest {
  transactions: CapitalGainsCalculationRequest[];
  broughtForwardSTCGLoss?: number;
  broughtForwardLTCGLoss?: number;
}

export interface CapitalGainsBatchResponse {
  transactions: CapitalGainsCalculationResponse[];
  summary: CapitalGainsSummary;
}

export interface ExemptionCalculationRequest {
  section: '54' | '54EC' | '54F' | '54B' | '54D' | '54G' | '54GB';
  capitalGain: number;
  investmentMade: number;
  netConsideration?: number;
  saleDate: string;
  investmentDate: string;
  isConstruction?: boolean;
  housesOwnedOnSaleDate?: number;
}

export interface ExemptionCalculationResponse {
  section: string;
  eligible: boolean;
  reason?: string;
  warning?: string;
  capitalGain: number;
  investmentMade: number;
  exemptionAmount: number;
  taxableGain: number;
}

export interface CIITableEntry {
  financialYear: number;
  ciiValue: number;
}

// Validation DTOs
export interface TransactionValidationRequest {
  assetType: string;
  assetDescription?: string;
  purchaseDate: string;
  saleDate: string;
  purchaseCost: number;
  saleCost: number;
  transferExpenses: number;
  costOfImprovement?: number;
  fmvAsOn31Jan2018?: number;
  stampDutyValue?: number;
  buyerName?: string;
  buyerPAN?: string;
  exemptionSection?: string;
  exemptionAmount?: number;
  capitalGain?: number;
  housesOwnedOnSaleDate?: number;
}

export interface CapitalGainsValidationResponse {
  valid: boolean;
  errors: string[];
  warnings: string[];
}

export interface BatchValidationRequest {
  transactions: TransactionValidationRequest[];
}

export interface BatchValidationResponse {
  valid: boolean;
  globalErrors: string[];
  transactionResults: {
    transactionIndex: number;
    description: string;
    errors: string[];
    warnings: string[];
  }[];
}

// ============================================================
// ALL CALCULATIONS DONE IN BACKEND - Frontend only displays
// ============================================================

/**
 * Calculate capital gains for a single transaction
 * Frontend only displays, backend does all calculations
 */
export const calculateCapitalGains = async (
  request: CapitalGainsCalculationRequest
): Promise<CapitalGainsCalculationResponse> => {
  const response = await axiosInstance.post<CapitalGainsCalculationResponse>(
    '/capital-gains/calculate',
    request
  );
  return response.data;
};

/**
 * Calculate capital gains for multiple transactions
 * Applies loss set-off rules and aggregates
 */
export const calculateBatchCapitalGains = async (
  request: CapitalGainsBatchRequest
): Promise<CapitalGainsBatchResponse> => {
  const response = await axiosInstance.post<CapitalGainsBatchResponse>(
    '/capital-gains/calculate-batch',
    request
  );
  return response.data;
};

/**
 * Calculate exemption under Section 54, 54EC, 54F
 */
export const calculateExemption = async (
  request: ExemptionCalculationRequest
): Promise<ExemptionCalculationResponse> => {
  const response = await axiosInstance.post<ExemptionCalculationResponse>(
    '/capital-gains/calculate-exemption',
    request
  );
  return response.data;
};

/**
 * Get Cost Inflation Index table from backend
 */
export const getCIITable = async (): Promise<CIITableEntry[]> => {
  const response = await axiosInstance.get<CIITableEntry[]>(
    '/capital-gains/cii-table'
  );
  return response.data;
};

/**
 * Validate a single capital gains transaction
 * Returns errors and warnings based on CBDT rules
 */
export const validateCapitalGainsTransaction = async (
  request: TransactionValidationRequest
): Promise<CapitalGainsValidationResponse> => {
  const response = await axiosInstance.post<CapitalGainsValidationResponse>(
    '/capital-gains/validate',
    request
  );
  return response.data;
};

/**
 * Validate batch of capital gains transactions
 */
export const validateCapitalGainsBatch = async (
  request: BatchValidationRequest
): Promise<BatchValidationResponse> => {
  const response = await axiosInstance.post<BatchValidationResponse>(
    '/capital-gains/validate-batch',
    request
  );
  return response.data;
};
