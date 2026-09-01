import type { Category80D, FinancialParticulars, ReturnDraft } from './types';
import { EMPTY_BROUGHT_FORWARD_LOSSES, EMPTY_CAPITAL_GAINS_SCHEDULE, EMPTY_CHAPTER_VIA } from './types';

// eslint-disable-next-line @typescript-eslint/no-unused-vars
type _FactoryTypeGuard = ReturnDraft;

/** Creates an empty 80D category with independent policy storage. */
export function createEmpty80DCategory(): Category80D { return { policies: [], preventiveCheckup: 0, medicalExpense: 0 }; }
/** Creates empty Schedule BP financial particulars. */
export function createEmptyFinancialParticulars(): FinancialParticulars { return { partnerMemberOwnCapital: 0, cashBalance: 0, bankBalance: 0, inventory: 0, sundryDebtors: 0, sundryCreditors: 0, fixedAssets: 0, investments: 0, loansAndAdvances: 0, otherAssets: 0, totalAssets: 0, securedLoans: 0, unsecuredLoans: 0, advances: 0, otherLiabilities: 0, totalLiabilities: 0, grossProfit: 0, expenses: 0, netProfit: 0 }; }
/** Creates an empty Schedule OS deductions block. */
export function createEmptyOtherSourcesDeductions() {
  return { expenses: 0, interestExpenseUs57: 0, interestExpenseEligibleUs57: 0, familyPensionDeductionUs57iia: 0, depreciation: 0, totalDeductions: 0, amountNotDeductibleUs58: 0, profitChargeableUs59: 0 };
}
/** Creates an empty unexplained income block. */
export function createEmptyUnexplainedIncome() {
  return { cashCreditsUs68: 0, unexplainedInvestmentsUs69: 0, unexplainedMoneyUs69A: 0, undisclosedInvestmentsUs69B: 0, unexplainedExpenditureUs69C: 0, hundiBorrowingUs69D: 0, priorYearBusinessTrust562xii: 0, priorYearLifeInsurance562xiii: 0 };
}
/** Creates a fresh normalized return draft with no shared mutable state. */
export function createEmptyReturnDraft(assessmentYear = '', form: ReturnDraft['form'] = 'ITR-1', regime: ReturnDraft['regime'] = 'new'): ReturnDraft {
  return {
    schemaVersion: 1, assessmentYear, form, regime,
    personal: {
      name: '', firstName: '', middleName: '', surnameOrOrgName: '', fatherName: '',
      pan: '', aadhaar: '', email: '', mobile: '', mobileCountryCode: '91',
      secondaryEmail: '', secondaryMobile: '', secondaryMobileCountryCode: '',
      dateOfBirth: null,
      flatNo: '', residenceName: '', roadOrStreet: '', localityOrArea: '',
      city: '', stateCode: '', countryCode: '91', pinCode: '', zipCode: '',
      employerCategory: '', age: 30, assesseeStatus: 'I',
      landlineStdCode: '0', landlinePhoneNo: '0',
      secondaryAddressDifferent: false, alternateAddress: null,
    },
    filing: {
      filingSection: '139(1)', returnType: 'ORIGINAL',
      originalAcknowledgementNumber: '', originalFilingDate: null,
      noticeNumber: '', noticeDate: null, representative: null,
      form10IEAAcknowledgement: '', form10IEADate: null,
      form10IEAEarlierAYOldRegime: 'NA', form10IEAAssessmentYear: '',
      form10IEAEarlierAYAckOldRegime: '', form10IEAEarlierAYNewRegime: 'N',
      form10IEANewRegimeAssessmentYear: '', form10IEAEarlierAYAckNewRegime: '',
      form10IEACurrentAYNewRegime: false, form10IEACurrentAYNewRegimeDate: null,
      form10IEACurrentAYNewRegimeAck: '', form10IEACurrentAYOldRegime: false,
      form10IEACurrentAYOldRegimeDate: null, form10IEACurrentAYOldRegimeAck: '',
      seventhProviso: {
        depositExceedsOneCrore: false, depositAmount: 0,
        foreignTravel: false, foreignTravelAmount: 0,
        electricityExpenditure: false, electricityExpenditureAmount: 0,
        otherClauseIV: false, clauseIVDetails: [],
      },
      sebiRegistrationNumber: '', isFiiFpi: false, portugueseCivilCodeApplies: false,
    },
    employers: [], houseProperties: [], housePropertyPassThroughIncome: 0, businesses: [], capitalGainsSchedule: { ...EMPTY_CAPITAL_GAINS_SCHEDULE },
    otherSources: {
      interest: [], dividends: [], familyPension: { grossAmount: 0, payerName: '', relationToPensioner: '' },
      winnings: [], gifts: [], otherIncome: [], dtaaIncome: [], dtaaAggregates: { totalAmountTaxUsDtaa: 0 },
      section89A: [], section89AAggregates: { incomeNotified89AOS: 0, incomeNotifiedOther89AOS: 0, incomeNotifiedPriorYear89AOS: 0, incomeReliefUs89AOS: 0 },
      accumulatedPf: [], accumulatedPfAggregates: { totalIncomeBenefit: 0, totalTaxBenefit: 0 }, specialRateIncome: [],
      unexplainedIncome: createEmptyUnexplainedIncome(),
      deductions: createEmptyOtherSourcesDeductions(),
    },
    exemptIncome: {
      interestIncome: 0, grossAgriculturalReceipts: 0, agriculturalExpenses: 0,
      unabsorbedAgriculturalLossPreviousEightYears: 0, agriculturalIncomeRule7And8: 0,
      netAgriculturalIncomeOrOtherIncomeRule7: 0, agriculturalLandParcels: [],
      otherExemptIncome: [], othersTotal: 0, dtaaExemptIncome: [],
      incomeNotChargeableToTax: 0, incomeChargeableAsPerDtaa: 0,
      passThroughIncomeNotChargeableToTax: 0, totalExemptIncome: 0,
    },
    deductions: { section80C: [], pensionContribution80CCC: [], section80D: { selfSeniorCitizen: 'N', parentsSeniorCitizen: 'N', selfFamily: createEmpty80DCategory(), selfFamilySenior: createEmpty80DCategory(), parents: createEmpty80DCategory(), parentsSenior: createEmpty80DCategory() }, section80G: [], loans: { loans: [], section80EEAStampDutyValue: 0 }, chapterVIA: { ...EMPTY_CHAPTER_VIA, businessDeductions: { ...EMPTY_CHAPTER_VIA.businessDeductions } }, schedule80GGA: [], schedule80GGC: [] },
    taxes: { tds: [], tcs: [], challans: [] }, bankAccounts: [],
    lossesBroughtForward: { ...EMPTY_BROUGHT_FORWARD_LOSSES },
    bpNetProfit: 0,
    verification: { capacity: 'SELF', place: '', date: null, declarationAccepted: false },
    taxReturnPreparer: { used: false, identificationNumber: '', name: '', reimbursementFromGovernment: 0 },
    provenance: [], reconciliation: { evidence: [], discrepancies: [] },
    broughtForwardLossEntries: [], carriedForwardLossEntries: [],
    foreignSourceIncome: [], foreignTaxRelief: [], foreignAssets: [],
    clubbedIncome: [], passThroughIncomeEntries: [],
    amt: null, assetLiability: null, portugueseCivilCode: null,
    esopDeferrals: [],
  };
}
