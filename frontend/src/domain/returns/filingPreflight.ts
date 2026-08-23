import {
  normalizeEmployerCategory,
  normalizeEmploymentNature,
  normalizeStateCode,
} from './cbdtEnums';
import type { ReturnDraft } from './types';
import { isValidTan } from '../../utils/taxIdentifiers';

const isValidIndianPin = (value: string): boolean => /^[1-9][0-9]{5}$/.test(value.trim());
const isValidPan = (value: string): boolean => /^[A-Z]{5}[0-9]{4}[A-Z]$/.test(value.trim().toUpperCase());
const isValidAadhaar = (value: string): boolean => /^[0-9]{12}$/.test(value.trim());
const isValidPanOrTan = (value: string): boolean =>
  isValidPan(value) || /^[A-Z]{4}[0-9]{5}[A-Z]$/.test(value.trim().toUpperCase());
const isValidIfsc = (value: string): boolean =>
  /^[A-Z]{4}0[A-Z0-9]{6}$/.test(value.trim().toUpperCase());
const isValidBankAccountNumber = (value: string): boolean => {
  const normalized = value.trim();
  return normalized.length >= 1
    && normalized.length <= 20
    && /^[A-Za-z0-9](?:[A-Za-z0-9/-]*[0-9])?$/.test(normalized)
    && /[1-9]/.test(normalized);
};
const BANK_ACCOUNT_TYPES = new Set(['SB', 'CA', 'CC', 'OD', 'NRO', 'OTH']);

/** Frontend checks for CBDT-constrained fields before validation or filing. */
export function validateCbdtFrontendFields(draft: ReturnDraft): string[] {
  const errors: string[] = [];

  if (!normalizeEmployerCategory(draft.personal.employerCategory)) {
    errors.push('Personal information: select a valid employer category.');
  }

  const expectedState = draft.personal.countryCode === '91' ? normalizeStateCode(draft.personal.stateCode) : draft.personal.stateCode === '99' ? '99' : '';
  if (!expectedState) {
    errors.push('Personal information: select a valid CBDT state code (use 99 for an address outside India).');
  }
  if (draft.personal.countryCode === '91' && !isValidIndianPin(draft.personal.pinCode)) {
    errors.push('Personal information: enter a valid 6-digit Indian PIN code.');
  }
  if (!draft.verification.place.trim()) {
    errors.push('Verification: enter the place of verification.');
  }
  if (!draft.verification.declarationAccepted) {
    errors.push('Verification: accept the declaration before validation or filing.');
  }
  if (draft.form === 'ITR-1' && !['SELF', 'REPRESENTATIVE'].includes(draft.verification.capacity)) {
    errors.push('Verification: ITR-1 capacity must be Self or Representative assessee.');
  }

  draft.employers.forEach((employer, index) => {
    const label = employer.employerName.trim() || `Employer ${index + 1}`;
    if (!normalizeEmploymentNature(employer.natureOfEmployment)) {
      errors.push(`${label}: select a valid nature of employment.`);
    }
    if (employer.employerTAN && !isValidTan(employer.employerTAN)) {
      errors.push(`${label}: employer TAN is not a valid CBDT jurisdiction TAN.`);
    }
    if (employer.employerPinCode && !isValidIndianPin(employer.employerPinCode)) {
      errors.push(`${label}: employer PIN code must be a valid 6-digit Indian PIN.`);
    }
  });
  const hraLocations = new Set(
    draft.employers
      .filter((employer) => employer.hra > 0 || employer.rentPaid > 0)
      .map((employer) => employer.isMetroCity),
  );
  if (draft.regime === 'old' && hraLocations.size > 1) {
    errors.push('HRA: CBDT Schedule 10(13A) cannot combine metro and non-metro employer evidence.');
  }

  draft.houseProperties.forEach((property, index) => {
    const label = `House property ${index + 1}`;
    const expectedState = property.countryCode === '91' ? normalizeStateCode(property.state) : property.state === '99' ? '99' : '';
    if (!expectedState) {
      errors.push(`${label}: select a valid CBDT state code.`);
    }
    if (property.countryCode === '91' && !isValidIndianPin(property.pinCode)) {
      errors.push(`${label}: enter a valid 6-digit Indian PIN code.`);
    }
    if (property.propertyOwnerType === 'OT' && !property.propertyOwnerOther.trim()) {
      errors.push(`${label}: describe the other property owner type.`);
    }

    const coOwners = property.coOwners ?? [];
    const tenants = property.tenantDetails ?? [];
    if (property.isCoOwned) {
      if (coOwners.length === 0) {
        errors.push(`${label}: add at least one co-owner.`);
      }
      if (!(property.ownershipShare > 0 && property.ownershipShare < 100)) {
        errors.push(`${label}: your ownership share must be above 0% and below 100%.`);
      }
      const totalShare = property.ownershipShare
        + coOwners.reduce((total, owner) => total + owner.share, 0);
      if (Math.abs(totalShare - 100) > 0.001) {
        errors.push(`${label}: your share and all co-owner shares must total 100%.`);
      }
    } else if (property.ownershipShare != null && property.ownershipShare !== 100) {
      errors.push(`${label}: sole ownership requires a 100% share.`);
    }

    const coOwnerPans = new Set<string>();
    const coOwnerAadhaars = new Set<string>();
    coOwners.forEach((owner, ownerIndex) => {
      const ownerLabel = `${label}, co-owner ${ownerIndex + 1}`;
      const pan = owner.pan.trim().toUpperCase();
      const aadhaar = owner.aadhaar.trim();
      if (!owner.name.trim()) {
        errors.push(`${ownerLabel}: enter the co-owner name.`);
      }
      if (!(owner.share > 0 && owner.share < 100)) {
        errors.push(`${ownerLabel}: share must be above 0% and below 100%.`);
      }
      if (pan && !isValidPan(pan)) {
        errors.push(`${ownerLabel}: enter a valid PAN.`);
      } else if (pan && pan === draft.personal.pan.trim().toUpperCase()) {
        errors.push(`${ownerLabel}: PAN cannot match the assessee PAN.`);
      } else if (pan && coOwnerPans.has(pan)) {
        errors.push(`${ownerLabel}: PAN duplicates another co-owner.`);
      }
      if (pan) coOwnerPans.add(pan);
      if (aadhaar && !isValidAadhaar(aadhaar)) {
        errors.push(`${ownerLabel}: enter a valid 12-digit Aadhaar number.`);
      } else if (aadhaar && aadhaar === draft.personal.aadhaar.trim()) {
        errors.push(`${ownerLabel}: Aadhaar cannot match the assessee Aadhaar.`);
      } else if (aadhaar && coOwnerAadhaars.has(aadhaar)) {
        errors.push(`${ownerLabel}: Aadhaar duplicates another co-owner.`);
      }
      if (aadhaar) coOwnerAadhaars.add(aadhaar);
    });

    const tenantPans = new Set<string>();
    const tenantAadhaars = new Set<string>();
    const tenantPanTans = new Set<string>();
    tenants.forEach((tenant, tenantIndex) => {
      const tenantLabel = `${label}, tenant ${tenantIndex + 1}`;
      const pan = tenant.pan.trim().toUpperCase();
      const aadhaar = tenant.aadhaar.trim();
      const panOrTan = tenant.panOrTan.trim().toUpperCase();
      if (!tenant.name.trim()) {
        errors.push(`${tenantLabel}: enter the tenant name.`);
      }
      if (pan && !isValidPan(pan)) {
        errors.push(`${tenantLabel}: enter a valid PAN.`);
      } else if (pan && tenantPans.has(pan)) {
        errors.push(`${tenantLabel}: PAN duplicates another tenant.`);
      }
      if (pan) tenantPans.add(pan);
      if (aadhaar && !isValidAadhaar(aadhaar)) {
        errors.push(`${tenantLabel}: enter a valid 12-digit Aadhaar number.`);
      } else if (aadhaar && tenantAadhaars.has(aadhaar)) {
        errors.push(`${tenantLabel}: Aadhaar duplicates another tenant.`);
      }
      if (aadhaar) tenantAadhaars.add(aadhaar);
      if (panOrTan && !isValidPanOrTan(panOrTan)) {
        errors.push(`${tenantLabel}: enter a valid PAN or TAN.`);
      } else if (panOrTan && tenantPanTans.has(panOrTan)) {
        errors.push(`${tenantLabel}: PAN/TAN duplicates another tenant.`);
      }
      if (panOrTan) tenantPanTans.add(panOrTan);
    });
    const annualLettableValue = property.annualLettingValue > 0
      ? property.annualLettingValue
      : property.annualRent;
    if (property.unrealizedRent > annualLettableValue && annualLettableValue > 0) {
      errors.push(`${label}: rent not realized cannot exceed annual lettable value.`);
    }
  });

  draft.deductions.section80G.forEach((donation, index) => {
    if (!normalizeStateCode(donation.stateCode) || donation.stateCode === '99') {
      errors.push(`80G donation ${index + 1}: select a valid Indian donee state code.`);
    }
    if (!isValidIndianPin(donation.pinCode)) {
      errors.push(`80G donation ${index + 1}: enter a valid 6-digit Indian PIN code.`);
    }
  });

  draft.deductions.schedule80GGA.forEach((donation, index) => {
    if (!normalizeStateCode(donation.stateCode) || donation.stateCode === '99') {
      errors.push(`80GGA donation ${index + 1}: select a valid Indian donee state code.`);
    }
    if (!isValidIndianPin(donation.pinCode)) {
      errors.push(`80GGA donation ${index + 1}: enter a valid 6-digit Indian PIN code.`);
    }
  });

  draft.taxes.tds.forEach((credit, index) => {
    if (credit.schedule !== 'TDS3' && !isValidTan(credit.deductorTAN)) {
      errors.push(`TDS entry ${index + 1}: deductor TAN is not a valid CBDT jurisdiction TAN.`);
    }
  });

  draft.taxes.tcs.forEach((credit, index) => {
    if (!isValidTan(credit.collectorTAN)) {
      errors.push(`TCS entry ${index + 1}: collector TAN is not a valid CBDT jurisdiction TAN.`);
    }
  });

  if (draft.bankAccounts.length === 0) {
    errors.push('Bank accounts: add at least one account for the mandatory refund section.');
  }
  const refundAccountCount = draft.bankAccounts.filter((account) => account.useForRefund).length;
  if (draft.bankAccounts.length > 0 && refundAccountCount !== 1) {
    errors.push('Bank accounts: select exactly one account to use for refund.');
  }
  const bankAccountKeys = new Set<string>();
  draft.bankAccounts.forEach((account, index) => {
    const label = `Bank account ${index + 1}`;
    const ifsc = account.ifscCode.trim().toUpperCase();
    const accountNumber = account.accountNumber.trim().toUpperCase();
    if (!account.bankName.trim()) {
      errors.push(`${label}: enter the bank name.`);
    } else if (account.bankName.trim().length > 125) {
      errors.push(`${label}: bank name cannot exceed 125 characters.`);
    }
    if (!isValidBankAccountNumber(account.accountNumber)) {
      errors.push(`${label}: enter a valid account number of up to 20 characters ending in a digit.`);
    }
    if (!isValidIfsc(ifsc)) {
      errors.push(`${label}: enter a valid IFSC (4 letters, 0, then 6 alphanumeric characters).`);
    }
    if (!BANK_ACCOUNT_TYPES.has(account.accountType)) {
      errors.push(`${label}: select a valid account type.`);
    }
    if (ifsc && accountNumber) {
      const key = `${ifsc}:${accountNumber}`;
      if (bankAccountKeys.has(key)) {
        errors.push(`${label}: duplicates another bank account.`);
      }
      bankAccountKeys.add(key);
    }
  });

  return errors;
}
