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

function formatErrorValue(value: unknown): string {
  if (typeof value === 'string') return value;
  if (value === null || value === undefined) return '';
  if (typeof value === 'object') {
    const record = value as { field?: unknown; message?: unknown; msg?: unknown; detail?: unknown };
    const message = record.message ?? record.msg ?? record.detail;
    if (message !== undefined) {
      const prefix = record.field ? `${String(record.field)}: ` : '';
      return `${prefix}${formatErrorValue(message)}`;
    }
    try {
      return JSON.stringify(value);
    } catch {
      return 'Invalid structured error detail';
    }
  }
  return String(value);
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
    const errors = Array.isArray(record.errors)
      ? record.errors.map(formatErrorValue).filter(Boolean)
      : [];
    throw new CbdtGenerationError(formatErrorValue(record.message) || 'CBDT JSON generation failed', errors);
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

  /** Downloads the saved canonical draft as a typed JSON file. */
  async download(clientId: string | number, assessmentYear: string): Promise<void> {
    try {
      const response = await axiosInstance.get<Blob>(
        `/v2/clients/${encoded(clientId)}/itr/${encoded(assessmentYear)}/download`,
        { responseType: 'blob' },
      );
      const blob = response.data instanceof Blob ? response.data : new Blob([response.data]);
      const disposition = String(response.headers?.['content-disposition'] ?? '');
      const filename = extractFilename(disposition) ?? `ITR_${clientId}_${assessmentYear}.json`;
      downloadBlob(blob, filename);
    } catch (error: unknown) {
      await parseBlobError(error);
    }
  },

  /** Downloads a one-page PDF snapshot of the saved canonical draft. */
  async downloadPdf(clientId: string | number, assessmentYear: string): Promise<void> {
    try {
      const response = await axiosInstance.get<Blob>(
        `/v2/clients/${encoded(clientId)}/itr/${encoded(assessmentYear)}/download-pdf`,
        { responseType: 'blob' },
      );
      const blob = response.data instanceof Blob ? response.data : new Blob([response.data]);
      const disposition = String(response.headers?.['content-disposition'] ?? '');
      const filename = extractFilename(disposition) ?? `ITR_${clientId}_${assessmentYear}.pdf`;
      downloadBlob(blob, filename);
    } catch (error: unknown) {
      await parseBlobError(error);
    }
  },
};

/** Extract the filename from a Content-Disposition header value. */
function extractFilename(disposition: string): string | null {
  const match = disposition.match(/filename="?([^";]+)"?/i);
  return match ? match[1] : null;
}
