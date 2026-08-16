import type { Employer } from '../domain/returns/types';
import type { ReturnDraftPatch } from '../domain/returns/draftPatch';
import type { AisImportData } from './mapAisToDraftPatch';
import { mapAisToDraftPatch } from './mapAisToDraftPatch';

export interface TisImportData extends AisImportData { salaryAmount?: number; dividendIncome?: number; interestFromDeposit?: number; }

function salaryTotalEmployer(amount: number): Employer {
  return {
    id: 'tis-employer-total', customEmployerName: 'TIS accepted salary total',
    employerName: 'TIS accepted salary total', employerTAN: '', natureOfEmployment: 'OTH',
    employerAddress: '', employerCity: '', employerStateCode: '', employerPinCode: '', employerZipCode: '',
    salaryNatureRows: [], perquisiteNatureRows: [], section10ExemptionRows: [],
    basic: amount, da: 0, commission: 0, hra: 0, bonus: 0, allowances: 0, lta: 0,
    otherAllowance: 0, arrearSalary: 0, perquisites: 0, profitsInLieu: 0, rentPaid: 0,
    city: '', isMetroCity: false, isGovernmentEmployee: false, isDisabledEmployee: false,
    commutedPension: 0, gratuity: 0, leaveEncashment: 0, averageMonthlySalary: 0,
    yearsOfService: 0, unavailedLeaveDays: 0, actualLtaFare: 0,
    isDomesticTravel: true, journeysInBlock: 0, ltaExempt: 0, numberOfChildren: 0,
    gratuityAlsoReceived: false, transportAllowance: 0, childrenEducationAllowance: 0,
    hostelExpenditureAllowance: 0, uniformAllowance: 0, entertainmentAllowance: 0,
    professionalTax: 0, vrsCompensation: 0, retrenchmentCompensation: 0,
    otherExempt: 0, tdsDeducted: 0, employerNPS: 0,
  };
}

/** Maps raw TIS import data into canonical draft fields without legacy fields. */
export function mapTisToDraftPatch(data: TisImportData | null | undefined): ReturnDraftPatch {
  if (!data) return {};
  const patch = mapAisToDraftPatch(data);
  if (data.salaryAmount) {
    // When AIS provided employer rows, augment the first with the accepted
    // total; otherwise emit a single "TIS accepted" salary stub so the
    // amount is not lost. An empty array would be treated as "preserve
    // existing" by mergeDraft, silently discarding the salary total.
    if (patch.employers && patch.employers.length > 0) {
      patch.employers = patch.employers.map((emp, index) =>
        index === 0 ? { ...emp, basic: data.salaryAmount } : emp,
      );
    } else {
      patch.employers = [salaryTotalEmployer(data.salaryAmount)];
    }
  }
  if (data.interestFromDeposit && (!patch.otherSources?.interest || patch.otherSources.interest.length === 0)) {
    patch.otherSources = { ...patch.otherSources, interest: [{ id: 'tis-interest-deposit', kind: 'TERM_DEPOSIT', grossAmount: data.interestFromDeposit, tdsDeducted: 0, bankName: 'TIS accepted total', accountType: 'FD', accountNumber: '', ifscCode: '', postOfficeName: '', accountNumberPO: '', nscCertificateNumber: '', yearOfPurchase: 0, scssAccountNumber: '', dateOfOpening: '', deductorName: '', deductorTAN: '', remarks: '' }] };
  }
  if (data.dividendIncome && (!patch.otherSources?.dividends || patch.otherSources.dividends.length === 0)) {
    patch.otherSources = { ...patch.otherSources, dividends: [{ id: 'tis-dividend-total', section: '194', grossAmount: data.dividendIncome, tdsDeducted: 0, companyName: 'TIS accepted total', companyPAN: '', deductorTAN: '', isin: '', category: 'EQUITY', q1: 0, q2: 0, q3: 0, q4: 0, q5: 0 }] };
  }
  patch.provenance = [{ source: 'TIS', importedAt: new Date().toISOString(), reference: 'direct-import' }];
  return patch;
}
