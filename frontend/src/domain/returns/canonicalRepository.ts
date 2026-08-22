import type { PersonalInfo, ReturnDraft } from './types';
import { itrV2 } from '../../api/itrV2';

/** Persistence boundary for the canonical income-tax return draft. */
export interface ReturnRepository {
  /** Loads and normalizes a saved draft. */
  get(clientId: string | number, assessmentYear: string): Promise<ReturnDraft>;
  /** Persists a normalized draft and returns the backend's normalized response. */
  save(clientId: string | number, draft: ReturnDraft): Promise<ReturnDraft>;
}

/**
 * Deep-clones a value and removes every `compatibility` key recursively
 * (objects) and at the top level, so the resulting JSON is acceptable to a
 * backend schema that uses `extra="forbid"`.
 *
 * The function never mutates the input; a fresh structure is returned.
 */
export function stripCompatibility<T>(value: T): T {
  return stripInternal(structuredClone(value)) as T;
}

/** Internal recursive walker. Mutates only the freshly-cloned tree. */
function stripInternal(value: unknown): unknown {
  if (Array.isArray(value)) {
    for (let index = 0; index < value.length; index += 1) {
      value[index] = stripInternal(value[index]) as unknown;
    }
    return value;
  }
  if (isPlainObject(value)) {
    const record = value as Record<string, unknown>;
    if (Object.prototype.hasOwnProperty.call(record, 'compatibility')) {
      delete record.compatibility;
    }
    for (const key of Object.keys(record)) {
      record[key] = stripInternal(record[key]);
    }
  }
  return value;
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && Object.getPrototypeOf(value) === Object.prototype;
}

/** Minimal empty personal info used when seeding a fresh canonical draft. */
export function createEmptyPersonalInfo(): PersonalInfo {
  return {
    name: '', firstName: '', middleName: '', surnameOrOrgName: '', fatherName: '',
    pan: '', aadhaar: '', email: '', mobile: '',
    secondaryEmail: '', secondaryMobile: '', secondaryMobileCountryCode: '',
    dateOfBirth: null,
    flatNo: '', residenceName: '', roadOrStreet: '', localityOrArea: '',
    city: '', stateCode: '', countryCode: '91', pinCode: '', zipCode: '',
    employerCategory: '',
  };
}

/**
 * Defensive minimal validator for a canonical draft response.
 *
 * Throws when the response is not a plain object or lacks the canonical
 * `schemaVersion` marker.  Does NOT enforce the full Pydantic schema — the
 * backend is authoritative there.  This guard catches obvious shape drift
 * (e.g. a legacy flat blob served by mistake) before it reaches the editor.
 */
export function assertCanonicalDraft(value: unknown): asserts value is ReturnDraft {
  if (!isPlainObject(value)) {
    throw new Error('Canonical return response is not a JSON object.');
  }
  const record = value as Record<string, unknown>;
  if (record.schemaVersion === undefined || record.schemaVersion === null) {
    throw new Error('Canonical return response is missing schemaVersion.');
  }
}

/**
 * Enforces that the draft's assessment year matches the requested year.
 *
 * Mirrors the backend guard in `save_client_itr_v2`, which rejects a draft
 * whose `assessmentYear` differs from the URL year with HTTP 422.  When the
 * draft has no assessment year (a freshly-seeded empty draft), the requested
 * year is stamped onto it so it can be persisted.
 */
export function enforceAssessmentYear(draft: ReturnDraft, assessmentYear: string): ReturnDraft {
  if (draft.assessmentYear && draft.assessmentYear !== assessmentYear) {
    throw new Error(
      `Draft assessmentYear (${draft.assessmentYear}) does not match the requested year (${assessmentYear}).`,
    );
  }
  return { ...draft, assessmentYear };
}

/** Canonical repository backed by direct typed `/v2` JSON endpoints. */
export class CanonicalReturnRepository implements ReturnRepository {
  /** Loads a typed canonical draft and verifies its assessment year. */
  public async get(clientId: string | number, assessmentYear: string): Promise<ReturnDraft> {
    const response: unknown = await itrV2.get(clientId, assessmentYear);
    assertCanonicalDraft(response);
    return enforceAssessmentYear(structuredClone(response), assessmentYear);
  }

  /** Saves a compatibility-free typed draft and validates the typed response. */
  public async save(clientId: string | number, draft: ReturnDraft): Promise<ReturnDraft> {
    if (!draft.assessmentYear) {
      throw new Error('Canonical return draft requires an assessmentYear before save.');
    }
    const payload = stripCompatibility(enforceAssessmentYear(draft, draft.assessmentYear));
    const response: unknown = await itrV2.put(clientId, payload.assessmentYear, payload);
    assertCanonicalDraft(response);
    return enforceAssessmentYear(structuredClone(response), payload.assessmentYear);
  }
}

/** Returns the singleton canonical repository. Phase 8 retired the legacy
 *  flat-blob repository and the `VITE_USE_V2` flag; the v2 endpoints are now
 *  the only path. */
export function createReturnRepository(): ReturnRepository {
  return new CanonicalReturnRepository();
}
