/**
 * ITD Portal automation job API.
 *
 * Start a background download job and poll for status.
 * All functions use the shared axiosInstance with automatic JWT auth.
 */
import axiosInstance from './axiosInstance';

// ── Debug guard: verify module loaded correctly in DEV ────────────────────────
// If this fires but callers still report "does not provide export", the
// caller's HMR snapshot is stale — run the cache-clear command below.
if (import.meta.env.DEV) {
  // eslint-disable-next-line no-console
  console.debug('[itrAutomation] module loaded OK — DEV only, safe to ignore.');
}

// ── Reconciled result types (shared by modal, form mapper, and job payload) ───

export interface ReconciledEntry {
  source: string;
  source_id?: string;
  pan?: string;
  tan?: string;
  description?: string;
  final_amount: number;
  amounts: Record<string, number>;
  as26_tds: number;
  as26_tcs?: number;
  credit_type?: 'TDS' | 'TCS' | null;
  credit_selected_source?: '26AS' | null;
  credit_selection_reason?: '26AS_TAX_CREDIT' | '';
  selected_source?: 'TIS' | 'AIS' | '26AS';
  selection_reason?: 'TIS_ACCEPTED_INCOME' | 'AIS_INCOME_FALLBACK' | '26AS_INCOME_FALLBACK' | '26AS_CREDIT_EVIDENCE_ONLY';
  present_in: Record<string, boolean>;
  has_discrepancy: boolean;
  discrepancy_detail?: string;
  income_head: string;
  section?: string;
  category?: string;
}

export interface ReconciledIncomeHead {
  income_head: string;
  total_final: number;
  total_tis: number;
  total_ais: number;
  total_as26: number;
  total_as26_tds: number;
  total_as26_tcs?: number;
  discrepancy_count: number;
  entries: ReconciledEntry[];
}

export interface ReconciledUnmatchedEntry {
  source: string;
  source_id?: string;
  category?: string;
  description?: string;
  income_head?: string;
  pan?: string;
  tan?: string;
  amount: number;
  tds: number;
  section: string;
}

export interface CapitalGainEvidence {
  evidence_id: string;
  granularity: 'TRANSACTION_DETAIL' | 'ACCOUNT_PERIOD_AGGREGATE' | 'REPORTING_SOURCE_AGGREGATE' | 'CATEGORY_CONTROL';
  side: 'PURCHASE' | 'SALE' | 'UNKNOWN';
  category: string;
  information_code: string;
  summary_sr_no: number;
  detail_sr_no: number | null;
  reporting_source: string;
  reporting_entity_pan?: string;
  account_id?: string;
  transaction_date?: string;
  /** AIS-reported quarter for SFT-18(Pur) purchase aggregates, e.g. "Q2(Jul-Sep)". */
  quarter?: string;
  security_class?: string;
  security_name?: string;
  security_identifier?: string;
  quantity?: number | null;
  amount: number;
  acquisition_cost?: number | null;
  fair_market_value?: number | null;
  unit_fmv?: number | null;
  sale_price_per_unit?: number | null;
  stt_amount?: number | null;
  debit_type?: string;
  credit_type?: string;
  asset_type?: string;
  stt_paid_on_acquisition?: boolean | null;
  stt_paid_on_transfer?: boolean | null;
  recognized_exchange?: boolean | null;
  acquired_before_31_jan_2018?: boolean | null;
  acquisition_mode?: string;
  status?: string;
  parser_confidence: 'HIGH' | 'MEDIUM' | 'LOW';
}

export interface CapitalGainControl {
  control_id: string;
  source_document: 'AIS' | 'TIS';
  granularity: 'REPORTING_SOURCE_AGGREGATE' | 'CATEGORY_CONTROL';
  category: string;
  side: 'PURCHASE' | 'SALE' | 'UNKNOWN';
  information_code: string;
  reporting_source: string;
  reporting_entity_pan?: string;
  amount: number;
  accepted_amount?: number | null;
}

export interface CapitalGainControlDiscrepancy {
  category: string;
  side: 'PURCHASE' | 'SALE' | 'UNKNOWN';
  detail_total: number;
  ais_control_total: number;
  tis_accepted_total: number;
  difference: number;
}

export interface ReconciledResults {
  metadata: {
    pan?: string;
    name?: string;
    financial_year?: string;
  };
  income_heads: Record<string, ReconciledIncomeHead>;
  category_controls?: Record<string, number>;
  category_control_discrepancies?: Array<{
    category: string;
    tis_accepted_total: number;
    tis_detail_total: number;
    difference: number;
  }>;
  capital_gain_evidence?: CapitalGainEvidence[];
  capital_gain_controls?: CapitalGainControl[];
  capital_gain_control_discrepancies?: CapitalGainControlDiscrepancy[];
  unmatched: {
    tis_only: ReconciledUnmatchedEntry[];
    ais_only: ReconciledUnmatchedEntry[];
    as26_only: ReconciledUnmatchedEntry[];
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
  _extraction_errors?: string[];
}

// NOTE: exported as `export type` so Rolldown (Vite 6) preserves it under
// verbatimModuleSyntax. Callers MUST use: import type { AutomationJob }.
export type AutomationJob = {
  id: number;
  client_id: number;
  user_id: number;
  job_type: string;
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';
  assessment_year: string | null;
  fiscal_year: string;
  steps_completed: string[];
  current_step: string | null;
  // User-facing progress fields (clean, no server tags)
  status_message: string | null;
  progress_pct: number;        // 0–100
  progress_label: string | null; // e.g. "Downloading Form 26AS"
  progress_icon: string | null;  // e.g. "📄"
  // Raw server log (for debugging)
  raw_status_message: string | null;
  files_downloaded: Record<string, string | null>;
  parsed_results: ReconciledResults | null;
  ais_ref_id: string | null;
  error_message: string | null;
  created_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  attempt_count: number;
  max_attempts: number;
};

export type StartJobResponse = {
  job_id: number;
  status: string;
  assessment_year: string;
  fiscal_year: string;
  download_dir: string;
  message: string;
}

export const itrAutomationApi = {
  /**
   * Start an ITD portal automation download job.
   */
  startImport(
    clientId: string,
    assessmentYear: string = '2026-27',
    jobType: string = 'DOWNLOAD_ALL',
  ): Promise<StartJobResponse> {
    return axiosInstance
      .post(`/clients/${clientId}/automation/import`, null, {
        params: { assessment_year: assessmentYear, job_type: jobType },
      })
      .then((res) => res.data);
  },

  /**
   * Poll job status.
   */
  getJobStatus(jobId: number): Promise<AutomationJob> {
    return axiosInstance
      .get(`/automation/jobs/${jobId}`)
      .then((res) => res.data);
  },
};
