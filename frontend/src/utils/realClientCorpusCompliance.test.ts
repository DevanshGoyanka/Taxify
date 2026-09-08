import { describe, expect, it } from 'vitest';

import { createEmptyReturnDraft } from '../domain/returns/factory';
import { mergeDraft } from '../domain/returns/draftPatch';
import { reconcileImportedEvidence } from '../domain/returns/reconciliation';
import { classifyAisEntry, classifyTisEntry } from '../domain/returns/sourceClassification';
import { mapAisToDraftPatch, type AisImportData } from './mapAisToDraftPatch';
import { mapTisToDraftPatch, type TisImportData } from './mapTisToDraftPatch';
import { map26asToDraftPatch, type Form26AsImportData } from './map26asToDraftPatch';

const aisModules = import.meta.glob('../../../ais_extractor/test_output/*_ais.json', { eager: true, import: 'default' }) as Record<string, AisImportData>;
const tisModules = import.meta.glob('../../../ais_extractor/test_output_tis/*_tis.json', { eager: true, import: 'default' }) as Record<string, TisImportData>;
const as26Modules = import.meta.glob('../../../ais_extractor/test_output_26as/*.json', { eager: true, import: 'default' }) as Record<string, Raw26AsDocument>;

interface Raw26AsDocument { header?: Record<string, unknown>; parts?: Record<string, { title?: string; credit?: boolean; rows?: Array<Record<string, unknown>> }>; }
interface TcsAggregate { collectorName?: string; collectorTAN?: string; sectionCode?: string; grossAmount?: number; taxCollected?: number; taxDeposited?: number; }
interface SourceRow { part?: string; rowIndex?: number; sectionCode?: string; title?: string; credit?: boolean; raw?: Record<string, unknown>; }
interface DeductorAggregate { sectionCode?: string; section?: string; employerName?: string; deductorName?: string; employerTAN?: string; deductorTAN?: string; deductorPAN?: string; totalAmount?: number; incomeAmount?: number; totalTDS?: number; tdsDeducted?: number; }

function anonymousKey(path: string): string {
  const filename = path.split('/').pop() || '';
  return filename.split('_')[0];
}

function num(value: unknown): number {
  const parsed = Number.parseFloat(String(value ?? '0').replace(/,/g, ''));
  return Number.isFinite(parsed) ? parsed : 0;
}

/** Minimal lossless adapter mirroring backend _map_legacy_26as sourceRows/tcsEntries. */
function normalize26as(raw: Raw26AsDocument): Form26AsImportData {
  const parts = raw.parts || {};
  const sourceRows: SourceRow[] = [];
  for (const [part, partData] of Object.entries(parts)) {
    for (const [index, row] of (partData.rows || []).entries()) {
      const details = (row._details as Array<Record<string, unknown>> | undefined) || [];
      const section = details.length ? String(details[0].Section || '') : '';
      sourceRows.push({ part, rowIndex: index, sectionCode: section, title: partData.title, credit: partData.credit, raw: row });
    }
  }
  const tcsEntries: TcsAggregate[] = (parts.VI?.rows || []).map((row) => ({
    collectorName: String(row['Name of Collector'] || ''),
    collectorTAN: String(row['TAN of Collector'] || ''),
    grossAmount: num(row['Total Amount Paid/Debited']),
    taxCollected: num(row['Total Tax Collected']),
    taxDeposited: num(row['Total TCS Deposited']),
  }));
  const deductorAggregates: DeductorAggregate[] = (parts.I?.rows || []).map((row) => ({
    sectionCode: String(((row._details as Array<Record<string, unknown>> | undefined)?.[0]?.Section) || '192'),
    employerName: String(row['Name of Deductor'] || ''),
    employerTAN: String(row['TAN of Deductor'] || ''),
    totalAmount: num(row['Total Amount Paid/Credited']),
    totalTDS: num(row['Total Tax Deducted']),
  }));
  return { financialYear: String(raw.header?.['Financial Year'] || ''), sourceRows, tcsEntries, deductorAggregates, tdsEntries: deductorAggregates };
}

function entriesOf(data: AisImportData): Array<Record<string, unknown>> {
  return Object.values(data.income_heads || {}).flatMap((head) => (head.entries || []) as unknown as Array<Record<string, unknown>>);
}

function tisEntriesOf(data: TisImportData): Array<Record<string, unknown>> {
  return Object.values(data.income_heads || {}).flatMap((head) => (head.entries || []) as unknown as Array<Record<string, unknown>>);
}

describe('real-client import corpus compliance', () => {
  const aisByKey = new Map(Object.entries(aisModules).map(([path, data]) => [anonymousKey(path), data]));
  const tisByKey = new Map(Object.entries(tisModules).map(([path, data]) => [anonymousKey(path), data]));
  const as26ByKey = new Map(Object.entries(as26Modules).map(([path, data]) => [anonymousKey(path), data]));
  const pairedKeys = [...aisByKey.keys()].filter((key) => tisByKey.has(key));
  const tripleKeys = pairedKeys.filter((key) => as26ByKey.has(key));

  it('loads at least 60 paired real-client AIS/TIS fixtures', () => {
    expect(pairedKeys.length).toBeGreaterThanOrEqual(60);
  });

  it('classifies every observed AIS code and TIS category without unknown loss', () => {
    const unknownAis = new Set<string>();
    const unknownTis = new Set<string>();
    for (const data of aisByKey.values()) {
      for (const row of entriesOf(data)) {
        const code = String(row.information_code || '');
        const category = String(row.category || '');
        if (classifyAisEntry(code, category).role === 'PARSER_WARNING') unknownAis.add(code || category || '<blank>');
      }
    }
    for (const data of tisByKey.values()) {
      for (const row of tisEntriesOf(data)) {
        const category = String(row.category || row.income_head || '');
        if (classifyTisEntry(category).role === 'PARSER_WARNING') unknownTis.add(category || '<blank>');
      }
    }
    expect([...unknownAis].sort()).toEqual([]);
    expect([...unknownTis].sort()).toEqual([]);
  });

  it('preserves every AIS entry and every TIS entry/detail as evidence', () => {
    for (const data of aisByKey.values()) {
      const sourceCount = entriesOf(data).length;
      const patch = mapAisToDraftPatch(data);
      expect(patch.reconciliation?.evidence?.length).toBe(sourceCount);
    }
    for (const data of tisByKey.values()) {
      const rows = tisEntriesOf(data);
      const sourceCount = rows.reduce((sum, row) => sum + 1 + (Array.isArray(row.details) ? row.details.length : 0), 0);
      const patch = mapTisToDraftPatch(data);
      expect(patch.reconciliation?.evidence?.length).toBe(sourceCount);
    }
  });

  it('preserves complete raw rows and deterministic evidence ids on reimport', () => {
    for (const data of aisByKey.values()) {
      const first = mapAisToDraftPatch(data).reconciliation?.evidence || [];
      const second = mapAisToDraftPatch(data).reconciliation?.evidence || [];
      expect(second.map((item) => item.id)).toEqual(first.map((item) => item.id));
      expect(second.map((item) => item.raw)).toEqual(first.map((item) => item.raw));
    }
  });

  it('preserves every 26AS part row as evidence and projects TCS credits', () => {
    expect(as26ByKey.size).toBeGreaterThanOrEqual(60);
    for (const raw of as26ByKey.values()) {
      const normalized = normalize26as(raw);
      const expectedRows = normalized.sourceRows?.length || 0;
      const patch = map26asToDraftPatch(normalized);
      expect(patch.reconciliation?.evidence?.length).toBe(expectedRows);
      expect(patch.taxes?.tcs?.length).toBe(normalized.tcsEntries?.length || 0);
    }
  });

  it('retains all AIS, TIS, and 26AS evidence after sequential import and emits explicit mismatches', () => {
    let mismatchCount = 0;
    for (const key of tripleKeys) {
      const aisPatch = mapAisToDraftPatch(aisByKey.get(key)!);
      const tisPatch = mapTisToDraftPatch(tisByKey.get(key)!);
      const as26Patch = map26asToDraftPatch(normalize26as(as26ByKey.get(key)!));
      let draft = createEmptyReturnDraft('2026-27');
      draft = mergeDraft(draft, as26Patch);
      draft = mergeDraft(draft, aisPatch);
      draft = mergeDraft(draft, tisPatch);
      const expectedEvidence = (as26Patch.reconciliation?.evidence?.length || 0) + (aisPatch.reconciliation?.evidence?.length || 0) + (tisPatch.reconciliation?.evidence?.length || 0);
      expect(draft.reconciliation.evidence).toHaveLength(expectedEvidence);
      const reconciled = reconcileImportedEvidence(draft);
      mismatchCount += reconciled.reconciliation.discrepancies.length;
      for (const discrepancy of reconciled.reconciliation.discrepancies) {
        expect(discrepancy.status).toBe('PENDING');
        expect(Math.abs(discrepancy.difference)).toBeGreaterThan(0);
      }
    }
    expect(mismatchCount).toBeGreaterThan(0);
  });

  it('preserves exact TIS accepted category controls', () => {
    for (const data of tisByKey.values()) {
      const patch = mapTisToDraftPatch(data);
      const controls = (patch.reconciliation?.evidence || []).filter((item) => item.source === 'TIS' && item.evidenceKind === 'CATEGORY_CONTROL');
      const sourceEntries = tisEntriesOf(data);
      expect(controls).toHaveLength(sourceEntries.length);
      for (const row of sourceEntries) {
        const category = String(row.category || row.income_head || '').toLowerCase();
        const expected = row.accepted_by_taxpayer !== undefined ? num(row.accepted_by_taxpayer) : num(row.processed_by_system);
        const control = controls.find((item) => (item.category || '').toLowerCase() === category);
        expect(control, `missing TIS control for ${category}`).toBeDefined();
        expect(control!.acceptedAmount).toBe(expected);
      }
    }
  });

  it('surfaces every cross-source TDS gap between 26AS and AIS as an explicit pending discrepancy', () => {
    let surfacedGaps = 0;
    for (const key of tripleKeys) {
      const ais = aisByKey.get(key)!;
      const as26 = normalize26as(as26ByKey.get(key)!);
      const aisPatch = mapAisToDraftPatch(ais);
      const as26Patch = map26asToDraftPatch(as26);
      let draft = createEmptyReturnDraft('2026-27');
      draft = mergeDraft(draft, as26Patch);
      draft = mergeDraft(draft, aisPatch);
      const aisTds = (aisPatch.taxes?.tds || []).reduce((sum, credit) => sum + (credit.taxDeducted || 0), 0);
      const as26Tds = (as26Patch.taxes?.tds || []).reduce((sum, credit) => sum + (credit.taxDeducted || 0), 0);
      const gap = Math.abs(aisTds - as26Tds);
      if (gap > 1) {
        // Any gap beyond rounding tolerance must be an explicit, decision-required
        // discrepancy — never a silent substitution or dropped row.
        const reconciled = reconcileImportedEvidence(draft);
        const pending = reconciled.reconciliation.discrepancies.filter((d) => d.status === 'PENDING' && Math.abs(d.difference) > 0);
        expect(pending.length).toBeGreaterThan(0);
        surfacedGaps += 1;
      }
    }
    // The corpus must produce at least one real cross-source gap; if zero,
    // the assertion is vacuous and cannot prove reconciliation coverage.
    expect(surfacedGaps).toBeGreaterThan(0);
  });
});
