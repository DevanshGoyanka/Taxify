import axiosInstance from './axiosInstance';

export const filingApi = {
  list: async (filters?: { clientId?: number; assessmentYear?: string; status?: string }) => {
    const { data } = await axiosInstance.get('/filing', { params: filters });
    return data as any[];
  },
  create: async (payload: any) => {
    const { data } = await axiosInstance.post('/filing', payload);
    return data;
  },
  update: async (id: number, payload: any) => {
    const { data } = await axiosInstance.put(`/filing/${id}`, payload);
    return data;
  },
  delete: async (id: number) => {
    await axiosInstance.delete(`/filing/${id}`);
  },
};
