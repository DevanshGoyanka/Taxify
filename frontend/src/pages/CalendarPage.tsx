export default function CalendarPage() {
  return (
    <div>
      <h1 className="crimson" style={{ fontSize: 22, marginBottom: 24 }}>Compliance Calendar</h1>
      <div style={{ background: 'var(--warning-bg)', padding: 16, borderRadius: 'var(--radius)', marginBottom: 24, border: '1px solid var(--warning)' }}>
        🚧 Backend integration coming soon
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 8 }}>
        {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map(d => (
          <div key={d} style={{ padding: 8, textAlign: 'center', fontWeight: 600, fontSize: 12 }}>{d}</div>
        ))}
        {Array.from({ length: 30 }, (_, i) => (
          <div key={i} style={{ background: 'white', padding: 12, borderRadius: 6, border: '1px solid var(--border)', minHeight: 80 }}>
            <div style={{ fontWeight: 600, marginBottom: 4 }}>{i + 1}</div>
            {i === 14 && <div style={{ fontSize: 10, background: 'var(--danger-bg)', color: 'var(--danger)', padding: 2, borderRadius: 3 }}>ITR Due</div>}
          </div>
        ))}
      </div>
    </div>
  );
}
