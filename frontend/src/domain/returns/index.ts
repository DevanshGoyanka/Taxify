export * from './types';
export * from './factory';
export * from './legacyAdapter';
export * from './legacySerializer';
export * from './repository';
export * from './canonicalRepository';
export * from './repositoryFactory';
export * from './state';
export * from './editorModel';
export * as editorModelV2 from './editorModelV2';
export type { ReturnEditorModelV2, DraftUpdater } from './editorModelV2';
export * from './draftPatch';
export * from './tdsSections';
export * from './sourceClassification';
export * from './evidence';
export * from './reconciliation';

// ── CBDT eligibility & schedule registry ─────────────────────────────────────
export {
  type EligibilityFacts,
  type FormRecommendation,
  type ItrForm,
  assessFormEligibility,
  assessFormEligibilityFromDraft,
  collectEligibilityFacts,
  collectEligibilityFactsFromDraft,
  evaluateEligibility,
} from '../eligibility';

export {
  type ScheduleDefinition,
  type ScheduleStatus,
  SCHEDULE_REGISTRY,
  activeSchedules,
  blockingSchedules,
  getSchedule,
  schedulesForForm,
} from '../scheduleRegistry';
