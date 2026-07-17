export default function ReportsPage() {
  return (
    <div>
      <h1 className="crimson" style={{ fontSize: 22, marginBottom: 24 }}>Reports & Analytics</h1>
      <div style={{ background: 'var(--warning-bg)', padding: 16, borderRadius: 'var(--radius)', marginBottom: 24, border: '1px solid var(--warning)' }}>
        🚧 Backend integration coming soon
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
        {['Filing Status Report', 'AIS Mismatch Report', 'Tax Computation Summary', 'Client-wise Report', 'Revenue Report', 'Compliance Report'].map(r => (
          <div key={r} style={{ background: 'white', padding: 20, borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
            <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>{r}</div>
            <button style={{ padding: '6px 12px', background: 'var(--gold)', color: 'white', border: 'none', borderRadius: 6, fontSize: 12, cursor: 'pointer' }}>Generate</button>
          </div>
        ))}
      </div>
    </div>
  );
}
