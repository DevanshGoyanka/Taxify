import { CanonicalReturnRepository } from './canonicalRepository';
import { HttpReturnRepository, type ReturnRepository } from './repository';

/** Returns whether canonical v2 persistence/computation is enabled. */
export function isCanonicalV2Enabled(env: ImportMetaEnv = import.meta.env): boolean {
  return env.VITE_USE_V2 === '1';
}

/** Creates the appropriate return repository for the supplied feature flags. */
export function createReturnRepository(env: ImportMetaEnv = import.meta.env): ReturnRepository {
  return isCanonicalV2Enabled(env) ? new CanonicalReturnRepository() : new HttpReturnRepository();
}
