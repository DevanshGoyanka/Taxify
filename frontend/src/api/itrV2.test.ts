import { beforeEach, describe, expect, it, vi } from 'vitest';
import { CbdtGenerationError, itrV2 } from './itrV2';
import axiosInstance from './axiosInstance';

const post = vi.spyOn(axiosInstance, 'post');

describe('itrV2 CBDT generation errors', () => {
  beforeEach(() => {
    post.mockReset();
    vi.stubGlobal('localStorage', {
      getItem: vi.fn(() => null),
      setItem: vi.fn(),
      removeItem: vi.fn(),
      clear: vi.fn(),
    });
    vi.stubGlobal('window', {
      location: { href: '' },
    });
  });

  it('preserves backend validation details from blob error responses', async () => {
    const detail = {
      message: 'ITR-4 CBDT Category A input validation failed.',
      errors: [
        '44AD: income declared (Rs 20000) < 6% of digital turnover (Rs 30000.00)',
      ],
    };
    const blob = new Blob([JSON.stringify({ detail })], { type: 'application/json' });
    post.mockRejectedValue({
      config: { responseType: 'blob' },
      response: { data: blob, status: 422 },
    });

    const request = itrV2.generate('client-1', '2026-27');

    await expect(request).rejects.toMatchObject({
      name: 'CbdtGenerationError',
      message: detail.message,
      errors: detail.errors,
    } satisfies Partial<CbdtGenerationError>);
  });

  it('preserves structured validation objects instead of showing object text', async () => {
    const detail = {
      message: 'ITR-4 CBDT Category A input validation failed.',
      errors: [{ field: '44AD', message: 'Income is below the statutory minimum.' }],
    };
    const blob = new Blob([JSON.stringify({ detail })], { type: 'application/json' });
    post.mockRejectedValue({
      config: { responseType: 'blob' },
      response: { data: blob, status: 422 },
    });

    await expect(itrV2.generate('client-1', '2026-27')).rejects.toMatchObject({
      errors: ['44AD: Income is below the statutory minimum.'],
    });
  });
});
