// FUTURE FEATURE — scaffolded but not yet wired into the app.
// Confirmed absent from App.tsx's route table and not imported by anything
// (full-codebase dead-code audit, 2026-09-05). Kept deliberately, not
// dead code to remove — see Docs/CODEBASE_DEAD_CODE_AUDIT_2026_09.md for
// the full list of what this belongs to and why it was kept.
export default function JobsPage() {
  return (
    <div>
      <h1 className="crimson" style={{ fontSize: 22, marginBottom: 24 }}>Background Jobs</h1>
      
      <div style={{
        background: 'var(--warning-bg)',
        padding: 16,
        borderRadius: 'var(--radius)',
        marginBottom: 24,
        border: '1px solid var(--warning)'
      }}>
        🚧 Backend integration coming soon
      </div>

      <div style={{ background: 'white', borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
        <table>
          <thead>
            <tr>
              <th>Job ID</th>
              <th>Type</th>
              <th>Status</th>
              <th>Progress</th>
              <th>Started</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {[
              { id: 'JOB-001', type: 'Bulk AIS Import', status: 'Running', progress: 65, started: '10:30 AM' },
              { id: 'JOB-002', type: 'Tax Computation', status: 'Completed', progress: 100, started: '09:15 AM' },
              { id: 'JOB-003', type: 'PDF Generation', status: 'Failed', progress: 45, started: '08:45 AM' }
            ].map((item) => (
              <tr key={item.id}>
                <td className="mono" style={{ fontSize: 12 }}>{item.id}</td>
                <td>{item.type}</td>
                <td>
                  <span className={`badge badge-${item.status === 'Completed' ? 'success' : item.status === 'Running' ? 'info' : 'danger'}`}>
                    {item.status}
                  </span>
                </td>
                <td>
                  <div className="progress-bar" style={{ width: 120 }}>
                    <div className="progress-fill" style={{ width: `${item.progress}%`, background: 'var(--accent-blue)' }} />
                  </div>
                </td>
                <td style={{ fontSize: 12 }}>{item.started}</td>
                <td>
                  <button style={{
                    padding: '4px 8px',
                    background: 'var(--border)',
                    border: 'none',
                    borderRadius: 4,
                    fontSize: 11,
                    cursor: 'pointer'
                  }}>
                    View Logs
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
