import type { CanonicalJsonValue, ITR3BusinessWorkspace } from './returns/types';

/** Official AY 2026-27 Schedule 80RA donee identity and claim facts. */
export interface Schedule80RADonee {
  NameOfDonee: string;
  AddrDetail: string;
  CityOrTownOrDistrict: string;
  StateCode: string;
  PinCode: number;
  DoneePAN: string;
  DonationAmtCash: number;
  DonationAmtOtherMode: number;
  DonationAmt: number;
}

/** Dedicated frontend representation of Schedule 80RA source facts. */
export interface Schedule80RAWorkspace { DonationDtlsRsrchAssctn: Schedule80RADonee[]; }

/** Official Schedule 80IB activity source facts; deduction rows are computed. */
export interface Schedule80IBActivity { Sch80LocOrDescCode: string; }

/** Dedicated frontend representation of Schedule 80IB source facts. */
export interface Schedule80IBWorkspace {
  Sch80SectionCode: '80-IB';
  DeductMinOilUs80_IB_9_Und: Schedule80IBActivity;
  DeductHousUs80_IB_10_Und: Schedule80IBActivity;
  DeductFruitVegUs80_IB_11A_Und: Schedule80IBActivity;
  DeductFoodGrainUs80_IB_11A_Und: Schedule80IBActivity;
}

const emptyRA: Schedule80RAWorkspace = { DonationDtlsRsrchAssctn: [] };
const emptyIB: Schedule80IBWorkspace = { Sch80SectionCode: '80-IB', DeductMinOilUs80_IB_9_Und: { Sch80LocOrDescCode: 'COMM_PROD' }, DeductHousUs80_IB_10_Und: { Sch80LocOrDescCode: 'HOUSING_PROJECT' }, DeductFruitVegUs80_IB_11A_Und: { Sch80LocOrDescCode: 'FRIUTS_VEGTBLE' }, DeductFoodGrainUs80_IB_11A_Und: { Sch80LocOrDescCode: 'STOR_TRANS' } };

/** Reads Schedule 80RA source facts without fabricating claims. */
export function readSchedule80RA(workspace: ITR3BusinessWorkspace): Schedule80RAWorkspace { const value = workspace.auxiliary.Schedule80RA; return value && typeof value === 'object' && !Array.isArray(value) ? value as unknown as Schedule80RAWorkspace : emptyRA; }
/** Reads Schedule 80IB source facts without exposing computed deduction rows. */
export function readSchedule80IB(workspace: ITR3BusinessWorkspace): Schedule80IBWorkspace { const value = workspace.auxiliary.Schedule80_IB; return value && typeof value === 'object' && !Array.isArray(value) ? value as unknown as Schedule80IBWorkspace : emptyIB; }

/** Updates one validated Schedule 80RA source scalar immutably. */
export function updateSchedule80RA(workspace: ITR3BusinessWorkspace, index: number, field: keyof Omit<Schedule80RADonee, 'AddrDetail' | 'CityOrTownOrDistrict' | 'StateCode' | 'PinCode'>, value: string | number): ITR3BusinessWorkspace {
  const current = readSchedule80RA(workspace); if (!Number.isInteger(index) || index < 0 || index >= current.DonationDtlsRsrchAssctn.length) return workspace;
  if (field === 'DonationAmtCash' || field === 'DonationAmtOtherMode' || field === 'DonationAmt') { if (typeof value !== 'number' || !Number.isFinite(value) || value < 0) return workspace; }
  if (field === 'NameOfDonee' || field === 'DoneePAN' && (typeof value !== 'string' || value.length > 10)) return workspace;
  const rows = current.DonationDtlsRsrchAssctn.map((row, rowIndex) => rowIndex === index ? { ...row, [field]: value } : row);
  return { ...workspace, auxiliary: { ...workspace.auxiliary, Schedule80RA: { ...current, DonationDtlsRsrchAssctn: rows } as unknown as CanonicalJsonValue } };
}

/** Adds an 80RA row only when all taxpayer/source fields are explicitly supplied. */
export function addSchedule80RARow(workspace: ITR3BusinessWorkspace, row: Schedule80RADonee): ITR3BusinessWorkspace { if (!validateSchedule80RARow(row).length) return { ...workspace, auxiliary: { ...workspace.auxiliary, Schedule80RA: { DonationDtlsRsrchAssctn: [...readSchedule80RA(workspace).DonationDtlsRsrchAssctn, { ...row }] } as unknown as CanonicalJsonValue } }; return workspace; }
/** Validates 80RA identity, PAN, date-independent amount, and address facts. */
export function validateSchedule80RARow(row: Schedule80RADonee): string[] { const errors: string[] = []; if (!row.NameOfDonee.trim()) errors.push('NameOfDonee is required'); if (!/^[A-Z]{5}[0-9]{4}[A-Z]$/.test(row.DoneePAN)) errors.push('DoneePAN is invalid'); if (!Number.isInteger(row.PinCode) || row.PinCode < 100000 || row.PinCode > 999999) errors.push('PinCode is invalid'); for (const field of ['DonationAmtCash', 'DonationAmtOtherMode', 'DonationAmt'] as const) if (!Number.isFinite(row[field]) || row[field] < 0) errors.push(`${field} is invalid`); return errors; }

/** Returns the fixed official 80IB source activity codes. */
export function schedule80IBActivities(): Schedule80IBWorkspace { return JSON.parse(JSON.stringify(emptyIB)) as Schedule80IBWorkspace; }
