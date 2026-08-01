import axiosInstance from '../../api/axiosInstance';
import { adaptLegacyReturn } from './legacyAdapter';
import { serializeReturnDraftToLegacy } from './legacySerializer';
import type { ReturnDraft } from './types';

/** Persistence boundary for normalized income-tax returns. */
export interface ReturnRepository {
  /** Loads and normalizes a saved draft. */
  get(clientId: string | number, assessmentYear: string): Promise<ReturnDraft>;
  /** Persists a normalized draft and returns the backend's normalized response. */
  save(clientId: string | number, draft: ReturnDraft): Promise<ReturnDraft>;
}

/** HTTP repository backed by the existing authenticated Axios instance. */
export class HttpReturnRepository implements ReturnRepository {
  /** Loads a return through the legacy endpoint. */
  public async get(clientId: string | number, assessmentYear: string): Promise<ReturnDraft> {
    const { data } = await axiosInstance.get<unknown>(`/clients/${encodeURIComponent(String(clientId))}/itr/${encodeURIComponent(assessmentYear)}`);
    const draft = adaptLegacyReturn(data);
    if (!draft.assessmentYear) draft.assessmentYear = assessmentYear;
    return draft;
  }

  /** Saves a return through the compatibility serializer and returns a normalized clone of the submission. */
  public async save(clientId: string | number, draft: ReturnDraft): Promise<ReturnDraft> {
    const payload = serializeReturnDraftToLegacy(draft);
    await axiosInstance.put<unknown>(
      `/clients/${encodeURIComponent(String(clientId))}/itr/${encodeURIComponent(draft.assessmentYear)}`,
      payload,
    );
    return adaptLegacyReturn(payload);
  }
}
