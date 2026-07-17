import axiosInstance from './axiosInstance';

export const documentsApi = {
  upload: async (file: File, clientId: number, assessmentYear: string, documentType: string) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('clientId', String(clientId));
    formData.append('assessmentYear', assessmentYear);
    formData.append('documentType', documentType);
    const { data } = await axiosInstance.post('/documents/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return data;
  },
  list: async (clientId: number, assessmentYear: string, documentType?: string) => {
    const { data } = await axiosInstance.get('/documents/list', {
      params: { clientId, assessmentYear, documentType },
    });
    return data as any[];
  },
  download: async (documentId: number, fileName: string) => {
    const res = await axiosInstance.get(`/documents/download/${documentId}`, { responseType: 'blob' });
    const url = URL.createObjectURL(new Blob([res.data]));
    const a = document.createElement('a');
    a.href = url; a.download = fileName;
    document.body.appendChild(a); a.click(); a.remove();
    URL.revokeObjectURL(url);
  },
  delete: async (documentId: number) => {
    await axiosInstance.delete(`/documents/${documentId}`);
  },
};
