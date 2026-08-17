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
});
