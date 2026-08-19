import { INR } from '../utils/formatters';
import ScheduleOSWorkspace from '../components/othersources/ScheduleOSWorkspace';
import DeductionsWorkspace from '../components/deductions/DeductionsWorkspace';
import type { ReturnDraft } from '../domain/returns/types';
import type { ItrForm } from '../domain/eligibility';
import { BankInterestEntryManager } from '../components/BankInterestEntryManager';
import { DividendEntryManager } from '../components/dividend/DividendEntryManager';
import { DonationEntryManager } from '../components/DonationEntryManager';
import { InterestEntryManager } from '../components/interest/InterestEntryManager';
import { WinningsManager } from '../components/winnings/WinningsManager';
import { FamilyPensionManager } from '../components/familyPension/FamilyPensionManager';
import { GiftPropertyManager } from '../components/gifts/GiftPropertyManager';
import { Section80DManager, type Section80DData } from '../components/Section80DManager';
import { DeductionLoanManager, type DeductionLoanData } from '../components/DeductionLoanManager';
import { Section80CManager, type Section80CData } from '../components/Section80CManager';
import type {
  BankManagerData, ChallanManagerEntry, DeductionLoanManagerData, FamilyPensionManagerEntry,
  GiftManagerEntry, InterestManagerEntry, TdsManagerEntry, WinningManagerEntry,
} from '../domain/returns';
import { classifyTdsSchedule, isTcsSection, DEDUCTED_YR_OPTIONS } from '../domain/returns/tdsSections';
import { tdsToManager, challansToManager, deductionLoansToManager } from '../domain/returns/editorModelV2';

export interface CanonicalManagerBindings {
  interest: (entries: InterestManagerEntry[]) => void;
  dividends: (entries: any[]) => void;
  familyPension: (entry: FamilyPensionManagerEntry) => void;
  winnings: (entries: WinningManagerEntry[]) => void;
  otherSources: (next: ReturnDraft['otherSources']) => void;
  gifts: (entries: GiftManagerEntry[]) => void;
  section80C: (data: Section80CData) => void;
  section80D: (data: Section80DData) => void;
  donations: (entries: any[]) => void;
  deductionLoans: (data: DeductionLoanManagerData) => void;
  chapterVIA: (next: import('../domain/returns/types').ChapterVIA) => void;
  tds: (entries: TdsManagerEntry[]) => void;
  tcs: (entries: import('../domain/returns/types').TcsCredit[]) => void;
  advanceTax: (entries: ChallanManagerEntry[]) => void;
  selfAssessmentTax: (entries: ChallanManagerEntry[]) => void;
  banks: (data: BankManagerData) => void;
  schedule80GGA: (entries: import('../domain/returns/types').Schedule80GGAEntry[]) => void;
  schedule80GGC: (entries: import('../domain/returns/types').Schedule80GGCEntry[]) => void;
  taxReturnPreparer: (next: import('../domain/returns/types').TaxReturnPreparer) => void;
}

export function BusinessTab({ taxResult, draft, onChangeBusinesses, onChangeBpNetProfit }: { taxResult: any; draft: ReturnDraft; onChangeBusinesses: (entries: ReturnDraft['businesses']) => void; onChangeBpNetProfit: (value: number) => void }) {
  return (
    <div>
      <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 16, color: 'var(--text-secondary)', display: 'flex', alignItems: 'center' }}>
        Income from Business or Profession
        <span style={{ position: 'relative', display: 'inline-flex', alignItems: 'center', marginLeft: 8 }}>
          <span style={{ cursor: 'pointer', fontSize: 12, color: 'var(--gold)', border: '1px solid var(--gold)', borderRadius: '50%', width: 16, height: 16, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontWeight: 600 }}>i</span>
          <span style={{ position: 'absolute', bottom: '100%', left: '50%', transform: 'translateX(-50%)', background: 'var(--text-primary)', color: 'white', padding: '8px 12px', borderRadius: 6, fontSize: 11, whiteSpace: 'nowrap', zIndex: 1000, display: 'none', marginBottom: 8, boxShadow: '0 2px 8px rgba(0,0,0,0.2)' }}>Sec 28-44 (Schedule BP)</span>
        </span>
      </h3>
      <div style={{ marginBottom: 16 }}>
        <label style={{ display: 'block', marginBottom: 8, fontSize: 12, fontWeight: 500 }}>Presumptive Scheme</label>
        <div style={{ display: 'flex', gap: 12 }}>
          {['44AD', '44ADA', 'Regular'].map(schemeOption => {
            const firstBusiness = draft.businesses?.[0];
            const schemeState = (firstBusiness?.scheme === '44AD' || firstBusiness?.scheme === '44ADA') ? firstBusiness.scheme : 'Regular';
            return (
              <button
                key={schemeOption}
                onClick={() => onChangeBusinesses(schemeOption === 'Regular' ? [] : [createBusinessStub(schemeOption as '44AD' | '44ADA', firstBusiness)])}
                style={{
                  padding: '8px 16px',
                  background: schemeState === schemeOption ? 'var(--gold)' : 'var(--bg)',
                  color: schemeState === schemeOption ? 'white' : 'var(--text-primary)',
                  border: '1px solid var(--border)',
                  borderRadius: 6,
                  fontSize: 13,
                  cursor: 'pointer'
                }}
              >
                {schemeOption}
              </button>
            );
          })}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 20 }}>
        <Field label="Gross Turnover/Receipts" value={aggregateGrossTurnover(draft.businesses)} computed />
        {(draft.businesses?.[0]?.scheme === '44AD' || draft.businesses?.[0]?.scheme === '44ADA') && (
          <Field label="Declared Income" value={aggregateDeclaredIncome(draft.businesses)} computed />
        )}
        {(!draft.businesses?.[0] || (draft.businesses[0]?.scheme !== '44AD' && draft.businesses[0]?.scheme !== '44ADA')) && (
          <Field label="Net Profit from P&L" value={draft.bpNetProfit ?? 0} onChange={(v: any) => onChangeBpNetProfit(Number(v) || 0)} />
        )}
        <Field label="Taxable Business Income" value={taxResult?.bizIncome} computed />
      </div>

      <h4 style={{ fontSize: 13, fontWeight: 600, marginBottom: 12, color: 'var(--text-secondary)' }}>
        Brought Forward Losses - Business/Profession
      </h4>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
        <Field label="Business Loss B/F" value={draft.lossesBroughtForward?.bfLossBusiness ?? 0} computed />
        <Field label="Speculation Loss B/F" value={draft.lossesBroughtForward?.bfLossSpeculation ?? 0} computed />
      </div>
    </div>
  );
}

function createBusinessStub(scheme: '44AD' | '44ADA', existing: ReturnDraft['businesses'][number] | undefined): ReturnDraft['businesses'][number] {
  if (existing && existing.scheme === scheme) return existing;
  return {
    id: `business-${scheme.toLowerCase()}-${Date.now()}`,
    businessName: '', natureCode: '', description: '',
    digitalReceipts: 0, nonDigitalReceipts: 0, declaredIncome: 0,
    gstinTurnovers: [], financialParticulars: { cashBalance: 0, bankBalance: 0, inventory: 0, sundryDebtors: 0, sundryCreditors: 0, otherAssets: 0, totalAssets: 0, securedLoans: 0, unsecuredLoans: 0, advances: 0, otherLiabilities: 0, totalLiabilities: 0, grossProfit: 0, expenses: 0, netProfit: 0 },
    scheme,
    ...(scheme === '44ADA' ? { grossReceipts: 0 } : {}),
  } as ReturnDraft['businesses'][number];
}

function aggregateGrossTurnover(businesses: ReturnDraft['businesses'] | undefined | null): number {
  return (businesses || []).reduce<number>((sum, entry) => {
    if (entry.scheme === '44ADA') return sum + (entry.grossReceipts || 0);
    if (entry.scheme === '44AD') return sum + (entry.digitalReceipts || 0) + (entry.nonDigitalReceipts || 0);
    if (entry.scheme === '44AE') return sum + (entry.vehicles || []).reduce<number>((vSum, vehicle) => vSum + (vehicle.presumptiveIncome || 0), 0);
    return sum;
  }, 0);
}

function aggregateDeclaredIncome(businesses: ReturnDraft['businesses'] | undefined | null): number {
  return (businesses || []).reduce<number>((sum, entry) => sum + (entry.declaredIncome || 0), 0);
}

export function OtherSourcesTab({ taxResult, managers, itrForm, regime, editorModel }: any) {
  // ── Unified canonical Schedule OS workspace ──────────────────────────────────
  // The complete seven-card editor reads/writes the canonical
  // ReturnDraft.otherSources superset directly via the typed managers.
  const os: ReturnDraft['otherSources'] = editorModel?.draft?.otherSources ?? {
    interest: [], dividends: [], familyPension: { grossAmount: 0, payerName: '', relationToPensioner: '' },
    winnings: [], gifts: [], otherIncome: [], dtaaIncome: [], dtaaAggregates: { totalAmountTaxUsDtaa: 0 },
    section89A: [], section89AAggregates: { incomeNotified89AOS: 0, incomeNotifiedOther89AOS: 0, incomeNotifiedPriorYear89AOS: 0, incomeReliefUs89AOS: 0 },
    accumulatedPf: [], accumulatedPfAggregates: { totalIncomeBenefit: 0, totalTaxBenefit: 0 }, specialRateIncome: [],
    unexplainedIncome: { cashCreditsUs68: 0, unexplainedInvestmentsUs69: 0, unexplainedMoneyUs69A: 0, undisclosedInvestmentsUs69B: 0, unexplainedExpenditureUs69C: 0, hundiBorrowingUs69D: 0, priorYearBusinessTrust562xii: 0, priorYearLifeInsurance562xiii: 0 },
    deductions: { expenses: 0, interestExpenseUs57: 0, interestExpenseEligibleUs57: 0, familyPensionDeductionUs57iia: 0, depreciation: 0, totalDeductions: 0, amountNotDeductibleUs58: 0, profitChargeableUs59: 0 },
  };
  const updateOS = (next: ReturnDraft['otherSources']): void => {
    managers?.otherSources?.(next);
  };
  return <ScheduleOSWorkspace form={(itrForm ?? 'ITR-1') as ItrForm} regime={(regime ?? 'new') === 'old' ? 'old' : 'new'} otherSources={os} onChange={updateOS} />;
}

export function VDATab({ draft, taxResult }: { draft: ReturnDraft; taxResult: any }) {
  // VDA rows are edited inside CapitalGainsEntryManager; this tab only surfaces
  // the aggregate as a read-only summary (computed either from the backend
  // tax result or derived from draft.capitalGainsSchedule.vda[]).
  const vdaRows = Array.isArray((draft.capitalGainsSchedule as { vda?: Array<{ consideration?: number; acquisitionCost?: number }> } | undefined)?.vda)
    ? (draft.capitalGainsSchedule as { vda: Array<{ consideration?: number; acquisitionCost?: number }> }).vda
    : [];
  const derivedVdaGain = vdaRows.reduce<number>((sum, row) => sum + ((Number(row.consideration) || 0) - (Number(row.acquisitionCost) || 0)), 0);
  const vdaGains = Number(taxResult?.vdaGains ?? derivedVdaGain);
  return (
    <div>
      <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 16, color: 'var(--text-secondary)' }}>
        Virtual Digital Assets (VDA) - Section 115BBH
      </h3>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
        <Field label="Net VDA Gains" value={vdaGains} computed />
        <Field label="VDA Tax @ 30%" value={taxResult?.vdaTax} computed />
      </div>
      <div style={{ marginTop: 12, padding: 12, background: 'var(--info-bg)', borderRadius: 6, fontSize: 12, color: 'var(--info)' }}>
        VDA rows are edited in the Capital Gains tab. No loss set-off allowed for VDA transactions as per CBDT rules.
      </div>
    </div>
  );
}

export function DeductionsTab({ regime, taxResult, managers, form, editorModel }: { regime: 'old' | 'new'; taxResult: any; managers: CanonicalManagerBindings; form: ItrForm; editorModel?: import('../domain/returns').ReturnEditorModelV2 | null }) {
  const draftDeductions = editorModel?.draft.deductions;
  const via = (draftDeductions?.chapterVIA ?? {}) as import('../domain/returns/types').ChapterVIA;
  const schedule80GGA = draftDeductions?.schedule80GGA ?? [];
  const schedule80GGC = draftDeductions?.schedule80GGC ?? [];
  return (
    <DeductionsWorkspace
      form={form}
      regime={regime}
      section80C={draftDeductions?.section80C ?? []}
      section80D={draftDeductions?.section80D ?? { selfSeniorCitizen: 'N', parentsSeniorCitizen: 'N', selfFamily: { policies: [], preventiveCheckup: 0, medicalExpense: 0 }, selfFamilySenior: { policies: [], preventiveCheckup: 0, medicalExpense: 0 }, parents: { policies: [], preventiveCheckup: 0, medicalExpense: 0 }, parentsSenior: { policies: [], preventiveCheckup: 0, medicalExpense: 0 } }}
      section80G={draftDeductions?.section80G ?? []}
      loans={deductionLoansToManager(draftDeductions?.loans ?? { loans: [], section80EEAStampDutyValue: 0 })}
      chapterVIA={via}
      onChangeChapterVIA={managers.chapterVIA}
      managers={managers}
      schedule80GGA={schedule80GGA}
      schedule80GGC={schedule80GGC}
      onChangeSchedule80GGA={managers.schedule80GGA}
      onChangeSchedule80GGC={managers.schedule80GGC}
      totalDeductions={taxResult?.totalDeductions}
      deductionBreakdown={taxResult?.deductionBreakdown}
    />
  );
}
export function LossesTab({ draft, taxResult, onChange }: { draft: ReturnDraft; taxResult: any; onChange: (patch: ReturnDraft['lossesBroughtForward']) => void }) {
  // HP loss disallowed (above the ₹2L set-off ceiling) is computed by the
  // backend engine (apply_inter_head_loss_limit). The frontend must not
  // recompute statutory loss set-off or carry-forward amounts.
  const hpLossDisallowed = taxResult?.hpLossDisallowed ?? 0;
  const currentYearHpLoss = (taxResult?.incomeFromHouseProperty ?? 0) < 0
    ? taxResult.incomeFromHouseProperty
    : 0;
  const losses = draft.lossesBroughtForward ?? { bfLossHP: 0, bfLossBusiness: 0, bfLossSTCG: 0, bfLossLTCG: 0, bfLossSpeculation: 0 };
  const pastYearHpLoss = losses.bfLossHP ?? 0;
  // Display-only total; the backend owns the set-off computation.
  const totalHpLossDisplay = Math.abs(currentYearHpLoss) + Math.abs(pastYearHpLoss);
  const patch = (key: keyof ReturnDraft['lossesBroughtForward'], value: number): void => {
    onChange({ ...losses, [key]: Math.max(0, Number(value) || 0) });
  };

  return (
    <div>
      <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 16, color: 'var(--text-secondary)' }}>
        Brought Forward Losses (CBDT Schedule CYLA)
      </h3>

      {/* Current Year HP Loss - Auto from backend */}
      <div style={{ marginBottom: 16, padding: 12, background: currentYearHpLoss < 0 ? 'var(--error-bg)' : 'var(--success-bg)', borderRadius: 6 }}>
        <div style={{ fontSize: 12, fontWeight: 600, color: currentYearHpLoss < 0 ? 'var(--error)' : 'var(--success)' }}>
          Current Year HP Loss (from backend): ₹{Math.abs(currentYearHpLoss).toLocaleString('en-IN')}
          {currentYearHpLoss === 0 && <span style={{ color: 'var(--success)' }}> - No loss from current year</span>}
        </div>
      </div>

      {/* Past Year Losses Brought Forward - Manual Entry */}
      <div style={{ marginBottom: 20, padding: 12, background: 'var(--bg)', borderRadius: 6, border: '1px solid var(--border)' }}>
        <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 8, color: 'var(--text-secondary)' }}>
          Losses Brought Forward from Previous Years
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 12 }}>
          <Field
            label="House Property Loss B/F from Prev Year (₹)"
            value={pastYearHpLoss}
            onChange={(v: any) => patch('bfLossHP', Number(v) || 0)}
          />
        </div>
        <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 6 }}>
          Enter HP losses from previous year that couldn't be fully set off. Maximum 8 years can be carried forward.
        </div>
      </div>

      {/* HP Loss Set-off from backend */}
      {totalHpLossDisplay > 0 && (
        <div style={{ marginBottom: 16, padding: 12, background: 'var(--gold-pale)', borderRadius: 6, border: '1px solid var(--gold)' }}>
          <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 8, color: 'var(--text-secondary)' }}>
            HP Loss Set-off (backend-computed)
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
            <div>Total HP Loss (display): ₹{totalHpLossDisplay.toLocaleString('en-IN')}</div>
            <div>HP Loss Disallowed by backend (above ₹2L ceiling): ₹{hpLossDisallowed.toLocaleString('en-IN')}</div>
            {hpLossDisallowed > 0 && (
              <div style={{ color: 'var(--error)', fontWeight: 600 }}>
                Disallowed loss may be carried forward to future years (up to 8 assessment years).
              </div>
            )}
          </div>
        </div>
      )}

      {/* Other Losses - Manual Entry */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 24 }}>
        <Field label="Business Loss B/F" value={losses.bfLossBusiness ?? 0} onChange={(v: any) => patch('bfLossBusiness', Number(v) || 0)} />
        <Field label="Speculation Loss B/F" value={losses.bfLossSpeculation ?? 0} onChange={(v: any) => patch('bfLossSpeculation', Number(v) || 0)} />
        <Field label="Short Term Capital Loss B/F" value={losses.bfLossSTCG ?? 0} onChange={(v: any) => patch('bfLossSTCG', Number(v) || 0)} />
        <Field label="Long Term Capital Loss B/F" value={losses.bfLossLTCG ?? 0} onChange={(v: any) => patch('bfLossLTCG', Number(v) || 0)} />
      </div>
      <div style={{ marginTop: 12, padding: 12, background: 'var(--info-bg)', borderRadius: 6, fontSize: 12, color: 'var(--info)' }}>
        <strong>CBDT Loss Set-off Rules:</strong>
        <ul style={{ marginTop: 8, paddingLeft: 20 }}>
          <li>House Property loss: Maximum ₹2,00,000 can be set off against other heads</li>
          <li>Business loss: Can be set off against any head except salary</li>
          <li>Speculation loss: Can only be set off against speculation income</li>
          <li>STCG loss: Can be set off against STCG or LTCG</li>
          <li>LTCG loss: Can only be set off against LTCG</li>
        </ul>
      </div>
    </div>
  );
}

export function TDSTab({ taxResult, managers, editorModel }: { taxResult: any; managers: CanonicalManagerBindings; editorModel?: import('../domain/returns').ReturnEditorModelV2 | null }) {
  // Source TDS + challan entries from the canonical draft via the typed
  // projection helpers.  The legacy `formData.tdsEntries` snapshot is no
  // longer authoritative; the draft (`draft.taxes.tds`, `draft.taxes.challans`)
  // is the single source of truth, written through the typed managers.
  const draftTds = editorModel?.draft?.taxes?.tds ?? [];
  const draftChallans = editorModel?.draft?.taxes?.challans ?? [];
  const tdsEntries = tdsToManager(draftTds);
  const selfAssessmentTaxEntries = challansToManager(draftChallans, 'SELF_ASSESSMENT');
  const advanceTaxEntries = challansToManager(draftChallans, 'ADVANCE_TAX');
  // TAN is jurisdiction-prefixed per the official schema (e.g. DELA12345B).
  const tanPattern = /^(HYD|VPN|BBN|BPL|JBP|CHE|CMB|MRI|DEL|CAL|MRT|AHM|BRD|RKT|SRT|BLR|AGR|KNP|CHN|TVD|ALD|LKN|MUM|NGP|AMR|JLD|PTL|RTK|KLP|NSK|PNE|PTN|RCH|JDH|JPR|SHL)[A-Z][0-9]{5}[A-Z]$/;
  // BSR Code: first 3 digits, then 4 alphanumeric (per TaxPayment.BSRCode pattern).
  const bsrPattern = /^[0-9]{3}[0-9A-Z]{4}$/;
  // Challan serial is an integer 1..99999 per the schema.
  const challanPattern = /^[0-9]{1,5}$/;
  const inputErrorStyle = { color: 'var(--danger)', fontSize: 11, marginTop: 4 };
  const deriveCin = (entry: any) => {
    const bsr = String(entry.bsrCode || '');
    const date = String(entry.depositDate || '').replaceAll('-', '');
    const serial = String(entry.challanNo ?? entry.challanSerialNo ?? '');
    return bsrPattern.test(bsr) && date.length === 8 && challanPattern.test(serial) && Number(serial) > 0
      ? `${bsr}-${date}-${serial.padStart(5, '0')}`
      : '';
  };

  // The TDS tab collects every section for every form; ITR-form eligibility
  // (which sections a given form may claim) is the backend's responsibility.
  const addTDSEntry = () => {
    const newEntry = {
      id: `tds-${crypto.randomUUID()}`,
      section: '192',
      deductorName: '',
      deductorTAN: '',
      deductorPAN: '',
      incomeAmount: 0,
      tdsDeducted: 0,
      certificateNo: '',
      deductionDate: '',
      uniqueTransactionNo: '',
      financialYear: '2025-26',
      verified26AS: false,
      claimedInReturn: true
    };
    managers.tds([...tdsEntries, newEntry]);
  };

  const updateTDSEntry = (index: number, field: string, value: any) => {
    const updated = [...tdsEntries];
    updated[index] = { ...updated[index], [field]: value };
    managers.tds(updated);
  };

  const removeTDSEntry = (index: number) => {
    const updated = tdsEntries.filter((_: any, i: number) => i !== index);
    managers.tds(updated);
  };

  const addSelfAssessmentEntry = () => {
    const newEntry = {
      id: `self-assessment-${crypto.randomUUID()}`,
      bsrCode: '',
      challanNo: '',
      depositDate: '',
      amount: 0,
      cin: ''
    };
    managers.selfAssessmentTax([...selfAssessmentTaxEntries, newEntry]);
  };

  const updateSelfAssessmentEntry = (index: number, field: string, value: any) => {
    const updated = [...selfAssessmentTaxEntries];
    updated[index] = { ...updated[index], [field]: value };
    managers.selfAssessmentTax(updated);
  };

  const removeSelfAssessmentEntry = (index: number) => {
    const updated = selfAssessmentTaxEntries.filter((_: any, i: number) => i !== index);
    managers.selfAssessmentTax(updated);
  };

  // Per-schedule aggregate totals (TotalTDSonSalaries, TotalTDSonOthThanSals,
  // TotalTDS3Details, TotalSchTCS) computed from the current entries, so the
  // user can reconcile against the official schedule totals.
  const tdsBreakdown = tdsEntries.reduce((acc: { tds1: number; tds2: number; tds3: number; tcs: number; }, entry: any) => {
    const section = entry.section || '192';
    const amount = Number(entry.tdsDeducted ?? entry.taxDeducted ?? 0) || 0;
    const claimed = entry.claimedInReturn !== false;
    if (!claimed) return acc;
    if (isTcsSection(section)) { acc.tcs += amount; return acc; }
    const sched = classifyTdsSchedule(section);
    if (sched === 'TDS1') acc.tds1 += amount;
    else if (sched === 'TDS2') acc.tds2 += amount;
    else if (sched === 'TDS3') acc.tds3 += amount;
    return acc;
  }, { tds1: 0, tds2: 0, tds3: 0, tcs: 0 });
  const advanceTotal = advanceTaxEntries.reduce((sum: number, e: any) => sum + (Number(e.amount) || 0), 0);
  const satTotal = selfAssessmentTaxEntries.reduce((sum: number, e: any) => sum + (Number(e.amount) || 0), 0);

  return (
    <div>
      {/* TDS entries are sourced from the canonical draft; the 26AS/AIS
          import snapshot banner was removed with the flat-blob bridge. */}

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-secondary)' }}>
          TDS Entries (CBDT Compliant)
        </h3>
        <button
          onClick={addTDSEntry}
          style={{
            padding: '6px 12px',
            background: 'var(--gold)',
            color: 'white',
            border: 'none',
            borderRadius: 6,
            fontSize: 12,
            cursor: 'pointer'
          }}
        >
          + Add TDS Entry
        </button>
      </div>

      {tdsEntries.length === 0 && (
        <div style={{ padding: 24, textAlign: 'center', color: 'var(--text-muted)', background: 'var(--bg)', borderRadius: 6, marginBottom: 24 }}>
          No TDS entries. Click "Add TDS Entry" to add deductions.
        </div>
      )}

      {tdsEntries.map((entry: any, index: number) => (
        <div key={index} style={{ marginBottom: 24, padding: 16, background: 'var(--bg)', borderRadius: 6, border: '1px solid var(--border)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <h4 style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)' }}>
              TDS Entry #{index + 1}
            </h4>
            <button
              onClick={() => removeTDSEntry(index)}
              style={{
                padding: '4px 8px',
                background: 'var(--danger)',
                color: 'white',
                border: 'none',
                borderRadius: 4,
                fontSize: 11,
                cursor: 'pointer'
              }}
            >
              Remove
            </button>
          </div>
          
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
            <div>
              <label style={{ display: 'block', marginBottom: 6, fontSize: 12, fontWeight: 500, color: 'var(--text-secondary)' }}>
                Section *
              </label>
              <select
                value={entry.section || '192'}
                onChange={(e) => updateTDSEntry(index, 'section', e.target.value)}
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  border: '1px solid var(--border)',
                  borderRadius: 6,
                  fontSize: 13
                }}
              >
                <optgroup label="Salary">
                  <option value="192">192 - Salary</option>
                  <option value="192A">192A - PF Withdrawal</option>
                </optgroup>
                <optgroup label="Interest / Securities">
                  <option value="193">193 - Interest on Securities</option>
                  <option value="194A">194A - Interest (other than securities)</option>
                  <option value="194LB">194LB - Infrastructure Debt Fund Interest</option>
                  <option value="194LD">194LD - Bonds/Government Securities</option>
                </optgroup>
                <optgroup label="Dividends">
                  <option value="194">194 - Dividends</option>
                  <option value="194K">194K - Mutual Fund Income</option>
                </optgroup>
                <optgroup label="Winnings / Games">
                  <option value="194B">194B - Lottery / Crossword</option>
                  <option value="194BA">194BA - Online Games</option>
                  <option value="194BB">194BB - Horse Race</option>
                </optgroup>
                <optgroup label="Contractor / Professional">
                  <option value="194C">194C - Contractor Payments</option>
                  <option value="194J">194J - Professional / Technical Fees</option>
                </optgroup>
                <optgroup label="Commission / Insurance">
                  <option value="194H">194H - Commission / Brokerage</option>
                  <option value="194D">194D - Insurance Commission</option>
                  <option value="194DA">194DA - Life Insurance Payment</option>
                </optgroup>
                <optgroup label="Rent / Property">
                  <option value="194I">194I - Rent (General)</option>
                  <option value="194IA">194IA - Sale of Immovable Property</option>
                  <option value="194IB">194IB - Rent by Individuals/HUF</option>
                  <option value="194IC">194IC - Specified Agreement</option>
                  <option value="194LA">194LA - Compensation on Acquisition</option>
                </optgroup>
                <optgroup label="Non-Resident">
                  <option value="194E">194E - Non-Resident Sportsmen</option>
                  <option value="195">195 - Sums Payable to Non-Resident</option>
                  <option value="196A">196A - Units of Non-Residents</option>
                  <option value="196B">196B - Offshore Fund Units</option>
                  <option value="196C">196C - Foreign Currency Bonds</option>
                  <option value="196D">196D - Foreign Institutional Investors</option>
                  <option value="196DA">196DA - Specified Fund Income</option>
                </optgroup>
                <optgroup label="Other TDS">
                  <option value="194EE">194EE - NSS Deposits</option>
                  <option value="194F">194F - Mutual Fund Repurchase</option>
                  <option value="194G">194G - Lottery Ticket Commission</option>
                  <option value="194LBA">194LBA - Business Trust Income</option>
                  <option value="194LBB">194LBB - Investment Fund Income</option>
                  <option value="194LBC">194LBC - Securitization Trust</option>
                  <option value="194LC">194LC - Interest (Infrastructure)</option>
                  <option value="194M">194M - Certain Sums by Individuals/HUF</option>
                  <option value="194N">194N - Cash Payment (Specified)</option>
                  <option value="194O">194O - E-Commerce Participant</option>
                  <option value="194P">194P - Specified Senior Citizen</option>
                  <option value="194Q">194Q - Purchase of Goods</option>
                  <option value="194R">194R - Benefits / Perquisites</option>
                  <option value="194S">194S - Virtual Digital Asset</option>
                </optgroup>
                <optgroup label="TCS">
                  <option value="206C">206C - TCS (General)</option>
                  <option value="206CA">206CA - Alcoholic Liquor</option>
                  <option value="206CB">206CB - Timber (Forest Lease)</option>
                  <option value="206CC">206CC - Timber (Other)</option>
                  <option value="206CD">206CD - Other Forest Produce</option>
                  <option value="206CE">206CE - Scrap</option>
                  <option value="206CF">206CF - Parking Lot</option>
                  <option value="206CG">206CG - Toll Plaza</option>
                  <option value="206CH">206CH - Mine / Quarry</option>
                  <option value="206CI">206CI - Tendu Leaves</option>
                  <option value="206CJ">206CJ - Minerals</option>
                  <option value="206CK">206CK - Bullion / Jewellery (Cash)</option>
                  <option value="206CL">206CL - Motor Vehicle</option>
                  <option value="206CM">206CM - Goods (Cash Sale)</option>
                  <option value="206CN">206CN - Services (Other)</option>
                  <option value="206CO">206CO - Overseas Tour Package</option>
                  <option value="206CP">206CP - LRS Education Loan</option>
                  <option value="206CQ">206CQ - LRS Other Purposes</option>
                  <option value="206CR">206CR - Sale of Goods</option>
                  <option value="206CT">206CT - LRS Education/Medical</option>
                </optgroup>
                <option value="OTHER">Other</option>
              </select>
            </div>
            <Field label="Deductor Name *" value={entry.deductorName || ''} onChange={(v: any) => updateTDSEntry(index, 'deductorName', v)} type="text" prefix="" required />
            <div>
              <label style={{ display: 'block', marginBottom: 6, fontSize: 12, fontWeight: 500, color: 'var(--text-secondary)' }}>
                Deductor TAN *
              </label>
              <input
                type="text"
                value={entry.deductorTAN || ''}
                onChange={(e) => updateTDSEntry(index, 'deductorTAN', e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 10))}
                placeholder="DELA12345B"
                maxLength={10}
                aria-invalid={Boolean(entry.deductorTAN) && !tanPattern.test(entry.deductorTAN)}
                style={{ width: '100%', padding: '8px 12px', border: `1px solid ${entry.deductorTAN && !tanPattern.test(entry.deductorTAN) ? 'var(--danger)' : 'var(--border)'}`, borderRadius: 6, fontSize: 13 }}
              />
              {entry.deductorTAN && !tanPattern.test(entry.deductorTAN) && (
                <div style={inputErrorStyle}>TAN must be a 10-char jurisdiction code (e.g. DELA12345B).</div>
              )}
            </div>
            <Field label="Deductor PAN" value={entry.deductorPAN || ''} onChange={(v: any) => updateTDSEntry(index, 'deductorPAN', v)} type="text" prefix="" />
            <Field label="Income Amount *" value={entry.incomeAmount || 0} onChange={(v: any) => updateTDSEntry(index, 'incomeAmount', v)} required />
            <Field label="TDS Deducted *" value={entry.tdsDeducted || 0} onChange={(v: any) => updateTDSEntry(index, 'tdsDeducted', v)} required />
            <Field label="Certificate No" value={entry.certificateNo || ''} onChange={(v: any) => updateTDSEntry(index, 'certificateNo', v)} type="text" prefix="" />
            <Field label="Deduction Date" value={entry.deductionDate || ''} onChange={(v: any) => updateTDSEntry(index, 'deductionDate', v)} type="date" prefix="" />
            <Field label="Unique Transaction No" value={entry.uniqueTransactionNo || ''} onChange={(v: any) => updateTDSEntry(index, 'uniqueTransactionNo', v)} type="text" prefix="" />
            <Field label="Financial Year *" value={entry.financialYear || '2025-26'} onChange={(v: any) => updateTDSEntry(index, 'financialYear', v)} type="text" prefix="" required />
            <div>
              <label style={{ display: 'block', marginBottom: 6, fontSize: 12, fontWeight: 500, color: 'var(--text-secondary)' }}>Deducted Year (FY tax deducted)</label>
              <select value={entry.deductedYr ?? ''} onChange={(e) => updateTDSEntry(index, 'deductedYr', e.target.value === '' ? '' : Number(e.target.value))} style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6, fontSize: 13, background: 'white' }}>
                <option value="">-- Select FY --</option>
                {DEDUCTED_YR_OPTIONS.map((y) => <option key={y} value={y}>{y}-{(y + 1) % 100}</option>)}
              </select>
            </div>
            {(() => {
              const sched = classifyTdsSchedule(entry.section || '192');
              const isTcs = isTcsSection(entry.section || '');
              const inputStyle = { width: '100%', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6, fontSize: 13 };
              const labelStyle = { display: 'block', marginBottom: 6, fontSize: 12, fontWeight: 500, color: 'var(--text-secondary)' };
              if (isTcs) return (
                <div style={{ gridColumn: '1 / -1', marginTop: 8, padding: 12, background: 'var(--gold-pale)', borderRadius: 6, border: '1px dashed var(--gold)' }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--gold)', marginBottom: 8 }}>Schedule TCS detail</div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
                    <div><label style={labelStyle}>TCS Credit Owner</label><select style={inputStyle} value={entry.tcsCreditOwner || '1'} onChange={(e) => updateTDSEntry(index, 'tcsCreditOwner', e.target.value as '1' | '2')}><option value="1">1 — Self</option><option value="2">2 — Spouse / Other Person</option></select></div>
                    <div><label style={labelStyle}>PAN of Spouse / Other</label><input style={inputStyle} type="text" maxLength={10} value={entry.panOfSpouseOrOthrPrsn || ''} onChange={(e) => updateTDSEntry(index, 'panOfSpouseOrOthrPrsn', e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 10))} placeholder="ABCDE1234F" /></div>
                    <div><label style={labelStyle}>TCS Collected (own)</label><input style={inputStyle} type="number" min={0} value={entry.tcsAmtCollOwnHand || ''} onChange={(e) => updateTDSEntry(index, 'tcsAmtCollOwnHand', parseFloat(e.target.value) || 0)} placeholder="0" /></div>
                    <div><label style={labelStyle}>TCS Collected (spouse/other)</label><input style={inputStyle} type="number" min={0} value={entry.tcsAmtCollSpouseOrOthrHand || ''} onChange={(e) => updateTDSEntry(index, 'tcsAmtCollSpouseOrOthrHand', parseFloat(e.target.value) || 0)} placeholder="0" /></div>
                    <div><label style={labelStyle}>TCS Claimed (own)</label><input style={inputStyle} type="number" min={0} value={entry.tcsClaimedAmtCollOwnHand || ''} onChange={(e) => updateTDSEntry(index, 'tcsClaimedAmtCollOwnHand', parseFloat(e.target.value) || 0)} placeholder="0" /></div>
                    <div><label style={labelStyle}>TCS Claimed (spouse/other)</label><input style={inputStyle} type="number" min={0} value={entry.tcsClaimedAmtCollSpouseOrOthrHand || ''} onChange={(e) => updateTDSEntry(index, 'tcsClaimedAmtCollSpouseOrOthrHand', parseFloat(e.target.value) || 0)} placeholder="0" /></div>
                  </div>
                </div>
              );
              if (sched === 'TDS3') return (
                <div style={{ gridColumn: '1 / -1', marginTop: 8, padding: 12, background: 'var(--info-bg)', borderRadius: 6, border: '1px dashed var(--info)' }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--info)', marginBottom: 8 }}>Schedule TDS-3 — tenant / buyer detail</div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
                    <div><label style={labelStyle}>Name of Tenant / Buyer *</label><input style={inputStyle} type="text" maxLength={125} value={entry.nameOfTenant || ''} onChange={(e) => updateTDSEntry(index, 'nameOfTenant', e.target.value)} placeholder="Tenant / buyer name" /></div>
                    <div><label style={labelStyle}>PAN of Tenant / Buyer</label><input style={inputStyle} type="text" maxLength={10} value={entry.panOfTenant || ''} onChange={(e) => updateTDSEntry(index, 'panOfTenant', e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 10))} placeholder="ABCDE1234F" /></div>
                    <div><label style={labelStyle}>Aadhaar of Tenant / Buyer</label><input style={inputStyle} type="text" maxLength={12} inputMode="numeric" value={entry.aadhaarOfTenant || ''} onChange={(e) => updateTDSEntry(index, 'aadhaarOfTenant', e.target.value.replace(/\D/g, '').slice(0, 12))} placeholder="12-digit Aadhaar" /></div>
                    <div><label style={labelStyle}>Gross Receipt to Tax Deduct (₹)</label><input style={inputStyle} type="number" min={0} value={entry.grsRcptToTaxDeduct || ''} onChange={(e) => updateTDSEntry(index, 'grsRcptToTaxDeduct', parseFloat(e.target.value) || 0)} placeholder="0" /></div>
                    <div><label style={labelStyle}>TDS Claimed (₹)</label><input style={inputStyle} type="number" min={0} value={entry.tdsClaimed || ''} onChange={(e) => updateTDSEntry(index, 'tdsClaimed', parseFloat(e.target.value) || 0)} placeholder="0" /></div>
                    <div><label style={labelStyle}>Head of Income</label><select style={inputStyle} value={entry.headOfIncome || 'NA'} onChange={(e) => updateTDSEntry(index, 'headOfIncome', e.target.value as 'HP' | 'CG' | 'OS' | 'BP' | 'EI' | 'NA')}><option value="NA">NA — Not Applicable</option><option value="HP">HP — House Property</option><option value="CG">CG — Capital Gains</option><option value="OS">OS — Other Sources</option><option value="BP">BP — Business/Profession</option><option value="EI">EI — Exempt Income</option></select></div>
                  </div>
                </div>
              );
              if (sched === 'TDS2') return (
                <div style={{ gridColumn: '1 / -1', marginTop: 8, padding: 12, background: 'var(--bg)', borderRadius: 6, border: '1px dashed var(--border)' }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8 }}>Schedule TDS-2 — non-salary TDS detail</div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
                    <div><label style={labelStyle}>TDS Credit Owner</label><select style={inputStyle} value={entry.tdsCreditName || 'S'} onChange={(e) => updateTDSEntry(index, 'tdsCreditName', e.target.value as 'S' | 'O')}><option value="S">S — Self</option><option value="O">O — Other Person</option></select></div>
                    <div><label style={labelStyle}>PAN of Other Person</label><input style={inputStyle} type="text" maxLength={10} value={entry.panOfOtherPerson || ''} onChange={(e) => updateTDSEntry(index, 'panOfOtherPerson', e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 10))} placeholder="ABCDE1234F" /></div>
                    <div><label style={labelStyle}>Aadhaar of Other Person</label><input style={inputStyle} type="text" maxLength={12} inputMode="numeric" value={entry.aadhaarOfOtherPerson || ''} onChange={(e) => updateTDSEntry(index, 'aadhaarOfOtherPerson', e.target.value.replace(/\D/g, '').slice(0, 12))} placeholder="12-digit Aadhaar" /></div>
                    <div><label style={labelStyle}>Head of Income</label><select style={inputStyle} value={entry.headOfIncome || 'NA'} onChange={(e) => updateTDSEntry(index, 'headOfIncome', e.target.value as 'HP' | 'CG' | 'OS' | 'BP' | 'EI' | 'NA')}><option value="NA">NA — Not Applicable</option><option value="HP">HP — House Property</option><option value="CG">CG — Capital Gains</option><option value="OS">OS — Other Sources</option><option value="BP">BP — Business/Profession</option><option value="EI">EI — Exempt Income</option></select></div>
                    <div><label style={labelStyle}>Brought-fwd TDS Amt (₹)</label><input style={inputStyle} type="number" min={0} value={entry.broughtFwdTDSAmt || ''} onChange={(e) => updateTDSEntry(index, 'broughtFwdTDSAmt', parseFloat(e.target.value) || 0)} placeholder="0" /></div>
                    <div><label style={labelStyle}>Carried-fwd TDS Amt (₹)</label><input style={inputStyle} type="number" min={0} value={entry.amtCarriedFwd || ''} onChange={(e) => updateTDSEntry(index, 'amtCarriedFwd', parseFloat(e.target.value) || 0)} placeholder="0" /></div>
                    <div><label style={labelStyle}>Claim out of Total TDS (₹)</label><input style={inputStyle} type="number" min={0} value={entry.claimOutOfTotTDSOnAmtPaid || ''} onChange={(e) => updateTDSEntry(index, 'claimOutOfTotTDSOnAmtPaid', parseFloat(e.target.value) || 0)} placeholder="0" /></div>
                  </div>
                </div>
              );
              return null;
            })()}
            <div>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, marginTop: 24 }}>
                <input
                  type="checkbox"
                  checked={entry.verified26AS || false}
                  onChange={(e) => updateTDSEntry(index, 'verified26AS', e.target.checked)}
                />
                Verified in 26AS
              </label>
            </div>
            <div>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, marginTop: 24 }}>
                <input
                  type="checkbox"
                  checked={entry.claimedInReturn !== false}
                  onChange={(e) => updateTDSEntry(index, 'claimedInReturn', e.target.checked)}
                />
                Claim in Return
              </label>
            </div>
          </div>
        </div>
      ))}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 32, marginBottom: 16 }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-secondary)' }}>
          Advance Tax Payments (CBDT Compliant — Per-Challan)
        </h3>
        <button
          onClick={() => {
            const entries = advanceTaxEntries;
            managers.advanceTax([...entries, { id: '', bsrCode: '', depositDate: '', challanSerialNo: 0, amount: 0 }]);
          }}
          style={{
            padding: '6px 12px',
            background: 'var(--gold)',
            color: 'white',
            border: 'none',
            borderRadius: 6,
            fontSize: 12,
            cursor: 'pointer'
          }}
        >
          + Add Advance Tax
        </button>
      </div>
      {(advanceTaxEntries).length === 0 && (
        <div style={{ padding: 24, textAlign: 'center', color: 'var(--text-muted)', background: 'var(--bg)', borderRadius: 6, marginBottom: 24 }}>
          No advance tax entries. Click "+ Add Advance Tax" to add per-challan payments with BSR code, date, and challan serial number.
        </div>
      )}
      {(advanceTaxEntries).map((entry: any, index: number) => (
        <div key={index} style={{ marginBottom: 16, padding: 16, background: 'var(--bg)', borderRadius: 6, border: '1px solid var(--border)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <h4 style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)' }}>
              Advance Tax #{index + 1}
            </h4>
            <button
              onClick={() => {
                const updated = [...(advanceTaxEntries)];
                updated.splice(index, 1);
                managers.advanceTax(updated);
              }}
              style={{ background: 'var(--danger)', color: 'white', border: 'none', width: 24, height: 24, borderRadius: '50%', cursor: 'pointer', fontSize: 14 }}
            >×</button>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12 }}>
            <div>
              <label style={{ display: 'block', marginBottom: 4, fontSize: 11, fontWeight: 600 }}>BSR Code *</label>
              <input type="text" inputMode="text" value={entry.bsrCode || ''} onChange={(e) => {
                const updated = [...(advanceTaxEntries)];
                updated[index] = { ...updated[index], bsrCode: e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 7) };
                managers.advanceTax(updated);
              }} placeholder="3 digits + 4 alphanumeric" maxLength={7} aria-invalid={Boolean(entry.bsrCode) && !bsrPattern.test(entry.bsrCode)} style={{ width: '100%', padding: '6px 8px', border: `1px solid ${entry.bsrCode && !bsrPattern.test(entry.bsrCode) ? 'var(--danger)' : 'var(--border)'}`, borderRadius: 4, fontSize: 12 }} />
              {entry.bsrCode && !bsrPattern.test(entry.bsrCode) && <div style={inputErrorStyle}>BSR must be 7 chars: 3 digits then 4 alphanumeric.</div>}
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: 4, fontSize: 11, fontWeight: 600 }}>Deposit Date *</label>
              <input type="date" value={entry.depositDate || ''} onChange={(e) => {
                const updated = [...(advanceTaxEntries)];
                updated[index] = { ...updated[index], depositDate: e.target.value };
                managers.advanceTax(updated);
              }} style={{ width: '100%', padding: '6px 8px', border: '1px solid var(--border)', borderRadius: 4, fontSize: 12 }} />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: 4, fontSize: 11, fontWeight: 600 }}>Challan Serial No. *</label>
              <input type="text" inputMode="numeric" value={entry.challanSerialNo || ''} onChange={(e) => {
                const updated = [...(advanceTaxEntries)];
                updated[index] = { ...updated[index], challanSerialNo: e.target.value.replace(/\D/g, '').slice(0, 5) };
                managers.advanceTax(updated);
              }} placeholder="1-5 digits" maxLength={5} aria-invalid={Boolean(entry.challanSerialNo) && (!challanPattern.test(String(entry.challanSerialNo)) || Number(entry.challanSerialNo) <= 0)} style={{ width: '100%', padding: '6px 8px', border: `1px solid ${entry.challanSerialNo && (!challanPattern.test(String(entry.challanSerialNo)) || Number(entry.challanSerialNo) <= 0) ? 'var(--danger)' : 'var(--border)'}`, borderRadius: 4, fontSize: 12 }} />
              {entry.challanSerialNo && (!challanPattern.test(String(entry.challanSerialNo)) || Number(entry.challanSerialNo) <= 0) && <div style={inputErrorStyle}>Enter 1-5 digits greater than zero.</div>}
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: 4, fontSize: 11, fontWeight: 600 }}>Amount (₹) *</label>
              <input type="number" value={entry.amount || ''} onChange={(e) => {
                const updated = [...(advanceTaxEntries)];
                updated[index] = { ...updated[index], amount: parseFloat(e.target.value) || 0 };
                managers.advanceTax(updated);
              }} placeholder="0" min={0} style={{ width: '100%', padding: '6px 8px', border: '1px solid var(--border)', borderRadius: 4, fontSize: 12, fontWeight: 600 }} />
            </div>
          </div>
        </div>
      ))}

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-secondary)' }}>
          Self Assessment Tax (CBDT Compliant)
        </h3>
        <button
          onClick={addSelfAssessmentEntry}
          style={{
            padding: '6px 12px',
            background: 'var(--gold)',
            color: 'white',
            border: 'none',
            borderRadius: 6,
            fontSize: 12,
            cursor: 'pointer'
          }}
        >
          + Add SAT Entry
        </button>
      </div>

      {selfAssessmentTaxEntries.length === 0 && (
        <div style={{ padding: 24, textAlign: 'center', color: 'var(--text-muted)', background: 'var(--bg)', borderRadius: 6, marginBottom: 24 }}>
          No self assessment tax entries. Click "Add SAT Entry" to add payments.
        </div>
      )}

      {selfAssessmentTaxEntries.map((entry: any, index: number) => (
        <div key={index} style={{ marginBottom: 16, padding: 16, background: 'var(--bg)', borderRadius: 6, border: '1px solid var(--border)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <h4 style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)' }}>
              SAT Entry #{index + 1}
            </h4>
            <button
              onClick={() => removeSelfAssessmentEntry(index)}
              style={{
                padding: '4px 8px',
                background: 'var(--danger)',
                color: 'white',
                border: 'none',
                borderRadius: 4,
                fontSize: 11,
                cursor: 'pointer'
              }}
            >
              Remove
            </button>
          </div>
          
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
            <div>
              <label style={{ display: 'block', marginBottom: 6, fontSize: 12, fontWeight: 500, color: 'var(--text-secondary)' }}>BSR Code *</label>
              <input type="text" inputMode="text" value={entry.bsrCode || ''} onChange={(e) => updateSelfAssessmentEntry(index, 'bsrCode', e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 7))} placeholder="3 digits + 4 alphanumeric" maxLength={7} aria-invalid={Boolean(entry.bsrCode) && !bsrPattern.test(entry.bsrCode)} style={{ width: '100%', padding: '8px 12px', border: `1px solid ${entry.bsrCode && !bsrPattern.test(entry.bsrCode) ? 'var(--danger)' : 'var(--border)'}`, borderRadius: 6, fontSize: 13 }} />
              {entry.bsrCode && !bsrPattern.test(entry.bsrCode) && <div style={inputErrorStyle}>BSR must be 7 chars: 3 digits then 4 alphanumeric.</div>}
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: 6, fontSize: 12, fontWeight: 500, color: 'var(--text-secondary)' }}>Challan Serial No *</label>
              <input type="text" inputMode="numeric" value={entry.challanNo || ''} onChange={(e) => updateSelfAssessmentEntry(index, 'challanNo', e.target.value.replace(/\D/g, '').slice(0, 5))} placeholder="1-5 digits" maxLength={5} aria-invalid={Boolean(entry.challanNo) && (!challanPattern.test(String(entry.challanNo)) || Number(entry.challanNo) <= 0)} style={{ width: '100%', padding: '8px 12px', border: `1px solid ${entry.challanNo && (!challanPattern.test(String(entry.challanNo)) || Number(entry.challanNo) <= 0) ? 'var(--danger)' : 'var(--border)'}`, borderRadius: 6, fontSize: 13 }} />
              {entry.challanNo && (!challanPattern.test(String(entry.challanNo)) || Number(entry.challanNo) <= 0) && <div style={inputErrorStyle}>Enter 1-5 digits greater than zero.</div>}
            </div>
            <Field label="Date of Deposit *" value={entry.depositDate || ''} onChange={(v: any) => updateSelfAssessmentEntry(index, 'depositDate', v)} type="date" prefix="" required />
            <Field label="Amount *" value={entry.amount || 0} onChange={(v: any) => updateSelfAssessmentEntry(index, 'amount', v)} required />
            <div>
              <label style={{ display: 'block', marginBottom: 6, fontSize: 12, fontWeight: 500, color: 'var(--text-secondary)' }}>CIN (derived)</label>
              <input type="text" value={deriveCin(entry)} readOnly placeholder="Complete BSR, date and serial" style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6, fontSize: 13, background: 'var(--gold-pale)' }} />
            </div>
          </div>
        </div>
      ))}

      <div style={{ marginTop: 24, padding: 16, background: 'var(--gold-pale)', borderRadius: 6 }}>
        <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--gold)', marginBottom: 10 }}>Schedule-wise totals (claimed)</div>
        <Field label="Schedule TDS-1 — Salary TDS (TotalTDSonSalaries)" value={tdsBreakdown.tds1} computed />
        <Field label="Schedule TDS-2 — Non-salary TDS (TotalTDSonOthThanSals)" value={tdsBreakdown.tds2} computed />
        <Field label="Schedule TDS-3 — Tenant/buyer TDS (TotalTDS3Details)" value={tdsBreakdown.tds3} computed />
        <Field label="Schedule TCS — Collected at source (TotalSchTCS)" value={tdsBreakdown.tcs} computed />
        <Field label="Advance Tax (TaxesPaid.AdvanceTax)" value={advanceTotal} computed />
        <Field label="Self-Assessment Tax (TaxesPaid.SelfAssessmentTax)" value={satTotal} computed />
        <Field label="Entered Tax Payments (TotalTaxPayments)" value={taxResult.enteredCredits?.total ?? taxResult.totalTaxPaid} computed />
        <Field label="Validated Filing Credits" value={taxResult.validatedCredits?.total ?? taxResult.totalTaxPaid} computed />
      </div>
    </div>
  );
}

export function TaxComputationTab({ taxResult, regime, itrForm }: any) {
  const INR = (v: any) => `₹${Number(v || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;
  const signedINR = (v: any) => {
    const amount = Number(v || 0);
    return `${amount >= 0 ? '+' : '−'}${INR(Math.abs(amount))}`;
  };

  // CBDT deduction breakdown entries (from backend engine)
  const dedBreakdown = taxResult.deductionBreakdown || {};
  const dedEntries = Object.entries(dedBreakdown).filter(([, v]: any) => Number(v) > 0);

  // Income head totals (all backend-computed)
  const incomeFromSal = Number(taxResult.incomeFromSal ?? taxResult.netSalary ?? 0);
  const hpIncome = Number(taxResult.totalIncChargeHP ?? taxResult.hpIncome ?? 0);
  const otherIncome = Number(taxResult.incomeOthSrc ?? taxResult.otherIncome ?? 0);
  const bizIncome = Number(taxResult.bizIncome ?? 0);
  const gti = Number(taxResult.grossTotIncome ?? taxResult.gti ?? 0);
  const totalIncome = Number(taxResult.totalIncome ?? 0);
  const chapVIA = Number(taxResult.deductChapVIA ?? taxResult.totalDeductions ?? 0);

  return (
    <div style={{ maxWidth: 800, margin: '0 auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <tbody>
          {/* ════════════════════════════════════════════════════════════════
              PART B — TOTAL INCOME (CBDT ITR1_IncomeDeductions)
          ═════════════════════════════════════════════════════════════════ */}
          <tr style={{ background: 'var(--bg)' }}>
            <td colSpan={2} style={{ padding: '8px 12px', fontWeight: 700, fontSize: 13, color: 'var(--gold)' }}>
              PART B — TOTAL INCOME
            </td>
          </tr>

          {/* ── Salary (Schedule S) — only show when salary exists ── */}
          {Number(taxResult.grossSalary) > 0 && (
            <>
              <tr>
                <td style={{ padding: '8px 12px', fontSize: 13, fontWeight: 600 }}>Gross Salary (u/s 17(1))</td>
                <td className="mono" style={{ padding: '8px 12px', fontSize: 13, textAlign: 'right' }}>{INR(taxResult.grossSalary)}</td>
              </tr>
              {Number(taxResult.totalSection10Exempt) > 0 && (
                <tr>
                  <td style={{ padding: '8px 12px', fontSize: 13, paddingLeft: '24px' }}>Less: Exempt Allowances (u/s 10)</td>
                  <td className="mono" style={{ padding: '8px 12px', fontSize: 13, textAlign: 'right', color: 'var(--danger)' }}>({INR(taxResult.totalSection10Exempt)})</td>
                </tr>
              )}
              <tr>
                <td style={{ padding: '8px 12px', fontSize: 13, paddingLeft: '24px' }}>Salary after Section 10 exemptions</td>
                <td className="mono" style={{ padding: '8px 12px', fontSize: 13, textAlign: 'right' }}>{INR(taxResult.salaryBeforeSection16)}</td>
              </tr>
              {Number(taxResult.deductionUs16) > 0 && (
                <tr>
                  <td style={{ padding: '8px 12px', fontSize: 13, paddingLeft: '24px' }}>Less: Deductions u/s 16</td>
                  <td className="mono" style={{ padding: '8px 12px', fontSize: 13, textAlign: 'right', color: 'var(--danger)' }}>({INR(taxResult.deductionUs16)})</td>
                </tr>
              )}
              {Number(taxResult.standardDeduction) > 0 && (
                <tr>
                  <td style={{ padding: '4px 12px 4px 36px', fontSize: 12, color: 'var(--text-muted)' }}>• Standard Deduction (16ia)</td>
                  <td className="mono" style={{ padding: '4px 12px', fontSize: 12, textAlign: 'right', color: 'var(--text-muted)' }}>{INR(taxResult.standardDeduction)}</td>
                </tr>
              )}
              {Number(taxResult.entertainmentAllowanceDed) > 0 && (
                <tr>
                  <td style={{ padding: '4px 12px 4px 36px', fontSize: 12, color: 'var(--text-muted)' }}>• Entertainment Allowance (16ii)</td>
                  <td className="mono" style={{ padding: '4px 12px', fontSize: 12, textAlign: 'right', color: 'var(--text-muted)' }}>{INR(taxResult.entertainmentAllowanceDed)}</td>
                </tr>
              )}
              {Number(taxResult.professionalTaxDed) > 0 && (
                <tr>
                  <td style={{ padding: '4px 12px 4px 36px', fontSize: 12, color: 'var(--text-muted)' }}>• Professional Tax (16iii)</td>
                  <td className="mono" style={{ padding: '4px 12px', fontSize: 12, textAlign: 'right', color: 'var(--text-muted)' }}>{INR(taxResult.professionalTaxDed)}</td>
                </tr>
              )}
            </>
          )}

          {/* ── Income head totals ── */}
          {incomeFromSal > 0 && (
            <tr>
              <td style={{ padding: '8px 12px', fontSize: 13, fontWeight: 600 }}>Income from Salary</td>
              <td className="mono" style={{ padding: '8px 12px', fontSize: 13, textAlign: 'right', fontWeight: 600 }}>{INR(incomeFromSal)}</td>
            </tr>
          )}
          {hpIncome !== 0 && (
            <tr>
              <td style={{ padding: '8px 12px', fontSize: 13, fontWeight: 600 }}>Income from House Property</td>
              <td className="mono" style={{ padding: '8px 12px', fontSize: 13, textAlign: 'right', fontWeight: 600 }}>{INR(hpIncome)}</td>
            </tr>
          )}
          {bizIncome > 0 && (
            <tr>
              <td style={{ padding: '8px 12px', fontSize: 13, fontWeight: 600 }}>Business/Profession Income (Presumptive)</td>
              <td className="mono" style={{ padding: '8px 12px', fontSize: 13, textAlign: 'right', fontWeight: 600 }}>{INR(bizIncome)}</td>
            </tr>
          )}
          {otherIncome > 0 && (
            <>
              <tr>
                <td style={{ padding: '8px 12px', fontSize: 13, fontWeight: 600 }}>Income from Other Sources</td>
                <td className="mono" style={{ padding: '8px 12px', fontSize: 13, textAlign: 'right', fontWeight: 600 }}>{INR(otherIncome)}</td>
              </tr>
              {Number(taxResult.familyPensionDed) > 0 && (
                <tr>
                  <td style={{ padding: '8px 12px', fontSize: 13, paddingLeft: '24px' }}>Less: Deduction u/s 57iia (Family Pension)</td>
                  <td className="mono" style={{ padding: '8px 12px', fontSize: 13, textAlign: 'right', color: 'var(--danger)' }}>({INR(taxResult.deductUs57iia ?? taxResult.familyPensionDed)})</td>
                </tr>
              )}
            </>
          )}

          {/* ── GTI ── */}
          <tr style={{ borderTop: '2px solid var(--border)' }}>
            <td style={{ padding: '8px 12px', fontSize: 13, fontWeight: 600 }}>Gross Total Income</td>
            <td className="mono" style={{ padding: '8px 12px', fontSize: 13, textAlign: 'right', fontWeight: 600 }}>{INR(gti)}</td>
          </tr>

          {/* ── Chapter VIA Deductions ── */}
          {regime === 'old' && chapVIA > 0 && (
            <>
              <tr>
                <td style={{ padding: '8px 12px', fontSize: 13 }}>Less: Deductions (Chapter VIA)</td>
                <td className="mono" style={{ padding: '8px 12px', fontSize: 13, textAlign: 'right', color: 'var(--danger)' }}>({INR(chapVIA)})</td>
              </tr>
              {dedEntries.map(([key, val]: any) => (
                <tr key={key}>
                  <td style={{ padding: '4px 12px 4px 36px', fontSize: 12, color: 'var(--text-muted)' }}>• {key}</td>
                  <td className="mono" style={{ padding: '4px 12px', fontSize: 12, textAlign: 'right', color: 'var(--text-muted)' }}>{INR(val)}</td>
                </tr>
              ))}
            </>
          )}

          {/* ── Total Income and Section 288A reconciliation ── */}
          <tr style={{ borderTop: '1px solid var(--border)' }}>
            <td style={{ padding: '8px 12px', fontSize: 13 }}>Total Income before rounding</td>
            <td className="mono" style={{ padding: '8px 12px', fontSize: 13, textAlign: 'right' }}>{INR(taxResult.totalIncomeBefore288A)}</td>
          </tr>
          {Number(taxResult.roundingAdjustment288A) !== 0 && (
            <tr>
              <td style={{ padding: '8px 12px', fontSize: 13, paddingLeft: '24px' }}>Section 288A rounding adjustment</td>
              <td className="mono" style={{ padding: '8px 12px', fontSize: 13, textAlign: 'right' }}>{signedINR(taxResult.roundingAdjustment288A)}</td>
            </tr>
          )}
          <tr style={{ borderTop: '2px solid var(--border)', background: 'var(--gold-pale)' }}>
            <td style={{ padding: '8px 12px', fontSize: 14, fontWeight: 700 }}>ROUNDED TOTAL INCOME (u/s 288A)</td>
            <td className="mono" style={{ padding: '8px 12px', fontSize: 14, textAlign: 'right', fontWeight: 700 }}>{INR(totalIncome)}</td>
          </tr>

          {/* ════════════════════════════════════════════════════════════════
              PART B — TAX COMPUTATION (CBDT ITR1_TaxComputation)
          ═════════════════════════════════════════════════════════════════ */}
          <tr style={{ borderTop: '2px solid var(--border)', background: 'var(--bg)' }}>
            <td colSpan={2} style={{ padding: '8px 12px', fontWeight: 700, fontSize: 13, color: 'var(--gold)' }}>
              TAX COMPUTATION
            </td>
          </tr>
          <tr>
            <td style={{ padding: '8px 12px', fontSize: 13 }}>Normal-rate income</td>
            <td className="mono" style={{ padding: '8px 12px', fontSize: 13, textAlign: 'right' }}>{INR(taxResult.normalRateIncome)}</td>
          </tr>
          <tr>
            <td style={{ padding: '8px 12px', fontSize: 13, paddingLeft: '24px' }}>Basic exemption limit</td>
            <td className="mono" style={{ padding: '8px 12px', fontSize: 13, textAlign: 'right' }}>{INR(taxResult.basicExemptionLimit)}</td>
          </tr>
          <tr>
            <td style={{ padding: '8px 12px', fontSize: 13, fontWeight: 600 }}>Income above basic exemption limit</td>
            <td className="mono" style={{ padding: '8px 12px', fontSize: 13, textAlign: 'right', fontWeight: 600 }}>{INR(taxResult.incomeChargeableAboveBasicExemption)}</td>
          </tr>
          {taxResult.nilTaxReason === 'BELOW_BASIC_EXEMPTION_LIMIT' && (
            <tr style={{ background: 'var(--success-bg)' }}>
              <td colSpan={2} style={{ padding: '8px 12px', fontSize: 12, color: 'var(--success)', fontWeight: 600 }}>
                Nil tax: normal-rate income does not exceed the applicable basic exemption limit.
              </td>
            </tr>
          )}
          <tr>
            <td style={{ padding: '8px 12px', fontSize: 13 }}>Tax before rebate</td>
            <td className="mono" style={{ padding: '8px 12px', fontSize: 13, textAlign: 'right' }}>{INR(taxResult.totalTaxPayable ?? taxResult.normalTax)}</td>
          </tr>
          {Number(taxResult.rebate87A) > 0 && (
            <tr>
              <td style={{ padding: '8px 12px', fontSize: 13, paddingLeft: '24px' }}>Less: Rebate u/s 87A</td>
              <td className="mono" style={{ padding: '8px 12px', fontSize: 13, textAlign: 'right', color: 'var(--success)' }}>({INR(taxResult.rebate87A)})</td>
            </tr>
          )}
          {taxResult.nilTaxReason === 'REBATE_87A' && Number(taxResult.rebate87A) > 0 && (
            <tr style={{ background: 'var(--success-bg)' }}>
              <td colSpan={2} style={{ padding: '8px 12px', fontSize: 12, color: 'var(--success)', fontWeight: 600 }}>
                Nil tax after applying rebate under Section 87A.
              </td>
            </tr>
          )}
          <tr>
            <td style={{ padding: '8px 12px', fontSize: 13, fontWeight: 600 }}>Tax After Rebate</td>
            <td className="mono" style={{ padding: '8px 12px', fontSize: 13, textAlign: 'right', fontWeight: 600 }}>{INR(taxResult.taxPayableOnRebate)}</td>
          </tr>
          {Number(taxResult.surcharge) > 0 && (
            <tr>
              <td style={{ padding: '8px 12px', fontSize: 13, paddingLeft: '24px' }}>Add: Surcharge</td>
              <td className="mono" style={{ padding: '8px 12px', fontSize: 13, textAlign: 'right' }}>{INR(taxResult.surcharge)}</td>
            </tr>
          )}
          {Number(taxResult.cess) > 0 && (
            <tr>
              <td style={{ padding: '8px 12px', fontSize: 13, paddingLeft: '24px' }}>Add: Health & Education Cess (4%)</td>
              <td className="mono" style={{ padding: '8px 12px', fontSize: 13, textAlign: 'right' }}>{INR(taxResult.cess)}</td>
            </tr>
          )}
          <tr style={{ borderTop: '1px solid var(--border)' }}>
            <td style={{ padding: '8px 12px', fontSize: 13, fontWeight: 600 }}>Gross Tax Liability</td>
            <td className="mono" style={{ padding: '8px 12px', fontSize: 13, textAlign: 'right', fontWeight: 600 }}>{INR(taxResult.grossTaxLiability)}</td>
          </tr>
          {(Number(taxResult.section89) ?? 0) > 0 && (
            <tr>
              <td style={{ padding: '8px 12px', fontSize: 13, paddingLeft: '24px' }}>Less: Relief u/s 89</td>
              <td className="mono" style={{ padding: '8px 12px', fontSize: 13, textAlign: 'right', color: 'var(--success)' }}>({INR(taxResult.section89)})</td>
            </tr>
          )}
          {(Number(taxResult.interest234A) || 0) > 0 && <tr><td style={{ padding: '8px 12px', fontSize: 13, paddingLeft: '24px' }}>Add: Interest u/s 234A</td><td className="mono" style={{ padding: '8px 12px', fontSize: 13, textAlign: 'right' }}>{INR(taxResult.interest234A)}</td></tr>}
          {(Number(taxResult.interest234B) || 0) > 0 && <tr><td style={{ padding: '8px 12px', fontSize: 13, paddingLeft: '24px' }}>Add: Interest u/s 234B</td><td className="mono" style={{ padding: '8px 12px', fontSize: 13, textAlign: 'right' }}>{INR(taxResult.interest234B)}</td></tr>}
          {(Number(taxResult.interest234C) || 0) > 0 && <tr><td style={{ padding: '8px 12px', fontSize: 13, paddingLeft: '24px' }}>Add: Interest u/s 234C</td><td className="mono" style={{ padding: '8px 12px', fontSize: 13, textAlign: 'right' }}>{INR(taxResult.interest234C)}</td></tr>}
          {(Number(taxResult.lateFee234F) || 0) > 0 && <tr><td style={{ padding: '8px 12px', fontSize: 13, paddingLeft: '24px' }}>Add: Late filing fee u/s 234F</td><td className="mono" style={{ padding: '8px 12px', fontSize: 13, textAlign: 'right' }}>{INR(taxResult.lateFee234F)}</td></tr>}
          {(Number(taxResult.fees234I) || 0) > 0 && <tr><td style={{ padding: '8px 12px', fontSize: 13, paddingLeft: '24px' }}>Add: Fee u/s 234-I (revised return)</td><td className="mono" style={{ padding: '8px 12px', fontSize: 13, textAlign: 'right' }}>{INR(taxResult.fees234I)}</td></tr>}
          <tr style={{ borderTop: '2px solid var(--border)', background: 'var(--navy)' }}>
            <td style={{ padding: '12px', fontSize: 15, fontWeight: 700, color: 'white' }}>NET TAX LIABILITY</td>
            <td className="mono" style={{ padding: '12px', fontSize: 15, textAlign: 'right', fontWeight: 700, color: 'white' }}>{INR(taxResult.netTaxLiability ?? taxResult.totalTaxLiability)}</td>
          </tr>

          {/* ════════════════════════════════════════════════════════════════
              TAXES PAID (CBDT TaxesPaid)
          ═════════════════════════════════════════════════════════════════ */}
          <tr style={{ borderTop: '2px solid var(--border)', background: 'var(--bg)' }}>
            <td colSpan={2} style={{ padding: '8px 12px', fontWeight: 700, fontSize: 13, color: 'var(--gold)' }}>
              TAXES PAID
            </td>
          </tr>
          <tr>
            <td style={{ padding: '8px 12px', fontSize: 13, paddingLeft: '24px' }}>Validated Advance Tax</td>
            <td className="mono" style={{ padding: '8px 12px', fontSize: 13, textAlign: 'right', color: 'var(--success)' }}>({INR(taxResult.validatedCredits?.advanceTax ?? taxResult.advanceTax)})</td>
          </tr>
          <tr>
            <td style={{ padding: '8px 12px', fontSize: 13, paddingLeft: '24px' }}>Validated TDS</td>
            <td className="mono" style={{ padding: '8px 12px', fontSize: 13, textAlign: 'right', color: 'var(--success)' }}>({INR(taxResult.validatedCredits?.tds ?? taxResult.totalTDS)})</td>
          </tr>
          {(taxResult.totalTCS ?? 0) > 0 && (
            <tr>
              <td style={{ padding: '8px 12px', fontSize: 13, paddingLeft: '24px' }}>TCS</td>
              <td className="mono" style={{ padding: '8px 12px', fontSize: 13, textAlign: 'right', color: 'var(--success)' }}>({INR(taxResult.totalTCS)})</td>
            </tr>
          )}
          <tr>
            <td style={{ padding: '8px 12px', fontSize: 13, paddingLeft: '24px' }}>Validated Self-Assessment Tax</td>
            <td className="mono" style={{ padding: '8px 12px', fontSize: 13, textAlign: 'right', color: 'var(--success)' }}>({INR(taxResult.validatedCredits?.selfAssessmentTax ?? taxResult.selfAssessmentTax ?? taxResult.selfTax)})</td>
          </tr>
          <tr style={{ borderTop: '1px solid var(--border)' }}>
            <td style={{ padding: '8px 12px', fontSize: 13, fontWeight: 600 }}>Validated Filing Credits</td>
            <td className="mono" style={{ padding: '8px 12px', fontSize: 13, textAlign: 'right', fontWeight: 600, color: 'var(--success)' }}>({INR(taxResult.validatedCredits?.total ?? taxResult.totalTaxesPaid ?? taxResult.totalTaxPaid)})</td>
          </tr>
          {taxResult.creditStatus === 'PROVISIONAL' && (
            <>
              <tr>
                <td style={{ padding: '8px 12px', fontSize: 13, fontWeight: 600 }}>Entered Credits (Provisional)</td>
                <td className="mono" style={{ padding: '8px 12px', fontSize: 13, textAlign: 'right', fontWeight: 600, color: 'var(--gold)' }}>({INR(taxResult.enteredCredits?.total)})</td>
              </tr>
              <tr>
                <td style={{ padding: '8px 12px', fontSize: 13, paddingLeft: '24px' }}>Blocked Pending Correction</td>
                <td className="mono" style={{ padding: '8px 12px', fontSize: 13, textAlign: 'right', color: 'var(--danger)' }}>{INR(taxResult.blockedCreditsTotal)}</td>
              </tr>
            </>
          )}

          {taxResult.creditStatus === 'PROVISIONAL' && (
            <tr style={{ background: 'var(--danger-bg)' }}>
              <td colSpan={2} style={{ padding: '10px 12px', fontSize: 12, color: 'var(--danger)' }}>
                <strong>Tax credits are provisional.</strong>
                {(taxResult.creditValidationIssues || []).map((issue: any, index: number) => (
                  <div key={`${issue.code}-${issue.row}-${index}`} style={{ marginTop: 4 }}>
                    • {issue.creditType} row {issue.row}: {issue.message}
                  </div>
                ))}
              </td>
            </tr>
          )}

          {/* ════════════════════════════════════════════════════════════════
              BALANCE / REFUND
          ═════════════════════════════════════════════════════════════════ */}
          <tr style={{ borderTop: '2px solid var(--border)', background: taxResult.balTaxPayable > 0 ? 'var(--danger-bg)' : taxResult.refundStatus === 'PROVISIONAL_BLOCKED' ? 'var(--gold-pale)' : 'var(--success-bg)' }}>
            <td style={{ padding: '12px', fontSize: 15, fontWeight: 700, color: taxResult.balTaxPayable > 0 ? 'var(--danger)' : taxResult.refundStatus === 'PROVISIONAL_BLOCKED' ? 'var(--gold)' : 'var(--success)' }}>
              {taxResult.balTaxPayable > 0 ? 'BALANCE TAX PAYABLE' : taxResult.refundStatus === 'PROVISIONAL_BLOCKED' ? 'PROVISIONAL REFUND — VALIDATION REQUIRED' : 'REFUND DUE'}
            </td>
            <td className="mono" style={{ padding: '12px', fontSize: 15, textAlign: 'right', fontWeight: 700, color: taxResult.balTaxPayable > 0 ? 'var(--danger)' : taxResult.refundStatus === 'PROVISIONAL_BLOCKED' ? 'var(--gold)' : 'var(--success)' }}>
              {INR(taxResult.balTaxPayable > 0
                ? taxResult.balTaxPayable
                : taxResult.refundStatus === 'PROVISIONAL_BLOCKED'
                  ? taxResult.provisionalRefund
                  : taxResult.confirmedRefund ?? taxResult.refundDue ?? taxResult.refund)}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

function Field({ label, value, onChange, computed, prefix = '₹', type = 'number', required = false }: any) {
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
          type={type}
          value={value}
          onChange={(e) => !computed && onChange(type === 'number' ? Number(e.target.value) : e.target.value)}
          readOnly={computed}
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

// The local computeTax() function has been REMOVED.
// All tax calculations now happen in the backend at /api/v1/tax-summary/compute.
// This ensures 100% CBDT compliance - frontend does ZERO calculation logic.
