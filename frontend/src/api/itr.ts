import axiosInstance from './axiosInstance';

export const itrApi = {
  getFormData: async (clientId: number, year: string) => {
    const { data } = await axiosInstance.get(`/clients/${clientId}/itr/${year}`);
    return data;
  },
  saveFormData: async (clientId: number, year: string, formData: any) => {
    const { data } = await axiosInstance.put(`/clients/${clientId}/itr/${year}`, formData);
    return data;
  },
  
  /**
   * Compute tax from frontend form data.
   * FRONTEND SENDS ALL FIELDS (even if 0).
   * BACKEND COMPUTES ALL VALUES including 0.
   * Returns TaxComputationResult with otherIncome, totalInterest, totalDividend, etc.
   */
  computeTax: async (formData: any, regime: string = 'NEW') => {
    const { data } = await axiosInstance.post('/api/tax/compute', formData, {
      params: { regime }
    });
    return data;
  },
  
  /**
   * Legacy computeTax - redirects to new endpoint
   */
  computeTaxLegacy: async (clientId: number, year: string, formData: any) => {
    const { data } = await axiosInstance.post(`/clients/${clientId}/itr/${year}/compute`, formData);
    return data;
  },
  
  /**
   * Compute complete tax summary in backend - replaces frontend computeTax() entirely.
   */
  computeTaxSummary: async (formData: any, assessmentYear: string, regime: string) => {
    const payload = {
      ...formData,
      assessmentYear,
      regime
    };
    console.log('[API] computeTaxSummary sending regime:', regime, 'payload keys:', Object.keys(payload));
    // Use query param so backend's @RequestParam picks it up reliably
    const { data } = await axiosInstance.post(`/tax-summary/compute?regime=${regime}`, payload);
    return data;
  },
  
  validate: async (clientId: number, year: string, formData: any) => {
    const { data } = await axiosInstance.post(`/clients/${clientId}/itr/${year}/validate`, formData);
    return data as { valid: boolean; errors: string[]; warnings: string[] };
  },
  downloadJson: async (clientId: number, year: string) => {
    const res = await axiosInstance.get(`/clients/${clientId}/itr/${year}/download`, { responseType: 'blob' });
    const url = URL.createObjectURL(new Blob([res.data]));
    const a = document.createElement('a');
    a.href = url; a.download = `ITR_${clientId}_${year}.json`;
    document.body.appendChild(a); a.click(); a.remove();
    URL.revokeObjectURL(url);
  },
  downloadPdf: async (clientId: number, year: string) => {
    const res = await axiosInstance.get(`/clients/${clientId}/itr/${year}/download-pdf`, { responseType: 'blob' });
    const url = URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }));
    const a = document.createElement('a');
    a.href = url; a.download = `ITR_${clientId}_${year}.pdf`;
    document.body.appendChild(a); a.click(); a.remove();
    URL.revokeObjectURL(url);
  },

  // ========== BUSINESS INCOME API - BACKEND CALCULATIONS ==========
  /**
   * Calculate business income - all calculations done in backend
   * POST /api/v1/business-income/calculate
   */
  calculateBusinessIncome: async (request: BusinessIncomeRequest, assessmentYear: string = '2026-27') => {
    const { data } = await axiosInstance.post(
      `/business-income/calculate?assessmentYear=${assessmentYear}`,
      request
    );
    return data as BusinessIncomeResponse;
  },

  /**
   * Validate business income inputs (turnover limits, audit requirements)
   * POST /api/v1/business-income/validate
   */
  validateBusinessInput: async (request: BusinessIncomeRequest) => {
    const { data } = await axiosInstance.post('/business-income/validate', request);
    return data as BusinessValidationResponse;
  },

  /**
   * Calculate capital gains - all calculations done in backend
   * POST /api/v1/capital-gains/calculate
   */
  calculateCapitalGains: async (request: CapitalGainsCalculationRequest) => {
    const { data } = await axiosInstance.post('/capital-gains/calculate', request);
    return data as CapitalGainsCalculationResponse;
  },

  /**
   * Batch calculate capital gains
   * POST /api/v1/capital-gains/calculate-batch
   */
  calculateCapitalGainsBatch: async (request: CapitalGainsBatchRequest) => {
    const { data } = await axiosInstance.post('/capital-gains/calculate-batch', request);
    return data as CapitalGainsBatchResponse;
  },
};

// ========== Type Definitions ==========

interface BusinessIncomeRequest {
  scheme: '44AD' | '44ADA' | '44AE' | 'Regular';
  grossTurnover?: number;
  declaredIncome?: number;
  netProfitPL?: number;
  isPresumptive44ADExceed50L?: boolean;
  isPassengerVehicle?: boolean;
  // Disallowances (for Regular scheme)
  disallowance40AIa?: number;
  disallowance40A2?: number;
  disallowance40A3?: number;
  disallowance43B?: number;
  disallowance43Bh?: number;
  disallowance14A?: number;
  personalExpenses?: number;
  capitalExpenses?: number;
  // Deductions
  depreciation?: number;
  additionalDepreciation?: number;
  deduction35AD?: number;
  otherDeductions?: number;
  // Loss
  broughtForwardLoss?: number;
  // Audit info
  isAudited?: boolean;
  businessNature?: string;
  nicCode?: string;
}

interface BusinessIncomeResponse {
  scheme: string;
  assessmentYear: string;
  grossTurnover: number;
  declaredIncome: number;
  netProfitPL: number;
  taxableIncome: number;
  adjustedTaxableIncome: number;
  presumptiveRate: number;
  incomeType: string;
  isLoss: boolean;
  businessLoss: number;
  complianceNotes: string[];
  timestamp: string;
}

interface BusinessValidationResponse {
  isValid: boolean;
  errors: string[];
  warnings: string[];
  assessmentYear: string;
}

interface CapitalGainsCalculationRequest {
  assetType: string;
  assetDescription?: string;
  purchaseDate?: string;
  saleDate?: string;
  purchaseCost: number;
  saleCost: number;
  transferExpenses?: number;
  costOfImprovement?: number;
  fmvAsOn31Jan2018?: number;
  assessmentYear?: string;
}

interface CapitalGainsCalculationResponse {
  gainType: string;
  longTerm: boolean;
  holdingPeriodMonths: number;
  purchaseCost: number;
  saleCost: number;
  costOfAcquisition: number;
  indexedCost: number;
  gain: number;
  taxableGain: number;
  taxRate: number;
  taxPayable: number;
  assessmentYear?: string;
  scheduleCGReference?: string;
  sectionReference?: string;
  complianceNotes?: string[];
}

interface CapitalGainsBatchRequest {
  transactions: CapitalGainsCalculationRequest[];
  broughtForwardSTCGLoss?: number;
  broughtForwardLTCGLoss?: number;
}

interface CapitalGainsBatchResponse {
  transactions: CapitalGainsCalculationResponse[];
  summary: {
    stcg111A: number;
    ltcg112A: number;
    stcgOther: number;
    ltcg112: number;
    totalCapitalGains: number;
    totalTax: number;
    lossSetOff: number;
    netCapitalGains: number;
    remainingLoss: number;
  };
}
