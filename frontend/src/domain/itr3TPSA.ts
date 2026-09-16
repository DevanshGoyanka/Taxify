import type { CanonicalJsonValue } from './returns/types';

/** Official AY 2026-27 Schedule TPSA tax-payment facts. */
export interface ITR3TPSATaxPayment {
  id: string;
  bsrCode: string;
  bankBranchName: string;
  dateDep: string;
  srlNoOfChaln: number;
  amount: number;
}

/** Canonical taxpayer-supplied Schedule TPSA facts; tax totals are backend outputs. */
export interface ITR3TPSA {
  details: ITR3TPSATaxPayment[];
}

/** Official scalar paths covered by the backend-computed TPSA projection. */
export const ITR3_TPSA_COMPUTED_PATHS = [
  'ScheduleTPSA.AmtPrimaryAdjUs92CE_2A',
  'ScheduleTPSA.AdditionalIncTax18PercAbove',
  'ScheduleTPSA.Surcharge12Perc',
  'ScheduleTPSA.HealthEducationCess',
  'ScheduleTPSA.TotalAdditionalTax',
  'ScheduleTPSA.TaxesPaid',
  'ScheduleTPSA.NetTaxPayable',
  'ScheduleTPSA.TotalAmountDeposited',
] as const;

/** Official editable TPSA tax-deposit paths. */
export const ITR3_TPSA_INPUT_PATHS = [
  'ScheduleTPSA.DtlsTaxesPaid[].Amount',
  'ScheduleTPSA.DtlsTaxesPaid[].BSRCode',
  'ScheduleTPSA.DtlsTaxesPaid[].BankBranchName',
  'ScheduleTPSA.DtlsTaxesPaid[].DateDep',
  'ScheduleTPSA.DtlsTaxesPaid[].SrlNoOfChaln',
] as const;

/** Applies a safe immutable patch to a TPSA deposit row. */
export function updateITR3TPSADeposit(row: ITR3TPSATaxPayment, patch: Partial<ITR3TPSATaxPayment>): ITR3TPSATaxPayment {
  return {
    ...row,
    bsrCode: patch.bsrCode === undefined ? row.bsrCode : String(patch.bsrCode).toUpperCase(),
    bankBranchName: patch.bankBranchName === undefined ? row.bankBranchName : String(patch.bankBranchName),
    dateDep: patch.dateDep === undefined ? row.dateDep : String(patch.dateDep),
    srlNoOfChaln: patch.srlNoOfChaln === undefined ? row.srlNoOfChaln : clampInteger(patch.srlNoOfChaln, 0, 99999),
    amount: patch.amount === undefined ? row.amount : nonNegative(patch.amount),
  };
}

/** Validates a TPSA challan against the official schema's scalar constraints. */
export function validateITR3TPSADeposit(row: ITR3TPSATaxPayment): string[] {
  const errors: string[] = [];
  if (!/^[0-9]{3}[0-9A-Z]{4}$/.test(row.bsrCode)) errors.push('BSRCode must contain 3 digits followed by 4 alphanumeric characters.');
  if (row.bankBranchName.trim().length < 1 || row.bankBranchName.length > 125) errors.push('Bank branch name is required and must be at most 125 characters.');
  if (!/^\d{4}-\d{2}-\d{2}$/.test(row.dateDep) || !isValidDate(row.dateDep)) errors.push('Date deposited must be a valid YYYY-MM-DD date.');
  if (!Number.isInteger(row.srlNoOfChaln) || row.srlNoOfChaln < 0 || row.srlNoOfChaln > 99999) errors.push('Challan serial number must be an integer from 0 to 99999.');
  if (!Number.isInteger(row.amount) || row.amount < 0) errors.push('Amount cannot be negative.');
  return errors;
}

/** Creates an empty deposit row without inventing taxpayer data. */
export function emptyITR3TPSADeposit(id: string): ITR3TPSATaxPayment {
  return { id, bsrCode: '', bankBranchName: '', dateDep: '', srlNoOfChaln: 0, amount: 0 };
}

function nonNegative(value: number): number { return Number.isFinite(value) && value >= 0 ? Math.trunc(value) : 0; }
function clampInteger(value: number, minimum: number, maximum: number): number { return Math.max(minimum, Math.min(maximum, Math.trunc(Number.isFinite(value) ? value : minimum))); }
function isValidDate(value: string): boolean { const date = new Date(`${value}T00:00:00Z`); return !Number.isNaN(date.getTime()) && date.toISOString().slice(0, 10) === value; }

/** Converts canonical TPSA deposits to the backend's JSON-compatible shape. */
export function toITR3TPSAJson(value: ITR3TPSA): CanonicalJsonValue { return { DtlsTaxesPaid: value.details.map(({ id: _id, bsrCode, bankBranchName, dateDep, srlNoOfChaln, amount }) => ({ BSRCode: bsrCode, BankBranchName: bankBranchName, DateDep: dateDep, SrlNoOfChaln: srlNoOfChaln, Amount: amount })) }; }
