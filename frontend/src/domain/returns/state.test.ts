import { describe, expect, it } from 'vitest';
import {
  createReturnEditorState,
  returnEditorReducer,
  selectReturnComputationIsStale,
  selectReturnIsComputing,
  selectReturnIsDirty,
  selectReturnIsLoading,
  selectReturnIsSaving,
  type ReturnEditorState,
} from './state';

type Draft = Readonly<{ value: number }>;
type Result = Readonly<{ tax: number }>;

const reduce = (state: ReturnEditorState<Draft, Result>, action: Parameters<typeof returnEditorReducer<Draft, Result>>[1]): ReturnEditorState<Draft, Result> =>
  returnEditorReducer(state, action);

describe('return editor state', () => {
  it('starts synchronized and tracks edits immutably by revision', () => {
    const initial = createReturnEditorState<Draft, Result>({ value: 1 });
    const edited = reduce(initial, { type: 'edit', draft: { value: 2 } });

    expect(initial).toMatchObject({ draft: { value: 1 }, revision: 0, savedRevision: 0 });
    expect(edited).toMatchObject({ draft: { value: 2 }, revision: 1, savedRevision: 0 });
    expect(selectReturnIsDirty(initial)).toBe(false);
    expect(selectReturnIsDirty(edited)).toBe(true);
  });

  it('captures the save revision so edits made during a save remain dirty', () => {
    let state = reduce(createReturnEditorState<Draft, Result>({ value: 0 }), { type: 'edit', draft: { value: 1 } });
    state = reduce(state, { type: 'saveStarted', requestId: 'save-1' });
    expect(selectReturnIsSaving(state)).toBe(true);
    state = reduce(state, { type: 'edit', draft: { value: 2 } });
    state = reduce(state, { type: 'saveSucceeded', requestId: 'save-1' });

    expect(state).toMatchObject({ revision: 2, savedRevision: 1, save: null });
    expect(selectReturnIsDirty(state)).toBe(true);
  });

  it('marks the exact saved revision clean when no intervening edit occurs', () => {
    let state = reduce(createReturnEditorState<Draft, Result>({ value: 0 }), { type: 'edit', draft: { value: 1 } });
    state = reduce(state, { type: 'saveStarted', requestId: 1 });
    state = reduce(state, { type: 'saveSucceeded', requestId: 1 });

    expect(state.revision).toBe(state.savedRevision);
    expect(selectReturnIsDirty(state)).toBe(false);
  });

  it('ignores stale save success and failure', () => {
    let state = reduce(createReturnEditorState<Draft, Result>({ value: 0 }), { type: 'saveStarted', requestId: 1 });
    state = reduce(state, { type: 'saveStarted', requestId: 2 });
    const before = state;

    expect(reduce(state, { type: 'saveSucceeded', requestId: 1 })).toBe(before);
    expect(reduce(state, { type: 'saveFailed', requestId: 1, error: 'old' })).toBe(before);
    state = reduce(state, { type: 'saveFailed', requestId: 2, error: 'current' });
    expect(state.save).toMatchObject({ requestId: 2, error: 'current' });
    expect(selectReturnIsSaving(state)).toBe(false);
  });

  it('ignores stale load success and failure and accepts only the latest load', () => {
    let state = createReturnEditorState<Draft, Result>({ value: 0 });
    state = reduce(state, { type: 'loadStarted', requestId: 'old' });
    state = reduce(state, { type: 'loadStarted', requestId: 'new' });
    const current = state;

    expect(reduce(state, { type: 'loadSucceeded', requestId: 'old', draft: { value: 1 } })).toBe(current);
    expect(reduce(state, { type: 'loadFailed', requestId: 'old', error: 'old error' })).toBe(current);
    state = reduce(state, { type: 'loadSucceeded', requestId: 'new', draft: { value: 2 } });
    expect(state).toEqual(createReturnEditorState<Draft, Result>({ value: 2 }));
  });

  it('does not overwrite edits made while a load is pending', () => {
    let state = reduce(createReturnEditorState<Draft, Result>({ value: 0 }), { type: 'loadStarted', requestId: 'load' });
    state = reduce(state, { type: 'edit', draft: { value: 2 } });
    const edited = state;

    expect(reduce(state, { type: 'loadSucceeded', requestId: 'load', draft: { value: 1 } })).toBe(edited);
    expect(reduce(state, { type: 'loadFailed', requestId: 'load', error: 'late failure' })).toBe(edited);
  });

  it('retains a current load failure without treating it as pending', () => {
    let state = reduce(createReturnEditorState<Draft, Result>({ value: 0 }), { type: 'loadStarted', requestId: 1 });
    expect(selectReturnIsLoading(state)).toBe(true);
    state = reduce(state, { type: 'loadFailed', requestId: 1, error: 'offline' });
    expect(state.load).toEqual({ requestId: 1, revision: 0, error: 'offline' });
    expect(selectReturnIsLoading(state)).toBe(false);
  });

  it('new loads invalidate pending save and computation requests', () => {
    let state = reduce(createReturnEditorState<Draft, Result>({ value: 0 }), { type: 'saveStarted', requestId: 'save' });
    state = reduce(state, { type: 'computationStarted', requestId: 'compute' });
    state = reduce(state, { type: 'loadStarted', requestId: 'load' });

    expect(state.save).toBeNull();
    expect(state.computation).toBeNull();
    expect(reduce(state, { type: 'saveSucceeded', requestId: 'save' })).toBe(state);
    expect(reduce(state, { type: 'computationSucceeded', requestId: 'compute', result: { tax: 1 } })).toBe(state);
  });

  it('stores computation revision and reports results stale after an edit', () => {
    let state = reduce(createReturnEditorState<Draft, Result>({ value: 0 }), { type: 'computationStarted', requestId: 1 });
    expect(selectReturnIsComputing(state)).toBe(true);
    state = reduce(state, { type: 'computationSucceeded', requestId: 1, result: { tax: 25 } });
    expect(state.computation).toMatchObject({ revision: 0, result: { tax: 25 } });
    expect(selectReturnComputationIsStale(state)).toBe(false);
    state = reduce(state, { type: 'edit', draft: { value: 1 } });
    expect(selectReturnComputationIsStale(state)).toBe(true);
  });

  it('only lets the latest computation success, failure, and completion state win', () => {
    let state = reduce(createReturnEditorState<Draft, Result>({ value: 0 }), { type: 'computationStarted', requestId: 1 });
    state = reduce(state, { type: 'computationStarted', requestId: 2 });
    const latest = state;

    expect(reduce(state, { type: 'computationSucceeded', requestId: 1, result: { tax: 99 } })).toBe(latest);
    expect(reduce(state, { type: 'computationFailed', requestId: 1, error: 'old' })).toBe(latest);
    state = reduce(state, { type: 'computationFailed', requestId: 2, error: 'Unable to compute' });
    expect(state.computation).toMatchObject({ requestId: 2, result: null, error: 'Unable to compute' });
    expect(selectReturnIsComputing(state)).toBe(false);
  });
});
