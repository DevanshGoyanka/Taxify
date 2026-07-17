import axiosInstance from './axiosInstance';

export const clientsApi = {
  list: async (params?: { search?: string; assessmentYear?: string; status?: string }) => {
    const { data } = await axiosInstance.get('/clients', { params });
    return data as any[];
  },
  get: async (id: number) => {
    const { data } = await axiosInstance.get(`/clients/${id}`);
    return data;
  },
  create: async (payload: any) => {
    const { data } = await axiosInstance.post('/clients', payload);
    return data;
  },
  update: async (id: number, payload: any) => {
    const { data } = await axiosInstance.put(`/clients/${id}`, payload);
    return data;
  },
  delete: async (id: number) => {
    await axiosInstance.delete(`/clients/${id}`);
  },
  getYears: async (id: number) => {
    const { data } = await axiosInstance.get(`/clients/${id}/years`);
    return data;
  },
  analyzepan: async (id: number) => {
    const { data } = await axiosInstance.get(`/clients/${id}/pan-analysis`);
    return data;
  },
  classifyITR: async (id: number, incomeProfile: any) => {
    const { data } = await axiosInstance.post(`/clients/${id}/itr-classification`, incomeProfile);
    return data;
  },
};
