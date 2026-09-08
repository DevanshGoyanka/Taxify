import { describe, expect, it } from 'vitest';
import type { PrefillExtraction } from './prefillTypes';
import { mapPrefillToDraftPatch } from './mapPrefillToDraftPatch';

function prefill(): PrefillExtraction {
  return {
    personal_info: { pan: 'ABCDE1234F', aadhaar_card_no: '123412341234', name: { first_name: 'A', middle_name: 'B', surname_or_org_name: 'C' }, assessee_ver_name: '', father_name: 'Parent', dob: '1990-01-01', status: 'I', employer_category: '', address: { residence_no: '1', residence_name: 'Home', road_or_street: 'Road', locality_or_area: 'Area', city_or_town_or_district: 'City', state_code: '29', country_code: '91', pin_code: '560001', zip_code: '', country_code_mobile: 91, mobile_no: 9876543210, country_code_mobile_sec: 0, mobile_no_sec: 0, email_address: 'a@example.com', email_address_secondary: '' }, residential_status: '' },
    filing_status: { return_file_sec: 11, residential_status: '', section_115ba: '', assessee_rep_flg: '' },
    employer_entries: [{ employer_name: 'Acme', tan: 'ABCD12345E', gross_salary: 1000, salary: 900, value_of_perquisites: 50, profits_in_lieu_of_salary: 50, nature_of_employment: 'PE', employer_address: 'Office', employer_city: 'City', employer_state_code: '29', employer_pin_code: '560001', employer_zip_code: '' }],
    salary_insights: { salary: 0, perquisites_value: 0, profits_in_salary: 0 }, house_property: [],
    other_sources: { dividend_gross: 100, interest_from_savings_bank: 200, interest_from_term_deposit: 300, interest_from_others: 0, rent_from_mach_plant_bldgs: 0, lottery_puzzle_income: 0, other_income_details: [] },
    bank_accounts: [{ bank_account_no: '123', bank_name: 'Bank', ifsc_code: 'BANK0123456', account_type: 'SB', use_for_refund: 'true' }],
    tds_salary_entries: [{ deductor_name: 'Acme', tan: 'ABCD12345E', section: '192', income_amount: 1000, tds_deducted: 100, tds_claimed: 100, gross_amount: 1000, head_of_income: '', deducted_year: '2025-26' }], tds_other_entries: [],
    deductions: { section_80c: 150000, section_80d: 0, section_80e: 0, section_80g: 0, section_80ccd_1b: 0, section_80tta: 0, section_80ttb: 0, section_80ccch: 0, total_chap_via_deductions: 150000 },
    verification: { assessee_ver_name: '', assessee_ver_pan: '', father_name: '', capacity: '', place: 'City' },
    presumptive_income: { gross_receipt_44ada: 0, declared_income_44ada: 0, business_nature_codes: [], total_presumptive_income_44ad: 0, total_presumptive_income_44ada: 0, presumptive_income_44ad_6pct: 0, presumptive_income_44ad_8pct: 0, businesses: [], gstin_turnovers: [], goods_carriages_44ae: [] },
    assessment_year: '2026-27', pan: 'ABCDE1234F',
  };
}

describe('mapPrefillToDraftPatch', () => {
  it('contributes personal info + refund bank account + presumptive business (no employers/TDS/income/deductions)', () => {
    const patch = mapPrefillToDraftPatch(prefill());
    // Personal info is emitted.
    expect(patch.personal).toMatchObject({ name: 'A B C', pan: 'ABCDE1234F', city: 'City' });
    expect(patch.filing?.filingSection).toBe('139(1)');
    // Refund bank account is emitted.
    expect(patch.bankAccounts?.[0]).toMatchObject({ accountNumber: '123', bankName: 'Bank', useForRefund: true });
    // No presumptive business data in the base fixture → businesses undefined.
    expect(patch.businesses).toBeUndefined();
    // Everything else is owned by the reconciled patch — prefill must NOT
    // emit it, otherwise mergeDraft's append-only list semantics duplicate
    // the same employer/TDS/income across prefill + reconciled.
    expect(patch.employers).toBeUndefined();
    expect(patch.taxes).toBeUndefined();
    expect(patch.otherSources).toBeUndefined();
    expect(patch.deductions).toBeUndefined();
  });

  it('seeds draft.businesses from prior-year 44AD/44ADA/44AE rows', () => {
    const data = prefill();
    data.presumptive_income!.businesses = [
      { scheme: '44AD', code: '01001', name_of_business: 'Acme Traders', description: '' },
      { scheme: '44ADA', code: '14001', name_of_business: 'Legal Practice', description: '' },
      { scheme: '44AE', code: '08001', name_of_business: 'Transport Co', description: '' },
    ];
    data.presumptive_income!.gross_receipt_44ada = 4000000;
    data.presumptive_income!.goods_carriages_44ae = [
      { reg_number: 'KA01', tonnage: 16, holding_period: 12, owned_leased_hired: 'OWN' },
    ];
    const patch = mapPrefillToDraftPatch(data);
    expect(patch.businesses).toBeDefined();
    expect(patch.businesses).toHaveLength(3);
    const ad = patch.businesses!.find((b) => b.scheme === '44AD');
    expect(ad).toMatchObject({ scheme: '44AD', businessName: 'Acme Traders', natureCode: '01001' });
    const ada = patch.businesses!.find((b) => b.scheme === '44ADA');
    expect(ada).toMatchObject({ scheme: '44ADA', businessName: 'Legal Practice', natureCode: '14001', grossReceipts: 4000000 });
    const ae = patch.businesses!.find((b) => b.scheme === '44AE') as any;
    expect(ae?.vehicles).toHaveLength(1);
    expect(ae?.vehicles?.[0]).toMatchObject({ vehicleNumber: 'KA01', vehicleType: 'HEAVY', tonnage: 16, ownedMonths: 12, leasedOrHired: false });
  });

  it('maps personal info even when only pan + personal_info are present', () => {
    const patch = mapPrefillToDraftPatch({
      assessment_year: '2026-27',
      pan: 'ABCDE1234F',
      personal_info: { pan: 'ABCDE1234F', name: { first_name: 'Solo' }, dob: '1990-01-01' },
    } as PrefillExtraction);
    expect(patch.personal).toMatchObject({ name: 'Solo', pan: 'ABCDE1234F' });
    expect(patch.employers).toBeUndefined();
    expect(patch.taxes).toBeUndefined();
  });

  it('returns an empty patch for missing input', () => expect(mapPrefillToDraftPatch(undefined)).toEqual({}));

  it('maps a revised-return filing section 139(4) canonical code', () => {
    const data = prefill();
    data.filing_status!.return_file_sec = 12;
    const patch = mapPrefillToDraftPatch(data);
    expect(patch.filing?.filingSection).toBe('139(4)');
  });
});
