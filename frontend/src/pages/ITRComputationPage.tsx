import React, { useState, useEffect, useMemo, useRef, useCallback, type SetStateAction } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAY } from '../contexts/AYContext';
import { itrApi } from '../api/itr';
import { itrV2 } from '../api/itrV2';
import { clientsApi } from '../api/clients';
import { itrAutomationApi } from '../api/itrAutomation';
import type { AutomationJob } from '../api/itrAutomation';
import { Spinner } from '../components/ui/Spinner';import StatusPill from '../components/StatusPill';
import toast from 'react-hot-toast';
import { EmployerEntryManager } from '../components/EmployerEntryManager';
import { BankAccountManager } from '../components/BankAccountManager';
import { PersonalInfoTab } from '../components/PersonalInfoTab';
import { CapitalGainsEntryManager, hasNonSimplifiedCapitalGains } from '../components/CapitalGainsEntryManager';
import { BusinessProfessionEntryManager } from '../components/BusinessProfessionEntryManager';
import { BankInterestEntryManager } from '../components/BankInterestEntryManager';
import { DonationEntryManager } from '../components/DonationEntryManager';
import { HousePropertyEntryManager } from '../components/HousePropertyEntryManager';
import EmployerReconciliationModal from '../components/EmployerReconciliationModal';
import { ITD_COUNTRY_CODES } from '../constants/itdCountryCodes';
import ExemptIncomeWorkspace from '../components/exemptincome/ExemptIncomeWorkspace';
import {
  createReturnRepository, stripCompatibility,
  applyLegacyPatch, applyLegacySetStateAction,
  banksToManager, challansToManager, composeLegacyPayload, createReturnEditorModelFromLegacy,
  deductionLoansToManager, familyPensionToManager, giftsToManager, interestToManager, tdsToManager,
  updateBankAccounts, updateBanksFromManager, updateChallanKindFromManager, updateDeductionLoansFromManager,
  updateDividendsFromManager, updateEmployers, updateExemptIncome, updateFamilyPensionFromManager, updateGiftsFromManager,
  updateHouseProperties, updateInterestFromManager, updateOtherSources, updateSection80C, updateSection80D, updateSection80G,
  updateChapterVIA, updateTdsFromManager, updateTcsCredits, updateWinningsFromManager, winningsToManager, type LegacyRecord,
  updateSchedule80GGA, updateSchedule80GGC, updateTaxReturnPreparer,
  type ReturnEditorModel,
} from '../domain/returns';
import {
  assessFormEligibility, assessFormEligibilityFromDraft, collectEligibilityFacts, type FormRecommendation, type ItrForm,
} from '../domain/returns';
import { activeSchedules, blockingSchedules, type ScheduleStatus } from '../domain/returns';
import ImportConfirmationModal from '../components/ImportConfirmationModal';
import type { ReconciledResults } from '../api/itrAutomation';
import { mapReconciledToFormData } from '../utils/mapReconciledToFormData';
import { mapPrefillToFormData } from '../utils/mapPrefillToFormData';
// TEMPORARILY DISABLED (Phase 2 testing) — See FILED_RETURN_REACTIVATION_GUIDE.md
// REACTIVATE: import { mapFiledReturnToFormData } from '../utils/mapFiledReturnToFormData';
import { calculateAgeFromDob as deriveAgeFromDob, getReferenceDate } from '../utils/age';
import { mergeDraft } from '../domain/returns/draftPatch';
import { replaceDraft } from '../domain/returns/editorModelV2';
import { mapPrefillToDraftPatch } from '../utils/mapPrefillToDraftPatch';
import { mapReconciledToDraftPatch } from '../utils/mapReconciledToDraftPatch';
import { mapAisToDraftPatch } from '../utils/mapAisToDraftPatch';
import { map26asToDraftPatch } from '../utils/map26asToDraftPatch';
import { mapTisToDraftPatch } from '../utils/mapTisToDraftPatch';

const returnRepository = createReturnRepository();

/**
 * Derive age from DOB using the shared assessment-year-aware utility.
 *
 * The current ITR-1 production scope supports AY 2026-27; the shared utility
 * keeps this call-site ready for a future assessment-year configuration.
 */
function calculateAgeFromDob(dob: string | undefined | null): number {
  return deriveAgeFromDob(dob, '2026-27');
}

function validateCapitalGainsSchedule(schedule: any, form: string): string | null {
  if (!schedule) return null;
  const panPattern = /^[A-Z]{5}[0-9]{4}[A-Z]$/;
  const isinPattern = /^IN[A-Z0-9]{10}$/;
  const simple = form === 'ITR1' || form === 'ITR4';
  const itr3 = form === 'ITR3';
  if (simple) {
    const block = schedule.simplified112A || {};
    if (block.totalSaleConsideration !== undefined && Number(block.totalSaleConsideration) < 0) return '112A sale consideration cannot be negative.';
    if (block.totalCostAcquisition !== undefined && Number(block.totalCostAcquisition) < 0) return '112A cost of acquisition cannot be negative.';
    return null;
  }
  const numberRow = (rows: any[], required: string[], context: string): string | null => {
    for (const row of rows) {
      for (const key of required) {
        const value = row[key];
        const missing = value === undefined || value === '' || value === null;
        if (missing) return `${context}: ${key.replace(/([A-Z])/g, ' $1').toLowerCase()} is required.`;
        if (typeof value === 'string' && (key === 'name' || key === 'doneeName' || key === 'firmName' || key === 'address') && String(value).length > 250) return `${context}: ${key} exceeds the 250-character limit.`;
      }
    }
    return null;
  };
  const scripRequired = ['isin','name','totalSaleValue','costWithoutIndexation','acquisitionCost','fmvPerUnit','totalFmv','transferExpenses'];
  let error = numberRow(schedule.schedule112A || [], scripRequired, 'Schedule 112A');
  if (error) return error;
  error = numberRow(schedule.schedule115AD || [], scripRequired, 'Schedule 115AD');
  if (error) return error;
  for (const scrip of [...(schedule.schedule112A || []), ...(schedule.schedule115AD || [])]) if (String(scrip.isin) && !isinPattern.test(String(scrip.isin))) return 'Every Schedule 112A / 115AD scrip requires a valid ISIN in the form INE012345678.';
  const vdaRequired = ['dateOfAcquisition','dateOfTransfer','head','acquisitionCost','consideration'];
  error = numberRow(schedule.vda || [], vdaRequired, 'Schedule VDA');
  if (error) return error;
  for (const vda of schedule.vda || []) {
    if (vda.dateOfAcquisition && vda.dateOfTransfer && String(vda.dateOfAcquisition) > String(vda.dateOfTransfer)) return 'VDA acquisition date must be on or before the transfer date.';
    if (vda.head && !['CG','BI'].includes(String(vda.head))) return 'VDA head must be capital gains or business income.';
    if (!itr3 && vda.head === 'BI') return 'Only ITR-3 may treat virtual digital asset transfers as business income.';
  }
  const claimRequired = ['section','dateOfTransfer','amountDeducted'];
  error = numberRow(schedule.deductionClaims || [], claimRequired, 'Deduction claims');
  if (error) return error;
  for (const claim of schedule.deductionClaims || []) {
    const allowed = itr3 ? ['54','54B','54EC','54F','115F','54D','54G','54GA'] : ['54','54B','54EC','54F','115F'];
    if (!allowed.includes(String(claim.section))) return 'Deduction section is not permitted for the selected form.';
    if (claim.ifsc && !/^[A-Z]{4}0[A-Z0-9]{6}$/.test(String(claim.ifsc))) return 'Deduction IFSC must follow the ABCD0123456 pattern.';
    if (claim.accountNumber && String(claim.accountNumber).length > 20) return 'Capital Gains Account number cannot exceed 20 characters.';
  }
  for (const row of schedule.stDtaa || []) if (!row.countryName || !row.countryCode || !row.article || Number(row.treatyRate) < 0 || !row.itActSection || Number(row.itActRate) < 0) return 'Complete every STCG DTAA row with country, article, treaty rate and Income-tax Act section and rate.';
  for (const row of schedule.ltDtaa || []) if (!row.countryName || !row.countryCode || !row.article || Number(row.treatyRate) < 0 || !row.itActSection || Number(row.itActRate) < 0) return 'Complete every LTCG DTAA row with country, article, treaty rate and Income-tax Act section and rate.';
  for (const row of schedule.stImmovable || []) {
    const transferees = row.transferees || [];
    if (transferees.length === 0) return 'STCG land/building rows require at least one transferee.';
    for (const buyer of transferees) if (!buyer.name || Number(buyer.share) < 0 || Number(buyer.share) > 100 || Number(buyer.amount) < 0 || (buyer.pan && !panPattern.test(String(buyer.pan)))) return 'Complete every STCG transferee with name, valid optional PAN, share 0–100 and non-negative amount.';
  }
  for (const row of schedule.ltImmovable || []) {
    const transferees = row.transferees || [];
    if (transferees.length === 0) return 'LTCG land/building rows require at least one transferee.';
    for (const buyer of transferees) if (!buyer.name || Number(buyer.share) < 0 || Number(buyer.share) > 100 || Number(buyer.amount) < 0 || (buyer.pan && !panPattern.test(String(buyer.pan)))) return 'Complete every LTCG transferee with name, valid optional PAN, share 0–100 and non-negative amount.';
    for (const improvement of row.improvements || []) if (!improvement.financialYear || Number(improvement.cost) < 0) return 'Complete every improvement with a financial year and non-negative cost.';
    for (const exemption of row.exemptions || []) if (!exemption.section || Number(exemption.amount) < 0) return 'Complete every exemption with a section and non-negative amount.';
  }
  return null;
}

function getRestrictedCapitalGainsState(formData: any, taxResult: any): {
  hasTransactions: boolean;
  hasEvidence: boolean;
  hasUnsupportedRows: boolean;
  hasIneligibleIssues: boolean;
  hasIncompleteEvidence: boolean;
  hasFormLevelLosses: boolean;
  eligibility: Record<string, boolean>;
} {
  const transactions = Array.isArray(formData.capitalGainTransactions) ? formData.capitalGainTransactions : [];
  const supportedAssets = new Set(['LISTED_EQUITY', 'EQUITY_ORIENTED_MUTUAL_FUND', 'BUSINESS_TRUST_UNIT']);
  const summary = taxResult?.capitalGainsSummary || {};
  const issues = Array.isArray(summary.issues)
    ? summary.issues
    : Array.isArray(taxResult?.capitalGainsIssues) ? taxResult.capitalGainsIssues : [];
  const eligibilityCodes = new Set(['UNSUPPORTED_ASSET', 'NOT_LONG_TERM', 'SECTION_112A_LOSS', 'AGGREGATE_LIMIT_EXCEEDED']);
  const evidenceCodes = new Set([
    'INVALID_TRANSACTION', 'MISSING_ACQUISITION_DATE', 'MISSING_TRANSFER_DATE', 'INVALID_DATE_ORDER',
    'MISSING_SALE_VALUE', 'INVALID_SALE_VALUE', 'MISSING_ACTUAL_COST', 'INVALID_ACTUAL_COST',
    'INVALID_TRANSFER_EXPENSES', 'MISSING_STT_ACQUISITION', 'MISSING_STT_TRANSFER',
    'MISSING_RECOGNIZED_EXCHANGE', 'MISSING_FMV_31_JAN_2018', 'INVALID_FMV_31_JAN_2018',
  ]);
  const hasAnyEntry = transactions.length > 0;
  const hasSaleEntry = transactions.some((entry: any) => Number(entry?.saleCost || entry?.saleValue) > 0);
  // Form-data-only loss detection: if any 112A-eligible transaction has a
  // negative gain (sale value < actual cost), it will produce a SECTION_112A_LOSS
  // issue and require ITR-2.  This lets us detect ITR-2 eligibility *before*
  // the first backend compute, so the correct endpoint is called from the
  // start instead of falling back after a 422 rejection.
  const hasFormLevelLosses = transactions.some((entry: any) => {
    const isSupported = supportedAssets.has(String(entry?.assetType || ''));
    const sale = Number(entry?.saleCost || entry?.saleValue || 0);
    const cost = Number(entry?.actualCost || entry?.purchaseCost || 0);
    return isSupported && sale > 0 && cost > 0 && sale < cost;
  });
  return {
    hasTransactions: hasAnyEntry,
    hasEvidence: hasAnyEntry,
    hasUnsupportedRows: transactions.some((entry: any) => !supportedAssets.has(String(entry?.assetType || ''))),
    hasIneligibleIssues: issues.some((issue: any) => eligibilityCodes.has(String(issue?.code || ''))),
    hasIncompleteEvidence: issues.some((issue: any) => evidenceCodes.has(String(issue?.code || ''))),
    hasFormLevelLosses,
    eligibility: summary.eligibility || taxResult?.capitalGainsEligibility || {},
  };
}

import {
  OtherSourcesTab,
  DeductionsTab,
  TDSTab,
  TaxComputationTab, type CanonicalManagerBindings
} from './ITRComputationTabs';

export default function ITRComputationPage() {
  const { clientId: routeClientId, year } = useParams();
  const clientId = routeClientId || '';
  const navigate = useNavigate();
  const { ayParam } = useAY();
  const effectiveAssessmentYear = year || ayParam || '2026-27';
  const loadGenerationRef = useRef(0);
  const loadedReturnKeyRef = useRef('');
  const computationGenerationRef = useRef(0);
  const suppressAutoDetectRef = useRef(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [validating, setValidating] = useState(false);
  const [validationReport, setValidationReport] = useState<{ valid: boolean; errors: string[]; warnings: string[] } | null>(null);
  const [activeTab, setActiveTab] = useState(0);
  const [regime, setRegime] = useState<'old' | 'new'>('new');
  const [itrForm, setItrForm] = useState<ItrForm>('ITR-1');
  const [eligibility, setEligibility] = useState<FormRecommendation | null>(null);
  const [formLockedByUser, setFormLockedByUser] = useState(false);
  const [showImportMenu, setShowImportMenu] = useState(false);
  const [clientData, setClientData] = useState<any>(null);
  const legacyClientId = clientData?.id as number | undefined;
  
  // Automation job state
  const [automationJobId, setAutomationJobId] = useState<number | null>(null);
  const [showStatusBox, setShowStatusBox] = useState(false);
  const [statusBoxJob, setStatusBoxJob] = useState<AutomationJob | null>(null);
  
  // Part 2: Import document state
  const [importedAIS, setImportedAIS] = useState<any>(null);
  const [imported26AS, setImported26AS] = useState<any>(null);
  const [importedTIS, setImportedTIS] = useState<any>(null);
  
  // Employer reconciliation state
  const [showReconciliationModal, setShowReconciliationModal] = useState(false);
  const [reconciliationResult, setReconciliationResult] = useState<any>(null);
  const emptyFormDataRef = useRef<LegacyRecord>({
    // Personal Info - CBDT Mandatory Fields
    gender: 'M', fatherName: '', maritalStatus: 'SINGLE', nationality: 'INDIA', residentialStatus: 'ROR',
    mobileCountryCode: '91', country: '91', state: '',
    isDirector: false, holdsUnlistedShares: false, agriculturalIncome: 0,
    
    // ===== SALARY INCOME - 101% CBDT COMPLIANT =====
    // Section 17(1) - Salary Components
    basic: 0, da: 0, bonus: 0, commission: 0,
    // Allowances under Section 17(1)
    hraReceived: 0, ltaReceived: 0, ceaReceived: 0, 
    hostelAllowanceReceived: 0, transportAllowanceReceived: 0,
    medicalReimbursementReceived: 0, conveyanceAllowanceReceived: 0, 
    uniformAllowanceReceived: 0, otherAllowance: 0,
    // Perquisites under Section 17(2)
    perquisites: 0,
    rentFreeAccommodationValue: 0, carValue: 0, gasFuelPowerValue: 0,
    freeHolidayValue: 0, freeGoodsValue: 0, freeServicesValue: 0,
    stockOptionsValue: 0, professionalTaxValue: 0,
    // Profits in Lieu under Section 17(3)
    profitsInLieu: 0,
    gratuityReceived: 0, leaveEncashmentReceived: 0, 
    commutationOfPensionReceived: 0, retrenchmentCompensation: 0, vrsCompensation: 0,
    // Retirement Details
    daForRetirement: 0, retirementDate: null,
    isGovernmentEmployee: false, isPensioner: false,
    
    // ===== HRA EXEMPTION u/s 10(13A) =====
    hraRent: 0, hraMetro: false, landlordPAN: '', landlordName: '',
    
    // ===== OTHER EXEMPTIONS =====
    ltaExempt: 0, ceaExempt: 0, entertainmentAllowance: 0, otherExempt: 0,
    
    // ===== PROFESSIONAL TAX u/s 16(iii) =====
    profTax: 0,
    
    // ===== LEGACY FIELDS (backward compatibility) =====  
    allowances: 0, hra: 0, // Legacy HRA received field
    // House Property
    hpType: 'self', grossRent: 0, munTax: 0, homeLoanInt: 0, sopLoanInt: 0,
    // Capital Gains
    stcgEquityPre: 0, stcgEquityPost: 0, stcgOtherSlab: 0, 
    ltcg112APre: 0, ltcg112APost: 0, ltcgOtherPre: 0, ltcgOtherPost: 0,
    // Business Income
    bizPresumptive: '44AD', bizTurnover: 0, bizDeclared: 0, bpNetProfit: 0, businessSchedule: {},
    // ===== OTHER SOURCES - CBDT COMPLIANT =====
    // Interest Income
    interestSB: 0, interestFD: 0, interestRD: 0, nscInterest: 0, scssInterest: 0, postOfficeInterest: 0, otherInterest: 0,
    // Dividend Income
    dividendShares: 0, dividendMF: 0, dividendUnits: 0, 
    dividendCompanyName: '', dividendCompanyTAN: '',
    // Winnings (Section 115BB - 30%)
    lotteryIncome: 0, crosswordPuzzleIncome: 0, horseRaceIncome: 0, cardGameIncome: 0,
    // Gifts (Section 56(2)(x))
    giftsFromRelatives: 0, giftsFromNonRelatives: 0,
    // Other
    familyPension: 0, incomeFromITRefund: 0, accumulatedSPF: 0, casualIncome: 0,
    // Legacy
    dividends: 0, otherMisc: 0,
    // VDA
    vdaGains: 0,
    // Deductions
    s80C_epf: 0, s80C_ppf: 0, s80C_elss: 0, s80C_lic: 0, s80C_home: 0,
    s80CCD1B: 0, s80CCD2: 0, s80D_self: 0, s80D_parent: 0, s80E: 0, s80TTA: 0, s80G: 0,
    // Losses - CBDT Compliant
    bfLossHP: 0, bfLossBusiness: 0, bfLossSTCG: 0, bfLossLTCG: 0, bfLossSpeculation: 0,
    // Phase 1 Multi-Entry Structures (CBDT Compliant)
    employerEntries: [],
    capitalGainTransactions: [],
    capitalGainsSchedule: {},
    bankInterestEntries: [],
    interestEntries: [],
    donationEntries: [],
    section80C: { investments: [] },
    section80D: {
      selfSeniorCitizen: 'N', parentsSeniorCitizen: 'N',
      selfFamily: { policies: [], preventiveCheckup: 0, medicalExpense: 0 },
      selfFamilySenior: { policies: [], preventiveCheckup: 0, medicalExpense: 0 },
      parents: { policies: [], preventiveCheckup: 0, medicalExpense: 0 },
      parentsSenior: { policies: [], preventiveCheckup: 0, medicalExpense: 0 },
    },
    deductionLoans: {
      section80E: { loans: [] }, section80EE: { loans: [] },
      section80EEA: { loans: [], stampDutyValue: 0 }, section80EEB: { loans: [] },
    },
    s80DDB_usrType: '', s80DDB_diseaseCode: '',
    s80DD_natureOfDisability: '', s80DD_typeOfDisability: '', s80DD_dependentType: '',
    s80U_natureOfDisability: '', s80U_typeOfDisability: '',
    // Tax Payments - Multi-entry structures
    tdsEntries: [],
    tcsEntries: [],
    advanceTaxEntries: [],
    selfAssessmentTaxEntries: [],
    bankAccountDetails: [],
    bankAccountData: { accounts: [] },
    // Legacy single-value fields (for backward compatibility)
    tdsS192: 0, tds194A: 0, tdsOther: 0,
    adv15Jun: 0, adv15Sep: 0, adv15Dec: 0, adv15Mar: 0, selfTax: 0,
    // Age is derived from DOB when a return is hydrated; never default to a
    // potentially incorrect statutory age bracket.
    age: 0
  });
  const [editorModel, setEditorModel] = useState<ReturnEditorModel | null>(null);
  const editorRef = useRef<ReturnEditorModel | null>(null);

  // Import confirmation modal state
  const [showImportConfirmModal, setShowImportConfirmModal] = useState(false);
  const [reconciledImportData, setReconciledImportData] = useState<ReconciledResults | null>(null);
  const [reconDiscrepancies, setReconDiscrepancies] = useState<string[]>([]);

  const formData = useMemo<any>(() => editorModel ? composeLegacyPayload(editorModel) : {}, [editorModel]);
  const setFormData = useCallback((action: SetStateAction<LegacyRecord>): void => {
    setEditorModel((current) => {
      if (!current) return current;
      const next = applyLegacySetStateAction(current, action);
      editorRef.current = next;
      return next;
    });
  }, []);
  const updateEditor = useCallback((update: (current: ReturnEditorModel) => ReturnEditorModel): void => {
    setEditorModel((current) => {
      if (!current) return current;
      const next = update(current);
      editorRef.current = next;
      return next;
    });
  }, []);
  const handleRegimeChange = useCallback((nextRegime: 'old' | 'new'): void => {
    setRegime(nextRegime);
    updateEditor((current) => ({
      draft: { ...current.draft, regime: nextRegime },
      extras: { ...current.extras, regime: nextRegime, taxRegime: nextRegime, optOutNewTaxRegime: nextRegime === 'old' ? 'Y' : 'N' },
    }));
  }, [updateEditor]);

  const managers = useMemo<CanonicalManagerBindings>(() => ({
    interest: (entries) => updateEditor((model) => updateInterestFromManager(model, entries)),
    dividends: (entries) => updateEditor((model) => updateDividendsFromManager(model, entries)),
    familyPension: (entry) => updateEditor((model) => updateFamilyPensionFromManager(model, entry)),
    winnings: (entries) => updateEditor((model) => updateWinningsFromManager(model, entries)),
    otherSources: (next) => updateEditor((model) => updateOtherSources(model, next)),
    gifts: (entries) => updateEditor((model) => updateGiftsFromManager(model, entries)),
    section80C: (data) => updateEditor((model) => updateSection80C(model, data.investments)),
    section80D: (data) => updateEditor((model) => updateSection80D(model, data)),
    donations: (entries) => updateEditor((model) => updateSection80G(model, entries)),
    deductionLoans: (data) => updateEditor((model) => updateDeductionLoansFromManager(model, data)),
    chapterVIA: (next) => updateEditor((model) => updateChapterVIA(model, next)),
    schedule80GGA: (entries) => updateEditor((model) => updateSchedule80GGA(model, entries)),
    schedule80GGC: (entries) => updateEditor((model) => updateSchedule80GGC(model, entries)),
    taxReturnPreparer: (next) => updateEditor((model) => updateTaxReturnPreparer(model, next)),
    tds: (entries) => updateEditor((model) => updateTdsFromManager(model, entries)),
    tcs: (entries) => updateEditor((model) => updateTcsCredits(model, entries)),
    advanceTax: (entries) => updateEditor((model) => updateChallanKindFromManager(model, 'ADVANCE_TAX', entries)),
    selfAssessmentTax: (entries) => updateEditor((model) => updateChallanKindFromManager(model, 'SELF_ASSESSMENT', entries)),
    banks: (data) => updateEditor((model) => updateBanksFromManager(model, data)),
  }), [updateEditor]);

  useEffect(() => {
    const requestId = ++loadGenerationRef.current;
    loadedReturnKeyRef.current = '';    ++computationGenerationRef.current;
    if (taxResultDebounceRef.current) clearTimeout(taxResultDebounceRef.current);
    setBackendTaxResult(null);
    setTaxResultLoading(false);
    setTaxResultError(null);
    setClientData(null);
    setImportedAIS(null);
    setImported26AS(null);
    setImportedTIS(null);
    setReconciliationResult(null);
    setShowReconciliationModal(false);
    const resetModel = createReturnEditorModelFromLegacy(structuredClone(emptyFormDataRef.current));
    editorRef.current = resetModel;
    setEditorModel(resetModel);
    if (!clientId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    Promise.all([
      clientsApi.get(clientId),
      returnRepository.get(clientId, effectiveAssessmentYear),
    ])
      .then(([client, draft]) => {
        if (requestId !== loadGenerationRef.current) return;
        const savedModel = createReturnEditorModelFromLegacy({
          ...structuredClone(emptyFormDataRef.current),
          ...composeLegacyPayload({ draft, extras: {} }),
        });
        const itrData = composeLegacyPayload(savedModel) as any;
        loadedReturnKeyRef.current = `${clientId}:${effectiveAssessmentYear}`;
        setClientData(client);
        suppressAutoDetectRef.current = true;
        setItrForm(draft.form);
        setRegime(draft.regime);
        const hydrated = applyLegacyPatch(savedModel, {
          name: itrData.name || client.name,
          firstName: itrData.firstName || client.firstName || '',
          middleName: itrData.middleName || client.middleName || '',
          surnameOrOrgName: itrData.surnameOrOrgName || client.surname || '',
          pan: itrData.pan || client.pan,
          email: itrData.email || client.email,
          mobile: itrData.mobile || client.mobile,
          aadhaar: itrData.aadhaar || client.aadhaar,
          dob: itrData.dob || client.dob,
          // Always derive age from DOB — never trust a persisted or
          // hardcoded age value. A 65-year-old senior citizen must get
          // the ₹3L exemption bracket, not the under-60 ₹2.5L bracket.
          age: calculateAgeFromDob(itrData.dob || client.dob),
          flatNo: itrData.flatDoorNo || itrData.flatNo,
          premises: itrData.premisesName || itrData.premises,
          road: itrData.roadStreet || itrData.road,
          city: itrData.townCity || itrData.city,
          pincode: itrData.pinCode || itrData.pincode,
          mobileCountryCode: String(itrData.mobileCountryCode || itrData.countryCodeMobile || '91'),
          country: String(itrData.countryCode || itrData.country || '91'),
        });
        editorRef.current = hydrated;
        setEditorModel(hydrated);
      })
      .catch((err: any) => {
        if (requestId === loadGenerationRef.current) toast.error(err.message);
      })
      .finally(() => {
        if (requestId === loadGenerationRef.current) setLoading(false);
      });
  }, [clientId, effectiveAssessmentYear]);

  useEffect(() => {
    if (!editorModel) return;
    if (editorModel.draft.form === itrForm && editorModel.draft.regime === regime) return;
    updateEditor((current) => ({
      draft: { ...current.draft, form: itrForm as ReturnEditorModel['draft']['form'], regime },
      extras: current.extras,
    }));
  }, [editorModel, itrForm, regime, updateEditor]);

  const [backendTaxResult, setBackendTaxResult] = useState<any>(null);
  const [taxResultLoading, setTaxResultLoading] = useState(false);
  const [taxResultError, setTaxResultError] = useState<string | null>(null);

  // Debounce timer ref for tax summary API calls
  const taxResultDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // ── CBDT Eligibility (recomputed on every form edit) ────────────────────
  // Under the canonical v2 path, the eligibility engine reads the typed
  // draft's reconciliation evidence so imported OUT_OF_SCOPE_TAXABLE rows
  // (capital-gains, business, VDA, foreign-remittance evidence) escalate
  // the form recommendation — the import layer must never be silently ignored.
  const eligibilityResult = useMemo<FormRecommendation>(
    () => editorModel?.draft
      ? assessFormEligibilityFromDraft(formData, editorModel.draft, backendTaxResult)
      : assessFormEligibility(formData, backendTaxResult),
    [editorModel?.draft, formData, backendTaxResult],
  );

  useEffect(() => {
    setEligibility(eligibilityResult);
    // When not locked by user, follow the recommendation.
    if (!formLockedByUser && eligibilityResult.recommendedForm !== itrForm) {
      setItrForm(eligibilityResult.recommendedForm);
      if (eligibilityResult.recommendedForm !== 'ITR-1') {
        toast(`Auto‑recommended: ${eligibilityResult.recommendedForm} — ${eligibilityResult.reason}`, { icon: '🔍', duration: 4000 });
      }
    }
  }, [eligibilityResult, formLockedByUser, itrForm]);

  const taxSummaryPayload = useMemo(
    // The canonical draft is sent directly to the v2 compute endpoint via
    // `editorRef.current.draft` (see the effect below).  This memo feeds the
    // payload-key memo for debounce gating only.
    () => ({ form: itrForm, assessmentYear: effectiveAssessmentYear, regime }),
    [itrForm, effectiveAssessmentYear, regime],
  );
  // Editor synchronization can recreate an equivalent formData object many
  // times. Depend on the serialized calculation contract so identity-only
  // rerenders do not trigger duplicate backend computations.
  const taxSummaryPayloadKey = useMemo(
    () => JSON.stringify(taxSummaryPayload),
    [taxSummaryPayload],
  );

  // Fetch backend-computed tax summary - replaces local computeTax()
  // All ITR forms (ITR-1, ITR-2, ITR-3, ITR-4) use the same endpoint.
  // The backend maps the flat payload to the correct canonical model
  // (ITR1Input / ITR2Input / ITR4Input) based on the `form` field and
  // runs the appropriate engine.  The frontend never needs a mapper.
  //
  // Debounced: only fires 500ms after user stops typing.
  useEffect(() => {
    if (!clientId || loading || loadedReturnKeyRef.current !== `${clientId}:${effectiveAssessmentYear}`) return;
    const requestId = ++computationGenerationRef.current;
    // A result is authoritative only for the exact payload that produced it.
    // Clear the prior draft's calculation while this draft is being recomputed.
    setBackendTaxResult(null);
    setTaxResultLoading(true);
    setTaxResultError(null);

    taxResultDebounceRef.current = setTimeout(() => {
      const currentDraft = editorRef.current?.draft;
      const computePromise = currentDraft
        ? itrV2.compute(stripCompatibility({ ...currentDraft, assessmentYear: effectiveAssessmentYear, form: itrForm, regime }))
        : itrApi.computeTaxSummary(taxSummaryPayload, effectiveAssessmentYear, regime);
      computePromise
        .then((result: any) => {
          if (requestId !== computationGenerationRef.current) return;
          setBackendTaxResult(result);
          setTaxResultError(null);
        })
        .catch((err: any) => {
          if (requestId !== computationGenerationRef.current) return;
          // Preserve the last successful tax figures, but replace capital-gain
          // validation state with the current rejected draft's structured
          // issues so users can fix the exact rows that blocked computation.
          const details = err?.details;
          const capitalGainsSummary = details?.capitalGainsSummary;
          if (capitalGainsSummary) {
            setBackendTaxResult((previous: any) => ({
              ...(previous || {}),
              capitalGainsSummary,
              capitalGainsStatus: details?.capitalGainsStatus || capitalGainsSummary.status,
              capitalGainsIssues: details?.capitalGainsIssues || capitalGainsSummary.issues || [],
              capitalGainsEligibility: details?.capitalGainsEligibility || capitalGainsSummary.eligibility || {},
            }));
          }
          const msg = typeof err?.message === 'string' && err.message.length > 0
            ? err.message
            : 'Tax computation failed. Please try again.';
          console.error('[TAX] compute failed:', { msg });
          setTaxResultError(msg);
        })
        .finally(() => {
          if (requestId === computationGenerationRef.current) setTaxResultLoading(false);
        });
    }, 500);

    return () => {
      if (taxResultDebounceRef.current) clearTimeout(taxResultDebounceRef.current);
    };
  }, [clientId, effectiveAssessmentYear, regime, taxSummaryPayloadKey, loading]);

  // Invalidate all asynchronous completions after unmount.
  useEffect(() => () => {
    ++loadGenerationRef.current;
    ++computationGenerationRef.current;
    if (taxResultDebounceRef.current) clearTimeout(taxResultDebounceRef.current);
  }, []);

  const taxResult = useMemo(() => {
    // ALWAYS use backend-computed result - no local calculation
    if (backendTaxResult) return backendTaxResult;
    // Return empty result when loading or no data - include ALL Other Sources properties
    return {
      // CBDT Income Summary
      grossSalary: 0, hraExempt: 0, salaryBeforeSection16: 0, netSalary: 0,
      incomeFromSal: 0, deductionUs16: 0,
      hpIncome: 0, totalIncChargeHP: 0,
      otherIncome: 0, incomeOthSrc: 0,
      familyPensionIncome: 0, familyPensionDed: 0, deductUs57iia: 0,
      bizIncome: 0,
      gti: 0, grossTotIncome: 0, grossTotIncomeIncLTCG112A: 0, gtiAfterSetOff: 0,
      totalDeductions: 0, deductChapVIA: 0,
      hpLossDisallowed: 0,
      totalIncomeBefore288A: 0, roundingAdjustment288A: 0, totalIncome: 0,

      // CBDT Tax Computation
      basicExemptionLimit: 0, normalRateIncome: 0,
      incomeChargeableAboveBasicExemption: 0, nilTaxReason: null,
      normalTax: 0, totalTaxPayable: 0,
      rebate87A: 0, taxPayableOnRebate: 0,
      surcharge: 0, cess: 0,
      grossTaxLiability: 0, section89: 0,
      netTaxLiability: 0, totalTaxLiability: 0,

      // CBDT Taxes Paid
      advanceTax: 0, totalTDS: 0, totalTCS: 0,
      selfAssessmentTax: 0, totalTaxPaid: 0, totalTaxesPaid: 0,
      claimedTDSEntered: 0, creditStatus: 'CONFIRMED',
      creditValidationIssues: [], refundStatus: 'NONE',
      enteredCredits: { tds: 0, advanceTax: 0, selfAssessmentTax: 0, total: 0 },
      validatedCredits: { tds: 0, advanceTax: 0, selfAssessmentTax: 0, tcs: 0, total: 0 },
      provisionalRefund: 0, provisionalTaxPayable: 0, blockedCreditsTotal: 0,
      confirmedRefund: null, calculationStatus: 'CALCULATED',

      // Balance / Refund
      balTaxPayable: 0, taxPayable: 0,
      refund: 0, refundDue: 0,

      // Legacy fields still used by other tabs
      vdaTax: 0, vdaGains: 0, cgTax: 0,
      totalInterest: 0, interestDeduction80TTA: 0, interestDeduction80TTB: 0,
      totalDividend: 0, dividendTaxableAtSpecialRate: 0, dividendTaxableAtNormalRate: 0,
      totalWinnings: 0, winningsTax: 0, taxableGifts: 0, specialRateIncome: 0,
      tdsS192: 0, tds194A: 0, tdsOther: 0,
      adv15Jun: 0, adv15Sep: 0, adv15Dec: 0, adv15Mar: 0,
      selfTax: 0, tdsEntries: [], selfAssessmentTaxEntries: [], advanceTaxEntries: [],
      salaryIncome: 0, salary171: 0, salary172: 0, salary173: 0,
      ltaExempt: 0, gratuityExempt: 0, leaveEncashmentExempt: 0,
      pensionCommutationExempt: 0, transportExempt: 0,
      childrenEducationExempt: 0, hostelExempt: 0, uniformExempt: 0,
      totalSection10Exempt: 0, standardDeduction: 0,
      entertainmentAllowanceDed: 0, professionalTaxDed: 0,
      totalSection16Deductions: 0, salaryTDS: 0, salaryEmployerCount: 0,
      hraCondition1: 0, hraCondition2: 0, hraCondition3: 0,
      hraIsMetro: false, hraCityClassified: '',
      deductionBreakdown: {} as Record<string, number>,
    };
  }, [backendTaxResult]);

  // ── Recomputation‑triggered eligibility update ──
  // The eligibilityResult memo above already updates on every formData change.
  // We also mark user‑locked when the form is explicitly set by the user
  // (e.g. after confirming an import recommendation or switching manually).
  // suppressAutoDetectRef prevents the first render from overwriting a saved form.
  useEffect(() => {
    if (suppressAutoDetectRef.current) {
      suppressAutoDetectRef.current = false;
      return;
    }
    // The eligibility engine automatically recommends the best form.
    // No separate autoDetectITRForm call needed — the memo + effect above handle it.
  }, [
    formData.basic, formData.bizTurnover, formData.bpNetProfit, formData.bizPresumptive,
    formData.stcgPre, formData.stcgPost, formData.stcgOther,
    formData.ltcgPre, formData.ltcgPost, formData.ltcgOther,
    formData.vdaGains, formData.grossRent, formData.interestFD, formData.dividends,
    formData.isDirector, formData.holdsUnlistedShares, formData.agriculturalIncome,
    formData.residentialStatus, formData.bfLossHP, formData.bfLossBusiness,
    formData.bfLossSTCG, formData.bfLossLTCG, formData.capitalGainTransactions,
    taxResult.capitalGainsSummary, taxResult.capitalGainsIssues,
  ]);

  const handleSave = async () => {
    setSaving(true);
    try {
      const currentEditor = editorRef.current;
      if (!currentEditor) throw new Error('Return is not loaded');

      // Operate directly on the typed draft and avoid the legacy flat-blob
      // round-trip entirely on save.  The canonical repository strips
      // `compatibility` and pins the AY.
      if (currentEditor.draft) {
        await returnRepository.save(clientId, {
          ...currentEditor.draft,
          assessmentYear: effectiveAssessmentYear,
          form: itrForm,
          regime,
        });
        toast.success('Saved ✓');
        return;
      }

      throw new Error('Return draft is not loaded');
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleValidate = async () => {
    const currentEditor = editorRef.current;
    setValidating(true);
    setValidationReport(null);
    try {
      if (!currentEditor) throw new Error('Return is not loaded');
      // Validate via the v2 compute path: persist the draft, run the canonical
      // compute (which surfaces engine eligibility + cross-field errors), and
      // report structured errors/warnings.  The legacy flat validate endpoint is
      // retired with the flat-blob bridge.
      const draft = {
        ...currentEditor.draft,
        assessmentYear: effectiveAssessmentYear,
        form: itrForm,
        regime,
      };
      await returnRepository.save(clientId, draft);
      let report: { valid: boolean; errors: string[]; warnings: string[] };
      try {
        const result = await itrV2.compute(stripCompatibility(draft));
        const errors: string[] = Array.isArray(result?.errors) ? result.errors : [];
        const warnings: string[] = Array.isArray(result?.warnings) ? result.warnings : [];
        report = { valid: errors.length === 0, errors, warnings };
      } catch (err: any) {
        const errors: string[] = Array.isArray(err?.errors) ? err.errors
          : Array.isArray(err?.details?.errors) ? err.details.errors
          : [err?.message || 'Validation failed'];
        report = { valid: false, errors, warnings: [] };
      }
      setValidationReport(report);
      if (report.valid && report.warnings.length === 0) {
        toast.success('Validation passed ✓');
      } else if (report.valid) {
        toast(`${report.warnings.length} warning(s) — see report`, { icon: '⚠️' });
      } else {
        toast.error(`${report.errors.length} blocking error(s) — see report`);
      }
    } catch (err: any) {
      toast.error(err.message || 'Validation failed');
    } finally {
      setValidating(false);
    }
  };

  const handleGenerateCbdtJson = async () => {
    if (itrForm === 'ITR-3') {
      toast.error('ITR-3 CBDT export is not implemented yet.');
      return;
    }
    try {
      const currentEditor = editorRef.current;
      // Generate from the typed canonical draft without composing or
      // normalizing a legacy payload. The v2 endpoint requires a persisted
      // draft, so save first to publish the latest editor state.
      if (currentEditor?.draft) {
        await returnRepository.save(clientId, {
          ...currentEditor.draft,
          assessmentYear: effectiveAssessmentYear,
          form: itrForm,
          regime,
        });
      }
      await itrV2.generate(clientId, effectiveAssessmentYear);
      toast.success(`CBDT ${itrForm} JSON generated ✓`);
    } catch (err: any) {
      const message = err?.message || 'CBDT JSON generation failed';
      const errors: string[] = Array.isArray(err?.errors) ? err.errors : [];
      toast.error(
        errors.length > 0 ? `${message}\n\n${errors.join('\n')}` : message,
        { duration: 10000 }
      );
    }
  };

  const handleDownloadPdf = async () => {
    try {
      await itrApi.downloadPdf(clientId, effectiveAssessmentYear);
      toast.success('PDF downloaded successfully');
    } catch (err: any) {
      toast.error(err.message || 'PDF download failed');
    }
  };

  // === ITD Portal Automation ===

  const handleImportFromPortal = async () => {
    if (!clientId || automationJobId) return;
    setShowImportMenu(false);
    setStatusBoxJob(null);

    try {
      const res = await itrAutomationApi.startImport(clientId, ayParam || '2026-27');
      setAutomationJobId(res.job_id);
      setShowStatusBox(true);
    } catch (err: any) {
      toast.error(`Failed to start import: ${err.message}`);
    }
  };

  // Called by StatusBox when the job completes — show import confirmation modal
  const handleAutomationComplete = (job: AutomationJob) => {
    setStatusBoxJob(job);
    // If reconciled data is available, show the confirmation modal
    if (job.parsed_results) {
      setReconciledImportData(job.parsed_results);
      setShowImportConfirmModal(true);
    } else {
      // No parsed data — raw error or extraction failed entirely
      toast.error('Import completed but no data was extracted. Check extraction errors.');
    }
  };

  const handleConfirmImport = () => {
    // Map reconciled data to form fields using the existing formData shape
    if (!reconciledImportData) {
      toast.error('No import data available');
      return;
    }

    const { formDataUpdate, discrepancies, summary } = mapReconciledToFormData(reconciledImportData);

    // Also extract the form-agnostic Prefill data (if the automation job
    // downloaded and parsed it).  The Prefill provides salary break-up,
    // deductions, bank accounts, and personal info that AIS/TIS/26AS
    // don't carry.  Merge it first, then let the reconciled update
    // override income/TDS fields (reconciled is more authoritative for
    // the current AY).
    const prefillData = (reconciledImportData as any).prefill || null;
    const prefillResult = mapPrefillToFormData(prefillData);

    // ──────────────────────────────────────────────────────────────────
    // TEMPORARILY DISABLED (Phase 2 testing)
    //
    // The filed-return merge is commented out so the portal automation
    // import doesn't surface the "already filed" blocking error during
    // testing.  See FILED_RETURN_REACTIVATION_GUIDE.md for reactivation.
    //
    // REACTIVATE: const advisory = (reconciledImportData as any).filing_advisory;
    // REACTIVATE: const filedReturnData = (reconciledImportData as any).filed_return || null;
    // REACTIVATE: const filedReturnResult = mapFiledReturnToFormData(filedReturnData);
    const advisory = null as any;
    const filedReturnResult = { formDataUpdate: {}, summary: { carryForwardLosses: 0, bankAccounts: 0, employerEntries: 0 } } as any;

    // A portal import replaces a material portion of the draft. Any result
    // computed for the pre-import generation must not be presented as current.
    ++computationGenerationRef.current;
    if (taxResultDebounceRef.current) clearTimeout(taxResultDebounceRef.current);
    setBackendTaxResult(null);
    setTaxResultLoading(true);
    setTaxResultError('Computation unavailable for the imported draft until recalculated.');

    // Build one merged snapshot for the editor and persistence.  The typed
    // draft path merges via `mergeDraft` (Prefill + reconciled patches) and
    // commits it directly; the legacy `safeUpdate` is only retained to source
    // filed-return compatibility fields that have no typed patch yet.
    const safeUpdate = { ...filedReturnResult.formDataUpdate, ...prefillResult.formDataUpdate, ...formDataUpdate };
    const EMPTY_KEEP_KEYS = ['employerEntries', 'dividendEntries', 'bankInterestEntries', 'interestEntries',
      'capitalGainTransactions', 'tdsEntries', 'tcsEntries'];
    let mergedImportData: any = null;
    if (editorRef.current) {
      // Merge the typed draft patches; this is the authoritative import path.
      mergedImportData = mergeDraft(
        mergeDraft(editorRef.current.draft, mapPrefillToDraftPatch(prefillData)),
        mapReconciledToDraftPatch(reconciledImportData),
      );
      updateEditor((current) => ({ ...replaceDraft(mergedImportData as any), extras: current.extras }));
    }

    // Collect discrepancy messages for the warning banner
    const msgs: string[] = [];
    if (discrepancies.length > 0) {
      msgs.push(
        `${discrepancies.length} discrepanc${discrepancies.length === 1 ? 'y' : 'ies'} found ` +
        'between AIS, TIS, and 26AS. The reconciled source amount has been selected. ' +
        'Review highlighted entries in Salary, Interest, Dividends, and Capital Gains tabs.'
      );
    }
    if ((reconciledImportData.category_control_discrepancies?.length || 0) > 0) {
      for (const discrepancy of reconciledImportData.category_control_discrepancies || []) {
        msgs.push(
          `${discrepancy.category}: TIS accepted total ₹${discrepancy.tis_accepted_total.toLocaleString('en-IN')} ` +
          `differs from annexure detail total ₹${discrepancy.tis_detail_total.toLocaleString('en-IN')}. ` +
          'The accepted TIS total controls computation; all detail rows remain preserved for review.'
        );
      }
    }
    if (reconciledImportData.summary.unmatched_tis > 0 ||
        reconciledImportData.summary.unmatched_ais > 0 ||
        reconciledImportData.summary.unmatched_as26 > 0) {
      const parts = [];
      if (reconciledImportData.summary.unmatched_tis) parts.push('TIS');
      if (reconciledImportData.summary.unmatched_ais) parts.push('AIS');
      if (reconciledImportData.summary.unmatched_as26) parts.push('26AS');
      msgs.push(
        `${reconciledImportData.summary.unmatched_tis + reconciledImportData.summary.unmatched_ais + reconciledImportData.summary.unmatched_as26} ` +
        `entries found in only one of ${parts.join('/')} were preserved for review.`
      );
    }
    // ──────────────────────────────────────────────────────────────────
    // TEMPORARILY DISABLED (Phase 2 testing)
    //
    // The advisory banner is commented out so the portal automation
    // import doesn't surface the "already filed" blocking warning during
    // testing.  See FILED_RETURN_REACTIVATION_GUIDE.md for reactivation.
    //
    // REACTIVATE: const advisoryBanner = (reconciledImportData as any).filing_advisory;
    // REACTIVATE: if (advisoryBanner && advisoryBanner.current_ay_already_filed) {
    // REACTIVATE:   if (advisoryBanner.current_ay_is_revised) {
    // REACTIVATE:     msgs.push(
    // REACTIVATE:       `⚠️ ITR for AY ${advisoryBanner.download_assessment_year || ''} is already filed as a REVISED return ` +
    // REACTIVATE:       `(section ${advisoryBanner.current_ay_filing_section || '139(5)'}). ` +
    // REACTIVATE:       'The last filed ITR was a revised return. To file another revised return, ' +
    // REACTIVATE:       'explicitly confirm the revised-return flow.'
    // REACTIVATE:     );
    // REACTIVATE:   } else {
    // REACTIVATE:     msgs.push(
    // REACTIVATE:       `⚠️ ITR for AY ${advisoryBanner.download_assessment_year || ''} is already filed ` +
    // REACTIVATE:       `(section ${advisoryBanner.current_ay_filing_section || '139(1)'}). ` +
    // REACTIVATE:       'To file a revised return, explicitly confirm the revised-return flow.'
    // REACTIVATE:     );
    // REACTIVATE:   }
    // REACTIVATE: }
    setReconDiscrepancies(msgs);

    toast.success(
      `Import complete: ${summary.totalIncome.toLocaleString('en-IN')} total income, ` +
      `${summary.salaryEntries} salary, ${(summary as any).businessEntries || 0} business, ` +
      `${summary.interestEntries} interest, ` +
      `${summary.dividendEntries} dividend, ${summary.capitalGainsEntries} capital gains entries`
    );

    // Show a secondary toast with Prefill-specific imports (deductions,
    // bank accounts, personal info) that AIS/TIS/26AS don't carry.
    if (prefillResult.summary.personalInfo || prefillResult.summary.employerEntries > 0 || prefillResult.summary.bankAccounts > 0) {
      const prefillParts: string[] = [];
      if (prefillResult.summary.personalInfo) prefillParts.push('personal info');
      if (prefillResult.summary.employerEntries > 0) prefillParts.push(`${prefillResult.summary.employerEntries} employer(s)`);
      if (prefillResult.summary.bankAccounts > 0) prefillParts.push(`${prefillResult.summary.bankAccounts} bank account(s)`);
      if (prefillResult.summary.deductionsTotal > 0) prefillParts.push(`deductions ₹${prefillResult.summary.deductionsTotal.toLocaleString('en-IN')}`);
      if (prefillResult.summary.tdsSalaryEntries > 0) prefillParts.push(`${prefillResult.summary.tdsSalaryEntries} TDS-salary`);
      toast(`Prefill: ${prefillParts.join(', ')}`, { icon: '📋' });
    }

    // ──────────────────────────────────────────────────────────────────
    // TEMPORARILY DISABLED (Phase 2 testing)
    //
    // The filed-return toast and the "already filed" error toast are
    // commented out so the portal automation import doesn't surface
    // the blocking error during testing.  See
    // FILED_RETURN_REACTIVATION_GUIDE.md for reactivation.
    //
    // REACTIVATE: if (filedReturnResult.summary.carryForwardLosses > 0 || filedReturnResult.summary.bankAccounts > 0) {
    // REACTIVATE:   const frParts: string[] = [];
    // REACTIVATE:   if (filedReturnResult.summary.carryForwardLosses > 0) frParts.push(`${filedReturnResult.summary.carryForwardLosses} brought-fwd loss(es)`);
    // REACTIVATE:   if (filedReturnResult.summary.bankAccounts > 0) frParts.push(`${filedReturnResult.summary.bankAccounts} bank account(s)`);
    // REACTIVATE:   if (filedReturnResult.summary.employerEntries > 0) frParts.push(`${filedReturnResult.summary.employerEntries} employer(s)`);
    // REACTIVATE:   toast(`Filed return: ${frParts.join(', ')}`, { icon: '📄' });
    // REACTIVATE: }
    //
    // REACTIVATE: if (advisory && advisory.current_ay_already_filed) {
    // REACTIVATE:   if (advisory.current_ay_is_revised) {
    // REACTIVATE:     toast.error(
    // REACTIVATE:       `ITR for AY ${advisory.download_assessment_year || ''} is already filed as a REVISED return. ` +
    // REACTIVATE:       'The last filed ITR was a revised return. To file another revised return, explicitly confirm the revised-return flow.',
    // REACTIVATE:       { duration: 8000 }
    // REACTIVATE:     );
    // REACTIVATE:   } else {
    // REACTIVATE:     toast.error(
    // REACTIVATE:       `ITR for AY ${advisory.download_assessment_year || ''} is already filed. ` +
    // REACTIVATE:       'To file a revised return, explicitly confirm the revised-return flow.',
    // REACTIVATE:       { duration: 8000 }
    // REACTIVATE:     );
    // REACTIVATE:   }
    // REACTIVATE: }

    // ── Reassess eligibility after import ────────────────────────────────
    setFormLockedByUser(false);

    // Save to backend so form state persists using the canonical repository.
    if (mergedImportData) {
      returnRepository.save(clientId, mergedImportData as any).catch(err => console.warn('Background save after import failed:', err));
    }

    setShowImportConfirmModal(false);
    setShowStatusBox(false);
    setAutomationJobId(null);
    setStatusBoxJob(null);
    setReconciledImportData(null);
  };

  const handleCancelImport = () => {
    // Discard job result client-side only
    setShowImportConfirmModal(false);
    setShowStatusBox(false);
    setAutomationJobId(null);
    setStatusBoxJob(null);
    setReconciledImportData(null);
  };

  // Called by StatusPill when the job fails
  const handleAutomationFailed = (job: AutomationJob) => {
    const reason = job.error_message
      ? job.error_message.split('\n')[0].slice(0, 150)
      : 'Unknown error';
    toast.error(`Import failed: ${reason}`);
    setStatusBoxJob(job);
  };

  // Called by StatusPill dismiss (✕ button or auto-dismiss)
  const handleDismissStatusBox = () => {
    setShowStatusBox(false);
    setAutomationJobId(null);
    setStatusBoxJob(null);
  };

  const handleFileImport = async (type: string, file: File) => {
    const importGeneration = loadGenerationRef.current;
    try {
      toast.loading(`Importing ${type}...`);
      
      if (type === 'form16-pdf' || type === 'form16-json') {
        const form16Data = await import('../api/integration').then(m => m.integrationApi.extractForm16(file));
        if (importGeneration !== loadGenerationRef.current || !editorRef.current) return;
        // The legacy /integration/autopopulate/form16 endpoint was a thin
        // server-side merge with no real Form 16 parser.  Inline the same
        // merge here so Form 16 import keeps working without the dead endpoint.
        const populated: Record<string, unknown> = {
          ...composeLegacyPayload(editorRef.current!),
          basic: form16Data?.basic ?? 0,
          da: form16Data?.da ?? 0,
          hraReceived: form16Data?.hra ?? 0,
          bonus: form16Data?.bonus ?? 0,
          profTax: form16Data?.professionalTax ?? 0,
          tdsS192: form16Data?.tdsDeducted ?? 0,
        };
        if (importGeneration !== loadGenerationRef.current) return;
        setFormData((prev: any) => ({ ...prev, ...populated }));
        toast.dismiss();
        toast.success('Form 16 imported and auto-populated');
      } else if (type === 'ais-pdf' || type === 'ais-json' || type === 'tis-pdf' || type === '26as-pdf' || type === '26as-txt' || type === 'prefill') {
        const typeStr = type as string;
        let data: any;

        const pan = clientData?.pan;
        const dob = clientData?.dob; // YYYY-MM-DD format

        // Validate PAN and DOB are available for encrypted documents
        // (ZIP uploads need DOB to unlock; PDF/TXT don't need it upfront)
        if ((typeStr === 'ais-pdf' || typeStr === 'ais-json' || typeStr === 'tis-pdf' || typeStr === '26as-pdf') && (!pan || !dob)) {
          toast.dismiss();
          toast.error('Client PAN and Date of Birth are required for importing encrypted ITD documents');
          setShowImportMenu(false);
          return;
        }

        if (typeStr === 'prefill') {
          const text = await file.text();
          data = JSON.parse(text);
        } else if (typeStr === 'ais-pdf') {
          const { integrationApi } = await import('../api/integration');
          data = await integrationApi.importAIS(file, legacyClientId!, effectiveAssessmentYear, pan!, dob!);
          if (importGeneration !== loadGenerationRef.current) return;
          setImportedAIS(data);
        } else if (typeStr === 'ais-json') {
          const { integrationApi } = await import('../api/integration');
          data = await integrationApi.importAISJson(file, pan!, dob!);
          if (importGeneration !== loadGenerationRef.current) return;
          setImportedAIS(data);
        } else if (typeStr === 'tis-pdf') {
          const { integrationApi } = await import('../api/integration');
          data = await integrationApi.importTIS(file, pan!, dob!);
          if (importGeneration !== loadGenerationRef.current) return;
          setImportedTIS(data);
        } else if (typeStr === '26as-txt' || typeStr === '26as-pdf') {
          const { integrationApi } = await import('../api/integration');
          // Backend will use client's DOB as password for ZIP files
          data = await integrationApi.import26AS(file, legacyClientId!, pan, dob, effectiveAssessmentYear);
          if (importGeneration !== loadGenerationRef.current) return;
          setImported26AS(data);
        }
        
        // Validate PAN matches
        const docPan = data.personalInfo?.pan || data.personalInfo?.assesseVerPan || data._rawData?.generalInfo?.pan || data.pan || data.generalInfo?.pan;
        if (docPan && docPan !== clientData?.pan) {
          toast.dismiss();
          toast.error(`PAN mismatch: Document PAN (${docPan}) does not match client PAN (${clientData?.pan})`);
          setShowImportMenu(false);
          return;
        }

        // Canonical imports bypass the legacy flat-blob adapter entirely.
        // The typed draft is patched and persisted directly.
        if (editorRef.current && typeStr !== 'prefill') {
          const patch = typeStr === '26as-pdf' || typeStr === '26as-txt'
            ? map26asToDraftPatch(data)
            : typeStr === 'tis-pdf'
              ? mapTisToDraftPatch(data)
              : mapAisToDraftPatch(data);
          const merged = mergeDraft(editorRef.current.draft, patch);
          updateEditor((current) => ({ ...replaceDraft(merged), extras: current.extras }));
          await returnRepository.save(clientId, merged);
          toast.dismiss();
          toast.success(`${typeStr.toUpperCase()} imported into the canonical draft`);
          setShowImportMenu(false);
          return;
        }

        if (type === 'prefill') {
          // ITD Prefill - use backend import API with clientId tracking
          const { integrationApi } = await import('../api/integration');

          // Import to backend - this parses + persists to ImportedDocument
          // and returns the form-agnostic extraction dict.
          const importResult = await integrationApi.importITDPrefill(
            file,
            legacyClientId!,
            effectiveAssessmentYear
          );

          // importResult.data is the PrefillExtraction dict.  Run it
          // through mapPrefillToFormData to surface the import summary
          // (personal info, employer entries, bank accounts, deductions,
          // TDS, other sources) for the toast, then merge the typed draft
          // patch and persist it.
          const prefillResult = mapPrefillToFormData(importResult.data || importResult);

          if (importGeneration !== loadGenerationRef.current || !editorRef.current) return;
          const merged = mergeDraft(editorRef.current.draft, mapPrefillToDraftPatch(importResult.data || importResult));
          updateEditor((current) => ({ ...replaceDraft(merged), extras: current.extras }));
          await returnRepository.save(clientId, merged);

          setShowImportMenu(false);

          const prefillParts: string[] = [];
          if (prefillResult.summary.personalInfo) prefillParts.push('personal info');
          if (prefillResult.summary.employerEntries > 0) prefillParts.push(`${prefillResult.summary.employerEntries} employer(s)`);
          if (prefillResult.summary.bankAccounts > 0) prefillParts.push(`${prefillResult.summary.bankAccounts} bank account(s)`);
          if (prefillResult.summary.deductionsTotal > 0) prefillParts.push(`deductions ₹${prefillResult.summary.deductionsTotal.toLocaleString('en-IN')}`);
          toast.dismiss();
          toast.success(`Prefill imported: ${prefillParts.join(', ')}`);
        } else {
          if (importGeneration !== loadGenerationRef.current) return;
          setFormData((prev: any) => ({ ...prev, ...data }));
        }
        
        toast.dismiss();
        toast.success(`${type.toUpperCase()} imported and validated`);
      }
      setShowImportMenu(false);
    } catch (err: any) {
      toast.dismiss();
      toast.error(err.message || 'Import failed');
    }
  };

  const handleReconciliationResolve = (discrepancy: any, action: 'KEEP_EXISTING' | 'USE_NEW' | 'MANUAL') => {
    if (action === 'MANUAL') {
      toast('Please review and update employer details manually in the Salary tab', { icon: 'ℹ️' });
      setShowReconciliationModal(false);
      return;
    }

    // Update employer entries based on action
    const updatedEntries = formData.employerEntries.map((entry: any) => {
      const matchingDiscrepancy = reconciliationResult?.discrepancies?.find(
        (d: any) => d.employerTAN === entry.employerTAN
      );
      
      if (matchingDiscrepancy && matchingDiscrepancy.employerTAN === discrepancy.employerTAN) {
        if (action === 'USE_NEW') {
          // Apply new values from discrepancy
          const updated = { ...entry };
          matchingDiscrepancy.fieldDiscrepancies.forEach((field: any) => {
            const fieldKey = field.fieldName.toLowerCase().replace(/\s+/g, '');
            if (fieldKey === 'basicsalary') updated.basic = field.newValue;
            else if (fieldKey === 'da') updated.da = field.newValue;
            else if (fieldKey === 'hra') updated.hra = field.newValue;
            else if (fieldKey === 'bonus') updated.bonus = field.newValue;
            else if (fieldKey === 'allowances') updated.allowances = field.newValue;
            else if (fieldKey === 'perquisites') updated.perquisites = field.newValue;
            else if (fieldKey === 'professionaltax') updated.professionalTax = field.newValue;
            else if (fieldKey === 'tdsdeducted') updated.tdsDeducted = field.newValue;
            else if (fieldKey === 'grosssalary') updated.grossSalary = field.newValue;
            else if (fieldKey === 'netsalary') updated.netSalary = field.newValue;
          });
          return updated;
        }
        // KEEP_EXISTING - no changes needed
      }
      return entry;
    });

    setFormData((previous: LegacyRecord) => ({ ...previous, employerEntries: updatedEntries }));
    toast.success(`Applied ${action === 'USE_NEW' ? 'new' : 'existing'} values for ${discrepancy.employerName}`);
    
    // Remove resolved discrepancy
    const remainingDiscrepancies = reconciliationResult.discrepancies.filter(
      (d: any) => d.employerTAN !== discrepancy.employerTAN
    );
    
    if (remainingDiscrepancies.length === 0) {
      setShowReconciliationModal(false);
      toast.success('All discrepancies resolved!');
    } else {
      setReconciliationResult({ ...reconciliationResult, discrepancies: remainingDiscrepancies });
    }
  };

  const autoDetectITRForm = () => {
    // Comprehensive ITR form detection based on CBDT rules - AY 2026-27
    const hasBusinessIncome = (formData.bizTurnover || 0) > 0 || (formData.bpNetProfit || 0) > 0;
    const hasPresumptiveIncome = hasBusinessIncome && formData.bizPresumptive && formData.bizPresumptive !== 'Regular';
    
    // Restricted long-term Section 112A gains are permitted in ITR-1/ITR-4.
    // Unsupported preserved rows or backend eligibility failures require ITR-2/3.
    // hasFormLevelLosses detects signed 112A losses from form data alone so
    // ITR-2 is detected *before* the first backend compute.
    const restrictedCapitalGains = getRestrictedCapitalGainsState(formData, taxResult);
    const hasLegacyCapitalGains =
      (formData.stcgPre || 0) > 0 ||
      (formData.stcgPost || 0) > 0 ||
      (formData.stcgOther || 0) > 0 ||
      (formData.ltcgPre || 0) > 0 ||
      (formData.ltcgPost || 0) > 0 ||
      (formData.ltcgOther || 0) > 0 ||
      (formData.vdaGains || 0) > 0;
    const hasCapitalGainsRequiringFutureForm = hasLegacyCapitalGains || restrictedCapitalGains.hasUnsupportedRows || restrictedCapitalGains.hasIneligibleIssues || restrictedCapitalGains.hasFormLevelLosses;
    
    // Special Income - Lottery, Online Gaming, Card Games, Race Winnings
    const hasSpecialIncome = 
      (formData.winnings || 0) > 0 || 
      (formData.lotteryIncome || 0) > 0 ||
      (formData.onlineGamingIncome || 0) > 0 ||
      (formData.cardGameIncome || 0) > 0 ||
      (formData.raceWinnings || 0) > 0;
    
    // Exempt Income (Schedule EI)
    const hasExemptIncome = 
      (formData.agriculturalIncome || 0) > 0 ||
      (formData.rajarshi || 0) > 0 ||
      (formData.municipal || 0) > 0 ||
      (formData.scholarship || 0) > 0 ||
      (formData.gratuity || 0) > 0 ||
      (formData.severance || 0) > 0 ||
      (formData.vrs || 0) > 0;
    
    const housePropertyEntries = Array.isArray(formData.housePropertyEntries) ? formData.housePropertyEntries : [];
    const hasMultipleProperties = housePropertyEntries.length > 2;
    const hasForeignIncome = (formData.foreignIncome || 0) > 0 || (formData.foreignAssets || 0) > 0;
    const totalIncome = taxResult.totalIncome || 0;
    const agriculturalIncome = formData.agriculturalIncome || 0;
    const isDirector = formData.isDirector || false;
    const hasUnlistedShares = formData.holdsUnlistedShares || false;
    const isNonResident = formData.residentialStatus && formData.residentialStatus !== 'ROR';
    const hasBFLoss = (formData.bfLossHP || 0) > 0 || (formData.bfLossBusiness || 0) > 0 || 
                      (formData.bfLossSTCG || 0) > 0 || (formData.bfLossLTCG || 0) > 0;

    let detectedForm: ItrForm = 'ITR-1';
    let reason = '';

    // Priority 1: ITR-4 for presumptive income only while restricted CG remains eligible.
    if (hasPresumptiveIncome && !hasCapitalGainsRequiringFutureForm) {
      detectedForm = 'ITR-4';
      reason = 'Presumptive income under 44AD/44ADA';
    }
    // Presumptive business plus CG outside restricted 112A requires the ITR-3 workflow.
    else if (hasPresumptiveIncome && hasCapitalGainsRequiringFutureForm) {
      detectedForm = 'ITR-3';
      reason = 'Presumptive income with capital gains outside restricted Section 112A eligibility';
    }
    // Priority 2: ITR-3 (Business/Professional income - non-presumptive)
    else if (hasBusinessIncome) {
      detectedForm = 'ITR-3';
      reason = 'Business or professional income';
    }
    // Priority 3: ITR-2 conditions - Capital Gains (Real-estate, Movable, Foreign, Securities, VDA)
    else if (hasCapitalGainsRequiringFutureForm) {
      detectedForm = hasBusinessIncome ? 'ITR-3' : 'ITR-2';
      reason = 'Capital-gains facts outside restricted Section 112A eligibility';
    }
    // Priority 4: ITR-2 - Special Income (Lottery, Online Gaming)
    else if (hasSpecialIncome) {
      detectedForm = 'ITR-2';
      reason = 'Lottery/Online gaming/Card game winnings (Section 115BB)';
    }
    // Priority 5: ITR-2 - Multiple house properties
    else if (hasMultipleProperties) {
      detectedForm = 'ITR-2';
      reason = 'Multiple house properties';
    }
    // Priority 6: ITR-2 - Foreign income/assets
    else if (hasForeignIncome) {
      detectedForm = 'ITR-2';
      reason = 'Foreign income or assets';
    }
    // Priority 7: ITR-2 - Total income > ₹50 lakh
    else if (totalIncome > 5000000) {
      detectedForm = 'ITR-2';
      reason = 'Total income exceeds ₹50 lakhs';
    }
    // Priority 8: ITR-2 - Non-resident
    else if (isNonResident) {
      detectedForm = 'ITR-2';
      reason = 'Non-resident or RNOR status';
    }
    // Priority 9: ITR-2 - Director in company/firm
    else if (isDirector) {
      detectedForm = 'ITR-2';
      reason = 'Director in a company';
    }
    // Priority 10: ITR-2 - Holds unlisted shares
    else if (hasUnlistedShares) {
      detectedForm = 'ITR-2';
      reason = 'Holds unlisted equity shares';
    }
    // Priority 11: ITR-2 - Agricultural income > ₹5,000
    else if (agriculturalIncome > 5000) {
      detectedForm = 'ITR-2';
      reason = 'Agricultural income exceeds ₹5,000';
    }
    // Priority 12: ITR-2 - Exempt income
    else if (hasExemptIncome) {
      detectedForm = 'ITR-2';
      reason = 'Exempt income (Schedule EI)';
    }
    // Priority 13: ITR-2 - Brought forward losses
    else if (hasBFLoss) {
      detectedForm = 'ITR-2';
      reason = 'Brought forward losses';
    }
    else {
      reason = 'Salary with simple income structure';
    }

    // Only update if form changed
    if (detectedForm !== itrForm) {
      setItrForm(detectedForm);
      toast(`Auto-detected: ${detectedForm} - ${reason}`, { icon: '🔍', duration: 4000 });
    }
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: 48 }}>
        <Spinner size={32} />
      </div>
    );
  }

  const tabs = [
    '📋 Personal Info',
    '💼 Salary Income',
    '🏠 House Property',
    '📈 Capital Gains',
    '🏪 Business or Profession',
    '💰 Other Sources',
    '📋 Exempt Income',  // VR1-027, VR1-028 - CBDT mandatory
    '➖ Deductions',
    '🧾 TDS & Advance Tax',
    '🧮 Tax Computation'
  ];

  return (
    <div>
      <div style={{
        background: 'white',
        padding: '16px 24px',
        marginBottom: 16,
        borderRadius: 'var(--radius)',
        border: '1px solid var(--border)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <button
              onClick={() => navigate('/filing')}
              style={{
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                fontSize: 18,
                color: 'var(--text-secondary)'
              }}
            >
              ←
            </button>
            <div>
              <div style={{ fontSize: 18, fontWeight: 600, color: 'var(--text-primary)' }}>
                {clientData?.name || 'Loading...'}
              </div>
              <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 2 }}>
                <span className="mono">{clientData?.pan || ''}</span>
                <span style={{ margin: '0 8px' }}>•</span>
                <span>AY {effectiveAssessmentYear}</span>
              </div>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <select
                value={itrForm}
                onChange={(e) => {
                  const newForm = e.target.value as ItrForm;
                  const blockers = eligibility?.blockersByForm?.[newForm] ?? [];
                  if (blockers.length > 0) {
                    toast.error(
                      `${newForm} has ${blockers.length} blocker(s):\n${blockers.join('\n')}`,
                      { duration: 6000 },
                    );
                  }
                  // Block downgrade to ITR-1/4 when non-112A Capital Gains data exists.
                  const isDowngrade = (newForm === 'ITR-1' || newForm === 'ITR-4') && (itrForm === 'ITR-2' || itrForm === 'ITR-3');
                  if (isDowngrade && hasNonSimplifiedCapitalGains(formData.capitalGainsSchedule)) {
                    const confirmDowngrade = window.confirm(
                      `Switching to ${newForm} will prevent the following Capital Gains data from being filed:\n\n` +
                      `• Full Schedule CG (STCG/LTCG land & building, equity, NRI, other assets, slump sales)\n` +
                      `• Schedule 112A scrip-level detail\n• Schedule 115AD\n• Schedule VDA\n• DTAA rows\n• Deduction claims\n• Loss set-off matrix\n\n` +
                      `The data will be preserved but will NOT be included in the filed return.\n\n` +
                      `Switch to ${newForm} anyway?`
                    );
                    if (!confirmDowngrade) {
                      // Revert the select by forcing re-render with the old value.
                      setItrForm(itrForm);
                      return;
                    }
                  }
                  // Allow the switch anyway — blockers disable filing, not viewing.
                  setItrForm(newForm);
                  setFormLockedByUser(true);
                  if (eligibility && newForm === eligibility.recommendedForm) {
                    toast.success(`Switched to recommended ${newForm}`);
                  }
                }}
                style={{
                  padding: '6px 12px',
                  border: '1px solid var(--border)',
                  borderRadius: 6,
                  fontSize: 13,
                  fontWeight: 500,
                  background: 'white',
                }}
              >
                {(['ITR-1', 'ITR-2', 'ITR-3', 'ITR-4'] as const).map((f) => (
                  <option key={f} value={f}>
                    {f}{eligibility?.recommendedForm === f ? ' ★' : ''}{eligibility?.blockersByForm?.[f]?.length ? ` (${eligibility.blockersByForm[f].length})` : ''}
                  </option>
                ))}
              </select>
              {eligibility && itrForm !== eligibility.recommendedForm && (
                <button
                  onClick={() => { setItrForm(eligibility.recommendedForm); setFormLockedByUser(false); }}
                  title={`Switch to recommended ${eligibility.recommendedForm}`}
                  style={{
                    padding: '2px 8px',
                    background: 'var(--gold)',
                    color: 'white',
                    border: 'none',
                    borderRadius: 4,
                    fontSize: 11,
                    cursor: 'pointer',
                  }}
                >
                  Use {eligibility.recommendedForm}
                </button>
              )}
            </div>
            <select
              value={regime}
              onChange={(e) => handleRegimeChange(e.target.value as 'old' | 'new')}
              style={{
                padding: '6px 12px',
                border: '1px solid var(--border)',
                borderRadius: 6,
                fontSize: 13,
                fontWeight: 500,
                background: 'white'
              }}
            >
              <option value="old">Old Regime</option>
              <option value="new">New Regime</option>
            </select>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, paddingLeft: 34 }}>

          <div style={{ position: 'relative', display: 'flex', alignItems: 'center', gap: 6 }}>
            <button
              onClick={() => setShowImportMenu(!showImportMenu)}
              style={{
                padding: '6px 12px',
                background: 'var(--info)',
                color: 'white',
                border: 'none',
                borderRadius: 6,
                fontSize: 12,
                cursor: 'pointer'
              }}
            >
              Import
            </button>
            {/* Inline status pill — shows during portal automation, auto-dismisses on complete */}
            {showStatusBox && automationJobId && (
              <StatusPill
                jobId={automationJobId}
                onComplete={handleAutomationComplete}
                onFailed={handleAutomationFailed}
                onDismiss={handleDismissStatusBox}
              />
            )}

            {/* Import Confirmation Modal — shown after job completes successfully */}
            <ImportConfirmationModal
              show={showImportConfirmModal}
              results={reconciledImportData}
              clientName={clientData?.name}
              pan={clientData?.pan}
              assessmentYear={ayParam}
              onConfirm={handleConfirmImport}
              onCancel={handleCancelImport}
            />
            {showImportMenu && (
              <div style={{
                position: 'absolute',
                top: '100%',
                left: 0,
                marginTop: 4,
                background: 'white',
                border: '1px solid var(--border)',
                borderRadius: 6,
                boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
                zIndex: 1000,
                minWidth: 200
              }}>
                <div
                  onClick={handleImportFromPortal}
                  style={{
                    display: 'block',
                    padding: '8px 12px',
                    fontSize: 12,
                    cursor: automationJobId ? 'not-allowed' : 'pointer',
                    opacity: automationJobId ? 0.5 : 1,
                    pointerEvents: automationJobId ? 'none' : 'auto',
                  }}
                >
                  Import from Portal
                </div>
                <label style={{
                  display: 'block',
                  padding: '8px 12px',
                  fontSize: 12,
                  cursor: 'pointer',
                  borderTop: '1px solid var(--border)'
                }}>
                  <input
                    type="file"
                    accept=".json"
                    onChange={(e) => e.target.files?.[0] && handleFileImport('prefill', e.target.files[0])}
                    style={{ display: 'none' }}
                  />
                  ITD Prefill JSON
                </label>
                <label style={{
                  display: 'block',
                  padding: '8px 12px',
                  fontSize: 12,
                  cursor: 'pointer',
                  borderTop: '1px solid var(--border)'
                }}>
                  <input
                    type="file"
                    accept=".txt,.zip"
                    onChange={(e) => e.target.files?.[0] && handleFileImport('26as-txt', e.target.files[0])}
                    style={{ display: 'none' }}
                  />
                  Form 26AS (TXT/ZIP)
                </label>
                <label style={{
                  display: 'block',
                  padding: '8px 12px',
                  fontSize: 12,
                  cursor: 'pointer',
                  borderTop: '1px solid var(--border)'
                }}>
                  <input
                    type="file"
                    accept=".pdf"
                    onChange={(e) => e.target.files?.[0] && handleFileImport('26as-pdf', e.target.files[0])}
                    style={{ display: 'none' }}
                  />
                  Form 26AS (PDF)
                </label>
                <label style={{
                  display: 'block',
                  padding: '8px 12px',
                  fontSize: 12,
                  cursor: 'pointer',
                  borderTop: '1px solid var(--border)'
                }}>
                  <input
                    type="file"
                    accept=".pdf"
                    onChange={(e) => e.target.files?.[0] && handleFileImport('ais-pdf', e.target.files[0])}
                    style={{ display: 'none' }}
                  />
                  AIS (PDF)
                </label>
                <label style={{
                  display: 'block',
                  padding: '8px 12px',
                  fontSize: 12,
                  cursor: 'pointer',
                  borderTop: '1px solid var(--border)'
                }}>
                  <input
                    type="file"
                    accept=".json"
                    onChange={(e) => e.target.files?.[0] && handleFileImport('ais-json', e.target.files[0])}
                    style={{ display: 'none' }}
                  />
                  AIS (JSON)
                </label>
                <label style={{
                  display: 'block',
                  padding: '8px 12px',
                  fontSize: 12,
                  cursor: 'pointer',
                  borderTop: '1px solid var(--border)'
                }}>
                  <input
                    type="file"
                    accept=".pdf"
                    onChange={(e) => e.target.files?.[0] && handleFileImport('tis-pdf', e.target.files[0])}
                    style={{ display: 'none' }}
                  />
                  TIS (PDF)
                </label>
              </div>
            )}
          </div>

          <button
            onClick={handleSave}
            disabled={saving}
            style={{
              padding: '6px 12px',
              background: saving ? 'var(--border)' : 'var(--gold)',
              color: 'white',
              border: 'none',
              borderRadius: 6,
              fontSize: 12,
              fontWeight: 500,
              cursor: saving ? 'not-allowed' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 6
            }}
          >
            {saving && <Spinner size={12} />}
            Save
          </button>

          <button
            onClick={handleValidate}
            disabled={validating}
            style={{
              padding: '6px 12px',
              background: validating ? 'var(--border)' : 'var(--accent-blue)',
              color: 'white',
              border: 'none',
              borderRadius: 6,
              fontSize: 12,
              fontWeight: 500,
              cursor: validating ? 'not-allowed' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 6
            }}
          >
            {validating && <Spinner size={12} />}
            Validate
          </button>

          {itrForm !== 'ITR-3' && itrForm !== 'ITR-2' && (
            <button
              onClick={handleGenerateCbdtJson}
              title="Generate and download the official CBDT ITD-compliant JSON (ITR-1/ITR-4)"
              style={{
                padding: '6px 12px',
                background: 'var(--gold)',
                color: 'white',
                border: 'none',
                borderRadius: 6,
                fontSize: 12,
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              CBDT JSON
            </button>
          )}

          <button
            onClick={handleDownloadPdf}
            style={{
              padding: '6px 12px',
              background: 'var(--accent-teal)',
              color: 'white',
              border: 'none',
              borderRadius: 6,
              fontSize: 12,
              cursor: 'pointer'
            }}
          >
            PDF
          </button>
        </div>
      </div>

      {taxResultLoading && (
        <div role="status" style={{ marginBottom: 12, color: 'var(--text-secondary)', fontSize: 13 }}>
          Computing tax summary…
        </div>
      )}
      {taxResultError && (
        <div role="alert" style={{ marginBottom: 12, padding: 12, borderRadius: 6, color: 'var(--error)', background: 'var(--error-bg)' }}>
          {backendTaxResult
            ? <>Current draft has an error; figures below are from the last successful backend computation: {taxResultError}</>
            : <>Tax computation failed: {taxResultError}</>}
        </div>
      )}
      {backendTaxResult?.filingComputationStatus === 'PROVISIONAL_COMMON_INCOME_PREVIEW' && (
        <div role="status" style={{ marginBottom: 12, padding: 12, borderRadius: 6, color: '#92400e', background: '#fffbeb', border: '1px solid #fcd34d' }}>
          <strong>Provisional preview only.</strong>{' '}
          {backendTaxResult.filingComputationMessage}
        </div>
      )}

      {validationReport && !validationReport.valid && (
        <div role="alert" style={{ marginBottom: 12, padding: 12, borderRadius: 6, color: 'var(--error)', background: 'var(--error-bg)' }}>
          <strong>Blocking errors ({validationReport.errors.length}):</strong>
          <ul style={{ margin: '6px 0 0', paddingLeft: 18 }}>
            {validationReport.errors.map((e, i) => <li key={i} style={{ fontSize: 13 }}>{e}</li>)}
          </ul>
        </div>
      )}

      {validationReport && validationReport.valid && validationReport.warnings.length > 0 && (
        <div role="status" style={{ marginBottom: 12, padding: 12, borderRadius: 6, color: 'var(--text-secondary)', background: 'var(--warn-bg, #fff8e1)' }}>
          <strong>Warnings ({validationReport.warnings.length}):</strong>
          <ul style={{ margin: '6px 0 0', paddingLeft: 18 }}>
            {validationReport.warnings.map((w, i) => <li key={i} style={{ fontSize: 13 }}>{w}</li>)}
          </ul>
        </div>
      )}

      {/* Reconciliation Discrepancy Warning Banner */}
      {reconDiscrepancies.length > 0 && (
        <div style={{
          display: 'flex',
          alignItems: 'flex-start',
          gap: 8,
          padding: '10px 14px',
          marginBottom: 12,
          background: '#fff8e1',
          border: '1px solid #f9a825',
          borderRadius: 8,
          fontSize: 12,
          color: '#5d4037',
        }}>
          <span style={{ fontSize: 16, flexShrink: 0 }}>⚠️</span>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4, flex: 1 }}>
            {reconDiscrepancies.map((msg: string, i: number) => (
              <span key={i}>{msg}</span>
            ))}
            <button
              onClick={() => setReconDiscrepancies([])}
              style={{
                alignSelf: 'flex-start',
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                fontSize: 11,
                color: 'var(--text-secondary)',
                textDecoration: 'underline',
                padding: 0,
              }}
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

    {/* ── Eligibility Banner (CBDT) ──────────────────────────────────── */}
      {eligibility && (
        <div style={{
          marginBottom: 12,
          padding: '10px 16px',
          borderRadius: 8,
          background: eligibility.blockers.length > 0 ? '#fef2f2' : '#f0fdf4',
          border: `1px solid ${eligibility.blockers.length > 0 ? '#fecaca' : '#bbf7d0'}`,
          fontSize: 13,
          color: eligibility.blockers.length > 0 ? '#991b1b' : '#166534',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div>
              <strong>{eligibility.blockers.length > 0 ? '⚠️' : '✅'} Recommended: {eligibility.recommendedForm}</strong>
              {' — '}{eligibility.reason}
              {eligibility.blockers.length > 0 && (
                <ul style={{ margin: '6px 0 0', paddingLeft: 18, fontSize: 12 }}>
                  {eligibility.blockers.map((b, i) => <li key={i}>{b}</li>)}
                </ul>
              )}
            </div>
            {formLockedByUser && (
              <button
                onClick={() => setFormLockedByUser(false)}
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: 'var(--text-secondary)',
                  cursor: 'pointer',
                  fontSize: 11,
                  textDecoration: 'underline',
                  padding: '2px 4px',
                }}
              >
                Unlock
              </button>
            )}
          </div>
        </div>
      )}

      {/* ── Schedule Checklist (dynamic per form) ─────────────────────── */}
      {eligibility && (() => {
        const facts = collectEligibilityFacts(formData, backendTaxResult);
        const schedules = activeSchedules(itrForm as ItrForm, facts);
        if (schedules.length === 0) return null;
        const blocking = new Set(blockingSchedules(itrForm as ItrForm, facts).map(s => s.id));
        const statusColors: Record<ScheduleStatus, string> = {
          'available': '#166534', 'partial': '#92400e', 'missing': '#991b1b',
          'derived': '#6b7280', 'not-applicable': '#9ca3af', 'unavailable': '#9ca3af',
        };
        const statusBg: Record<ScheduleStatus, string> = {
          'available': '#dcfce7', 'partial': '#fffbeb', 'missing': '#fef2f2',
          'derived': '#f3f4f6', 'not-applicable': '#f3f4f6', 'unavailable': '#f3f4f6',
        };
        return (
          <div style={{ marginBottom: 12, padding: '8px 12px', borderRadius: 8, background: '#f8fafc', border: '1px solid #e2e8f0', fontSize: 12 }}>
            <div style={{ fontWeight: 600, marginBottom: 6, color: '#334155' }}>
              Schedules for {itrForm} ({schedules.length})
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
              {schedules.map(({ schedule, status }) => (
                <span key={schedule.id} style={{
                  padding: '2px 8px', borderRadius: 4, fontSize: 11,
                  color: statusColors[status], background: statusBg[status],
                  border: `1px solid ${blocking.has(schedule.id) ? '#f87171' : 'transparent'}`,
                  fontWeight: blocking.has(schedule.id) ? 600 : 400,
                }} title={schedule.description}>
                  {schedule.label}{blocking.has(schedule.id) ? ' ⚠' : ''}
                </span>
              ))}
            </div>
          </div>
        );
      })()}

      <div style={{
        background: 'var(--navy)',
        borderRadius: 'var(--radius)',
        marginBottom: 16,
        display: 'flex',
        overflowX: 'auto'
      }}>
        {tabs.map((tab, idx) => (
          <button
            key={idx}
            onClick={() => setActiveTab(idx)}
            style={{
              padding: '12px 16px',
              background: activeTab === idx ? 'rgba(201, 148, 58, 0.15)' : 'transparent',
              color: activeTab === idx ? 'var(--gold)' : 'var(--text-muted)',
              border: 'none',
              borderBottom: activeTab === idx ? '3px solid var(--gold)' : '3px solid transparent',
              fontSize: 13,
              fontWeight: activeTab === idx ? 600 : 400,
              cursor: 'pointer',
              whiteSpace: 'nowrap'
            }}
          >
            {tab}
          </button>
        ))}
      </div>

      <div style={{
        background: 'white',
        padding: 24,
        borderRadius: 'var(--radius)',
        border: '1px solid var(--border)'
      }}>
        {activeTab === 0 && <PersonalInfoTab formData={formData} itrForm={itrForm as 'ITR-1' | 'ITR-2' | 'ITR-3' | 'ITR-4'} onChange={setFormData} onBanksChange={managers.banks} onRegimeChange={handleRegimeChange} />}
        {activeTab === 1 && <SalaryTab entries={editorModel?.draft.employers ?? []} onChange={(entries: any[]) => updateEditor((model) => updateEmployers(model, entries))} taxResult={backendTaxResult} ayParam={effectiveAssessmentYear} regime={regime} tdsEntries={formData.tdsEntries || []} />}
        {activeTab === 2 && <HousePropertyTab entries={editorModel?.draft.houseProperties ?? []} passThroughIncome={editorModel?.draft.housePropertyPassThroughIncome ?? 0} onChange={(entries: any[], passThroughIncome: number) => updateEditor((model) => updateHouseProperties(model, entries, passThroughIncome))} itrForm={itrForm} taxResult={backendTaxResult} />}
        {activeTab === 3 && <CapitalGainsTab formData={formData} setFormData={setFormData} taxResult={taxResult} itrForm={itrForm} />}
        {activeTab === 4 && <BusinessTab formData={formData} setFormData={setFormData} taxResult={taxResult} itrForm={itrForm} />}
        {activeTab === 5 && <OtherSourcesTab formData={formData} setFormData={setFormData} taxResult={taxResult} managers={managers} itrForm={itrForm} regime={regime} editorModel={editorModel} />}
        {activeTab === 6 && editorModel && <ExemptIncomeWorkspace form={itrForm} schedule={editorModel.draft.exemptIncome} onChange={(next) => updateEditor((model) => updateExemptIncome(model, next))} />}
        {activeTab === 7 && <DeductionsTab formData={formData} setFormData={setFormData} regime={regime} taxResult={taxResult} managers={managers} form={itrForm} editorModel={editorModel} />}
        {activeTab === 8 && <TDSTab formData={formData} setFormData={setFormData} taxResult={taxResult} managers={managers} />}
        {activeTab === 9 && (!backendTaxResult && taxResultError
          ? <div role="alert" style={{ padding: 24, textAlign: 'center', color: 'var(--error)' }}>Tax figures are unavailable until the first computation succeeds.</div>
          : <TaxComputationTab taxResult={taxResult} regime={regime} itrForm={itrForm} />)}
      </div>

      {/* Employer Reconciliation Modal */}
      <EmployerReconciliationModal
        show={showReconciliationModal}
        result={reconciliationResult}
        onClose={() => setShowReconciliationModal(false)}
        onResolve={handleReconciliationResolve}
      />
    </div>
  );
}

// ============================================================================
// EXEMPT INCOME TAB - Replaced by the canonical ExemptIncomeWorkspace component.
// The old scalar editor (including the stale section 10(38) path) has been removed
// to eliminate duplicate capture; non-salary exempt income is now owned solely by
// the canonical Schedule EI superset on ReturnDraft.exemptIncome.
// ============================================================================

function Field({ label, value, onChange, computed, prefix = '₹', type = 'number', required = false, pattern, maxLength, min, max, inputMode, helpText }: any) {
  const [displayValue, setDisplayValue] = React.useState('');
  const [isFocused, setIsFocused] = React.useState(false);

  // Format number with Indian comma style (lakhs/crores)
  const formatIndianNumber = (num: number) => {
    if (num == null || num === 0) return '0';
    // Round to integer to avoid floating point precision issues
    const rounded = Math.round(num);
    const numStr = rounded.toString();
    
    // Indian formatting: last 3 digits, then groups of 2
    let formatted = '';
    const len = numStr.length;
    
    if (len <= 3) {
      formatted = numStr;
    } else {
      formatted = numStr.slice(-3);
      let remaining = numStr.slice(0, -3);
      
      while (remaining.length > 0) {
        if (remaining.length <= 2) {
          formatted = remaining + ',' + formatted;
          remaining = '';
        } else {
          formatted = remaining.slice(-2) + ',' + formatted;
          remaining = remaining.slice(0, -2);
        }
      }
    }
    
    return formatted;
  };

  // Remove commas for parsing
  const parseIndianNumber = (str: string) => {
    return str.replace(/,/g, '');
  };

  React.useEffect(() => {
    if (type === 'number' && !isFocused) {
      setDisplayValue(value == null || value === 0 ? '' : formatIndianNumber(value));
    } else if (type !== 'number') {
      setDisplayValue(value || '');
    }
  }, [value, type, isFocused]);

  const handleFocus = (e: any) => {
    setIsFocused(true);
    if (type === 'number') {
      // Clear the field if it's 0, null, undefined, or empty
      if (value == null || value === 0 || value === '') {
        setDisplayValue('');
        e.target.value = '';
      } else {
        // Show raw number without commas for editing
        const str = String(value);
        setDisplayValue(str);
        e.target.value = str;
      }
    }
  };

  const handleBlur = () => {
    setIsFocused(false);
    if (type === 'number') {
      // Reformat with commas when focus is lost
      setDisplayValue(value === 0 ? '' : formatIndianNumber(value));
    }
  };

  const handleChange = (e: any) => {
    if (computed) return;
    
    if (type === 'number') {
      const rawValue = parseIndianNumber(e.target.value ?? '');
      // Only allow integers, no decimals
      const numValue = rawValue === '' ? 0 : Math.round(Number(rawValue));
      
      if (!isNaN(numValue)) {
        setDisplayValue(e.target.value ?? '');
        onChange(numValue);
      }
    } else {
      setDisplayValue(e.target.value ?? '');
      onChange(e.target.value);
    }
  };

  return (
    <div style={{ marginBottom: 16 }}>
      <label style={{ display: 'block', marginBottom: 6, fontSize: 12, fontWeight: 500, color: 'var(--text-secondary)' }}>
        {label}{required && ' *'}
      </label>
      <div style={{ position: 'relative' }}>
        {prefix && !computed && (
          <span style={{
            position: 'absolute',
            left: 12,
            top: '50%',
            transform: 'translateY(-50%)',
            color: 'var(--text-muted)',
            fontSize: 13
          }}>
            {prefix}
          </span>
        )}
        <input
          type={type === 'number' ? 'text' : type}
          value={computed ? (type === 'number' ? formatIndianNumber(value) : value ?? '') : displayValue}
          onChange={handleChange}
          onFocus={handleFocus}
          onBlur={handleBlur}
          readOnly={computed}
          required={required}
          pattern={pattern}
          maxLength={maxLength}
          min={min}
          max={max}
          inputMode={inputMode || (type === 'number' ? 'numeric' : undefined)}
          aria-label={label}
          placeholder={type === 'number' && !computed ? '0' : ''}
          style={{
            width: '100%',
            padding: '8px 12px',
            paddingLeft: prefix && !computed ? 28 : 12,
            border: '1px solid var(--border)',
            borderRadius: 6,
            fontSize: 13,
            background: computed ? 'var(--gold-pale)' : 'white',
            cursor: computed ? 'default' : 'text',
            fontFamily: type === 'number' ? 'DM Mono' : 'inherit'
          }}
        />
      </div>
      {helpText && <div style={{ marginTop: 4, fontSize: 11, color: 'var(--text-muted)' }}>{helpText}</div>}
    </div>
  );
}

function SalaryTab({ entries, onChange, taxResult, ayParam, regime, tdsEntries }: any) {
  return <EmployerEntryManager entries={entries} onChange={onChange} assessmentYear={ayParam || '2026-27'} taxRegime={regime === 'new' ? 'NEW' : 'OLD'} backendResult={taxResult} tdsEntries={tdsEntries || []} />;
}

function HousePropertyTab({ entries, passThroughIncome, onChange, itrForm, taxResult }: any) {
  return <HousePropertyEntryManager entries={entries} passThroughIncome={passThroughIncome} onChange={onChange} itrForm={itrForm} taxResult={taxResult} />;
}

function CapitalGainsTab({ formData, setFormData, taxResult, itrForm }: any) {
  const summary = taxResult?.capitalGainsSummary || null;
  return <CapitalGainsEntryManager
    data={formData.capitalGainsSchedule || {}}
    entries={formData.capitalGainTransactions || []}
    onChange={(capitalGainsSchedule) => setFormData({ ...formData, capitalGainsSchedule })}
    selectedForm={itrForm}
    summary={summary}
    issues={taxResult?.capitalGainsIssues || summary?.issues || []}
  />;
}

function BusinessTab({ formData, setFormData, taxResult, itrForm }: any) {
  return <BusinessProfessionEntryManager
    data={formData.businessSchedule || {}}
    onChange={(businessSchedule) => setFormData({ ...formData, businessSchedule })}
    selectedForm={itrForm}
    taxResult={taxResult}
  />;
}
