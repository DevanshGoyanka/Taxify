import { beforeEach, describe, expect, it, vi } from 'vitest';
import axiosInstance from '../../api/axiosInstance';
import { itrV2 } from '../../api/itrV2';
import { createReturnRepository, isCanonicalV2Enabled } from './repositoryFactory';
import { CanonicalReturnRepository } from './canonicalRepository';
import { HttpReturnRepository } from './repository';
import { createEmptyReturnDraft } from './factory';

vi.mock('../../api/axiosInstance', () => ({ default: { get: vi.fn(), put: vi.fn(), post: vi.fn() } }));

describe('isCanonicalV2Enabled', () => {
  beforeEach(() => {
    vi.resetModules();
  });

  it('returns true when VITE_USE_V2 === "1"', () => {
    expect(isCanonicalV2Enabled({ VITE_USE_V2: '1' } as unknown as ImportMetaEnv)).toBe(true);
  });

  it('returns false when VITE_USE_V2 is unset or any other value', () => {
    expect(isCanonicalV2Enabled({} as unknown as ImportMetaEnv)).toBe(false);
    expect(isCanonicalV2Enabled({ VITE_USE_V2: '0' } as unknown as ImportMetaEnv)).toBe(false);
    expect(isCanonicalV2Enabled({ VITE_USE_V2: undefined } as unknown as ImportMetaEnv)).toBe(false);
  });
});

describe('createReturnRepository', () => {
  it('returns a CanonicalReturnRepository when VITE_USE_V2 === "1"', () => {
    expect(createReturnRepository({ VITE_USE_V2: '1' } as unknown as ImportMetaEnv)).toBeInstanceOf(CanonicalReturnRepository);
  });

  it('returns an HttpReturnRepository when the flag is off (legacy behavior)', () => {
    expect(createReturnRepository({} as unknown as ImportMetaEnv)).toBeInstanceOf(HttpReturnRepository);
  });
});

describe('itrV2 endpoint URLs', () => {
  beforeEach(() => vi.clearAllMocks());

  it('get encodes clientId and year into the /v2 clients itr path', async () => {
    vi.mocked(axiosInstance.get).mockResolvedValue({ data: createEmptyReturnDraft('2026-27', 'ITR-1', 'new') });
    await itrV2.get('a/b', '2026-27');
    expect(axiosInstance.get).toHaveBeenCalledWith('/v2/clients/a%2Fb/itr/2026-27');
  });

  it('put encodes the path and forwards the typed draft body', async () => {
    vi.mocked(axiosInstance.put).mockResolvedValue({ data: createEmptyReturnDraft('2026-27', 'ITR-1', 'new') });
    const draft = createEmptyReturnDraft('2026-27', 'ITR-1', 'new');
    await itrV2.put(7, '2026-27', draft);
    const args = vi.mocked(axiosInstance.put).mock.calls[0];
    expect(args[0]).toBe('/v2/clients/7/itr/2026-27');
    expect(args[1]).toBe(draft);
  });

  it('compute posts the draft to /v2/tax-summary/compute', async () => {
    vi.mocked(axiosInstance.post).mockResolvedValue({ data: { gti: 0 } });
    const draft = createEmptyReturnDraft('2026-27', 'ITR-1', 'new');
    await itrV2.compute(draft);
    const args = vi.mocked(axiosInstance.post).mock.calls[0];
    expect(args[0]).toBe('/v2/tax-summary/compute');
    expect(args[1]).toBe(draft);
  });

  it('generate posts to the v2 generate-cbdt-json endpoint with a blob response', async () => {
    const click = vi.fn();
    const remove = vi.fn();
    const appendChild = vi.fn(() => ({ click, remove }));
    const removeChild = vi.fn();
    vi.stubGlobal('document', { createElement: () => ({ click, remove }), body: { appendChild, removeChild } });
    vi.stubGlobal('URL', { createObjectURL: () => 'blob:url', revokeObjectURL: () => {} });
    try {
      vi.mocked(axiosInstance.post).mockResolvedValue({ data: new Blob(['{}']) });
      await itrV2.generate(42, '2026-27');
      const args = vi.mocked(axiosInstance.post).mock.calls[0];
      expect(args[0]).toBe('/v2/clients/42/itr/2026-27/generate-cbdt-json');
      expect(args[2]).toMatchObject({ responseType: 'blob' });
    } finally {
      vi.unstubAllGlobals();
    }
  });
});
