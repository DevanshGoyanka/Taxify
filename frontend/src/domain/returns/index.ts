export * from './types';
export * from './factory';
export * from './legacyAdapter';
export * from './legacySerializer';
export * from './repository';
export * from './canonicalRepository';
export * from './repositoryFactory';
export * from './state';
export * from './editorModel';
export * from './tdsSections';

// ── CBDT eligibility & schedule registry ─────────────────────────────────────
export {
  type EligibilityFacts,
  type FormRecommendation,
  type ItrForm,
  assessFormEligibility,
  collectEligibilityFacts,
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
