import axiosInstance from './axiosInstance';
import type { AISData, Form26ASData, TISData, ReconciliationReport } from '../types/import.types';

const multipartPost = async (endpoint: string, file: File, params?: Record<string, string>) => {
  const fd = new FormData();
  fd.append('file', file);
  const { data } = await axiosInstance.post(endpoint, fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
    params,
  });
  return data;
};

export const integrationApi = {
  extractForm16: (file: File) => multipartPost('/integration/form16/extract', file),
  
  importAIS: async (file: File, clientId: number, assessmentYear: string, pan: string, dob: string): Promise<AISData> => {
    const fd = new FormData();
    fd.append('file', file);
    fd.append('client_id', clientId.toString());
    fd.append('assessment_year', assessmentYear);
    fd.append('pan', pan);
    fd.append('dob', dob);
    const { data } = await axiosInstance.post('/api/v1/imports/ais', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return data;
  },

  importAISJson: async (file: File, pan: string, dob: string): Promise<AISData> => {
    return multipartPost('/integration/ais-json/import', file, { pan, dob });
  },
  
  importTIS: async (file: File, pan: string, dob: string): Promise<TISData> => {
    return multipartPost('/integration/tis/import', file, { pan, dob });
  },
  
  import26AS: async (file: File, clientId: number, pan?: string, dob?: string, assessmentYear?: string): Promise<Form26ASData> => {
    const fd = new FormData();
    fd.append('file', file);
    fd.append('clientId', clientId.toString());
    if (pan) fd.append('pan', pan);
    if (dob) fd.append('dob', dob);
    if (assessmentYear) fd.append('assessmentYear', assessmentYear);
    const { data } = await axiosInstance.post('/integration/26as/import', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return data;
  },
  
  // Fixed: pass clientId and assessmentYear to backend for proper storage
  importITDPrefill: (file: File, clientId: number, assessmentYear: string) => {
    const fd = new FormData();
    fd.append('file', file);
    fd.append('clientId', clientId.toString());
    fd.append('assessmentYear', assessmentYear);
    return axiosInstance.post('/integration/prefill/import', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  
  autoPopulateFromForm16: async (itrData: any, form16Data: any) => {
    const { data } = await axiosInstance.post('/integration/autopopulate/form16', {
      formData: itrData,
      form16Data: form16Data
    });
    return data;
  },
  
  autoPopulateFromAIS: async (itrData: any, aisData: any) => {
    const { data } = await axiosInstance.post('/integration/autopopulate/ais', {
      formData: itrData,
      aisData: aisData
    });
    return data;
  },
  
  autoPopulateAll: async (
    clientId: number,
    year: string,
    aisData?: AISData,
    form26ASData?: Form26ASData,
    tisData?: TISData
  ) => {
    const { data } = await axiosInstance.post('/prefill/autoPopulateAll', {
      clientId,
      year,
      aisData,
      form26ASData,
      tisData,
      itrType: 'ITR-1'
    });
    return data;
  },
  
  getReconciliationReport: async (
    aisData: AISData,
    data26AS: Form26ASData,
    tisData?: TISData
  ): Promise<ReconciliationReport> => {
    const { data } = await axiosInstance.post('/integration/reconciliation', {
      aisData,
      data26AS,
      tisData
    });
    return data;
  },
  
  autoPopulateFromPrefill: async (itrData: any, prefillData: any) => {
    const { data } = await axiosInstance.post('/prefill/autopopulate', {
      formData: itrData,
      prefillData: prefillData
    });
    return data;
  },
};

