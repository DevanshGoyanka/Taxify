export default function SyncPage() {
  return (
    <div>
      <h1 className="crimson" style={{ fontSize: 22, marginBottom: 24 }}>ITD Portal Sync</h1>
      
      <div style={{
        background: 'var(--warning-bg)',
        padding: 16,
        borderRadius: 'var(--radius)',
        marginBottom: 24,
        border: '1px solid var(--warning)'
      }}>
        🚧 Backend integration coming soon
      </div>

      <div style={{ background: 'white', padding: 24, borderRadius: 'var(--radius)', border: '1px solid var(--border)', marginBottom: 24 }}>
        <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 16 }}>Sync Configuration</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 16 }}>
          <div>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}>
              <input type="checkbox" defaultChecked />
              AIS Data
            </label>
          </div>
          <div>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}>
              <input type="checkbox" defaultChecked />
              Form 26AS
            </label>
          </div>
          <div>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}>
              <input type="checkbox" />
              Prefill JSON
            </label>
          </div>
        </div>
        <button style={{
          marginTop: 16,
          padding: '8px 16px',
          background: 'var(--gold)',
          color: 'white',
          border: 'none',
          borderRadius: 6,
          fontSize: 13,
          fontWeight: 600,
          cursor: 'pointer'
        }}>
          Start Sync
        </button>
      </div>

      <div style={{ background: 'white', borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
        <h3 style={{ padding: 20, fontSize: 16, fontWeight: 600, borderBottom: '1px solid var(--border)' }}>Sync History</h3>
        <table>
          <thead>
            <tr>
              <th>Date</th>
              <th>Type</th>
              <th>Clients Synced</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {[
              { date: '2026-04-14 10:30', type: 'AIS + 26AS', clients: 45, status: 'Completed' },
              { date: '2026-04-13 09:15', type: 'AIS Only', clients: 38, status: 'Completed' },
              { date: '2026-04-12 14:20', type: 'Full Sync', clients: 52, status: 'Completed' }
            ].map((item, idx) => (
              <tr key={idx}>
                <td className="mono" style={{ fontSize: 12 }}>{item.date}</td>
                <td>{item.type}</td>
                <td className="mono">{item.clients}</td>
                <td>
                  <span className="badge badge-success">{item.status}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
