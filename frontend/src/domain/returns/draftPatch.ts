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

  // Identified rows merge by id in base order; new incoming ids append.
  // UNIDENTIFIED rows are append-only: an incoming blank-id row never
  // matches or overwrites an existing row, so a second import (e.g. AIS
  // after 26AS) cannot wipe rows that lack a stable id. Only a row whose
  // id matches an existing one is treated as an update.
  const incomingById = new Map<string, unknown>();
  for (const item of patch) {
    if (isIdentified(item)) {
      incomingById.set(item.id, item);
    }
  }
  // Arrays whose incoming rows have no stable ids (for example provenance)
  // retain ordinary replacement semantics.
  if (incomingById.size === 0) return structuredClone(patch);

  const result: unknown[] = [];
  const consumedIds = new Set<string>();
  for (const item of base) {
    if (isIdentified(item) && incomingById.has(item.id)) {
      consumedIds.add(item.id);
      result.push(mergeValue(item, incomingById.get(item.id)));
    } else {
      result.push(structuredClone(item));
    }
  }

  // Append every incoming row whose id did not match a base row. This
  // includes identified rows with new ids and all unidentified rows.
  for (const item of patch) {
    if (isIdentified(item)) {
      if (!consumedIds.has(item.id)) {
        // Use the map value so duplicate ids within the patch resolve
        // deterministically to the final incoming row and append once.
        result.push(structuredClone(incomingById.get(item.id)));
        consumedIds.add(item.id);
      }
    } else {
      result.push(structuredClone(item));
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
