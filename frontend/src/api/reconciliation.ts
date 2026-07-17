import { stub } from './_stubs';

export const reconciliationApi = {
  getStatus: async () => stub('/api/reconciliation', {}),
};
