// 80G Donation Entry Manager - CBDT Compliant
import React, { useState } from 'react';

interface DonationEntry {
  doneeName: string;
  doneePAN: string;
  donee80GNumber?: string;
  donationAmount: number;
  eligiblePercentage: number;
  eligibleAmount: number;
  modeOfPayment: string;
  donationDate?: string;
  receiptNumber?: string;
}

interface DonationEntryManagerProps {
  entries: DonationEntry[];
  onChange: (entries: DonationEntry[]) => void;
}

export const DonationEntryManager: React.FC<DonationEntryManagerProps> = ({ entries, onChange }) => {
  const [editingIndex, setEditingIndex] = useState<number | null>(null);

  const addEntry = () => {
    const newEntry: DonationEntry = {
      doneeName: '',
      doneePAN: '',
      donationAmount: 0,
      eligiblePercentage: 100,
      eligibleAmount: 0,
      modeOfPayment: 'ONLINE',
    };
    onChange([...entries, newEntry]);
    setEditingIndex(entries.length);
  };

  const removeEntry = (index: number) => {
    onChange(entries.filter((_, i) => i !== index));
  };

  const updateEntry = (index: number, field: keyof DonationEntry, value: any) => {
    const updated = [...entries];
    updated[index] = { ...updated[index], [field]: value };
    
    // Auto-calculate eligible amount
    if (field === 'donationAmount' || field === 'eligiblePercentage') {
      const entry = updated[index];
      entry.eligibleAmount = (entry.donationAmount * entry.eligiblePercentage) / 100;
    }
    
    onChange(updated);
  };

  const getTotalDonations = () => entries.reduce((sum, e) => sum + e.donationAmount, 0);
  const getTotalEligible = () => entries.reduce((sum, e) => sum + e.eligibleAmount, 0);

  return (
    <div style={{ padding: 20, background: '#f9f9f9', borderRadius: 8 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <h3 style={{ margin: 0 }}>80G Donations (CBDT Compliant)</h3>
        <button onClick={addEntry} style={{ background: '#4CAF50', color: 'white', border: 'none', padding: '10px 20px', borderRadius: 4, cursor: 'pointer' }}>
          + Add Donation
        </button>
      </div>

      {entries.length === 0 && (
        <div style={{ textAlign: 'center', padding: 40, color: '#666' }}>
          No donations added. Click "Add Donation" to add 80G eligible donations.
        </div>
      )}

      {entries.map((entry, index) => (
        <div key={index} style={{ background: 'white', border: '1px solid #ddd', borderRadius: 8, padding: 20, marginBottom: 15 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 15 }}>
            <span style={{ background: entry.eligiblePercentage === 100 ? '#4CAF50' : '#FF9800', color: 'white', padding: '5px 10px', borderRadius: 4, fontSize: 14 }}>
              {entry.eligiblePercentage}% Eligible
            </span>
            <button onClick={() => removeEntry(index)} style={{ background: '#f44336', color: 'white', border: 'none', width: 30, height: 30, borderRadius: '50%', cursor: 'pointer', fontSize: 20 }}>
              ×
            </button>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: 15 }}>
            <div>
              <label style={{ display: 'block', marginBottom: 5, fontWeight: 500 }}>Donee Name *</label>
              <input
                type="text"
                value={entry.doneeName}
                onChange={(e) => updateEntry(index, 'doneeName', e.target.value)}
                placeholder="e.g., PM CARES Fund"
                style={{ width: '100%', padding: 8, border: '1px solid #ddd', borderRadius: 4 }}
              />
            </div>

            <div>
              <label style={{ display: 'block', marginBottom: 5, fontWeight: 500 }}>Donee PAN *</label>
              <input
                type="text"
                value={entry.doneePAN}
                onChange={(e) => updateEntry(index, 'doneePAN', e.target.value.toUpperCase())}
                placeholder="e.g., AAAAA1234A"
                maxLength={10}
                style={{ width: '100%', padding: 8, border: '1px solid #ddd', borderRadius: 4 }}
              />
            </div>

            <div>
              <label style={{ display: 'block', marginBottom: 5, fontWeight: 500 }}>80G Registration Number</label>
              <input
                type="text"
                value={entry.donee80GNumber || ''}
                onChange={(e) => updateEntry(index, 'donee80GNumber', e.target.value)}
                placeholder="80G registration number"
                style={{ width: '100%', padding: 8, border: '1px solid #ddd', borderRadius: 4 }}
              />
            </div>

            <div>
              <label style={{ display: 'block', marginBottom: 5, fontWeight: 500 }}>Donation Amount *</label>
              <input
                type="number"
                value={entry.donationAmount}
                onChange={(e) => updateEntry(index, 'donationAmount', parseFloat(e.target.value) || 0)}
                placeholder="0"
                style={{ width: '100%', padding: 8, border: '1px solid #ddd', borderRadius: 4 }}
              />
            </div>

            <div>
              <label style={{ display: 'block', marginBottom: 5, fontWeight: 500 }}>Eligible Percentage *</label>
              <select
                value={entry.eligiblePercentage}
                onChange={(e) => updateEntry(index, 'eligiblePercentage', parseFloat(e.target.value))}
                style={{ width: '100%', padding: 8, border: '1px solid #ddd', borderRadius: 4 }}
              >
                <option value={100}>100% (PM CARES, CM Relief, etc.)</option>
                <option value={50}>50% (Other approved funds)</option>
              </select>
            </div>

            <div>
              <label style={{ display: 'block', marginBottom: 5, fontWeight: 500 }}>Mode of Payment *</label>
              <select
                value={entry.modeOfPayment}
                onChange={(e) => updateEntry(index, 'modeOfPayment', e.target.value)}
                style={{ width: '100%', padding: 8, border: '1px solid #ddd', borderRadius: 4 }}
              >
                <option value="ONLINE">Online/UPI</option>
                <option value="CHEQUE">Cheque</option>
                <option value="DD">Demand Draft</option>
                <option value="CASH">Cash (Max ₹2,000)</option>
              </select>
            </div>

            <div>
              <label style={{ display: 'block', marginBottom: 5, fontWeight: 500 }}>Donation Date</label>
              <input
                type="date"
                value={entry.donationDate || ''}
                onChange={(e) => updateEntry(index, 'donationDate', e.target.value)}
                style={{ width: '100%', padding: 8, border: '1px solid #ddd', borderRadius: 4 }}
              />
            </div>

            <div>
              <label style={{ display: 'block', marginBottom: 5, fontWeight: 500 }}>Receipt Number</label>
              <input
                type="text"
                value={entry.receiptNumber || ''}
                onChange={(e) => updateEntry(index, 'receiptNumber', e.target.value)}
                placeholder="Receipt number"
                style={{ width: '100%', padding: 8, border: '1px solid #ddd', borderRadius: 4 }}
              />
            </div>

            <div>
              <label style={{ display: 'block', marginBottom: 5, fontWeight: 500 }}>Eligible Deduction (Computed)</label>
              <input
                type="number"
                value={entry.eligibleAmount}
                disabled
                style={{ width: '100%', padding: 8, border: '1px solid #ddd', borderRadius: 4, background: '#f5f5f5', fontWeight: 'bold' }}
              />
            </div>
          </div>
        </div>
      ))}

      {entries.length > 0 && (
        <div style={{ marginTop: 20, padding: 15, background: '#e3f2fd', borderRadius: 4 }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 15 }}>
            <div>
              <strong>Total Donations:</strong> ₹{getTotalDonations().toLocaleString('en-IN')}
            </div>
            <div>
              <strong>Total Eligible Deduction:</strong> ₹{getTotalEligible().toLocaleString('en-IN')}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
