import { describe, expect, it } from 'vitest';
import { addSchedule80RARow, readSchedule80RA, schedule80IBActivities, updateSchedule80RA, validateSchedule80RARow } from './itr3Schedule80Coverage';
import { createEmptyReturnDraft } from './returns/factory';

describe('Schedule 80RA and 80IB coverage', () => {
  const row = { NameOfDonee: 'Research Institute', AddrDetail: '1 Main Road', CityOrTownOrDistrict: 'Delhi', StateCode: '07', PinCode: 110001, DoneePAN: 'ABCDE1234F', DonationAmtCash: 0, DonationAmtOtherMode: 10000, DonationAmt: 10000 };
  it('validates identity, address, PAN, and non-negative values', () => { expect(validateSchedule80RARow(row)).toEqual([]); expect(validateSchedule80RARow({ ...row, DoneePAN: 'bad', PinCode: 0, DonationAmt: -1 })).toHaveLength(3); });
  it('adds rows and updates source facts immutably', () => { const draft = createEmptyReturnDraft('2026-27', 'ITR-3', 'old'); const next = addSchedule80RARow(draft.itr3BusinessWorkspace, row); expect(readSchedule80RA(next).DonationDtlsRsrchAssctn).toHaveLength(1); expect(next).not.toBe(draft.itr3BusinessWorkspace); const changed = updateSchedule80RA(next, 0, 'DonationAmtOtherMode', 12000); expect(readSchedule80RA(changed).DonationDtlsRsrchAssctn[0].DonationAmtOtherMode).toBe(12000); });
  it('protects invalid and computed-only updates and exposes official 80IB codes', () => { const draft = createEmptyReturnDraft('2026-27', 'ITR-3', 'old'); const next = updateSchedule80RA(draft.itr3BusinessWorkspace, 0, 'DonationAmt', 1); expect(next).toBe(draft.itr3BusinessWorkspace); expect(schedule80IBActivities().DeductHousUs80_IB_10_Und.Sch80LocOrDescCode).toBe('HOUSING_PROJECT'); });
});
