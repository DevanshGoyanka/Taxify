// Frontend Phase 2 - Type definitions for ComputedReturn and Rules
// Document 1 §4.1, §5.2

export interface ComputedReturn {
  clientId: string;
  assessmentYear: string;
  rulesVersion: string;
  itrFormVersion: string;
  jsonSchemaVersion: string;
  triggeredBy: string;
  regime: 'OLD' | 'NEW';
  
  // Income schedules (stubs for Phase 2)
  salary?: any;
  houseProperty?: any;
  capitalGains?: any;
  businessIncome?: any;
  otherSources?: any;
  
  // Tax computation
  grossTotalIncome: number;
  deductions: number;
  totalIncome: number;
  taxOnTotalIncome: number;
  surcharge: number;
  cess: number;
  totalTaxLiability: number;
}

export interface TaxYearRules {
  assessmentYear: string;
  version: string;
  newRegime: {
    slabs: Array<{ limit: number; rate: number }>;
    standardDeduction: number;
    rebate87A: number;
  };
  oldRegime: {
    slabs: Array<{ limit: number; rate: number }>;
    standardDeduction: number;
    rebate87A: number;
  };
  surcharge: {
    threshold50L: number;
    threshold1Cr: number;
    threshold2Cr: number;
    threshold5Cr: number;
  };
  cess: number;
}
