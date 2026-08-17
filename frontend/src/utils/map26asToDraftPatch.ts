import { EMPTY_TDS_CREDIT, EMPTY_TCS_CREDIT, type DividendIncome, type Employer, type InterestIncome, type TdsCredit, type TcsCredit } from '../domain/returns/types';
import type { ReturnDraftPatch } from '../domain/returns/draftPatch';
import { createReconciliationEvidence } from '../domain/returns/evidence';
import { classify26asEntry } from '../domain/returns/sourceClassification';
import { normalizeNatureOfEmployment } from './normalizeNatureOfEmployment';

interface DeductorAggregate { sectionCode?: string; section?: string; employerName?: string; deductorName?: string; employerTAN?: string; deductorTAN?: string; deductorPAN?: string; totalAmount?: number; incomeAmount?: number; totalTDS?: number; tdsDeducted?: number; }
export interface Form26AsImportData { financialYear?: string; tdsEntries?: DeductorAggregate[]; deductorAggregates?: DeductorAggregate[]; incomeBreakdown?: { deductorDetails?: DeductorAggregate[] }; tcsEntries?: TcsAggregate[]; sourceRows?: SourceRow[]; }
interface TcsAggregate { collectorName?: string; collectorTAN?: string; sectionCode?: string; grossAmount?: number; taxCollected?: number; taxDeposited?: number; }
interface SourceRow { part?: string; rowIndex?: number; sectionCode?: string; title?: string; credit?: boolean; raw?: Record<string, unknown>; }
function id(prefix: string, ...parts: unknown[]): string {
  const text = parts.map((part) => String(part ?? '')).join('|');
  let hash = 2166136261;
  for (let i = 0; i < text.length; i += 1) { hash ^= text.charCodeAt(i); hash = Math.imul(hash, 16777619); }
  return `${prefix}-${(hash >>> 0).toString(36)}`;
}
function rowId(prefix: string, row: DeductorAggregate): string { return id(prefix, row.employerTAN || row.deductorTAN, row.sectionCode || row.section, row.totalAmount || row.incomeAmount); }
function fy(value?: string): string { const match = value?.match(/^(\d{4})-(?:\d{2})?(\d{2})$/); return match ? `${match[1]}-${match[2]}` : value || '2025-26'; }

/** Maps raw Form 26AS import data into canonical draft fields. */
export function map26asToDraftPatch(data: Form26AsImportData | null | undefined): ReturnDraftPatch {
  if (!data) return {};
  const rows = data.incomeBreakdown?.deductorDetails || data.tdsEntries || data.deductorAggregates || [];
  const salary = rows.filter((row) => ['192', '192A'].includes(row.sectionCode || row.section || ''));
  const interestRows = rows.filter((row) => ['193', '194A', '194K'].includes(row.sectionCode || row.section || ''));
  const dividendRows = rows.filter((row) => (row.sectionCode || row.section) === '194');
  const employers: Employer[] = salary.map((row) => ({ id: `employer-${(row.employerTAN || row.deductorTAN || row.employerName || row.deductorName || 'unknown').trim().toUpperCase()}`, customEmployerName: row.employerName || row.deductorName || '', employerName: row.employerName || row.deductorName || 'Employer', employerTAN: row.employerTAN || row.deductorTAN || '', natureOfEmployment: normalizeNatureOfEmployment('OTH'), employerAddress: '', employerCity: '', employerStateCode: '', employerPinCode: '', employerZipCode: '', salaryNatureRows: [], perquisiteNatureRows: [], section10ExemptionRows: [], basic: row.totalAmount || row.incomeAmount || 0, da: 0, commission: 0, hra: 0, bonus: 0, allowances: 0, lta: 0, otherAllowance: 0, arrearSalary: 0, perquisites: 0, profitsInLieu: 0, rentPaid: 0, city: '', isMetroCity: false, isGovernmentEmployee: false, isDisabledEmployee: false, commutedPension: 0, gratuity: 0, leaveEncashment: 0, averageMonthlySalary: 0, yearsOfService: 0, unavailedLeaveDays: 0, actualLtaFare: 0, isDomesticTravel: true, journeysInBlock: 0, ltaExempt: 0, numberOfChildren: 0, gratuityAlsoReceived: false, transportAllowance: 0, childrenEducationAllowance: 0, hostelExpenditureAllowance: 0, uniformAllowance: 0, entertainmentAllowance: 0, professionalTax: 0, vrsCompensation: 0, retrenchmentCompensation: 0, otherExempt: 0, tdsDeducted: row.totalTDS || row.tdsDeducted || 0, employerNPS: 0 }));
  const interest: InterestIncome[] = interestRows.map((row) => { const section = row.sectionCode || row.section || '194A'; const kind = section === '193' ? 'SAVINGS_BANK' : section === '194K' ? 'OTHER' : 'TERM_DEPOSIT'; return { id: id('26as-interest', row), kind, grossAmount: row.totalAmount || row.incomeAmount || 0, tdsDeducted: row.totalTDS || row.tdsDeducted || 0, bankName: row.employerName || row.deductorName || 'Bank', accountType: kind === 'SAVINGS_BANK' ? 'SAVINGS' : 'FD', accountNumber: '', ifscCode: '', postOfficeName: '', accountNumberPO: '', nscCertificateNumber: '', yearOfPurchase: 0, scssAccountNumber: '', dateOfOpening: '', deductorName: row.employerName || row.deductorName || '', deductorTAN: row.employerTAN || row.deductorTAN || '', remarks: '' }; });
  const dividends: DividendIncome[] = dividendRows.map((row) => ({ id: id('26as-dividend', row), section: '194', grossAmount: row.totalAmount || row.incomeAmount || 0, tdsDeducted: row.totalTDS || row.tdsDeducted || 0, companyName: row.employerName || row.deductorName || 'Company', companyPAN: row.deductorPAN || '', deductorTAN: row.employerTAN || row.deductorTAN || '', isin: '', category: 'EQUITY', q1: 0, q2: 0, q3: 0, q4: 0, q5: 0 }));
  const taxes: TdsCredit[] = rows.filter((row) => (row.totalTDS || row.tdsDeducted || 0) > 0).map((row) => { const section = row.sectionCode || row.section || '192'; const tax = row.totalTDS || row.tdsDeducted || 0; return { ...structuredClone(EMPTY_TDS_CREDIT), id: rowId('26as-tds', row), section, deductorName: row.employerName || row.deductorName || '', deductorTAN: row.employerTAN || row.deductorTAN || '', deductorPAN: row.deductorPAN || '', grossAmount: row.totalAmount || row.incomeAmount || 0, taxDeducted: tax, financialYear: fy(data.financialYear), verified26AS: true, schedule: section === '192' ? 'TDS1' : 'TDS2', headOfIncome: section === '192' ? 'NA' : 'OS', claimOutOfTotTDSOnAmtPaid: tax }; });
  const tcs: TcsCredit[] = (data.tcsEntries || []).map((row, index) => ({
    ...structuredClone(EMPTY_TCS_CREDIT), id: id('26as-tcs', row.collectorTAN, row.sectionCode, row.grossAmount, row.taxCollected, index),
    collectorName: row.collectorName || '', collectorTAN: row.collectorTAN || '', grossAmount: row.grossAmount || 0,
    taxCollected: row.taxCollected || 0, deductedYr: Number.parseInt(fy(data.financialYear).slice(0, 4), 10) || '',
    tcsAmtCollOwnHand: row.taxCollected || 0, tcsClaimedAmtCollOwnHand: row.taxCollected || 0,
  }));
  const evidence = (data.sourceRows || []).length > 0
    ? (data.sourceRows || []).map((sourceRow, index) => {
      const raw = sourceRow.raw || {};
      const section = sourceRow.sectionCode || '';
      const classification = classify26asEntry(section);
      return createReconciliationEvidence({
        source: '26AS', code: section, section: sourceRow.part || '', category: section || `Part ${sourceRow.part || ''}`,
        description: sourceRow.title || `26AS Part ${sourceRow.part || ''}`,
        sourceName: String(raw['Name of Deductor'] || raw['Name of Collector'] || ''),
        sourceIdentifier: String(raw['TAN of Deductor'] || raw['TAN of Collector'] || raw['PAN of Deductor'] || ''),
        reportedAmount: raw['Total Amount Paid/Credited'] || raw['Total Amount Paid/Debited'] || raw['Total Transaction Amount'],
        processedAmount: raw['Total Amount Paid/Credited'] || raw['Total Amount Paid/Debited'] || raw['Total Transaction Amount'],
        taxAmount: raw['Total Tax Deducted'] || raw['Total Tax Collected'], status: classification.role,
        evidenceKind: 'SOURCE_DETAIL', raw, identity: [sourceRow.part, sourceRow.rowIndex, section, index],
      });
    })
    : rows.map((row, index) => {
      const section = row.sectionCode || row.section || '';
      return createReconciliationEvidence({
        source: '26AS', code: section, section, category: section, description: row.employerName || row.deductorName || '',
        sourceName: row.employerName || row.deductorName || '', sourceIdentifier: row.employerTAN || row.deductorTAN || row.deductorPAN || '',
        reportedAmount: row.totalAmount || row.incomeAmount, processedAmount: row.totalAmount || row.incomeAmount,
        taxAmount: row.totalTDS || row.tdsDeducted, status: section, raw: row as unknown as Record<string, unknown>,
        identity: [section, row.employerTAN || row.deductorTAN, row.totalAmount || row.incomeAmount, row.totalTDS || row.tdsDeducted, index],
      });
    });
  return { employers, otherSources: { interest, dividends }, taxes: { tds: taxes, tcs }, provenance: [{ source: '26AS', importedAt: new Date().toISOString(), reference: fy(data.financialYear) }], reconciliation: { evidence, discrepancies: [] } };
}
