// Section 80C Investment Manager — CBDT AY 2026-27 COMPLIANT
// Schedule80CDtls[] = { IdentificationNo, Amount } per investment
// Cap: ₹1,50,000 aggregate across all 80C investments
// Matches DonationEntryManager UI style: collapsible cards with type badges.

import React, { useState, useMemo } from 'react';
import { IndianNumberInput } from './IndianNumberInput';

interface Investment80C {
  id: string;
  investmentType: string;
  identificationNo: string;
  accountOrPolicyNo: string;
  amount: number;
  dateOfInvestment: string;
  institutionName: string;
  institutionPAN: string;
}

const INVESTMENT_TYPES: Record<string, { label: string; color: string }> = {
  'EPF':     { label: 'Employees Provident Fund',      color: '#1565c0' },
  'VPF':     { label: 'Voluntary Provident Fund',       color: '#0d47a1' },
  'PPF':     { label: 'Public Provident Fund',          color: '#2e7d32' },
  'ELSS':    { label: 'ELSS Mutual Fund',               color: '#ef6c00' },
  'LIC':     { label: 'Life Insurance Premium',         color: '#c62828' },
  'NSC':     { label: 'National Savings Certificate',   color: '#00695c' },
  'HomeLoan':{ label: 'Home Loan Principal Repayment',  color: '#4527a0' },
  'Tuition': { label: 'Tuition Fees (Children)',        color: '#00838f' },
  'FD':      { label: 'Tax-Saver Fixed Deposit (5yr)',  color: '#4e342e' },
  'ULIP':    { label: 'ULIP Premium',                   color: '#37474f' },
  'SSY':     { label: 'Sukanya Samriddhi Yojana',       color: '#ad1457' },
  'OTHER':   { label: 'Other 80C Investment',           color: '#78909c' },
};

export interface Section80CData {
  investments: Investment80C[];
}

interface Section80CManagerProps {
  data: Section80CData;
  onChange: (data: Section80CData) => void;
  /** Authoritative 80C eligible amount from the backend engine
   *  (section_80c aggregator with ₹1.5L ceiling). */
  backendEligible?: number | null;
}

let _invIdCounter = 1;
const nextInvId = (): string => `80c-${Date.now()}-${_invIdCounter++}`;

const labelStyle: React.CSSProperties = { display: 'block', marginBottom: 3, fontSize: 11, fontWeight: 600, color: '#555' };
const inputStyle: React.CSSProperties = { width: '100%', padding: '6px 8px', border: '1px solid #ddd', borderRadius: 4, fontSize: 12, boxSizing: 'border-box' };

export const Section80CManager: React.FC<Section80CManagerProps> = ({ data, onChange, backendEligible }) => {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const addInvestment = () => {
    const inv: Investment80C = {
      id: nextInvId(), investmentType: 'EPF', identificationNo: '', accountOrPolicyNo: '',
      amount: 0, dateOfInvestment: '', institutionName: '', institutionPAN: '',
    };
    onChange({ investments: [...(data.investments || []), inv] });
    setExpandedId(inv.id);
  };

  const removeInvestment = (id: string) => {
    onChange({ investments: (data.investments || []).filter(i => i.id !== id) });
    if (expandedId === id) setExpandedId(null);
  };

  const updateInvestment = (id: string, field: keyof Investment80C, value: unknown) => {
    onChange({ investments: (data.investments || []).map(i => i.id === id ? { ...i, [field]: value } : i) });
  };

  const toggleExpand = (id: string) => { setExpandedId(expandedId === id ? null : id); };

  const totalAmount = useMemo(() => (data.investments || []).reduce((s, i) => s + i.amount, 0), [data]);

  const investments = data.investments || [];

  return (
    <div style={{ fontFamily: 'system-ui, sans-serif' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <div>
          <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>Schedule 80C — Investments (Max ₹1,50,000)</h3>
          <p style={{ margin: '4px 0 0', fontSize: 11, color: '#666' }}>Per-investment details with identification number. Capped at ₹1.5L aggregate.</p>
        </div>
        <button onClick={addInvestment} style={{ background: '#4CAF50', color: 'white', border: 'none', padding: '8px 16px', borderRadius: 4, cursor: 'pointer', fontSize: 13, fontWeight: 600 }}>
          + Add Investment
        </button>
      </div>

      {investments.length === 0 && (
        <div style={{ textAlign: 'center', padding: 40, color: '#999', background: '#fafafa', borderRadius: 8, border: '1px dashed #ddd' }}>
          <div style={{ fontSize: 32, marginBottom: 8 }}>💰</div>
          <div style={{ fontSize: 13 }}>No 80C investments added.</div>
          <div style={{ fontSize: 11, marginTop: 4 }}>Click "+ Add Investment" to add EPF, PPF, LIC, ELSS, etc.</div>
        </div>
      )}

      {investments.map((inv) => {
        const isExpanded = expandedId === inv.id;
        const typeInfo = INVESTMENT_TYPES[inv.investmentType] || INVESTMENT_TYPES['OTHER'];
        return (
          <div key={inv.id} style={{
            background: 'white', border: `1px solid ${isExpanded ? typeInfo.color : '#e0e0e0'}`,
            borderLeft: `4px solid ${typeInfo.color}`, borderRadius: 6, marginBottom: 8, overflow: 'hidden',
          }}>
            <div onClick={() => toggleExpand(inv.id)} style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              padding: '8px 12px', cursor: 'pointer', userSelect: 'none',
              background: isExpanded ? `${typeInfo.color}06` : 'white',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1, minWidth: 0 }}>
                <span style={{ background: typeInfo.color, color: 'white', fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 3, whiteSpace: 'nowrap' }}>
                  {inv.investmentType}
                </span>
                <span style={{ fontSize: 13, fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {typeInfo.label}
                </span>
                {inv.identificationNo && <span style={{ fontSize: 11, color: '#888', fontFamily: 'monospace' }}>{inv.identificationNo}</span>}
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
                <span style={{ fontSize: 13, fontWeight: 600 }}>₹{inv.amount.toLocaleString('en-IN')}</span>
                <span style={{ fontSize: 14, color: '#999', transform: isExpanded ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }}>▾</span>
                <button onClick={(ev) => { ev.stopPropagation(); removeInvestment(inv.id); }} style={{ background: 'transparent', border: 'none', color: '#f44336', fontSize: 16, cursor: 'pointer', padding: '0 2px', lineHeight: 1 }}>×</button>
              </div>
            </div>
            {isExpanded && (
              <div style={{ padding: '12px 14px', borderTop: '1px solid #eee' }}>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 10 }}>
                  <div>
                    <label style={labelStyle}>Investment Type *</label>
                    <select value={inv.investmentType} onChange={e => updateInvestment(inv.id, 'investmentType', e.target.value)} style={inputStyle}>
                      {Object.entries(INVESTMENT_TYPES).map(([k, v]) => (<option key={k} value={k}>{v.label}</option>))}
                    </select>
                  </div>
                  <div>
                    <label style={labelStyle}>Identification No *</label>
                    <input type="text" value={inv.identificationNo || ''} onChange={e => updateInvestment(inv.id, 'identificationNo', e.target.value)}
                      placeholder="Investment identification number" maxLength={50} style={{ ...inputStyle, fontFamily: 'monospace' }} />
                  </div>
                  <div>
                    <label style={labelStyle}>Account / Policy No *</label>
                    <input type="text" value={inv.accountOrPolicyNo || ''} onChange={e => updateInvestment(inv.id, 'accountOrPolicyNo', e.target.value)}
                      placeholder="Policy, PPF, folio or loan account" maxLength={50} style={{ ...inputStyle, fontFamily: 'monospace' }} />
                  </div>
                  <div>
                    <label style={labelStyle}>Date of Investment *</label>
                    <input type="date" value={inv.dateOfInvestment || ''} onChange={e => updateInvestment(inv.id, 'dateOfInvestment', e.target.value)} style={inputStyle} />
                  </div>
                  <div>
                    <label style={labelStyle}>Institution Name *</label>
                    <input type="text" value={inv.institutionName || ''} onChange={e => updateInvestment(inv.id, 'institutionName', e.target.value)}
                      placeholder="Employer / Bank / AMC name" maxLength={125} style={inputStyle} />
                  </div>
                  <div>
                    <label style={labelStyle}>Institution PAN *</label>
                    <input type="text" value={inv.institutionPAN || ''} onChange={e => updateInvestment(inv.id, 'institutionPAN', e.target.value.toUpperCase().slice(0, 10))}
                      placeholder="ABCDE1234F" maxLength={10} style={{ ...inputStyle, fontFamily: 'monospace', textTransform: 'uppercase' }} />
                  </div>
                  <div>
                    <label style={{ ...labelStyle, color: '#2e7d32' }}>Amount (₹) *</label>
                    <IndianNumberInput value={inv.amount || 0} onChange={v => updateInvestment(inv.id, 'amount', v)}
                      style={{ ...inputStyle, fontWeight: 600, color: '#2e7d32' }} />
                  </div>
                </div>
              </div>
            )}
          </div>
        );
      })}

      {investments.length > 0 && (
        <div style={{ marginTop: 14, padding: 12, background: '#e8f5e9', borderRadius: 6, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: 11, color: '#666' }}>Total invested: <strong>₹{totalAmount.toLocaleString('en-IN')}</strong></span>
          <span style={{ fontWeight: 700, fontSize: 16, color: '#2e7d32' }}>
            {backendEligible == null ? 'Eligible: awaiting backend calculation' : `Eligible: ₹${backendEligible.toLocaleString('en-IN')}`}
          </span>
        </div>
      )}
    </div>
  );
};
