/**
 * Corpus-driven source classification registry for ITR-1 imports.
 *
 * Every observed AIS / TIS / 26AS category and information code from the
 * 60+ real-client corpus is classified into one of these roles. The role
 * decides where a row lands in the canonical draft — and critically,
 * whether it is taxable ITR-1 income at all.
 *
 * ITR-1 scope rule: only rows classified `TAXABLE_ITR1` flow into the tax
 * computation. `TAX_CREDIT` rows become TDS/TCS credits. Everything else is
 * preserved as reconciliation evidence so nothing is silently dropped, but
 * control-only / acquisition / out-of-ITR-1 rows are never misclassified as
 * taxable income.
 */

import type { ReconciliationRole, RelatedTab } from './types';

/** Classification role for an imported source row. */
export type ClassificationRole = ReconciliationRole;

/** Frontend tab/schedule where a row is surfaced for review. */
export type RelatedTabVal = RelatedTab;

/** Canonical draft destination for a classified row, if any. */
export type CanonicalDestination =
  | 'employers'
  | 'otherSources.interest'
  | 'otherSources.dividends'
  | 'otherSources.winnings'
  | 'otherSources.otherIncome'
  | 'otherSources.familyPension'
  | 'otherSources.specialRateIncome'
  | 'houseProperties'
  | 'businesses'
  | 'capitalGainsSchedule'
  | 'exemptIncome'
  | 'deductions.section80C'
  | 'deductions.section80D'
  | 'deductions.section80G'
  | 'deductions.chapterVIA'
  | 'taxes.tds'
  | 'taxes.tcs'
  | 'taxes.challans'
  | 'bankAccounts'
  | 'filing'
  | 'personal'
  | 'verification'
  | 'none';

/** Classification result for one source row. */
export interface Classification {
  role: ClassificationRole;
  relatedTab: RelatedTab;
  category?: string;
  canonicalDestination?: CanonicalDestination;
  description: string;
}

/** A registry entry keyed by an exact AIS information code. */
interface CodeEntry {
  role: ClassificationRole;
  relatedTab: RelatedTab;
  canonicalDestination: CanonicalDestination;
  description: string;
}

/**
 * Classification registry for every observed AIS `information_code` in the
 * 60+ real-client corpus. Keys are upper-cased for case-insensitive lookup.
 */
const AIS_CODE_REGISTRY: Record<string, CodeEntry> = {
  'TDS-ANN.II-SAL': { role: 'TAXABLE_ITR1', relatedTab: 'SALARY', canonicalDestination: 'employers', description: 'Salary Annexure-II detail (Form 24Q).' },
  'TDS-192': { role: 'TAX_CREDIT', relatedTab: 'TAXES', canonicalDestination: 'taxes.tds', description: 'TDS on salary (section 192) tax credit.' },

  'TDS-194': { role: 'TAX_CREDIT', relatedTab: 'TAXES', canonicalDestination: 'taxes.tds', description: 'TDS on dividend (section 194) tax credit.' },
  'TDS-194A': { role: 'TAX_CREDIT', relatedTab: 'TAXES', canonicalDestination: 'taxes.tds', description: 'TDS on interest (section 194A) tax credit.' },
  'TDS-194K': { role: 'TAX_CREDIT', relatedTab: 'TAXES', canonicalDestination: 'taxes.tds', description: 'TDS on MF distribution (section 194K) tax credit.' },
  'TDS-194BA': { role: 'TAX_CREDIT', relatedTab: 'TAXES', canonicalDestination: 'taxes.tds', description: 'TDS on specified online-gaming winnings (section 194BA) tax credit.' },
  'TDS-194S': { role: 'TAX_CREDIT', relatedTab: 'TAXES', canonicalDestination: 'taxes.tds', description: 'TDS on VDA transfer (section 194S) tax credit.' },

  'TDS-194C': { role: 'OUT_OF_SCOPE_TAXABLE', relatedTab: 'BUSINESS', canonicalDestination: 'none', description: 'TDS on contractor (section 194C) — business receipts, not ITR-1 income.' },
  'TDS-194D': { role: 'OUT_OF_SCOPE_TAXABLE', relatedTab: 'BUSINESS', canonicalDestination: 'none', description: 'TDS on insurance commission (section 194D) — business income, not ITR-1.' },
  'TDS-194H': { role: 'OUT_OF_SCOPE_TAXABLE', relatedTab: 'BUSINESS', canonicalDestination: 'none', description: 'TDS on commission/brokerage (section 194H) — business income, not ITR-1.' },
  'TDS-194R': { role: 'OUT_OF_SCOPE_TAXABLE', relatedTab: 'BUSINESS', canonicalDestination: 'none', description: 'TDS on perquisite/benefit (section 194R) — not ITR-1 income.' },
  'TDS-194T': { role: 'OUT_OF_SCOPE_TAXABLE', relatedTab: 'BUSINESS', canonicalDestination: 'none', description: 'TDS on partner-firm payment (section 194T) — not ITR-1 income.' },
  'TDS-194N': { role: 'CONTROL_ONLY', relatedTab: 'RECONCILIATION', canonicalDestination: 'none', description: 'TDS on cash withdrawal (section 194N) — reporting control only.' },
  'TDS-194NF': { role: 'CONTROL_ONLY', relatedTab: 'RECONCILIATION', canonicalDestination: 'none', description: 'TDS on co-op dividend (section 194NF) — reporting control.' },
  'TDS-194IA(R)': { role: 'OUT_OF_SCOPE_TAXABLE', relatedTab: 'CAPITAL_GAINS', canonicalDestination: 'none', description: 'TDS on immovable-property sale (section 194IA) — capital gains, not ITR-1.' },
  'TDS-194IA(RV)': { role: 'OUT_OF_SCOPE_TAXABLE', relatedTab: 'CAPITAL_GAINS', canonicalDestination: 'none', description: 'TDS on immovable-property sale (section 194IA, revised) — capital gains, not ITR-1.' },
  'TDS-195': { role: 'OUT_OF_SCOPE_TAXABLE', relatedTab: 'RECONCILIATION', canonicalDestination: 'none', description: 'TDS on non-resident payments (section 195) — requires form review.' },

  'SFT-015': { role: 'TAXABLE_ITR1', relatedTab: 'OTHER_SOURCES', canonicalDestination: 'otherSources.dividends', description: 'Dividend income (SFT-015).' },
  'SFT-18(DIV)': { role: 'TAXABLE_ITR1', relatedTab: 'OTHER_SOURCES', canonicalDestination: 'otherSources.dividends', description: 'Mutual-fund dividend (SFT-18 Div).' },
  'SFT-016(SB)': { role: 'TAXABLE_ITR1', relatedTab: 'OTHER_SOURCES', canonicalDestination: 'otherSources.interest', description: 'Savings-bank interest (SFT-016 SB).' },
  'SFT-016(TD)': { role: 'TAXABLE_ITR1', relatedTab: 'OTHER_SOURCES', canonicalDestination: 'otherSources.interest', description: 'Term-deposit interest (SFT-016 TD).' },
  'SFT-016(RD)': { role: 'TAXABLE_ITR1', relatedTab: 'OTHER_SOURCES', canonicalDestination: 'otherSources.interest', description: 'Recurring-deposit interest (SFT-016 RD).' },

  'SFT-003(P)': { role: 'CONTROL_ONLY', relatedTab: 'RECONCILIATION', canonicalDestination: 'none', description: 'Cash deposit in current account (SFT-003 P) — control only.' },
  'SFT-003(R)': { role: 'CONTROL_ONLY', relatedTab: 'RECONCILIATION', canonicalDestination: 'none', description: 'Cash withdrawal from current account (SFT-003 R) — control only.' },
  'SFT-004(P)': { role: 'CONTROL_ONLY', relatedTab: 'RECONCILIATION', canonicalDestination: 'none', description: 'Cash deposit in non-current account (SFT-004 P) — control only.' },
  'SFT-004(R)': { role: 'CONTROL_ONLY', relatedTab: 'RECONCILIATION', canonicalDestination: 'none', description: 'Cash withdrawal (SFT-004 R) — control only.' },
  'SFT-005': { role: 'ACQUISITION_ONLY', relatedTab: 'RECONCILIATION', canonicalDestination: 'none', description: 'Purchase of time deposits (SFT-005) — acquisition control.' },
  'SFT-006': { role: 'CONTROL_ONLY', relatedTab: 'RECONCILIATION', canonicalDestination: 'none', description: 'Miscellaneous payment (SFT-006) — known reporting control requiring review.' },

  'SFT-17-LES(M)': { role: 'RESTRICTED_112A_TAXABLE', relatedTab: 'CAPITAL_GAINS', canonicalDestination: 'none', description: 'Sale of listed equity shares (SFT-17 LES) — Section 112A capital gains, allowed in ITR-1/4 up to ₹1.25L exemption.' },
  'SFT-17(PUR)': { role: 'ACQUISITION_ONLY', relatedTab: 'RECONCILIATION', canonicalDestination: 'none', description: 'Purchase of listed securities (SFT-17 Pur) — acquisition control, not a capital-gains event.' },
  'SFT-18-EMF(M)': { role: 'RESTRICTED_112A_TAXABLE', relatedTab: 'CAPITAL_GAINS', canonicalDestination: 'none', description: 'Sale of equity-oriented MF units (SFT-18 EMF) — Section 112A capital gains, allowed in ITR-1/4 up to ₹1.25L exemption.' },
  'SFT-18-OTU(M)': { role: 'OUT_OF_SCOPE_TAXABLE', relatedTab: 'CAPITAL_GAINS', canonicalDestination: 'none', description: 'Sale of other units (SFT-18 OTU) — non-112A capital gains, not ITR-1.' },
  'SFT-18(PUR)': { role: 'ACQUISITION_ONLY', relatedTab: 'RECONCILIATION', canonicalDestination: 'none', description: 'Purchase of mutual-fund units (SFT-18 Pur) — acquisition control.' },
  'SFT-012': { role: 'OUT_OF_SCOPE_TAXABLE', relatedTab: 'CAPITAL_GAINS', canonicalDestination: 'none', description: 'Sale of immovable property (SFT-012) — capital gains, not ITR-1.' },
  'SFT-012(P)': { role: 'ACQUISITION_ONLY', relatedTab: 'RECONCILIATION', canonicalDestination: 'none', description: 'Purchase of immovable property (SFT-012 P) — acquisition control.' },

  'EXC-GSTR3B': { role: 'CONTROL_ONLY', relatedTab: 'BUSINESS', canonicalDestination: 'none', description: 'GST turnover (GSTR-3B) — business control, not ITR-1 income.' },
  'EXC-GSTR1(P)': { role: 'CONTROL_ONLY', relatedTab: 'BUSINESS', canonicalDestination: 'none', description: 'GST purchases (GSTR-1 P) — business control.' },
};

/**
 * Classification registry for every observed TIS `category` string in the
 * 60+ real-client corpus. Keys are lower-cased for case-insensitive lookup.
 */
const TIS_CATEGORY_REGISTRY: Record<string, CodeEntry> = {
  'salary': { role: 'TAXABLE_ITR1', relatedTab: 'SALARY', canonicalDestination: 'employers', description: 'Salary accepted total.' },
  'interest from savings bank': { role: 'TAXABLE_ITR1', relatedTab: 'OTHER_SOURCES', canonicalDestination: 'otherSources.interest', description: 'Savings-bank interest accepted total.' },
  'interest from deposit': { role: 'TAXABLE_ITR1', relatedTab: 'OTHER_SOURCES', canonicalDestination: 'otherSources.interest', description: 'Deposit interest accepted total.' },
  'dividend': { role: 'TAXABLE_ITR1', relatedTab: 'OTHER_SOURCES', canonicalDestination: 'otherSources.dividends', description: 'Dividend accepted total.' },

  'sale of securities and units of mutual fund': { role: 'RESTRICTED_112A_TAXABLE', relatedTab: 'CAPITAL_GAINS', canonicalDestination: 'none', description: 'Sale of listed securities/MF units — Section 112A capital gains, allowed in ITR-1/4 up to ₹1.25L exemption.' },
  'purchase of securities and units of mutual funds': { role: 'ACQUISITION_ONLY', relatedTab: 'RECONCILIATION', canonicalDestination: 'none', description: 'Purchase of securities/MF units — acquisition control, not a capital-gains event.' },
  'sale of land or building': { role: 'OUT_OF_SCOPE_TAXABLE', relatedTab: 'CAPITAL_GAINS', canonicalDestination: 'none', description: 'Sale of land/building — non-112A capital gains, not ITR-1.' },
  'receipts from transfer of immovable property': { role: 'OUT_OF_SCOPE_TAXABLE', relatedTab: 'CAPITAL_GAINS', canonicalDestination: 'none', description: 'Immovable-property transfer receipts — non-112A capital gains, not ITR-1.' },
  'purchase of immovable property': { role: 'ACQUISITION_ONLY', relatedTab: 'RECONCILIATION', canonicalDestination: 'none', description: 'Purchase of immovable property — acquisition control, not a capital-gains event.' },
  'receipts on transfer of virtual digital asset': { role: 'OUT_OF_SCOPE_TAXABLE', relatedTab: 'CAPITAL_GAINS', canonicalDestination: 'none', description: 'VDA transfer receipts — non-112A capital gains, not ITR-1.' },
  'business receipts': { role: 'OUT_OF_SCOPE_TAXABLE', relatedTab: 'BUSINESS', canonicalDestination: 'none', description: 'Business receipts — not ITR-1 income.' },
  'insurance commission': { role: 'OUT_OF_SCOPE_TAXABLE', relatedTab: 'BUSINESS', canonicalDestination: 'none', description: 'Insurance commission — business income, not ITR-1.' },
  'receipt of amount by partners from partnership firm': { role: 'OUT_OF_SCOPE_TAXABLE', relatedTab: 'BUSINESS', canonicalDestination: 'none', description: 'Partner receipts from firm — requires classification.' },
  'gst turnover': { role: 'CONTROL_ONLY', relatedTab: 'BUSINESS', canonicalDestination: 'none', description: 'GST turnover — business control.' },
  'gst purchases': { role: 'CONTROL_ONLY', relatedTab: 'BUSINESS', canonicalDestination: 'none', description: 'GST purchases — business control.' },
  'winnings from online games': { role: 'OUT_OF_SCOPE_TAXABLE', relatedTab: 'OTHER_SOURCES', canonicalDestination: 'none', description: 'Online-gaming winnings (section 115BBH) — special rate, not ITR-1.' },
  'cash deposits': { role: 'CONTROL_ONLY', relatedTab: 'RECONCILIATION', canonicalDestination: 'none', description: 'Cash deposits — reporting control.' },
  'cash withdrawals': { role: 'CONTROL_ONLY', relatedTab: 'RECONCILIATION', canonicalDestination: 'none', description: 'Cash withdrawals — reporting control.' },
  'purchase of time deposits': { role: 'ACQUISITION_ONLY', relatedTab: 'RECONCILIATION', canonicalDestination: 'none', description: 'Purchase of time deposits — acquisition control.' },
  'miscellaneous payment': { role: 'CONTROL_ONLY', relatedTab: 'RECONCILIATION', canonicalDestination: 'none', description: 'Miscellaneous payment — known reporting control requiring review.' },
  'purchase of vehicle': { role: 'ACQUISITION_ONLY', relatedTab: 'RECONCILIATION', canonicalDestination: 'none', description: 'Purchase of vehicle — acquisition control.' },
  'outward foreign remittance/purchase of foreign currency': { role: 'CONTROL_ONLY', relatedTab: 'RECONCILIATION', canonicalDestination: 'none', description: 'Foreign remittance — TCS/foreign-asset control.' },
};

/**
 * Classification registry for every observed 26AS `sectionCode` / `section`
 * in the 60+ real-client corpus. Keys are upper-cased.
 */
const SECTION_26AS_REGISTRY: Record<string, CodeEntry> = {
  '192': { role: 'TAX_CREDIT', relatedTab: 'TAXES', canonicalDestination: 'taxes.tds', description: 'TDS on salary (section 192).' },
  '192A': { role: 'TAX_CREDIT', relatedTab: 'TAXES', canonicalDestination: 'taxes.tds', description: 'TDS on salary (section 192A).' },
  '193': { role: 'TAX_CREDIT', relatedTab: 'TAXES', canonicalDestination: 'taxes.tds', description: 'TDS on securities interest (section 193).' },
  '194': { role: 'TAX_CREDIT', relatedTab: 'TAXES', canonicalDestination: 'taxes.tds', description: 'TDS on dividend (section 194).' },
  '194A': { role: 'TAX_CREDIT', relatedTab: 'TAXES', canonicalDestination: 'taxes.tds', description: 'TDS on interest other than securities (section 194A).' },
  '194B': { role: 'TAX_CREDIT', relatedTab: 'TAXES', canonicalDestination: 'taxes.tds', description: 'TDS on lottery/game winnings (section 194B).' },
  '194BA': { role: 'TAX_CREDIT', relatedTab: 'TAXES', canonicalDestination: 'taxes.tds', description: 'TDS on specified online-gaming winnings (section 194BA).' },
  '194BB': { role: 'TAX_CREDIT', relatedTab: 'TAXES', canonicalDestination: 'taxes.tds', description: 'TDS on horse-race winnings (section 194BB).' },
  '194K': { role: 'TAX_CREDIT', relatedTab: 'TAXES', canonicalDestination: 'taxes.tds', description: 'TDS on MF distribution (section 194K).' },
  '194C': { role: 'TAX_CREDIT', relatedTab: 'TAXES', canonicalDestination: 'taxes.tds', description: 'TDS on contractor (section 194C) — tax credit only.' },
  '194D': { role: 'TAX_CREDIT', relatedTab: 'TAXES', canonicalDestination: 'taxes.tds', description: 'TDS on insurance commission (section 194D).' },
  '194H': { role: 'TAX_CREDIT', relatedTab: 'TAXES', canonicalDestination: 'taxes.tds', description: 'TDS on commission/brokerage (section 194H).' },
  '194I': { role: 'TAX_CREDIT', relatedTab: 'TAXES', canonicalDestination: 'taxes.tds', description: 'TDS on rent (section 194I).' },
  '194IA': { role: 'TAX_CREDIT', relatedTab: 'TAXES', canonicalDestination: 'taxes.tds', description: 'TDS on immovable-property sale (section 194IA).' },
  '194IB': { role: 'TAX_CREDIT', relatedTab: 'TAXES', canonicalDestination: 'taxes.tds', description: 'TDS on rent by individual/HUF (section 194IB).' },
  '194J': { role: 'TAX_CREDIT', relatedTab: 'TAXES', canonicalDestination: 'taxes.tds', description: 'TDS on professional/technical fees (section 194J).' },
  '194M': { role: 'TAX_CREDIT', relatedTab: 'TAXES', canonicalDestination: 'taxes.tds', description: 'TDS on payment to contractor/professional by individual (section 194M).' },
  '194N': { role: 'TAX_CREDIT', relatedTab: 'TAXES', canonicalDestination: 'taxes.tds', description: 'TDS on cash withdrawal (section 194N) — tax credit only.' },
  '194NF': { role: 'TAX_CREDIT', relatedTab: 'TAXES', canonicalDestination: 'taxes.tds', description: 'TDS on co-op dividend (section 194NF).' },
  '194O': { role: 'TAX_CREDIT', relatedTab: 'TAXES', canonicalDestination: 'taxes.tds', description: 'TDS on e-commerce operator (section 194O).' },
  '194Q': { role: 'TAX_CREDIT', relatedTab: 'TAXES', canonicalDestination: 'taxes.tds', description: 'TDS on purchase of goods (section 194Q).' },
  '194R': { role: 'TAX_CREDIT', relatedTab: 'TAXES', canonicalDestination: 'taxes.tds', description: 'TDS on perquisite/benefit (section 194R).' },
  '194S': { role: 'TAX_CREDIT', relatedTab: 'TAXES', canonicalDestination: 'taxes.tds', description: 'TDS on VDA transfer (section 194S).' },
  '194T': { role: 'TAX_CREDIT', relatedTab: 'TAXES', canonicalDestination: 'taxes.tds', description: 'TDS on partner-firm payment (section 194T).' },
  '195': { role: 'TAX_CREDIT', relatedTab: 'TAXES', canonicalDestination: 'taxes.tds', description: 'TDS on non-resident payments (section 195).' },
  '206C': { role: 'TAX_CREDIT', relatedTab: 'TAXES', canonicalDestination: 'taxes.tcs', description: 'TCS (section 206C).' },
  '206CE': { role: 'TAX_CREDIT', relatedTab: 'TAXES', canonicalDestination: 'taxes.tcs', description: 'TCS on sale of scrap/minerals (section 206CE).' },
  '206CF': { role: 'TAX_CREDIT', relatedTab: 'TAXES', canonicalDestination: 'taxes.tcs', description: 'TCS on sale of motor vehicle (section 206CF).' },
  '206CQ': { role: 'TAX_CREDIT', relatedTab: 'TAXES', canonicalDestination: 'taxes.tcs', description: 'TCS on e-commerce (section 206CQ).' },
};

const UNCLASSIFIED: CodeEntry = {
  role: 'PARSER_WARNING',
  relatedTab: 'RECONCILIATION',
  canonicalDestination: 'none',
  description: 'Unrecognized source code/category — manual review required.',
};

function lookupEntry(registry: Record<string, CodeEntry>, key: string | undefined, casing: 'upper' | 'lower' = 'upper'): CodeEntry {
  if (!key) return UNCLASSIFIED;
  const trimmed = key.trim();
  if (!trimmed) return UNCLASSIFIED;
  const normalized = casing === 'lower' ? trimmed.toLowerCase() : trimmed.toUpperCase();
  return registry[normalized] ?? UNCLASSIFIED;
}

/** Form-agnostic classification by source. Unknowns become PARSER_WARNING. */
export function classifySource(source: 'AIS' | 'TIS' | '26AS' | 'ITD_PREFILL', value: string | undefined): Classification {
  if (source === 'ITD_PREFILL') {
    return { role: 'INFORMATIONAL', relatedTab: 'RECONCILIATION', category: value || 'prefill', canonicalDestination: 'none', description: `ITD prefill ${value || 'section'}.` };
  }
  if (source === 'AIS') return classifyAisEntry(value);
  if (source === 'TIS') return classifyTisEntry(value);
  if (source === '26AS') return classify26asEntry(value);
  return { ...UNCLASSIFIED, category: value || '' };
}

/** Classify an AIS entry by its `information_code` (and optional category fallback). */
export function classifyAisEntry(informationCode: string | undefined, category?: string | undefined): Classification {
  const entry = lookupEntry(AIS_CODE_REGISTRY, informationCode);
  if (entry === UNCLASSIFIED && category) {
    const categoryEntry = lookupEntry(TIS_CATEGORY_REGISTRY, category, 'lower');
    if (categoryEntry !== UNCLASSIFIED) {
      return { ...categoryEntry, category, description: `${categoryEntry.description} (classified via AIS category)` };
    }
  }
  return { ...entry, category: category || informationCode || '' };
}

/** Classify a TIS entry by its `category` string. */
export function classifyTisEntry(category: string | undefined): Classification {
  const entry = lookupEntry(TIS_CATEGORY_REGISTRY, category, 'lower');
  return { ...entry, category: category || '' };
}

/** Classify a 26AS entry by its `sectionCode` or `section`. */
export function classify26asEntry(sectionCode: string | undefined, section?: string | undefined): Classification {
  const entry = lookupEntry(SECTION_26AS_REGISTRY, sectionCode) ?? lookupEntry(SECTION_26AS_REGISTRY, section);
  return { ...(entry ?? UNCLASSIFIED), category: sectionCode || section || '' };
}

/** True when a role represents taxable ITR-1 income. */
export function isTaxableItr1(role: ClassificationRole): boolean {
  return role === 'TAXABLE_ITR1';
}

/** True when a role represents a tax credit (TDS/TCS). */
export function isTaxCredit(role: ClassificationRole): boolean {
  return role === 'TAX_CREDIT';
}

/** True when a role requires manual review before compute. */
export function requiresReview(role: ClassificationRole): boolean {
  return role === 'PARSER_WARNING' || role === 'OUT_OF_SCOPE_TAXABLE';
}

/** Deterministic FNV-1a hash id for evidence records. */
export function deterministicEvidenceId(source: string, ...identity: unknown[]): string {
  const text = `${source}|${identity.map((value) => String(value ?? '')).join('|')}`;
  let hash = 2166136261;
  for (let index = 0; index < text.length; index += 1) {
    hash ^= text.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  const tag = source.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '') || 'src';
  return `evidence-${tag}-${(hash >>> 0).toString(36)}`;
}

/** Exposes the registries for tests/coverage assertions. Do not mutate. */
export const AIS_CLASSIFICATIONS = AIS_CODE_REGISTRY;
export const TIS_CLASSIFICATIONS = TIS_CATEGORY_REGISTRY;
export const AS26_CLASSIFICATIONS = SECTION_26AS_REGISTRY;
export const SOURCE_CLASSIFICATION_REGISTRIES = {
  ais: AIS_CODE_REGISTRY,
  tis: TIS_CATEGORY_REGISTRY,
  twentysixas: SECTION_26AS_REGISTRY,
  unclassified: UNCLASSIFIED,
} as const;
