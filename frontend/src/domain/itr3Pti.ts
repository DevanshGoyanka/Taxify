import type { PassThroughIncomeEntry, PTIIncomeHead } from './returns/types';

/** Official ITR-3 Schedule PTI section codes supported by the backend mapper. */
export const ITR3_PTI_SECTIONS = ['115UA', '115UB', '115U', '115T', '111A', '112A', '112', '23FBAA', '23FBB', 'OTHER'] as const;
export type ITR3PTISection = typeof ITR3_PTI_SECTIONS[number];

/** Canonical official paths represented by the editable PTI row model. */
export const ITR3_PTI_PATHS = [
  'SchedulePTI.SchedulePTIDtls[].InvstmntCvrdUs115UA115UB',
  'SchedulePTI.SchedulePTIDtls[].BusinessName',
  'SchedulePTI.SchedulePTIDtls[].BusinessPAN',
  'SchedulePTI.SchedulePTIDtls[].IncFromHP',
  'SchedulePTI.SchedulePTIDtls[].CapitalGainsPTI',
  'SchedulePTI.SchedulePTIDtls[].CapitalGainsPTI.ShortTermCG',
  'SchedulePTI.SchedulePTIDtls[].CapitalGainsPTI.STCG_Sec111A',
  'SchedulePTI.SchedulePTIDtls[].CapitalGainsPTI.STCG_Others',
  'SchedulePTI.SchedulePTIDtls[].CapitalGainsPTI.LongTermCG',
  'SchedulePTI.SchedulePTIDtls[].CapitalGainsPTI.LTCG_Sec112A',
  'SchedulePTI.SchedulePTIDtls[].CapitalGainsPTI.LTCG_Others',
  'SchedulePTI.SchedulePTIDtls[].IncClmdPTI',
  'SchedulePTI.SchedulePTIDtls[].IncClmdPTI.TotalSec23FBB',
  'SchedulePTI.SchedulePTIDtls[].IncClmdPTI.Sec23FBB',
  'SchedulePTI.SchedulePTIDtls[].IncClmdPTI.SecBIncExmptDtl',
  'SchedulePTI.SchedulePTIDtls[].IncClmdPTI.SecCIncExmptDtl',
  'SchedulePTI.SchedulePTIDtls[].IncOthSrc',
  'SchedulePTI.SchedulePTIDtls[].OS_Dividend',
  'SchedulePTI.SchedulePTIDtls[].OS_Others',
] as const;

const PAN = /^[A-Z]{5}[0-9]{4}[A-Z]$/;
const HEADS: readonly PTIIncomeHead[] = ['HP', 'STCG', 'LTCG', 'OS'];

/** Creates a blank canonical row without adding unsupported schema fields. */
export function createITR3PTIEntry(id: string): PassThroughIncomeEntry {
  return { id, investmentType: 'A', entityName: '', entityPAN: '', incomeHead: 'OS', section: '115UA', incomeAmount: 0, tdsCredit: 0 };
}

/** Returns validation errors that prevent an amount being assigned to the wrong head/section. */
export function validateITR3PTIEntry(entry: PassThroughIncomeEntry): string[] {
  const errors: string[] = [];
  const section = entry.section.toUpperCase();
  const expectedType = section === '115UA' ? 'A' : section === '115UB' ? 'B' : section === '115U' ? 'C' : '';
  if (expectedType && entry.investmentType !== expectedType) errors.push('Entity type must match the applicable section.');
  if (!entry.entityName.trim()) errors.push('Trust/fund name is required.');
  if (!PAN.test(entry.entityPAN.trim().toUpperCase())) errors.push('Trust/fund PAN must be a valid PAN.');
  if (!HEADS.includes(entry.incomeHead)) errors.push('Income head is not supported by Schedule PTI.');
  if (!ITR3_PTI_SECTIONS.includes(entry.section as ITR3PTISection)) errors.push('Select an official Schedule PTI section.');
  if (entry.incomeAmount < 0 || entry.tdsCredit < 0) errors.push('Income and TDS credit cannot be negative.');
  if (entry.tdsCredit > entry.incomeAmount && entry.incomeAmount >= 0) errors.push('TDS credit cannot exceed the reported PTI income.');
  if (entry.incomeHead === 'STCG' && !['111A', '115UA', '115UB', '115U', '115T'].includes(section)) errors.push('STCG must use section 111A or the applicable trust/fund section.');
  if (entry.incomeHead === 'LTCG' && !['112', '112A', '115UA', '115UB', '115U', '115T'].includes(section)) errors.push('LTCG must use section 112/112A or the applicable trust/fund section.');
  if (entry.incomeHead === 'HP' && ['111A', '112', '112A'].includes(section)) errors.push('House-property PTI cannot use a capital-gains section.');
  if (entry.incomeHead === 'OS' && ['111A', '112', '112A'].includes(section)) errors.push('Other-sources PTI cannot use a capital-gains section.');
  return [...new Set(errors)];
}

/** Calculates read-only aggregates grouped by income head. */
export function aggregateITR3PTI(entries: readonly PassThroughIncomeEntry[]): Record<PTIIncomeHead, number> {
  return entries.reduce<Record<PTIIncomeHead, number>>((result, entry) => {
    result[entry.incomeHead] += Number.isFinite(entry.incomeAmount) ? entry.incomeAmount : 0;
    return result;
  }, { HP: 0, STCG: 0, LTCG: 0, OS: 0 });
}
