import axiosInstance from '../api/axiosInstance';

export interface EmployerInput {
  employerName: string;
  employerTAN: string;
  employerPAN?: string;
  natureOfEmployment?: string;
  periodFrom?: string;
  periodTo?: string;
  
  // Section 17(1) - Salary Components
  basic: number;
  da: number;
  hra: number;
  bonus: number;
  allowances: number;
  lta: number;
  rentPaid?: number;
  isMetroCity?: boolean;
  pension: number;
  commutedPension: number;
  uncommutedPension: number;
  gratuity: number;
  leaveEncashment: number;
  arrearsOfSalary: number;
  
  // Section 17(2) - Perquisites
  perqRentFreeAccommodation: number;
  perqConcessionalRent: number;
  perqMotorCar: number;
  perqSweeper: number;
  perqGasElectricityWater: number;
  perqInterestFreeLoan: number;
  perqHolidayExpenses: number;
  perqFreeEducation: number;
  perqGiftsVouchers: number;
  perqCreditCard: number;
  perqClubExpenses: number;
  perqMovableAssets: number;
  perqOthers: number;
  
  // Section 17(3) - Profits in Lieu
  profitsCompensationTermination: number;
  profitsNonCompete: number;
  
  // Additional Exemptions
  ltaExempt: number;
  gratuityExempt: number;
  leaveEncashmentExempt: number;
  otherExemptions: number;
  medicalReimbursementReceived?: number;
  transportAllowanceReceived?: number;
  isDisabledEmployee?: boolean;
  childrenEducationAllowance?: number;
  hostelExpenditureAllowance?: number;
  pensionType?: string;
  
  // Deductions u/s 16
  professionalTax: number;
  entertainmentAllowance: number;
  
  // TDS
  tdsDeducted: number;
}

// ALL CALCULATIONS DONE IN BACKEND - Frontend only displays
export interface EmployerCalculation {
  employerName: string;
  employerTAN: string;
  employerPAN?: string;
  natureOfEmployment?: string;
  periodFrom?: string;
  periodTo?: string;
  
  // Section 17(1) inputs
  basic: number;
  da: number;
  hraReceived: number;
  bonus: number;
  allowances: number;
  lta: number;
  pension: number;
  commutedPension: number;
  uncommutedPension: number;
  gratuity: number;
  leaveEncashment: number;
  arrearsOfSalary: number;
  
  // Section 17(2) - Perquisites breakdown
  perquisites: number;
  perqRentFreeAccommodation: number;
  perqConcessionalRent: number;
  perqMotorCar: number;
  perqSweeper: number;
  perqGasElectricityWater: number;
  perqInterestFreeLoan: number;
  perqHolidayExpenses: number;
  perqFreeEducation: number;
  perqGiftsVouchers: number;
  perqCreditCard: number;
  perqClubExpenses: number;
  perqMovableAssets: number;
  perqOthers: number;
  
  // Section 17(3) - Profits in Lieu
  profitsInLieu: number;
  profitsCompensationTermination: number;
  profitsNonCompete: number;
  
  // HRA Details
  rentPaid?: number;
  isMetroCity?: boolean;
  
  // Exemptions ALL CALCULATED IN BACKEND
  hraExempt: number;
  hraTaxable: number;
  ltaExempt: number;
  ltaTaxable: number;
  gratuityExempt: number;
  gratuityTaxable: number;
  leaveEncashmentExempt: number;
  leaveEncashmentTaxable: number;
  pensionCommutationExempt: number;
  pensionCommutationTaxable: number;
  medicalReimbursementExempt: number;
  medicalReimbursementTaxable: number;
  transportAllowanceExempt: number;
  childrenEducationExempt: number;
  hostelExpenditureExempt: number;
  otherExemptions: number;
  totalExemptions: number;
  
  // Gross Salary Breakdown (ALL FROM BACKEND)
  salary171: number;  // Section 17(1)
  salary172: number;  // Section 17(2) Perquisites
  salary173: number;  // Section 17(3) Profits in Lieu
  grossSalary: number;
  
  // Deductions u/s 16 (ALL FROM BACKEND)
  standardDeduction: number;
  professionalTax: number;
  entertainmentAllowance: number;
  totalDeductions16: number;
  
  // Net Salary (ALL FROM BACKEND)
  netSalary: number;
  
  // TDS
  tdsDeducted: number;
  
  // Validation
  validationWarnings?: string[];
  validationErrors?: string[];
}

// ALL TOTALS CALCULATED IN BACKEND - NOT IN FRONTEND
export interface SalaryCalculationResponse {
  // Computed values from backend (new format)
  basicSalary: number;
  daAmount: number;
  bonusAmount: number;
  salary17_1: number;
  grossSalary: number;
  
  // Exemptions (Section 10)
  hraExempt: number;
  ltaExempt: number;
  ceaExempt: number;
  transportExempt: number;
  medicalExempt: number;
  totalExemptAllowances: number;
  
  // Deductions (Section 16)
  standardDeduction: number;
  professionalTax: number;
  entertainmentAllowance: number;
  totalDeductions16: number;
  
  // Final
  incomeFromSalary: number;
  
  // Legacy backward compatibility
  totalGrossSalary?: number;
  totalNetSalary?: number;
  totalTDS?: number;
  totalBasic?: number;
  totalDA?: number;
  totalHRA?: number;
  totalBonus?: number;
  totalAllowances?: number;
  totalLTA?: number;
  totalPension?: number;
  totalPerquisites?: number;
  totalProfitsInLieu?: number;
  totalExemptions?: number;
  totalStandardDeduction?: number;
  totalProfessionalTax?: number;
  totalEntertainmentAllowance?: number;
  totalHRAExempt?: number;
  assessmentYear?: string;
  standardDeductionAmount?: string;
  
  // Legacy employer support
  employers?: any[];
  
  // Metadata
  calculationTimestamp?: string;
  ay?: string;
  compliance?: string;
  
  // Validation
  validationWarnings?: string[];
  validationErrors?: string[];
}

/**
 * Calculate Salary Income - NOW CALLS BACKEND API
 * 
 * CBDT AY 2026-27: All calculations happen in IncomeCalculationController
 */
export const calculateSalary = async (
  assessmentYear: string,
  employerInputs: any[],
  taxRegime: string = 'OLD'
): Promise<SalaryCalculationResponse> => {
  // Build salary input from employer data
  const salaryInput = buildSalaryInput(employerInputs, taxRegime);
  
  const response = await axiosInstance.post<SalaryCalculationResponse>(
    '/calculations/salary',
    salaryInput
  );
  
  // Map new format to legacy for backward compatibility
  const data = response.data;
  return {
    ...data,
    employers: employerInputs,
    totalGrossSalary: data.totalGrossSalary ?? data.grossSalary,
    totalNetSalary: data.totalNetSalary ?? data.incomeFromSalary,
    totalBasic: data.totalBasic ?? data.basicSalary,
    totalDA: data.totalDA ?? data.daAmount,
    totalHRA: data.totalHRA ?? data.hraExempt,
    totalBonus: data.totalBonus ?? data.bonusAmount,
    totalStandardDeduction: data.totalStandardDeduction ?? data.standardDeduction,
    totalProfessionalTax: data.totalProfessionalTax ?? data.professionalTax,
    totalHRAExempt: data.totalHRAExempt ?? data.hraExempt,
    assessmentYear: data.assessmentYear ?? data.ay ?? assessmentYear,
    standardDeductionAmount: data.standardDeductionAmount ?? String(data.totalStandardDeduction ?? data.standardDeduction ?? (taxRegime === 'NEW' ? 75000 : 50000)),
  };
};

/**
 * Build salary input from employer data for backend API
 */
function buildSalaryInput(employerInputs: any[], taxRegime: string = 'OLD'): any {
  // Aggregate all employer data into single salary input
  let totalBasic = 0, totalDA = 0, totalHRA = 0, totalBonus = 0;
  let totalAllowances = 0, totalLTA = 0, totalPension = 0;
  let totalPerquisites = 0, totalProfitsInLieu = 0;
  let totalHRAReceived = 0, totalLTAReceived = 0;
  let totalTransportAllowance = 0, totalMedicalReimbursement = 0;
  let totalChildrenEducation = 0, totalHostelAllowance = 0;
  let totalProfTax = 0, totalEntertainment = 0;
  let totalLtaExempt = 0;
  
  for (const emp of employerInputs) {
    totalBasic += emp.basic || 0;
    totalDA += emp.da || 0;
    totalHRA += emp.hra || 0;
    totalBonus += emp.bonus || 0;
    totalAllowances += emp.allowances || 0;
    totalLTA += emp.lta || 0;
    totalPension += emp.pension || 0;
    totalPerquisites += Object.values(emp.perquisites || {}).reduce((a: number, b: any) => a + (Number(b) || 0), 0);
    totalProfitsInLieu += emp.profitsInLieu || 0;
    totalHRAReceived += emp.hra || 0;
    totalLTAReceived += emp.lta || 0;
    totalTransportAllowance += emp.transportAllowance || 0;
    totalMedicalReimbursement += emp.medicalReimbursement || 0;
    totalChildrenEducation += emp.childrenEducation || 0;
    totalHostelAllowance += emp.hostelAllowance || 0;
    totalProfTax += emp.professionalTax || 0;
    totalEntertainment += emp.entertainmentAllowance || 0;
    totalLtaExempt += emp.ltaExempt || 0;
  }
  
  return {
    taxRegime: taxRegime,
    assessmentYear: "2026-27",
    employers: employerInputs.map(emp => ({
      employerName: emp.employerName || 'Employer',
      employerTAN: emp.employerTAN || '',
      basic: emp.basic || 0,
      da: emp.da || 0,
      hraReceived: emp.hra || 0,
      ltaReceived: emp.lta || 0,
      bonus: emp.bonus || 0,
      allowances: emp.allowances || 0,
      perquisitesValue: emp.perquisites || 0,
      profitsInLieu: emp.profitsInLieu || 0,
      annualRentPaid: emp.rentPaid || 0,
      isMetroCity: emp.isMetroCity || false,
      isGovernmentEmployee: emp.isGovernmentEmployee || false,
      isDisabledEmployee: emp.isDisabledEmployee || false,
      gratuityReceived: emp.gratuity || 0,
      leaveEncashmentReceived: emp.leaveEncashment || 0,
      commutedPensionReceived: emp.commutedPension || 0,
      professionalTax: emp.professionalTax || 0,
      entertainmentAllowance: emp.entertainmentAllowance || 0,
      tdsDeducted: emp.tdsDeducted || 0,
      childrenEducationAllowance: emp.childrenEducationAllowance || 0,
      hostelExpenditureAllowance: emp.hostelExpenditureAllowance || 0,
      transportAllowance: emp.transportAllowance || 0,
    }))
  };
}
