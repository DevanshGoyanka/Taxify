import React, { useState, useEffect, useMemo, useRef, useCallback, type SetStateAction } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAY } from '../contexts/AYContext';
import { itrV2 } from '../api/itrV2';
import { clientsApi } from '../api/clients';
import { itrAutomationApi } from '../api/itrAutomation';
import type { AutomationJob } from '../api/itrAutomation';
import { filingSubmitApi, type FilingJobStatus, type VerificationMode } from '../api/filingSubmit';
import { Spinner } from '../components/ui/Spinner';import StatusPill from '../components/StatusPill';
import toast from 'react-hot-toast';
import { EmployerEntryManager } from '../components/EmployerEntryManager';
import { BankAccountManager } from '../components/BankAccountManager';
import { PersonalInfoTab } from '../components/PersonalInfoTab';
import { hasNonSimplifiedCapitalGains } from '../components/CapitalGainsEntryManager';
import { BusinessProfessionEntryManager, type BusinessProfessionScheduleData } from '../components/BusinessProfessionEntryManager';
import { BankInterestEntryManager } from '../components/BankInterestEntryManager';
import { DonationEntryManager } from '../components/DonationEntryManager';
import { HousePropertyEntryManager } from '../components/HousePropertyEntryManager';
import EmployerReconciliationModal from '../components/EmployerReconciliationModal';
import { ITD_COUNTRY_CODES } from '../constants/itdCountryCodes';
import ExemptIncomeWorkspace from '../components/exemptincome/ExemptIncomeWorkspace';
import {
  createReturnRepository, stripCompatibility,
} from '../domain/returns';
import {
  banksToManager, challansToManager, deductionLoansToManager, familyPensionToManager, giftsToManager,
  interestToManager, tdsToManager, winningsToManager,
  updateBanksFromManager, updateBpNetProfit, updateCapitalGainsSchedule, updateChallanKindFromManager, updateDeductionLoansFromManager,
  updateDividendsFromManager, updateEmployers, updateExemptIncome, updateFamilyPensionFromManager, updateGiftsFromManager,
  updateHouseProperties, updateInterestFromManager, updateLossesBroughtForward, updateOtherSources, updateSection80C, updateSection80D, updateSection80G,
  updateChapterVIA, updateTaxCreditsFromManager, updateTcsCredits, updateWinningsFromManager,
  updatePensionContribution80CCC, updateSchedule80GGA, updateSchedule80GGC, updateTaxReturnPreparer,
  replaceDraft, type ReturnEditorModelV2,
} from '../domain/returns/editorModelV2';
import { createEmptyReturnDraft } from '../domain/returns/factory';
import type { ReturnDraft } from '../domain/returns/types';
import type {
  BankManagerData, ChallanManagerEntry, DeductionLoanManagerData, FamilyPensionManagerEntry,
  GiftManagerEntry, InterestManagerEntry, TdsManagerEntry, WinningManagerEntry,
} from '../domain/returns/editorModelV2';
import {
  assessFormEligibilityFromDraft, collectEligibilityFactsFromDraft, type FormRecommendation, type ItrForm,
} from '../domain/returns';
import { activeSchedules, blockingSchedules, type ScheduleStatus } from '../domain/returns';
import ImportConfirmationModal from '../components/ImportConfirmationModal';
import type { ReconciledResults } from '../api/itrAutomation';
import { calculateAgeFromDob as deriveAgeFromDob, getReferenceDate } from '../utils/age';
import { mergeDraft } from '../domain/returns/draftPatch';
import { buildPriorYearBPData, mapPrefillToDraftPatch } from '../utils/mapPrefillToDraftPatch';
import type { ITR4ScheduleBPData } from '../components/business/ITR4ScheduleBPManager';
import { businessesFromScheduleBp, scheduleBpFromBusinesses } from '../domain/returns/scheduleBpAdapter';
import { mapReconciledToDraftPatch } from '../utils/mapReconciledToDraftPatch';
import { mapAisToDraftPatch } from '../utils/mapAisToDraftPatch';
import { map26asToDraftPatch } from '../utils/map26asToDraftPatch';
import { mapTisToDraftPatch } from '../utils/mapTisToDraftPatch';
import { validateCbdtFrontendFields } from '../domain/returns/filingPreflight';

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

// Restricted-112A detection was folded into assessFormEligibilityFromDraft
// in Phase 8: it reads draft.capitalGainsSchedule and the backend's
// structured capital-gains issues directly. The standalone helper below was
// deleted with the rest of the flat-blob bridge.

import {
  OtherSourcesTab,
  DeductionsTab,
  TDSTab,
  TaxComputationTab, type CanonicalManagerBindings,
  CapitalGainsTab,
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

  // Type-3 Direct Submit (portal upload automation) state.
  // The backend generates + validates the CBDT JSON and enqueues a
  // Playwright upload job; we poll it here and surface the result inline.
  const [filingJobId, setFilingJobId] = useState<number | null>(null);
  const [filingSubmitting, setFilingSubmitting] = useState(false);
  const [filingJob, setFilingJob] = useState<FilingJobStatus | null>(null);
  
  // Part 2: Import document state
  const [importedAIS, setImportedAIS] = useState<any>(null);
  const [imported26AS, setImported26AS] = useState<any>(null);
  const [importedTIS, setImportedTIS] = useState<any>(null);
  
  // Employer reconciliation state
  const [showReconciliationModal, setShowReconciliationModal] = useState(false);
  const [reconciliationResult, setReconciliationResult] = useState<any>(null);
  const [editorModel, setEditorModel] = useState<ReturnEditorModelV2 | null>(null);
  const editorRef = useRef<ReturnEditorModelV2 | null>(null);
  // Monotonic counter bumped on every draft mutation so the debounced
  // compute effect re-fires after imports/edits (not just on form/regime
  // changes).  Without this, a prefill import that only changes the
  // draft content would leave the tax summary stale at ₹0.
  const [draftVersion, setDraftVersion] = useState(0);

  // Import confirmation modal state
  const [showImportConfirmModal, setShowImportConfirmModal] = useState(false);
  const [reconciledImportData, setReconciledImportData] = useState<ReconciledResults | null>(null);
  const [reconDiscrepancies, setReconDiscrepancies] = useState<string[]>([]);

  // The canonical draft is editor state, persistence state, and the only
  // payload the rest of the page reads. No flat-blob projection survives.
  const updateEditor = useCallback((update: (current: ReturnEditorModelV2) => ReturnEditorModelV2): void => {
    setEditorModel((current) => {
      if (!current) return current;
      const next = update(current);
      editorRef.current = next;
      setDraftVersion((v) => v + 1);
      return next;
    });
  }, []);
  const handleRegimeChange = useCallback((nextRegime: 'old' | 'new'): void => {
    setRegime(nextRegime);
    updateEditor((current) => replaceDraft({ ...current.draft, regime: nextRegime }));
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
    pensionContribution80CCC: (entries) => updateEditor((model) => updatePensionContribution80CCC(model, entries)),
    schedule80GGA: (entries) => updateEditor((model) => updateSchedule80GGA(model, entries)),
    schedule80GGC: (entries) => updateEditor((model) => updateSchedule80GGC(model, entries)),
    taxReturnPreparer: (next) => updateEditor((model) => updateTaxReturnPreparer(model, next)),
    tds: (entries) => updateEditor((model) => updateTaxCreditsFromManager(model, entries)),
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
    const resetModel = replaceDraft(createEmptyReturnDraft(effectiveAssessmentYear, itrForm, regime));
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
        loadedReturnKeyRef.current = `${clientId}:${effectiveAssessmentYear}`;
        setClientData(client);
        suppressAutoDetectRef.current = true;
        setItrForm(draft.form);
        setRegime(draft.regime);
        // Hydrate the canonical personal-info block from the saved draft,
        // falling back to the client record only when the draft is silent.
        const hydrated: ReturnEditorModelV2 = replaceDraft({
          ...draft,
          personal: {
            ...draft.personal,
            name: draft.personal.name || client.name || '',
            firstName: draft.personal.firstName || client.firstName || '',
            middleName: draft.personal.middleName || client.middleName || '',
            surnameOrOrgName: draft.personal.surnameOrOrgName || client.surname || '',
            pan: draft.personal.pan || client.pan || '',
            email: draft.personal.email || client.email || '',
            mobile: draft.personal.mobile || client.mobile || '',
            aadhaar: draft.personal.aadhaar || client.aadhaar || '',
            dateOfBirth: draft.personal.dateOfBirth || client.dob || null,
          },
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
    updateEditor((current) => replaceDraft({ ...current.draft, form: itrForm, regime }));
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
  const eligibilityResult = useMemo<FormRecommendation | null>(
    () => editorModel?.draft
      ? assessFormEligibilityFromDraft(editorModel.draft, backendTaxResult)
      : null,
    [editorModel?.draft, backendTaxResult],
  );

  useEffect(() => {
    if (!eligibilityResult) { setEligibility(null); return; }
    setEligibility(eligibilityResult);
    if (!formLockedByUser && eligibilityResult.recommendedForm !== itrForm) {
      setItrForm(eligibilityResult.recommendedForm);
      if (eligibilityResult.recommendedForm !== 'ITR-1') {
        toast(`Auto‑recommended: ${eligibilityResult.recommendedForm} — ${eligibilityResult.reason}`, { icon: '🔍', duration: 4000 });
      }
    }
  }, [eligibilityResult, formLockedByUser, itrForm]);

  const taxSummaryPayloadKey = useMemo(
    // The canonical draft is sent directly to the v2 compute endpoint via
    // `editorRef.current.draft` (see the effect below).  This memo feeds the
    // payload-key memo for debounce gating only.
    () => JSON.stringify({ form: itrForm, regime, ay: effectiveAssessmentYear }),
    [itrForm, effectiveAssessmentYear, regime],
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
      if (!currentDraft) return;
      const computePromise = itrV2.compute(stripCompatibility({ ...currentDraft, assessmentYear: effectiveAssessmentYear, form: itrForm, regime }));
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
  }, [clientId, effectiveAssessmentYear, regime, taxSummaryPayloadKey, loading, draftVersion]);

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

  // Recomputation-triggered eligibility: the eligibilityResult memo above
  // already updates on every canonical-draft change via the typed
  // assessFormEligibilityFromDraft evaluator.  This effect only resets the
  // suppress flag after the first saved-form load so the engine doesn't
  // immediately override the user-saved form choice.
  useEffect(() => {
    if (suppressAutoDetectRef.current) {
      suppressAutoDetectRef.current = false;
    }
  }, [editorModel?.draft]);

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
      const frontendErrors = validateCbdtFrontendFields(draft);
      if (frontendErrors.length > 0) {
        const report = { valid: false, errors: frontendErrors, warnings: [] };
        setValidationReport(report);
        toast.error(`${frontendErrors.length} blocking error(s) — see report`);
        return;
      }
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
      if (!currentEditor?.draft) throw new Error('Return is not loaded');
      const frontendErrors = validateCbdtFrontendFields(currentEditor.draft);
      if (frontendErrors.length > 0) {
        throw Object.assign(new Error('Correct the CBDT-constrained fields before generating JSON.'), { errors: frontendErrors });
      }
      // Generate from the typed canonical draft without composing or
      // normalizing a legacy payload. The v2 endpoint requires a persisted
      // draft, so save first to publish the latest editor state.
      await returnRepository.save(clientId, {
        ...currentEditor.draft,
        assessmentYear: effectiveAssessmentYear,
        form: itrForm,
        regime,
      });
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
      await itrV2.downloadPdf(clientId, effectiveAssessmentYear);
      toast.success('PDF downloaded successfully');
    } catch (err: any) {
      toast.error(err.message || 'PDF download failed');
    }
  };

  const handleDownloadJson = async () => {
    try {
      await itrV2.download(clientId, effectiveAssessmentYear);
      toast.success('Draft JSON downloaded successfully');
    } catch (err: any) {
      toast.error(err.message || 'Draft JSON download failed');
    }
  };

  // === Type-3 Direct Submit (portal upload automation) ===

  /**
   * Polling hook for a queued Direct-Submit filing job.
   *
   * Polls ``/api/v1/filing/jobs/{job_id}`` every 2s until the job reaches a
   * terminal state, then surfaces the acknowledgement number or error.
   */
  useEffect(() => {
    if (filingJobId === null) return;
    let cancelled = false;
    let interval: ReturnType<typeof setInterval> | null = null;
    const stopPolling = () => {
      if (interval) {
        clearInterval(interval);
        interval = null;
      }
    };
    const poll = async () => {
      try {
        const status = await filingSubmitApi.getJobStatus(filingJobId);
        if (cancelled) return;
        setFilingJob(status);
        if (status.status === 'completed') {
          stopPolling();
          const filing = status.result?.filing;
          const ack = filing?.acknowledgement_number;
          if (filing?.everify_status === 'verified') {
            toast.success(`Return submitted & e-verified ✓  ARN: ${ack ?? 'n/a'}`);
          } else if (ack) {
            toast.success(`Return submitted ✓  ARN: ${ack}`);
          } else {
            toast.success('Return submitted ✓');
          }
          // Auto-dismiss the success pill after 6s so the operator sees the
          // result, then clear job state so the button re-enables.
          setTimeout(() => {
            if (cancelled) return;
            setFilingJobId(null);
            setFilingJob(null);
            setFilingSubmitting(false);
          }, 6000);
        } else if (status.status === 'failed') {
          // STOP the interval — otherwise the poll keeps firing forever.
          // Keep the failed pill visible (no auto-clear) so the operator
          // can read the reason; the ✕ button clears job state.
          stopPolling();
          setFilingSubmitting(false);
          const reason = status.error_message || status.result?.filing?.reason || 'Portal upload failed';
          toast.error(`Submit failed: ${reason.slice(0, 200)}`, { duration: 10000 });
        }
      } catch {
        // transient poll error — retry on next tick
      }
    };
    poll();
    interval = setInterval(poll, 2000);
    return () => {
      cancelled = true;
      stopPolling();
    };
  }, [filingJobId]);

  const handleDirectSubmit = async () => {
    if (itrForm === 'ITR-3' || itrForm === 'ITR-2') {
      toast.error('Direct Submit is available for ITR-1 and ITR-4 only this season.');
      return;
    }
    if (!clientId || filingSubmitting || filingJobId !== null) return;

    // Consequential action — confirm before launching the portal upload.
    const ay = effectiveAssessmentYear;
    const ok = window.confirm(
      `Direct Submit will generate the CBDT JSON and launch a visible browser\n` +
      `that logs into the ITD portal as ${clientData?.pan ?? 'the taxpayer'} and uploads\n` +
      `the ${itrForm} return for AY ${ay}.\n\n` +
      `Verification mode: LATER (no OTP needed — verify after submission).\n\n` +
      `Continue?`,
    );
    if (!ok) return;

    setFilingSubmitting(true);
    setFilingJob(null);
    try {
      const currentEditor = editorRef.current;
      if (!currentEditor?.draft) throw new Error('Return is not loaded');
      const frontendErrors = validateCbdtFrontendFields(currentEditor.draft);
      if (frontendErrors.length > 0) {
        throw Object.assign(new Error('Correct the CBDT-constrained fields before direct submission.'), { details: { errors: frontendErrors } });
      }
      await returnRepository.save(clientId, {
        ...currentEditor.draft,
        assessmentYear: ay,
        form: itrForm,
        regime,
      });
      const verificationMode: VerificationMode = 'LATER';
      const res = await filingSubmitApi.submit(clientId, ay, itrForm, verificationMode);
      setFilingJobId(res.job_id);
      toast.success('Filing job queued — a browser will open to upload the JSON…');
    } catch (err: any) {
      setFilingSubmitting(false);
      const message = err?.message || 'Direct Submit failed';
      const errors: string[] = Array.isArray(err?.details?.errors) ? err.details.errors : [];
      toast.error(
        errors.length > 0 ? `${message}\n\n${errors.join('\n')}` : message,
        { duration: 10000 },
      );
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
    // Both AIS/TIS/26AS and the form-agnostic ITD Prefill are merged into the
    // canonical draft via typed patches. There is no flat-blob intermediate.
    if (!reconciledImportData) {
      toast.error('No import data available');
      return;
    }

    const discrepancies = Array.isArray((reconciledImportData as any).discrepancies) ? (reconciledImportData as any).discrepancies : [];
    const summary = (reconciledImportData as any).summary ?? { totalIncome: 0, salaryEntries: 0, businessEntries: 0, interestEntries: 0, dividendEntries: 0, capitalGainsEntries: 0, unmatched_tis: 0, unmatched_ais: 0, unmatched_as26: 0 };
    const prefillData = (reconciledImportData as any).prefill || null;

    // ──────────────────────────────────────────────────────────────────
    // TEMPORARILY DISABLED (Phase 2 testing)
    //
    // The filed-return merge is commented out so the portal automation
    // import doesn't surface the "already filed" blocking error during
    // testing.  See FILED_RETURN_REACTIVATION_GUIDE.md for reactivation.
    // REACTIVATE: const advisory = (reconciledImportData as any).filing_advisory;
    const advisory = null as any;

    // A portal import replaces a material portion of the draft. Any result
    // computed for the pre-import generation must not be presented as current.
    ++computationGenerationRef.current;
    if (taxResultDebounceRef.current) clearTimeout(taxResultDebounceRef.current);
    setBackendTaxResult(null);
    setTaxResultLoading(true);
    setTaxResultError('Computation unavailable for the imported draft until recalculated.');

    let mergedImportData: ReturnDraft | null = null;
    if (editorRef.current) {
      // An import is AUTHORITATIVE for the sections it covers (income
      // heads, employers, banks, TDS/TCS, businesses, capital gains,
      // house property, losses).  It must REPLACE those sections, not
      // accumulate via mergeDraft's append-only list semantics —
      // otherwise every re-import layers new entries on top of old
      // ones and the same interest appears 2×, 3×, 4×...  Personal info
      // is preserved from the existing draft (the import may not carry
      // it if the prefill didn't download).  See
      // IMPORTS_AND_RECONCILIATION_END_TO_END.md §4.
      // Prefill contributes ONLY personal info + refund bank account.
      // Everything else (income heads, employers, TDS/TCS, deductions,
      // capital gains) comes from the reconciled patch (26AS/AIS/TIS).
      // This is the single source of truth — no duplication possible.
      const prefillPatch = mapPrefillToDraftPatch(prefillData);
      const reconciledPatch = mapReconciledToDraftPatch(reconciledImportData);
      // Debug: trace what the import patches contain so blank-tab issues
      // can be diagnosed without a debugger.
      if (import.meta.env.DEV) {
        // eslint-disable-next-line no-console
        console.debug('[handleConfirmImport] reconciledPatch keys:', Object.keys(reconciledPatch));
        // eslint-disable-next-line no-console
        console.debug('[handleConfirmImport] CG sales:', (reconciledImportData as any)?.capital_gain_sales?.length, 'purchases:', (reconciledImportData as any)?.capital_gain_purchases?.length);
        // eslint-disable-next-line no-console
        console.debug('[handleConfirmImport] CG schedule:', Object.keys(reconciledPatch.capitalGainsSchedule || {}));
        // eslint-disable-next-line no-console
        console.debug('[handleConfirmImport] businesses:', reconciledPatch.businesses?.length);
        // eslint-disable-next-line no-console
        console.debug('[handleConfirmImport] income_heads:', Object.keys((reconciledImportData as any)?.income_heads || {}));
      }
      // Start from a baseline that keeps personal/filing/regime/form
      // but BLANKS every import-owned list so the patches populate them
      // fresh (no accumulation across re-imports).
      const prior = editorRef.current.draft;
      // Clone personal/filing/form/regime + the house-property pass-through
      // and exempt-income state from the prior draft (the import may not
      // carry these), but BLANK every import-owned list so patches
      // populate them fresh — no accumulation across re-imports.
      const blankedBaseline: ReturnDraft = {
        ...prior,
        employers: [],
        bankAccounts: [],
        businesses: [],
        houseProperties: [],
        capitalGainsSchedule: {
          ...prior.capitalGainsSchedule,
          schedule112A: [],
          schedule115AD: [],
          purchases: [],
          stEquity: [],
          stImmovable: [],
          ltImmovable: [],
          vda: [],
          stDtaa: [],
          ltDtaa: [],
          simplified112A: { totalSaleConsideration: 0, totalCostAcquisition: 0 },
        },
        otherSources: {
          ...prior.otherSources,
          interest: [],
          dividends: [],
          winnings: [],
          gifts: [],
          otherIncome: [],
          dtaaIncome: [],
          section89A: [],
          accumulatedPf: [],
          specialRateIncome: [],
        },
        taxes: { tds: [], tcs: [], challans: [] },
        provenance: [],
      };
      mergedImportData = mergeDraft(
        mergeDraft(blankedBaseline, prefillPatch),
        reconciledPatch,
      );
      updateEditor((current) => replaceDraft(mergedImportData as ReturnDraft));
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
    if (((reconciledImportData as any).category_control_discrepancies?.length || 0) > 0) {
      for (const discrepancy of (reconciledImportData as any).category_control_discrepancies || []) {
        msgs.push(
          `${discrepancy.category}: TIS accepted total ₹${discrepancy.tis_accepted_total.toLocaleString('en-IN')} ` +
          `differs from annexure detail total ₹${discrepancy.tis_detail_total.toLocaleString('en-IN')}. ` +
          'The accepted TIS total controls computation; all detail rows remain preserved for review.'
        );
      }
    }
    if ((summary.unmatched_tis || 0) > 0 || (summary.unmatched_ais || 0) > 0 || (summary.unmatched_as26 || 0) > 0) {
      const parts: string[] = [];
      if (summary.unmatched_tis) parts.push('TIS');
      if (summary.unmatched_ais) parts.push('AIS');
      if (summary.unmatched_as26) parts.push('26AS');
      msgs.push(
        `${(summary.unmatched_tis || 0) + (summary.unmatched_ais || 0) + (summary.unmatched_as26 || 0)} ` +
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
      `Import complete: ${Number(summary.totalIncome || 0).toLocaleString('en-IN')} total income, ` +
      `${Number(summary.salaryEntries || 0)} salary, ${Number((summary as any).businessEntries || 0)} business, ` +
      `${Number(summary.interestEntries || 0)} interest, ` +
      `${Number(summary.dividendEntries || 0)} dividend, ${Number(summary.capitalGainsEntries || 0)} capital gains entries`
    );

    // Show a secondary toast with Prefill-specific imports (deductions,
    // bank accounts, personal info) that AIS/TIS/26AS don't carry.
    const prefillSummary = (prefillData as any)?.summary ?? (prefillData as any) ?? {};
    const prefillHasContent = !!prefillSummary.personalInfo || Number(prefillSummary.employerEntries || 0) > 0 || Number(prefillSummary.bankAccounts || 0) > 0;
    if (prefillHasContent) {
      const prefillParts: string[] = [];
      if (prefillSummary.personalInfo) prefillParts.push('personal info');
      if (Number(prefillSummary.employerEntries || 0) > 0) prefillParts.push(`${prefillSummary.employerEntries} employer(s)`);
      if (Number(prefillSummary.bankAccounts || 0) > 0) prefillParts.push(`${prefillSummary.bankAccounts} bank account(s)`);
      if (Number(prefillSummary.deductionsTotal || 0) > 0) prefillParts.push(`deductions ₹${Number(prefillSummary.deductionsTotal).toLocaleString('en-IN')}`);
      if (Number(prefillSummary.tdsSalaryEntries || 0) > 0) prefillParts.push(`${prefillSummary.tdsSalaryEntries} TDS-salary`);
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
      returnRepository.save(clientId, mergedImportData).catch(err => console.warn('Background save after import failed:', err));
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
        // server-side merge with no real Form 16 parser.  Patch the first
        // employer row directly on the canonical draft instead of round-
        // tripping through a flat-blob composition.
        const data = (form16Data || {}) as {
            basic?: number; da?: number; hra?: number; bonus?: number;
            professionalTax?: number; tdsDeducted?: number;
          };
        updateEditor((current) => {
          const first = current.draft.employers[0] ?? {
            id: 'employer-form16', customEmployerName: '', employerName: '', employerTAN: '',
            natureOfEmployment: '', employerAddress: '', employerCity: '', employerStateCode: '',
            employerPinCode: '', employerZipCode: '',
            salaryNatureRows: [], perquisiteNatureRows: [], section10ExemptionRows: [],
            basic: 0, da: 0, commission: 0, hra: 0, bonus: 0, allowances: 0, lta: 0,
            otherAllowance: 0, arrearSalary: 0, perquisites: 0, profitsInLieu: 0, rentPaid: 0,
            city: '', isMetroCity: false, isGovernmentEmployee: false, isDisabledEmployee: false,
            commutedPension: 0, gratuity: 0, leaveEncashment: 0, averageMonthlySalary: 0,
            yearsOfService: 0, unavailedLeaveDays: 0, actualLtaFare: 0, isDomesticTravel: false,
            journeysInBlock: 0, ltaExempt: 0, numberOfChildren: 0, gratuityAlsoReceived: false,
            transportAllowance: 0, childrenEducationAllowance: 0, hostelExpenditureAllowance: 0,
            uniformAllowance: 0, entertainmentAllowance: 0, professionalTax: 0,
            vrsCompensation: 0, retrenchmentCompensation: 0, otherExempt: 0, tdsDeducted: 0,
            employerNPS: 0,
          };
          const patched = {
            ...first,
            basic: data.basic ?? first.basic,
            da: data.da ?? first.da,
            hra: data.hra ?? first.hra,
            bonus: data.bonus ?? first.bonus,
            professionalTax: data.professionalTax ?? first.professionalTax,
            tdsDeducted: data.tdsDeducted ?? first.tdsDeducted,
          };
          const employers = current.draft.employers.length > 0 ? [patched, ...current.draft.employers.slice(1)] : [patched];
          return replaceDraft({ ...current.draft, employers });
        });
        toast.dismiss();
        toast.success('Form 16 imported into the canonical draft');
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
          updateEditor((current) => replaceDraft(merged));
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

          // importResult.data is the PrefillExtraction dict.  Pull its summary
          // block directly (the typed patcher below carries every
          // employer/bank/deduction entry into the draft).
          const prefillPayload = importResult.data || importResult;

          if (importGeneration !== loadGenerationRef.current || !editorRef.current) return;
          const merged = mergeDraft(editorRef.current.draft, mapPrefillToDraftPatch(prefillPayload));
          updateEditor((current) => replaceDraft(merged));
          await returnRepository.save(clientId, merged);

          setShowImportMenu(false);

          const prefillSummary = (prefillPayload as any)?.summary ?? (prefillPayload as any) ?? {};
          const prefillParts: string[] = [];
          if (prefillSummary.personalInfo) prefillParts.push('personal info');
          if (Number(prefillSummary.employerEntries || 0) > 0) prefillParts.push(`${prefillSummary.employerEntries} employer(s)`);
          if (Number(prefillSummary.bankAccounts || 0) > 0) prefillParts.push(`${prefillSummary.bankAccounts} bank account(s)`);
          if (Number(prefillSummary.deductionsTotal || 0) > 0) prefillParts.push(`deductions ₹${Number(prefillSummary.deductionsTotal).toLocaleString('en-IN')}`);
          toast.dismiss();
          toast.success(`Prefill imported: ${prefillParts.join(', ') || 'canonical draft updated'}`);
        } else {
          // All non-prefill import types now flow through the typed patcher
          // branch above; if any new type falls through here, surface an
          // explicit error rather than silently writing to a flat blob.
          toast.dismiss();
          toast.error(`No typed patcher wired for ${String(type).toUpperCase()}; import aborted.`);
        }
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

    // Update employer entries based on action.  Apply new values directly to
    // the canonical draft.employers list and strip any reconciliation row
    // matching the same TAN from the displayed discrepancies.
    updateEditor((current) => {
      const list = current.draft.employers.map((entry: any) => {
        const matchingDiscrepancy = reconciliationResult?.discrepancies?.find(
          (d: any) => d.employerTAN === entry.employerTAN,
        );
        if (matchingDiscrepancy && matchingDiscrepancy.employerTAN === discrepancy.employerTAN && action === 'USE_NEW') {
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
        return entry;
      });
      return replaceDraft({ ...current.draft, employers: list });
    });
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

  // The legacy autoDetectITRForm function was deleted in Phase 8: ITR form
  // selection now flows through assessFormEligibilityFromDraft and the
  // `eligibilityResult` useMemo above, which reads the typed canonical draft.

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
                  if (isDowngrade && hasNonSimplifiedCapitalGains(editorModel?.draft.capitalGainsSchedule)) {
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

          <button
            onClick={handleDownloadJson}
            title="Download the saved canonical ReturnDraft as a JSON file"
            style={{
              padding: '6px 12px',
              background: 'var(--accent-purple)',
              color: 'white',
              border: 'none',
              borderRadius: 6,
              fontSize: 12,
              cursor: 'pointer'
            }}
          >
            Draft JSON
          </button>

          {itrForm !== 'ITR-3' && itrForm !== 'ITR-2' && (
            <button
              onClick={handleDirectSubmit}
              disabled={filingSubmitting || filingJobId !== null}
              title="Generate the CBDT JSON and launch a visible browser that logs into the ITD portal and uploads the return (Type-3, verification mode: LATER)"
              style={{
                padding: '6px 12px',
                background: (filingSubmitting || filingJobId !== null)
                  ? 'var(--border)'
                  : 'var(--accent-navy, #0b3d6b)',
                color: 'white',
                border: 'none',
                borderRadius: 6,
                fontSize: 12,
                fontWeight: 600,
                cursor: (filingSubmitting || filingJobId !== null) ? 'not-allowed' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: 6,
              }}
            >
              {filingSubmitting && <Spinner size={12} />}
              Direct Submit
            </button>
          )}

          {filingJobId !== null && filingJob && (
            <span
              className={`badge badge-${filingJob.status === 'completed' ? 'success' : filingJob.status === 'failed' ? 'danger' : 'info'}`}
              style={{
                fontSize: 11.5,
                padding: '5px 10px',
                borderRadius: 'var(--radius-sm)',
                lineHeight: 1.3,
                userSelect: 'none',
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
              }}
              title={filingJob.error_message ? filingJob.error_message.slice(0, 200) : undefined}
            >
              {filingJob.status !== 'completed' && filingJob.status !== 'failed' && (
                <span
                  style={{
                    display: 'inline-block',
                    width: 6,
                    height: 6,
                    borderRadius: '50%',
                    background: 'currentColor',
                    animation: 'pulse 1.2s ease-in-out infinite',
                  }}
                />
              )}
              <span>
                {filingJob.status === 'queued' && 'Filing queued…'}
                {filingJob.status === 'running' && (filingJob.progress_label || filingJob.status_message || 'Uploading…')}
                {filingJob.status === 'completed' && (() => {
                  const ack = filingJob.result?.filing?.acknowledgement_number;
                  return ack ? `Submitted ✓ ${ack}` : 'Submitted ✓';
                })()}
                {filingJob.status === 'failed' && 'Submit failed'}
              </span>
              {filingJob.status !== 'completed' && (
                <button
                  onClick={() => {
                    setFilingJobId(null);
                    setFilingJob(null);
                    setFilingSubmitting(false);
                  }}
                  style={{
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    padding: 0,
                    margin: 0,
                    marginLeft: 2,
                    fontSize: 10,
                    color: 'inherit',
                    opacity: 0.6,
                    lineHeight: 1,
                  }}
                  title="Dismiss"
                >
                  ✕
                </button>
              )}
            </span>
          )}
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
      {eligibility && editorModel && (() => {
        const facts = collectEligibilityFactsFromDraft(editorModel.draft, backendTaxResult);
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
        {activeTab === 0 && editorModel && <PersonalInfoTab draft={editorModel.draft} itrForm={itrForm as 'ITR-1' | 'ITR-2' | 'ITR-3' | 'ITR-4'} onChange={(patch: any) => updateEditor((current) => ({
          ...current,
          draft: {
            ...current.draft,
            ...(patch.regime ? { regime: patch.regime } : {}),
            ...(patch.personal ? { personal: { ...current.draft.personal, ...patch.personal } } : {}),
            ...(patch.filing ? { filing: { ...current.draft.filing, ...patch.filing } } : {}),
            ...(patch.verification ? { verification: { ...current.draft.verification, ...patch.verification } } : {}),
            ...(patch.taxReturnPreparer ? { taxReturnPreparer: { ...current.draft.taxReturnPreparer, ...patch.taxReturnPreparer } } : {}),
          },
        }))} onBanksChange={managers.banks} onRegimeChange={handleRegimeChange} />}
        {activeTab === 1 && <SalaryTab entries={editorModel?.draft.employers ?? []} onChange={(entries: any[]) => updateEditor((model) => updateEmployers(model, entries))} taxResult={backendTaxResult} ayParam={effectiveAssessmentYear} regime={regime} tdsEntries={tdsToManager(editorModel?.draft?.taxes?.tds ?? [])} />}
        {activeTab === 2 && <HousePropertyTab entries={editorModel?.draft.houseProperties ?? []} passThroughIncome={editorModel?.draft.housePropertyPassThroughIncome ?? 0} onChange={(entries: any[], passThroughIncome: number) => updateEditor((model) => updateHouseProperties(model, entries, passThroughIncome))} itrForm={itrForm} taxResult={backendTaxResult} />}
        {activeTab === 3 && editorModel && <CapitalGainsTab draft={editorModel.draft} taxResult={taxResult} itrForm={itrForm as ItrForm} onChange={(schedule) => updateEditor((model) => updateCapitalGainsSchedule(model, schedule))} />}
        {activeTab === 4 && editorModel && <BusinessTab taxResult={taxResult} itrForm={itrForm as string} draft={editorModel.draft} onChangeBusinesses={(entries: ReturnDraft['businesses']) => updateEditor((model) => replaceDraft({ ...model.draft, businesses: entries }))} onChangeBpNetProfit={(value: number) => updateEditor((model) => updateBpNetProfit(model, value))} priorYearData={buildPriorYearBPData((reconciledImportData as any)?.prefill)} />}
        {activeTab === 5 && <OtherSourcesTab taxResult={taxResult} managers={managers} itrForm={itrForm} regime={regime} editorModel={editorModel as any} />}
        {activeTab === 6 && editorModel && <ExemptIncomeWorkspace form={itrForm} schedule={editorModel.draft.exemptIncome} onChange={(next) => updateEditor((model) => updateExemptIncome(model, next))} />}
        {activeTab === 7 && editorModel && <DeductionsTab regime={regime} taxResult={taxResult} managers={managers} form={itrForm} editorModel={editorModel as any} />}
        {activeTab === 8 && editorModel && <TDSTab taxResult={taxResult} managers={managers} editorModel={editorModel as any} />}
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

function BusinessTab({ taxResult, itrForm, draft, onChangeBusinesses, priorYearData }: { taxResult: any; itrForm: string; draft: ReturnDraft; onChangeBusinesses: (entries: ReturnDraft['businesses']) => void; onChangeBpNetProfit: (value: number) => void; priorYearData?: ITR4ScheduleBPData | null }): React.ReactElement {
  if (itrForm === 'ITR-4') {
    return <BusinessProfessionEntryManager
      data={{ ITR4ScheduleBP: scheduleBpFromBusinesses(draft.businesses) }}
      onChange={(next) => onChangeBusinesses(businessesFromScheduleBp(next.ITR4ScheduleBP ?? {}))}
      selectedForm={itrForm}
      taxResult={taxResult}
      priorYearData={priorYearData}
    />;
  }
  // Surface the reconciled business income the import produced (GST
  // turnover, business receipts, commission, etc. rolled into a presumptive
  // 44AD/44ADA entry on draft.businesses).  The BusinessProfessionEntryManager
  // below captures the full official ITR-3/4 Schedule BP beyond the
  // presumptive roll-up; that fuller state is kept in a localStorage cache
  // keyed by PAN+AY+form so switching tabs (which unmounts this component)
  // does not lose it.
  const cacheKey = `biz-schedule-${draft.personal?.pan || 'unknown'}-${draft.assessmentYear || ''}-${itrForm}`;
  const importedBusiness = draft.businesses[0] as any;
  const importedData: BusinessProfessionScheduleData = (importedBusiness?.businessSpecific ?? {}) as BusinessProfessionScheduleData;
  const [data, setData] = useState<BusinessProfessionScheduleData>(() => {
    try {
      const raw = localStorage.getItem(cacheKey);
      return raw ? JSON.parse(raw) as BusinessProfessionScheduleData : importedData;
    } catch {
      return importedData;
    }
  });
  // When the import's business roll-up changes (e.g. re-import), re-seed
  // from the draft so the imported figures are never lost behind a stale
  // cache.
  useEffect(() => {
    setData((prev) => {
      const seed = importedData;
      const hasImport = Object.keys(seed).length > 0;
      if (!hasImport) return prev;
      return { ...prev, ...seed };
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cacheKey, draft.businesses]);
  const handleChange = useCallback((next: BusinessProfessionScheduleData) => {
    setData(next);
    try { localStorage.setItem(cacheKey, JSON.stringify(next)); } catch { /* ignore quota */ }
  }, [cacheKey]);
  // Imported presumptive roll-up banner (turnover + scheme + declared
  // income) so the user sees the reconciled business income even before
  // they fill the full Schedule BP.
  const importedRollup = importedBusiness
    ? { scheme: importedBusiness.scheme, turnover: Number(importedBusiness.digitalReceipts ?? importedBusiness.grossReceipts ?? 0), declaredIncome: Number(importedBusiness.declaredIncome ?? 0), businessName: importedBusiness.businessName || '' }
    : null;
  return <>
    {importedRollup && (
      <div style={{ marginBottom: 12, padding: '10px 14px', background: 'var(--gold-pale)', border: '1px solid var(--gold)', borderRadius: 6, fontSize: 12, color: 'var(--text-secondary)' }}>
        <strong>Reconciled business income (from AIS/TIS):</strong>
        &nbsp;{importedRollup.businessName} — {importedRollup.scheme} —
        Gross receipts ₹{Number(importedRollup.turnover || 0).toLocaleString('en-IN')} →
        Presumptive income ₹{Number(importedRollup.declaredIncome || 0).toLocaleString('en-IN')}.
        &nbsp;Review and adjust the Schedule BP below.
      </div>
    )}
    <BusinessProfessionEntryManager
      data={data}
      onChange={handleChange}
      selectedForm={itrForm}
      taxResult={taxResult}
      priorYearData={priorYearData}
    />
  </>;
}
