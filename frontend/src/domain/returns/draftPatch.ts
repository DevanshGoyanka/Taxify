import type { Identified, ReturnDraft } from './types';

/** Recursively optional representation of a canonical return draft. */
export type DeepPartial<T> = T extends (...args: never[]) => unknown
  ? T
  : T extends readonly (infer U)[]
    ? Array<DeepPartial<U>>
    : T extends object
      ? { [K in keyof T]?: DeepPartial<T[K]> }
      : T;

/** A non-destructive update produced by an import mapper. */
export type ReturnDraftPatch = DeepPartial<ReturnDraft>;

function isObject(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function isIdentified(value: unknown): value is Identified {
  return isObject(value) && typeof value.id === 'string' && value.id.length > 0;
}

function isEmpty(value: unknown): boolean {
  return value === undefined || value === null || value === '' ||
    (Array.isArray(value) && value.length === 0);
}

function mergeArrays(base: unknown[], patch: unknown[]): unknown[] {
  if (patch.length === 0) return structuredClone(base);
  const identified = patch.every(isIdentified) && base.every(isIdentified);
  if (!identified) return structuredClone(patch);

  const incomingById = new Map(patch.map((item) => [item.id, item]));
  const result = base.map((item) => {
    const incoming = incomingById.get(item.id);
    if (!incoming) return structuredClone(item);
    incomingById.delete(item.id);
    return mergeValue(item, incoming);
  });
  for (const item of patch) {
    if (incomingById.has(item.id)) {
      result.push(structuredClone(item));
      incomingById.delete(item.id);
    }
  }
  return result;
}

function mergeValue(base: unknown, patch: unknown): unknown {
  if (isEmpty(patch)) return structuredClone(base);
  if (Array.isArray(patch)) return mergeArrays(Array.isArray(base) ? base : [], patch);
  if (isObject(patch)) {
    const result: Record<string, unknown> = isObject(base) ? structuredClone(base) : {};
    for (const key of Object.keys(patch).sort()) {
      result[key] = mergeValue(result[key], patch[key]);
    }
    return result;
  }
  return structuredClone(patch);
}

/**
 * Deeply merges an import patch into a canonical draft without mutation.
 *
 * Identified arrays merge by id in base order and append new incoming rows.
 * Empty scalar/array values preserve existing values; zero and false are data.
 *
 * @param base Existing canonical return draft.
 * @param patch Imported canonical patch.
 * @returns A detached, deterministic merged draft.
 */
export function mergeDraft(base: ReturnDraft, patch: ReturnDraftPatch | null | undefined): ReturnDraft {
  if (!patch) return structuredClone(base);
  return mergeValue(base, patch) as ReturnDraft;
}
