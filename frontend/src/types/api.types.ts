export interface ClientRequest {
  pan: string;
  name: string;
  email?: string;
  mobile?: string;
  aadhaar?: string;
  dob?: string;
}

export interface YearStatus {
  year: string;
  status: string;
  itrType: string;
}

export interface ClientResponse {
  id: number;
  pan: string;
  name: string;
  email: string;
  mobile: string;
  aadhaar: string;
  dob: string;
  years: YearStatus[];
}

export interface FilingRequest {
  clientId: number;
  assessmentYear: string;
  itrType: string;
  status: string;
  filingDate?: string;
  acknowledgementNumber?: string;
}

export interface FilingResponse extends FilingRequest {
  id: number;
  clientName: string;
  clientPan: string;
  totalIncome?: number;
  taxPayable?: number;
  refundAmount?: number;
  createdAt: string;
  updatedAt: string;
}

export interface DocumentMetadata {
  id: number;
  clientId: number;
  assessmentYear: string;
  documentType: string;
  fileName: string;
  fileSize: number;
  uploadedAt: string;
  url?: string;
}
