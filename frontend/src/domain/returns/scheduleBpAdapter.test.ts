import { describe, expect, it } from 'vitest';
import { createEmptyFinancialParticulars } from './factory';
import { businessesFromScheduleBp, scheduleBpFromBusinesses } from './scheduleBpAdapter';
import type { ReturnDraft } from './types';

describe('Schedule BP canonical adapter', () => {
  it('round-trips all three schemes, arrays, enums, and integer fields', () => {
    const fp = {
      ...createEmptyFinancialParticulars(),
      partnerMemberOwnCapital: 100000,
      fixedAssets: 50000,
      totalAssets: 50000,
    };
    const businesses: ReturnDraft['businesses'] = [
      {
        id: 'ad', scheme: '44AD', businessName: 'Trading', natureCode: '01001', description: 'Retail',
        digitalReceipts: 1000000, nonDigitalReceipts: 100000, otherModeReceipts: 50000,
        digitalPresumptiveIncome: 63000, nonDigitalPresumptiveIncome: 8000,
        declaredIncome: 71000,
        gstinTurnovers: [{ id: 'gst', gstin: '07ABCDE1234F1Z5', turnover: 1150000 }],
        financialParticulars: fp,
      },
      {
        id: 'ada', scheme: '44ADA', businessName: 'Consulting', natureCode: '14001', description: 'Legal',
        grossReceipts: 400000, digitalReceipts: 300000, nonDigitalReceipts: 50000,
        otherModeReceipts: 50000, declaredIncome: 200000, gstinTurnovers: [],
        financialParticulars: fp,
      },
      {
        id: 'ae', scheme: '44AE', businessName: 'Transport', natureCode: '08001', description: 'Freight',
        vehicles: [{
          id: 'vehicle', vehicleNumber: 'DL01AB1234', vehicleType: 'HEAVY', tonnage: 16,
          ownedMonths: 2, leasedOrHired: true, ownedLeasedHiredFlag: 'LEASE', presumptiveIncome: 32000,
        }],
        declaredIncome: 30000, salaryInterestFromFirm: 2000, gstinTurnovers: [],
        financialParticulars: fp,
      },
    ];

    const schedule = scheduleBpFromBusinesses(businesses);
    expect(schedule.NatOfBus44AD?.[0].CodeAD).toBe('01001');
    expect(schedule.PersumptiveInc44AD?.GrsTrnOverAnyOthMode).toBe(50000);
    expect(schedule.PersumptiveInc44ADA?.GrsReceipt).toBe(400000);
    expect(schedule.GoodsDtlsUs44AE?.[0]).toMatchObject({
      OwnedLeasedHiredFlag: 'LEASE', HoldingPeriod: 2, PresumptiveIncome: 32000,
    });
    expect(schedule.PersumptiveInc44AE).toEqual({
      TotPersumInc44AE: 32000,
      SalInterestByFirm: 2000,
      TotalPersumptiveInc: 30000,
      IncChargeableUnderBus: 301000,
    });
    expect(schedule.TotalTurnoverGrsRcptGSTIN).toBe(1150000);

    const restored = businessesFromScheduleBp(schedule);
    expect(restored.map((row) => row.scheme)).toEqual(['44AD', '44ADA', '44AE']);
    expect(restored[0]).toMatchObject({
      scheme: '44AD', otherModeReceipts: 50000, digitalPresumptiveIncome: 63000,
    });
    expect(restored[1]).toMatchObject({
      scheme: '44ADA', grossReceipts: 400000, otherModeReceipts: 50000,
    });
    expect(restored[2]).toMatchObject({
      scheme: '44AE', declaredIncome: 30000, salaryInterestFromFirm: 2000,
    });
    if (restored[2].scheme !== '44AE') throw new Error('Expected 44AE');
    expect(restored[2].vehicles[0]).toMatchObject({
      vehicleNumber: 'DL01AB1234', ownedLeasedHiredFlag: 'LEASE', ownedMonths: 2,
    });
  });

  it('sums two Section 44AD entries correctly when fields arrive as backend-serialized strings', () => {
    // Backend monetary fields travel over the wire as JSON strings on a
    // loaded draft (e.g. digitalReceipts: "500000"), not numbers, even
    // though ReturnDraft's own TS type says `number`. The prior
    // implementation did `sum + row.digitalReceipts` directly -- with a
    // string right-hand side, `+` is JS string concatenation, not
    // addition. Confirmed live: adding a second Section 44AD business
    // entry (whose own digitalReceipts/declaredIncome are correctly 0,
    // since only the first entry carries the real aggregate figures) took
    // a genuine Rs 5,00,000 turnover / Rs 35,000 presumptive income and
    // corrupted them into Rs 50,00,000 / Rs 3,50,000: `0 + "500000"` =
    // "0500000", then `"0500000" + "0"` = "05000000", which parses back
    // to 5,000,000.
    const fp = createEmptyFinancialParticulars();
    const businesses = [
      {
        id: 'schedule-bp-44ad-0', scheme: '44AD' as const, businessName: 'OTHERS', natureCode: '21008', description: 'OTHERS',
        digitalReceipts: '500000' as unknown as number, nonDigitalReceipts: '0' as unknown as number, otherModeReceipts: '0' as unknown as number,
        digitalPresumptiveIncome: '35000' as unknown as number, nonDigitalPresumptiveIncome: '0' as unknown as number,
        declaredIncome: '35000' as unknown as number, gstinTurnovers: [], financialParticulars: fp,
      },
      {
        id: 'schedule-bp-44ad-1', scheme: '44AD' as const, businessName: 'Consulting Services', natureCode: '21008', description: '',
        digitalReceipts: '0' as unknown as number, nonDigitalReceipts: '0' as unknown as number, otherModeReceipts: '0' as unknown as number,
        digitalPresumptiveIncome: '0' as unknown as number, nonDigitalPresumptiveIncome: '0' as unknown as number,
        declaredIncome: '0' as unknown as number, gstinTurnovers: [], financialParticulars: fp,
      },
    ];

    const schedule = scheduleBpFromBusinesses(businesses);
    expect(schedule.PersumptiveInc44AD?.GrsTrnOverBank).toBe(500000);
    expect(schedule.PersumptiveInc44AD?.GrsTotalTrnOver).toBe(500000);
    expect(schedule.PersumptiveInc44AD?.PersumptiveInc44AD6Per).toBe(35000);
    expect(schedule.PersumptiveInc44AD?.TotPersumptiveInc44AD).toBe(35000);
  });
});
