import React, { useState } from 'react';
import type { GiftEntry, GiftPropertyType } from '../../types/scheduleOS';

interface GiftPropertyManagerProps {
  entries: GiftEntry[];
  onChange: (entries: GiftEntry[]) => void;
}

const generateId = () => Math.random().toString(36).substr(2, 9);

export function GiftPropertyManager({ entries = [], onChange }: GiftPropertyManagerProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const addEntry = (propertyType: GiftPropertyType) => {
    onChange([...entries, { id: generateId(), propertyType, value: 0 }]);
  };

  const updateEntry = (id: string, updates: Partial<GiftEntry>) => {
    onChange(entries.map(e => e.id === id ? { ...e, ...updates } : e));
  };

  const removeEntry = (id: string) => {
    onChange(entries.filter(e => e.id !== id));
    if (expandedId === id) setExpandedId(null);
  };

  return (
    <div>
      <div style={{ marginBottom: 12, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ fontSize: 12, color: '#888' }}>
          <span style={{ color: '#ef6c00', fontWeight: 600 }}>Sec 56(2)(x)</span>
          {' '} | Taxable above ₹50K
        </div>
        <select onChange={(e) => e.target.value && addEntry(e.target.value as GiftPropertyType)} defaultValue=""
          style={{ padding: '6px 12px', borderRadius: 4, border: '1px solid var(--border)', fontSize: 13 }}>
          <option value="">+ Add Gift</option>
          <option value="IMMOVABLE">Immovable</option>
          <option value="OTHER">Other</option>
        </select>
      </div>

      {entries.map(entry => (
        <div key={entry.id} style={{ marginBottom: 8, border: '1px solid var(--border)', borderRadius: 6, overflow: 'hidden' }}>
          <div onClick={() => setExpandedId(expandedId === entry.id ? null : entry.id)}
            style={{ padding: '10px 14px', cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 10, padding: '2px 6px', background: entry.propertyType === 'IMMOVABLE' ? '#7b1fa2' : '#1976d2', color: 'white', borderRadius: 3, fontWeight: 600 }}>
                {entry.propertyType === 'IMMOVABLE' ? 'Immovable' : 'Other'}
              </span>
              <span style={{ fontSize: 13 }}>{entry.description || entry.donorName || 'Gift'}</span>
            </div>
            <span style={{ fontWeight: 600, fontSize: 13 }}>₹{entry.value.toLocaleString('en-IN')}</span>
          </div>

          {expandedId === entry.id && (
            <div style={{ padding: 12, borderTop: '1px solid var(--border)', background: '#fafafa' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <div style={{ flex: 1.5, minWidth: 120 }}>
                  <select value={entry.propertyType} onChange={(e) => updateEntry(entry.id, { propertyType: e.target.value as GiftPropertyType })}
                    style={{ width: '100%', padding: 4, border: '1px solid #ddd', borderRadius: 3, fontSize: 12 }}>
                    <option value="IMMOVABLE">Immovable</option>
                    <option value="CASH">Cash</option>
                    <option value="MOVABLE">Movable</option>
                    <option value="OTHER">Other</option>
                  </select>
                </div>
                <input type="text" value={entry.donorName || ''}
                  onChange={(e) => updateEntry(entry.id, { donorName: e.target.value })}
                  placeholder="Donor Name"
                  style={{ flex: 2, minWidth: 140, padding: 4, border: '1px solid #ddd', borderRadius: 3, fontSize: 12 }} />
                <div style={{ display: 'flex', alignItems: 'center', gap: 4, flex: 1 }}>
                  <span style={{ fontSize: 10, color: '#888' }}>₹</span>
                  <input type="number" value={entry.value || ''}
                    onChange={(e) => updateEntry(entry.id, { value: parseFloat(e.target.value) || 0 })}
                    placeholder="Value"
                    style={{ width: '100%', padding: 4, border: '1px solid #ddd', borderRadius: 3, fontSize: 12 }} />
                </div>
                <label style={{ fontSize: 11, display: 'flex', alignItems: 'center', gap: 3, whiteSpace: 'nowrap' }}>
                  <input type="checkbox" checked={entry.fromRelative || false}
                    onChange={(e) => updateEntry(entry.id, { fromRelative: e.target.checked })} />
                  Relative
                </label>
                <label style={{ fontSize: 11, display: 'flex', alignItems: 'center', gap: 3, whiteSpace: 'nowrap' }}>
                  <input type="checkbox" checked={entry.receivedOnMarriage || false}
                    onChange={(e) => updateEntry(entry.id, { receivedOnMarriage: e.target.checked })} />
                  Marriage
                </label>
                <button onClick={() => removeEntry(entry.id)}
                  style={{ padding: '2px 8px', fontSize: 12, border: 'none', borderRadius: 3, color: '#999', background: 'transparent', cursor: 'pointer' }}>✕</button>
              </div>
            </div>
          )}
        </div>
      ))}

      {entries.length === 0 && (
        <div style={{ textAlign: 'center', padding: 20, color: 'var(--text-muted)', background: 'var(--bg)', borderRadius: 6, fontSize: 13 }}>
          No gifts added. Gifts above ₹50K from non-relatives are taxable.
        </div>
      )}
    </div>
  );
}
