import axiosInstance from './axiosInstance';
import type {
  ClientListParams,
  ClientRecord,
  ClientUpsertPayload,
} from '../types/client.types';

export type ClientIdentifier = string | number;

export const clientsApi = {
  list: async (params?: ClientListParams): Promise<ClientRecord[]> => {
    const { data } = await axiosInstance.get<ClientRecord[]>('/clients', { params });
    return data;
  },
  get: async (id: ClientIdentifier): Promise<ClientRecord> => {
    const { data } = await axiosInstance.get<ClientRecord>(`/clients/${id}`);
    return data;
  },
  create: async (payload: ClientUpsertPayload): Promise<ClientRecord> => {
    const { data } = await axiosInstance.post<ClientRecord>('/clients', payload);
    return data;
  },
  update: async (id: ClientIdentifier, payload: Partial<ClientUpsertPayload>): Promise<ClientRecord> => {
    const { data } = await axiosInstance.put<ClientRecord>(`/clients/${id}`, payload);
    return data;
  },
  archive: async (id: ClientIdentifier): Promise<void> => {
    await axiosInstance.delete(`/clients/${id}`);
  },
  /** @deprecated Use archive; retained while older callers are migrated. */
  delete: async (id: ClientIdentifier): Promise<void> => {
    await axiosInstance.delete(`/clients/${id}`);
  },
  restore: async (id: ClientIdentifier): Promise<ClientRecord> => {
    const { data } = await axiosInstance.post<ClientRecord>(`/clients/${id}/restore`);
    return data;
  },
  getYears: async (id: ClientIdentifier): Promise<string[]> => {
    const { data } = await axiosInstance.get<string[]>(`/clients/${id}/years`);
    return data;
  },
  analyzepan: async (id: ClientIdentifier) => {
    const { data } = await axiosInstance.get(`/clients/${id}/pan-analysis`);
    return data;
  },
  classifyITR: async (id: ClientIdentifier, incomeProfile: Record<string, unknown>) => {
    const { data } = await axiosInstance.post(`/clients/${id}/itr-classification`, incomeProfile);
    return data;
  },
};
