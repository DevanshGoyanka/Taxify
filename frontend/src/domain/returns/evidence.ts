import type { ReconciliationEvidence } from './types';
import { classifySource, deterministicEvidenceId } from './sourceClassification';

export interface EvidenceInput {
  source: ReconciliationEvidence['source']; code?: string; section?: string; incomeHead?: string; category?: string;
  description?: string; sourceName?: string; sourceIdentifier?: string; reportedAmount?: unknown;
  processedAmount?: unknown; acceptedAmount?: unknown; taxAmount?: unknown; status?: string;
  evidenceKind?: ReconciliationEvidence['evidenceKind']; raw: Record<string, unknown>;
  identity?: unknown[];
}

const numeric = (value: unknown): number => {
  const parsed = Number.parseFloat(String(value ?? '0').replace(/,/g, ''));
  return Number.isFinite(parsed) ? parsed : 0;
};

/** Builds one classified, deterministic, raw-preserving evidence record. */
export function createReconciliationEvidence(input: EvidenceInput): ReconciliationEvidence {
  const classifierValue = input.source === 'TIS' ? input.category : input.code || input.section;
  const classification = input.source === 'ITD_PREFILL'
    ? { role: 'INFORMATIONAL' as const, relatedTab: 'RECONCILIATION' as const, category: input.category || input.code || 'prefill', canonicalDestination: undefined }
    : classifySource(input.source, classifierValue);
  const category = input.category || classification.category || '';
  const sourceCode = input.code || '';
  const sourceSection = input.section || '';
  const id = deterministicEvidenceId(input.source, ...(input.identity ?? [sourceCode, sourceSection, category, input.sourceIdentifier, input.raw]));
  return {
    id, source: input.source, sourceCode, sourceSection, incomeHead: input.incomeHead || '', category,
    description: input.description || '', sourceName: input.sourceName || '', sourceIdentifier: input.sourceIdentifier || '',
    role: classification.role, relatedTab: classification.relatedTab, canonicalDestination: classification.canonicalDestination,
    evidenceKind: input.evidenceKind || 'SOURCE_DETAIL',
    reportedAmount: numeric(input.reportedAmount), processedAmount: numeric(input.processedAmount), acceptedAmount: numeric(input.acceptedAmount), taxAmount: numeric(input.taxAmount),
    status: input.status || '', requiresReview: classification.role === 'PARSER_WARNING', raw: structuredClone(input.raw),
  };
}
