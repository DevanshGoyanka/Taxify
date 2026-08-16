import { describe, expect, it } from 'vitest';

import { map26asToDraftPatch } from './map26asToDraftPatch';
import { mapAisToDraftPatch } from './mapAisToDraftPatch';
import { mapTisToDraftPatch } from './mapTisToDraftPatch';

describe('direct typed import mappers', () => {
  it('maps AIS salary, interest, dividends, and TDS into complete canonical rows', () => {
    const patch = mapAisToDraftPatch({
      income_heads: {
        Salary: {
          entries: [{
            section: 'B7',
            information_code: 'TDS-ANN.II-SAL',
            information_source: 'ACME PRIVATE LIMITED (ABCD12345E)',
            amount: 800000,
          }],
        },
        Other: {
          entries: [
            {
              section: 'B2',
              information_code: 'SFT-016(SB)',
              information_source: 'BANK LIMITED (EFGH12345I)',
              amount: 12000,
            },
            {
              section: 'B2',
              information_code: 'SFT-015',
              information_source: 'COMPANY LIMITED (IJKL12345M)',
              institution_pan: 'ABCDE1234F',
              amount: 5000,
            },
            {
              section: 'B1',
              information_code: 'TDS-194A',
              information_source: 'BANK LIMITED (EFGH12345I)',
              amount: 12000,
            },
          ],
        },
      },
    });

    expect(patch.employers?.[0]).toMatchObject({
      employerName: 'ACME PRIVATE LIMITED',
      employerTAN: 'ABCD12345E',
      basic: 800000,
      natureOfEmployment: 'OTH',
      salaryNatureRows: [],
      isDomesticTravel: true,
    });
    expect(patch.otherSources?.interest?.[0]).toMatchObject({ kind: 'SAVINGS_BANK', grossAmount: 12000 });
    expect(patch.otherSources?.dividends?.[0]).toMatchObject({ grossAmount: 5000, category: 'EQUITY' });
    expect(patch.taxes?.tds?.[0]).toMatchObject({ section: '194A', schedule: 'TDS2' });
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
      employerName: 'ACME PRIVATE LIMITED',
      basic: 900000,
      tdsDeducted: 90000,
      salaryNatureRows: [],
      employerNPS: 0,
    });
    expect(patch.taxes?.tds?.[0]).toMatchObject({
      section: '192', taxDeducted: 90000, financialYear: '2025-26', schedule: 'TDS1',
    });
  });

  it('does not discard a TIS accepted salary total without AIS employer rows', () => {
    const patch = mapTisToDraftPatch({ salaryAmount: 750000 });
    expect(patch.employers).toHaveLength(1);
    expect(patch.employers?.[0]).toMatchObject({
      id: 'tis-employer-total', basic: 750000, natureOfEmployment: 'OTH', salaryNatureRows: [],
    });
    expect(patch.provenance?.[0].source).toBe('TIS');
  });
});
