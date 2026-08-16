import axiosInstance from './axiosInstance';
import type { ReturnDraft } from '../domain/returns/types';

/** Tax summary returned by the canonical computation endpoint. */
export type CanonicalTaxSummary = Record<string, unknown>;

/** Error raised when canonical CBDT generation returns structured validation details. */
export class CbdtGenerationError extends Error {
  /** Backend validation errors associated with the generation failure. */
  public readonly errors: string[];

  /** Creates a canonical CBDT generation error. */
  public constructor(message: string, errors: string[] = []) {
    super(message);
    this.name = 'CbdtGenerationError';
    this.errors = errors;
  }
}

function encoded(value: string | number): string {
  return encodeURIComponent(String(value));
}

async function parseBlobError(error: unknown): Promise<never> {
  const responseData = (error as { response?: { data?: unknown } })?.response?.data;
  if (!(responseData instanceof Blob)) throw error;
  const text = await responseData.text();
  let body: unknown;
  try {
    body = JSON.parse(text);
  } catch {
    body = text;
  }
  const detail = body && typeof body === 'object' && 'detail' in body
    ? (body as { detail: unknown }).detail
    : body;
  if (detail && typeof detail === 'object') {
    const record = detail as { message?: unknown; errors?: unknown };
    const errors = Array.isArray(record.errors) ? record.errors.map(String) : [];
    throw new CbdtGenerationError(String(record.message ?? 'CBDT JSON generation failed'), errors);
  }
  throw new CbdtGenerationError(typeof detail === 'string' && detail ? detail : 'CBDT JSON generation failed');
}

function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

/** Typed API client for canonical v2 return operations. */
export const itrV2 = {
  /** Loads a canonical return draft. */
  async get(clientId: string | number, assessmentYear: string): Promise<ReturnDraft> {
    const { data } = await axiosInstance.get<ReturnDraft>(
      `/v2/clients/${encoded(clientId)}/itr/${encoded(assessmentYear)}`,
    );
    return data;
  },

  /** Saves a canonical return draft directly as typed JSON. */
  async put(clientId: string | number, assessmentYear: string, draft: ReturnDraft): Promise<ReturnDraft> {
    const { data } = await axiosInstance.put<ReturnDraft>(
      `/v2/clients/${encoded(clientId)}/itr/${encoded(assessmentYear)}`,
      draft,
    );
    return data;
  },

  /** Computes tax directly from a canonical return draft. */
  async compute(draft: ReturnDraft): Promise<CanonicalTaxSummary> {
    const { data } = await axiosInstance.post<CanonicalTaxSummary>('/v2/tax-summary/compute', draft);
    return data;
  },

  /** Generates and downloads CBDT JSON from the previously saved canonical draft. */
  async generate(clientId: string | number, assessmentYear: string): Promise<void> {
    try {
      const response = await axiosInstance.post<Blob>(
        `/v2/clients/${encoded(clientId)}/itr/${encoded(assessmentYear)}/generate-cbdt-json`,
        undefined,
        { responseType: 'blob' },
      );
      downloadBlob(
        response.data instanceof Blob ? response.data : new Blob([response.data]),
        `CBDT_${encoded(clientId)}_${assessmentYear}.json`,
      );
    } catch (error: unknown) {
      await parseBlobError(error);
    }
  },
};
