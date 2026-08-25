// Bank Account Manager - CBDT AY 2026-27 COMPLIANT
import React, { useState } from 'react';

export interface BankAccountEntry {
  id: string;
  bankName: string;
  accountNumber: string;
  ifscCode: string;
  accountType: 'SB' | 'CA' | 'CC' | 'OD' | 'NRO' | 'OTH';
  useForRefund: boolean;
}

export interface BankAccountData {
  accounts: BankAccountEntry[];
}

interface BankAccountManagerProps {
  data: BankAccountData;
  onChange: (data: BankAccountData) => void;
}

const ACCOUNT_TYPES = [
  { value: 'SB', label: 'Savings Bank (SB)', color: '#1565c0' },
  { value: 'CA', label: 'Current Account (CA)', color: '#2e7d32' },
  { value: 'CC', label: 'Cash Credit (CC)', color: '#ef6c00' },
  { value: 'OD', label: 'Overdraft (OD)', color: '#6a1b9a' },
  { value: 'NRO', label: 'Non-Resident Ordinary (NRO)', color: '#00838f' },
  { value: 'OTH', label: 'Others (OTH)', color: '#78909c' },
];

let _accIdCounter = 1;
const nextAccId = (): string => 'acc-' + Date.now() + '-' + (_accIdCounter++);

const labelStyle: React.CSSProperties = { display: 'block', marginBottom: 3, fontSize: 11, fontWeight: 600, color: '#555' };
const inputStyle: React.CSSProperties = { width: '100%', padding: '6px 8px', border: '1px solid #ddd', borderRadius: 4, fontSize: 12, boxSizing: 'border-box' as const };

export const BankAccountManager: React.FC<BankAccountManagerProps> = ({ data, onChange }) => {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const accounts = data.accounts || [];

  const addAccount = () => {
    const newAccount: BankAccountEntry = {
      id: nextAccId(),
      bankName: '',
      accountNumber: '',
      ifscCode: '',
      accountType: 'SB',
      useForRefund: accounts.length === 0,
    };
    onChange({ accounts: [...accounts, newAccount] });
    setExpandedId(newAccount.id);
  };

  const removeAccount = (id: string) => {
    onChange({ accounts: accounts.filter(a => a.id !== id) });
    if (expandedId === id) setExpandedId(null);
  };

  const updateAccount = (id: string, field: keyof BankAccountEntry, value: unknown) => {
    const updated = accounts.map(account => {
      if (field === 'useForRefund' && value === true) {
        return { ...account, useForRefund: account.id === id };
      }
      return account.id === id ? { ...account, [field]: value } : account;
    });
    onChange({ accounts: updated });
  };

  const toggleExpand = (id: string) => { setExpandedId(expandedId === id ? null : id); };

  return (
    <div style={{ fontFamily: 'system-ui, sans-serif' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <div>
          <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>Bank Account Details (Refund)</h3>
          <p style={{ margin: '4px 0 0', fontSize: 11, color: '#666' }}>At least one account must be marked for refund.</p>
        </div>
        <button onClick={addAccount} style={{ background: '#4CAF50', color: 'white', border: 'none', padding: '8px 16px', borderRadius: 4, cursor: 'pointer', fontSize: 13, fontWeight: 600 }}>+ Add Bank Account</button>
      </div>
      {accounts.length === 0 && <div style={{ textAlign: 'center', padding: 40, color: '#999', background: '#fafafa', borderRadius: 8, border: '1px dashed #ddd' }}>No bank accounts added.</div>}
      {accounts.map((account) => {
        const isExpanded = expandedId === account.id;
        const accType = ACCOUNT_TYPES.find(t => t.value === account.accountType) || ACCOUNT_TYPES[0];
        return (
          <div key={account.id} style={{ background: 'white', border: '1px solid ' + (isExpanded ? accType.color : '#e0e0e0'), borderLeft: '4px solid ' + accType.color, borderRadius: 6, marginBottom: 8, overflow: 'hidden' }}>
            <div onClick={() => toggleExpand(account.id)} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 12px', cursor: 'pointer', background: isExpanded ? accType.color + '06' : 'white' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ background: accType.color, color: 'white', fontSize: 10, padding: '2px 8px', borderRadius: 3 }}>{account.accountType}</span>
                <span style={{ fontSize: 13, fontWeight: 600 }}>{account.bankName || '(Unnamed Bank)'}</span>
                {account.useForRefund && <span style={{ background: '#2e7d32', color: 'white', fontSize: 9, padding: '1px 6px', borderRadius: 3 }}>PRIMARY</span>}
              </div>
              <button onClick={(ev) => { ev.stopPropagation(); removeAccount(account.id); }} style={{ background: 'transparent', border: 'none', color: '#f44336', fontSize: 16, cursor: 'pointer' }}>x</button>
            </div>
            {isExpanded && (
              <div style={{ padding: '12px 14px', borderTop: '1px solid #eee' }}>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 10 }}>
                  <div><label style={labelStyle}>Bank Name *</label><input type="text" value={account.bankName} onChange={(e) => updateAccount(account.id, 'bankName', e.target.value)} placeholder="e.g., SBI" maxLength={125} style={inputStyle} /></div>
                  <div><label style={labelStyle}>Account Number *</label><input type="text" value={account.accountNumber} onChange={(e) => updateAccount(account.id, 'accountNumber', e.target.value)} placeholder="Account number" maxLength={20} style={{ ...inputStyle, fontFamily: 'monospace' }} /></div>
                  <div><label style={labelStyle}>IFSC Code *</label><input type="text" value={account.ifscCode} onChange={(e) => updateAccount(account.id, 'ifscCode', e.target.value.toUpperCase().slice(0, 11))} placeholder="SBIN0001234" maxLength={11} style={{ ...inputStyle, fontFamily: 'monospace', textTransform: 'uppercase' }} /></div>
                  <div><label style={labelStyle}>Account Type *</label><select value={account.accountType} onChange={(e) => updateAccount(account.id, 'accountType', e.target.value)} style={inputStyle}>{ACCOUNT_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}</select></div>
                  <div style={{ display: 'flex', alignItems: 'center', paddingTop: 20 }}><label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: 12 }}><input type="checkbox" checked={account.useForRefund} onChange={(e) => updateAccount(account.id, 'useForRefund', e.target.checked)} style={{ width: 16, height: 16 }} />Use for Refund</label></div>
                </div>
              </div>
            )}
          </div>
        );
      })}
      {accounts.length > 0 && <div style={{ marginTop: 14, padding: 12, background: '#e8eaf6', borderRadius: 6, display: 'flex', justifyContent: 'space-between' }}><span>{accounts.length} account(s)</span><span>Primary: <strong>{accounts.find(a => a.useForRefund)?.bankName || 'None'}</strong></span></div>}
    </div>
  );
};
