import type { Category80D, FinancialParticulars, ReturnDraft } from './types';

/** Creates an empty 80D category with independent policy storage. */
export function createEmpty80DCategory(): Category80D { return { policies: [], preventiveCheckup: 0, medicalExpense: 0 }; }
/** Creates empty Schedule BP financial particulars. */
export function createEmptyFinancialParticulars(): FinancialParticulars { return { cashBalance: 0, bankBalance: 0, inventory: 0, sundryDebtors: 0, sundryCreditors: 0, otherAssets: 0, totalAssets: 0, securedLoans: 0, unsecuredLoans: 0, advances: 0, otherLiabilities: 0, totalLiabilities: 0, grossProfit: 0, expenses: 0, netProfit: 0 }; }
/** Creates a fresh normalized return draft with no shared mutable state. */
export function createEmptyReturnDraft(assessmentYear = '', form: ReturnDraft['form'] = 'ITR-1', regime: ReturnDraft['regime'] = 'new'): ReturnDraft {
  return {
    schemaVersion: 1, assessmentYear, form, regime,
    personal: { name: '', pan: '', email: '', mobile: '', dateOfBirth: null },
    filing: { filingSection: '139(1)', returnType: 'ORIGINAL', originalAcknowledgementNumber: '', originalFilingDate: null, noticeNumber: '' },
    employers: [], houseProperties: [], housePropertyPassThroughIncome: 0, businesses: [], capitalGainsSchedule: {},
    otherSources: { interest: [], dividends: [], familyPension: { grossAmount: 0, payerName: '', relationToPensioner: '' }, winnings: [], gifts: [] },
    exemptIncome: [],
    deductions: { section80C: [], section80D: { selfSeniorCitizen: 'N', parentsSeniorCitizen: 'N', selfFamily: createEmpty80DCategory(), selfFamilySenior: createEmpty80DCategory(), parents: createEmpty80DCategory(), parentsSenior: createEmpty80DCategory() }, section80G: [], loans: { loans: [], section80EEAStampDutyValue: 0 } },
    taxes: { tds: [], tcs: [], challans: [] }, bankAccounts: [],
    verification: { capacity: 'SELF', place: '', date: null, declarationAccepted: false }, provenance: [],
  };
}
