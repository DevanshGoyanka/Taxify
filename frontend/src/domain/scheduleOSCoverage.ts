/** Official AY 2026-27 ITR-3 Schedule OS field contract. Generated from the CBDT schema. */

export type ScheduleOSFieldGroup = 'normal-rate-income' | 'dividend' | 'interest' | 'lottery-online-games-horse-race' | 'dtaa' | 'section-89a' | 'deductions' | 'special-rate-income' | 'quarterly-accrual' | 'totals';
export type ScheduleOSFieldDisposition = 'editable' | 'computed';
export interface ScheduleOSField { readonly path: string; readonly group: ScheduleOSFieldGroup; readonly disposition: ScheduleOSFieldDisposition; readonly array: boolean; }

export const SCHEDULE_OS_OFFICIAL_PATH_COUNT = 143 as const;
export const SCHEDULE_OS_FIELDS: readonly ScheduleOSField[] = [
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.GrossIncChrgblTaxAtAppRate", group: "totals", disposition: 'computed', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.DividendGross", group: "dividend", disposition: 'computed', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.DividendOthThan22e", group: "dividend", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.Dividend22e", group: "dividend", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.Dividend22f", group: "dividend", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.InterestGross", group: "interest", disposition: 'computed', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.IntrstFrmSavingBank", group: "interest", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.IntrstFrmTermDeposit", group: "interest", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.IntrstFrmIncmTaxRefund", group: "interest", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.NatofPassThrghIncome", group: "normal-rate-income", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.IntrstSec10XIFirstProviso", group: "interest", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.IntrstSec10XISecondProviso", group: "interest", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.IntrstSec10XIIFirstProviso", group: "interest", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.IntrstSec10XIISecondProviso", group: "interest", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.IntrstFrmOthers", group: "interest", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.RentFromMachPlantBldgs", group: "normal-rate-income", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.Tot562x", group: "totals", disposition: 'computed', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.Aggrtvaluewithoutcons562x", group: "normal-rate-income", disposition: 'computed', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.Immovpropwithoutcons562x", group: "normal-rate-income", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.Immovpropinadeqcons562x", group: "normal-rate-income", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.Anyotherpropwithoutcons562x", group: "normal-rate-income", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.Anyotherpropinadeqcons562x", group: "normal-rate-income", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.FamilyPension", group: "normal-rate-income", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.IncomeNotified89AOS", group: "section-89a", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.IncomeNotified89ATypeOS", group: "section-89a", disposition: 'editable', array: true },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.IncomeNotified89ATypeOS[].NOT89ACountrycode", group: "section-89a", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.IncomeNotified89ATypeOS[].NOT89AAmount", group: "section-89a", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.IncomeNotifiedOther89AOS", group: "section-89a", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.IncomeNotifiedPrYr89AOS", group: "section-89a", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.SumRecdPrYrBusTRU562xii", group: "special-rate-income", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.SumRecdPrYrLifIns562xiii", group: "special-rate-income", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.AnyOtherIncome", group: "normal-rate-income", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.OthersInc.OthersIncDtls", group: "normal-rate-income", disposition: 'editable', array: true },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.OthersInc.OthersIncDtls[].OthNatOfInc", group: "normal-rate-income", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.OthersInc.OthersIncDtls[].OthAmount", group: "normal-rate-income", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.IncChargeableSpecialRates", group: "special-rate-income", disposition: 'computed', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.LtryPzzlChrgblUs115BB", group: "lottery-online-games-horse-race", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.IncChrgblUs115BBJ", group: "lottery-online-games-horse-race", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.IncChrgblUs115BBE", group: "special-rate-income", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.CashCreditsUs68", group: "special-rate-income", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.UnExplndInvstmntsUs69", group: "special-rate-income", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.UnExplndMoneyUs69A", group: "special-rate-income", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.UnDsclsdInvstmntsUs69B", group: "normal-rate-income", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.UnExplndExpndtrUs69C", group: "special-rate-income", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.AmtBrwdRepaidOnHundiUs69D", group: "normal-rate-income", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.TaxAccumulatedBalRecPF.TaxAccmltdBalRecPFDtls", group: "special-rate-income", disposition: 'editable', array: true },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.TaxAccumulatedBalRecPF.TaxAccmltdBalRecPFDtls[].AssessmentYear", group: "special-rate-income", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.TaxAccumulatedBalRecPF.TaxAccmltdBalRecPFDtls[].IncomeBenefit", group: "special-rate-income", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.TaxAccumulatedBalRecPF.TaxAccmltdBalRecPFDtls[].TaxBenefit", group: "special-rate-income", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.TaxAccumulatedBalRecPF.TotalIncomeBenefit", group: "special-rate-income", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.TaxAccumulatedBalRecPF.TotalTaxBenefit", group: "special-rate-income", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.OthersGross", group: "special-rate-income", disposition: 'computed', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.OthersGrossDtls", group: "special-rate-income", disposition: 'editable', array: true },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.OthersGrossDtls[].SourceDescription", group: "special-rate-income", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.OthersGrossDtls[].SourceAmount", group: "special-rate-income", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.PassThrIncOSChrgblSplRate", group: "normal-rate-income", disposition: 'computed', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.PTIOthersGrossDtls", group: "special-rate-income", disposition: 'editable', array: true },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.PTIOthersGrossDtls[].SourceDescription", group: "special-rate-income", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.PTIOthersGrossDtls[].SourceAmount", group: "special-rate-income", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.IncChargblSplRateOS.TotalAmtTaxUsDTAASchOs", group: "dtaa", disposition: 'computed', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.IncChargblSplRateOS.NRIOsDTAA.NRIDTAADtlsSchOS", group: "dtaa", disposition: 'editable', array: true },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.IncChargblSplRateOS.NRIOsDTAA.NRIDTAADtlsSchOS[].DTAAamt", group: "dtaa", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.IncChargblSplRateOS.NRIOsDTAA.NRIDTAADtlsSchOS[].NatureOfIncome", group: "dtaa", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.IncChargblSplRateOS.NRIOsDTAA.NRIDTAADtlsSchOS[].CountryName", group: "dtaa", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.IncChargblSplRateOS.NRIOsDTAA.NRIDTAADtlsSchOS[].CountryCodeExcludingIndia", group: "dtaa", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.IncChargblSplRateOS.NRIOsDTAA.NRIDTAADtlsSchOS[].DTAAarticle", group: "dtaa", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.IncChargblSplRateOS.NRIOsDTAA.NRIDTAADtlsSchOS[].RateAsPerTreaty", group: "dtaa", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.IncChargblSplRateOS.NRIOsDTAA.NRIDTAADtlsSchOS[].TaxRescertifiedFlag", group: "dtaa", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.IncChargblSplRateOS.NRIOsDTAA.NRIDTAADtlsSchOS[].ItemNoincl", group: "dtaa", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.IncChargblSplRateOS.NRIOsDTAA.NRIDTAADtlsSchOS[].RateAsPerITAct", group: "dtaa", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.IncChargblSplRateOS.NRIOsDTAA.NRIDTAADtlsSchOS[].ApplicableRate", group: "dtaa", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.Deductions.Expenses", group: "deductions", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.Deductions.UsrIntExp57", group: "deductions", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.Deductions.IntExp57", group: "deductions", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.Deductions.DeductionUs57iia", group: "deductions", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.Deductions.Depreciation", group: "deductions", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.Deductions.TotDeductions", group: "deductions", disposition: 'computed', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.AmtNotDeductibleUs58", group: "deductions", disposition: 'computed', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.ProfitChargTaxUs59", group: "deductions", disposition: 'computed', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.Increliefus89AOS", group: "section-89a", disposition: 'computed', array: false },
  { path: "ScheduleOS.IncOthThanOwnRaceHorse.BalanceNoRaceHorse", group: "totals", disposition: 'computed', array: false },
  { path: "ScheduleOS.TotOthSrcNoRaceHorse", group: "totals", disposition: 'computed', array: false },
  { path: "ScheduleOS.IncFromOwnHorse.Receipts", group: "lottery-online-games-horse-race", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncFromOwnHorse.DeductSec57", group: "lottery-online-games-horse-race", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncFromOwnHorse.AmtNotDeductibleUs58", group: "lottery-online-games-horse-race", disposition: 'computed', array: false },
  { path: "ScheduleOS.IncFromOwnHorse.ProfitChargTaxUs59", group: "lottery-online-games-horse-race", disposition: 'computed', array: false },
  { path: "ScheduleOS.IncFromOwnHorse.BalanceOwnRaceHorse", group: "lottery-online-games-horse-race", disposition: 'computed', array: false },
  { path: "ScheduleOS.IncChargeable", group: "totals", disposition: 'computed', array: false },
  { path: "ScheduleOS.IncFrmLottery.DateRange.Upto15Of6", group: "lottery-online-games-horse-race", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncFrmLottery.DateRange.Up16Of6To15Of9", group: "lottery-online-games-horse-race", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncFrmLottery.DateRange.Up16Of9To15Of12", group: "lottery-online-games-horse-race", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncFrmLottery.DateRange.Up16Of12To15Of3", group: "lottery-online-games-horse-race", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncFrmLottery.DateRange.Up16Of3To31Of3", group: "lottery-online-games-horse-race", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncFrmOnGames.DateRange.Upto15Of6", group: "lottery-online-games-horse-race", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncFrmOnGames.DateRange.Upto15Of9", group: "lottery-online-games-horse-race", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncFrmOnGames.DateRange.Up16Of9To15Of12", group: "lottery-online-games-horse-race", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncFrmOnGames.DateRange.Up16Of12To15Of3", group: "lottery-online-games-horse-race", disposition: 'editable', array: false },
  { path: "ScheduleOS.IncFrmOnGames.DateRange.Up16Of3To31Of3", group: "lottery-online-games-horse-race", disposition: 'editable', array: false },
  { path: "ScheduleOS.DividendIncUs115BBDA.DateRange.Upto15Of6", group: "dividend", disposition: 'editable', array: false },
  { path: "ScheduleOS.DividendIncUs115BBDA.DateRange.Up16Of6To15Of9", group: "dividend", disposition: 'editable', array: false },
  { path: "ScheduleOS.DividendIncUs115BBDA.DateRange.Up16Of9To15Of12", group: "dividend", disposition: 'editable', array: false },
  { path: "ScheduleOS.DividendIncUs115BBDA.DateRange.Up16Of12To15Of3", group: "dividend", disposition: 'editable', array: false },
  { path: "ScheduleOS.DividendIncUs115BBDA.DateRange.Up16Of3To31Of3", group: "dividend", disposition: 'editable', array: false },
  { path: "ScheduleOS.DividendIncUs115BBDAaiii.DateRange.Upto15Of6", group: "dividend", disposition: 'editable', array: false },
  { path: "ScheduleOS.DividendIncUs115BBDAaiii.DateRange.Up16Of6To15Of9", group: "dividend", disposition: 'editable', array: false },
  { path: "ScheduleOS.DividendIncUs115BBDAaiii.DateRange.Up16Of9To15Of12", group: "dividend", disposition: 'editable', array: false },
  { path: "ScheduleOS.DividendIncUs115BBDAaiii.DateRange.Up16Of12To15Of3", group: "dividend", disposition: 'editable', array: false },
  { path: "ScheduleOS.DividendIncUs115BBDAaiii.DateRange.Up16Of3To31Of3", group: "dividend", disposition: 'editable', array: false },
  { path: "ScheduleOS.DividendIncUs115A1ai.DateRange.Upto15Of6", group: "dividend", disposition: 'editable', array: false },
  { path: "ScheduleOS.DividendIncUs115A1ai.DateRange.Up16Of6To15Of9", group: "dividend", disposition: 'editable', array: false },
  { path: "ScheduleOS.DividendIncUs115A1ai.DateRange.Up16Of9To15Of12", group: "dividend", disposition: 'editable', array: false },
  { path: "ScheduleOS.DividendIncUs115A1ai.DateRange.Up16Of12To15Of3", group: "dividend", disposition: 'editable', array: false },
  { path: "ScheduleOS.DividendIncUs115A1ai.DateRange.Up16Of3To31Of3", group: "dividend", disposition: 'editable', array: false },
  { path: "ScheduleOS.DividendIncUs115A1aA.DateRange.Upto15Of6", group: "dividend", disposition: 'editable', array: false },
  { path: "ScheduleOS.DividendIncUs115A1aA.DateRange.Upto15Of9", group: "dividend", disposition: 'editable', array: false },
  { path: "ScheduleOS.DividendIncUs115A1aA.DateRange.Up16Of9To15Of12", group: "dividend", disposition: 'editable', array: false },
  { path: "ScheduleOS.DividendIncUs115A1aA.DateRange.Up16Of12To15Of3", group: "dividend", disposition: 'editable', array: false },
  { path: "ScheduleOS.DividendIncUs115A1aA.DateRange.Up16Of3To31Of3", group: "dividend", disposition: 'editable', array: false },
  { path: "ScheduleOS.DividendIncUs115AC.DateRange.Upto15Of6", group: "dividend", disposition: 'editable', array: false },
  { path: "ScheduleOS.DividendIncUs115AC.DateRange.Up16Of6To15Of9", group: "dividend", disposition: 'editable', array: false },
  { path: "ScheduleOS.DividendIncUs115AC.DateRange.Up16Of9To15Of12", group: "dividend", disposition: 'editable', array: false },
  { path: "ScheduleOS.DividendIncUs115AC.DateRange.Up16Of12To15Of3", group: "dividend", disposition: 'editable', array: false },
  { path: "ScheduleOS.DividendIncUs115AC.DateRange.Up16Of3To31Of3", group: "dividend", disposition: 'editable', array: false },
  { path: "ScheduleOS.DividendIncUs115ACA.DateRange.Upto15Of6", group: "dividend", disposition: 'editable', array: false },
  { path: "ScheduleOS.DividendIncUs115ACA.DateRange.Up16Of6To15Of9", group: "dividend", disposition: 'editable', array: false },
  { path: "ScheduleOS.DividendIncUs115ACA.DateRange.Up16Of9To15Of12", group: "dividend", disposition: 'editable', array: false },
  { path: "ScheduleOS.DividendIncUs115ACA.DateRange.Up16Of12To15Of3", group: "dividend", disposition: 'editable', array: false },
  { path: "ScheduleOS.DividendIncUs115ACA.DateRange.Up16Of3To31Of3", group: "dividend", disposition: 'editable', array: false },
  { path: "ScheduleOS.DividendIncUs115AD1i.DateRange.Upto15Of6", group: "dividend", disposition: 'editable', array: false },
  { path: "ScheduleOS.DividendIncUs115AD1i.DateRange.Up16Of6To15Of9", group: "dividend", disposition: 'editable', array: false },
  { path: "ScheduleOS.DividendIncUs115AD1i.DateRange.Up16Of9To15Of12", group: "dividend", disposition: 'editable', array: false },
  { path: "ScheduleOS.DividendIncUs115AD1i.DateRange.Up16Of12To15Of3", group: "dividend", disposition: 'editable', array: false },
  { path: "ScheduleOS.DividendIncUs115AD1i.DateRange.Up16Of3To31Of3", group: "dividend", disposition: 'editable', array: false },
  { path: "ScheduleOS.NOT89A.DateRange.Upto15Of6", group: "section-89a", disposition: 'editable', array: false },
  { path: "ScheduleOS.NOT89A.DateRange.Up16Of6To15Of9", group: "section-89a", disposition: 'editable', array: false },
  { path: "ScheduleOS.NOT89A.DateRange.Up16Of9To15Of12", group: "section-89a", disposition: 'editable', array: false },
  { path: "ScheduleOS.NOT89A.DateRange.Up16Of12To15Of3", group: "section-89a", disposition: 'editable', array: false },
  { path: "ScheduleOS.NOT89A.DateRange.Up16Of3To31Of3", group: "section-89a", disposition: 'editable', array: false },
  { path: "ScheduleOS.DividendDTAA.DateRange.Upto15Of6", group: "dividend", disposition: 'editable', array: false },
  { path: "ScheduleOS.DividendDTAA.DateRange.Up16Of6To15Of9", group: "dividend", disposition: 'editable', array: false },
  { path: "ScheduleOS.DividendDTAA.DateRange.Up16Of9To15Of12", group: "dividend", disposition: 'editable', array: false },
  { path: "ScheduleOS.DividendDTAA.DateRange.Up16Of12To15Of3", group: "dividend", disposition: 'editable', array: false },
  { path: "ScheduleOS.DividendDTAA.DateRange.Up16Of3To31Of3", group: "dividend", disposition: 'editable', array: false },
];

export const SCHEDULE_OS_FIELDS_BY_PATH: ReadonlyMap<string, ScheduleOSField> = new Map(SCHEDULE_OS_FIELDS.map((field) => [field.path, field]));

export interface ScheduleOSUpdateResult<T> { readonly value: T; readonly changed: boolean; readonly error?: string; }

/** Returns whether an official Schedule OS path is backend-computed. */
export function isScheduleOSComputed(path: string): boolean {
  return SCHEDULE_OS_FIELDS_BY_PATH.get(path)?.disposition === 'computed';
}

/** Validates and applies one exact canonical Schedule OS field update. Computed fields remain immutable. */
export function updateScheduleOSField<T>(root: T, path: string, value: unknown): ScheduleOSUpdateResult<T> {
  const field = SCHEDULE_OS_FIELDS_BY_PATH.get(path);
  if (!field) return { value: root, changed: false, error: `Unknown Schedule OS path: ${path}` };
  if (field.disposition === 'computed') return { value: root, changed: false, error: `Computed Schedule OS field is read-only: ${path}` };
  const segments = path.replace(/^ScheduleOS\./, '').split('.');
  const clone: any = structuredClone(root);
  let cursor: any = clone;
  for (let index = 0; index < segments.length - 1; index += 1) {
    const segment = segments[index];
    if (segment === '[]') return { value: root, changed: false, error: `Array row updates require a row identifier: ${path}` };
    if (cursor === null || typeof cursor !== 'object' || !(segment in cursor)) return { value: root, changed: false, error: `Path is not present in draft: ${path}` };
    cursor = cursor[segment];
  }
  const leaf = segments[segments.length - 1];
  if (cursor === null || typeof cursor !== 'object' || leaf === '[]') return { value: root, changed: false, error: `Invalid Schedule OS leaf: ${path}` };
  cursor[leaf] = value;
  return { value: clone as T, changed: true };
}

/** Returns exact field counts by official grouping. */
export function scheduleOSCoverageByGroup(): Readonly<Record<ScheduleOSFieldGroup, number>> {
  const result: Record<ScheduleOSFieldGroup, number> = {
    'normal-rate-income': 0, dividend: 0, interest: 0, 'lottery-online-games-horse-race': 0,
    dtaa: 0, 'section-89a': 0, deductions: 0, 'special-rate-income': 0,
    'quarterly-accrual': 0, totals: 0,
  };
  for (const field of SCHEDULE_OS_FIELDS) result[field.group] += 1;
  return result;
}
