// TDS/TCS section-code mapping and per-form enum scoping.
// Single source of truth for mapping the user-facing numeric section codes
// (e.g. "194A") to the official schema's abbreviated TDSSection enum codes
// (e.g. "94A"), and for scoping which codes each ITR form permits.

import type { ItrForm } from '../eligibility';

/** User-facing section code → official schema TDSSection enum code. */
export const TDS_SECTION_TO_SCHEMA: Readonly<Record<string, string>> = {
  '92A': '92A', '92B': '92B', '92C': '92C',
  '192': '92B',      // salary — non-govt default
  '192A': '192A',
  '193': '193',
  '194': '194',
  '194A': '94A',
  '194B': '94B', '194BA': '94BA',
  '194BB': '4BB',
  '194C': '94C',
  '194D': '94D',
  '194DA': '4DA',
  '194E': '94E',
  '194EE': '4EE',
  '194F': '4F',
  '194G': '4G',
  '194H': '4H',
  '194I(a)': '4-IA', '194I(b)': '4-IB',
  '194IA': '4IA',
  '194IB': '4IB',
  '194IC': '4IC',
  '194J(a)': '94J-A', '194J(b)': '94J-B',
  '194K': '94K',
  '194LA': '4LA',
  '194LB': '4LB',
  '194LC': '4LC1',
  '194LBA': '4BA1',
  '194LBB': 'LBB',
  '194LBC': 'LBC',
  '194LD': '4LD',
  '194M': '94M',
  '194N': '94N',
  '194O': '94O',
  '194P': '94P',
  '194Q': '94Q',
  '194R': '94R',
  '194S': '94S',
  '195': '195',
  '196A': '96A', '196B': '96B', '196C': '96C', '196D': '96D', '196DA': '96DA',
};

/** Reverse map: schema code → user-facing section code (first match wins). */
export const SCHEMA_TO_TDS_SECTION: Readonly<Record<string, string>> = Object.entries(TDS_SECTION_TO_SCHEMA)
  .reduce((acc, [userCode, schemaCode]) => {
    if (!(schemaCode in acc)) acc[schemaCode] = userCode;
    return acc;
  }, {} as Record<string, string>);

/** ITR-1 / ITR-4 permit only these 5 TDSSection codes (salary + PF + securities). */
export const ITR14_TDS_SECTIONS: readonly string[] = ['92A', '92B', '92C', '192A', '193'];

/** Full ITR-2 / ITR-3 TDSSection enum (59 codes, in schema order). */
export const ITR23_TDS_SECTIONS: readonly string[] = [
  '92A', '92B', '92C', '192A', '193', '194', '94A', '94B', '94BA', '4BB', '94C', '94D', '4DA',
  '94E', '4EE', '4F', '4G', '4H', '4-IA', '4-IB', '4IA', '4IB', '4IC', '94J-A', '94J-B', '94K',
  '4LA', '4LB', '4LC1', '4LC2', '4LC3', '4BA1', '4BA2', 'LBA1', 'LBA2', 'LBA3', 'LBB', '94R',
  '94S', '94B-P', '94R-P', '94S-P', 'LBC', '4LD', '94M', '94N', '94N-F', '94N-C', '94N-FT',
  '94O', '94P', '94Q', '195', '96A', '96B', '96C', '96D', '96DA', '94BA-P',
];

/** Returns the TDSSection codes permitted for the given form. */
export function tdsSectionsForForm(form: ItrForm): readonly string[] {
  return form === 'ITR-1' || form === 'ITR-4' ? ITR14_TDS_SECTIONS : ITR23_TDS_SECTIONS;
}

/** Maps a user-facing section code to the official schema enum code. */
export function toSchemaSectionCode(userCode: string): string {
  return TDS_SECTION_TO_SCHEMA[userCode] ?? userCode;
}

/** Maps a schema enum code back to the user-facing section code. */
export function fromSchemaSectionCode(schemaCode: string): string {
  return SCHEMA_TO_TDS_SECTION[schemaCode] ?? schemaCode;
}

/** Returns true when the user-facing section code is permitted for the form. */
export function isSectionAllowedForForm(userCode: string, form: ItrForm): boolean {
  return tdsSectionsForForm(form).includes(toSchemaSectionCode(userCode));
}

/** Whether a user-facing section code is a salary-TDS section (Schedule TDS1). */
export function isSalaryTdsSection(userCode: string): boolean {
  const schema = toSchemaSectionCode(userCode);
  return schema === '92A' || schema === '92B' || schema === '92C' || schema === '192A';
}

/** Whether a user-facing section code belongs to Schedule TDS-3 (tenant/buyer). */
export function isTenantTdsSection(userCode: string): boolean {
  const schema = toSchemaSectionCode(userCode);
  return schema === '4IA' || schema === '4IB' || schema === '4IC';
}

/** Classifies a TDS row into Schedule TDS1 / TDS2 / TDS3 by its section code. */
export function classifyTdsSchedule(userCode: string): 'TDS1' | 'TDS2' | 'TDS3' {
  if (isTenantTdsSection(userCode)) return 'TDS3';
  if (isSalaryTdsSection(userCode)) return 'TDS1';
  return 'TDS2';
}

/** TCS section codes (206C family). Used by the TCS capture (separate from TDS). */
export const TCS_SECTIONS: readonly string[] = [
  '206C', '206CA', '206CB', '206CC', '206CD', '206CE', '206CF', '206CG', '206CH', '206CI',
  '206CJ', '206CK', '206CL', '206CM', '206CN', '206CO', '206CP', '206CQ', '206CR', '206CT',
];

/** Whether a user-facing code is a TCS section (206C family). */
export function isTcsSection(userCode: string): boolean {
  const code = String(userCode || '');
  return code.startsWith('206C') || code === '206C';
}

/** DeductedYr enum values permitted by the schema (2008..2025). */
export const DEDUCTED_YR_OPTIONS: readonly number[] = Array.from({ length: 18 }, (_, i) => 2025 - i);

/** HeadOfIncome enum values permitted by the schema. */
export const HEAD_OF_INCOME_OPTIONS = ['HP', 'CG', 'OS', 'EI', 'NA'] as const;
/** ITR-3/4 add BP (business/profession) to the HeadOfIncome enum. */
export const HEAD_OF_INCOME_OPTIONS_BUSINESS = [...HEAD_OF_INCOME_OPTIONS, 'BP'] as const;
