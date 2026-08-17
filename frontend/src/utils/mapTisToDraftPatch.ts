import type {
  DividendIncome,
  Employer,
  InterestIncome,
} from '../domain/returns/types';
import type { ReturnDraftPatch } from '../domain/returns/draftPatch';
import { createReconciliationEvidence } from '../domain/returns/evidence';
import type { AisImportData } from './mapAisToDraftPatch';

interface TisDetail {
  sr_no?: number | string;
  part?: string;
  information_description?: string;
  information_source?: string;
  institution_pan?: string;
  reported_by_source?: number | string;
  processed_by_system?: number | string;
  accepted_by_taxpayer?: number | string;
}

interface TisEntry {
  sr_no?: number | string;
  category?: string;
  processed_by_system?: number | string;
  accepted_by_taxpayer?: number | string;
  income_head?: string;
  details?: TisDetail[];
}

export interface TisImportData extends AisImportData {
  overview?: TisEntry[];
  income_heads?: Record<string, { entries?: TisEntry[] }>;
  salaryAmount?: number;
  dividendIncome?: number;
  interestFromDeposit?: number;
}

function numberValue(value: unknown): number {
  const parsed = Number.parseFloat(String(value ?? '0').replace(/,/g, ''));
  return Number.isFinite(parsed) ? parsed : 0;
}

function hashId(prefix: string, ...values: unknown[]): string {
  const text = values.map((value) => String(value ?? '')).join('|');
  let hash = 2166136261;
  for (let index = 0; index < text.length; index += 1) {
    hash ^= text.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return `${prefix}-${(hash >>> 0).toString(36)}`;
}

function source(value: string | undefined): { name: string; tan: string } {
  const raw = value || '';
  const match = raw.match(/^(.+?)\s*\(([^)]+)\)\s*$/);
  return {
    name: match?.[1]?.trim() || raw.trim(),
    tan: match?.[2]?.split('.')[0]?.trim() || '',
  };
}

function completeEmployer(name: string, tan: string, amount: number, id: string): Employer {
  return {
    id, customEmployerName: name, employerName: name || 'Employer from TIS',
    employerTAN: tan, natureOfEmployment: 'OTH', employerAddress: '',
    employerCity: '', employerStateCode: '', employerPinCode: '', employerZipCode: '',
    salaryNatureRows: [], perquisiteNatureRows: [], section10ExemptionRows: [],
    basic: amount, da: 0, commission: 0, hra: 0, bonus: 0, allowances: 0, lta: 0,
    otherAllowance: 0, arrearSalary: 0, perquisites: 0, profitsInLieu: 0, rentPaid: 0,
    city: '', isMetroCity: false, isGovernmentEmployee: false,
    isDisabledEmployee: false, commutedPension: 0, gratuity: 0, leaveEncashment: 0,
    averageMonthlySalary: 0, yearsOfService: 0, unavailedLeaveDays: 0,
    actualLtaFare: 0, isDomesticTravel: true, journeysInBlock: 0, ltaExempt: 0,
    numberOfChildren: 0, gratuityAlsoReceived: false, transportAllowance: 0,
    childrenEducationAllowance: 0, hostelExpenditureAllowance: 0,
    uniformAllowance: 0, entertainmentAllowance: 0, professionalTax: 0,
    vrsCompensation: 0, retrenchmentCompensation: 0, otherExempt: 0,
    tdsDeducted: 0, employerNPS: 0,
  };
}

function interestRow(
  kind: InterestIncome['kind'],
  amount: number,
  name: string,
  tan: string,
  identity: unknown,
): InterestIncome {
  return {
    id: hashId('tis-interest', kind, tan || name, identity), kind,
    grossAmount: amount, tdsDeducted: 0, bankName: name,
    accountType: kind === 'SAVINGS_BANK' ? 'SAVINGS' : 'FD',
    accountNumber: '', ifscCode: '', postOfficeName: '', accountNumberPO: '',
    nscCertificateNumber: '', yearOfPurchase: 0, scssAccountNumber: '',
    dateOfOpening: '', deductorName: name, deductorTAN: tan, remarks: '',
  };
}

function dividendRow(
  amount: number,
  name: string,
  pan: string,
  tan: string,
  identity: unknown,
): DividendIncome {
  return {
    id: hashId('tis-dividend', tan || pan || name, identity), section: '194',
    grossAmount: amount, tdsDeducted: 0, companyName: name || 'TIS accepted total',
    companyPAN: pan, deductorTAN: tan, isin: '', category: 'EQUITY',
    q1: 0, q2: 0, q3: 0, q4: 0, q5: 0,
  };
}

function acceptedAmount(entry: TisEntry): number {
  const accepted = numberValue(entry.accepted_by_taxpayer);
  if (accepted || entry.accepted_by_taxpayer === 0 || entry.accepted_by_taxpayer === '0') {
    return accepted;
  }
  return numberValue(entry.processed_by_system);
}

function detailAmount(detail: TisDetail): number {
  if (detail.accepted_by_taxpayer !== undefined && detail.accepted_by_taxpayer !== null && detail.accepted_by_taxpayer !== '-') {
    return numberValue(detail.accepted_by_taxpayer);
  }
  if (detail.processed_by_system !== undefined && detail.processed_by_system !== null && detail.processed_by_system !== '-') {
    return numberValue(detail.processed_by_system);
  }
  return numberValue(detail.reported_by_source);
}

function taxableDetails(entry: TisEntry): TisDetail[] {
  return (entry.details || []).filter((detail) => (detail.part || '').trim().toUpperCase() !== 'TDS/TCS');
}

/** Maps real TIS extractor output into canonical draft fields. */
export function mapTisToDraftPatch(data: TisImportData | null | undefined): ReturnDraftPatch {
  if (!data) return {};

  const entries = Object.values(data.income_heads || {}).flatMap((head) => head.entries || []);
  const employers: Employer[] = [];
  const interest: InterestIncome[] = [];
  const dividends: DividendIncome[] = [];
  const evidence = entries.flatMap((entry) => {
    const category = entry.category || entry.income_head || '';
    const control = createReconciliationEvidence({
      source: 'TIS', category, incomeHead: entry.income_head, description: category,
      evidenceKind: 'CATEGORY_CONTROL',
      reportedAmount: entry.processed_by_system, processedAmount: entry.processed_by_system,
      acceptedAmount: acceptedAmount(entry), raw: entry as unknown as Record<string, unknown>,
      identity: [entry.sr_no, category, 'category-control'],
    });
    const details = (entry.details || []).map((detail) => {
      const origin = source(detail.information_source);
      return createReconciliationEvidence({
        source: 'TIS', category, incomeHead: entry.income_head, description: detail.information_description,
        evidenceKind: 'SOURCE_DETAIL',
        sourceName: origin.name, sourceIdentifier: origin.tan || detail.institution_pan,
        reportedAmount: detail.reported_by_source, processedAmount: detail.processed_by_system,
        acceptedAmount: detail.accepted_by_taxpayer, raw: detail as unknown as Record<string, unknown>,
        identity: [entry.sr_no, detail.sr_no, category, origin.tan || detail.institution_pan],
      });
    });
    return [control, ...details];
  });

  for (const entry of entries) {
    const category = (entry.category || entry.income_head || '').trim().toLowerCase();
    const taxable = taxableDetails(entry);
    const entryAmount = acceptedAmount(entry);

    if (category.includes('salary')) {
      if (taxable.length > 0) {
        for (const detail of taxable) {
          const origin = source(detail.information_source);
          const amount = detailAmount(detail);
          employers.push(completeEmployer(
            origin.name,
            origin.tan,
            amount,
            `employer-${(origin.tan || origin.name || `tis-${entry.sr_no}`).trim().toUpperCase()}`,
          ));
        }
      } else if (entryAmount > 0) {
        employers.push(completeEmployer('TIS accepted salary total', '', entryAmount, 'tis-employer-total'));
      }
      continue;
    }

    const isSavings = category.includes('interest') && category.includes('saving');
    const isDeposit = category.includes('interest') && (
      category.includes('deposit') || category.includes('term') || category.includes('fixed')
    );
    if (isSavings || isDeposit) {
      const kind: InterestIncome['kind'] = isSavings ? 'SAVINGS_BANK' : 'TERM_DEPOSIT';
      if (taxable.length > 0) {
        for (const detail of taxable) {
          const origin = source(detail.information_source);
          const amount = detailAmount(detail);
          interest.push(interestRow(kind, amount, origin.name, origin.tan, detail.sr_no ?? entry.sr_no));
        }
      } else if (entryAmount > 0) {
        interest.push(interestRow(kind, entryAmount, 'TIS accepted total', '', entry.sr_no ?? category));
      }
      continue;
    }

    if (category.includes('dividend')) {
      if (taxable.length > 0) {
        for (const detail of taxable) {
          const origin = source(detail.information_source);
          const amount = detailAmount(detail);
          dividends.push(dividendRow(
            amount, origin.name, detail.institution_pan || '', origin.tan,
            detail.sr_no ?? entry.sr_no,
          ));
        }
      } else if (entryAmount > 0) {
        dividends.push(dividendRow(entryAmount, 'TIS accepted total', '', '', entry.sr_no ?? category));
      }
    }
  }

  // Backward-compatible support for the legacy summarized TIS shape.
  if (employers.length === 0 && numberValue(data.salaryAmount) > 0) {
    employers.push(completeEmployer('TIS accepted salary total', '', numberValue(data.salaryAmount), 'tis-employer-total'));
  }
  if (interest.length === 0 && numberValue(data.interestFromDeposit) > 0) {
    interest.push(interestRow('TERM_DEPOSIT', numberValue(data.interestFromDeposit), 'TIS accepted total', '', 'legacy-total'));
  }
  if (dividends.length === 0 && numberValue(data.dividendIncome) > 0) {
    dividends.push(dividendRow(numberValue(data.dividendIncome), 'TIS accepted total', '', '', 'legacy-total'));
  }

  return {
    employers,
    otherSources: { interest, dividends },
    provenance: [{ source: 'TIS', importedAt: new Date().toISOString(), reference: 'direct-import' }],
    reconciliation: { evidence, discrepancies: [] },
  };
}
