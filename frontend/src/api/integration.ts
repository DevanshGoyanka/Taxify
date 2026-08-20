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

  /**
   * Server-side reconcile (P6 fix): loads the persisted import set for the
   * client+AY from `imported_document` and reconciles on the backend. This
   * avoids silent TDS/TCS credit loss when the frontend's in-memory state
   * is dropped (page refresh) between upload and reconcile. Prefer this over
   * `getReconciliationReport` whenever a clientId+assessmentYear is available.
   */
  getReconciliationReportFromServer: async (
    clientId: number,
    assessmentYear: string
  ): Promise<ReconciliationReport> => {
    const { data } = await axiosInstance.get(
      `/integration/reconciliation/client/${clientId}`,
      { params: { assessmentYear } }
    );
    return data;
  },
};

