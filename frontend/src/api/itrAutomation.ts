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

export interface CapitalGainSale {
  id: string;
  information_code: string;
  reporting_source: string;
  reporting_entity_pan?: string;
  security_name: string;
  security_identifier: string;
  quantity?: number | null;
  sale_price_per_unit?: number | null;
  total_sale_value: number;
  acquisition_cost?: number | null;
  fair_market_value?: number | null;
  unit_fmv?: number | null;
  transaction_date: string;
  asset_type: string;
  security_class: string;
  status: string;
  is_summary: boolean;
  /** Immovable-property-only fields (SFT-012 sale). */
  property_address?: string;
  property_type?: string;
  transaction_type?: string;
  transaction_amount?: number | null;
  stamp_duty_value?: number | null;
  transaction_amount_assigned?: number | null;
  reported_on?: string;
  party_count?: number | null;
}

export interface CapitalGainPurchase {
  id: string;
  information_code: string;
  reporting_source: string;
  reporting_entity_pan?: string;
  security_name: string;
  account_id: string;
  period: string;
  purchase_amount: number;
  status: string;
  is_summary: boolean;
  /** Immovable-property-only fields (SFT-012(P) purchase). */
  property_address?: string;
  property_type?: string;
  transaction_type?: string;
  transaction_relation?: string;
  transaction_amount?: number | null;
  stamp_duty_value?: number | null;
  transaction_amount_assigned?: number | null;
  reported_on?: string;
  party_count?: number | null;
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
  capital_gain_sales?: CapitalGainSale[];
  capital_gain_purchases?: CapitalGainPurchase[];
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
  prefill?: any;
  filing_advisory?: {
    already_filed_advisory: boolean;
    already_filed_advisory_message: string;
    prior_return_reference_ay?: string | null;
    download_row_identity?: string | null;
    download_assessment_year?: string | null;
    revision_selected: boolean;
    updated_return_selected: boolean;
    notice_response_selected: boolean;
    current_ay_already_filed: boolean;
    current_ay_is_revised: boolean;
    current_ay_filing_section?: string | null;
    download_is_current_ay: boolean;
    requires_user_confirmation_for_revision: boolean;
  };
  filing_mode_classification?: {
    state: string;
    filing_context: string;
    current_assessment_year: string;
    current_return_count: number;
    current_ay_already_filed: boolean;
    current_ay_is_revised: boolean;
    current_ay_filing_section?: string | null;
    review_required: boolean;
    review_reasons: string[];
  };
}

export type ArtifactOutcome = {
  state: 'downloaded' | 'no_data' | 'retryable_failure' | 'validation_failed' | 'session_expired' | 'permanent_failure';
  path: string | null;
  reason: string;
  ay: string;
};

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
  artifact_outcomes: Record<string, ArtifactOutcome>;
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
