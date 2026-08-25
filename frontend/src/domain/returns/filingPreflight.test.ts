import { describe, expect, it } from 'vitest';
import { createEmptyReturnDraft } from './factory';
import { validateCbdtFrontendFields } from './filingPreflight';
import { EMPTY_TDS_CREDIT, type ReturnDraft } from './types';

const createPreflightDraft = (
  form: ReturnDraft['form'] = 'ITR-1',
  regime: ReturnDraft['regime'] = 'new',
): ReturnDraft => {
  const draft = createEmptyReturnDraft('2026-27', form, regime);
  draft.bankAccounts = [{
    id: 'bank-1',
    bankName: 'State Bank of India',
    accountNumber: '1234567890',
    ifscCode: 'SBIN0001234',
    accountType: 'SB',
    useForRefund: true,
  }];
  // Required by the CBDT verification declaration, so every draft that is
  // meant to reach filing has to carry them.
  draft.personal.fatherName = 'Mohan Sharma';
  draft.personal.surnameOrOrgName = 'Sharma';
  draft.personal.pan = 'ABCDE1234F';
  draft.verification.place = 'Delhi';
  // A return filed under 139(1) declares a filing date on or before the due
  // date; without one the fixture is judged against the day the suite runs.
  draft.verification.date = '2026-07-31';
  draft.verification.declarationAccepted = true;
  return draft;
};

describe('validateCbdtFrontendFields', () => {
  it('requires personal employer category independently of employer rows', () => {
    const draft = createPreflightDraft();
    draft.personal.stateCode = '09';
    draft.personal.pinCode = '110001';

    expect(validateCbdtFrontendFields(draft)).toContain(
      'Personal information: select a valid employer category.',
    );

    draft.personal.employerCategory = 'NA';
    expect(validateCbdtFrontendFields(draft)).toEqual([]);
  });

  it('validates each employer enum, state, and optional TAN', () => {
    const draft = createPreflightDraft();
    draft.personal.employerCategory = 'OTH';
    draft.personal.stateCode = '09';
    draft.personal.pinCode = '110001';
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
    const draft = createPreflightDraft();
    draft.personal.employerCategory = 'NA';
    draft.personal.stateCode = '09';
    draft.personal.pinCode = '110001';
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
    const draft = createPreflightDraft();
    draft.personal.employerCategory = 'NA';
    draft.personal.stateCode = '09';
    draft.personal.pinCode = '110001';
    draft.houseProperties = [{
      id: 'hp-1',
      propertySequenceNo: 1,
      propertyType: 'SELF_OCCUPIED',
      state: '',
      countryCode: '91',
      pinCode: '',
    } as unknown as ReturnDraft['houseProperties'][number]];
    draft.deductions.section80G = [{
      id: '80g-1',
      stateCode: '',
      pinCode: '',
    } as ReturnDraft['deductions']['section80G'][number]];

    expect(validateCbdtFrontendFields(draft)).toEqual([
      'House property 1: select a valid CBDT state code.',
      'House property 1: enter a valid 6-digit Indian PIN code.',
      '80G donation 1: select a valid Indian donee state code.',
      '80G donation 1: enter a valid 6-digit Indian PIN code.',
    ]);
  });

  it('validates personal and conditional-row PIN codes', () => {
    const draft = createPreflightDraft();
    draft.personal.employerCategory = 'NA';
    draft.personal.stateCode = '09';
    draft.personal.pinCode = '012345';
    draft.deductions.schedule80GGA = [{
      id: '80gga-1', relevantClause: '80GGA2a', doneeName: 'Research Fund',
      doneePAN: 'ABCDE1234F', addressLine: '1 Main Road', city: 'Delhi',
      stateCode: '09', pinCode: '12345', cashAmount: 0, otherModeAmount: 1000,
    }];

    expect(validateCbdtFrontendFields(draft)).toEqual([
      'Personal information: enter a valid 6-digit Indian PIN code.',
      '80GGA donation 1: enter a valid 6-digit Indian PIN code.',
    ]);
  });

  it('validates property ownership shares and conditional owner details', () => {
    const draft = createPreflightDraft();
    draft.personal.employerCategory = 'NA';
    draft.personal.stateCode = '09';
    draft.personal.pinCode = '110001';
    draft.houseProperties = [{
      id: 'hp-1', propertySequenceNo: 1, propertyType: 'LET_OUT',
      state: '09', countryCode: '91', pinCode: '110001',
      propertyOwnerType: 'OT', propertyOwnerOther: '', isCoOwned: true,
      ownershipShare: 100, coOwners: [],
      tenantDetails: [], unrealizedRent: 0, annualLettingValue: 100000,
    } as unknown as ReturnDraft['houseProperties'][number]];

    const errors = validateCbdtFrontendFields(draft);
    expect(errors).toContain('House property 1: describe the other property owner type.');
    expect(errors).toContain('House property 1: add at least one co-owner.');
    expect(errors).toContain('House property 1: your ownership share must be above 0% and below 100%.');
  });

  it('validates property identity formats, duplicates, and share cross-foot', () => {
    const draft = createPreflightDraft();
    draft.personal.employerCategory = 'NA';
    draft.personal.stateCode = '09';
    draft.personal.pinCode = '110001';
    draft.personal.pan = 'ABCDE1234F';
    draft.personal.aadhaar = '123456789012';
    draft.houseProperties = [{
      id: 'hp-1', propertySequenceNo: 1, propertyType: 'LET_OUT',
      state: '09', countryCode: '91', pinCode: '110001',
      propertyOwnerType: 'SE', propertyOwnerOther: '', isCoOwned: true,
      ownershipShare: 60,
      coOwners: [
        { coOwnerSNo: 1, name: 'One', pan: 'ABCDE1234F', aadhaar: '123456789012', share: 20 },
        { coOwnerSNo: 2, name: 'Two', pan: 'ABCDE1234F', aadhaar: '123456789012', share: 10 },
      ],
      tenantDetails: [
        { tenantSNo: 1, name: 'Tenant', pan: 'bad', aadhaar: '123', panOrTan: 'bad' },
      ],
      unrealizedRent: 120000, annualLettingValue: 100000,
    } as unknown as ReturnDraft['houseProperties'][number]];

    const errors = validateCbdtFrontendFields(draft);
    expect(errors).toContain('House property 1: your share and all co-owner shares must total 100%.');
    expect(errors).toContain('House property 1, co-owner 1: PAN cannot match the assessee PAN.');
    expect(errors).toContain('House property 1, co-owner 2: PAN cannot match the assessee PAN.');
    expect(errors).toContain('House property 1, co-owner 1: Aadhaar cannot match the assessee Aadhaar.');
    expect(errors).toContain('House property 1, tenant 1: enter a valid PAN.');
    expect(errors).toContain('House property 1, tenant 1: enter a valid 12-digit Aadhaar number.');
    expect(errors).toContain('House property 1, tenant 1: enter a valid PAN or TAN.');
    expect(errors).toContain('House property 1: rent not realized cannot exceed annual lettable value.');
  });

  it('uses legacy annual rent only when canonical annual lettable value is absent', () => {
    const draft = createPreflightDraft('ITR-1', 'old');
    draft.personal.stateCode = '09';
    draft.personal.pinCode = '110001';
    draft.houseProperties = [{
      id: 'hp-1', propertySequenceNo: 1, propertyType: 'LET_OUT',
      state: '09', countryCode: '91', pinCode: '110001',
      propertyOwnerType: 'SE', isCoOwned: false, ownershipShare: 100,
      coOwners: [], tenantDetails: [], unrealizedRent: 120000,
      annualLettingValue: 0, annualRent: 100000,
    } as unknown as ReturnDraft['houseProperties'][number]];

    expect(validateCbdtFrontendFields(draft)).toContain(
      'House property 1: rent not realized cannot exceed annual lettable value.',
    );
  });

  it('rejects mixed metro and non-metro HRA evidence', () => {
    const draft = createPreflightDraft('ITR-1', 'old');
    draft.personal.employerCategory = 'OTH';
    draft.personal.stateCode = '09';
    draft.personal.pinCode = '110001';
    const base: Omit<
      ReturnDraft['employers'][number],
      'id' | 'employerName' | 'isMetroCity'
    > = {
      customEmployerName: '', employerTAN: '', natureOfEmployment: 'OTH',
      employerAddress: '', employerCity: '', employerStateCode: '',
      employerPinCode: '', employerZipCode: '', salaryNatureRows: [],
      perquisiteNatureRows: [], section10ExemptionRows: [], basic: 500000,
      da: 0, commission: 0, hra: 100000, bonus: 0, allowances: 0, lta: 0,
      otherAllowance: 0, arrearSalary: 0, perquisites: 0, profitsInLieu: 0,
      rentPaid: 150000, city: '', isGovernmentEmployee: false,
      isDisabledEmployee: false, commutedPension: 0, gratuity: 0,
      leaveEncashment: 0, averageMonthlySalary: 0, yearsOfService: 0,
      unavailedLeaveDays: 0, actualLtaFare: 0, isDomesticTravel: true,
      journeysInBlock: 0, ltaExempt: 0, numberOfChildren: 0,
      gratuityAlsoReceived: false, transportAllowance: 0,
      childrenEducationAllowance: 0, hostelExpenditureAllowance: 0,
      uniformAllowance: 0, entertainmentAllowance: 0, professionalTax: 0,
      vrsCompensation: 0, retrenchmentCompensation: 0, otherExempt: 0,
      tdsDeducted: 0, employerNPS: 0,
    };
    draft.employers = [
      { ...base, id: 'e1', employerName: 'Metro Employer', isMetroCity: true },
      { ...base, id: 'e2', employerName: 'Other Employer', isMetroCity: false },
    ];

    expect(validateCbdtFrontendFields(draft)).toContain(
      'HRA: CBDT Schedule 10(13A) cannot combine metro and non-metro employer evidence.',
    );
  });

  it('requires one complete bank account selected for refund', () => {
    const draft = createPreflightDraft();
    draft.personal.employerCategory = 'NA';
    draft.personal.stateCode = '09';
    draft.personal.pinCode = '110001';

    draft.bankAccounts = [];
    expect(validateCbdtFrontendFields(draft)).toEqual([
      'Bank accounts: add at least one account for the mandatory refund section.',
    ]);

    draft.bankAccounts = [{
      id: 'bank-1', bankName: '', accountNumber: 'ABC', ifscCode: 'BAD',
      accountType: 'SB', useForRefund: false,
    }];
    expect(validateCbdtFrontendFields(draft)).toEqual([
      'Bank accounts: select exactly one account to use for refund.',
      'Bank account 1: enter the bank name.',
      'Bank account 1: enter a valid account number of up to 20 characters ending in a digit.',
      'Bank account 1: enter a valid IFSC (4 letters, 0, then 6 alphanumeric characters).',
    ]);
  });

  it('requires verification consent and a form-compatible capacity', () => {
    const draft = createPreflightDraft();
    draft.personal.employerCategory = 'NA';
    draft.personal.stateCode = '09';
    draft.personal.pinCode = '110001';
    draft.verification.place = '';
    draft.verification.declarationAccepted = false;
    draft.verification.capacity = 'KARTA';

    expect(validateCbdtFrontendFields(draft)).toEqual([
      'Verification: enter the place of verification.',
      'Verification: accept the declaration before validation or filing.',
      'Verification: ITR-1 capacity must be Self or Representative assessee.',
    ]);

    draft.form = 'ITR-4';
    draft.verification.place = 'Delhi';
    draft.verification.declarationAccepted = true;
    expect(validateCbdtFrontendFields(draft)).toEqual([]);
  });

  it('rejects multiple refund selections and duplicate bank accounts', () => {
    const draft = createPreflightDraft();
    draft.personal.employerCategory = 'NA';
    draft.personal.stateCode = '09';
    draft.personal.pinCode = '110001';
    draft.bankAccounts.push({
      ...draft.bankAccounts[0],
      id: 'bank-2',
      bankName: 'Duplicate Bank',
    });

    expect(validateCbdtFrontendFields(draft)).toEqual([
      'Bank accounts: select exactly one account to use for refund.',
      'Bank account 2: duplicates another bank account.',
    ]);
  });
});
