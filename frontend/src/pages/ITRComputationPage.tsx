import React, { useState, useEffect, useMemo, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAY } from '../contexts/AYContext';
import { itrApi } from '../api/itr';
import { clientsApi } from '../api/clients';
import { Spinner } from '../components/ui/Spinner';
import toast from 'react-hot-toast';
import { EmployerEntryManager } from '../components/EmployerEntryManager';
import { BankAccountManager } from '../components/BankAccountManager';
import { CapitalGainsEntryManager } from '../components/CapitalGainsEntryManager';
import { BankInterestEntryManager } from '../components/BankInterestEntryManager';
import { DonationEntryManager } from '../components/DonationEntryManager';
import { HousePropertyEntryManager } from '../components/HousePropertyEntryManager';
import EmployerReconciliationModal from '../components/EmployerReconciliationModal';
import { ITD_COUNTRY_CODES } from '../constants/itdCountryCodes';

function buildPhase1Payload(source: any): any {
  const data = { ...source };
  const investments = data.section80C?.investments || [];
  const healthCategories = data.section80D
    ? [data.section80D.selfFamily, data.section80D.selfFamilySenior, data.section80D.parents, data.section80D.parentsSenior]
    : [];
  const loans80E = data.deductionLoans?.section80E?.loans || [];
  const eligibleDonations = (data.donationEntries || []).reduce((sum: number, entry: any) => {
    const percentage = String(entry.category || '').startsWith('50_') ? 0.5 : 1;
    return sum + (Math.min(Number(entry.donationAmtCash) || 0, 2000) + (Number(entry.donationAmtOtherMode) || 0)) * percentage;
  }, 0);

  data.s80C = investments.reduce((sum: number, item: any) => sum + (Number(item.amount) || 0), 0);
  data.s80D = healthCategories.reduce((total: number, category: any) => total
    + (category?.policies || []).reduce((sum: number, policy: any) => sum + (Number(policy.premiumAmount) || 0), 0)
    + (Number(category?.preventiveCheckup) || 0) + (Number(category?.medicalExpense) || 0), 0);
  data.s80E = loans80E.reduce((sum: number, loan: any) => sum + (Number(loan.interestAmount) || 0), 0);
  data.s80G = eligibleDonations;
  data.bankAccountDetails = (data.bankAccountData?.accounts || []).map((account: any) => ({ ...account }));
  data.countryCodeMobile = String(data.mobileCountryCode || '91');
  data.countryCode = String(data.country || '91');
  data.stateCode = String(data.state || '');
  data.advanceTaxEntries = Array.isArray(data.advanceTaxEntries) ? data.advanceTaxEntries : [];
  if (data.advanceTaxEntries.length >= 0) {
    data.adv15Jun = 0; data.adv15Sep = 0; data.adv15Dec = 0; data.adv15Mar = 0;
  }
  return data;
}

function validatePhase1Payload(data: any): string | null {
  const panPattern = /^[A-Z]{5}[0-9]{4}[A-Z]$/;
  const ifscPattern = /^[A-Z]{4}0[A-Z0-9]{6}$/;
  const bsrPattern = /^[0-9]{3}[0-9A-Z]{4}$/;
  if (!/^[0-9]{1,5}$/.test(String(data.mobileCountryCode || ''))) return 'Select a valid mobile country code.';
  if (!data.state) return 'Select a state code.';
  if (!data.country) return 'Select a country code.';
  if (data.pincode && !/^[1-9][0-9]{5}$/.test(String(data.pincode))) return 'PIN code must contain 6 digits and cannot start with zero.';
  for (const entry of data.donationEntries || []) {
    if (!entry.doneeName || !panPattern.test(entry.doneePAN || '') || !entry.addrDetail || !entry.city || !entry.stateCode || !/^[1-9][0-9]{5}$/.test(entry.pinCode || '')) return 'Complete every 80G donee name, PAN, address, state and PIN code before saving.';
  }
  for (const investment of data.section80C?.investments || []) {
    if (!investment.investmentType || !investment.dateOfInvestment || !investment.institutionName || !panPattern.test(investment.institutionPAN || '') || !investment.accountOrPolicyNo || Number(investment.amount) <= 0) return 'Complete every 80C investment, including date, institution PAN, account/policy number and amount.';
  }
  const categories = data.section80D ? [data.section80D.selfFamily, data.section80D.selfFamilySenior, data.section80D.parents, data.section80D.parentsSenior] : [];
  for (const category of categories) for (const policy of category?.policies || []) {
    if (!policy.insurerName || !policy.policyNo || !policy.policyType || !policy.dateOfCommencement || Number(policy.premiumAmount) <= 0) return 'Complete every 80D policy, including policy type and commencement date.';
  }
  for (const section of ['section80E', 'section80EE', 'section80EEA', 'section80EEB']) for (const loan of data.deductionLoans?.[section]?.loans || []) {
    if (!loan.bankOrInstnName || !panPattern.test(loan.lenderPAN || '') || !loan.loanAccNo || !loan.dateOfLoan || Number(loan.interestAmount) <= 0) return `Complete every ${section.replace('section', '')} loan, including lender PAN and interest.`;
    if (section === 'section80EE' && loan.firstTimeBuyerEligible !== true) return '80EE loans require first-time home buyer eligibility confirmation.';
    if (section === 'section80EEB' && !loan.vehicleRegNo) return '80EEB loans require the vehicle registration number.';
  }
  const accounts = data.bankAccountData?.accounts || [];
  if (accounts.length > 0 && !accounts.some((account: any) => account.useForRefund)) return 'Mark one bank account for refund.';
  for (const account of accounts) if (!account.bankName || !account.accountNumber || !ifscPattern.test(account.ifscCode || '')) return 'Complete every bank account with a valid 11-character IFSC code.';
  for (const payment of data.advanceTaxEntries || []) if (!bsrPattern.test(payment.bsrCode || '') || !payment.depositDate || !payment.challanSerialNo || Number(payment.amount) <= 0) return 'Complete every advance-tax challan with valid BSR code, date, serial number and amount.';
  return null;
}

import { 
  BusinessTab, 
  OtherSourcesTab, 
  DeductionsTab, 
  TDSTab, 
  TaxComputationTab
} from './ITRComputationTabs';

export default function ITRComputationPage() {
  const { clientId, year } = useParams();
  const navigate = useNavigate();
  const { ayParam } = useAY();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [activeTab, setActiveTab] = useState(0);
  const [regime, setRegime] = useState<'old' | 'new'>('new');
  const [itrForm, setItrForm] = useState('ITR-1');
  const [showImportMenu, setShowImportMenu] = useState(false);
  const [clientData, setClientData] = useState<any>(null);
  
  // Part 2: Import document state
  const [importedAIS, setImportedAIS] = useState<any>(null);
  const [imported26AS, setImported26AS] = useState<any>(null);
  const [importedTIS, setImportedTIS] = useState<any>(null);
  
  // Employer reconciliation state
  const [showReconciliationModal, setShowReconciliationModal] = useState(false);
  const [reconciliationResult, setReconciliationResult] = useState<any>(null);
  const [formData, setFormData] = useState<any>({
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
    bizPresumptive: '44AD', bizTurnover: 0, bizDeclared: 0, bpNetProfit: 0,
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
    bankInterestEntries: [],
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
    advanceTaxEntries: [],
    selfAssessmentTaxEntries: [],
    bankAccountDetails: [],
    bankAccountData: { accounts: [] },
    // Legacy single-value fields (for backward compatibility)
    tdsS192: 0, tds194A: 0, tdsOther: 0,
    adv15Jun: 0, adv15Sep: 0, adv15Dec: 0, adv15Mar: 0, selfTax: 0,
    age: 30
  });

  useEffect(() => {
    if (!clientId) return;
    setLoading(true);
    Promise.all([
      clientsApi.get(Number(clientId)),
      itrApi.getFormData(Number(clientId), ayParam || '2025-26')
    ])
      .then(([client, itrData]) => {
        setClientData(client);
        // Prioritize saved form data over client master data
        // Map address fields from backend names to frontend names
        setFormData((prev: any) => ({ 
          ...prev,
          // Use client data as fallback only if form data doesn't have it
          name: itrData.name || client.name,
          pan: itrData.pan || client.pan,
          email: itrData.email || client.email,
          mobile: itrData.mobile || client.mobile,
          aadhaar: itrData.aadhaar || client.aadhaar,
          dob: itrData.dob || client.dob,
          fatherName: itrData.fatherName,
          age: itrData.age,
          // Address field mapping: backend -> frontend
          flatNo: itrData.flatDoorNo || itrData.flatNo,
          premises: itrData.premisesName || itrData.premises,
          road: itrData.roadStreet || itrData.road,
          area: itrData.area,
          city: itrData.townCity || itrData.city,
          state: itrData.state,
          pincode: itrData.pinCode || itrData.pincode,
          // Spread all other form data
          ...itrData,
          mobileCountryCode: String(itrData.mobileCountryCode || itrData.countryCodeMobile || prev.mobileCountryCode || '91'),
          country: String(itrData.countryCode || itrData.country || prev.country || '91'),
          advanceTaxEntries: Array.isArray(itrData.advanceTaxEntries) ? itrData.advanceTaxEntries : [],
          section80C: itrData.section80C?.investments ? itrData.section80C : prev.section80C,
          section80D: itrData.section80D?.selfFamily ? itrData.section80D : prev.section80D,
          deductionLoans: itrData.deductionLoans?.section80E ? itrData.deductionLoans : prev.deductionLoans,
          bankAccountData: itrData.bankAccountData?.accounts
            ? itrData.bankAccountData
            : { accounts: (itrData.bankAccountDetails || []).map((account: any, index: number) => ({
                id: account.id || `legacy-bank-${index}`,
                bankName: account.bankName || '', accountNumber: account.accountNumber || '',
                ifscCode: account.ifscCode || '',
                accountType: account.accountType === 'SAVINGS' ? 'SB' : account.accountType === 'CURRENT' ? 'CA' : (account.accountType || 'SB'),
                useForRefund: account.useForRefund === true || index === 0,
              })) },
        }));
      })
      .catch(err => toast.error(err.message))
      .finally(() => setLoading(false));
  }, [clientId, ayParam]);

  const [backendTaxResult, setBackendTaxResult] = useState<any>(null);
  const [taxResultLoading, setTaxResultLoading] = useState(false);

  // Debounce timer ref for tax summary API calls
  const taxResultDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Fetch backend-computed tax summary - replaces local computeTax()
  // Debounced: only fires 500ms after user stops typing
  useEffect(() => {
    if (!clientId || !ayParam) return;

    // Cancel any pending call
    if (taxResultDebounceRef.current) {
      clearTimeout(taxResultDebounceRef.current);
    }

    taxResultDebounceRef.current = setTimeout(() => {
      console.log('[TAX] Calling computeTaxSummary for Other Sources...', { ayParam, regime: regime, formDataKeys: Object.keys(formData || {}) });
      setTaxResultLoading(true);
      itrApi.computeTaxSummary(buildPhase1Payload(formData), ayParam || '2025-26', regime)
        .then((result: any) => {
          console.log('[TAX] computeTaxSummary result - regimeUsed:', result.taxRegime, 'result:', result);
          setBackendTaxResult(result);
        })
        .catch((err: any) => {
          console.error('[TAX] computeTaxSummary ERROR:', err);
          // If backend call fails, clear result (no fallback to local)
          setBackendTaxResult(null);
        })
        .finally(() => setTaxResultLoading(false));
    }, 500);
  }, [clientId, ayParam, regime, formData]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (taxResultDebounceRef.current) {
        clearTimeout(taxResultDebounceRef.current);
      }
    };
  }, []);

  const taxResult = useMemo(() => {
    // ALWAYS use backend-computed result - no local calculation
    if (backendTaxResult) return backendTaxResult;
    // Return empty result when loading or no data - include ALL Other Sources properties
    return {
      grossSalary: 0, hraExempt: 0, netSalary: 0, hpIncome: 0, cgTax: 0,
      bizIncome: 0, otherIncome: 0, vdaTax: 0, gti: 0, gtiAfterSetOff: 0,
      totalDeductions: 0, totalIncome: 0, normalTax: 0, rebate87A: 0,
      surcharge: 0, cess: 0, totalTaxLiability: 0, totalTaxPaid: 0,
      taxPayable: 0, refund: 0, vdaGains: 0,
      totalInterest: 0, interestDeduction80TTA: 0, interestDeduction80TTB: 0,
      totalDividend: 0, dividendTaxableAtSpecialRate: 0, dividendTaxableAtNormalRate: 0,
      totalWinnings: 0, winningsTax: 0, taxableGifts: 0, familyPensionDed: 0, specialRateIncome: 0,
      familyPensionIncome: 0, // Added for Other Sources
      tdsS192: 0, tds194A: 0, tdsOther: 0,
      adv15Jun: 0, adv15Sep: 0, adv15Dec: 0, adv15Mar: 0,
      selfTax: 0, tdsEntries: [], selfAssessmentTaxEntries: [],
      // Schedule S (Salary) fields — populated by backend SalaryScheduleComputer
      salaryIncome: 0, salary171: 0, salary172: 0, salary173: 0,
      ltaExempt: 0, gratuityExempt: 0, leaveEncashmentExempt: 0,
      pensionCommutationExempt: 0, transportExempt: 0,
      childrenEducationExempt: 0, hostelExempt: 0, uniformExempt: 0,
      totalSection10Exempt: 0, standardDeduction: 0,
      entertainmentAllowanceDed: 0, professionalTaxDed: 0,
      totalSection16Deductions: 0, salaryTDS: 0, salaryEmployerCount: 0,
      hraCondition1: 0, hraCondition2: 0, hraCondition3: 0,
      hraIsMetro: false, hraCityClassified: ''
    };
  }, [backendTaxResult]);

  useEffect(() => {
    autoDetectITRForm();
  }, [
    formData.basic, 
    formData.bizTurnover, 
    formData.bpNetProfit, 
    formData.bizPresumptive,
    formData.stcgPre, 
    formData.stcgPost, 
    formData.stcgOther,
    formData.ltcgPre, 
    formData.ltcgPost, 
    formData.ltcgOther,
    formData.vdaGains,
    formData.grossRent, 
    formData.interestFD, 
    formData.dividends,
    formData.isDirector,
    formData.holdsUnlistedShares,
    formData.agriculturalIncome,
    formData.residentialStatus,
    formData.bfLossHP,
    formData.bfLossBusiness,
    formData.bfLossSTCG,
    formData.bfLossLTCG
  ]);

  const handleSave = async () => {
    setSaving(true);
    try {
      // Clear legacy fields if using new array-based system
      const validationError = validatePhase1Payload(formData);
      if (validationError) {
        toast.error(validationError);
        return;
      }
      const dataToSave = buildPhase1Payload(formData);
      
      // Clear legacy TDS/SAT fields
      if (dataToSave.tdsEntries && dataToSave.tdsEntries.length >= 0) {
        dataToSave.tdsS192 = 0;
        dataToSave.tds194A = 0;
        dataToSave.tdsOther = 0;
      }
      if (dataToSave.selfAssessmentTaxEntries && dataToSave.selfAssessmentTaxEntries.length >= 0) {
        dataToSave.selfTax = 0;
      }
      
      // Clear legacy salary fields if using multi-employer
      if (dataToSave.employerEntries && dataToSave.employerEntries.length > 0) {
        dataToSave.basic = 0;
        dataToSave.da = 0;
        dataToSave.hra = 0;
        dataToSave.bonus = 0;
      }
      
      // Clear legacy CG fields if using transaction-based
      if (dataToSave.capitalGainTransactions && dataToSave.capitalGainTransactions.length > 0) {
        dataToSave.stcgEquityPre = 0;
        dataToSave.stcgEquityPost = 0;
        dataToSave.stcgOtherSlab = 0;
        dataToSave.ltcg112APre = 0;
        dataToSave.ltcg112APost = 0;
        dataToSave.ltcgOtherPre = 0;
        dataToSave.ltcgOtherPost = 0;
      }
      
      // Clear legacy interest fields if using bank-wise
      if (dataToSave.bankInterestEntries && dataToSave.bankInterestEntries.length > 0) {
        dataToSave.interestSB = 0;
        dataToSave.interestFD = 0;
      }
      
      // Clear legacy 80G field if using donation entries
      if (dataToSave.donationEntries && dataToSave.donationEntries.length > 0) {
        dataToSave.s80G = 0;
      }
      
      await itrApi.saveFormData(Number(clientId), year!, dataToSave);
      toast.success('Saved ✓');
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleDownloadJson = () => {
    itrApi.downloadJson(Number(clientId), year!).catch(err => toast.error(err.message));
  };

  const handleDownloadPdf = async () => {
    try {
      await itrApi.downloadPdf(Number(clientId), year!);
      toast.success('PDF downloaded successfully');
    } catch (err: any) {
      toast.error(err.message || 'PDF download failed');
    }
  };

  const handleFileImport = async (type: string, file: File) => {
    try {
      toast.loading(`Importing ${type}...`);
      
      if (type === 'form16-pdf' || type === 'form16-json') {
        const data = await import('../api/integration').then(m => m.integrationApi.extractForm16(file));
        const populated = await import('../api/integration').then(m => m.integrationApi.autoPopulateFromForm16(formData, data));
        setFormData((prev: any) => ({ ...prev, ...populated }));
        toast.dismiss();
        toast.success('Form 16 imported and auto-populated');
      } else if (type === 'ais-pdf' || type === 'ais-json' || type === 'tis-pdf' || type === '26as-pdf' || type === '26as-txt' || type === 'prefill') {
        const typeStr = type as string;
        let data: any;

        const pan = clientData?.pan;
        const dob = clientData?.dob; // YYYY-MM-DD format

        // Validate PAN and DOB are available for encrypted documents (except TXT/ZIP)
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
          data = await integrationApi.importAIS(file, Number(clientId), year!, pan!, dob!);
          setImportedAIS(data);
        } else if (typeStr === 'ais-json') {
          const { integrationApi } = await import('../api/integration');
          data = await integrationApi.importAISJson(file, pan!, dob!);
          setImportedAIS(data);
        } else if (typeStr === 'tis-pdf') {
          const { integrationApi } = await import('../api/integration');
          data = await integrationApi.importTIS(file, pan!, dob!);
          setImportedTIS(data);
        } else if (typeStr === '26as-txt' || typeStr === '26as-pdf') {
          const { integrationApi } = await import('../api/integration');
          // Backend will use client's DOB as password for ZIP files
          data = await integrationApi.import26AS(file, Number(clientId));
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
        
        // Auto-populate from all available documents
        if (type === 'ais-pdf' || type === 'ais-json' || type === 'tis-pdf' || type === '26as-pdf' || type === '26as-txt') {
          // For 26AS, transform TDS entries to frontend format
          let tdsEntriesForForm = [];
          
          // Determine financial year from 26AS data
          // Format from 26AS: "2025-2026" -> convert to "2025-26"
          let fyFrom26AS = '2025-26'; // default
          if (data.financialYear) {
            const fyParts = data.financialYear.split('-');
            if (fyParts.length === 2) {
              fyFrom26AS = fyParts[0] + '-' + fyParts[1].substring(2);
            }
          }
          
          if (type === '26as-txt' || type === '26as-pdf') {
            const tdsFrom26AS = data.tdsEntries || data.deductorAggregates || [];
            tdsEntriesForForm = tdsFrom26AS.map((entry: any) => ({
              section: entry.sectionCode || entry.section || '192',
              deductorName: entry.employerName || entry.deductorName || 'Unknown Employer',
              deductorTAN: entry.employerTAN || entry.deductorTAN || '',
              deductorPAN: entry.deductorPAN || '',
              incomeAmount: entry.incomeAmount || entry.totalAmount || 0,
              tdsDeducted: entry.tdsDeducted || entry.totalTDS || 0,
              certificateNo: entry.certificateNo || '',
              deductionDate: entry.transactionDate || entry.deductionDate || '',
              uniqueTransactionNo: entry.uniqueTransactionNo || entry.utrNo || '',
              financialYear: fyFrom26AS, // Use correct FY from 26AS
              verified26AS: true,
              claimedInReturn: true
            }));
            console.log('26AS TDS entries transformed with FY:', fyFrom26AS, tdsEntriesForForm);
          }
          
          // For 26AS only, directly set form data without calling autoPopulateAll
          if (type === '26as-txt' || type === '26as-pdf') {
            const incomeBreakdown = data.incomeBreakdown || {};
            const deductorDetails = incomeBreakdown.deductorDetails || [];
            
            // Get financial year from 26AS data (format: "2025-2026" -> "2025-26")
            let fyFrom26AS = data.financialYear || '2025-26';
            if (fyFrom26AS.includes("2025")) {
              fyFrom26AS = '2025-26';
            } else if (fyFrom26AS.includes("2024")) {
              fyFrom26AS = '2024-25';
            }
            
            // TDS entries only (where TDS > 0)
            const tdsOnlyEntries = tdsEntriesForForm.filter((e: any) => (e.tdsDeducted || 0) > 0);
            
            // ===== BUILD EMPLOYER ENTRIES (Summary per employer) =====
            const salaryDeductors = deductorDetails.filter((d: any) => 
              d.sectionCode === '192' || d.sectionCode === '192A'
            );
            
            const employerEntriesFrom26AS = salaryDeductors.map((deductor: any) => ({
              employerName: deductor.employerName || 'Employer',
              employerTAN: deductor.employerTAN || '',
              employerPAN: '',
              basic: deductor.totalAmount || 0,
              da: 0,
              hra: 0,
              bonus: 0,
              allowances: 0,
              perquisites: 0,
              professionalTax: 0,
              tdsDeducted: deductor.totalTDS || 0,
              grossSalary: deductor.totalAmount || 0,
              netSalary: (deductor.totalAmount || 0) - (deductor.totalTDS || 0),
              financialYear: fyFrom26AS,
              verified26AS: true
            }));
            
            // ===== BUILD DIVIDEND ENTRIES (Summary per company) =====
            const dividendDeductors = deductorDetails.filter((d: any) => d.sectionCode === '194');
            const dividendEntriesFrom26AS = dividendDeductors.map((deductor: any) => ({
              companyName: deductor.employerName || 'Company',
              companyPAN: '',
              dividendAmount: deductor.totalAmount || 0,
              tdsDeducted: deductor.totalTDS || 0,
              deductorTAN: deductor.employerTAN || '',
              isin: '',
              category: 'SHARES',
              section: deductor.sectionCode || '194'
            }));
            
            // ===== BUILD INTEREST ENTRIES (Summary per bank/deductor) =====
            const interestDeductors = deductorDetails.filter((d: any) => 
              d.sectionCode === '194A' || d.sectionCode === '193' || d.sectionCode === '194K'
            );
            const bankInterestEntriesFrom26AS = interestDeductors.map((deductor: any) => ({
              bankName: deductor.employerName || 'Bank',
              accountNumber: '',
              accountType: 'SAVINGS',
              interestEarned: deductor.totalAmount || 0,
              tdsDeducted: deductor.totalTDS || 0,
              deductorTAN: deductor.employerTAN || '',
              section: deductor.sectionCode || '194A'
            }));
            
            // Calculate total income from all heads
            const totalIncomeFrom26AS = 
              (incomeBreakdown.salaryIncome || 0) + 
              (incomeBreakdown.dividendIncome || 0) + 
              (incomeBreakdown.interestIncome || 0) +
              (incomeBreakdown.housePropertyIncome || 0) +
              (incomeBreakdown.capitalGains || 0) +
              (incomeBreakdown.businessIncome || 0) +
              (incomeBreakdown.lotteryIncome || 0) +
              (incomeBreakdown.vdaIncome || 0) +
              (incomeBreakdown.onlineGamingIncome || 0) +
              (incomeBreakdown.tcsIncome || 0);
            
            const formDataUpdate: any = {
              // ===== SALARY ENTRIES =====
              employerEntries: employerEntriesFrom26AS.length > 0 ? employerEntriesFrom26AS : [],
              basic: employerEntriesFrom26AS.length > 0 ? employerEntriesFrom26AS[0].basic : 0,
              
              // ===== TDS ENTRIES =====
              tdsEntries: tdsOnlyEntries,
              tdsS192: incomeBreakdown.salaryIncome > 0 ? (data.totalTdsSalary || 0) : 0,
              tds194A: incomeBreakdown.interestIncome > 0 ? (data.totalTdsInterest || 0) : 0,
              tdsOther: (data.totalTDS || 0) - (data.totalTdsSalary || 0) - (data.totalTdsInterest || 0),
              
              // Store 26AS import info for display
              imported26AS: {
                totalTDS: data.totalTDS,
                totalIncome: totalIncomeFrom26AS,
                financialYear: fyFrom26AS,
                assessmentYear: data.assessmentYear || '2026-27',
                deductorCount: tdsOnlyEntries.length,
                incomeBreakdown: incomeBreakdown
              },
              
              // ===== DIVIDEND ENTRIES (per company) =====
              dividendEntries: dividendEntriesFrom26AS.length > 0 ? dividendEntriesFrom26AS : [],
              
              // ===== BANK INTEREST ENTRIES (per bank) =====
              bankInterestEntries: bankInterestEntriesFrom26AS.length > 0 ? bankInterestEntriesFrom26AS : [],
              
              // ===== MAP TO RESPECTIVE INCOME HEADS =====
              grossRent: incomeBreakdown.housePropertyIncome || 0,
              ltcgProperty: incomeBreakdown.capitalGains || 0,
              bizTurnover: incomeBreakdown.businessIncome || 0,
              interestSB: incomeBreakdown.interestIncome || 0,
              interestFD: incomeBreakdown.interestIncome || 0,
              dividends: incomeBreakdown.dividendIncome || 0,
              lotteryIncome: incomeBreakdown.lotteryIncome || 0,
              horseRaceIncome: incomeBreakdown.horseRaceIncome || 0,
              vdaGains: incomeBreakdown.vdaIncome || 0,
              onlineGamingIncome: incomeBreakdown.onlineGamingIncome || 0,
              tcsCollections: incomeBreakdown.tcsIncome || 0,
              incomeBreakdown26AS: incomeBreakdown,
            };
            
            console.log('26AS Import - Employer Entries:', employerEntriesFrom26AS);
            console.log('26AS Import - Dividend Entries:', dividendEntriesFrom26AS);
            console.log('26AS Import - Interest Entries:', bankInterestEntriesFrom26AS);
            
            setFormData((prev: any) => ({ ...prev, ...formDataUpdate }));
            await itrApi.saveFormData(Number(clientId), year!, { ...formData, ...formDataUpdate });
            toast.dismiss();
            
            const message = `26AS imported! ${tdsOnlyEntries.length} TDS entries. ` +
              `Salary: ${employerEntriesFrom26AS.length} employer (₹${(incomeBreakdown.salaryIncome || 0).toLocaleString('en-IN')}), ` +
              `Dividends: ${dividendEntriesFrom26AS.length} companies (₹${(incomeBreakdown.dividendIncome || 0).toLocaleString('en-IN')})`;
            toast.success(message);
            setShowImportMenu(false);
            return;
          }
          
          const { integrationApi } = await import('../api/integration');

          // Auto-populate from AIS and TIS documents
          const populated = await integrationApi.autoPopulateAll(
            Number(clientId),
            year!,
            importedAIS || data,
            imported26AS || data,
            importedTIS || data
          );
          
          setFormData((prev: any) => ({ ...prev, ...populated }));
          
          // If both AIS and 26AS available, check reconciliation
          const ais = importedAIS || data;
          const f26as = imported26AS || data;
          const tis = importedTIS || data;
          
          if (ais && f26as) {
            const report = await integrationApi.getReconciliationReport(ais, f26as, tis);
            if (report.hasDiscrepancies) {
              toast.dismiss();
              toast.error(`${type.toUpperCase()} imported. Reconciliation needed - ${report.items.length} discrepancies found.`);
              setShowImportMenu(false);
              return;
            }
          }
          
          await itrApi.saveFormData(Number(clientId), year!, { ...formData, ...populated });
          toast.dismiss();
          toast.success(`${type.toUpperCase()} imported and auto-populated successfully!`);
        } else if (type === 'prefill') {
          // ITD Prefill - use backend import API with clientId tracking
          const { integrationApi } = await import('../api/integration');
          
          // Import to backend - this saves to database
          const importResult = await integrationApi.importITDPrefill(
            file, 
            Number(clientId), 
            year!
          );
          
          console.log('Prefill import result:', importResult);
          toast.success('Prefill imported successfully! Reloading data...');
          
          // Reload form data from backend to get the extracted data
          const freshFormData = await itrApi.getFormData(Number(clientId), year!);
          console.log('Fresh form data from backend:', freshFormData);
          
          // Update form with the extracted data - use direct assignment for numeric fields
          setFormData((prev: any) => ({ 
            ...prev,
            // Numeric fields - use ?? for null/undefined, allow 0 values through
            interestSB: freshFormData.interestSB ?? prev.interestSB,
            interestFD: freshFormData.interestFD ?? prev.interestFD,
            bankInterest: freshFormData.bankInterest ?? prev.bankInterest,
            totalDividend: freshFormData.totalDividend ?? prev.totalDividend,
            dividends: freshFormData.dividends ?? prev.dividends,
            itRefundInterest: freshFormData.itRefundInterest ?? prev.itRefundInterest,
            incomeFromITRefund: freshFormData.incomeFromITRefund ?? prev.incomeFromITRefund,
            s80TTB: freshFormData.s80TTB ?? prev.s80TTB,
            s80C: freshFormData.s80C ?? prev.s80C,
            s80D: freshFormData.s80D ?? prev.s80D,
            s80E: freshFormData.s80E ?? prev.s80E,
            s80TTA: freshFormData.s80TTA ?? prev.s80TTA,
            s80G: freshFormData.s80G ?? prev.s80G,
            s80CCD: freshFormData.s80CCD ?? prev.s80CCD,
            s80CCC1B: freshFormData.s80CCC1B ?? prev.s80CCC1B,
            totalTds: freshFormData.totalTds ?? prev.totalTds,
            tds194A: freshFormData.tds194A ?? prev.tds194A,
            // String fields - use || for empty strings
            name: freshFormData.name || prev.name,
            pan: freshFormData.pan || prev.pan,
            email: freshFormData.email || prev.email,
            mobile: freshFormData.mobile || prev.mobile,
            aadhaar: freshFormData.aadhaar || prev.aadhaar,
            // Array fields - preserve if empty
            employerEntries: freshFormData.employerEntries || prev.employerEntries,
            tdsEntries: freshFormData.tdsEntries || prev.tdsEntries,
            bankAccountDetails: freshFormData.bankAccountDetails || prev.bankAccountDetails,
            bankAccountData: freshFormData.bankAccountData || prev.bankAccountData || { accounts: [] },
            bankInterestEntries: freshFormData.bankInterestEntries || prev.bankInterestEntries,
          }));
          
          setShowImportMenu(false);
          
          // All data is now loaded from backend, just show success message
          toast.dismiss();
          toast.success('Prefill data imported and loaded successfully!');
        } else {
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

    setFormData({ ...formData, employerEntries: updatedEntries });
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
    // Comprehensive ITR form detection based on CBDT rules - AY 2025-26
    const hasBusinessIncome = (formData.bizTurnover || 0) > 0 || (formData.bpNetProfit || 0) > 0;
    const hasPresumptiveIncome = hasBusinessIncome && formData.bizPresumptive && formData.bizPresumptive !== 'Regular';
    
    // Capital Gains - ALL types including real-estate, movable, VDA, securities
    const hasCapitalGains = 
      (formData.stcgPre || 0) > 0 || 
      (formData.stcgPost || 0) > 0 || 
      (formData.stcgOther || 0) > 0 ||
      (formData.ltcgPre || 0) > 0 || 
      (formData.ltcgPost || 0) > 0 || 
      (formData.ltcgOther || 0) > 0 ||
      (formData.vdaGains || 0) > 0;
    
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
    
    const hasMultipleProperties = formData.hpType === 'letout' && (formData.grossRent || 0) > 0;
    const hasForeignIncome = (formData.foreignIncome || 0) > 0 || (formData.foreignAssets || 0) > 0;
    const totalIncome = taxResult.totalIncome || 0;
    const agriculturalIncome = formData.agriculturalIncome || 0;
    const isDirector = formData.isDirector || false;
    const hasUnlistedShares = formData.holdsUnlistedShares || false;
    const isNonResident = formData.residentialStatus && formData.residentialStatus !== 'ROR';
    const hasBFLoss = (formData.bfLossHP || 0) > 0 || (formData.bfLossBusiness || 0) > 0 || 
                      (formData.bfLossSTCG || 0) > 0 || (formData.bfLossLTCG || 0) > 0;

    let detectedForm = 'ITR-1';
    let reason = '';

    // Priority 1: ITR-4 (Presumptive taxation)
    if (hasPresumptiveIncome) {
      detectedForm = 'ITR-4';
      reason = 'Presumptive income under 44AD/44ADA';
    }
    // Priority 2: ITR-3 (Business/Professional income - non-presumptive)
    else if (hasBusinessIncome) {
      detectedForm = 'ITR-3';
      reason = 'Business or professional income';
    }
    // Priority 3: ITR-2 conditions - Capital Gains (Real-estate, Movable, Foreign, Securities, VDA)
    else if (hasCapitalGains) {
      detectedForm = 'ITR-2';
      reason = 'Capital gains from investments/real-estate/VDA/securities';
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

  const validateITRFormSelection = (selectedForm: string) => {
    // Validate if manually selected form is eligible - CBDT Rules for ITR-1/ITR-2
    const hasBusinessIncome = (formData.bizTurnover || 0) > 0 || (formData.bpNetProfit || 0) > 0;
    const hasPresumptiveIncome = hasBusinessIncome && formData.bizPresumptive && formData.bizPresumptive !== 'Regular';
    
    // ALL Capital Gains - Real-estate, Movable, Foreign, Securities, VDA
    const hasCapitalGains = 
      (formData.stcgPre || 0) > 0 || 
      (formData.stcgPost || 0) > 0 || 
      (formData.stcgOther || 0) > 0 ||
      (formData.ltcgPre || 0) > 0 || 
      (formData.ltcgPost || 0) > 0 || 
      (formData.ltcgOther || 0) > 0 ||
      (formData.vdaGains || 0) > 0;
    
    // Special Income - Lottery, Online Gaming
    const hasSpecialIncome = 
      (formData.winnings || 0) > 0 || 
      (formData.lotteryIncome || 0) > 0 ||
      (formData.onlineGamingIncome || 0) > 0 ||
      (formData.cardGameIncome || 0) > 0 ||
      (formData.raceWinnings || 0) > 0;
    
    // Exempt Income
    const hasExemptIncome = 
      (formData.rajarshi || 0) > 0 ||
      (formData.municipal || 0) > 0 ||
      (formData.scholarship || 0) > 0 ||
      (formData.gratuity || 0) > 0 ||
      (formData.severance || 0) > 0 ||
      (formData.vrs || 0) > 0;
    
    const totalIncome = taxResult.totalIncome || 0;
    const agriculturalIncome = formData.agriculturalIncome || 0;
    const isDirector = formData.isDirector || false;
    const hasUnlistedShares = formData.holdsUnlistedShares || false;
    const isNonResident = formData.residentialStatus && formData.residentialStatus !== 'ROR';
    const hasBFLoss = (formData.bfLossHP || 0) > 0 || (formData.bfLossBusiness || 0) > 0 || 
                      (formData.bfLossSTCG || 0) > 0 || (formData.bfLossLTCG || 0) > 0;
    const hasForeignIncome = (formData.foreignIncome || 0) > 0 || (formData.foreignAssets || 0) > 0;

    const errors: string[] = [];

    if (selectedForm === 'ITR-1') {
      // Rule 10: Total income > ₹50 lakh
      if (totalIncome > 5000000) errors.push('Total income exceeds ₹50 lakhs (Rule 10)');
      // Capital Gains - All types
      if (hasCapitalGains) errors.push('Capital gains (Real-estate/Movable/Securities/VDA) not allowed in ITR-1');
      // Business Income
      if (hasBusinessIncome) errors.push('Business income not allowed in ITR-1 (use ITR-3/ITR-4)');
      // Agricultural Income
      if (agriculturalIncome > 5000) errors.push('Agricultural income exceeds ₹5,000');
      // Director in company/firm
      if (isDirector) errors.push('Directors must file ITR-2 or ITR-3');
      // Unlisted shares
      if (hasUnlistedShares) errors.push('Unlisted shares holders must file ITR-2');
      // Non-resident
      if (isNonResident) errors.push('Non-residents/RNOR must file ITR-2');
      // Brought forward losses
      if (hasBFLoss) errors.push('Brought forward losses not allowed in ITR-1');
      // Special income (Lottery, Gaming)
      if (hasSpecialIncome) errors.push('Lottery/Online gaming winnings require ITR-2 (Section 115BB)');
      // Foreign income
      if (hasForeignIncome) errors.push('Foreign income/assets require ITR-2');
      // Exempt income requiring Schedule EI
      if (hasExemptIncome) errors.push('Exempt income requires ITR-2 (Schedule EI)');
    }
    else if (selectedForm === 'ITR-2') {
      // ITR-2 cannot have regular business income (use ITR-3)
      if (hasBusinessIncome && !hasPresumptiveIncome) {
        errors.push('Regular business income requires ITR-3 or ITR-4 (presumptive)');
      }
      // ITR-2 cannot have presumptive business (use ITR-4)
      if (hasPresumptiveIncome) {
        errors.push('Presumptive income (44AD/44ADA/44AE) requires ITR-4');
      }
    }
    else if (selectedForm === 'ITR-3') {
      if (!hasBusinessIncome) errors.push('ITR-3 is only for business/professional income');
      if (hasPresumptiveIncome) errors.push('Presumptive income should use ITR-4');
    }
    else if (selectedForm === 'ITR-4') {
      if (!hasPresumptiveIncome) errors.push('ITR-4 is only for presumptive taxation (44AD/44ADA/44AE)');
    }

    if (errors.length > 0) {
      toast.error(`ITR-${selectedForm.split('-')[1]} not eligible:\n${errors.join('\n')}`, { duration: 6000 });
      return false;
    }
    return true;
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
                <span>AY {ayParam || '2025-26'}</span>
              </div>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <select
              value={itrForm}
              onChange={(e) => {
                const newForm = e.target.value;
                if (validateITRFormSelection(newForm)) {
                  setItrForm(newForm);
                } else {
                  // Revert to previous value if validation fails
                  e.target.value = itrForm;
                }
              }}
              style={{
                padding: '6px 12px',
                border: '1px solid var(--border)',
                borderRadius: 6,
                fontSize: 13,
                fontWeight: 500,
                background: 'white'
              }}
            >
              <option value="ITR-1">ITR-1</option>
              <option value="ITR-2">ITR-2</option>
              <option value="ITR-3">ITR-3</option>
              <option value="ITR-4">ITR-4</option>
            </select>
            <select
              value={regime}
              onChange={(e) => {
                const newRegime = e.target.value as 'old' | 'new';
                console.log('[REGIME] Changed from', regime, 'to', newRegime);
                setRegime(newRegime);
              }}
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

          <div style={{ position: 'relative' }}>
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
                <label style={{
                  display: 'block',
                  padding: '8px 12px',
                  fontSize: 12,
                  cursor: 'pointer'
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
            onClick={handleDownloadJson}
            style={{
              padding: '6px 12px',
              background: 'var(--accent-blue)',
              color: 'white',
              border: 'none',
              borderRadius: 6,
              fontSize: 12,
              cursor: 'pointer'
            }}
          >
            JSON
          </button>

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
        {activeTab === 0 && <PersonalInfoTab formData={formData} setFormData={setFormData} />}
        {activeTab === 1 && <SalaryTab formData={formData} setFormData={setFormData} taxResult={taxResult} ayParam={ayParam} regime={regime} />}
        {activeTab === 2 && <HousePropertyTab formData={formData} setFormData={setFormData} taxResult={taxResult} itrForm={itrForm} />}
        {activeTab === 3 && <CapitalGainsTab formData={formData} setFormData={setFormData} taxResult={taxResult} year={year!} />}
        {activeTab === 4 && <BusinessTab formData={formData} setFormData={setFormData} taxResult={taxResult} />}
        {activeTab === 5 && <OtherSourcesTab formData={formData} setFormData={setFormData} taxResult={taxResult} />}
        {activeTab === 6 && <ExemptIncomeTab formData={formData} setFormData={setFormData} />}
        {activeTab === 7 && <DeductionsTab formData={formData} setFormData={setFormData} regime={regime} taxResult={taxResult} />}
        {activeTab === 8 && <TDSTab formData={formData} setFormData={setFormData} taxResult={taxResult} />}
        {activeTab === 9 && <TaxComputationTab taxResult={taxResult} regime={regime} itrForm={itrForm} />}
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
// EXEMPT INCOME TAB - CBDT SCHEDULE EI (VR1-027, VR1-028)
// ============================================================================
function ExemptIncomeTab({ formData, setFormData }: any) {
  return (
    <div>
      <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 16, color: 'var(--text-secondary)' }}>
        Schedule EI - Exempt Income (CBDT VR1-027, VR1-028)
      </h3>
      
      <div style={{ padding: 12, background: 'var(--info-bg)', borderRadius: 6, fontSize: 12, color: 'var(--info)', marginBottom: 16 }}>
        Exempt income is reported in Schedule EI. Agricultural income above Rs 5,000 requires ITR-2.
      </div>

      {/* Agricultural Income */}
      <h4 style={{ fontSize: 13, fontWeight: 600, marginBottom: 12, color: 'var(--text-secondary)' }}>
        Agricultural Income (Section 10(1))
      </h4>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 24 }}>
        <Field label="Gross Agricultural Income" value={formData.agricultureIncome || 0} onChange={(v: any) => setFormData({ ...formData, agricultureIncome: v })} />
        <Field label="Deductible Agricultural Expenses" value={formData.agricultureExpenses || 0} onChange={(v: any) => setFormData({ ...formData, agricultureExpenses: v })} />
        <Field label="Net Agricultural Income" value={(formData.agricultureIncome || 0) - (formData.agricultureExpenses || 0)} computed />
      </div>

      {/* Exempt Interest Income */}
      <h4 style={{ fontSize: 13, fontWeight: 600, marginBottom: 12, color: 'var(--text-secondary)' }}>
        Exempt Interest Income (Section 10)
      </h4>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 24 }}>
        <Field label="PPF Interest (Exempt)" value={formData.ppfInterest || 0} onChange={(v: any) => setFormData({ ...formData, ppfInterest: v })} />
        <Field label="Sukanya Samriddhi Interest (Exempt)" value={formData.sukanyaSamriddhiInterest || 0} onChange={(v: any) => setFormData({ ...formData, sukanyaSamriddhiInterest: v })} />
        <Field label="Other Exempt Interest" value={formData.otherExemptInterest || 0} onChange={(v: any) => setFormData({ ...formData, otherExemptInterest: v })} />
      </div>

      {/* Long Term Capital Gains Exempt */}
      <h4 style={{ fontSize: 13, fontWeight: 600, marginBottom: 12, color: 'var(--text-secondary)' }}>
        LTCG Exempt u/s 10(33) - Equity Shares
      </h4>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 24 }}>
        <Field label="LTCG u/s 10(33) - Equity" value={formData.ltcgExempt || 0} onChange={(v: any) => setFormData({ ...formData, ltcgExempt: v })} />
        <Field label="LTCG Exemption u/s 10(38)" value={formData.ltcgExempt38 || 0} onChange={(v: any) => setFormData({ ...formData, ltcgExempt38: v })} />
        <Field label="Total Exempt LTCG" value={(formData.ltcgExempt || 0) + (formData.ltcgExempt38 || 0)} computed />
      </div>

      {/* Other Exempt Income */}
      <h4 style={{ fontSize: 13, fontWeight: 600, marginBottom: 12, color: 'var(--text-secondary)' }}>
        Other Exempt Income
      </h4>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 24 }}>
        <Field label="Gratuity Exempt u/s 10(10)" value={formData.gratuityExempt || 0} onChange={(v: any) => setFormData({ ...formData, gratuityExempt: v })} />
        <Field label="Leave Encashment Exempt u/s 10(10AA)" value={formData.leaveEncashmentExempt || 0} onChange={(v: any) => setFormData({ ...formData, leaveEncashmentExempt: v })} />
        <Field label="VRS Compensation Exempt u/s 10(10C)" value={formData.vrsCompensationExempt || 0} onChange={(v: any) => setFormData({ ...formData, vrsCompensationExempt: v })} />
        <Field label="Commutation of Pension" value={formData.commutationPension || 0} onChange={(v: any) => setFormData({ ...formData, commutationPension: v })} />
        <Field label="Share of Profit from Firm/HUF" value={formData.shareOfProfitFirm || 0} onChange={(v: any) => setFormData({ ...formData, shareOfProfitFirm: v })} />
        <Field label="Any Other Exempt Income" value={formData.otherExemptIncome || 0} onChange={(v: any) => setFormData({ ...formData, otherExemptIncome: v })} />
      </div>

      {/* Total Exempt Income Summary */}
      <h4 style={{ fontSize: 13, fontWeight: 600, marginBottom: 12, color: 'var(--gold)' }}>
        Total Exempt Income
      </h4>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 16 }}>
        <Field 
          label="Total Exempt Income (Schedule EI)" 
          value={
            (formData.agricultureIncome || 0) +
            (formData.ppfInterest || 0) +
            (formData.sukanyaSamriddhiInterest || 0) +
            (formData.otherExemptInterest || 0) +
            (formData.ltcgExempt || 0) +
            (formData.ltcgExempt38 || 0) +
            (formData.gratuityExempt || 0) +
            (formData.leaveEncashmentExempt || 0) +
            (formData.vrsCompensationExempt || 0) +
            (formData.commutationPension || 0) +
            (formData.shareOfProfitFirm || 0) +
            (formData.otherExemptIncome || 0)
          } 
          computed 
        />
      </div>
    </div>
  );
}

function Field({ label, value, onChange, computed, prefix = '₹', type = 'number', required = false }: any) {
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
      // Clear the field if it's 0 or empty
      if (value === 0 || value === '') {
        setDisplayValue('');
        e.target.value = '';
      } else {
        // Show raw number without commas for editing
        setDisplayValue(value.toString());
        e.target.value = value.toString();
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
      const rawValue = parseIndianNumber(e.target.value);
      // Only allow integers, no decimals
      const numValue = rawValue === '' ? 0 : Math.round(Number(rawValue));
      
      if (!isNaN(numValue)) {
        setDisplayValue(e.target.value);
        onChange(numValue);
      }
    } else {
      setDisplayValue(e.target.value);
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
          type="text"
          value={computed ? (type === 'number' ? formatIndianNumber(value) : value) : displayValue}
          onChange={handleChange}
          onFocus={handleFocus}
          onBlur={handleBlur}
          readOnly={computed}
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
    </div>
  );
}

function SalaryTab({ formData, setFormData, taxResult, ayParam, regime }: any) {
  return <EmployerEntryManager entries={formData.employerEntries || []} onChange={(entries) => setFormData({ ...formData, employerEntries: entries })} assessmentYear={ayParam || '2025-26'} taxRegime={regime === 'new' ? 'NEW' : 'OLD'} backendResult={taxResult} />;
}

function HousePropertyTab({ formData, setFormData, itrForm }: any) {
  return <HousePropertyEntryManager entries={formData.housePropertyEntries || []} onChange={(entries) => setFormData({ ...formData, housePropertyEntries: entries })} itrForm={itrForm} />;
}

function CapitalGainsTab({ formData, setFormData }: any) {
  return <CapitalGainsEntryManager entries={formData.capitalGainTransactions || []} onChange={(entries) => setFormData({ ...formData, capitalGainTransactions: entries })} />;
}

function PersonalInfoTab({ formData, setFormData }: any) {
  const calculateAge = (dob: string) => {
    if (!dob) return 0;
    const birthDate = new Date(dob);
    const refDate = new Date('2026-03-31'); // Age as on 31st March of AY
    let age = refDate.getFullYear() - birthDate.getFullYear();
    const monthDiff = refDate.getMonth() - birthDate.getMonth();
    if (monthDiff < 0 || (monthDiff === 0 && refDate.getDate() < birthDate.getDate())) {
      age--;
    }
    return age;
  };

  const handleDobChange = (dob: string) => {
    const age = calculateAge(dob);
    setFormData({ ...formData, dob, age });
  };

  return (
    <div>
      <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 16, color: 'var(--text-secondary)' }}>
        Part A - General Information (Auto-populated from Client Master)
      </h3>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 24 }}>
        <Field label="Name of Assessee" value={formData.name || ''} onChange={(v: any) => setFormData({ ...formData, name: v })} type="text" prefix="" />
        <Field label="PAN" value={formData.pan || ''} onChange={(v: any) => setFormData({ ...formData, pan: v })} type="text" prefix="" />
        <Field label="Aadhaar Number" value={formData.aadhaar || ''} onChange={(v: any) => setFormData({ ...formData, aadhaar: v })} type="text" prefix="" />
        <Field label="Date of Birth / Formation" value={formData.dob || ''} onChange={handleDobChange} type="date" prefix="" />
        <Field label="Age as on 31/03" value={formData.age} computed prefix="" />
        <Field label="Status" value={formData.status || 'Individual'} onChange={(v: any) => setFormData({ ...formData, status: v })} type="text" prefix="" />
      </div>

      <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 16, color: 'var(--text-secondary)' }}>
        CBDT Mandatory Fields
      </h3>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 24 }}>
        <Field label="Father's Name *" value={formData.fatherName || ''} onChange={(v: any) => setFormData({ ...formData, fatherName: v })} type="text" prefix="" required />
        <div>
          <label style={{ display: 'block', marginBottom: 6, fontSize: 12, fontWeight: 500, color: 'var(--text-secondary)' }}>
            Gender *
          </label>
          <select
            value={formData.gender || 'M'}
            onChange={(e) => setFormData({ ...formData, gender: e.target.value })}
            style={{
              width: '100%',
              padding: '8px 12px',
              border: '1px solid var(--border)',
              borderRadius: 6,
              fontSize: 13
            }}
          >
            <option value="M">Male</option>
            <option value="F">Female</option>
            <option value="T">Transgender</option>
          </select>
        </div>
        <div>
          <label style={{ display: 'block', marginBottom: 6, fontSize: 12, fontWeight: 500, color: 'var(--text-secondary)' }}>
            Marital Status *
          </label>
          <select
            value={formData.maritalStatus || 'SINGLE'}
            onChange={(e) => setFormData({ ...formData, maritalStatus: e.target.value })}
            style={{
              width: '100%',
              padding: '8px 12px',
              border: '1px solid var(--border)',
              borderRadius: 6,
              fontSize: 13
            }}
          >
            <option value="SINGLE">Single</option>
            <option value="MARRIED">Married</option>
            <option value="DIVORCED">Divorced</option>
            <option value="WIDOWED">Widowed</option>
          </select>
        </div>
        <Field label="Nationality *" value={formData.nationality || 'INDIA'} onChange={(v: any) => setFormData({ ...formData, nationality: v })} type="text" prefix="" required />
        <div>
          <label style={{ display: 'block', marginBottom: 6, fontSize: 12, fontWeight: 500, color: 'var(--text-secondary)' }}>
            Director in Company?
          </label>
          <select
            value={formData.isDirector ? 'Y' : 'N'}
            onChange={(e) => setFormData({ ...formData, isDirector: e.target.value === 'Y' })}
            style={{
              width: '100%',
              padding: '8px 12px',
              border: '1px solid var(--border)',
              borderRadius: 6,
              fontSize: 13
            }}
          >
            <option value="N">No</option>
            <option value="Y">Yes (Triggers ITR-2)</option>
          </select>
        </div>
        <div>
          <label style={{ display: 'block', marginBottom: 6, fontSize: 12, fontWeight: 500, color: 'var(--text-secondary)' }}>
            Holds Unlisted Shares?
          </label>
          <select
            value={formData.holdsUnlistedShares ? 'Y' : 'N'}
            onChange={(e) => setFormData({ ...formData, holdsUnlistedShares: e.target.value === 'Y' })}
            style={{
              width: '100%',
              padding: '8px 12px',
              border: '1px solid var(--border)',
              borderRadius: 6,
              fontSize: 13
            }}
          >
            <option value="N">No</option>
            <option value="Y">Yes (Triggers ITR-2)</option>
          </select>
        </div>
        <Field label="Agricultural Income (>₹5,000 triggers ITR-2)" value={formData.agriculturalIncome || 0} onChange={(v: any) => setFormData({ ...formData, agriculturalIncome: v })} />
      </div>

      <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 16, color: 'var(--text-secondary)' }}>
        Contact Details
      </h3>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 24 }}>
        <div>
          <label style={{ display: 'block', marginBottom: 6, fontSize: 12, fontWeight: 500, color: 'var(--text-secondary)' }}>
            Country Code
          </label>
          <select
            value={formData.mobileCountryCode || '91'}
            onChange={(e) => setFormData({ ...formData, mobileCountryCode: e.target.value })}
            style={{
              width: '100%',
              padding: '8px 12px',
              border: '1px solid var(--border)',
              borderRadius: 6,
              fontSize: 13
            }}
          >
            {ITD_COUNTRY_CODES.map((option) => (
              <option key={option.value} value={option.value}>+{option.value} ({option.label})</option>
            ))}
          </select>
        </div>
        <Field label="Mobile Number" value={formData.mobile || ''} onChange={(v: any) => setFormData({ ...formData, mobile: v })} type="tel" prefix="" />
        <Field label="Email Address" value={formData.email || ''} onChange={(v: any) => setFormData({ ...formData, email: v })} type="email" prefix="" />
        <Field label="Telephone (STD-Number)" value={formData.telephone || ''} onChange={(v: any) => setFormData({ ...formData, telephone: v })} type="tel" prefix="" />
      </div>

      <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 16, color: 'var(--text-secondary)' }}>
        Address for Communication
      </h3>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 24 }}>
        <Field label="Flat/Door/Block No." value={formData.flatNo || ''} onChange={(v: any) => setFormData({ ...formData, flatNo: v })} type="text" prefix="" />
        <Field label="Name of Premises/Building/Village" value={formData.premises || ''} onChange={(v: any) => setFormData({ ...formData, premises: v })} type="text" prefix="" />
        <Field label="Road/Street/Post Office" value={formData.road || ''} onChange={(v: any) => setFormData({ ...formData, road: v })} type="text" prefix="" />
        <Field label="Area/Locality" value={formData.area || ''} onChange={(v: any) => setFormData({ ...formData, area: v })} type="text" prefix="" />
        <Field label="Town/City/District" value={formData.city || ''} onChange={(v: any) => setFormData({ ...formData, city: v })} type="text" prefix="" />
        <div>
          <label style={{ display: 'block', marginBottom: 6, fontSize: 12, fontWeight: 500, color: 'var(--text-secondary)' }}>
            State *
          </label>
          <select
            value={formData.state || ''}
            onChange={(e) => setFormData({ ...formData, state: e.target.value })}
            style={{
              width: '100%',
              padding: '8px 12px',
              border: '1px solid var(--border)',
              borderRadius: 6,
              fontSize: 13
            }}
          >
            <option value="">-- Select State --</option>
            <option value="01">01 - Andaman &amp; Nicobar Islands</option>
            <option value="02">02 - Andhra Pradesh</option>
            <option value="03">03 - Arunachal Pradesh</option>
            <option value="04">04 - Assam</option>
            <option value="05">05 - Bihar</option>
            <option value="06">06 - Chandigarh</option>
            <option value="07">07 - Dadra &amp; Nagar Haveli</option>
            <option value="08">08 - Daman &amp; Diu</option>
            <option value="09">09 - Delhi</option>
            <option value="10">10 - Goa</option>
            <option value="11">11 - Gujarat</option>
            <option value="12">12 - Haryana</option>
            <option value="13">13 - Himachal Pradesh</option>
            <option value="14">14 - Jammu &amp; Kashmir</option>
            <option value="15">15 - Karnataka</option>
            <option value="16">16 - Kerala</option>
            <option value="17">17 - Lakshadweep</option>
            <option value="18">18 - Madhya Pradesh</option>
            <option value="19">19 - Maharashtra</option>
            <option value="20">20 - Manipur</option>
            <option value="21">21 - Meghalaya</option>
            <option value="22">22 - Mizoram</option>
            <option value="23">23 - Nagaland</option>
            <option value="24">24 - Odisha</option>
            <option value="25">25 - Puducherry</option>
            <option value="26">26 - Punjab</option>
            <option value="27">27 - Rajasthan</option>
            <option value="28">28 - Sikkim</option>
            <option value="29">29 - Tamil Nadu</option>
            <option value="30">30 - Tripura</option>
            <option value="31">31 - Uttar Pradesh</option>
            <option value="32">32 - West Bengal</option>
            <option value="33">33 - Chhattisgarh</option>
            <option value="34">34 - Uttarakhand</option>
            <option value="35">35 - Jharkhand</option>
            <option value="36">36 - Telangana</option>
            <option value="37">37 - Ladakh</option>
          </select>
        </div>
        <div>
          <Field label="PIN Code" value={formData.pincode || ''} onChange={(v: any) => setFormData({ ...formData, pincode: v })} type="text" prefix="" />
          <div style={{ fontSize: 10, color: '#888', marginTop: 2 }}>6-digit (e.g., 110001)</div>
        </div>
        <div>
          <label style={{ display: 'block', marginBottom: 6, fontSize: 12, fontWeight: 500, color: 'var(--text-secondary)' }}>
            Country *
          </label>
          <select
            value={formData.country || '91'}
            onChange={(e) => setFormData({ ...formData, country: e.target.value })}
            style={{
              width: '100%',
              padding: '8px 12px',
              border: '1px solid var(--border)',
              borderRadius: 6,
              fontSize: 13
            }}
          >
            {ITD_COUNTRY_CODES.map((option) => (
              <option key={option.value} value={option.value}>{option.value} - {option.label}</option>
            ))}
          </select>
        </div>
      </div>

      <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 16, color: 'var(--text-secondary)' }}>
        Filing Details
      </h3>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
        <div>
          <label style={{ display: 'block', marginBottom: 6, fontSize: 12, fontWeight: 500, color: 'var(--text-secondary)' }}>
            Return Filed u/s
          </label>
          <select
            value={formData.filingSection || '139(1)'}
            onChange={(e) => setFormData({ ...formData, filingSection: e.target.value })}
            style={{
              width: '100%',
              padding: '8px 12px',
              border: '1px solid var(--border)',
              borderRadius: 6,
              fontSize: 13
            }}
          >
            <option value="139(1)">139(1) - On or before due date</option>
            <option value="139(4)">139(4) - Belated return</option>
            <option value="139(5)">139(5) - Revised return</option>
            <option value="119(2)(b)">119(2)(b) - After condonation of delay</option>
          </select>
        </div>
        <div>
          <label style={{ display: 'block', marginBottom: 6, fontSize: 12, fontWeight: 500, color: 'var(--text-secondary)' }}>
            Residential Status
          </label>
          <select
            value={formData.residentialStatus || 'ROR'}
            onChange={(e) => setFormData({ ...formData, residentialStatus: e.target.value })}
            style={{
              width: '100%',
              padding: '8px 12px',
              border: '1px solid var(--border)',
              borderRadius: 6,
              fontSize: 13
            }}
          >
            <option value="ROR">Resident</option>
            <option value="RNOR">Resident but Not Ordinarily Resident</option>
            <option value="NR">Non-Resident</option>
          </select>
        </div>
        <div>
          <label style={{ display: 'block', marginBottom: 6, fontSize: 12, fontWeight: 500, color: 'var(--text-secondary)' }}>
            Employer Category * (VR1-EC-001)
          </label>
          <select
            value={formData.employerCategory || 'OTH'}
            onChange={(e) => setFormData({ ...formData, employerCategory: e.target.value })}
            style={{
              width: '100%',
              padding: '8px 12px',
              border: '1px solid var(--border)',
              borderRadius: 6,
              fontSize: 13
            }}
          >
            <option value="CGOV">Central Government (CGOV)</option>
            <option value="SGOV">State Government (SGOV)</option>
            <option value="PSU">Public Sector Undertaking (PSU)</option>
            <option value="PE">Pensioner (PE)</option>
            <option value="PESG">Pensioner (State Government) (PESG)</option>
            <option value="PEPS">Pensioner (PSU) (PEPS)</option>
            <option value="PEO">Other Pensioner (PEO)</option>
            <option value="OTH">Others (OTH)</option>
            <option value="NA">Not Applicable (NA)</option>
          </select>
        </div>
        <div>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: 'var(--text-secondary)', cursor: 'pointer' }}>
            <input type='checkbox' checked={formData.bankUseForRefund !== false} onChange={(e) => setFormData({ ...formData, bankUseForRefund: e.target.checked })} style={{ width: 16, height: 16 }} />
            Use this account for refund
          </label>
        </div>
      </div>

      <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 16, color: 'var(--text-secondary)' }}>
        Bank Account Details for Refund
      </h3>
      <BankAccountManager
        data={formData.bankAccountData || { accounts: [] }}
        onChange={(d) => setFormData({ ...formData, bankAccountData: d })}
      />

      <div style={{ marginTop: 16, padding: 12, background: 'var(--info-bg)', borderRadius: 6, fontSize: 12, color: 'var(--info)' }}>
        Add every bank account used for refund and mark exactly one as the refund account.
      </div>
    </div>
  );
}