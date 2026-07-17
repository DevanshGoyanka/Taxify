import { stub } from './_stubs';

export const syncApi = {
  getStatus: async () => stub('/api/sync/status', {}),
  startSync: async () => stub('/api/sync/start', {}),
};
