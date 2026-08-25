export type ReturnEditorRequestId = string | number;

/** Tracks a normalized return draft and its asynchronous editor operations. */
export interface ReturnEditorState<TDraft, TComputation = unknown> {
  readonly draft: TDraft;
  readonly revision: number;
  readonly savedRevision: number;
  readonly load: Readonly<{ requestId: ReturnEditorRequestId; revision: number; error: string | null }> | null;
  readonly save: Readonly<{ requestId: ReturnEditorRequestId; revision: number; error: string | null }> | null;
  readonly computation: Readonly<{
    requestId: ReturnEditorRequestId;
    revision: number;
    result: TComputation | null;
    error: string | null;
  }> | null;
}

export type ReturnEditorAction<TDraft, TComputation = unknown> =
  | Readonly<{ type: 'edit'; draft: TDraft }>
  | Readonly<{ type: 'loadStarted'; requestId: ReturnEditorRequestId }>
  | Readonly<{ type: 'loadSucceeded'; requestId: ReturnEditorRequestId; draft: TDraft }>
  | Readonly<{ type: 'loadFailed'; requestId: ReturnEditorRequestId; error: string }>
  | Readonly<{ type: 'saveStarted'; requestId: ReturnEditorRequestId }>
  | Readonly<{ type: 'saveSucceeded'; requestId: ReturnEditorRequestId }>
  | Readonly<{ type: 'saveFailed'; requestId: ReturnEditorRequestId; error: string }>
  | Readonly<{ type: 'computationStarted'; requestId: ReturnEditorRequestId }>
  | Readonly<{ type: 'computationSucceeded'; requestId: ReturnEditorRequestId; result: TComputation }>
  | Readonly<{ type: 'computationFailed'; requestId: ReturnEditorRequestId; error: string }>;

/** Creates editor state for an initial, already-synchronized draft. */
export function createReturnEditorState<TDraft, TComputation = unknown>(draft: TDraft): ReturnEditorState<TDraft, TComputation> {
  return { draft, revision: 0, savedRevision: 0, load: null, save: null, computation: null };
}

/** Applies an immutable editor transition while rejecting stale asynchronous completions. */
export function returnEditorReducer<TDraft, TComputation = unknown>(
  state: ReturnEditorState<TDraft, TComputation>,
  action: ReturnEditorAction<TDraft, TComputation>,
): ReturnEditorState<TDraft, TComputation> {
  switch (action.type) {
    case 'edit':
      return { ...state, draft: action.draft, revision: state.revision + 1 };
    case 'loadStarted':
      return {
        ...state,
        load: { requestId: action.requestId, revision: state.revision, error: null },
        save: null,
        computation: null,
      };
    case 'loadSucceeded':
      if (state.load?.requestId !== action.requestId || state.load.revision !== state.revision) return state;
      return {
        draft: action.draft,
        revision: 0,
        savedRevision: 0,
        load: null,
        save: null,
        computation: null,
      };
    case 'loadFailed':
      if (state.load?.requestId !== action.requestId || state.load.revision !== state.revision) return state;
      return { ...state, load: { requestId: action.requestId, revision: state.load.revision, error: action.error } };
    case 'saveStarted':
      return { ...state, save: { requestId: action.requestId, revision: state.revision, error: null } };
    case 'saveSucceeded':
      if (state.save?.requestId !== action.requestId) return state;
      return { ...state, savedRevision: state.save.revision, save: null };
    case 'saveFailed':
      if (state.save?.requestId !== action.requestId) return state;
      return { ...state, save: { ...state.save, error: action.error } };
    case 'computationStarted':
      return {
        ...state,
        computation: {
          requestId: action.requestId,
          revision: state.revision,
          result: null,
          error: null,
        },
      };
    case 'computationSucceeded':
      if (state.computation?.requestId !== action.requestId) return state;
      return { ...state, computation: { ...state.computation, result: action.result, error: null } };
    case 'computationFailed':
      if (state.computation?.requestId !== action.requestId) return state;
      return { ...state, computation: { ...state.computation, result: null, error: action.error } };
  }
}

/** Returns whether the current draft contains edits not covered by the last successful save. */
export function selectReturnIsDirty<TDraft, TComputation>(state: ReturnEditorState<TDraft, TComputation>): boolean {
  return state.revision !== state.savedRevision;
}

/** Returns whether the current computation was made for an older draft revision. */
export function selectReturnComputationIsStale<TDraft, TComputation>(state: ReturnEditorState<TDraft, TComputation>): boolean {
  return state.computation !== null && state.computation.revision !== state.revision;
}

/** Returns whether a load request is currently pending. */
export function selectReturnIsLoading<TDraft, TComputation>(state: ReturnEditorState<TDraft, TComputation>): boolean {
  return state.load !== null && state.load.error === null;
}

/** Returns whether a save request is currently pending. */
export function selectReturnIsSaving<TDraft, TComputation>(state: ReturnEditorState<TDraft, TComputation>): boolean {
  return state.save !== null && state.save.error === null;
}

/** Returns whether a computation request is currently pending. */
export function selectReturnIsComputing<TDraft, TComputation>(state: ReturnEditorState<TDraft, TComputation>): boolean {
  return state.computation !== null && state.computation.result === null && state.computation.error === null;
}
