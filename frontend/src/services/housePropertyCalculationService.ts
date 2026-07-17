import axiosInstance from '../api/axiosInstance';

export interface HousePropertyInput {
  // Property identification
  propertySequenceNo?: number;
  propertyType: 'SELF_OCCUPIED' | 'LET_OUT' | 'DEEMED_LET_OUT';
  address: string;
  city: string;
  state: string;
  pinCode: string;
  propertyIdentificationNo: string;
  
  // Ownership
  propertyOwnerType?: 'SE' | 'MI' | 'SP' | 'OT';
  ownershipType?: 'SOLE' | 'JOINT';
  ownershipShare?: number;
  isCoOwned?: boolean;
  
  // Co-owners
  coOwners?: Array<{
    name: string;
    pan: string;
    aadhaar?: string;
    sharePercentage: number;
  }>;

  // Rental income details
  annualRent?: number;
  municipalRateableValue?: number;
  fairRentValue?: number;
  standardRent?: number;
  unrealizedRent?: number;
  arrearsOfRent?: number;
  vacancyPeriodMonths?: number;

  // Deductions
  municipalTaxesPaid?: number;
  interestOnLoan?: number;
  preConstructionInterest?: number;
  
  // Loan details (Section 24B)
  homeLoans?: Array<{
    lenderType?: 'B' | 'I' | 'L';
    lenderName: string;
    lenderPAN?: string;
    loanAccountNo?: string;
    dateOfLoan?: string;
    totalLoanAmount?: number;
    loanOutstandingAmount?: number;
    interestUs24B?: number;
  }>;

  // Tenant details
  tenantName?: string;
  tenantPAN?: string;
  tenantAadhaar?: string;
}

/**
 * CBDT AY 2026-27 Compliance:
 * 
 * IMPORTANT: This service now calls BACKEND API for ALL calculations.
 * Frontend should ONLY collect input and display results.
 * 
 * All calculations are performed in IncomeCalculationController
 * which follows exact CBDT rules per Income Tax Act:
 * - Section 23: Annual Value calculation
 * - Section 24(a): Standard deduction 30%
 * - Section 24(b): Interest on loan deduction
 * - Proper rounding to nearest rupee
 */

export interface PropertyCalculation {
  // Property info
  propertySequenceNo: number;
  propertyType: string;
  address: string;
  city: string;
  
  // Input values (echoed from backend)
  annualRent: number;
  municipalRateableValue: number;
  fairRentValue: number;
  unrealizedRent: number;
  municipalTaxesPaid: number;
  
  // Calculated values from BACKEND (CBDT compliant)
  grossAnnualValue: number;   // GAV per Section 23
  netAnnualValue: number;     // NAV
  standardDeduction: number;  // 30% of NAV per Section 24(a)
  interestOnLoan: number;     // Section 24(b)
  interestDeduction: number;  // Total allowable interest
  incomeFromHP: number;      // Final income/loss (CAN BE NEGATIVE)
  
  // Additional info
  selfOccupiedInterestCap: number;  // Max ₹2L for self-occupied
  preConstructionInterestClaimed: number;
  
  // Validation
  validationWarnings?: string[];
  validationErrors?: string[];
}

export interface HousePropertyCalculationResponse {
  properties: PropertyCalculation[];
  totalIncomeFromHP: number;
  calculationTimestamp: string;
  ay: string;
  compliance: string;
}

/**
 * Calculate House Property Income - NOW CALLS BACKEND API
 * 
 * Fetches computed values from backend to ensure CBDT compliance.
 * All calculations happen in IncomeCalculationController.
 */
export async function calculateHouseProperty(
  ay: string,
  properties: HousePropertyInput[]
): Promise<HousePropertyCalculationResponse> {
  try {
    // Call BACKEND API for all calculations
    const response = await axiosInstance.post<HousePropertyCalculationResponse>(
      `/api/v1/calculations/house-property?itrType=ITR1`,
      properties
    );
    
    return response.data;
  } catch (error: any) {
    console.error('Backend calculation failed:', error);
    throw new Error('Failed to calculate house property income. Please ensure backend is running.');
  }
}






