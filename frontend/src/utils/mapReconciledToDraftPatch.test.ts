import { describe, expect, it } from 'vitest';
import type { ReconciledResults } from '../api/itrAutomation';
import { mapReconciledToDraftPatch } from './mapReconciledToDraftPatch';

function results(): ReconciledResults {
  const entry = (category: string, income_head: string, section: string, amount: number) => ({ source: `${category} source`, source_id: category, final_amount: amount, amounts: { as26: amount }, as26_tds: 10, present_in: { as26: true }, has_discrepancy: false, income_head, section, category });
  return {
    metadata: { pan: 'ABCDE1234F', financial_year: '2025-26' },
    income_heads: { salary: { income_head: 'Salary', total_final: 1000, total_tis: 0, total_ais: 0, total_as26: 0, total_as26_tds: 10, discrepancy_count: 0, entries: [entry('salary', 'Salary', '192', 1000)] }, other: { income_head: 'Other Sources', total_final: 300, total_tis: 0, total_ais: 0, total_as26: 0, total_as26_tds: 20, discrepancy_count: 0, entries: [entry('interest from deposit', 'Income from Other Sources', '194A', 200), entry('dividend', 'Income from Other Sources', '194', 100)] }, business: { income_head: 'Business', total_final: 500, total_tis: 0, total_ais: 0, total_as26: 0, total_as26_tds: 10, discrepancy_count: 0, entries: [entry('professional fees', 'Profits and Gains of Business or Profession', '194J', 500)] } },
    unmatched: { tis_only: [], ais_only: [], as26_only: [] },
    summary: { total_entries: 4, total_final_income: 1800, total_discrepancies: 0, matched_all_three: 0, matched_two: 0, matched_one: 4, unmatched_tis: 0, unmatched_ais: 0, unmatched_as26: 0 },
  };
}

describe('mapReconciledToDraftPatch', () => {
  it('maps salary, other sources, TDS and presumptive business', () => {
    const patch = mapReconciledToDraftPatch(results());
    expect(patch.employers?.[0]).toMatchObject({
      basic: 1000,
      tdsDeducted: 10,
      natureOfEmployment: 'OTH',
      employerAddress: '',
      salaryNatureRows: [],
      isDomesticTravel: true,
    });
    expect(patch.otherSources?.interest?.[0]).toMatchObject({ kind: 'TERM_DEPOSIT', grossAmount: 200 });
    expect(patch.otherSources?.dividends?.[0].grossAmount).toBe(100);
    expect(patch.taxes?.tds).toHaveLength(4);
    expect(patch.businesses?.[0]).toMatchObject({ scheme: '44ADA', grossReceipts: 500, declaredIncome: 250 });
  });

  it('returns an empty patch for missing results', () => expect(mapReconciledToDraftPatch(undefined)).toEqual({}));

  it('projects capital_gain_sales into the CG schedule', () => {
    const withCG: ReconciledResults = {
      ...results(),
      capital_gain_sales: [
        {
          id: 'sale-1', information_code: 'SFT-18-EMF',
          reporting_source: 'CAMS', reporting_entity_pan: 'AAACC3035G',
          transaction_date: '30/03/2026',
          security_name: 'Reliance', security_identifier: 'INE123456789',
          asset_type: 'Long term', quantity: 100, total_sale_value: 250000,
          acquisition_cost: 175000, sale_price_per_unit: 2500,
          unit_fmv: 2400, fair_market_value: 240000,
          security_class: 'Unit of Equity Oriented Mutual Fund',
          status: 'Active', is_summary: false,
        },
      ],
    };
    const patch = mapReconciledToDraftPatch(withCG);
    expect(patch.capitalGainsSchedule?.schedule112A).toHaveLength(1);
    expect(patch.capitalGainsSchedule?.schedule112A?.[0].isin).toBe('INE123456789');
    expect(patch.capitalGainsSchedule?.simplified112A).toEqual({
      totalSaleConsideration: 250000, totalCostAcquisition: 175000,
    });
  });
});

/**
 * Regression: the portal-automation "Import All" merge must not triplicate
 * income-head entries across re-imports.  The bug: mergeDraft is append-
 * only for rows with new ids, so (a) prefill + reconciled both emit the
 * same interest/dividend → 2×, and (b) re-importing on top of a draft
 * that already has the entries → 3×, 4×, ...
 *
 * Fix: mapPrefillToDraftPatch now contributes ONLY personal info + refund
 * bank account (no income heads/employers/TDS/deductions), and
 * handleConfirmImport builds the merge on a blankedBaseline that resets
 * the import-owned lists so patches populate them fresh.
 */
describe('handleConfirmImport merge regression (no triplication)', () => {
  it('produces exactly one entry per reconciled source, not 3× across re-imports', async () => {
    // Simulate the handleConfirmImport merge sequence.
    const { mergeDraft } = await import('../domain/returns/draftPatch');
    const { createEmptyReturnDraft } = await import('../domain/returns/factory');
    const { mapPrefillToDraftPatch } = await import('./mapPrefillToDraftPatch');

    // Reconciled patch owns income-head entries (1 interest + 1 dividend).
    const reconciledPatch = mapReconciledToDraftPatch(results());
    expect(reconciledPatch.otherSources?.interest).toHaveLength(1);
    expect(reconciledPatch.otherSources?.dividends).toHaveLength(1);

    // Prefill patch emits ONLY personal info + bank account — no income
    // heads, so it cannot duplicate the reconciled income.
    const prefill = {
      personal_info: { pan: 'ABCDE1234F', name: { first_name: 'A' } },
      other_sources: { interest_from_savings_bank: 200, dividend_gross: 100 },
    } as any;
    const prefillPatch = mapPrefillToDraftPatch(prefill);
    expect(prefillPatch.otherSources?.interest).toBeUndefined();
    expect(prefillPatch.otherSources?.dividends).toBeUndefined();

    // First import: blanked baseline + prefill + reconciled.
    const prior1 = createEmptyReturnDraft('2026-27', 'ITR-1', 'new');
    const blanked1: any = {
      ...prior1,
      employers: [], bankAccounts: [], businesses: [], houseProperties: [],
      otherSources: { ...prior1.otherSources, interest: [], dividends: [], otherIncome: [] },
      taxes: { tds: [], tcs: [], challans: [] },
    };
    let merged = mergeDraft(mergeDraft(blanked1, prefillPatch), reconciledPatch);
    expect(merged.otherSources.interest).toHaveLength(1);
    expect(merged.otherSources.dividends).toHaveLength(1);
    expect(merged.otherSources.interest[0].grossAmount).toBe(200);
    expect(merged.otherSources.dividends[0].grossAmount).toBe(100);

    // Re-import on top of the already-populated draft: the blanked
    // baseline MUST reset the lists, so the count stays at 1 (not 2 or 3).
    const prior2 = merged;
    const blanked2: any = {
      ...prior2,
      employers: [], bankAccounts: [], businesses: [], houseProperties: [],
      otherSources: { ...prior2.otherSources, interest: [], dividends: [], otherIncome: [] },
      taxes: { tds: [], tcs: [], challans: [] },
    };
    merged = mergeDraft(mergeDraft(blanked2, prefillPatch), reconciledPatch);
    expect(merged.otherSources.interest).toHaveLength(1);
    expect(merged.otherSources.dividends).toHaveLength(1);
  });
});
