import { stub } from './_stubs';

export const billingApi = {
  list: async () => stub('/api/billing', []),
};
