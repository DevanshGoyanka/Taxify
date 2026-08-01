export type ItrForm = 'ITR-1' | 'ITR-2' | 'ITR-3' | 'ITR-4';
export type TaxRegime = 'old' | 'new';
export type Money = number;
export interface Identified { id: string; }

export interface Employer extends Identified {
  customEmployerName: string; employerName: string; employerTAN: string; natureOfEmployment: string;
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
export interface HomeLoan { lenderType: 'B' | 'I' | 'L'; lenderName: string; lenderPAN: string; loanAccountNo: string; dateOfLoan: string; totalLoanAmount: Money; loanOutstandingAmount: Money; interestUs24B: Money; constructionCompletionDate: string; completedWithin5Years: boolean; preConstructionInterest: Money; }
export interface HouseProperty extends Identified {
  name: string; propertySequenceNo: number; propertyType: 'SELF_OCCUPIED' | 'LET_OUT' | 'DEEMED_LET_OUT';
  address: string; premisesName: string; roadOrStreet: string; area: string; city: string; state: string; pinCode: string;
  countryCode: string; propertyIdentificationNo: string; propertyOwnerType: 'SE' | 'MI' | 'SP' | 'OT'; ownershipType: 'SOLE' | 'JOINT';
  ownershipShare: number; isCoOwned: boolean; isPropertyInJointOwnership: boolean; coOwners: CoOwner[];
  annualRent: Money; municipalRateableValue: Money; fairRentValue: Money; standardRent: Money; annualLettingValue: Money;
  unrealizedRent: Money; arrearsOfRent: Money; vacancyPeriodMonths: number; municipalTaxesPaid: Money; interestOnLoan: Money;
  preConstructionInterest: Money; lenderName: string; lenderPAN: string; lenderType: 'B' | 'I' | 'L'; loanAccountNo: string;
  loanSanctionDate: string; constructionCompletionDate: string; principalRepayment: Money; totalLoanAmount: Money;
  loanOutstandingAmount: Money; completedWithin5Years: boolean; homeLoans: HomeLoan[]; tenantName: string; tenantPAN: string;
  tenantAadhaar: string; grossAnnualValue: Money; netAnnualValue: Money; standardDeduction30Pct: Money; incomeFromHP: number;
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

export type InterestKind = 'SAVINGS_BANK' | 'TERM_DEPOSIT' | 'IT_REFUND' | 'POST_OFFICE' | 'NSC' | 'SCSS' | 'OTHER' | 'BONDS' | 'SECURITIES';
export interface InterestIncome extends Identified { kind: InterestKind; grossAmount: Money; tdsDeducted: Money; bankName: string; accountType: 'SAVINGS' | 'CURRENT' | 'FD' | ''; accountNumber: string; ifscCode: string; postOfficeName: string; accountNumberPO: string; nscCertificateNumber: string; yearOfPurchase: number; scssAccountNumber: string; dateOfOpening: string; deductorName: string; deductorTAN: string; remarks: string; }
export interface DividendIncome extends Identified { section: '10(22e)' | '10(22f)' | '194'; grossAmount: Money; tdsDeducted: Money; companyName: string; companyPAN: string; deductorTAN: string; isin: string; category: 'EQUITY' | 'PREFERENCE' | 'MUTUAL_FUND' | ''; q1: Money; q2: Money; q3: Money; q4: Money; }
export interface FamilyPension { grossAmount: Money; payerName: string; relationToPensioner: string; }
export interface WinningIncome extends Identified { type: 'LOTTERY' | 'BETTING' | 'CARD_GAME' | 'HORSE_RACE'; grossAmount: Money; tdsDeducted: Money; payerName: string; payerTAN: string; dateOfWinning: string; }
export interface GiftIncome extends Identified { propertyType: 'IMMOVABLE' | 'CASH' | 'MOVABLE' | 'OTHER'; value: Money; donorName: string; donorRelation: string; dateOfReceipt: string; description: string; fromRelative: boolean; receivedOnMarriage: boolean; }

export interface Investment80C extends Identified { investmentType: string; identificationNo: string; accountOrPolicyNo: string; amount: Money; dateOfInvestment: string; institutionName: string; institutionPAN: string; }
export interface Policy80D extends Identified { insurerName: string; policyNo: string; premiumAmount: Money; policyType: 'INDIVIDUAL' | 'FAMILY_FLOATER' | 'GROUP' | 'OTHER'; dateOfCommencement: string; }
export interface Category80D { policies: Policy80D[]; preventiveCheckup: Money; medicalExpense: Money; }
export interface Section80D { selfSeniorCitizen: 'Y' | 'N' | 'S'; parentsSeniorCitizen: 'Y' | 'N' | 'P'; selfFamily: Category80D; selfFamilySenior: Category80D; parents: Category80D; parentsSenior: Category80D; }
export interface Donation80G extends Identified { category: '100_NO_APPROVAL' | '50_NO_APPROVAL' | '100_APPROVAL_REQD' | '50_APPROVAL_REQD'; doneeName: string; doneePAN: string; arnNumber: string; addrDetail: string; city: string; stateCode: string; pinCode: string; donationAmtCash: Money; donationAmtOtherMode: Money; transactionRefNum: string; ifscCode: string; donationDate: string; receiptNumber: string; notes: string; }
export interface DeductionLoan extends Identified { section: '80E' | '80EE' | '80EEA' | '80EEB'; loanTakenFrom: 'B' | 'I'; lenderName: string; lenderPAN: string; loanAccountNo: string; dateOfLoan: string; totalLoanAmount: Money; outstandingAmount: Money; interestAmount: Money; firstTimeBuyerEligible: boolean; vehicleRegNo: string; }
export interface LoanDeductions { loans: DeductionLoan[]; section80EEAStampDutyValue: Money; }
export interface TdsCredit extends Identified { section: string; deductorName: string; deductorTAN: string; grossAmount: Money; taxDeducted: Money; deductionDate: string; uniqueTransactionNo: string; financialYear: string; verified26AS: boolean; claimedInReturn: boolean; }
export interface TcsCredit extends Identified { collectorName: string; collectorTAN: string; grossAmount: Money; taxCollected: Money; claimedInReturn: boolean; }
export interface TaxChallan extends Identified { kind: 'ADVANCE_TAX' | 'SELF_ASSESSMENT'; bsrCode: string; depositDate: string; challanSerialNo: string; amount: Money; cin: string; }
export interface BankAccount extends Identified { bankName: string; accountNumber: string; ifscCode: string; accountType: 'SB' | 'CA' | 'CC' | 'OD' | 'NRO' | 'OTH'; useForRefund: boolean; }
export interface FilingStatus { filingSection: '139(1)' | '139(4)' | '139(5)' | '119(2)(b)'; returnType: 'ORIGINAL' | 'REVISED'; originalAcknowledgementNumber: string; originalFilingDate: string | null; noticeNumber: string; }
export interface ExemptIncomeEntry extends Identified { kind: 'AGRICULTURE' | 'PPF_INTEREST' | 'SUKANYA_INTEREST' | 'OTHER_INTEREST' | 'LTCG_10_33' | 'LTCG_10_38' | 'GRATUITY' | 'LEAVE_ENCASHMENT' | 'VRS' | 'COMMUTED_PENSION' | 'FIRM_PROFIT_SHARE' | 'OTHER'; description: string; grossAmount: Money; expenses: Money; }
export interface ImportProvenance { source: 'MANUAL' | 'FORM16' | 'AIS' | 'TIS' | '26AS' | 'ITD_PREFILL' | 'LEGACY'; importedAt: string | null; reference: string; }
export interface Verification { capacity: 'SELF' | 'REPRESENTATIVE'; place: string; date: string | null; declarationAccepted: boolean; }
export interface LegacyCompatibilityEnvelope { source: 'legacy-flat-v1'; unknownFields: Readonly<Record<string, unknown>>; }
export interface ReturnDraft {
  schemaVersion: 1; assessmentYear: string; form: ItrForm; regime: TaxRegime;
  personal: { name: string; pan: string; email: string; mobile: string; dateOfBirth: string | null };
  filing: FilingStatus; employers: Employer[]; houseProperties: HouseProperty[]; businesses: PresumptiveBusiness[];
  otherSources: { interest: InterestIncome[]; dividends: DividendIncome[]; familyPension: FamilyPension; winnings: WinningIncome[]; gifts: GiftIncome[] };
  exemptIncome: ExemptIncomeEntry[];
  deductions: { section80C: Investment80C[]; section80D: Section80D; section80G: Donation80G[]; loans: LoanDeductions };
  taxes: { tds: TdsCredit[]; tcs: TcsCredit[]; challans: TaxChallan[] }; bankAccounts: BankAccount[];
  verification: Verification; provenance: ImportProvenance[]; compatibility?: LegacyCompatibilityEnvelope;
}
