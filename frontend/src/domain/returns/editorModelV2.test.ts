import { describe, expect, it } from 'vitest';
import { createEmptyReturnDraft } from './factory';
import {
  replaceDraft,
  updateCapitalGainsSchedule,
  updateAmt,
  updateAssetLiability,
  updateBroughtForwardLossEntries,
  updateCarriedForwardLossEntries,
  updateClubbedIncome,
  updateEsopDeferrals,
  updateForeignAssets,
  updateForeignSourceIncome,
  updateForeignTaxRelief,
  updatePassThroughIncomeEntries,
  updatePortugueseCivilCode,
  updateScheduleSIEntries,
  updateDeductionLoansFromManager,
  updateDraft,
  updateEmployers,
  updateSchedule80GGA,
  updateSchedule80GGC,
  updateSection80C,
  updateTaxReturnPreparer,
  updateTaxCreditsFromManager,
  type ReturnEditorModelV2,
} from './editorModelV2';
import type { CapitalGainsSchedule, Employer, Investment80C } from './types';

function employer(): Employer {
  return {
    id: 'employer-1', customEmployerName: '', employerName: 'Acme', employerTAN: '', natureOfEmployment: 'OTH',
    employerAddress: '', employerCity: '', employerStateCode: '', employerPinCode: '', employerZipCode: '',
    salaryNatureRows: [], perquisiteNatureRows: [], section10ExemptionRows: [],
    basic: 100, da: 0, commission: 0, hra: 0, bonus: 0, allowances: 0, lta: 0,
    otherAllowance: 0, arrearSalary: 0, perquisites: 0, profitsInLieu: 0, rentPaid: 0,
    city: '', isMetroCity: false, isGovernmentEmployee: false, isDisabledEmployee: false,
    commutedPension: 0, gratuity: 0, leaveEncashment: 0, averageMonthlySalary: 0, yearsOfService: 0,
    unavailedLeaveDays: 0, actualLtaFare: 0, isDomesticTravel: true, journeysInBlock: 0, ltaExempt: 0,
    numberOfChildren: 0, gratuityAlsoReceived: false, transportAllowance: 0, childrenEducationAllowance: 0,
    hostelExpenditureAllowance: 0, uniformAllowance: 0, entertainmentAllowance: 0, professionalTax: 0,
    vrsCompensation: 0, retrenchmentCompensation: 0, otherExempt: 0, tdsDeducted: 0, employerNPS: 0,
  };
}

function investment(): Investment80C {
  return { id: '80c-1', investmentType: 'PPF', identificationNo: '', accountOrPolicyNo: 'A', amount: 100, dateOfInvestment: '2026-01-01', institutionName: 'Bank', institutionPAN: 'ABCDE1234F' };
}

describe('ReturnEditorModelV2', () => {
  it('performs detached immutable updates without mutating model or inputs', () => {
    const original: ReturnEditorModelV2 = { draft: createEmptyReturnDraft('2026-27') };
    const entries = [employer()];
    const updated = updateEmployers(original, entries);
    entries[0].employerName = 'Mutated input';
    updated.draft.employers[0].employerName = 'Mutated result';

    expect(original.draft.employers).toEqual([]);
    expect(updated).not.toBe(original);
    expect(updated.draft).not.toBe(original.draft);
    expect(entries[0].employerName).toBe('Mutated input');
  });

  it('supports idempotent draft transformations', () => {
    const model = replaceDraft(createEmptyReturnDraft('2026-27'));
    const setOldRegime = (draft: ReturnEditorModelV2['draft']): ReturnEditorModelV2['draft'] => ({ ...draft, regime: 'old' });
    const once = updateDraft(model, setOldRegime);
    const twice = updateDraft(once, setOldRegime);

    expect(twice).toEqual(once);
    expect(twice).not.toBe(once);
    expect(twice.draft).not.toBe(once.draft);
  });

  it('never produces an extras or compatibility envelope', () => {
    const draft = createEmptyReturnDraft('2026-27');
    draft.compatibility = { source: 'legacy-flat-v1', unknownFields: { future: true } };
    const model = replaceDraft(draft);
    const updated = updateSection80C(model, [investment()]);

    expect(Object.keys(updated)).toEqual(['draft']);
    expect(updated).not.toHaveProperty('extras');
    expect(updated.draft).not.toHaveProperty('compatibility');
    expect(updated.draft.deductions.section80C).toHaveLength(1);
  });

  it('seeds the capital gains schedule as the typed EMPTY_CAPITAL_GAINS_SCHEDULE', () => {
    const draft = createEmptyReturnDraft('2026-27');
    const schedule = draft.capitalGainsSchedule as CapitalGainsSchedule;
    expect(schedule.simplified112A).toEqual({ totalSaleConsideration: 0, totalCostAcquisition: 0 });
    expect(schedule.schedule112A).toEqual([]);
    expect(schedule.schedule115AD).toEqual([]);
    expect(schedule.vda).toEqual([]);
    expect(schedule.stImmovable).toEqual([]);
    expect(schedule.ltImmovable).toEqual([]);
    expect(schedule.stUnutilizedFlag).toBe('N');
    expect(schedule.ltUnutilizedFlag).toBe('N');
    expect(schedule.aggregates).toEqual({
      stPassThrough: 0, stPassThrough20: 0, stPassThrough30: 0, stPassThroughApplicable: 0,
      ltPassThrough: 0, ltPassThrough112A: 0, ltPassThrough125: 0,
    });
  });

  it('replaces the capital gains schedule immutably via updateCapitalGainsSchedule', () => {
    const model = replaceDraft(createEmptyReturnDraft('2026-27'));
    const newSchedule: CapitalGainsSchedule = {
      ...model.draft.capitalGainsSchedule,
      simplified112A: { totalSaleConsideration: 250000, totalCostAcquisition: 180000 },
      schedule112A: [{
        id: 'scrip-1', shareOnOrBefore: 'AE', isin: 'INE123456789', name: 'Reliance',
        quantity: 100, salePricePerUnit: 2500, totalSaleValue: 250000,
        costWithoutIndexation: 180000, acquisitionCost: 175000, fmvPerUnit: 2400,
        totalFmv: 240000, transferExpenses: 5000,
      }],
    };
    const updated = updateCapitalGainsSchedule(model, newSchedule);

    // Immutable: original unchanged
    expect(model.draft.capitalGainsSchedule.simplified112A.totalSaleConsideration).toBe(0);
    expect(model.draft.capitalGainsSchedule.schedule112A).toEqual([]);

    // Updated: new values
    expect(updated).not.toBe(model);
    expect(updated.draft).not.toBe(model.draft);
    expect(updated.draft.capitalGainsSchedule).not.toBe(model.draft.capitalGainsSchedule);
    expect(updated.draft.capitalGainsSchedule.simplified112A.totalSaleConsideration).toBe(250000);
    expect(updated.draft.capitalGainsSchedule.schedule112A).toHaveLength(1);
    expect(updated.draft.capitalGainsSchedule.schedule112A[0].isin).toBe('INE123456789');

    // Detached: mutating the input after the call does not affect the model
    newSchedule.schedule112A[0].isin = 'MUTATED';
    expect(updated.draft.capitalGainsSchedule.schedule112A[0].isin).toBe('INE123456789');
  });

  it('updates all ITR-2 additive schedules immutably', () => {
    const model = replaceDraft(createEmptyReturnDraft('2026-27', 'ITR-2', 'new'));
    const broughtForwardLossEntries = [{ id: 'bf-1', assessmentYear: '2025-26', head: 'HP' as const, subCategory: 'SELF', originalLoss: 1000, broughtForward: 500 }];
    const carriedForwardLossEntries = [{ id: 'cf-1', assessmentYearOfLoss: '2024-25', head: 'LTCG' as const, originalLoss: 2000, lossRemaining: 1500 }];
    const scheduleSIEntries = [{ id: 'si-1', section: '111' as const, description: 'Gain', grossIncome: 1000, deductions: 0, taxRatePct: 10 }];
    const foreignSourceIncome = [{ id: 'fsi-1', countryCode: 'US', taxIdentificationNo: 'TIN', salaryIncome: 100, hpIncome: 0, cgIncome: 0, osIncome: 0, taxPaidOutsideIndia: 10, taxPayableInIndia: 12, reliefSection: '90' as const }];
    const foreignTaxRelief = [{ id: 'tr-1', countryCode: 'US', taxIdentificationNo: 'TIN', incomeIncludedInThisReturn: 100, taxPaidOutsideIndia: 10, indianTaxPayable: 12, reliefClaimed: 10, reliefSection: '90' as const, form67Filed: true }];
    const foreignAssets = [{ id: 'fa-1', assetType: 'BANK_ACCOUNT' as const, countryCode: 'US', institutionOrEntityName: 'Bank', address: 'A', accountOrAssetIdentifier: '1', ownershipStatus: 'OWNER', openingOrAcquisitionDate: '2025-04-01', peakValue: 10, closingValue: 8, grossIncome: 0, incomeOffered: 0 }];
    const clubbedIncome = [{ id: 'spi-1', specifiedPersonName: 'Spouse', pan: 'ABCDE1234F', relationship: 'SPOUSE', amountIncluded: 100, headOfIncome: 'OS' as const }];
    const passThroughIncomeEntries = [{ id: 'pti-1', entityName: 'Trust', entityPAN: 'ABCDE1234F', incomeHead: 'OS' as const, section: '115UA', incomeAmount: 100, tdsCredit: 5 }];
    const amt = { deduction10AA: 1, deduction80IAto80RRBExcept80P: 2, deduction35ADNetDepreciation: 3, creditsBroughtForward: [{ id: 'amt-1', assessmentYear: '2025-26', creditBroughtForward: 4 }] };
    const assetLiability = { immovableProperty: 1, cashInHand: 2, bankDeposits: 3, sharesAndSecurities: 4, insurancePolicies: 5, loansAndAdvances: 6, jewellery: 7, art: 8, vehiclesBoatsAircraft: 9, relatedLiabilities: 10 };
    const portugueseCivilCode = { spouseName: 'Spouse', spousePAN: 'ABCDE1234F', spouseAadhaar: '', hpAmountApportioned: 1, cgAmountApportioned: 2, osAmountApportioned: 3, tdsApportioned: 4 };
    const esopDeferrals = [{ id: 'esop-1', employerPAN: 'ABCDE1234F', dpiitRegistrationNumber: 'DPIIT-1', assessmentYear: '2025-26', taxDeferredBroughtForward: 10, taxPayableCurrentYear: 5, balanceTaxCarriedForward: 5 }];

    const updated = updateEsopDeferrals(
      updatePortugueseCivilCode(
        updateAssetLiability(
          updateAmt(
            updatePassThroughIncomeEntries(
              updateClubbedIncome(
                updateForeignAssets(
                  updateForeignTaxRelief(
                    updateForeignSourceIncome(
                      updateScheduleSIEntries(
                        updateCarriedForwardLossEntries(
                          updateBroughtForwardLossEntries(model, broughtForwardLossEntries),
                          carriedForwardLossEntries,
                        ),
                        scheduleSIEntries,
                      ),
                      foreignSourceIncome,
                    ),
                    foreignTaxRelief,
                  ),
                  foreignAssets,
                ),
                clubbedIncome,
              ),
              passThroughIncomeEntries,
            ),
            amt,
          ),
          assetLiability,
        ),
        portugueseCivilCode,
      ),
      esopDeferrals,
    );

    expect(updated.draft.broughtForwardLossEntries).toEqual(broughtForwardLossEntries);
    expect(updated.draft.carriedForwardLossEntries).toEqual(carriedForwardLossEntries);
    expect(updated.draft.scheduleSIEntries).toEqual(scheduleSIEntries);
    expect(updated.draft.foreignSourceIncome).toEqual(foreignSourceIncome);
    expect(updated.draft.foreignTaxRelief).toEqual(foreignTaxRelief);
    expect(updated.draft.foreignAssets).toEqual(foreignAssets);
    expect(updated.draft.clubbedIncome).toEqual(clubbedIncome);
    expect(updated.draft.passThroughIncomeEntries).toEqual(passThroughIncomeEntries);
    expect(updated.draft.amt).toEqual(amt);
    expect(updated.draft.assetLiability).toEqual(assetLiability);
    expect(updated.draft.portugueseCivilCode).toEqual(portugueseCivilCode);
    expect(updated.draft.esopDeferrals).toEqual(esopDeferrals);
    expect(model.draft.broughtForwardLossEntries).toEqual([]);
    expect(model.draft.amt).toBeNull();

    broughtForwardLossEntries[0].broughtForward = 999;
    amt.creditsBroughtForward[0].creditBroughtForward = 999;
    expect(updated.draft.broughtForwardLossEntries[0].broughtForward).toBe(500);
    expect(updated.draft.amt?.creditsBroughtForward[0].creditBroughtForward).toBe(4);
  });

  it('synchronizes loan detail interest into Chapter VI-A scalar claims', () => {
    const model = replaceDraft(createEmptyReturnDraft('2026-27'));
    const updated = updateDeductionLoansFromManager(model, {
      section80E: { loans: [{ id: 'e', loanTakenFrom: 'B', bankOrInstnName: 'Bank', lenderPAN: '', loanAccNo: 'E-1', dateOfLoan: '2025-01-01', totalLoanAmt: 100000, loanOutstandingAmt: 90000, interestAmount: 5000 }] },
      section80EE: { loans: [{ id: 'ee', loanTakenFrom: 'B', bankOrInstnName: 'Bank', lenderPAN: '', loanAccNo: 'EE-1', dateOfLoan: '2025-01-01', totalLoanAmt: 200000, loanOutstandingAmt: 180000, interestAmount: 6000 }] },
      section80EEA: { loans: [{ id: 'eea', loanTakenFrom: 'B', bankOrInstnName: 'Bank', lenderPAN: '', loanAccNo: 'EEA-1', dateOfLoan: '2025-01-01', totalLoanAmt: 300000, loanOutstandingAmt: 250000, interestAmount: 7000 }], stampDutyValue: 4000000 },
      section80EEB: { loans: [{ id: 'eeb', loanTakenFrom: 'I', bankOrInstnName: 'Lender', lenderPAN: '', loanAccNo: 'EEB-1', dateOfLoan: '2025-01-01', totalLoanAmt: 400000, loanOutstandingAmt: 300000, interestAmount: 8000 }] },
    });

    expect(updated.draft.deductions.chapterVIA).toMatchObject({
      section80E: 5000,
      section80EE: 6000,
      section80EEA: 7000,
      section80EEAStampDutyValue: 4000000,
      section80EEB: 8000,
    });
  });

  it('synchronizes non-cash 80GGA and 80GGC detail totals', () => {
    const model = replaceDraft(createEmptyReturnDraft('2026-27'));
    const withGga = updateSchedule80GGA(model, [{
      id: 'gga', relevantClause: '80GGA2aa', doneeName: 'Research Trust',
      doneePAN: 'ABCDE1234F', addressLine: '1 Road', city: 'Delhi',
      stateCode: '07', pinCode: '110001', cashAmount: 100, otherModeAmount: 3000,
    }]);
    const withGgc = updateSchedule80GGC(withGga, [{
      id: 'ggc', cashAmount: 200, otherModeAmount: 4000,
      contributionDate: '2025-06-01', transactionRef: 'UTR-1',
      ifscCode: 'SBIN0001234', politicalPartyName: 'Party',
      politicalPartyPAN: 'ABCDE1234F',
    }]);

    expect(withGgc.draft.deductions.chapterVIA.section80GGA).toBe(3000);
    expect(withGgc.draft.deductions.chapterVIA.section80GGC).toBe(4000);
  });

  it('persists complete Tax Return Preparer details immutably', () => {
    const model = replaceDraft(createEmptyReturnDraft('2026-27'));
    const updated = updateTaxReturnPreparer(model, {
      used: true,
      identificationNumber: 'T123456789',
      name: 'Registered Tax Preparer',
      reimbursementFromGovernment: 750,
    });

    expect(updated.draft.taxReturnPreparer).toEqual({
      used: true,
      identificationNumber: 'T123456789',
      name: 'Registered Tax Preparer',
      reimbursementFromGovernment: 750,
    });
    expect(model.draft.taxReturnPreparer.used).toBe(false);
  });

  it('partitions combined editor rows into canonical TDS and TCS schedules', () => {
    const model = replaceDraft(createEmptyReturnDraft('2026-27'));
    const updated = updateTaxCreditsFromManager(model, [
      {
        id: 'tds3', section: '194IB', deductorName: 'Tenant',
        deductorTAN: '', incomeAmount: 100000, tdsDeducted: 5000,
        nameOfTenant: 'Tenant', panOfTenant: 'ABCDE1234F',
        deductedYr: 2024, headOfIncome: 'HP', broughtFwdTDSAmt: 100,
        amtCarriedFwd: 200, tdsClaimed: 4700,
      },
      {
        id: 'tcs', section: '206C', deductorName: 'Collector',
        deductorTAN: 'DELA12345B', incomeAmount: 200000, tdsDeducted: 2000,
        deductedYr: 2024, tcsCreditOwner: '1', tcsAmtCollOwnHand: 2000,
        tcsClaimedAmtCollOwnHand: 1800,
      },
    ]);

    expect(updated.draft.taxes.tds).toHaveLength(1);
    expect(updated.draft.taxes.tds[0]).toMatchObject({
      id: 'tds3', schedule: 'TDS3', deductedYr: 2024, headOfIncome: 'HP',
      broughtFwdTDSAmt: 100, amtCarriedFwd: 200, tdsClaimed: 4700,
    });
    expect(updated.draft.taxes.tcs).toHaveLength(1);
    expect(updated.draft.taxes.tcs[0]).toMatchObject({
      id: 'tcs', collectorName: 'Collector', collectorTAN: 'DELA12345B',
      grossAmount: 200000, taxCollected: 2000, deductedYr: 2024,
      tcsAmtCollOwnHand: 2000, tcsClaimedAmtCollOwnHand: 1800,
    });
  });
});
