import { describe, expect, it } from 'vitest';
import { createEmptyReturnDraft } from './factory';
import { validateCbdtFrontendFields } from './filingPreflight';
import { EMPTY_TDS_CREDIT, type ReturnDraft } from './types';

describe('validateCbdtFrontendFields', () => {
  it('requires personal employer category independently of employer rows', () => {
    const draft = createEmptyReturnDraft('2026-27');
    draft.personal.stateCode = '09';

    expect(validateCbdtFrontendFields(draft)).toContain(
      'Personal information: select a valid employer category.',
    );

    draft.personal.employerCategory = 'NA';
    expect(validateCbdtFrontendFields(draft)).toEqual([]);
  });

  it('validates each employer enum, state, and optional TAN', () => {
    const draft = createEmptyReturnDraft('2026-27');
    draft.personal.employerCategory = 'OTH';
    draft.personal.stateCode = '09';
    draft.employers = [{
      id: 'employer-1',
      customEmployerName: '',
      employerName: 'Acme',
      employerTAN: 'ABCD12345E',
      natureOfEmployment: '',
      employerAddress: '',
      employerCity: '',
      employerStateCode: '',
      employerPinCode: '',
      employerZipCode: '',
      salaryNatureRows: [],
      perquisiteNatureRows: [],
      section10ExemptionRows: [],
      basic: 0, da: 0, commission: 0, hra: 0, bonus: 0, allowances: 0, lta: 0,
      otherAllowance: 0, arrearSalary: 0, perquisites: 0, profitsInLieu: 0,
      rentPaid: 0, city: '', isMetroCity: false, isGovernmentEmployee: false,
      isDisabledEmployee: false, commutedPension: 0, gratuity: 0, leaveEncashment: 0,
      averageMonthlySalary: 0, yearsOfService: 0, unavailedLeaveDays: 0,
      actualLtaFare: 0, isDomesticTravel: true, journeysInBlock: 0, ltaExempt: 0,
      numberOfChildren: 0, gratuityAlsoReceived: false, transportAllowance: 0,
      childrenEducationAllowance: 0, hostelExpenditureAllowance: 0,
      uniformAllowance: 0, entertainmentAllowance: 0, professionalTax: 0,
      vrsCompensation: 0, retrenchmentCompensation: 0, otherExempt: 0,
      tdsDeducted: 0, employerNPS: 0,
    }];

    expect(validateCbdtFrontendFields(draft)).toEqual([
      'Acme: select a valid nature of employment.',
      'Acme: employer TAN is not a valid CBDT jurisdiction TAN.',
    ]);

    draft.employers[0].natureOfEmployment = 'OTH';
    draft.employers[0].employerStateCode = '09';
    draft.employers[0].employerTAN = 'DELA12345B';
    expect(validateCbdtFrontendFields(draft)).toEqual([]);
  });

  it('rejects invalid TDS and TCS jurisdiction TANs', () => {
    const draft = createEmptyReturnDraft('2026-27');
    draft.personal.employerCategory = 'NA';
    draft.personal.stateCode = '09';
    draft.taxes.tds = [{
      ...structuredClone(EMPTY_TDS_CREDIT),
      id: 'tds-1',
      section: '192',
      deductorName: 'Acme',
      deductorTAN: 'ABCD12345E',
    }];
    draft.taxes.tcs = [{
      id: 'tcs-1', collectorName: 'Collector', collectorTAN: 'DELA12345B',
      grossAmount: 1, taxCollected: 1, claimedInReturn: true, tcsCreditOwner: '1',
      panOfSpouseOrOthrPrsn: '', deductedYr: 2025, broughtFwdTDSAmt: 0,
      tcsAmtCollOwnHand: 1, tcsAmtCollSpouseOrOthrHand: 0,
      tcsClaimedAmtCollOwnHand: 1, tcsClaimedAmtCollSpouseOrOthrHand: 0,
      claimedPANOfSpouseOrOthrPrsn: '',
    }];

    expect(validateCbdtFrontendFields(draft)).toEqual([
      'TDS entry 1: deductor TAN is not a valid CBDT jurisdiction TAN.',
    ]);
  });

  it('validates state enums in conditional property and donation rows', () => {
    const draft = createEmptyReturnDraft('2026-27');
    draft.personal.employerCategory = 'NA';
    draft.personal.stateCode = '09';
    draft.houseProperties = [{
      id: 'hp-1',
      propertySequenceNo: 1,
      propertyType: 'SELF_OCCUPIED',
      state: '',
    } as ReturnDraft['houseProperties'][number]];
    draft.deductions.section80G = [{
      id: '80g-1',
      stateCode: '',
    } as ReturnDraft['deductions']['section80G'][number]];

    expect(validateCbdtFrontendFields(draft)).toEqual([
      'House property 1: select a valid CBDT state code.',
      '80G donation 1: select a valid Indian donee state code.',
    ]);
  });
});
