// Capital Gains Transaction Manager - GRID VIEW (CBDT Compliant)
// All calculations performed in backend, frontend ONLY displays results
import React, { useState, useCallback } from 'react';
import {
  calculateCapitalGains,
  calculateExemption,
  type CapitalGainsCalculationRequest,
  type CapitalGainsCalculationResponse,
  type ExemptionCalculationRequest,
  type ExemptionCalculationResponse,
} from '../services/capitalGainsCalculationService';

interface CapitalGainTransaction {
  id?: string;
  assetType: string;
  assetDescription: string;
  purchaseDate: string;
  saleDate: string;
  purchaseCost: number;
  saleCost: number;
  expenses: number;
  costOfImprovement?: number;
  indexedCost?: number;
  fmvJan2018?: number;
  buyerName?: string;
  buyerPAN?: string;
  exemptionSection?: string;
  exemptionClaimed?: number;
  
  // Calculated by backend - read only
  gainType?: string;
  longTerm?: boolean;
  holdingPeriodMonths?: number;
  gain?: number;
  taxableGain?: number;
  taxRate?: number;
  taxPayable?: number;
  exemptionLimit?: number;
  usedIndexation?: boolean;
  costInflationIndexAcquisition?: number;
  costInflationIndexTransfer?: number;
  costOfAcquisition?: number;
  
  // Validation errors from backend
  validationErrors?: string[];
  validationWarnings?: string[];
}

interface CapitalGainsEntryManagerProps {
  entries: CapitalGainTransaction[];
  onChange: (entries: CapitalGainTransaction[]) => void;
}

// Asset type options
const ASSET_TYPE_OPTIONS = [
  { value: 'EQUITY', label: 'Equity (Demat)', description: 'STT paid' },
  { value: 'MUTUAL_FUND', label: 'MF', description: 'STT paid' },
  { value: 'OFF_MARKET', label: 'Off-Market', description: 'No STT' },
  { value: 'IPO', label: 'IPO', description: 'No STT' },
  { value: 'FPO', label: 'FPO', description: 'No STT' },
  { value: 'PREFERENTIAL', label: 'Pref. Allot', description: 'No STT' },
  { value: 'BLOCK_DEAL', label: 'Block Deal', description: 'No STT' },
  { value: 'RIGHT_ISSUE', label: 'Right Issue', description: 'No STT' },
  { value: 'PROPERTY', label: 'Property' },
  { value: 'LAND', label: 'Land' },
  { value: 'GOLD', label: 'Gold' },
  { value: 'BONDS', label: 'Bonds' },
  { value: 'VDA', label: 'VDA/Crypto' },
  { value: 'OTHER', label: 'Other' },
];

const EXEMPTION_OPTIONS = [
  { value: '', label: 'Nil' },
  { value: '54', label: '54' },
  { value: '54EC', label: '54EC' },
  { value: '54F', label: '54F' },
];

export const CapitalGainsEntryManager: React.FC<CapitalGainsEntryManagerProps> = ({
  entries,
  onChange,
}) => {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Calculate a single transaction via backend
  const calculateTransaction = useCallback(async (
    transaction: CapitalGainTransaction
  ): Promise<CapitalGainsCalculationResponse | null> => {
    if (!transaction.purchaseDate || !transaction.saleDate || 
        transaction.purchaseCost === undefined || transaction.saleCost === undefined) {
      return null;
    }
    
    try {
      const request: CapitalGainsCalculationRequest = {
        assetType: transaction.assetType,
        assetDescription: transaction.assetDescription || '',
        purchaseDate: transaction.purchaseDate,
        saleDate: transaction.saleDate,
        purchaseCost: transaction.purchaseCost,
        saleCost: transaction.saleCost,
        transferExpenses: transaction.expenses || 0,
        costOfImprovement: transaction.costOfImprovement || 0,
        fmvAsOn31Jan2018: transaction.fmvJan2018,
        buyerName: transaction.buyerName,
        buyerPAN: transaction.buyerPAN,
        exemptionSection: transaction.exemptionSection,
        exemptionAmount: transaction.exemptionClaimed,
      };

      const result = await calculateCapitalGains(request);
      return result;
    } catch (err) {
      console.error('Error calculating:', err);
      setError('Calculation failed');
      return null;
    }
  }, []);

  // Handle field change with auto-calculation
  const handleFieldChange = useCallback(async (index: number, field: keyof CapitalGainTransaction, value: any) => {
    const updated = [...entries];
    updated[index] = { ...updated[index], [field]: value };
    onChange(updated);
  }, [entries, onChange]);

  // Calculate on blur
  const handleBlur = useCallback(async (index: number) => {
    const entry = entries[index];
    if (!entry.purchaseDate || !entry.saleDate || entry.purchaseCost === undefined || entry.saleCost === undefined) {
      return;
    }

    setIsLoading(true);
    const result = await calculateTransaction(entry);
    setIsLoading(false);

    if (result) {
      const updated = [...entries];
      updated[index] = {
        ...entry,
        gainType: result.gainType,
        longTerm: result.longTerm,
        holdingPeriodMonths: result.holdingPeriodMonths,
        gain: result.gain,
        taxableGain: result.taxableGain,
        taxRate: result.taxRate,
        taxPayable: result.taxPayable,
        exemptionLimit: result.exemptionLimit,
        indexedCost: result.indexedCost,
        usedIndexation: result.usedIndexation,
        costInflationIndexAcquisition: result.costInflationIndexAcquisition,
        costInflationIndexTransfer: result.costInflationIndexTransfer,
        costOfAcquisition: result.costOfAcquisition,
      };
      onChange(updated);
    }
  }, [entries, onChange, calculateTransaction]);

  // Exemption section change
  const handleExemptionChange = useCallback(async (index: number, section: string) => {
    const entry = entries[index];
    const updated = [...entries];
    updated[index] = { ...entry, exemptionSection: section };
    onChange(updated);
  }, [entries, onChange]);

  const addEntry = () => {
    const newEntry: CapitalGainTransaction = {
      assetType: 'EQUITY',
      assetDescription: '',
      purchaseDate: '',
      saleDate: '',
      purchaseCost: 0,
      saleCost: 0,
      expenses: 0,
      gainType: 'STCG_111A',
      longTerm: false,
    };
    onChange([...entries, newEntry]);
  };

  const removeEntry = (index: number) => {
    onChange(entries.filter((_, i) => i !== index));
  };

  // Calculate totals
  const totalGain = entries.reduce((sum, e) => sum + (e.taxableGain || e.gain || 0), 0);
  const totalTax = entries.reduce((sum, e) => sum + (e.taxPayable || 0), 0);
  const totalSTCG111A = entries.filter(e => e.gainType === 'STCG_111A').reduce((sum, e) => sum + (e.taxableGain || e.gain || 0), 0);
  const totalLTCG112A = entries.filter(e => e.gainType === 'LTCG_112A').reduce((sum, e) => sum + (e.taxableGain || e.gain || 0), 0);
  const totalSTCGOther = entries.filter(e => e.gainType === 'STCG_OTHER').reduce((sum, e) => sum + (e.taxableGain || e.gain || 0), 0);
  const totalLTCG112 = entries.filter(e => e.gainType === 'LTCG_112').reduce((sum, e) => sum + (e.taxableGain || e.gain || 0), 0);

  // Format currency
  const formatINR = (num: number) => num ? num.toLocaleString('en-IN') : '-';

  // Table styles
  const tableStyle: React.CSSProperties = {
    width: '100%',
    borderCollapse: 'collapse',
    fontSize: '12px',
    background: 'white',
  };

  const thStyle: React.CSSProperties = {
    padding: '8px 6px',
    textAlign: 'left',
    background: '#1a1a2e',
    color: 'white',
    fontWeight: 600,
    border: '1px solid #ddd',
    whiteSpace: 'nowrap',
  };

  const tdStyle: React.CSSProperties = {
    padding: '4px 6px',
    border: '1px solid #ddd',
    verticalAlign: 'middle',
  };

  const inputStyle: React.CSSProperties = {
    width: '100%',
    padding: '4px 6px',
    border: '1px solid #ddd',
    borderRadius: '4px',
    fontSize: '12px',
  };

  const selectStyle: React.CSSProperties = {
    width: '100%',
    padding: '4px 6px',
    border: '1px solid #ddd',
    borderRadius: '4px',
    fontSize: '12px',
    background: 'white',
  };

  const getGainBadgeStyle = (gainType?: string): React.CSSProperties => {
    if (!gainType) return { background: '#999', color: 'white', padding: '2px 6px', borderRadius: '3px', fontSize: '10px' };
    if (gainType.includes('LTCG')) return { background: '#22c55e', color: 'white', padding: '2px 6px', borderRadius: '3px', fontSize: '10px' };
    return { background: '#f59e0b', color: 'white', padding: '2px 6px', borderRadius: '3px', fontSize: '10px' };
  };

  return (
    <div style={{ padding: 0, background: '#f9f9f9', borderRadius: 8 }}>
      {/* Header */}
      <div style={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center', 
        padding: '12px 16px',
        background: '#1a1a2e',
        borderRadius: '8px 8px 0 0',
      }}>
        <div style={{ color: 'white', display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontWeight: 600, fontSize: 14 }}>Capital Gains Transactions</span>
          <span style={{ fontSize: 11, opacity: 0.8 }}>(All calculations done in backend)</span>
        </div>
        <button 
          onClick={addEntry}
          disabled={isLoading}
          style={{
            background: '#22c55e',
            color: 'white',
            border: 'none',
            padding: '6px 16px',
            borderRadius: 4,
            cursor: isLoading ? 'not-allowed' : 'pointer',
            fontSize: 12,
            fontWeight: 500,
          }}
        >
          + Add
        </button>
      </div>

      {error && (
        <div style={{ padding: 8, background: '#fee', color: '#c00', fontSize: 12 }}>
          {error}
        </div>
      )}

      {/* Summary Row */}
      <div style={{ 
        display: 'grid', 
        gridTemplateColumns: 'repeat(6, 1fr)', 
        gap: 1, 
        background: '#ddd',
        borderBottom: '2px solid #1a1a2e',
      }}>
        {[
          { label: 'STCG 111A', value: totalSTCG111A, color: '#f59e0b' },
          { label: 'LTCG 112A', value: totalLTCG112A, color: '#22c55e' },
          { label: 'STCG Other', value: totalSTCGOther, color: '#f59e0b' },
          { label: 'LTCG 112', value: totalLTCG112, color: '#22c55e' },
          { label: 'Total Gains', value: totalGain, color: '#1a1a2e' },
          { label: 'Total Tax', value: totalTax, color: '#dc2626' },
        ].map((item, i) => (
          <div key={i} style={{ 
            padding: '8px 12px', 
            background: 'white',
            textAlign: 'center',
          }}>
            <div style={{ fontSize: 10, color: '#666', marginBottom: 2 }}>{item.label}</div>
            <div style={{ fontSize: 13, fontWeight: 700, color: item.color }}>
              ₹{formatINR(item.value)}
            </div>
          </div>
        ))}
      </div>

      {/* Table */}
      <div style={{ overflowX: 'auto', maxHeight: '500px', overflowY: 'auto' }}>
        <table style={tableStyle}>
          <thead style={{ position: 'sticky', top: 0, zIndex: 1 }}>
            <tr>
              <th style={{ ...thStyle, width: 40 }}>#</th>
              <th style={{ ...thStyle, width: 70 }}>Asset</th>
              <th style={{ ...thStyle, width: 100 }}>Description</th>
              <th style={{ ...thStyle, width: 90 }}>Purchase Date</th>
              <th style={{ ...thStyle, width: 90 }}>Sale Date</th>
              <th style={{ ...thStyle, width: 80 }}>Purchase Cost</th>
              <th style={{ ...thStyle, width: 80 }}>Sale Price</th>
              <th style={{ ...thStyle, width: 60 }}>Expenses</th>
              <th style={{ ...thStyle, width: 60 }}>Type</th>
              <th style={{ ...thStyle, width: 60 }}>Holding</th>
              <th style={{ ...thStyle, width: 90 }}>Gain</th>
              <th style={{ ...thStyle, width: 80 }}>Taxable</th>
              <th style={{ ...thStyle, width: 50 }}>Rate</th>
              <th style={{ ...thStyle, width: 80 }}>Tax</th>
              <th style={{ ...thStyle, width: 50 }}>Exempt</th>
              <th style={{ ...thStyle, width: 40 }}></th>
            </tr>
          </thead>
          <tbody>
            {entries.length === 0 ? (
              <tr>
                <td colSpan={16} style={{ ...tdStyle, textAlign: 'center', padding: 24, color: '#666' }}>
                  No transactions. Click "+ Add" to add capital gains.
                </td>
              </tr>
            ) : (
              entries.map((entry, index) => (
                <tr key={index} style={{ background: index % 2 === 0 ? '#fff' : '#f8f9fa' }}>
                  <td style={{ ...tdStyle, textAlign: 'center', color: '#888' }}>{index + 1}</td>
                  
                  {/* Asset Type */}
                  <td style={tdStyle}>
                    <select
                      value={entry.assetType}
                      onChange={(e) => handleFieldChange(index, 'assetType', e.target.value)}
                      style={selectStyle}
                    >
                      {ASSET_TYPE_OPTIONS.map(opt => (
                        <option key={opt.value} value={opt.value}>{opt.label}</option>
                      ))}
                    </select>
                  </td>
                  
                  {/* Description */}
                  <td style={tdStyle}>
                    <input
                      type="text"
                      value={entry.assetDescription || ''}
                      onChange={(e) => handleFieldChange(index, 'assetDescription', e.target.value)}
                      placeholder="Details"
                      style={inputStyle}
                    />
                  </td>
                  
                  {/* Purchase Date */}
                  <td style={tdStyle}>
                    <input
                      type="date"
                      value={entry.purchaseDate}
                      onChange={(e) => handleFieldChange(index, 'purchaseDate', e.target.value)}
                      onBlur={() => handleBlur(index)}
                      style={inputStyle}
                    />
                  </td>
                  
                  {/* Sale Date */}
                  <td style={tdStyle}>
                    <input
                      type="date"
                      value={entry.saleDate}
                      onChange={(e) => handleFieldChange(index, 'saleDate', e.target.value)}
                      onBlur={() => handleBlur(index)}
                      style={inputStyle}
                    />
                  </td>
                  
                  {/* Purchase Cost */}
                  <td style={tdStyle}>
                    <input
                      type="number"
                      value={entry.purchaseCost || ''}
                      onChange={(e) => handleFieldChange(index, 'purchaseCost', parseFloat(e.target.value) || 0)}
                      onBlur={() => handleBlur(index)}
                      placeholder="0"
                      style={inputStyle}
                    />
                  </td>
                  
                  {/* Sale Price */}
                  <td style={tdStyle}>
                    <input
                      type="number"
                      value={entry.saleCost || ''}
                      onChange={(e) => handleFieldChange(index, 'saleCost', parseFloat(e.target.value) || 0)}
                      onBlur={() => handleBlur(index)}
                      placeholder="0"
                      style={inputStyle}
                    />
                  </td>
                  
                  {/* Expenses */}
                  <td style={tdStyle}>
                    <input
                      type="number"
                      value={entry.expenses || ''}
                      onChange={(e) => handleFieldChange(index, 'expenses', parseFloat(e.target.value) || 0)}
                      onBlur={() => handleBlur(index)}
                      placeholder="0"
                      style={inputStyle}
                    />
                  </td>
                  
                  {/* Gain Type Badge */}
                  <td style={{ ...tdStyle, textAlign: 'center' }}>
                    <span style={getGainBadgeStyle(entry.gainType)}>
                      {entry.gainType?.replace('STCG_', 'S').replace('LTCG_', 'L') || '-'}
                    </span>
                  </td>
                  
                  {/* Holding Period */}
                  <td style={{ ...tdStyle, textAlign: 'center', color: '#666', fontSize: 11 }}>
                    {entry.holdingPeriodMonths ? `${entry.holdingPeriodMonths}m` : '-'}
                  </td>
                  
                  {/* Gain (calculated) */}
                  <td style={{ ...tdStyle, textAlign: 'right', fontFamily: 'monospace', fontWeight: 500, color: entry.gain && entry.gain > 0 ? '#166534' : entry.gain !== undefined ? '#991b1b' : '#666' }}>
                    {entry.gain !== undefined ? formatINR(Math.round(entry.gain)) : '-'}
                  </td>
                  
                  {/* Taxable Gain */}
                  <td style={{ ...tdStyle, textAlign: 'right', fontFamily: 'monospace', fontWeight: 600, color: entry.taxableGain && entry.taxableGain > 0 ? '#166534' : '#666' }}>
                    {entry.taxableGain !== undefined ? formatINR(Math.round(entry.taxableGain)) : '-'}
                  </td>
                  
                  {/* Tax Rate */}
                  <td style={{ ...tdStyle, textAlign: 'center', fontSize: 11 }}>
                    {entry.taxRate ? `${(entry.taxRate * 100).toFixed(1)}%` : '-'}
                  </td>
                  
                  {/* Tax Payable */}
                  <td style={{ ...tdStyle, textAlign: 'right', fontFamily: 'monospace', fontWeight: 600, color: '#991b1b' }}>
                    {entry.taxPayable !== undefined ? formatINR(Math.round(entry.taxPayable)) : '-'}
                  </td>
                  
                  {/* Exemption Section */}
                  <td style={tdStyle}>
                    <select
                      value={entry.exemptionSection || ''}
                      onChange={(e) => handleExemptionChange(index, e.target.value)}
                      style={selectStyle}
                    >
                      {EXEMPTION_OPTIONS.map(opt => (
                        <option key={opt.value} value={opt.value}>{opt.label}</option>
                      ))}
                    </select>
                  </td>
                  
                  {/* Delete Button */}
                  <td style={{ ...tdStyle, textAlign: 'center' }}>
                    <button
                      onClick={() => removeEntry(index)}
                      style={{
                        background: 'transparent',
                        border: 'none',
                        color: '#ef4444',
                        cursor: 'pointer',
                        fontSize: 16,
                        padding: '2px 6px',
                      }}
                    >
                      ×
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Loading indicator */}
      {isLoading && (
        <div style={{ padding: 8, textAlign: 'center', background: '#e0f2fe', color: '#0369a1', fontSize: 12 }}>
          ⟳ Calculating...
        </div>
      )}
    </div>
  );
};
