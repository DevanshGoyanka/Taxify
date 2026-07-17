// Frontend Phase 2 - API hooks for rules and snapshots
// Document 1 §5.2, §8

import { useState, useEffect } from 'react';
import type { TaxYearRules, ComputedReturn } from '../types/phase2';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080/api';

export function useTaxYearRules(assessmentYear: string) {
  const [rules, setRules] = useState<TaxYearRules | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API_BASE}/rules/${assessmentYear}`)
      .then(res => res.json())
      .then(data => {
        setRules(data);
        setLoading(false);
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
      });
  }, [assessmentYear]);

  return { rules, loading, error };
}

export async function recordSnapshot(computedReturn: ComputedReturn): Promise<number> {
  const response = await fetch(`${API_BASE}/snapshots`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(computedReturn),
  });
  
  if (!response.ok) {
    throw new Error('Failed to record snapshot');
  }
  
  return response.json();
}
