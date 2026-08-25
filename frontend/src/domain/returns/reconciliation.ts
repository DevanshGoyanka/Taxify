import type { ReconciliationDiscrepancy, ReconciliationEvidence, ReturnDraft } from './types';
import { deterministicEvidenceId } from './sourceClassification';

const comparable = (item: ReconciliationEvidence): boolean => !['CONTROL_ONLY', 'ACQUISITION_ONLY', 'INFORMATIONAL', 'PARSER_WARNING', 'TAX_CREDIT'].includes(item.role);
const amount = (item: ReconciliationEvidence): number => item.acceptedAmount || item.processedAmount || item.reportedAmount || 0;
const rounded = (value: number): number => Math.round((value + Number.EPSILON) * 100) / 100;
const TDS_TOLERANCE = 1;

/** Rebuilds AIS-vs-TIS and 26AS-vs-AIS discrepancies while preserving unchanged decisions. */
export function reconcileImportedEvidence(draft: ReturnDraft): ReturnDraft {
  const evidence = draft.reconciliation?.evidence ?? [];
  const ais = evidence.filter((item) => item.source === 'AIS' && item.evidenceKind === 'SOURCE_DETAIL' && comparable(item));
  const tis = evidence.filter((item) => item.source === 'TIS' && item.evidenceKind === 'CATEGORY_CONTROL' && comparable(item));
  const categories = [...new Set(tis.map((item) => item.category.toLowerCase()))].sort();
  const previous = new Map((draft.reconciliation?.discrepancies ?? []).map((item) => [item.id, item]));
  const discrepancies: ReconciliationDiscrepancy[] = [];
  for (const category of categories) {
    const matchingAis = ais.filter((item) => item.category.toLowerCase() === category);
    if (matchingAis.length === 0) continue;
    const aisAmount = rounded(matchingAis.reduce((sum, item) => sum + amount(item), 0));
    const tisAcceptedAmount = rounded(tis.filter((item) => item.category.toLowerCase() === category).reduce((sum, item) => sum + amount(item), 0));
    const difference = rounded(aisAmount - tisAcceptedAmount);
    if (difference === 0) continue;
    const as26Amount = rounded(evidence.filter((item) => item.source === '26AS' && item.category.toLowerCase() === category).reduce((sum, item) => sum + amount(item), 0));
    const id = deterministicEvidenceId('reconciliation', category);
    const old = previous.get(id);
    const unchanged = old && old.aisAmount === aisAmount && old.tisAcceptedAmount === tisAcceptedAmount && old.as26Amount === as26Amount;
    discrepancies.push({ id, category, description: `AIS and TIS accepted amounts differ for ${category}.`, aisAmount, tisAcceptedAmount, as26Amount, difference, status: unchanged ? old.status : 'PENDING' });
  }

  // Cross-source TDS reconciliation: 26AS tax-credit totals must match AIS B1
  // TDS totals for the same deductor+section. Any gap beyond rounding tolerance
  // is surfaced as an explicit, decision-required discrepancy.
  const aisTds = ais.filter((item) => item.taxAmount > 0);
  const as26Rows = evidence.filter((item) => item.source === '26AS' && item.taxAmount > 0);
  const tdsKeys = new Set<string>([
    ...aisTds.map((item) => `${(item.sourceIdentifier || '').toUpperCase()}|${(item.sourceCode || '').toUpperCase()}`),
    ...as26Rows.map((item) => `${(item.sourceIdentifier || '').toUpperCase()}|${(item.sourceCode || '').toUpperCase()}`),
  ]);
  for (const key of [...tdsKeys].sort()) {
    const [tan, section] = key.split('|');
    const aisTotal = rounded(aisTds.filter((item) => (item.sourceIdentifier || '').toUpperCase() === tan && (item.sourceCode || '').toUpperCase() === section).reduce((sum, item) => sum + item.taxAmount, 0));
    const as26Total = rounded(as26Rows.filter((item) => (item.sourceIdentifier || '').toUpperCase() === tan && (item.sourceCode || '').toUpperCase() === section).reduce((sum, item) => sum + item.taxAmount, 0));
    const difference = rounded(aisTotal - as26Total);
    if (Math.abs(difference) <= TDS_TOLERANCE) continue;
    const id = deterministicEvidenceId('reconciliation-tds', key);
    const old = previous.get(id);
    const unchanged = old && old.aisAmount === aisTotal && old.as26Amount === as26Total;
    discrepancies.push({ id, category: `TDS ${section} ${tan}`, description: `26AS and AIS TDS totals differ for ${section} (${tan}).`, aisAmount: aisTotal, tisAcceptedAmount: 0, as26Amount: as26Total, difference, status: unchanged ? old.status : 'PENDING' });
  }

  return { ...structuredClone(draft), reconciliation: { evidence: structuredClone(evidence), discrepancies } };
}
