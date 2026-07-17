// Bank Interest Entry Manager - CBDT Compliant
import React, { useState } from 'react';

interface BankInterestEntry {
  bankName: string;
  accountType: string;
  accountNumber: string;
  ifscCode?: string;
  interestEarned: number;
  tdsDeducted: number;
  section: string;
}

interface BankInterestEntryManagerProps {
  entries: BankInterestEntry[];
  onChange: (entries: BankInterestEntry[]) => void;
}

export const BankInterestEntryManager: React.FC<BankInterestEntryManagerProps> = ({ entries, onChange }) => {
  const [editingIndex, setEditingIndex] = useState<number | null>(null);

  const addEntry = () => {
    const newEntry: BankInterestEntry = {
      bankName: '',
      accountType: 'SAVINGS',
      accountNumber: '',
      interestEarned: 0,
      tdsDeducted: 0,
      section: '194A',
    };
    onChange([...entries, newEntry]);
    setEditingIndex(entries.length);
  };

  const removeEntry = (index: number) => {
    onChange(entries.filter((_, i) => i !== index));
  };

  const updateEntry = (index: number, field: keyof BankInterestEntry, value: any) => {
    const updated = [...entries];
    updated[index] = { ...updated[index], [field]: value };
    onChange(updated);
  };

  const getTotalInterest = () => entries.reduce((sum, e) => sum + e.interestEarned, 0);
  const getTotalTDS = () => entries.reduce((sum, e) => sum + e.tdsDeducted, 0);
  const getSavingsInterest = () => entries.filter(e => e.accountType === 'SAVINGS').reduce((sum, e) => sum + e.interestEarned, 0);
  const getDepositInterest = () => entries.filter(e => e.accountType === 'FD' || e.accountType === 'RD').reduce((sum, e) => sum + e.interestEarned, 0);

  return (
    <div style={{ padding: 20, background: '#f9f9f9', borderRadius: 8 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <h3 style={{ margin: 0 }}>Bank Interest Details</h3>
          <span style={{ background: '#4CAF50', color: 'white', padding: '2px 8px', borderRadius: 4, fontSize: 10, fontWeight: 600 }}>
            Sec 194A
          </span>
        </div>
        <button onClick={addEntry} style={{ background: '#4CAF50', color: 'white', border: 'none', padding: '10px 20px', borderRadius: 4, cursor: 'pointer' }}>
          + Add Bank Account
        </button>
      </div>

      {entries.length === 0 && (
        <div style={{ textAlign: 'center', padding: 40, color: '#666' }}>
          No bank accounts added. Click "Add Bank Account" to add interest details.
        </div>
      )}

      {entries.map((entry, index) => (
        <div key={index} style={{ background: 'white', border: '1px solid #ddd', borderRadius: 8, padding: 20, marginBottom: 15 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 15 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ background: entry.accountType === 'SAVINGS' ? '#2196F3' : '#FF9800', color: 'white', padding: '5px 10px', borderRadius: 4, fontSize: 14 }}>
                {entry.accountType}
              </span>
              <span style={{ background: '#e3f2fd', color: '#1565c0', padding: '4px 8px', borderRadius: 4, fontSize: 11, fontWeight: 600 }}>
                Sec {entry.section || '194A'}
              </span>
            </div>
            <button onClick={() => removeEntry(index)} style={{ background: '#f44336', color: 'white', border: 'none', width: 30, height: 30, borderRadius: '50%', cursor: 'pointer', fontSize: 20 }}>
              ×
            </button>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: 15 }}>
            <div>
              <label style={{ display: 'block', marginBottom: 5, fontWeight: 500 }}>Bank Name *</label>
              <input
                type="text"
                value={entry.bankName}
                onChange={(e) => updateEntry(index, 'bankName', e.target.value)}
                placeholder="e.g., State Bank of India"
                style={{ width: '100%', padding: 8, border: '1px solid #ddd', borderRadius: 4 }}
              />
            </div>

            <div>
              <label style={{ display: 'block', marginBottom: 5, fontWeight: 500 }}>Account Type *</label>
              <select
                value={entry.accountType}
                onChange={(e) => updateEntry(index, 'accountType', e.target.value)}
                style={{ width: '100%', padding: 8, border: '1px solid #ddd', borderRadius: 4 }}
              >
                <option value="SAVINGS">Savings Account</option>
                <option value="FD">Fixed Deposit</option>
                <option value="RD">Recurring Deposit</option>
                <option value="CURRENT">Current Account</option>
              </select>
            </div>

            <div>
              <label style={{ display: 'block', marginBottom: 5, fontWeight: 500 }}>Section</label>
              <select
                value={entry.section || '194A'}
                onChange={(e) => updateEntry(index, 'section', e.target.value)}
                style={{ width: '100%', padding: 8, border: '1px solid #ddd', borderRadius: 4 }}
              >
                <option value="194A">194A - Interest (other than securities)</option>
                <option value="193">193 - Interest on Securities</option>
                <option value="194K">194K - MF/UTI Income</option>
                <option value="194LB">194LB - Infrastructure Debt Fund</option>
                <option value="194LC">194LC - Interest on Bonds</option>
                <option value="194LD">194LD - Interest on Gov Securities</option>
              </select>
            </div>

            <div>
              <label style={{ display: 'block', marginBottom: 5, fontWeight: 500 }}>Account Number *</label>
              <input
                type="text"
                value={entry.accountNumber}
                onChange={(e) => updateEntry(index, 'accountNumber', e.target.value)}
                placeholder="Account number"
                style={{ width: '100%', padding: 8, border: '1px solid #ddd', borderRadius: 4 }}
              />
            </div>

            <div>
              <label style={{ display: 'block', marginBottom: 5, fontWeight: 500 }}>IFSC Code</label>
              <input
                type="text"
                value={entry.ifscCode || ''}
                onChange={(e) => updateEntry(index, 'ifscCode', e.target.value.toUpperCase())}
                placeholder="e.g., SBIN0001234"
                maxLength={11}
                style={{ width: '100%', padding: 8, border: '1px solid #ddd', borderRadius: 4 }}
              />
            </div>

            <div>
              <label style={{ display: 'block', marginBottom: 5, fontWeight: 500 }}>Interest Earned *</label>
              <input
                type="number"
                value={entry.interestEarned}
                onChange={(e) => updateEntry(index, 'interestEarned', parseFloat(e.target.value) || 0)}
                placeholder="0"
                style={{ width: '100%', padding: 8, border: '1px solid #ddd', borderRadius: 4 }}
              />
            </div>

            <div>
              <label style={{ display: 'block', marginBottom: 5, fontWeight: 500 }}>TDS Deducted</label>
              <input
                type="number"
                value={entry.tdsDeducted}
                onChange={(e) => updateEntry(index, 'tdsDeducted', parseFloat(e.target.value) || 0)}
                placeholder="0"
                style={{ width: '100%', padding: 8, border: '1px solid #ddd', borderRadius: 4 }}
              />
            </div>
          </div>
        </div>
      ))}

      {entries.length > 0 && (
        <div style={{ marginTop: 20, padding: 15, background: '#e3f2fd', borderRadius: 4 }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 15 }}>
            <div>
              <strong>Savings Interest:</strong> ₹{getSavingsInterest().toLocaleString('en-IN')}
            </div>
            <div>
              <strong>Deposit Interest:</strong> ₹{getDepositInterest().toLocaleString('en-IN')}
            </div>
            <div>
              <strong>Total Interest:</strong> ₹{getTotalInterest().toLocaleString('en-IN')}
            </div>
            <div>
              <strong>Total TDS:</strong> ₹{getTotalTDS().toLocaleString('en-IN')}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
