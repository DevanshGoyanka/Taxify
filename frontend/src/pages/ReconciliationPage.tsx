export default function ReconciliationPage() {
  return (
    <div>
      <h1 className="crimson" style={{ fontSize: 22, marginBottom: 24 }}>Reconciliation</h1>
      
      <div style={{
        background: 'var(--warning-bg)',
        padding: 16,
        borderRadius: 'var(--radius)',
        marginBottom: 24,
        border: '1px solid var(--warning)'
      }}>
        <div style={{ fontWeight: 600, marginBottom: 8 }}>🚧 Backend integration coming soon</div>
        <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
          This feature is being integrated with the backend
        </div>
      </div>

      <div style={{ background: 'white', borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
        <table>
          <thead>
            <tr>
              <th>Client</th>
              <th>Source</th>
              <th>Mismatch Type</th>
              <th>AIS Amount</th>
              <th>ITR Amount</th>
              <th>Difference</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {[
              { client: 'Rajesh Kumar', source: 'Salary', type: 'TDS Mismatch', ais: 850000, itr: 840000, diff: 10000, status: 'Pending' },
              { client: 'Priya Sharma', source: 'Dividend', type: 'Income Not Reported', ais: 25000, itr: 0, diff: 25000, status: 'Review' },
              { client: 'Amit Patel', source: 'Capital Gains', type: 'Rate Difference', ais: 150000, itr: 145000, diff: 5000, status: 'Resolved' }
            ].map((item, idx) => (
              <tr key={idx}>
                <td style={{ fontWeight: 500 }}>{item.client}</td>
                <td>{item.source}</td>
                <td>{item.type}</td>
                <td className="mono">₹{item.ais.toLocaleString('en-IN')}</td>
                <td className="mono">₹{item.itr.toLocaleString('en-IN')}</td>
                <td className="mono" style={{ color: 'var(--danger)' }}>₹{item.diff.toLocaleString('en-IN')}</td>
                <td>
                  <span className={`badge badge-${item.status === 'Resolved' ? 'success' : 'warning'}`}>
                    {item.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
