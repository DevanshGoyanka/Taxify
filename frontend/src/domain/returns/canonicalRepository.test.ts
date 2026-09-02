import { beforeEach, describe, expect, it, vi } from 'vitest';
import axiosInstance from '../../api/axiosInstance';
import { createEmptyReturnDraft } from './factory';
import type { ReturnDraft } from './types';
import {
  CanonicalReturnRepository,
  assertCanonicalDraft,
  enforceAssessmentYear,
  normalizeLoadedDraft,
  stripCompatibility,
} from './canonicalRepository';

vi.mock('../../api/axiosInstance', () => ({ default: { get: vi.fn(), put: vi.fn(), post: vi.fn() } }));

describe('stripCompatibility', () => {
  it('removes top-level and nested compatibility keys without mutating the source', () => {
    const source = {
      schemaVersion: 1,
      assessmentYear: '2026-27',
      compatibility: { source: 'legacy-flat-v1', unknownFields: { a: 1 } },
      employers: [{ id: 'e', compatibility: { unknownFields: { b: 2 } }, employerName: 'Acme' }],
    } as unknown as ReturnType<typeof createEmptyReturnDraft>;
    const before = structuredClone(source);
    const result = stripCompatibility(source);
    expect((result as { compatibility?: unknown }).compatibility).toBeUndefined();
    expect((result as { employers: Array<{ compatibility?: unknown }> }).employers[0].compatibility).toBeUndefined();
    expect(source).toEqual(before);
  });

  it('strips compatibility from nested arrays of records', () => {
    const source = {
      schemaVersion: 1,
      assessmentYear: '2026-27',
      employers: [
        { id: 'a', compatibility: { unknownFields: { x: 9 } } },
        { id: 'b', compatibility: { unknownFields: { y: 8 } } },
      ],
    } as unknown as ReturnType<typeof createEmptyReturnDraft>;
    const result = stripCompatibility(source) as { employers: Array<{ compatibility?: unknown; id: string }> };
    expect(result.employers.every((e) => e.compatibility === undefined)).toBe(true);
    expect(result.employers.map((e) => e.id)).toEqual(['a', 'b']);
  });
});

describe('assertCanonicalDraft', () => {
  it('accepts an object carrying schemaVersion', () => {
    expect(() => assertCanonicalDraft({ schemaVersion: 1, assessmentYear: '2026-27' })).not.toThrow();
  });
  it('rejects non-objects', () => {
    expect(() => assertCanonicalDraft(null)).toThrow();
    expect(() => assertCanonicalDraft('nope')).toThrow();
  });
  it('rejects an object without schemaVersion (legacy flat blob)', () => {
    expect(() => assertCanonicalDraft({ form: 'ITR-1', name: 'A' })).toThrow();
  });
});

describe('enforceAssessmentYear', () => {
  it('stamps the requested year onto an empty assessmentYear', () => {
    const draft = createEmptyReturnDraft('', 'ITR-1', 'new');
    const result = enforceAssessmentYear(draft, '2026-27');
    expect(result.assessmentYear).toBe('2026-27');
  });
  it('returns the draft unchanged when the year already matches', () => {
    const draft = createEmptyReturnDraft('2026-27', 'ITR-1', 'new');
    expect(enforceAssessmentYear(draft, '2026-27').assessmentYear).toBe('2026-27');
  });
  it('throws when the draft year disagrees with the requested year', () => {
    const draft = createEmptyReturnDraft('2025-26', 'ITR-1', 'new');
    expect(() => enforceAssessmentYear(draft, '2026-27')).toThrow();
  });
});

describe('normalizeLoadedDraft', () => {
  it('backfills 80CCC detail rows for drafts saved before the field existed', () => {
    const draft = createEmptyReturnDraft('2026-27', 'ITR-1', 'old');
    delete (draft.deductions as Partial<typeof draft.deductions>).pensionContribution80CCC;
    expect(normalizeLoadedDraft(draft).deductions.pensionContribution80CCC).toEqual([]);
  });

  it('serializes additive schedules unchanged through the canonical payload boundary', () => {
    const draft = createEmptyReturnDraft('2026-27', 'ITR-2', 'new');
    draft.foreignAssets = [{ id: 'fa-1', assetType: 'BANK_ACCOUNT', countryCode: 'US', institutionOrEntityName: 'Bank', address: 'A', accountOrAssetIdentifier: '1', ownershipStatus: 'OWNER', openingOrAcquisitionDate: '2025-04-01', peakValue: 10, closingValue: 8, grossIncome: 0, incomeOffered: 0 }];
    const normalized = normalizeLoadedDraft(JSON.parse(JSON.stringify(draft)) as ReturnDraft);
    expect(JSON.parse(JSON.stringify(normalized)).foreignAssets).toEqual(draft.foreignAssets);
  });

  it('backfills every ITR-2 additive field without replacing existing values', () => {
    const draft = createEmptyReturnDraft('2026-27', 'ITR-2', 'new');
    draft.scheduleSIEntries = [{ id: 'si-1', section: '111', description: 'Dividend', grossIncome: 100, deductions: 0, taxRatePct: 10 }];
    const legacy = draft as unknown as Record<string, unknown>;
    for (const field of ['broughtForwardLossEntries', 'carriedForwardLossEntries', 'foreignSourceIncome', 'foreignTaxRelief', 'foreignAssets', 'clubbedIncome', 'passThroughIncomeEntries', 'amt', 'assetLiability', 'portugueseCivilCode', 'esopDeferrals']) delete legacy[field];
    const normalized = normalizeLoadedDraft(draft);
    expect(normalized.scheduleSIEntries).toEqual(draft.scheduleSIEntries);
    expect(normalized.broughtForwardLossEntries).toEqual([]);
    expect(normalized.carriedForwardLossEntries).toEqual([]);
    expect(normalized.foreignSourceIncome).toEqual([]);
    expect(normalized.foreignTaxRelief).toEqual([]);
    expect(normalized.foreignAssets).toEqual([]);
    expect(normalized.clubbedIncome).toEqual([]);
    expect(normalized.passThroughIncomeEntries).toEqual([]);
    expect(normalized.amt).toBeNull();
    expect(normalized.assetLiability).toBeNull();
    expect(normalized.portugueseCivilCode).toBeNull();
    expect(normalized.esopDeferrals).toEqual([]);
  });
});

describe('CanonicalReturnRepository', () => {
  beforeEach(() => vi.clearAllMocks());

  it('GET hits the canonical /v2 endpoint with encoded ids', async () => {
    vi.mocked(axiosInstance.get).mockResolvedValue({ data: createEmptyReturnDraft('2026-27', 'ITR-1', 'new') });
    const repo = new CanonicalReturnRepository();
    await repo.get('a/b', '2026-27');
    expect(axiosInstance.get).toHaveBeenCalledWith('/v2/clients/a%2Fb/itr/2026-27');
  });

  it('GET rejects a legacy flat blob without schemaVersion', async () => {
    vi.mocked(axiosInstance.get).mockResolvedValue({ data: { form: 'ITR-1', name: 'A' } });
    const repo = new CanonicalReturnRepository();
    await expect(repo.get('1', '2026-27')).rejects.toThrow();
  });

  it('PUT strips compatibility and posts typed JSON to the canonical /v2 endpoint', async () => {
    vi.mocked(axiosInstance.put).mockResolvedValue({ data: createEmptyReturnDraft('2026-27', 'ITR-4', 'old') });
    const draft = createEmptyReturnDraft('2026-27', 'ITR-4', 'old');
    (draft as unknown as { compatibility: unknown }).compatibility = { source: 'legacy-flat-v1', unknownFields: { legacy: true } };
    const repo = new CanonicalReturnRepository();
    await repo.save(7, draft);
    expect(axiosInstance.put).toHaveBeenCalledOnce();
    const args = vi.mocked(axiosInstance.put).mock.calls[0];
    expect(args[0]).toBe('/v2/clients/7/itr/2026-27');
    const payload = args[1] as { compatibility?: unknown; assessmentYear: string; form: string };
    expect(payload.compatibility).toBeUndefined();
    expect(payload.assessmentYear).toBe('2026-27');
    expect(payload.form).toBe('ITR-4');
  });

  it('PUT returns an independent clone that does not mutate the caller draft', async () => {
    const draft = createEmptyReturnDraft('2026-27', 'ITR-1', 'new');
    draft.personal.name = 'Asha';
    vi.mocked(axiosInstance.put).mockResolvedValue({ data: structuredClone(draft) });
    const result = await new CanonicalReturnRepository().save(7, draft);
    result.personal.name = 'Changed';
    expect(draft.personal.name).toBe('Asha');
  });
});
