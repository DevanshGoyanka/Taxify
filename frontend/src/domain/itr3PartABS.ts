import type { CanonicalObject, CanonicalValue } from '../components/business/ITR3BusinessCoreManager';
import { ITR3_PARTA_BS_FIELDS, type ITR3FinancialField, isFinancialFieldEditable, readCanonicalPath, updateCanonicalPath } from './itr3PartAFinancials';

/** Official scalar leaf groups for the AY 2026-27 PARTA_BS editor. */
export interface ITR3PartABSCurrentAssets { cashInHand: number; bankBalance: number; finishedGoods: number; rawMaterials: number; workInProcess: number; storesConsumables: number; sundryDebtors: number; otherCurrentAssets: number; }
export interface ITR3PartABSLoansAdvances { advancesRecoverable: number; balancesWithRevenueAuthority: number; deposits: number; }
export interface ITR3PartABSFixedAssets { grossBlock: number; depreciation: number; capitalWorkInProgress: number; }
export interface ITR3PartABSInvestments { governmentOtherSecuritiesUnquoted: number; governmentOtherSecuritiesQuoted: number; debentures: number; equityShares: number; preferenceShares: number; }
export interface ITR3PartABSLiabilities { accruedInterestNotDue: number; accruedInterestLeasedAsset: number; liabilityLeasedAsset: number; sundryCreditors: number; incomeTaxProvision: number; employeeBenefitsProvision: number; otherProvision: number; }
export interface ITR3PartABSLoanFunds { securedForeignCurrency: number; securedFromBank: number; securedFromOthers: number; unsecuredFromBank: number; unsecuredFromOthers: number; }
export interface ITR3PartABSProprietorFund { proprietorCapital: number; capitalReserve: number; otherReserve: number; revenueReserve: number; statutoryReserve: number; }
export interface ITR3PartABSNoBooks { cashBalance: number; stockInTrade: number; sundryCreditors: number; sundryDebtors: number; }
export interface ITR3PartABSDetails { currentAssets: ITR3PartABSCurrentAssets; loansAndAdvances: ITR3PartABSLoansAdvances; fixedAssets: ITR3PartABSFixedAssets; investments: ITR3PartABSInvestments; liabilities: ITR3PartABSLiabilities; loanFunds: ITR3PartABSLoanFunds; proprietorFund: ITR3PartABSProprietorFund; deferredTax: number; advancesFromPersons: number; advancesFromOthers: number; accumulatedLosses: number; deferredTaxAsset: number; miscellaneousExpenditure: number; noBooks: ITR3PartABSNoBooks; }

/** Returns the official PARTA_BS fields, including mandatory scalar leaves. */
export function partABSFields(): readonly ITR3FinancialField[] { return ITR3_PARTA_BS_FIELDS; }

/** Updates one editable PARTA_BS field without mutating the source workspace. */
export function updatePartABSField(value: CanonicalObject, field: ITR3FinancialField, next: CanonicalValue): CanonicalObject {
  if (!isFinancialFieldEditable(field) || field.schedule !== 'PARTA_BS') return value;
  return updateCanonicalPath(value, field.path, next);
}

/** Reads an official PARTA_BS field from the canonical workspace. */
export function readPartABSField(value: CanonicalObject, field: ITR3FinancialField): CanonicalValue | undefined { return readCanonicalPath(value, field.path); }
