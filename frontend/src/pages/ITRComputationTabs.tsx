import { INR } from '../utils/formatters';
import { BankInterestEntryManager } from '../components/BankInterestEntryManager';
import { DividendEntryManager } from '../components/dividend/DividendEntryManager';
import { DonationEntryManager } from '../components/DonationEntryManager';
import { InterestEntryManager } from '../components/interest/InterestEntryManager';
import { WinningsManager } from '../components/winnings/WinningsManager';
import { FamilyPensionManager } from '../components/familyPension/FamilyPensionManager';
import { GiftPropertyManager } from '../components/gifts/GiftPropertyManager';
import { Section80DManager, type Section80DData } from '../components/Section80DManager';

export function BusinessTab({ formData, setFormData, taxResult }: any) {
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
          {['44AD', '44ADA', 'Regular'].map(scheme => (
            <button
              key={scheme}
              onClick={() => setFormData({ ...formData, bizPresumptive: scheme })}
              style={{
                padding: '8px 16px',
                background: formData.bizPresumptive === scheme ? 'var(--gold)' : 'var(--bg)',
                color: formData.bizPresumptive === scheme ? 'white' : 'var(--text-primary)',
                border: '1px solid var(--border)',
                borderRadius: 6,
                fontSize: 13,
                cursor: 'pointer'
              }}
            >
              {scheme}
            </button>
          ))}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 20 }}>
        <Field label="Gross Turnover/Receipts" value={formData.bizTurnover} onChange={(v: any) => setFormData({ ...formData, bizTurnover: v })} />
        {formData.bizPresumptive !== 'Regular' && (
          <Field label="Declared Income" value={formData.bizDeclared} onChange={(v: any) => setFormData({ ...formData, bizDeclared: v })} />
        )}
        {formData.bizPresumptive === 'Regular' && (
          <Field label="Net Profit from P&L" value={formData.bpNetProfit} onChange={(v: any) => setFormData({ ...formData, bpNetProfit: v })} />
        )}
        <Field label="Taxable Business Income" value={taxResult.bizIncome} computed />
      </div>

      <h4 style={{ fontSize: 13, fontWeight: 600, marginBottom: 12, color: 'var(--text-secondary)' }}>
        Brought Forward Losses - Business/Profession
      </h4>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
        <Field label="Business Loss B/F" value={formData.bfLossBusiness || 0} onChange={(v: any) => setFormData({ ...formData, bfLossBusiness: v })} />
        <Field label="Speculation Loss B/F" value={formData.bfLossSpeculation || 0} onChange={(v: any) => setFormData({ ...formData, bfLossSpeculation: v })} />
      </div>
    </div>
  );
}

export function OtherSourcesTab({ formData, setFormData, taxResult }: any) {
  // Calculate totals from 26AS
  const totalTDSFrom26AS = formData.tdsEntries ? formData.tdsEntries.reduce((sum: number, e: any) => sum + (e.tdsDeducted || 0), 0) : 0;
  const incomeBreakdown = formData.incomeBreakdown26AS || {};
  
  // Get income from 26AS breakdown
  const dividendFrom26AS = incomeBreakdown.dividendIncome || 0;
  const interestFrom26AS = incomeBreakdown.interestIncome || 0;
  const salaryFrom26AS = incomeBreakdown.salaryIncome || 0;
  
  // Calculate total income from 26AS
  const totalIncomeFrom26AS = salaryFrom26AS + dividendFrom26AS + interestFrom26AS;
  
  return (
    <div style={{ padding: '16px', background: '#fafafa' }}>
      {/* 26AS Import Summary */}
      {formData.imported26AS && (
        <div style={{ marginBottom: 24, padding: 16, background: 'var(--gold-pale)', borderRadius: 6, border: '1px solid var(--gold)' }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12, color: 'var(--gold)' }}>
            📊 Form 26AS Import Summary
          </h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 16 }}>
            <div style={{ padding: 12, background: 'white', borderRadius: 6 }}>
              <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 4 }}>Total Income (26AS)</div>
              <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-primary)' }}>₹{totalIncomeFrom26AS.toLocaleString('en-IN')}</div>
            </div>
            <div style={{ padding: 12, background: 'white', borderRadius: 6 }}>
              <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 4 }}>Total TDS Credit</div>
              <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--gold)' }}>₹{totalTDSFrom26AS.toLocaleString('en-IN')}</div>
            </div>
            <div style={{ padding: 12, background: 'white', borderRadius: 6 }}>
              <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 4 }}>Salary (192)</div>
              <div style={{ fontSize: 16, fontWeight: 600 }}>₹{salaryFrom26AS.toLocaleString('en-IN')}</div>
            </div>
            <div style={{ padding: 12, background: 'white', borderRadius: 6 }}>
              <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 4 }}>Interest (193, 194A, 194K)</div>
              <div style={{ fontSize: 16, fontWeight: 600 }}>₹{interestFrom26AS.toLocaleString('en-IN')}</div>
            </div>
            <div style={{ padding: 12, background: 'white', borderRadius: 6 }}>
              <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 4 }}>Dividends (194)</div>
              <div style={{ fontSize: 16, fontWeight: 600 }}>₹{dividendFrom26AS.toLocaleString('en-IN')}</div>
            </div>
          </div>
        </div>
      )}

      <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 20, color: '#1a237e', display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ background: '#1a237e', color: 'white', padding: '4px 10px', borderRadius: 4, fontSize: 12 }}>OS</span>
        Income from Other Sources
        <span style={{ fontSize: 11, color: '#666', fontWeight: 400 }}>Schedule OS - Sec 56-59</span>
      </h3>

      {/* ===== INTEREST INCOME (ITD Tags 17A-17H) ===== */}
      <div style={{ marginBottom: 20, background: 'white', borderRadius: 8, padding: 16, borderLeft: '4px solid #1565c0', boxShadow: '0 1px 3px rgba(0,0,0,0.08)' }}>
        <h4 style={{ fontSize: 13, fontWeight: 600, marginBottom: 12, color: '#1565c0', display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ background: '#e3f2fd', color: '#1565c0', padding: '2px 8px', borderRadius: 4, fontSize: 10 }}>17A-17H</span>
          Interest Income
          <span style={{ fontSize: 11, color: '#888', fontWeight: 400 }}>Sec 194A, 194K, 244A</span>
        </h4>
        <InterestEntryManager
          entries={formData.interestEntries || []}
          onChange={(entries) => setFormData({ ...formData, interestEntries: entries })}
        />
      </div>

      {/* DIVIDEND income section - ITD Compliant */}
      <div style={{ marginBottom: 20, background: 'white', borderRadius: 8, padding: 16, borderLeft: '4px solid #2e7d32', boxShadow: '0 1px 3px rgba(0,0,0,0.08)' }}>
        <h4 style={{ fontSize: 13, fontWeight: 600, marginBottom: 12, color: '#2e7d32', display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ background: '#e8f5e9', color: '#2e7d32', padding: '2px 8px', borderRadius: 4, fontSize: 10 }}>DIV</span>
          Dividend Income
          <span style={{ fontSize: 11, color: '#888', fontWeight: 400 }}>Sec 2(22)(e), 2(22)(f), 194</span>
        </h4>
        <DividendEntryManager
          entries={formData.dividendEntries || []}
          onChange={(entries) => setFormData({ ...formData, dividendEntries: entries })}
        />
      </div>

      {/* FAMILY PENSION section - ITD Compliant */}
      <div style={{ marginBottom: 20, background: 'white', borderRadius: 8, padding: 16, borderLeft: '4px solid #7b1fa2', boxShadow: '0 1px 3px rgba(0,0,0,0.08)' }}>
        <FamilyPensionManager
          entry={formData.familyPensionEntry || null}
          onChange={(entry) => setFormData({ ...formData, familyPensionEntry: entry })}
        />
      </div>

      {/* WINNINGS section - ITD Compliant */}
      <div style={{ marginBottom: 20, background: 'white', borderRadius: 8, padding: 16, borderLeft: '4px solid #c62828', boxShadow: '0 1px 3px rgba(0,0,0,0.08)' }}>
        <WinningsManager
          entries={formData.winningsEntries || []}
          onChange={(entries) => setFormData({ ...formData, winningsEntries: entries })}
        />
      </div>

      {/* GIFTS section - ITD Compliant */}
      <div style={{ marginBottom: 20, background: 'white', borderRadius: 8, padding: 16, borderLeft: '4px solid #ef6c00', boxShadow: '0 1px 3px rgba(0,0,0,0.08)' }}>
        <GiftPropertyManager
          entries={formData.giftEntries || []}
          onChange={(entries) => setFormData({ ...formData, giftEntries: entries })}
        />
      </div>

      {/* VDA section */}
      <div style={{ marginBottom: 20, background: 'white', borderRadius: 8, padding: 16, borderLeft: '4px solid #e65100', boxShadow: '0 1px 3px rgba(0,0,0,0.08)' }}>
        <h4 style={{ fontSize: 13, fontWeight: 600, marginBottom: 12, color: '#e65100', display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ background: '#fff3e0', color: '#e65100', padding: '2px 8px', borderRadius: 4, fontSize: 10 }}>VDA</span>
          Virtual Digital Assets
          <span style={{ fontSize: 11, color: '#888', fontWeight: 400 }}>Sec 194S / 115BBH</span>
        </h4>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
          <div>
            <label style={{ display: 'block', fontSize: 11, color: '#888', marginBottom: 4 }}>VDA Gains (₹)</label>
            <input type="number" value={formData.vdaGains || ''}
              onChange={(v: any) => setFormData({ ...formData, vdaGains: parseFloat(v.target.value) || 0 })}
              style={{ width: '100%', padding: 8, border: '1px solid var(--border)', borderRadius: 4 }} />
          </div>
          <div>
            <label style={{ display: 'block', fontSize: 11, color: '#888', marginBottom: 4 }}>VDA Tax @ 30%</label>
            <input type="number" value={taxResult.vdaTax || 0} readOnly
              style={{ width: '100%', padding: 8, border: '1px solid var(--border)', borderRadius: 4, background: '#fff3e0', color: '#e65100', fontWeight: 600 }} />
          </div>
        </div>
        <div style={{ marginTop: 8, fontSize: 11, color: '#e65100', fontStyle: 'italic' }}>
          ⚠️ VDA income taxed @ 30% + 4% cess. No loss set-off allowed.
        </div>
      </div>

      {/* ===== OTHER SOURCES SUMMARY (CBDT Schedule OS) ===== */}
      <div style={{ marginTop: 32, padding: 20, background: 'var(--bg)', borderRadius: 8, border: '1px solid var(--border)' }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 16, color: 'var(--text-secondary)', display: 'flex', alignItems: 'center' }}>
          Income from Other Sources - Summary (Backend Computed)
          <span title="Schedule OS - Sec 56-59 (Calculated by backend as per CBDT rules)" style={{ cursor: 'help', fontSize: 12, color: 'var(--gold)', border: '1px solid var(--gold)', borderRadius: '50%', width: 16, height: 16, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontWeight: 600, marginLeft: 8 }}>i</span>
        </h3>
        
        <div style={{ marginBottom: 16 }}>
          {/* Interest Income - ITD Tags 17A-17H */}
          {(taxResult.intrFrmSavingBank || taxResult.intrFrmTermDeposit || taxResult.intrFrmIncmTaxRefund || 
            taxResult.intrSec10XIFirstProviso || taxResult.intrSec10XISecondProviso || taxResult.intrSec10XIIFirstProviso) > 0 && (
            <>
              <div style={{ fontSize: 12, fontWeight: 600, color: '#1565c0', marginBottom: 8 }}>Interest Income (17A-17H)</div>
              {(taxResult.intrFrmSavingBank ?? 0) > 0 && (
                <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0' }}>
                  <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>17A - Savings Bank</span>
                  <span style={{ fontWeight: 500 }}>₹{(taxResult.intrFrmSavingBank ?? 0).toLocaleString('en-IN')}</span>
                </div>
              )}
              {(taxResult.intrFrmTermDeposit ?? 0) > 0 && (
                <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0' }}>
                  <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>17B - Term Deposit</span>
                  <span style={{ fontWeight: 500 }}>₹{(taxResult.intrFrmTermDeposit ?? 0).toLocaleString('en-IN')}</span>
                </div>
              )}
              {(taxResult.intrSec10XIFirstProviso ?? 0) > 0 && (
                <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0' }}>
                  <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>17D - Post Office</span>
                  <span style={{ fontWeight: 500 }}>₹{(taxResult.intrSec10XIFirstProviso ?? 0).toLocaleString('en-IN')}</span>
                </div>
              )}
              {(taxResult.intrSec10XISecondProviso ?? 0) > 0 && (
                <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0' }}>
                  <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>17E - NSC (Exempt)</span>
                  <span style={{ fontWeight: 500, color: '#2e7d32' }}>₹{(taxResult.intrSec10XISecondProviso ?? 0).toLocaleString('en-IN')}</span>
                </div>
              )}
              {(taxResult.intrSec10XIIFirstProviso ?? 0) > 0 && (
                <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0' }}>
                  <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>17F - SCSS (Exempt)</span>
                  <span style={{ fontWeight: 500, color: '#2e7d32' }}>₹{(taxResult.intrSec10XIIFirstProviso ?? 0).toLocaleString('en-IN')}</span>
                </div>
              )}
            </>
          )}
          
          {/* Dividend - ITD Taxable (2(22)(e), 2(22)(f), 194) */}
          {(taxResult.dividend22e || taxResult.dividend22f || taxResult.dividend) > 0 && (
            <>
              <div style={{ fontSize: 12, fontWeight: 600, color: '#2e7d32', margin: '12px 0 8px' }}>Dividend Income</div>
              {(taxResult.dividend ?? 0) > 0 && (
                <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0' }}>
                  <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>194 - Regular Dividend</span>
                  <span style={{ fontWeight: 500 }}>₹{(taxResult.dividend ?? 0).toLocaleString('en-IN')}</span>
                </div>
              )}
              {(taxResult.dividend22e ?? 0) > 0 && (
                <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0' }}>
                  <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>2(22)(e) - Deemed Dividend</span>
                  <span style={{ fontWeight: 500 }}>₹{(taxResult.dividend22e ?? 0).toLocaleString('en-IN')}</span>
                </div>
              )}
              {(taxResult.dividend22f ?? 0) > 0 && (
                <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0' }}>
                  <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>2(22)(f) - Capital Reduction</span>
                  <span style={{ fontWeight: 500 }}>₹{(taxResult.dividend22f ?? 0).toLocaleString('en-IN')}</span>
                </div>
              )}
            </>
          )}
          
          {/* Family Pension */}
          {(taxResult.familyPensionIncome ?? 0) > 0 && (
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderTop: '1px solid var(--border)', marginTop: 8 }}>
              <span style={{ color: 'var(--text-secondary)' }}>Family Pension (Gross)</span>
              <span style={{ fontWeight: 600 }}>₹{(taxResult.familyPensionIncome ?? 0).toLocaleString('en-IN')}</span>
            </div>
          )}
          {(taxResult.familyPensionDed ?? 0) > 0 && (
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0' }}>
              <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>Less: Deduction u/s 57(iia)</span>
              <span style={{ fontWeight: 500, color: '#2e7d32' }}>-₹{(taxResult.familyPensionDed ?? 0).toLocaleString('en-IN')}</span>
            </div>
          )}
          
          {/* Winnings */}
          {(taxResult.totalWinnings ?? 0) > 0 && (
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderTop: '1px solid var(--border)', marginTop: 8 }}>
              <span style={{ color: 'var(--text-secondary)' }}>Winnings (194B/194BB) @ 30%</span>
              <span style={{ fontWeight: 600 }}>₹{(taxResult.totalWinnings ?? 0).toLocaleString('en-IN')}</span>
            </div>
          )}
          
          {/* VDA */}
          {(taxResult.vdaGains ?? 0) > 0 && (
            <>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderTop: '1px solid var(--border)', marginTop: 8 }}>
                <span style={{ color: 'var(--text-secondary)' }}>VDA Gains (115BBH)</span>
                <span style={{ fontWeight: 600 }}>₹{(taxResult.vdaGains ?? 0).toLocaleString('en-IN')}</span>
              </div>
            </>
          )}
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', padding: '12px 0', borderTop: '2px solid var(--gold)', marginTop: 8 }}>
          <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>Gross Income from Other Sources</span>
          <span style={{ fontWeight: 700, fontSize: 16, color: 'var(--gold)' }}>₹{(taxResult.otherIncome ?? 0).toLocaleString('en-IN')}</span>
        </div>
        <div style={{ marginTop: 12, fontSize: 11, color: 'var(--text-muted)' }}>
          Note: Winnings (Lottery/Betting/Horse Race) and VDA are taxed at 30% + 4% cess. Family pension deduction u/s 57(iia) applied by backend.
        </div>
      </div>
    </div>
  );
}

export function VDATab({ formData, setFormData, taxResult }: any) {
  return (
    <div>
      <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 16, color: 'var(--text-secondary)' }}>
        Virtual Digital Assets (VDA) - Section 115BBH
      </h3>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
        <Field label="Net VDA Gains" value={formData.vdaGains} onChange={(v: any) => setFormData({ ...formData, vdaGains: v })} />
        <Field label="VDA Tax @ 30%" value={taxResult.vdaTax} computed />
      </div>
      <div style={{ marginTop: 12, padding: 12, background: 'var(--info-bg)', borderRadius: 6, fontSize: 12, color: 'var(--info)' }}>
        No loss set-off allowed for VDA transactions as per CBDT rules
      </div>
    </div>
  );
}

export function DeductionsTab({ formData, setFormData, regime, taxResult }: any) {
  if (regime === 'new') {
    return (
      <div style={{ padding: 24, textAlign: 'center', color: 'var(--text-muted)' }}>
        No deductions available in New Regime (except 80CCD(2) - employer NPS contribution as per CBDT)
        <div style={{ marginTop: 16 }}>
          <Field label="80CCD(2) - Employer NPS" value={formData.s80CCD2} onChange={(v: any) => setFormData({ ...formData, s80CCD2: v })} />
        </div>
      </div>
    );
  }

  return (
    <div>
      <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 16, color: 'var(--text-secondary)' }}>
        Deductions under Chapter VI-A (CBDT Schedule VIA)
      </h3>
      <h4 style={{ fontSize: 13, fontWeight: 600, marginBottom: 12, color: 'var(--text-secondary)' }}>Section 80C (Max 1.5L)</h4>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 24 }}>
        <Field label="EPF" value={formData.s80C_epf} onChange={(v: any) => setFormData({ ...formData, s80C_epf: v })} />
        <Field label="PPF" value={formData.s80C_ppf} onChange={(v: any) => setFormData({ ...formData, s80C_ppf: v })} />
        <Field label="PPF Account No" value={formData.s80C_ppfAccNo || ''} onChange={(v: any) => setFormData({ ...formData, s80C_ppfAccNo: v })} type="text" prefix="" />
        <Field label="ELSS" value={formData.s80C_elss} onChange={(v: any) => setFormData({ ...formData, s80C_elss: v })} />
        <Field label="LIC Premium" value={formData.s80C_lic} onChange={(v: any) => setFormData({ ...formData, s80C_lic: v })} />
        <Field label="LIC Policy No" value={formData.s80C_licPolicyNo || ''} onChange={(v: any) => setFormData({ ...formData, s80C_licPolicyNo: v })} type="text" prefix="" />
        <Field label="Home Loan Principal" value={formData.s80C_home} onChange={(v: any) => setFormData({ ...formData, s80C_home: v })} />
        <Field label="Lender Name" value={formData.s80C_homeLenderName || ''} onChange={(v: any) => setFormData({ ...formData, s80C_homeLenderName: v })} type="text" prefix="" />
      </div>

      <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 16, color: 'var(--text-secondary)' }}>NPS</h3>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 24 }}>
        <Field label="80CCD(1B) - Max ₹50K" value={formData.s80CCD1B} onChange={(v: any) => setFormData({ ...formData, s80CCD1B: v })} />
        <Field label="NPS PRAN" value={formData.s80CCD1B_PRAN || ''} onChange={(v: any) => setFormData({ ...formData, s80CCD1B_PRAN: v })} type="text" prefix="" />
        <Field label="80CCD(2) - Employer" value={formData.s80CCD2} onChange={(v: any) => setFormData({ ...formData, s80CCD2: v })} />
      </div>

      <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 16, color: "var(--text-secondary)" }}>Health Insurance (80D)</h3>
      <Section80DManager
        data={formData.section80D || {
          selfSeniorCitizen: "N", parentsSeniorCitizen: "N",
          selfFamily: { policies: [], preventiveCheckup: 0, medicalExpense: 0 },
          selfFamilySenior: { policies: [], preventiveCheckup: 0, medicalExpense: 0 },
          parents: { policies: [], preventiveCheckup: 0, medicalExpense: 0 },
          parentsSenior: { policies: [], preventiveCheckup: 0, medicalExpense: 0 },
        }}
        onChange={(d) => setFormData({ ...formData, section80D: d })}
      />

      Donations (80G)</h3>
      
      {/* Donation Multi-Entry Manager */}
      <DonationEntryManager
        entries={formData.donationEntries || []}
        onChange={(entries) => setFormData({ ...formData, donationEntries: entries })}
      />
      
      <div style={{ marginTop: 24 }}>
        <h4 style={{ fontSize: 13, fontWeight: 600, marginBottom: 12, color: 'var(--text-secondary)' }}>
          Legacy Single-Value Field (Use multi-entry above for CBDT compliance)
        </h4>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 24 }}>
          <Field label="Donation Amount" value={formData.s80G} onChange={(v: any) => setFormData({ ...formData, s80G: v })} />
          <Field label="Donee Name" value={formData.s80G_doneeName || ''} onChange={(v: any) => setFormData({ ...formData, s80G_doneeName: v })} type="text" prefix="" />
          <Field label="Donee PAN" value={formData.s80G_doneePAN || ''} onChange={(v: any) => setFormData({ ...formData, s80G_doneePAN: v })} type="text" prefix="" />
          <Field label="Receipt No" value={formData.s80G_receiptNo || ''} onChange={(v: any) => setFormData({ ...formData, s80G_receiptNo: v })} type="text" prefix="" />
        </div>
      </div>

      <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 16, color: 'var(--text-secondary)' }}>Others</h3>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
        <Field label="80E - Education Loan" value={formData.s80E} onChange={(v: any) => setFormData({ ...formData, s80E: v })} />
        <Field label="Lender Name" value={formData.s80E_lenderName || ''} onChange={(v: any) => setFormData({ ...formData, s80E_lenderName: v })} type="text" prefix="" />
        <Field label="80TTA - SB Interest (Max ₹10K)" value={formData.s80TTA} onChange={(v: any) => setFormData({ ...formData, s80TTA: v })} />
        <Field label="Total Deductions" value={taxResult.totalDeductions} computed />
      </div>
    </div>
  );
}

export function LossesTab({ formData, setFormData }: any) {
  // Current year HP loss from House Property section (auto-calculated, capped at -₹2L)
  const currentYearHpLoss = (formData.incomeFromHouseProperty || 0) < 0 
    ? Math.min((formData.incomeFromHouseProperty || 0), -200000) 
    : 0;
  
  // Past year HP loss brought forward (manual entry for losses from previous years)
  const pastYearHpLoss = formData.bfLossHP || 0;
  
  // Total HP loss available for set-off = current year + past year brought forward
  const totalHpLossForSetoff = currentYearHpLoss + pastYearHpLoss;
  
  // Amount used for set-off (max ₹2L)
  const lossUsedForSetoff = Math.min(Math.abs(totalHpLossForSetoff), 200000);
  
  // Excess loss to be carried forward to future years
  const lossCarriedForward = Math.abs(totalHpLossForSetoff) > 200000 
    ? Math.abs(totalHpLossForSetoff) - 200000 
    : 0;
  
  return (
    <div>
      <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 16, color: 'var(--text-secondary)' }}>
        Brought Forward Losses (CBDT Schedule CYLA)
      </h3>
      
      {/* Current Year HP Loss - Auto Calculated - Read Only */}
      <div style={{ marginBottom: 16, padding: 12, background: currentYearHpLoss < 0 ? 'var(--error-bg)' : 'var(--success-bg)', borderRadius: 6 }}>
        <div style={{ fontSize: 12, fontWeight: 600, color: currentYearHpLoss < 0 ? 'var(--error)' : 'var(--success)' }}>
          Current Year HP Loss (Auto from HP tab): ₹{currentYearHpLoss.toLocaleString('en-IN')}
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
            value={formData.bfLossHP || 0} 
            onChange={(v: any) => setFormData({ ...formData, bfLossHP: v })} 
          />
        </div>
        <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 6 }}>
          Enter HP losses from previous year that couldn't be fully set off. Maximum 8 years can be carried forward.
        </div>
      </div>
      
      {/* Summary of Set-off */}
      {totalHpLossForSetoff !== 0 && (
        <div style={{ marginBottom: 16, padding: 12, background: 'var(--gold-pale)', borderRadius: 6, border: '1px solid var(--gold)' }}>
          <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 8, color: 'var(--text-secondary)' }}>
            HP Loss Set-off Summary
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
            <div>Total HP Loss available: ₹{Math.abs(totalHpLossForSetoff).toLocaleString('en-IN')}</div>
            <div>Already used this year: ₹{lossUsedForSetoff.toLocaleString('en-IN')}</div>
            {lossCarriedForward > 0 && (
              <div style={{ color: 'var(--error)', fontWeight: 600 }}>
                Carried Forward to Future Years: ₹{lossCarriedForward.toLocaleString('en-IN')}
                <span style={{ fontWeight: 400, fontSize: 11 }}> (can be used for next 8 years)</span>
              </div>
            )}
          </div>
        </div>
      )}
      
      {/* Other Losses - Manual Entry */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 24 }}>
        <Field label="Business Loss B/F" value={formData.bfLossBusiness || 0} onChange={(v: any) => setFormData({ ...formData, bfLossBusiness: v })} />
        <Field label="Speculation Loss B/F" value={formData.bfLossSpeculation || 0} onChange={(v: any) => setFormData({ ...formData, bfLossSpeculation: v })} />
        <Field label="Short Term Capital Loss B/F" value={formData.bfLossSTCG || 0} onChange={(v: any) => setFormData({ ...formData, bfLossSTCG: v })} />
        <Field label="Long Term Capital Loss B/F" value={formData.bfLossLTCG || 0} onChange={(v: any) => setFormData({ ...formData, bfLossLTCG: v })} />
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

export function TDSTab({ formData, setFormData, taxResult }: any) {
  const tdsEntries = formData.tdsEntries || [];
  const selfAssessmentTaxEntries = formData.selfAssessmentTaxEntries || [];

  const addTDSEntry = () => {
    const newEntry = {
      section: '192',
      deductorName: '',
      deductorTAN: '',
      deductorPAN: '',
      incomeAmount: 0,
      tdsDeducted: 0,
      certificateNo: '',
      deductionDate: '',
      uniqueTransactionNo: '',
      financialYear: '2024-25',
      verified26AS: false,
      claimedInReturn: true
    };
    setFormData({ ...formData, tdsEntries: [...tdsEntries, newEntry] });
  };

  const updateTDSEntry = (index: number, field: string, value: any) => {
    const updated = [...tdsEntries];
    updated[index] = { ...updated[index], [field]: value };
    setFormData({ ...formData, tdsEntries: updated });
  };

  const removeTDSEntry = (index: number) => {
    const updated = tdsEntries.filter((_: any, i: number) => i !== index);
    setFormData({ ...formData, tdsEntries: updated });
  };

  const addSelfAssessmentEntry = () => {
    const newEntry = {
      bsrCode: '',
      challanNo: '',
      depositDate: '',
      amount: 0,
      cin: ''
    };
    setFormData({ ...formData, selfAssessmentTaxEntries: [...selfAssessmentTaxEntries, newEntry] });
  };

  const updateSelfAssessmentEntry = (index: number, field: string, value: any) => {
    const updated = [...selfAssessmentTaxEntries];
    updated[index] = { ...updated[index], [field]: value };
    setFormData({ ...formData, selfAssessmentTaxEntries: updated });
  };

  const removeSelfAssessmentEntry = (index: number) => {
    const updated = selfAssessmentTaxEntries.filter((_: any, i: number) => i !== index);
    setFormData({ ...formData, selfAssessmentTaxEntries: updated });
  };

  return (
    <div>
      {/* Auto-populated TDS entries from AIS/26AS */}
      {(formData.aisImported || formData.imported26AS) && (
        <div style={{ marginBottom: 24, padding: 16, background: 'var(--success-bg)', borderRadius: 6, border: '1px solid var(--success)' }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12, color: 'var(--success)' }}>
            ✓ 26AS Data Imported
          </h3>
          <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
            TDS entries have been auto-populated from Form 26AS. 
            {formData.imported26AS && `Found ${(formData.tdsEntries || []).length} deductor(s) with total TDS of ₹${((formData.imported26AS || {}).totalTDS || 0).toLocaleString('en-IN')}.`}
            Review and update if needed.
          </div>
        </div>
      )}

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
            <Field label="Deductor TAN *" value={entry.deductorTAN || ''} onChange={(v: any) => updateTDSEntry(index, 'deductorTAN', v)} type="text" prefix="" required />
            <Field label="Deductor PAN" value={entry.deductorPAN || ''} onChange={(v: any) => updateTDSEntry(index, 'deductorPAN', v)} type="text" prefix="" />
            <Field label="Income Amount *" value={entry.incomeAmount || 0} onChange={(v: any) => updateTDSEntry(index, 'incomeAmount', v)} required />
            <Field label="TDS Deducted *" value={entry.tdsDeducted || 0} onChange={(v: any) => updateTDSEntry(index, 'tdsDeducted', v)} required />
            <Field label="Certificate No *" value={entry.certificateNo || ''} onChange={(v: any) => updateTDSEntry(index, 'certificateNo', v)} type="text" prefix="" required />
            <Field label="Deduction Date *" value={entry.deductionDate || ''} onChange={(v: any) => updateTDSEntry(index, 'deductionDate', v)} type="date" prefix="" required />
            <Field label="Unique Transaction No" value={entry.uniqueTransactionNo || ''} onChange={(v: any) => updateTDSEntry(index, 'uniqueTransactionNo', v)} type="text" prefix="" />
            <Field label="Financial Year *" value={entry.financialYear || '2024-25'} onChange={(v: any) => updateTDSEntry(index, 'financialYear', v)} type="text" prefix="" required />
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

      <h3 style={{ fontSize: 14, fontWeight: 600, marginTop: 32, marginBottom: 16, color: 'var(--text-secondary)' }}>
        Advance Tax Payments
      </h3>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 24 }}>
        <Field label="15-Jun" value={formData.adv15Jun || 0} onChange={(v: any) => setFormData({ ...formData, adv15Jun: v })} />
        <Field label="15-Sep" value={formData.adv15Sep || 0} onChange={(v: any) => setFormData({ ...formData, adv15Sep: v })} />
        <Field label="15-Dec" value={formData.adv15Dec || 0} onChange={(v: any) => setFormData({ ...formData, adv15Dec: v })} />
        <Field label="15-Mar" value={formData.adv15Mar || 0} onChange={(v: any) => setFormData({ ...formData, adv15Mar: v })} />
      </div>

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
            <Field label="BSR Code *" value={entry.bsrCode || ''} onChange={(v: any) => updateSelfAssessmentEntry(index, 'bsrCode', v)} type="text" prefix="" required />
            <Field label="Challan Serial No *" value={entry.challanNo || ''} onChange={(v: any) => updateSelfAssessmentEntry(index, 'challanNo', v)} type="text" prefix="" required />
            <Field label="Date of Deposit *" value={entry.depositDate || ''} onChange={(v: any) => updateSelfAssessmentEntry(index, 'depositDate', v)} type="date" prefix="" required />
            <Field label="Amount *" value={entry.amount || 0} onChange={(v: any) => updateSelfAssessmentEntry(index, 'amount', v)} required />
            <Field label="CIN (Challan ID) *" value={entry.cin || ''} onChange={(v: any) => updateSelfAssessmentEntry(index, 'cin', v)} type="text" prefix="" required />
          </div>
        </div>
      ))}

      <div style={{ marginTop: 24, padding: 16, background: 'var(--gold-pale)', borderRadius: 6 }}>
        <Field label="Total Tax Paid" value={taxResult.totalTaxPaid} computed />
      </div>
    </div>
  );
}

export function TaxComputationTab({ taxResult, regime, itrForm }: any) {
  return (
    <div style={{ maxWidth: 800, margin: '0 auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <tbody>
          <tr style={{ background: 'var(--bg)' }}>
            <td colSpan={2} style={{ padding: '8px 12px', fontWeight: 600, fontSize: 13 }}>Income Summary</td>
          </tr>
          {taxResult.netSalary > 0 && (
            <tr>
              <td style={{ padding: '8px 12px', fontSize: 13 }}>Salary (Net Taxable)</td>
              <td className="mono" style={{ padding: '8px 12px', fontSize: 13, textAlign: 'right' }}>{INR(taxResult.netSalary)}</td>
            </tr>
          )}
          {taxResult.hpIncome !== 0 && (
            <tr>
              <td style={{ padding: '8px 12px', fontSize: 13 }}>House Property Income</td>
              <td className="mono" style={{ padding: '8px 12px', fontSize: 13, textAlign: 'right' }}>{INR(taxResult.hpIncome)}</td>
            </tr>
          )}
          {taxResult.bizIncome > 0 && (
            <tr>
              <td style={{ padding: '8px 12px', fontSize: 13 }}>Business Income</td>
              <td className="mono" style={{ padding: '8px 12px', fontSize: 13, textAlign: 'right' }}>{INR(taxResult.bizIncome)}</td>
            </tr>
          )}
          {taxResult.otherIncome > 0 && (
            <tr>
              <td style={{ padding: '8px 12px', fontSize: 13 }}>Other Sources</td>
              <td className="mono" style={{ padding: '8px 12px', fontSize: 13, textAlign: 'right' }}>{INR(taxResult.otherIncome)}</td>
            </tr>
          )}
          {taxResult.vdaGains > 0 && (
            <tr>
              <td style={{ padding: '8px 12px', fontSize: 13 }}>VDA Income</td>
              <td className="mono" style={{ padding: '8px 12px', fontSize: 13, textAlign: 'right' }}>{INR(taxResult.vdaGains)}</td>
            </tr>
          )}
          <tr style={{ borderTop: '2px solid var(--border)' }}>
            <td style={{ padding: '8px 12px', fontSize: 13, fontWeight: 600 }}>Gross Total Income (GTI)</td>
            <td className="mono" style={{ padding: '8px 12px', fontSize: 13, textAlign: 'right', fontWeight: 600 }}>{INR(taxResult.gti)}</td>
          </tr>
          {(taxResult.gti - taxResult.gtiAfterSetOff) > 0 && itrForm !== 'ITR-1' && (
            <>
              <tr>
                <td style={{ padding: '8px 12px', fontSize: 13 }}>Less: B/F Loss</td>
                <td className="mono" style={{ padding: '8px 12px', fontSize: 13, textAlign: 'right', color: 'var(--danger)' }}>({INR(taxResult.gti - taxResult.gtiAfterSetOff)})</td>
              </tr>
              <tr>
                <td style={{ padding: '8px 12px', fontSize: 13, fontWeight: 600 }}>GTI After Set-offs</td>
                <td className="mono" style={{ padding: '8px 12px', fontSize: 13, textAlign: 'right', fontWeight: 600 }}>{INR(taxResult.gtiAfterSetOff)}</td>
              </tr>
            </>
          )}
          {regime === 'old' && taxResult.totalDeductions > 0 && (
            <tr>
              <td style={{ padding: '8px 12px', fontSize: 13 }}>Less: Total Deductions</td>
              <td className="mono" style={{ padding: '8px 12px', fontSize: 13, textAlign: 'right', color: 'var(--danger)' }}>({INR(taxResult.totalDeductions)})</td>
            </tr>
          )}
          <tr style={{ borderTop: '2px solid var(--border)', background: 'var(--gold-pale)' }}>
            <td style={{ padding: '8px 12px', fontSize: 14, fontWeight: 600 }}>Total Taxable Income</td>
            <td className="mono" style={{ padding: '8px 12px', fontSize: 14, textAlign: 'right', fontWeight: 600 }}>{INR(taxResult.totalIncome)}</td>
          </tr>
          <tr style={{ borderTop: '2px solid var(--border)', background: 'var(--bg)' }}>
            <td colSpan={2} style={{ padding: '8px 12px', fontWeight: 600, fontSize: 13 }}>Tax Calculation</td>
          </tr>
          <tr>
            <td style={{ padding: '8px 12px', fontSize: 13 }}>Tax on Normal Income</td>
            <td className="mono" style={{ padding: '8px 12px', fontSize: 13, textAlign: 'right' }}>{INR(taxResult.normalTax)}</td>
          </tr>
          {taxResult.rebate87A > 0 && (
            <tr>
              <td style={{ padding: '8px 12px', fontSize: 13, paddingLeft: '24px' }}>Less: Rebate u/s 87A</td>
              <td className="mono" style={{ padding: '8px 12px', fontSize: 13, textAlign: 'right', color: 'var(--success)' }}>({INR(taxResult.rebate87A)})</td>
            </tr>
          )}
          {taxResult.surcharge > 0 && (
            <tr>
              <td style={{ padding: '8px 12px', fontSize: 13 }}>Surcharge</td>
              <td className="mono" style={{ padding: '8px 12px', fontSize: 13, textAlign: 'right' }}>{INR(taxResult.surcharge)}</td>
            </tr>
          )}
          <tr>
            <td style={{ padding: '8px 12px', fontSize: 13 }}>Health & Education Cess (4%)</td>
            <td className="mono" style={{ padding: '8px 12px', fontSize: 13, textAlign: 'right' }}>{INR(taxResult.cess)}</td>
          </tr>
          <tr>
            <td style={{ padding: '8px 12px', fontSize: 13 }}>VDA Tax @ 30%</td>
            <td className="mono" style={{ padding: '8px 12px', fontSize: 13, textAlign: 'right' }}>{INR(taxResult.vdaTax)}</td>
          </tr>
          <tr>
            <td style={{ padding: '8px 12px', fontSize: 13 }}>Capital Gains Tax (Special)</td>
            <td className="mono" style={{ padding: '8px 12px', fontSize: 13, textAlign: 'right' }}>{INR(taxResult.cgTax)}</td>
          </tr>
          <tr style={{ borderTop: '2px solid var(--border)', background: 'var(--navy)' }}>
            <td style={{ padding: '12px', fontSize: 15, fontWeight: 600, color: 'white' }}>TOTAL TAX LIABILITY</td>
            <td className="mono" style={{ padding: '12px', fontSize: 15, textAlign: 'right', fontWeight: 600, color: 'white' }}>{INR(taxResult.totalTaxLiability)}</td>
          </tr>
          <tr style={{ background: 'var(--bg)' }}>
            <td colSpan={2} style={{ padding: '8px 12px', fontWeight: 600, fontSize: 13 }}>Less: Tax Payments</td>
          </tr>
          <tr>
            <td style={{ padding: '8px 12px', fontSize: 13, paddingLeft: '24px' }}>TDS Deducted ({(taxResult.tdsEntries || []).filter((e: any) => e.claimedInReturn !== false).length} entries)</td>
            <td className="mono" style={{ padding: '8px 12px', fontSize: 13, textAlign: 'right', color: 'var(--success)' }}>({INR((taxResult.tdsEntries || []).reduce((sum: number, e: any) => sum + (e.claimedInReturn !== false ? (e.tdsDeducted || 0) : 0), 0) || ((taxResult.tdsS192 || 0) + (taxResult.tds194A || 0) + (taxResult.tdsOther || 0)))})</td>
          </tr>
          <tr>
            <td style={{ padding: '8px 12px', fontSize: 13, paddingLeft: '24px' }}>Advance Tax Paid</td>
            <td className="mono" style={{ padding: '8px 12px', fontSize: 13, textAlign: 'right', color: 'var(--success)' }}>({INR((taxResult.adv15Jun || 0) + (taxResult.adv15Sep || 0) + (taxResult.adv15Dec || 0) + (taxResult.adv15Mar || 0))})</td>
          </tr>
          <tr>
            <td style={{ padding: '8px 12px', fontSize: 13, paddingLeft: '24px' }}>Self Assessment Tax ({(taxResult.selfAssessmentTaxEntries || []).length} entries)</td>
            <td className="mono" style={{ padding: '8px 12px', fontSize: 13, textAlign: 'right', color: 'var(--success)' }}>({INR((taxResult.selfAssessmentTaxEntries || []).reduce((sum: number, e: any) => sum + (e.amount || 0), 0) || (taxResult.selfTax || 0))})</td>
          </tr>
          <tr style={{ borderTop: '1px solid var(--border)' }}>
            <td style={{ padding: '8px 12px', fontSize: 13, fontWeight: 600 }}>Total Tax Paid</td>
            <td className="mono" style={{ padding: '8px 12px', fontSize: 13, textAlign: 'right', fontWeight: 600, color: 'var(--success)' }}>({INR(taxResult.totalTaxPaid)})</td>
          </tr>
          <tr style={{ borderTop: '2px solid var(--border)', background: taxResult.taxPayable > 0 ? 'var(--danger-bg)' : 'var(--success-bg)' }}>
            <td style={{ padding: '12px', fontSize: 15, fontWeight: 600, color: taxResult.taxPayable > 0 ? 'var(--danger)' : 'var(--success)' }}>
              {taxResult.taxPayable > 0 ? 'TAX PAYABLE' : 'REFUND'}
            </td>
            <td className="mono" style={{ padding: '12px', fontSize: 15, textAlign: 'right', fontWeight: 600, color: taxResult.taxPayable > 0 ? 'var(--danger)' : 'var(--success)' }}>
              {INR(taxResult.taxPayable > 0 ? taxResult.taxPayable : taxResult.refund)}
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
