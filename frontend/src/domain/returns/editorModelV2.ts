import { classifyTdsSchedule, toSchemaSectionCode } from './tdsSections';
import type {
  BankAccount,
  BroughtForwardLossEntry,
  CarriedForwardLossEntry,
  CapitalGainsSchedule,
  ChapterVIA,
  ClubbedIncomeEntry,
  DeductionLoan,
  DividendIncome,
  Donation80G,
  Employer,
  ESOPDeferralEntry,
  FamilyPension,
  ForeignAssetEntry,
  ForeignSourceIncomeEntry,
  ForeignTaxReliefEntry,
  GiftConsiderationKind,
  GiftIncome,
  HouseProperty,
  InterestIncome,
  InterestKind,
  Investment80C,
  LoanDeductions,
  AMTDetails,
  AssetLiabilityDetails,
  PortugueseCivilCodeDetails,
  PassThroughIncomeEntry,
  Policy80D,
  ReturnDraft,
  Schedule80GGAEntry,
  Schedule80GGCEntry,
  ScheduleSIEntry,
  Section80D,
  TaxChallan,
  TcsCredit,
  TdsCredit,
  WinningIncome,
} from './types';

/** Canonical editor state. It intentionally has no legacy compatibility envelope. */
export interface ReturnEditorModelV2 {
  draft: ReturnDraft;
}

/** Immutable canonical draft transformation. */
export type DraftUpdater = (draft: ReturnDraft) => ReturnDraft;

/** Manager entry shapes (previously re-exported from the legacy editorModel). */

export type LegacyRecord = Record<string, unknown>;

export interface InterestManagerEntry extends Partial<Omit<InterestIncome, 'kind'>> {
  id: string;
  itdTag: InterestKind;
}

export interface DividendManagerEntry {
  id?: string;
  section?: string;
  grossAmount?: number;
  dividendAmount?: number;
  tdsDeducted?: number;
  companyName?: string;
  companyPAN?: string;
  deductorTAN?: string;
  isin?: string;
  category?: DividendIncome['category'];
  q1?: number;
  q2?: number;
  q3?: number;
  q4?: number;
  q5?: number;
}

export interface FamilyPensionManagerEntry {
  grossAmount: number;
  payerName?: string;
  relationToPensioner?: string;
}

export interface WinningManagerEntry extends Partial<Omit<WinningIncome, 'id'>> {
  id: string;
  type: WinningIncome['type'];
  grossAmount: number;
  tdsDeducted: number;
}

export interface GiftManagerEntry extends Partial<Omit<GiftIncome, 'id'>> {
  id: string;
  propertyType: GiftIncome['propertyType'];
  value: number;
}

export interface DeductionLoanManagerEntry {
  id: string;
  loanTakenFrom: DeductionLoan['loanTakenFrom'];
  bankOrInstnName: string;
  lenderPAN: string;
  loanAccNo: string;
  dateOfLoan: string;
  totalLoanAmt: number;
  loanOutstandingAmt: number;
  interestAmount: number;
  firstTimeBuyerEligible?: boolean;
  vehicleRegNo?: string;
}

export interface DeductionLoanManagerData {
  section80E: { loans: DeductionLoanManagerEntry[] };
  section80EE: { loans: DeductionLoanManagerEntry[] };
  section80EEA: { loans: DeductionLoanManagerEntry[]; stampDutyValue: number };
  section80EEB: { loans: DeductionLoanManagerEntry[] };
}

export interface TdsManagerEntry {
  id: string;
  section?: string;
  deductorName?: string;
  deductorTAN?: string;
  deductorPAN?: string;
  certificateNo?: string;
  incomeAmount?: number;
  grossAmount?: number;
  tdsDeducted?: number;
  taxDeducted?: number;
  deductionDate?: string;
  uniqueTransactionNo?: string;
  financialYear?: string;
  verified26AS?: boolean;
  claimedInReturn?: boolean;
  // ── Schema-faithful enrichment (TDS-2 advanced / TDS-3 tenant / TCS) ────
  deductedYr?: number | '';
  headOfIncome?: 'HP' | 'CG' | 'OS' | 'BP' | 'EI' | 'NA';
  tdsCreditName?: 'S' | 'O';
  panOfOtherPerson?: string;
  aadhaarOfOtherPerson?: string;
  broughtFwdTDSAmt?: number;
  amtCarriedFwd?: number;
  claimOutOfTotTDSOnAmtPaid?: number;
  nameOfTenant?: string;
  panOfTenant?: string;
  aadhaarOfTenant?: string;
  grsRcptToTaxDeduct?: number;
  tdsClaimed?: number;
  // ── Schedule TCS fields (when a 206C section is in the TDS list) ──────────
  tcsCreditOwner?: '1' | '2';
  panOfSpouseOrOthrPrsn?: string;
  tcsAmtCollOwnHand?: number;
  tcsAmtCollSpouseOrOthrHand?: number;
  tcsClaimedAmtCollOwnHand?: number;
  tcsClaimedAmtCollSpouseOrOthrHand?: number;
}

export interface ChallanManagerEntry {
  id: string;
  bsrCode?: string;
  depositDate?: string;
  challanNo?: string | number;
  challanSerialNo?: string | number;
  amount?: number;
  cin?: string;
}

export type BankManagerEntry = BankAccount;
export interface BankManagerData { accounts: BankManagerEntry[] }

// ---------------------------------------------------------------------------
// Internal helpers (previously shared from the legacy editorModel).
// ---------------------------------------------------------------------------

const clone = <T>(value: T): T => structuredClone(value);
const cloneArray = <T>(value: readonly T[]): T[] => value.map((entry) => clone(entry));
const record = (value: unknown): value is LegacyRecord => value !== null && typeof value === 'object' && !Array.isArray(value);
const finiteMoney = (value: unknown): number => typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : 0;
const optionalText = (value: unknown): string => value == null ? '' : String(value);

function stableStringify(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(stableStringify).join(',')}]`;
  if (record(value)) return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${stableStringify(value[key])}`).join(',')}}`;
  return JSON.stringify(value) ?? 'null';
}

function deterministicId(prefix: string, value: unknown, index: number): string {
  const candidate = record(value) && typeof value.id === 'string' ? value.id.trim() : '';
  if (candidate) return candidate;
  const input = `${prefix}|${index}|${stableStringify(value)}`;
  let hash = 0x811c9dc5;
  for (let i = 0; i < input.length; i += 1) {
    hash ^= input.charCodeAt(i);
    hash = Math.imul(hash, 0x01000193);
  }
  return `${prefix}-${(hash >>> 0).toString(36)}`;
}

function mergeById<T extends { id: string }, U extends { id: string }>(
  previous: readonly T[],
  incoming: readonly U[],
  convert: (entry: U, prior: T | undefined, index: number) => T,
): T[] {
  const existing = new Map(previous.map((entry) => [entry.id, entry]));
  return incoming.map((entry, index) => convert(clone(entry), existing.get(entry.id), index));
}

// ---------------------------------------------------------------------------
// Core state operations.
// ---------------------------------------------------------------------------

/** Applies a canonical transformation to a detached draft. */
export function updateDraft(previous: ReturnEditorModelV2, next: DraftUpdater): ReturnEditorModelV2 {
  const detached = structuredClone(previous.draft);
  return { draft: structuredClone(next(detached)) };
}

/** Replaces the canonical draft with a detached copy (stripping any
 *  compatibility envelope so the canonical editor never carries it). */
export function replaceDraft(draft: ReturnDraft): ReturnEditorModelV2 {
  const clean = clone(draft);
  delete clean.compatibility;
  return { draft: clean };
}

/** Replaces the draft inside a V2 model immutably (stripping any
 *  compatibility envelope carried over from a legacy merge). */
function withDraft(model: ReturnEditorModelV2, draft: ReturnDraft): ReturnEditorModelV2 {
  const clean = clone(draft);
  delete clean.compatibility;
  return { draft: clean };
}

// ---------------------------------------------------------------------------
// Field updaters (operate directly on the canonical draft).
// ---------------------------------------------------------------------------

/** Replaces employers immutably. */
export function updateEmployers(model: ReturnEditorModelV2, employers: readonly Employer[]): ReturnEditorModelV2 {
  return withDraft(model, { ...model.draft, employers: cloneArray(employers) });
}

/** Replaces house properties immutably. */
export function updateHouseProperties(model: ReturnEditorModelV2, properties: readonly HouseProperty[], passThroughIncome = model.draft.housePropertyPassThroughIncome): ReturnEditorModelV2 {
  return withDraft(model, { ...model.draft, houseProperties: cloneArray(properties), housePropertyPassThroughIncome: passThroughIncome });
}

/** Replaces Section 80C investments immutably. */
export function updateSection80C(model: ReturnEditorModelV2, investments: readonly Investment80C[]): ReturnEditorModelV2 {
  return withDraft(model, { ...model.draft, deductions: { ...model.draft.deductions, section80C: cloneArray(investments) } });
}

/** Replaces Section 80D details immutably. */
export function updateSection80D(model: ReturnEditorModelV2, value: Section80D): ReturnEditorModelV2 {
  return withDraft(model, { ...model.draft, deductions: { ...model.draft.deductions, section80D: clone(value) } });
}

/** Replaces Section 80G donations immutably. */
export function updateSection80G(model: ReturnEditorModelV2, entries: readonly Donation80G[]): ReturnEditorModelV2 {
  return withDraft(model, { ...model.draft, deductions: { ...model.draft.deductions, section80G: cloneArray(entries) } });
}

/** Replaces deduction loans immutably. */
export function updateDeductionLoans(model: ReturnEditorModelV2, loans: LoanDeductions): ReturnEditorModelV2 {
  return withDraft(model, { ...model.draft, deductions: { ...model.draft.deductions, loans: clone(loans) } });
}

/** Updates deduction loans from manager values. */
export function updateDeductionLoansFromManager(model: ReturnEditorModelV2, data: DeductionLoanManagerData): ReturnEditorModelV2 {
  const loans = deductionLoansFromManager(data, model.draft.deductions.loans);
  const total = (section: DeductionLoan['section']): number => loans.loans
    .filter((loan) => loan.section === section)
    .reduce((sum, loan) => sum + finiteMoney(loan.interestAmount), 0);
  return withDraft(model, {
    ...model.draft,
    deductions: {
      ...model.draft.deductions,
      loans,
      chapterVIA: {
        ...model.draft.deductions.chapterVIA,
        section80E: total('80E'),
        section80EE: total('80EE'),
        section80EEA: total('80EEA'),
        section80EEAStampDutyValue: loans.section80EEAStampDutyValue,
        section80EEB: total('80EEB'),
      },
    },
  });
}

/** Replaces Chapter VI-A details immutably. */
export function updateChapterVIA(model: ReturnEditorModelV2, value: ChapterVIA): ReturnEditorModelV2 {
  return withDraft(model, { ...model.draft, deductions: { ...model.draft.deductions, chapterVIA: clone(value) } });
}

/** Replaces Schedule CYLA brought-forward losses immutably. */
export function updateLossesBroughtForward(model: ReturnEditorModelV2, value: ReturnDraft['lossesBroughtForward']): ReturnEditorModelV2 {
  return withDraft(model, { ...model.draft, lossesBroughtForward: clone(value) });
}

/** Replaces ITR-2/3 Schedule CFL opening loss rows immutably. */
export function updateBroughtForwardLossEntries(model: ReturnEditorModelV2, entries: readonly BroughtForwardLossEntry[]): ReturnEditorModelV2 {
  return withDraft(model, { ...model.draft, broughtForwardLossEntries: cloneArray(entries) });
}

/** Replaces ITR-2/3 carried-forward loss ledger rows immutably. */
export function updateCarriedForwardLossEntries(model: ReturnEditorModelV2, entries: readonly CarriedForwardLossEntry[]): ReturnEditorModelV2 {
  return withDraft(model, { ...model.draft, carriedForwardLossEntries: cloneArray(entries) });
}

/** Replaces Schedule SI rows immutably. */
export function updateScheduleSIEntries(model: ReturnEditorModelV2, entries: readonly ScheduleSIEntry[]): ReturnEditorModelV2 {
  return withDraft(model, { ...model.draft, scheduleSIEntries: cloneArray(entries) });
}

/** Replaces Schedule FSI rows immutably. */
export function updateForeignSourceIncome(model: ReturnEditorModelV2, entries: readonly ForeignSourceIncomeEntry[]): ReturnEditorModelV2 {
  return withDraft(model, { ...model.draft, foreignSourceIncome: cloneArray(entries) });
}

/** Replaces Schedule TR rows immutably. */
export function updateForeignTaxRelief(model: ReturnEditorModelV2, entries: readonly ForeignTaxReliefEntry[]): ReturnEditorModelV2 {
  return withDraft(model, { ...model.draft, foreignTaxRelief: cloneArray(entries) });
}

/** Replaces Schedule FA rows immutably. */
export function updateForeignAssets(model: ReturnEditorModelV2, entries: readonly ForeignAssetEntry[]): ReturnEditorModelV2 {
  return withDraft(model, { ...model.draft, foreignAssets: cloneArray(entries) });
}

/** Replaces Schedule SPI rows immutably. */
export function updateClubbedIncome(model: ReturnEditorModelV2, entries: readonly ClubbedIncomeEntry[]): ReturnEditorModelV2 {
  return withDraft(model, { ...model.draft, clubbedIncome: cloneArray(entries) });
}

/** Replaces Schedule PTI rows immutably. */
export function updatePassThroughIncomeEntries(model: ReturnEditorModelV2, entries: readonly PassThroughIncomeEntry[]): ReturnEditorModelV2 {
  return withDraft(model, { ...model.draft, passThroughIncomeEntries: cloneArray(entries) });
}

/** Replaces Schedule AMT details immutably. */
export function updateAmt(model: ReturnEditorModelV2, value: AMTDetails | null): ReturnEditorModelV2 {
  return withDraft(model, { ...model.draft, amt: value === null ? null : clone(value) });
}

/** Replaces Schedule AL details immutably. */
export function updateAssetLiability(model: ReturnEditorModelV2, value: AssetLiabilityDetails | null): ReturnEditorModelV2 {
  return withDraft(model, { ...model.draft, assetLiability: value === null ? null : clone(value) });
}

/** Replaces Schedule 5A details immutably. */
export function updatePortugueseCivilCode(model: ReturnEditorModelV2, value: PortugueseCivilCodeDetails | null): ReturnEditorModelV2 {
  return withDraft(model, { ...model.draft, portugueseCivilCode: value === null ? null : clone(value) });
}

/** Replaces Schedule ESOP rows immutably. */
export function updateEsopDeferrals(model: ReturnEditorModelV2, entries: readonly ESOPDeferralEntry[]): ReturnEditorModelV2 {
  return withDraft(model, { ...model.draft, esopDeferrals: cloneArray(entries) });
}

/** Updates the non-presumptive PGBP net-profit figure immutably. */
export function updateBpNetProfit(model: ReturnEditorModelV2, value: number): ReturnEditorModelV2 {
  const sanitized = typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : 0;
  return withDraft(model, { ...model.draft, bpNetProfit: sanitized });
}

/** Replaces the entire Capital Gains Schedule immutably.
 *
 *  The schedule is a single typed object (not an id-merged array), so a
 *  whole-replacement clone is the correct immutable update — every
 *  sub-array inside is deep-cloned by `clone`. */
export function updateCapitalGainsSchedule(model: ReturnEditorModelV2, schedule: CapitalGainsSchedule): ReturnEditorModelV2 {
  return withDraft(model, { ...model.draft, capitalGainsSchedule: clone(schedule) });
}

/** Replaces Schedule 80GGA rows immutably. */
export function updateSchedule80GGA(model: ReturnEditorModelV2, entries: readonly Schedule80GGAEntry[]): ReturnEditorModelV2 {
  const schedule80GGA = cloneArray(entries);
  const section80GGA = schedule80GGA.reduce((sum, entry) => sum + finiteMoney(entry.otherModeAmount), 0);
  return withDraft(model, {
    ...model.draft,
    deductions: {
      ...model.draft.deductions,
      schedule80GGA,
      chapterVIA: { ...model.draft.deductions.chapterVIA, section80GGA },
    },
  });
}

/** Replaces official Section 80CCC identifier rows immutably. */
export function updatePensionContribution80CCC(model: ReturnEditorModelV2, entries: readonly import('./types').PensionContribution80CCC[]): ReturnEditorModelV2 {
  return withDraft(model, { ...model.draft, deductions: { ...model.draft.deductions, pensionContribution80CCC: cloneArray(entries) } });
}

/** Replaces Schedule 80GGC rows immutably. */
export function updateSchedule80GGC(model: ReturnEditorModelV2, entries: readonly Schedule80GGCEntry[]): ReturnEditorModelV2 {
  const schedule80GGC = cloneArray(entries);
  const section80GGC = schedule80GGC.reduce((sum, entry) => sum + finiteMoney(entry.otherModeAmount), 0);
  return withDraft(model, {
    ...model.draft,
    deductions: {
      ...model.draft.deductions,
      schedule80GGC,
      chapterVIA: { ...model.draft.deductions.chapterVIA, section80GGC },
    },
  });
}

/** Replaces Tax Return Preparer details immutably. */
export function updateTaxReturnPreparer(model: ReturnEditorModelV2, value: ReturnDraft['taxReturnPreparer']): ReturnEditorModelV2 {
  return withDraft(model, { ...model.draft, taxReturnPreparer: clone(value) });
}

/** Replaces canonical TDS credits immutably. */
export function updateTdsCredits(model: ReturnEditorModelV2, entries: readonly TdsCredit[]): ReturnEditorModelV2 {
  return withDraft(model, { ...model.draft, taxes: { ...model.draft.taxes, tds: cloneArray(entries) } });
}

/** Updates canonical TDS credits from manager values. */
export function updateTdsFromManager(model: ReturnEditorModelV2, entries: readonly TdsManagerEntry[]): ReturnEditorModelV2 {
  return updateTdsCredits(model, tdsFromManager(entries, model.draft.taxes.tds));
}

/** Updates the combined tax-credit editor, partitioning TDS and TCS rows into
 *  their distinct canonical schedules. */
export function updateTaxCreditsFromManager(model: ReturnEditorModelV2, entries: readonly TdsManagerEntry[]): ReturnEditorModelV2 {
  const tdsEntries = entries.filter((entry) => !String(entry.section ?? '').startsWith('206C'));
  const tcsEntries = entries.filter((entry) => String(entry.section ?? '').startsWith('206C'));
  return withDraft(model, {
    ...model.draft,
    taxes: {
      ...model.draft.taxes,
      tds: tdsFromManager(tdsEntries, model.draft.taxes.tds),
      tcs: tcsFromManager(tcsEntries, model.draft.taxes.tcs),
    },
  });
}

/** Replaces canonical TCS credits immutably. */
export function updateTcsCredits(model: ReturnEditorModelV2, entries: readonly TcsCredit[]): ReturnEditorModelV2 {
  return withDraft(model, { ...model.draft, taxes: { ...model.draft.taxes, tcs: cloneArray(entries) } });
}

/** Replaces canonical tax challans immutably. */
export function updateTaxChallans(model: ReturnEditorModelV2, entries: readonly TaxChallan[]): ReturnEditorModelV2 {
  return withDraft(model, { ...model.draft, taxes: { ...model.draft.taxes, challans: cloneArray(entries) } });
}

/** Updates one challan kind from manager values. */
export function updateChallanKindFromManager(model: ReturnEditorModelV2, kind: TaxChallan['kind'], entries: readonly ChallanManagerEntry[]): ReturnEditorModelV2 {
  return updateTaxChallans(model, replaceChallanKind(model.draft.taxes.challans, kind, entries));
}

/** Replaces bank accounts immutably. */
export function updateBankAccounts(model: ReturnEditorModelV2, entries: readonly BankAccount[]): ReturnEditorModelV2 {
  return withDraft(model, { ...model.draft, bankAccounts: cloneArray(entries) });
}

/** Updates bank accounts from manager values. */
export function updateBanksFromManager(model: ReturnEditorModelV2, data: BankManagerData): ReturnEditorModelV2 {
  return updateBankAccounts(model, banksFromManager(data));
}

/** Replaces exempt-income data immutably. */
export function updateExemptIncome(model: ReturnEditorModelV2, value: ReturnDraft['exemptIncome']): ReturnEditorModelV2 {
  return withDraft(model, { ...model.draft, exemptIncome: clone(value) });
}

/** Replaces other-sources data immutably. */
export function updateOtherSources(model: ReturnEditorModelV2, value: ReturnDraft['otherSources']): ReturnEditorModelV2 {
  return withDraft(model, { ...model.draft, otherSources: clone(value) });
}

/** Replaces canonical dividend entries with an immutable detached copy. */
export function updateDividends(model: ReturnEditorModelV2, dividends: readonly DividendIncome[]): ReturnEditorModelV2 {
  return withDraft(model, { ...model.draft, otherSources: { ...model.draft.otherSources, dividends: cloneArray(dividends) } });
}

// ---------------------------------------------------------------------------
// Projection functions (canonical ↔ manager).
// ---------------------------------------------------------------------------

/** Projects canonical interest entries into the existing manager shape. */
export function interestToManager(entries: readonly InterestIncome[]): InterestManagerEntry[] {
  return entries.map(({ kind, ...entry }) => ({ ...clone(entry), itdTag: kind }));
}

/** Merges manager interest entries into canonical entries by ID. */
export function interestFromManager(entries: readonly InterestManagerEntry[], previous: readonly InterestIncome[] = []): InterestIncome[] {
  return mergeById(previous, entries, (entry, prior, index) => ({
    ...(prior ?? {} as InterestIncome), id: deterministicId('interest', entry, index),
    kind: entry.itdTag, grossAmount: finiteMoney(entry.grossAmount), tdsDeducted: finiteMoney(entry.tdsDeducted),
    bankName: optionalText(entry.bankName ?? prior?.bankName), accountType: entry.accountType ?? prior?.accountType ?? '',
    accountNumber: optionalText(entry.accountNumber ?? prior?.accountNumber), ifscCode: optionalText(entry.ifscCode ?? prior?.ifscCode),
    postOfficeName: optionalText(entry.postOfficeName ?? prior?.postOfficeName), accountNumberPO: optionalText(entry.accountNumberPO ?? prior?.accountNumberPO),
    nscCertificateNumber: optionalText(entry.nscCertificateNumber ?? prior?.nscCertificateNumber), yearOfPurchase: finiteMoney(entry.yearOfPurchase ?? prior?.yearOfPurchase),
    scssAccountNumber: optionalText(entry.scssAccountNumber ?? prior?.scssAccountNumber), dateOfOpening: optionalText(entry.dateOfOpening ?? prior?.dateOfOpening),
    deductorName: optionalText(entry.deductorName ?? prior?.deductorName), deductorTAN: optionalText(entry.deductorTAN ?? prior?.deductorTAN), remarks: optionalText(entry.remarks ?? prior?.remarks),
  }));
}

/** Updates canonical interest entries from manager values. */
export function updateInterestFromManager(model: ReturnEditorModelV2, entries: readonly InterestManagerEntry[]): ReturnEditorModelV2 {
  const interest = interestFromManager(entries, model.draft.otherSources.interest);
  return withDraft(model, { ...model.draft, otherSources: { ...model.draft.otherSources, interest } });
}

/** Projects canonical dividends into the compatibility manager shape. */
export function dividendsToManager(entries: readonly DividendIncome[]): DividendManagerEntry[] {
  return cloneArray(entries);
}

/** Merges partial dividend-manager rows by ID and fills complete canonical defaults. */
export function dividendsFromManager(entries: readonly DividendManagerEntry[], previous: readonly DividendIncome[] = []): DividendIncome[] {
  const normalized = entries.map((entry, index) => ({ ...entry, id: deterministicId('dividend', entry, index) }));
  return mergeById(previous, normalized, (entry, prior) => {
    const section = entry.section === '10(22e)' || entry.section === '10(22f)' ? entry.section : '194';
    return {
      ...prior,
      id: entry.id,
      section,
      grossAmount: finiteMoney(entry.grossAmount ?? entry.dividendAmount ?? prior?.grossAmount),
      tdsDeducted: finiteMoney(entry.tdsDeducted ?? prior?.tdsDeducted),
      companyName: optionalText(entry.companyName ?? prior?.companyName),
      companyPAN: optionalText(entry.companyPAN ?? prior?.companyPAN),
      deductorTAN: optionalText(entry.deductorTAN ?? prior?.deductorTAN),
      isin: optionalText(entry.isin ?? prior?.isin),
      category: entry.category ?? prior?.category ?? '',
      q1: finiteMoney(entry.q1 ?? prior?.q1),
      q2: finiteMoney(entry.q2 ?? prior?.q2),
      q3: finiteMoney(entry.q3 ?? prior?.q3),
      q4: finiteMoney(entry.q4 ?? prior?.q4),
      q5: finiteMoney(entry.q5 ?? prior?.q5),
    };
  });
}

/** Updates canonical dividend entries from partial manager rows. */
export function updateDividendsFromManager(model: ReturnEditorModelV2, entries: readonly DividendManagerEntry[]): ReturnEditorModelV2 {
  return updateDividends(model, dividendsFromManager(entries, model.draft.otherSources.dividends));
}

/** Projects family pension into the manager's optional-field shape. */
export function familyPensionToManager(entry: FamilyPension): FamilyPensionManagerEntry {
  return clone(entry);
}

/** Converts manager family pension data to its canonical shape. */
export function familyPensionFromManager(entry: FamilyPensionManagerEntry): FamilyPension {
  return { grossAmount: finiteMoney(entry.grossAmount), payerName: optionalText(entry.payerName), relationToPensioner: optionalText(entry.relationToPensioner) };
}

/** Updates canonical family pension from manager data. */
export function updateFamilyPensionFromManager(model: ReturnEditorModelV2, entry: FamilyPensionManagerEntry): ReturnEditorModelV2 {
  return withDraft(model, { ...model.draft, otherSources: { ...model.draft.otherSources, familyPension: familyPensionFromManager(entry) } });
}

/** Projects winnings into the manager shape. */
export function winningsToManager(entries: readonly WinningIncome[]): WinningManagerEntry[] { return cloneArray(entries); }

/** Merges winnings manager values by ID, preserving unexposed canonical fields. */
export function winningsFromManager(entries: readonly WinningManagerEntry[], previous: readonly WinningIncome[] = []): WinningIncome[] {
  return mergeById(previous, entries, (entry, prior, index) => ({ ...prior, id: deterministicId('winning', entry, index), type: entry.type, grossAmount: finiteMoney(entry.grossAmount), tdsDeducted: finiteMoney(entry.tdsDeducted), payerName: optionalText(entry.payerName ?? prior?.payerName), payerTAN: optionalText(entry.payerTAN ?? prior?.payerTAN), dateOfWinning: optionalText(entry.dateOfWinning ?? prior?.dateOfWinning) }));
}

/** Updates canonical winnings from manager values. */
export function updateWinningsFromManager(model: ReturnEditorModelV2, entries: readonly WinningManagerEntry[]): ReturnEditorModelV2 {
  const winnings = winningsFromManager(entries, model.draft.otherSources.winnings);
  return withDraft(model, { ...model.draft, otherSources: { ...model.draft.otherSources, winnings } });
}

/** Projects gifts into the manager shape. */
export function giftsToManager(entries: readonly GiftIncome[]): GiftManagerEntry[] { return cloneArray(entries); }

/** Merges gift manager values by ID, preserving unexposed canonical fields. */
export function giftsFromManager(entries: readonly GiftManagerEntry[], previous: readonly GiftIncome[] = []): GiftIncome[] {
  return mergeById(previous, entries, (entry, prior, index) => ({ ...prior, id: deterministicId('gift', entry, index), propertyType: entry.propertyType, value: finiteMoney(entry.value), donorName: optionalText(entry.donorName ?? prior?.donorName), donorRelation: optionalText(entry.donorRelation ?? prior?.donorRelation), dateOfReceipt: optionalText(entry.dateOfReceipt ?? prior?.dateOfReceipt), description: optionalText(entry.description ?? prior?.description), fromRelative: entry.fromRelative ?? prior?.fromRelative ?? false, receivedOnMarriage: entry.receivedOnMarriage ?? prior?.receivedOnMarriage ?? false, considerationKind: (entry.considerationKind ?? prior?.considerationKind ?? 'WITHOUT_CONSIDERATION') as GiftConsiderationKind, stampDutyValue: finiteMoney(entry.stampDutyValue ?? prior?.stampDutyValue), considerationPaid: finiteMoney(entry.considerationPaid ?? prior?.considerationPaid), fairMarketValue: finiteMoney(entry.fairMarketValue ?? prior?.fairMarketValue) }));
}

/** Updates canonical gifts from manager values. */
export function updateGiftsFromManager(model: ReturnEditorModelV2, entries: readonly GiftManagerEntry[]): ReturnEditorModelV2 {
  const gifts = giftsFromManager(entries, model.draft.otherSources.gifts);
  return withDraft(model, { ...model.draft, otherSources: { ...model.draft.otherSources, gifts } });
}

/** Projects grouped canonical deduction loans into the manager wrapper. */
export function deductionLoansToManager(value: LoanDeductions): DeductionLoanManagerData {
  const group = (section: DeductionLoan['section']): DeductionLoanManagerEntry[] => value.loans.filter((loan) => loan.section === section).map((loan) => ({ id: loan.id, loanTakenFrom: loan.loanTakenFrom, bankOrInstnName: loan.lenderName, lenderPAN: loan.lenderPAN, loanAccNo: loan.loanAccountNo, dateOfLoan: loan.dateOfLoan, totalLoanAmt: loan.totalLoanAmount, loanOutstandingAmt: loan.outstandingAmount, interestAmount: loan.interestAmount, firstTimeBuyerEligible: loan.firstTimeBuyerEligible, vehicleRegNo: loan.vehicleRegNo }));
  return { section80E: { loans: group('80E') }, section80EE: { loans: group('80EE') }, section80EEA: { loans: group('80EEA'), stampDutyValue: value.section80EEAStampDutyValue }, section80EEB: { loans: group('80EEB') } };
}

/** Converts grouped manager loans to canonical loans, preserving hidden fields by ID. */
export function deductionLoansFromManager(data: DeductionLoanManagerData, previous: LoanDeductions = { loans: [], section80EEAStampDutyValue: 0 }): LoanDeductions {
  const groups: Array<[DeductionLoan['section'], readonly DeductionLoanManagerEntry[]]> = [['80E', data.section80E.loans], ['80EE', data.section80EE.loans], ['80EEA', data.section80EEA.loans], ['80EEB', data.section80EEB.loans]];
  const existing = new Map(previous.loans.map((loan) => [loan.id, loan]));
  const loans = groups.flatMap(([section, entries]) => entries.map((entry, index): DeductionLoan => ({ ...existing.get(entry.id), id: deterministicId(`loan-${section}`, entry, index), section, loanTakenFrom: entry.loanTakenFrom, lenderName: entry.bankOrInstnName, lenderPAN: entry.lenderPAN, loanAccountNo: entry.loanAccNo, dateOfLoan: entry.dateOfLoan, totalLoanAmount: finiteMoney(entry.totalLoanAmt), outstandingAmount: finiteMoney(entry.loanOutstandingAmt), interestAmount: finiteMoney(entry.interestAmount), firstTimeBuyerEligible: entry.firstTimeBuyerEligible ?? existing.get(entry.id)?.firstTimeBuyerEligible ?? false, vehicleRegNo: optionalText(entry.vehicleRegNo ?? existing.get(entry.id)?.vehicleRegNo) })));
  return { loans, section80EEAStampDutyValue: finiteMoney(data.section80EEA.stampDutyValue) };
}

/** Projects canonical TDS entries into aliases used by the TDS editor. */
export function tdsToManager(entries: readonly TdsCredit[]): TdsManagerEntry[] {
  return entries.map((entry) => ({
    ...clone(entry), incomeAmount: entry.grossAmount, tdsDeducted: entry.taxDeducted,
    // Project the schema-enrichment fields so the UI can render saved values.
    deductedYr: entry.deductedYr, headOfIncome: entry.headOfIncome, tdsCreditName: entry.tdsCreditName,
    panOfOtherPerson: entry.panOfOtherPerson, aadhaarOfOtherPerson: entry.aadhaarOfOtherPerson,
    broughtFwdTDSAmt: entry.broughtFwdTDSAmt, amtCarriedFwd: entry.amtCarriedFwd,
    claimOutOfTotTDSOnAmtPaid: entry.claimOutOfTotTDSOnAmtPaid,
    nameOfTenant: entry.nameOfTenant, panOfTenant: entry.panOfTenant, aadhaarOfTenant: entry.aadhaarOfTenant,
    grsRcptToTaxDeduct: entry.grsRcptToTaxDeduct, tdsClaimed: entry.tdsClaimed,
    tcsCreditOwner: entry.tcsCreditOwner, panOfSpouseOrOthrPrsn: entry.panOfSpouseOrOthrPrsn,
    tcsAmtCollOwnHand: entry.tcsAmtCollOwnHand, tcsAmtCollSpouseOrOthrHand: entry.tcsAmtCollSpouseOrOthrHand,
    tcsClaimedAmtCollOwnHand: entry.tcsClaimedAmtCollOwnHand, tcsClaimedAmtCollSpouseOrOthrHand: entry.tcsClaimedAmtCollSpouseOrOthrHand,
  }));
}

/** Projects canonical TCS entries into the shared tax-credit editor shape. */
export function tcsToManager(entries: readonly TcsCredit[]): TdsManagerEntry[] {
  return entries.map((entry) => ({
    id: entry.id,
    section: '206C',
    deductorName: entry.collectorName,
    deductorTAN: entry.collectorTAN,
    incomeAmount: entry.grossAmount,
    tdsDeducted: entry.taxCollected,
    claimedInReturn: entry.claimedInReturn,
    deductedYr: entry.deductedYr,
    broughtFwdTDSAmt: entry.broughtFwdTDSAmt,
    tcsCreditOwner: entry.tcsCreditOwner,
    panOfSpouseOrOthrPrsn: entry.panOfSpouseOrOthrPrsn,
    tcsAmtCollOwnHand: entry.tcsAmtCollOwnHand,
    tcsAmtCollSpouseOrOthrHand: entry.tcsAmtCollSpouseOrOthrHand,
    tcsClaimedAmtCollOwnHand: entry.tcsClaimedAmtCollOwnHand,
    tcsClaimedAmtCollSpouseOrOthrHand: entry.tcsClaimedAmtCollSpouseOrOthrHand,
  }));
}

/** Converts shared tax-credit editor rows into canonical Schedule TCS rows. */
export function tcsFromManager(entries: readonly TdsManagerEntry[], previous: readonly TcsCredit[] = []): TcsCredit[] {
  return mergeById(previous, entries as readonly (TdsManagerEntry & { id: string })[], (entry, prior, index) => {
    const collected = finiteMoney(entry.tdsDeducted ?? entry.taxDeducted ?? prior?.taxCollected);
    return {
      ...prior,
      id: deterministicId('tcs', entry, index),
      collectorName: optionalText(entry.deductorName ?? prior?.collectorName),
      collectorTAN: optionalText(entry.deductorTAN ?? prior?.collectorTAN),
      grossAmount: finiteMoney(entry.incomeAmount ?? entry.grossAmount ?? prior?.grossAmount),
      taxCollected: collected,
      claimedInReturn: entry.claimedInReturn ?? prior?.claimedInReturn ?? true,
      tcsCreditOwner: entry.tcsCreditOwner ?? prior?.tcsCreditOwner ?? '1',
      panOfSpouseOrOthrPrsn: optionalText(entry.panOfSpouseOrOthrPrsn ?? prior?.panOfSpouseOrOthrPrsn),
      deductedYr: entry.deductedYr !== undefined && entry.deductedYr !== '' ? entry.deductedYr : (prior?.deductedYr ?? ''),
      broughtFwdTDSAmt: finiteMoney(entry.broughtFwdTDSAmt ?? prior?.broughtFwdTDSAmt),
      tcsAmtCollOwnHand: finiteMoney(entry.tcsAmtCollOwnHand ?? prior?.tcsAmtCollOwnHand ?? collected),
      tcsAmtCollSpouseOrOthrHand: finiteMoney(entry.tcsAmtCollSpouseOrOthrHand ?? prior?.tcsAmtCollSpouseOrOthrHand),
      tcsClaimedAmtCollOwnHand: finiteMoney(entry.tcsClaimedAmtCollOwnHand ?? prior?.tcsClaimedAmtCollOwnHand ?? collected),
      tcsClaimedAmtCollSpouseOrOthrHand: finiteMoney(entry.tcsClaimedAmtCollSpouseOrOthrHand ?? prior?.tcsClaimedAmtCollSpouseOrOthrHand),
      claimedPANOfSpouseOrOthrPrsn: prior?.claimedPANOfSpouseOrOthrPrsn ?? '',
    };
  });
}

/** Merges TDS editor values by ID, including UI-only PAN and certificate fields.
 *  Schema-enrichment fields (schedule, tdsSectionCode, taxDeductCreditDtls,
 *  tenant fields, etc.) are preserved from the prior row and auto-derived
 *  from the user-facing section code where possible. */
export function tdsFromManager(entries: readonly TdsManagerEntry[], previous: readonly TdsCredit[] = []): TdsCredit[] {
  return mergeById(previous, entries as readonly (TdsManagerEntry & { id: string })[], (entry, prior, index) => {
    const section = optionalText(entry.section ?? prior?.section);
    return {
      ...prior,
      id: deterministicId('tds', entry, index),
      section,
      deductorName: optionalText(entry.deductorName ?? prior?.deductorName),
      deductorTAN: optionalText(entry.deductorTAN ?? prior?.deductorTAN),
      deductorPAN: optionalText(entry.deductorPAN ?? prior?.deductorPAN),
      certificateNo: optionalText(entry.certificateNo ?? prior?.certificateNo),
      grossAmount: finiteMoney(entry.incomeAmount ?? entry.grossAmount ?? prior?.grossAmount),
      taxDeducted: finiteMoney(entry.tdsDeducted ?? entry.taxDeducted ?? prior?.taxDeducted),
      deductionDate: optionalText(entry.deductionDate ?? prior?.deductionDate),
      uniqueTransactionNo: optionalText(entry.uniqueTransactionNo ?? prior?.uniqueTransactionNo),
      financialYear: optionalText(entry.financialYear ?? prior?.financialYear),
      verified26AS: entry.verified26AS ?? prior?.verified26AS ?? false,
      claimedInReturn: entry.claimedInReturn ?? prior?.claimedInReturn ?? true,
      // Auto-derived / user-edited schema enrichment fields. Read the manager
      // entry first (UI edits), fall back to the prior canonical row, then default.
      tdsSectionCode: toSchemaSectionCode(section),
      schedule: classifyTdsSchedule(section),
      deductedYr: entry.deductedYr !== undefined && entry.deductedYr !== '' ? entry.deductedYr : (prior?.deductedYr !== undefined && prior.deductedYr !== '' ? prior.deductedYr : ''),
      headOfIncome: entry.headOfIncome ?? prior?.headOfIncome ?? 'NA',
      tdsCreditName: entry.tdsCreditName ?? prior?.tdsCreditName ?? 'S',
      panOfOtherPerson: optionalText(entry.panOfOtherPerson ?? prior?.panOfOtherPerson),
      aadhaarOfOtherPerson: optionalText(entry.aadhaarOfOtherPerson ?? prior?.aadhaarOfOtherPerson),
      broughtFwdTDSAmt: finiteMoney(entry.broughtFwdTDSAmt ?? prior?.broughtFwdTDSAmt),
      amtCarriedFwd: finiteMoney(entry.amtCarriedFwd ?? prior?.amtCarriedFwd),
      claimOutOfTotTDSOnAmtPaid: finiteMoney(entry.claimOutOfTotTDSOnAmtPaid ?? prior?.claimOutOfTotTDSOnAmtPaid),
      taxDeductCreditDtls: prior?.taxDeductCreditDtls ?? { taxDeductedOwnHands: 0, taxDeductedIncome: 0, taxDeductedTDS: finiteMoney(entry.tdsDeducted ?? entry.taxDeducted), taxClaimedOwnHands: finiteMoney(entry.tdsDeducted ?? entry.taxDeducted), taxClaimedIncome: 0, taxClaimedTDS: finiteMoney(entry.tdsDeducted ?? entry.taxDeducted), taxClaimedSpouseOthPrsnPAN: '', spouseOthPrsnAadhaar: '' },
      nameOfTenant: optionalText(entry.nameOfTenant ?? prior?.nameOfTenant),
      grsRcptToTaxDeduct: finiteMoney(entry.grsRcptToTaxDeduct ?? prior?.grsRcptToTaxDeduct),
      tdsClaimed: finiteMoney(entry.tdsClaimed ?? prior?.tdsClaimed),
      panOfTenant: optionalText(entry.panOfTenant ?? prior?.panOfTenant),
      aadhaarOfTenant: optionalText(entry.aadhaarOfTenant ?? prior?.aadhaarOfTenant),
      // Schedule TCS fields (a 206C row stored in the TDS list carries these).
      tcsCreditOwner: entry.tcsCreditOwner ?? prior?.tcsCreditOwner ?? '1',
      panOfSpouseOrOthrPrsn: optionalText(entry.panOfSpouseOrOthrPrsn ?? prior?.panOfSpouseOrOthrPrsn),
      tcsAmtCollOwnHand: finiteMoney(entry.tcsAmtCollOwnHand ?? prior?.tcsAmtCollOwnHand),
      tcsAmtCollSpouseOrOthrHand: finiteMoney(entry.tcsAmtCollSpouseOrOthrHand ?? prior?.tcsAmtCollSpouseOrOthrHand),
      tcsClaimedAmtCollOwnHand: finiteMoney(entry.tcsClaimedAmtCollOwnHand ?? prior?.tcsClaimedAmtCollOwnHand),
      tcsClaimedAmtCollSpouseOrOthrHand: finiteMoney(entry.tcsClaimedAmtCollSpouseOrOthrHand ?? prior?.tcsClaimedAmtCollSpouseOrOthrHand),
    };
  });
}

/** Projects one challan kind into the editor shape. */
export function challansToManager(challans: readonly TaxChallan[], kind: TaxChallan['kind']): ChallanManagerEntry[] {
  return challans.filter((entry) => entry.kind === kind).map((entry) => ({ id: entry.id, bsrCode: entry.bsrCode, depositDate: entry.depositDate, challanSerialNo: entry.challanSerialNo, challanNo: entry.challanSerialNo, amount: entry.amount, cin: entry.cin }));
}

/** Replaces one challan kind while preserving every challan of the other kind.
 *  `challanSerialNo` is coerced to an integer per the schema's SrlNoOfChaln type. */
export function replaceChallanKind(challans: readonly TaxChallan[], kind: TaxChallan['kind'], entries: readonly ChallanManagerEntry[]): TaxChallan[] {
  const existing = new Map(challans.filter((entry) => entry.kind === kind).map((entry) => [entry.id, entry]));
  const retained = clone(challans.filter((entry) => entry.kind !== kind));
  const replacements = entries.map((entry, index): TaxChallan => {
    const prior = existing.get(entry.id);
    const serialRaw = kind === 'SELF_ASSESSMENT' ? entry.challanNo ?? entry.challanSerialNo ?? prior?.challanSerialNo : entry.challanSerialNo ?? entry.challanNo ?? prior?.challanSerialNo;
    const serial = Math.max(0, Math.min(99999, Math.trunc(Number(serialRaw)) || 0));
    const bsr = optionalText(entry.bsrCode ?? prior?.bsrCode);
    const date = optionalText(entry.depositDate ?? prior?.depositDate);
    const amount = finiteMoney(entry.amount ?? prior?.amount);
    return { ...prior, id: deterministicId(kind === 'ADVANCE_TAX' ? 'advance' : 'self-assessment', entry, index), kind, bsrCode: bsr, depositDate: date, challanSerialNo: serial, amount, cin: deriveCin(bsr, date, serial) };
  });
  return [...retained, ...replacements];
}

/** Derives the Challan Identification Number (CIN) from BSR, date and serial. */
function deriveCin(bsr: string, date: string, serial: number): string {
  const bsrValid = bsr && /^[0-9]{3}[0-9A-Z]{4}$/.test(bsr);
  const dateCompact = String(date || '').replaceAll('-', '');
  const serialValid = serial > 0 && serial <= 99999;
  return bsrValid && dateCompact.length === 8 && serialValid
    ? `${bsr}-${dateCompact}-${String(serial).padStart(5, '0')}`
    : '';
}

/** Projects canonical bank accounts into the manager wrapper. */
export function banksToManager(accounts: readonly BankAccount[]): BankManagerData { return { accounts: cloneArray(accounts) }; }

/** Converts the manager bank wrapper to detached canonical accounts. */
export function banksFromManager(data: BankManagerData): BankAccount[] { return cloneArray(data.accounts); }

/** Produces a detached copy of a policy list for typed 80D manager integration. */
export function clonePolicies(policies: readonly Policy80D[]): Policy80D[] { return cloneArray(policies); }
