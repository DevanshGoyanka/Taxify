import React, { useState, useMemo } from 'react';
import type { DividendSection } from '../../types/scheduleOS';
import { IndianNumberInput } from '../IndianNumberInput';

interface DividendEntryCompat {
  id?: string;
  section?: string;
  grossAmount?: number;
  dividendAmount?: number;
  tdsDeducted?: number;
  companyName?: string;
  companyPAN?: string;
  deductorTAN?: string;
}

interface DividendEntryManagerProps {
  entries: DividendEntryCompat[];
  onChange: (entries: DividendEntryCompat[]) => void;
}

const generateId = () => Math.random().toString(36).substr(2, 9);
const getAmount = (e: DividendEntryCompat) => e.grossAmount || e.dividendAmount || 0;

const getSectionLabel = (section: string | undefined): string => {
  switch (section) {
    case '194': return '194 - Taxable';
    case '10(22e)': return '2(22)(e) - Deemed Dividend';
    case '2(22)(e)': return '2(22)(e) - Deemed Dividend';
    case '10(22f)': return '2(22)(f) - Capital Reduction';
    case '2(22)(f)': return '2(22)(f) - Capital Reduction';
    default: return section || '194';
  }
};

export function DividendEntryManager({ entries = [], onChange }: DividendEntryManagerProps) {
  const [expandedSection, setExpandedSection] = useState<string | null>(null);

  // Group entries by section
  const groupedEntries = useMemo(() => {
    return entries.reduce((acc, entry) => {
      const section = entry.section || '194';
      if (!acc[section]) acc[section] = [];
      acc[section].push(entry);
      return acc;
    }, {} as Record<string, DividendEntryCompat[]>);
  }, [entries]);

  const normalizedEntries = useMemo(() => entries.map(e => ({
    ...e,
    id: e.id || generateId(),
    section: e.section || '194'
  })), [entries]);

  const addEntry = (section: DividendSection) => {
    onChange([...entries, { id: generateId(), section, grossAmount: 0, tdsDeducted: 0, companyName: '' }]);
    setExpandedSection(section);
  };

  const updateEntry = (id: string, updates: Partial<DividendEntryCompat>) => {
    onChange(entries.map(e => e.id === id ? { ...e, ...updates } : e));
  };

  const removeEntry = (id: string) => {
    onChange(entries.filter(e => e.id !== id));
  };

  const usedSections = Object.keys(groupedEntries) as string[];

  return (
    <div>
      <div style={{ marginBottom: 12, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ fontSize: 12, color: '#888' }}>
          <span style={{ color: '#2e7d32', fontWeight: 600 }}>Sec 2(22)(e) / 2(22)(f) / 194</span>
          {' '} | Taxable vs Exempt
        </div>
        <select onChange={(e) => e.target.value && addEntry(e.target.value as DividendSection)} defaultValue=""
          style={{ padding: '6px 12px', borderRadius: 4, border: '1px solid var(--border)', fontSize: 13 }}>
          <option value="">+ Add Dividend</option>
          <option value="194">194 - Taxable</option>
          <option value="10(22e)">2(22)(e) - Deemed Dividend</option>
          <option value="10(22f)">2(22)(f) - Capital Reduction</option>
        </select>
      </div>

      {/* Render each section group */}
      {usedSections.map(section => {
        const sectionEntries = groupedEntries[section];
        const total = sectionEntries.reduce((sum, e) => sum + getAmount(e), 0);
        
        return (
          <div key={section} style={{ marginBottom: 8, border: '1px solid var(--border)', borderRadius: 6, overflow: 'hidden' }}>
            <div 
              onClick={() => setExpandedSection(expandedSection === section ? null : section)}
              style={{ 
                padding: '10px 14px', 
                cursor: 'pointer',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 12, fontWeight: 600 }}>
                  {getSectionLabel(section)}
                </span>
                <span style={{ fontSize: 11, color: '#888' }}>({sectionEntries.length})</span>
              </div>
              <span style={{ fontWeight: 600, fontSize: 13 }}>
                ₹{total.toLocaleString('en-IN')}
              </span>
            </div>

            {expandedSection === section && (
              <div style={{ padding: 12, borderTop: '1px solid var(--border)', background: '#fafafa' }}>
                {sectionEntries.map(entry => (
                  <div key={entry.id} style={{ marginBottom: 8, padding: 8, background: 'white', borderRadius: 4, border: '1px solid #eee' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <input type="text" value={entry.companyName || ''} 
                        onChange={(e) => updateEntry(entry.id!, { companyName: e.target.value })}
                        placeholder="Company Name"
                        style={{ flex: 3, minWidth: 200, padding: 4, border: '1px solid #ddd', borderRadius: 3, fontSize: 12 }} />
                      <div style={{ display: 'flex', alignItems: 'center', gap: 4, flex: 1 }}>
                        <span style={{ fontSize: 10, color: '#888' }}>₹</span>
                        <IndianNumberInput value={getAmount(entry) || 0}
                          onChange={(v) => updateEntry(entry.id!, { grossAmount: v })}
                          style={{ width: '100%', padding: 4, border: '1px solid #ddd', borderRadius: 3, fontSize: 12 }} />
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 4, flex: 1 }}>
                        <span style={{ fontSize: 10, color: '#888' }}>TDS ₹</span>
                        <IndianNumberInput value={entry.tdsDeducted || 0}
                          onChange={(v) => updateEntry(entry.id!, { tdsDeducted: v })}
                          style={{ width: '100%', padding: 4, border: '1px solid #ddd', borderRadius: 3, fontSize: 12 }} />
                      </div>
                      <button onClick={() => removeEntry(entry.id!)} style={{ padding: '2px 8px', fontSize: 12, border: 'none', borderRadius: 3, color: '#999', background: 'transparent', cursor: 'pointer' }}>✕</button>
                    </div>
                  </div>
                ))}
                <button 
                  onClick={() => addEntry(section as DividendSection)}
                  style={{ marginTop: 8, padding: '6px 12px', fontSize: 11, border: '1px dashed #ccc', borderRadius: 4, background: 'white', color: '#666', cursor: 'pointer', width: '100%' }}
                >
                  + Add another {getSectionLabel(section)}
                </button>
              </div>
            )}
          </div>
        );
      })}

      {normalizedEntries.length === 0 && (
        <div style={{ textAlign: 'center', padding: 20, color: 'var(--text-muted)', background: 'var(--bg)', borderRadius: 6, fontSize: 13 }}>
          No dividend entries added. Click "+ Add Dividend" above.
        </div>
      )}
    </div>
  );
}
