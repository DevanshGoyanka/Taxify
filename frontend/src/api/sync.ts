// FUTURE FEATURE — scaffolded but not yet wired into the app.
// Confirmed absent from App.tsx's route table and not imported by anything
// (full-codebase dead-code audit, 2026-09-05). Kept deliberately, not
// dead code to remove — see Docs/CODEBASE_DEAD_CODE_AUDIT_2026_09.md for
// the full list of what this belongs to and why it was kept.
import { stub } from './_stubs';

export const syncApi = {
  getStatus: async () => stub('/api/sync/status', {}),
  startSync: async () => stub('/api/sync/start', {}),
};
