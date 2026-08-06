import { describe, expect, it } from 'vitest';

import type { ReconciledResults } from '../api/itrAutomation';
import { mapReconciledToFormData } from './mapReconciledToFormData';

function syntheticResults(): ReconciledResults {
  return {
    metadata: { pan: 'AAAAA0000A', financial_year: '2025-26' },
    income_heads: {
      Salary: {
        income_head: 'Salary',
        total_final: 1_000_000,
        total_tis: 1_000_000,
        total_ais: 1_000_000,
        total_as26: 1_000_000,
        total_as26_tds: 80_000,
        discrepancy_count: 0,
        entries: [{
          source: 'SYNTHETIC EMPLOYER PRIVATE LIMITED',
          source_id: 'salary|id:ABCD12345E',
          tan: 'ABCD12345E',
          final_amount: 1_000_000,
          amounts: { tis: 1_000_000, ais: 1_000_000, as26: 1_000_000 },
          as26_tds: 80_000,
          present_in: { tis: true, ais: true, as26: true },
          has_discrepancy: false,
          income_head: 'Salary',
          section: '192',
          category: 'salary',
        }],
      },
      'Income from Other Sources': {
        income_head: 'Income from Other Sources',
        total_final: 20_000,
        total_tis: 20_000,
        total_ais: 20_000,
        total_as26: 20_000,
        total_as26_tds: 2_000,
        discrepancy_count: 0,
        entries: [{
          source: 'SYNTHETIC BANK LIMITED',
          source_id: 'interest from deposit|id:EFGH12345I',
          tan: 'EFGH12345I',
          final_amount: 20_000,
          amounts: { tis: 20_000, ais: 20_000, as26: 20_000 },
          as26_tds: 2_000,
          present_in: { tis: true, ais: true, as26: true },
          has_discrepancy: false,
          income_head: 'Income from Other Sources',
          section: '194A',
          category: 'interest from deposit',
        }],
      },
      'Capital Gains': {
        income_head: 'Capital Gains',
        total_final: 50_000,
        total_tis: 0,
        total_ais: 50_000,
        total_as26: 0,
        total_as26_tds: 0,
        discrepancy_count: 0,
        entries: [{
          source: 'SYNTHETIC MUTUAL FUND REGISTRAR',
          source_id: 'purchase of securities and units of mutual funds|id:BBBBB0000B',
          pan: 'BBBBB0000B',
          final_amount: 50_000,
          amounts: { tis: 0, ais: 50_000, as26: 0 },
          as26_tds: 0,
          present_in: { tis: false, ais: true, as26: false },
          has_discrepancy: false,
          income_head: 'Capital Gains',
          section: 'SFT-18',
          category: 'purchase of securities and units of mutual funds',
        }],
      },
    },
    category_controls: { dividend: 0 },
    category_control_discrepancies: [],
    unmatched: { tis_only: [], ais_only: [], as26_only: [] },
    summary: {
      total_entries: 3,
      total_final_income: 1_070_000,
      total_discrepancies: 0,
      matched_all_three: 1,
      matched_two: 0,
      matched_one: 1,
      unmatched_tis: 0,
      unmatched_ais: 1,
      unmatched_as26: 0,
    },
  };
}

describe('mapReconciledToFormData', () => {
  it('copies real TAN and maps SFT purchase values without inventing taxable gains', () => {
    const mapped = mapReconciledToFormData(syntheticResults());
    const employer = mapped.formDataUpdate.employerEntries[0];
    const salaryTds = mapped.formDataUpdate.tdsEntries.find((entry: { section: string }) => entry.section === '192');
    const interestTds = mapped.formDataUpdate.tdsEntries.find((entry: { section: string }) => entry.section === '194A');

    expect(employer.employerTAN).toBe('ABCD12345E');
    expect(employer.employerPAN).toBe('');
    expect(salaryTds.deductorTAN).toBe('ABCD12345E');
    expect(salaryTds.deductorTAN).not.toBe(String(salaryTds.tdsDeducted));
    expect(interestTds.deductorTAN).toBe('EFGH12345I');
    expect(mapped.formDataUpdate.tdsS192).toBe(80_000);
    expect(mapped.formDataUpdate.tds194A).toBe(2_000);
    expect(mapped.formDataUpdate.tcsEntries).toBeUndefined();
    expect(mapped.formDataUpdate.capitalGainTransactions).toEqual([]);
    expect(mapped.formDataUpdate.ltcg112APre).toBeUndefined();
  });

  it('maps AIS CG evidence into simple editable rows', () => {
    const results = syntheticResults();
    results.capital_gain_evidence = [{
      evidence_id: 'evidence-1',
      granularity: 'TRANSACTION_DETAIL',
      side: 'PURCHASE',
      category: 'purchase of securities and units of mutual funds',
      information_code: 'SFT-18(Pur)',
      summary_sr_no: 1,
      detail_sr_no: 1,
      reporting_source: 'Synthetic Registrar',
      account_id: '12345678',
      security_name: 'ICICI Prudential Mutual Fund(P)',
      amount: 12_000,
      status: 'Active',
      parser_confidence: 'HIGH',
    }];

    const mapped = mapReconciledToFormData(results);
    const entry = mapped.formDataUpdate.capitalGainTransactions[0];

    expect(mapped.formDataUpdate.capitalGainTransactions).toHaveLength(1);
    expect(entry.transactionId).toBe('evidence-1');
    expect(entry.purchaseCost).toBe(12_000);
    expect(entry.saleCost).toBe(0);
    expect(entry.description).toContain('ICICI Prudential');
    expect(entry.importSource).toBe('Synthetic Registrar');
    expect(entry.accountId).toBe('12345678');
  });

  it('maps sale-side CG evidence with sale amount populated', () => {
    const results = syntheticResults();
    results.capital_gain_evidence = [{
      evidence_id: 'sale-1',
      granularity: 'REPORTING_SOURCE_AGGREGATE',
      side: 'SALE',
      category: 'sale of securities and units of mutual fund',
      information_code: 'SFT-17-LES(M)',
      summary_sr_no: 2,
      detail_sr_no: null,
      reporting_source: 'Synthetic Depository',
      amount: 648_038,
      parser_confidence: 'MEDIUM',
    }];

    const mapped = mapReconciledToFormData(results);
    const entry = mapped.formDataUpdate.capitalGainTransactions[0];

    expect(mapped.formDataUpdate.capitalGainTransactions).toHaveLength(1);
    expect(entry.purchaseCost).toBe(0);
    expect(entry.saleCost).toBe(648_038);
    expect(entry.saleValue).toBe(648_038);
  });

  it('maps detailed SFT-18 disposals as computable mutual-fund transactions', () => {
    const results = syntheticResults();
    results.capital_gain_evidence = [{
      evidence_id: 'fund-sale-1',
      granularity: 'TRANSACTION_DETAIL',
      side: 'SALE',
      category: 'sale of securities and units of mutual fund',
      information_code: 'SFT-18-EMF(M)',
      summary_sr_no: 16,
      detail_sr_no: 1,
      reporting_source: 'Synthetic RTA',
      transaction_date: '30/03/2026',
      security_class: 'Unit of Equity Oriented Mutual Fund',
      security_name: 'Bandhan Financial Services Fund',
      security_identifier: 'INF194KB1GE6',
      quantity: 1169.15,
      amount: 15_000,
      acquisition_cost: 16_044.20,
      sale_price_per_unit: 12.83,
      stt_amount: 0.15,
      asset_type: 'Long term',
      status: 'Active',
      parser_confidence: 'HIGH',
    }];

    const entry = mapReconciledToFormData(results).formDataUpdate.capitalGainTransactions[0];

    expect(entry.recordKind).toBe('TRANSACTION');
    expect(entry.assetType).toBe('EQUITY_ORIENTED_MUTUAL_FUND');
    expect(entry.saleDate).toBe('2026-03-30');
    expect(entry.purchaseCost).toBe(16_044.20);
    expect(entry.saleCost).toBe(15_000);
    expect(entry.isin).toBe('INF194KB1GE6');
    expect(entry.aisHoldingPeriod).toBe('Long term');
    expect(entry.sttPaidOnTransfer).toBe(true);
  });

  it('produces stable imported row identifiers across repeated mapping', () => {
    const first = mapReconciledToFormData(syntheticResults()).formDataUpdate;
    const second = mapReconciledToFormData(syntheticResults()).formDataUpdate;

    expect(first.employerEntries[0].id).toBe(second.employerEntries[0].id);
    expect(first.tdsEntries[0].id).toBe(second.tdsEntries[0].id);
  });
});
