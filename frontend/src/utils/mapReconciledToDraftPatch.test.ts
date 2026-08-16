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
      employerNPS: 0,
    });
    expect(patch.otherSources?.interest?.[0]).toMatchObject({ kind: 'TERM_DEPOSIT', grossAmount: 200 });
    expect(patch.otherSources?.dividends?.[0].grossAmount).toBe(100);
    expect(patch.taxes?.tds).toHaveLength(4);
    expect(patch.businesses?.[0]).toMatchObject({ scheme: '44ADA', grossReceipts: 500, declaredIncome: 250 });
  });

  it('returns an empty patch for missing results', () => expect(mapReconciledToDraftPatch(undefined)).toEqual({}));
});
