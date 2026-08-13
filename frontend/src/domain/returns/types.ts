export type ItrForm = 'ITR-1' | 'ITR-2' | 'ITR-3' | 'ITR-4';
export type TaxRegime = 'old' | 'new';
export type Money = number;
export interface Identified { id: string; }

export interface Employer extends Identified {
  customEmployerName: string; employerName: string; employerTAN: string; natureOfEmployment: string;
  employerAddress: string; employerCity: string; employerStateCode: string; employerPinCode: string; employerZipCode: string;
  salaryNatureRows: Array<{ id: string; natureCode: string; otherDescription: string; amount: Money }>;
  perquisiteNatureRows: Array<{ id: string; natureCode: string; otherDescription: string; amount: Money }>;
  section10ExemptionRows: Array<{ id: string; natureCode: string; otherDescription: string; amount: Money }>;
  basic: Money; da: Money; commission: Money; hra: Money; bonus: Money; allowances: Money; lta: Money;
  otherAllowance: Money; arrearSalary: Money; perquisites: Money; profitsInLieu: Money; rentPaid: Money;
  city: string; isMetroCity: boolean; isGovernmentEmployee: boolean; isDisabledEmployee: boolean;
  commutedPension: Money; gratuity: Money; leaveEncashment: Money; averageMonthlySalary: Money; yearsOfService: number;
  unavailedLeaveDays: number; actualLtaFare: Money; isDomesticTravel: boolean; journeysInBlock: number; ltaExempt: Money;
  numberOfChildren: number; gratuityAlsoReceived: boolean; transportAllowance: Money; childrenEducationAllowance: Money;
  hostelExpenditureAllowance: Money; uniformAllowance: Money; entertainmentAllowance: Money; professionalTax: Money;
  vrsCompensation: Money; retrenchmentCompensation: Money; otherExempt: Money; tdsDeducted: Money; employerNPS: Money;
}
export interface CoOwner { coOwnerSNo: number; name: string; pan: string; aadhaar: string; share: number; }
export interface TenantDetail { tenantSNo: number; name: string; pan: string; aadhaar: string; panOrTan: string; }
export interface HomeLoan { lenderType: 'B' | 'I'; lenderName: string; lenderPAN: string; loanAccountNo: string; dateOfLoan: string; totalLoanAmount: Money; loanOutstandingAmount: Money; interestUs24B: Money; constructionCompletionDate: string; completedWithin5Years: boolean; preConstructionInterest: Money; }
export interface HouseProperty extends Identified {
  name: string; propertySequenceNo: number; propertyType: 'SELF_OCCUPIED' | 'LET_OUT' | 'DEEMED_LET_OUT';
  address: string; premisesName: string; roadOrStreet: string; area: string; city: string; state: string; pinCode: string; zipCode: string;
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
export interface FinancialParticulars { cashBalance: Money; bankBalance: Money; inventory: Money; sundryDebtors: Money; sundryCreditors: Money; otherAssets: Money; totalAssets: Money; securedLoans: Money; unsecuredLoans: Money; advances: Money; otherLiabilities: Money; totalLiabilities: Money; grossProfit: Money; expenses: Money; netProfit: Money; }
export interface Presumptive44AD extends Identified, BusinessIdentity { scheme: '44AD'; digitalReceipts: Money; nonDigitalReceipts: Money; digitalPresumptiveIncome: Money; nonDigitalPresumptiveIncome: Money; declaredIncome: Money; gstinTurnovers: GstinTurnoverRow[]; financialParticulars: FinancialParticulars; }
export interface Presumptive44ADA extends Identified, BusinessIdentity { scheme: '44ADA'; grossReceipts: Money; digitalReceipts: Money; nonDigitalReceipts: Money; declaredIncome: Money; gstinTurnovers: GstinTurnoverRow[]; financialParticulars: FinancialParticulars; }
export interface VehicleRecord extends Identified { vehicleNumber: string; vehicleType: 'HEAVY' | 'OTHER'; tonnage: number; ownedMonths: number; leasedOrHired: boolean; presumptiveIncome: Money; }
export interface Presumptive44AE extends Identified, BusinessIdentity { scheme: '44AE'; vehicles: VehicleRecord[]; declaredIncome: Money; gstinTurnovers: GstinTurnoverRow[]; financialParticulars: FinancialParticulars; }
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
export interface Policy80D extends Identified { insurerName: string; policyNo: string; premiumAmount: Money; policyType: 'INDIVIDUAL' | 'FAMILY_FLOATER' | 'GROUP' | 'OTHER'; dateOfCommencement: string; }
export interface Category80D { policies: Policy80D[]; preventiveCheckup: Money; medicalExpense: Money; }
export interface Section80D { selfSeniorCitizen: 'Y' | 'N' | 'S'; parentsSeniorCitizen: 'Y' | 'N' | 'P'; selfFamily: Category80D; selfFamilySenior: Category80D; parents: Category80D; parentsSenior: Category80D; }
export interface Donation80G extends Identified { category: '100_NO_APPROVAL' | '50_NO_APPROVAL' | '100_APPROVAL_REQD' | '50_APPROVAL_REQD'; doneeName: string; doneePAN: string; arnNumber: string; addrDetail: string; city: string; stateCode: string; pinCode: string; donationAmtCash: Money; donationAmtOtherMode: Money; transactionRefNum: string; ifscCode: string; donationDate: string; receiptNumber: string; notes: string; }
export interface DeductionLoan extends Identified { section: '80E' | '80EE' | '80EEA' | '80EEB'; loanTakenFrom: 'B' | 'I'; lenderName: string; lenderPAN: string; loanAccountNo: string; dateOfLoan: string; totalLoanAmount: Money; outstandingAmount: Money; interestAmount: Money; firstTimeBuyerEligible: boolean; vehicleRegNo: string; }
export interface LoanDeductions { loans: DeductionLoan[]; section80EEAStampDutyValue: Money; }

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
  section80DDB: 0, section80DDBUserType: '', section80DDBNameOfSpecDisease: '',
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
export interface FilingStatus { filingSection: '139(1)' | '139(4)' | '139(5)' | '119(2)(b)'; returnType: 'ORIGINAL' | 'REVISED'; originalAcknowledgementNumber: string; originalFilingDate: string | null; noticeNumber: string; }
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
export interface Verification { capacity: 'SELF' | 'REPRESENTATIVE'; place: string; date: string | null; declarationAccepted: boolean; }
export interface LegacyCompatibilityEnvelope { source: 'legacy-flat-v1'; unknownFields: Readonly<Record<string, unknown>>; }
export interface ReturnDraft {
  schemaVersion: 1; assessmentYear: string; form: ItrForm; regime: TaxRegime;
  personal: { name: string; pan: string; email: string; mobile: string; dateOfBirth: string | null };
  filing: FilingStatus; employers: Employer[]; houseProperties: HouseProperty[]; housePropertyPassThroughIncome: number; businesses: PresumptiveBusiness[]; capitalGainsSchedule: Record<string, unknown>;
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
  deductions: { section80C: Investment80C[]; section80D: Section80D; section80G: Donation80G[]; loans: LoanDeductions; chapterVIA: ChapterVIA };
  taxes: { tds: TdsCredit[]; tcs: TcsCredit[]; challans: TaxChallan[] }; bankAccounts: BankAccount[];
  verification: Verification; provenance: ImportProvenance[]; compatibility?: LegacyCompatibilityEnvelope;
}
