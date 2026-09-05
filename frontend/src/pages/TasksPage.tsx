// FUTURE FEATURE — scaffolded but not yet wired into the app.
// Confirmed absent from App.tsx's route table and not imported by anything
// (full-codebase dead-code audit, 2026-09-05). Kept deliberately, not
// dead code to remove — see Docs/CODEBASE_DEAD_CODE_AUDIT_2026_09.md for
// the full list of what this belongs to and why it was kept.
export default function TasksPage() {
  return (
    <div>
      <h1 className="crimson" style={{ fontSize: 22, marginBottom: 24 }}>Tasks & Work Queue</h1>
      <div style={{ background: 'var(--warning-bg)', padding: 16, borderRadius: 'var(--radius)', marginBottom: 24, border: '1px solid var(--warning)' }}>
        🚧 Backend integration coming soon
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
        {['To Do', 'In Progress', 'Done'].map(status => (
          <div key={status}>
            <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>{status}</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {[1, 2].map(i => (
                <div key={i} style={{ background: 'white', padding: 12, borderRadius: 6, border: '1px solid var(--border)' }}>
                  <div style={{ fontWeight: 500, fontSize: 13, marginBottom: 4 }}>Task {i}</div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Client: Sample Client</div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
