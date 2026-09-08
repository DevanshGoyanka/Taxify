import React, { useState } from 'react';
import type { WinningsEntry, WinningsType } from '../../types/scheduleOS';
import { IndianNumberInput } from '../IndianNumberInput';

interface WinningsManagerProps {
  entries: WinningsEntry[];
  onChange: (entries: WinningsEntry[]) => void;
}

const generateId = () => Math.random().toString(36).substr(2, 9);

export function WinningsManager({ entries = [], onChange }: WinningsManagerProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const addEntry = (type: WinningsType) => {
    onChange([...entries, { id: generateId(), type, grossAmount: 0, tdsDeducted: 0 }]);
  };

  const updateEntry = (id: string, updates: Partial<WinningsEntry>) => {
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
          <span style={{ color: '#c62828', fontWeight: 600 }}>Sec 115BB</span>
          {' '} | 30% Flat Tax
        </div>
        <select onChange={(e) => e.target.value && addEntry(e.target.value as WinningsType)} defaultValue=""
          style={{ padding: '6px 12px', borderRadius: 4, border: '1px solid var(--border)', fontSize: 13 }}>
          <option value="">+ Add Winnings</option>
          <option value="LOTTERY">Lottery/Betting</option>
          <option value="CARD_GAME">Card Game</option>
          <option value="HORSE_RACE">Horse Race</option>
        </select>
      </div>

      {entries.map(entry => (
        <div key={entry.id} style={{ marginBottom: 8, border: '1px solid var(--border)', borderRadius: 6, overflow: 'hidden' }}>
          <div onClick={() => setExpandedId(expandedId === entry.id ? null : entry.id)}
            style={{ padding: '10px 14px', cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 10, padding: '2px 6px', background: '#c62828', color: 'white', borderRadius: 3, fontWeight: 600 }}>
                {entry.type === 'LOTTERY' ? '194B' : entry.type === 'HORSE_RACE' ? '194BB' : '194B'}
              </span>
              <span style={{ fontSize: 13 }}>{entry.type === 'LOTTERY' ? 'Lottery/Betting' : entry.type === 'CARD_GAME' ? 'Card Game' : 'Horse Race'}</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <span style={{ fontWeight: 600, fontSize: 13 }}>₹{entry.grossAmount.toLocaleString('en-IN')}</span>
              <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>TDS: ₹{(entry.tdsDeducted || 0).toLocaleString('en-IN')}</span>
              {/* Tax is computed by the backend engine u/s 115BB; the
                  frontend does not perform statutory tax calculations. */}
            </div>
          </div>

          {expandedId === entry.id && (
            <div style={{ padding: 12, borderTop: '1px solid var(--border)', background: '#fafafa' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <div style={{ flex: 1.5, minWidth: 120 }}>
                  <select value={entry.type} onChange={(e) => updateEntry(entry.id, { type: e.target.value as WinningsType })}
                    style={{ width: '100%', padding: 4, border: '1px solid #ddd', borderRadius: 3, fontSize: 12 }}>
                    <option value="LOTTERY">Lottery/Betting</option>
                    <option value="CARD_GAME">Card Game</option>
                    <option value="HORSE_RACE">Horse Race</option>
                  </select>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 4, flex: 1 }}>
                  <span style={{ fontSize: 10, color: '#888' }}>₹</span>
                  <IndianNumberInput value={entry.grossAmount || 0}
                    onChange={(v) => updateEntry(entry.id, { grossAmount: v })}
                    placeholder="Gross Amount"
                    style={{ width: '100%', padding: 4, border: '1px solid #ddd', borderRadius: 3, fontSize: 12 }} />
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 4, flex: 1 }}>
                  <span style={{ fontSize: 10, color: '#888' }}>TDS ₹</span>
                  <IndianNumberInput value={entry.tdsDeducted || 0}
                    onChange={(v) => updateEntry(entry.id, { tdsDeducted: v })}
                    placeholder="TDS"
                    style={{ width: '100%', padding: 4, border: '1px solid #ddd', borderRadius: 3, fontSize: 12 }} />
                </div>
                <button onClick={() => removeEntry(entry.id)}
                  style={{ padding: '2px 8px', fontSize: 12, border: 'none', borderRadius: 3, color: '#999', background: 'transparent', cursor: 'pointer' }}>✕</button>
              </div>
            </div>
          )}
        </div>
      ))}

      {entries.length === 0 && (
        <div style={{ textAlign: 'center', padding: 20, color: 'var(--text-muted)', background: 'var(--bg)', borderRadius: 6, fontSize: 13 }}>
          No winnings added.
        </div>
      )}
    </div>
  );
}
