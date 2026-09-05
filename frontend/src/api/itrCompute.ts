/**
 * API functions for ITR-1 / ITR-4 computation and saved-return CRUD.
 *
 * All monetary values in responses come back as strings (serialised Decimal).
 * Parse them with Number() or keep as strings for display — do not use
 * parseFloat() which loses precision.
 */

import axiosInstance from './axiosInstance';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ITR1Input {
  age_bracket: 'below_60' | '60_to_80' | 'above_80';
  tax_regime: 'old' | 'new';
  salary_income: {
    gross_salary: number;
    standard_deduction_claimed?: number;
    perquisites_value?: number;
    profits_in_lieu_of_salary?: number;
    hra_exempt_amount?: number;
    other_exemptions?: number;
    professional_tax_paid?: number;
    entertainment_allowance?: number;
    is_government_employee?: boolean;
  };
  house_property_income: {
    property_type: 'S' | 'L' | 'D';   // S=self-occupied, L=let-out, D=deemed
    annual_rent_received?: number;
    municipal_taxes_paid?: number;
    home_loan_interest_paid?: number;
  };
  other_sources_income?: {
    interest_income?: number;
    family_pension_received?: number;
    dividend_income?: number;
  };
  deductions_chapter6a?: {
    amount_80c?: number;
    amount_80ccc?: number;
    amount_80ccd1?: number;
    amount_80ccd1b?: number;
    amount_80ccd2?: number;
    amount_80d_self?: number;
    amount_80d_parents?: number;
    amount_80dd?: number;
    amount_80ddb?: number;
    amount_80e?: number;
    amount_80ee?: number;
    amount_80eea?: number;
    amount_80eeb?: number;
    amount_80g?: number;
    amount_80gg?: number;
    amount_80tta?: number;
    amount_80ttb?: number;
    amount_80u?: number;
  };
}

export interface ITR1Result {
  salary_income: string;
  house_property_income: string;
  other_sources_income: string;
  gross_total_income: string;
  deductions_chapter6a: string;
  taxable_income: string;
  slab_tax: string;
  rebate_87a: string;
  tax_after_rebate: string;
  surcharge: string;
  health_education_cess: string;
  total_tax_payable: string;
  hp_loss_disallowed: string;
}

export interface ITR4Result extends ITR1Result {
  pgbp_income: string;
}

export interface ReturnSummary {
  id: number;
  itr_type: 'ITR1' | 'ITR2' | 'ITR4';
  created_at: string;
}

export interface ReturnDetail extends ReturnSummary {
  input_data: Record<string, unknown>;
  computed_result: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// API calls
// ---------------------------------------------------------------------------

export const itrComputeApi = {
  /**
   * Compute ITR-1 tax breakdown. Does NOT save to database.
   * Returns all income heads, deductions, slab tax, rebate, cess, total.
   */
  computeItr1: async (input: ITR1Input): Promise<ITR1Result> => {
    const { data } = await axiosInstance.post('/itr1/compute', input);
    return data as ITR1Result;
  },

  /**
   * Compute ITR-4 (presumptive) tax breakdown. Does NOT save to database.
   */
  computeItr4: async (input: Record<string, unknown>): Promise<ITR4Result> => {
    const { data } = await axiosInstance.post('/itr4/compute', input);
    return data as ITR4Result;
  },

  /**
   * Save a tax computation result linked to the current user.
   * Returns the id of the newly created record.
   */
  saveReturn: async (
    itrType: 'ITR1' | 'ITR2' | 'ITR4',
    inputData: Record<string, unknown>,
    computedResult: Record<string, unknown>
  ): Promise<{ id: number }> => {
    const { data } = await axiosInstance.post('/returns/save', {
      itr_type: itrType,
      input_data: inputData,
      computed_result: computedResult,
    });
    return data;
  },

  /**
   * List all saved returns for the current user (summary only — no full data).
   * Ordered most-recent first.
   */
  listReturns: async (): Promise<ReturnSummary[]> => {
    const { data } = await axiosInstance.get('/returns');
    return data as ReturnSummary[];
  },

  /**
   * Fetch a single saved return by id, including full input + result data.
   * Throws 403 if the return belongs to a different user, 404 if not found.
   */
  getReturn: async (id: number): Promise<ReturnDetail> => {
    const { data } = await axiosInstance.get(`/returns/${id}`);
    return data as ReturnDetail;
  },
};
