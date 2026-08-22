import {
  normalizeEmployerCategory,
  normalizeEmploymentNature,
  normalizeStateCode,
} from './cbdtEnums';
import type { ReturnDraft } from './types';
import { isValidTan } from '../../utils/taxIdentifiers';

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

  draft.employers.forEach((employer, index) => {
    const label = employer.employerName.trim() || `Employer ${index + 1}`;
    if (!normalizeEmploymentNature(employer.natureOfEmployment)) {
      errors.push(`${label}: select a valid nature of employment.`);
    }
    if (employer.employerTAN && !isValidTan(employer.employerTAN)) {
      errors.push(`${label}: employer TAN is not a valid CBDT jurisdiction TAN.`);
    }
  });

  draft.houseProperties.forEach((property, index) => {
    const expectedState = property.countryCode === '91' ? normalizeStateCode(property.state) : property.state === '99' ? '99' : '';
    if (!expectedState) {
      errors.push(`House property ${index + 1}: select a valid CBDT state code.`);
    }
  });

  draft.deductions.section80G.forEach((donation, index) => {
    if (!normalizeStateCode(donation.stateCode) || donation.stateCode === '99') {
      errors.push(`80G donation ${index + 1}: select a valid Indian donee state code.`);
    }
  });

  draft.deductions.schedule80GGA.forEach((donation, index) => {
    if (!normalizeStateCode(donation.stateCode) || donation.stateCode === '99') {
      errors.push(`80GGA donation ${index + 1}: select a valid Indian donee state code.`);
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

  return errors;
}
