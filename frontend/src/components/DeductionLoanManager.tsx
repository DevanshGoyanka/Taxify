// Deduction Loan Manager — CBDT AY 2026-27 COMPLIANT
// Covers Sections 80E, 80EE, 80EEA, 80EEB
// Each section requires per-loan detail arrays with:
//   - LoanTknFrom (B=Bank, I=Institution)
//   - BankOrInstnName (max 125)
//   - LoanAccNoOfBankOrInstnRefNo (max 20, alphanumeric)
//   - DateofLoan (YYYY-MM-DD)
//   - TotalLoanAmt
//   - LoanOutstndngAmt
//   - Interest field (section-specific name)
//   - 80EEA: PropStmpDtyVal (max ₹45L) at section level
//   - 80EEB: VehicleRegNo (max 11) per loan
//
// UI style matches DonationEntryManager: collapsible cards with category badges.

import React, { useState, useMemo } from 'react';

// ---- Per-loan entry ----
interface LoanEntry {
  id: string;
  loanTakenFrom: 'B' | 'I';    // B=Bank, I=Institution
  bankOrInstnName: string;       // max 125, required
  loanAccNo: string;             // max 20, alphanumeric, required
  dateOfLoan: string;            // YYYY-MM-DD, required
  totalLoanAmt: number;          // required
  loanOutstandingAmt: number;    // required
  interestAmount: number;        // required (section-specific name)
  vehicleRegNo?: string;          // 80EEB only, max 11
}

// ---- Section config ----
type SectionKey = '80E' | '80EE' | '80EEA' | '80EEB';

interface SectionConfig {
  key: SectionKey;
  label: string;
  shortLabel: string;
  color: string;
  interestLabel: string;
  interestField: string;
  capLabel: string;
  showStampDuty: boolean;
  showVehicleReg: boolean;
}

const SECTIONS: SectionConfig[] = [
  { key: '80E', label: 'Section 80E — Education Loan Interest', shortLabel: '80E', color: '#1565c0', interestLabel: 'Interest Paid on Loan', interestField: 'interest80E', capLabel: 'No aggregate cap (8 years or interest cap)', showStampDuty: false, showVehicleReg: false },
  { key: '80EE', label: 'Section 80EE — First Home Buyer (₹35L loan)', shortLabel: '80EE', color: '#2e7d32', interestLabel: 'Interest Paid on Loan', interestField: 'interest80EE', capLabel: 'Max ₹2L/year, loan ≤ ₹35L', showStampDuty: false, showVehicleReg: false },
  { key: '80EEA', label: 'Section 80EEA — Affordable Housing (₹45L stamp duty)', shortLabel: '80EEA', color: '#ef6c00', interestLabel: 'Interest Paid on Loan', interestField: 'interest80EEA', capLabel: 'Max ₹1.5L/year, stamp duty ≤ ₹45L', showStampDuty: true, showVehicleReg: false },
  { key: '80EEB', label: 'Section 80EEB — Electric Vehicle Loan Interest', shortLabel: '80EEB', color: '#6a1b9a', interestLabel: 'Interest Paid on Loan', interestField: 'interest80EEB', capLabel: 'Max ₹1.5L/year', showStampDuty: false, showVehicleReg: true },
];

// ---- Top-level form data ----
export interface DeductionLoanData {
  section80E: { loans: LoanEntry[] };
  section80EE: { loans: LoanEntry[] };
  section80EEA: { loans: LoanEntry[]; stampDutyValue: number };
  section80EEB: { loans: LoanEntry[] };
}

interface DeductionLoanManagerProps {
  data: DeductionLoanData;
  onChange: (data: DeductionLoanData) => void;
}

let _loanIdCounter = 1;
const nextLoanId = (): string => `loan-${Date.now()}-${_loanIdCounter++}`;

const newLoan = (): LoanEntry => ({
  id: nextLoanId(), loanTakenFrom: 'B', bankOrInstnName: '', loanAccNo: '',
  dateOfLoan: '', totalLoanAmt: 0, loanOutstandingAmt: 0, interestAmount: 0,
});

const sectionKeyToDataKey: Record<SectionKey, string> = {
  '80E': 'section80E',
  '80EE': 'section80EE',
  '80EEA': 'section80EEA',
  '80EEB': 'section80EEB',
};

// ---- Shared styles ----
const labelStyle: React.CSSProperties = {
  display: 'block', marginBottom: 3, fontSize: 11, fontWeight: 600, color: '#555',
};
const inputStyle: React.CSSProperties = {
  width: '100%', padding: '6px 8px', border: '1px solid #ddd', borderRadius: 4,
  fontSize: 12, boxSizing: 'border-box',
};

export const DeductionLoanManager: React.FC<DeductionLoanManagerProps> = ({ data, onChange }) => {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [activeSection, setActiveSection] = useState<SectionKey>('80E');

  const getLoans = (key: SectionKey): LoanEntry[] => {
    const d = data[sectionKeyToDataKey[key]] as any;
    return d?.loans || [];
  };

  const setLoans = (key: SectionKey, loans: LoanEntry[]) => {
    const d = { ...data };
    (d as any)[sectionKeyToDataKey[key]] = { ...(d as any)[sectionKeyToDataKey[key]], loans };
    onChange(d);
  };

  const addLoan = (key: SectionKey) => {
    const loan = newLoan();
    setLoans(key, [...getLoans(key), loan]);
    setExpandedId(loan.id);
  };

  const removeLoan = (key: SectionKey, id: string) => {
    setLoans(key, getLoans(key).filter(l => l.id !== id));
    if (expandedId === id) setExpandedId(null);
  };

  const updateLoan = (key: SectionKey, id: string, field: keyof LoanEntry, value: unknown) => {
    setLoans(key, getLoans(key).map(l => l.id === id ? { ...l, [field]: value } : l));
  };

  const toggleExpand = (id: string) => {
    setExpandedId(expandedId === id ? null : id);
  };

  // Grand totals per section
  const sectionTotals = useMemo(() => {
    const totals: Record<SectionKey, { totalLoan: number; totalOutstanding: number; totalInterest: number }> = {
      '80E': { totalLoan: 0, totalOutstanding: 0, totalInterest: 0 },
      '80EE': { totalLoan: 0, totalOutstanding: 0, totalInterest: 0 },
      '80EEA': { totalLoan: 0, totalOutstanding: 0, totalInterest: 0 },
      '80EEB': { totalLoan: 0, totalOutstanding: 0, totalInterest: 0 },
    };
    for (const sec of SECTIONS) {
      for (const l of getLoans(sec.key)) {
        totals[sec.key].totalLoan += l.totalLoanAmt;
        totals[sec.key].totalOutstanding += l.loanOutstandingAmt;
        totals[sec.key].totalInterest += l.interestAmount;
      }
    }
    return totals;
  }, [data]);

  return (
    <div style={{ fontFamily: 'system-ui, sans-serif' }}>
      {/* Section tabs */}
      <div style={{ display: 'flex', gap: 0, marginBottom: 16, borderRadius: 6, overflow: 'hidden', border: '1px solid #ddd' }}>
        {SECTIONS.map(sec => {
          const loans = getLoans(sec.key);
          const isActive = activeSection === sec.key;
          return (
            <button key={sec.key} onClick={() => setActiveSection(sec.key)} style={{
              flex: 1, padding: '8px 4px', border: 'none', cursor: 'pointer',
              background: isActive ? sec.color : '#f5f5f5',
              color: isActive ? 'white' : '#666', fontSize: 12, fontWeight: isActive ? 700 : 500,
              borderBottom: isActive ? 'none' : '1px solid #ddd',
              position: 'relative',
            }}>
              {sec.shortLabel}
              {loans.length > 0 && (
                <span style={{ marginLeft: 4, background: isActive ? 'rgba(255,255,255,0.3)' : sec.color, color: isActive ? 'white' : 'white', borderRadius: 8, padding: '1px 6px', fontSize: 10 }}>
                  {loans.length}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Active section */}
      {SECTIONS.filter(s => s.key === activeSection).map(sec => {
        const loans = getLoans(sec.key);
        const totals = sectionTotals[sec.key];

        return (
          <div key={sec.key}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <div>
                <span style={{ background: sec.color, color: 'white', fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 3, marginRight: 8 }}>{sec.shortLabel}</span>
                <span style={{ fontSize: 13, fontWeight: 600 }}>{sec.label}</span>
              </div>
              <button onClick={() => addLoan(sec.key)} style={{
                background: sec.color, color: 'white', border: 'none', padding: '6px 14px', borderRadius: 4, cursor: 'pointer', fontSize: 12, fontWeight: 600,
              }}>
                + Add Loan
              </button>
            </div>

            <p style={{ margin: '0 0 12px', fontSize: 11, color: '#666' }}>{sec.capLabel}</p>

            {/* 80EEA stamp duty */}
            {sec.showStampDuty && (
              <div style={{ marginBottom: 12, padding: 12, background: '#fff8e1', borderRadius: 6, border: '1px solid #ffe082' }}>
                <label style={{ ...labelStyle, color: '#e65100' }}>Stamp Duty Value of Property (max ₹45,00,000)</label>
                <input type="number" value={data.section80EEA.stampDutyValue || ''}
                  onChange={e => onChange({ ...data, section80EEA: { ...data.section80EEA, stampDutyValue: parseFloat(e.target.value) || 0 } })}
                  placeholder="0" min={0} max={4500000}
                  style={{ ...inputStyle, maxWidth: 300 }} />
                <span style={{ fontSize: 10, color: '#888', marginLeft: 8 }}>Required for 80EEA eligibility</span>
              </div>
            )}

            {/* Empty state */}
            {loans.length === 0 && (
              <div style={{ textAlign: 'center', padding: 30, color: '#999', background: '#fafafa', borderRadius: 8, border: '1px dashed #ddd' }}>
                <div style={{ fontSize: 28, marginBottom: 8 }}>🏦</div>
                <div style={{ fontSize: 13 }}>No loans added for {sec.shortLabel}.</div>
                <div style={{ fontSize: 11, marginTop: 4 }}>Click "+ Add Loan" to add loan details.</div>
              </div>
            )}

            {/* Loan cards */}
            {loans.map((loan) => {
              const isExpanded = expandedId === loan.id;
              return (
                <div key={loan.id} style={{
                  background: 'white', border: `1px solid ${isExpanded ? sec.color : '#e0e0e0'}`,
                  borderLeft: `4px solid ${sec.color}`, borderRadius: 6, marginBottom: 8, overflow: 'hidden',
                }}>
                  {/* Collapsed summary */}
                  <div onClick={() => toggleExpand(loan.id)} style={{
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    padding: '8px 12px', cursor: 'pointer', userSelect: 'none',
                    background: isExpanded ? `${sec.color}06` : 'white',
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1, minWidth: 0 }}>
                      <span style={{ background: loan.loanTakenFrom === 'B' ? '#1565c0' : '#ff9800', color: 'white', fontSize: 10, fontWeight: 700, padding: '2px 6px', borderRadius: 3 }}>
                        {loan.loanTakenFrom === 'B' ? 'BANK' : 'INST'}
                      </span>
                      <span style={{ fontSize: 13, fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {loan.bankOrInstnName || '(Unnamed Lender)'}
                      </span>
                      {loan.loanAccNo && <span style={{ fontSize: 11, color: '#888', fontFamily: 'monospace' }}>{loan.loanAccNo}</span>}
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
                      <span style={{ fontSize: 12, color: '#666' }}>₹{(loan.totalLoanAmt || 0).toLocaleString('en-IN')}</span>
                      <span style={{ fontSize: 14, color: '#999', transform: isExpanded ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }}>▾</span>
                      <button onClick={(ev) => { ev.stopPropagation(); removeLoan(sec.key, loan.id); }} style={{
                        background: 'transparent', border: 'none', color: '#f44336', fontSize: 16, cursor: 'pointer', padding: '0 2px', lineHeight: 1,
                      }}>×</button>
                    </div>
                  </div>

                  {/* Expanded detail */}
                  {isExpanded && (
                    <div style={{ padding: '12px 14px', borderTop: '1px solid #eee' }}>
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 10, marginBottom: 12 }}>
                        <div>
                          <label style={labelStyle}>Lender Type *</label>
                          <select value={loan.loanTakenFrom} onChange={e => updateLoan(sec.key, loan.id, 'loanTakenFrom', e.target.value as 'B' | 'I')}
                            style={inputStyle}>
                            <option value="B">Bank (B)</option>
                            <option value="I">Institution (I)</option>
                          </select>
                        </div>
                        <div>
                          <label style={labelStyle}>Lender Name *</label>
                          <input type="text" value={loan.bankOrInstnName} onChange={e => updateLoan(sec.key, loan.id, 'bankOrInstnName', e.target.value)}
                            placeholder="e.g., SBI, HDFC, ICICI" maxLength={125} style={inputStyle} />
                        </div>
                        <div>
                          <label style={labelStyle}>Loan Account / Ref No *</label>
                          <input type="text" value={loan.loanAccNo} onChange={e => updateLoan(sec.key, loan.id, 'loanAccNo', e.target.value)}
                            placeholder="Account number" maxLength={20} style={{ ...inputStyle, fontFamily: 'monospace' }} />
                        </div>
                        <div>
                          <label style={labelStyle}>Date of Loan *</label>
                          <input type="date" value={loan.dateOfLoan} onChange={e => updateLoan(sec.key, loan.id, 'dateOfLoan', e.target.value)}
                            style={inputStyle} />
                        </div>
                      </div>
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 10, marginBottom: 12 }}>
                        <div>
                          <label style={labelStyle}>Total Loan Amount (₹) *</label>
                          <input type="number" value={loan.totalLoanAmt || ''} onChange={e => updateLoan(sec.key, loan.id, 'totalLoanAmt', parseFloat(e.target.value) || 0)}
                            placeholder="0" min={0} style={{ ...inputStyle, fontWeight: 600 }} />
                        </div>
                        <div>
                          <label style={labelStyle}>Outstanding Amount (₹) *</label>
                          <input type="number" value={loan.loanOutstandingAmt || ''} onChange={e => updateLoan(sec.key, loan.id, 'loanOutstandingAmt', parseFloat(e.target.value) || 0)}
                            placeholder="0" min={0} style={inputStyle} />
                        </div>
                        <div>
                          <label style={{ ...labelStyle, color: sec.color }}>{sec.interestLabel} (₹) *</label>
                          <input type="number" value={loan.interestAmount || ''} onChange={e => updateLoan(sec.key, loan.id, 'interestAmount', parseFloat(e.target.value) || 0)}
                            placeholder="0" min={0} style={{ ...inputStyle, background: `${sec.color}08`, fontWeight: 600, color: sec.color }} />
                        </div>
                        {sec.showVehicleReg && (
                          <div>
                            <label style={labelStyle}>Vehicle Registration No. *</label>
                            <input type="text" value={loan.vehicleRegNo || ''} onChange={e => updateLoan(sec.key, loan.id, 'vehicleRegNo', e.target.value)}
                              placeholder="e.g., MH01AB1234" maxLength={11} style={{ ...inputStyle, fontFamily: 'monospace', textTransform: 'uppercase' }} />
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}

            {/* Section totals */}
            {loans.length > 0 && (
              <div style={{ marginTop: 8, padding: 12, background: '#e8eaf6', borderRadius: 6, display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
                <div>
                  <span style={{ fontSize: 11, color: '#666' }}>Total Loan: </span>
                  <strong style={{ fontSize: 13 }}>₹{totals.totalLoan.toLocaleString('en-IN')}</strong>
                </div>
                <div>
                  <span style={{ fontSize: 11, color: '#666' }}>Outstanding: </span>
                  <strong style={{ fontSize: 13 }}>₹{totals.totalOutstanding.toLocaleString('en-IN')}</strong>
                </div>
                <div>
                  <span style={{ fontSize: 11, color: '#666' }}>Interest: </span>
                  <strong style={{ fontSize: 13, color: sec.color }}>₹{totals.totalInterest.toLocaleString('en-IN')}</strong>
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};
