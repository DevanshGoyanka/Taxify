export default function BillingPage() {
  return (
    <div>
      <h1 className="crimson" style={{ fontSize: 22, marginBottom: 24 }}>Billing & Fees</h1>
      <div style={{ background: 'var(--warning-bg)', padding: 16, borderRadius: 'var(--radius)', marginBottom: 24, border: '1px solid var(--warning)' }}>
        🚧 Backend integration coming soon
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 24 }}>
        {[{ label: 'Total Billed', value: '₹12,50,000' }, { label: 'Collected', value: '₹9,80,000' }, { label: 'Outstanding', value: '₹2,70,000' }].map(s => (
          <div key={s.label} style={{ background: 'white', padding: 16, borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>{s.label}</div>
            <div className="mono" style={{ fontSize: 20, fontWeight: 600 }}>{s.value}</div>
          </div>
        ))}
      </div>
      <div style={{ background: 'white', borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
        <table>
          <thead><tr><th>Invoice</th><th>Client</th><th>Amount</th><th>Status</th><th>Date</th></tr></thead>
          <tbody>
            {[{ id: 'INV-001', client: 'Rajesh Kumar', amount: 15000, status: 'Paid', date: '2026-04-01' }].map(i => (
              <tr key={i.id}><td className="mono">{i.id}</td><td>{i.client}</td><td className="mono">₹{i.amount.toLocaleString('en-IN')}</td><td><span className="badge badge-success">{i.status}</span></td><td>{i.date}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
