import axiosInstance from './axiosInstance';

export const advancedTaxApi = {
  // HRA Computation
  computeHRA: async (input: {
    hraReceived: number;
    basicDA: number;
    rentPaid: number;
    cityType: 'METRO' | 'NON_METRO';
  }) => {
    const { data } = await axiosInstance.post('/advanced-tax/hra', input);
    return data;
  },

  // Section 14A Disallowance
  computeSection14A: async (input: {
    directExpensesRelatedToExemptIncome: number;
    exemptIncome: number;
    avgInvestmentInExemptIncome: number;
    totalInterestExpense: number;
    avgTotalAssets: number;
    totalExpenses: number;
  }) => {
    const { data } = await axiosInstance.post('/advanced-tax/section14a', input);
    return data;
  },

  // Section 50C Validation
  validateSection50C: async (input: {
    salePrice: number;
    stampDutyValue: number;
    isSellerTransaction: boolean;
  }) => {
    const { data } = await axiosInstance.post('/advanced-tax/section50c', input);
    return data;
  },

  // Relief u/s 89
  computeRelief89: async (input: {
    taxOnTotalIncomeWithArrears: number;
    taxOnTotalIncomeWithoutArrears: number;
    arrearEntries: Array<{
      yearToWhichArrearRelates: string;
      arrearAmount: number;
      taxOnIncomeWithArrear: number;
      taxOnIncomeWithoutArrear: number;
    }>;
  }) => {
    const { data } = await axiosInstance.post('/advanced-tax/relief89', input);
    return data;
  },

  // Depreciation
  computeDepreciation: async (input: {
    openingWDV: number;
    additionsFirstHalf: number;
    additionsSecondHalf: number;
    sales: number;
    assetCategory: string;
  }) => {
    const { data } = await axiosInstance.post('/advanced-tax/depreciation', input);
    return data;
  },

  getDepreciationRates: async () => {
    const { data } = await axiosInstance.get('/advanced-tax/depreciation/rates');
    return data;
  },

  // Multi-Employer Consolidation
  consolidateMultiEmployer: async (employers: Array<{
    employerName: string;
    employerTAN: string;
    employerPAN: string;
    grossSalary: number;
    exemptAllowances: number;
    standardDeduction: number;
    professionalTax: number;
    tdsDeducted: number;
    periodFrom: string;
    periodTo: string;
  }>) => {
    const { data } = await axiosInstance.post('/advanced-tax/multi-employer', employers);
    return data;
  },

  // LTCG Grandfathering
  computeLTCGGrandfathering: async (input: {
    acquisitionDate: string;
    saleDate: string;
    actualCost: number;
    fmvJan312018: number;
    saleValue: number;
    transferExpenses: number;
    isin?: string;
  }) => {
    const { data } = await axiosInstance.post('/advanced-tax/ltcg-grandfathering', input);
    return data;
  },

  // EPF Taxation
  computeEPFTaxation: async (input: {
    employeeEPFContribution: number;
    employeeVPFContribution: number;
    totalInterestEarned: number;
    employerHasPF: boolean;
  }) => {
    const { data } = await axiosInstance.post('/advanced-tax/epf-taxation', input);
    return data;
  },

  // Clubbing - Minor Child
  computeMinorChildClubbing: async (input: {
    childIncome: number;
    numberOfMinorChildren: number;
    parent1Income: number;
    parent2Income: number;
  }) => {
    const { data } = await axiosInstance.post('/advanced-tax/clubbing/minor-child', input);
    return data;
  },

  // Clubbing - Spouse
  computeSpouseClubbing: async (input: {
    spouseIncome: number;
    transferType: string;
    adequateConsideration: boolean;
  }) => {
    const { data } = await axiosInstance.post('/advanced-tax/clubbing/spouse', input);
    return data;
  },

  // F&O Trading
  computeFOTrading: async (input: {
    totalProfit: number;
    totalLoss: number;
  }) => {
    const { data } = await axiosInstance.post('/advanced-tax/fo-trading', input);
    return data;
  },

  // Break-Even Analysis
  analyzeBreakEven: async (input: {
    grossIncome: number;
    currentDeductions: number;
  }) => {
    const { data } = await axiosInstance.post('/advanced-tax/break-even', input);
    return data;
  },
};
