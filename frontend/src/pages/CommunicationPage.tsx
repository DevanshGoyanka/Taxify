// FUTURE FEATURE — scaffolded but not yet wired into the app.
// Confirmed absent from App.tsx's route table and not imported by anything
// (full-codebase dead-code audit, 2026-09-05). Kept deliberately, not
// dead code to remove — see Docs/CODEBASE_DEAD_CODE_AUDIT_2026_09.md for
// the full list of what this belongs to and why it was kept.
export default function CommunicationPage() {
  return (
    <div>
      <h1 className="crimson" style={{ fontSize: 22, marginBottom: 24 }}>Communication</h1>
      <div style={{ background: 'var(--warning-bg)', padding: 16, borderRadius: 'var(--radius)', marginBottom: 24, border: '1px solid var(--warning)' }}>
        🚧 Backend integration coming soon
      </div>
      <div style={{ background: 'white', padding: 24, borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
        <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 16 }}>Broadcast Message</h3>
        <div style={{ marginBottom: 16 }}>
          <label style={{ display: 'block', marginBottom: 6, fontSize: 13, fontWeight: 500 }}>Template</label>
          <select style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6, fontSize: 13 }}>
            <option>ITR Filing Reminder</option>
            <option>Document Request</option>
            <option>Payment Reminder</option>
          </select>
        </div>
        <div style={{ marginBottom: 16 }}>
          <label style={{ display: 'block', marginBottom: 6, fontSize: 13, fontWeight: 500 }}>Message</label>
          <textarea style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 6, fontSize: 13, minHeight: 100 }} placeholder="Type your message..." />
        </div>
        <button style={{ padding: '8px 16px', background: 'var(--gold)', color: 'white', border: 'none', borderRadius: 6, fontSize: 13, fontWeight: 600, cursor: 'pointer' }}>Send</button>
      </div>
    </div>
  );
}
