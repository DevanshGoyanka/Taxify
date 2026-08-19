import { describe, expect, it } from 'vitest';

import { map26asToDraftPatch } from './map26asToDraftPatch';
import { mapAisToDraftPatch } from './mapAisToDraftPatch';
import { mapTisToDraftPatch } from './mapTisToDraftPatch';
import { mergeDraft } from '../domain/returns/draftPatch';
import { createEmptyReturnDraft } from '../domain/returns/factory';

// Real extractor output shapes, captured from
// ais_extractor/test_output/EPPPG3078Q_ais.json and
// ais_extractor/test_output_tis/EPPPG3078Q_tis.json.
const realAis = {
  metadata: { pan: 'EPPPG3078Q', financial_year: '2025-26' },
  income_heads: {
    'Income from Other Sources': {
      income_head: 'Income from Other Sources',
      total_amount: 1126.0,
      entries: [
        {
          sr_no: 1,
          information_code: 'SFT-015',
          information_source: 'INDIAN RAILWAY FINANCE CORPORATION (AAACI0681C.AN555)',
          institution_pan: 'AAACI0681C',
          amount: 130.0,
          category: 'dividend',
          section: 'B2',
          detail_header: ['SR. NO.', 'REPORTED ON', 'DIVIDEND AMOUNT', 'STATUS'],
          details: [{ sr_no: 1, data: { col_0: '1', col_1: '22/05/2026', col_2: '130', col_3: 'Active' } }],
        },
        {
          sr_no: 2,
          information_code: 'SFT-016(SB)',
          information_source: 'STATE BANK OF INDIA (AAACS8577K.AB703)',
          institution_pan: 'AAACS8577K',
          amount: 157.0,
          category: 'interest from savings bank',
          section: 'B2',
          detail_header: ['SR. NO.', 'REPORTED ON', 'ACCOUNT NUMBER', 'ACCOUNT TYPE', 'INTEREST AMOUNT', 'STATUS'],
          details: [{ sr_no: 1, data: { col_0: '1', col_4: '157', col_5: 'Active' } }],
        },
        {
          sr_no: 3,
          information_code: 'SFT-016(TD)',
          information_source: 'STATE BANK OF INDIA (AAACS8577K.AB703)',
          institution_pan: 'AAACS8577K',
          amount: 839.0,
          category: 'interest from deposit',
          section: 'B2',
          detail_header: ['SR. NO.', 'REPORTED ON', 'ACCOUNT NUMBER', 'ACCOUNT TYPE', 'INTEREST AMOUNT', 'STATUS'],
          details: [{ sr_no: 1, data: { col_0: '1', col_4: '839', col_5: 'Active' } }],
        },
      ],
    },
  },
  summary: { total_tds: 0.0 },
};

const realTis = {
  metadata: { pan: 'EPPPG3078Q', financial_year: '2025-26' },
  income_heads: {
    'Income from Other Sources': {
      income_head: 'Income from Other Sources',
      total_processed: 1126.0,
      total_accepted: 1126.0,
      entries: [
        { sr_no: 1, category: 'Dividend', accepted_by_taxpayer: 130.0, details: [{ sr_no: 1, part: 'SFT', information_source: 'INDIAN RAILWAY FINANCE CORPORATION (AAACI0681C.AN555)', institution_pan: 'AAACI0681C', reported_by_source: '130', accepted_by_taxpayer: '130' }] },
        { sr_no: 2, category: 'Interest from savings bank', accepted_by_taxpayer: 157.0, details: [{ sr_no: 1, part: 'SFT', information_source: 'STATE BANK OF INDIA (AAACS8577K.AB703)', institution_pan: 'AAACS8577K', reported_by_source: '157', accepted_by_taxpayer: '157' }] },
        { sr_no: 3, category: 'Interest from deposit', accepted_by_taxpayer: 839.0, details: [{ sr_no: 1, part: 'SFT', information_source: 'STATE BANK OF INDIA (AAACS8577K.AB703)', institution_pan: 'AAACS8577K', reported_by_source: '839', accepted_by_taxpayer: '839' }] },
      ],
    },
  },
};

describe('direct typed import mappers against real extractor fixtures', () => {
  it('maps the real AIS fixture into interest + dividend canonical rows', () => {
    const patch = mapAisToDraftPatch(realAis as never);

    expect(patch.otherSources?.interest).toHaveLength(2);
    expect(patch.otherSources?.interest?.[0]).toMatchObject({ kind: 'SAVINGS_BANK', grossAmount: 157 });
    expect(patch.otherSources?.interest?.[1]).toMatchObject({ kind: 'TERM_DEPOSIT', grossAmount: 839 });
    expect(patch.otherSources?.dividends?.[0]).toMatchObject({ grossAmount: 130 });
    expect(patch.employers).toHaveLength(0);
  });

  it('maps the real TIS fixture into interest + dividend canonical rows', () => {
    const patch = mapTisToDraftPatch(realTis as never);

    expect(patch.employers).toHaveLength(0);
    expect(patch.otherSources?.interest).toHaveLength(2);
    expect(patch.otherSources?.interest?.[0]).toMatchObject({ kind: 'SAVINGS_BANK', grossAmount: 157 });
    expect(patch.otherSources?.interest?.[1]).toMatchObject({ kind: 'TERM_DEPOSIT', grossAmount: 839 });
    expect(patch.otherSources?.dividends?.[0]).toMatchObject({ grossAmount: 130 });
  });

  it('maps a TIS accepted salary total when no AIS employer rows exist', () => {
    const data = {
      income_heads: {
        Salary: {
          entries: [{ sr_no: 1, category: 'Salary', accepted_by_taxpayer: 750000, details: [] }],
        },
      },
    };
    const patch = mapTisToDraftPatch(data as never);
    expect(patch.employers).toHaveLength(1);
    expect(patch.employers?.[0]).toMatchObject({ id: 'tis-employer-total', basic: 750000 });
  });

  it('maps 26AS salary and TDS into complete canonical rows', () => {
    const patch = map26asToDraftPatch({
      financialYear: '2025-26',
      tdsEntries: [{
        sectionCode: '192',
        employerName: 'ACME PRIVATE LIMITED',
        employerTAN: 'ABCD12345E',
        totalAmount: 900000,
        totalTDS: 90000,
      }],
    });

    expect(patch.employers?.[0]).toMatchObject({
      employerName: 'ACME PRIVATE LIMITED', basic: 900000, tdsDeducted: 90000,
    });
    expect(patch.taxes?.tds?.[0]).toMatchObject({
      section: '192', taxDeducted: 90000, financialYear: '2025-26', schedule: 'TDS1',
    });
  });

  it('maps AIS salary B7 + salary TDS B1 into one employer and one TDS row', () => {
    const patch = mapAisToDraftPatch({
      income_heads: {
        Salary: { entries: [
          { information_code: 'TDS-ANN.II-SAL', information_source: 'ACME PRIVATE LIMITED (ABCD12345E)', amount: 800000, category: 'Salary', section: 'B7', income_head: 'Salary', detail_header: ['SR. NO.', '17(1) AMOUNT', 'TDS DEDUCTED', 'STATUS'], details: [{ data: { col_0: '1', col_1: '800000', col_2: '80000', col_3: 'Active' } }] },
          { information_code: 'TDS-192', information_source: 'ACME PRIVATE LIMITED (ABCD12345E)', amount: 800000, category: 'Salary', section: 'B1', income_head: 'Salary', detail_header: ['SR. NO.', 'AMOUNT PAID', 'TDS DEDUCTED', 'STATUS'], details: [{ data: { col_0: '1', col_1: '800000', col_2: '80000', col_3: 'Active' } }] },
        ] },
      },
    } as never);

    expect(patch.employers).toHaveLength(1);
    expect(patch.employers?.[0]).toMatchObject({ employerName: 'ACME PRIVATE LIMITED', basic: 800000, tdsDeducted: 80000 });
    expect(patch.taxes?.tds).toHaveLength(1);
    expect(patch.taxes?.tds?.[0]).toMatchObject({ section: '192', schedule: 'TDS1', taxDeducted: 80000 });
  });

  it('preserves 26AS rows when AIS is imported afterwards (the regression)', () => {
    const base = createEmptyReturnDraft();
    const from26as = map26asToDraftPatch({
      financialYear: '2025-26',
      tdsEntries: [{
        sectionCode: '192', employerName: 'ACME PRIVATE LIMITED', employerTAN: 'ABCD12345E',
        totalAmount: 900000, totalTDS: 90000,
      }],
    });
    const merged26as = mergeDraft(base, from26as);
    expect(merged26as.employers).toHaveLength(1);
    expect(merged26as.taxes.tds).toHaveLength(1);

    // Simulate a subsequent AIS import that has different employers + interest.
    const fromAis = mapAisToDraftPatch({
      income_heads: {
        Other: { entries: [{ information_code: 'SFT-016(SB)', information_source: 'BANK LIMITED (EFGH12345I)', amount: 12000, category: 'interest from savings bank', section: 'B2' }] },
      },
    } as never);
    const mergedAis = mergeDraft(merged26as, fromAis);

    // The 26AS salary employer + TDS must survive the AIS import.
    expect(mergedAis.employers).toHaveLength(1);
    expect(mergedAis.employers[0]).toMatchObject({ employerName: 'ACME PRIVATE LIMITED', basic: 900000 });
    expect(mergedAis.taxes.tds).toHaveLength(1);
    // The AIS interest is appended.
    expect(mergedAis.otherSources.interest).toHaveLength(1);
    expect(mergedAis.otherSources.interest[0]).toMatchObject({ grossAmount: 12000 });
  });

  it('does NOT create phantom 112A scrips from PURCHASE-side AIS entries', () => {
    // Real shape from AEDPD0736M_ais.json: the SALE entry (SFT-17-LES(M)) is
    // summary-only (no details), and the PURCHASE entries (SFT-17(Pur) /
    // SFT-18(Pur)) carry column-keyed detail rows with TOTAL PURCHASE AMOUNT /
    // TOTAL SALES VALUE — no parsed `sales_consideration`/`isin`/`cost` keys.
    // Previously the direct-import mapper fell back to `entry.amount` for the
    // sale value, producing phantom scrips whose `totalSaleValue` was the
    // PURCHASE aggregate (456609, 11999, ...) and whose cost/ISIN were 0.
    const patch = mapAisToDraftPatch({
      income_heads: {
        'Capital Gains': { entries: [
          // Summary-only SALE — no detail rows; must not yield scrips.
          { sr_no: 26, information_code: 'SFT-17-LES(M)', category: 'sale of securities and units of mutual fund', amount: 496301, detail_header: [], details: [] },
          // PURCHASE entries with column-keyed details — must be skipped.
          { sr_no: 27, information_code: 'SFT-17(Pur)', category: 'purchase of securities and units of mutual funds', amount: 456609, detail_header: ['SR. NO.', 'QUARTER', 'CLIENT ID', 'HOLDER FLAG', 'MARKET PURCHASE', 'MARKET SALES', 'STATUS'], details: [{ sr_no: 1, data: { col_0: '1', col_1: '-', col_2: '26674871', col_3: 'First', col_4: '4,56,609', col_5: '4,95,332', col_6: 'Active' } }] },
          { sr_no: 30, information_code: 'SFT-18(Pur)', category: 'purchase of securities and units of mutual funds', amount: 11999, detail_header: ['SR. NO.', 'QUARTER', 'CLIENT ID', 'AMC NAME (CODE)', 'HOLDER FLAG', 'TOTAL PURCHASE AMOUNT', 'TOTAL SALES VALUE', 'STATUS'], details: [{ sr_no: 1, data: { col_0: '1', col_1: 'Q4(Jan-Mar)', col_2: '91041541744', col_3: 'AXIS MUTUAL FUND(128)', col_4: 'First', col_5: '3,000', col_6: '0', col_7: 'Active' } }] },
        ] },
      },
    } as never);

    // No phantom scrips — the CG schedule is empty (the AIS genuinely has no
    // per-scrip SALE detail for this client; only purchase-side aggregates).
    expect(patch.capitalGainsSchedule?.schedule112A ?? []).toHaveLength(0);
    expect(patch.capitalGainsSchedule?.schedule115AD ?? []).toHaveLength(0);
    expect(patch.capitalGainsSchedule?.stEquity ?? []).toHaveLength(0);
    // No simplified112A aggregate either (no realisation rows).
    expect(patch.capitalGainsSchedule?.simplified112A).toBeUndefined();
  });

  it('creates a 112A scrip from a SALE detail row with parsed keys', () => {
    // A real listed-equity SALE detail row where the extractor populated the
    // parsed keys (isin, sales_consideration, cost_of_acquisition, etc.).
    const patch = mapAisToDraftPatch({
      income_heads: {
        'Capital Gains': { entries: [
          { sr_no: 1, information_code: 'SFT-17-LES', category: 'sale of securities and units of mutual fund', amount: 456609, detail_header: ['SR. NO.', 'DATE OF SALE/TRANSFER', 'SECURITY NAME', 'SALES CONSIDERATION', 'COST OF ACQUISITION', 'ASSET TYPE', 'STATUS'], details: [{ sr_no: 1, data: { isin: 'INE123A01014', security_name: 'RELIANCE INDUSTRIES', sales_consideration: '4,56,609', cost_of_acquisition: '3,00,000', quantity: '50', sale_price_per_unit: '9132.18', asset_type: 'Long term', transfer_date: '2026-02-15' } }] },
        ] },
      },
    } as never);

    expect(patch.capitalGainsSchedule?.schedule112A).toHaveLength(1);
    expect(patch.capitalGainsSchedule?.schedule112A?.[0]).toMatchObject({
      isin: 'INE123A01014', name: 'RELIANCE INDUSTRIES', totalSaleValue: 456609,
      costWithoutIndexation: 300000, acquisitionCost: 300000, quantity: 50,
    });
    // The LTCG sale aggregates into the simplified112A quick-entry totals.
    expect(patch.capitalGainsSchedule?.simplified112A).toMatchObject({
      totalSaleConsideration: 456609, totalCostAcquisition: 300000,
    });
  });
});
