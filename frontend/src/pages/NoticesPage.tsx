export default function NoticesPage() {
  return (
    <div>
      <h1 className="crimson" style={{ fontSize: 22, marginBottom: 24 }}>Notice Management</h1>
      <div style={{ background: 'var(--warning-bg)', padding: 16, borderRadius: 'var(--radius)', marginBottom: 24, border: '1px solid var(--warning)' }}>
        🚧 Backend integration coming soon
      </div>
      <div style={{ background: 'white', borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
        <table>
          <thead><tr><th>Notice ID</th><th>Client</th><th>Type</th><th>Date</th><th>Due Date</th><th>Status</th></tr></thead>
          <tbody>
            {[{ id: 'N-001', client: 'Rajesh Kumar', type: '143(1)', date: '2026-03-15', due: '2026-04-30', status: 'Pending' }].map(n => (
              <tr key={n.id}><td className="mono">{n.id}</td><td>{n.client}</td><td>{n.type}</td><td>{n.date}</td><td>{n.due}</td><td><span className="badge badge-warning">{n.status}</span></td></tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
