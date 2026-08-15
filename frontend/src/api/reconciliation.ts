import { apiClient } from './client';

export interface ReconciliationResult {
  income_heads: Record<string, any>;
  unmatched: {
    tis_only: any[];
    ais_only: any[];
    as26_only: any[];
  };
  summary: {
    total_entries: number;
    total_final_income: number;
    total_discrepancies: number;
    matched_all_three: number;
    matched_two: number;
    matched_one: number;
    unmatched_tis: number;
    unmatched_ais: number;
    unmatched_as26: number;
  };
  capital_gain_evidence?: any[];
  capital_gain_controls?: any[];
  capital_gain_control_discrepancies?: any[];
}

export const reconciliationApi = {
  reconcile: async (aisData: any, tisData: any, data26AS: any): Promise<ReconciliationResult> => {
    const res = await apiClient.post('/integration/reconciliation', {
      aisData,
      tisData,
      data26AS,
    });
    return res.data;
  },
};
