/**
 * Type-3 portal filing API client.
 *
 * Wraps the unified `/api/v1/filing/*` endpoints exposed by
 * `app/routers/filing.py`.  Flow:
 *   1. submit() — generate the CBDT JSON on the backend and queue a
 *      Playwright portal-upload filing job (non-blocking).
 *   2. getJobStatus() — poll the queued/running filing job.
 *   3. supplyOtp() — deliver an Aadhaar OTP / Bank EVC to the running job
 *      when the portal is waiting on it (never persisted on the server).
 *   4. getStatus() — read durable filing state (acknowledgement number,
 *      e-verify status) for a client + assessment year.
 *
 * The backend generates the JSON and owns the upload; the frontend only
 * starts the job, polls it, and (optionally) supplies the OTP.
 */
import axiosInstance from './axiosInstance';

/** Verification mode the portal should use after upload. */
export type VerificationMode = 'LATER' | 'AADHAAR_OTP' | 'BANK_EVC';

/** Queued/running/completed filing job state returned by the backend. */
export interface FilingJobStatus {
  id: number;
  client_id: number;
  status: 'queued' | 'running' | 'completed' | 'failed';
  assessment_year: string | null;
  current_step: string | null;
  status_message: string | null;
  progress_pct: number;
  progress_label: string | null;
  /** Nested ``{filing: {...}}`` result once the portal responds. */
  result: {
    filing?: {
      state?: string;
      acknowledgement_number?: string | null;
      everify_status?: string | null;
      acknowledgement_path?: string | null;
      reason?: string;
    };
  };
  error_message: string | null;
  created_at: string | null;
  started_at: string | null;
  completed_at: string | null;
}

/** Durable filing record row for one (client, AY) pair. */
export interface FilingRecordSummary {
  id: number;
  itr_type: string;
  mode: string;
  environment: string;
  status: string;
  acknowledgement_number: string | null;
  everify_status: string | null;
  has_acknowledgement: boolean;
  error_message: string | null;
  updated_at: string | null;
}

function encoded(value: string | number): string {
  return encodeURIComponent(String(value));
}

/** Type-3 portal filing endpoints. */
export const filingSubmitApi = {
  /**
   * Queue a Type-3 portal submission job for a saved canonical draft.
   *
   * The backend generates + validates the CBDT JSON and enqueues a
   * Playwright upload job.  Returns immediately with a ``job_id`` to poll.
   */
  async submit(
    clientId: string | number,
    assessmentYear: string,
    itrType: string,
    verificationMode: VerificationMode = 'LATER',
  ): Promise<{ job_id: number; filing_id: number; status: string; verification_mode: string }> {
    const { data } = await axiosInstance.post(
      `/api/v1/filing/${encoded(clientId)}/${encoded(assessmentYear)}/${encoded(itrType)}/submit`,
      { verification_mode: verificationMode },
    );
    return data;
  },

  /** Poll a filing job (queued → running → completed/failed). */
  async getJobStatus(jobId: number): Promise<FilingJobStatus> {
    const { data } = await axiosInstance.get(`/api/v1/filing/jobs/${jobId}`);
    return data;
  },

  /** Deliver an OTP/EVC to a running filing job that is awaiting input. */
  async supplyOtp(jobId: number, otp: string): Promise<{ accepted: boolean }> {
    const { data } = await axiosInstance.post(
      `/api/v1/filing/jobs/${jobId}/otp`,
      { otp },
    );
    return data;
  },

  /** Read durable filing state for a client + assessment year. */
  async getStatus(clientId: string | number, assessmentYear: string): Promise<{ filings: FilingRecordSummary[] }> {
    const { data } = await axiosInstance.get(
      `/api/v1/filing/${encoded(clientId)}/${encoded(assessmentYear)}/status`,
    );
    return data;
  },

  /**
   * Trigger the STANDALONE Type-3 acknowledgement downloader.
   *
   * The backend logs in as the taxpayer, navigates to View Filed Returns,
   * locates the row for the return's acknowledgement number, downloads the
   * ITR-V PDF, and persists the path on the FilingRecord. Returns the PDF
   * as a Blob so the frontend can save/open it. Requires that a filing for
   * this (client, AY, ITR-type) already has an acknowledgement_number.
   */
  async fetchAcknowledgement(
    clientId: string | number,
    assessmentYear: string,
    itrType: string,
  ): Promise<Blob> {
    const response = await axiosInstance.post(
      `/api/v1/filing/${encoded(clientId)}/${encoded(assessmentYear)}/${encoded(itrType)}/acknowledgement/fetch`,
      null,
      { responseType: 'blob' },
    );
    return response.data;
  },
};
