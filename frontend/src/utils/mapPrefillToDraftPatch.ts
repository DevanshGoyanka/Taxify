import type { ReturnDraftPatch } from '../domain/returns/draftPatch';
import { createReconciliationEvidence } from '../domain/returns/evidence';
import { normalizeEmployerCategory, normalizeStateCode } from '../domain/returns/cbdtEnums';
import type { ITR4ScheduleBPData } from '../components/business/ITR4ScheduleBPManager';
import type {
  PrefillExtraction,
  PrefillGoodsCarriage44AE,
  PrefillGstinTurnover,
  PrefillPresumptiveBusiness,
} from './prefillTypes';

function id(prefix: string, ...parts: unknown[]): string {
  const text = parts.map((part) => String(part ?? '')).join('|');
  let hash = 2166136261;
  for (let index = 0; index < text.length; index += 1) {
    hash ^= text.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return `${prefix}-${(hash >>> 0).toString(36)}`;
}

function filingSection(code: number | string | undefined): '139(1)' | '139(4)' | '139(5)' | '119(2)(b)' | undefined {
  const normalized = String(code ?? '').trim();
  const mapping: Record<string, '139(1)' | '139(4)' | '139(5)' | '119(2)(b)'> = {
    '11': '139(1)',
    '12': '139(4)',
    '13': '139(5)',
    '139(1)': '139(1)',
    '139(4)': '139(4)',
    '139(5)': '139(5)',
    '119(2)(b)': '119(2)(b)',
  };
  return mapping[normalized];
}

/** Maps the prefill's presumptive business data into canonical draft.businesses.
 *
 * Per the CBDT Prefill schema (V6.5), business data lives in two places:
 *   - form26as.persumptiveInc44ADA + form26as.scheduleBP.turnoverGrsRcptForGSTIN
 *     (current-year 44ADA gross receipts + GSTIN turnover).
 *   - lastFiledITR.natOfBus44AD/44ADA/44AE + lastFiledITR.goodsDtlsUs44AE
 *     (prior-year business rows + 44AE vehicle details).
 *
 * Prior-year rows seed the canonical draft.businesses list so the Business tab
 * has the code/name/turnover pre-populated. Current-year 44ADA gross receipts
 * flow into the first 44ADA row's grossReceipts field. GSTIN turnover rows
 * attach to the first business row (shared across all schemes). The prefill's
 * prior-year figures are ALSO surfaced to the UI as read-only reference labels
 * (see ITR4ScheduleBPManager's priorYearData prop) so the user can see last
 * year's filed values above this year's entry fields.
 */
function mapPrefillBusinesses(prefill: PrefillExtraction): ReturnDraftPatch['businesses'] {
  const pi = prefill.presumptive_income;
  if (!pi) return undefined;
  const businesses = pi.businesses ?? [];
  const gstinTurnovers = (pi.gstin_turnovers ?? []).map((g: PrefillGstinTurnover) => ({
    id: id('prefill-gstin', g.gstin, g.amount),
    gstin: g.gstin || '',
    turnover: g.amount || 0,
  }));
  if (businesses.length === 0 && gstinTurnovers.length === 0 && !pi.gross_receipt_44ada) {
    return undefined;
  }

  // Group prior-year businesses by scheme so each becomes the correct
  // discriminated-union member (Presumptive44AD/44ADA/44AE).
  const byScheme = new Map<string, PrefillPresumptiveBusiness[]>();
  for (const b of businesses) {
    const list = byScheme.get(b.scheme) ?? [];
    list.push(b);
    byScheme.set(b.scheme, list);
  }

  const draftBusinesses: NonNullable<ReturnDraftPatch['businesses']> = [];

  // 44AD — first prior-year row seeds digital/non-digital + financials.
  const adRows = byScheme.get('44AD') ?? [];
  if (adRows.length > 0) {
    const first = adRows[0];
    draftBusinesses.push({
      id: id('prefill-44ad', first.code, first.name_of_business),
      scheme: '44AD',
      businessName: first.name_of_business || '',
      natureCode: first.code || '',
      description: first.description || '',
      digitalReceipts: 0,
      nonDigitalReceipts: 0,
      digitalPresumptiveIncome: 0,
      nonDigitalPresumptiveIncome: 0,
      declaredIncome: 0,
      gstinTurnovers: gstinTurnovers,
    });
  }

  // 44ADA — current-year gross receipts from form26as.persumptiveInc44ADA.
  const adaRows = byScheme.get('44ADA') ?? [];
  if (adaRows.length > 0 || pi.gross_receipt_44ada) {
    const first = adaRows[0];
    draftBusinesses.push({
      id: id('prefill-44ada', first?.code, first?.name_of_business),
      scheme: '44ADA',
      businessName: first?.name_of_business || '',
      natureCode: first?.code || '',
      description: first?.description || '',
      grossReceipts: pi.gross_receipt_44ada || 0,
      digitalReceipts: 0,
      nonDigitalReceipts: 0,
      declaredIncome: pi.declared_income_44ada || 0,
      gstinTurnovers: adRows.length === 0 ? gstinTurnovers : gstinTurnovers,
    });
  }

  // 44AE — prior-year vehicle details seed the vehicles list.
  const aeRows = byScheme.get('44AE') ?? [];
  const carriages = pi.goods_carriages_44ae ?? [];
  if (aeRows.length > 0 || carriages.length > 0) {
    const first = aeRows[0];
    const vehicles = carriages.map((v: PrefillGoodsCarriage44AE) => ({
      id: id('prefill-44ae-veh', v.reg_number, v.holding_period),
      vehicleNumber: v.reg_number || '',
      vehicleType: (v.tonnage > 12 ? 'HEAVY' : 'OTHER') as 'HEAVY' | 'OTHER',
      tonnage: v.tonnage || 0,
      ownedMonths: v.holding_period || 1,
      leasedOrHired: v.owned_leased_hired !== 'OWN',
      presumptiveIncome: 0,
    }));
    draftBusinesses.push({
      id: id('prefill-44ae', first?.code, first?.name_of_business),
      scheme: '44AE',
      businessName: first?.name_of_business || '',
      natureCode: first?.code || '',
      description: first?.description || '',
      vehicles,
      declaredIncome: 0,
      gstinTurnovers: gstinTurnovers,
    });
  }

  return draftBusinesses.length > 0 ? draftBusinesses : undefined;
}

/** Maps an ITD prefill extraction directly into canonical draft fields.
 *
 * Prefill contributes:
 *   - Personal info + refund bank account (filing section, verification,
 *     provenance metadata).
 *   - Presumptive business income (44AD/44ADA/44AE): prior-year business
 *     rows seed draft.businesses, current-year 44ADA gross receipts flow
 *     into the 44ADA row, and GSTIN turnover attaches to each business row.
 *     The prior-year figures are also surfaced to the Business tab as
 *     read-only reference labels above this year's entry fields.
 *
 * Other income heads (salary, house property, other sources, TDS,
 * deductions, capital gains) remain owned by the reconciliation patch
 * (built from 26AS/AIS/TIS); emitting them here would duplicate when both
 * patches merge.
 */
export function mapPrefillToDraftPatch(
  prefill: PrefillExtraction | null | undefined,
): ReturnDraftPatch {
  if (!prefill) return {};
  const pi = prefill.personal_info;
  const name = pi?.name;
  const address = pi?.address;
  const topLevelSections: Array<[keyof PrefillExtraction, unknown]> = [
    ['personal_info', prefill.personal_info], ['filing_status', prefill.filing_status], ['employer_entries', prefill.employer_entries],
    ['salary_insights', prefill.salary_insights], ['house_property', prefill.house_property], ['other_sources', prefill.other_sources],
    ['bank_accounts', prefill.bank_accounts], ['tds_salary_entries', prefill.tds_salary_entries], ['tds_other_entries', prefill.tds_other_entries],
    ['deductions', prefill.deductions], ['verification', prefill.verification], ['assessment_year', prefill.assessment_year], ['pan', prefill.pan],
  ];
  const evidence = topLevelSections.filter(([, value]) => value !== null && value !== undefined && value !== '' && (!Array.isArray(value) || value.length > 0)).map(([section, value]) => createReconciliationEvidence({
    source: 'ITD_PREFILL', code: String(section), section: String(section), category: String(section).replace(/_/g, ' '),
    description: `ITD prefill ${String(section)}`, raw: { value } as Record<string, unknown>, identity: [section],
  }));
  return {
    assessmentYear: prefill.assessment_year || undefined,
    personal: {
      name: [name?.first_name, name?.middle_name, name?.surname_or_org_name].filter(Boolean).join(' '), firstName: name?.first_name,
      middleName: name?.middle_name, surnameOrOrgName: name?.surname_or_org_name, fatherName: pi?.father_name, pan: pi?.pan || prefill.pan,
      aadhaar: pi?.aadhaar_card_no, email: address?.email_address, mobile: address?.mobile_no ? String(address.mobile_no) : undefined,
      secondaryEmail: address?.email_address_secondary, secondaryMobile: address?.mobile_no_sec ? String(address.mobile_no_sec) : undefined,
      secondaryMobileCountryCode: address?.country_code_mobile_sec ? String(address.country_code_mobile_sec) : undefined,
      dateOfBirth: pi?.dob || undefined, flatNo: address?.residence_no, residenceName: address?.residence_name, roadOrStreet: address?.road_or_street,
      localityOrArea: address?.locality_or_area, city: address?.city_or_town_or_district,
      stateCode: normalizeStateCode(address?.state_code) || undefined,
      countryCode: address?.country_code,
      pinCode: address?.pin_code ? String(address.pin_code) : undefined, zipCode: address?.zip_code,
      employerCategory: normalizeEmployerCategory(pi?.employer_category) || undefined,
    },
    filing: { filingSection: filingSection(prefill.filing_status?.return_file_sec) },
    bankAccounts: (prefill.bank_accounts || []).map((account) => ({ id: id('prefill-bank', account.bank_account_no, account.ifsc_code), bankName: account.bank_name || '', accountNumber: account.bank_account_no || '', ifscCode: account.ifsc_code || '', accountType: ['SB', 'CA', 'CC', 'OD', 'NRO', 'OTH'].includes(account.account_type?.toUpperCase()) ? account.account_type.toUpperCase() as 'SB' | 'CA' | 'CC' | 'OD' | 'NRO' | 'OTH' : 'SB', useForRefund: String(account.use_for_refund).toLowerCase() === 'true' })),
    businesses: mapPrefillBusinesses(prefill),
    verification: { place: prefill.verification?.place, capacity: prefill.verification?.capacity?.toUpperCase().includes('REP') ? 'REPRESENTATIVE' : undefined },
    provenance: [{ source: 'ITD_PREFILL', importedAt: new Date().toISOString(), reference: prefill.pan || pi?.pan || '' }],
    reconciliation: { evidence, discrepancies: [] },
  };
}

/** Build a read-only prior-year Schedule BP reference from the prefill.
 *
 * Constructs the CBDT-shaped ``ITR4ScheduleBPData`` (PascalCase keys) from
 * the prefill's ``presumptive_income`` so the Business tab can display
 * last-year's filed figures as small read-only reference labels above
 * each input field. Only fields present in the prefill are populated; the
 * rest stay undefined so the UI shows no reference label for them.
 */
export function buildPriorYearBPData(prefill: PrefillExtraction | null | undefined): ITR4ScheduleBPData | null {
  if (!prefill) return null;
  const pi = prefill.presumptive_income;
  if (!pi) return null;
  const hasData = (pi.businesses?.length ?? 0) > 0
    || (pi.gstin_turnovers?.length ?? 0) > 0
    || (pi.goods_carriages_44ae?.length ?? 0) > 0
    || !!pi.gross_receipt_44ada
    || !!pi.total_presumptive_income_44ad
    || !!pi.total_presumptive_income_44ada;
  if (!hasData) return null;

  const adBusinesses = (pi.businesses ?? []).filter((b) => b.scheme === '44AD');
  const adaBusinesses = (pi.businesses ?? []).filter((b) => b.scheme === '44ADA');
  const aeBusinesses = (pi.businesses ?? []).filter((b) => b.scheme === '44AE');

  return {
    NatOfBus44AD: adBusinesses.length
      ? adBusinesses.map((b) => ({ NameOfBusiness: b.name_of_business, CodeAD: b.code, Description: b.description }))
      : undefined,
    PersumptiveInc44AD: pi.total_presumptive_income_44ad
      ? { TotPersumptiveInc44AD: pi.total_presumptive_income_44ad, PersumptiveInc44AD6Per: pi.presumptive_income_44ad_6pct, PersumptiveInc44AD8Per: pi.presumptive_income_44ad_8pct }
      : undefined,
    NatOfBus44ADA: adaBusinesses.length
      ? adaBusinesses.map((b) => ({ NameOfBusiness: b.name_of_business, CodeADA: b.code, Description: b.description }))
      : undefined,
    PersumptiveInc44ADA: (pi.gross_receipt_44ada || pi.total_presumptive_income_44ada)
      ? { GrsReceipt: pi.gross_receipt_44ada, TotPersumptiveInc44ADA: pi.total_presumptive_income_44ada }
      : undefined,
    NatOfBus44AE: aeBusinesses.length
      ? aeBusinesses.map((b) => ({ NameOfBusiness: b.name_of_business, CodeAE: b.code, Description: b.description }))
      : undefined,
    GoodsDtlsUs44AE: (pi.goods_carriages_44ae ?? []).map((v) => ({
      RegNumberGoodsCarriage: v.reg_number,
      OwnedLeasedHiredFlag: (v.owned_leased_hired || 'OWN') as 'OWN' | 'LEASE' | 'HIRED',
      TonnageCapacity: v.tonnage,
      HoldingPeriod: v.holding_period,
      PresumptiveIncome: 0,
    })),
    TurnoverGrsRcptForGSTIN: (pi.gstin_turnovers ?? []).map((g) => ({
      GSTINNo: g.gstin,
      AmtTurnGrossRcptGSTIN: g.amount,
    })),
  } as ITR4ScheduleBPData;
}
