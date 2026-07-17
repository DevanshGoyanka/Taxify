import { stub } from './_stubs';

export const noticesApi = {
  list: async () => stub('/api/notices', []),
};
