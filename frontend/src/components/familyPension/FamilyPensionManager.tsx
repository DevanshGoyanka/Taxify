import React from 'react';
import type { FamilyPensionEntry } from '../../types/scheduleOS';

interface FamilyPensionManagerProps {
  entry: FamilyPensionEntry | null;
  onChange: (entry: FamilyPensionEntry) => void;
}

export function FamilyPensionManager({ entry = null, onChange }: FamilyPensionManagerProps) {
  const grossAmount = entry?.grossAmount || 0;

  return (
    <div>
      <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 12, color: '#7b1fa2', display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ background: '#f3e5f5', color: '#7b1fa2', padding: '2px 8px', borderRadius: 4, fontSize: 10 }}>PEN</span>
        Family Pension
        <span style={{ fontSize: 11, color: '#888', fontWeight: 400 }}>Sec 56(1) | Deduction u/s 57(iia)</span>
      </h3>
      
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <div style={{ flex: 2, minWidth: 160 }}>
          <input type="text" value={entry?.payerName || ''}
            onChange={(e) => onChange({ grossAmount, payerName: e.target.value, relationToPensioner: entry?.relationToPensioner })}
            placeholder="Payer Name"
            style={{ width: '100%', padding: 4, border: '1px solid #ddd', borderRadius: 3, fontSize: 12 }} />
        </div>
        <div style={{ flex: 2, minWidth: 160 }}>
          <input type="text" value={entry?.relationToPensioner || ''}
            onChange={(e) => onChange({ grossAmount, payerName: entry?.payerName, relationToPensioner: e.target.value })}
            placeholder="Relation (e.g. Widow of employee)"
            style={{ width: '100%', padding: 4, border: '1px solid #ddd', borderRadius: 3, fontSize: 12 }} />
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, flex: 1 }}>
          <span style={{ fontSize: 10, color: '#888' }}>₹</span>
          <input type="number" value={grossAmount || ''}
            onChange={(e) => onChange({ grossAmount: parseFloat(e.target.value) || 0, payerName: entry?.payerName, relationToPensioner: entry?.relationToPensioner })}
            placeholder="Gross Pension"
            style={{ width: '100%', padding: 4, border: '1px solid #ddd', borderRadius: 3, fontSize: 12 }} />
        </div>
      </div>
    </div>
  );
}
