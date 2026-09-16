import type { ForeignSourceIncomeEntry, ForeignTaxReliefEntry, ForeignReliefSection } from './returns/types';

/** Official Schedule FSI editable paths mapped to ReturnDraft fields. */
export const ITR3_FSI_INPUT_PATHS = [
  'ScheduleFSI.ScheduleFSIDtls[].CountryName',
  'ScheduleFSI.ScheduleFSIDtls[].CountryCodeExcludingIndia',
  'ScheduleFSI.ScheduleFSIDtls[].TaxIdentificationNo',
  'ScheduleFSI.ScheduleFSIDtls[].IncFromSal.IncFrmOutsideInd',
  'ScheduleFSI.ScheduleFSIDtls[].IncFromSal.TaxPaidOutsideInd',
  'ScheduleFSI.ScheduleFSIDtls[].IncFromHP.IncFrmOutsideInd',
  'ScheduleFSI.ScheduleFSIDtls[].IncFromHP.TaxPaidOutsideInd',
  'ScheduleFSI.ScheduleFSIDtls[].IncFromBusiness.IncFrmOutsideInd',
  'ScheduleFSI.ScheduleFSIDtls[].IncFromBusiness.TaxPaidOutsideInd',
  'ScheduleFSI.ScheduleFSIDtls[].IncCapGain.IncFrmOutsideInd',
  'ScheduleFSI.ScheduleFSIDtls[].IncCapGain.TaxPaidOutsideInd',
  'ScheduleFSI.ScheduleFSIDtls[].IncOthSrc.IncFrmOutsideInd',
  'ScheduleFSI.ScheduleFSIDtls[].IncOthSrc.TaxPaidOutsideInd',
  'ScheduleFSI.ScheduleFSIDtls[].IncFromSal.DTAAReliefUs90or90A',
  'ScheduleFSI.ScheduleFSIDtls[].IncFromHP.DTAAReliefUs90or90A',
  'ScheduleFSI.ScheduleFSIDtls[].IncFromBusiness.DTAAReliefUs90or90A',
  'ScheduleFSI.ScheduleFSIDtls[].IncCapGain.DTAAReliefUs90or90A',
  'ScheduleFSI.ScheduleFSIDtls[].IncOthSrc.DTAAReliefUs90or90A',
] as const;

/** Official Schedule TR1 editable paths mapped to ReturnDraft fields. */
export const ITR3_TR1_INPUT_PATHS = [
  'ScheduleTR1.ScheduleTR[].CountryCodeExcludingIndia',
  'ScheduleTR1.ScheduleTR[].TaxIdentificationNo',
  'ScheduleTR1.ScheduleTR[].IncomeIncludedInThisReturn',
  'ScheduleTR1.ScheduleTR[].TaxPaidOutsideIndia',
  'ScheduleTR1.ScheduleTR[].IndianTaxPayable',
  'ScheduleTR1.ScheduleTR[].ReliefClaimedUsSection',
  'ScheduleTR1.ScheduleTR[].Form67Filed',
  'ScheduleTR1.ScheduleTR[].Form10FFiled',
] as const;

/** Backend-owned Schedule FSI/TR1 paths; displayed read-only only. */
export const ITR3_FOREIGN_COMPUTED_PATHS = [
  'ScheduleFSI.ScheduleFSIDtls[].TotalCountryWise',
  'ScheduleFSI.ScheduleFSIDtls[].TaxReliefinInd',
  'ScheduleTR1.TotalTaxPaidOutsideIndia',
  'ScheduleTR1.TotalTaxReliefOutsideIndia',
  'ScheduleTR1.TaxReliefOutsideIndiaDTAA',
  'ScheduleTR1.TaxReliefOutsideIndiaNotDTAA',
] as const;

export function foreignIncomeTotal(entry: ForeignSourceIncomeEntry): number {
  return Math.max(0, Number(entry.salaryIncome) || 0) + Math.max(0, Number(entry.hpIncome) || 0) + Math.max(0, Number(entry.businessIncome) || 0) + Math.max(0, Number(entry.cgIncome) || 0) + Math.max(0, Number(entry.osIncome) || 0);
}

export function computedRelief(taxPaid: number, indianTax: number): number {
  return Math.min(Math.max(0, Number(taxPaid) || 0), Math.max(0, Number(indianTax) || 0));
}

export function validateForeignSourceIncome(entry: ForeignSourceIncomeEntry): string[] {
  const errors: string[] = [];
  if (!entry.countryName.trim()) errors.push('Country name is required.');
  if (!entry.countryCode.trim()) errors.push('Country code is required.');
  if (!entry.taxIdentificationNo.trim()) errors.push('Foreign tax identification number is required.');
  if (!['90', '90A', '91'].includes(entry.reliefSection)) errors.push('Select Section 90, 90A, or 91.');
  for (const [label, value] of [['Salary income', entry.salaryIncome], ['House-property income', entry.hpIncome], ['Business income', entry.businessIncome], ['Capital gains', entry.cgIncome], ['Other-source income', entry.osIncome], ['Foreign tax paid', entry.taxPaidOutsideIndia], ['Indian tax payable', entry.taxPayableInIndia]] as const) {
    if (!Number.isFinite(Number(value)) || Number(value) < 0) errors.push(`${label} cannot be negative.`);
  }
  return errors;
}

export function validateForeignTaxRelief(entry: ForeignTaxReliefEntry): string[] {
  const errors: string[] = [];
  if (!entry.countryCode.trim()) errors.push('Country is required.');
  if (!entry.taxIdentificationNo.trim()) errors.push('Foreign tax identification number is required.');
  if (!['90', '90A', '91'].includes(entry.reliefSection)) errors.push('Select Section 90, 90A, or 91.');
  for (const [label, value] of [['Income included', entry.incomeIncludedInThisReturn], ['Foreign tax paid', entry.taxPaidOutsideIndia], ['Indian tax payable', entry.indianTaxPayable], ['Relief claimed', entry.reliefClaimed]] as const) {
    if (!Number.isFinite(Number(value)) || Number(value) < 0) errors.push(`${label} cannot be negative.`);
  }
  if (Number(entry.reliefClaimed) > computedRelief(Number(entry.taxPaidOutsideIndia), Number(entry.indianTaxPayable))) errors.push('Relief claimed cannot exceed the lower of foreign tax paid and Indian tax payable.');
  return errors;
}

/** Computes Schedule TR1 aggregate values without mutating the canonical draft. */
export function foreignReliefTotals(entries: readonly ForeignTaxReliefEntry[]): { taxPaid: number; relief: number; dtaaRelief: number; nonDtaaRelief: number } {
  return entries.reduce((totals, entry) => {
    const relief = Math.max(0, Number(entry.reliefClaimed) || 0);
    totals.taxPaid += Math.max(0, Number(entry.taxPaidOutsideIndia) || 0);
    totals.relief += relief;
    if (entry.reliefSection === '90' || entry.reliefSection === '90A') totals.dtaaRelief += relief;
    else totals.nonDtaaRelief += relief;
    return totals;
  }, { taxPaid: 0, relief: 0, dtaaRelief: 0, nonDtaaRelief: 0 });
}

export type ForeignSection = ForeignReliefSection;
