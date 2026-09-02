import type { EmployerCategory, NatureOfEmployment, StateCode } from './cbdtEnums';

export type ItrForm = 'ITR-1' | 'ITR-2' | 'ITR-3' | 'ITR-4';
export type TaxRegime = 'old' | 'new';
export type Money = number;
export interface Identified { id: string; }

export interface Employer extends Identified {
  customEmployerName: string; employerName: string; employerTAN: string; natureOfEmployment: NatureOfEmployment | '';
  employerAddress: string; employerCity: string; employerStateCode: StateCode | ''; employerPinCode: string; employerZipCode: string;
  section10ExemptionRows: Array<{ id: string; natureCode: string; otherDescription: string; amount: Money }>;
  basic: Money; da: Money; commission: Money; hra: Money; bonus: Money; allowances: Money; lta: Money;
  otherAllowance: Money; arrearSalary: Money; perquisites: Money; profitsInLieu: Money; rentPaid: Money;
  city: string; isMetroCity: boolean; isGovernmentEmployee: boolean; isDisabledEmployee: boolean;
  commutedPension: Money; gratuity: Money; leaveEncashment: Money; averageMonthlySalary: Money; yearsOfService: number;
  unavailedLeaveDays: number; actualLtaFare: Money; isDomesticTravel: boolean; journeysInBlock: number;
  numberOfChildren: number; gratuityAlsoReceived: boolean; transportAllowance: Money; childrenEducationAllowance: Money;
  hostelExpenditureAllowance: Money; uniformAllowance: Money; entertainmentAllowance: Money; professionalTax: Money;
  vrsCompensation: Money; retrenchmentCompensation: Money; tdsDeducted: Money;
}
export interface CoOwner { coOwnerSNo: number; name: string; pan: string; aadhaar: string; share: number; }
export interface TenantDetail { tenantSNo: number; name: string; pan: string; aadhaar: string; panOrTan: string; }
export interface HomeLoan { lenderType: 'B' | 'I'; lenderName: string; lenderPAN: string; loanAccountNo: string; dateOfLoan: string; totalLoanAmount: Money; loanOutstandingAmount: Money; interestUs24B: Money; constructionCompletionDate: string; completedWithin5Years: boolean; preConstructionInterest: Money; }
export interface HouseProperty extends Identified {
  name: string; propertySequenceNo: number; propertyType: 'SELF_OCCUPIED' | 'LET_OUT' | 'DEEMED_LET_OUT';
  address: string; premisesName: string; roadOrStreet: string; area: string; city: string; state: StateCode | ''; pinCode: string; zipCode: string;
  countryCode: string; propertyIdentificationNo: string; propertyOwnerType: 'SE' | 'MI' | 'SP' | 'OT'; propertyOwnerOther: string; ownershipType: 'SOLE' | 'JOINT';
  ownershipShare: number; isCoOwned: boolean; isPropertyInJointOwnership: boolean; coOwners: CoOwner[];
  annualRent: Money; municipalRateableValue: Money; fairRentValue: Money; standardRent: Money; annualLettingValue: Money;
  unrealizedRent: Money; arrearsOfRent: Money; vacancyPeriodMonths: number; municipalTaxesPaid: Money; interestOnLoan: Money;
  preConstructionInterest: Money; lenderName: string; lenderPAN: string; lenderType: 'B' | 'I'; loanAccountNo: string;
  loanSanctionDate: string; constructionCompletionDate: string; principalRepayment: Money; totalLoanAmount: Money;
  loanOutstandingAmount: Money; completedWithin5Years: boolean; homeLoans: HomeLoan[]; tenantDetails: TenantDetail[]; tenantName: string; tenantPAN: string;
  tenantAadhaar: string; passThroughIncome: Money; grossAnnualValue: Money; netAnnualValue: Money; standardDeduction30Pct: Money; incomeFromHP: number;
  maxRent: Money; preConstructionInterestClaimed: Money;
}
export interface BusinessIdentity { businessName: string; natureCode: string; description: string; }
export interface GstinTurnoverRow extends Identified { gstin: string; turnover: Money; }
export interface FinancialParticulars { partnerMemberOwnCapital: Money; cashBalance: Money; bankBalance: Money; inventory: Money; sundryDebtors: Money; sundryCreditors: Money; fixedAssets: Money; investments: Money; loansAndAdvances: Money; otherAssets: Money; totalAssets: Money; securedLoans: Money; unsecuredLoans: Money; advances: Money; otherLiabilities: Money; totalLiabilities: Money; grossProfit: Money; expenses: Money; netProfit: Money; }
export interface Presumptive44AD extends Identified, BusinessIdentity { scheme: '44AD'; digitalReceipts: Money; nonDigitalReceipts: Money; otherModeReceipts: Money; digitalPresumptiveIncome: Money; nonDigitalPresumptiveIncome: Money; declaredIncome: Money; gstinTurnovers: GstinTurnoverRow[]; financialParticulars: FinancialParticulars; }
export interface Presumptive44ADA extends Identified, BusinessIdentity { scheme: '44ADA'; grossReceipts: Money; digitalReceipts: Money; nonDigitalReceipts: Money; otherModeReceipts: Money; declaredIncome: Money; gstinTurnovers: GstinTurnoverRow[]; financialParticulars: FinancialParticulars; }
export interface VehicleRecord extends Identified { vehicleNumber: string; vehicleType: 'HEAVY' | 'OTHER'; tonnage: number; ownedMonths: number; leasedOrHired: boolean; ownedLeasedHiredFlag: 'OWN' | 'LEASE' | 'HIRED'; presumptiveIncome: Money; }
export interface Presumptive44AE extends Identified, BusinessIdentity { scheme: '44AE'; vehicles: VehicleRecord[]; declaredIncome: Money; salaryInterestFromFirm: Money; gstinTurnovers: GstinTurnoverRow[]; financialParticulars: FinancialParticulars; }
export type PresumptiveBusiness = Presumptive44AD | Presumptive44ADA | Presumptive44AE;

export type InterestKind = 'SAVINGS_BANK' | 'TERM_DEPOSIT' | 'IT_REFUND' | 'POST_OFFICE' | 'NSC' | 'SCSS' | 'OTHER' | 'BONDS' | 'SECURITIES' | 'PF_10_11_FIRST' | 'PF_10_11_SECOND' | 'PF_10_12_FIRST' | 'PF_10_12_SECOND';
export interface InterestIncome extends Identified { kind: InterestKind; grossAmount: Money; tdsDeducted: Money; bankName: string; accountType: 'SAVINGS' | 'CURRENT' | 'FD' | ''; accountNumber: string; ifscCode: string; postOfficeName: string; accountNumberPO: string; nscCertificateNumber: string; yearOfPurchase: number; scssAccountNumber: string; dateOfOpening: string; deductorName: string; deductorTAN: string; remarks: string; }
export type DividendSection = '194' | '10(22e)' | '10(22f)' | '115BBDA' | '115BBDAaiii' | '115A1ai' | '115A1aA' | '115AC' | '115ACA' | '115AD1i' | 'DTAA';
export interface DividendIncome extends Identified { section: DividendSection; grossAmount: Money; tdsDeducted: Money; companyName: string; companyPAN: string; deductorTAN: string; isin: string; category: 'EQUITY' | 'PREFERENCE' | 'MUTUAL_FUND' | ''; q1: Money; q2: Money; q3: Money; q4: Money; q5: Money; }
export interface FamilyPension { grossAmount: Money; payerName: string; relationToPensioner: string; }
export type WinningIncomeType = 'LOTTERY' | 'BETTING' | 'CARD_GAME' | 'HORSE_RACE' | 'ONLINE_GAMING' | 'RACE_HORSE_ACTIVITY' | 'UNEXPLAINED_115BBE';
export interface WinningIncome extends Identified { type: WinningIncomeType; grossAmount: Money; tdsDeducted: Money; payerName: string; payerTAN: string; dateOfWinning: string; q1?: Money; q2?: Money; q3?: Money; q4?: Money; q5?: Money; receipts?: Money; deductionUs57?: Money; amountNotDeductibleUs58?: Money; profitChargeableUs59?: Money; balance?: Money; }
export type GiftConsiderationKind = 'WITHOUT_CONSIDERATION' | 'INADEQUATE_CONSIDERATION';
export interface GiftIncome extends Identified { propertyType: 'IMMOVABLE' | 'CASH' | 'MOVABLE' | 'OTHER'; value: Money; donorName: string; donorRelation: string; dateOfReceipt: string; description: string; fromRelative: boolean; receivedOnMarriage: boolean; considerationKind: GiftConsiderationKind; stampDutyValue?: Money; considerationPaid?: Money; fairMarketValue?: Money; }
export interface OtherIncomeEntry extends Identified { nature: string; description: string; amount: Money; }
export type DtaaNatureOfIncome = '1ai' | '1aiii' | '1b' | '1c' | '1d' | '2ai' | '2aii' | '2d' | '2e';
export interface DtaaIncomeEntry extends Identified { amount: Money; natureOfIncome: DtaaNatureOfIncome; countryName: string; countryCode: string; dtaaArticle: string; rateAsPerTreaty: number; rateAsPerITAct: number; taxResidencyCertificate: 'Y' | 'N'; itemNoIncl: string; applicableRate: number; q1: Money; q2: Money; q3: Money; q4: Money; q5: Money; }
export interface Section89AEntry extends Identified { countryCode: 'US' | 'UK' | 'CA'; amount: Money; }
export interface Section89AAggregates { incomeNotified89AOS: Money; incomeNotifiedOther89AOS: Money; incomeNotifiedPriorYear89AOS: Money; incomeReliefUs89AOS: Money; }
export type PfAssessmentYear = '2005-06' | '2006-07' | '2007-08' | '2008-09' | '2009-10' | '2010-11' | '2011-12' | '2012-13' | '2013-14' | '2014-15' | '2015-16' | '2016-17' | '2017-18' | '2018-19' | '2019-20' | '2020-21' | '2021-22' | '2022-23' | '2023-24' | '2024-25' | '2025-26';
export interface AccumulatedPfEntry extends Identified { assessmentYear: PfAssessmentYear; incomeBenefit: Money; taxBenefit: Money; }
export interface AccumulatedPfAggregates { totalIncomeBenefit: Money; totalTaxBenefit: Money; }
export type SpecialRateSourceDescription = '5A1ai' | '5A1aA' | '5A1aii' | '5A1aiia' | '5A1aiiaa' | '5A1aiiab' | '5A1aiiac' | '5A1aiii' | '5A1bA' | '5AC1ab' | '5AC1abD' | '5ACA1a' | '5AD1i' | '5AD1iP' | '5BBA' | '5BBF' | '5BBG' | '5Ea' | '5A1aiiaaP' | '5A1aiiaa2P' | '5AD1iDiv';
export interface SpecialRateIncomeEntry extends Identified { sourceDescription: SpecialRateSourceDescription; sourceAmount: Money; }
export interface UnexplainedIncomeDetails { cashCreditsUs68: Money; unexplainedInvestmentsUs69: Money; unexplainedMoneyUs69A: Money; undisclosedInvestmentsUs69B: Money; unexplainedExpenditureUs69C: Money; hundiBorrowingUs69D: Money; priorYearBusinessTrust562xii: Money; priorYearLifeInsurance562xiii: Money; }
export interface OtherSourcesDeductions { expenses: Money; interestExpenseUs57: Money; interestExpenseEligibleUs57: Money; familyPensionDeductionUs57iia: Money; depreciation: Money; totalDeductions: Money; amountNotDeductibleUs58: Money; profitChargeableUs59: Money; }

export interface Investment80C extends Identified { investmentType: string; identificationNo: string; accountOrPolicyNo: string; amount: Money; dateOfInvestment: string; institutionName: string; institutionPAN: string; }
export interface PensionContribution80CCC extends Identified { identifierType: 'PRAN' | 'OTHPRAN'; identifierName: string; amount: Money; }
export interface Policy80D extends Identified { insurerName: string; policyNo: string; premiumAmount: Money; policyType: 'INDIVIDUAL' | 'FAMILY_FLOATER' | 'GROUP' | 'OTHER'; dateOfCommencement: string; }
export interface Category80D { policies: Policy80D[]; preventiveCheckup: Money; medicalExpense: Money; }
export interface Section80D { selfSeniorCitizen: 'Y' | 'N' | 'S'; parentsSeniorCitizen: 'Y' | 'N' | 'P'; selfFamily: Category80D; selfFamilySenior: Category80D; parents: Category80D; parentsSenior: Category80D; }
export interface Donation80G extends Identified { category: '100_NO_APPROVAL' | '50_NO_APPROVAL' | '100_APPROVAL_REQD' | '50_APPROVAL_REQD'; doneeName: string; doneePAN: string; arnNumber: string; addrDetail: string; city: string; stateCode: StateCode | ''; pinCode: string; donationAmtCash: Money; donationAmtOtherMode: Money; transactionRefNum: string; ifscCode: string; donationDate: string; receiptNumber: string; notes: string; }
export interface DeductionLoan extends Identified { section: '80E' | '80EE' | '80EEA' | '80EEB'; loanTakenFrom: 'B' | 'I'; lenderName: string; lenderPAN: string; loanAccountNo: string; dateOfLoan: string; totalLoanAmount: Money; outstandingAmount: Money; interestAmount: Money; firstTimeBuyerEligible: boolean; vehicleRegNo: string; }
export interface LoanDeductions { loans: DeductionLoan[]; section80EEAStampDutyValue: Money; }

/** Official clauses under which a Section 80GGA deduction is claimed. */
export type Section80GGAClause =
  | '80GGA2a' | '80GGA2aa' | '80GGA2b' | '80GGA2bb'
  | '80GGA2c' | '80GGA2cc' | '80GGA2d' | '80GGA2e';

/** Canonical donation row for Schedule 80GGA (scientific research / rural development). */
export interface Schedule80GGAEntry extends Identified {
  relevantClause: Section80GGAClause;
  doneeName: string;
  doneePAN: string;
  addressLine: string;
  city: string;
  stateCode: StateCode | '';
  pinCode: string;
  cashAmount: Money;
  otherModeAmount: Money;
}

/** Canonical political contribution row for Schedule 80GGC. */
export interface Schedule80GGCEntry extends Identified {
  cashAmount: Money;
  otherModeAmount: Money;
  contributionDate: string;
  transactionRef: string;
  ifscCode: string;
  politicalPartyName: string;
  politicalPartyPAN: string;
}

/** Official Tax Return Preparer details (omitted entirely when ``used`` is false). */
export interface TaxReturnPreparer {
  used: boolean;
  identificationNumber: string;
  name: string;
  reimbursementFromGovernment: Money;
}

/** Form-10-IA filing metadata shared by Schedule 80DD and 80U. */
export interface Form10IAFiling { filed: 'Y' | 'N'; acknowledgementNumber: string; filingDate: string | null; formAckNum11A: string; }

/** Canonical Chapter VI-A aggregate mirroring the official UsrDeductUndChapVIAType schema. */
export interface ChapterVIA {
  section80C: Money;
  section80CCC: Money;
  /** Aggregate of the PensionContribution80CCC[] detail array (computed total). */
  pensionContribution80CCC: Money;
  section80CCDEmployeeOrSE: Money;
  section80CCD1B: Money;
  section80CCDEmployer: Money;
  /** Single PRAN from the PRANDtls[] detail array (typical case; one PRAN per assessee). */
  pranNumber: string;
  section80D: Money;
  section80DD: Money;
  section80DDNatureOfDisability: '1' | '2' | '';
  section80DDTypeOfDisability: '1' | '2' | '';
  section80DDDependentType: string;
  section80DDDependentPAN: string;
  section80DDDependentAadhaar: string;
  section80DDForm10IA: Form10IAFiling;
  section80DDUDIDNumber: string;
  section80DDB: Money;
  section80DDBUserType: '1' | '2' | '';
  section80DDBNameOfSpecDisease: string;
  section80DDBReimbursement: Money;
  section80E: Money;
  section80EE: Money;
  section80EEA: Money;
  section80EEAStampDutyValue: Money;
  section80EEB: Money;
  section80G: Money;
  section80GG: Money;
  section80GGRentPaid: Money;
  section80GGA: Money;
  section80GGC: Money;
  section80U: Money;
  section80UNatureOfDisability: '1' | '2' | '';
  section80UTypeOfDisability: '1' | '2' | '';
  section80UForm10IA: Form10IAFiling;
  section80UUDIDNumber: string;
  section80QQB: Money;
  section80QQBRoyaltyIncome: Money;
  section80QQBForm10CCDAckNum: string;
  section80RRB: Money;
  section80RRBForm10CCEAckNum: string;
  section80TTA: Money;
  section80TTB: Money;
  form10BAAckNum: string;
  anyOtherSection80CCH: Money;
  anyOtherSection80CCHDescription: string;
  totalChapterVIADeductions: Money;
  /** ITR-3 only — Part B/C business-linked deductions (80IA family). */
  businessDeductions: BusinessDeductions;
}

/** ITR-3 Part B/C Chapter VI-A business-linked deduction fields. */
export interface BusinessDeductions {
  totalPartBChapterVIA: Money;
  section80IA: Money;
  section80IAB: Money;
  section80IB: Money;
  section80IBA: Money;
  section80IC: Money;
  section80JJA: Money;
  section80JJAA: Money;
  totalPartCChapterVIA: Money;
  totalPartCAAndDChapterVIA: Money;
}

/** Empty Chapter VI-A aggregate used as the default for fresh drafts. */
export const EMPTY_CHAPTER_VIA: ChapterVIA = {
  section80C: 0, section80CCC: 0, pensionContribution80CCC: 0, section80CCDEmployeeOrSE: 0, section80CCD1B: 0, section80CCDEmployer: 0, pranNumber: '',
  section80D: 0, section80DD: 0, section80DDNatureOfDisability: '', section80DDTypeOfDisability: '', section80DDDependentType: '', section80DDDependentPAN: '', section80DDDependentAadhaar: '', section80DDForm10IA: { filed: 'N', acknowledgementNumber: '', filingDate: null, formAckNum11A: '' }, section80DDUDIDNumber: '',
  section80DDB: 0, section80DDBUserType: '', section80DDBNameOfSpecDisease: '', section80DDBReimbursement: 0,
  section80E: 0, section80EE: 0, section80EEA: 0, section80EEAStampDutyValue: 0, section80EEB: 0,
  section80G: 0, section80GG: 0, section80GGRentPaid: 0, section80GGA: 0, section80GGC: 0,
  section80U: 0, section80UNatureOfDisability: '', section80UTypeOfDisability: '', section80UForm10IA: { filed: 'N', acknowledgementNumber: '', filingDate: null, formAckNum11A: '' }, section80UUDIDNumber: '',
  section80QQB: 0, section80QQBRoyaltyIncome: 0, section80QQBForm10CCDAckNum: '',
  section80RRB: 0, section80RRBForm10CCEAckNum: '',
  section80TTA: 0, section80TTB: 0,
  form10BAAckNum: '', anyOtherSection80CCH: 0, anyOtherSection80CCHDescription: '', totalChapterVIADeductions: 0,
  businessDeductions: { totalPartBChapterVIA: 0, section80IA: 0, section80IAB: 0, section80IB: 0, section80IBA: 0, section80IC: 0, section80JJA: 0, section80JJAA: 0, totalPartCChapterVIA: 0, totalPartCAAndDChapterVIA: 0 },
};
/** TDS credit claim detail sub-object (mirrors TaxDeductCreditDtls). */
export interface TaxDeductCreditDtls {
  taxDeductedOwnHands: Money;
  taxDeductedIncome: Money;
  taxDeductedTDS: Money;
  taxClaimedOwnHands: Money;
  taxClaimedIncome: Money;
  taxClaimedTDS: Money;
  taxClaimedSpouseOthPrsnPAN: string;
  spouseOthPrsnAadhaar: string;
}

/** Empty TaxDeductCreditDtls used as the default for fresh TDS rows. */
export const EMPTY_TAX_DEDUCT_CREDIT_DTLS: TaxDeductCreditDtls = {
  taxDeductedOwnHands: 0, taxDeductedIncome: 0, taxDeductedTDS: 0,
  taxClaimedOwnHands: 0, taxClaimedIncome: 0, taxClaimedTDS: 0,
  taxClaimedSpouseOthPrsnPAN: '', spouseOthPrsnAadhaar: '',
};

/** Canonical TDS credit row. The visible UI fields keep their legacy names; */
/*  the schema-faithful fields are added alongside for serialization.        */
export interface TdsCredit extends Identified {
  // ── Visible UI fields (unchanged) ────────────────────────────────────────
  section: string;              // user-facing section code (e.g. "194A")
  deductorName: string;         // → EmployerOrDeductorOrCollecterName
  deductorTAN: string;          // → TAN (jurisdiction-prefixed)
  deductorPAN: string;          // → PAN (salary TDS uses employer PAN; TDS3 uses tenant PAN)
  certificateNo: string;        // TDS certificate number (UI convenience)
  grossAmount: Money;           // → IncChrgSal / GrossAmount / AmtForTaxDeduct
  taxDeducted: Money;           // → TotalTDSSal / TotTDSOnAmtPaid / TDSDeducted
  deductionDate: string;         // deduction date (UI convenience)
  uniqueTransactionNo: string;  // UTN (UI convenience)
  financialYear: string;         // user-entered FY label (UI convenience)
  verified26AS: boolean;         // UI reconciliation flag
  claimedInReturn: boolean;      // UI claim flag → drives TaxClaimedOwnHands
  // ── Schema-faithful enrichment (hidden from the current UI) ─────────────
  schedule: 'TDS1' | 'TDS2' | 'TDS3';       // which Schedule TDS the row belongs to
  tdsSectionCode: string;                   // schema enum code (e.g. "94A"), mapped from `section`
  deductedYr: number | '';                  // DeductedYr enum (2008..2025)
  headOfIncome: 'HP' | 'CG' | 'OS' | 'BP' | 'EI' | 'NA';
  tdsCreditName: 'S' | 'O';                  // S=Self, O=Other person
  panOfOtherPerson: string;
  aadhaarOfOtherPerson: string;
  broughtFwdTDSAmt: Money;                   // BroughtFwdTDSAmt
  amtCarriedFwd: Money;                      // AmtCarriedFwd / TDSCreditCarriedFwd
  claimOutOfTotTDSOnAmtPaid: Money;          // ITR-1/4 TDS2 simplified shape
  taxDeductCreditDtls: TaxDeductCreditDtls;  // ITR-2/3 TDS2 claim detail
  // ── Schedule TDS-3 (tenant/buyer) fields ────────────────────────────────
  nameOfTenant: string;
  grsRcptToTaxDeduct: Money;
  tdsClaimed: Money;
  panOfTenant: string;
  aadhaarOfTenant: string;
  // ── Schedule TCS fields (when a 206C section row is stored in the TDS list)
  tcsCreditOwner: '1' | '2';
  panOfSpouseOrOthrPrsn: string;
  tcsAmtCollOwnHand: Money;
  tcsAmtCollSpouseOrOthrHand: Money;
  tcsClaimedAmtCollOwnHand: Money;
  tcsClaimedAmtCollSpouseOrOthrHand: Money;
}

/** Empty TdsCredit used as the default for fresh rows. */
export const EMPTY_TDS_CREDIT: Omit<TdsCredit, 'id'> = {
  section: '192', deductorName: '', deductorTAN: '', deductorPAN: '', certificateNo: '',
  grossAmount: 0, taxDeducted: 0, deductionDate: '', uniqueTransactionNo: '',
  financialYear: '2025-26', verified26AS: false, claimedInReturn: true,
  schedule: 'TDS1', tdsSectionCode: '', deductedYr: '', headOfIncome: 'NA',
  tdsCreditName: 'S', panOfOtherPerson: '', aadhaarOfOtherPerson: '',
  broughtFwdTDSAmt: 0, amtCarriedFwd: 0, claimOutOfTotTDSOnAmtPaid: 0,
  taxDeductCreditDtls: { ...EMPTY_TAX_DEDUCT_CREDIT_DTLS },
  nameOfTenant: '', grsRcptToTaxDeduct: 0, tdsClaimed: 0, panOfTenant: '', aadhaarOfTenant: '',
  tcsCreditOwner: '1', panOfSpouseOrOthrPrsn: '', tcsAmtCollOwnHand: 0, tcsAmtCollSpouseOrOthrHand: 0, tcsClaimedAmtCollOwnHand: 0, tcsClaimedAmtCollSpouseOrOthrHand: 0,
};

/** Canonical TCS credit row (Schedule TCS). The visible UI fields mirror the */
/*  TDS row shape so the same UI component can render both; schema fields    */
/*  are enriched for serialization.                                          */
export interface TcsCredit extends Identified {
  // ── Visible UI fields (reuse TDS-like shape) ──────────────────────────────
  collectorName: string;        // → EmployerOrDeductorOrCollecterName
  collectorTAN: string;         // → EmployerOrDeductorOrCollectTAN
  grossAmount: Money;           // → GrossAmount
  taxCollected: Money;          // → TotalTCSAmt
  claimedInReturn: boolean;     // UI claim flag
  // ── Schema-faithful enrichment ──────────────────────────────────────────
  tcsCreditOwner: '1' | '2';                  // 1=Self, 2=Spouse/Other person
  panOfSpouseOrOthrPrsn: string;
  deductedYr: number | '';
  broughtFwdTDSAmt: Money;
  tcsAmtCollOwnHand: Money;                   // TCSCurrFYDtls.TCSAmtCollOwnHand
  tcsAmtCollSpouseOrOthrHand: Money;          // TCSCurrFYDtls.TCSAmtCollSpouseOrOthrHand
  tcsClaimedAmtCollOwnHand: Money;            // TCSClaimedThisYearDtls.TCSAmtCollOwnHand
  tcsClaimedAmtCollSpouseOrOthrHand: Money;   // TCSClaimedThisYearDtls.TCSAmtCollSpouseOrOthrHand
  claimedPANOfSpouseOrOthrPrsn: string;       // TCSClaimedThisYearDtls.PANOfSpouseOrOthrPrsn
}

/** Empty TcsCredit used as the default for fresh rows. */
export const EMPTY_TCS_CREDIT: Omit<TcsCredit, 'id'> = {
  collectorName: '', collectorTAN: '', grossAmount: 0, taxCollected: 0, claimedInReturn: true,
  tcsCreditOwner: '1', panOfSpouseOrOthrPrsn: '', deductedYr: '', broughtFwdTDSAmt: 0,
  tcsAmtCollOwnHand: 0, tcsAmtCollSpouseOrOthrHand: 0,
  tcsClaimedAmtCollOwnHand: 0, tcsClaimedAmtCollSpouseOrOthrHand: 0, claimedPANOfSpouseOrOthrPrsn: '',
};

/** Canonical tax challan (TaxPayment). Schema requires integer SrlNoOfChaln ≤ 99999. */
export interface TaxChallan extends Identified {
  kind: 'ADVANCE_TAX' | 'SELF_ASSESSMENT';
  bsrCode: string;            // → BSRCode, pattern [0-9]{3}[0-9A-Z]{4}
  depositDate: string;        // → DateDep (YYYY-MM-DD)
  challanSerialNo: number;     // → SrlNoOfChaln (integer, 0..99999)
  amount: Money;               // → Amt
  cin: string;                 // derived: BSR-Date-Serial
}

/** Empty TaxChallan used as the default for fresh challans. */
export const EMPTY_TAX_CHALLAN: Omit<TaxChallan, 'id'> = {
  kind: 'ADVANCE_TAX', bsrCode: '', depositDate: '', challanSerialNo: 0, amount: 0, cin: '',
};

export interface BankAccount extends Identified { bankName: string; accountNumber: string; ifscCode: string; accountType: 'SB' | 'CA' | 'CC' | 'OD' | 'NRO' | 'OTH'; useForRefund: boolean; }
export type FilingSection = '139(1)' | '139(4)' | '142(1)' | '148' | '153C' | '139(5)' | '139(9)' | '119(2)(b)';
export interface SeventhProvisoClause extends Identified { nature: '1' | '2' | '3' | '4'; amount: Money; }
export interface SeventhProviso {
  depositExceedsOneCrore: boolean; depositAmount: Money;
  foreignTravel: boolean; foreignTravelAmount: Money;
  electricityExpenditure: boolean; electricityExpenditureAmount: Money;
  otherClauseIV: boolean; clauseIVDetails: SeventhProvisoClause[];
}
export interface RepresentativeAssessee { name: string; email: string; mobileCountryCode: string; mobile: string; }
export interface AlternateAddress {
  residenceNo: string; residenceName: string; roadOrStreet: string; localityOrArea: string;
  cityOrTownOrDistrict: string; stateCode: StateCode | ''; countryCode: string; pinCode: string; zipCode: string;
}
export interface FilingStatus {
  filingSection: FilingSection; returnType: 'ORIGINAL' | 'REVISED';
  originalAcknowledgementNumber: string; originalFilingDate: string | null;
  noticeNumber: string; noticeDate: string | null;
  representative: RepresentativeAssessee | null;
  form10IEAAcknowledgement: string; form10IEADate: string | null;
  form10IEAEarlierAYOldRegime: 'Y' | 'N' | 'NA';
  form10IEAAssessmentYear: '' | '2024-25' | '2025-26';
  form10IEAEarlierAYAckOldRegime: string;
  form10IEAEarlierAYNewRegime: 'Y' | 'N';
  form10IEANewRegimeAssessmentYear: '' | '2025-26';
  form10IEAEarlierAYAckNewRegime: string;
  form10IEACurrentAYNewRegime: boolean; form10IEACurrentAYNewRegimeDate: string | null; form10IEACurrentAYNewRegimeAck: string;
  form10IEACurrentAYOldRegime: boolean; form10IEACurrentAYOldRegimeDate: string | null; form10IEACurrentAYOldRegimeAck: string;
  seventhProviso: SeventhProviso;
  /** ITR-2 only: SEBI FII/FPI registration number, required when isFiiFpi is true. */
  sebiRegistrationNumber: string;
  /** ITR-2 only: whether the assessee is a Foreign Institutional Investor / Foreign Portfolio Investor. */
  isFiiFpi: boolean;
  /** ITR-2 only: whether the Portuguese Civil Code (Schedule 5A) applies to this assessee. */
  portugueseCivilCodeApplies: boolean;
}
export type ExemptIncomeCategory = 'AGRI' | 'GOVC' | 'ISI' | 'SSRA' | 'SRSC' | 'SRST' | 'SRPC' | 'OTH' | 'OTHN';
export type ExemptIncomeSubCategory = '10(1)' | '10(2)' | '10(2A)' | '10(4)(i)' | '10(4)(ii)' | '10(4B)' | '10(4C)' | '10(4E)' | '10(4F)' | '10(4G)' | '10(4H)' | '10(6B)' | '10(6BB)' | '10(6D)' | '10(8)' | '10(8A)' | '10(8B)' | '10(9)' | '10(10BB)' | '10(10BC)' | '10(10D)' | '10(11)' | '10(11A)' | '10(12)' | '10(12A)' | '10(12AA)' | '10(12AB)' | '10(12B)' | '10(12BA)' | '10(12C)' | '10(13)' | '10(15)' | '10(16)' | '10(17A)' | '10(18)' | '10(19)' | '10(19A)' | '10(23AA)' | '10(23FBB)' | '10(23FBC)' | '10(23FD)' | '10(23FF)' | '10(25)' | '10(26)' | '10(26AAA)' | '10(30)' | '10(31)' | '10(32)' | '10(33)' | '10(35)' | '10(35A)' | '10(36)' | '10(37)' | '10(37A)' | '10(43)' | '10(44)' | 'DMD' | 'Incmexmptcircular' | 'Incmexmptnotification' | 'Receiptnotincme' | 'Anyother1' | 'Anyother2' | 'Anyother3' | 'Anyother4';
export interface ExemptIncomeEntry extends Identified { category: ExemptIncomeCategory; subCategory: ExemptIncomeSubCategory; description: string; grossAmount: Money; }
export interface AgriculturalLandParcel extends Identified { nameOfDistrict: string; pinCode: string; measurementOfLand: number; ownedFlag: 'O' | 'H'; irrigatedFlag: 'IRG' | 'RF'; }
export interface DtaaExemptIncomeEntry extends Identified { amountOfIncome: Money; natureOfIncome: string; countryName: string; countryCode: string; articleOfDtaa: string; headOfIncome: 'SA' | 'HP' | 'PG' | 'CG' | 'OS'; trcFlag: 'Y' | 'N'; }
export interface ExemptIncomeSchedule {
  interestIncome: Money;
  grossAgriculturalReceipts: Money;
  agriculturalExpenses: Money;
  unabsorbedAgriculturalLossPreviousEightYears: Money;
  agriculturalIncomeRule7And8: Money;
  netAgriculturalIncomeOrOtherIncomeRule7: Money;
  agriculturalLandParcels: AgriculturalLandParcel[];
  otherExemptIncome: ExemptIncomeEntry[];
  othersTotal: Money;
  dtaaExemptIncome: DtaaExemptIncomeEntry[];
  incomeNotChargeableToTax: Money;
  incomeChargeableAsPerDtaa: Money;
  passThroughIncomeNotChargeableToTax: Money;
  totalExemptIncome: Money;
}
export interface ImportProvenance { source: 'MANUAL' | 'FORM16' | 'AIS' | 'TIS' | '26AS' | 'ITD_PREFILL' | 'LEGACY'; importedAt: string | null; reference: string; }
export type ReconciliationRole = 'TAXABLE_ITR1' | 'RESTRICTED_112A_TAXABLE' | 'TAX_CREDIT' | 'OUT_OF_SCOPE_TAXABLE' | 'CONTROL_ONLY' | 'ACQUISITION_ONLY' | 'INFORMATIONAL' | 'PARSER_WARNING';
export type RelatedTab = 'SALARY' | 'OTHER_SOURCES' | 'CAPITAL_GAINS' | 'BUSINESS' | 'TAXES' | 'HOUSE_PROPERTY' | 'RECONCILIATION';
export interface ReconciliationEvidence extends Identified {
  source: 'AIS' | 'TIS' | '26AS' | 'ITD_PREFILL'; sourceCode: string; sourceSection: string;
  incomeHead: string; category: string; description: string; sourceName: string; sourceIdentifier: string;
  role: ReconciliationRole; relatedTab: RelatedTab; canonicalDestination?: string;
  evidenceKind: 'CATEGORY_CONTROL' | 'SOURCE_DETAIL' | 'SECTION_SUMMARY';
  reportedAmount: Money; processedAmount: Money; acceptedAmount: Money; taxAmount: Money;
  status: string; requiresReview: boolean; raw: Record<string, unknown>;
}
export type ReconciliationDiscrepancyStatus = 'PENDING' | 'CONFIRMED_TIS' | 'CONFIRMED_AIS' | 'IGNORED';
export interface ReconciliationDiscrepancy extends Identified {
  category: string; description: string; aisAmount: Money; tisAcceptedAmount: Money; as26Amount: Money;
  difference: Money; status: ReconciliationDiscrepancyStatus;
}
export interface ReconciliationState { evidence: ReconciliationEvidence[]; discrepancies: ReconciliationDiscrepancy[]; }
export interface Verification { capacity: 'SELF' | 'REPRESENTATIVE' | 'KARTA' | 'PARTNER'; place: string; date: string | null; declarationAccepted: boolean; }
export interface LegacyCompatibilityEnvelope { source: 'legacy-flat-v1'; unknownFields: Readonly<Record<string, unknown>>; }
export interface PersonalInfo {
  name: string;
  firstName: string;
  middleName: string;
  surnameOrOrgName: string;
  fatherName: string;
  pan: string;
  aadhaar: string;
  email: string;
  mobile: string;
  mobileCountryCode: string;
  secondaryEmail: string;
  secondaryMobile: string;
  secondaryMobileCountryCode: string;
  dateOfBirth: string | null;
  flatNo: string;
  residenceName: string;
  roadOrStreet: string;
  localityOrArea: string;
  city: string;
  stateCode: StateCode | '';
  countryCode: string;
  pinCode: string;
  zipCode: string;
  /** Mandatory CBDT PersonalInfo category, independent of employer row count. */
  employerCategory: EmployerCategory | '';
  age: number;
  assesseeStatus: 'I' | 'H' | 'F';
  landlineStdCode: string;
  landlinePhoneNo: string;
  secondaryAddressDifferent: boolean;
  alternateAddress: AlternateAddress | null;
  /** Questionnaire inputs surfaced as canonical draft fields for the
   *  eligibility engine (formerly read from the flat blob). */
  residentialStatus?: 'ROR' | 'RNOR' | 'NR';
  isDirector?: boolean;
  holdsUnlistedShares?: boolean;
}

// ---------------------------------------------------------------------------
// Capital Gains Schedule (Schedule CG)
// ---------------------------------------------------------------------------
//
// The canonical typed shape of the CBDT Schedule CG.  Each sub-array
// corresponds to a part of the official schedule:
//   - simplified112A  : ITR-1/4 quick-entry aggregate (sale − cost)
//   - schedule112A[]  : scrip-level 112A transactions (listed equity/MF)
//   - schedule115AD[] : scrip-level 115AD transactions (FII/FPI)
//   - vda[]           : Virtual Digital Asset transactions (s.115BBH)
//   - stImmovable[]/ltImmovable[] : land/building STCG/LTCG (with nested
//                                  transferees, improvements, exemptions)
//   - stDtaa[]/ltDtaa[] : DTAA-rate capital gains
//   - deductionClaims[] : s.54/54B/54EC/54F/115F/54D/54G/54GA claims
//   - stUnutilized[]/ltUnutilized[] : prior-year unutilized CG deposits
//   - aggregates/lossSetOff/quarterly : pass-through + computation matrix
//
// The element interfaces below are typed for the sub-arrays that the
// unified import pipeline auto-populates from AIS/TIS/26AS evidence
// (112A scrips, 115AD scrips, VDA, immovable property).  The remaining
// sub-arrays (stEquity, stNriUnlisted, stOtherAssets, ltProviso112,
// ltNri112115, ltForeignAssets, ltOtherAssets, stSlumpSale, ltSlumpSale,
// buyBackLosses) are kept as JsonRow[] because the existing
// CapitalGainsEntryManager already edits them with field-spec validation
// and a full rewrite is out of scope for Phase 1.

/** A generic JSON row (preserves the existing component's flexibility). */
export type JsonRow = Record<string, unknown>;

/** A read-only purchase reference row (AIS SFT-18(Pur) / SFT-17(Pur)).
 *  Purchases are cost-base evidence for future sales, not gains; they
 *  surface in the Capital Gains tab for transparency only. */
export interface CapitalGainPurchase {
  id: string;
  /** AIS information code, e.g. SFT-18(Pur), SFT-17(Pur). */
  informationCode: string;
  /** Reporting entity (RTA / depository / AMC). */
  reportingSource: string;
  /** Security / scheme name when available. */
  securityName: string;
  /** ISIN when available. */
  isin: string;
  /** Quarter or transaction date the purchase was reported for. */
  period: string;
  /** Total purchase amount (consideration paid). */
  purchaseAmount: number;
  /** Account/client id at the RTA, when available. */
  accountId: string;
  /** AIS-reported status ('Active', etc.). */
  status: string;
}

/** One scrip in Schedule 112A (listed equity / equity-oriented MF). */
export interface Scrip112A {
  id: string;
  /** Whether the sale/transfer is on or before 31-Jan-2018 ('BE') or after ('AE'). */
  shareOnOrBefore: 'BE' | 'AE' | '';
  /** ISIN of the security. */
  isin: string;
  /** Name of the security / fund scheme. */
  name: string;
  quantity: number;
  salePricePerUnit: number;
  totalSaleValue: number;
  costWithoutIndexation: number;
  acquisitionCost: number;
  fmvPerUnit: number;
  totalFmv: number;
  transferExpenses: number;
  /** Computed by the tax engine — lower of cost or FMV (grandfathering). */
  ltcgBeforeLower?: number;
  /** Computed by the tax engine — total deductions. */
  totalDeductions?: number;
  /** Computed by the tax engine — taxable balance after ₹1.25L exemption. */
  balance?: number;
  /** Added during the ITR-2 backend mapper work — the original shipped type
   *  had no date fields, but CBDT Schedule 112A requires a transfer date per
   *  scrip. Optional so existing construction sites are unaffected until
   *  updated; a scrip missing this is skipped (not fabricated) by the mapper. */
  dateOfAcquisition?: string | null;
  dateOfTransfer?: string | null;
}

/** One scrip in Schedule 115AD (FII/FPI). Same shape as 112A. */
export interface Scrip115AD extends Scrip112A {}

/** One Virtual Digital Asset transaction (s.115BBH). */
export interface VdaEntry {
  id: string;
  dateOfAcquisition: string;
  dateOfTransfer: string;
  /** Head of income: 'CG' (capital gains) or 'BI' (business income, ITR-3 only). */
  head: 'CG' | 'BI' | '';
  acquisitionCost: number;
  consideration: number;
  /** Computed income from VDA (consideration − acquisitionCost). */
  incomeFromVda?: number;
}

/** A transferee detail nested inside stImmovable/ltImmovable rows. */
export interface TransfereeDetail {
  id: string;
  name: string;
  pan: string;
  aadhaar?: string;
  panOrTan?: string;
  share: number;
  amount: number;
  address?: string;
  stateCode?: string;
  countryCode?: string;
  pinCode?: string;
  zipCode?: string;
}

/** An improvement-cost detail nested inside ltImmovable rows. */
export interface ImprovementDetail {
  id: string;
  serialNumber: number;
  cost: number;
  financialYear: string;
  indexedCost?: number;
}

/** An exemption claim nested inside ltImmovable rows. */
export interface ExemptionClaim {
  id: string;
  section: '54' | '54B' | '54EC' | '54F' | '115F' | '54D' | '54G' | '54GA' | '';
  amount: number;
}

/** One STCG/LTCG land-or-building row (Schedule CG A1/B1). */
export interface ImmovableAssetGain {
  id: string;
  dateOfPurchase?: string;
  dateOfSale: string;
  fullConsideration: number;
  stampDutyValue?: number;
  /** Property address from AIS SFT-012 detail. */
  propertyAddress?: string;
  /** Section 50C consideration (if stamp duty > consideration). */
  consideration50C?: number;
  acquisitionCost: number;
  improvementCost?: number;
  transferExpenses: number;
  deduction54B?: number;
  totalDeductions?: number;
  balance?: number;
  capitalGain?: number;
  /** LTCG-only: indexed acquisition cost. */
  indexedAcquisitionCost?: number;
  /** LTCG-only: indexed improvement cost. */
  indexedImprovementCost?: number;
  improvementFinancialYear?: string;
  exemptionSection?: '54' | '54B' | '54EC' | '54F' | '115F' | '54D' | '54G' | '54GA' | '';
  exemptionAmount?: number;
  transferees?: TransfereeDetail[];
  improvements?: ImprovementDetail[];
  exemptions?: ExemptionClaim[];
}

/** A DTAA-rate capital gains row (Schedule CG A6/B7). */
export interface DtaaEntry {
  id: string;
  amount: number;
  itemNumber?: string;
  countryName: string;
  countryCode?: string;
  article: string;
  treatyRate?: number;
  trcAvailable?: boolean;
  itActSection?: string;
  itActRate?: number;
  applicableRate?: number;
}

/** A s.54/54B/54EC/54F/115F/54D/54G/54GA deduction claim (Schedule CG F). */
export interface DeductionClaim {
  id: string;
  section: '54' | '54B' | '54EC' | '54F' | '115F' | '54D' | '54G' | '54GA' | '';
  dateOfTransfer: string;
  newAssetCost?: number;
  dateOfPurchase?: string;
  amountDeposited?: number;
  depositDate?: string;
  accountNumber?: string;
  ifsc?: string;
  amountDeducted: number;
}

/** Prior-year unutilized CG deposit (s.54/54B/54D/54G/54GA reinvestment). */
export interface UnutilizedDeposit {
  id: string;
  transferPreviousYear: string;
  sectionClaimed: string;
  yearAssetAcquired?: string;
  amountUtilized: number;
  amountUnutilized: number;
}

/** Pass-through STCG/LTCG aggregates for the schedule. */
export interface CapitalGainsAggregates {
  stPassThrough: number;
  stPassThrough20: number;
  stPassThrough30: number;
  stPassThroughApplicable: number;
  ltPassThrough: number;
  ltPassThrough112A: number;
  ltPassThrough125: number;
}

/** Current-year loss set-off matrix (Schedule CG H). */
export type LossSetOff = Record<string, number>;

/** Instalment-period accrual matrix (Schedule CG G). */
export type QuarterlyMatrix = Record<string, number>;

/** The fully-typed canonical Capital Gains Schedule. */
export interface CapitalGainsSchedule {
  /** ITR-1/4 quick-entry aggregate. Auto-populated from imported scrips. */
  simplified112A: { totalSaleConsideration: number; totalCostAcquisition: number };
  /** STCG land/building (A1). */
  stImmovable: ImmovableAssetGain[];
  /** STCG equity/STT (A2). */
  stEquity: JsonRow[];
  /** STCG NRI unlisted (A3). */
  stNriUnlisted: JsonRow[];
  /** STCG other assets (A4). */
  stOtherAssets: JsonRow[];
  /** STCG slump sale (A5, ITR-3 only). */
  stSlumpSale: JsonRow[];
  /** LTCG land/building (B1). */
  ltImmovable: ImmovableAssetGain[];
  /** LTCG proviso to s.112 (B2). */
  ltProviso112: JsonRow[];
  /** LTCG NRI u/s 112/115 (B3). */
  ltNri112115: JsonRow[];
  /** LTCG NRI specified foreign assets (B4, s.115F). */
  ltForeignAssets: JsonRow[];
  /** LTCG other assets (B5). */
  ltOtherAssets: JsonRow[];
  /** LTCG slump sale (B6, ITR-3 only). */
  ltSlumpSale: JsonRow[];
  /** Schedule 112A scrips (C) — auto-populated from AIS SFT-17-LES. */
  schedule112A: Scrip112A[];
  /** Schedule 115AD scrips (D) — auto-populated from AIS SFT-18-EMF (FII). */
  schedule115AD: Scrip115AD[];
  /** Purchase reference rows (informational only, read-only).  AIS SFT-18(Pur)
   *  and SFT-17(Pur) purchase transactions are NOT capital gains — they are
   *  cost-base evidence for future sales.  They surface here so the user can
   *  see every purchase the AIS reported, but they contribute no gain. */
  purchases: CapitalGainPurchase[];
  /** VDA transactions (E) — auto-populated from AIS/26AS VDA rows. */
  vda: VdaEntry[];
  /** Prior-year unutilized STCG deposits. */
  stUnutilized: UnutilizedDeposit[];
  /** Prior-year unutilized LTCG deposits. */
  ltUnutilized: UnutilizedDeposit[];
  /** STCG under DTAA (A6). */
  stDtaa: DtaaEntry[];
  /** LTCG under DTAA (B7). */
  ltDtaa: DtaaEntry[];
  /** Capital loss on buy-back of shares. */
  buyBackLosses: JsonRow[];
  /** s.54/54B/54EC/54F/115F/54D/54G/54GA deduction claims (F). */
  deductionClaims: DeductionClaim[];
  /** NRI STT paid/not-paid aggregates. */
  stSection48: { nriSttPaid: number; nriSttNotPaid: number };
  /** NRI LTCG without indexation + s.54F. */
  ltNriProviso48: { ltcgWithoutBenefit: number; deduction54F: number };
  /** NRI/FII Schedule 112A balance + s.54F. */
  ltNri112A: Record<string, number>;
  /** Whether prior-year STCG unutilized deposits exist ('Y'/'N'/'X'). */
  stUnutilizedFlag: 'Y' | 'N' | 'X';
  /** Whether prior-year LTCG unutilized deposits exist ('Y'/'N'/'X'). */
  ltUnutilizedFlag: 'Y' | 'N' | 'X';
  /** Instalment-period accrual matrix (G). */
  quarterly: QuarterlyMatrix;
  /** Pass-through STCG/LTCG aggregates. */
  aggregates: CapitalGainsAggregates;
  /** Current-year loss set-off matrix (H). */
  lossSetOff: LossSetOff;
}

/** Empty (factory-seed) capital gains schedule. */
export const EMPTY_CAPITAL_GAINS_SCHEDULE: CapitalGainsSchedule = {
  simplified112A: { totalSaleConsideration: 0, totalCostAcquisition: 0 },
  stImmovable: [], stEquity: [], stNriUnlisted: [], stOtherAssets: [], stSlumpSale: [],
  ltImmovable: [], ltProviso112: [], ltNri112115: [], ltForeignAssets: [], ltOtherAssets: [], ltSlumpSale: [],
  schedule112A: [], schedule115AD: [], purchases: [], vda: [], stUnutilized: [], ltUnutilized: [], stDtaa: [], ltDtaa: [], buyBackLosses: [], deductionClaims: [],
  stSection48: { nriSttPaid: 0, nriSttNotPaid: 0 },
  ltNriProviso48: { ltcgWithoutBenefit: 0, deduction54F: 0 },
  ltNri112A: {},
  stUnutilizedFlag: 'N',
  ltUnutilizedFlag: 'N',
  quarterly: {},
  aggregates: { stPassThrough: 0, stPassThrough20: 0, stPassThrough30: 0, stPassThroughApplicable: 0, ltPassThrough: 0, ltPassThrough112A: 0, ltPassThrough125: 0 },
  lossSetOff: {},
};

export interface ReturnDraft {
  schemaVersion: 1; assessmentYear: string; form: ItrForm; regime: TaxRegime;
  personal: PersonalInfo;
  filing: FilingStatus; employers: Employer[]; houseProperties: HouseProperty[]; housePropertyPassThroughIncome: number; businesses: PresumptiveBusiness[]; capitalGainsSchedule: CapitalGainsSchedule;
  otherSources: {
    interest: InterestIncome[];
    dividends: DividendIncome[];
    familyPension: FamilyPension;
    winnings: WinningIncome[];
    gifts: GiftIncome[];
    otherIncome: OtherIncomeEntry[];
    dtaaIncome: DtaaIncomeEntry[];
    dtaaAggregates: { totalAmountTaxUsDtaa: Money };
    section89A: Section89AEntry[];
    section89AAggregates: Section89AAggregates;
    accumulatedPf: AccumulatedPfEntry[];
    accumulatedPfAggregates: AccumulatedPfAggregates;
    specialRateIncome: SpecialRateIncomeEntry[];
    unexplainedIncome: UnexplainedIncomeDetails;
    deductions: OtherSourcesDeductions;
  };
  exemptIncome: ExemptIncomeSchedule;
  deductions: { section80C: Investment80C[]; pensionContribution80CCC: PensionContribution80CCC[]; section80D: Section80D; section80G: Donation80G[]; loans: LoanDeductions; chapterVIA: ChapterVIA; schedule80GGA: Schedule80GGAEntry[]; schedule80GGC: Schedule80GGCEntry[] };
  taxes: { tds: TdsCredit[]; tcs: TcsCredit[]; challans: TaxChallan[] }; bankAccounts: BankAccount[];
  /** Brought-forward loss inputs from previous assessment years (Schedule CYLA). */
  lossesBroughtForward: BroughtForwardLosses;
  /** Net profit from P&L when the user files regular books under Section 44AA/regular PGBP (non-presumptive). */
  bpNetProfit: Money;
  verification: Verification; taxReturnPreparer: TaxReturnPreparer; provenance: ImportProvenance[]; compatibility?: LegacyCompatibilityEnvelope; reconciliation: ReconciliationState;
  // ── ITR-2/3 additive fields (ignored by ITR-1/ITR-4) ──────────────────
  /** Schedule CFL opening rows, per origin AY. ITR-2/3 only. */
  broughtForwardLossEntries: BroughtForwardLossEntry[];
  /** Legacy CFL control totals, reconciliation only. ITR-2/3 only. */
  carriedForwardLossEntries: CarriedForwardLossEntry[];
  /** Schedule SI (special-rate income). ITR-2/3 only. */
  scheduleSIEntries: ScheduleSIEntry[];
  /** Schedule FSI. ITR-2/3 only. */
  foreignSourceIncome: ForeignSourceIncomeEntry[];
  /** Schedule TR. ITR-2/3 only. */
  foreignTaxRelief: ForeignTaxReliefEntry[];
  /** Schedule FA. ITR-2/3 only. */
  foreignAssets: ForeignAssetEntry[];
  /** Schedule SPI (clubbing of income). ITR-2/3 only. */
  clubbedIncome: ClubbedIncomeEntry[];
  /** Schedule PTI (pass-through income). ITR-2/3 only. */
  passThroughIncomeEntries: PassThroughIncomeEntry[];
  /** Schedule AMT + AMTC. ITR-2/3 only. */
  amt: AMTDetails | null;
  /** Schedule AL. ITR-2/3 only. */
  assetLiability: AssetLiabilityDetails | null;
  /** Schedule 5A (Portuguese Civil Code). ITR-2/3 only. */
  portugueseCivilCode: PortugueseCivilCodeDetails | null;
  /** Schedule ESOP. ITR-2/3 only. */
  esopDeferrals: ESOPDeferralEntry[];
}

/** Canonical aggregate of brought-forward losses the user is carrying into the current year. */
export interface BroughtForwardLosses {
  bfLossHP: Money;
  bfLossBusiness: Money;
  bfLossSTCG: Money;
  bfLossLTCG: Money;
  bfLossSpeculation: Money;
}

export const EMPTY_BROUGHT_FORWARD_LOSSES: BroughtForwardLosses = {
  bfLossHP: 0, bfLossBusiness: 0, bfLossSTCG: 0, bfLossLTCG: 0, bfLossSpeculation: 0,
};

// ── ITR-2/3 additive schedules (FSI, TR, FA, SPI, PTI, AMT, AL, 5A, ESOP,
// brought/carried-forward loss ledger) — ignored by ITR-1/ITR-4. Mirrors
// app/schemas/return_draft.py's ITR-2/ITR-3 additive schedules block exactly.

export type LossHead = 'HP' | 'STCG' | 'LTCG' | 'RaceHorse';
export type ForeignReliefSection = '90' | '90A' | '91';
export type ForeignAssetType =
  | 'BANK_ACCOUNT' | 'CUSTODIAL_ACCOUNT' | 'EQUITY_DEBT_INTEREST' | 'CASH_VALUE_INSURANCE'
  | 'FINANCIAL_INTEREST' | 'IMMOVABLE_PROPERTY' | 'SIGNING_AUTHORITY' | 'TRUST'
  | 'OTHER_FOREIGN_INCOME' | 'OTHER_ASSET';
export type ClubbedHeadOfIncome = 'SAL' | 'HP' | 'CG' | 'OS';
export type PTIIncomeHead = 'HP' | 'STCG' | 'LTCG' | 'OS';

/** Opening brought-forward loss balance for one origin AY (Schedule CFL opening rows). ITR-2/3. */
export interface BroughtForwardLossEntry extends Identified {
  assessmentYear: string; head: LossHead; subCategory: string;
  originalLoss: Money; broughtForward: Money; dateOfFiling?: string | null;
}

/** Legacy CFL control total retained for reconciliation only. ITR-2/3. */
export interface CarriedForwardLossEntry extends Identified {
  assessmentYearOfLoss: string; head: LossHead; originalLoss: Money; lossRemaining: Money;
}

export type ScheduleSISection = '115BB' | '115BBE' | '115BBF' | '115BBG' | '115BBJ' | '115BBA' | '111';

/** Schedule SI: special-rate income not generated by another schedule.
 *  Distinct from OtherSources' SpecialRateIncomeEntry (sourceDescription/
 *  sourceAmount, Schedule-5A codes) -- ITR-2's calculator needs grossIncome/
 *  deductions/taxRatePct per section, which that existing type lacks. */
export interface ScheduleSIEntry extends Identified {
  section: ScheduleSISection; description: string;
  grossIncome: Money; deductions: Money; taxRatePct?: number | null;
}

/** Schedule FSI: foreign-source income and foreign tax, per jurisdiction. */
export interface ForeignSourceIncomeEntry extends Identified {
  countryCode: string; taxIdentificationNo: string;
  salaryIncome: Money; hpIncome: Money; cgIncome: Money; osIncome: Money;
  taxPaidOutsideIndia: Money; taxPayableInIndia: Money; reliefSection: ForeignReliefSection;
}

/** Schedule TR: foreign tax relief claim for one jurisdiction (Sec 90/90A/91). */
export interface ForeignTaxReliefEntry extends Identified {
  countryCode: string; taxIdentificationNo: string;
  incomeIncludedInThisReturn: Money; taxPaidOutsideIndia: Money; indianTaxPayable: Money;
  reliefClaimed: Money; reliefSection: ForeignReliefSection; form67Filed: boolean;
}

/** Schedule FA: one foreign asset or account disclosure. */
export interface ForeignAssetEntry extends Identified {
  assetType: ForeignAssetType; countryCode: string; institutionOrEntityName: string;
  address: string; accountOrAssetIdentifier: string; ownershipStatus: string;
  openingOrAcquisitionDate: string; peakValue: Money; closingValue: Money;
  grossIncome: Money; incomeOffered: Money; incomeHead?: ClubbedHeadOfIncome | null;
}

/** Schedule SPI: income clubbed under Section 64. */
export interface ClubbedIncomeEntry extends Identified {
  specifiedPersonName: string; pan: string; relationship: string;
  amountIncluded: Money; headOfIncome: ClubbedHeadOfIncome;
}

/** Schedule PTI: pass-through income from a business trust or investment fund.
 *  Distinct from HouseProperty.passThroughIncome / CG pass-through aggregates. */
export interface PassThroughIncomeEntry extends Identified {
  entityName: string; entityPAN: string; incomeHead: PTIIncomeHead;
  section: string; incomeAmount: Money; tdsCredit: Money;
}

/** AMT credit brought forward from one assessment year. */
export interface AMTCreditEntry extends Identified {
  assessmentYear: string; creditBroughtForward: Money;
}

/** Alternate Minimum Tax additions and opening credit ledger. ITR-2/3. */
export interface AMTDetails {
  deduction10AA: Money; deduction80IAto80RRBExcept80P: Money;
  deduction35ADNetDepreciation: Money; creditsBroughtForward: AMTCreditEntry[];
}

/** Schedule AL: assets and related liabilities (mandatory above the income threshold). */
export interface AssetLiabilityDetails {
  immovableProperty: Money; cashInHand: Money; bankDeposits: Money;
  sharesAndSecurities: Money; insurancePolicies: Money; loansAndAdvances: Money;
  jewellery: Money; art: Money; vehiclesBoatsAircraft: Money; relatedLiabilities: Money;
}

/** Schedule 5A: Portuguese Civil Code income apportionment facts. */
export interface PortugueseCivilCodeDetails {
  spouseName: string; spousePAN: string; spouseAadhaar: string;
  hpAmountApportioned: Money; cgAmountApportioned: Money; osAmountApportioned: Money;
  tdsApportioned: Money;
}

/** Eligible-startup ESOP tax deferral ledger entry (Sec 191(2)). */
export interface ESOPDeferralEntry extends Identified {
  employerPAN: string; dpiitRegistrationNumber: string; assessmentYear: string;
  taxDeferredBroughtForward: Money; taxPayableCurrentYear: Money; balanceTaxCarriedForward: Money;
}
