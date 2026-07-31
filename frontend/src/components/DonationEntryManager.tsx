// 80G Donation Entry Manager — CBDT AY 2026-27 COMPLIANT
// Mirrors official Schedule80G JSON schema with 4 category breakdown:
//   1. Don100Percent        — 100% eligible, no approval required (PM CARES, CM Relief, etc.)
//   2. Don50PercentNoApprReqd — 50% eligible, no approval required
//   3. Don100PercentApprReqd  — 100% eligible, approval required u/s 80G(5)
//   4. Don50PercentApprReqd   — 50% eligible, approval required u/s 80G(5)
//
// Each category collects DoneeWithPan[] entries with full address per donee
// and cash vs other-mode amount split per the official ITD schema.

import React, { useState, useMemo } from 'react';

// ---- State codes per ITD schema (01–37) ----
const STATE_CODES: Record<string, string> = {
  '01': 'Andaman & Nicobar', '02': 'Andhra Pradesh', '03': 'Arunachal Pradesh',
  '04': 'Assam', '05': 'Bihar', '06': 'Chandigarh',
  '07': 'Dadra & Nagar Haveli', '08': 'Daman & Diu', '09': 'Delhi',
  '10': 'Goa', '11': 'Gujarat', '12': 'Haryana',
  '13': 'Himachal Pradesh', '14': 'Jammu & Kashmir', '15': 'Karnataka',
  '16': 'Kerala', '17': 'Lakshadweep', '18': 'Madhya Pradesh',
  '19': 'Maharashtra', '20': 'Manipur', '21': 'Meghalaya',
  '22': 'Mizoram', '23': 'Nagaland', '24': 'Odisha',
  '25': 'Puducherry', '26': 'Punjab', '27': 'Rajasthan',
  '28': 'Sikkim', '29': 'Tamil Nadu', '30': 'Tripura',
  '31': 'Uttar Pradesh', '32': 'West Bengal', '33': 'Chhattisgarh',
  '34': 'Uttarakhand', '35': 'Jharkhand', '36': 'Telangana',
  '37': 'Ladakh',
};

// ---- 4 official 80G categories ----
type DonationCategory = '100_NO_APPROVAL' | '50_NO_APPROVAL' | '100_APPROVAL_REQD' | '50_APPROVAL_REQD';

const CATEGORY_INFO: Record<DonationCategory, { label: string; shortLabel: string; eligiblePct: number; color: string; schemaKey: string }> = {
  '100_NO_APPROVAL':   { label: '100% — No Approval Required (PM CARES, CM Relief, PMNRF, etc.)', shortLabel: '100% No Appr.', eligiblePct: 100, color: '#2e7d32', schemaKey: 'Don100Percent' },
  '50_NO_APPROVAL':    { label: '50% — No Approval Required (Jawaharlal Nehru Memorial Fund, etc.)', shortLabel: '50% No Appr.', eligiblePct: 50, color: '#1565c0', schemaKey: 'Don50PercentNoApprReqd' },
  '100_APPROVAL_REQD': { label: '100% — Approval Required u/s 80G(5)(vi)', shortLabel: '100% Appr. Reqd', eligiblePct: 100, color: '#ef6c00', schemaKey: 'Don100PercentApprReqd' },
  '50_APPROVAL_REQD':  { label: '50% — Approval Required u/s 80G(5)(vi)', shortLabel: '50% Appr. Reqd', eligiblePct: 50, color: '#6a1b9a', schemaKey: 'Don50PercentApprReqd' },
};

// ---- Per-donee entry (maps to DoneeWithPan + AddressDetail in ITD schema) ----
export interface DoneeEntry {
  id: string;
  category: DonationCategory;
  doneeName: string;               // → DoneeWithPanName (max 125, required)
  doneePAN: string;                // → DoneePAN ([A-Z]{5}[0-9]{4}[A-Z], required)
  arnNumber: string;               // → ArnNbr (max 25, optional)
  // AddressDetail (required by schema)
  addrDetail: string;              // → AddrDetail (max 200, required)
  city: string;                    // → CityOrTownOrDistrict (max 50, required)
  stateCode: string;               // → StateCode (01–37, required)
  pinCode: string;                 // → PinCode (100000–999999, required)
  // Amount split — cash vs other mode
  donationAmtCash: number;         // → DonationAmtCash (required)
  donationAmtOtherMode: number;    // → DonationAmtOtherMode (required)
  // References
  transactionRefNum: string;       // → TransactionRefNum (max 50, optional)
  ifscCode: string;                // → IFSCCode ([A-Z]{4}[0][A-Z0-9]{6}, optional)
  donationDate: string;            // UI-only display field
  receiptNumber: string;           // UI-only display field
  notes: string;                   // Free-text
}

interface CategoryTotals {
  totalCash: number;
  totalOtherMode: number;
  totalDonation: number;
  totalEligible: number;
}

interface DonationEntryManagerProps {
  entries: DoneeEntry[];
  onChange: (entries: DoneeEntry[]) => void;
}

let _doneeIdCounter = 1;
const nextDoneeId = (): string => `d-${Date.now()}-${_doneeIdCounter++}`;

export const DonationEntryManager: React.FC<DonationEntryManagerProps> = ({ entries, onChange }) => {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const addEntry = () => {
    const newEntry: DoneeEntry = {
      id: nextDoneeId(),
      category: '100_NO_APPROVAL',
      doneeName: '',
      doneePAN: '',
      arnNumber: '',
      addrDetail: '',
      city: '',
      stateCode: '',
      pinCode: '',
      donationAmtCash: 0,
      donationAmtOtherMode: 0,
      transactionRefNum: '',
      ifscCode: '',
      donationDate: '',
      receiptNumber: '',
      notes: '',
    };
    onChange([...entries, newEntry]);
    setExpandedId(newEntry.id);
  };

  const removeEntry = (id: string) => {
    onChange(entries.filter(e => e.id !== id));
    if (expandedId === id) setExpandedId(null);
  };

  const updateEntry = (id: string, field: keyof DoneeEntry, value: unknown) => {
    onChange(entries.map(e => e.id === id ? { ...e, [field]: value } : e));
  };

  const toggleExpand = (id: string) => {
    setExpandedId(expandedId === id ? null : id);
  };

  // ---- Category totals ----
  const categoryTotals = useMemo((): Record<DonationCategory, CategoryTotals> => {
    const init = (): CategoryTotals => ({ totalCash: 0, totalOtherMode: 0, totalDonation: 0, totalEligible: 0 });
    const map: Record<DonationCategory, CategoryTotals> = {
      '100_NO_APPROVAL': init(), '50_NO_APPROVAL': init(),
      '100_APPROVAL_REQD': init(), '50_APPROVAL_REQD': init(),
    };
    for (const e of entries) {
      const t = map[e.category];
      t.totalCash += e.donationAmtCash;
      t.totalOtherMode += e.donationAmtOtherMode;
      t.totalDonation += e.donationAmtCash + e.donationAmtOtherMode;
      const eligibleCash = Math.min(e.donationAmtCash, 2000);
      t.totalEligible += Math.round((eligibleCash + e.donationAmtOtherMode) * CATEGORY_INFO[e.category].eligiblePct / 100);
    }
    return map;
  }, [entries]);

  const grandTotalCash = Object.values(categoryTotals).reduce((s, t) => s + t.totalCash, 0);
  const grandTotalOther = Object.values(categoryTotals).reduce((s, t) => s + t.totalOtherMode, 0);
  const grandTotal = grandTotalCash + grandTotalOther;
  const grandEligible = Object.values(categoryTotals).reduce((s, t) => s + t.totalEligible, 0);

  // ---- Shared styles ----
  const labelStyle: React.CSSProperties = {
    display: 'block', marginBottom: 3, fontSize: 11, fontWeight: 600, color: '#555',
  };
  const inputStyle: React.CSSProperties = {
    width: '100%', padding: '6px 8px', border: '1px solid #ddd', borderRadius: 4,
    fontSize: 12, boxSizing: 'border-box',
  };

  return (
    <div style={{ fontFamily: 'system-ui, sans-serif' }}>
      {/* ── Header ── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <div>
          <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>Schedule 80G — Donations</h3>
          <p style={{ margin: '4px 0 0', fontSize: 11, color: '#666' }}>
            Per-donee entries grouped by 4 CBDT categories. Cash donations capped at ₹2,000 per donee.
          </p>
        </div>
        <button onClick={addEntry} style={{
          background: '#4CAF50', color: 'white', border: 'none',
          padding: '8px 16px', borderRadius: 4, cursor: 'pointer', fontSize: 13, fontWeight: 600,
        }}>
          + Add Donee
        </button>
      </div>

      {/* ── Category summary cards ── */}
      {entries.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 10, marginBottom: 16 }}>
          {(Object.keys(CATEGORY_INFO) as DonationCategory[]).map(cat => {
            const t = categoryTotals[cat];
            if (t.totalDonation === 0) return null;
            const ci = CATEGORY_INFO[cat];
            return (
              <div key={cat} style={{
                padding: 10, borderRadius: 6, border: `1px solid ${ci.color}30`,
                background: `${ci.color}08`,
              }}>
                <div style={{ fontSize: 10, fontWeight: 700, color: ci.color, marginBottom: 4 }}>
                  {ci.shortLabel}
                </div>
                <div style={{ fontSize: 12, color: '#333' }}>
                  Donation: <strong>₹{t.totalDonation.toLocaleString('en-IN')}</strong>
                </div>
                <div style={{ fontSize: 12, color: '#333' }}>
                  Eligible: <strong style={{ color: ci.color }}>₹{t.totalEligible.toLocaleString('en-IN')}</strong>
                </div>
                <div style={{ fontSize: 10, color: '#888' }}>
                  Cash: ₹{t.totalCash.toLocaleString('en-IN')} | Other: ₹{t.totalOtherMode.toLocaleString('en-IN')}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* ── Empty state ── */}
      {entries.length === 0 && (
        <div style={{ textAlign: 'center', padding: 40, color: '#999', background: '#fafafa', borderRadius: 8, border: '1px dashed #ddd' }}>
          <div style={{ fontSize: 32, marginBottom: 8 }}>🙏</div>
          <div style={{ fontSize: 13 }}>No 80G donations added yet.</div>
          <div style={{ fontSize: 11, marginTop: 4 }}>
            Click "+ Add Donee" to record donations eligible for deduction under Section 80G.
          </div>
        </div>
      )}

      {/* ── Donee cards ── */}
      {entries.map((entry) => {
        const isExpanded = expandedId === entry.id;
        const ci = CATEGORY_INFO[entry.category];
        const totalAmt = entry.donationAmtCash + entry.donationAmtOtherMode;
        const eligibleCash = entry.donationAmtCash <= 2000 ? entry.donationAmtCash : 0;
        const eligibleAmt = Math.round((eligibleCash + entry.donationAmtOtherMode) * ci.eligiblePct / 100);

        return (
          <div key={entry.id} style={{
            background: 'white', border: `1px solid ${isExpanded ? ci.color : '#e0e0e0'}`,
            borderLeft: `4px solid ${ci.color}`, borderRadius: 6, marginBottom: 10,
            overflow: 'hidden', transition: 'border 0.2s',
          }}>
            {/* ── Collapsed summary row ── */}
            <div
              onClick={() => toggleExpand(entry.id)}
              style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                padding: '10px 14px', cursor: 'pointer', userSelect: 'none',
                background: isExpanded ? `${ci.color}06` : 'white',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, flex: 1, minWidth: 0 }}>
                <span style={{
                  background: ci.color, color: 'white', fontSize: 10, fontWeight: 700,
                  padding: '2px 8px', borderRadius: 3, whiteSpace: 'nowrap',
                }}>
                  {ci.shortLabel}
                </span>
                <span style={{ fontSize: 13, fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {entry.doneeName || '(Unnamed Donee)'}
                </span>
                {entry.doneePAN && (
                  <span style={{ fontSize: 11, color: '#888', fontFamily: 'monospace' }}>{entry.doneePAN}</span>
                )}
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexShrink: 0 }}>
                <span style={{ fontSize: 13, fontWeight: 600 }}>₹{totalAmt.toLocaleString('en-IN')}</span>
                <span style={{ fontSize: 11, color: ci.color }}>Elig: ₹{eligibleAmt.toLocaleString('en-IN')}</span>
                <span style={{ fontSize: 14, color: '#999', transform: isExpanded ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }}>
                  ▾
                </span>
                <button onClick={(ev) => { ev.stopPropagation(); removeEntry(entry.id); }} style={{
                  background: 'transparent', border: 'none', color: '#f44336', fontSize: 18, cursor: 'pointer', padding: '0 2px', lineHeight: 1,
                }} title="Remove donee">×</button>
              </div>
            </div>

            {/* ── Expanded detail form ── */}
            {isExpanded && (
              <div style={{ padding: '14px', borderTop: '1px solid #eee' }}>
                {/* Row 1: Category + Donee Identity */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 10, marginBottom: 12 }}>
                  <div>
                    <label style={labelStyle}>Category *</label>
                    <select value={entry.category}
                      onChange={e => updateEntry(entry.id, 'category', e.target.value as DonationCategory)}
                      style={inputStyle}>
                      {Object.entries(CATEGORY_INFO).map(([k, v]) => (
                        <option key={k} value={k}>{v.label}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label style={labelStyle}>Donee Name *</label>
                    <input type="text" value={entry.doneeName}
                      onChange={e => updateEntry(entry.id, 'doneeName', e.target.value)}
                      placeholder="e.g., PM CARES Fund" maxLength={125}
                      style={inputStyle} />
                  </div>
                  <div>
                    <label style={labelStyle}>Donee PAN *</label>
                    <input type="text" value={entry.doneePAN}
                      onChange={e => updateEntry(entry.id, 'doneePAN', e.target.value.toUpperCase())}
                      placeholder="AAAAA1234A" maxLength={10}
                      style={{ ...inputStyle, fontFamily: 'monospace', textTransform: 'uppercase' }} />
                  </div>
                  <div>
                    <label style={labelStyle}>ARN / 80G Registration No.</label>
                    <input type="text" value={entry.arnNumber}
                      onChange={e => updateEntry(entry.id, 'arnNumber', e.target.value)}
                      placeholder="Donation reference / ARN" maxLength={25}
                      style={inputStyle} />
                  </div>
                </div>

                {/* Row 2: Donee address — required by ITD schema */}
                <div style={{ marginBottom: 10, padding: '8px 10px', background: '#fff8e1', borderRadius: 4, fontSize: 10, color: '#e65100', fontWeight: 600 }}>
                  📍 Donee Address (required — every DoneeWithPan entry must include full address)
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 10, marginBottom: 12 }}>
                  <div style={{ gridColumn: '1 / -1' }}>
                    <label style={labelStyle}>Address *</label>
                    <input type="text" value={entry.addrDetail}
                      onChange={e => updateEntry(entry.id, 'addrDetail', e.target.value)}
                      placeholder="Building, Street, Locality" maxLength={200}
                      style={inputStyle} />
                  </div>
                  <div>
                    <label style={labelStyle}>City / Town / District *</label>
                    <input type="text" value={entry.city}
                      onChange={e => updateEntry(entry.id, 'city', e.target.value)}
                      placeholder="City" maxLength={50}
                      style={inputStyle} />
                  </div>
                  <div>
                    <label style={labelStyle}>State *</label>
                    <select value={entry.stateCode}
                      onChange={e => updateEntry(entry.id, 'stateCode', e.target.value)}
                      style={inputStyle}>
                      <option value="">— Select State —</option>
                      {Object.entries(STATE_CODES).map(([code, name]) => (
                        <option key={code} value={code}>{code} — {name}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label style={labelStyle}>PIN Code *</label>
                    <input type="text" value={entry.pinCode}
                      onChange={e => updateEntry(entry.id, 'pinCode', e.target.value.replace(/\D/g, '').slice(0, 6))}
                      placeholder="6-digit PIN" maxLength={6}
                      style={inputStyle} />
                  </div>
                </div>

                {/* Row 3: Amounts — cash vs other mode split */}
                <div style={{ marginBottom: 10, padding: '8px 10px', background: '#e8f5e9', borderRadius: 4, fontSize: 10, color: '#2e7d32', fontWeight: 600 }}>
                  💰 Donation Amount — Cash vs Bank/Digital (cash max ₹2,000 per donee for 80G)
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 10, marginBottom: 12 }}>
                  <div>
                    <label style={labelStyle}>Cash Amount (₹)</label>
                    <input type="number" value={entry.donationAmtCash || ''}
                      onChange={e => updateEntry(entry.id, 'donationAmtCash', parseFloat(e.target.value) || 0)}
                      placeholder="0" min={0} style={inputStyle} />
                    {entry.donationAmtCash > 2000 && (
                      <span style={{ fontSize: 10, color: '#f44336' }}>⚠ Cash donations &gt; ₹2,000 not eligible for 80G</span>
                    )}
                  </div>
                  <div>
                    <label style={labelStyle}>Bank/Digital Amount (₹)</label>
                    <input type="number" value={entry.donationAmtOtherMode || ''}
                      onChange={e => updateEntry(entry.id, 'donationAmtOtherMode', parseFloat(e.target.value) || 0)}
                      placeholder="0" min={0} style={inputStyle} />
                  </div>
                  <div>
                    <label style={labelStyle}>Total Donation</label>
                    <input type="number" value={totalAmt} disabled
                      style={{ ...inputStyle, background: '#f5f5f5', fontWeight: 700 }} />
                  </div>
                  <div>
                    <label style={{ ...labelStyle, color: ci.color }}>Eligible ({ci.eligiblePct}%)</label>
                    <input type="number" value={eligibleAmt} disabled
                      style={{ ...inputStyle, background: `${ci.color}10`, fontWeight: 700, color: ci.color }} />
                  </div>
                </div>

                {/* Row 4: Reference fields */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 10, marginBottom: 12 }}>
                  <div>
                    <label style={labelStyle}>Transaction Ref. Number</label>
                    <input type="text" value={entry.transactionRefNum}
                      onChange={e => updateEntry(entry.id, 'transactionRefNum', e.target.value)}
                      placeholder="UTR / Cheque no." maxLength={50}
                      style={inputStyle} />
                  </div>
                  <div>
                    <label style={labelStyle}>IFSC Code</label>
                    <input type="text" value={entry.ifscCode}
                      onChange={e => updateEntry(entry.id, 'ifscCode', e.target.value.toUpperCase().slice(0, 11))}
                      placeholder="SBIN0001234" maxLength={11}
                      style={{ ...inputStyle, fontFamily: 'monospace' }} />
                  </div>
                  <div>
                    <label style={labelStyle}>Donation Date</label>
                    <input type="date" value={entry.donationDate}
                      onChange={e => updateEntry(entry.id, 'donationDate', e.target.value)}
                      style={inputStyle} />
                  </div>
                  <div>
                    <label style={labelStyle}>Receipt Number</label>
                    <input type="text" value={entry.receiptNumber}
                      onChange={e => updateEntry(entry.id, 'receiptNumber', e.target.value)}
                      placeholder="Receipt / acknowledgment no." maxLength={50}
                      style={inputStyle} />
                  </div>
                </div>

                {/* Row 5: Notes */}
                <div>
                  <label style={labelStyle}>Notes</label>
                  <input type="text" value={entry.notes}
                    onChange={e => updateEntry(entry.id, 'notes', e.target.value)}
                    placeholder="Any additional notes" maxLength={200}
                    style={inputStyle} />
                </div>
              </div>
            )}
          </div>
        );
      })}

      {/* ── Grand total footer ── */}
      {entries.length > 0 && (
        <div style={{
          marginTop: 14, padding: 12, background: '#e8eaf6', borderRadius: 6,
          display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12,
        }}>
          <div>
            <span style={{ fontSize: 11, color: '#666' }}>Total Cash: </span>
            <strong style={{ fontSize: 13 }}>₹{grandTotalCash.toLocaleString('en-IN')}</strong>
          </div>
          <div>
            <span style={{ fontSize: 11, color: '#666' }}>Total Bank/Digital: </span>
            <strong style={{ fontSize: 13 }}>₹{grandTotalOther.toLocaleString('en-IN')}</strong>
          </div>
          <div>
            <span style={{ fontSize: 11, color: '#666' }}>Gross Donations: </span>
            <strong style={{ fontSize: 14 }}>₹{grandTotal.toLocaleString('en-IN')}</strong>
          </div>
          <div>
            <span style={{ fontSize: 11, color: '#666' }}>Total Eligible Deduction: </span>
            <strong style={{ fontSize: 14, color: '#2e7d32' }}>₹{grandEligible.toLocaleString('en-IN')}</strong>
          </div>
        </div>
      )}
    </div>
  );
};
