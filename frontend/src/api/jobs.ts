import { stub } from './_stubs';

export const jobsApi = {
  list: async () => stub('/api/jobs', []),
};
