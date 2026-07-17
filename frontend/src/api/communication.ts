import { stub } from './_stubs';

export const communicationApi = {
  list: async () => stub('/api/communication', []),
};
