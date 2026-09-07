import React, { useState, useMemo } from 'react';
import type { InterestEntry, InterestITDTag } from '../../types/scheduleOS';
import { INTEREST_TAG_INFO } from '../../types/scheduleOS';
import { IndianNumberInput } from '../IndianNumberInput';

interface InterestEntryManagerProps {
  entries: InterestEntry[];
  onChange: (entries: InterestEntry[]) => void;
}

const generateId = () => Math.random().toString(36).substr(2, 9);

// Group entries by ITD tag
const groupByTag = (entries: InterestEntry[]): Record<InterestITDTag, InterestEntry[]> => {
  return entries.reduce((acc, entry) => {
    if (!acc[entry.itdTag]) acc[entry.itdTag] = [];
    acc[entry.itdTag].push(entry);
    return acc;
  }, {} as Record<InterestITDTag, InterestEntry[]>);
};

const getTagLabel = (tag: InterestITDTag): string => INTEREST_TAG_INFO[tag]?.label || tag;

export function InterestEntryManager({ entries = [], onChange }: InterestEntryManagerProps) {
  const [expandedTag, setExpandedTag] = useState<InterestITDTag | null>(null);
  const [editingEntryId, setEditingEntryId] = useState<string | null>(null);

  // Group entries by ITD tag
  const groupedEntries = useMemo(() => groupByTag(entries), [entries]);

  const addEntry = (itdTag: InterestITDTag) => {
    const newEntry: InterestEntry = {
      id: generateId(),
      itdTag,
      grossAmount: 0,
      tdsDeducted: 0,
    };
    onChange([...entries, newEntry]);
    setExpandedTag(itdTag);
    setEditingEntryId(newEntry.id);
  };

  const updateEntry = (id: string, updates: Partial<InterestEntry>) => {
    onChange(entries.map(e => e.id === id ? { ...e, ...updates } : e));
  };

  const removeEntry = (id: string) => {
    onChange(entries.filter(e => e.id !== id));
    setEditingEntryId(null);
  };

  // Get all ITD tags that have entries or need to be shown
  const usedTags = Object.keys(groupedEntries) as InterestITDTag[];

  return (
    <div>
      <div style={{ marginBottom: 12, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ fontSize: 12, color: '#888' }}>
          <span style={{ color: '#1565c0', fontWeight: 600 }}>ITD Tags 17A-17H</span>
          {' '} | TDS under Sec 194A/194K
        </div>
        <select 
          onChange={(e) => e.target.value && addEntry(e.target.value as InterestITDTag)}
          defaultValue=""
          style={{ padding: '6px 12px', borderRadius: 4, border: '1px solid var(--border)', fontSize: 13 }}
        >
          <option value="">+ Add Interest</option>
          <option value="SAVINGS_BANK">17A - Bank Savings</option>
          <option value="TERM_DEPOSIT">17B - Term Deposit</option>
          <option value="IT_REFUND">17C - IT Refund</option>
          <option value="POST_OFFICE">17D - Post Office</option>
          <option value="NSC">17E - NSC</option>
          <option value="SCSS">17F - SCSS</option>
          <option value="OTHER">17H - Other</option>
        </select>
      </div>

      {/* Render each ITD tag group */}
      {usedTags.map(itdTag => {
        const tagEntries = groupedEntries[itdTag];
        const total = tagEntries.reduce((sum, e) => sum + (e.grossAmount || 0), 0);
        const isExempt = INTEREST_TAG_INFO[itdTag]?.exempt;
        
        return (
          <div key={itdTag} style={{ marginBottom: 8, border: '1px solid var(--border)', borderRadius: 6, overflow: 'hidden' }}>
            <div 
              onClick={() => setExpandedTag(expandedTag === itdTag ? null : itdTag)}
              style={{ 
                padding: '10px 14px', 
                cursor: 'pointer',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                background: isExempt ? 'var(--gold-pale)' : 'transparent'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 12, fontWeight: 600, color: isExempt ? '#2e7d32' : '#1565c0' }}>
                  {getTagLabel(itdTag)}
                </span>
                {isExempt && (
                  <span style={{ fontSize: 10, padding: '1px 5px', background: '#4caf50', color: 'white', borderRadius: 3 }}>EXEMPT</span>
                )}
                <span style={{ fontSize: 11, color: '#888' }}>({tagEntries.length} entry)</span>
              </div>
              <span style={{ fontWeight: 600, fontSize: 13 }}>
                ₹{total.toLocaleString('en-IN')}
              </span>
            </div>

            {expandedTag === itdTag && (
              <div style={{ padding: 12, borderTop: '1px solid var(--border)', background: '#fafafa' }}>
                {tagEntries.map(entry => (
                  <div key={entry.id} style={{ marginBottom: 8, padding: 8, background: 'white', borderRadius: 4, border: '1px solid #eee' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <input type="text" value={entry.bankName || entry.deductorName || ''}
                        onChange={(e) => updateEntry(entry.id, { bankName: e.target.value })}
                        placeholder="Bank / Institution Name"
                        style={{ flex: 3, minWidth: 200, padding: 4, border: '1px solid #ddd', borderRadius: 3, fontSize: 12 }} />
                      <div style={{ display: 'flex', alignItems: 'center', gap: 4, flex: 1 }}>
                        <span style={{ fontSize: 10, color: '#888' }}>₹</span>
                        <IndianNumberInput value={entry.grossAmount || 0}
                          onChange={(v) => updateEntry(entry.id, { grossAmount: v })}
                          style={{ width: '100%', padding: 4, border: '1px solid #ddd', borderRadius: 3, fontSize: 12 }} />
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 4, flex: 1 }}>
                        <span style={{ fontSize: 10, color: '#888' }}>TDS ₹</span>
                        <IndianNumberInput value={entry.tdsDeducted || 0}
                          onChange={(v) => updateEntry(entry.id, { tdsDeducted: v })}
                          style={{ width: '100%', padding: 4, border: '1px solid #ddd', borderRadius: 3, fontSize: 12 }} />
                      </div>
                      <button onClick={() => removeEntry(entry.id)} style={{ padding: '2px 8px', fontSize: 12, border: 'none', borderRadius: 3, color: '#999', background: 'transparent', cursor: 'pointer' }}>✕</button>
                    </div>
                  </div>
                ))}
                <button 
                  onClick={() => addEntry(itdTag)}
                  style={{ marginTop: 8, padding: '6px 12px', fontSize: 11, border: '1px dashed #ccc', borderRadius: 4, background: 'white', color: '#666', cursor: 'pointer', width: '100%' }}
                >
                  + Add another {getTagLabel(itdTag)}
                </button>
              </div>
            )}
          </div>
        );
      })}

      {entries.length === 0 && (
        <div style={{ textAlign: 'center', padding: 20, color: 'var(--text-muted)', background: 'var(--bg)', borderRadius: 6, fontSize: 13 }}>
          No interest entries added. Click "+ Add Interest" above.
        </div>
      )}
    </div>
  );
}
