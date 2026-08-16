import type {
  BankAccount,
  ChapterVIA,
  Donation80G,
  Employer,
  HouseProperty,
  Investment80C,
  LoanDeductions,
  ReturnDraft,
  Schedule80GGAEntry,
  Schedule80GGCEntry,
  Section80D,
  TaxChallan,
  TcsCredit,
  TdsCredit,
} from './types';
import type {
  BankManagerData,
  ChallanManagerEntry,
  DeductionLoanManagerData,
  DividendManagerEntry,
  FamilyPensionManagerEntry,
  GiftManagerEntry,
  InterestManagerEntry,
  ReturnEditorModel,
  TdsManagerEntry,
  WinningManagerEntry,
} from './editorModel';
import {
  updateBankAccounts as updateBankAccountsLegacy,
  updateBanksFromManager as updateBanksFromManagerLegacy,
  updateChallanKindFromManager as updateChallanKindFromManagerLegacy,
  updateChapterVIA as updateChapterVIALegacy,
  updateDeductionLoans as updateDeductionLoansLegacy,
  updateDeductionLoansFromManager as updateDeductionLoansFromManagerLegacy,
  updateDividendsFromManager as updateDividendsFromManagerLegacy,
  updateEmployers as updateEmployersLegacy,
  updateExemptIncome as updateExemptIncomeLegacy,
  updateFamilyPensionFromManager as updateFamilyPensionFromManagerLegacy,
  updateGiftsFromManager as updateGiftsFromManagerLegacy,
  updateHouseProperties as updateHousePropertiesLegacy,
  updateInterestFromManager as updateInterestFromManagerLegacy,
  updateOtherSources as updateOtherSourcesLegacy,
  updateSchedule80GGA as updateSchedule80GGALegacy,
  updateSchedule80GGC as updateSchedule80GGCLegacy,
  updateSection80C as updateSection80CLegacy,
  updateSection80D as updateSection80DLegacy,
  updateSection80G as updateSection80GLegacy,
  updateTaxChallans as updateTaxChallansLegacy,
  updateTaxReturnPreparer as updateTaxReturnPreparerLegacy,
  updateTcsCredits as updateTcsCreditsLegacy,
  updateTdsCredits as updateTdsCreditsLegacy,
  updateTdsFromManager as updateTdsFromManagerLegacy,
  updateWinningsFromManager as updateWinningsFromManagerLegacy,
} from './editorModel';

/** Canonical editor state. It intentionally has no legacy compatibility envelope. */
export interface ReturnEditorModelV2 {
  draft: ReturnDraft;
}

/** Immutable canonical draft transformation. */
export type DraftUpdater = (draft: ReturnDraft) => ReturnDraft;

/** Applies a canonical transformation to a detached draft. */
export function updateDraft(previous: ReturnEditorModelV2, next: DraftUpdater): ReturnEditorModelV2 {
  const detached = structuredClone(previous.draft);
  return { draft: structuredClone(next(detached)) };
}

/** Replaces the canonical draft with a detached copy. */
export function replaceDraft(draft: ReturnDraft): ReturnEditorModelV2 {
  return { draft: structuredClone(draft) };
}

function delegate(
  model: ReturnEditorModelV2,
  updater: (model: ReturnEditorModel) => ReturnEditorModel,
): ReturnEditorModelV2 {
  const result = updater({ draft: structuredClone(model.draft), extras: {} });
  const draft = structuredClone(result.draft);
  delete draft.compatibility;
  return { draft };
}

/** Replaces employers immutably. */
export function updateEmployers(model: ReturnEditorModelV2, employers: readonly Employer[]): ReturnEditorModelV2 {
  return delegate(model, (legacy) => updateEmployersLegacy(legacy, employers));
}

/** Replaces house properties immutably. */
export function updateHouseProperties(model: ReturnEditorModelV2, properties: readonly HouseProperty[], passThroughIncome = model.draft.housePropertyPassThroughIncome): ReturnEditorModelV2 {
  return delegate(model, (legacy) => updateHousePropertiesLegacy(legacy, properties, passThroughIncome));
}

/** Replaces Section 80C investments immutably. */
export function updateSection80C(model: ReturnEditorModelV2, investments: readonly Investment80C[]): ReturnEditorModelV2 {
  return delegate(model, (legacy) => updateSection80CLegacy(legacy, investments));
}

/** Replaces Section 80D details immutably. */
export function updateSection80D(model: ReturnEditorModelV2, value: Section80D): ReturnEditorModelV2 {
  return delegate(model, (legacy) => updateSection80DLegacy(legacy, value));
}

/** Replaces Section 80G donations immutably. */
export function updateSection80G(model: ReturnEditorModelV2, entries: readonly Donation80G[]): ReturnEditorModelV2 {
  return delegate(model, (legacy) => updateSection80GLegacy(legacy, entries));
}

/** Replaces deduction loans immutably. */
export function updateDeductionLoans(model: ReturnEditorModelV2, loans: LoanDeductions): ReturnEditorModelV2 {
  return delegate(model, (legacy) => updateDeductionLoansLegacy(legacy, loans));
}

/** Updates deduction loans from manager values. */
export function updateDeductionLoansFromManager(model: ReturnEditorModelV2, data: DeductionLoanManagerData): ReturnEditorModelV2 {
  return delegate(model, (legacy) => updateDeductionLoansFromManagerLegacy(legacy, data));
}

/** Replaces Chapter VI-A details immutably. */
export function updateChapterVIA(model: ReturnEditorModelV2, value: ChapterVIA): ReturnEditorModelV2 {
  return delegate(model, (legacy) => updateChapterVIALegacy(legacy, value));
}

/** Replaces Schedule 80GGA rows immutably. */
export function updateSchedule80GGA(model: ReturnEditorModelV2, entries: readonly Schedule80GGAEntry[]): ReturnEditorModelV2 {
  return delegate(model, (legacy) => updateSchedule80GGALegacy(legacy, entries));
}

/** Replaces Schedule 80GGC rows immutably. */
export function updateSchedule80GGC(model: ReturnEditorModelV2, entries: readonly Schedule80GGCEntry[]): ReturnEditorModelV2 {
  return delegate(model, (legacy) => updateSchedule80GGCLegacy(legacy, entries));
}

/** Replaces Tax Return Preparer details immutably. */
export function updateTaxReturnPreparer(model: ReturnEditorModelV2, value: ReturnDraft['taxReturnPreparer']): ReturnEditorModelV2 {
  return delegate(model, (legacy) => updateTaxReturnPreparerLegacy(legacy, value));
}

/** Replaces canonical TDS credits immutably. */
export function updateTdsCredits(model: ReturnEditorModelV2, entries: readonly TdsCredit[]): ReturnEditorModelV2 {
  return delegate(model, (legacy) => updateTdsCreditsLegacy(legacy, entries));
}

/** Updates canonical TDS credits from manager values. */
export function updateTdsFromManager(model: ReturnEditorModelV2, entries: readonly TdsManagerEntry[]): ReturnEditorModelV2 {
  return delegate(model, (legacy) => updateTdsFromManagerLegacy(legacy, entries));
}

/** Replaces canonical TCS credits immutably. */
export function updateTcsCredits(model: ReturnEditorModelV2, entries: readonly TcsCredit[]): ReturnEditorModelV2 {
  return delegate(model, (legacy) => updateTcsCreditsLegacy(legacy, entries));
}

/** Replaces canonical tax challans immutably. */
export function updateTaxChallans(model: ReturnEditorModelV2, entries: readonly TaxChallan[]): ReturnEditorModelV2 {
  return delegate(model, (legacy) => updateTaxChallansLegacy(legacy, entries));
}

/** Updates one challan kind from manager values. */
export function updateChallanKindFromManager(model: ReturnEditorModelV2, kind: TaxChallan['kind'], entries: readonly ChallanManagerEntry[]): ReturnEditorModelV2 {
  return delegate(model, (legacy) => updateChallanKindFromManagerLegacy(legacy, kind, entries));
}

/** Replaces bank accounts immutably. */
export function updateBankAccounts(model: ReturnEditorModelV2, entries: readonly BankAccount[]): ReturnEditorModelV2 {
  return delegate(model, (legacy) => updateBankAccountsLegacy(legacy, entries));
}

/** Updates bank accounts from manager values. */
export function updateBanksFromManager(model: ReturnEditorModelV2, data: BankManagerData): ReturnEditorModelV2 {
  return delegate(model, (legacy) => updateBanksFromManagerLegacy(legacy, data));
}

/** Replaces exempt-income data immutably. */
export function updateExemptIncome(model: ReturnEditorModelV2, value: ReturnDraft['exemptIncome']): ReturnEditorModelV2 {
  return delegate(model, (legacy) => updateExemptIncomeLegacy(legacy, value));
}

/** Replaces other-sources data immutably. */
export function updateOtherSources(model: ReturnEditorModelV2, value: ReturnDraft['otherSources']): ReturnEditorModelV2 {
  return delegate(model, (legacy) => updateOtherSourcesLegacy(legacy, value));
}

/** Updates interest rows from manager values. */
export function updateInterestFromManager(model: ReturnEditorModelV2, entries: readonly InterestManagerEntry[]): ReturnEditorModelV2 {
  return delegate(model, (legacy) => updateInterestFromManagerLegacy(legacy, entries));
}

/** Updates dividend rows from manager values. */
export function updateDividendsFromManager(model: ReturnEditorModelV2, entries: readonly DividendManagerEntry[]): ReturnEditorModelV2 {
  return delegate(model, (legacy) => updateDividendsFromManagerLegacy(legacy, entries));
}

/** Updates family pension from manager values. */
export function updateFamilyPensionFromManager(model: ReturnEditorModelV2, entry: FamilyPensionManagerEntry): ReturnEditorModelV2 {
  return delegate(model, (legacy) => updateFamilyPensionFromManagerLegacy(legacy, entry));
}

/** Updates winnings from manager values. */
export function updateWinningsFromManager(model: ReturnEditorModelV2, entries: readonly WinningManagerEntry[]): ReturnEditorModelV2 {
  return delegate(model, (legacy) => updateWinningsFromManagerLegacy(legacy, entries));
}

/** Updates gifts from manager values. */
export function updateGiftsFromManager(model: ReturnEditorModelV2, entries: readonly GiftManagerEntry[]): ReturnEditorModelV2 {
  return delegate(model, (legacy) => updateGiftsFromManagerLegacy(legacy, entries));
}
