import React, { useState } from 'react';

/**
 * EmployerEntryManager — multi-employer salary data entry.
 *
 * IMPORTANT: This component is now a PURE DATA-ENTRY component.
 * All exemption/tax calculations are done in the BACKEND via
 * SalaryScheduleComputer (called by TaxController and
 * TaxComputationOrchestrator). The frontend only:
 *   1. Collects raw user input
 *   2. Displays backend-computed results from `taxResult` prop
 *
 * Field names match the backend EmployerEntry record so the
 * TaxController.mapToEmployerEntry() conversion is lossless.
 */

interface EmployerEntry {
  id: string;
  customEmployerName?: string;
  employerName?: string;
  employerTAN?: string;
  natureOfEmployment?: string;

  // Section 17(1) — Gross Salary
  basic?: number;
  da?: number;
  commission?: number;
  hra?: number;
  bonus?: number;
  allowances?: number;
  lta?: number;
  otherAllowance?: number;
  arrearSalary?: number;

  // Section 17(2) — Perquisites (single aggregate field)
  perquisites?: number;

  // Section 17(3) — Profits in Lieu (single aggregate field)
  profitsInLieu?: number;

  // HRA inputs
  rentPaid?: number;
  city?: string;
  isMetroCity?: boolean;
  isGovernmentEmployee?: boolean;
  isDisabledEmployee?: boolean;

  // Retirement benefits
  commutedPension?: number;
  gratuity?: number;
  leaveEncashment?: number;
  averageMonthlySalary?: number;
  yearsOfService?: number;
  unavailedLeaveDays?: number;

  // LTA inputs
  actualLtaFare?: number;
  isDomesticTravel?: boolean;
  journeysInBlock?: number;
  ltaExempt?: number;

  // Children count (for CEA/hostel)
  numberOfChildren?: number;

  // Gratuity also received (for pension commutation)
  gratuityAlsoReceived?: boolean;

  // Section 10(14) allowances
  transportAllowance?: number;
  childrenEducationAllowance?: number;
  hostelExpenditureAllowance?: number;
  uniformAllowance?: number;

  // Section 16 deductions
  entertainmentAllowance?: number;
  professionalTax?: number;

  // VRS / Retrenchment
  vrsCompensation?: number;
  retrenchmentCompensation?: number;

  // Other
  otherExempt?: number;

  // TDS
  tdsDeducted?: number;

  // NPS
  employerNPS?: number;
}

interface Props {
  entries: EmployerEntry[];
  onChange: (entries: EmployerEntry[]) => void;
  assessmentYear: string;
  taxRegime?: string;
  /** Backend-computed salary result (from taxResult prop) */
  backendResult?: {
    grossSalaryTotal?: number;
    hraExempt?: number;
    ltaExempt?: number;
    gratuityExempt?: number;
    leaveEncashmentExempt?: number;
    pensionCommutationExempt?: number;
    transportAllowanceExempt?: number;
    childrenEducationExempt?: number;
    hostelExpenditureExempt?: number;
    uniformAllowanceExempt?: number;
    totalSection10Exempt?: number;
    standardDeduction?: number;
    entertainmentAllowanceDed?: number;
    professionalTaxDed?: number;
    totalSection16Deductions?: number;
    netTaxableSalary?: number;
    totalTDSDeducted?: number;
    employerCount?: number;
    hraCondition1_Actual?: number;
    hraCondition2_RentMinus10Pct?: number;
    hraCondition3_MetroPct?: number;
    hraIsMetroCity?: boolean;
    hraCityClassified?: string;
  };
}

const generateId = () => 'emp_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);

const formatINR = (num?: number): string => {
  if (!num || typeof num !== 'number' || isNaN(num)) return '0';
  return Math.round(num).toLocaleString('en-IN');
};

const Section = ({ title, expanded, onClick, badge, children }: any) => (
  <div style={{ marginBottom: 8, border: '1px solid #e2e8f0', borderRadius: 8, overflow: 'hidden' }}>
    <button onClick={onClick} style={{ width: '100%', padding: 12, display: 'flex', justifyContent: 'space-between', background: expanded ? '#fef3e2' : '#f8fafc', border: 'none', cursor: 'pointer' }}>
      <span style={{ fontSize: 13, fontWeight: 600, color: '#475569' }}>{title}</span>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        {badge && <span style={{ fontSize: 11, background: '#e2e8f0', padding: '2px 8px', borderRadius: 4 }}>{badge}</span>}
        <span style={{ fontSize: 12, color: '#94a3b8' }}>{expanded ? '▲' : '▼'}</span>
      </div>
    </button>
    {expanded && <div style={{ padding: 16, background: 'white' }}>{children}</div>}
  </div>
);

const F = ({ label, hint, children }: any) => (
  <div>
    <label style={{ display: 'block', marginBottom: 4, fontSize: 12, fontWeight: 500, color: '#64748b' }}>{label}</label>
    {children}
    {hint && <div style={{ fontSize: 10, color: '#94a3b8', marginTop: 2 }}>{hint}</div>}
  </div>
);

const Inp = (p: any) => (
  <input type="text" inputMode="numeric" value={p.value === 0 || p.value === undefined ? '' : String(p.value)}
    onChange={(e: any) => { let val = String(e.target.value).replace(/[^\d]/g, ''); p.onChange(val === '' ? 0 : parseInt(val, 10) || 0); }}
    style={{ width: '100%', padding: '8px 10px', border: '1px solid #e2e8f0', borderRadius: 6, fontSize: 13 }} />
);

const TextInp = (p: any) => (
  <input type="text" value={p.value || ''} onChange={(e: any) => p.onChange(e.target.value)}
    style={{ width: '100%', padding: '8px 10px', border: '1px solid #e2e8f0', borderRadius: 6, fontSize: 13 }} />
);

export function EmployerEntryManager({ entries = [], onChange, assessmentYear, taxRegime = 'OLD', backendResult }: Props) {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const toggleExpand = (id: string) => setExpandedId(expandedId === id ? null : id);

  const addEntry = () => onChange([...entries, { id: generateId(), customEmployerName: `Employer ${entries.length + 1}` }]);

  const updateEntry = (id: string, updates: Partial<EmployerEntry>) => {
    onChange(entries.map(e => e.id === id ? { ...e, ...updates } : e));
  };

  const removeEntry = (id: string) => onChange(entries.filter(e => e.id !== id));

  // ── Local gross calculation (for display only — backend is authoritative) ──
  const getGross = (e: EmployerEntry) => {
    const b = typeof e.basic === 'number' && e.basic > 0 ? e.basic : 0;
    const d = typeof e.da === 'number' && e.da > 0 ? e.da : 0;
    const h = typeof e.hra === 'number' && e.hra > 0 ? e.hra : 0;
    const bn = typeof e.bonus === 'number' && e.bonus > 0 ? e.bonus : 0;
    const a = typeof e.allowances === 'number' && e.allowances > 0 ? e.allowances : 0;
    const l = typeof e.lta === 'number' && e.lta > 0 ? e.lta : 0;
    const cp = typeof e.commutedPension === 'number' && e.commutedPension > 0 ? e.commutedPension : 0;
    const g = typeof e.gratuity === 'number' && e.gratuity > 0 ? e.gratuity : 0;
    const leave = typeof e.leaveEncashment === 'number' && e.leaveEncashment > 0 ? e.leaveEncashment : 0;
    const perq = typeof e.perquisites === 'number' && e.perquisites > 0 ? e.perquisites : 0;
    const pil = typeof e.profitsInLieu === 'number' && e.profitsInLieu > 0 ? e.profitsInLieu : 0;
    const comm = typeof e.commission === 'number' && e.commission > 0 ? e.commission : 0;
    const oa = typeof e.otherAllowance === 'number' && e.otherAllowance > 0 ? e.otherAllowance : 0;
    const vrs = typeof e.vrsCompensation === 'number' && e.vrsCompensation > 0 ? e.vrsCompensation : 0;
    const retrench = typeof e.retrenchmentCompensation === 'number' && e.retrenchmentCompensation > 0 ? e.retrenchmentCompensation : 0;
    return b + d + h + bn + a + l + cp + g + leave + perq + pil + comm + oa + vrs + retrench;
  };

  const totalGross = () => entries.reduce((s, e) => s + getGross(e), 0);
  const totalTDS = () => entries.reduce((s, e) => s + (e.tdsDeducted || 0), 0);

  // ── Backend-computed values (preferred) ──
  const backendGross = backendResult?.grossSalaryTotal ?? 0;
  const backendExempt = (backendResult?.totalSection10Exempt ?? 0) + (backendResult?.totalSection16Deductions ?? 0);
  const backendNet = backendResult?.netTaxableSalary ?? 0;
  const backendTDS = backendResult?.totalTDSDeducted ?? 0;
  const hasBackend = backendResult && (backendResult.grossSalaryTotal ?? 0) > 0;

  return (
    <div style={{ marginBottom: 24 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600, color: '#64748b' }}>Salary Details ({taxRegime})</h3>
        <button onClick={addEntry} style={{ padding: '8px 16px', background: '#c9943a', color: 'white', border: 'none', borderRadius: 6, fontSize: 13, cursor: 'pointer' }}>+ Add</button>
      </div>

      {entries.length === 0 ? (
        <div style={{ textAlign: 'center', padding: 40, color: '#94a3b8', background: '#f8fafc', borderRadius: 8, border: '1px dashed #cbd5e1' }}>Click "+ Add" to add salary details</div>
      ) : entries.map(e => (
        <div key={e.id} style={{ background: 'white', border: '1px solid #e2e8f0', borderRadius: 12, padding: 20, marginBottom: 16 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16, paddingBottom: 16, borderBottom: '1px solid #f1f5f9' }}>
            <input type="text" value={e.customEmployerName || 'Employer'} onChange={(ev: any) => updateEntry(e.id, { customEmployerName: ev.target.value })}
              style={{ border: 'none', borderBottom: '1px dashed #c9943a', background: 'transparent', fontSize: 14, fontWeight: 600, minWidth: 150, outline: 'none' }} />
            <button onClick={() => removeEntry(e.id)} style={{ background: '#fef2f2', color: '#ef4444', border: 'none', width: 28, height: 28, borderRadius: '50%', cursor: 'pointer' }}>×</button>
          </div>

          {/* Per-employer summary card — local gross only (backend aggregates across employers) */}
          <div style={{ padding: 16, background: 'linear-gradient(135deg, #fef3e2, #fff7ed)', borderRadius: 8, marginBottom: 16, border: '1px solid #fed7aa' }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 16 }}>
              <div>
                <div style={{ fontSize: 11, color: '#78716c' }}>This Employer Gross (Local)</div>
                <div style={{ fontSize: 16, fontWeight: 700 }}>₹{formatINR(getGross(e))}</div>
              </div>
              <div>
                <div style={{ fontSize: 11, color: '#78716c' }}>TDS (This Employer)</div>
                <div style={{ fontSize: 16, fontWeight: 700 }}>₹{formatINR(e.tdsDeducted)}</div>
              </div>
            </div>
            <div style={{ fontSize: 10, color: '#78716c', marginTop: 8, fontStyle: 'italic' }}>
              Aggregated Schedule S computation shown below (backend-computed)
            </div>
          </div>

          <Section title="Employer Details" expanded={expandedId === `emp-${e.id}`} onClick={() => toggleExpand(`emp-${e.id}`)} badge={e.employerName || 'Req'}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
              <F label="Name"><TextInp value={e.employerName || ''} onChange={(v: any) => updateEntry(e.id, { employerName: v })} /></F>
              <F label="TAN"><TextInp value={e.employerTAN || ''} onChange={(v: any) => updateEntry(e.id, { employerTAN: v.toUpperCase() })} /></F>
              <F label="Nature">
                <select value={e.natureOfEmployment || 'NGOV'} onChange={(ev: any) => updateEntry(e.id, { natureOfEmployment: ev.target.value })} style={{ width: '100%', padding: '8px 10px', border: '1px solid #e2e8f0', borderRadius: 6 }}>
                  <option value="NGOV">Private</option><option value="GOV">Government</option><option value="PSU">PSU</option>
                </select>
              </F>
            </div>
          </Section>

          <Section title="Salary Components (Section 17(1))" expanded={expandedId === `sal-${e.id}`} onClick={() => toggleExpand(`sal-${e.id}`)} badge="">
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
              <F label="Basic"><Inp value={e.basic} onChange={(v: any) => updateEntry(e.id, { basic: v })} /></F>
              <F label="DA"><Inp value={e.da} onChange={(v: any) => updateEntry(e.id, { da: v })} /></F>
              <F label="HRA"><Inp value={e.hra} onChange={(v: any) => updateEntry(e.id, { hra: v })} /></F>
              <F label="Bonus"><Inp value={e.bonus} onChange={(v: any) => updateEntry(e.id, { bonus: v })} /></F>
              <F label="Allowances"><Inp value={e.allowances} onChange={(v: any) => updateEntry(e.id, { allowances: v })} /></F>
              <F label="LTA"><Inp value={e.lta} onChange={(v: any) => updateEntry(e.id, { lta: v })} /></F>
              <F label="Commission"><Inp value={e.commission} onChange={(v: any) => updateEntry(e.id, { commission: v })} /></F>
              <F label="Other Allowance"><Inp value={e.otherAllowance} onChange={(v: any) => updateEntry(e.id, { otherAllowance: v })} /></F>
              <F label="Arrear Salary"><Inp value={e.arrearSalary} onChange={(v: any) => updateEntry(e.id, { arrearSalary: v })} /></F>
            </div>
          </Section>

          <Section title="Perquisites & Profits in Lieu (Section 17(2) & 17(3))" expanded={expandedId === `perq-${e.id}`} onClick={() => toggleExpand(`perq-${e.id}`)} badge="">
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 12 }}>
              <F label="Perquisites u/s 17(2)" hint="Aggregate value of all perquisites"><Inp value={e.perquisites} onChange={(v: any) => updateEntry(e.id, { perquisites: v })} /></F>
              <F label="Profits in Lieu u/s 17(3)" hint="Compensation, non-compete, etc."><Inp value={e.profitsInLieu} onChange={(v: any) => updateEntry(e.id, { profitsInLieu: v })} /></F>
            </div>
          </Section>

          <Section title="HRA Exemption u/s 10(13A)" expanded={expandedId === `hra-${e.id}`} onClick={() => toggleExpand(`hra-${e.id}`)} badge={taxRegime}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
              <F label="Rent Paid (Annual)"><Inp value={e.rentPaid} onChange={(v: any) => updateEntry(e.id, { rentPaid: v })} hint="Required for HRA exemption" /></F>
              <F label="City of Employment" hint="For metro classification">
                <TextInp value={e.city || ''} onChange={(v: any) => updateEntry(e.id, { city: v })} />
              </F>
              <F label="Metro City">
                <select value={e.isMetroCity ? 'yes' : 'no'} onChange={(ev: any) => updateEntry(e.id, { isMetroCity: ev.target.value === 'yes' })} style={{ width: '100%', padding: '8px 10px', border: '1px solid #e2e8f0', borderRadius: 6 }}>
                  <option value="no">No (40%)</option><option value="yes">Yes (50%)</option>
                </select>
              </F>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 20 }}>
                <input type="checkbox" checked={e.isGovernmentEmployee || false} onChange={(ev: any) => updateEntry(e.id, { isGovernmentEmployee: ev.target.checked })} />
                <span style={{ fontSize: 12 }}>Govt Employee (full HRA exempt)</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 20 }}>
                <input type="checkbox" checked={e.isDisabledEmployee || false} onChange={(ev: any) => updateEntry(e.id, { isDisabledEmployee: ev.target.checked })} />
                <span style={{ fontSize: 12 }}>Disabled Employee (higher transport cap)</span>
              </div>
            </div>
          </Section>

          <Section title="Retirement & VRS Benefits" expanded={expandedId === `ret-${e.id}`} onClick={() => toggleExpand(`ret-${e.id}`)} badge="">
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
              <F label="Commuted Pension" hint="u/s 10(10A)"><Inp value={e.commutedPension} onChange={(v: any) => updateEntry(e.id, { commutedPension: v })} /></F>
              <F label="Gratuity (max ₹20L)" hint="u/s 10(10)"><Inp value={e.gratuity} onChange={(v: any) => updateEntry(e.id, { gratuity: v })} /></F>
              <F label="Leave Encash (max ₹25L)" hint="u/s 10(10AA)"><Inp value={e.leaveEncashment} onChange={(v: any) => updateEntry(e.id, { leaveEncashment: v })} /></F>
              <F label="VRS Compensation (max ₹5L)" hint="u/s 10(10C)"><Inp value={e.vrsCompensation} onChange={(v: any) => updateEntry(e.id, { vrsCompensation: v })} /></F>
              <F label="Retrenchment (max ₹5L)" hint="u/s 10(10B)"><Inp value={e.retrenchmentCompensation} onChange={(v: any) => updateEntry(e.id, { retrenchmentCompensation: v })} /></F>
              <F label="Avg Monthly Salary" hint="For gratuity/leave encashment"><Inp value={e.averageMonthlySalary} onChange={(v: any) => updateEntry(e.id, { averageMonthlySalary: v })} /></F>
              <F label="Years of Service" hint="For gratuity/leave encashment"><Inp value={e.yearsOfService} onChange={(v: any) => updateEntry(e.id, { yearsOfService: v })} /></F>
              <F label="Unavailed Leave Days" hint="For leave encashment"><Inp value={e.unavailedLeaveDays} onChange={(v: any) => updateEntry(e.id, { unavailedLeaveDays: v })} /></F>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 20 }}>
                <input type="checkbox" checked={e.gratuityAlsoReceived || false} onChange={(ev: any) => updateEntry(e.id, { gratuityAlsoReceived: ev.target.checked })} />
                <span style={{ fontSize: 12 }}>Gratuity also received (affects pension commutation)</span>
              </div>
            </div>
          </Section>

          <Section title="LTA Exemption u/s 10(5)" expanded={expandedId === `lta-${e.id}`} onClick={() => toggleExpand(`lta-${e.id}`)} badge="">
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
              <F label="Actual LTA Fare" hint="Shortest route, economy class"><Inp value={e.actualLtaFare} onChange={(v: any) => updateEntry(e.id, { actualLtaFare: v })} /></F>
              <F label="Journeys in Block" hint="Max 2 per 4-year block">
                <Inp value={e.journeysInBlock} onChange={(v: any) => updateEntry(e.id, { journeysInBlock: v })} />
              </F>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 20 }}>
                <input type="checkbox" checked={e.isDomesticTravel !== false} onChange={(ev: any) => updateEntry(e.id, { isDomesticTravel: ev.target.checked })} />
                <span style={{ fontSize: 12 }}>Domestic travel only</span>
              </div>
            </div>
          </Section>

          <Section title="Section 10(14) Allowances" expanded={expandedId === `all-${e.id}`} onClick={() => toggleExpand(`all-${e.id}`)} badge="">
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
              <F label="Transport Allowance" hint="u/s 10(14) — max ₹19,200 (₹38,400 if disabled)"><Inp value={e.transportAllowance} onChange={(v: any) => updateEntry(e.id, { transportAllowance: v })} /></F>
              <F label="Children Education" hint="u/s 10(14) — ₹1,200/child, max 2"><Inp value={e.childrenEducationAllowance} onChange={(v: any) => updateEntry(e.id, { childrenEducationAllowance: v })} /></F>
              <F label="Hostel Expenditure" hint="u/s 10(14) — ₹3,600/child, max 2"><Inp value={e.hostelExpenditureAllowance} onChange={(v: any) => updateEntry(e.id, { hostelExpenditureAllowance: v })} /></F>
              <F label="Uniform Allowance" hint="u/s 10(14) — actual expenditure"><Inp value={e.uniformAllowance} onChange={(v: any) => updateEntry(e.id, { uniformAllowance: v })} /></F>
              <F label="Number of Children" hint="For CEA/hostel cap">
                <Inp value={e.numberOfChildren} onChange={(v: any) => updateEntry(e.id, { numberOfChildren: v })} />
              </F>
              <F label="Entertainment Allowance" hint="u/s 16(ii) — Govt only, max ₹5,000"><Inp value={e.entertainmentAllowance} onChange={(v: any) => updateEntry(e.id, { entertainmentAllowance: v })} /></F>
            </div>
          </Section>

          <Section title="Deductions u/s 16 & TDS" expanded={expandedId === `ded-${e.id}`} onClick={() => toggleExpand(`ded-${e.id}`)} badge="">
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
              <F label="Professional Tax" hint="u/s 16(iii) — max ₹2,500/year"><Inp value={e.professionalTax} onChange={(v: any) => updateEntry(e.id, { professionalTax: v })} /></F>
              <F label="TDS Deducted" hint="u/s 192"><Inp value={e.tdsDeducted} onChange={(v: any) => updateEntry(e.id, { tdsDeducted: v })} /></F>
              <F label="Employer NPS (80CCD2)" hint="For deduction"><Inp value={e.employerNPS} onChange={(v: any) => updateEntry(e.id, { employerNPS: v })} /></F>
              <F label="Other Exemptions" hint="Schedule EI"><Inp value={e.otherExempt} onChange={(v: any) => updateEntry(e.id, { otherExempt: v })} /></F>
            </div>
          </Section>
        </div>
      ))}

      {/* ── Aggregated Schedule S Summary (Backend-Computed) ── */}
      {entries.length > 0 && (
        <div style={{ padding: 20, background: 'linear-gradient(135deg, #1e293b, #334155)', borderRadius: 12, color: 'white' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <h4 style={{ margin: 0, fontSize: 13, fontWeight: 600, color: '#fbbf24' }}>
              Schedule S — Income from Salary (Backend-Computed)
            </h4>
            <span style={{ fontSize: 10, padding: '2px 8px', background: hasBackend ? '#16a34a' : '#94a3b8', borderRadius: 4 }}>
              {hasBackend ? '✓ LIVE' : '⏳ PENDING'}
            </span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, textAlign: 'center', marginBottom: 12 }}>
            <div>
              <div style={{ fontSize: 11, opacity: 0.7 }}>GROSS SALARY</div>
              <div style={{ fontSize: 22, fontWeight: 700 }}>₹{formatINR(hasBackend ? backendGross : totalGross())}</div>
              <div style={{ fontSize: 9, opacity: 0.6 }}>17(1)+17(2)+17(3)</div>
            </div>
            <div>
              <div style={{ fontSize: 11, opacity: 0.7 }}>EXEMPTIONS</div>
              <div style={{ fontSize: 22, fontWeight: 700, color: '#4ade80' }}>₹{formatINR(hasBackend ? backendExempt : 0)}</div>
              <div style={{ fontSize: 9, opacity: 0.6 }}>u/s 10 + u/s 16</div>
            </div>
            <div>
              <div style={{ fontSize: 11, opacity: 0.7 }}>NET TAXABLE</div>
              <div style={{ fontSize: 22, fontWeight: 700, color: '#fbbf24' }}>₹{formatINR(hasBackend ? backendNet : 0)}</div>
              <div style={{ fontSize: 9, opacity: 0.6 }}>Income from Salary</div>
            </div>
            <div>
              <div style={{ fontSize: 11, opacity: 0.7 }}>TDS</div>
              <div style={{ fontSize: 22, fontWeight: 700 }}>₹{formatINR(hasBackend ? backendTDS : totalTDS())}</div>
              <div style={{ fontSize: 9, opacity: 0.6 }}>u/s 192</div>
            </div>
          </div>

          {/* Detailed ITD-tagged breakdown (only when backend has computed) */}
          {hasBackend && (
            <div style={{ borderTop: '1px solid rgba(255,255,255,0.2)', paddingTop: 12, fontSize: 11 }}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ opacity: 0.7 }}>17(1) Salary:</span>
                  <span>₹{formatINR(backendResult?.grossSalaryTotal ?? 0)}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ opacity: 0.7 }}>HRA Exempt 10(13A):</span>
                  <span style={{ color: '#4ade80' }}>₹{formatINR(backendResult?.hraExempt ?? 0)}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ opacity: 0.7 }}>LTA Exempt 10(5):</span>
                  <span style={{ color: '#4ade80' }}>₹{formatINR(backendResult?.ltaExempt ?? 0)}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ opacity: 0.7 }}>Gratuity 10(10):</span>
                  <span style={{ color: '#4ade80' }}>₹{formatINR(backendResult?.gratuityExempt ?? 0)}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ opacity: 0.7 }}>Leave Encash 10(10AA):</span>
                  <span style={{ color: '#4ade80' }}>₹{formatINR(backendResult?.leaveEncashmentExempt ?? 0)}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ opacity: 0.7 }}>Pension Comm 10(10A):</span>
                  <span style={{ color: '#4ade80' }}>₹{formatINR(backendResult?.pensionCommutationExempt ?? 0)}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ opacity: 0.7 }}>Std Deduction 16(ia):</span>
                  <span style={{ color: '#4ade80' }}>₹{formatINR(backendResult?.standardDeduction ?? 0)}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ opacity: 0.7 }}>Prof Tax 16(iii):</span>
                  <span style={{ color: '#4ade80' }}>₹{formatINR(backendResult?.professionalTaxDed ?? 0)}</span>
                </div>
              </div>
              {backendResult?.hraIsMetroCity !== undefined && (
                <div style={{ marginTop: 8, padding: 8, background: 'rgba(255,255,255,0.05)', borderRadius: 4, fontSize: 10 }}>
                  <strong>HRA Debug:</strong> Actual={formatINR(backendResult.hraCondition1_Actual)} |
                  Rent-10%={formatINR(backendResult.hraCondition2_RentMinus10Pct)} |
                  Metro%={formatINR(backendResult.hraCondition3_MetroPct)} |
                  City={backendResult.hraCityClassified || 'N/A'} |
                  Metro={backendResult.hraIsMetroCity ? 'Yes' : 'No'}
                </div>
              )}
            </div>
          )}

          <div style={{ fontSize: 10, marginTop: 12, textAlign: 'center', opacity: 0.6 }}>
            All values computed by SalaryScheduleComputer (CBDT-compliant). Final tax in Tax Computation tab.
          </div>
        </div>
      )}
    </div>
  );
}
