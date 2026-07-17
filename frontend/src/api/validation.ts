// Frontend Phase 3 - Validation API hooks
// Document 3 Phase 3

import { useState } from 'react';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080/api/v1';

export interface ValidationResult {
  passed: boolean;
  severity: 'BLOCKING' | 'WARNING';
  validatorName: string;
  fieldReference?: string;
  message: string;
  itdErrorCode?: string;
}

export interface ValidationReport {
  clientId: number;
  assessmentYear: string;
  validatedAt: string;
  results: ValidationResult[];
  blockingCount: number;
  warningCount: number;
}

export async function validateDraft(clientId: number, assessmentYear: string): Promise<ValidationReport> {
  const response = await fetch(
    `${API_BASE}/clients/${clientId}/validate/${assessmentYear}`,
    { method: 'POST' }
  );
  
  if (!response.ok) {
    throw new Error('Validation failed');
  }
  
  return response.json();
}

export function useValidation() {
  const [validating, setValidating] = useState(false);
  const [report, setReport] = useState<ValidationReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  const validate = async (clientId: number, assessmentYear: string) => {
    setValidating(true);
    setError(null);
    
    try {
      const result = await validateDraft(clientId, assessmentYear);
      setReport(result);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setValidating(false);
    }
  };

  return { validate, validating, report, error };
}
