import type { AssetLiabilityDetails, AssetLiabilityImmovable, ESOPDeferralEntry, ForeignAssetEntry, ForeignAssetType } from './returns/types';

/** Supported official Schedule FA categories. */
export const ITR3_FA_ASSET_TYPES: readonly ForeignAssetType[] = [
  'BANK_ACCOUNT', 'CUSTODIAL_ACCOUNT', 'EQUITY_DEBT_INTEREST', 'CASH_VALUE_INSURANCE',
  'FINANCIAL_INTEREST', 'IMMOVABLE_PROPERTY', 'SIGNING_AUTHORITY', 'TRUST',
] as const;

/** Fields whose values are derived by the backend and must never be edited in the UI. */
export const SCHEDULE_AL_COMPUTED_FIELDS = ['totalAssets', 'netAssets'] as const;
export const SCHEDULE_ESOP_COMPUTED_FIELDS = ['balanceTaxCarriedForward'] as const;

const nonNegative = (value: unknown): boolean => typeof value === 'number' && Number.isFinite(value) && value >= 0;
const required = (value: unknown): boolean => typeof value === 'string' && value.trim().length > 0;

/** Validate an official Schedule AL immovable-property row. */
export function validateScheduleALImmovable(row: AssetLiabilityImmovable | null | undefined): string[] {
  if (!row) return ['Immovable-property details are required.'];
  const errors: string[] = [];
  if (!required(row.description)) errors.push('Description is required.');
  if (!row.address || !required(row.address.residenceNo) || !required(row.address.localityOrArea) || !required(row.address.cityOrTownOrDistrict) || !required(row.address.stateCode) || !required(row.address.countryCode)) errors.push('Complete official address is required.');
  if (!nonNegative(row.amount)) errors.push('Amount must be a non-negative number.');
  return errors;
}

/** Validate Schedule AL source facts, excluding backend-computed totals. */
export function validateScheduleAL(value: AssetLiabilityDetails | null | undefined): string[] {
  if (!value) return [];
  const errors: string[] = [];
  for (const key of ['immovableProperty', 'cashInHand', 'bankDeposits', 'sharesAndSecurities', 'insurancePolicies', 'loansAndAdvances', 'jewellery', 'art', 'vehiclesBoatsAircraft', 'relatedLiabilities'] as const) if (!nonNegative(value[key])) errors.push(`${key} must be non-negative.`);
  value.immovableProperties ?? [].forEach((row) => errors.push(...validateScheduleALImmovable(row)));
  for (const row of value.interestHeldInAssets ?? []) {
    if (!required(row.nameOfFirm) || !required(row.panOfFirm)) errors.push('Firm name and PAN are required for an ownership-interest row.');
    if (!nonNegative(row.assesseInvestment)) errors.push('Assessee investment must be non-negative.');
    if (!row.address || !required(row.address.residenceNo) || !required(row.address.localityOrArea) || !required(row.address.cityOrTownOrDistrict) || !required(row.address.stateCode) || !required(row.address.countryCode)) errors.push('Complete address is required for an ownership-interest row.');
  }
  if (value.interestHeldInAssetFlag === 'Y' && !(value.interestHeldInAssets?.length)) errors.push('At least one ownership-interest row is required when the flag is Yes.');
  return errors;
}

/** Validate category-specific Schedule FA required fields. */
export function validateScheduleFA(value: ForeignAssetEntry | null | undefined): string[] {
  if (!value) return ['Foreign-asset row is required.'];
  const errors: string[] = [];
  if (!ITR3_FA_ASSET_TYPES.includes(value.assetType)) errors.push('Unsupported foreign-asset category.');
  for (const [label, field] of [['Country code', value.countryCode], ['Institution/entity name', value.institutionOrEntityName], ['Address', value.address], ['Asset identifier', value.accountOrAssetIdentifier], ['Ownership status', value.ownershipStatus], ['Opening/acquisition date', value.openingOrAcquisitionDate], ['Nature of asset', value.natureOfAsset], ['Nature of income', value.natureOfIncome]] as const) if (!required(field)) errors.push(`${label} is required.`);
  for (const [label, field] of [['Peak value', value.peakValue], ['Closing value', value.closingValue], ['Gross income', value.grossIncome], ['Income offered', value.incomeOffered], ['Total gross proceeds', value.totalGrossProceedsValue]] as const) if (!nonNegative(field)) errors.push(`${label} must be non-negative.`);
  if (value.assetType === 'EQUITY_DEBT_INTEREST' && !nonNegative(value.initialValueOfInvestment)) errors.push('Initial investment value is required for equity/debt interest.');
  return errors;
}

/** Validate user-supplied Schedule ESOP facts. */
export function validateScheduleESOP(value: ESOPDeferralEntry | null | undefined): string[] {
  if (!value) return ['ESOP row is required.'];
  const errors: string[] = [];
  if (!/^[A-Z]{5}[0-9]{4}[A-Z]$/.test(value.employerPAN)) errors.push('Employer PAN is invalid.');
  if (!required(value.dpiitRegistrationNumber) || !required(value.assessmentYear)) errors.push('DPIIT registration and assessment year are required.');
  if (!['FS', 'PS', 'NS'].includes(value.securityType ?? '')) errors.push('Security type must be FS, PS, or NS.');
  for (const [label, field] of [['Tax deferred brought forward', value.taxDeferredBroughtForward], ['Tax payable current year', value.taxPayableCurrentYear], ['Gross perquisite tax', value.grossPerquisiteTax]] as const) if (!nonNegative(field)) errors.push(`${label} must be non-negative.`);
  return errors;
}

/** Compute the display-only Schedule AL asset total from declared source facts. */
export function scheduleALAssetTotal(value: AssetLiabilityDetails | null): number {
  if (!value) return 0;
  return [value.immovableProperty, value.cashInHand, value.bankDeposits, value.sharesAndSecurities, value.insurancePolicies, value.loansAndAdvances, value.jewellery, value.art, value.vehiclesBoatsAircraft].reduce((sum, item) => sum + (Number.isFinite(item) ? item : 0), 0);
}

/** Compute the display-only ESOP reconciliation amount. */
export function scheduleESOPReconciliation(value: ESOPDeferralEntry): number {
  return Math.max(0, value.taxDeferredBroughtForward + (value.grossPerquisiteTax ?? 0) - value.taxPayableCurrentYear);
}
